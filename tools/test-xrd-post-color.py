"""Authored ordered private dependencies; no native programs or pixels."""
import copy
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('boundary',Path(__file__).with_name('xrd-sign-boundary.py'))
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
# Inventory integrity already has grading/shader tests; exercise the new chain guard.
boundary.grading_programs=lambda folder,state: None
data={};programs=[]
for i in range(1,11):
    surface=f'0x{i:04x}'
    stage=dict(screen_shader=surface,surface=surface,capture_boundary='after-screen-draw',
        diagnostic_pipeline=True,presentation_index=1,counter=10,observation=dict(fighters=['held']),
        format=21,width=16,height=16,texture_sources=[dict(slot=0,surface=f'0x{i-1:04x}')])
    data[f'pass-{i:02}.json']=stage
    assembly='// SceneColorTexture s0 1\n// SourceTexture s1 1\n' if i==9 else '// SceneColorTexture s0 1\n'
    programs.append(dict(shader=surface,source_target=surface,assembly=assembly,file=f'screen-{i:02}.bin',
        vertex_input=dict(stride=32),vertex_program=dict(code_hex='local-test',shader='0xeeee')))
data['screen-shaders.json']=programs
class File:
    def __init__(self,name):self.name=name
    def read_text(self):return json.dumps(data[self.name])
    def read_bytes(self):return b'authored'
class Folder:
    def __truediv__(self,name):return File(name)
grade=dict(shader='0x0001',target='0x0001')
assert len(boundary.post_color_programs(Folder(),{},grade))==9
baseline=copy.deepcopy(data)
for change in ('foreign-input','missing-vertex','changed-state','oversized','duplicate-slot','missing-composite'):
    data=copy.deepcopy(baseline)
    if change=='foreign-input':data['pass-04.json']['texture_sources'][0]['surface']='0xffff'
    if change=='missing-vertex':data['screen-shaders.json'][3]['vertex_input']=None
    if change=='changed-state':data['pass-04.json']['counter']=11
    if change=='oversized':data['pass-04.json']['width']=2049
    if change=='duplicate-slot':data['pass-04.json']['texture_sources']*=2
    if change=='missing-composite':data['screen-shaders.json'][8]['assembly']='// SceneColorTexture s0 1\n'
    try:boundary.post_color_programs(Folder(),{},grade)
    except ValueError:pass
    else:raise AssertionError(change+' accepted')
print('Ordered private dependency, vertex/state/dimension/sampler and composite guards passed.')
data=copy.deepcopy(baseline)
for i,names in [(11,'// SceneColorTexture s0 1\n// SMAAParamA c0 1\n'),
        (12,'// edgesTex s0 1\n// areaTex s1 1\n// searchTex s2 1\n// SMAAParamA c0 1\n'),
        (13,'// SceneColorTexture s0 1\n// blendTex s1 1\n// SMAAParamA c0 1\n')]:
    surface=f'0x{i:04x}'
    stage=copy.deepcopy(data['pass-10.json']);stage.update(screen_shader=surface,surface=surface)
    stage['texture_sources']=[dict(slot=0,surface=f'0x{i-1:04x}')]
    if i==12:stage['texture_sources']+=[dict(slot=1,surface='0xaaaa'),dict(slot=2,surface='0xbbbb')]
    if i==13:
        stage.update(width=12,height=12)
        stage['texture_sources']=[dict(slot=0,surface='0x000a'),dict(slot=1,surface='0x000c')]
    data[f'pass-{i:02}.json']=stage
    data['screen-shaders.json'].append(dict(shader=surface,source_target=surface,assembly=names,
        file=f'screen-{i:02}.bin',vertex_input=dict(stride=32),vertex_program=dict(code_hex='local-test',shader='0xeeee')))
result=boundary.post_color_programs(Folder(),{},grade,True)
assert len(result)==12 and result[-2]['lookup_slots']==[1,2] and result[-1]['width']==12
smaa_baseline=copy.deepcopy(data)
for change in ('scene-as-lookup','unknown-blend-input','missing-lookup','wrong-edges','oversized-output'):
    data=copy.deepcopy(smaa_baseline)
    if change=='scene-as-lookup':data['pass-12.json']['texture_sources'][1]['surface']='0x000a'
    if change=='unknown-blend-input':data['pass-13.json']['texture_sources'][0]['surface']='0xffff'
    if change=='missing-lookup':data['pass-12.json']['texture_sources'].pop()
    if change=='wrong-edges':data['screen-shaders.json'][10]['assembly']='// SceneColorTexture s0 1\n'
    if change=='oversized-output':data['pass-13.json']['width']=17
    try:boundary.post_color_programs(Folder(),{},grade,True)
    except ValueError:pass
    else:raise AssertionError(change+' accepted')
print('SMAA ordering, private scene dependencies, distinct native lookups and cropped output guards passed.')
data=copy.deepcopy(smaa_baseline)
for i,program in enumerate(data['screen-shaders.json'],1):
    program['vertex_input']['declaration_hex']='00000000030000000000100001000500ff00000011000000'
    program['vertex_program']['assembly']='// SMAAParamA c6 1\n' if i>=11 else '// Transform c9 4\n'
for i in range(3,9):data[f'pass-{i:02}.json'].update(format=36,width=6,height=6)
result=boundary.post_color_programs(Folder(),{},grade,True,dict(width=640,height=768))
assert result[1]['private_width']==162 and result[1]['private_height']==194
assert result[-1]['private_width']==640 and result[-1]['pixel_smaa']==0
normalized_baseline=copy.deepcopy(data)
for change in ('wrong-declaration','wrong-downsample','unknown-uniform','wrong-uniform-size'):
    data=copy.deepcopy(normalized_baseline)
    if change=='wrong-declaration':data['screen-shaders.json'][3]['vertex_input']['declaration_hex']='00'*24
    if change=='wrong-downsample':data['pass-04.json']['width']=7
    if change=='unknown-uniform':data['screen-shaders.json'][3]['vertex_program']['assembly']='// Unknown c9 4\n'
    if change=='wrong-uniform-size':data['screen-shaders.json'][3]['vertex_program']['assembly']='// Transform c9 1\n'
    try:boundary.post_color_programs(Folder(),{},grade,True,dict(width=640,height=768))
    except ValueError:pass
    else:raise AssertionError(change+' accepted')
print('Normalized declaration/uniform guards and quarter-resolution padded private dimensions passed.')
