"""Authored malformed animation checks and optional local Sol rig/metadata linkage."""
import copy
import json
from pathlib import Path
import struct

from xrd_animation import array, diagnostic_scales, properties, psa, posed_gltf, sample, scale_tracks, object_properties
from xrd_package import Reader, lzo_decoder, package


def rejects(function, value):
    try:
        function(value)
    except (ValueError, UnicodeError):
        return
    raise AssertionError('malformed animation accepted')


def chunk(tag, size, data):
    return struct.pack('<20s3i', tag.encode(), 0, size, len(data)//size if size else 0)+data


bones = ['root', 'leaf', 'extra']
info = struct.pack('<64s64s4i3f3i', b'Authored', b'', 3, 0, 0, 6, 0, 2, 60, 0, 0, 2)
keys = struct.pack('<8f', 3, 4, 5, 0, 0, 0, 1, 1)*6
data = chunk('ANIMHEAD', 0, b'')+chunk('BONENAMES', 120, b''.join(struct.pack('<64s56x', x.encode()) for x in bones))
data += chunk('ANIMINFO', 168, info)+chunk('ANIMKEYS', 32, keys)+chunk('SCALEKEYS', 16, b'')
animation = psa(data)
gltf = {'skins': [{'joints': [0, 1]}], 'nodes': [{'name': 'root'}, {'name': 'leaf'}]}
posed = posed_gltf(copy.deepcopy(gltf), animation, 'Authored', 0)
assert posed['nodes'][1]['translation'] == [.03, .05, -.04]
assert posed['nodes'][0]['rotation'] == [0, 0, 0, -1]  # Equivalent identity after PSA mirror undo.
assert len(sample(animation, 'Authored', 1)) == 3
rejects(psa, data[:-1])
rejects(psa, data+chunk('ANIMKEYS', 32, keys))
rejects(lambda x: sample(animation, 'Authored', x), 2)
bad = copy.deepcopy(gltf); bad['nodes'][1]['name'] = 'missing'
rejects(lambda x: posed_gltf(x, animation, 'Authored', 0), bad)
bad = data.replace(keys, struct.pack('<8f', float('nan'), 4, 5, 0, 0, 0, 1, 1)*6)
rejects(lambda x: sample(psa(x), 'Authored', 0), bad)
bad_info = bytearray(info); struct.pack_into('<i', bad_info, 160, 1)
rejects(psa, data.replace(info, bad_info))
rejects(lambda x: array(x, lambda r: r.integer()), struct.pack('<i', -1))
rejects(lambda x: array(x, lambda r: r.integer()), struct.pack('<2i', 0, 1))
names = ['None', 'flag', 'BoolProperty']
tags = struct.pack('<6iB2i', 1, 0, 2, 0, 0, 0, 1, 0, 0)
assert properties(Reader(tags), names)['flag', 0]['value'] is True
rejects(lambda x: properties(Reader(x), names), tags[:20])
bad = bytearray(tags); bad[24] = 2
rejects(lambda x: properties(Reader(x), names), bad)
tracks = {'leaf': [{'time': 0, 'scale': [1, 2, 3]}, {'time': .25, 'scale': [.1, .2, .3]}]}
assert diagnostic_scales(posed, tracks, .25) == []
assert posed['nodes'][1]['scale'] == [.1, .3, .2]
print('Authored PSA partition/name binding/basis/bounds/metadata checks passed')

root = Path(__file__).resolve().parent.parent
folders = sorted((root/'extracted/xrd-sign').glob('*/inspection.json'))
for receipt in reversed(folders):
    folder = receipt.parent
    source = folder/'SOL_ANM_BTL_01_SF.upk.dec'
    if not source.is_file():
        continue
    virtual, names, exports = package(source.read_bytes(), lzo_decoder(root/'local-cache/xrd-tools/lzo.dll'))
    for part, mesh, expected_count, bones_count in [('Body', 'SOL_body01', 23, 219), ('Head', 'SOL_head01', 2, 201), ('Weapon', 'Sol_weapon01', 2, 48)]:
        anim_file = folder/f'graphics/SOL_ANM_BTL_01_SF/AnimSet/AS_SOL_BTL_{part}_01.psa'
        animation = psa(anim_file.read_bytes())
        assert len(animation['bones']) == bones_count and animation['clips']['sol200']['frames'] == 31
        gltf = json.loads((folder/f'graphics/SOL_MSH_01_SF/SkeletalMesh3/{mesh}.gltf').read_text())
        for frame in (0, 5, 10, 15, 20, 25, 30):
            posed_gltf(copy.deepcopy(gltf), animation, 'sol200', frame)
        entry = next(x for x in exports if x['class'] == 'AnimSet' and x['name'] == f'AS_SOL_BTL_{part}_01')
        refs = array(object_properties(virtual, names, entry)['Sequences', 0]['value'], lambda r: r.integer())
        sequence = next(p for p in [object_properties(virtual, names, exports[x-1]) for x in refs] if p['SequenceName', 0]['value'] == 'sol200')
        tracks = scale_tracks(virtual, names, exports, sequence)
        assert len(tracks) == expected_count
        absent = diagnostic_scales(gltf, tracks, 0)
        assert absent == (['wep_base_high'] if part == 'Weapon' else [])
        if part == 'Weapon':
            node = next(x for x in gltf['nodes'] if x['name'] == 'wep_base_obake')
            assert max(node['scale']) < 1e-10
    print('Local Sol body/head/weapon sample and 27 scale-controller link checks passed')
    break
else:
    print('Local stock check skipped: run xrd-sign-import.py --graphics first')
