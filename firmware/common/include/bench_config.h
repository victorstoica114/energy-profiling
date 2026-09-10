/* Generated from config/experiment.json; do not edit by hand. */
#ifndef BENCH_CONFIG_H
#define BENCH_CONFIG_H
#include <stdint.h>
#if (defined(BENCH_BOARD_ESP32) + defined(BENCH_BOARD_RP2040) + defined(BENCH_BOARD_STM32)) != 1
#error Select exactly one BENCH_BOARD target
#endif
#if defined(BENCH_BOARD_ESP32)
#define BENCH_BOARD_NAME "esp32"
#define BENCH_EXPECTED_CPU_HZ 240000000u
#define BENCH_PIN_RUN 18u
static const uint32_t bench_iterations[12] = {3000u, 3000u, 200u, 200u, 1000u, 1000u, 3000u, 3000u, 50u, 300u, 50u, 1u};
#elif defined(BENCH_BOARD_RP2040)
#define BENCH_BOARD_NAME "rp2040"
#define BENCH_EXPECTED_CPU_HZ 133000000u
#define BENCH_PIN_RUN 2u
static const uint32_t bench_iterations[12] = {3000u, 3000u, 200u, 500u, 100u, 500u, 3000u, 3000u, 20u, 300u, 50u, 1u};
#elif defined(BENCH_BOARD_STM32)
#define BENCH_BOARD_NAME "stm32"
#define BENCH_EXPECTED_CPU_HZ 100000000u
#define BENCH_SIGNAL_GPIO_PORT 2u
#define BENCH_EXPECTED_OSCILLATOR_HZ 16000000u
#define BENCH_PIN_RUN 0u
static const uint32_t bench_iterations[12] = {3000u, 3000u, 200u, 100u, 100u, 500u, 3000u, 3000u, 20u, 300u, 50u, 1u};
#endif
#define BENCH_STARTUP_IDLE_MS 5000u
#define BENCH_INTER_ALGORITHM_IDLE_MS 1000u
#define BENCH_POST_SUITE_IDLE_MS 2000u
#endif
