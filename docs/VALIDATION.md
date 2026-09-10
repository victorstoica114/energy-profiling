# Validation status

Updated **10 September 2026** for **energy-profiling-v3-single-gpio**, experiment schema 2. The common input bytes, workload variants and original call counts are unchanged. The runner, platform marker and capture interpretation now use one GPIO, so the September eight-signal hardware runs do not validate this new protocol.

## Current single-GPIO software checks

| Check | Result |
|---|---|
| Actual common C kernels against independent references | 119 data/kernel cases passed again; repeat/reset and deliberate output corruption checks also passed |
| PPK2/CSV analyzer | 24 tests passed, including one selected channel, integration, LOW lower bounds, incomplete/extra pulses, unsafe files and structural-observability limits |
| Host runner | All six board/diagnostic variants passed; each covers twelve normal pulses and ten failure scenarios, including the last DCT invocation and post-DCT platform check |
| Serial collector | Five tests passed; malformed fields/counts, trailing ERROR and unterminated events are rejected |
| Generated inputs/configuration | Ten generated files agree with the generator and schema-2 configuration |
| Board/algorithm counts | All 36 values retain the original experiment-note counts |
| Native measurement builds | ESP32, RP2040 and STM32F446 single-GPIO builds compiled successfully; artifacts are archived separately |

Detailed kernel results are in [results.json](../tests/kernel_tests/results.json). Reproduction commands are in [BUILD_AND_TEST.md](BUILD_AND_TEST.md). Host kernel tests do not estimate MCU performance. Synthetic capture tests do not replace a physical GPIO/export pilot.

The new native archive location for each target is build_verified/single_gpio_measurement. It contains the relevant image, compiler commands and source/artifact provenance. [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) identifies the candidate profile separately from previously programmed images. **No new flashing or single-GPIO hardware run is established by these software checks.**

The intended platform profile is explicit: ESP32 240 MHz, one application core, Wi-Fi/Bluetooth uninitialized; RP2040 133 MHz, one application core; STM32F446RE 100 MHz with FPU enabled, nominal internal HSI16 and APB1/APB2 at 25/50 MHz. Platform checks validate configuration; physical clock frequency, real voltage and exported pulses remain external checks.

## Historical eight-signal evidence

On **9 September 2026**, all three boards passed twelve functional algorithms using separate diagnostic images. Measurement images with application diagnostics disabled were then programmed. That event belongs to **energy-profiling-v2-f446**, with RUN, four ID bits, IDLE_VALID, ERROR and DONE. See the [hardware report](HARDWARE_VALIDATION.md) and the preserved [v2 programmed-image manifest](../hardware/2026-09-09/firmware_manifest_v2.json).

Old build_verified/measurement and build_verified/diagnostic directories retain their original binaries, logs and hash records. Files directly under the earlier build_verified directories belong to an even earlier F411-era configuration. Their READMEs identify that historical scope. Old GPIO checks, including simultaneous DONE/IDLE changes, are not claims about the new one-wire runner.

Archived native records showed all kernels and fixed-count loops present; ESP32 and STM32 DCT contained hardware single-precision arithmetic. Double arithmetic was not represented as hardware accelerated. The new build archives must be used when discussing the new runner or source identity.

## Remaining physical work

The single-GPIO candidate requires hardware revalidation, correct isolated 3V3 wiring, physical voltage/frequency checks, twelve HIGH pulses, required LOW gaps, a final recording tail and fault behavior. Structural parser acceptance cannot prove final verification completed during a LOW hang or identify every reset. PPK2 energy acquisitions have not yet been performed for this campaign.

Use the [pilot protocol](PROTOCOL.md), including the Nucleo bridge requirements. New results must be based on the actual new image and measurement fixture. Static workspaces and repaired kernels already changed the workload from the recovered original code, so unchanged byte count and repetitions do not make historical energies equivalent.

Evidence files may contain absolute local paths from their original build directory. Those paths are provenance and must not be rewritten as if they were portable SDK installation instructions. No binary/log/hash evidence is translated or rewritten by this documentation update.
