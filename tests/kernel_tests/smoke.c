#include "bench_kernels.h"
#include "bench_data.h"
#include <stdio.h>

/* Integration with the exact linked benchmark dataset, not local test copies. */
int main(void) {
    for (unsigned id=1;id<=BENCH_KERNEL_COUNT;++id) {
        const uint8_t *input=id<=4 ? bench_compression_input : id<=8 ? bench_crypto_input : bench_dsp_input;
        if (!bench_kernel_prepare(id,input,BENCH_MAX_INPUT_BYTES)) return 10+(int)id;
        uint32_t first=0;
        for (unsigned repetition=0;repetition<2;++repetition) {
            if (!bench_kernel_run(id) || !bench_kernel_verify(id)) {
                fprintf(stderr,"Kernel %u %s failed verification\n",id,bench_kernel_name(id));
                return 30+(int)id;
            }
            uint32_t digest=bench_kernel_digest(id);
            if (!repetition) first=digest;
            else if (digest!=first) return 50+(int)id;
        }
        printf("%2u %-9s PASS %08lx\n",id,bench_kernel_name(id),(unsigned long)first);
    }
    return 0;
}
