"""Authored named-input, native-layout and source-step association checks."""
import struct

from xrd_input import input_mask, input_plan, input_candidate, input_check


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('accepted invalid input/layout')


def main():
    assert input_mask({'forward':True,'punch':True})==24
    assert input_mask({'forward':True,'punch':True},True)==20
    assert input_mask({'back':True},True)==8
    assert input_mask({'left':True,'right':True,'up':True,'down':True,'dust':True})==256
    assert input_mask({'punch':True},accept_input=False)==0
    for named in ({'record':True},{'menu':True},{'punch':1},{'unknown':False}): reject(lambda:input_mask(named))
    reject(lambda:input_mask({},facing_left=1))
    assert len(input_plan([dict(frames=2,input={'punch':True})]))==2
    for plan in ([],[dict(frames=True)],[dict(frames=161)],[dict(frames=100),dict(frames=100)],[dict(extra=1)],[dict(accept_input=0)]):
        reject(lambda:input_plan(plan))
    # Invented fields/code locations; no source game bytes or layout profile in this test.
    code=bytearray(b'\xcc'*0x500)
    code[0x100:0x140]=b'\x90'*63+b'\xc3'
    code[0x110:0x118]=b'\x56\x8b\xcf\xe8'+struct.pack('<i',0x1300-0x1118)
    code[0x300:0x318]=b'\x90'*21+b'\xc2\x04\x00'
    row=lambda address,op,args:dict(address=address,op=op,args=args)
    sampler=[row(0x1100,'lea','ecx,[eax+0x200]'),row(0x1110,'push','esi'),
        row(0x1111,'mov','ecx,edi'),row(0x1113,'call','0x1300'),row(0x1118,'push','esi'),
        row(0x1119,'push','ebp'),row(0x111a,'add','edi,0x16'),row(0x111d,'inc','ebp'),row(0x113f,'ret','')]
    writer=[row(0x1300,'mov','WORD PTR [ecx+0x2],si'),row(0x1304,'movzx','eax,WORD PTR [ecx+0x14]'),
        row(0x1308,'cmp','si,WORD PTR [ecx+eax*2+0x4]'),row(0x130c,'lea','eax,[ecx+eax*2+0xc]'),
        row(0x1310,'cmp','ax,0x4'),row(0x1315,'ret','0x4')]
    local=dict(sampler_rva=0x1100,sampler_size=64,writer_rva=0x1300,writer_size=24,ingress_rva=0x1110)
    owner=[row(0x1000,'call','0x1100')]
    p=input_candidate(code,0x1000,local,owner,sampler,writer)
    assert p['ring_field']==0x200 and p['capacity']==4 and p['stride']==22 and not p['validated_semantics']
    reject(lambda:input_candidate(code,0x1000,local,[],sampler,writer))
    reject(lambda:input_candidate(code,0x1000,local|dict(ingress_rva=0x1111),owner,sampler,writer))
    reject(lambda:input_candidate(code,0x1000,local,owner,sampler[:6]+[sampler[6]|dict(args='edi,0x18')]+sampler[7:],writer))
    bad=bytearray(code);bad[0x110]=0x90
    reject(lambda:input_candidate(bad,0x1000,local,owner,sampler,writer))
    records=[dict(executed=True,before=10,requested_inputs=[16,0])]
    states=[[dict(x_raw=0,y_raw=0,hit_count=1,state_candidates=[dict(value='NmlAtk5A')],pose_candidates=[dict(value='sol200_02')]),{}]]
    calls=[dict(injected=True,counter=10,slot=i,incoming=mask) for i,mask in enumerate([16,0])]
    checked=input_check(records,states,calls)
    assert checked['source_history_linked'] and checked['standing_punch_activations']==1 and checked['active_normal_steps']==1
    assert not input_check(records,states,calls[:-1])['source_history_linked']
    assert not input_check(records,states,[calls[0]|dict(incoming=0),calls[1]])['source_history_linked']
    print('Named input/facing/SOCD, bounded plans, native layout/caller/byte rejection and per-step history association passed.')


if __name__=='__main__': main()
