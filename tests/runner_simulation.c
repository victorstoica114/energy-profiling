/* Execute the actual runner with observable fake hardware and kernels. */
#include "bench_platform.h"
#include "bench_kernels.h"
#include "bench_config.h"
#include "bench_data.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

void bench_main(void);
extern volatile uint32_t bench_completed_calls[12];
extern volatile uint32_t bench_result_digests[12];
extern volatile unsigned bench_failed_algorithm;
extern volatile uint32_t bench_failure_reason;

static unsigned current_id, rises, falls, preparations, verifications, checks;
static unsigned finishes, idle5, idle1, final_idle, settle;
static uint32_t actual[12];
static bool running, idle_state, error_seen, done_seen;
static unsigned fault;
struct diagnostic_event {
    const char *event;
    unsigned id, calls;
    uint32_t digest;
};
static struct diagnostic_event reports[32];
static unsigned report_count;

bool bench_platform_init(void) { return fault != 1u; }
bool bench_platform_check(void) {
    ++checks;
    return !((fault == 2u && checks == 1u) ||
             (fault == 6u && checks == 2u) ||
             (fault == 7u && checks == 3u));
}
void bench_platform_signals(unsigned id, bool run, bool idle, bool error, bool done) {
    assert(id <= 12u && !(run && idle));
    if (run && !running) {
        assert(id == rises + 1u && id != 0u && !error && !done);
        current_id = id;
        ++rises;
    }
    if (running) assert(id == current_id);
    if (!run && running) ++falls;
    running = run;
    idle_state = idle;
    error_seen |= error;
    done_seen |= done;
    if (done) assert(rises == 12u && falls == 12u && !run && !error);
}
void bench_platform_wait_ms(uint32_t ms) {
    assert(!running);
    if (ms == 5000u) { assert(idle_state); ++idle5; }
    else if (ms == 1000u) { assert(idle_state); ++idle1; }
    else if (ms == 2000u) { assert(idle_state && done_seen); ++final_idle; }
    else if (ms == 1u) { assert(!idle_state); ++settle; }
    else assert(!"Unexpected control delay");
}
void bench_platform_finish(void) { assert(!running); ++finishes; }

#if BENCH_DIAGNOSTICS
void bench_platform_report(const char *event, unsigned id, unsigned calls, uint32_t digest) {
    /* The central contract: UART work never overlaps RUN or marked idle. */
    assert(!running && !idle_state && report_count < 32u);
    if (!strcmp(event, "BOOT")) {
        assert(!rises && !preparations && !id && !calls && !digest);
    } else if (!strcmp(event, "START")) {
        assert(id >= 1u && id <= 12u && !actual[id-1u]);
        assert(calls == bench_iterations[id-1u] && !digest);
    } else if (!strcmp(event, "PASS")) {
        assert(id == verifications && calls == bench_completed_calls[id-1u]);
        assert(digest == bench_result_digests[id-1u] && digest == 0xabc00000u + id);
    } else if (!strcmp(event, "DONE")) {
        assert(done_seen && final_idle == 1u && !id && !calls && !digest);
    } else if (!strcmp(event, "ERROR")) {
        assert(error_seen && !done_seen && id == bench_failed_algorithm);
        assert(digest == bench_failure_reason);
        assert(calls == (id ? bench_completed_calls[id-1u] : 0u));
    } else {
        assert(!"Unexpected diagnostic event");
    }
    reports[report_count++] = (struct diagnostic_event){event, id, calls, digest};
}

static void expect_report(unsigned index, const char *event, unsigned id,
                          unsigned calls, uint32_t digest) {
    assert(index < report_count);
    assert(!strcmp(reports[index].event, event));
    assert(reports[index].id == id && reports[index].calls == calls && reports[index].digest == digest);
}
#endif

static void expect_failure(unsigned id, unsigned calls, enum bench_error_reason reason,
                           unsigned expected_reports) {
    assert(bench_failed_algorithm == id && bench_failure_reason == (uint32_t)reason);
#if BENCH_DIAGNOSTICS
    assert(report_count == expected_reports);
    expect_report(report_count-1u, "ERROR", id, calls, (uint32_t)reason);
    for (unsigned i=0; i<report_count; ++i) assert(strcmp(reports[i].event, "DONE"));
#else
    (void)calls; (void)expected_reports;
    assert(report_count == 0u);
#endif
}

