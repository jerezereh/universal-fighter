"""Blender-only independent glTF skinning oracle for the diagnostic SIGN renderer."""
import json

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree


def check_skin(path, objects):
    gltf = json.loads(path.read_text())
    buffers = [(path.parent/x['uri']).read_bytes() for x in gltf['buffers']]

    def accessor(index):
        item = gltf['accessors'][index]
        view = gltf['bufferViews'][item['bufferView']]
        dtype = {5121: 'u1', 5123: '<u2', 5126: '<f4'}[item['componentType']]
        width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[item['type']]
        size = np.dtype(dtype).itemsize*width
        stride = view.get('byteStride', size)
        start = view.get('byteOffset', 0)+item.get('byteOffset', 0)
        end = start+(item['count']-1)*stride+size
        if 'sparse' in item or stride < size or end > view.get('byteOffset', 0)+view['byteLength']:
            raise ValueError('unsupported/out-of-bounds glTF accessor')
        return np.ndarray((item['count'], width), dtype=dtype, buffer=buffers[view['buffer']],
                          offset=start, strides=(stride, np.dtype(dtype).itemsize)).copy()

    world = {}

    def visit(index, parent):
        if index in world:
            raise ValueError('cyclic/shared skeleton node')
        node = gltf['nodes'][index]
        if 'matrix' in node:
            raise ValueError('expected exported TRS node')
        x, y, z, w = node.get('rotation', [0, 0, 0, 1])
        local = Matrix.LocRotScale(Vector(node.get('translation', [0, 0, 0])),
                                  Quaternion((w, x, y, z)), Vector(node.get('scale', [1, 1, 1])))
        world[index] = parent@local
        for child in node.get('children', []):
            visit(child, world[index])

    for node in gltf['scenes'][gltf.get('scene', 0)]['nodes']:
        visit(node, Matrix.Identity(4))
    skin = gltf['skins'][0]
    inverses = accessor(skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
    transforms = np.array([world[x] for x in skin['joints']], dtype=np.float64)@inverses
    expected = []
    for primitive in gltf['meshes'][0]['primitives']:
        attr = primitive['attributes']
        positions = accessor(attr['POSITION'])
        joints = accessor(attr['JOINTS_0']).astype(np.int64)
        weights = accessor(attr['WEIGHTS_0']).astype(np.float64)
        if not np.isfinite(positions).all() or not np.isfinite(weights).all() or (joints >= len(transforms)).any() or (weights.sum(axis=1) <= 0).any():
            raise ValueError('invalid skin vertices')
        weights /= weights.sum(axis=1, keepdims=True)
        matrices = (transforms[joints]*weights[:, :, None, None]).sum(axis=1)
        homogeneous = np.column_stack((positions, np.ones(len(positions))))
        points = np.einsum('nij,nj->ni', matrices, homogeneous)[:, :3]
        # Blender's glTF coordinate conversion: (X,Y,Z) -> (X,-Z,Y).
        points = points[:, [0, 2, 1]]*np.array([1, -1, 1])
        indices = accessor(primitive['indices']).ravel()
        expected.extend(points[np.unique(indices)])
    if not expected:
        raise ValueError('empty diagnostic mesh')
    tree = KDTree(len(expected))
    for i, point in enumerate(expected):
        tree.insert(point, i)
    tree.balance()
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    actual_points, error = [], 0.0
    for obj in objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            for vertex in mesh.vertices:
                point = evaluated.matrix_world@vertex.co
                error = max(error, tree.find(point)[2])
                actual_points.append(point.copy())
        finally:
            evaluated.to_mesh_clear()
    if not actual_points:
        raise ValueError('missing evaluated mesh')
    reverse = KDTree(len(actual_points))
    for i, point in enumerate(actual_points):
        reverse.insert(point, i)
    reverse.balance()
    for point in expected:
        error = max(error, reverse.find(point)[2])
    if error > .0002:
        raise ValueError(f'glTF/Blender skin disagreement: {error:.6g} m; {len(actual_points)} vertices')
    return {'reference_vertices': len(expected), 'evaluated_vertices': len(actual_points),
            'max_nearest_error_m': error, 'tolerance_m': .0002}
