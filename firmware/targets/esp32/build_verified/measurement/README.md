# esp32 measurement build

> Historical eight-signal archive. The binary, logs and hashes below describe their original snapshot, not the current single-GPIO campaign. Current candidates are identified separately in CURRENT_FIRMWARE.json.

Native compilation and linking succeeded. See `verification.json` for artifact hashes, compiler identity and diagnostic-symbol checks. `source_sha256_at_archive.json` records the source observed when this archive was produced. Hardware execution and flash readback are recorded separately by the test operator.

Serial diagnostics are compiled out. Serial/USB peripheral shutdown is implemented by the target platform. A silent terminal is not evidence that all workloads completed; completion must be verified with the digital markers.

The files directly in the parent `build_verified` directory are historical and are preserved.
