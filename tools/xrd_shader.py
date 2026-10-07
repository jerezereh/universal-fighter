"""Bounded Shader Model 3 token framing and a private opaque-alpha variant.

Consumes the user's local GPU program; native shader bytecode is never versioned.
"""
import hashlib
import struct


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
