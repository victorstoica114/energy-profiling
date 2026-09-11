# Capture files and offline integration

The standard-library Python analyzer accepts one complete **single-GPIO** experiment sequence and produces derived JSON and workload CSV files. It never changes captures, repairs boundaries, substitutes published execution times or automatically subtracts idle current. Current profiles: **`energy-profiling-v4-max-clock`** and **`energy-profiling-v5-common160`**, schema **2**, GPIO protocol `single_run_v1`.

Use the experiment manifest recorded for each capture. Both campaigns are complete: the [maximum-clock selection](../ROW_Data/source_campaign.json) combines retained ESP32 v3 records with RP2040/STM32 v4 records, while the [common160 selection](../ROW_Data/common160/source_campaign.json) contains thirty new v5 records. The selections pin each original profile and capture. Do not substitute current configuration bytes for an older capture's manifest or relabel the retained ESP32 image as the unmeasured v4 candidate.

## Acquisition contract

Use the official Nordic Power Profiler application at **100,000 samples/s**. Start recording before powering or releasing reset on the DUT. Preserve the native .ppk2 file and export all samples with timestamps, current and the RUN channel. Record application/PPK2 firmware versions, the physical board, programmed image and experiment manifest.

Lower sampling settings average data before storage and cannot restore native timing later. Rates other than 100000 samples/s are rejected. Display zoom/minimap data are not used for integration.

**Only PPK2 D0 is used.** Wire ESP32 GPIO18, Pico GP2 or Nucleo PC0 to D0. HIGH normally encloses one batch; LOW is outside. No separate ID, error, completion or idle marker exists. D1-D7 are ignored, including unknown or mixed states on those unused inputs.

Exactly twelve complete HIGH pulses are assigned by position to RLE, Delta, LZ77, Huffman, AES-128, SHA-256, ChaCha20, CRC32, FFT, FIR, IIR and DCT. The board manifest supplies each batch's call count. The analyzer does not detect the algorithm from current shape or count individual calls inside a pulse.

Before the first pulse, ESP32 and RP2040 must have at least **495000 defined LOW samples**; each of their eleven inter-workload LOW gaps requires at least **99000 samples**. These are nominal 5 s and 1 s MCU pause lower bounds with 1% tolerance. NUCLEO-F446RE uses the internal HSI16 RC oscillator for its control timer, so its explicitly reported structural allowance is 2%: **490000 startup samples** and **98000 samples per inter-workload gap**. Confirm these thresholds in each new setup pilot; they are not clock-calibration results. This board-specific allowance affects only LOW-interval validation, never RUN boundaries, duration, charge or energy integration. No upper bounds apply because initialization, preparation and verification can lengthen LOW intervals. The recording must include at least **300000 trailing LOW samples**, three seconds, after the twelfth falling edge. This final recording minimum does not use the MCU pause tolerance.

The startup baseline is the **last 200000 LOW samples immediately before the first HIGH**, corresponding to two seconds. Firmware performs initialization, preparation and platform checks before the nominal five-second pause, leaving the selected baseline as operational idle apart from timer/gate boundary overhead. Other complete LOW intervals are not labeled idle: they can contain preparation, verification, active waiting or final platform sleep.

Detected firmware errors latch RUN HIGH until reset. A stuck-HIGH interval, absent fall, incomplete or additional pulse sequence, or insufficient LOW interval is rejected. If failure occurs inside a batch, the firmware keeps the existing gate open instead of emitting a normal falling edge first.

A pass is **structural_protocol_pass**, not an attestation of firmware success. The trace cannot independently prove the programmed image, internal call counts, absence of every reset, or completion of final verification. A hang while LOW after the twelfth pulse can leave an accepted shape. There is no DONE signal from which to prove completion. Retain image/programming provenance and perform physical revalidation separately.

## Startup values and current policy

