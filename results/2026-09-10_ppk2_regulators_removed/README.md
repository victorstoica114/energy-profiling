# PPK2 campaign — ESP32 and RP2040 without onboard regulators

ESP32-D0WD-V3 and Raspberry Pi Pico RP2040 were each remeasured after removal of their onboard voltage regulator, with PPK2 VOUT connected directly to the 3V3 rail. Each modified board has ten accepted independent cold-boot captures. The original ten STM32F446 captures are reused unchanged to retain a complete three-board campaign summary. Pilot captures are excluded from all aggregate statistics.

Conditions: PPK2 F7839E12B2AE in Source Meter mode, 3300 mV setpoint, externally observed DUT rail 3.30 V, assigned voltage uncertainty ±0.01 V, and approximate room temperature 25 °C. RP2040 GP2 and ESP32 GPIO18 were connected to D0; USB and all other DUT power sources were disconnected.

| Board | Regulator-present baseline | Regulator-removed baseline | Change |
|---|---:|---:|---:|
| ESP32 | 55.578 ± 0.386 mA | 53.310 ± 0.045 mA | −2.269 mA (−4.082%) |
| RP2040 | 28.469 ± 0.041 mA | 28.402 ± 0.034 mA | −0.067 mA (−0.236%) |

For RP2040, non-baseline-subtracted energy per call fell by 0.199% to 0.341% across the twelve workloads; the unweighted mean of those percentage changes is 0.291%. Execution-duration changes were at most 0.0005%, and the largest energy coefficient of variation in the new RP2040 series was 0.184%. The regulator-removal effect is therefore much smaller than on ESP32 and should not be interpreted without the separately documented PPK2 and voltage uncertainty limitations.

[comparison_rp2040_vs_regulator.csv](comparison_rp2040_vs_regulator.csv) contains the RP2040 comparison for every workload. The earlier [ESP32 regulator comparison](../2026-09-10_ppk2_esp32_noreg/comparison_vs_regulator.csv) remains authoritative for that board. [campaign_summary.csv](campaign_summary.csv) and [campaign_summary.json](campaign_summary.json) contain the complete modified-fixture aggregate; [capture_index.csv](capture_index.csv) links every selected capture to its hashes. The exact selection is recorded in [the campaign manifest](../../campaigns/2026-09-10_ppk2_regulators_removed.json).

Energy is RUN charge multiplied by 3.30 V without baseline subtraction. Structural acceptance does not attest the flashed firmware or prove final validation after DCT; expected firmware hashes are recorded provenance rather than device readback.
