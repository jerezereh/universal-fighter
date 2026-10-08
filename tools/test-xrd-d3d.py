"""Independent installed-header ABI verification, including the reversed sampler regression."""
from pathlib import Path
from xrd_d3d import device_methods, validate_device_calls

root=Path(__file__).resolve().parent.parent
header=(root/'local-cache/msys64/mingw64/include/d3d9.h').read_text()
methods=device_methods(header)
assert methods[68]==('GetSamplerState',['integer','integer','pointer'])
assert methods[69]==('SetSamplerState',['integer','integer','integer'])
sources=[(root/'tools'/name).read_text() for name in ('xrd-sign-boundary.js','xrd-sign-layer.js','xrd-sign-grade.js')]
result=validate_device_calls(sources,header);assert result['literal_device_calls_checked']>=80
for source in ["com(device,69,'int',['uint','uint','pointer'])", "com(device,68,'int',['uint','uint','uint'])",
        "com(device,83,'int',['uint','pointer','pointer','uint'])"]:
    try: validate_device_calls([source],header)
    except ValueError: continue
    raise AssertionError('incorrect native device ABI accepted')
print('Installed native D3D9 header validates',result['literal_device_calls_checked'],'literal calls; reversed sampler and draw prototypes reject.')
