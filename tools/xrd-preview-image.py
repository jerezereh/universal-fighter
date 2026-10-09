"""Export a local static review DTO; never enables a live SIGN producer."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from xrd_layer import layer_pixels


def export(folder,index):
    receipt=json.loads((folder/'inspection.json').read_text())
    if receipt['errors'] or not all(receipt.get(k) is True for k in
            ('loaded_code_restored','detached','source_unchanged','controlled_update_step_verified','private_layer_state_restored')) or receipt.get('render_cleanup',{}).get('render_code_restored') is not True:
        raise ValueError('requires clean native review capture')
    if type(index)!=int or not 1<=index<=8:raise ValueError('bounded capture index required')
    metadata=json.loads((folder/'layers'/f'render-{index:02}.json').read_text())
    if metadata.get('normalized_projection') is not True or metadata.get('canonical_right_facing') is not True or metadata.get('identical_native_pixels') is not True:
        raise ValueError('requires settled canonical normalized image')
    raw_name=metadata['raw']
    if Path(raw_name).name!=raw_name:raise ValueError('invalid raw image path')
    pixels=(folder/'layers'/raw_name).read_bytes()
    if hashlib.sha256(pixels).hexdigest()!=metadata['raw_sha256']:raise ValueError('native review pixels changed')
    analysis=layer_pixels(metadata,pixels)
    if analysis['touches_target_edge']:raise ValueError('clipped image cannot establish visual review')
    bounds=analysis['native_coverage_bounds']
    x0,y0,x1,y1=bounds;rgba=bytearray()
    for y in range(y0,y1):
        row=pixels[4*(y*metadata['width']+x0):4*(y*metadata['width']+x1)]
        for i in range(0,len(row),4):rgba.extend((row[i+2],row[i+1],row[i],row[i+3]))
    pivot=metadata['projection_pivot'];path=folder/'static-review-image.json'
    path.write_text(json.dumps(dict(Width=x1-x0,Height=y1-y0,Pivot=[pivot[0]-x0,pivot[1]-y0],RGBA=base64.b64encode(rgba).decode('ascii'))))
    (folder/'static-review-receipt.json').write_text(json.dumps(dict(source_capture=index,source_hash=metadata['raw_sha256'],
        crop=bounds,original_pivot=pivot,fixture=path.name,fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        static_image_only=True,authored_behavior_only=True,source_capabilities_enabled=False,
        foot_pivot_verified=False,scale_verified=False),indent=2))
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path);p.add_argument('--capture',type=int,default=1)
    a=p.parse_args();print(export(a.trace.resolve(),a.capture))
