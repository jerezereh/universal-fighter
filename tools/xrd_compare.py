"""Measure original-camera private grading versus source RGB; never promote fidelity."""
import hashlib
import json
from pathlib import Path
import re

from xrd_layer import layer_pixels


def compare_pixels(source, private, exclusions=()):
    import numpy as np
    if (source.dtype != np.uint8 or private.dtype != np.uint8 or source.shape != private.shape or
            source.ndim != 3 or source.shape[2] != 4 or any(not 5 <= n <= 2048 for n in source.shape[:2])):
        raise ValueError('requires matching bounded BGRA source/private images')
    covered = private[:, :, 3] == 255
    if not np.isin(private[:, :, 3], [0, 255]).all() or not covered.any() or covered.all():
        raise ValueError('requires partial opaque native coverage')
    if np.any(private[~covered, :3]) or any(np.any(edge) for edge in
            (covered[0], covered[-1], covered[:, 0], covered[:, -1])):
        raise ValueError('leaking RGB or clipped source-view coverage')
    height, width = covered.shape
    padded = np.pad(covered, 2)
    interior = np.ones_like(covered)
    for y in range(5):
        for x in range(5):
            interior &= padded[y:y + height, x:x + width]
    if len(exclusions) > 16:
        raise ValueError('too many comparison exclusions')
    original_count = int(interior.sum())
    for rectangle in exclusions:
        if (len(rectangle) != 4 or any(type(n) != int for n in rectangle) or
                not 0 <= rectangle[0] < rectangle[2] <= width or
                not 0 <= rectangle[1] < rectangle[3] <= height):
            raise ValueError('exclusion rectangle outside source viewport')
        x0, y0, x1, y1 = rectangle
        interior[y0:y1, x0:x1] = False
    if not interior.any():
        raise ValueError('no opaque interior after excluding two-pixel edges')
    delta = abs(source[interior, :3].astype('int16') - private[interior, :3].astype('int16'))
    return dict(covered_pixels=int(covered.sum()), interior_pixels=int(interior.sum()),
        excluded_interior_pixels=original_count-int(interior.sum()),
        exclusion_rectangles=[list(r) for r in exclusions],
        edge_exclusion_pixels=2, mean_absolute_rgb_error=float(delta.mean()),
        p95_absolute_channel_error=float(np.percentile(delta, 95)), max_channel_error=int(delta.max()),
        exact_rgb_fraction=float(np.all(delta == 0, axis=1).mean()),
        source_mask_is_private_coverage=True, geometry_alignment_verified=False,
        color_verified=False, isolated_rgba=False, host_publishable=False)


def compare_trace(folder, exclusions=(), exclusion_note='', color_stage=False):
    import numpy as np
    if exclusions and (not isinstance(exclusion_note, str) or not 1 <= len(exclusion_note.strip()) <= 512):
        raise ValueError('explicit exclusions require a bounded evidence note')
    receipt = json.loads((folder / 'inspection.json').read_text())
    if (receipt['errors'] or not all(receipt.get(k) is True for k in
            ('loaded_code_restored', 'detached', 'source_unchanged', 'controlled_update_step_verified',
             'source_input_routing_verified', 'private_layer_state_restored')) or
            receipt.get('d3d_abi', {}).get('native_header_checked') is not True or
            receipt.get('render_cleanup', {}).get('render_code_restored') is not True):
        raise ValueError('requires clean source/input/graphics/native-ABI evidence')
    files = sorted((folder / 'layers').glob('render-[0-9][0-9].json'))
    if len(files) != 4:
        raise ValueError('requires four bounded neutral source-view captures')
    results = []
    for file in files:
        layer = json.loads(file.read_text())
        scene_file = file.name.replace('render-', 'pass-') if color_stage else file.name
        scene = json.loads((folder / scene_file).read_text())
        if color_stage and (scene.get('original_color_stage') is not True or scene.get('format') not in (21,22) or
                scene.get('capture_boundary')!='after-original-color-draw' or
                scene.get('original_color_shader')!=layer.get('source_color_shader')):
            raise ValueError('requires linked original color-stage capture')
        if (layer.get('source_view_projection') is not True or layer.get('normalized_projection') or
                layer.get('native_color_grading_replayed') is not True or
                layer.get('frame_readiness_candidate') or
                any(layer[k] != scene[k] for k in ('counter', 'presentation_index')) or
                layer['observation']['fighters'] != scene['observation']['fighters']):
            raise ValueError('unlinked or normalized/non-graded source-view comparison')
        images = []
        for directory, metadata in ((folder, scene), (folder / 'layers', layer)):
            pattern=r'pass-[0-9]{2}\.raw' if color_stage and directory==folder else r'render-[0-9]{2}\.bgra'
            if not re.fullmatch(pattern, metadata['raw']):
                raise ValueError('invalid raw capture filename')
            raw = (directory / metadata['raw']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != metadata['raw_sha256']:
                raise ValueError('native pixel hash changed')
            if directory == folder / 'layers':
                layer_pixels(metadata, raw)
            images.append(np.frombuffer(raw, dtype='uint8').reshape(metadata['height'], metadata['width'], 4))
        # Larger internal allocations can contain a backbuffer-sized viewport. Never
        # resize the entire allocation and misidentify geometry errors as color errors.
        viewport=layer.get('source_viewport',[])
        if (len(viewport)!=4 or viewport[:2]!=[0,0] or
                any(type(n)!=int or not 5<=n<=2048 for n in viewport[2:]) or
                viewport[2]>scene['width'] or viewport[3]>scene['height'] or
                (not color_stage and viewport[2:]!=[scene['width'],scene['height']]) or
                scene['width'] > layer['width'] or scene['height'] > layer['height']):
            raise ValueError('source/private viewport alignment is not observed')
        images = [i[:viewport[3],:viewport[2]] for i in images]
        results.append(dict(counter=layer['counter'], capture=file.name,
            full_source_color_replayed=layer.get('full_source_color_replayed') is True,
            private_dimensions=[layer['width'], layer['height']],
            source_dimensions=[scene['width'], scene['height']],
            reference_scope='original-color-stage' if color_stage else 'final-backbuffer',
            compared_viewport=viewport,
            comparison_resampling='none', source_viewport_crop=True, **compare_pixels(*images, exclusions)))
    result = dict(samples=results, exclusion_note=exclusion_note, diagnostic_only=True,
        color_verified=False, host_publishable=False)
    name = ('source-color-stage-comparison' if color_stage else 'source-comparison') + ('-excluded' if exclusions else '') + '.json'
    (folder / name).write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--exclude-rect', action='append', default=[], help='observed overlay rectangle x0,y0,x1,y1 in source pixels; up to 16')
    parser.add_argument('--exclusion-note', default='', help='required with exclusions: evidence and omitted coverage')
    parser.add_argument('--color-stage', action='store_true', help='compare paired original color target before later processing rather than final backbuffer')
    args = parser.parse_args()
    rectangles = [tuple(int(n) for n in r.split(',')) for r in args.exclude_rect]
    print(json.dumps(compare_trace(args.trace.resolve(), rectangles, args.exclusion_note, args.color_stage), indent=2))
