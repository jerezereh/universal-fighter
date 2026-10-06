"""Blender-only base-color sample renderer; invoked by xrd-sign-poses.py."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xrd_gltf_check import check_skin

folder = Path(sys.argv[sys.argv.index('--')+1])
report = json.loads((folder/'preview.json').read_text())
checks = {}
for frame in report['frames']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for part, data in report['parts'].items():
        bpy.ops.import_scene.gltf(filepath=str(folder/f'{part}-{frame}.gltf'))
        imported = list(bpy.context.selected_objects)
        checks[f'{part}-{frame}'] = check_skin(folder/f'{part}-{frame}.gltf', imported)
        image = bpy.data.images.load(data['texture'], check_existing=True)
        for obj in bpy.context.selected_objects:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                mat = slot.material
                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                nodes.clear()
                texture = nodes.new('ShaderNodeTexImage')
                texture.image = image
                uv = nodes.new('ShaderNodeUVMap')
                uv.uv_map = obj.data.uv_layers[0].name
                emission = nodes.new('ShaderNodeEmission')
                output = nodes.new('ShaderNodeOutputMaterial')
                mat.node_tree.links.new(texture.outputs['Color'], emission.inputs['Color'])
                mat.node_tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
                mat.node_tree.links.new(emission.outputs[0], output.inputs['Surface'])
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 1  # Base-color emission preview; no light transport needs sampling.
    scene.render.film_transparent = True
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    bpy.ops.object.camera_add(location=(0, -8, 1))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 1))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 3.2
    scene.camera = camera
    scene.render.filepath = str(folder/f'sample-{frame}.png')
    bpy.ops.render.render(write_still=True)
(folder/'skinning-checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
