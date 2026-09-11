# Accepted maximum-clock campaign

This package summarizes the thirty accepted maximum-clock captures: ten retained ESP32 v3 captures at 240 MHz, ten RP2040 v4 captures at 200 MHz and ten STM32F446 v4 captures at nominal 180 MHz. The selection contains 132,329,472 samples and 360 workload gates. Its original source archive is commit `7909bfd5966b0ecc976450e21fbe530d673d3ec1`.

The [completed selection](../../ROW_Data/source_campaign.json) pins every original capture directory, profile, expected image and metadata/analysis hash. The [dataset guide](../../ROW_Data/README.md) describes waveform availability. The measured ESP32 image is the [retained v3 archive](../../firmware/targets/esp32/build_verified/single_gpio_measurement/README.md); the v4 ESP32 candidate was not used for these captures.

## Reproduce the summaries

With Python and the real Git LFS RAW objects available, run from the repository root using a fresh output directory:

```powershell
python tools/summarize_campaign.py ROW_Data/source_campaign.json --output-dir results/max_clock_recheck
```

The summarizer validates the declared profiles, expected images, environment, fixed order/counts, saved analysis, RAW hashes and sizes. It accepts the documented STM32 fixture only with explicit regulator isolation, open JP6, MCU VDD injection and operator correction evidence. The LDO remains fitted; ESP32/Pico board regulators were removed.

The three supplied outputs are `campaign_summary.csv`, `campaign_summary.json` and `capture_index.csv`. They contain 36 board/workload groups and the thirty capture identities. This is offline regeneration from the accepted saved batch analyses, not a new acquisition or an independent full-waveform integration. Current, duration, charge and energy are summarized across ten captures using arithmetic mean and sample SD. The `*_per_call_*` columns already divide each capture's batch duration, charge and energy by its preset call count; they are suitable for per-invocation comparisons and must not be divided a second time. Current is the average within RUN. Full RUN energy includes the active-idle level; baseline-subtracted plots and other article-specific derived statistics are prepared separately in the article workspace.

The saved JSON records the summarizer identity, execution time and provenance. Reproduction on another workstation can change those fields while preserving numerical results. The independent [common160 package](../2026-09-11_common160/README.md) retains its original adapter and acceptance evidence byte-for-byte; its capture numbers are not paired with this campaign.

[MEASUREMENT_STATUS.json](../../MEASUREMENT_STATUS.json) separates completed capture acceptance from unchanged programming-time manifests. GPIO gates and expected image hashes do not independently attest device flash or final silent-image verification. Sample SD describes repeatability; it does not replace instrument, voltage or clock uncertainty.
