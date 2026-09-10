# Acquisition protocol

Current campaign: **`energy-profiling-v3-single-gpio`**, experiment schema 2. [experiment.json](../config/experiment.json) defines the parameters and the [input manifest](../data/manifest.json) identifies the exact bytes. The earlier eight-signal images and September 2026 hardware logs are historical evidence, not single-GPIO acquisitions.

## Power and wiring

Use PPK2 in Source Meter mode at a nominal 3300 mV. Connect VOUT to DUT 3V3, GND to DUT GND and LOGIC VCC to the measured 3V3 rail. Connect **only the measurement output to PPK2 D0**:

| Board | RUN output |
|---|---|
| ESP32 | GPIO18 |
| Raspberry Pi Pico | GP2 |
| NUCLEO-F446RE | PC0, CN7 pin 38 |

No algorithm-ID, ERROR, DONE or IDLE_VALID wires are used. D1-D7 do not form part of the protocol. Instrumentation connections are part of the fixture and must remain consistent between captures. Disconnect DUT USB, external UART adapters, programmers and other power sources during acquisition. PPK2's own USB connection is required for data collection. A dedicated logic signal replaces the original LED marker.

Direct external 3V3 power on NUCLEO-F446RE requires the UM1724 configuration: physically separate ST-LINK or open **SB2 and SB12**. Disabling UART in software does not provide electrical isolation. Check the actual PC0 routing and bridge arrangement before wiring, as described in the [F446 target](../firmware/targets/stm32f446/README.md). The internal HSI clock avoids dependence on a powered ST-LINK MCO. See [ST UM1724, section 7.5.3 and connector tables](https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf).

