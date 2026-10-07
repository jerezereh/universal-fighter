"""Derive a local read-only SIGN observation profile; never execute discovered code."""
from collections import Counter
import hashlib
import math
from pathlib import Path
import re
import struct
import subprocess


def assembly_rows(text):
    rows=[]
    for line in text.splitlines():
        m=re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*([a-z][a-z0-9]*)(?:\s+(.*))?$',line)
        if m:
            rows.append(dict(address=int(m[1],16),op=m[2],args=(m[3] or '').strip()))
    return rows


def getter_fields(rows):
    aliases=[r['args'].split(',')[0] for r in rows[:8] if r['op']=='mov' and r['args'].endswith(',ecx')]
    if len(aliases)!=1 or aliases[0] not in ('esi','edi') or not any(r['op']=='ret' for r in rows):
        raise ValueError('not a bounded scalar thiscall getter')
    alias=aliases[0]
    scalars=[]; parents=[]
    for r in rows:
        m=re.fullmatch(r'(eax|ecx|esi),DWORD PTR \['+alias+r'\+0x([0-9a-f]+)\]',r['args'])
        if m and r['op']=='mov':
            offset=int(m[2],16)
            if m[1]=='ecx': parents.append(offset)
            elif (m[1]=='eax' and alias=='esi') or (m[1]=='esi' and alias=='edi'): scalars.append(offset)
    counts=Counter(scalars)
    if not counts:
        raise ValueError('no scalar getter field')
    ranked=counts.most_common()
    if ranked[0][1]<2 or len(ranked)>1 and ranked[0][1]==ranked[1][1]:
        raise ValueError('ambiguous scalar getter field')
    return ranked[0][0],sorted(set(parents))


def unique(rows, label):
    if len(rows)!=1: raise ValueError('missing/ambiguous '+label)
    return rows[0]


def global_operand(code, offset, base, image_size, sections):
    if offset<2 or offset+4>len(code) or code[offset-2:offset]!=b'\x8b\x0d':
        raise ValueError('global candidate is not an absolute ECX load operand')
    address=struct.unpack_from('<I',code,offset)[0];rva=address-base
    if not 0<=rva<=image_size-4 or rva%4 or not any(s['rva']<=rva<s['rva']+max(s['virtual_size'],s['size']) and s['flags']&0x80000000 for s in sections):
        raise ValueError('global operand outside writable module data')
    return rva


def profile(report, folder, source, objdump):
    if 'image_size' not in report: raise ValueError('old live receipt: run a fresh native probe')
    section=unique([s for s in report['sections'] if s['name']=='.text'],'code section')
    code=(folder/'text-loaded.bin').read_bytes()
    if hashlib.sha256(code).hexdigest()!=report['loaded_hashes']['.text']:
        raise ValueError('loaded code receipt drift')
    base=report['module_base'];code_base=base+section['rva']
    candidates={r['name']:r['matches'] for r in report['loaded_candidates']}
    engine=unique(candidates['asw_engine'],'engine global')['candidate_rva']
    engine_rva=global_operand(code,engine-section['rva'],base,report['image_size'],report['sections'])

    def disassemble(rva,label):
        at=rva-section['rva']
        if not 0<=at<len(code) or at and code[at-1]!=0xcc:
            raise ValueError('candidate does not start at an aligned function boundary')
        pad=re.search(rb'\xcc{2,}',code[at:at+2048])
        if not pad: raise ValueError('function extent exceeds bounded scan')
        end=at+pad.start()
        text=subprocess.check_output([str(objdump),'-D','-b','binary','-m','i386','-Mintel',
                                      '--adjust-vma='+hex(code_base),'--start-address='+hex(base+rva),
                                      '--stop-address='+hex(code_base+end),str(folder/'text-loaded.bin')],text=True)
        (folder/(label+'.asm.txt')).write_text(text)
        rows=assembly_rows(text)
        if not rows or rows[0]['address']!=base+rva: raise ValueError('invalid disassembly boundary')
        return rows

    throw=unique(candidates['can_throw'],'throw envelope')['candidate_rva']
    calls=Counter(int(r['args'].split()[0],16)-base for r in disassemble(throw,'state-throw') if r['op']=='call' and re.match(r'0x[0-9a-f]+',r['args']))
    fields={};getters={};parent_fields=set()
    for axis,name in (('x','get_pos_x'),('y','get_pos_y')):
        called=[m['candidate_rva'] for m in candidates[name] if calls[m['candidate_rva']]>=2]
        target=unique(called,axis+' getter linked by throw envelope')
        raw,parents=getter_fields(disassemble(target,'state-get-'+axis))
        fields[axis]=raw;getters[axis]=target;parent_fields.update(parents)

    def reference_field(name):
        # Only read declarations from the pinned public reference. Never carry retail addresses.
        pattern=r'const auto\s+\*?'+name+r'\s*=.*?\+\s*(0x[0-9a-fA-F]+)\)'
        values=set(int(m,16) for m in re.findall(pattern,source))
        return unique(list(values),'reference '+name)

    fields.update(slots=reference_field('ent_slots'),count=reference_field('ent_count'),
                  boxes=reference_field('hitbox_data'),hurt_count=reference_field('hurtbox_count'),
                  hit_count=reference_field('hitbox_count'),scale_x=reference_field('scale_x'),scale_y=reference_field('scale_y'),rotation=reference_field('angle'))
    facing=unique(list(set(int(v,16) for v in re.findall(r'const auto flip = \*\(int\*\)\([^\n]*?\+\s*(0x[0-9a-fA-F]+)\)',source))),'reference facing')
    fields['facing']=facing
    if any(not 0<=v<0x10000 or v%4 for v in fields.values()) or any(not 0<=v<0x10000 or v%4 for v in parent_fields):
        raise ValueError('unbounded native profile fields')
    return dict(schema=1,pid=report['pid'],module_base=base,exe_sha256=report['exe_sha256'],
                code_sha256=report['loaded_hashes']['.text'],code_rva=section['rva'],code_size=section['size'],
                engine_global_rva=engine_rva,fields=fields,parents=sorted(parent_fields),getters=getters,
                native_tick_verified=False,host_step=False,isolated_rgba=False,universal_contact=False)


