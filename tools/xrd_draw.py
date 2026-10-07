"""Derive mesh-buffer candidates from local UEViewer section metadata and actual D3D9 calls."""
import re


def mesh_sections(gltf):
    primitives=[p for mesh in gltf['meshes'] for p in mesh['primitives']]
    if not 1<=len(primitives)<=128: raise ValueError('unbounded mesh sections')
    vertices=[];indices=[];accessors=set()
    for p in primitives:
        position=p['attributes']['POSITION']
        if p.get('mode',4)!=4 or position in accessors: raise ValueError('expected separate triangle-list section streams')
        accessors.add(position)
        vc=gltf['accessors'][position]['count'];ic=gltf['accessors'][p['indices']]['count']
        if type(vc)!=int or type(ic)!=int or not 1<=vc<=1000000 or not 3<=ic<=3000000 or ic%3:
            raise ValueError('invalid section count')
        vertices.append(vc);indices.append(ic)
    total=sum(vertices);vstart=istart=0;signatures=[]
    if total>1000000: raise ValueError('unbounded aggregate mesh vertices')
    for vc,ic in zip(vertices,indices):
        signatures.append([4,0,vstart,total-vstart,istart,ic//3])
        vstart+=vc;istart+=ic
    return signatures


def buffer_candidates(frames,parts):
    if len(frames)!=2 or not 1<=len(parts)<=8: raise ValueError('requires two frames and bounded mesh parts')
    devices={f['device'] for f in frames}
    if len(devices)!=1: raise ValueError('source device changed')
    selected={};evidence={}
    for name,signatures in parts.items():
        required={tuple(s) for s in signatures if s[5]>12}
        if len(required)<2: raise ValueError('mesh needs two nontrivial section signatures')
        per_frame=[]
        for frame in frames:
            ib=vb=None;matches={}
            for event in frame['events']:
                if event['hresult']!=0: raise ValueError('failed native draw/binding')
                values=event['values'];method=event['method']
                if method=='SetIndices': ib=values[0]
                elif method=='SetStreamSource' and values[0]==0: vb=values[1]
                elif method=='DrawIndexedPrimitive' and tuple(values) in required:
                    if any(not isinstance(p,str) or not re.fullmatch('0x[0-9a-f]{1,8}',p) or p=='0x0' for p in (ib,vb)):
                        raise ValueError('unknown mesh buffer binding')
                    matches.setdefault((ib,vb),set()).add(tuple(values))
            per_frame.append({pair for pair,seen in matches.items() if seen==required})
        consistent=set.intersection(*per_frame)
        if len(consistent)!=1: raise ValueError('missing/ambiguous mesh buffer: '+name)
        pair=consistent.pop()
        if pair in selected.values(): raise ValueError('mesh parts share an ambiguous buffer identity')
        selected[name]=pair;evidence[name]=dict(signatures=signatures,nontrivial_sections=len(required))
    return dict(device=devices.pop(),parts={name:dict(index_buffer=p[0],vertex_buffer=p[1]) for name,p in selected.items()},
        evidence=evidence,geometry_match_verified=True,actor_identity_verified=False,isolated_rgba=False)
