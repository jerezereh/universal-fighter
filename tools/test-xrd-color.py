"""Authored packed color cube and native scalar framing; no game assets."""
import struct
import numpy as np
from xrd_color import apply_lut, inline_constants, observed_power

words=[0xffff0300,0x05000051,0xa00f0007,*struct.unpack('<4I',struct.pack('<4f',1,.5,1,1)),0xffff]
code=struct.pack('<'+'I'*len(words),*words)
assembly='mul r2.xyz, r4, c7.y\nexp_sat_pp r1.z, r2.x\nexp_sat_pp r1.w, r2.y\nexp_sat_pp r1.xy, r2.z\n'
assert inline_constants(code)[7][1]==.5 and observed_power(assembly,code)==.5
for data in [code[:-1],code+bytes(4),code[:4]+bytes(4),struct.pack('<I',0xfffe0300)+code[4:]]:
    try: inline_constants(data)
    except ValueError: continue
    raise AssertionError('invalid native scalar program accepted')
for text in ['',assembly+assembly,assembly.replace('c7.y','c8.y')]:
    try: observed_power(text,code)
    except ValueError: continue
    raise AssertionError('ambiguous/missing native power accepted')

edge=4;lut=np.zeros((edge,edge*edge,4),dtype='u1')
for g in range(edge):
    for b in range(edge):
        for r in range(edge): lut[g,b*edge+r]=[b*85,g*85,r*85,255]
body=np.array([[[64,25,100,255],[8,9,10,0],[0,0,0,7],[255,255,255,255]]],dtype='u1')
identity=apply_lut(body,lut,1)
assert np.array_equal(identity[0,0],body[0,0]) and np.array_equal(identity[0,1],[0,0,0,0])
assert np.array_equal(identity[:,:,3],body[:,:,3])
powered=apply_lut(body,lut,.5)
assert abs(int(powered[0,0,0])-128)<=1 and np.array_equal(powered[0,3],[255,255,255,255])
lift=lut.copy();lift[0,0]=[5,4,3,255]
assert np.array_equal(apply_lut(body,lift,1)[0,2],[5,4,3,7])
for image,cube,power in [(body.astype('float32'),lut,1),(body,lut[:,:3],1),
        (body,lut,float('nan')),(body,lut,0),(body[:,:,:3],lut,1)]:
    try: apply_lut(image,cube,power)
    except ValueError: continue
    raise AssertionError('invalid color cube/image/power accepted')
print('Native scalar framing, packed LUT axes/interpolation, black coverage, unchanged alpha and invalid input checks passed.')
