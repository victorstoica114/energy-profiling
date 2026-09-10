#include "bench_kernels.h"
#include "bench_golden.h"
#include <math.h>
#include <string.h>

/* Original-library entry points, deliberately kept in a separate C unit. */
int my_rle_encode(const uint8_t *,int,uint8_t *);
int my_delta_encode(const uint8_t *,int,uint8_t *);
int my_lz77_encode(const uint8_t *,int,uint8_t *);
int my_huffman_encode(const uint8_t *,int,uint8_t *);
int my_aes_encrypt(const uint8_t *,int,uint8_t *,const uint8_t *);
int my_sha256_hash(const uint8_t *,int,uint8_t *);
int my_chacha20_encrypt(const uint8_t *,int,uint8_t *,const uint8_t *,const uint8_t *);
int my_crc32(const uint8_t *,int,uint32_t *);
int my_fft(const uint8_t *,int,float *);
int my_fir_filter(const uint8_t *,int,uint8_t *,const uint8_t *,int);
int my_iir_filter(const uint8_t *,int,uint8_t *,const uint8_t *,int,const uint8_t *,int);
int my_dct(const uint8_t *,int,float *);

#define OUT_CAPACITY (3u*BENCH_MAX_INPUT_BYTES+264u)
#define GUARD 0x83A76D21u
static uint8_t input_data[BENCH_MAX_INPUT_BYTES];
static struct { uint32_t pre; uint8_t data[OUT_CAPACITY]; uint32_t post; } byte_out;
static struct { uint32_t pre; float data[BENCH_MAX_INPUT_BYTES]; uint32_t post; } float_out;
static uint8_t decoded[BENCH_MAX_INPUT_BYTES];
static unsigned active_id;
static size_t input_len, output_len;
static bool last_success, golden_crypto, golden_dsp;
static const uint8_t aes_key[16] = "0123456789abcdef";
static const uint8_t chacha_key[32] = "0123456789abcdef0123456789abcdef";
static const uint8_t chacha_nonce[12] = {0};

static void store32(uint8_t *p,uint32_t x) {
    for (unsigned j=0;j<4;++j) p[j]=(uint8_t)(x>>(8*j));
}
static uint32_t load32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static bool guards_ok(void) {
    return byte_out.pre==GUARD && byte_out.post==GUARD &&
           float_out.pre==GUARD && float_out.post==GUARD;
}
static bool crypto_fixture(void) {
    if (input_len!=2048) return false;
    uint32_t x=0x1A2B3C4Du;
    for (size_t i=0;i<input_len;++i) {
        x^=x<<13; x^=x>>17; x^=x<<5;
        if (input_data[i]!=(uint8_t)x) return false;
    }
    return true;
}
static bool dsp_fixture(void) {
    if (input_len!=2048) return false;
    for (size_t i=0;i<input_len;++i)
        if (input_data[i]!=golden_dsp_period[i%128]) return false;
    return true;
}

bool bench_kernel_prepare(unsigned id,const uint8_t *input,size_t len) {
    active_id=0; last_success=false; input_len=output_len=0;
    if (id<1 || id>BENCH_KERNEL_COUNT || len>BENCH_MAX_INPUT_BYTES || (!input && len)) return false;
    if ((id==BENCH_FFT && (!len || (len&(len-1)))) || (id==BENCH_DCT && !len)) return false;
    if (len) memcpy(input_data,input,len);
    input_len=len;
    byte_out.pre=byte_out.post=float_out.pre=float_out.post=GUARD;
    golden_crypto=crypto_fixture(); golden_dsp=dsp_fixture();
    active_id=id;
    return true;
}

