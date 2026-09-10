# PPK2 campaign update — ESP32 without voltage regulator

The ESP32-D0WD-V3 board was remeasured after its onboard voltage regulator was removed. PPK2 VOUT supplied the 3V3 rail directly. Ten independent cold-boot captures were accepted, containing 120 complete D0 RUN windows and 38,462,464 samples at 100 kS/s. The preceding pilot capture is stored separately and is not included in these statistics.

Conditions: PPK2 F7839E12B2AE in Source Meter mode, 3300 mV setpoint, externally observed DUT rail 3.30 V, assigned voltage uncertainty ±0.01 V, and approximate room temperature 25 °C. GPIO18 was connected to D0; USB and other DUT power sources were disconnected.

| ESP32 hardware state | Captures | Startup baseline mean ± sample SD |
|---|---:|---:|
| Regulator fitted | 10 | 55.578 ± 0.386 mA |
| Regulator removed | 10 | 53.310 ± 0.045 mA |
| Change | — | −2.269 mA (−4.082%) |

Across the twelve workloads, mean non-baseline-subtracted energy per call decreased by 2.405% to 2.811% (mean of the twelve percentage changes: 2.646%). Execution-duration changes were at most 0.0005%, so the energy reduction is attributable to lower measured current rather than a timing change. The largest energy coefficient of variation in the new ten-capture series was 0.268%.

[comparison_vs_regulator.csv](comparison_vs_regulator.csv) contains the direct ESP32 comparison for every workload. [campaign_summary.csv](campaign_summary.csv) and [campaign_summary.json](campaign_summary.json) contain the full aggregate statistics; [capture_index.csv](capture_index.csv) links the selected captures to their hashes. The exact selection and fixture description are in [the no-regulator campaign manifest](../../campaigns/2026-09-10_ppk2_esp32_noreg.json).

RP2040 and STM32 were not remeasured for this update. Their original validated captures are reused in the combined summary so its three-board layout remains directly comparable to the initial report. Energy is RUN charge multiplied by 3.30 V without baseline subtraction. Structural acceptance and firmware-attestation limitations remain the same as in the original campaign.
