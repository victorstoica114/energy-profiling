include(${CMAKE_CURRENT_LIST_DIR}/../../../common/bench_sources.cmake)
# IDF discovers component requirements in an early standalone CMake pass,
# before this project's diagnostic option is available. Declare the header
# dependency here; OFF compilation contains no UART-driver calls, and unused
# driver sections are removed by the final link.
set(BENCH_PLATFORM_REQUIRES esp_driver_gpio esp_driver_gptimer esp_hw_support esp_wifi esp_driver_uart)
idf_component_register(SRCS "platform_esp32.c" ${BENCH_COMMON_SOURCES}
    INCLUDE_DIRS ${BENCH_COMMON_INCLUDE_DIRS}
    REQUIRES ${BENCH_PLATFORM_REQUIRES})
target_compile_definitions(${COMPONENT_LIB} PRIVATE BENCH_BOARD_ESP32=1 BENCH_COMMON_CLOCK_160=${BENCH_COMMON_CLOCK_160} BENCH_DIAGNOSTICS=$<BOOL:${BENCH_DIAGNOSTICS}>)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-lto -Wall -Wextra)
