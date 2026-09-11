# RP2040 measurement target

Marble Pico board with RP2040, using the Pico-compatible SDK board profile and 2 MiB configured Flash address space. Native Pico SDK, nominal CPU **200 MHz**, internal core regulator **1.15 V**, experiment `energy-profiling-v4-max-clock`, schema 2. This README describes **BENCH_DIAGNOSTICS=OFF** measurement firmware.

## Single measurement output

Connect **GP2 to PPK2 D0**. HIGH normally encloses one fixed-count kernel batch; LOW is outside. The twelve algorithms are inferred from pulse order. There are no separate ID, ERROR, DONE or IDLE_VALID outputs. A detected failure latches GP2 HIGH until reset; failures during a batch do not first emit a normal falling edge. This is a dedicated output, not the LED.

See the [protocol](../../../docs/PROTOCOL.md) for common ground, LOGIC VCC, direct DUT 3V3 supply and required recording intervals. A long LOW tail alone cannot prove final verification completed.

## Platform behavior

Core1 is not launched; it remains in its Boot ROM waiting state. RP2040 has no FPU and uses software floating point. SDK startup and Flash boot code are retained. Core0 reserves 4 KiB of stack in dedicated SCRATCH_Y; main work buffers are static, with fixed local arrays where needed. Link maps record the actual layout.

USB/UART stdio is disabled. UART0/1, USBCTRL and ADC are held in reset; clk_usb and clk_adc are stopped before measurement. GPIO0/1 are disconnected without pulls and the GP25 LED is held LOW/off. PLL_USB remains enabled because the SDK uses its 48 MHz output for clk_peri. clk_rtc remains at 46875 Hz. The SDK default alarm pool/handler is compiled in, but the application registers no periodic callbacks and does not globally mask interrupts. The measurement image does not enumerate as USB CDC.

SDK startup uses its default 125 MHz clock. Before the first preparation or measurement window, the firmware sets the internal core regulator to 1.15 V, waits at least 1 ms for settling, checks the voltage-selection and regulation-status bits, and switches clk_sys to 200 MHz. With the configured 12 MHz crystal, the SDK selects a 1200 MHz PLL VCO and post-dividers 6 and 1. The [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf), Sections 2.15.3 and 5.6, documents 200 MHz operation at this core voltage. The external board regulator remains removed and the PPK2 continues to supply the 3V3 rail at 3.3 V; it does not supply the core directly.

The Flash boot stage and application both use `PICO_FLASH_SPI_CLKDIV=4`, giving a 50 MHz QSPI clock during RUN. This conservative setting is deliberate: the CPU maximum does not imply running the external Flash at its maximum. The new measurements describe this complete clock configuration; previously measured energies cannot be rescaled into results for the current firmware.

Clock configuration is checked using clock_get_hz and the hardware frequency counter, accepting 200000 kHz +/-0.1% relative to clk_ref. Checks also require clk_peri at 48 MHz, the internal regulator selected at 1.15 V and reporting regulation, and the SSI Flash divider at 4. These register and counter checks are not external oscillator or voltage calibration. The hardware timer is read only for fixed control gaps, busy-polling while the CPU remains awake. PPK2 provides the benchmark timebase. After final verification and a two-second LOW pause, execution enters WFI with RUN LOW; that final state is not the active baseline.

## Build

Pinned [Pico SDK 2.2.0](https://github.com/raspberrypi/pico-sdk/tree/a1438dff1d38bd9c65dbd693f0e5db4b9ae91779), commit a1438dff1d38bd9c65dbd693f0e5db4b9ae91779. Verified campaign compiler: GNU Arm Embedded GCC 9.2.1 20191025. **TinyUSB is not needed by the measurement image.** Run from the project root and use short dependency paths on Windows:

```powershell
python scripts/fetch_native_sdks.py --dest C:/energy-deps --only rp2040
$env:PICO_TOOLCHAIN_PATH = 'C:/path/to/gcc'
cmake -S firmware/targets/rp2040 -B build/rp2040-max-clock -G Ninja -DPICO_SDK_PATH=C:/energy-deps/pico-sdk-a1438dff1d38 -DBENCH_DIAGNOSTICS=OFF
cmake --build build/rp2040-max-clock --parallel
```

The ARM helper supports the same measurement configuration:

```powershell
./scripts/build_arms.ps1 -ArmGccBin C:/path/to/gcc/bin -DepsRoot C:/energy-deps -BuildRoot build/arm-max-clock -Only rp2040
```

CMake emits ELF, BIN, HEX, map and disassembly without downloading picotool. An installed official elf2uf2 utility can produce the UF2:

```powershell
elf2uf2 build/rp2040-max-clock/energy_bench_rp2040.elf build/rp2040-max-clock/energy_bench_rp2040.uf2
```

Current artifacts belong in `build_verified/max_clock_measurement`, with compiler commands, source hashes and verification.json. [CURRENT_FIRMWARE.json](../../../CURRENT_FIRMWARE.json) identifies the current build and recorded programming status. Its `single_gpio_measurement` profile key is retained for collector compatibility and points to this current archive. Earlier firmware is available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0). Earlier measurement sets and validation logs must not be relabeled as current results.

Record the physical board and its Flash part when validating this Pico-compatible profile. Compilation and static checks are not a PPK2 hardware acceptance capture. The 200 MHz profile requires new captures for all twelve workloads and its active-idle reference. [Official Pico clock API](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#hardware_clocks).
