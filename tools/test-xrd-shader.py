"""Authored Shader Model 3 framing and alpha-variant guards; no game bytecode."""
import struct
from xrd_shader import opaque_alpha_variant, screen_packet


def pack(words): return struct.pack('<'+'I'*len(words),*words)
def reject(words):
    try: opaque_alpha_variant(pack(words))
    except ValueError: return
    raise AssertionError('unsafe shader variant accepted')


def main():
    words=[0xffff0300,0x02000001,0x800f0800,0x80e40000,0xffff]
    patched,report=opaque_alpha_variant(pack(words))
    assert patched==pack(words[:-1]+[0x02000001,0x80080800,0xa00000df,0xffff])
    assert report['constant']==223 and not report['coverage_verified']
    commented=[words[0],0x0001fffe,0xdeadbeef]+words[1:]
    assert opaque_alpha_variant(pack(commented))[0].startswith(pack(commented[:-1]))
    for bad in ([0xffff0200]+words[1:],words+[0],words[:-1],
                [words[0],0x000afffe,0xffff],
                [words[0],0x0000001c]+words[1:],
                [words[0],0x02000001,0x800f0800,0xa0e400df,0xffff],
                [words[0],0x02000001,0x800f0800,0xa0e42000,0xffff],
                [words[0],0x02000001,0x800f0000,0x80e40000,0xffff]): reject(bad)
    print('Shader framing/comments/end, untouched original prefix, reserved/dynamic constants and subroutine/output rejection passed.')
    metadata=dict(kind='screen-shader',code_size=len(pack(words)),read_only=True,shader='0x1000',source_target='0x2000',
        counter=12,trace_frame=1,trace_event=0,lut_source=None,
        constants_hex='00'*(224*16),assembly='ps_3_0\n',srgb_write=0,
        samplers=[dict(slot=i,texture=None,srgb=0) for i in range(16)])
    result=screen_packet(metadata,pack(words))
    associated=metadata|dict(samplers=[dict(slot=i,texture='0x3000' if i==0 else None,srgb=0) for i in range(16)],
        texture_sources=[dict(slot=0,texture='0x3000',surface='0x4000',format=21,width=1920,height=1080)])
    assert screen_packet(associated,pack(words))['texture_sources'][0]['width']==1920
    try:screen_packet(associated|dict(texture_sources=associated['texture_sources']*2),pack(words))
    except ValueError:pass
    else:raise AssertionError('duplicate texture association accepted')
    assert not result['color_verified'] and not result['replay_verified']
    vertex=dict(shader='0x3000',code_hex=pack([0xfffe0300]+words[1:]).hex(),
        constants_hex='00'*4096,assembly='vs_3_0\n')
    assert screen_packet(metadata|dict(vertex_program=vertex),pack(words))['vertex_code_sha256']
    for change in [dict(shader='0x0'),dict(constants_hex=''),dict(code_hex=pack(words).hex()),dict(assembly='')]:
        try: screen_packet(metadata|dict(vertex_program=vertex|change),pack(words))
        except ValueError: continue
        raise AssertionError('invalid screen vertex evidence accepted')
    quad=dict(stride=32,index_format=101,vertices_hex='00'*128,
        indices_hex=struct.pack('<6H',0,1,2,2,1,3).hex(),
        declaration_hex=(struct.pack('<HH4B',0,0,3,0,0,0)+struct.pack('<HH4B',255,0,17,0,0,0)).hex())
    assert screen_packet(metadata|dict(vertex_input=quad),pack(words))['vertex_input_sha256']
    for change in [dict(stride=2048),dict(vertices_hex=None),dict(indices_hex=struct.pack('<6H',0,1,2,2,1,4).hex()),
                   dict(declaration_hex='00'*16),dict(index_format=100)]:
        try: screen_packet(metadata|dict(vertex_input=quad|change),pack(words))
        except ValueError: continue
        raise AssertionError('invalid screen quad evidence accepted')
    for change,data in [(dict(read_only=False),pack(words)),(dict(constants_hex=''),pack(words)),
            (dict(srgb_write=2),pack(words)),(dict(samplers=[]),pack(words)),
            (dict(shader='0x0'),pack(words)),(dict(counter=-1),pack(words)),(dict(trace_frame=3),pack(words)),
            (dict(lut_source=dict(slot=2,texture='0x1234',surface='0x5678',format=21,width=256,height=16)),pack(words)),
            ({},pack(words)[:-1]),({},pack([0xfffe0300]+words[1:]))]:
        try: screen_packet(metadata|change,data)
        except ValueError: continue
        raise AssertionError('invalid/promoted screen program accepted')
    print('Read-only screen program, sampler/constant bounds and unsupported replay/color promotion guards passed.')


if __name__=='__main__': main()
