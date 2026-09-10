# stm32f446 single-GPIO measurement build

Native compilation and linking passed for **energy-profiling-v3-single-gpio**, experiment schema 2, with **BENCH_DIAGNOSTICS=OFF**. This archive was produced on 10 September 2026. **It has not been flashed or executed on hardware.** Earlier sibling measurement/diagnostic archives retain their historical eight-signal protocol.

The only measurement output is **PC0**, connected to PPK2 D0. Normal HIGH encloses one fixed-count batch; LOW is outside. Kernel identity is inferred from twelve pulses in fixed order. A detected error latches HIGH until reset; there is no separate ID, ERROR, DONE or IDLE_VALID output.

Experiment-manifest SHA-256: `e458d429cf49d803dd7dbfb5373e2bcac49e21f572466affb464c4a9971d1075`.

| Artifact | SHA-256 |
|---|---|
| `energy_bench_stm32f446.elf` | `3b34ea640b77521a74241932bbe0d66c603bd767da418b06ddd895b6a1e29190` |
| `energy_bench_stm32f446.bin` | `159849461b7f3ade75b4b4674f4302327964ec31fc1404bc8609fd47f9e80b2d` |
| `energy_bench_stm32f446.map` | `91a7b16007c15273fb00b5bcc7e545bd7a8f5e612b6ca4cc35314b795cc5c0c1` |
| `energy_bench_stm32f446.hex` | `34d340aec994ba749c04c1e9c5024378b599ae5beac9fc2d3682700ad60941ff` |

[verification.json](verification.json) identifies compiler, build result, source/input/configuration hashes and the artifact set. [source_sha256_at_archive.json](source_sha256_at_archive.json) preserves the compiled project snapshot; documentation is outside that source hash set. [native_commands.json](native_commands.json) records native commands. Local paths in these records are original build provenance and are not portable installation instructions.

Binary inspection retained all twelve kernels, the counted loop and the frozen input bytes. Iteration constants matched the manifest. The marker changes one output atomically, without a LOW write on the HIGH path, and a failed invocation reaches the latched-HIGH state without a normal falling edge. Application serial reporting and obsolete eight-signal symbols are absent. See [disassembly_benchmark.txt](disassembly_benchmark.txt) and [final_static_review.json](final_static_review.json).

These are native-build/static-inspection results, not a physical GPIO trace or energy measurement. Clock frequency, supply isolation, board programming, pulse order and PPK2 export require hardware revalidation. A structurally accepted one-wire recording cannot prove final verification completed if execution hangs LOW.

See the [measurement specification](../../../../README.md), [current-image state](../../../../../CURRENT_FIRMWARE.json) and [validation report](../../../../../docs/VALIDATION.md).
