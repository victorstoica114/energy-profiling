# Accepted common160 campaign and reproducible analysis

This package preserves the audited results for thirty new common160 captures:
ten independent cold boots each for ESP32, RP2040 and STM32F446 at nominal
160 MHz. The selection contains 153,391,616 samples and 360 workload windows;
all captures are included. Original source archive commit:
`f19c3b4c96e85d6348c9966bc012bbdbbeac1112`.

The [completed campaign](../../ROW_Data/common160/source_campaign.json) pins
all original capture directories, experiment/image identities, metadata and
analysis hashes. The [dataset guide](../../ROW_Data/common160/README.md)
describes the separately curated selection. Original RAW/CSV and sidecars stay
in `captures_common160/`; this results package duplicates no waveform files.

## Reproduce from the public repository

Use Python's standard library and a checkout containing the real Git LFS RAW
objects for `captures_common160/`, rather than LFS pointer files. No firmware
build, measurement hardware or private article-workspace path is required.
Run from the repository root:

```powershell
python results/2026-09-11_common160/acceptance/summarize_campaign_fixture_adapter.py ROW_Data/common160/source_campaign.json --project-root . --output-dir results/common160_recheck
```

The output directory must be unused; the summarizer refuses to overwrite its
three result files. It verifies all original profile, image, environment,
workload-order/count, analysis-status, timing-policy, RAW-hash and size checks,
then recomputes 36 board/workload summaries. Current, duration, charge and energy
use arithmetic mean and sample SD across ten captures. Duration and energy are
normalized by each board/workload's fixed call count. Full RUN energy has no
baseline subtraction; the separate baseline is the final two LOW seconds
before RLE. This command summarizes saved acquisition analyses after validation;
it does not independently reintegrate the complete waveform CSVs.

## Why the fixture adapter is supplied

The repository's [original summarizer](../../tools/summarize_campaign.py) is
unchanged. Its physical-regulator-removal requirement does not represent the
operator-confirmed STM32 fixture: the LDO remains fitted, JP6 is open and PPK2
supplies MCU VDD. ESP32/Pico retain physical board-regulator removal.

The supplied adapter is an exact copy of the audited script. Its only change
to the original validator is one fixture-validation block, admitting STM32
only with explicit physical-removal=false, electrical-isolation=true, open
JP6, MCU-VDD injection and recorded operator evidence. All other validation
bytes remain unchanged. The complete patch and source/adapter SHA-256 values
are supplied below. This is an offline analysis artifact; firmware images,
build configurations and original acquisition records are not modified.

## Preserved evidence

- `campaign_summary.csv`: 36 mean/sample-SD rows, with ten captures per row.
- `campaign_summary.json`: completed campaign, detailed statistics and provenance.
- `capture_index.csv`: thirty selected capture identities and source hashes.
- `acceptance/summarize_campaign_fixture_adapter.py`: the standalone audited
  validator used by the command above.
- `acceptance/summarizer_fixture_adapter.patch` and `adapter_provenance.json`:
  exact fixture change and source/adapter/campaign hashes.
- `acceptance/capture_integrity_audit.json`: complete RAW/CSV hashes and sizes,
  counter continuity, twelve gate pairs, own-capture baseline, trailing LOW and
  five negative checks of the fixture exception.
- `acceptance/source_identity_audit.json`: archived images, experiment,
  image-manifest, collector and analyzer identities verified against captures.

These eight evidence files preserve the original audit bytes, including any
absolute workstation paths in historical provenance. Those paths describe the
original audit location; the public command resolves the completed selection
against `--project-root .` and does not need those private paths. New output JSON
will record the new audit time and local paths, while numerical results should
match the published summaries.

The GPIO sequence and expected-image hashes are not independent flash
attestation or proof of final validation. Sample SD describes capture
repeatability, not total measurement uncertainty. A six-bit rolling counter
cannot detect losing exactly a multiple of 64 samples. The recorded 3.3 V and
assigned 0.01 V voltage uncertainty remain operator records; no calibration
certificate is inferred.
