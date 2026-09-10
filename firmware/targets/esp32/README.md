# ESP32 native target

Classic ESP32 DevKit profile, native ESP-IDF **5.5.4**, CPU 240 MHz. Build-time
checks require FreeRTOS unicore mode (benchmark on CPU0, CPU1 disabled), PM disabled,
Bluetooth disabled and task watchdog disabled. The interrupt watchdog and periodic
FreeRTOS tick remain enabled: long fixed-count DCT loops are allowed without an
idle-task watchdog reset, while interrupts are not globally masked. This RTOS
background is part of this configuration and is not claimed identical to bare metal.

| PPK2 digital bit | Signal | MCU GPIO |
|---|---|---|
| D0 | RUN | 18 |
| D1 | ID bit 0 | 19 |
| D2 | ID bit 1 | 21 |
| D3 | ID bit 2 | 22 |
| D4 | ID bit 3 | 23 |
| D5 | IDLE_VALID | 25 |
| D6 | ERROR | 26 |
| D7 | DONE | 27 |

These GPIOs are dedicated logic outputs, without LEDs. RUN is lowered before an
identity/status update and raised last. Follow the root fixture wiring document.
GPIO bank writes raise final IDLE_VALID and DONE together. Clearing IDLE_VALID
later preserves DONE without a low glitch. The generated manifest pin map and
CPU frequency are compile-time checked against this target.

No code initializes Wi-Fi or Bluetooth. `esp_wifi_get_mode` must return
`ESP_ERR_WIFI_NOT_INIT` before a sequence or subsequent lot may proceed. This
explicitly rejects an initialized but merely disconnected Wi-Fi driver. The Wi-Fi
component is linked to query this state; linking it is not starting the radio.
With `BENCH_DIAGNOSTICS=OFF` (the default), the harness resets and gates UART0/1/2
and disables GPIO1/3 without pulls. It initializes no console. Immutable ROM boot
text can precede application initialization and the settling period; it is outside
acquisition windows. PM/automatic sleep and frequency scaling are disabled.

`BENCH_DIAGNOSTICS=ON` enables UART0 at 115200 baud, 8N1, TX GPIO1/RX GPIO3.
It emits a `BENCH CONFIG` line and BOOT/START/PASS/DONE/ERROR events; each write
finishes before returning, and the common runner reports outside RUN and IDLE_VALID.
This profile validates functional execution with USB/UART connected. It is unsuitable
for energy acquisition even though the kernels are the same.

CPU clock is checked with the native clock-tree API and the execution core checked
at runtime; this validates configured state, not external oscillator metrology.
A volatile float probe checks an executable FP path; final ELF inspection must
also verify float instructions in the actual kernels. Crypto kernels are the common
software implementation, without calls to ESP hardware crypto entry points.

GPTimer at 1 MHz is used only for control gaps. The gap routine busy-polls its count
and stops the timer before returning. It never determines a benchmark duration.
These are active control idle intervals. The scheduler-parking state at the end is
outside IDLE_VALID. The common runner controls RUN and exports no MCU timestamps.

Pinned toolchain: Espressif GCC `esp-14.2.0_20260121` (GCC 14.2.0), as required by
ESP-IDF 5.5.4 `tools/tools.json`. Activate that IDF's environment with its matching
Python dependencies and compiler on PATH. Run these commands from the project root;
use separate build directories for the two profiles:

```powershell
cmake -S firmware/targets/esp32 -B build/esp32-diagnostic -G Ninja -DIDF_TARGET=esp32 -DBENCH_DIAGNOSTICS=ON
cmake --build build/esp32-diagnostic --parallel
cmake -S firmware/targets/esp32 -B build/esp32-measurement -G Ninja -DIDF_TARGET=esp32 -DBENCH_DIAGNOSTICS=OFF
cmake --build build/esp32-measurement --parallel
```

The equivalent IDF wrapper commands are:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32-diagnostic -DBENCH_DIAGNOSTICS=ON build
idf.py -C firmware/targets/esp32 -B build/esp32-measurement -DBENCH_DIAGNOSTICS=OFF build
```

Use a fresh build directory and retain the generated `sdkconfig`, build log, ELF,
map and binary hashes. Defaults cannot silently override an existing conflicting
sdkconfig: compile-time/runtime gates reject the essential profile mismatches.
No flash or monitor command is run automatically. A successful build still requires
the hardware acceptance procedure before any new scientific data is accepted.

Both current native builds passed. Use the current
[diagnostic archive](build_verified/diagnostic/README.md) for functional UART tests
and [measurement archive](build_verified/measurement/README.md) for the serial-off
image. Each records artifact SHA256 hashes in `verification.json`, along with its
ELF, map, compiler commands, logs, symbol checks and source snapshot. ESP32 archives
also contain the bootloader, partition table and `flash_args`. Their bootloader
headers are already DIO/40 MHz/4 MB; actual flash verification is recorded separately
with the hardware test. Files directly in the parent `build_verified` directory are
historical. A silent serial terminal does not prove workload completion; the OFF
image requires the digital markers to validate its complete sequence.

Official references: [IDF 5.5.4](https://github.com/espressif/esp-idf/tree/v5.5.4),
[clock-tree API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/peripherals/clk_tree.html),
[Wi-Fi driver state](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/network/esp_wifi.html),
[watchdogs](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/system/wdts.html).
