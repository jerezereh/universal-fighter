"""Exercise retained evidence bounds and gaps that predate the retained window."""
from xrd_stream import RollingAudit

audit=RollingAudit()
for index in range(10000):
    counter=(0xffffff00+index)&0xffffffff
    audit.record(dict(before=counter if index!=2 else counter+1,after=(counter+1)&0xffffffff),[index])
    audit.frame(dict(request_index=index,counter=counter))
assert audit.samples==audit.frame_count==10000 and audit.gaps==1
assert len(audit.records)==len(audit.states)==64 and len(audit.frames)==2
assert audit.frames[-1]['request_index']==9999 and audit.states[0]==[9936]
for receipt in (dict(request_index=9999,counter=0),dict(request_index=10000,counter=0)):
    try:audit.frame(receipt)
    except ValueError:pass
    else:raise AssertionError('accepted duplicate or mismatched counter')
assert audit.frame_count==10000 and len(audit.frames)==2
print('Rolling audit: 10000 samples/frames, bounded retention, wrap, old-gap preservation and invalid-frame rejection passed')
