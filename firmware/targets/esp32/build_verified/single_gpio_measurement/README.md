# esp32 single-GPIO measurement build

Native compilation and linking passed for **energy-profiling-v3-single-gpio**, experiment schema 2, with **BENCH_DIAGNOSTICS=OFF**. This archive was produced on 10 September 2026. **It has not been flashed or executed on hardware.** Earlier sibling measurement/diagnostic archives retain their historical eight-signal protocol.

The only measurement output is **GPIO18**, connected to PPK2 D0. Normal HIGH encloses one fixed-count batch; LOW is outside. Kernel identity is inferred from twelve pulses in fixed order. A detected error latches HIGH until reset; there is no separate ID, ERROR, DONE or IDLE_VALID output.

Experiment-manifest SHA-256: `e458d429cf49d803dd7dbfb5373e2bcac49e21f572466affb464c4a9971d1075`.

| Artifact | SHA-256 |
|---|---|
| `energy_bench_esp32.elf` | `3a1419b252ff11bee85d9234f1999da5d02fc3e7e01697f0bfe33a1927f26802` |
| `energy_bench_esp32.bin` | `7ddad2c4440d72f42cd1052cd80f2cf6aa46f304b5c4772388cb12ad0d8b94fd` |
| `energy_bench_esp32.map` | `9a455fa4319aa5cdde15363f98eb1e3eebb9e8ea1c343912b8a853fb6c5c1d0a` |
| `bootloader/bootloader.bin` | `f29111807dbbf3827bf3b744d305a92b6408d5f8b40734ed0011b23874dc19d4` |
| `partition_table/partition-table.bin` | `7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820` |

[verification.json](verification.json) identifies compiler, build result, source/input/configuration hashes and the artifact set. [source_sha256_at_archive.json](source_sha256_at_archive.json) preserves the compiled project snapshot; documentation is outside that source hash set. [native_commands.json](native_commands.json) records native commands. Local paths in these records are original build provenance and are not portable installation instructions.

Binary inspection retained all twelve kernels, the counted loop and the frozen input bytes. Iteration constants matched the manifest. The marker changes one output atomically, without a LOW write on the HIGH path, and a failed invocation reaches the latched-HIGH state without a normal falling edge. Application serial reporting and obsolete eight-signal symbols are absent. See [disassembly_benchmark.txt](disassembly_benchmark.txt) and [final_static_review.json](final_static_review.json).

These are native-build/static-inspection results, not a physical GPIO trace or energy measurement. Clock frequency, supply isolation, board programming, pulse order and PPK2 export require hardware revalidation. A structurally accepted one-wire recording cannot prove final verification completed if execution hangs LOW.

See the [measurement specification](../../../../README.md), [current-image state](../../../../../CURRENT_FIRMWARE.json) and [validation report](../../../../../docs/VALIDATION.md).
