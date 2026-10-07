"""Authored counter-boundary and captured-state checks; no game or injector required."""
import importlib.util
import json
from pathlib import Path
import runpy
import struct
import tempfile

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
    evidence=dict(pid=123,samples=100,errors=[],continuity_gaps=0,counter_deltas={'1':100},
        this_deltas=[4],depths=[0],threads=[99],return_addresses=['0x2000'],
        observations_only=True,loaded_code_restored=True,detached=True)
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder);(folder/'candidate.json').write_text(json.dumps(p))
        def check_evidence(changes):
            (folder/'inspection.json').write_text(json.dumps(evidence|changes))
            return boundary.gate_evidence(folder,p,dict(pid=123))
        assert check_evidence({})==dict(thread=99,return_address='0x2000')
        for changes in (dict(pid=124),dict(samples=99),dict(threads=[99,100]),dict(detached=False),dict(counter_deltas={'0':100})):
            reject(lambda:check_evidence(changes))
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
    records=[dict(executed=False,counter_delta=0),dict(executed=True,counter_delta=1),
             dict(executed=False,counter_delta=0),dict(executed=True,counter_delta=1),
             dict(executed=False,counter_delta=0),dict(executed=True,counter_delta=1)]
    states=[0,1,1,2,2,3]
    for r,s in zip(records,states): r['before']=s
    checked=boundary.gate_check(records,states)
    assert checked['exact_steps'] and checked['frozen_counter'] and checked['frozen_observed_state']
    assert not boundary.gate_check(records,[0,1,9,2,2,3])['frozen_observed_state']
    assert not boundary.gate_check(records[:-1],states[:-1])['exact_steps']
    assert not boundary.gate_check([records[0]|dict(counter_delta=1)]+records[1:],states)['frozen_counter']
    assert not checked['rendering_while_frozen']
    held=[dict(executed=False,counter_delta=0,before=10),dict(executed=False,counter_delta=0,before=11)]
    presentations=[dict(counter=c,hresult=0) for c in (10,11) for _ in range(10)]
    assert boundary.gate_check(held,[0,0],presentations)['rendering_while_frozen']
    assert not boundary.gate_check(held,[0,0],[p|dict(hresult=-1) for p in presentations])['rendering_while_frozen']
    diagnostics=[dict(message='gate lease expired'),dict(message='hard gate lifetime expired')]
    r=[dict(executed=False,counter_delta=0,before=10,after=10)]
    checked=boundary.lease_check(r,[dict(counter=11,hresult=0)],diagnostics,True)
    assert all(checked.values())
    assert not boundary.lease_check(r,[],diagnostics,True)['lease_resumed']
    assert not boundary.lease_check(r,[dict(counter=11,hresult=0)],diagnostics,False)['hard_lifetime_removed_hook']
    print('Bounded thiscall/counter derivation, byte agreement, invalid candidate/capture rejection and snapshot reuse passed.')


if __name__=='__main__': main()
