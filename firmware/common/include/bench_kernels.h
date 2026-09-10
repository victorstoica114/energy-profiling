#ifndef BENCH_KERNELS_H
#define BENCH_KERNELS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#define BENCH_MAX_INPUT_BYTES 2048u
#define BENCH_KERNEL_COUNT 12u
enum bench_kernel_id {
    BENCH_RLE=1, BENCH_DELTA, BENCH_LZ77, BENCH_HUFFMAN,
    BENCH_AES128, BENCH_SHA256, BENCH_CHACHA20, BENCH_CRC32,
    BENCH_FFT, BENCH_FIR, BENCH_IIR, BENCH_DCT
};

/* Single non-reentrant workspace. prepare copies the input outside RUN.
 * run resets each kernel's algorithmic state, writes output, and allocates no
 * memory. It must be called exactly N times by the runner between GPIO edges.
 * verify/digest are outside RUN. Verification uses independent decompression or
 * registered golden outputs. Unknown crypto/DSP fixtures return false from
 * verify; prepare/run accept arbitrary <=2048-byte fixtures for host tests.
 * DSP input is 2048 numeric uint8_t samples, never float object bytes.
 */
bool bench_kernel_prepare(unsigned id, const uint8_t *input, size_t len);
bool bench_kernel_run(unsigned id);
bool bench_kernel_verify(unsigned id);
uint32_t bench_kernel_digest(unsigned id);
const char *bench_kernel_name(unsigned id);

/* Read-only last-result access for tests/export; invalid until a successful run.
 * Byte output: all except FFT/DCT; CRC32 is four explicit little-endian bytes.
 * FFT: N float normalized magnitudes; DCT: N signed orthonormal coefficients.
 * LZ77: uint32 LE original length, then (distance,length,[literal]); the literal
 * is absent if a match ends exactly at the original length.
 * Huffman: uint32 LE original length, uint32 LE valid payload bit count,
 * 256 uint8 code lengths, then canonical MSB-first payload (264-byte header).
 */
const uint8_t *bench_kernel_output_bytes(size_t *length);
const float *bench_kernel_output_floats(size_t *count);
size_t bench_kernel_input_length(void);

#ifdef __cplusplus
}
#endif
#endif
