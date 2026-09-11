# Repository consistency audit — 11 September 2026

The working tree now contains the two accepted campaign selections and their
required firmware, acquisition and analysis evidence. The cleanup removed
384 obsolete local files totaling 7,401,315,751 bytes, including 258 tracked
files. Git history, release tags and published release assets were preserved.
Removing a working-tree file does not purge its historical Git/LFS archive.

## Retained evidence

- Sixty accepted RAW streams, 285,721,088 samples and 720 workload gates:
  [maximum clocks](../ROW_Data/source_campaign.json) and
  [common160](../ROW_Data/common160/source_campaign.json).
- The ten original ESP32 240 MHz v3 captures, plus the exact associated
  [measurement archive](../firmware/targets/esp32/build_verified/single_gpio_measurement/README.md),
  restored from `v1.0.0`. The accepted application SHA-256 is
  `7ddad2c4440d72f42cd1052cd80f2cf6aa46f304b5c4772388cb12ad0d8b94fd`.
- Current maximum-clock and common160 images, deterministic inputs, build
  evidence, hardware functional/programming records and photographs.
- Both original `CURRENT_FIRMWARE.json` snapshots and the original common160
  acceptance adapter, patch and provenance records, with their exact bytes.

Obsolete pilots, rejected/incomplete transports, replaced campaigns and their
derived reports, the local `ROW_Data_history` copies, older eight-signal build
artifacts and the unused delivery manifest were removed from the working tree.
The current [RAW inventory](../dataset/README.md) contains exactly 60
`selected_final` streams totaling 1,142,884,352 bytes.

## Corrections

1. [MEASUREMENT_STATUS.json](../MEASUREMENT_STATUS.json) records completed
   acceptance separately from immutable programming-time snapshots. It
   distinguishes the measured ESP32 v3 image from the unused v4 candidate.
2. The live campaign summarizer accepts explicitly documented STM32 JP6
   isolation as well as physical regulator removal. Missing isolation evidence,
   the wrong supply domain and applying the JP6 exception to another board are
   rejected. Integration, workload normalization and statistical formulas were
   not changed.
3. The inventory defaults to the two completed `ROW_Data` selections rather
   than historical campaign files or acquisition templates. Explicit
   `--campaign` selection remains available.
4. Active guides now describe both completed campaigns, the STM32 MCU VDD
   supply boundary and the accepted image identities. The software citation
   metadata identifies release `v1.2.0`.

## Verification

- All 89 Python unit tests passed with the pinned PPK2 dependency installed.
- All 119 host kernel checks passed, including all twelve workloads, repeated
  state initialization and rejection of deliberately corrupted outputs.
- All twelve host runner simulations passed: three boards, measurement and
  diagnostic modes, under each of the two clock profiles.
- RAW files, curated CSVs, available source CSVs and copied acquisition
  sidecars were checked against the accepted manifests. All sixty captures
  passed; 20,840,497,768 waveform bytes were hashed.
- The corrected core summarizer reproduced both campaigns' summary CSV and
  capture index byte-for-byte against their previously accepted outputs.
- Firmware source, measured images, original acquisition metadata and the
  programming-time manifests retain their original identities.

The [maximum-clock summary](../results/2026-09-11_max_clock/README.md) and
[common160 acceptance package](../results/2026-09-11_common160/README.md) provide
the respective reproduction commands. Host checks and structural acquisition
acceptance do not constitute independent flash readback or prove final silent
firmware validation. They also do not remove instrument uncertainty or turn
one physical unit per model into a population-level comparison.
