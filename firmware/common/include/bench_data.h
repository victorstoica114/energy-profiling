#ifndef BENCH_DATA_H
#define BENCH_DATA_H
#include <stdint.h>
#define BENCH_INPUT_BYTES 2048u
extern const uint8_t bench_compression_input[BENCH_INPUT_BYTES];
extern const uint8_t bench_crypto_input[BENCH_INPUT_BYTES];
extern const uint8_t bench_dsp_input[BENCH_INPUT_BYTES];
#endif
