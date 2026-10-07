"""Authored section signatures and two-frame buffer ambiguity checks; no game assets."""
from xrd_draw import mesh_sections,buffer_candidates


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('invalid identity accepted')


def main():
    gltf=dict(meshes=[dict(primitives=[dict(attributes=dict(POSITION=0),indices=1),dict(attributes=dict(POSITION=2),indices=3)])],
        accessors=[dict(count=20),dict(count=60),dict(count=15),dict(count=45)])
    signatures=mesh_sections(gltf)
    assert signatures==[[4,0,0,35,0,20],[4,0,20,15,60,15]]
    reject(lambda:mesh_sections(gltf|dict(accessors=[dict(count=True)]+gltf['accessors'][1:])))
    reject(lambda:mesh_sections(gltf|dict(accessors=[dict(count=20),dict(count=61)]+gltf['accessors'][2:])))
    def event(method,values): return dict(method=method,values=values,hresult=0)
    events=[event('SetIndices',['0x10000']),event('SetStreamSource',[0,'0x20000',0,12])]+[event('DrawIndexedPrimitive',s) for s in signatures]
    frames=[dict(device='0x30000',events=events) for _ in range(2)]
    result=buffer_candidates(frames,dict(body=signatures))
    assert result['parts']['body']==dict(index_buffer='0x10000',vertex_buffer='0x20000')
    assert not result['actor_identity_verified'] and not result['isolated_rgba']
    reject(lambda:buffer_candidates(frames[:1],dict(body=signatures)))
    reject(lambda:buffer_candidates([frames[0],frames[1]|dict(device='0x40000')],dict(body=signatures)))
    reject(lambda:buffer_candidates([frames[0],frames[1]|dict(events=events[:-1])],dict(body=signatures)))
    duplicate=[event('SetIndices',['0x50000']),event('SetStreamSource',[0,'0x60000',0,12])]+[event('DrawIndexedPrimitive',s) for s in signatures]
    reject(lambda:buffer_candidates([f|dict(events=events+duplicate) for f in frames],dict(body=signatures)))
    reject(lambda:buffer_candidates(frames,dict(body=signatures,head=signatures)))
    print('Section offsets/counts, complete two-frame matching, missing/ambiguous/device-drift rejection and candidate-only status passed.')


if __name__=='__main__': main()
