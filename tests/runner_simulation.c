/* Exercise the real runner with fake kernels and the observable single GPIO. */
#include "bench_platform.h"
#include "bench_kernels.h"
#include "bench_config.h"
#include "bench_data.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

extern volatile uint32_t bench_completed_calls[12];
extern volatile uint32_t bench_result_digests[12];
extern volatile unsigned bench_failed_algorithm;
extern volatile uint32_t bench_failure_reason;

static unsigned prepared_id, rises, falls, preparations, verifications, checks;
static unsigned finishes, idle5, idle1, final_idle, fault;
static uint32_t actual[12];
static bool marker_high, failure_latched;
struct diagnostic_event { const char *event; unsigned id, calls; uint32_t digest; };
static struct diagnostic_event reports[32];
static unsigned report_count;

bool bench_platform_init(void) { return fault != 1u; }
bool bench_platform_check(void) {
    ++checks;
    return !((fault == 2u && checks == 1u) ||
             (fault == 6u && checks == 2u) ||
             (fault == 7u && checks == 3u) ||
             (fault == 9u && checks == 36u));
}
void bench_platform_marker(bool high) {
    if (bench_failure_reason) {
        assert(high); /* No failure is allowed to create a valid falling edge. */
        failure_latched = true;
    }
    if (failure_latched) assert(high);
    if (high && !marker_high) ++rises;
    if (!high && marker_high) { assert(!failure_latched); ++falls; }
    marker_high = high;
}
void bench_platform_wait_ms(uint32_t ms) {
    assert(!marker_high && !failure_latched);
    if (ms == 5000u) {
        assert(prepared_id == 1u && checks == 2u && !rises);
        ++idle5;
    } else if (ms == 1000u) {
        assert(prepared_id >= 2u && checks == (prepared_id - 1u) * 3u + 2u);
        assert(falls == prepared_id - 1u);
        ++idle1;
    } else if (ms == 2000u) {
        assert(verifications == 12u && falls == 12u);
        ++final_idle;
    } else assert(!"Unexpected delay: the single GPIO has no ID-settle interval");
#if BENCH_DIAGNOSTICS
    if (ms != 2000u) assert(!strcmp(reports[report_count-1u].event, "START"));
#endif
}
void bench_platform_finish(void) {
    assert(marker_high == failure_latched);
    assert(failure_latched || final_idle == 1u);
    ++finishes;
}

#if BENCH_DIAGNOSTICS
void bench_platform_report(const char *event, unsigned id, unsigned calls, uint32_t digest) {
    assert(report_count < 32u);
    if (!strcmp(event, "ERROR")) {
        assert(marker_high && failure_latched && id == bench_failed_algorithm);
        assert(digest == bench_failure_reason);
        assert(calls == (id ? bench_completed_calls[id-1u] : 0u));
    } else {
        assert(!marker_high && !failure_latched);
        if (!strcmp(event, "BOOT")) {
            assert(!rises && !preparations && !id && !calls && !digest);
        } else if (!strcmp(event, "START")) {
            assert(id == prepared_id && !actual[id-1u]);
            assert(calls == bench_iterations[id-1u] && !digest);
        } else if (!strcmp(event, "PASS")) {
            assert(id == verifications && calls == bench_completed_calls[id-1u]);
            assert(digest == bench_result_digests[id-1u] && digest == 0xabc00000u + id);
        } else if (!strcmp(event, "DONE")) {
            assert(final_idle == 1u && !id && !calls && !digest);
        } else assert(!"Unexpected diagnostic event");
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
    assert(finishes == 1u && marker_high && failure_latched && !final_idle);
    assert(rises == falls + 1u);
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
    assert(!marker_high && length == 2048u && id == preparations + 1u);
    assert(data == (id <= 4u ? bench_compression_input : id <= 8u ? bench_crypto_input : bench_dsp_input));
    prepared_id = id;
    ++preparations;
    return !(fault == 3u && id == 3u);
}
bool bench_kernel_run(unsigned id) {
    assert(marker_high && !failure_latched && id == prepared_id);
    ++actual[id - 1u];
    return !((fault == 4u && id == 5u && actual[id - 1u] == 7u) ||
             (fault == 10u && id == 12u));
}
bool bench_kernel_verify(unsigned id) {
    assert(!marker_high && id == prepared_id && actual[id-1u] == bench_iterations[id-1u]);
    ++verifications;
    return !((fault == 5u && id == 6u) || (fault == 8u && id == 12u));
}
uint32_t bench_kernel_digest(unsigned id) { assert(!marker_high); return 0xabc00000u + id; }
const char *bench_kernel_name(unsigned id) { (void)id; return "fake"; }

static void reset(unsigned scenario) {
    prepared_id = rises = falls = preparations = verifications = checks = 0;
    finishes = idle5 = idle1 = final_idle = 0;
    marker_high = failure_latched = false;
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
    assert(finishes == 1u && rises == 12u && falls == 12u && !marker_high);
    assert(!failure_latched && preparations == 12u && verifications == 12u && checks == 36u);
    assert(idle5 == 1u && idle1 == 11u && final_idle == 1u);
    for (unsigned n = 0; n < 12u; ++n) {
        assert(actual[n] == bench_iterations[n]);
        assert(bench_completed_calls[n] == bench_iterations[n]);
        assert(bench_result_digests[n] == 0xabc00001u+n);
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
    assert(falls == 0u);
    expect_failure(0u, 0u, BENCH_ERROR_PLATFORM_INIT, 1u);
    reset(2u); bench_main();
    assert(falls == 0u && preparations == 0u);
    expect_failure(1u, 0u, BENCH_ERROR_PLATFORM_BEFORE_PREPARE, 2u);
    reset(3u); bench_main();
    assert(falls == 2u && actual[2] == 0u);
    expect_failure(3u, 0u, BENCH_ERROR_KERNEL_PREPARE, 6u);
    reset(4u); bench_main();
    assert(rises == 5u && falls == 4u);
    assert(actual[4] == 7u && bench_completed_calls[4] == 6u && actual[5] == 0u);
    expect_failure(5u, 6u, BENCH_ERROR_KERNEL_RUN, 11u);
    reset(5u); bench_main();
    assert(falls == 6u && actual[6] == 0u && bench_result_digests[5] == 0u);
    expect_failure(6u, bench_iterations[5], BENCH_ERROR_KERNEL_VERIFY, 13u);
    reset(6u); bench_main();
    assert(!falls && !idle5);
    expect_failure(1u, 0u, BENCH_ERROR_PLATFORM_BEFORE_RUN, 2u);
    reset(7u); bench_main();
    assert(falls == 1u && !verifications);
    expect_failure(1u, bench_iterations[0], BENCH_ERROR_PLATFORM_AFTER_RUN, 3u);
    reset(8u); bench_main();
    assert(rises == 13u && falls == 12u && !bench_result_digests[11]);
    expect_failure(12u, bench_iterations[11], BENCH_ERROR_KERNEL_VERIFY, 25u);
    reset(9u); bench_main();
    assert(rises == 13u && falls == 12u && verifications == 11u);
    expect_failure(12u, bench_iterations[11], BENCH_ERROR_PLATFORM_AFTER_RUN, 25u);
    reset(10u); bench_main();
    assert(rises == 12u && falls == 11u && !bench_completed_calls[11]);
    expect_failure(12u, 0u, BENCH_ERROR_KERNEL_RUN, 25u);
    printf("%s runner diagnostics=%d: twelve ordered gates, fixed counts and ten fault scenarios passed\n",
           BENCH_BOARD_NAME, BENCH_DIAGNOSTICS);
    return 0;
}
