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
        constants_hex='00'*(224*16),assembly='ps_3_0\n',srgb_write=0,
        samplers=[dict(slot=i,texture=None,srgb=0) for i in range(16)])
    result=screen_packet(metadata,pack(words))
    assert not result['color_verified'] and not result['replay_verified']
    for change,data in [(dict(read_only=False),pack(words)),(dict(constants_hex=''),pack(words)),
            (dict(srgb_write=2),pack(words)),(dict(samplers=[]),pack(words)),
            (dict(shader='0x0'),pack(words)),({},pack(words)[:-1]),({},pack([0xfffe0300]+words[1:]))]:
        try: screen_packet(metadata|change,data)
        except ValueError: continue
        raise AssertionError('invalid/promoted screen program accepted')
    print('Read-only screen program, sampler/constant bounds and unsupported replay/color promotion guards passed.')


if __name__=='__main__': main()
