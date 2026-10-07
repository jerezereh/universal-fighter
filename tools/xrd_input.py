"""Validate session-local SIGN input ingress and compile named receiver inputs."""
import re
import struct

from xrd_state import unique

# Core bits agree with the inspected SIGN mapper and pinned public input declarations.
# Macros and training/menu controls are deliberately excluded from this first slice.
INPUT_BITS=dict(up=1,down=2,left=4,right=8,punch=16,kick=32,slash=64,heavy_slash=128,dust=256,taunt=512)


def input_mask(named,facing_left=False,accept_input=True):
    if type(named)!=dict or any(k not in INPUT_BITS and k not in ('forward','back') or type(v)!=bool for k,v in named.items()):
        raise ValueError('unknown/non-boolean SIGN input')
    if type(facing_left)!=bool or type(accept_input)!=bool: raise ValueError('invalid facing/input acceptance')
    if not accept_input: return 0
    values=dict(named)
    values['left']=named.get('left',False) or named.get('forward' if facing_left else 'back',False)
    values['right']=named.get('right',False) or named.get('back' if facing_left else 'forward',False)
    # ponytail: neutral opposing directions; no game-specific SOCD policy until its oracle exists.
    for a,b in (('left','right'),('up','down')):
        if values.get(a) and values.get(b): values[a]=values[b]=False
    return sum(bit for name,bit in INPUT_BITS.items() if values.get(name))


def input_plan(data):
    if type(data)!=list or not 1<=len(data)<=32: raise ValueError('input plan must have 1..32 segments')
    frames=[]
    for segment in data:
        if type(segment)!=dict or set(segment)-{'frames','input','label','accept_input'}:
            raise ValueError('invalid input segment')
        count=segment.get('frames',1);label=segment.get('label','input')
        if type(count)!=int or not 1<=count<=160 or type(label)!=str or not 1<=len(label)<=32:
            raise ValueError('invalid input frame count/label')
        named=segment.get('input',{});accept=segment.get('accept_input',True)
        input_mask(named,False,accept)
        frames.extend(dict(input=dict(named),label=label,accept_input=accept) for _ in range(count))
        if len(frames)>160: raise ValueError('input plan exceeds bounded gate capacity')
    return frames


def input_check(records,states,inputs):
    executed=[(r,s) for r,s in zip(records,states) if r['executed']]
    by_counter={}
    for i in inputs:
        if i['injected']: by_counter.setdefault(i['counter'],[]).append(i)
    linked=bool(executed)
    for r,s in executed:
        calls=by_counter.get(r['before'],[])
        linked &= len(calls)==2 and sorted(i['slot'] for i in calls)==[0,1] and all(i['incoming']==r['requested_inputs'][i['slot']] for i in calls)
    walk_left=walk_right=airborne=False;normal_activations=0;was_normal=False
    for index,(r,s) in enumerate(executed):
        sol=s[0];normal=any(n['value']=='NmlAtk5A' for n in sol['state_candidates']) and any(n['value'].startswith('sol200_') for n in sol['pose_candidates'])
        if normal and not was_normal: normal_activations+=1
        was_normal=normal
        airborne |= sol['y_raw']>0
        if index:
            delta=sol['x_raw']-executed[index-1][1][0]['x_raw']
            mask=r['requested_inputs'][0]
            walk_left |= bool(mask&4) and delta<0
            walk_right |= bool(mask&8) and delta>0
    return dict(source_history_linked=bool(linked),executed_steps=len(executed),
        walk_left=bool(walk_left),walk_right=bool(walk_right),airborne=bool(airborne),
        grounded_at_end=bool(executed) and executed[-1][1][0]['y_raw']==0,
        standing_punch_activations=normal_activations,
        active_normal_steps=sum(s[0]['hit_count']>0 for r,s in executed),
        opponent_neutral=bool(executed) and all(r['requested_inputs'][1]==0 for r,s in executed))


