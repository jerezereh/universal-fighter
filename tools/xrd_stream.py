"""Bounded recent evidence for development source streams; no image history."""
from collections import deque


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
