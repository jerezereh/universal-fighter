"""Check device call argument types against the installed native D3D9 header."""
import re


def device_methods(header):
    block=re.search(r'DECLARE_INTERFACE_IID_\(IDirect3DDevice9,.*?\n\{(.*?)\n\};',header,re.S)
    if not block: raise ValueError('native IDirect3DDevice9 declaration missing')
    rows=re.findall(r'STDMETHOD(?:_\([^,]+,\s*(\w+)\)|\((\w+)\))\s*\((.*?)\)\s*PURE;',block[1],re.S)
    if len(rows)!=119: raise ValueError('incomplete native D3D9 device declaration')
    result=[]
    for first,second,arguments in rows:
        arguments=re.sub(r'^THIS_?\s*','',arguments.strip())
        types=[]
        for argument in arguments.split(',') if arguments else []:
            types.append('pointer' if '*' in argument else 'float' if re.search(r'\bfloat\b',argument) else 'integer')
        result.append((first or second,types))
    return result


def validate_device_calls(sources,header):
    methods=device_methods(header);checked=0
    for source in sources:
        for slot,arguments in re.findall(r"com\(device,\s*(\d+),\s*'(?:int|uint)',\s*\[([^\]]*)\]\)",source):
            slot=int(slot)
            if not 0<=slot<len(methods): raise ValueError('device method outside native vtable')
            name,expected=methods[slot];actual=re.findall(r"'(\w+)'",arguments)
            actual=['integer' if kind in ('uint','int') else kind for kind in actual]
            if actual!=expected: raise ValueError(f'D3D9 ABI mismatch at {name} slot {slot}: {actual} versus {expected}')
            checked+=1
    if not checked: raise ValueError('no literal device calls checked')
    return dict(literal_device_calls_checked=checked,native_header_checked=True,dynamic_calls_checked=False)
