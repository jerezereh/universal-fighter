"""Authored vertex observation bounds and held-register comparisons, never source code."""
import struct
from xrd_transform import transform_packet,transform_changes,projection_bindings

meta=dict(bytecode_size=8,constants=256,read_only=True,assembly='vs_3_0',counter=10,request_index=0,
    presentation_index=3,viewport_hex=struct.pack('<4I2f',0,0,2,2,0,1).hex())
packet=struct.pack('<2I',0xfffe0300,0xffff)+bytes(4096)
code,constants,analysis=transform_packet(meta,packet)
assert len(constants)==4096 and analysis['viewport']==[0,0,2,2,0,1]
for changed,data in ((dict(bytecode_size=4),packet),(dict(constants=255),packet),
        (dict(read_only=False),packet),(dict(request_index=-1),packet),(dict(viewport_hex='no'),packet),
        (dict(viewport_hex=struct.pack('<4I2f',0,0,0,2,0,1).hex()),packet),({},packet[:-1]),({},bytes(len(packet)))):
    try: transform_packet(meta|changed,data)
    except ValueError: continue
    raise AssertionError('invalid vertex observation accepted')
other=bytearray(constants);struct.pack_into('<f',other,7*16+4,2)
records=[(meta|analysis,code,constants),(meta|analysis|dict(presentation_index=6),code,bytes(other))]
r=transform_changes(records);assert r['groups'][0]['changes'][0]['changed_registers']==[7]
assert not r['groups'][0]['changes'][0]['viewport_changed'] and not r['transform_semantics_verified']
try: transform_changes([records[0],(records[1][0]|dict(counter=11),code,bytes(other))])
except ValueError: pass
else: raise AssertionError('advanced counter accepted')
print('Vertex program/viewport/packet bounds and exact held-register changes passed.')

assembly='// ViewProjectionMatrix c1 4\n// ViewOrthoProjectionX c7 1\n// LocalToWorld c10 4\n'
assert projection_bindings(assembly,packet[:8])==dict(projection=1,ortho=7,local_to_world=10)
for changed in (assembly.replace(' c1 4',' c1 3'),assembly.replace('c7 1','c2 1'),
        assembly+'    def c2, 0, 0, 0, 0\n',assembly.replace('c10 4','c1 4'),assembly+'// LocalToWorld c10 4\n'):
    try: projection_bindings(changed,packet[:8])
    except ValueError: pass
    else: raise AssertionError('invalid native projection binding accepted')
