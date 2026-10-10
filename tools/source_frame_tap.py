"""Development source observations and optional steps, not the playable guest protocol."""
import base64
import json
import math
from pathlib import Path
import re
import secrets
import select
import socket
import struct
import time

LIMIT=8<<20


def read_exact(conn,size):
    result=bytearray()
    while len(result)<size:
        part=conn.recv(size-len(result))
        if not part:raise EOFError('frame tap disconnected')
        result.extend(part)
    return bytes(result)


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate transport field')
        result[key]=value
    return result


def read_packet(conn,limit=LIMIT):
    size=struct.unpack('>I',read_exact(conn,4))[0]
    if not 0<size<=limit:raise ValueError('transport packet exceeds bounds')
    def reject_constant(value):raise ValueError('nonfinite transport value')
    def finite_float(value):
        result=float(value)
        if not math.isfinite(result):reject_constant(value)
        return result
    return json.loads(read_exact(conn,size),object_pairs_hook=unique_object,parse_constant=reject_constant,parse_float=finite_float)


def write_packet(conn,packet):
    data=json.dumps(packet,separators=(',',':'),allow_nan=False).encode()
    if not 0<len(data)<=LIMIT:raise ValueError('transport packet exceeds bounds')
    conn.sendall(struct.pack('>I',len(data))+data)


def identity(packet,ready,operation,sequence=None):
    expected=dict(schema=1,session=ready['session'],game=ready['game'],operation=operation)
    if sequence is not None:expected['sequence']=sequence
    if (type(packet)!=dict or set(packet)!=set(expected) or packet!=expected or
        type(packet.get('schema'))!=int or sequence is not None and type(packet.get('sequence'))!=int):
        raise ValueError('frame tap identity/operation/sequence mismatch')


def ready_address(ready):
    if (type(ready)!=dict or set(ready)!={'schema','kind','session','game','address'} or
        type(ready['schema'])!=int or ready['schema']!=1 or ready['kind'] not in ('source-frame-tap','source-control-tap') or
        type(ready['game'])!=str or not 1<=len(ready['game'])<=128 or
        not isinstance(ready['session'],str) or not re.fullmatch('[0-9a-f]{32}',ready['session']) or type(ready['address'])!=str):
        raise ValueError('invalid frame tap ready receipt')
    host,port=ready['address'].rsplit(':',1)
    if host!='127.0.0.1' or not port.isdecimal() or not 1<=int(port)<=65535:
        raise ValueError('frame tap requires numeric IPv4 loopback')
    return host,int(port)


def frame_pixels(packet,ready,sequence,initial_counter=None):
    keys={'schema','kind','session','game','sequence','counter','request_index','capabilities',
        'units_verified','pivot_verified','atomic_native_frame','readiness_candidate','state','image'}
    if (type(packet)!=dict or set(packet)!=keys or packet.get('schema')!=1 or type(packet.get('schema'))!=int or
        packet.get('kind')!='source-observation' or packet.get('session')!=ready['session'] or
        packet.get('game')!=ready['game'] or type(packet.get('sequence'))!=int or packet['sequence']!=sequence or
        packet.get('capabilities')!=[] or any(packet.get(k) is not False for k in
        ('units_verified','pivot_verified','atomic_native_frame')) or packet.get('readiness_candidate') is not True):
        raise ValueError('invalid or promoted source observation')
    counter,index=packet.get('counter'),packet.get('request_index')
    if (type(counter)!=int or not 0<=counter<=0xffffffff or type(index)!=int or index!=sequence-1 or
        initial_counter is not None and ((counter-initial_counter)&0xffffffff)!=index or
        type(packet.get('state'))!=list or not 1<=len(packet['state'])<=64):
        raise ValueError('source observation counter/state mismatch')
    image=packet.get('image',{})
    if type(image)!=dict or set(image)!={'Width','Height','Pivot','RGBA'}:raise ValueError('invalid observation image')
    if any(type(image[k])!=int or not 1<=image[k]<=1024 for k in ('Width','Height')):
        raise ValueError('invalid observation dimensions')
    if (type(image['Pivot'])!=list or len(image['Pivot'])!=2 or
        any(type(v)!=int or not 0<=v<bound for v,bound in zip(image['Pivot'],(image['Width'],image['Height'])))):
        raise ValueError('invalid observation pivot')
    if type(image['RGBA'])!=str:raise ValueError('invalid encoded observation pixels')
    pixels=base64.b64decode(image['RGBA'],validate=True)
    if len(pixels)!=image['Width']*image['Height']*4:raise ValueError('incomplete observation pixels')
    return pixels


