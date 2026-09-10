"""Independent standard-library references; never used in measured firmware.

AES S-box is derived algebraically, and MixColumns uses the general GF matrix.
FFT verification uses a direct DFT; DCT uses a direct double-precision formula.
"""
import cmath
import hashlib
import math
import struct
import zlib


def xorshift_bytes(seed, n):
    out = bytearray()
    for _ in range(n):
        seed ^= (seed << 13) & 0xffffffff
        seed ^= seed >> 17
        seed ^= (seed << 5) & 0xffffffff
        seed &= 0xffffffff
        out.append(seed & 255)
    return bytes(out)


def fixtures():
    motif = bytes.fromhex('00 00 01 01 02 02 03 03 10 20 30 40 AA 55 AA 55')
    block = bytes(32) + bytes([255]*32) + bytes(range(64)) + motif*8
    dsp_period = bytes(math.floor(128 + 100*math.sin(2*math.pi*n/128) + .5) for n in range(128))
    return block*8, xorshift_bytes(0x1A2B3C4D, 2048), dsp_period*16


def gmul(a,b):
    result=0
    for _ in range(8):
        if b & 1: result ^= a
        a = ((a<<1) ^ (0x11b if a & 128 else 0)) & 255
        b >>= 1
    return result


def gpow(a,p):
    r=1
    while p:
        if p&1: r=gmul(r,a)
        a=gmul(a,a)
        p>>=1
    return r


def aes_sbox(a):
    a=gpow(a,254) if a else 0
    return a ^ ((a<<1)|(a>>7))&255 ^ ((a<<2)|(a>>6))&255 ^ ((a<<3)|(a>>5))&255 ^ ((a<<4)|(a>>4))&255 ^ 0x63


SBOX=tuple(aes_sbox(i) for i in range(256))


def aes_encrypt(data, key=b'0123456789abcdef'):
    schedule=list(key)
    rc=1
    while len(schedule)<176:
        word=schedule[-4:]
        if len(schedule)%16==0:
            word=[SBOX[v] for v in word[1:]+word[:1]]
            word[0] ^= rc
            rc=gmul(rc,2)
        for v in word: schedule.append(schedule[-16]^v)
    pad=16-len(data)%16
    data=data+bytes([pad])*pad
    encrypted=bytearray()
    matrix=((2,3,1,1),(1,2,3,1),(1,1,2,3),(3,1,1,2))
    for start in range(0,len(data),16):
        state=[data[start+i]^schedule[i] for i in range(16)]
        for rnd in range(1,11):
            state=[SBOX[v] for v in state]
            state=[state[4*((column+row)%4)+row] for column in range(4) for row in range(4)]
            if rnd!=10:
                state=[gmul(matrix[row][0],state[4*column]) ^
                       gmul(matrix[row][1],state[4*column+1]) ^
                       gmul(matrix[row][2],state[4*column+2]) ^
                       gmul(matrix[row][3],state[4*column+3])
                       for column in range(4) for row in range(4)]
            state=[v^schedule[16*rnd+i] for i,v in enumerate(state)]
        encrypted.extend(state)
    return bytes(encrypted)


def chacha20(data, key=b'0123456789abcdef0123456789abcdef', nonce=bytes(12)):
    state=list(struct.unpack('<4I',b'expand 32-byte k')+struct.unpack('<8I',key)+(1,)+struct.unpack('<3I',nonce))
    out=bytearray()
    def rotate(a,n): return ((a<<n)|(a>>(32-n)))&0xffffffff
    def quarter(s,a,b,c,d):
        s[a]=(s[a]+s[b])&0xffffffff; s[d]=rotate(s[d]^s[a],16)
        s[c]=(s[c]+s[d])&0xffffffff; s[b]=rotate(s[b]^s[c],12)
        s[a]=(s[a]+s[b])&0xffffffff; s[d]=rotate(s[d]^s[a],8)
        s[c]=(s[c]+s[d])&0xffffffff; s[b]=rotate(s[b]^s[c],7)
    for start in range(0,len(data),64):
        working=state.copy()
        for _ in range(10):
            for args in ((0,4,8,12),(1,5,9,13),(2,6,10,14),(3,7,11,15),
                         (0,5,10,15),(1,6,11,12),(2,7,8,13),(3,4,9,14)):
                quarter(working,*args)
        stream=struct.pack('<16I',*((a+b)&0xffffffff for a,b in zip(working,state)))
        out.extend(a^b for a,b in zip(data[start:start+64],stream))
        state[12]=(state[12]+1)&0xffffffff
    return bytes(out)


def fft_magnitudes(data):
    n=len(data)
    return [abs(sum(v*cmath.exp(-2j*math.pi*k*i/n) for i,v in enumerate(data)))/n for k in range(n)]


def dct_ortho(data):
    n=len(data)
    return [(math.sqrt(1/n) if k==0 else math.sqrt(2/n)) *
            math.fsum(v*math.cos(math.pi*k*(2*i+1)/(2*n)) for i,v in enumerate(data))
            for k in range(n)]


def fir(data):
    return bytes(sum(data[n-k]*c for k,c in enumerate((1,2,3,2,1)) if n>=k)//9 for n in range(len(data)))


def iir(data):
    out=[]
    for n,v in enumerate(data):
        s=v
        if n>=1: s+=2*data[n-1]+out[n-1]
        if n>=2: s+=data[n-2]+out[n-2]
        out.append(min(255,s//4))
    return bytes(out)


def decode_rle(data):
    if len(data)%2: raise ValueError('odd RLE frame')
    return b''.join(bytes([data[i+1]])*data[i] for i in range(0,len(data),2))


def decode_lz77(data):
    n=struct.unpack_from('<I',data)[0]
    pos=4
    out=bytearray()
    while len(out)<n:
        distance,length=data[pos:pos+2]; pos+=2
        if length and not 0<distance<=len(out): raise ValueError('invalid match')
        for _ in range(length): out.append(out[-distance])
        if len(out)>n: raise ValueError('match overrun')
        if len(out)<n:
            out.append(data[pos]); pos+=1
    if pos!=len(data): raise ValueError('unused data')
    return bytes(out)


def decode_huffman(data):
    n,bits=struct.unpack_from('<II',data)
    lengths=data[8:264]
    ordered=sorted((size,symbol) for symbol,size in enumerate(lengths) if size)
    code=0; prev=0; table={}
    for size,symbol in ordered:
        code<<=size-prev
        if code >= 1<<size: raise ValueError('overfull codebook')
        table[size,code]=symbol
        code+=1; prev=size
    out=bytearray(); code=0; size=0
    for bit in range(bits):
        code=(code<<1)|((data[264+bit//8]>>(7-bit%8))&1); size+=1
        if (size,code) in table:
            out.append(table[size,code]); code=0; size=0
    if len(out)!=n or size or len(data)!=264+(bits+7)//8: raise ValueError('invalid length')
    return bytes(out)


def selfcheck():
    assert aes_encrypt(bytes.fromhex('6bc1bee22e409f96e93d7e117393172a'),
                       bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c'))[:16].hex()=='3ad77bb40d7a3660a89ecaf32466ef97'
    assert chacha20(bytes(64),bytes(range(32)),bytes.fromhex('000000090000004a00000000')).hex()==(
        '10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e'
        'd2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e')
    assert zlib.crc32(b'123456789')==0xcbf43926


if __name__=='__main__': selfcheck()
