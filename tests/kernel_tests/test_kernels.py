"""Compile the actual common C library and compare all 12 kernels independently.
Run: python tests/kernel_tests/test_kernels.py
No measured board performance is inferred from this host test.
"""
from pathlib import Path
import collections
import ctypes as C
import hashlib
import heapq
import json
import math
import os
import struct
import subprocess
import sys
import zlib
import references as ref

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BUILD=HERE/'build'
BUILD.mkdir(exist_ok=True)
suffix='.dll' if os.name=='nt' else '.so'
library=BUILD/('bench_kernels_host'+suffix)
cmd=['gcc','-std=c11','-O2','-fno-lto','-Wall','-Wextra','-Werror','-shared']
if os.name!='nt': cmd+=['-fPIC']
cmd+=['-I',str(ROOT/'firmware/common/include')]
cmd += [str(p) for p in sorted((ROOT/'firmware/common/kernels').glob('*.c'))]
cmd+=['-o',str(library),'-lm']
subprocess.run(cmd,check=True)
lib=C.CDLL(str(library))
U8=C.c_uint8
lib.bench_kernel_prepare.argtypes=[C.c_uint,C.POINTER(U8),C.c_size_t]
lib.bench_kernel_prepare.restype=C.c_bool
for name in ['run','verify']:
    f=getattr(lib,'bench_kernel_'+name); f.argtypes=[C.c_uint]; f.restype=C.c_bool
lib.bench_kernel_digest.argtypes=[C.c_uint]; lib.bench_kernel_digest.restype=C.c_uint32
lib.bench_kernel_output_bytes.argtypes=[C.POINTER(C.c_size_t)]
lib.bench_kernel_output_bytes.restype=C.POINTER(U8)
lib.bench_kernel_output_floats.argtypes=[C.POINTER(C.c_size_t)]
lib.bench_kernel_output_floats.restype=C.POINTER(C.c_float)
lib.bench_kernel_name.argtypes=[C.c_uint]; lib.bench_kernel_name.restype=C.c_char_p
tests=[]
max_dct_error=0.0
max_fft_error=0.0


def prepare(k,data):
    a=(U8*max(1,len(data)))(*data)
    assert lib.bench_kernel_prepare(k,a,len(data)), (k,len(data),'prepare')


def run(k,data,repeat=2):
    prepare(k,data)
    outputs=[]
    for _ in range(repeat):
        assert lib.bench_kernel_run(k), (k,len(data),'run')
        n=C.c_size_t()
        if k in (9,12):
            p=lib.bench_kernel_output_floats(C.byref(n)); result=list(p[:n.value])
        else:
            p=lib.bench_kernel_output_bytes(C.byref(n)); result=bytes(p[:n.value])
        outputs.append(result)
    assert all(o==outputs[0] for o in outputs), (k,'independent repeated state')
    return outputs[0]


def compare_float(actual,expected,k):
    global max_dct_error,max_fft_error
    assert len(actual)==len(expected)
    error=max(abs(a-b) for a,b in zip(actual,expected))
    for a,b in zip(actual,expected):
        tolerance=(.01 if k==12 else .0001)+.00002*abs(b)
        assert math.isfinite(a) and abs(a-b)<=tolerance,(k,a,b,tolerance)
    if k==12: max_dct_error=max(max_dct_error,error)
    else: max_fft_error=max(max_fft_error,error)


def huffman_optimal_bits(data):
    weights=list(collections.Counter(data).values())
    if len(weights)==1:return len(data)
    heapq.heapify(weights); total=0
    while len(weights)>1:
        combined=heapq.heappop(weights)+heapq.heappop(weights)
        heapq.heappush(weights,combined); total+=combined
    return total


