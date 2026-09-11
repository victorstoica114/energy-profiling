# Energy Profiling

Firmware and offline analysis for measuring ESP32, RP2040 and **NUCLEO-F446RE** workloads with Nordic PPK2. Release **v1.1.0** defines **`energy-profiling-v4-max-clock`**, experiment schema 2. One digital output marks the twelve fixed-count workload batches; the algorithm is inferred from pulse order.

The common C library executes twelve algorithms on identical inputs across boards, retaining the repetition counts documented in the original experiment. Native adapters use ESP-IDF, Pico SDK and STM32 CMSIS. The firmware does not calculate algorithm duration or energy.

| Platform | Nominal CPU clock | Required operating configuration |
|---|---:|---|
| ESP32-D0WD-V3 | 240 MHz | One application core; Wi-Fi and Bluetooth uninitialized |
| RP2040, Marble Pico | 200 MHz | Internal core regulator 1.15 V; QSPI Flash 50 MHz |
| NUCLEO-F446RE | 180 MHz | Scale 1 and OverDrive; internal HSI-derived PLL |

These are the configured maximum CPU operating profiles. They do not imply that every bus, external Flash or hardware accelerator is used at its maximum. The existing CSV captures belong to the preceding campaign. **New RP2040 and STM32 measurements are required before reporting results for this release.** ESP32 captures can be retained only with their original provenance and confirmation that its measured configuration remains equivalent.

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

The measurement image uses **`BENCH_DIAGNOSTICS=OFF`**. Application serial reporting is absent and UART/USB interfaces are disabled. During acquisition, the board runs autonomously with its USB, UART adapter and programmer disconnected. [CURRENT_FIRMWARE.json](CURRENT_FIRMWARE.json) records image hashes, build status and observed programming status separately. Current images are archived under each target's `build_verified/max_clock_measurement`. Earlier firmware remains available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0).

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
