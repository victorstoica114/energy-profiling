# NUCLEO-F446RE native target

This is the current STM32 target. The separate `stm32` directory retains the
earlier F411 target and its historical artifacts; its binaries must not be used
on this board. This target uses the actual F446 CMSIS header and vector table,
512 KiB Flash, 128 KiB SRAM, and a linker reservation of 16 KiB for stack.
Startup rejects a device ID other than `0x421` or a flash-size register other
than 512 KiB.

The clock is nominally **100 MHz**, preserving the campaign's selected CPU
frequency. HSI16 /16 x200 /2 supplies SYSCLK without the ST-Link MCO signal or
an assumed external crystal. AHB is 100 MHz, APB1 25 MHz (/4), APB2 50 MHz (/2).
The F446 bus limits are 45 and 90 MHz, so the F411 bus divisors cannot be reused.
Scale 1, overdrive off, three Flash wait states, prefetch and Flash caches are
explicit. FPU access and hard-float flags are enabled and checked. These are
register checks, not an external measurement of the HSI's physical frequency.
[ST datasheet DS10693](https://www.st.com/resource/en/datasheet/stm32f446re.pdf)
and [RM0390](https://www.st.com/resource/en/reference_manual/rm0390-stm32f446xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)
define the device and clock tree.

GPIO signals occupy one atomic bank, PC0 through PC7. LD2 on PA5 stays LOW/off.
TIM2 uses the 50 MHz APB1 timer clock, /5000, for busy-polled control gaps.
RUN duration is never measured by the MCU.

| PPK2 | Signal | MCU | Nucleo morpho position |
|---|---|---|---|
| D0 | RUN | PC0 | CN7 pin 38 |
| D1 | ID bit 0 | PC1 | CN7 pin 36 |
| D2 | ID bit 1 | PC2 | CN7 pin 35 |
| D3 | ID bit 2 | PC3 | CN7 pin 37 |
| D4 | ID bit 3 | PC4 | CN10 pin 34 |
| D5 | IDLE_VALID | PC5 | CN10 pin 6 |
| D6 | ERROR | PC6 | CN10 pin 4 |
| D7 | DONE | PC7 | CN10 pin 19 |

PC0/PC1 routing requires SB51/SB56 ON and SB46/SB52 OFF; inspect the actual board
before wiring. The onboard VCP connects USART2 PA2/PA3 through SB13/SB14. The
diagnostic transmitter uses PA2 only, leaving RX unused. Connector and bridge
details come from [UM1724, tables 10 and 29](https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf).

`BENCH_DIAGNOSTICS` is **OFF by default**. With ON, USART2 sends 115200-baud 8N1
records without interrupts or DMA. Every report waits for transmission complete
before returning; the runner reports outside RUN and IDLE_VALID. BOOT includes
a CONFIG line with actual clock, device and FPU registers. Event lines follow
`BENCH event=PASS id=1 calls=3000 digest=12345678`.

With OFF, no reporter implementation or UART message strings are linked,
USART2's peripheral clock is disabled, and PA2/PA3 are analog inputs. This
software switch does not electrically isolate the onboard debugger, USB power
or UART bridges; follow the project fixture procedure for the energy campaign.
UART diagnostic firmware is a functional pilot, not an energy-measurement image.

Both builds use the pinned SDK identities in `sdk.lock.json` and GNU Arm Embedded
GCC 9.2.1 20191025. From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/short/deps -BuildRoot C:/short/build -Only stm32 -Diagnostics
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/short/deps -BuildRoot C:/short/build -Only stm32
```

The first output directory is `stm32f446-diagnostic`, the second `stm32f446`.
BIN load address is `0x08000000`. Build helpers do not flash devices. Archived
native results are separated in `build_verified/diagnostic` and
`build_verified/measurement`; hardware test reports are maintained by the
project's hardware-validation procedure.
