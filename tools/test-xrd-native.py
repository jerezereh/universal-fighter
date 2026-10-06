"""Authored PE/signature checks and own-process read-only Windows API oracle."""
import ctypes
import os
from pathlib import Path
import struct
import sys

from xrd_native import MAX_IMAGE, PE, ReadOnlyProcess, legacy_patterns, scan_patterns


def fixture():
    data = bytearray(2048)
    data[:2]=b'MZ'; struct.pack_into('<I',data,60,128)
    data[128:132]=b'PE\0\0'; struct.pack_into('<HH',data,132,0x14c,1)
    struct.pack_into('<H',data,148,224)
    optional=152
    struct.pack_into('<H',data,optional,0x10b)
    struct.pack_into('<I',data,optional+16,0x1000)
    struct.pack_into('<I',data,optional+28,0x400000)
    struct.pack_into('<I',data,optional+56,0x2000)
    section=optional+224
    data[section:section+8]=b'.text\0\0\0'
    struct.pack_into('<4I',data,section+8,512,0x1000,512,512)
    struct.pack_into('<I',data,section+36,0x60000020)
    return data


def reject(action):
    try:
        action()
    except (ValueError,OSError):
        return
    raise AssertionError('accepted invalid input')


def main():
    data=fixture(); pe=PE(data)
    assert pe.base==0x400000 and len(pe.executable_sections())==1
    for offset,fmt,value in ((60,'I',MAX_IMAGE),(132,'H',0x8664),(152,'H',0x20b),
                             (208,'I',MAX_IMAGE+1),(396,'I',2048)):
        bad=bytearray(data); struct.pack_into('<'+fmt,bad,offset,value)
        reject(lambda:PE(bad))
    source=r'''/* disabled = sigscan("GuiltyGearXrd.exe", "\xCC", "x"); */
    sample = (thing)(sigscan("GuiltyGearXrd.exe", "\xAA\x00\xBB", "x?x") - 1);
    other = sigscan("GuiltyGearXrd.exe", "\xCC\xDD", "xx");'''
    patterns=legacy_patterns(source)
    assert [p['name'] for p in patterns]==['sample','other']
    s=pe.executable_sections()[0]
    rows=scan_patterns([(s,b'\0\xAA\x12\xBB\0\xCC\xDD')],patterns)
    assert all(r['unique'] for r in rows) and rows[0]['matches'][0]['candidate_rva']==0x1000
    assert not any(r['validated_semantics'] for r in rows)
    rows=scan_patterns([(s,b'\0\xAA\x12\xBB\0\xAA\x34\xBB')],patterns)
    assert not rows[0]['unique'] and len(rows[0]['matches'])==2 and not rows[1]['matches']
    overlap=scan_patterns([(s,b'AAA')],[dict(name='overlap',data=b'AA',mask='xx',delta=0)])
    assert len(overlap[0]['matches'])==2 and not overlap[0]['unique']
    reject(lambda:legacy_patterns(source+source))
    reject(lambda:scan_patterns([(s,b'\xAA\x12\xBB')],patterns))
    print('PE bounds, reference parsing, unique/ambiguous/missing signatures and candidate-only status passed.')
    if os.name=='nt':
        buffer=ctypes.create_string_buffer(b'authored-read-only-oracle')
        with ReadOnlyProcess(os.getpid(),sys.executable) as process:
            assert process.read(ctypes.addressof(buffer),ctypes.sizeof(buffer))==buffer.raw
            base,size=process.module_base()
            assert base and size>0 and process.read(base,2)==b'MZ'
            reject(lambda:process.read(1,16))
            reject(lambda:process.read(base,MAX_IMAGE+1))
        reject(lambda:ReadOnlyProcess(os.getpid(),Path('not-the-process.exe')))
        print('Own-process VM_READ, module enumeration, identity guard and bad-read rejection passed.')


if __name__=='__main__':
    main()
