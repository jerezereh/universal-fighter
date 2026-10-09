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
        vertex_input=dict(stride=32),vertex_program=dict(code_hex='local-test')))
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
