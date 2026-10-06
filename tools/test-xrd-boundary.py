"""Authored counter-boundary and captured-state checks; no game or injector required."""
import importlib.util
from pathlib import Path
import runpy
import struct

from xrd_state import boundary_candidate, observe

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('boundary',ROOT/'xrd-sign-boundary.py')
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
fixture=runpy.run_path(str(ROOT/'test-xrd-state.py'))['fixture']


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('accepted invalid boundary/capture')


def main():
    code=b'\xcc\x8b\xf1'+b'\x90'*9+b'\xff\x86'+struct.pack('<I',0x200)+b'\x90'*5+b'\xc3'
    candidate=dict(rva=0x1001,writer_rva=0x100c,code_size=23)
    rows=[dict(address=0x1001,op='mov',args='esi,ecx'),
          dict(address=0x100c,op='inc',args='DWORD PTR [esi+0x200]'),
          dict(address=0x1017,op='ret',args='')]
    p=boundary_candidate(code,0x1000,candidate,rows)
    assert p['counter_field']==0x200 and not p['validated_semantics']
    for changed in (dict(rva=True),dict(writer_rva=0x100d),dict(code_size=8193),dict(rva=0x1002)):
        reject(lambda:boundary_candidate(code,0x1000,candidate|changed,rows))
    reject(lambda:boundary_candidate(b'\x90'+code[1:],0x1000,candidate,rows))
    reject(lambda:boundary_candidate(code[:-1]+b'\xc2',0x1000,candidate,rows))
    reject(lambda:boundary_candidate(code,0x1000,candidate,[rows[0],rows[1]|dict(args='DWORD PTR [esi+0x204]'),rows[2]]))
    m,p=fixture();segments=[];data=b''
    for address,block in m.segments.items():
        segments.append(dict(address=address,offset=len(data),size=len(block)));data+=block
    captured=boundary.CapturedMemory(segments,data)
    assert observe(captured,p)==observe(m,p)
    reject(lambda:boundary.CapturedMemory(segments,data[:-1]))
    reject(lambda:boundary.CapturedMemory([segments[0]|dict(offset=1)]+segments[1:],data))
    reject(lambda:captured.read(1,4))
    print('Bounded thiscall/counter derivation, byte agreement, invalid candidate/capture rejection and snapshot reuse passed.')


if __name__=='__main__': main()
