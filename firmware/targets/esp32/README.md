# ESP32 measurement target

Classic ESP32 DevKit profile, native ESP-IDF **5.5.4**, nominal CPU **240 MHz**. Current experiment: `energy-profiling-v4-max-clock`, schema 2, GPIO protocol `single_run_v1`. This README describes the measurement image, built with **BENCH_DIAGNOSTICS=OFF**.

## Single measurement output

Connect **GPIO18 to PPK2 D0**. It is a dedicated logic output, without a marker LED. HIGH normally encloses one fixed-count workload batch; LOW is outside. Algorithms are inferred from the twelve pulses in fixed order. There are no separate ID, ERROR, DONE or IDLE_VALID outputs. A detected error latches GPIO18 HIGH until reset, without an intervening LOW when the batch itself fails.

The generated manifest's marker pin and CPU frequency are checked against this target. Follow the [acquisition protocol](../../../docs/PROTOCOL.md) for ground, LOGIC VCC, isolated DUT 3V3 supply and the three-second final LOW recording tail. Structural acceptance cannot prove all final checks completed if execution hangs LOW.

## Platform behavior

Compile-time checks require FreeRTOS unicore mode (benchmark on CPU0, CPU1 disabled), PM disabled, Bluetooth disabled and task watchdog disabled. The interrupt watchdog and 100 Hz FreeRTOS tick remain active. Interrupts are not globally masked. This RTOS background belongs to the configured workload and is not claimed identical to bare metal.

No code initializes Wi-Fi or Bluetooth. esp_wifi_get_mode must return ESP_ERR_WIFI_NOT_INIT before the sequence or a later batch proceeds. An initialized but disconnected Wi-Fi driver is rejected. Linking the Wi-Fi component to query its state does not start the radio.

With the measurement option OFF, UART0/1/2 are reset and their clocks gated; GPIO1/3 are disabled without pulls. No console is initialized. Immutable ROM boot text can precede application initialization and the baseline; it is outside the measured windows. PM, automatic sleep and frequency scaling are disabled.

The native clock-tree API checks nominal CPU frequency, and runtime checks require core0. A volatile float probe exercises a floating-point path. Common crypto kernels are software implementations and do not call ESP hardware crypto entry points. Single-precision arithmetic can use the FPU; double is not assumed hardware-accelerated. Main-task stack reservation is 16 KiB.

GPTimer at 1 MHz controls the pauses by busy polling and is stopped before returning. The CPU remains awake during the operational baseline. After final verification and the two-second LOW pause, the main task is suspended and the RTOS idle/scheduler continues. That final state is outside the selected baseline. The MCU exports no benchmark timestamp.

## Build

Use Espressif GCC esp-14.2.0_20260121 (GCC 14.2.0), required by ESP-IDF 5.5.4 tools/tools.json, and the matching IDF Python environment. Run from the project root in a fresh build directory:

```powershell
cmake -S firmware/targets/esp32 -B build/esp32-max-clock -G Ninja -DIDF_TARGET=esp32 -DBENCH_DIAGNOSTICS=OFF
cmake --build build/esp32-max-clock --parallel
```

Equivalent IDF wrapper:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32-max-clock -DBENCH_DIAGNOSTICS=OFF build
```

Retain sdkconfig, build log, ELF, map, compiler commands and image hashes. Existing sdkconfig is not silently overridden to mask essential profile mismatches: compile-time/runtime gates reject them. Build helpers do not flash or launch a monitor.

ESP32 bootloader, partition table and application form the flashing set. Keep flash_args and their relative layout with the build; the application BIN alone is not a complete blank-board image. Flash settings are DIO/40 MHz/4 MiB for the selected board; PSRAM is disabled.

Current measurement artifacts are archived under `build_verified/max_clock_measurement`. [CURRENT_FIRMWARE.json](../../../CURRENT_FIRMWARE.json) separates build status from recorded programming and measurement evidence. Its `single_gpio_measurement` profile key is retained for collector compatibility and points to the current archive. Earlier firmware is available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0).

The ESP32 CPU clock, radio policy, Flash settings, workload inputs and repetition counts are unchanged by this maximum-clock transition. Earlier ESP32 captures may be retained with their original manifest and image hashes when configuration equivalence is verified. They are not captures of the newly compiled binary. Compilation or a silent terminal is not physical pulse/energy validation.

Official references: [IDF 5.5.4](https://github.com/espressif/esp-idf/tree/v5.5.4), [clock-tree API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/peripherals/clk_tree.html), [Wi-Fi state](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/network/esp_wifi.html), [watchdogs](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/system/wdts.html).
