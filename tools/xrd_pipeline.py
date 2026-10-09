"""Describe one held native post-color pipeline; regional metrics are not fighter fidelity."""
import hashlib
import json
from pathlib import Path
import re
from xrd_shader import screen_packet


def stage_role(names):
    names=set(names)
    if 'ColorGradingLUT' in names: return 'color grading'
    if 'edgesTex' in names: return 'SMAA weights'
    if 'blendTex' in names: return 'SMAA neighborhood blend'
    if 'SMAAParamA' in names: return 'SMAA edges'
    if {'SourceTexture','SceneColorTexture'}<=names: return 'color composite'
    if names=={'SourceTexture'}: return 'blur'
    if 'InverseGamma' in names: return 'vertex-color overlay'
    return 'copy/other'


def roi_error(reference, image, rectangle):
    import numpy as np
    if len(rectangle)!=4 or any(type(n)!=int for n in rectangle): raise ValueError('invalid observed pipeline region')
    x0,y0,x1,y1=rectangle
    if (
            not 0<=x0<x1<=reference.shape[1] or not 0<=y0<y1<=reference.shape[0] or
            image.shape[0]<y1 or image.shape[1]<x1): raise ValueError('invalid observed pipeline region')
    delta=abs(reference[y0:y1,x0:x1,:3].astype('int16')-image[y0:y1,x0:x1,:3].astype('int16'))
    return dict(mean_absolute_rgb_error=float(delta.mean()),max_channel_error=int(delta.max()),
        exact_rgb_fraction=float(np.all(delta==0,axis=2).mean()))


def analyze(folder, rectangle, note):
    import numpy as np
    if not 1<=len(note.strip())<=512: raise ValueError('observed region requires an evidence note')
    receipt=json.loads((folder/'inspection.json').read_text())
    if (receipt['errors'] or not all(receipt.get(k) is True for k in
            ('loaded_code_restored','detached','source_unchanged','controlled_update_step_verified','source_input_routing_verified')) or
            receipt.get('render_cleanup',{}).get('render_code_restored') is not True or
            receipt.get('d3d_abi',{}).get('native_header_checked') is not True):
        raise ValueError('requires clean native pipeline evidence')
    inventory=json.loads((folder/'screen-shaders.json').read_text())
    for s in inventory:
        if not re.fullmatch(r'screen-[0-9]{2}\.bin',s['file']):raise ValueError('invalid program file')
        if screen_packet(s,(folder/s['file']).read_bytes())['sha256']!=s['sha256']:raise ValueError('program hash changed')
    programs={(s['shader'],s['source_target']):s for s in inventory}
    final=json.loads((folder/'render-01.json').read_text())
    if final.get('diagnostic_pipeline') is not True or final.get('presentation_index')!=1:
        raise ValueError('requires matching first-presentation final reference')
    files=sorted(folder.glob('pass-[0-9][0-9].json'))
    if not 2<=len(files)<=24: raise ValueError('missing/unbounded pipeline stages')
    baseline=None;last_color=None;steps=[];outputs={}
    for file in files:
        stage=json.loads(file.read_text())
        if (stage.get('capture_boundary')!='after-screen-draw' or stage.get('diagnostic_pipeline') is not True or
                stage.get('presentation_index')!=1 or stage['counter']!=final['counter'] or
                stage['observation']['fighters']!=final['observation']['fighters']):
            raise ValueError('stages do not belong to the same held presentation/state')
        program=programs[(stage['screen_shader'],stage['surface'])]
        names=re.findall(r'^//\s+(\w+)\s+[cs]\d+\s+\d+\s*$',program['assembly'],re.M)
        role=stage_role(names);metrics=None
        if not re.fullmatch(r'pass-[0-9]{2}\.raw',stage['raw']): raise ValueError('invalid stage raw path')
        raw=(folder/stage['raw']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=stage['raw_sha256']: raise ValueError('stage pixels changed')
        if stage['format'] in (21,22):
            pixels=np.frombuffer(raw,dtype='u1').reshape(stage['height'],stage['width'],4)
            if baseline is None:
                if role!='color grading': raise ValueError('pipeline must start at native color grading')
                baseline=pixels
            if role not in ('SMAA edges','SMAA weights') and stage['height']>=rectangle[3] and stage['width']>=rectangle[2]:
                metrics=roi_error(baseline,pixels,rectangle)
                last_color=pixels
        sources=stage.get('texture_sources')
        if not isinstance(sources,list) or len(sources)>16: raise ValueError('missing stage-specific texture associations')
        dependencies=[dict(slot=s['slot'],earlier_capture=outputs.get(s['surface'])) for s in sources]
        outputs[stage['surface']]=file.name
        steps.append(dict(capture=file.name,role=role,dimensions=[stage['width'],stage['height']],
            inputs=dependencies,regional_rgb=metrics))
    if final.get('raw')!='render-01.bgra':raise ValueError('invalid final reference path')
    raw=(folder/final['raw']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=final['raw_sha256']:raise ValueError('final reference changed')
    final_pixels=np.frombuffer(raw,dtype='u1').reshape(final['height'],final['width'],4)
    result=dict(counter=final['counter'],presentation=1,observed_region=rectangle,region_note=note,
        region_includes_background=True,dependency_scope='latest retained draw to the same native surface; not proof of complete write history',
        stages=steps,last_color_to_final_rgb=roi_error(last_color,final_pixels,rectangle),
        diagnostic_only=True,color_verified=False,host_publishable=False)
    (folder/'pipeline-analysis.json').write_text(json.dumps(result,indent=2));return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path)
    p.add_argument('--region',required=True,help='observed x0,y0,x1,y1 in source pixels')
    p.add_argument('--note',required=True)
    a=p.parse_args();print(json.dumps(analyze(a.trace.resolve(),[int(v) for v in a.region.split(',')],a.note),indent=2))
