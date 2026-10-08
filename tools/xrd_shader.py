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
    return metadata|dict(sha256=hashlib.sha256(data).hexdigest(),color_verified=False,replay_verified=False)


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
