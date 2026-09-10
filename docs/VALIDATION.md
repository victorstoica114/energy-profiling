# Validation status

Updated **10 September 2026** for **energy-profiling-v3-single-gpio**, experiment schema 2. The common input bytes, workload variants and original call counts are unchanged. The runner, platform marker and capture interpretation now use one GPIO, so the September eight-signal hardware runs do not validate this new protocol.

## Current single-GPIO software checks

| Check | Result |
|---|---|
| Actual common C kernels against independent references | 119 data/kernel cases passed again; repeat/reset and deliberate output corruption checks also passed |
| PPK2/CSV analyzer | 25 tests passed, including board-specific LOW lower bounds, one selected channel, integration, incomplete/extra pulses, unsafe files and structural-observability limits |
| Host runner | All six board/diagnostic variants passed; each covers twelve normal pulses and ten failure scenarios, including the last DCT invocation and post-DCT platform check |
| Serial collector | Five tests passed; malformed fields/counts, trailing ERROR and unterminated events are rejected |
| Generated inputs/configuration | Ten generated files agree with the generator and schema-2 configuration |
| Board/algorithm counts | All 36 values retain the original experiment-note counts |
| Native measurement builds | ESP32, RP2040 and STM32F446 single-GPIO builds compiled successfully; artifacts are archived separately |

Detailed kernel results are in [results.json](../tests/kernel_tests/results.json). Reproduction commands are in [BUILD_AND_TEST.md](BUILD_AND_TEST.md). Host kernel tests do not estimate MCU performance. Synthetic capture tests do not replace a physical GPIO/export pilot.

The new native archive location for each target is build_verified/single_gpio_measurement. It contains the relevant image, compiler commands and source/artifact provenance. [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) identifies the candidate profile separately from previously programmed images. Software checks alone do not establish flashing or a physical run; the separate campaign evidence below establishes the observed single-GPIO sequences but still does not attest flash contents.

The intended platform profile is explicit: ESP32 240 MHz, one application core, Wi-Fi/Bluetooth uninitialized; RP2040 133 MHz, one application core; STM32F446RE 100 MHz with FPU enabled, nominal internal HSI16 and APB1/APB2 at 25/50 MHz. Platform checks validate configuration. The campaign records an externally observed 3.30 V rail and exported pulses; physical clock frequency was not independently calibrated.

## Historical eight-signal evidence

On **9 September 2026**, all three boards passed twelve functional algorithms using separate diagnostic images. Measurement images with application diagnostics disabled were then programmed. That event belongs to **energy-profiling-v2-f446**, with RUN, four ID bits, IDLE_VALID, ERROR and DONE. See the [hardware report](HARDWARE_VALIDATION.md) and the preserved [v2 programmed-image manifest](../hardware/2026-09-09/firmware_manifest_v2.json).

Old build_verified/measurement and build_verified/diagnostic directories retain their original binaries, logs and hash records. Files directly under the earlier build_verified directories belong to an even earlier F411-era configuration. Their READMEs identify that historical scope. Old GPIO checks, including simultaneous DONE/IDLE changes, are not claims about the new one-wire runner.

Archived native records showed all kernels and fixed-count loops present; ESP32 and STM32 DCT contained hardware single-precision arithmetic. Double arithmetic was not represented as hardware accelerated. The new build archives must be used when discussing the new runner or source identity.

## Current single-GPIO hardware campaign and remaining limitations

On **10 September 2026**, PPK2 F7839E12B2AE acquired ten accepted cold-boot captures for each of ESP32, RP2040 and STM32F446: **30/30 final captures**, 360 RUN windows and 165,203,968 samples at 100 kS/s. Every capture passed the twelve-pulse structure and final LOW-tail checks. Conditions, exact capture selection, hashes and aggregate statistics are in the [campaign report](../results/2026-09-10_ppk2/README.md) and [campaign manifest](../campaigns/2026-09-10_ppk2.json).

The same ESP32 was subsequently remeasured in ten accepted cold boots after removal of its onboard voltage regulator, with PPK2 VOUT connected directly to the 3V3 rail. The startup baseline fell from 55.578 ± 0.386 mA to 53.310 ± 0.045 mA; non-baseline-subtracted workload energy fell by 2.405% to 2.811%, while measured durations remained unchanged within 0.0005%. The exact capture selection and comparison are in the [ESP32 no-regulator report](../results/2026-09-10_ppk2_esp32_noreg/README.md) and [manifest](../campaigns/2026-09-10_ppk2_esp32_noreg.json). The pilot preceding those ten captures is excluded.

RP2040 was then remeasured under the same conditions after removal of its onboard regulator. Ten accepted cold boots reduced its startup baseline from 28.469 ± 0.041 mA to 28.402 ± 0.034 mA (−0.236%). Its non-baseline-subtracted workload energy changed by −0.199% to −0.341%, with duration changes below 0.0005%. The smaller effect should be considered together with the systematic uncertainty limitations below. Selection and aggregate results are in the [regulator-removed campaign report](../results/2026-09-10_ppk2_regulators_removed/README.md) and [manifest](../campaigns/2026-09-10_ppk2_regulators_removed.json); the RP2040 pilot is excluded.

The F446 pilot exposed nominal one-second LOW gaps of 0.98579..0.99163 s from its HSI16-derived timer. Its structural short allowance is therefore explicitly 2%, while ESP32 and RP2040 retain 1%. This affects only LOW-interval acceptance and does not change RUN boundaries or energy integration. The policy is recorded in each analysis and covered by automated tests.

Remaining limitations are substantive: the single D0 signal does not attest board/firmware identity or prove final validation after DCT; some LOW hangs or resets remain observationally ambiguous. The expected image hashes are provenance supplied to the collector, not readback attestation. The multimeter model/calibration, an independent clock measurement, external fault-latch exercise and an official Nordic native `.ppk2` comparison were not recorded. Automated captures preserve exact API transport frames plus CSV rather than native application files.

The acquisition used the [pilot protocol](PROTOCOL.md), including Nucleo ST-LINK isolation, `JP6` fitted and external 3V3 on CN6. Static workspaces and repaired kernels changed the workload from the recovered original code, so unchanged byte count and repetitions do not make historical energies equivalent.

Evidence files may contain absolute local paths from their original build directory. Those paths are provenance and must not be rewritten as if they were portable SDK installation instructions. No binary/log/hash evidence is translated or rewritten by this documentation update.
