# Energy Profiling

Firmware and offline analysis for measuring ESP32, RP2040 and **NUCLEO-F446RE** workloads with Nordic PPK2. Release **v1.2.0** adds a **common 160 MHz comparison** (`energy-profiling-v5-common160`) alongside the maximum-clock experiment (`energy-profiling-v4-max-clock`, originally released as v1.1.0). Both use experiment schema 2 and one digital output to mark the twelve fixed-count workload batches; the algorithm is inferred from pulse order.

The default remains **max_clock**, so existing acquisition commands keep their current meaning. Select **common160** explicitly for the new comparison. See the [160 MHz configuration and campaign guide](docs/COMMON_CLOCK_160.md), [its exact image manifest](profiles/common160/CURRENT_FIRMWARE.json) and the [release downloads](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.2.0). All three boards require ten new captures at 160 MHz; these data are separate from the maximum-clock campaign.

The common C library executes twelve algorithms on identical inputs across boards, retaining the repetition counts documented in the original experiment. Native adapters use ESP-IDF, Pico SDK and STM32 CMSIS. The firmware does not calculate algorithm duration or energy.

| Platform | Maximum-clock experiment | Required operating configuration |
|---|---:|---|
| ESP32-D0WD-V3 | 240 MHz | One application core; Wi-Fi and Bluetooth uninitialized |
| RP2040, Marble Pico | 200 MHz | Internal core regulator 1.15 V; QSPI Flash 50 MHz |
| NUCLEO-F446RE | 180 MHz | Scale 1 and OverDrive; internal HSI-derived PLL |

These are the configured maximum CPU operating profiles. They do not imply that every bus, external Flash or hardware accelerator is used at its maximum. The existing CSV captures belong to the preceding campaign. **New RP2040 and STM32 measurements are required before reporting maximum-clock results.** That campaign retains the ten accepted regulator-removed ESP32 captures at 240 MHz, with their original v3 experiment, image and acquisition provenance. No repeat ESP32 measurements at 240 MHz are required; the common160 campaign requires separate new captures.

**Maximum-clock functional validation passed on RP2040 and STM32F446: all twelve workloads and final DONE.** The silent measurement images were programmed afterward. See the [hardware validation record](docs/HARDWARE_VALIDATION.md) for logs, register observations and image hashes. New PPK2 captures remain pending.

**Common160 functional validation passed on all three boards: all twelve workloads with exact call counts and final DONE at the configured 160 MHz.** Their matching silent measurement images were installed afterward; common160 is the latest recorded installation on Pico, ESP32 and STM32F446. Separate diagnostic and programming evidence is retained for [Pico](hardware/common160/2026-09-11/rp2040_diagnostic_01.json) ([programming](hardware/common160/2026-09-11/rp2040_measurement_programming_01.json)), [ESP32](hardware/common160/2026-09-11/esp32_diagnostic_01.json) ([programming](hardware/common160/2026-09-11/esp32_measurement_programming_01.json)) and [STM32F446](hardware/common160/2026-09-11/stm32f446_diagnostic_01.json) ([programming](hardware/common160/2026-09-11/stm32f446_measurement_programming_01.json)). All three common160 PPK2 capture sets remain pending; programming observations do not independently validate the silent images' complete execution.

## Hardware used in the tests

The photographs show the three microcontroller boards and the Nordic Power
Profiler Kit II (PPK2) used for the measurements. Click any photograph to open
it at full resolution.

<table>
  <tr>
    <td align="center" width="50%">
      <strong>ESP32</strong><br>
      <a href="docs/images/hardware/esp32.jpg"><img src="docs/images/hardware/esp32.jpg" alt="ESP32 development board used in the benchmark" height="240"></a><br>
      Classic ESP32 development board.<br>
      RUN output: GPIO18.
    </td>
    <td align="center" width="50%">
      <strong>RP2040 — Marble Pico</strong><br>
      <a href="docs/images/hardware/rp2040-marble-pico.jpg"><img src="docs/images/hardware/rp2040-marble-pico.jpg" alt="RP2040 board labeled Marble Pico used in the benchmark" height="240"></a><br>
      RP2040 board labeled Marble Pico.<br>
      RUN output: GP2.
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <strong>NUCLEO-F446RE</strong><br>
      <a href="docs/images/hardware/nucleo-f446re.jpg"><img src="docs/images/hardware/nucleo-f446re.jpg" alt="NUCLEO-F446RE target board used in the benchmark" height="240"></a><br>
      STM32F446 target board.<br>
      RUN output: PC0.
    </td>
    <td align="center" width="50%">
      <strong>PPK2 acquisition setup</strong><br>
      <a href="docs/images/hardware/ppk2-rp2040-setup.jpg"><img src="docs/images/hardware/ppk2-rp2040-setup.jpg" alt="Nordic Power Profiler Kit II connected to the RP2040 board" height="240"></a><br>
      Nordic PPK2 connected to the RP2040 board.<br>
      Current acquisition and digital RUN marker.
    </td>
  </tr>
