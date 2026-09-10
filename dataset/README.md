# PPK2 raw-data archive

This repository archives the exact PPK2 transport streams used by the `energy-profiling-v3-single-gpio` campaign. The archive contains **65 `.raw4` files (1,415,499,776 bytes)**:

| Role | Files | Interpretation |
|---|---:|---|
| `selected_final` | 50 | Ten original captures for each of three boards, plus ten ESP32 and ten RP2040 captures after regulator removal |
| `pilot` | 5 | Structurally complete setup runs excluded from aggregate statistics |
| `rejected_complete` | 1 | Complete transport rejected by the then-active structural tolerance |
| `incomplete_transport` | 9 | Interrupted setup/diagnostic transports; never used for reported results |

[raw_inventory.csv](raw_inventory.csv) and [raw_inventory.json](raw_inventory.json) record the path, size, SHA-256, board, physical-board identifier, selection role and associated campaign IDs for every raw file. The explicit campaign manifests, rather than folder naming, are authoritative for statistical inclusion:

- [Original three-board campaign](../campaigns/2026-09-10_ppk2.json): 30 selected captures with the original ESP32 and RP2040 fixtures.
- [ESP32 regulator-removal comparison](../campaigns/2026-09-10_ppk2_esp32_noreg.json): ten new ESP32 captures; original RP2040 and STM32 captures reused.
- [Final regulator-removed campaign](../campaigns/2026-09-10_ppk2_regulators_removed.json): ten new ESP32 and ten new RP2040 captures; original STM32 captures reused.

## Obtaining the data

The `.raw4` files are tracked with Git LFS. Install Git LFS before cloning, or run `git lfs pull` after cloning. GitHub source archives contain only LFS pointer files unless the repository owner enables inclusion of LFS objects in archives.

The large `capture.csv` files are deliberately omitted because they are deterministic derivatives totaling approximately 10.7 GiB. Each selected capture retains its `capture_metadata.json`, analyzer output and original CSV SHA-256. Recreate and verify a CSV offline with:

```text
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-ppk2.txt
.venv/Scripts/python tools/export_ppk2_raw.py captures/rp2040/20260910T110338.807055Z_rp2040_001/transport.raw4
```

On POSIX systems, use `.venv/bin/python`. The exporter refuses to overwrite an existing CSV, checks the RAW hash before decoding, and checks the reconstructed CSV hash afterward. `ppk2-api==0.9.2` is pinned because its calibration and range-transition behavior is part of the conversion provenance.

After regeneration, analyze a capture as documented in [capture_format.md](../docs/capture_format.md). Aggregate tables already produced from the selected captures are under [results](../results).

## Format and limitations

`transport.raw4` is the exact aligned four-byte stream consumed by `ppk2-api`; it is **not** a Nordic Power Profiler application `.ppk2` archive. Sample time is reconstructed at the configured 100 kS/s. Current values depend on the PPK2 calibration metadata stored beside each complete capture. D0 is decoded from the logic byte and provides RUN boundaries only.

The rolling six-bit hardware counter was checked during complete acquisitions, but loss of an exact multiple of 64 frames is not independently excluded. Voltage was externally observed as 3.30 V and is not sampled in the RAW stream. The single D0 signal does not attest firmware identity or final validation after DCT. See [the validation report](../docs/VALIDATION.md) for the complete limitations.

For scholarly citation, use [CITATION.cff](../CITATION.cff) together with the immutable release tag or commit hash. A DOI-backed archival release is preferable when one becomes available.
