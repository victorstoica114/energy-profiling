# Maximum-clock capture campaign

`2026-09-11_ppk2_max_clock.template.json` is a pending acquisition plan, not a
result. The collector writes new acquisitions to `captures_max_clock/` by
default and requires the v4 experiment and its matching silent image archive.
Existing captures remain in their original locations.

The template explicitly retains the ten regulator-removed ESP32 cold boots
from 10 September 2026 at 240 MHz. It pins their original v3 experiment file,
expected firmware image, acquisition metadata and analysis JSON files by
SHA-256. These records are not relabelled as executions of the v4 firmware.
Their original voltage and approximate temperature records are retained.

The RP2040 200 MHz / 1.15 V and STM32F446 180 MHz sections require ten new
regulator-removed cold boots each. Empty capture lists and `null` environment
values are deliberate. Fill the measured voltage, assigned absolute voltage
uncertainty and ambient temperature from each new session; do not copy the
historical values without a new observation. Physical board IDs retain the
existing unit labels, including the legacy `RPI-PICO-RP2040-01-NOREG` label for
the Marble Pico unit.

For a completed campaign, save a separate JSON file based on the template:

1. Confirm the PPK2 serial number, fixture, board IDs, image hashes and experiment
   file hash. A hash of the expected image does not attest the DUT's flash.
2. Enter the exact ten new project-relative capture directories for each changed
   board. Pin each `capture_metadata.json` and `analysis/capture.analysis.json`
   in `capture_file_sha256` using the `metadata` and `analysis` keys shown in the
   ESP32 section. SHA-256 values must be lowercase hexadecimal strings.
3. Fill the recorded environment for each board and set the completed file's
   `status` to `ready_for_analysis`. Keep the template pending.
4. Run the summarizer with a new, unused output directory, for example:

```powershell
python tools/summarize_campaign.py campaigns/completed_max_clock.json --output-dir analysis/max_clock_results
```

The summarizer requires all 30 captures before writing results. Schema 2 binds
each capture to its explicit board profile, including its manifest bytes,
embedded analysis manifest, clock, repetition counts and expected image hash.
It checks the original raw transport SHA-256 and byte count. Cross-profile
reuse requires an explicit justification and all the same checks. The output
capture index retains the original per-capture experiment IDs and hashes.

The offline analyzer also accepts the original v3 manifest for reproducibility.
That support does not permit acquiring new data under an obsolete experiment
or inserting old RP2040/STM32 results into the prepared v4 board sections.
