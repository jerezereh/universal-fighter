"""Validate a read-only source frame tap from any game; retain only hashes/last counter."""
import argparse
import hashlib
import json
from pathlib import Path
import socket

from source_frame_tap import ready_address,read_packet,write_packet,frame_pixels


def receive(path,frames,report):
    ready=json.loads(path.read_text());address=ready_address(ready)
    result=dict(passed=False,frames=0,game=ready['game'],capabilities=[],playable_guest_protocol=False)
    initial=None
    try:
        with socket.create_connection(address,5) as conn:
            conn.settimeout(30) # Initial native readiness includes the guarded thirteen-second hold.
            write_packet(conn,dict(schema=1,session=ready['session'],game=ready['game'],operation='subscribe'))
            for sequence in range(1,frames+1):
                packet=read_packet(conn);pixels=frame_pixels(packet,ready,sequence,initial)
                if initial is None:initial=packet['counter']
                result.update(frames=sequence,last_counter=packet['counter'],last_rgba_sha256=hashlib.sha256(pixels).hexdigest())
                write_packet(conn,dict(schema=1,session=ready['session'],game=ready['game'],operation='ack',sequence=sequence))
            result['passed']=True
    except Exception as error:
        result['error']=repr(error);raise
    finally:report.write_text(json.dumps(result,indent=2))
    print('Source frame transport:',result,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ready',type=Path);parser.add_argument('--frames',type=int,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.frames<=10000:parser.error('frames must be 1..10000')
    receive(args.ready,args.frames,args.report)
