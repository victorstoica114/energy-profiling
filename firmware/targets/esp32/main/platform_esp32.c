#include "bench_platform.h"
#include "bench_config.h"
#include "sdkconfig.h"
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "esp_clk_tree.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "soc/clk_tree_defs.h"
#include "soc/gpio_struct.h"
#include "esp_private/periph_ctrl.h"
#include "hal/uart_ll.h"
#if BENCH_DIAGNOSTICS
#include "driver/uart.h"
#include <stdio.h>
#include <string.h>
#endif

#if CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ != 240
#error "Benchmark requires a fixed 240 MHz CPU"
#endif
#if !CONFIG_FREERTOS_UNICORE || CONFIG_PM_ENABLE || CONFIG_BT_ENABLED
#error "Benchmark requires unicore, PM disabled, and Bluetooth disabled"
#endif
#if CONFIG_ESP_TASK_WDT_EN
#error "Uninterrupted fixed-count kernels require task watchdog disabled"
#endif

_Static_assert(BENCH_EXPECTED_CPU_HZ == 240000000u, "CPU profile mismatch");
_Static_assert(BENCH_PIN_RUN == 18 && BENCH_PIN_ID0 == 19 && BENCH_PIN_ID1 == 21 &&
    BENCH_PIN_ID2 == 22 && BENCH_PIN_ID3 == 23 && BENCH_PIN_IDLE == 25 &&
    BENCH_PIN_ERROR == 26 && BENCH_PIN_DONE == 27, "ESP32 signal map mismatch");
static const unsigned id_pins[4] = {BENCH_PIN_ID0, BENCH_PIN_ID1, BENCH_PIN_ID2, BENCH_PIN_ID3};
enum { RUN_PIN = BENCH_PIN_RUN, IDLE_PIN = BENCH_PIN_IDLE,
       ERROR_PIN = BENCH_PIN_ERROR, DONE_PIN = BENCH_PIN_DONE };
#define SIGNAL_MASK ((1u << RUN_PIN) | (1u << BENCH_PIN_ID0) | (1u << BENCH_PIN_ID1) | \
    (1u << BENCH_PIN_ID2) | (1u << BENCH_PIN_ID3) | (1u << IDLE_PIN) | \
    (1u << ERROR_PIN) | (1u << DONE_PIN))
static gptimer_handle_t gap_timer;
static bool configured;

#if BENCH_DIAGNOSTICS
static bool diagnostic_uart_ready;
static bool diagnostic_init(void)
{
    const uart_config_t serial = {
        .baud_rate = 115200, .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_APB
    };
    if (uart_param_config(UART_NUM_0, &serial) != ESP_OK ||
        uart_set_pin(UART_NUM_0, 1, 3, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE) != ESP_OK ||
        uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0) != ESP_OK) return false;
    diagnostic_uart_ready = true;
    return true;
}

static void diagnostic_write(const char *line)
{
    if (!diagnostic_uart_ready) return;
    size_t length = strlen(line);
    if (uart_write_bytes(UART_NUM_0, line, length) != (int)length ||
        uart_wait_tx_done(UART_NUM_0, pdMS_TO_TICKS(1000)) != ESP_OK) {
        bench_platform_signals(0, false, false, true, false);
        bench_platform_finish();
    }
}

