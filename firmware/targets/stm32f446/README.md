# NUCLEO-F446RE measurement target

Current STM32 target: NUCLEO-F446RE, experiment **energy-profiling-v4-max-clock**, schema 2. The target uses the actual F446 CMSIS header/vector table, 512 KiB Flash, 128 KiB SRAM and a 16 KiB linker stack reservation. Startup rejects device ID other than 0x421 or a Flash-size register other than 512 KiB.

This README describes the measurement image, **BENCH_DIAGNOSTICS=OFF**.

## Clock and runtime

Nominal CPU frequency is **180 MHz**, the maximum specified STM32F446 frequency. HSI16 /16 x360 /2 supplies SYSCLK without ST-LINK MCO or an assumed external crystal. AHB=180 MHz, APB1=45 MHz (/4), APB2=90 MHz (/2). These APB limits apply with OverDrive enabled. The unused PLL Q output is 72 MHz; USB is disabled and does not require a 48 MHz clock.

At the measured 3.3 V supply, Scale 1, OverDrive, five Flash wait states, prefetch and the Flash instruction/data caches are explicit. Startup selects HSI, starts the PLL, waits for voltage scaling and both OverDrive readiness flags, applies and reads back the Flash configuration, then switches to PLL. GPIO clocks are gated during the power transition with RUN and the LED latched LOW; TIM2 starts afterward. Removing the board's external 3.3 V regulator does not disable the MCU's internal core regulator or its OverDrive requirement.

FPU access and hard-float compiler flags are enabled and checked. Single precision uses the FPU; double arithmetic remains software. Before and after measured batches, runtime guards check clock selection, PLL and bus divisors, power-mode readiness, Flash latency/cache settings and the pause-timer configuration. Register checks validate the nominal clock configuration, not HSI's exact physical frequency or drift; an independent clock/timer measurement is required during validation. [ST DS10693, Tables 16, 17 and 43](https://www.st.com/resource/en/datasheet/stm32f446re.pdf) and [RM0390, OverDrive entry and RCC sections](https://www.st.com/resource/en/reference_manual/dm00135183.pdf) define the device and clock tree.

TIM2 receives the 90 MHz APB1 timer clock, divided by 9000 (PSC=8999), for busy-polled control pauses without IRQ. The 10 kHz timer preserves the five-second startup pause, one-second gaps and two-second final pause. SysTick is stopped. The CPU does not measure RUN duration. After final verification and the two-second LOW pause, the target enters WFI with RUN LOW.

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

The helper output directory is stm32f446. BIN load address is **0x08000000**. Build helpers do not flash devices.

Current measurement artifacts belong in build_verified/max_clock_measurement. Use the [current-image manifest](../../../CURRENT_FIRMWARE.json) to identify the intended image and its programming/validation state. Successful compilation is not programming, a hardware run or a PPK2 energy capture. New energy results require independent captures with this exact firmware and its matching experiment manifest.
