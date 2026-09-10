# Verified native build

These are the Raspberry Pi Pico candidate firmware artifacts, not a hardware test
result. `verification.json` records SHA-256 hashes of the complete common source,
generated inputs/configuration, target source, SDK tree, compiler and artifacts.
ELF, BIN, HEX, UF2 and map correspond to the same build. UF2 was generated from
the ELF with the installed official Pico `elf2uf2` converter.

Compiler: GNU Arm Embedded GCC 9.2.1 20191025. Benchmark compilation uses
`-O2 -fno-fast-math -ffp-contract=off -fno-lto`. All twelve workload symbols are
retained. Cortex-M0+ has no hardware FPU attributes in this ELF; floating point
uses software support. Core 0 has an explicit 4096-byte stack in SCRATCH_Y,
retaining the official Pico SDK linker layout. The compiler reports 1344-byte
Huffman encoder, 744-byte verifier, and 48-byte runner frames. These are separate
frames, not a measured maximum of the complete call chain.

`compile_commands.json` and disassembly retain local build paths as provenance.
Use the project `scripts/build_arms.ps1` for a new build. Any later source or
manifest change requires new firmware artifacts and hashes. No hardware was
flashed or powered during verification.
