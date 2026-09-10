# Building and checking the project

Run commands from the Energy Profiling project root. External SDK trees and intermediate build directories are dependencies, not experiment source. Source, inputs, configuration and delivered artifacts have separate hashes. Current source: **energy-profiling-v3-single-gpio**, experiment schema 2. Older build_verified archives retain their original eight-signal snapshots.

## Host checks

Requirements: Python 3.11+, GCC, CMake and Ninja. Kernel and capture-analyzer checks use no external Python packages.

```powershell
python tools/generate_inputs.py --check
python tests/kernel_tests/test_kernels.py
python -m unittest discover -s tests -p test_capture_analysis.py -v
cmake -S . -B build/host -G Ninja
cmake --build build/host
ctest --test-dir build/host --output-on-failure
```

Kernel checks compile this project's actual common C implementation and compare it with independent references, including deliberately corrupted outputs. Runner checks simulate hardware/kernels and verify twelve pulses, exact call counts, pauses and latched-HIGH failure paths. Parser tests use synthetic currents and boundaries with known results. Details: [kernel tests](../tests/kernel_tests/README.md), [capture format](capture_format.md).

`generate_inputs.py --check` does not write files. Without --check, it deliberately regenerates data/headers from the script definition and configuration manifest. Numerical references are frozen in bench_golden.h; changing inputs requires deliberate reference regeneration and revalidation as described in the kernel-test README.

## Pico and STM32

Pico and STM32 SDK versions and archive hashes are pinned in their target sdk.lock.json files. The fetcher checks archives and extracted trees, does not follow a floating Git branch and does not modify global installations.

```powershell
python scripts/fetch_native_sdks.py --help
Get-Help scripts/build_arms.ps1
```

SDK/toolchain path arguments are explicit. The campaign uses GNU Arm Embedded GCC 9.2.1 20191025, Pico SDK 2.2.0, cmsis-device-f4 v2.6.11 and CMSIS_5 5.9.0. STM32 uses direct registers/CMSIS, without Arduino or a periodic HAL runtime.

Direct STM32 builds need ARM_GCC_BIN, STM32_CMSIS_DEVICE_PATH and CMSIS_CORE_PATH. Pico needs PICO_SDK_PATH and the ARM toolchain. Use the complete measurement commands in the [F446 target](../firmware/targets/stm32f446/README.md) and [Pico target](../firmware/targets/rp2040/README.md). The helper targets F446; historical F411 CMake is deliberately blocked against the current campaign.

## ESP32

Use ESP-IDF **5.5.4**, its matching Espressif compiler and Python environment. Do not automatically reuse another IDF major-version environment. The IDF version is checked by target CMake; the packaged framework identity is framework-espidf 3.50504. ESP32 archive provenance records the package, compiler and observed SDK source hashes rather than a target sdk.lock.json.

From a prepared IDF 5.5.4 terminal:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32-single-gpio -DBENCH_DIAGNOSTICS=OFF build
```

Retain application, bootloader, partition table and flashing arguments together; application BIN alone is not a complete blank-device image. The profile uses CPU 240 MHz, FreeRTOS unicore, uninitialized radio, PM/task watchdog disabled and application logs/console off. System interrupts remain part of the documented IDF platform.

## Artifact status and physical checks

New single-GPIO artifacts are in build_verified/single_gpio_measurement for ESP32, RP2040 and STM32F446. They record native build evidence and hashes. [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) separates those candidates from the last programmed images; **new compilation does not mean the board was flashed**. The prior installed image manifest is preserved byte-for-byte at [firmware_manifest_v2.json](../hardware/2026-09-09/firmware_manifest_v2.json).

Before acquisition, check real DUT voltage, the one RUN pin, exported pulses, clock frequency and latched-fault behavior. F446's nominal HSI16/PLL configuration yields 100 MHz, but actual frequency/drift requires external validation. PC-powered UART/USB functional tests are not energy measurements. Nucleo direct 3V3 power requires the bridge preparation described in the [protocol](PROTOCOL.md).

## Separate functional diagnostic builds

This build/test section is separate from the measurement specification. BENCH_DIAGNOSTICS=ON enables functional feedback; OFF is the default measurement setting. Use distinct build directories:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32-single-gpio-diagnostic -DBENCH_DIAGNOSTICS=ON build
idf.py -C firmware/targets/esp32 -B build/esp32-single-gpio -DBENCH_DIAGNOSTICS=OFF build
```

On ARM, scripts/build_arms.ps1 -Diagnostics selects diagnostics; omitting it selects measurement. Default Pico diagnostics use USB CDC, requiring Pico SDK's pinned TinyUSB gitlink. The measurement image does not need TinyUSB. Prepare a separate dependency tree:

```powershell
python scripts/fetch_diagnostic_usb.py --dest C:/energy-deps
$env:PICO_TINYUSB_PATH = 'C:/energy-deps/tinyusb-86ad6e56c170'
./scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/energy-deps -BuildRoot build/arm-diagnostic -Only rp2040 -Diagnostics
```

TinyUSB commit is 86ad6e56c1700e85f1c5678607a762cfe3aa2f47. The fetcher checks archive SHA-256 3011c90c128988012b553e5d2f0a90bc0b64046591c964bc1f9f6659edcd7e4b, bounds size/extraction paths and materializes two pinned internal documentation symlinks as recorded copies. It records provenance in .energy_diagnostic_usb.json and leaves the verified Pico SDK tree unchanged. Offline --archive uses the same hash requirement.

For external UART0 instead of USB, configure Pico with BENCH_DIAGNOSTIC_TRANSPORT=UART0 and BENCH_DIAGNOSTICS=ON. It uses GPIO0 TX/GPIO1 RX, 115200 baud, 8N1, without TinyUSB. ESP32 diagnostics use UART0 GPIO1/3; F446 uses USART2 TX PA2 through ST-LINK VCP. These interfaces can change consumption even when normal reports are outside batches and must not be used for energy acquisition.

The new runner performs normal START reporting before the active idle pause. An ERROR report can accompany the deliberately latched HIGH failure state; that state is not a valid measurement batch. Diagnostic DONE is a serial event after final verification/idle, not an additional GPIO output.

The serial collector needs pyserial. It records BOOT, twelve START/PASS pairs with exact call counts and DONE, rejecting ERROR/malformed sequences. Its timestamps are host times, never benchmark duration. It does not independently attest that the file supplied with --firmware is the executing image. Use the matching binary and experiment configuration. The [hardware report](HARDWARE_VALIDATION.md) records historical runs, not a new one-wire hardware execution.

```powershell
python -m unittest discover -s tests -p test_serial_validation.py -v
```
