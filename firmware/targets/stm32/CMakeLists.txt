cmake_minimum_required(VERSION 3.20)
message(FATAL_ERROR "Historical STM32F411 target: disabled for the current NUCLEO-F446RE campaign. Use firmware/targets/stm32f446. Restore the complete historical configuration separately to reproduce F411 artifacts.")
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
if(DEFINED ARM_GCC_BIN)
  file(TO_CMAKE_PATH "${ARM_GCC_BIN}" ARM_GCC_BIN)
  set(CMAKE_C_COMPILER "${ARM_GCC_BIN}/arm-none-eabi-gcc.exe")
  set(CMAKE_ASM_COMPILER "${ARM_GCC_BIN}/arm-none-eabi-gcc.exe")
  set(CMAKE_OBJCOPY "${ARM_GCC_BIN}/arm-none-eabi-objcopy.exe")
endif()
project(energy_bench_stm32 C ASM)
set(CMAKE_C_STANDARD 11)
file(TO_CMAKE_PATH "${STM32_CMSIS_DEVICE_PATH}" STM32_CMSIS_DEVICE_PATH)
file(TO_CMAKE_PATH "${CMSIS_CORE_PATH}" CMSIS_CORE_PATH)
if(NOT EXISTS "${STM32_CMSIS_DEVICE_PATH}/Include/stm32f411xe.h")
  message(FATAL_ERROR "Set STM32_CMSIS_DEVICE_PATH to cmsis-device-f4 v2.6.11")
endif()
if(NOT EXISTS "${CMSIS_CORE_PATH}/CMSIS/Core/Include/core_cm4.h")
  message(FATAL_ERROR "Set CMSIS_CORE_PATH to CMSIS_5 5.9.0")
endif()
include(${CMAKE_CURRENT_LIST_DIR}/../../common/bench_sources.cmake)
add_executable(energy_bench_stm32
  platform_stm32.c runtime.c
  ${STM32_CMSIS_DEVICE_PATH}/Source/Templates/gcc/startup_stm32f411xe.s
  ${STM32_CMSIS_DEVICE_PATH}/Source/Templates/system_stm32f4xx.c
  ${BENCH_COMMON_SOURCES})
target_include_directories(energy_bench_stm32 PRIVATE ${BENCH_COMMON_INCLUDE_DIRS}
  ${STM32_CMSIS_DEVICE_PATH}/Include ${CMSIS_CORE_PATH}/CMSIS/Core/Include)
target_compile_definitions(energy_bench_stm32 PRIVATE BENCH_BOARD_STM32=1 STM32F411xE HSE_VALUE=25000000U)
target_compile_options(energy_bench_stm32 PRIVATE -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16
  -mfloat-abi=hard -O2 -fno-fast-math -ffp-contract=off -fno-lto -ffunction-sections
  -fdata-sections -fstack-usage -Wall -Wextra)
target_link_options(energy_bench_stm32 PRIVATE -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16
  -mfloat-abi=hard -nostartfiles --specs=nano.specs --specs=nosys.specs
  "-T${CMAKE_CURRENT_LIST_DIR}/stm32f411.ld" -Wl,--gc-sections
  "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/energy_bench_stm32.map")
target_link_libraries(energy_bench_stm32 m c gcc)
set_target_properties(energy_bench_stm32 PROPERTIES SUFFIX .elf)
add_custom_command(TARGET energy_bench_stm32 POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:energy_bench_stm32> energy_bench_stm32.bin
  COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:energy_bench_stm32> energy_bench_stm32.hex)
