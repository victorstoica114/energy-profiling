# NUCLEO-F446RE measurement target

Current STM32 target: NUCLEO-F446RE, with separate `max_clock` and `common160` measurement profiles (schema 2). The target uses the actual F446 CMSIS header/vector table, 512 KiB Flash, 128 KiB SRAM and a 16 KiB linker stack reservation. Startup rejects device ID other than 0x421 or a Flash-size register other than 512 KiB.

This README describes the measurement image, **BENCH_DIAGNOSTICS=OFF**.

## Clock and runtime

The default **max_clock** profile retains nominal CPU **180 MHz**, the maximum specified STM32F446 frequency. The additional **common160** profile uses nominal CPU **160 MHz** for comparison with ESP32 and RP2040 at the same CPU frequency. Both use HSI16 through the PLL without ST-LINK MCO or an assumed external crystal.

| Setting | max_clock | common160 |
|---|---|---|
| Experiment manifest | `config/experiment.json` | `config/experiment.common160.json` |
| SYSCLK / AHB | 180 MHz | 160 MHz |
| PLL M / N / P | 16 / 360 / 2 | 16 / 320 / 2 |
| APB1 / APB2 | 45 / 90 MHz | 40 / 80 MHz |
| Internal regulator | Scale 1, OverDrive enabled | Scale 1, OverDrive disabled |
| Flash wait states | 5 | 5 |
| TIM2 input / prescaler | 90 MHz / 8999 | 80 MHz / 7999 |
| Unused PLL Q output | 72 MHz | 64 MHz |

At the measured 3.3 V supply, five Flash wait states are required above 150 MHz in both profiles. Prefetch and the Flash instruction/data caches remain enabled. Scale 1 without OverDrive supports 160 MHz; OverDrive is required for 180 MHz. Startup selects HSI, configures the selected regulator mode, starts the PLL, waits for the applicable voltage readiness flags, applies and reads back the Flash configuration, then switches to PLL. GPIO clocks are gated during the power transition with RUN and the LED latched LOW; TIM2 starts afterward. Removing the board's external 3.3 V regulator does not disable the MCU's internal core regulator. USB remains disabled; the unused Q output need not be 48 MHz.

FPU access and hard-float compiler flags are enabled and checked. Single precision uses the FPU; double arithmetic remains software. Before and after measured batches, runtime guards check clock selection, PLL and bus divisors, power-mode readiness, Flash latency/cache settings and the pause-timer configuration. Register checks validate the nominal clock configuration, not HSI's exact physical frequency or drift; an independent clock/timer measurement is required during validation. [ST DS10693, Tables 16, 17 and 43](https://www.st.com/resource/en/datasheet/stm32f446re.pdf) and [RM0390, OverDrive entry and RCC sections](https://www.st.com/resource/en/reference_manual/dm00135183.pdf) define the device and clock tree.

TIM2 divides its APB1 timer clock to 10 kHz using the profile-specific prescaler shown above, for busy-polled control pauses without IRQ. The 10 kHz timer preserves the five-second startup pause, one-second gaps and two-second final pause. SysTick is stopped. The CPU does not measure RUN duration. After final verification and the two-second LOW pause, the target enters WFI with RUN LOW.

## Single measurement output and power

| PPK2 | Signal | MCU | Nucleo morpho position |
|---|---|---|---|
| D0 | RUN | PC0 | CN7 pin 38 |

HIGH normally encloses one fixed-count kernel batch; LOW is outside. There are no additional ID/status outputs on PC1-PC7. Algorithms are inferred from the twelve pulses in fixed order. A detected fault latches PC0 HIGH until reset without a spurious normal falling edge when failure occurs inside a batch. LD2 on PA5 stays LOW/off.

Inspect the actual PC0 routing and solder bridges before wiring. The documented PC0/PC1 routing group uses SB51/SB56 ON and SB46/SB52 OFF; only PC0 is required by the current measurement protocol. Connector/bridge details are in [UM1724, tables 10 and 29](https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf).

In the measurement image, no reporter implementation or application UART strings are linked. USART2's peripheral clock is disabled and PA2/PA3 are analog inputs without pulls. This software setting does not electrically isolate ST-LINK, USB power or UART bridges.

For external direct 3V3 supply, physically separate ST-LINK or open **SB2 and SB12**, following UM1724 section 7.5.3. Connect PC0 to PPK2 D0, LOGIC VCC to measured DUT 3V3 and common ground, with DUT USB/programmer disconnected. See the [full protocol](../../../docs/PROTOCOL.md). Structural pulse acceptance cannot prove final verification completed if execution hangs LOW.

## Build and provenance

Dependencies are pinned in sdk.lock.json: cmsis-device-f4 v2.6.11 and CMSIS_5 5.9.0. The campaign compiler is GNU Arm Embedded GCC 9.2.1 20191025. From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/short/deps -BuildRoot C:/short/build-max-clock -Only stm32
```

For the additional profile, append `-ClockProfile common160` and use a separate build root. The helper output directories are `stm32f446` for max_clock and `stm32f446-common160` for common160. Direct CMake builds select `-DBENCH_CLOCK_PROFILE=max_clock` or `-DBENCH_CLOCK_PROFILE=common160`; changing profiles in an existing configured build directory is rejected. BIN load address is **0x08000000**. Build helpers do not flash devices.

The existing measurement archive remains `build_verified/max_clock_measurement`; the additional archive is `build_verified/common160_measurement`. Use the [current-image manifest](../../../CURRENT_FIRMWARE.json) to identify the intended image and its programming/validation state. Successful compilation is not programming, a hardware run or a PPK2 energy capture. New energy results require independent captures with this exact firmware and its matching experiment manifest.

The common160 profile requires its own independent captures for all twelve workloads and active-idle reference. Equal nominal CPU frequency does not equate bus frequencies, memory systems, FPU capabilities, internal regulator settings or physical oscillator accuracy. Do not combine captures from the two profiles or rescale max_clock energies into common160 results.
