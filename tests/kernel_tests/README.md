# Common kernel implementation and validation

The common C library derives from the recovered `algoritmi.c/.h` authored for the original thesis benchmark. Original scalar algorithms are retained; this is a repaired and versioned workload, not a claim to reproduce the old executable instruction for instruction. The old source is not modified. No vendor crypto or DSP accelerator is selected by these kernels.

The public API is `firmware/common/include/bench_kernels.h`. IDs 1–12 are RLE, Delta, LZ77, Huffman, AES-128, SHA-256, ChaCha20, CRC32, FFT, FIR, IIR, DCT. There is one non-reentrant static workspace. `prepare` copies at most 2048 bytes and recognizes registered golden inputs outside RUN; `run` performs one independent workload execution; `verify` and `digest` execute outside RUN. The runner owns repetition counts and GPIO timing. Output accessors are read-only interfaces used by tests and export.

## Repairs and defined workload

- RLE retains count/value pairs with runs split at 255; maximum 4096 output bytes at the measured input size.
- Delta retains byte differences modulo 256 and returns 2048 bytes. It does not itself reduce the payload size.
- LZ77 retains the original exhaustive search with 255-byte history/lookahead. Its frame starts with four little-endian original-length bytes; each token has distance and match length followed by a literal only if the match did not reach the end. Maximum storage is bounded by `4 + 3*input_length`; overlap matches are supported. The old extra terminal literal is eliminated.
- Huffman retains the original tree-free frequency/branch construction and canonical encoding. The last-symbol sort bug and single-symbol handling are repaired; frequency ties are deterministic. A complete frame has 4-byte LE original length, 4-byte LE valid bit count, 256 code lengths, then MSB-first payload. Header creation is included in RUN. The writer does not initialize a byte beyond the payload. Code lengths are limited to 32; the supported input limit of 2048 makes that sufficient. The decoder and host cost check verify prefix coding and optimal payload length independently.
- AES remains the original scalar AES-128 ECB block processing with PKCS#7 padding and key expansion at each call. A 2048-byte input yields **2064 output bytes**. The shared output workspace has sufficient capacity. The benchmark key is the 16 ASCII bytes of `0123456789abcdef`.
- SHA-256 retains the original transform and padding. Byte-to-word shifts are explicitly unsigned. Success returns 32 within the private function; the public API correctly treats it as a length.
- ChaCha20 retains the scalar 20-round kernel with the original 32-byte benchmark key, 12 zero nonce bytes, and counter reset to 1 per independent call. Word output is serialized explicitly little-endian instead of depending on host byte order.
- CRC32 retains reflected polynomial `0xEDB88320`, initial state and final XOR `0xFFFFFFFF`. Output is four explicitly little-endian bytes.
- FFT retains radix-2 butterflies, float real/imaginary arrays and double twiddle/intermediate arithmetic. Its input is numerical uint8 samples, converted to float, and its output is **float magnitude divided by N**. Stage count is calculated by integer shifts, avoiding a floating `log2` used as an index. Scratch arrays are statically allocated, initialized by each call. **The original per-call malloc/free costs are removed by the approved fixed-workspace design.**
- FIR retains integer taps `[1,2,3,2,1]`, unsigned accumulation, integer division by 9 and a byte output. Initial samples use zero-valued history. It does not become a floating-point workload.
- IIR retains the original, now explicit recurrence `Q((x[n]+2*x[n-1]+x[n-2]+y[n-1]+y[n-2])/4)`, where Q truncates and saturates to `[0,255]`. State starts at zero on each call and feedback uses the quantized prior outputs. The unquantized linear core has denominator `[1,-0.25,-0.25]` and stable poles; its DC gain is 2. It is not a generic interpretation of the old array `[1,1,1]` as denominator coefficients. Double arithmetic remains in the recovered scalar implementation.
- DCT retains the direct O(N²) algorithm with float cosine/accumulation and orthonormal scaling. The DCT-II angle is corrected. Exact integer reduction modulo `4*N` is applied to `k*(2*n+1)` before forming the angle, keeping `cosf`'s argument in `[0,2*pi)` and avoiding large-argument float loss. The result is signed float coefficients without byte clipping.

The kernels use reusable static workspaces and bounded local stack storage. There are no malloc/free calls, output hashing, printing, or intentional delays inside a kernel run. Algorithmic state initialization (including Huffman environment reset and FFT scratch initialization), frame headers, AES key expansion, return/status handling and guard checks remain part of RUN. Output allocation, fixture recognition, golden verification and CRC digest calculation do not.

## Reproducible checks

Run from the project directory:

```text
python tests/kernel_tests/generate_golden.py
python tests/kernel_tests/test_kernels.py
```

The generator uses only Python's standard library. AES is independently implemented with an algebraically generated S-box and general GF matrix multiplication, then checked against a NIST example. ChaCha20 is checked against RFC 8439. SHA-256 and CRC32 use `hashlib` and `zlib`. FFT uses a direct DFT; DCT uses an independent double-precision direct formula. No expected output is generated by calling the measured C kernel. The frozen golden header is shipped with firmware, so firmware does not need Python.

`golden_manifest.json` records input/output SHA-256 hashes and primary reference URLs. The crypto input is xorshift32, seed `0x1A2B3C4D`, low byte after each update. DSP is the approved 128-sample rounded sine period repeated 16 times. Fixture recognition checks every byte. If those inputs change, regenerate references deliberately and update the workload version.

`test_kernels.py` compiles the actual common C sources using an installed GCC with `-O2 -fno-lto -Wall -Wextra -Werror` and compares all 12 functions against independent references. The suite contains 119 data/algorithm cases, input-boundary checks, repeat/reset checks, and deliberate output corruption for all 12 verifiers. It includes direct C checks of the NIST AES and RFC ChaCha20 vectors, complete 2048-byte datasets, compression pathologies, SHA padding boundaries, AES padding lengths, and FFT/DCT analytic signals. These are correctness tests, not host-to-MCU performance estimates.

The C `smoke.c` links the exact project `bench_data.c` rather than reconstructed Python copies. It runs and verifies every kernel twice and emits result digests. Link it with the two common kernel C files, `bench_data.c`, the common include directory and the math library. It has no board-framework dependency.

## Verification contracts

Compression outputs are verified by independent decoding to the original input. FIR and IIR are recomputed using independent integer formulas. AES/SHA/ChaCha/CRC compare full output bytes against registered independent golden results. FFT/DCT compare all numerical outputs to golden float64-derived values, using:

- FFT: `abs(actual-reference) <= 0.0001 + 0.00002*abs(reference)`.
- DCT: `abs(actual-reference) <= 0.01 + 0.00002*abs(reference)`.

All non-finite transform outputs fail. These numerical tolerances are part of the workload version and must be reviewed before measurements; they are not fitted to energy rankings. On the current GCC host, maximum errors across tested cases were approximately `1.34e-6` for FFT and `0.00147` for DCT. Board self-checks must also pass before captures count as valid.

For arbitrary inputs, prepare/run support valid lengths up to 2048. Crypto and transform `verify` deliberately returns false for an unregistered fixture; this prevents a different input from accidentally being accepted against a golden intended for the campaign. The host suite independently verifies those arbitrary edge-case outputs. Compression and filter verifiers work on arbitrary supported inputs.

The post-RUN CRC digest provides an observable result and corruption/provenance record. Raw float digests can differ across toolchains even when numerical verification passes; they are not a cross-platform numerical-equivalence criterion. Keep the kernel C unit separate from the runner and disable LTO; the runner must preserve every call. Inspect each platform's generated binary before measurement to confirm counts and exclusion of result verification from the marked RUN window.
