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
    tap=FrameTap(Path(folder)/'control.json','authored-control',True)
    server,client=socket.socketpair();tap.conn=server;tap.sequence=1;tap.last_counter=123
    request=dict(schema=1,session=tap.ready['session'],game=tap.ready['game'],operation='step',
        sequence=1,counter=123,input={'left':True},accept_input=True)
    with client:
        assert tap.poll_step() is None # Holding without requests grants nothing.
        for change in (dict(counter=122),dict(sequence=0),dict(accept_input=1),dict(input={'left':1}),dict(extra=1)):
            write_packet(client,request|change);reject(tap.poll_step)
        assert tap.control_sequence==0
        write_packet(client,request);assert tap.poll_step()==request
        write_packet(client,request);reject(tap.poll_step) # No duplicate credit at the same ready frame.
        assert tap.control_sequence==tap.controls_received==1
        tap.sequence=2;tap.last_counter=124
        write_packet(client,request|dict(sequence=2,counter=124,input={},accept_input=False))
        assert tap.poll_step()['accept_input'] is False
        assert tap.controls_received==2
    reject(tap.poll_step);tap.close()
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
