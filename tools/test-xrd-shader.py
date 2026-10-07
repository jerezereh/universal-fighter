"""Authored Shader Model 3 framing and alpha-variant guards; no game bytecode."""
import struct
from xrd_shader import opaque_alpha_variant


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


if __name__=='__main__': main()
