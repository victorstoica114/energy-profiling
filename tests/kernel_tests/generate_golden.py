"""Offline generation of independent expected outputs for the frozen fixtures."""
from pathlib import Path
import hashlib
import json
import struct
import zlib
import references as ref

ROOT=Path(__file__).resolve().parents[2]
ref.selfcheck()
compression,crypto,dsp=ref.fixtures()
for name,data in [('compression',compression),('crypto',crypto),('dsp',dsp)]:
    assert (ROOT/'data'/f'{name}.bin').read_bytes()==data, 'Frozen input differs: '+name
arrays={
    'golden_aes':ref.aes_encrypt(crypto),
    'golden_sha256':hashlib.sha256(crypto).digest(),
    'golden_chacha20':ref.chacha20(crypto),
    'golden_crc32':struct.pack('<I',zlib.crc32(crypto)),
    'golden_dsp_period':dsp[:128],
    'golden_fft_period':ref.fft_magnitudes(dsp[:128]),
    'golden_dct':ref.dct_ortho(dsp),
}
text=['/* Generated offline by tests/kernel_tests/generate_golden.py. */',
      '#ifndef BENCH_GOLDEN_H','#define BENCH_GOLDEN_H','#include <stdint.h>']
for name,values in arrays.items():
    is_float=not isinstance(values,bytes)
    text.append('static const %s %s[%d] = {' % ('float' if is_float else 'uint8_t',name,len(values)))
    tokens=[]
    for value in values:
        if is_float:
            literal=format(value,'.9g')
            if '.' not in literal and 'e' not in literal: literal+='.0'
            tokens.append(literal+'f')
        else: tokens.append(f'0x{value:02x}')
    for i in range(0,len(tokens),8): text.append('    '+', '.join(tokens[i:i+8])+',')
    text.append('};')
text.append('#endif')
(ROOT/'firmware/common/kernels/bench_golden.h').write_text('\n'.join(text)+'\n',encoding='utf-8')
manifest={
    'method':'Independent Python standard-library references; direct DFT and orthonormal DCT, AES algebraic S-box, explicit ChaCha rounds, hashlib/zlib',
    'inputs':{name:hashlib.sha256(data).hexdigest() for name,data in [('compression',compression),('crypto',crypto),('dsp',dsp)]},
    'output_hashes':{name:hashlib.sha256(values).hexdigest() for name,values in arrays.items() if isinstance(values,bytes)},
    'references':[
        'https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Standards-and-Guidelines/documents/examples/AES_Core128.pdf',
        'https://www.rfc-editor.org/rfc/rfc8439#section-2.3.2',
        'https://docs.scipy.org/doc/scipy/reference/generated/scipy.fft.dct.html']}
(ROOT/'tests/kernel_tests/golden_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,indent=2))
