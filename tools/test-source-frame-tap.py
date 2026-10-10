"""Real loopback framing, generic game identity, raw color preservation and rejection."""
import base64
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading

from source_frame_tap import FrameTap,ready_address,read_packet,write_packet,frame_pixels,identity


def reject(action):
    try:action()
    except (ValueError,EOFError):return
    raise AssertionError('accepted invalid tap packet')


with tempfile.TemporaryDirectory() as folder:
    for game in ('authored-first','authored-second'):
        tap=FrameTap(Path(folder)/'ready.json',game);errors=[]
        def publish():
            try:tap.publish(dict(counter=0xffffffff,request_index=0,width=1,height=1,projection_pivot=[0,0]),bytes([3,2,1,255]),[{'x_raw':7}])
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=publish);thread.start()
        with socket.create_connection(ready_address(tap.ready),1) as conn:
            conn.settimeout(1)
            write_packet(conn,dict(schema=1,session=tap.ready['session'],game=game,operation='subscribe'))
            packet=read_packet(conn)
            assert frame_pixels(packet,tap.ready,1)==bytes([1,2,3,255])
            assert packet['state']==[{'x_raw':7}]
            for change in (dict(game='wrong'),dict(session='0'*32),dict(sequence=True),dict(capabilities=['host-step']),dict(units_verified=True),dict(extra=1)):
                reject(lambda:frame_pixels(packet|change,tap.ready,1))
            reject(lambda:frame_pixels(packet,tap.ready,2))
            write_packet(conn,dict(schema=1,session=tap.ready['session'],game=game,operation='ack',sequence=1))
        thread.join(2);assert not thread.is_alive() and not errors and tap.sequence==1
        tap.close()
        reject(lambda:identity(dict(schema=1,session=tap.ready['session'],game=game,operation='step'),tap.ready,'ack',1))
        reject(lambda:ready_address(tap.ready|dict(address='0.0.0.0:1')))
    # Fragments arrive through normal TCP reads; reject lengths before reading their payload.
    left,right=socket.socketpair()
    with left,right:
        left.sendall(struct.pack('>I',0));reject(lambda:read_packet(right))
        left.sendall(struct.pack('>I',(8<<20)+1));reject(lambda:read_packet(right))
        raw=b'{"schema":1,"schema":2}'
        left.sendall(struct.pack('>I',len(raw))+raw);reject(lambda:read_packet(right))
        raw=b'{"state":1e309}'
        left.sendall(struct.pack('>I',len(raw))+raw);reject(lambda:read_packet(right))
        left.shutdown(socket.SHUT_WR);reject(lambda:read_packet(right))
print('Source frame tap: two games, loopback RGBA/state, nonce/sequence/capability/size/duplicate/EOF checks passed')
