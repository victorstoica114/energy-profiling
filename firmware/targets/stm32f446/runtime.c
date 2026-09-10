#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>
#include "bench_platform.h"

extern unsigned char _end, __heap_limit;
/* Newlib constructor hooks; no board or I/O initialization is hidden here. */
void _init(void) {}
void _fini(void) {}

void *_sbrk(ptrdiff_t increment)
{
    static unsigned char *position;
    if (!position) position = &_end;
    if (increment < 0 || (uintptr_t)increment > (uintptr_t)&__heap_limit - (uintptr_t)position) {
        errno = ENOMEM; return (void *)-1;
    }
    void *previous = position;
    position += increment;
    return previous;
}

void _exit(int status)
{
    (void)status;
    bench_platform_signals(0, false, false, true, false);
    bench_platform_finish();
    for (;;) {}
}
