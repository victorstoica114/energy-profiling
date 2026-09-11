# Validation status

Updated **11 September 2026** for **energy-profiling-v4-max-clock**, release **v1.1.0**, experiment schema 2. The twelve workload variants, frozen input bytes, per-board call counts and single-GPIO protocol are preserved. CPU, regulator and related clock settings are explicit parts of the new experiment.

## Common160 addition, release v1.2.0

The separate `energy-profiling-v5-common160` configuration and its native images are recorded in [profiles/common160/CURRENT_FIRMWARE.json](../profiles/common160/CURRENT_FIRMWARE.json). Native measurement and diagnostic builds passed on all three targets. Common160 hardware observations are recorded separately from the maximum-clock checks below.

The [Pico common160 diagnostic](../hardware/common160/2026-09-11/rp2040_diagnostic_01.json) passed all twelve workloads with exact call counts and final DONE. It reported CPU 160000000 Hz, peripheral clock 48000000 Hz, VREG selection 12 (1.15 V) with regulation-ready asserted, Flash divider 4, derived Flash clock 40000000 Hz, active core 0 and platform check 1. The matching silent common160 UF2 was [programmed afterward](../hardware/common160/2026-09-11/rp2040_measurement_programming_01.json), with completed host transfer and disappearance of the ROM volume and diagnostic USB CDC. This 160 MHz image is the Pico's latest recorded installation. Silent-image execution and flash readback have not been independently validated.

The [ESP32 common160 diagnostic](../hardware/common160/2026-09-11/esp32_diagnostic_01.json) also passed all twelve workloads with exact call counts and final DONE. It reported CPU 160000000 Hz, APB 80000000 Hz, digital-bias selection 4 (SDK nominal 1.10 V), active core 0, uninitialized radio and platform check 1. The matching silent release bootloader, partition table and application were [programmed afterward](../hardware/common160/2026-09-11/esp32_measurement_programming_01.json), with esptool reporting successful hash verification for all three segments. Common160 is the ESP32's latest recorded installation. This programming verification is distinct from independent flash readback and PPK2 validation, which remain unavailable.

Common160 functional validation and programming remain pending for STM32F446. All three boards still require new common160 PPK2 pilots and ten accepted captures each; see [COMMON_CLOCK_160.md](COMMON_CLOCK_160.md). The ten accepted ESP32 captures at 240 MHz remain selected for the maximum-clock campaign with their original v3 provenance; no repeat 240 MHz acquisition is required.

## Maximum-clock firmware evidence

| Target | Configured measurement profile | Validation recorded so far |
|---|---|---|
| ESP32-D0WD-V3 | 240 MHz; one application core; Wi-Fi/Bluetooth uninitialized; DIO Flash 40 MHz | Ten accepted regulator-removed captures are retained with their original v3 image/manifest provenance; no repeat 240 MHz acquisition |
| RP2040, Marble Pico | 200 MHz; internal VREG 1.15 V; clk_peri 48 MHz; QSPI Flash 50 MHz | Native diagnostic and measurement builds passed; twelve functional PASS events and DONE observed; final serial-disabled measurement UF2 programmed |
| NUCLEO-F446RE | Nominal 180 MHz; Scale 1/OverDrive; APB1/APB2 45/90 MHz; five Flash wait states | Twelve PASS events with exact call counts and DONE observed through a separate USART3/PC10 diagnostic image; original release serial-disabled measurement BIN reinstalled through ST-LINK mass storage |

[CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) records maximum-clock image hashes, compilation, historical programming and validation separately. Maximum-clock measurement archives are under `firmware/targets/<target>/build_verified/max_clock_measurement`. The manifest's `single_gpio_measurement` profile key remains for collector compatibility and points to that location. The earlier Pico 200 MHz PASS and programming records remain valid historical observations; Pico and ESP32 now have common160 as their latest recorded installation. See the [hardware report](HARDWARE_VALIDATION.md) for observed device results.

The RP2040 diagnostic confirmed CPU 200000000 Hz, peripheral clock 48000000 Hz, VREG selection 12 (1.15 V) with regulation-ready asserted, SSI divider 4 and JEDEC identifier `ef4017`. These are software/register observations, not independently calibrated physical clock or voltage measurements. A successful functional run with USB connected is not an energy capture. The final measurement image has application serial diagnostics disabled.