def input_candidate(code,code_rva,local,owner_rows,sampler_rows,writer_rows):
    """Derive the native ring layout and callsite from bounded actual instructions."""
    for label,rows,ending in (('sampler',sampler_rows,b'\xc3'),('writer',writer_rows,b'\xc2\x04\x00')):
        rva,size=(local[label+'_'+k] for k in ('rva','size'))
        if type(rva)!=int or type(size)!=int: raise ValueError('non-integer native input candidate')
        at=rva-code_rva
        if not 0<at<at+size<=len(code) or not 16<=size<=4096 or code[at-1]!=0xcc or not code[at:at+size].endswith(ending):
            raise ValueError('invalid bounded native input '+label)
        if not rows or rows[0]['address']!=rva or rows[-1]['op']!='ret' or rows[-1]['address']+len(ending)!=rva+size:
            raise ValueError('input disassembly extent mismatch')
    sampler,writer,ingress=(local[k] for k in ('sampler_rva','writer_rva','ingress_rva'))
    if not any(r['op']=='call' and r['args']==hex(sampler) for r in owner_rows):
        raise ValueError('sampler is not called by the validated update owner')
    fields=unique([int(m[1],16) for r in sampler_rows if r['op']=='lea' and (m:=re.fullmatch(r'ecx,\[eax\+0x([0-9a-f]+)\]',r['args']))],'native input ring origin')
    i=unique([i for i,r in enumerate(sampler_rows) if r['address']==ingress],'input ingress instruction')
    strides=unique([int(m[1],16) for r in sampler_rows[i+3:i+24] if r['op']=='add' and (m:=re.fullmatch(r'edi,0x([0-9a-f]+)',r['args']))],'native input ring stride')
    if i+2>=len(sampler_rows) or [(r['op'],r['args']) for r in sampler_rows[i:i+3]]!=[('push','esi'),('mov','ecx,edi'),('call',hex(writer))]:
        raise ValueError('input ingress is not the native ring write')
    at=ingress-code_rva
    if code[at:at+4]!=b'\x56\x8b\xcf\xe8' or ingress+8+struct.unpack_from('<i',code,at+4)[0]!=writer:
        raise ValueError('input ingress instruction bytes disagree')
    if not any(r['op']=='inc' and r['args']=='ebp' for r in sampler_rows) or not any(r['op']=='push' and r['args']=='ebp' for r in sampler_rows[i+3:i+7]):
        raise ValueError('missing native player-index loop')
    current=unique([int(m[1],16) for r in writer_rows if r['op']=='mov' and (m:=re.fullmatch(r'WORD PTR \[ecx\+0x([0-9a-f]+)\],si',r['args']))],'current input field')
    index=unique(sorted(set(int(m[1],16) for r in writer_rows if r['op']=='movzx' and (m:=re.fullmatch(r'(?:eax|edx),WORD PTR \[ecx\+0x([0-9a-f]+)\]',r['args'])))),'ring index field')
    inputs=unique([int(m[1],16) for r in writer_rows if r['op']=='cmp' and (m:=re.fullmatch(r'si,WORD PTR \[ecx\+eax\*2\+0x([0-9a-f]+)\]',r['args']))],'ring entries')
    held=unique([int(m[1],16) for r in writer_rows if r['op']=='lea' and (m:=re.fullmatch(r'eax,\[ecx\+eax\*2\+0x([0-9a-f]+)\]',r['args']))],'ring held durations')
    capacity=unique([int(m[1],16) for r in writer_rows if r['op']=='cmp' and (m:=re.fullmatch(r'ax,0x([0-9a-f]+)',r['args']))],'ring capacity')
    if not 0<fields<4<<20 or fields%4 or not 2<=capacity<=64 or strides!=index+2 or not 0<current<inputs<held<index or inputs+2*capacity!=held or held+2*capacity!=index:
        raise ValueError('invalid bounded native input layout')
    result=dict(local,ring_field=fields,stride=strides,current=current,index=index,inputs=inputs,held=held,capacity=capacity,validated_semantics=False)
    for label in ('sampler','writer'):
        at=local[label+'_rva']-code_rva
        result[label+'_hex']=code[at:at+local[label+'_size']].hex()
    return result