bool bench_kernel_prepare(unsigned id, const uint8_t *data, size_t length) {
    assert(!running && length == 2048u);
    assert(data == (id <= 4u ? bench_compression_input : id <= 8u ? bench_crypto_input : bench_dsp_input));
    ++preparations;
    return !(fault == 3u && id == 3u);
}
bool bench_kernel_run(unsigned id) {
    assert(running && id == current_id && !idle_state);
    ++actual[id - 1u];
    return !(fault == 4u && id == 5u && actual[id - 1u] == 7u);
}
bool bench_kernel_verify(unsigned id) {
    assert(!running && id == current_id);
    ++verifications;
    return !(fault == 5u && id == 6u);
}
uint32_t bench_kernel_digest(unsigned id) { assert(!running); return 0xabc00000u + id; }
const char *bench_kernel_name(unsigned id) { (void)id; return "fake"; }

static void reset(unsigned scenario) {
    current_id = rises = falls = preparations = verifications = checks = 0;
    finishes = idle5 = idle1 = final_idle = settle = 0;
    running = idle_state = error_seen = done_seen = false;
    memset(actual, 0, sizeof actual);
    for (unsigned n = 0; n < 12u; ++n) { bench_completed_calls[n] = 0; bench_result_digests[n] = 0; }
    bench_failed_algorithm = 0;
    bench_failure_reason = 0;
    report_count = 0;
    memset(reports, 0, sizeof reports);
    fault = scenario;
}

int main(void) {
    reset(0u); bench_main();
    assert(finishes == 1u && rises == 12u && falls == 12u);
    assert(!error_seen && done_seen && preparations == 12u && verifications == 12u);
    assert(idle5 == 1u && idle1 == 11u && final_idle == 1u && settle == 12u);
    for (unsigned n = 0; n < 12u; ++n) {
        assert(actual[n] == bench_iterations[n]);
        assert(bench_completed_calls[n] == bench_iterations[n]);
        assert(bench_result_digests[n] == 0xabc00001u + n);
    }
#if BENCH_DIAGNOSTICS
    assert(report_count == 26u);
    expect_report(0u, "BOOT", 0u, 0u, 0u);
    for (unsigned id=1u; id<=12u; ++id) {
        expect_report(2u*id-1u, "START", id, bench_iterations[id-1u], 0u);
        expect_report(2u*id, "PASS", id, bench_iterations[id-1u], 0xabc00000u+id);
    }
    expect_report(25u, "DONE", 0u, 0u, 0u);
#else
    assert(report_count == 0u);
#endif
    reset(1u); bench_main();
    assert(finishes == 1u && error_seen && !done_seen && rises == 0u);
    expect_failure(0u, 0u, BENCH_ERROR_PLATFORM_INIT, 1u);
    reset(2u); bench_main();
    assert(error_seen && !done_seen && rises == 0u && preparations == 0u);
    expect_failure(1u, 0u, BENCH_ERROR_PLATFORM_BEFORE_PREPARE, 2u);
    reset(3u); bench_main();
    assert(error_seen && !done_seen && rises == 2u && bench_failed_algorithm == 3u);
    expect_failure(3u, 0u, BENCH_ERROR_KERNEL_PREPARE, 6u);
    reset(4u); bench_main();
    assert(error_seen && !done_seen && rises == 5u && falls == 5u);
    assert(actual[4] == 7u && bench_completed_calls[4] == 6u && actual[5] == 0u);
    expect_failure(5u, 6u, BENCH_ERROR_KERNEL_RUN, 11u);
    reset(5u); bench_main();
    assert(error_seen && !done_seen && rises == 6u && bench_failed_algorithm == 6u);
    assert(actual[6] == 0u && bench_result_digests[5] == 0u);
    expect_failure(6u, bench_iterations[5], BENCH_ERROR_KERNEL_VERIFY, 13u);
    reset(6u); bench_main();
    assert(error_seen && !done_seen && !rises && idle5 == 1u && settle == 1u);
    expect_failure(1u, 0u, BENCH_ERROR_PLATFORM_BEFORE_RUN, 2u);
    reset(7u); bench_main();
    assert(error_seen && !done_seen && rises == 1u && falls == 1u && !verifications);
    expect_failure(1u, bench_iterations[0], BENCH_ERROR_PLATFORM_AFTER_RUN, 3u);
    printf("%s runner diagnostics=%d: fixed counts, marker windows and seven failure paths passed\n",
           BENCH_BOARD_NAME, BENCH_DIAGNOSTICS);
    return 0;
}
