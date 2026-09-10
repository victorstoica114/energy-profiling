# NUCLEO-F446RE measurement target

Current STM32 target: NUCLEO-F446RE, experiment **energy-profiling-v3-single-gpio**, schema 2. The separate stm32 directory retains F411 history and its binaries must not be used on F446. The target uses the actual F446 CMSIS header/vector table, 512 KiB Flash, 128 KiB SRAM and a 16 KiB linker stack reservation. Startup rejects device ID other than 0x421 or a Flash-size register other than 512 KiB.

This README describes the measurement image, **BENCH_DIAGNOSTICS=OFF**.

## Clock and runtime

Nominal CPU frequency is **100 MHz**. HSI16 /16 x200 /2 supplies SYSCLK without ST-LINK MCO or an assumed external crystal. AHB=100 MHz, APB1=25 MHz (/4), APB2=50 MHz (/2). F446 bus limits are 45 and 90 MHz, so original F411 bus divisors cannot simply be reused. Scale1, overdrive off, three Flash wait states, prefetch and Flash caches are explicit.

FPU access and hard-float compiler flags are enabled and checked. Single precision uses the FPU; double arithmetic remains software. Register checks validate the clock configuration, not HSI's exact physical frequency or drift. [ST DS10693](https://www.st.com/resource/en/datasheet/stm32f446re.pdf) and [RM0390](https://www.st.com/resource/en/reference_manual/rm0390-stm32f446xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf) define the device and clock tree.

TIM2 receives the 50 MHz APB1 timer clock, divided by 5000, for busy-polled control pauses without IRQ. SysTick is stopped. The CPU does not measure RUN duration. After final verification and the two-second LOW pause, the target enters WFI with RUN LOW.

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
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/short/deps -BuildRoot C:/short/build-single-gpio -Only stm32
```

The helper output directory is stm32f446. BIN load address is **0x08000000**. Build helpers do not flash devices.

New one-wire artifacts belong in build_verified/single_gpio_measurement. Earlier build_verified/measurement and build_verified/diagnostic files are historical **eight-signal** images. The [current-image manifest](../../../CURRENT_FIRMWARE.json) distinguishes new candidates from last programmed firmware; successful compilation is not programming, a hardware run or a PPK2 energy capture.
