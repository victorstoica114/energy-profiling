# Temporary STM32F446 PC10 UART diagnostic

This isolated diagnostic image routes USART3 TX to PC10 (AF7) at 115200 baud, 8N1, without RX, interrupts, or DMA. It bypasses the board's open PA2 routing bridge. PC10 is available at NUCLEO-F446RE CN7 pin 1 and connects to the ST-LINK UART RX at CN3 pin 1. The CONFIG line includes `transport=USART3_PC10`.

This image is for functional checks only. The published silent measurement image and canonical source tree have not been changed. Do not use this diagnostic image for energy acquisition.

## Exact changes

Only `firmware/targets/stm32f446/platform_stm32f446.c` differs from the canonical source snapshot:

- Require `BENCH_DIAGNOSTICS=1` at compilation.
- Initialize PC10 AF7 and USART3 instead of PA2 AF7 and USART2.
- Send UART output through USART3; retain APB1-derived baud calculation.
- Require USART3 enabled and USART2 disabled in the diagnostic platform guard; disable both UART clocks before initialization.
- Append the transport identifier to CONFIG.

The clock configuration function is identical to the canonical version. The 180 MHz HSI/PLL profile, Scale 1/OverDrive, Flash configuration, timer, RUN PC0, algorithm order, fixed input data, and iteration counts are unchanged. `diagnostic_uart_pc10.patch` records every source change. `source_sha256_at_archive.json` records all copied source/configuration/input files. The complete isolated source is included in `stm32_uart_pc10_source.zip`; extract it to reproduce the build. Absolute paths in archived build commands identify the original build environment.

## Reproduction

Use the pinned SDK versions in the copied target's `sdk.lock.json` and GNU Arm GCC 9.2.1. The configure and build invocations, exit statuses, source directory, and short temporary build path are recorded in `build_commands.json`. Set `BENCH_DIAGNOSTICS=ON`; the additional source guard deliberately rejects an OFF build. CMake checks the frozen input files and generated configuration before compiling.

## Verification

`verification.json` records the native build, compiler flags, embedded 2048-byte inputs, all 12 kernel symbols and exact iteration counts. All seven common, runtime, and startup object files are byte-identical to the original PA2 diagnostic build. The linked image includes the USART3 and GPIOC register bases and the explicit transport string. BIN, ELF, HEX, MAP, compile commands, CMake cache, Ninja build rules, symbols, and disassembly are archived here.

Canonical silent measurement BIN SHA-256 remains `9fa0531d09e2e55ab22d7f4eaa39d0a5a32b3d7c3c15cd6fda716621f6adfafd`. Temporary PC10 diagnostic BIN SHA-256 is `bad4ada326566d1dc029fdca394bfb2f6a389514877ff4e473746eea177f7b53`.

Hardware execution passed: all twelve workloads and final DONE are recorded in [the diagnostic record](../stm32f446_pc10_diagnostic_01.json), with the raw UART bytes alongside it. A successful diagnostic run does not establish silent-image execution or PPK2 capture acceptance.
