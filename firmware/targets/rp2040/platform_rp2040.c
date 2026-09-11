#include "bench_platform.h"
#include "bench_config.h"
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/structs/timer.h"
#include "hardware/regs/clocks.h"
#include "hardware/resets.h"
#include "hardware/structs/resets.h"
#include "hardware/structs/clocks.h"
#include "hardware/vreg.h"
#include "hardware/structs/ssi.h"
#include "hardware/structs/vreg_and_chip_reset.h"
#if BENCH_DIAGNOSTICS
#include <stdio.h>
#include "hardware/flash.h"
#include "hardware/sync.h"
#if BENCH_DIAGNOSTIC_USB
#include "pico/stdio_usb.h"
#else
#include "hardware/uart.h"
#endif
#endif

#if BENCH_COMMON_CLOCK_160
_Static_assert(BENCH_EXPECTED_CPU_HZ == 160000000u, "CPU profile mismatch");
#else
_Static_assert(BENCH_EXPECTED_CPU_HZ == 200000000u, "CPU profile mismatch");
#endif
_Static_assert(BENCH_PIN_RUN == 2, "RP2040 RUN pin mismatch");
_Static_assert(PICO_FLASH_SPI_CLKDIV == 4, "RP2040 Flash clock divider mismatch");
enum { RUN_PIN = BENCH_PIN_RUN };
static bool configured;

#if BENCH_DIAGNOSTICS
static bool diagnostic_ready;
static uint32_t diagnostic_flash_jedec_id;
static bool diagnostic_init(void)
{
    /* Read JEDEC identification before enabling either serial transport.
       XIP is temporarily unavailable; core 1 is parked and interrupts masked. */
    const uint8_t command[4] = {0x9f, 0, 0, 0};
    uint8_t response[4] = {0};
    uint32_t interrupt_state = save_and_disable_interrupts();
    flash_do_cmd(command, response, sizeof command);
    restore_interrupts(interrupt_state);
    diagnostic_flash_jedec_id = ((uint32_t)response[1] << 16) |
        ((uint32_t)response[2] << 8) | response[3];
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

void bench_platform_marker(bool high)
{
    /* gpio_put uses an atomic set/clear write and changes only RUN. */
    __asm__ volatile ("dmb" ::: "memory");
    gpio_put(RUN_PIN, high);
    __asm__ volatile ("dmb" ::: "memory");
}

bool bench_platform_check(void)
{
    if (!configured || clock_get_hz(clk_sys) != BENCH_EXPECTED_CPU_HZ || get_core_num() != 0)
        return false;
    if (clock_get_hz(clk_peri) != 48000000u ||
        vreg_get_voltage() != VREG_VOLTAGE_1_15 ||
        !(vreg_and_chip_reset_hw->vreg & VREG_AND_CHIP_RESET_VREG_ROK_BITS) ||
        ssi_hw->baudr != PICO_FLASH_SPI_CLKDIV) return false;
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
    uint32_t target_khz = BENCH_EXPECTED_CPU_HZ / 1000u;
    return khz >= target_khz - target_khz / 1000u &&
        khz <= target_khz + target_khz / 1000u;
}

bool bench_platform_init(void)
{
    gpio_init(RUN_PIN);
    gpio_put(RUN_PIN, 0);
    gpio_set_dir(RUN_PIN, GPIO_OUT);
    /* Pico onboard LED explicitly off. Core 1 is never launched. */
    gpio_init(25); gpio_put(25, 0); gpio_set_dir(25, GPIO_OUT);
    /* The removed board regulator is distinct from this internal core supply.
       Raise DVDD and allow 1 ms settling at the SDK startup clock before raising clk_sys to the selected profile. */
    vreg_set_voltage(VREG_VOLTAGE_1_15);
    busy_wait_at_least_cycles(clock_get_hz(clk_sys) / 1000u);
    if (vreg_get_voltage() != VREG_VOLTAGE_1_15 ||
        !(vreg_and_chip_reset_hw->vreg & VREG_AND_CHIP_RESET_VREG_ROK_BITS)) return false;
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
    char line[320];
    snprintf(line, sizeof line,
        "BENCH CONFIG board=rp2040 diagnostics=1 cpu_hz=%lu peri_hz=%lu vreg_target_mv=1150 vreg_sel=%u vreg_rok=%u flash_div=%lu flash_hz=%lu flash_jedec_id=%06lx clock_profile=%s fpu=software radio=absent core=%u transport=%s check=%u\r\n",
        (unsigned long)clock_get_hz(clk_sys), (unsigned long)clock_get_hz(clk_peri),
        (unsigned)vreg_get_voltage(),
        (unsigned)((vreg_and_chip_reset_hw->vreg & VREG_AND_CHIP_RESET_VREG_ROK_BITS) != 0),
        (unsigned long)ssi_hw->baudr,
        (unsigned long)(ssi_hw->baudr ? clock_get_hz(clk_sys) / ssi_hw->baudr : 0u),
        (unsigned long)diagnostic_flash_jedec_id,
#if BENCH_COMMON_CLOCK_160
        "common160",
#else
        "max_clock",
#endif
        get_core_num(),
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
