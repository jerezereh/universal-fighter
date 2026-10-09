"""Authored pipeline-role and regional metrics; no retail inputs."""
import numpy as np
from xrd_pipeline import stage_role,roi_error

assert stage_role(['SMAAParamA','edgesTex','areaTex','searchTex'])=='SMAA weights'
assert stage_role(['SMAAParamA','blendTex','SceneColorTexture'])=='SMAA neighborhood blend'
assert stage_role(['SceneColorTexture','SourceTexture'])=='color composite'
a=np.zeros((8,8,4),dtype='u1');b=a.copy();b[2:6,2:6,:3]=7
assert roi_error(a,b,[2,2,6,6])['mean_absolute_rgb_error']==7
assert roi_error(a,b,[0,0,2,2])['exact_rgb_fraction']==1
for rectangle in [[0,0,9,8],[-1,0,2,2],[1,1,1,2],[1.0,1,2,2],[0,0,1]]:
    try:roi_error(a,b,rectangle)
    except ValueError:continue
    raise AssertionError('invalid pipeline region accepted')
print('Pipeline auxiliary/color role separation and observed-region metrics/bounds passed.')
