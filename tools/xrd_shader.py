"""Bounded Shader Model 3 token framing and a private opaque-alpha variant.

Consumes the user's local GPU program; native shader bytecode is never versioned.
"""
import hashlib
import struct
import re


def screen_packet(metadata,data):
    """Read-only screen-draw program/constant observation, never a replayable color pass."""
    if (not 8<=len(data)<=65536 or len(data)%4 or metadata.get('code_size')!=len(data) or
            struct.unpack_from('<I',data)[0] not in (0xffff0200,0xffff0300) or data[-4:]!=b'\xff\xff\0\0' or
            metadata.get('read_only') is not True or metadata.get('kind')!='screen-shader' or
            not re.fullmatch('[0-9a-f]{7168}',metadata.get('constants_hex','')) or
            not isinstance(metadata.get('assembly'),str) or not 1<=len(metadata['assembly'])<=131072 or
            type(metadata.get('srgb_write'))!=int or metadata['srgb_write'] not in (0,1) or
            any(not re.fullmatch('0x[0-9a-f]{1,8}',metadata.get(k,'')) or metadata[k]=='0x0'
                for k in ('shader','source_target'))):
        raise ValueError('invalid screen shader observation')
    samplers=metadata.get('samplers',[])
    if (len(samplers)!=16 or any(s.get('slot')!=i or type(s.get('srgb'))!=int or s['srgb'] not in (0,1) or
            s.get('texture') is not None and not re.fullmatch('0x[0-9a-f]{1,8}',s['texture'])
            for i,s in enumerate(samplers))): raise ValueError('invalid screen sampler observation')
    for key,low,high in [('counter',0,0xffffffff),('trace_frame',1,2),('trace_event',0,8191)]:
        if type(metadata.get(key))!=int or not low<=metadata[key]<=high: raise ValueError('invalid screen frame identity')
    lut=metadata.get('lut_source')
    sources=metadata.get('texture_sources')
    if sources is not None and (type(sources)!=list or len(sources)>16 or
            len({s.get('slot') for s in sources})!=len(sources) or any(
                type(s.get('slot'))!=int or not 0<=s['slot']<16 or
                s.get('texture')!=samplers[s['slot']]['texture'] or
                not re.fullmatch('0x[0-9a-f]{1,8}',s.get('surface','')) or s['surface']=='0x0' or
                type(s.get('format'))!=int or not 0<=s['format']<=0xffffffff or
                any(type(s.get(k))!=int or not 1<=s[k]<=2048 for k in ('width','height')) for s in sources)):
        raise ValueError('invalid screen texture/surface association')
    if lut is not None and (type(lut.get('slot'))!=int or not 0<=lut['slot']<16 or
            lut.get('texture')!=samplers[lut['slot']]['texture'] or
            not re.fullmatch('0x[0-9a-f]{1,8}',lut.get('surface','')) or lut['surface']=='0x0' or
            lut.get('format')!=21 or any(type(lut.get(k))!=int or not 2<=lut[k]<=1024 for k in ('width','height'))):
        raise ValueError('invalid native LUT surface association')
    vertex=metadata.get('vertex_program');vertex_hash=None
    if vertex is not None:
        if (type(vertex)!=dict or set(vertex)!={'shader','code_hex','assembly','constants_hex'} or
                not re.fullmatch('0x[0-9a-f]{1,8}',vertex.get('shader','')) or vertex['shader']=='0x0' or
                not re.fullmatch('[0-9a-f]{16,131072}',vertex.get('code_hex','')) or len(vertex['code_hex'])%8 or
                not re.fullmatch('[0-9a-f]{8192}',vertex.get('constants_hex','')) or
                not isinstance(vertex.get('assembly'),str) or not 1<=len(vertex['assembly'])<=131072):
            raise ValueError('invalid screen vertex observation')
        code=bytes.fromhex(vertex['code_hex'])
        if struct.unpack_from('<I',code)[0] not in (0xfffe0200,0xfffe0300) or code[-4:]!=b'\xff\xff\0\0':
            raise ValueError('unsupported screen vertex program')
        vertex_hash=hashlib.sha256(code).hexdigest()
    vertex_input=metadata.get('vertex_input');input_hash=None
    if vertex_input is not None:
        if (type(vertex_input)!=dict or set(vertex_input)!={'stride','index_format','vertices_hex','indices_hex','declaration_hex'} or
                type(vertex_input['stride'])!=int or not 16<=vertex_input['stride']<=256 or vertex_input['stride']%4 or
                vertex_input['index_format'] not in (101,102) or
                any(type(vertex_input[k])!=str for k in ('vertices_hex','indices_hex','declaration_hex')) or
                not re.fullmatch('[0-9a-f]{'+str(vertex_input['stride']*8)+'}',vertex_input['vertices_hex']) or
                not re.fullmatch('[0-9a-f]{'+str(24 if vertex_input['index_format']==101 else 48)+'}',vertex_input['indices_hex']) or
                not re.fullmatch('[0-9a-f]{32,512}',vertex_input['declaration_hex']) or len(vertex_input['declaration_hex'])%16):
            raise ValueError('invalid screen quad input')
        indices=bytes.fromhex(vertex_input['indices_hex'])
        if any(n>=4 for n in struct.unpack('<6'+('H' if vertex_input['index_format']==101 else 'I'),indices)):
            raise ValueError('grading index outside quad')
        declaration=bytes.fromhex(vertex_input['declaration_hex'])
        if declaration[-8:]!=struct.pack('<HH4B',255,0,17,0,0,0):
            raise ValueError('grading declaration end missing')
        input_hash=hashlib.sha256(bytes.fromhex(vertex_input['vertices_hex'])+indices+declaration).hexdigest()
    return metadata|dict(sha256=hashlib.sha256(data).hexdigest(),vertex_code_sha256=vertex_hash,vertex_input_sha256=input_hash,
        color_verified=False,replay_verified=False)


