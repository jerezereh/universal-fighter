"""Authored proxy scope/ownership rejection checks; no source code or process."""
import copy
import hashlib
import struct
from xrd_proxy import attack_region, idle_check


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('invalid proxy witness accepted')


code = bytearray(b'\xcc'*512)
code[16:33] = b'\x8d\x8e'+struct.pack('<I',128)+b'\xe8'+struct.pack('<i',128-27)+b'\x8d\x8e'+struct.pack('<I',192)
code[128:160] = b'\x90'*31+b'\xc3'
local = dict(caller_rva=4112, initializer_rva=4224, initializer_size=32,
    initializer_sha256=hashlib.sha256(code[128:160]).hexdigest())
assert attack_region(code,4096,local) == (128,64)
for change in [dict(caller_rva=True),dict(initializer_rva=4225),dict(initializer_size=33),dict(initializer_sha256='wrong')]:
    reject(lambda:attack_region(code,4096,local|change))
bad = bytearray(code);bad[27]=0
reject(lambda:attack_region(bad,4096,local))
records=[dict(executed=True,requested_inputs=[0,0]),dict(executed=False,requested_inputs=None)]
states=[[{},dict(hit_count=0,y_raw=0,pose_candidates=[dict(value='kyk000_01')])] for _ in records]
event=dict(proxy_metadata_restored=True,proxy_hit_count_before=0)
assert idle_check(records,states,event)
alt=copy.deepcopy(states);alt[0][1]['pose_candidates']=[dict(value='kyk001_06')]
assert idle_check(records,alt,event)
assert not idle_check(records,states,event|dict(proxy_metadata_restored=False))
assert not idle_check(records,states,event|dict(proxy_hit_count_before=1))
for field,value in [('hit_count',1),('y_raw',1),('pose_candidates',[dict(value='kyk200_01')]),('pose_candidates',[])]:
    bad=copy.deepcopy(states);bad[0][1][field]=value
    assert not idle_check(records,bad,event)
bad=copy.deepcopy(records);bad[0]['requested_inputs']=[0,16]
assert not idle_check(bad,states,event)
assert not idle_check(records,states[:1],event)
print('Proxy initializer, neutral input, idle pose and restoration rejection checks passed.')