#if defined(__GNUC__)
__attribute__((noinline))
#endif
bool bench_kernel_run(unsigned id) {
    last_success=false;
    if (id!=active_id || !active_id || !guards_ok()) return false;
    int result=-1;
    output_len=0;
    switch (id) {
    case BENCH_RLE: result=my_rle_encode(input_data,(int)input_len,byte_out.data); break;
    case BENCH_DELTA: result=my_delta_encode(input_data,(int)input_len,byte_out.data); break;
    case BENCH_LZ77:
        store32(byte_out.data,(uint32_t)input_len);
        result=my_lz77_encode(input_data,(int)input_len,byte_out.data+4);
        if (result>=0) result+=4;
        break;
    case BENCH_HUFFMAN: result=my_huffman_encode(input_data,(int)input_len,byte_out.data); break;
    case BENCH_AES128: result=my_aes_encrypt(input_data,(int)input_len,byte_out.data,aes_key); break;
    case BENCH_SHA256: result=my_sha256_hash(input_data,(int)input_len,byte_out.data); break;
    case BENCH_CHACHA20:
        result=my_chacha20_encrypt(input_data,(int)input_len,byte_out.data,chacha_key,chacha_nonce); break;
    case BENCH_CRC32: {
        uint32_t crc=0;
        if (my_crc32(input_data,(int)input_len,&crc)==0) {
            store32(byte_out.data,crc); result=4;
        }
        break;
    }
    case BENCH_FFT:
        if (my_fft(input_data,(int)input_len,float_out.data)==0) result=(int)(input_len*sizeof(float));
        break;
    case BENCH_FIR: {
        const uint8_t taps[5]={1,2,3,2,1};
        if (my_fir_filter(input_data,(int)input_len,byte_out.data,taps,5)==0) result=(int)input_len;
        break;
    }
    case BENCH_IIR: {
        /* Q((x[n]+2x[n-1]+x[n-2]+y[n-1]+y[n-2])/4).
         * Q truncates/clips to uint8; startup state is zero per function call.
         * Linear core denominator [1,-.25,-.25], not [1,1,1]. */
        const uint8_t b[3]={1,2,1}, feedback[3]={1,1,1};
        if (my_iir_filter(input_data,(int)input_len,byte_out.data,b,3,feedback,3)==0) result=(int)input_len;
        break;
    }
    case BENCH_DCT:
        if (my_dct(input_data,(int)input_len,float_out.data)==0) result=(int)(input_len*sizeof(float));
        break;
    default: return false;
    }
    if (result<0 || !guards_ok()) return false;
    output_len=(size_t)result;
    if (id!=BENCH_FFT && id!=BENCH_DCT && output_len>OUT_CAPACITY) return false;
    last_success=true;
    return true;
}

