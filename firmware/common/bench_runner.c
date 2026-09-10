/* Fixed-count benchmark. Time and charge are measured externally by PPK2. */
#include "bench_platform.h"
#include "bench_kernels.h"
#include "bench_config.h"
#include "bench_data.h"
#include <stdbool.h>
#include <stdint.h>

/* Retained for a debugger outside acquisition. Never printed during RUN. */
volatile uint32_t bench_completed_calls[12];
volatile uint32_t bench_result_digests[12];
volatile unsigned bench_failed_algorithm;
volatile uint32_t bench_failure_reason;

static void compiler_barrier(void) {
#if defined(__GNUC__)
    __asm__ volatile ("" ::: "memory");
#else
#error This benchmark requires an audited compiler barrier
#endif
}

static void fail(unsigned id, unsigned completed, enum bench_error_reason reason) {
    bench_failed_algorithm = id;
    bench_failure_reason = (uint32_t)reason;
    bench_platform_signals(id, false, false, true, false);
    bench_platform_report("ERROR", id, completed, (uint32_t)reason);
    bench_platform_finish();
}

static const uint8_t *input_for(unsigned id) {
    if (id <= 4u) return bench_compression_input;
    if (id <= 8u) return bench_crypto_input;
    return bench_dsp_input;
}

void bench_main(void) {
    if (!bench_platform_init()) { fail(0u, 0u, BENCH_ERROR_PLATFORM_INIT); return; }
    bench_platform_signals(0u, false, false, false, false);
    bench_platform_report("BOOT", 0u, 0u, 0u);
    for (unsigned id = 1u; id <= 12u; ++id) {
        bench_platform_signals(0u, false, false, false, false);
        if (!bench_platform_check()) {
            fail(id, 0u, BENCH_ERROR_PLATFORM_BEFORE_PREPARE); return;
        }
        if (!bench_kernel_prepare(id, input_for(id), BENCH_INPUT_BYTES)) {
            fail(id, 0u, BENCH_ERROR_KERNEL_PREPARE); return;
        }
        /* Prepare first, then measure a stable operational idle interval. */
        bench_platform_signals(0u, false, true, false, false);
        bench_platform_wait_ms(id == 1u ? BENCH_STARTUP_IDLE_MS : BENCH_INTER_ALGORITHM_IDLE_MS);
        bench_platform_signals(id, false, false, false, false);
        /* ID settles for many PPK2 samples; this is outside RUN. */
        bench_platform_wait_ms(1u);
        if (!bench_platform_check()) { fail(id, 0u, BENCH_ERROR_PLATFORM_BEFORE_RUN); return; }
        const uint32_t count = bench_iterations[id - 1u];
        uint32_t completed = 0u;
        bool success = true;
        bench_platform_report("START", id, count, 0u);
        compiler_barrier();
        bench_platform_signals(id, true, false, false, false);
        compiler_barrier();
        for (uint32_t iteration = 0u; iteration < count; ++iteration) {
            if (!bench_kernel_run(id)) { success = false; break; }
            compiler_barrier();
            ++completed;
        }
        compiler_barrier();
        bench_platform_signals(id, false, false, false, false);
        compiler_barrier();
        bench_completed_calls[id - 1u] = completed;
        if (!success) { fail(id, completed, BENCH_ERROR_KERNEL_RUN); return; }
        if (completed != count) { fail(id, completed, BENCH_ERROR_CALL_COUNT); return; }
        if (!bench_platform_check()) { fail(id, completed, BENCH_ERROR_PLATFORM_AFTER_RUN); return; }
        if (!bench_kernel_verify(id)) { fail(id, completed, BENCH_ERROR_KERNEL_VERIFY); return; }
        bench_result_digests[id - 1u] = bench_kernel_digest(id);
        bench_platform_report("PASS", id, completed, bench_result_digests[id - 1u]);
    }
    bench_platform_signals(0u, false, true, false, true);
    bench_platform_wait_ms(BENCH_POST_SUITE_IDLE_MS);
    /* Platform finish may enter WFI/scheduler idle: it is not the active baseline. */
    bench_platform_signals(0u, false, false, false, true);
    bench_platform_report("DONE", 0u, 0u, 0u);
    bench_platform_finish();
}
