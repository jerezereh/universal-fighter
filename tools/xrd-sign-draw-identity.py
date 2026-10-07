"""Match local Sol mesh sections to same-session native draw buffers; visual proof still required."""
import argparse
import json
from pathlib import Path

from xrd_draw import mesh_sections,buffer_candidates
from xrd_native import fingerprint,SIGN_HASH
from xrd_render import draw_check

ROOT=Path(__file__).resolve().parent.parent


def derive(folder,meshes):
    receipt=json.loads((folder/'inspection.json').read_text())
    if not receipt.get('controlled_update_step_verified') or receipt['errors'] or not receipt['loaded_code_restored'] or not receipt['render_cleanup']['render_code_restored']:
        raise ValueError('requires a clean bounded same-session draw proof')
    frames=json.loads((folder/'draw-trace.json').read_text());draw_check(frames)
    if not meshes.resolve().is_relative_to((ROOT/'extracted/xrd-sign').resolve()):
        raise ValueError('requires an ignored local SIGN graphics import')
    parts={};hashes={}
    for part,name in dict(body='SOL_body01',head='SOL_head01',weapon='Sol_weapon01').items():
        path=meshes/(name+'.gltf')
        if path.stat().st_size>8<<20: raise ValueError('unbounded mesh metadata')
        hashes[name]=fingerprint(path);parts[part]=mesh_sections(json.loads(path.read_text()))
    result=buffer_candidates(frames,parts)|dict(pid=receipt['pid'],mesh_metadata_hashes=hashes,
        exe_sha256=SIGN_HASH,source_trace=folder.name)
    output=folder/'draw-identity.json';output.write_text(json.dumps(result,indent=2))
    print('Three mesh parts match complete nontrivial section signatures across both frames; visual identity remains unaccepted.')
    print(output)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path);p.add_argument('meshes',type=Path)
    a=p.parse_args();derive(a.trace.resolve(),a.meshes.resolve())
