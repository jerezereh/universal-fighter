"""Create explicit Sol animation-sample previews from a completed local graphics import.

This is a diagnostic bake, not an accepted sprite mapping or playable fighter pack.
Native scale controllers, facial blending and toon passes still need an oracle.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

from xrd_animation import array, diagnostic_scales, object_properties, posed_gltf, properties, psa, sample, scale_tracks
from xrd_package import lzo_decoder, package

ROOT = Path(__file__).resolve().parent.parent
PARTS = {'body': ('SOL_body01', 'AS_SOL_BTL_Body_01', 'SOL_base'),
         'head': ('SOL_head01', 'AS_SOL_BTL_Head_01', 'SOL_base'),
         'weapon': ('Sol_weapon01', 'AS_SOL_BTL_Weapon_01', 'SOLW_base')}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(folder, clip, frames):
    allowed = (ROOT/'extracted/xrd-sign').resolve()
    if not folder.is_relative_to(allowed):
        raise ValueError('preview requires an ignored local SIGN import')
    receipt = json.loads((folder/'inspection.json').read_text())
    if not receipt['complete'] or receipt['backend'] != 'xrd-sign-inspection':
        raise ValueError('incomplete source inspection')
    materials = [name for name in receipt['packages'] if name.startswith('SOL_MAT_01')]
    if len(materials) != 1:
        raise ValueError('missing/ambiguous source palette package')
    material_package = materials[0]
    material_folder = folder/'graphics'/material_package.removesuffix('.upk')/'Texture2D'
    material_source = folder/(material_package+'.dec')
    if digest(material_source) != receipt['packages'][material_package]['decoded_sha256']:
        raise ValueError('material package fingerprint changed')
    source = folder/'SOL_ANM_BTL_01_SF.upk.dec'
    if digest(source) != receipt['packages']['SOL_ANM_BTL_01_SF.upk']['decoded_sha256']:
        raise ValueError('animation package fingerprint changed')
    virtual, names, exports = package(source.read_bytes(), lzo_decoder(ROOT/'local-cache/xrd-tools/lzo.dll'))
    output = folder/'pose-previews'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    report = {'schema': 1, 'clip': clip, 'frames': frames, 'sprite_mapping_verified': False,
              'visual_accepted': False, 'source_shader_reproduced': False,
              'native_scale_controllers_applied': False, 'diagnostic_scale_mode': 'local-held-key',
              'rendered': False, 'material_package': material_package,
              'parts': {}, 'inputs': {str(source): digest(source), str(material_source): digest(material_source)}}
    for part, (mesh_name, set_name, texture_name) in PARTS.items():
        mesh = folder/'graphics/SOL_MSH_01_SF/SkeletalMesh3'/f'{mesh_name}.gltf'
        anim_file = folder/'graphics/SOL_ANM_BTL_01_SF/AnimSet'/f'{set_name}.psa'
        texture = material_folder/f'{texture_name}.png'
        animation = psa(anim_file.read_bytes())
        entry = next(x for x in exports if x['class'] == 'AnimSet' and x['name'] == set_name)
        props = object_properties(virtual, names, entry)
        refs = props['Sequences', 0]['value']
        references = array(refs, lambda r: r.integer(), len(exports))
        if any(not 0 < x <= len(exports) for x in references):
            raise ValueError('invalid AnimSet sequence references')
        sequence = None
        for ref in references:
            candidate = exports[ref-1]
            if candidate['class'] != 'AnimSequence':
                raise ValueError('AnimSet references a non-sequence')
            values = object_properties(virtual, names, candidate)
            if values['SequenceName', 0]['value'] == clip:
                if sequence is not None:
                    raise ValueError('ambiguous source sequence')
                sequence = values
        if sequence is None or sequence['NumFrames', 0]['value'] != animation['clips'][clip]['frames']:
            raise ValueError('source package/PSA sequence disagreement')
        tracks = scale_tracks(virtual, names, exports, sequence)
        trees = [x for x in exports if x['class'] == 'REDAnimTree'
                 and x['name'].casefold() == set_name.replace('AS_', 'AT_', 1).casefold()]
        if len(trees) != 1:
            raise ValueError('missing/ambiguous source animation tree')
        tree_entry = trees[0]
        tree = object_properties(virtual, names, tree_entry)
        controls = {}
        for control in array(tree['SkelControlLists', 0]['value'], lambda r: properties(r, names)):
            ref = control['ControlHead', 0]['value']
            if not 0 < ref <= len(exports) or exports[ref-1]['class'] != 'SkelControl_Scale3D':
                raise ValueError('unclassified scale controller')
            data = object_properties(virtual, names, exports[ref-1])
            control_name = data['ControlName', 0]['value']
            if control_name in controls:
                raise ValueError('duplicate scale controller name')
            controls[control_name] = control['BoneName', 0]['value']
        report['parts'][part] = {**animation['clips'][clip], 'bones': len(animation['bones']),
                                'source_sequence_length': sequence['SequenceLength', 0]['value'],
                                'scale_controller_count': len(tracks), 'scale_keys': tracks}
        original = json.loads(mesh.read_text())
        mesh_bones = {original['nodes'][i]['name'] for i in original['skins'][0]['joints']}
        if any(controls.get(target) != target for target in tracks if target in mesh_bones):
            raise ValueError('scale metadata lacks matching bone controller')
        for buffer in original['buffers']:
            uri = buffer['uri']
            if Path(uri).name != uri:
                raise ValueError('unexpected glTF buffer path')
            shutil.copyfile(mesh.parent/uri, output/uri)
            report['inputs'][str(mesh.parent/uri)] = digest(mesh.parent/uri)
        for frame in frames:
            gltf = posed_gltf(json.loads(mesh.read_text()), animation, clip, frame)
            absent = diagnostic_scales(gltf, tracks, frame/animation['clips'][clip]['rate'])
            report['parts'][part]['scale_targets_absent_from_mesh'] = absent
            # Diagnostic base-color pass only: retail outline/shadow/decal passes need their shaders.
            for item in gltf['meshes']:
                item['primitives'] = [p for p in item['primitives']
                                      if gltf['materials'][p['material']]['name'] == 'M_Character']
            (output/f'{part}-{frame}.gltf').write_text(json.dumps(gltf), encoding='utf-8')
        for path in (mesh, anim_file, texture):
            report['inputs'][str(path)] = digest(path)
        report['parts'][part]['texture'] = str(texture)
        # Export-sample differences are evidence, not an assumed sprite-to-time conversion.
        chosen = [sample(animation, clip, i) for i in frames]
        report['parts'][part]['samples_distinct'] = len({str(x) for x in chosen})
    (output/'preview.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('import_folder', type=Path)
    parser.add_argument('--clip', default='sol200')
    parser.add_argument('--frames', default='0', help='explicit zero-based PSA samples, not sprite suffixes')
    parser.add_argument('--blender', type=Path, help='optionally render with an installed Blender executable')
    args = parser.parse_args()
    frames = [int(x) for x in args.frames.split(',')]
    if not frames or len(frames) != len(set(frames)) or any(x < 0 for x in frames):
        raise ValueError('invalid explicit sample list')
    output = prepare(args.import_folder.resolve(), args.clip, frames)
    if args.blender:
        result = subprocess.run([str(args.blender.resolve()), '--background', '--factory-startup',
                                 '--python', str(ROOT/'tools/xrd-sign-render.py'), '--', str(output)],
                                capture_output=True, timeout=240)
        (output/'blender.log').write_bytes(result.stdout+result.stderr)
        if result.returncode or not all((output/f'sample-{x}.png').is_file() for x in frames):
            raise RuntimeError(f'preview render failed: {output}/blender.log')
        report = json.loads((output/'preview.json').read_text())
        skinning = json.loads((output/'skinning-checks.json').read_text())
        if set(skinning) != {f'{part}-{frame}' for part in PARTS for frame in frames}:
            raise ValueError('incomplete renderer skinning verification')
        if any(x['max_nearest_error_m'] > x['tolerance_m'] for x in skinning.values()):
            raise ValueError('renderer skinning verification failed')
        report['gltf_skinning_verified'] = True
        report['skinning_checks'] = skinning
        if any(digest(Path(path)) != value for path, value in report['inputs'].items()):
            raise ValueError('source export changed during rendering')
        report['renders'] = {}
        for frame in frames:
            path = output/f'sample-{frame}.png'
            header = path.read_bytes()[:24]
            if header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>2I', header[16:24]) != (640, 640):
                raise ValueError('unexpected preview image format/dimensions')
            report['renders'][path.name] = digest(path)
        report['rendered'] = True
        report['source_exports_unchanged'] = True
        report['blender_sha256'] = digest(args.blender.resolve())
        (output/'preview.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('Diagnostic sample PNGs rendered; source mapping/shaders remain unaccepted.')
    print(output)
