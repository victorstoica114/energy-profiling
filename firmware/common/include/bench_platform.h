#ifndef BENCH_PLATFORM_H
#define BENCH_PLATFORM_H

#include <stdbool.h>
#include <stdint.h>

/* Validation builds may use a synchronous UART reporter. Measurement builds
 * default to no diagnostic code and require no platform reporter definition. */
#ifndef BENCH_DIAGNOSTICS
#define BENCH_DIAGNOSTICS 0
#endif
#if BENCH_DIAGNOSTICS != 0 && BENCH_DIAGNOSTICS != 1
#error BENCH_DIAGNOSTICS must be 0 or 1
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* No function in this interface measures or reports benchmark duration. */
bool bench_platform_init(void);
bool bench_platform_check(void);
/* The only exported GPIO: HIGH during a batch, LOW between batches.
 * A detected failure latches HIGH until reset; no other status pins exist.
 * Setting an already-HIGH marker must not insert a spurious LOW pulse. */
void bench_platform_marker(bool high);
/* Hardware timebase used only for control gaps, outside RUN. */
void bench_platform_wait_ms(uint32_t milliseconds);
void bench_platform_finish(void);

/* Events: BOOT, START, PASS, DONE, ERROR. START carries the configured count;
 * PASS carries the completed count and output digest; BOOT/DONE use zeros.
 * ERROR carries the completed count and a bench_error_reason in digest.
 * Ordinary events occur while RUN is LOW, outside the active idle waits.
 * ERROR may be reported after the fault has latched RUN HIGH. Enabled platform
 * implementations must finish transmitting before returning (no async tail).
 * UART schema: BENCH event=... id=... calls=... digest=<8 hex digits>
 */
enum bench_error_reason {
    BENCH_ERROR_PLATFORM_INIT = 1,
    BENCH_ERROR_PLATFORM_BEFORE_PREPARE = 2,
    BENCH_ERROR_KERNEL_PREPARE = 3,
    BENCH_ERROR_PLATFORM_BEFORE_RUN = 4,
    BENCH_ERROR_KERNEL_RUN = 5,
    BENCH_ERROR_CALL_COUNT = 6,
    BENCH_ERROR_PLATFORM_AFTER_RUN = 7,
    BENCH_ERROR_KERNEL_VERIFY = 8
};
#if BENCH_DIAGNOSTICS
void bench_platform_report(const char *event, unsigned id, unsigned calls, uint32_t digest);
#else
static inline void bench_platform_report(const char *event, unsigned id,
                                         unsigned calls, uint32_t digest) {
    (void)event; (void)id; (void)calls; (void)digest;
}
#endif
/* Implemented by the common runner; called once from the native entry point. */
void bench_main(void);

#ifdef __cplusplus
}
#endif
#endif