Unknown D0 is allowed only as a contiguous prefix before the first defined LOW sample. After that synchronization point, unknown D0 is rejected even before the first RUN. Mixed D0 states are always rejected. An acquisition beginning HIGH is invalid because it lacks the required initial LOW interval. Unused digital channels do not affect these rules.

Finite negative current is permitted anywhere before the first RUN **except within the selected two-second baseline**. The baseline and all samples from the first RUN onward must be nonnegative. Negative startup samples are counted and retain their indices; they are neither clipped nor included in active/baseline integrals. Their sign does not establish whether their physical cause is offset. Nonfinite current always rejects the capture, including startup.

## Native .ppk2 support

Supported format: Nordic .ppk2 **formatVersion 2**. The ZIP must contain exactly these root files:

- metadata.json: JSON with formatVersion=2 and metadata.samplesPerSecond=100000; optional metadata.startSystemTime.
- session.raw: six bytes per retained sample: **little-endian float32 current in microamperes**, then a **big-endian uint16 digital word**. Each channel has two bits. D0 is the lowest pair: 01=LOW, 10=HIGH, 00=unknown, 11=mixed. Only the D0 pair is interpreted by the current protocol.
- minimap.raw: condensed display data, unused for metrics.

The mixed byte order is intentional and follows Nordic's DataView storage. Unsupported versions and legacy .ppk are rejected. ZIP members are read without extraction, in bounded chunks. The default cap is sixty million samples, ten minutes at 100 kS/s; metadata is limited to 1 MiB and minimap to 64 MiB. `--max-samples` changes the explicit sample-count cap. Unexpected members/paths, encrypted entries, symlinks, unsupported compression and partial frames are rejected. Metadata/session CRC failures abort analysis; unused minimap is not decompressed merely to check its CRC.

Nordic implementation examined at commit `881d596480f60dea045ad6f3643afdc3f9d5a0a6`: [sample storage/timebase](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/globals.ts), [digital encoding](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/utils/bitConversion.ts), [metadata/save format](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/utils/saveFileHandler.ts).

## CSV: select an explicit profile

`--csv-profile nordic` uses Timestamp(ms) in milliseconds and Current(uA) in microamperes. If D0 exists, it is selected and other digital columns are ignored, including a redundant D0-D7 column. Otherwise D0-D7 must contain eight characters; its **first character is D0** and the remaining seven are ignored. An export does not need eight separately wired signals.

Nordic CSV rounds current to 0.001 microampere; native files retain float32 values. The official CSV exporter skips NaN current samples, so an omission can appear as a timestamp gap and be rejected. [Nordic CSV exporter](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/actions/exportChartAction.ts).

For another schema, use `--csv-profile generic` and explicitly select current/time names and units. Current units: A, mA, uA. Time units: s, ms, us. Supply **`--digital-column NAME`** for one RUN column, or **`--digital-bitstring-column NAME`** for a D0-first eight-character representation. The old plural --digital-columns option is not the current interface. Values 0/1 represent LOW/HIGH, '-' is unknown subject to the prefix rule, and X is mixed/rejected on the selected channel. There is no unit inference from numeric magnitude. Decimal separator is a dot; --delimiter changes the column separator. Headers must be unique.

Each timestamp interval must match 1/fs within max(1 ps, 0.01% of 1/fs). Decimal arithmetic preserves differences with large absolute offsets. `--index-column` optionally checks consecutive integer indices. Missing, duplicate, backward or detectably irregular timestamps/indices reject the file. These checks cannot detect upstream data loss followed by reconstruction of a uniform index/timebase. Native .ppk2 is index-based and has no independent hardware timestamp for every sample; absence of packet loss is not proven.

## Commands

Run from the project root. Use an unused result directory or capture stem; existing output files are not overwritten.

```powershell
python tools/analyze_capture.py captures/esp32_001.ppk2 --board esp32 --manifest config/experiment.json --output-dir results/esp32_001

python tools/analyze_capture.py captures/esp32_001.csv --csv-profile nordic --board esp32 --manifest config/experiment.json --output-dir results/esp32_001_csv

python tools/analyze_capture.py captures/custom.csv --csv-profile generic --current-column I --current-unit mA --time-column t --time-unit us --digital-column RUN --board rp2040 --manifest config/experiment.json --output-dir results/custom
```