ref.selfcheck()
# Anchor the actual C crypto implementation directly to published vectors too.
def u8(data): return (U8*max(1,len(data)))(*data)
aes_raw=lib.my_aes_encrypt
aes_raw.argtypes=[C.POINTER(U8),C.c_int,C.POINTER(U8),C.POINTER(U8)]
aes_raw.restype=C.c_int
out=(U8*64)()
assert aes_raw(u8(bytes.fromhex('6bc1bee22e409f96e93d7e117393172a')),16,out,
               u8(bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')))==32
assert bytes(out[:16]).hex()=='3ad77bb40d7a3660a89ecaf32466ef97'
tests.append({'kernel':5,'bytes':16,'reference':'NIST AES-128 ECB','result':'pass'})
chacha_raw=lib.my_chacha20_encrypt
chacha_raw.argtypes=[C.POINTER(U8),C.c_int,C.POINTER(U8),C.POINTER(U8),C.POINTER(U8)]
chacha_raw.restype=C.c_int
assert chacha_raw(u8(bytes(64)),64,out,u8(bytes(range(32))),
                  u8(bytes.fromhex('000000090000004a00000000')))==64
assert bytes(out).hex()==('10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e'
                         'd2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e')
tests.append({'kernel':7,'bytes':64,'reference':'RFC 8439 2.3.2','result':'pass'})
comp,crypto,dsp=ref.fixtures()
for name,data in [('compression',comp),('crypto',crypto),('dsp',dsp)]:
    assert (ROOT/'data'/f'{name}.bin').read_bytes()==data, 'Frozen input differs: '+name
compression_cases=[b'',b'A',b'ABCCCCCCCC',bytes([0])*2048,bytes([255])*2048,
    b'A'*254+b'B',b'A'*255+b'B',b'A'*256+b'B',bytes(range(256))*8,
    b'\x00\xff'*1024,ref.xorshift_bytes(0x12345678,2048),comp]
for k in range(1,5):
    for data in compression_cases:
        out=run(k,data)
        assert lib.bench_kernel_verify(k),(k,len(data),'device decoder')
        if k==1: decoded=ref.decode_rle(out)
        elif k==2:
            decoded=bytearray(); value=0
            for v in out: value=(value+v)&255; decoded.append(value)
        elif k==3: decoded=ref.decode_lz77(out)
        else:
            decoded=ref.decode_huffman(out)
            assert struct.unpack_from('<I',out,4)[0]==huffman_optimal_bits(data)
        assert bytes(decoded)==data,(k,len(data),'roundtrip')
        tests.append({'kernel':k,'bytes':len(data),'result':'pass'})

crypto_cases=[b'',b'abc',bytes(range(15)),bytes(range(16)),bytes(range(17)),
              bytes(range(55)),bytes(range(56)),bytes(range(63)),bytes(range(64)),
              bytes(range(65)),crypto]
for k in range(5,9):
    for data in crypto_cases:
        out=run(k,data)
        expected={5:ref.aes_encrypt,6:lambda x:hashlib.sha256(x).digest(),7:ref.chacha20,
                  8:lambda x:struct.pack('<I',zlib.crc32(x))}[k](data)
        assert out==expected,(k,len(data),'independent reference')
        assert bool(lib.bench_kernel_verify(k))==(data==crypto)
        tests.append({'kernel':k,'bytes':len(data),'result':'pass'})

filter_cases=[b'',b'\xff',bytes([40])*64,bytes([255])*2048,
              b'\xff'+bytes(2047),ref.xorshift_bytes(0xBEEF,2048),dsp]
for k in (10,11):
    for data in filter_cases:
        out=run(k,data)
        assert out==(ref.fir(data) if k==10 else ref.iir(data))
        assert lib.bench_kernel_verify(k)
        tests.append({'kernel':k,'bytes':len(data),'result':'pass'})

for k in (9,12):
    cases=[b'\xff',bytes([10])*8,b'\x10'+bytes(7),ref.xorshift_bytes(0x1234,32),dsp]
    if k==12: cases += [bytes(range(7))]
    for data in cases:
        out=run(k,data)
        if k==9:
            if data==dsp:
                period=ref.fft_magnitudes(dsp[:128]); expected=[period[i//16] if i%16==0 else 0 for i in range(2048)]
            else: expected=ref.fft_magnitudes(data)
        else: expected=ref.dct_ortho(data)
        compare_float(out,expected,k)
        assert bool(lib.bench_kernel_verify(k))==(data==dsp)
        tests.append({'kernel':k,'bytes':len(data),'result':'pass'})

# State/error contracts and actual corruption rejection, not only happy paths.
a=(U8*2049)()
assert not lib.bench_kernel_prepare(0,a,1)
assert not lib.bench_kernel_prepare(13,a,1)
assert not lib.bench_kernel_prepare(1,a,2049)
assert not lib.bench_kernel_prepare(1,None,1)
assert not lib.bench_kernel_prepare(9,a,0)
assert not lib.bench_kernel_prepare(9,a,3)
assert not lib.bench_kernel_prepare(12,a,0)
assert not lib.bench_kernel_run(1)
assert not lib.bench_kernel_verify(1)
for k in range(1,13):
    data=comp if k<=4 else crypto if k<=8 else dsp
    run(k,data,1)
    assert lib.bench_kernel_verify(k)
    n=C.c_size_t()
    if k in (9,12):
        p=lib.bench_kernel_output_floats(C.byref(n)); p[0]=float('nan')
    else:
        p=lib.bench_kernel_output_bytes(C.byref(n)); p[n.value-1]^=1
    assert not lib.bench_kernel_verify(k),(k,'corrupt output accepted')
    assert lib.bench_kernel_run(k) and lib.bench_kernel_verify(k)
    assert lib.bench_kernel_digest(k)==zlib.crc32(
        bytes(lib.bench_kernel_output_bytes(C.byref(n))[:n.value]) if k not in (9,12)
        else struct.pack('<%df'%2048,*lib.bench_kernel_output_floats(C.byref(n))[:n.value]))

summary={'checks':len(tests),'all_12_kernels_passed':True,'repeat_reset_checked':True,
    'corruption_rejected_for_all_12':True,'max_fft_absolute_error':max_fft_error,
    'max_dct_absolute_error':max_dct_error,'command':cmd,'cases':tests}
(HERE/'results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='cases'},indent=2))
