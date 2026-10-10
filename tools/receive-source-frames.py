"""Validate a read-only source frame tap from any game; retain only hashes/last counter."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time

from source_frame_tap import ready_address,read_packet,write_packet,frame_pixels
from xrd_input import input_plan


def receive(path,frames,report,plan=None,pause_after=5,pause_seconds=0):
    ready=json.loads(path.read_text());address=ready_address(ready)
    result=dict(passed=False,frames=0,game=ready['game'],capabilities=[],playable_guest_protocol=False)
    initial=None
    if (ready['kind']=='source-control-tap')!=(plan is not None):raise ValueError('control plan/tap mode mismatch')
    if plan is not None and len(plan)!=frames-1:raise ValueError('control plan frame count mismatch')
    try:
        with socket.create_connection(address,5) as conn:
            conn.settimeout(30) # Initial native readiness includes the guarded thirteen-second hold.
            write_packet(conn,dict(schema=1,session=ready['session'],game=ready['game'],operation='subscribe'))
            for sequence in range(1,frames+1):
                packet=read_packet(conn);pixels=frame_pixels(packet,ready,sequence,initial)
                if initial is None:initial=packet['counter']
                result.update(frames=sequence,last_counter=packet['counter'],last_rgba_sha256=hashlib.sha256(pixels).hexdigest())
                write_packet(conn,dict(schema=1,session=ready['session'],game=ready['game'],operation='ack',sequence=sequence))
                if plan is not None and sequence<frames:
                    if sequence==pause_after:
                        result['pause_counter']=packet['counter'];result['pause_seconds']=pause_seconds
                        time.sleep(pause_seconds)
                    request=plan[sequence-1]
                    write_packet(conn,dict(schema=1,session=ready['session'],game=ready['game'],operation='step',
                        sequence=sequence,counter=packet['counter'],input=request['input'],accept_input=request['accept_input']))
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
    parser.add_argument('--input-plan',type=Path)
    parser.add_argument('--pause-after',type=int,default=5)
    parser.add_argument('--pause-seconds',type=float,default=0)
    args=parser.parse_args()
    if not 1<=args.frames<=10000:parser.error('frames must be 1..10000')
    if not 0<=args.pause_seconds<=5 or args.input_plan and not 1<=args.pause_after<args.frames:parser.error('invalid bounded pause')
    plan=input_plan(json.loads(args.input_plan.read_text()),args.frames-1) if args.input_plan else None
    receive(args.ready,args.frames,args.report,plan,args.pause_after,args.pause_seconds)
