# Historical hardware functional validation - 9 September 2026

**Historical scope: energy-profiling-v2-f446, the eight-signal protocol.** This report does not establish a hardware run of the current single-GPIO source. The old programmed-image manifest is preserved at [firmware_manifest_v2.json](../hardware/2026-09-09/firmware_manifest_v2.json); its SHA-256 is e4f83daaeb2d3fdc684b1fc310505fdce41e7cc1b63e82f65dcf26679d5c7c4b.

All three boards successfully executed **12/12 algorithms**, using configured call counts and result verification on the MCU. Each log contains BOOT, twelve START/PASS pairs and DONE. After validation, each board was loaded with that version's measurement image, without application serial diagnostics.

| Identified board | Reported startup configuration | Functional-test transport | Result |
|---|---|---|---|
| ESP32-D0WD-V3, revision 3.1, 4 MB Flash | CPU 240 MHz, core0, single-precision FPU, radio uninitialized | UART0 through CH340, COM4, 115200 | 12 PASS + DONE |
| Raspberry Pi Pico, RP2040 | CPU 133 MHz, core0, software floating point | USB CDC, COM7 after programming | 12 PASS + DONE |
| NUCLEO-F446RE, IDCODE 10006421, 512 KiB Flash | HSI + PLL, CPU 100 MHz, APB1 25 MHz, APB2 50 MHz, CPACR 00f00000 | USART2 through ST-LINK VCP, COM6, 115200 | 12 PASS + DONE |

Frequencies were inferred by firmware from hardware configuration, not externally calibrated. COM numbers can change between connections. These runs used PC power/instrumentation, without PPK2 energy acquisition.

## Preserved evidence

- ESP32: [serial log](../hardware/2026-09-09/esp32_diagnostic_01.log), [result and hashes](../hardware/2026-09-09/esp32_diagnostic_01.json), [serial-off programming record](../hardware/2026-09-09/esp32_measurement_programming.json).
- Pico: [serial log](../hardware/2026-09-09/rp2040_diagnostic_01.log), [result and hashes](../hardware/2026-09-09/rp2040_diagnostic_01.json), [USB/UART-off programming record](../hardware/2026-09-09/rp2040_measurement_programming.json).
- Nucleo: [serial log](../hardware/2026-09-09/stm32_diagnostic_01.log), [result and hashes](../hardware/2026-09-09/stm32_diagnostic_01.json), [serial-off programming record](../hardware/2026-09-09/stm32_measurement_programming.json).

The six historical builds remain in firmware/targets/<target>/build_verified/{diagnostic,measurement}; the Nucleo target is stm32f446. Even earlier manifests directly in build_verified retain their own snapshot identity. The root [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) now distinguishes this last programmed state from later unprogrammed candidates.

ESP32 was flashed through esptool, verifying written hashes for bootloader, partitions and application. Nucleo was programmed through the ST-LINK NODE_F446RE volume without FAIL.TXT; Pico used UF2 on the ROM RPI-RP2 volume. USB debug drivers for ST-LINK/picoboot were unavailable, but volume-based programming and serial feedback worked. No global drivers were installed.

The UART-off Nucleo produced no data during an eight-second observation. ESP32 with application UART disabled emitted only immutable ROM boot messages. The USB-disabled Pico disappeared from the serial-port list. Those observations and binary inspection support diagnostic shutdown; they do not independently demonstrate the full GPIO sequence in the measurement image.

The initial STM32 log was collected before the serial parser gained its trailing-data drain. Its complete saved sequence was independently checked for all twelve results and no recorded ERROR; that check cannot certify bytes the old collector did not record.

## Reproducing a historical functional run

Use the matching historical diagnostic binary and its original experiment configuration, not the current single-GPIO source/manifest as if they were the same build. The collector command shape used for ESP32 was:

```powershell
python tools/serial_validation.py --board esp32 --port COM4 --reset esp32 --firmware firmware/targets/esp32/build_verified/diagnostic/energy_bench_esp32.bin --output hardware/new_esp32_run
```

For Nucleo, start collection on its VCP before resetting/programming. Pico --board rp2040 --port auto waits for USB CDC 2E8A:000A, so start the collector before loading UF2. After installing a USB-disabled image, hold BOOTSEL while connecting Pico USB to return to ROM programming mode.

The collector refuses to overwrite existing files. Log timestamps are host times and are not performance/energy measurements. Floating-point result digests can differ across architectures; FFT/DCT acceptance uses numerical references/tolerances, not bitwise digest equality.

## Current campaign follow-up

The new one-wire campaign needs its own programming record and hardware revalidation. Confirm the twelve pulse windows, fault latch, LOW intervals, isolated 3V3 supply, real voltage and clock frequency, and Nucleo bridge preparation under the [current protocol](PROTOCOL.md). The former IDLE_VALID/ERROR/DONE signals do not exist in the new measurement image. Historical UART results and host tests do not replace these checks or PPK2 energy captures.