</table>

The RP2040 board pictured above runs the repository's `rp2040` firmware target.
During energy acquisition, PPK2 supplies the DUT's 3.3 V rail and records the
single RUN signal on D0. The DUT's USB, UART adapter and programmer are
disconnected or electrically isolated; PPK2 remains connected to the acquisition
computer. See the [acquisition protocol](docs/PROTOCOL.md) for the wiring details.

## Documentation and source

- [Firmware specification](firmware/README.md): measurement behavior, compilation, inputs, algorithm contracts, memory, board configuration and measured boundaries.
- [Common 160 MHz comparison](docs/COMMON_CLOCK_160.md): supported clocks, internal supply settings, build selection, new images and thirty-capture campaign.
- [Experiment manifest](config/experiment.json): fixed order, repetitions, input size, target clocks, single output pin and pauses.
- [Autonomous runner](firmware/common/bench_runner.c) and [common kernels](firmware/common/kernels).
- [Board targets](firmware/targets) and [input manifest](data/manifest.json).
- [Acquisition protocol](docs/PROTOCOL.md) and [capture format and analyzer](docs/capture_format.md).
- [Maximum-clock campaign plan](campaigns/MAX_CLOCK_CAMPAIGN.md): ten new Pico and ten new STM32 captures, with explicitly pinned reuse of the ten unchanged ESP32 captures.
- [Automated PPK2 collector](tools/capture_ppk2.py), which power-cycles one DUT, stops after the twelve D0 windows plus the required LOW tail, preserves raw transport/CSV, and runs the structural analyzer.
- [Build instructions](docs/BUILD_AND_TEST.md), [validation status](docs/VALIDATION.md) and [current hardware report](docs/HARDWARE_VALIDATION.md).
- [Completed 30-capture PPK2 campaign](results/2026-09-10_ppk2/README.md), with aggregate CSV/JSON and a hash-linked capture index.
- [ESP32 no-regulator measurement update](results/2026-09-10_ppk2_esp32_noreg/README.md), with ten new cold-boot captures and a direct comparison against the original ESP32 fixture.
- [Regulator-removed campaign update](results/2026-09-10_ppk2_regulators_removed/README.md), combining the new ESP32 and RP2040 series with the unchanged STM32 series.
- [Raw-data archive and reproduction guide](dataset/README.md), with a SHA-256 inventory of all final, pilot, rejected and incomplete PPK2 transports.
- [Selected full CSV dataset](ROW_Data/README.md): 30 regulator-removed captures, organized into ESP32, RP2040 and STM32F446 folders, with acquisition metadata, original analyses and hashes.

The measurement image uses **`BENCH_DIAGNOSTICS=OFF`**. Application serial reporting is absent and UART/USB interfaces are disabled. During acquisition, the board runs autonomously with its USB, UART adapter and programmer disconnected. [CURRENT_FIRMWARE.json](CURRENT_FIRMWARE.json) records image hashes, build status and observed programming status separately. Maximum-clock images are archived under each target's `build_verified/max_clock_measurement`; common160 images and their separate manifest use `build_verified/common160_measurement` and `profiles/common160/CURRENT_FIRMWARE.json`. Earlier firmware remains available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0).

## Selected CSV data and article analysis

The curated `ROW_Data/` directory is stored in this checkout, locally at
`D:\Documente\Energy Profiling\ROW_Data`. It contains ten full captures per board
(30 waveform CSVs, 165,200,896 sample rows, approximately 6.11 GB of waveform
CSV data), together with the original sidecars and selection manifest. These
are historical measurements; they have not been replaced or relabeled as
measurements of the current maximum-clock firmware.