The manifest supplies sample rate and must agree with native metadata. Optional `--sample-rate-hz 100000` adds an operator cross-check. `--voltage 3.3` supplies a declared constant DUT voltage; otherwise manifest nominal voltage is used. Neither certifies a voltage measurement. `--voltage-uncertainty-v` records an absolute uncertainty whose basis must be documented separately; it does not calculate a complete energy uncertainty budget.

## Numerical results

For each half-open HIGH window [a,b):

```text
T = (b-a) / fs
Q = sum(I[a:b]) / fs
E = V_assumed_constant * Q
T_per_call = T / iterations_from_manifest
Q_per_call = Q / iterations_from_manifest
E_per_call = E / iterations_from_manifest
```

The falling-edge sample is outside RUN. The gate includes loop, status and GPIO-boundary overhead. No execution time from the MCU or original article is substituted. The entire capture's first-to-last span `(N-1)/fs` is distinct from its integration support N/fs.

JSON schema 2 uses status **structural_protocol_pass**. The runs contain sequence_position, algorithm_assumed_from_order and iterations_from_manifest alongside integral/per-call metrics. startup_baseline contains the selected final two seconds before the first HIGH.

low_intervals distinguishes startup_low, inter_workload_low and trailing_low. startup_low contains boundaries/duration without a current integral because it can contain signed boot current. Inter-workload and trailing LOW intervals can include current/energy statistics, but are explicitly mixed activity, not controlled idle. The schema records trailing_low_duration_s, unresolved_D0_samples_in_startup_prefix, negative_current_samples_in_unmeasured_startup and **final_validation_completion_proven=false**.

Current mean, population standard deviation, minimum and maximum describe each selected window. They do not establish independent samples, calibrated current stability or confidence across repeated experiments. JSON also preserves protocol checks, voltage basis, limitations, the selected manifest and SHA-256 hashes of capture, manifest and analyzer. The workload CSV contains twelve structurally accepted active-window rows. Rejected captures produce no new analysis files.

Independent cold boots must be recorded and analyzed separately; between-capture statistics are a separate step. Historical files require their matching analyzer and manifest. Earlier firmware and tools remain available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0); do not relabel their captured results as current measurements.

## Automated PPK2 collection

The optional collector uses the same generic CSV interface and runs this analyzer automatically:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ppk2.txt
.\.venv\Scripts\python.exe tools\capture_ppk2.py --list-devices
.\.venv\Scripts\python.exe tools\capture_ppk2.py --board rp2040 --physical-board-id PICO-01 --ambient-temperature-c 23.0 --confirm-wiring
```

Each unique capture directory contains `transport.raw4`, `capture.csv`, `capture_metadata.json` and analyzer output under `analysis/`. The raw file is the exact four-byte stream consumed by `ppk2-api`, not a Nordic `.ppk2` archive. CSV columns are explicit sample index, reconstructed time in microseconds, calibrated current in microamperes and D0. The collector rejects a discontinuity in the rolling 6-bit hardware sample counter and also compares represented time with host elapsed time; exact 64-sample-multiple losses are not independently excluded. Partial files and `failure.json` are retained on errors for diagnosis. Use `--captures 10` for a campaign only after a physical one-run pilot passes. Multi-capture runs require `--measured-voltage-v`, temperature and a physical board identifier; document the external voltage measurement and uncertainty basis with the campaign records.

## Parser checks

```powershell
python -m unittest discover -s tests -p test_capture_analysis.py -v
```

Synthetic cases cover known integration windows, native byte/bit order, selected-channel behavior, CSV units, missing/extra/incomplete pulses, LOW lower bounds, timestamp/index gaps, unsafe/truncated native files and nonfinite data. These checks do not replace a physical GPIO/export pilot or resolve the one-wire observability limits.
