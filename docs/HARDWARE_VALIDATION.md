# Hardware validation - 11 September 2026

This report records **energy-profiling-v5-common160** (release **v1.2.0**) and the preceding **energy-profiling-v4-max-clock** validation (release **v1.1.0**). It separates functional execution, programming of the measurement image and PPK2 energy acquisition. Exact image hashes and status are in the [common160 manifest](../profiles/common160/CURRENT_FIRMWARE.json) and [maximum-clock manifest](../CURRENT_FIRMWARE.json). Their separate archives retain the original images and source/build evidence.

## Common160 hardware observations

| Board | Functional execution at 160 MHz | Common160 measurement-image programming | Common160 PPK2 campaign |
|---|---|---|---|
| RP2040, Marble Pico | Twelve PASS events with exact call counts and DONE observed through USB CDC | Exact silent release UF2 installed through ROM mass storage; latest recorded Pico installation | Pending |
| NUCLEO-F446RE | Twelve PASS events with exact call counts and DONE observed through USART3/PC10 | Exact silent release BIN installed through ST-LINK mass storage; completed host transfer and no `FAIL.TXT` | Pending |
| ESP32-D0WD-V3 | Twelve PASS events with exact call counts and DONE observed through UART0 | Exact silent release bootloader, partition table and application installed; esptool verified all three segment hashes | Pending |

The [Pico common160 diagnostic record](../hardware/common160/2026-09-11/rp2040_diagnostic_01.json) identifies UF2 SHA-256 `b7ee4830b567f2764351bab8225099f294e271861236e9d8c54f493865e8a3f8`. Its [serial log](../hardware/common160/2026-09-11/rp2040_diagnostic_01.log) contains the checked configuration and complete workload sequence:

| Observation | Recorded common160 value |
|---|---|
| CPU frequency from clock API | 160000000 Hz |
| Peripheral clock | 48000000 Hz |
| Internal regulator selection / ready | 12, nominal 1.15 V / asserted |
| SSI Flash divider / derived clock | 4 / 40000000 Hz |
| JEDEC Flash identifier | `ef4017` |
| Profile / active core / platform check | `common160` / 0 / 1 |
| Functional sequence | Twelve PASS events with exact call counts and DONE |

After that diagnostic passed, the [programming record](../hardware/common160/2026-09-11/rp2040_measurement_programming_01.json) documents installation of the exact silent release UF2, SHA-256:

```text
7f0c61102d09e1cd75a1b94c2740926490ab6ba1ae178c9e575115cf853de0de
```

The host copy completed without error, and both the ROM volume and diagnostic USB CDC disappeared. This is the Pico's latest recorded programming state, replacing its earlier maximum-clock image. These observations do not establish flash readback, independent execution validation of the silent image or a PPK2 energy capture.

The [ESP32 common160 diagnostic record](../hardware/common160/2026-09-11/esp32_diagnostic_01.json) identifies application BIN SHA-256 `b52ff8c65d4cdc47c23a1c0509e9202617bc29d0986a12ccf7313cd89efa1c8a`. Its [programming record](../hardware/common160/2026-09-11/esp32_diagnostic_programming_01.json) and [esptool log](../hardware/common160/2026-09-11/esp32_diagnostic_programming_01.log) retain the three diagnostic segments and their verification. The [serial log](../hardware/common160/2026-09-11/esp32_diagnostic_01.log) records:

| Observation | Recorded ESP32 common160 value |
|---|---|
| CPU frequency from clock API | 160000000 Hz |
| APB clock | 80000000 Hz |
| Digital-bias selection | 4, corresponding to SDK nominal 1.10 V |
| Active core / platform check | 0 / 1 |
| Floating point / radio state | Single precision / uninitialized |
| Diagnostic transport | UART0, TX GPIO1, RX GPIO3, 115200 baud |
| Functional sequence | Twelve PASS events with exact call counts and DONE |

After that diagnostic passed, the [silent-image programming record](../hardware/common160/2026-09-11/esp32_measurement_programming_01.json) and [esptool log](../hardware/common160/2026-09-11/esp32_measurement_programming_01.log) document installation and successful hash verification of all three unchanged release segments:

| Silent common160 segment | Flash offset | SHA-256 |
|---|---|---|
| Bootloader | `0x1000` | `faa1aba03b3a385e6dbcc38883aa635abba2a8a4c9ff19f7cc9f393409f08e13` |
| Partition table | `0x8000` | `7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820` |
| Application | `0x10000` | `7889845c7f39b17531be9e553aa9d7d5fe239aa8727520f99001eb880a7e219a` |

