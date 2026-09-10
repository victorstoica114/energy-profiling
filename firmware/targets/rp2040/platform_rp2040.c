#include "bench_platform.h"
#include "bench_config.h"
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/structs/timer.h"
#include "hardware/regs/clocks.h"
#include "hardware/resets.h"
#include "hardware/structs/resets.h"
#include "hardware/structs/clocks.h"
#if BENCH_DIAGNOSTICS
#include <stdio.h>
#if BENCH_DIAGNOSTIC_USB
#include "pico/stdio_usb.h"
#else
#include "hardware/uart.h"
#endif
#endif

_Static_assert(BENCH_EXPECTED_CPU_HZ == 133000000u, "CPU profile mismatch");
_Static_assert(BENCH_PIN_RUN == 2 && BENCH_PIN_ID0 == 3 && BENCH_PIN_ID1 == 4 &&
    BENCH_PIN_ID2 == 5 && BENCH_PIN_ID3 == 6 && BENCH_PIN_IDLE == 7 &&
    BENCH_PIN_ERROR == 8 && BENCH_PIN_DONE == 9, "RP2040 contiguous signal map required");
enum { RUN_PIN = BENCH_PIN_RUN, ID_FIRST = BENCH_PIN_ID0, IDLE_PIN = BENCH_PIN_IDLE,
       ERROR_PIN = BENCH_PIN_ERROR, DONE_PIN = BENCH_PIN_DONE };
#define SIGNAL_MASK (0xffu << RUN_PIN)
static bool configured;

#if BENCH_DIAGNOSTICS
static bool diagnostic_ready;
static bool diagnostic_init(void)
{
#if BENCH_DIAGNOSTIC_USB
    if (!stdio_usb_init()) return false;
    absolute_time_t deadline = make_timeout_time_ms(5000);
    while (!stdio_usb_connected() && !time_reached(deadline)) sleep_ms(10);
    if (stdio_usb_connected()) sleep_ms(50); /* Host CDC line-state settle. */
#else
    if (!uart_init(uart0, 115200)) return false;
    uart_set_hw_flow(uart0, false, false);
    uart_set_format(uart0, 8, 1, UART_PARITY_NONE);
    gpio_set_function(0, GPIO_FUNC_UART);
    gpio_set_function(1, GPIO_FUNC_UART);
#endif
    diagnostic_ready = true;
    return true;
}

static void diagnostic_write(const char *line)
{
    if (!diagnostic_ready) return;
#if BENCH_DIAGNOSTIC_USB
    printf("%s", line);
    stdio_flush();
#else
    uart_puts(uart0, line);
    uart_tx_wait_blocking(uart0);
#endif
}

void bench_platform_report(const char *event, unsigned id, unsigned calls, uint32_t digest)
{
    char line[160];
    snprintf(line, sizeof line, "BENCH event=%s id=%u calls=%u digest=%08lx\r\n",
             event, id, calls, (unsigned long)digest);
    diagnostic_write(line);
}
#endif

void bench_platform_signals(unsigned id, bool run, bool idle, bool error, bool done)
{
    gpio_put(RUN_PIN, 0);
    uint32_t bits = ((id & 15u) << ID_FIRST) | ((uint32_t)idle << IDLE_PIN) |
        ((uint32_t)error << ERROR_PIN) | ((uint32_t)done << DONE_PIN);
    gpio_put_masked(SIGNAL_MASK, bits);
    __asm__ volatile ("dmb" ::: "memory");
    gpio_put(RUN_PIN, run);
}

bool bench_platform_check(void)
{
    if (!configured || clock_get_hz(clk_sys) != BENCH_EXPECTED_CPU_HZ || get_core_num() != 0)
        return false;
    uint32_t held_reset = RESETS_RESET_ADC_BITS | RESETS_RESET_UART1_BITS;
#if !BENCH_DIAGNOSTICS || BENCH_DIAGNOSTIC_USB
    held_reset |= RESETS_RESET_UART0_BITS;
#endif
#if !BENCH_DIAGNOSTICS || !BENCH_DIAGNOSTIC_USB
    held_reset |= RESETS_RESET_USBCTRL_BITS;
#endif
    if ((resets_hw->reset & held_reset) != held_reset ||
        (clocks_hw->clk[clk_adc].ctrl & CLOCKS_CLK_ADC_CTRL_ENABLE_BITS)) return false;
#if !BENCH_DIAGNOSTICS || !BENCH_DIAGNOSTIC_USB
    if (clocks_hw->clk[clk_usb].ctrl & CLOCKS_CLK_USB_CTRL_ENABLE_BITS) return false;
#else
    if (clock_get_hz(clk_usb) != 48000000u) return false;
#endif
    /* Independent peripheral counter relative to clk_ref; not an external calibration. */
    uint32_t khz = frequency_count_khz(CLOCKS_FC0_SRC_VALUE_CLK_SYS);
    return khz >= 132867u && khz <= 133133u;
}

bool bench_platform_init(void)
{
    gpio_init_mask(SIGNAL_MASK);
    gpio_put_masked(SIGNAL_MASK, 0);
    gpio_set_dir_out_masked(SIGNAL_MASK);
    /* Pico onboard LED explicitly off. Core 1 is never launched. */
    gpio_init(25); gpio_put(25, 0); gpio_set_dir(25, GPIO_OUT);
    if (!set_sys_clock_khz(BENCH_EXPECTED_CPU_HZ / 1000u, false)) return false;
    reset_block(RESETS_RESET_ADC_BITS | RESETS_RESET_UART0_BITS | RESETS_RESET_UART1_BITS);
#if !BENCH_DIAGNOSTICS || !BENCH_DIAGNOSTIC_USB
    reset_block(RESETS_RESET_USBCTRL_BITS);
    clock_stop(clk_usb);
#endif
    clock_stop(clk_adc);
    gpio_set_function(0, GPIO_FUNC_NULL); gpio_disable_pulls(0);
    gpio_set_function(1, GPIO_FUNC_NULL); gpio_disable_pulls(1);
#if BENCH_DIAGNOSTICS
    if (!diagnostic_init()) return false;
#endif
    configured = true;
    bool valid = bench_platform_check();
#if BENCH_DIAGNOSTICS
    char line[224];
    snprintf(line, sizeof line,
        "BENCH CONFIG board=rp2040 diagnostics=1 cpu_hz=%lu fpu=software radio=absent core=%u transport=%s check=%u\r\n",
        (unsigned long)clock_get_hz(clk_sys), get_core_num(),
#if BENCH_DIAGNOSTIC_USB
        "USB_CDC",
#else
        "UART0_TX0_RX1_115200",
#endif
        (unsigned)valid);
    diagnostic_write(line);
#endif
    return valid;
}

static uint64_t hardware_time_us(void)
{
    uint32_t high, low;
    do {
        high = timer_hw->timerawh;
        low = timer_hw->timerawl;
    } while (high != timer_hw->timerawh);
    return ((uint64_t)high << 32) | low;
}

void bench_platform_wait_ms(uint32_t milliseconds)
{
    /* The free-running hardware timer is read only for a control gap, never RUN timing. */
    uint64_t start = hardware_time_us();
    uint64_t duration = (uint64_t)milliseconds * 1000u;
    while (hardware_time_us() - start < duration) tight_loop_contents();
}

void bench_platform_finish(void)
{
    for (;;) __asm__ volatile ("wfi");
}

int main(void)
{
    bench_main();
    bench_platform_finish();
    return 0;
}
