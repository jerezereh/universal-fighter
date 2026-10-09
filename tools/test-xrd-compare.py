"""Authored interior/error measurements; no game pixels needed."""
import numpy as np
import hashlib
import json
from pathlib import Path
import tempfile
from xrd_compare import compare_pixels, compare_trace

private = np.zeros((16, 16, 4), dtype='uint8')
private[3:13, 3:13] = [0, 40, 80, 255]  # Opaque black channels remain covered.
source = private.copy()
source[:, :, 3] = 255  # Source alpha is not used to invent an isolated source mask.
source[:3, :, :3] = 200
result = compare_pixels(source, private)
assert result['interior_pixels'] == 36 and result['exact_rgb_fraction'] == 1
source[5:11, 5:11, 0] = 9
result = compare_pixels(source, private)
assert result['mean_absolute_rgb_error'] == 3 and result['max_channel_error'] == 9
assert not result['color_verified'] and not result['host_publishable']
excluded = compare_pixels(source, private, [(5, 5, 8, 11), (5, 5, 8, 11)])
assert excluded['excluded_interior_pixels'] == 18 and excluded['interior_pixels'] == 18
assert excluded['mean_absolute_rgb_error'] == 3  # Exclusions do not zero remaining errors.
for rectangles in [[(-1, 0, 1, 1)], [(0, 0, 17, 1)], [(1, 1, 1, 2)], [(0, 0, 16, 16)], [(0., 0, 1, 1)]]:
    try: compare_pixels(source, private, rectangles)
    except ValueError: continue
    raise AssertionError('invalid/empty comparison exclusion accepted')
for broken in ('leak', 'clip', 'alpha', 'thin'):
    p = private.copy()
    if broken == 'leak': p[0, 0, 0] = 1
    if broken == 'clip': p[0, 5] = [0, 0, 0, 255]
    if broken == 'alpha': p[6, 6, 3] = 128
    if broken == 'thin': p[:, :, 3] = 0; p[:, :, :3] = 0; p[8, 3:13, 3] = 255
    try: compare_pixels(source, p)
    except ValueError: continue
    raise AssertionError('invalid comparison accepted: ' + broken)
print('Interior color metrics preserve black coverage and reject leaking/clipped/partial/thin masks; fidelity stays unaccepted.')

with tempfile.TemporaryDirectory() as temporary:
    folder = Path(temporary); (folder / 'layers').mkdir()
    receipt = {k: True for k in ('loaded_code_restored', 'detached', 'source_unchanged',
        'controlled_update_step_verified', 'source_input_routing_verified', 'private_layer_state_restored')}
    receipt.update(errors=[], d3d_abi=dict(native_header_checked=True), render_cleanup=dict(render_code_restored=True))
    (folder / 'inspection.json').write_text(json.dumps(receipt))
    for i in range(1, 5):
        name = f'render-{i:02}'
        common = dict(width=16, height=16, counter=i, presentation_index=3, raw=name + '.bgra',
            observation=dict(fighters=[dict(x_raw=0, y_raw=0)]))
        layer = common | dict(kind='render-layer', format=21, native_coverage_verified=False,
            source_graphics_state_verified=True, replayed_draws=13, source_view_projection=True,
            native_color_grading_replayed=True, source_viewport=[0, 0, 16, 16])
        for directory, metadata, pixels in ((folder, common, source), (folder / 'layers', layer, private)):
            raw = pixels.tobytes(); metadata['raw_sha256'] = hashlib.sha256(raw).hexdigest()
            (directory / (name + '.bgra')).write_bytes(raw)
            (directory / (name + '.json')).write_text(json.dumps(metadata))
    assert len(compare_trace(folder)['samples']) == 4
    assert not compare_trace(folder, [(5, 5, 8, 11)], 'Authored overlay fixture; half the interior omitted')['color_verified']
    assert (folder / 'source-comparison.json').exists() and (folder / 'source-comparison-excluded.json').exists()
    try: compare_trace(folder, [(5, 5, 8, 11)])
    except ValueError: pass
    else: raise AssertionError('unexplained exclusion accepted')
    for i in range(1,5):
        file=folder/'layers'/f'render-{i:02}.json'; layer=json.loads(file.read_text())
        layer.update(full_source_color_replayed=True,source_color_shader='0x5000');file.write_text(json.dumps(layer))
        stage=layer|dict(original_color_stage=True,original_color_shader='0x5000',
            capture_boundary='after-original-color-draw',raw=f'pass-{i:02}.raw')
        (folder/stage['raw']).write_bytes(private.tobytes())
        (folder/f'pass-{i:02}.json').write_text(json.dumps(stage))
    result=compare_trace(folder,color_stage=True)
    assert all(s['exact_rgb_fraction']==1 and s['reference_scope']=='original-color-stage' for s in result['samples'])
    post_file=folder/'layers/render-01.json';post=json.loads(post_file.read_text())
    post_file.write_text(json.dumps(post|dict(native_post_color_replayed=True)))
    try:compare_trace(folder,color_stage=True)
    except ValueError as e:assert 'post-color output' in str(e)
    else:raise AssertionError('processed pixels mislabeled as original grading replay')
    post_file.write_text(json.dumps(post))
    stage_file=folder/'pass-01.json';stage=json.loads(stage_file.read_text())
    stage_file.write_text(json.dumps(stage|dict(original_color_shader='0x6000')))
    try: compare_trace(folder,color_stage=True)
    except ValueError: pass
    else: raise AssertionError('unlinked stage shader accepted')
    file = folder / 'layers/render-01.json'; metadata = json.loads(file.read_text())
    for field, value in [('source_viewport', [0, 0, 15, 16]), ('counter', 100),
                         ('raw_sha256', '0' * 64), ('normalized_projection', True)]:
        file.write_text(json.dumps(metadata | {field: value}))
        try: compare_trace(folder)
        except ValueError: pass
        else: raise AssertionError('unverified trace accepted: ' + field)
    print('Paired trace comparison rejects stale counter/hash, normalized frames and unobserved viewport alignment.')
