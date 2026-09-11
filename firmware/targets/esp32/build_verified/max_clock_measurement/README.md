# esp32 maximum-clock measurement image

Release v1.1.0, experiment `energy-profiling-v4-max-clock`, schema 2. Nominal CPU clock: **240 MHz**. Benchmark serial diagnostics are disabled; RUN is the single PPK2 D0 output.

Native compilation, linking and static checks passed. This measurement image has not been programmed or validated on hardware in this release campaign. Measurement-image runtime validation and new PPK2 acceptance captures are pending. No independent flash-readback attestation is claimed.

`verification.json` records build and hardware evidence; `source_sha256_at_archive.json` records source/input hashes, and `experiment_manifest_at_archive.json` preserves the matching configuration. Compiler commands and disassembly are included. Earlier firmware remains available in the [v1.0.0 release](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0).