def observe(process, p):
    def uint(address): return struct.unpack('<I',process.read(address,4))[0]
    root=uint(p['module_base']+p['engine_global_rva'])
    if not root: raise ValueError('native battle engine is absent')
    f=p['fields'];count=struct.unpack('<i',process.read(root+f['count'],4))[0]
    if not 2<=count<=256: raise ValueError('native entity count outside training bounds')
    slots=struct.unpack('<2I',process.read(root+f['slots'],8))
    if not all(slots) or slots[0]==slots[1]: raise ValueError('invalid native fighter slots')
    result=[]
    for slot,address in enumerate(slots):
        size=max([f[k]+4 for k in ('x','y','facing','boxes','hurt_count','hit_count','scale_x','scale_y')]+[v+4 for v in p['parents']]+([f['rotation']+4] if 'rotation' in f else []))
        data=process.read(address,size)
        integer=lambda name:struct.unpack_from('<i',data,f[name])[0]
        if any(struct.unpack_from('<I',data,v)[0] for v in p['parents']):
            raise ValueError('attached/parent-relative fighter unsupported by raw observation')
        x,y,facing=integer('x'),integer('y'),integer('facing')
        hurt,hit=integer('hurt_count'),integer('hit_count')
        if facing not in (0,1) or max(abs(x),abs(y))>10000000 or not 0<=hurt<=64 or not 0<=hit<=64:
            raise ValueError('invalid native transform/collision counts')
        pointer=struct.unpack_from('<I',data,f['boxes'])[0]
        boxes=[]
        if hurt+hit:
            raw=process.read(pointer,20*(hurt+hit))
            for i in range(hurt+hit):
                kind,bx,by,w,h=struct.unpack_from('<I4f',raw,i*20)
                if kind not in (0,1) or not all(math.isfinite(v) and abs(v)<1e6 for v in (bx,by,w,h)) or w<0 or h<0:
                    raise ValueError('invalid native collision record')
                boxes.append([kind,bx,by,w,h])
        names=process.read(address,0x2600)
        # Names occupy aligned native buffers; inspect overlapping prefixes so adjacent
        # scalar bytes cannot hide a valid name or add a spurious leading character.
        poses=[dict(offset=m.start(),value=m[1][:-1].decode()) for m in re.finditer(rb'(?=([a-z]{2,4}[0-9]{3}_[0-9]{2}\0))',names) if m.start()%4==0]
        states=[dict(offset=m.start(),value=m[0][:-1].decode()) for m in re.finditer(rb'(?:CmnAct|NmlAtk)[A-Za-z0-9_]{1,28}\0',names)]
        result.append(dict(slot=slot,x_raw=x,y_raw=y,facing_left=bool(facing),hurt_count=hurt,hit_count=hit,
                           scale_raw=[integer('scale_x'),integer('scale_y')],rotation_raw=integer('rotation') if 'rotation' in f else None,
                           boxes=boxes,pose_candidates=poses,state_candidates=states))
        if p.get('scalar_fields'):
            result[-1]['scalar_observations']={name:struct.unpack_from('<i',names,offset)[0] for name,offset in p['scalar_fields'].items()}
    if uint(p['module_base']+p['engine_global_rva'])!=root or process.read(root+f['slots'],8)!=struct.pack('<2I',*slots):
        raise ValueError('native scene changed during observation')
    return dict(entities=count,fighters=result,atomic_native_frame=False)


def boundary_candidate(code, code_rva, candidate, rows):
    """Validate a local counter-writer's enclosing thiscall routine, not its semantics."""
    rva,writer,size=(candidate[k] for k in ('rva','writer_rva','code_size'))
    if any(type(v)!=int for v in (rva,writer,size)):
        raise ValueError('non-integer native candidate')
    start=rva-code_rva;end=start+size
    if not 0<start<end<=len(code) or not 16<=size<=8192 or code[start-1]!=0xcc or code[end-1]!=0xc3:
        raise ValueError('invalid bounded no-stack-argument function extent')
    if not rva<=writer<rva+size or not rows or rows[0]['address']!=rva or rows[-1]['address']!=rva+size-1 or rows[-1]['op']!='ret' or rows[-1]['args']:
        raise ValueError('disassembly does not cover candidate boundaries')
    if not any(r['op']=='mov' and r['args']=='esi,ecx' and r['address']<rva+128 for r in rows):
        raise ValueError('missing thiscall object alias')
    row=unique([r for r in rows if r['address']==writer],'counter writer instruction')
    field=re.fullmatch(r'DWORD PTR \[esi\+0x([0-9a-f]+)\]',row['args'])
    if row['op']!='inc' or not field: raise ValueError('candidate is not an object counter increment')
    counter=int(field[1],16)
    if not 0<counter<4<<20 or counter%4: raise ValueError('unbounded counter field')
    # Require the actual instruction bytes as well as the disassembler's text.
    at=writer-code_rva
    if code[at:at+6]!=b'\xff\x86'+struct.pack('<I',counter): raise ValueError('counter instruction bytes disagree')
    return dict(rva=rva,writer_rva=writer,code_size=size,counter_field=counter,
                function_hex=code[start:end].hex(),validated_semantics=False)
