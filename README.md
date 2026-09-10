# Energy Profiling

Firmware and offline analysis for measuring ESP32, RP2040 and **NUCLEO-F446RE** workloads with Nordic PPK2. The current source defines **`energy-profiling-v3-single-gpio`**, experiment schema 2. STM32F446 replaces the original F411. One digital output marks the twelve fixed-count workload batches; the algorithm is inferred from pulse order.

The common C library executes twelve algorithms on identical inputs across boards, retaining the repetition counts documented in the original experiment. Native adapters use ESP-IDF, Pico SDK and STM32 CMSIS. The firmware does not calculate algorithm duration or energy.

## Documentation and source

- [Firmware specification](firmware/README.md): measurement behavior, compilation, inputs, algorithm contracts, memory, board configuration and measured boundaries.
- [Experiment manifest](config/experiment.json): fixed order, repetitions, input size, target clocks, single output pin and pauses.
- [Autonomous runner](firmware/common/bench_runner.c) and [common kernels](firmware/common/kernels).
- [Board targets](firmware/targets) and [input manifest](data/manifest.json).
- [Acquisition protocol](docs/PROTOCOL.md) and [capture format and analyzer](docs/capture_format.md).
- [Build instructions](docs/BUILD_AND_TEST.md), [validation status](docs/VALIDATION.md) and [historical hardware report](docs/HARDWARE_VALIDATION.md).

The measurement image uses **`BENCH_DIAGNOSTICS=OFF`**. Application serial reporting is absent and diagnostic UART/USB interfaces are disabled. During acquisition, the board runs autonomously with its USB, UART adapter and programmer disconnected. [CURRENT_FIRMWARE.json](CURRENT_FIRMWARE.json) distinguishes images last installed on hardware from newly built candidates. The images and logs from 9 September 2026 describe the earlier eight-signal protocol; they do not establish that the single-GPIO firmware has been installed or measured.

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

Start recording before powering the DUT and keep at least **3 s of LOW after the twelfth falling edge**. The baseline is the last 2 s before the first rising edge. The analyzer checks lower bounds of 5 s before the first pulse and 1 s between pulses, allowing 1% for these nominal MCU delays; it requires a 3 s final LOW tail. Preparation and verification make LOW intervals longer, so there is no upper-duration test for those intervals.

There are no extra warm-up kernel calls or MCU timing reports. Reusable workspaces remove heap allocation from RUN; algorithmic initialization remains measured. Active idle keeps the CPU awake and is not deep sleep or hardware Standby. Wiring, voltage, clocks and the exported GPIO trace require a PPK2 pilot before scientific measurements are accepted.
