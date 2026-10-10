"""Bounded recent evidence for development source streams; no image history."""
from collections import deque
import math


def body_geometry(native):
    """Retain checked render geometry, without accepting an anatomical foot pivot."""
    origin=native.get('native_absolute_body_origin',[])
    pivot=native.get('projection_pivot',[])
    scale=native.get('pixels_per_world_unit')
    bounds=(native.get('width'),native.get('height'))
    if (len(origin)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6 for v in origin) or
            abs(origin[1])>.001 or any(type(v)!=int or not 1<=v<=1024 for v in bounds) or
            len(pivot)!=2 or any(type(v)!=int or not 0<=v<b for v,b in zip(pivot,bounds)) or
            type(scale) not in (int,float) or not math.isfinite(scale) or not 0<scale<=16):
        raise ValueError('invalid streaming body geometry')
    return dict(native_absolute_body_origin=list(origin),projection_pivot=list(pivot),
        pixels_per_world_unit=scale,width=bounds[0],height=bounds[1],foot_pivot_verified=False)


class RollingAudit:
    def __init__(self):
        self.records=deque(maxlen=64);self.states=deque(maxlen=64)
        self.frames=deque(maxlen=2)
        self.samples=self.frame_count=self.gaps=0
        self.previous_counter=self.initial_frame=None

    def record(self,record,fighters):
        if self.previous_counter is not None and record['before']!=self.previous_counter:self.gaps+=1
        self.previous_counter=record['after'];self.samples+=1
        self.records.append(record);self.states.append(fighters)

    def frame(self,receipt):
        if receipt['request_index']!=self.frame_count:raise ValueError('unordered rolling frame')
        initial=receipt['counter'] if self.initial_frame is None else self.initial_frame
        if ((receipt['counter']-initial)&0xffffffff)!=self.frame_count:
            raise ValueError('rolling frame counter mismatch')
        self.initial_frame=initial;self.frame_count+=1;self.frames.append(receipt)
