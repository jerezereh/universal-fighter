"""Authored shared GPU layer for passthrough-demo.py (docs/PASSTHROUGH_V2.md item 1).

Renders rectangles into a named shared D3D12 texture with render-target clears and signals a
named shared D3D12 fence per frame, matching the Rev2 producer's resource description
(B8G8R8A8, render target + simultaneous access, shared committed heap). Windows, 64-bit Python.
"""
import ctypes
import os
import time
import uuid

V, P, U = ctypes.c_void_p, ctypes.POINTER, ctypes.c_uint


def _guid(text):
    return (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(text).bytes_le)


def _method(obj, slot, restype, *argtypes):
    vtable = ctypes.cast(obj, P(P(V))).contents
    return ctypes.WINFUNCTYPE(restype, V, *argtypes)(vtable[slot])


def _ok(hr, what):
    if hr != 0:
        raise OSError(f'{what} failed 0x{hr & 0xffffffff:08x}')


class SharedLayer:
    def __init__(self, width, height, stem):
        self.width, self.height, self.value, self.objects, self.handles = width, height, 0, [], []
        self.kernel32 = ctypes.WinDLL('kernel32')
        device = V()
        _ok(ctypes.WinDLL('d3d12').D3D12CreateDevice(None, 0xb000, _guid('189819f1-1db6-4b57-be54-1821339b85f7'),
                                                     ctypes.byref(device)), 'D3D12CreateDevice')
        self.device = self._keep(device)

        def make(what, slot, *args, argtypes):
            out = V()
            _ok(_method(device, slot, ctypes.c_long, *argtypes, P(V))(device, *args, ctypes.byref(out)), what)
            return self._keep(out)

        self.queue = make('CreateCommandQueue', 8, (ctypes.c_ubyte * 16)(), _guid('0ec870a6-5d7e-4c22-8cfc-5baae07616ed'),
                          argtypes=(V, V))
        self.allocator = make('CreateCommandAllocator', 9, 0, _guid('6102dee4-af59-4b09-b999-b44d73f09b24'), argtypes=(U, V))
        self.list = make('CreateCommandList', 12, 0, 0, self.allocator, None, _guid('5b160d0f-ac1b-4185-8ba8-b3ae42a5a455'),
                         argtypes=(U, U, V, V, V))
        _ok(_method(self.list, 9, ctypes.c_long)(self.list), 'Close')
        self.fence = make('CreateFence', 36, 0, 1, _guid('0a753dcf-c4d8-4b91-adf6-be5a60d95a76'), argtypes=(ctypes.c_uint64, U, V))
        heap = (ctypes.c_uint * 5)(1, 0, 0, 0, 0)
        desc = (ctypes.c_ubyte * 56)()
        for offset, ctype, value in ((0, ctypes.c_uint, 3), (16, ctypes.c_uint64, width), (24, ctypes.c_uint, height),
                                     (28, ctypes.c_ushort, 1), (30, ctypes.c_ushort, 1), (32, ctypes.c_uint, 87),
                                     (36, ctypes.c_uint, 1), (48, ctypes.c_uint, 0x21)):
            ctype.from_buffer(desc, offset).value = value
        self.texture = make('CreateCommittedResource', 27, heap, 1, desc, 0, None,
                            _guid('696442be-a72e-4059-bc79-5b5c98040fad'), argtypes=(V, U, V, U, V, V))
        info = (ctypes.c_uint64 * 2)()
        _method(device, 25, V, V, U, U, V)(device, info, 0, 1, desc)
        self.size = info[0]
        self.memory_name, self.fence_name = stem + '-memory', stem + '-fence'
        for obj, name in ((self.texture, self.memory_name), (self.fence, self.fence_name)):
            handle = V()
            _ok(_method(device, 31, ctypes.c_long, V, V, U, ctypes.c_wchar_p, P(V))(
                device, obj, None, 0x10000000, name, ctypes.byref(handle)), 'CreateSharedHandle')
            self.handles.append(handle)
        self.rtv_heap = make('CreateDescriptorHeap', 14, (ctypes.c_uint * 4)(2, 1, 0, 0),
                             _guid('8efb471d-616c-4f49-90f7-127bb763fa51'), argtypes=(V, V))
        self.rtv = ctypes.c_size_t()
        _method(self.rtv_heap, 9, V, P(ctypes.c_size_t))(self.rtv_heap, ctypes.byref(self.rtv))
        _method(device, 20, None, V, V, ctypes.c_size_t)(device, self.texture, None, self.rtv.value)

    def _keep(self, obj):
        self.objects.append(obj)
        return obj

    def render(self, rects):
        """rects: [(left, top, right, bottom, (r, g, b, a) premultiplied 0..1)]; returns the frame's fence value."""
        completed = _method(self.fence, 8, ctypes.c_uint64)
        deadline = time.monotonic() + 1
        while completed(self.fence) < self.value:   # the previous frame's clears must be done before reuse
            if time.monotonic() > deadline:
                raise TimeoutError('previous shared layer frame did not complete')
            time.sleep(0.0005)
        _ok(_method(self.allocator, 8, ctypes.c_long)(self.allocator), 'CommandAllocator.Reset')
        _ok(_method(self.list, 10, ctypes.c_long, V, V)(self.list, self.allocator, None), 'CommandList.Reset')
        clear = _method(self.list, 48, None, ctypes.c_size_t, V, U, V)
        clear(self.list, self.rtv.value, (ctypes.c_float * 4)(0, 0, 0, 0), 0, None)
        for left, top, right, bottom, colour in rects:
            left, top, right, bottom = max(0, left), max(0, top), min(self.width, right), min(self.height, bottom)
            if left < right and top < bottom:
                clear(self.list, self.rtv.value, (ctypes.c_float * 4)(*colour), 1, (ctypes.c_long * 4)(left, top, right, bottom))
        _ok(_method(self.list, 9, ctypes.c_long)(self.list), 'CommandList.Close')
        _method(self.queue, 10, None, U, V)(self.queue, 1, (V * 1)(self.list))
        self.value += 1
        _ok(_method(self.queue, 14, ctypes.c_long, V, ctypes.c_uint64)(self.queue, self.fence, self.value), 'Signal')
        return self.value

    def describe(self, pivot):
        return dict(kind='d3d12-shared', memory=self.memory_name, fence=self.fence_name, value=self.value,
                    width=self.width, height=self.height, size=self.size, pivot=list(pivot), premultiplied=True)

    def close(self):
        for h in self.handles:
            self.kernel32.CloseHandle(h)
        for obj in reversed(self.objects):
            _method(obj, 2, ctypes.c_ulong)(obj)
        self.objects, self.handles = [], []


def unique_stem(variant):
    return f'uf-demo-{variant}-{os.getpid()}-{time.monotonic_ns()}'
