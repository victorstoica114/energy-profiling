# PPK2 campaign summary — 10 September 2026

The `energy-profiling-v3-single-gpio` campaign completed **30 accepted cold-boot captures**: ten each for ESP32-D0WD-V3, Raspberry Pi Pico RP2040 and NUCLEO-F446RE. Every accepted capture contains twelve complete D0 RUN windows and the required LOW tail. The combined dataset contains 165,203,968 samples at 100 kS/s.

Conditions recorded for all final captures: PPK2 F7839E12B2AE in Source Meter mode, 3300 mV setpoint, externally observed DUT rail 3.30 V, assigned voltage uncertainty ±0.01 V, and approximate room temperature 25 °C. The multimeter model/calibration and an independently calibrated clock measurement were not recorded.

| Board | Accepted captures | Startup baseline mean ± sample SD |
|---|---:|---:|
| ESP32 | 10 | 55.578 ± 0.386 mA |
| RP2040 | 10 | 28.469 ± 0.041 mA |
| STM32F446 | 10 | 18.510 ± 0.030 mA |

The complete 36-row comparison is in [campaign_summary.csv](campaign_summary.csv). [campaign_summary.json](campaign_summary.json) preserves full statistics, conditions, selection and provenance; [capture_index.csv](capture_index.csv) links every accepted capture to its hashes and firmware-provenance claim. The explicit source selection is [the campaign manifest](../../campaigns/2026-09-10_ppk2.json).

Energy is the non-baseline-subtracted RUN charge multiplied by 3.30 V. Reported dispersion is the sample standard deviation across ten independent cold boots. The separate voltage component covers only ±0.01 V; it is not a complete uncertainty budget. Per-call values divide each fixed-count batch by its manifest iteration count, so calls within a batch are not independent replicates.

Acceptance is structural, not firmware attestation. A single D0 wire cannot prove final validation after DCT, distinguish every LOW hang/reset, identify the programmed binary or independently verify the board clock. ESP32/RP2040 LOW checks use 1% pause tolerance; STM32 uses a documented 2% allowance because its HSI16-derived pilot gaps were 0.98579..0.99163 s. This allowance does not alter RUN integration.