void bench_platform_report(const char *event, unsigned id, unsigned calls, uint32_t digest)
{
    char line[160];
    snprintf(line, sizeof line, "BENCH event=%s id=%u calls=%u digest=%08lx\r\n",
             event, id, calls, (unsigned long)digest);
    diagnostic_write(line);
}
#else
static bool disable_serial(void)
{
    /* No UART driver is installed. Gate inherited ROM/boot UART clocks without
       decrementing an unowned driver's peripheral reference count. */
    PERIPH_RCC_ATOMIC() {
        uart_ll_reset_register(UART_NUM_0);
        uart_ll_enable_bus_clock(UART_NUM_0, false);
        uart_ll_reset_register(UART_NUM_1);
        uart_ll_enable_bus_clock(UART_NUM_1, false);
        uart_ll_reset_register(UART_NUM_2);
        uart_ll_enable_bus_clock(UART_NUM_2, false);
    }
    const gpio_config_t serial_pins = {
        .pin_bit_mask = (1ULL << 1) | (1ULL << 3), .mode = GPIO_MODE_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    return gpio_config(&serial_pins) == ESP_OK;
}
#endif

void bench_platform_signals(unsigned id, bool run, bool idle, bool error, bool done)
{
    /* One bank write makes DONE and final IDLE rise together. Preserve every
       requested high status bit when lowering IDLE later (no DONE glitch). */
    GPIO.out_w1tc = 1u << RUN_PIN;
    uint32_t bits = ((uint32_t)idle << IDLE_PIN) |
        ((uint32_t)error << ERROR_PIN) | ((uint32_t)done << DONE_PIN);
    for (unsigned bit = 0; bit < 4; ++bit)
        bits |= ((id >> bit) & 1u) << id_pins[bit];
    GPIO.out_w1tc = SIGNAL_MASK & ~bits;
    GPIO.out_w1ts = bits;
    __asm__ volatile ("memw" ::: "memory");
    if (run) GPIO.out_w1ts = 1u << RUN_PIN;
}

bool bench_platform_check(void)
{
    uint32_t hz = 0;
    wifi_mode_t unused;
    return configured &&
        esp_clk_tree_src_get_freq_hz(SOC_MOD_CLK_CPU,
            ESP_CLK_TREE_SRC_FREQ_PRECISION_EXACT, &hz) == ESP_OK &&
        hz == BENCH_EXPECTED_CPU_HZ && xPortGetCoreID() == 0 &&
        /* A disconnected AP is insufficient: the driver must be uninitialized. */
        esp_wifi_get_mode(&unused) == ESP_ERR_WIFI_NOT_INIT;
}

bool bench_platform_init(void)
{
#if BENCH_DIAGNOSTICS
    if (!diagnostic_init()) return false;
#else
    if (!disable_serial()) return false;
#endif
    const uint64_t mask = SIGNAL_MASK;
    gpio_config_t pins = {
        .pin_bit_mask = mask, .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    if (gpio_config(&pins) != ESP_OK) return false;
    bench_platform_signals(0, false, false, false, false);
    /* Wi-Fi/Bluetooth stay uninitialized in both profiles. Serial exists only
       in the diagnostic build and all report calls are outside marked windows. */
    gptimer_config_t timer = {
        .clk_src = GPTIMER_CLK_SRC_DEFAULT, .direction = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000
    };
    if (gptimer_new_timer(&timer, &gap_timer) != ESP_OK ||
        gptimer_enable(gap_timer) != ESP_OK) return false;
    /* Volatile input prevents a compile-time-only floating-point test. */
    volatile float a = 1.5f, b = 2.0f;
    volatile float result = a * b + 0.25f;
    if (result != 3.25f) return false;
    configured = true;
    bool valid = bench_platform_check();
#if BENCH_DIAGNOSTICS
    uint32_t hz = 0;
    esp_clk_tree_src_get_freq_hz(SOC_MOD_CLK_CPU, ESP_CLK_TREE_SRC_FREQ_PRECISION_EXACT, &hz);
    char line[224];
    snprintf(line, sizeof line,
        "BENCH CONFIG board=esp32 diagnostics=1 cpu_hz=%lu fpu=single_precision radio=uninitialized core=%u transport=UART0 tx=1 rx=3 baud=115200 check=%u\r\n",
        (unsigned long)hz, (unsigned)xPortGetCoreID(), (unsigned)valid);
    diagnostic_write(line);
#endif
    return valid;
}

void bench_platform_wait_ms(uint32_t milliseconds)
{
    uint64_t count = 0;
    if (!milliseconds) return;
    if (!gap_timer || gptimer_set_raw_count(gap_timer, 0) != ESP_OK ||
        gptimer_start(gap_timer) != ESP_OK) goto fail;
    do {
        if (gptimer_get_raw_count(gap_timer, &count) != ESP_OK) goto fail;
    } while (count < (uint64_t)milliseconds * 1000u);
    if (gptimer_stop(gap_timer) != ESP_OK) goto fail;
    return;
fail:
    bench_platform_signals(0, false, false, true, false);
    bench_platform_finish();
}

void bench_platform_finish(void)
{
    /* Scheduler idle is the final state; no automatic light/deep sleep. */
    vTaskSuspend(NULL);
    for (;;) { __asm__ volatile ("nop"); }
}

void app_main(void)
{
    bench_main();
    bench_platform_finish();
}
