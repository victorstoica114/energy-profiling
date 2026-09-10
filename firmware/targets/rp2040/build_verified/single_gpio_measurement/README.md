# rp2040 single-GPIO measurement build

Native compilation and linking passed for **energy-profiling-v3-single-gpio**, experiment schema 2, with **BENCH_DIAGNOSTICS=OFF**. This archive was produced on 10 September 2026. **It has not been flashed or executed on hardware.** Earlier sibling measurement/diagnostic archives retain their historical eight-signal protocol.

The only measurement output is **GPIO2**, connected to PPK2 D0. Normal HIGH encloses one fixed-count batch; LOW is outside. Kernel identity is inferred from twelve pulses in fixed order. A detected error latches HIGH until reset; there is no separate ID, ERROR, DONE or IDLE_VALID output.

Experiment-manifest SHA-256: `e458d429cf49d803dd7dbfb5373e2bcac49e21f572466affb464c4a9971d1075`.

| Artifact | SHA-256 |
|---|---|
| `energy_bench_rp2040.elf` | `1f95859155cbf8a9368d47ff8f1c7ff8a817ba70cc0a8ecfe669cb3748f71eba` |
| `energy_bench_rp2040.bin` | `d96f5cad69eb9fd587e880992b42387366bc6515d11301c7db8698da87c02458` |
| `energy_bench_rp2040.elf.map` | `e81a23aacfdb93b5daafe111636d8dda8cd23b247b1c06da305cede1bdb62d1e` |
| `energy_bench_rp2040.uf2` | `85ccf6b07845d379e9b647698950b2bffca27c34174072c9c67d34f648d84e15` |
| `energy_bench_rp2040.hex` | `cb281ec80d0074cef75dcdaeb726f4511e92d0342102d68bb526cf49462ef225` |

[verification.json](verification.json) identifies compiler, build result, source/input/configuration hashes and the artifact set. [source_sha256_at_archive.json](source_sha256_at_archive.json) preserves the compiled project snapshot; documentation is outside that source hash set. [native_commands.json](native_commands.json) records native commands. Local paths in these records are original build provenance and are not portable installation instructions.

Binary inspection retained all twelve kernels, the counted loop and the frozen input bytes. Iteration constants matched the manifest. The marker changes one output atomically, without a LOW write on the HIGH path, and a failed invocation reaches the latched-HIGH state without a normal falling edge. Application serial reporting and obsolete eight-signal symbols are absent. See [disassembly_benchmark.txt](disassembly_benchmark.txt) and [final_static_review.json](final_static_review.json).

These are native-build/static-inspection results, not a physical GPIO trace or energy measurement. Clock frequency, supply isolation, board programming, pulse order and PPK2 export require hardware revalidation. A structurally accepted one-wire recording cannot prove final verification completed if execution hangs LOW.

See the [measurement specification](../../../../README.md), [current-image state](../../../../../CURRENT_FIRMWARE.json) and [validation report](../../../../../docs/VALIDATION.md).
