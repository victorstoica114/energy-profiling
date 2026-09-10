set(BENCH_COMMON_ROOT "${CMAKE_CURRENT_LIST_DIR}")
get_filename_component(BENCH_PROJECT_ROOT "${BENCH_COMMON_ROOT}/../.." ABSOLUTE)
if(DEFINED PYTHON)
    set(BENCH_CHECK_PYTHON "${PYTHON}")
else()
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(BENCH_CHECK_PYTHON "${Python3_EXECUTABLE}")
endif()
execute_process(COMMAND "${BENCH_CHECK_PYTHON}" "${BENCH_PROJECT_ROOT}/tools/generate_inputs.py" --check
    RESULT_VARIABLE BENCH_INPUT_CHECK OUTPUT_VARIABLE BENCH_INPUT_CHECK_OUTPUT
    ERROR_VARIABLE BENCH_INPUT_CHECK_ERROR)
if(NOT BENCH_INPUT_CHECK EQUAL 0)
    message(FATAL_ERROR "Manifest/generated input mismatch: ${BENCH_INPUT_CHECK_OUTPUT}${BENCH_INPUT_CHECK_ERROR}")
endif()
set(BENCH_KERNEL_SOURCES
    "${BENCH_COMMON_ROOT}/kernels/bench_algorithms.c"
    "${BENCH_COMMON_ROOT}/kernels/bench_kernels.c")
set(BENCH_COMMON_SOURCES
    "${BENCH_COMMON_ROOT}/bench_runner.c"
    "${BENCH_COMMON_ROOT}/bench_data.c"
    ${BENCH_KERNEL_SOURCES})
set(BENCH_COMMON_INCLUDE_DIRS
    "${BENCH_COMMON_ROOT}/include"
    "${BENCH_COMMON_ROOT}/kernels")
