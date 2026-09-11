# Common160 firmware profile

This directory identifies the separate **160 MHz on all three CPUs** experiment added in release v1.2.0. [CURRENT_FIRMWARE.json](CURRENT_FIRMWARE.json) pins the measurement and separate diagnostic images, native build/source evidence and exact experiment configuration. All paths in that JSON are relative to the repository root.

The repository-root CURRENT_FIRMWARE.json continues to identify the maximum-clock campaign. No board is switched merely by updating this repository. Select `--clock-profile common160` for acquisition or serial validation; select `-DBENCH_CLOCK_PROFILE=common160` when compiling.

Native measurement and diagnostic builds passed on all three targets. The [Pico common160 diagnostic](../../hardware/common160/2026-09-11/rp2040_diagnostic_01.json) subsequently passed all twelve workloads with exact call counts and final DONE, reporting CPU 160 MHz, peripheral clock 48 MHz, internal VREG selection 12 (1.15 V) with regulation ready, and Flash divider 4 for 40 MHz QSPI. The [exact silent release UF2 was installed afterward](../../hardware/common160/2026-09-11/rp2040_measurement_programming_01.json); common160 is the Pico's latest recorded installation.

STM32F446 and ESP32 common160 hardware validation and programming remain pending. The earlier maximum-clock RP2040/STM32 PASS records remain unchanged, and all three common160 PPK2 capture sets remain pending. Diagnostic execution and observed UF2 programming do not independently validate the silent image's execution or attest its flash contents. The new campaign still requires a PPK2 pilot and ten accepted independent cold boots on each board.

Software verification includes 84 Python tests, 119 kernel-reference checks and twelve host runner simulations across the two profiles. Static native checks bind source, configuration and images; confirm fixed counts/input bytes, the selected 160 MHz configuration and absence of application serial reporting in measurement images. ARM maximum-clock regression BINs are byte-identical to the published v1.1.0 images.

See the [complete common160 guide](../../docs/COMMON_CLOCK_160.md), [build and diagnostic instructions](../../docs/BUILD_AND_TEST.md), [experiment](../../config/experiment.common160.json) and [pending campaign template](../../campaigns/2026-09-11_ppk2_common160.template.json).
