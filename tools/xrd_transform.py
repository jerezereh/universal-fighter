"""Bounded native vertex programs/constants; observation does not assign camera semantics."""
import hashlib
import re
import struct


def transform_packet(metadata,data):
    size=metadata.get('bytecode_size')
    if (type(size)!=int or not 8<=size<=65536 or size%4 or len(data)!=size+4096 or
            metadata.get('constants')!=256 or metadata.get('read_only') is not True or
            not isinstance(metadata.get('assembly'),str) or not 1<=len(metadata['assembly'])<=131072 or
            not re.fullmatch('[0-9a-f]{48}',metadata.get('viewport_hex',''))):
        raise ValueError('invalid bounded vertex observation')
    for key,low,high in (('counter',0,0xffffffff),('request_index',0,160),('presentation_index',3,24)):
        if type(metadata.get(key))!=int or not low<=metadata[key]<=high: raise ValueError('invalid transform '+key)
    if struct.unpack_from('<I',data)[0] not in (0xfffe0200,0xfffe0300): raise ValueError('unsupported vertex program')
    viewport=struct.unpack('<4I2f',bytes.fromhex(metadata['viewport_hex']))
    if not (0<=viewport[0]<2048 and 0<=viewport[1]<2048 and 1<=viewport[2]<=2048 and
            1<=viewport[3]<=2048 and 0<=viewport[4]<=viewport[5]<=1): raise ValueError('invalid native viewport')
    return data[:size],data[size:],dict(viewport=list(viewport),
        vertex_program_sha256=hashlib.sha256(data[:size]).hexdigest(),
        vertex_constants_sha256=hashlib.sha256(data[size:]).hexdigest(),transform_semantics_verified=False)


def transform_changes(records):
    import numpy as np
    groups=[]
    for step in sorted({m['request_index'] for m,_,_ in records}):
        items=[(m,c) for m,_,c in records if m['request_index']==step]
        if any(m['counter']!=items[0][0]['counter'] for m,c in items): raise ValueError('counter advanced in transform group')
        changes=[]
        for (a,ca),(b,cb) in zip(items,items[1:]):
            if a['vertex_program_sha256']!=b['vertex_program_sha256']: raise ValueError('vertex program changed in transform group')
            aa=np.frombuffer(ca,dtype='<u4').reshape(256,4);bb=np.frombuffer(cb,dtype='<u4').reshape(256,4)
            indices=np.flatnonzero(np.any(aa!=bb,axis=1)).tolist()
            changes.append(dict(presentations=[a['presentation_index'],b['presentation_index']],
                changed_registers=indices,viewport_changed=a['viewport']!=b['viewport']))
        groups.append(dict(request_index=step,samples=len(items),changes=changes))
    return dict(groups=groups,observations_only=True,transform_semantics_verified=False)