static bool verify_rle(void) {
    if (output_len%2) return false;
    size_t pos=0;
    for (size_t i=0;i<output_len;i+=2) {
        unsigned count=byte_out.data[i];
        if (!count || count>input_len-pos) return false;
        while (count--) if (input_data[pos++]!=byte_out.data[i+1]) return false;
    }
    return pos==input_len;
}
static bool verify_lz77(void) {
    if (output_len<4 || load32(byte_out.data)!=input_len) return false;
    size_t src=4,dst=0;
    while (dst<input_len) {
        if (output_len-src<2) return false;
        unsigned distance=byte_out.data[src++],len=byte_out.data[src++];
        if ((len && (!distance || distance>dst)) || len>input_len-dst) return false;
        for (unsigned j=0;j<len;++j) { decoded[dst]=decoded[dst-distance]; ++dst; }
        if (dst<input_len) {
            if (src>=output_len) return false;
            decoded[dst++]=byte_out.data[src++];
        }
    }
    return src==output_len && !memcmp(decoded,input_data,input_len);
}
static bool verify_huffman(void) {
    if (output_len<264 || load32(byte_out.data)!=input_len) return false;
    uint32_t bits=load32(byte_out.data+4);
    if ((size_t)((bits+7u)/8u)+264u!=output_len || bits>32u*input_len) return false;
    uint32_t counts[33]={0},first[33]={0},offset[33]={0};
    uint8_t symbols[256];
    const uint8_t *lengths=byte_out.data+8;
    unsigned used=0;
    for (unsigned s=0;s<256;++s) {
        if (lengths[s]>32) return false;
        if (lengths[s]) { ++counts[lengths[s]]; ++used; }
    }
    if (!input_len) return !bits && !used;
    if (!used) return false;
    uint64_t code=0;
    unsigned cursor=0;
    for (unsigned len=1;len<=32;++len) {
        code=(code+counts[len-1])*2u;
        if (code+counts[len]>(UINT64_C(1)<<len)) return false;
        first[len]=(uint32_t)code; offset[len]=cursor;
        for (unsigned s=0;s<256;++s) if (lengths[s]==len) symbols[cursor++]=(uint8_t)s;
    }
    uint32_t accum=0;
    unsigned len=0;
    size_t dst=0;
    for (uint32_t bit=0;bit<bits;++bit) {
        accum=(accum<<1)|((byte_out.data[264+bit/8]>>(7-bit%8))&1u);
        if (++len>32) return false;
        if (counts[len] && accum>=first[len] && accum-first[len]<counts[len]) {
            if (dst>=input_len || symbols[offset[len]+accum-first[len]]!=input_data[dst++]) return false;
            accum=0; len=0;
        }
    }
    if (bits%8 && (byte_out.data[output_len-1]&((1u<<(8u-bits%8u))-1u))) return false;
    return dst==input_len && len==0;
}
static bool verify_filter(bool feedback) {
    if (output_len!=input_len) return false;
    static const unsigned taps[5]={1,2,3,2,1};
    for (size_t n=0;n<input_len;++n) {
        unsigned value=0;
        if (!feedback) {
            for (size_t k=0;k<5 && k<=n;++k) value+=input_data[n-k]*taps[k];
            value/=9;
        } else {
            value=input_data[n];
            if (n>=1) value+=2u*input_data[n-1]+decoded[n-1];
            if (n>=2) value+=input_data[n-2]+decoded[n-2];
            value/=4;
            if (value>255) value=255;
        }
        decoded[n]=(uint8_t)value;
    }
    return !memcmp(decoded,byte_out.data,input_len);
}
static bool verify_transform(unsigned id) {
    if (!golden_dsp || output_len!=input_len*sizeof(float)) return false;
    for (size_t i=0;i<input_len;++i) {
        float ref=id==BENCH_DCT ? golden_dct[i] : (i%16 ? 0.0f : golden_fft_period[i/16]);
        float actual=float_out.data[i];
        /* Absolute bounds include accumulated single-precision rounding.
         * Golden references use double precision, independent direct formulas. */
        float tolerance=id==BENCH_DCT ? 0.01f+0.00002f*fabsf(ref) : 0.0001f+0.00002f*fabsf(ref);
        if (!isfinite(actual) || fabsf(actual-ref)>tolerance) return false;
    }
    return true;
}
bool bench_kernel_verify(unsigned id) {
    if (id!=active_id || !last_success || !guards_ok()) return false;
    switch (id) {
    case BENCH_RLE: return verify_rle();
    case BENCH_DELTA: {
        if (output_len!=input_len) return false;
        uint8_t value=0;
        for (size_t i=0;i<input_len;++i) { value=(uint8_t)(value+byte_out.data[i]); if (value!=input_data[i]) return false; }
        return true;
    }
    case BENCH_LZ77: return verify_lz77();
    case BENCH_HUFFMAN: return verify_huffman();
    case BENCH_AES128: return golden_crypto && output_len==sizeof(golden_aes) && !memcmp(byte_out.data,golden_aes,sizeof(golden_aes));
    case BENCH_SHA256: return golden_crypto && output_len==32 && !memcmp(byte_out.data,golden_sha256,32);
    case BENCH_CHACHA20: return golden_crypto && output_len==sizeof(golden_chacha20) && !memcmp(byte_out.data,golden_chacha20,sizeof(golden_chacha20));
    case BENCH_CRC32: return golden_crypto && output_len==4 && !memcmp(byte_out.data,golden_crc32,4);
    case BENCH_FFT: case BENCH_DCT: return verify_transform(id);
    case BENCH_FIR: return verify_filter(false);
    case BENCH_IIR: return verify_filter(true);
    default: return false;
    }
}

const uint8_t *bench_kernel_output_bytes(size_t *length) {
    bool valid=last_success && active_id!=BENCH_FFT && active_id!=BENCH_DCT;
    if (length) *length=valid ? output_len : 0;
    return valid ? byte_out.data : NULL;
}
const float *bench_kernel_output_floats(size_t *count) {
    bool valid=last_success && (active_id==BENCH_FFT || active_id==BENCH_DCT);
    if (count) *count=valid ? input_len : 0;
    return valid ? float_out.data : NULL;
}
size_t bench_kernel_input_length(void) { return input_len; }
uint32_t bench_kernel_digest(unsigned id) {
    if (id!=active_id || !last_success || !guards_ok()) return 0;
    const uint8_t *p=(id==BENCH_FFT || id==BENCH_DCT) ? (const uint8_t *)float_out.data : byte_out.data;
    uint32_t crc=0xffffffffu;
    for (size_t i=0;i<output_len;++i) {
        crc^=p[i];
        for (unsigned j=0;j<8;++j) crc=(crc>>1)^((crc&1u) ? 0xedb88320u : 0u);
    }
    return ~crc;
}
const char *bench_kernel_name(unsigned id) {
    static const char *const names[]={"INVALID","RLE","Delta","LZ77","Huffman","AES-128","SHA-256","ChaCha20","CRC32","FFT","FIR","IIR","DCT"};
    return id<=BENCH_KERNEL_COUNT ? names[id] : names[0];
}
