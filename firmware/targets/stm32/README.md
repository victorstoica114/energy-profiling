# STM32F411CE native target

**Historical archive only.** The current campaign uses NUCLEO-F446RE and
`firmware/targets/stm32f446`. This target's CMake configuration deliberately stops
to prevent combining an F411 binary with the current F446 manifest. The preserved
`build_verified` binaries and hashes describe the previous complete configuration;
they are not current campaign firmware. Reproduction requires restoring that
complete historical source/configuration snapshot. Instructions below are retained
as historical documentation.

This profile uses ST's CMSIS device startup and Arm CMSIS Core, without Arduino,
HAL, an RTOS, or a SysTick handler. Board: Black Pill STM32F411CE, 512 KiB Flash,
128 KiB RAM, a **physically confirmed 25 MHz HSE**, and 3.3 V external power.
Clock checks decode settings; they do not independently measure crystal frequency.

| PPK2 digital bit | Signal | MCU pin |
|---|---|---|
| D0 | RUN | PA0 |
| D1 | ID bit 0 | PA1 |
| D2 | ID bit 1 | PA2 |
| D3 | ID bit 2 | PA3 |
| D4 | ID bit 3 | PA4 |
| D5 | IDLE_VALID | PA5 |
| D6 | ERROR | PA6 |
| D7 | DONE | PA7 |

These are dedicated outputs, not LEDs. PC13 is separately held HIGH to switch
off the Black Pill's active-low LED. Confirm the actual board and pin labels
before connecting the fixture. RUN is lowered before ID/status changes and raised
last. Common ground and PPK2 digital-level supply follow the project wiring plan.

CPU = 100 MHz from HSE / 25 × 200 / 2; AHB /1, APB1 /2, APB2 /1. PLLQ /5 is
unused by the application. USB is not initialized. Scale 1 and 3 Flash wait states,
prefetch/I-cache/D-cache enabled. Startup waits for HSE, PLL, and VOSRDY before
switching SYSCLK. FPU is enabled with CPACR and hard-float compiler flags, then
checked with a volatile float calculation. Checks repeat outside every RUN.
TIM2 counts at 10 kHz only for control gaps. These gaps busy-poll the peripheral:
they are active control idle, not a sleep-energy measurement. CPU fault handlers
lower RUN and raise ERROR. DONE final parking is outside IDLE_VALID.

Pinned dependencies (official repositories):

- [cmsis-device-f4 v2.6.11](https://github.com/STMicroelectronics/cmsis-device-f4/tree/0fa0e489e053fa1ca7790bb40b4d76458f64c55d), commit `0fa0e489e053fa1ca7790bb40b4d76458f64c55d`.
- [CMSIS_5 5.9.0](https://github.com/ARM-software/CMSIS_5/tree/2b7495b8535bdcb306dac29b9ded4cfb679d7e5c), commit `2b7495b8535bdcb306dac29b9ded4cfb679d7e5c`.
- Verified native compiler: GNU Arm Embedded GCC 9.2.1 20191025.

From the project root, with dependencies in short paths on Windows:

```powershell
cmake -S firmware/targets/stm32 -B build/stm32 -G Ninja -DARM_GCC_BIN=C:/path/to/gcc/bin -DSTM32_CMSIS_DEVICE_PATH=C:/deps/cmsis-device-f4 -DCMSIS_CORE_PATH=C:/deps/CMSIS_5
cmake --build build/stm32 --parallel
```

Outputs are ELF, BIN, HEX and map. The `.bin` base address is `0x08000000`.
This project contains no automatic flash command. Archive the exact binary hash
with a capture. Compilation and static checks are not a hardware acceptance run.

The VOSRDY order follows [ST's F4 power driver](https://github.com/STMicroelectronics/stm32f4xx-hal-driver/blob/master/Src/stm32f4xx_hal_pwr_ex.c): requested scaling becomes active with PLL enabled. Device voltage/frequency limits are in the [STM32F411 datasheet](https://www.st.com/resource/en/datasheet/stm32f411ce.pdf).
