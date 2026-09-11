# ESP32 measurement target

Classic ESP32 DevKit target, native ESP-IDF **5.5.4**, with two explicit clock profiles. `BENCH_CLOCK_PROFILE=max_clock` is the default: **240 MHz**, experiment `energy-profiling-v4-max-clock`, application version 1.1.0. `BENCH_CLOCK_PROFILE=common160` selects **160 MHz**, experiment `energy-profiling-v5-common160`, application version 1.2.0. Both retain experiment schema 2 and GPIO protocol `single_run_v1`. This README describes the measurement image, built with **BENCH_DIAGNOSTICS=OFF**.

## Single measurement output

Connect **GPIO18 to PPK2 D0**. It is a dedicated logic output, without a marker LED. HIGH normally encloses one fixed-count workload batch; LOW is outside. Algorithms are inferred from the twelve pulses in fixed order. There are no separate ID, ERROR, DONE or IDLE_VALID outputs. A detected error latches GPIO18 HIGH until reset, without an intervening LOW when the batch itself fails.

The generated manifest's marker pin and CPU frequency are checked against this target. Follow the [acquisition protocol](../../../docs/PROTOCOL.md) for ground, LOGIC VCC, isolated DUT 3V3 supply and the three-second final LOW recording tail. Structural acceptance cannot prove all final checks completed if execution hangs LOW.

## Platform behavior

Compile-time checks require FreeRTOS unicore mode (benchmark on CPU0, CPU1 disabled), PM disabled, Bluetooth disabled and task watchdog disabled. The interrupt watchdog and 100 Hz FreeRTOS tick remain active. Interrupts are not globally masked. This RTOS background belongs to the configured workload and is not claimed identical to bare metal.

No code initializes Wi-Fi or Bluetooth. esp_wifi_get_mode must return ESP_ERR_WIFI_NOT_INIT before the sequence or a later batch proceeds. An initialized but disconnected Wi-Fi driver is rejected. Linking the Wi-Fi component to query its state does not start the radio.

With the measurement option OFF, UART0/1/2 are reset and their clocks gated; GPIO1/3 are disabled without pulls. No console is initialized. Immutable ROM boot text can precede application initialization and the baseline; it is outside the measured windows. PM, automatic sleep and frequency scaling are disabled.

The native clock-tree API checks nominal CPU frequency, and runtime checks require core0. A volatile float probe exercises a floating-point path. Common crypto kernels are software implementations and do not call ESP hardware crypto entry points. Single-precision arithmetic can use the FPU; double is not assumed hardware-accelerated. Main-task stack reservation is 16 KiB.

Classic ESP32 supports the standard PLL CPU frequencies 80, 160 and 240 MHz; 160 MHz is the highest of these compatible with the selected STM32F446's 180 MHz ceiling. At 160 MHz, ESP-IDF uses the 320 MHz PLL divided by two; at 240 MHz, it uses the 480 MHz PLL divided by two. APB remains 80 MHz in both profiles. With the retained 40 MHz Flash setting, ESP-IDF selects `RTC_CNTL_DBIAS_1V10` at 160 MHz and `RTC_CNTL_DBIAS_1V25` at 240 MHz. These are nominal internal digital-core bias settings, not externally measured voltages; the PPK2 supply remains 3.3 V. The comparison therefore changes the SDK-supported operating point, including its internal bias policy, rather than varying CPU frequency alone. [IDF clock modes](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/system/power_management.html), [clock implementation](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_hw_support/port/esp32/rtc_clk.c) and [bias definitions](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_hw_support/port/esp32/include/soc/rtc.h).

GPTimer at 1 MHz controls the pauses by busy polling and is stopped before returning. The CPU remains awake during the operational baseline. After final verification and the two-second LOW pause, the main task is suspended and the RTOS idle/scheduler continues. That final state is outside the selected baseline. The MCU exports no benchmark timestamp.

## Build

Use Espressif GCC esp-14.2.0_20260121 (GCC 14.2.0), required by ESP-IDF 5.5.4 tools/tools.json, and the matching IDF Python environment. Run from the project root in a fresh build directory:

```powershell
cmake -S firmware/targets/esp32 -B build/esp32-max-clock -G Ninja -DIDF_TARGET=esp32 -DBENCH_CLOCK_PROFILE=max_clock -DBENCH_DIAGNOSTICS=OFF
cmake --build build/esp32-max-clock --parallel

cmake -S firmware/targets/esp32 -B build/esp32-common160 -G Ninja -DIDF_TARGET=esp32 -DBENCH_CLOCK_PROFILE=common160 -DBENCH_DIAGNOSTICS=OFF
cmake --build build/esp32-common160 --parallel
```

Equivalent IDF wrapper:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32-max-clock -DBENCH_CLOCK_PROFILE=max_clock -DBENCH_DIAGNOSTICS=OFF build
idf.py -C firmware/targets/esp32 -B build/esp32-common160 -DBENCH_CLOCK_PROFILE=common160 -DBENCH_DIAGNOSTICS=OFF build
```

Each build directory owns its generated `sdkconfig`. CMake selects `sdkconfig.defaults` for `max_clock` or `sdkconfig.defaults.common160` for `common160`; their only setting difference is the CPU frequency. A source-directory `sdkconfig` is left untouched and is not shared between profiles. CMake rejects a profile change in an existing build directory, an external/shared SDKCONFIG path, an incompatible defaults file or a mismatched cached CPU frequency. Compile-time checks also compare SDK frequency against the selected generated manifest; runtime checks repeat the CPU/core validation. Retain each build's sdkconfig, log, ELF, map, compiler commands and image hashes. Build commands do not flash or launch a monitor.

ESP32 bootloader, partition table and application form the flashing set. Keep flash_args and their relative layout with the build; the application BIN alone is not a complete blank-board image. Flash settings are DIO/40 MHz/4 MiB for the selected board; PSRAM is disabled.

The published maximum-clock measurement artifacts remain under `build_verified/max_clock_measurement`. Keep common160 artifacts in a separate archive and identify their manifest and image hashes explicitly. [CURRENT_FIRMWARE.json](../../../CURRENT_FIRMWARE.json) separates build status from recorded programming and measurement evidence. Earlier firmware is available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0).

Both profiles preserve the radio policy, Flash settings, workload inputs and repetition counts. Earlier 240 MHz ESP32 captures may be retained only for the maximum-clock campaign, with their original manifest and image hashes and verified configuration equivalence. The common160 campaign requires new ESP32 captures and new active-idle references. Compilation or a silent terminal is not physical pulse/energy validation.

Official references: [IDF 5.5.4](https://github.com/espressif/esp-idf/tree/v5.5.4), [clock-tree API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/peripherals/clk_tree.html), [Wi-Fi state](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/network/esp_wifi.html), [watchdogs](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/system/wdts.html).
