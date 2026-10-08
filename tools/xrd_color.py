"""Offline native-LUT diagnostic; bloom, HDR precision and full source color remain gates."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from xrd_layer import layer_pixels, settled_oracle
from xrd_shader import screen_packet


def inline_constants(code):
    if not 8<=len(code)<=65536 or len(code)%4: raise ValueError('invalid native program bounds')
    words=struct.unpack('<'+'I'*(len(code)//4),code)
    if words[0]!=0xffff0300: raise ValueError('requires native pixel shader model 3')
    result={};at=1
    while at<len(words):
        token=words[at];op=token&0xffff
        if op==0xffff:
            if token!=0xffff or at!=len(words)-1: raise ValueError('invalid native program end')
            return result
        size=(token>>16)&0x7fff if op==0xfffe else (token>>24)&15
        if at+1+size>=len(words): raise ValueError('instruction outside native program')
        if op==81:
            if size!=5: raise ValueError('invalid inline constant')
            destination=words[at+1];register=destination&0x7ff
            if (((destination>>28)&7)|((destination>>8)&24))!=2 or destination&0x2000 or register>=224 or register in result:
                raise ValueError('invalid/aliased inline register')
            result[register]=struct.unpack('<4f',struct.pack('<4I',*words[at+2:at+6]))
        at+=1+size
    raise ValueError('missing native program end')


def observed_power(assembly,code):
    # Read the native scalar feeding the three observed color exponent instructions.
    matches=re.findall(r'\bmul(?:_pp)?\s+r\d+\.xyz,\s*r\d+,\s*c(\d+)\.([xyzw])\s*\n'
        r'(?:\s*exp(?:_sat)?(?:_pp)?\s+r\d+\.[xyzw]+,\s*r\d+\.[xyzw]\s*\n){3}',assembly)
    if len(matches)!=1: raise ValueError('ambiguous/unsupported native color power path')
    register,component=matches[0];constants=inline_constants(code)
    if int(register) not in constants: raise ValueError('color power is not an observed inline scalar')
    power=constants[int(register)]['xyzw'.index(component)]
    if not math.isfinite(power) or not .1<=power<=4: raise ValueError('invalid native color power')
    return power


def apply_lut(bgra,lut,power):
    import numpy as np
    if (bgra.dtype!=np.uint8 or bgra.ndim!=3 or bgra.shape[2]!=4 or
            any(not 1<=n<=1024 for n in bgra.shape[:2]) or lut.dtype!=np.uint8 or lut.ndim!=3 or lut.shape[2]!=4 or
            not 2<=lut.shape[0]<=32 or lut.shape[1]!=lut.shape[0]**2 or
            type(power) not in (int,float) or not math.isfinite(power) or not .1<=power<=4):
        raise ValueError('invalid packed LUT/image/power')
    edge=lut.shape[0];covered=bgra[:,:,3]!=0;output=np.zeros_like(bgra);output[:,:,3]=bgra[:,:,3]
    points=np.power(bgra[covered,:3][:,::-1].astype('float64')/255,power)*(edge-1)
    low=np.floor(points).astype('int32');high=np.minimum(low+1,edge-1);fraction=points-low
    rgb=np.zeros_like(points)
    # ponytail: standard trilinear diagnostic; native half precision/bloom/AA are not reproduced.
    for red in range(2):
        for green in range(2):
            for blue in range(2):
                choices=[red,green,blue];index=np.where(choices,high,low)
                weight=np.prod(np.where(choices,fraction,1-fraction),axis=1)
                rgb+=lut[index[:,1],index[:,2]*edge+index[:,0],:3][:,::-1]*weight[:,None]
    output[covered,:3]=np.rint(np.clip(rgb,0,255)).astype('uint8')[:,::-1]
    return output


def raw_file(folder,metadata,suffix):
    name=metadata['raw']
    if not re.fullmatch(r'(?:pass|render)-[0-9]{2}\.'+suffix,name): raise ValueError('invalid local pixel filename')
    data=(folder/name).read_bytes()
    if hashlib.sha256(data).hexdigest()!=metadata['raw_sha256']: raise ValueError('native pixel hash changed')
    return data


def preview(folder):
    import numpy as np
    from PIL import Image
    receipt=json.loads((folder/'inspection.json').read_text())
    if (receipt['errors'] or not receipt['controlled_update_step_verified'] or not receipt['source_input_routing_verified'] or
            not receipt['loaded_code_restored'] or not receipt['source_unchanged'] or not receipt['detached'] or
            not receipt['render_cleanup']['render_code_restored']): raise ValueError('requires restored native source evidence')
    shaders=json.loads((folder/'screen-shaders.json').read_text())
    consumers=[s for s in shaders if s.get('lut_source') is not None]
    if len(consumers)!=1: raise ValueError('requires one observed native LUT consumer')
    shader=consumers[0];name=shader['file']
    if not re.fullmatch(r'screen-[0-9]{2}\.bin',name): raise ValueError('invalid shader filename')
    code=(folder/name).read_bytes()
    if screen_packet(shader,code)['sha256']!=shader['sha256']: raise ValueError('native color program hash changed')
    power=observed_power(shader['assembly'],code);surface=shader['lut_source']
    passes=[json.loads(p.read_text()) for p in sorted(folder.glob('pass-[0-9][0-9].json'))]
    selected=[p for p in passes if p['surface']==surface['surface'] and p['counter']==shader['counter']]
    if len(selected)!=1: raise ValueError('missing/unpaired native LUT target readback')
    metadata=selected[0]
    if (metadata['format']!=21 or metadata['width']!=surface['width'] or metadata['height']!=surface['height'] or
            metadata['observation']['fighters'] is None): raise ValueError('LUT format/dimensions changed')
    lut=np.frombuffer(raw_file(folder,metadata,'raw'),dtype='u1').reshape(metadata['height'],metadata['width'],4)
    layers=[json.loads(p.read_text()) for p in sorted((folder/'layers').glob('render-[0-9][0-9].json'))]
    scenes=[json.loads(p.read_text()) for p in sorted(folder.glob('render-[0-9][0-9].json'))]
    if not 2<=len(layers)==len(scenes)<=8: raise ValueError('missing/unbounded private pairs')
    for scene in scenes: raw_file(folder,scene,'bgra')
    for image in layers:
        pixels=raw_file(folder/'layers',image,'bgra');image.update(layer_pixels(image,pixels))
    if not settled_oracle('render-neutral',layers,scenes,[c['request_index'] for c in layers[1::2]])['passed']:
        raise ValueError('private pixels/state are not settled')
    image=layers[1]
    if image['counter']!=shader['counter'] or image['observation']['fighters']!=metadata['observation']['fighters']:
        raise ValueError('LUT and private body source states differ')
    body=np.frombuffer(raw_file(folder/'layers',image,'bgra'),dtype='u1').reshape(image['height'],image['width'],4)
    colored=apply_lut(body,lut,power);bounds=image['native_coverage_bounds'];x,y,right,bottom=bounds
    result_image=Image.fromarray(colored[:,:,[2,1,0,3]]).crop(bounds)
    result_image.save(folder/'color-lut-preview.png')
    yy,xx=np.indices((bottom-y,right-x));gray=np.where((xx//16+yy//16)%2,220,180).astype('u1')
    checker=Image.fromarray(np.repeat(gray[:,:,None],3,axis=2)).convert('RGBA');checker.alpha_composite(result_image)
    checker.convert('RGB').save(folder/'color-lut-checker.png')
    result=dict(native_lut_surface_linked=True,held_source_state_linked=True,power_from_native_program=power,
        source_program_sha256=shader['sha256'],lut_sha256=metadata['raw_sha256'],native_alpha_unchanged=True,
        transparent_rgb_zero=True,crop_origin=[image['projection_pivot'][0]-x,image['projection_pivot'][1]-y],
        source_body_origin=image['native_absolute_body_origin'],origin_to_coverage_bottom=bottom-image['projection_pivot'][1],
        foot_pivot_verified=False,color_verified=False,host_publishable=False,
        limitations=['A8 input can lose HDR precision','bloom/blur/SMAA omitted','standard interpolation differs from native half precision'])
    (folder/'color-lut-preview.json').write_text(json.dumps(result,indent=2));return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('trace',type=Path)
    args=parser.parse_args();print(json.dumps(preview(args.trace),indent=2))
