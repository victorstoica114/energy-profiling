# Included before target project() and during common-source setup.
# A build directory belongs to one experiment; never reuse cached SDK settings
# after changing its clock profile.
set(BENCH_CLOCK_PROFILE "max_clock" CACHE STRING "Clock experiment: max_clock or common160")
set_property(CACHE BENCH_CLOCK_PROFILE PROPERTY STRINGS max_clock common160)
if(NOT BENCH_CLOCK_PROFILE MATCHES "^(max_clock|common160)$")
    message(FATAL_ERROR "BENCH_CLOCK_PROFILE must be max_clock or common160")
endif()
if(DEFINED BENCH_BUILD_CLOCK_PROFILE AND NOT BENCH_BUILD_CLOCK_PROFILE STREQUAL BENCH_CLOCK_PROFILE)
    message(FATAL_ERROR "This build directory belongs to ${BENCH_BUILD_CLOCK_PROFILE}; use a new directory for ${BENCH_CLOCK_PROFILE}")
endif()
set(BENCH_BUILD_CLOCK_PROFILE "${BENCH_CLOCK_PROFILE}" CACHE INTERNAL "Immutable build-directory experiment")
if(BENCH_CLOCK_PROFILE STREQUAL "common160")
    set(BENCH_COMMON_CLOCK_160 1)
else()
    set(BENCH_COMMON_CLOCK_160 0)
endif()
