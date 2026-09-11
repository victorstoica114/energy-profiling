# Hardware validation - 11 September 2026

This report concerns **energy-profiling-v4-max-clock**, release **v1.1.0**. It separates functional execution, programming of the measurement image and PPK2 energy acquisition. Exact image hashes and recorded status are in [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json); archived images and source/build evidence are under each target's `build_verified/max_clock_measurement`.

## Observed current status

| Board | Functional execution | Measurement-image programming | New PPK2 energy campaign |
|---|---|---|---|
| RP2040, Marble Pico | Twelve PASS events and DONE observed at the configured 200 MHz operating point | Serial-disabled UF2 programmed through ROM mass storage after the functional run | Pending |
| NUCLEO-F446RE | Twelve PASS events with exact call counts and DONE observed through a separate USART3/PC10 diagnostic image | Original release serial-disabled BIN reinstalled through ST-LINK mass storage after the functional run | Pending |
| ESP32-D0WD-V3 | Current build/programming status is recorded in CURRENT_FIRMWARE.json | See current manifest | Earlier accepted captures may be reused only with their original provenance and verified configuration equivalence |

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

The final RP2040 measurement UF2 has SHA-256:

```text
593f7e06dde7d7e03dc4f7bfc3ffe0ee877910841af8ed23819cdbeabc83257e
```

That image was programmed after the successful functional run. Its serial reporting and USB/UART interfaces are disabled; static inspection finds no diagnostic reporting entry points or JEDEC command in the measurement application. ROM-volume programming and USB disappearance are programming observations, not a flash-readback attestation or evidence of a complete PPK2 capture.

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

The final STM32 measurement BIN has SHA-256:

```text
9fa0531d09e2e55ab22d7f4eaa39d0a5a32b3d7c3c15cd6fda716621f6adfafd
```

This original release image was reinstalled after the successful diagnostic run through the ST-LINK `NODE_F446RE` mass-storage volume. The [measurement programming record](../hardware/2026-09-11/stm32f446_measurement_programming_02.json) reports transfer completion and no `FAIL.TXT` afterward. Flash readback and execution of the silent measurement image have not been independently validated, and the new PPK2 campaign remains pending. These follow-up hardware observations are recorded separately from the unchanged archived release build records.

## How to interpret this evidence

The recorded clocks and regulator fields are configuration/register observations. They are not an external frequency calibration or a measured internal voltage. STM32's nominal HSI-derived frequency likewise needs independent physical validation; increasing the configured clock does not eliminate oscillator error. All functional runs use a PC connection and must remain separate from energy measurements.

Functional diagnostics and collection commands are described in [BUILD_AND_TEST.md](BUILD_AND_TEST.md). After any functional run, install the matching measurement image and record its hash and programming evidence. The physical acquisition uses only PPK2 power, ground, logic reference and one RUN wire, with DUT USB/UART/programmers disconnected or isolated.

## Measurements still required

Acquire and review a new PPK2 pilot for RP2040 and STM32 before the ten accepted full-suite cold boots for each. Confirm the supply rail, physical clock, twelve RUN windows, LOW gaps, fault behavior, export format and capture integrity. The active-idle reference must come from each new capture. Successful functional output and firmware programming do not provide workload energy values.

Existing waveform datasets remain the preceding campaign's evidence and have not been relabeled. Historical firmware and validation records remain available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0). Follow the [current acquisition protocol](PROTOCOL.md) and consult [validation status](VALIDATION.md) when combining retained ESP32 data with replacement measurements.
