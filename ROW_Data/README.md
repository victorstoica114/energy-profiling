# Accepted maximum-clock CSV dataset

The accepted selection contains ten captures per platform: ESP32 at 240 MHz
(retained 10 September 2026 v3 records), RP2040 at 200 MHz with internal DVDD
selected at 1.15 V, and STM32F446 at 180 MHz (new 11 September v4 records).
All 30 captures are used: 132,329,472 sample rows and 360 complete RUN windows.
The source archive is commit `7909bfd5966b0ecc976450e21fbe530d673d3ec1`.

## Published selection and local waveforms

This directory publishes the completed selection, capture index and original
experiment profiles. Full curated CSVs and copied acquisition sidecars remain
local in `ESP32/`, `RP2040/` and `STM32F446/`, each with `run_01/` through
`run_10/`. These local copies are ignored by Git to avoid duplicating the source
archive. Each run contains `capture.csv`, unchanged `capture_metadata.json`,
and `original_analysis/capture.analysis.json` and `capture.workloads.csv`.

`capture_index.csv` maps every local run to its original timestamped capture
directory and RAW path. Original RAW transports and acquisition sidecars are
published in `captures_noreg/` and `captures_max_clock/`. Git LFS supplies the
RAW transports and new maximum-clock waveform CSVs. The repository tool
`tools/export_ppk2_raw.py` can reconstruct CSVs from RAW using each capture's
saved calibration parameters. Compare the complete CSV SHA-256 with the index
before using a reconstructed or copied file.

The CSV header is `Sample,Timestamp(us),Current(uA),D0`. Timestamps are the
zero-based sample index times 10 microseconds at nominal 100 kS/s. The accepted
waveforms are not smoothed, clipped, resampled, padded or baseline-subtracted.
Each capture has twelve ordered HIGH intervals; normalize batch energy and
duration by the preset call count before averaging ten capture-level values.

## Provenance and measurement boundary

`source_campaign.json` defines the completed selection. `dataset_manifest.json`
pins the original profiles, candidate firmware hashes, capture hashes and
unchanged sidecars. ESP32 retains its v3 identity; RP2040 and STM32 retain v4.
Files under `config/` and `campaigns/profiles/` are original experiment copies,
whose historical status fields are preserved. Acceptance belongs to the
completed campaign rather than to edits of those original records.

ESP32/Pico board LDOs were removed. The operator corrected the STM32 fixture
description: its LDO remains fitted, JP6 is open, and PPK2 supplies MCU VDD.
The completed campaign records electrical isolation separately from physical
removal and preserves the original template description. STM32 energy covers
the supplied MCU VDD domain, not the complete Nucleo PCB. All boards use the
3.3 V PPK2 supply, with DUT USB, UART and programmer connections absent.

The prior local CSV selection is archived at
`../ROW_Data_history/2026-09-10_ppk2_regulators_removed_csv` and is not used in
the current article. Article analysis scripts resolve this current `ROW_Data`
directory by default or through `PPK2_DATA_DIR`. Unrounded results and the
independent full-waveform integration audit accompany the article workspace.
The separate common160 campaign contributes no measurements to this selection.

## Accepted common-frequency campaign

The independent [common160 selection](common160/README.md) contains thirty new
160 MHz captures, with its own manifests, index and local board/run folders.
Maximum-clock data above remain unchanged. The [public common160 results and
acceptance package](../results/2026-09-11_common160/README.md) provides audited
summaries and the exact fixture adapter needed to reproduce them.
