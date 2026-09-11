# Selected PPK2 measurement data (CSV)

**Historical campaign.** These measurements retain their original configuration
and are not results for the maximum-clock firmware. This release publishes the
selection index and manifests; the full curated CSVs and copied sidecars remain
in the local working tree. Original transport files and acquisition sidecars
are available in `captures/` and `captures_noreg/`; use
`tools/export_ppk2_raw.py` to reconstruct the corresponding waveform CSVs.

This dataset contains the 30 selected captures from the 10 September 2026
campaign: ten captures each for ESP32, Raspberry Pi Pico (RP2040), and
NUCLEO-F446RE (STM32F446). The onboard voltage regulator was physically removed
on all three boards during these measurements.

ESP32 and Pico use the later `captures_noreg` series selected in the final
campaign manifest. The Nucleo uses the original ten selected STM32 captures:
the operator confirmed on 10 September 2026 that its regulator had been removed
before any measurements. This clarification is recorded separately in
`dataset_manifest.json`; the original acquisition metadata is preserved.

## Location and article workspace

This directory is now stored in the Energy Profiling checkout, at
`D:\Documente\Energy Profiling\ROW_Data`. It was moved intact from the separate
article workspace. Capture paths in this manifest are relative to this dataset
root; the original metadata, input hashes and measurement bytes are preserved.
The source RAW transports and curated CSVs now share the same repository tree.

The article retains its derived results, table/plot generators and LaTeX sources
in its own workspace. Its current analysis scripts resolve this sibling
`Energy Profiling/ROW_Data` directory by default; `PPK2_DATA_DIR` overrides the
location. A relative override is resolved from the article workspace.
The pinned source commit below identifies the original RAW/firmware archive;
this relocated CSV directory is a later local addition to that checkout.

## Layout

```text
ROW_Data/
  ESP32/
    run_01/ ... run_10/
  RP2040/
    run_01/ ... run_10/
  STM32F446/
    run_01/ ... run_10/
  capture_index.csv
  dataset_manifest.json
  experiment.json
  source_campaign.json
  README.md
```

Each run directory contains:

- `capture.csv`: the complete sample-level current and D0 recording.
- `capture_metadata.json`: the original acquisition metadata, including PPK2
  calibration parameters, sample count, recorded hashes and firmware provenance.
- `original_analysis/capture.analysis.json`: the previously saved analysis.
- `original_analysis/capture.workloads.csv`: the previously saved workload results.

Run numbers follow the final campaign manifest. `capture_index.csv` maps each
local run to its original timestamped capture ID and RAW path. It also records
sample counts, file sizes, SHA-256 hashes and the evidence for regulator removal.
The RAW files remain in the source repository at `D:\Documente\Energy Profiling`.
Original absolute paths inside copied metadata refer to the acquisition PC;
use the index and `source_local_root` in `dataset_manifest.json` to locate the
files on this PC.

## CSV columns and units

CSV files use UTF-8, commas, a decimal point and LF line endings. Each data row
represents one sample. The header is:

```csv
Sample,Timestamp(us),Current(uA),D0
```

| Column | Meaning |
| --- | --- |
| `Sample` | Zero-based sample index within this capture. |
| `Timestamp(us)` | `Sample * 10`, in microseconds from the first sample. |
| `Current(uA)` | Current in microamperes, decoded using the capture's saved calibration parameters. |
| `D0` | Recorded RUN level: `1` during an algorithm batch, `0` outside it. |

The nominal PPK2 rate is 100,000 samples/s. Timestamps are reconstructed from
the sample index at that rate; they are not independent timestamps carried by
each transport frame and do not use MCU `micros()` or `millis()`. The acquisition
metadata retains the sample-counter continuity check and its limitations.

The 30 captures contain 165,200,896 sample rows in total. Capture lengths vary;
they have not been padded or truncated. Full recordings include the startup
prefix, LOW intervals, twelve HIGH intervals and the final LOW tail.

Current conversion reproduces the original `ppk2-api==0.9.2` decoder, including
its range-switch spike handling. This export adds no smoothing, resampling,
decimation, baseline subtraction, clipping or removal of negative samples.
CSV values retain the original floating-point text representation.

## Interpreting the RUN signal

The twelve complete HIGH windows correspond, in order, to:

1. RLE
2. Delta
3. LZ77
4. Huffman
5. AES-128
6. SHA-256
7. ChaCha20
8. CRC32
9. FFT
10. FIR
11. IIR
12. DCT

Algorithm identity is assigned by this fixed order; D0 carries no algorithm ID.
A RUN window includes samples from its rising edge up to, but excluding, its
falling edge. Iteration counts differ between some boards and are recorded in
`experiment.json`. Use those counts when deriving per-invocation quantities.

The supply setpoint is 3.3 V. There is no sampled voltage column in these CSVs;
energy calculations require an explicitly stated voltage assumption. The
original campaign records the operator's external voltage reading and assigned
uncertainty. The copied analysis files are existing results, not calculations
performed by this export. Their status is a structural protocol check; firmware
attestation and final validation limitations remain as recorded in the metadata.

## Provenance and verification

Source repository: [energy-profiling](https://github.com/victorstoica114/energy-profiling),
commit `9562df9212a043c8db625f47dfee2c7d2ae494da`.

Selection follows `campaigns/2026-09-10_ppk2_regulators_removed.json`, copied here
as `source_campaign.json`. `experiment.json` is also copied byte for byte;
historical status fields in these original files have not been rewritten.

For every capture, reconstruction verifies the RAW SHA-256 against acquisition
metadata and inventory. It then checks the exported CSV against the CSV SHA-256
recorded at acquisition and independently rereads the stored CSV to check that
hash again. Copied sidecars are also checked against their source files.
`dataset_manifest.json` records completion, all per-capture hashes, source
paths, tool hashes and conversion versions.

The preparation script remains `scripts/prepare_ppk2_csv_dataset.py` in the
separate article workspace. Run the following commands from that workspace:

```powershell
python -m venv analysis/ppk2_csv_env
& '.\analysis\ppk2_csv_env\Scripts\python.exe' -m pip install 'ppk2-api==0.9.2' 'pyserial==3.5'
& '.\analysis\ppk2_csv_env\Scripts\python.exe' '.\scripts\prepare_ppk2_csv_dataset.py' --source 'D:\Documente\Energy Profiling' --destination 'D:\Documente\Energy Profiling\ROW_Data' --workers 3
```

The source repository must be at the recorded commit with its selected Git LFS
RAW files available locally. Existing matching outputs can be reused; differing
capture files or sidecars are not overwritten. Each capture has several million
rows, so use a CSV reader that can stream or process chunks for subsequent work.