def opaque_alpha_variant(data):
    if not 8<=len(data)<=65536 or len(data)%4: raise ValueError('invalid shader bounds')
    words=list(struct.unpack('<'+'I'*(len(data)//4),data))
    if words[0]!=0xffff0300: raise ValueError('requires pixel shader model 3')
    i=1;writes_color=False;instructions=0
    while i<len(words):
        token=words[i];opcode=token&0xffff
        if opcode==0xffff:
            if token!=0xffff or i!=len(words)-1: raise ValueError('invalid shader end/trailing tokens')
            break
        if opcode==0xfffe:
            length=(token>>16)&0x7fff
            if i+1+length>=len(words): raise ValueError('unbounded shader comment')
            i+=1+length;continue
        if opcode in (25,26,28,30): raise ValueError('subroutine/return shader requires another alpha route')
        length=(token>>24)&15
        if i+1+length>=len(words): raise ValueError('instruction leaves shader bounds')
        for operand in words[i+1:i+1+length]:
            if not operand&0x80000000: continue
            register_type=((operand>>28)&7)|((operand>>8)&24)
            register=operand&0x7ff
            if register_type==2 and (register==223 or operand&0x2000):
                raise ValueError('reserved constant is used or dynamically addressed')
        if length:
            destination=words[i+1]
            if (((destination>>28)&7)|((destination>>8)&24))==8 and (destination&0x7ff)==0:
                writes_color=True
        instructions+=1;i+=1+length
    else: raise ValueError('shader end missing')
    if not writes_color: raise ValueError('no color-zero output')
    # SDK tokens: MOV oC0.w,c223.x. Original colors, texture sampling and TEXKILL remain intact.
    patched=words[:-1]+[0x02000001,0x80080800,0xa00000df,0xffff]
    return struct.pack('<'+'I'*len(patched),*patched),dict(constant=223,instructions=instructions,
        original_sha256=hashlib.sha256(data).hexdigest(),opaque_alpha_only=True,coverage_verified=False)
