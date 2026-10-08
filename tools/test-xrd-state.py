"""Authored state-reader and scalar-getter checks; no source game required."""
import struct

from xrd_state import assembly_rows, getter_fields, global_operand, observe


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('accepted invalid state')


class Memory:
    def __init__(self,segments): self.segments=segments
    def read(self,address,size):
        for base,data in self.segments.items():
            if base<=address and address+size<=base+len(data): return bytes(data[address-base:address-base+size])
        raise ValueError('out-of-bounds authored read')


def fixture():
    module=bytearray(16);struct.pack_into('<I',module,4,0x20000)
    engine=bytearray(32);struct.pack_into('<i2I',engine,0,2,0x30000,0x40000)
    fields=dict(count=0,slots=4,x=0,y=4,facing=8,boxes=12,hurt_count=16,hit_count=20,scale_x=24,scale_y=28,rotation=36)
    body=bytearray(0x2600);struct.pack_into('<iiiIiiiiI',body,0,-250,0,0,0x50000,1,0,1000,1000,0)
    body[80:90]=b'sol000_00\0';body[96:108]=b'CmnActStand\0'
    other=bytearray(body);struct.pack_into('<iiiI',other,0,250,0,1,0x60000)
    boxes=bytearray(struct.pack('<I4f',0,-15,-80,30,80))
    memory=Memory({0x10000:module,0x20000:engine,0x30000:body,0x40000:other,0x50000:boxes,0x60000:bytearray(boxes)})
    profile=dict(module_base=0x10000,engine_global_rva=4,fields=fields,parents=[32])
    return memory,profile


def main():
    text='''
       1000: 56                    push esi
       1001: 8b f1                 mov esi,ecx
       1003: 8b 8e 34 12 00 00     mov ecx,DWORD PTR [esi+0x1234]
       1009: 8b 86 44 12 00 00     mov eax,DWORD PTR [esi+0x1244]
       100f: 8b 86 44 12 00 00     mov eax,DWORD PTR [esi+0x1244]
       1015: c3                    ret
    '''
    rows=assembly_rows(text);raw,parents=getter_fields(rows)
    assert raw==0x1244 and parents==[0x1234] and rows[0]['address']==0x1000
    reject(lambda:getter_fields(rows[:4]))
    code=b'\x8b\x0d'+struct.pack('<I',0x10200)
    section=dict(rva=0x200,virtual_size=0x100,size=0x100,flags=0x80000000)
    assert global_operand(code,2,0x10000,0x1000,[section])==0x200
    reject(lambda:global_operand(b'\x90\x90'+code[2:],2,0x10000,0x1000,[section]))
    reject(lambda:global_operand(code,2,0x20000,0x1000,[section]))
    memory,p=fixture();record=observe(memory,p)
    assert record['fighters'][0]['x_raw']==-250 and record['fighters'][1]['facing_left']
    assert record['fighters'][0]['pose_candidates'][0]['value']=='sol000_00'
    assert record['fighters'][0]['boxes']==[[0,-15,-80,30,80]] and not record['atomic_native_frame']
    p['scalar_fields']={'authored':24};record=observe(memory,p)
    assert record['fighters'][0]['scalar_observations']=={'authored':1000}
    memory.segments[0x40000][80:90]=b'kyk000_00\0'
    memory.segments[0x40000][79]=ord('a')
    assert observe(memory,p)['fighters'][1]['pose_candidates'][0]['value']=='kyk000_00'
    for field,value in (('facing',2),('hurt_count',65),('hit_count',-1)):
        m,p=fixture();struct.pack_into('<i',m.segments[0x30000],p['fields'][field],value)
        reject(lambda:observe(m,p))
    m,p=fixture();struct.pack_into('<I',m.segments[0x30000],32,1);reject(lambda:observe(m,p))
    m,p=fixture();struct.pack_into('<f',m.segments[0x50000],4,float('nan'));reject(lambda:observe(m,p))
    m,p=fixture();struct.pack_into('<I',m.segments[0x20000],8,0x30000);reject(lambda:observe(m,p))
    print('Authored getter/operand derivation, raw observation, bounds/parent/NaN/slot rejection and unsynchronized status passed.')


if __name__=='__main__': main()

# Clock reads must keep one engine identity, including across the last read.
from unittest.mock import patch
from xrd_state import read_clock
class ClockMemory:
    def __init__(self,values,change_after=99): self.values=iter(values);self.roots=0;self.change_after=change_after
    def read(self,address,size):
        assert size==4
        if address==0x10020:
            self.roots+=1;value=0x20000 if self.roots<=self.change_after else 0
        else:
            assert address==0x2001c;value=next(self.values)
        return struct.pack('<I',value)
if __name__=='__main__':
    with patch('xrd_state.time.sleep',lambda _:None):
        p=dict(module_base=0x10000,engine_global_rva=0x20);candidate=dict(counter_field=0x18)
        assert read_clock(ClockMemory([0xfffffffe,0xffffffff,0,1,2,3]),p,candidate)['advancing']
        assert read_clock(ClockMemory([7]*6),p,candidate)['paused']
        for change in (0,1,7): reject(lambda:read_clock(ClockMemory([7]*6,change),p,candidate))
        for field in (True,0,-4,3,4<<20): reject(lambda:read_clock(ClockMemory([7]*6),p,dict(counter_field=field)))
    print('Read-only counter bounds, wrap and initial/intermediate/final source engine changes checked.')