class FrameTap:
    def __init__(self,path,game,control=False):
        if type(control)!=bool:raise ValueError('invalid source control mode')
        self.listener=socket.socket();self.conn=None;self.sequence=0;self.bytes_sent=0;self.max_ack_ms=0
        self.control=control;self.control_sequence=0;self.controls_received=0;self.last_counter=None
        self.listener.bind(('127.0.0.1',0));self.listener.listen(1);self.listener.settimeout(.5)
        self.ready=dict(schema=1,kind='source-control-tap' if control else 'source-frame-tap',session=secrets.token_hex(16),game=game,
            address='127.0.0.1:'+str(self.listener.getsockname()[1]))
        try:
            ready_address(self.ready)
            Path(path).write_text(json.dumps(self.ready,indent=2))
        except Exception:
            self.close();raise

    def await_subscriber(self,timeout=30):
        self.listener.settimeout(timeout)
        self.conn,_=self.listener.accept();self.conn.settimeout(.5)
        identity(read_packet(self.conn,16384),self.ready,'subscribe')
        self.listener.close() # One subscriber; never replace a lost controller.

    def publish(self,metadata,pixels,state):
        if self.conn is None:self.await_subscriber(.5)
        rgba=bytearray(len(pixels))
        for target,source in enumerate((2,1,0,3)):rgba[target::4]=pixels[source::4]
        sequence=self.sequence+1
        packet=dict(schema=1,kind='source-observation',session=self.ready['session'],game=self.ready['game'],
            sequence=sequence,counter=metadata['counter'],request_index=metadata['request_index'],
            capabilities=[],units_verified=False,pivot_verified=False,atomic_native_frame=False,readiness_candidate=True,
            state=state,image=dict(Width=metadata['width'],Height=metadata['height'],Pivot=metadata['projection_pivot'],
                RGBA=base64.b64encode(rgba).decode()))
        frame_pixels(packet,self.ready,sequence)
        started=time.perf_counter();write_packet(self.conn,packet)
        identity(read_packet(self.conn,16384),self.ready,'ack',sequence)
        self.max_ack_ms=max(self.max_ack_ms,(time.perf_counter()-started)*1000)
        self.sequence=sequence;self.bytes_sent+=len(rgba)
        self.last_counter=metadata['counter']

    def poll_step(self):
        if not self.control:raise ValueError('observation tap does not accept steps')
        if not select.select([self.conn],[],[],0)[0]:return None
        packet=read_packet(self.conn,16384)
        fields={'schema','session','game','operation','sequence','counter','input','accept_input'}
        if type(packet)!=dict or set(packet)!=fields:raise ValueError('invalid source control fields')
        identity({k:v for k,v in packet.items() if k not in ('counter','input','accept_input')},self.ready,'step',self.sequence)
        if (self.control_sequence==self.sequence or type(packet['counter'])!=int or packet['counter']!=self.last_counter or
            type(packet['accept_input'])!=bool or type(packet['input'])!=dict or len(packet['input'])>10 or
            any(type(k)!=str or not 1<=len(k)<=32 or type(v)!=bool for k,v in packet['input'].items())):
            raise ValueError('stale or invalid source step')
        self.control_sequence=self.sequence
        self.controls_received+=1
        return packet

    def close(self):
        if self.conn is not None:self.conn.close()
        self.listener.close()

    def receipt(self):
        return dict(frames_acknowledged=self.sequence,rgba_bytes=self.bytes_sent,max_ack_ms=self.max_ack_ms,
            source_capabilities_enabled=False,playable_guest_protocol=False,request_driven=self.control,
            controls_received=self.controls_received)
