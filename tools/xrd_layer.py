"""Inspect the native alpha channel of a diagnostic private mesh layer."""
import hashlib


def layer_pixels(metadata,pixels):
    import numpy as np
    width,height=metadata['width'],metadata['height']
    if (any(type(n)!=int or not 1<=n<=2048 for n in (width,height)) or
            metadata.get('kind')!='render-layer' or metadata.get('format')!=21 or
            metadata.get('native_coverage_verified') is not False or
            metadata.get('source_graphics_state_verified') is not True or
            type(metadata.get('replayed_draws'))!=int or not 1<=metadata['replayed_draws']<=8192 or len(pixels)!=width*height*4):
        raise ValueError('requires bounded restored-state diagnostic A8 layer')
    bgra=np.frombuffer(pixels,dtype='u1').reshape(height,width,4)
    alpha=bgra[:,:,3];covered=alpha!=0
    if not covered.any() or covered.all(): raise ValueError('missing/full-target coverage')
    y,x=np.nonzero(covered);bounds=[int(x.min()),int(y.min()),int(x.max())+1,int(y.max())+1]
    if np.any(bgra[~covered,:3]): raise ValueError('RGB outside native coverage')
    values,counts=np.unique(alpha,return_counts=True)
    return dict(native_alpha_values={str(int(v)):int(n) for v,n in zip(values,counts)},
        native_coverage_bounds=bounds,covered_pixels=int(covered.sum()),
        alpha_sha256=hashlib.sha256(alpha.tobytes()).hexdigest(),transparent_rgb_zero=True,
        native_coverage_verified=False,isolated_rgba=False)


def save_layer_preview(folder,metadata):
    """RGBA crop and checker preview use the actual GPU alpha, including black material pixels."""
    import numpy as np
    from PIL import Image
    pixels=(folder/metadata['raw']).read_bytes();analysis=layer_pixels(metadata,pixels)
    rgba=np.frombuffer(pixels,dtype='u1').reshape(metadata['height'],metadata['width'],4)[:,:,[2,1,0,3]]
    image=Image.fromarray(rgba).crop(tuple(analysis['native_coverage_bounds']))
    name=metadata['image'].removesuffix('.png')
    image.save(folder/(name+'-rgba.png'))
    y,x=np.indices((image.height,image.width));gray=np.where(((x//16+y//16)%2)==0,180,220).astype('u1')
    check=Image.fromarray(np.repeat(gray[:,:,None],3,axis=2)).convert('RGBA')
    check.alpha_composite(image);check.convert('RGB').save(folder/(name+'-checker.png'))
    return analysis|dict(rgba_preview=name+'-rgba.png',checker_preview=name+'-checker.png',
        crop_is_diagnostic=True,pivot_verified=False,color_verified=False)