The compiled DIO, 40 MHz, 4 MiB Flash settings were preserved. Common160 is the ESP32's latest recorded installation. The [post-programming UART observation](../hardware/common160/2026-09-11/esp32_measurement_uart_01.json) and [UART log](../hardware/common160/2026-09-11/esp32_measurement_uart_01.log) contain 304 bytes from one ROM boot during approximately 8.188 seconds after reset, with no application BENCH messages or panic detected. This short observation does not establish workload completion. Esptool's segment verification is distinct from an independent flash-readback attestation. No PPK2 capture or independent validation of the silent application's complete execution has been obtained.

The [STM32F446 common160 diagnostic record](../hardware/common160/2026-09-11/stm32f446_diagnostic_01.json) identifies BIN SHA-256 `7541759d66183f7c543ae682e30c092461908abdeac6f176ac920274a3e5493e`. Its [programming record](../hardware/common160/2026-09-11/stm32f446_diagnostic_programming_01.json) documents the preceding ST-LINK mass-storage transfer. The diagnostic used USART3 TX on target PC10 (CN7 pin 1), connected to detached ST-LINK CN3 pin 1 (RX), with common ground. The [serial log](../hardware/common160/2026-09-11/stm32f446_diagnostic_01.log) records:

| Observation | Recorded STM32 common160 value |
|---|---|
| CPU frequency from software configuration | 160000000 Hz, HSI-derived |
| APB1 / APB2 clocks | 40000000 / 80000000 Hz |
| RCC PLLCFGR / CFGR | `0x25005010` / `0x0000940a` |
| FPU access, CPACR | `0x00f00000`, full access |
| Flash ACR | `0x00000705`, five wait states with prefetch and instruction/data caches enabled |
| PWR CR / CSR | `0x0000c000` / `0x00004000`, Scale 1 ready and OverDrive disabled |
| TIM2 prescaler | 7999 |
| Profile / diagnostic transport | `common160` / USART3 PC10, 115200 baud |
| Functional sequence | Twelve PASS events with exact call counts and DONE |

After that diagnostic passed, the [measurement programming record](../hardware/common160/2026-09-11/stm32f446_measurement_programming_01.json) documents installation of the exact silent release BIN at `0x08000000`, SHA-256:

```text
ef7dbca813c2ba2d4b6ebd10dcff71f2fd167f4919cdc6b973e38286351fc6da
```

The host copy to the ST-LINK `NODE_F446RE` mass-storage volume completed without error; no `FAIL.TXT` was present after five seconds. Common160 is the STM32's latest recorded installation, replacing the earlier 180 MHz measurement image. These observations do not independently attest flash contents, validate the silent image's complete execution or provide PPK2 energy measurements.

All three common160 functional diagnostics passed and their silent measurement images were installed. All three boards still require common160 PPK2 pilots and ten accepted cold-boot captures each. The existing ten accepted ESP32 240 MHz captures remain unchanged and selected only for the maximum-clock campaign, with their original v3 manifest and expected-image provenance; no repeat 240 MHz acquisition is required.

## Recorded maximum-clock validation (v1.1.0)

| Board | Functional execution | Measurement-image programming | New PPK2 energy campaign |
|---|---|---|---|
| RP2040, Marble Pico | Twelve PASS events and DONE observed at the configured 200 MHz operating point | Serial-disabled UF2 programmed through ROM mass storage after the functional run | Pending |
| NUCLEO-F446RE | Twelve PASS events with exact call counts and DONE observed through a separate USART3/PC10 diagnostic image | Original release serial-disabled BIN reinstalled through ST-LINK mass storage after the functional run | Pending |
| ESP32-D0WD-V3 | Original capture/image provenance retained | Historical image identity retained; latest installation is common160 | Ten accepted regulator-removed 240 MHz captures retained with original v3 provenance; no repeat acquisition |

The RP2040 run reported:

| Observation | Recorded value |
|---|---|
| CPU frequency from clock API | 200000000 Hz |
| Peripheral clock | 48000000 Hz |
| Internal regulator selection | 12, corresponding to nominal 1.15 V |
| Internal regulator ready | Asserted |
| SSI Flash divider | 4 |
| Derived QSPI clock | 50000000 Hz |
| JEDEC Flash identifier | `ef4017` |
| Functional sequence | Twelve PASS events and DONE |