The [STM32 functional diagnostic](../hardware/2026-09-11/stm32f446_pc10_diagnostic_01.json) passed all twelve workloads with their exact call counts and final DONE. Its separate USART3/PC10 transport used target CN7 pin 1 to detached ST-LINK CN3 pin 1 (RX), with common ground, because open SB63 blocked PA2 TX at CN9 pin 2. It reported the expected nominal CPU/bus clocks, FPU access, Flash and power-control registers, and TIM2 prescaler. The diagnostic transport change preserved the clock setup, kernels, inputs and call counts. Afterward, the original published serial-disabled measurement BIN was [reinstalled through ST-LINK mass storage](../hardware/2026-09-11/stm32f446_measurement_programming_02.json) without `FAIL.TXT`. No flash-readback attestation was obtained; execution of the silent measurement image and PPK2 validation remain pending. Exact image hashes and the separate diagnostic/programming evidence are recorded in the current manifest and [hardware report](HARDWARE_VALIDATION.md).

## Software and binary checks

The project retains independent kernel-reference tests, host runner simulations, serial-collector tests and synthetic capture-analyzer tests. They check actual common C kernels, exact call counts and pulse order, failure paths, parser boundaries, file safety and known numerical integrals. Reproduction commands are in [BUILD_AND_TEST.md](BUILD_AND_TEST.md); [kernel test records](../tests/kernel_tests/README.md) retain their own execution provenance. A retained test result must not be relabeled as a new hardware measurement.

For each release image, inspect native compiler commands and source/image hashes. The common units must retain `-O2 -fno-fast-math -ffp-contract=off -fno-lto`, the frozen inputs, all twelve kernels and fixed-count loops. Build archives distinguish these static checks from physical execution. RP2040 static checks also confirm the divider in the Flash boot stage and absence of serial reporting from the measurement image. STM32 checks cover the FPU, PLL/bus setup, regulator sequencing, Flash settings and control-timer prescaler.

## PPK2 data status

**No replacement maximum-clock RP2040 or STM32 energy datasets are available yet.** Each changed platform requires a physical PPK2 pilot followed by ten accepted independent cold-boot captures. Every capture includes all twelve workload windows and its own active-idle reference. Compute per-call duration and energy from the new PPK2 samples and then aggregate the ten capture-level values using arithmetic mean and sample standard deviation.

The data already stored in `ROW_Data/`, `captures/`, `captures_noreg/`, `campaigns/` and dated `results/` directories belong to the preceding campaign. Their waveforms, manifests and hashes remain unchanged. The [selected CSV dataset](../ROW_Data/README.md) and [regulator-removed campaign report](../results/2026-09-10_ppk2_regulators_removed/README.md) identify those historical measurements. Their existence does not validate the new clock profiles.

ESP32's configured CPU clock, Flash settings, radio policy, inputs, repetitions and measured boundaries are unchanged by this transition. Its accepted regulator-removed captures can be retained after configuration-equivalence checks, with their original capture/image provenance. They must not be described as captures of the newly compiled release binary.

## Remaining measurement limits

The single D0 signal does not independently attest board/firmware identity, count individual calls or prove final validation after DCT. A hang or reset while LOW can be observationally ambiguous. Expected image hashes supplied to the collector are provenance, not device flash readback. Programming, result validation and the physical GPIO/PPK2 pilot provide distinct evidence.

Validate the isolated 3.3 V fixture, real voltage and clock frequency, twelve pulses, LOW gaps, fault behavior and export schema before accepting the new campaign. The existing structural short-gap allowance is 1% for ESP32/RP2040 and 2% for the HSI-derived STM32 control timer; check it again in the new pilot. It does not adjust RUN time or energy. Instrument accuracy, voltage uncertainty, clock drift and range switching remain separate from between-capture dispersion.

The historical firmware and its original validation evidence are preserved in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0). One physical unit per model and fixed workload order do not characterize manufacturing variation or remove heating/cache effects.