This directory was moved from the separate article workspace. Relative paths
inside its manifests remain valid, and the original acquisition files and
measurement values are preserved. The raw transport archive under `captures/`
and `captures_noreg/` remains the source evidence at the pinned v1.0.0 commit;
the curated CSV folder is a later local working-tree addition, not part of
that earlier release. Its selection index and manifests are published; the 6.11 GB
of curated waveform CSVs remain local. The public raw transports can be exported
back to CSV with `tools/export_ppk2_raw.py`. Waveform CSVs under `ROW_Data/` are
configured for Git LFS if they are published later.

The article keeps its derived `data/`, generated tables/figures and analysis
scripts in the article workspace. Those scripts use the sibling
`Energy Profiling/ROW_Data` directory by default. Set `PPK2_DATA_DIR` to the
CSV dataset root when using a different directory layout. See the
[dataset README](ROW_Data/README.md) for columns, provenance and reconstruction.

## One measurement signal

| PPK2 input | Meaning | ESP32 | Pico RP2040 | NUCLEO-F446RE |
|---|---|---|---|---|
| D0 | RUN | GPIO18 | GP2 | PC0 |

Connect the selected MCU output to PPK2 D0, LOGIC VCC to the measured DUT 3V3 rail, and the grounds as specified in the [protocol](docs/PROTOCOL.md). In Source Meter mode, PPK2 VOUT supplies the board's 3V3 input. PPK2's own USB connection to the acquisition computer remains connected.

**HIGH marks one complete fixed-count kernel batch; LOW is outside the batch.** There are no additional algorithm-ID, error, completion or idle-validity outputs. Only D0 is interpreted by the analyzer; other PPK2 digital inputs are unused.

## Autonomous sequence

```text
boot, platform initialization/checks and first input preparation
  -> RUN LOW: nominal 5 s active control idle
  -> RLE -> Delta -> LZ77 -> Huffman -> AES -> SHA -> ChaCha -> CRC -> FFT -> FIR -> IIR -> DCT
  -> after final verification: nominal 2 s active control idle, RUN LOW
  -> platform final state, RUN remains LOW until reset
```

Each arrow between algorithms contains result verification, preparation of the next workload and a nominal 1 s active idle pause. Each algorithm produces exactly one HIGH pulse containing its configured number of independent calls. There is no extra 1 ms ID-settling delay. The initial 5 s starts after initialization and the first preparation, so power-on boot time is additional.

A detected fault latches the same RUN output **HIGH until reset**. Missing falling edges, extra pulses and incomplete sequences cause structural rejection. With one wire, a LOW tail cannot by itself prove that final verification finished, and some resets or hangs can be indistinguishable from an otherwise valid pulse sequence. Capture acceptance is a structural check, not an independent firmware attestation.

Start recording before powering the DUT and keep at least **3 s of LOW after the twelfth falling edge**. The baseline is the last 2 s before the first rising edge. The analyzer checks lower bounds of 5 s before the first pulse and 1 s between pulses, allowing 1% for ESP32/RP2040 and 2% for the HSI-derived STM32 control delays; it requires a 3 s final LOW tail. These allowances affect structural checks, not RUN integration, and require confirmation in the new physical pilot. Preparation and verification make LOW intervals longer, so there is no upper-duration test for those intervals.

For scripted acquisition, install `requirements-ppk2.txt` in an isolated virtual environment and first run `python tools/capture_ppk2.py --list-devices`. A one-capture pilot for an ESP32 is:

```powershell
python tools/capture_ppk2.py --board esp32 --physical-board-id ESP32-01 --ambient-temperature-c 23.0 --confirm-wiring
```

Use `--captures 10` only after the pilot passes. The script uses PPK2 Source Meter mode, leaves the DUT powered off on exit, and refuses to enable VOUT without `--confirm-wiring`. Its CSV timestamps are reconstructed from sample indices; retain an official Nordic `.ppk2` capture as well when native-file provenance or independent comparison with the Power Profiler application is required.

If no first D0 rise appears within 30 s, the collector rejects the pilot and turns VOUT off automatically. `python tools/capture_ppk2.py --power-off` is the explicit recovery command if an external runner or terminal is terminated abruptly.

There are no extra warm-up kernel calls or MCU timing reports. Reusable workspaces remove heap allocation from RUN; algorithmic initialization remains measured. Active idle keeps the CPU awake and is not deep sleep or hardware Standby. Wiring, voltage, clocks and the exported GPIO trace require a PPK2 pilot before scientific measurements are accepted.
