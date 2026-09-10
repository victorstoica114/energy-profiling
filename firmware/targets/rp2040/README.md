# RP2040 native target

Board profile: Raspberry Pi Pico (RP2040, 2 MiB configured Flash), native Pico SDK.
CPU clock = 133 MHz. Core 1 is never launched. RP2040 uses software floating point;
this is recorded rather than emulating an unavailable FPU setting. SDK startup and
Flash boot code are retained. With `BENCH_DIAGNOSTICS=OFF` (the default), USB/UART
stdio are disabled; UART0/1, USB and ADC are held in reset, and the USB/ADC clocks
are stopped before measurement. GPIO0/1 are disconnected with no pulls. GPIO25 LED is LOW/off.
Core 0 reserves 4 KiB of stack in the SDK's dedicated SCRATCH_Y bank. The main
work buffers are static. Link maps record the memory layout of each verified build.

| PPK2 digital bit | Signal | MCU GPIO |
|---|---|---|
| D0 | RUN | 2 |
| D1 | ID bit 0 | 3 |
| D2 | ID bit 1 | 4 |
| D3 | ID bit 2 | 5 |
| D4 | ID bit 3 | 6 |
| D5 | IDLE_VALID | 7 |
| D6 | ERROR | 8 |
| D7 | DONE | 9 |

These are dedicated digital outputs, not LEDs. RUN is low while ID/status changes,
then asserted last. Follow the root wiring document for ground and PPK2 logic supply.

Clock configuration is checked both against `clock_get_hz` and Pico's hardware
frequency counter: 133000 kHz ±0.1% relative to clk_ref. This does not certify an
external oscillator against a laboratory frequency standard. GPIO measurement
timings always come from PPK2. The raw hardware timer is read only for fixed
control gaps, which busy-poll at the configured CPU frequency: active idle, not sleep.

Pinned SDK: [Pico SDK 2.2.0](https://github.com/raspberrypi/pico-sdk/tree/a1438dff1d38bd9c65dbd693f0e5db4b9ae91779),
commit `a1438dff1d38bd9c65dbd693f0e5db4b9ae91779`. TinyUSB is unnecessary for the
measurement profile and the optional hardware-UART diagnostic profile. The default
diagnostic profile enables USB CDC and needs Pico SDK's exact TinyUSB gitlink,
commit `86ad6e56c1700e85f1c5678607a762cfe3aa2f47`. Verified compiler: GNU Arm Embedded
GCC 9.2.1 20191025. Run all commands below from the project root, using short paths
for dependencies on Windows. Replace the example compiler path with its installation.

Prepare the SDK and the separate USB dependency:

```powershell
python scripts/fetch_native_sdks.py --dest C:/energy-deps --only rp2040
python scripts/fetch_diagnostic_usb.py --dest C:/energy-deps
$env:PICO_TOOLCHAIN_PATH = 'C:/path/to/gcc'
```

The USB fetcher downloads
[the official TinyUSB commit archive](https://codeload.github.com/hathach/tinyusb/zip/86ad6e56c1700e85f1c5678607a762cfe3aa2f47),
requires SHA256 `3011c90c128988012b553e5d2f0a90bc0b64046591c964bc1f9f6659edcd7e4b`,
and bounds archive size and extraction paths. It creates
`C:/energy-deps/tinyusb-86ad6e56c170` and verifies that tree on subsequent calls.
The two pinned documentation symlinks are materialized as copies of their internal
targets and recorded in `.energy_diagnostic_usb.json`; SDK and source files are
unmodified. For an offline copy, add `--archive C:/path/to/tinyusb.zip`; the same
archive hash is required. Do not copy TinyUSB into the already verified SDK tree.

Build USB diagnostic ON and measurement OFF in distinct directories:

```powershell
cmake -S firmware/targets/rp2040 -B build/rp2040-diagnostic -G Ninja -DPICO_SDK_PATH=C:/energy-deps/pico-sdk-a1438dff1d38 -DPICO_TINYUSB_PATH=C:/energy-deps/tinyusb-86ad6e56c170 -DBENCH_DIAGNOSTICS=ON -DBENCH_DIAGNOSTIC_TRANSPORT=USB
cmake --build build/rp2040-diagnostic --parallel
cmake -S firmware/targets/rp2040 -B build/rp2040-measurement -G Ninja -DPICO_SDK_PATH=C:/energy-deps/pico-sdk-a1438dff1d38 -DBENCH_DIAGNOSTICS=OFF
cmake --build build/rp2040-measurement --parallel
```

USB diagnostics use CDC VID `2E8A`, PID `000A`, with a bounded 5-second startup wait
for the host. CONFIG and BOOT/START/PASS/DONE/ERROR report functional status, without
MCU benchmark timestamps. USB remains active for this test profile, which must not
be used for energy measurement. The OFF image does not enumerate as a USB serial
port; use GPIO markers to verify completion, because terminal silence proves neither
success nor failure.

The existing ARM helper also accepts the dependency through the environment, as
supported by Pico SDK. Set it before `-Diagnostics`; use a fresh build directory if
a previous CMake cache contains another TinyUSB path:

```powershell
$env:PICO_TINYUSB_PATH = 'C:/energy-deps/tinyusb-86ad6e56c170'
./scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/energy-deps -BuildRoot build/arm-diagnostic -Only rp2040 -Diagnostics
```

For an external 3.3 V serial adapter instead of USB CDC, select UART0 TX GPIO0/RX
GPIO1, 115200 baud, 8N1. This optional diagnostic variant leaves USB disabled and
does not need TinyUSB:

```powershell
cmake -S firmware/targets/rp2040 -B build/rp2040-diagnostic-uart -G Ninja -DPICO_SDK_PATH=C:/energy-deps/pico-sdk-a1438dff1d38 -DBENCH_DIAGNOSTICS=ON -DBENCH_DIAGNOSTIC_TRANSPORT=UART0
cmake --build build/rp2040-diagnostic-uart --parallel
```

CMake emits ELF, BIN, HEX, map and disassembly, without downloading picotool.
For UF2, an existing official Pico `elf2uf2` tool can convert the ELF:

```powershell
elf2uf2 build/rp2040-diagnostic/energy_bench_rp2040.elf build/rp2040-diagnostic/energy_bench_rp2040.uf2
elf2uf2 build/rp2040-measurement/energy_bench_rp2040.elf build/rp2040-measurement/energy_bench_rp2040.uf2
```

Current verified archives are [USB diagnostic](build_verified/diagnostic/README.md),
[measurement](build_verified/measurement/README.md), and
[optional UART0 diagnostic](build_verified/diagnostic_uart/README.md). Each includes
ELF/BIN/UF2, compiler commands, logs, source snapshots and artifact hashes in
`verification.json`. The USB archive also records its TinyUSB provenance. Existing
files directly in the parent `build_verified` directory are historical.

Do not alter the board profile to accommodate a different physical board silently.
Compilation/static checks do not constitute a test on hardware.
Clock API details: [official Pico SDK](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#hardware_clocks).
