# Verified ESP32 native build

> Historical eight-signal archive. The binary, logs and hashes below describe their original snapshot, not the current single-GPIO campaign. Current candidates are identified separately in CURRENT_FIRMWARE.json.

The native ESP-IDF 5.5.4 build completed successfully. These are candidate firmware
artifacts for a later hardware pilot; no board was flashed or executed.

The application is 165648 bytes. `flash_manifest.json` records the complete set,
including SHA-256 hashes, offsets and DIO/40 MHz/4 MiB flash settings:

| Artifact | Offset | Bytes |
|---|---:|---:|
| `bootloader/bootloader.bin` | `0x1000` | 18016 |
| `partition_table/partition-table.bin` | `0x8000` | 3072 |
| `energy_bench_esp32.bin` | `0x10000` | 165648 |

The preserved directory layout makes every relative path in `flash_args` resolve
from this directory. The file is provenance and is not executed automatically.
ELF, map, resolved sdkconfig, full build/configuration logs and compile commands
belong to this build. Local absolute paths inside diagnostic files are provenance,
not portable SDK installation paths.

Static inspection confirms all twelve kernel symbols and dispatch calls survive.
The runner still calls `bench_kernel_run` inside the fixed-count loop. `my_dct`
contains Xtensa `mul.s`/`add.s`; floating-point verification therefore concerns the
actual kernel, not just the startup probe. Double arithmetic remains distinct.
GPIO W1TC/W1TS stores and `memw` barriers are present; IDLE_VALID and DONE are
assembled for one status-setting write. Relevant function bodies are collected
in `decisive_disassembly.txt`.

`benchmark_compile_commands.json` isolates the five project compilation units.
Their last optimization flag is `-O2`, after SDK defaults, and all use
`-fno-fast-math -ffp-contract=off -fno-lto`. The compiler is Espressif
`esp-14.2.0_20260121`, GCC 14.2.0. `pip_freeze.txt` records package versions from
the isolated IDF 5.5 Python environment. `sdk_source_sha256.json` records the
observed packaged SDK tree, excluding Python bytecode caches and `.git`.

`verification.json` contains hashes of every common source/configuration/input,
the ESP32 target sources, compiler executables, SDK manifest and artifacts.
Changing any source or experimental configuration requires a new build and hashes.
