# Accepted PPK2 raw-data archive

The current working tree contains **60 accepted `.raw4` streams (1,142,884,352 bytes)**, covering two independent campaign selections. Every stream is `selected_final` in the [CSV inventory](raw_inventory.csv) and [JSON inventory](raw_inventory.json).

| Selection | Captures | Samples | Workload gates |
|---|---:|---:|---:|
| [Maximum clocks](../ROW_Data/source_campaign.json) | 30 | 132,329,472 | 360 |
| [Common160](../ROW_Data/common160/source_campaign.json) | 30 | 153,391,616 | 360 |

The maximum-clock selection retains ten ESP32 v3 captures at 240 MHz and adds ten RP2040 v4 captures at 200 MHz and ten STM32 v4 captures at nominal 180 MHz. Common160 contains thirty new v5 captures, ten per board. Capture numbers do not pair observations between campaigns. The explicit completed manifests define membership; directory names alone are not selection evidence.

The inventory records each original RAW path, byte count, SHA-256, board, physical-board ID, role and associated completed campaign. Obsolete captures, pilots and derived reports were removed from the current working tree. Earlier published records remain in Git history and existing release tags.

## Obtain and verify the data

Install Git LFS before cloning, or run `git lfs pull` afterward. Source captures are in `captures_noreg/esp32/` (retained v3), `captures_max_clock/` and `captures_common160/`. Git LFS supplies all RAW streams and the fifty new maximum-clock/common160 source CSVs. A source archive without LFS objects contains pointer files, not usable waveform data.

The ten retained ESP32 CSVs can be reconstructed from the RAW streams and saved calibration metadata. Each selected capture retains the original CSV SHA-256. Use an isolated environment and, when no CSV is already present, run:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-ppk2.txt
.venv/Scripts/python tools/export_ppk2_raw.py captures_noreg/esp32/20260910T123000.452016Z_esp32_001/transport.raw4
```

On POSIX systems, use `.venv/bin/python`. The exporter refuses to overwrite a CSV, checks the RAW hash before decoding, and verifies the complete reconstructed CSV hash afterward. `ppk2-api==0.9.2` pins calibration and range-transition behavior. Curated local copies under `ROW_Data/` are ignored to avoid duplicating the published source archive; see the [dataset guide](../ROW_Data/README.md).

Regenerate the current inventory after verifying the checkout and LFS objects:

```powershell
python tools/build_raw_inventory.py --force
```

The default selection inputs are `ROW_Data/source_campaign.json` and `ROW_Data/common160/source_campaign.json`; pending templates are excluded. `--campaign path/to/selection.json` can be repeated to request explicit selection manifests. The tool inventories available RAW streams and checks recorded hashes; it does not itself perform the complete campaign acceptance audit.

For accepted summaries, see [maximum-clock results](../results/2026-09-11_max_clock/README.md) and the [common160 results and original acceptance package](../results/2026-09-11_common160/README.md). Reintegrate individual CSVs using the [capture analyzer](../docs/capture_format.md).

## Format and scope

`transport.raw4` is the exact aligned four-byte stream consumed by `ppk2-api`, not a Nordic application `.ppk2` archive. Sample time is reconstructed at nominal 100 kS/s. Current conversion uses saved calibration parameters. The rolling six-bit hardware counter cannot exclude loss of exactly a multiple of 64 frames. The recorded constant 3.3 V and assigned 0.01 V uncertainty are operator records; voltage is not sampled in the transport and voltmeter identity/calibration were not recorded.

ESP32/Pico board regulators were removed. Nucleo retains its LDO, with JP6 open and PPK2 supplying MCU VDD. Original acquisition metadata is preserved separately from this recorded fixture correction. D0 marks workload boundaries; it does not attest firmware identity or prove final verification after DCT. See [validation status](../docs/VALIDATION.md).

For scholarly citation use [CITATION.cff](../CITATION.cff), together with the source commit and measured-image identity in the completed campaign. Release version alone does not identify the retained ESP32 v3 measurements.