Start acquisition before applying DUT power or releasing reset. Set the official Nordic Power Profiler application explicitly to **100,000 samples/s**, retaining current and D0. Preserve the native `.ppk2` file and a complete CSV export. Record the PPK2 serial number, hardware/firmware/application versions, acquisition settings, physical board and SHA-256 of the programmed image. Check the export against a known pulse sequence before the campaign. [Nordic application instructions](https://docs.nordicsemi.com/r/bundle/nrf-connect-for-desktop/page/app/pc-nrfconnect-ppk/using_ppk_app.html).

## Signal and workload order

RUN HIGH normally encloses the complete batch of R independent calls. RUN LOW is outside a batch; it can contain initialization, preparation, checks, active idle or the final platform state. LOW alone does not classify a sample as idle.

The twelve pulses are assigned in this fixed order:

```text
1 RLE, 2 Delta, 3 LZ77, 4 Huffman, 5 AES-128, 6 SHA-256,
7 ChaCha20, 8 CRC32, 9 FFT, 10 FIR, 11 IIR, 12 DCT
```

There is one pulse per batch, not one pulse per kernel call. The parser obtains R from the board-specific manifest; it cannot count calls inside a HIGH pulse. Algorithm identity is inferred from position, without decoding a separate ID bus or recognizing the analog current shape.

Before the first batch, initialization, platform checks and input preparation finish, followed by a nominal **5 s active control idle**. Checks that could disturb the baseline occur before this pause. The **last 2 s immediately before the first rising edge** form the baseline, apart from timer/gate boundary overhead. The initial 5 s does not equal the first 5 s after physical power-on because boot and preparation take additional time.

After each of the first eleven batches, RUN falls; the firmware checks the platform and last result, consumes the result digest, prepares the next workload, and waits a nominal **1 s** before the next rising edge. Successful call/count checks take place immediately before the falling edge. The total LOW gap is longer when preparation and verification take additional time. There is no ID-settling delay.

After the twelfth falling edge, final verification and digest calculation run while LOW, followed by **2 s of active control idle** and then the platform's final state. The GPIO remains LOW. The final platform state may suspend a task or use WFI and must not be mixed into the active baseline. **Record at least 3 s of LOW after the twelfth falling edge**, and longer if final verification has not yet had time to finish.

## Faults and limits of one-wire observation

A detected error requests RUN HIGH and leaves it latched until reset. If an error occurs during HIGH execution, the firmware does not emit a normal falling edge first. An error detected after a falling edge can create an additional HIGH interval. The parser rejects a missing falling edge, additional pulse, incomplete pulse sequence or insufficient LOW interval.

Before the GPIO and logic reference are initialized, the selected digital input can be unknown. A contiguous unknown prefix is allowed only before the first defined LOW sample. All subsequent selected-input states must be definite LOW/HIGH; mixed states are rejected. Native files may still contain unresolved states on unused D1-D7; these do not describe this protocol. Signed finite current is permitted before the first RUN except within the selected 2 s baseline; all later samples must be nonnegative. Nonfinite current is always rejected.

The one-wire trace cannot distinguish every possible reset, arbitrary glitch or hang. In particular, a hang during final verification with RUN LOW can still leave twelve pulses and a long LOW tail. The parser therefore reports **structural capture acceptance**, not proof that final verification completed or that a particular firmware hash ran. Firmware/image provenance and the physical pilot remain separate evidence. Do not infer success from LOW alone.

## Measured boundary and integration

RUN includes R kernel calls, the wrapper's state/guard/return checks, loop overhead and the successful batch/count checks before the falling edge. Each call reinitializes its algorithmic state. External preparation, result hashing, full reference comparison and pauses are outside RUN. MCU timers control pauses but do not supply benchmark duration.

For a half-open interval `[a,b)`, the first HIGH sample is included and the first LOW sample is excluded. With nominal sample rate fs:

```text
M = b - a
T_batch = M / fs
Q_batch = sum(I[a:b]) / fs
E_batch = V_DUT_constant * Q_batch
T_call = T_batch / R
Q_call = Q_batch / R
E_call = E_batch / R
```

The PPK2 stream does not provide simultaneously sampled DUT voltage. Verify voltage at the DUT terminals under load and document its uncertainty. The parser distinguishes the manifest's nominal 3.3 V from an operator-supplied constant; neither is independently verified by software. A declared voltage uncertainty is recorded without automatically propagating a full energy uncertainty budget. Active board energy is reported without automatic baseline subtraction.

100 kS/s provides a nominal 10 microseconds step. Edge quantization, analog/digital alignment, range changes and GPIO/loop overhead need separate checks. An empty-loop capture is an instrumentation control, not a universal automatic correction. A uniform timebase reconstructed from indices cannot itself prove that upstream data were never lost. [Nordic digital resolution](https://docs.nordicsemi.com/r/bundle/ug_ppk2/page/ug/ppk/digital_input_resolution.html).

The referenced current specification lists typical +/-10% in 5-50 mA and +/-15% in 50-1000 mA, with corresponding offset specifications. Check known loads before the campaign and report instrument accuracy separately from statistical dispersion. Small observed differences do not automatically establish a ranking. [Nordic current accuracy](https://docs.nordicsemi.com/r/bundle/ug_ppk2/page/ug/ppk/ppk_measure_accuracy.html).

## Capture acceptance and independent repetitions

Use one complete suite per file. The analyzer requires exactly twelve complete HIGH pulses, a valid LOW prefix of at least the nominal 5 s and eleven LOW gaps of at least the nominal 1 s. A **1% tolerance applies to those MCU pause lower bounds**; no upper bound is used because initialization/preparation/verification can lengthen LOW. At 100 kS/s, the minimum counts are 495000 startup LOW samples, 99000 samples in each inter-workload gap and **300000 trailing LOW samples**. The baseline uses only the final 200000 samples before the first pulse; entire gaps are not labeled active idle.

Use at least ten separate power-on captures per board, recording temperature and the rest period between starts. R calls within one batch provide one aggregate observation, not R independent experiments. A single physical board of each model does not characterize variation across units. Fixed order, cache state and heating may affect later workloads; keep conditions consistent and assess drift.

The pilot must check the programmed image, clocks, FPU/radio configuration, output correctness, memory, all twelve pulses, LOW gaps, latched-fault behavior, export schema and real voltage. It must also assess observable resets and reported data losses. Final measurements begin after pilot problems are resolved. See [capture format and CLI](capture_format.md), including `--digital-column` for a generic single-signal CSV.
