"""Run with Blender --background --factory-startup --python tools/test-xrd-gltf.py.

An authored triangle proves pose transport and deliberately breaks it to check rejection.
"""
import json
from pathlib import Path
import struct
import sys
import tempfile

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xrd_gltf_check import check_skin

root = Path(__file__).resolve().parent.parent
fixture_root = root/'local-cache/gltf-checks'
fixture_root.mkdir(parents=True, exist_ok=True)
folder = Path(tempfile.mkdtemp(dir=fixture_root))
gltf = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
        'nodes': [{'mesh': 0, 'skin': 0, 'children': [1]}, {'name': 'AuthoredJoint', 'translation': [1, 0, 0]}],
        'skins': [{'joints': [1], 'skeleton': 1, 'inverseBindMatrices': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 1, 'JOINTS_0': 2, 'WEIGHTS_0': 3}, 'indices': 4}]}],
        'accessors': [], 'bufferViews': []}
blob = bytearray()
for kind, component, count, fmt, values in [
        ('MAT4', 5126, 1, '16f', [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
        ('VEC3', 5126, 3, '9f', [0, 0, 0, 0, 1, 0, 0, 0, 1]),
        ('VEC4', 5123, 3, '12H', [0]*12),
        ('VEC4', 5126, 3, '12f', [1, 0, 0, 0]*3),
        ('SCALAR', 5123, 3, '3H', [0, 1, 2])]:
    raw = struct.pack('<'+fmt, *values)
    index = len(gltf['bufferViews'])
    gltf['bufferViews'].append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': len(raw)})
    gltf['accessors'].append({'bufferView': index, 'componentType': component, 'count': count, 'type': kind})
    blob.extend(raw)
    blob.extend(b'\0'*(-len(blob)%4))
gltf['accessors'][1].update(min=[0, 0, 0], max=[0, 1, 1])
gltf['buffers'] = [{'uri': 'authored.bin', 'byteLength': len(blob)}]
(folder/'authored.bin').write_bytes(blob)
path = folder/'authored.gltf'
path.write_text(json.dumps(gltf))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(path))
objects = list(bpy.context.selected_objects)
result = check_skin(path, objects)
assert result['evaluated_vertices'] == 3 and result['max_nearest_error_m'] < 1e-6
obj = next(x for x in objects if x.type == 'MESH')
obj.location.x += .05
try:
    check_skin(path, objects)
except ValueError as error:
    assert 'skin disagreement' in str(error)
else:
    raise AssertionError('wrong renderer pose was accepted')
obj.location.x -= .05
obj.data.vertices[0].co.x += .05
try:
    check_skin(path, objects)
except ValueError as error:
    assert 'skin disagreement' in str(error)
else:
    raise AssertionError('wrong renderer geometry was accepted')
print('Authored glTF translated skin, wrong transform and wrong geometry checks passed')
