# RP2040 measurement target

Raspberry Pi Pico profile with RP2040 and 2 MiB configured Flash. Native Pico SDK, nominal CPU **133 MHz**, experiment `energy-profiling-v3-single-gpio`, schema 2. This README describes **BENCH_DIAGNOSTICS=OFF** measurement firmware.

## Single measurement output

Connect **GP2 to PPK2 D0**. HIGH normally encloses one fixed-count kernel batch; LOW is outside. The twelve algorithms are inferred from pulse order. There are no separate ID, ERROR, DONE or IDLE_VALID outputs. A detected failure latches GP2 HIGH until reset; failures during a batch do not first emit a normal falling edge. This is a dedicated output, not the LED.

See the [protocol](../../../docs/PROTOCOL.md) for common ground, LOGIC VCC, direct DUT 3V3 supply and required recording intervals. A long LOW tail alone cannot prove final verification completed.

## Platform behavior

Core1 is not launched; it remains in its Boot ROM waiting state. RP2040 has no FPU and uses software floating point. SDK startup and Flash boot code are retained. Core0 reserves 4 KiB of stack in dedicated SCRATCH_Y; main work buffers are static, with fixed local arrays where needed. Link maps record the actual layout.

USB/UART stdio is disabled. UART0/1, USBCTRL and ADC are held in reset; clk_usb and clk_adc are stopped before measurement. GPIO0/1 are disconnected without pulls and the GP25 LED is held LOW/off. PLL_USB remains enabled because the SDK uses its 48 MHz output for clk_peri. clk_rtc remains at 46875 Hz. The SDK default alarm pool/handler is compiled in, but the application registers no periodic callbacks and does not globally mask interrupts. The measurement image does not enumerate as USB CDC.

Clock configuration is checked using clock_get_hz and the hardware frequency counter, accepting 133000 kHz +/-0.1% relative to clk_ref. This is not external oscillator calibration. The hardware timer is read only for fixed control gaps, busy-polling while the CPU remains awake. PPK2 provides the benchmark timebase. After final verification and a two-second LOW pause, execution enters WFI with RUN LOW; that final state is not the active baseline.

## Build

Pinned [Pico SDK 2.2.0](https://github.com/raspberrypi/pico-sdk/tree/a1438dff1d38bd9c65dbd693f0e5db4b9ae91779), commit a1438dff1d38bd9c65dbd693f0e5db4b9ae91779. Verified campaign compiler: GNU Arm Embedded GCC 9.2.1 20191025. **TinyUSB is not needed by the measurement image.** Run from the project root and use short dependency paths on Windows:

```powershell
python scripts/fetch_native_sdks.py --dest C:/energy-deps --only rp2040
$env:PICO_TOOLCHAIN_PATH = 'C:/path/to/gcc'
cmake -S firmware/targets/rp2040 -B build/rp2040-single-gpio -G Ninja -DPICO_SDK_PATH=C:/energy-deps/pico-sdk-a1438dff1d38 -DBENCH_DIAGNOSTICS=OFF
cmake --build build/rp2040-single-gpio --parallel
```

The ARM helper supports the same measurement configuration:

```powershell
./scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/energy-deps -BuildRoot build/arm-single-gpio -Only rp2040
```

CMake emits ELF, BIN, HEX, map and disassembly without downloading picotool. An installed official elf2uf2 utility can produce the UF2:

```powershell
elf2uf2 build/rp2040-single-gpio/energy_bench_rp2040.elf build/rp2040-single-gpio/energy_bench_rp2040.uf2
```

New artifacts belong in build_verified/single_gpio_measurement, with compiler commands, source hashes and verification.json. [CURRENT_FIRMWARE.json](../../../CURRENT_FIRMWARE.json) distinguishes candidate builds from images last programmed. Files directly in build_verified and the older measurement, diagnostic and diagnostic_uart subdirectories retain the **historical eight-signal protocol**. Their logs do not prove the new one-wire firmware has run on a board.

Do not silently change the board profile to accommodate another physical board. Compilation and static checks are not a PPK2 hardware acceptance capture. [Official Pico clock API](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#hardware_clocks).