The JEDEC identifier indicates Winbond manufacturer/type and a 64-Mbit capacity code; it does not identify the precise device suffix or prove its read-mode timing limit. The firmware therefore retains QSPI at 50 MHz. The Pico-compatible SDK profile configures a 2 MiB address space; the observed capacity code does not change that build layout.

The maximum-clock RP2040 measurement UF2 has SHA-256:

```text
593f7e06dde7d7e03dc4f7bfc3ffe0ee877910841af8ed23819cdbeabc83257e
```

That 200 MHz image was programmed after the successful maximum-clock functional run and was subsequently replaced by the common160 UF2 recorded above. Its serial reporting and USB/UART interfaces are disabled; static inspection finds no diagnostic reporting entry points or JEDEC command in the measurement application. ROM-volume programming and USB disappearance are programming observations, not a flash-readback attestation or evidence of a complete PPK2 capture.

NUCLEO-F446RE functional validation passed using a separate diagnostic image with USART3 TX on PC10. The temporary wire connected target CN7 pin 1 (PC10) to detached ST-LINK CN3 pin 1 (RX), with common ground. This bypassed the open SB63 bridge that prevented the original PA2 TX signal from reaching header CN9 pin 2. The diagnostic transport change preserved the clock setup, kernels, inputs and call counts; the published measurement image was unchanged.

The [STM32 diagnostic record](../hardware/2026-09-11/stm32f446_pc10_diagnostic_01.json) contains twelve PASS events with the expected call counts and final DONE. It identifies diagnostic BIN SHA-256 `bad4ada326566d1dc029fdca394bfb2f6a389514877ff4e473746eea177f7b53` and records:

| Observation | Recorded value |
|---|---|
| CPU frequency from software configuration | 180000000 Hz |
| APB1 / APB2 clocks | 45000000 / 90000000 Hz |
| FPU access, CPACR | `0x00f00000`, full access |
| Flash ACR | `0x00000705`, five wait states with prefetch and instruction/data caches enabled |
| PWR CR / CSR | `0x0003c000` / `0x00034000`, Scale 1 and OverDrive configured and ready |
| TIM2 prescaler | 8999 |
| Functional sequence | Twelve PASS events with exact call counts and DONE |

The maximum-clock STM32 measurement BIN has SHA-256:

```text
9fa0531d09e2e55ab22d7f4eaa39d0a5a32b3d7c3c15cd6fda716621f6adfafd
```

This original 180 MHz release image was reinstalled after the successful maximum-clock diagnostic run through the ST-LINK `NODE_F446RE` mass-storage volume. The [measurement programming record](../hardware/2026-09-11/stm32f446_measurement_programming_02.json) reports transfer completion and no `FAIL.TXT` afterward. That installation was subsequently replaced by the common160 BIN recorded above. Flash readback and execution of the silent measurement image have not been independently validated, and the new maximum-clock PPK2 campaign remains pending. These follow-up hardware observations are recorded separately from the unchanged archived release build records.

## How to interpret this evidence

The recorded clocks and regulator fields are configuration/register observations. They are not an external frequency calibration or a measured internal voltage. STM32's nominal HSI-derived frequency likewise needs independent physical validation; increasing the configured clock does not eliminate oscillator error. All functional runs use a PC connection and must remain separate from energy measurements.

Functional diagnostics and collection commands are described in [BUILD_AND_TEST.md](BUILD_AND_TEST.md). After any functional run, install the matching measurement image and record its hash and programming evidence. The physical acquisition uses only PPK2 power, ground, logic reference and one RUN wire, with DUT USB/UART/programmers disconnected or isolated.

## Measurements still required for the maximum-clock campaign

Acquire and review a new PPK2 pilot for RP2040 and STM32 before the ten accepted full-suite cold boots for each. Confirm the supply rail, physical clock, twelve RUN windows, LOW gaps, fault behavior, export format and capture integrity. The active-idle reference must come from each new capture. Successful functional output and firmware programming do not provide workload energy values.

Existing waveform datasets remain the preceding campaign's evidence and have not been relabeled. Historical firmware and validation records remain available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0). Follow the [current acquisition protocol](PROTOCOL.md) and consult [validation status](VALIDATION.md) when combining retained ESP32 data with replacement measurements.
