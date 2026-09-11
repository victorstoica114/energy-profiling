/* Generated from config/experiment.json and config/experiment.common160.json; do not edit by hand. */
#ifndef BENCH_CONFIG_H
#define BENCH_CONFIG_H
#include <stdint.h>
#ifndef BENCH_COMMON_CLOCK_160
#define BENCH_COMMON_CLOCK_160 0
#endif
#if BENCH_COMMON_CLOCK_160 != 0 && BENCH_COMMON_CLOCK_160 != 1
#error Invalid clock profile selector
#endif
#if BENCH_COMMON_CLOCK_160
#define BENCH_EXPERIMENT_ID "energy-profiling-v5-common160"
#else
#define BENCH_EXPERIMENT_ID "energy-profiling-v4-max-clock"
#endif
#if (defined(BENCH_BOARD_ESP32) + defined(BENCH_BOARD_RP2040) + defined(BENCH_BOARD_STM32)) != 1
#error Select exactly one BENCH_BOARD target
#endif
#if defined(BENCH_BOARD_ESP32)
#define BENCH_BOARD_NAME "esp32"
#if BENCH_COMMON_CLOCK_160
#define BENCH_EXPECTED_CPU_HZ 160000000u
#else
#define BENCH_EXPECTED_CPU_HZ 240000000u
#endif
#define BENCH_PIN_RUN 18u
static const uint32_t bench_iterations[12] = {3000u, 3000u, 200u, 200u, 1000u, 1000u, 3000u, 3000u, 50u, 300u, 50u, 1u};
#elif defined(BENCH_BOARD_RP2040)
#define BENCH_BOARD_NAME "rp2040"
#if BENCH_COMMON_CLOCK_160
#define BENCH_EXPECTED_CPU_HZ 160000000u
#else
#define BENCH_EXPECTED_CPU_HZ 200000000u
#endif
#define BENCH_PIN_RUN 2u
static const uint32_t bench_iterations[12] = {3000u, 3000u, 200u, 500u, 100u, 500u, 3000u, 3000u, 20u, 300u, 50u, 1u};
#elif defined(BENCH_BOARD_STM32)
#define BENCH_BOARD_NAME "stm32"
#if BENCH_COMMON_CLOCK_160
#define BENCH_EXPECTED_CPU_HZ 160000000u
#else
#define BENCH_EXPECTED_CPU_HZ 180000000u
#endif
#define BENCH_SIGNAL_GPIO_PORT 2u
#define BENCH_EXPECTED_OSCILLATOR_HZ 16000000u
#define BENCH_PIN_RUN 0u
static const uint32_t bench_iterations[12] = {3000u, 3000u, 200u, 100u, 100u, 500u, 3000u, 3000u, 20u, 300u, 50u, 1u};
#endif
#define BENCH_STARTUP_IDLE_MS 5000u
#define BENCH_INTER_ALGORITHM_IDLE_MS 1000u
#define BENCH_POST_SUITE_IDLE_MS 2000u
#endif
