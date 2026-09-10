# Verified native build

These are the STM32F411CE candidate firmware artifacts, not a hardware test result.
`verification.json` records SHA-256 hashes of the complete common source, generated
inputs/configuration, target source, SDK trees, compiler and output artifacts.
The ELF, BIN, HEX and map were built together. BIN load address: `0x08000000`.

The compiler is GNU Arm Embedded GCC 9.2.1 20191025. Benchmark compilation uses
`-O2 -fno-fast-math -ffp-contract=off -fno-lto` and Cortex-M4 hard-float flags.
All twelve workload symbols are present. The ELF declares VFPv4-D16, single
precision and VFP argument registers; `my_dct` contains `vmul.f32`/`vadd.f32`.
FFT and IIR retain software double operations, visible as `__aeabi_d*` calls.

The linker reserves 16 KiB for the stack. Compiler stack records show 1344 bytes
for the Huffman encoder, 736 for its verifier, and 48 for the common runner;
these are individual frames, not a measured maximum of the complete call chain.

`compile_commands.json` and disassembly preserve local build paths as provenance.
Rebuild from the project with `scripts/build_arms.ps1`; do not reuse these paths
as a portable build configuration. A later source or manifest change requires
new artifacts and hashes. No board was flashed or powered during this verification.
