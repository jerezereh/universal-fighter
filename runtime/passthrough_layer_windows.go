//go:build windows

package main

import (
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

// Shared-layer importer (docs/PASSTHROUGH_V2.md item 2). The guest's named D3D12 texture is opened in
// D3D11 and registered with the current OpenGL context through WGL_NV_DX_interop2; the named D3D12
// fence is opened for a CPU completion wait. Drivers that refuse to register the opened shared
// texture (Intel) get a local D3D11 texture that the shared one is copied into on the GPU each frame.
// Plain syscall COM/WGL calls: no new dependencies. Must run on the thread owning the GL context.

var (
	ptD3D12      = syscall.NewLazyDLL("d3d12.dll")
	ptD3D11      = syscall.NewLazyDLL("d3d11.dll")
	ptOpenGL     = syscall.NewLazyDLL("opengl32.dll")
	ptKernel32   = syscall.NewLazyDLL("kernel32.dll")
	ptGetProc    = ptOpenGL.NewProc("wglGetProcAddress")
	ptGenTex     = ptOpenGL.NewProc("glGenTextures")
	ptDeleteTex  = ptOpenGL.NewProc("glDeleteTextures")
	ptCreateEvt  = ptKernel32.NewProc("CreateEventW")
	ptWaitObject = ptKernel32.NewProc("WaitForSingleObject")
	ptCloseH     = ptKernel32.NewProc("CloseHandle")
)

const (
	ptGLTexture2D       = 0x0DE1
	ptWGLAccessReadOnly = 0x0000
	ptGenericAll        = 0x10000000
	ptSharedRead        = 0x80000000
)

func ptGUID(text string) *[16]byte {
	raw, err := hex.DecodeString(strings.ReplaceAll(text, "-", ""))
	if err != nil || len(raw) != 16 {
		panic("bad GUID " + text)
	}
	var g [16]byte
	binary.LittleEndian.PutUint32(g[0:], binary.BigEndian.Uint32(raw[0:]))
	binary.LittleEndian.PutUint16(g[4:], binary.BigEndian.Uint16(raw[4:]))
	binary.LittleEndian.PutUint16(g[6:], binary.BigEndian.Uint16(raw[6:]))
	copy(g[8:], raw[8:])
	return &g
}

var (
	ptIIDDevice12  = ptGUID("189819f1-1db6-4b57-be54-1821339b85f7")
	ptIIDFence     = ptGUID("0a753dcf-c4d8-4b91-adf6-be5a60d95a76")
	ptIIDDevice1   = ptGUID("a04bfb29-08ef-43d6-a49c-a9bdbdcbe686")
	ptIIDTexture2D = ptGUID("6f15aaf2-d208-4e89-9ab4-489535d34f9c")
)

// ptCall invokes COM method `slot` of object `this` (stdcall/x64 ABI) and returns the raw result.
// COM objects live outside the Go heap; the reads reinterpret the handle without uintptr->Pointer casts.
func ptCall(this uintptr, slot int, args ...uintptr) uintptr {
	object := *(**[1]uintptr)(unsafe.Pointer(&this))         // object's first word: the vtable address
	vtable := *(**[1024]uintptr)(unsafe.Pointer(&object[0])) // the method table
	r, _, _ := syscall.SyscallN(vtable[slot], append([]uintptr{this}, args...)...)
	return r
}

func ptOK(hr uintptr, what string) error {
	if int32(hr) < 0 {
		return fmt.Errorf("%s failed 0x%08x", what, uint32(hr))
	}
	return nil
}

func ptRelease(object uintptr) {
	if object != 0 {
		ptCall(object, 2)
	}
}

func ptWide(s string) *uint16 {
	p, err := syscall.UTF16PtrFromString(s)
	if err != nil {
		panic(err)
	}
	return p
}

func ptWGL(name string) (uintptr, error) {
	b := append([]byte(name), 0)
	address, _, _ := ptGetProc.Call(uintptr(unsafe.Pointer(&b[0])))
	if address == 0 {
		return 0, fmt.Errorf("%s is not available (no current GL context or missing WGL_NV_DX_interop2)", name)
	}
	return address, nil
}

type sharedLayerImport struct {
	names                       [2]string
	Width, Height               int
	device12, fence, event      uintptr
	device11, context11, device uintptr
	texture11, local            uintptr
	interop, registered         uintptr
	GLTexture                   uint32
	locked                      bool
	lock, unlock, unregister    uintptr
	closeDevice                 uintptr
}

// openSharedLayer imports layer l into the GL context current on this thread.
func openSharedLayer(l GuestLayer) (s *sharedLayerImport, err error) {
	s = &sharedLayerImport{names: [2]string{l.Memory, l.Fence}, Width: l.Width, Height: l.Height}
	defer func() {
		if err != nil {
			s.Close()
			s = nil
		}
	}()
	// D3D12: the shared fence, opened by name, for the completion wait.
	if err = ptD3D12.Load(); err != nil {
		return
	}
	r, _, _ := ptD3D12.NewProc("D3D12CreateDevice").Call(0, 0xb000, uintptr(unsafe.Pointer(ptIIDDevice12)), uintptr(unsafe.Pointer(&s.device12)))
	if err = ptOK(r, "D3D12CreateDevice"); err != nil {
		return
	}
	var handle uintptr
	if err = ptOK(ptCall(s.device12, 33, uintptr(unsafe.Pointer(ptWide(l.Fence))), ptGenericAll, uintptr(unsafe.Pointer(&handle))), "OpenSharedHandleByName(fence)"); err != nil {
		return
	}
	err = ptOK(ptCall(s.device12, 32, handle, uintptr(unsafe.Pointer(ptIIDFence)), uintptr(unsafe.Pointer(&s.fence))), "OpenSharedHandle(fence)")
	ptCloseH.Call(handle)
	if err != nil {
		return
	}
	if s.event, _, _ = ptCreateEvt.Call(0, 0, 0, 0); s.event == 0 {
		return s, fmt.Errorf("CreateEventW failed")
	}
	// D3D11: the shared texture, opened by name.
	var level uint32
	r, _, _ = ptD3D11.NewProc("D3D11CreateDevice").Call(0, 1, 0, 0x20, 0, 0, 7, uintptr(unsafe.Pointer(&s.device11)), uintptr(unsafe.Pointer(&level)), uintptr(unsafe.Pointer(&s.context11)))
	if err = ptOK(r, "D3D11CreateDevice"); err != nil {
		return
	}
	if err = ptOK(ptCall(s.device11, 0, uintptr(unsafe.Pointer(ptIIDDevice1)), uintptr(unsafe.Pointer(&s.device))), "QueryInterface(ID3D11Device1)"); err != nil {
		return
	}
	if err = ptOK(ptCall(s.device, 49, uintptr(unsafe.Pointer(ptWide(l.Memory))), ptSharedRead, uintptr(unsafe.Pointer(ptIIDTexture2D)), uintptr(unsafe.Pointer(&s.texture11))), "OpenSharedResourceByName(texture)"); err != nil {
		return
	}
	// WGL_NV_DX_interop2: register with GL, falling back to a local copy target.
	var open, register uintptr
	for _, f := range []struct {
		name   string
		target *uintptr
	}{{"wglDXOpenDeviceNV", &open}, {"wglDXRegisterObjectNV", &register}, {"wglDXUnregisterObjectNV", &s.unregister},
		{"wglDXLockObjectsNV", &s.lock}, {"wglDXUnlockObjectsNV", &s.unlock}, {"wglDXCloseDeviceNV", &s.closeDevice}} {
		if *f.target, err = ptWGL(f.name); err != nil {
			return
		}
	}
	if s.interop, _, _ = syscall.SyscallN(open, s.device11); s.interop == 0 {
		return s, fmt.Errorf("wglDXOpenDeviceNV failed")
	}
	ptGenTex.Call(1, uintptr(unsafe.Pointer(&s.GLTexture)))
	if s.registered, _, _ = syscall.SyscallN(register, s.interop, s.texture11, uintptr(s.GLTexture), ptGLTexture2D, ptWGLAccessReadOnly); s.registered == 0 {
		var desc [44]byte // D3D11_TEXTURE2D_DESC
		ptCall(s.texture11, 10, uintptr(unsafe.Pointer(&desc[0])))
		binary.LittleEndian.PutUint32(desc[32:], 0x8|0x20) // BIND_SHADER_RESOURCE | BIND_RENDER_TARGET
		binary.LittleEndian.PutUint32(desc[40:], 0)        // MiscFlags: not shared
		if err = ptOK(ptCall(s.device11, 5, uintptr(unsafe.Pointer(&desc[0])), 0, uintptr(unsafe.Pointer(&s.local))), "CreateTexture2D(local)"); err != nil {
			return
		}
		if s.registered, _, _ = syscall.SyscallN(register, s.interop, s.local, uintptr(s.GLTexture), ptGLTexture2D, ptWGLAccessReadOnly); s.registered == 0 {
			return s, fmt.Errorf("wglDXRegisterObjectNV refused both the shared and a local texture")
		}
	}
	return s, nil
}

func (s *sharedLayerImport) Matches(l GuestLayer) bool {
	return s.names == [2]string{l.Memory, l.Fence} && s.Width == l.Width && s.Height == l.Height
}

// Update makes frame `value` available to GL: release GL ownership, wait for the guest's copy to
// complete, refresh the local copy if one is used, then lock the texture for GL until the next update.
func (s *sharedLayerImport) Update(value uint64, timeout time.Duration) error {
	if err := s.Unlock(); err != nil {
		return err
	}
	if completed := ptCall(s.fence, 8); uint64(completed) < value {
		if err := ptOK(ptCall(s.fence, 9, uintptr(value), s.event), "SetEventOnCompletion"); err != nil {
			return err
		}
		if r, _, _ := ptWaitObject.Call(s.event, uintptr(timeout/time.Millisecond)); r != 0 {
			return fmt.Errorf("shared layer fence did not reach %d within %v", value, timeout)
		}
	}
	if s.local != 0 {
		ptCall(s.context11, 47, s.local, s.texture11) // CopyResource, ordered before the interop lock
		ptCall(s.context11, 111)                      // Flush
	}
	objects := [1]uintptr{s.registered}
	if r, _, _ := syscall.SyscallN(s.lock, s.interop, 1, uintptr(unsafe.Pointer(&objects[0]))); r == 0 {
		return fmt.Errorf("wglDXLockObjectsNV failed")
	}
	s.locked = true
	return nil
}

func (s *sharedLayerImport) Unlock() error {
	if !s.locked {
		return nil
	}
	objects := [1]uintptr{s.registered}
	if r, _, _ := syscall.SyscallN(s.unlock, s.interop, 1, uintptr(unsafe.Pointer(&objects[0]))); r == 0 {
		return fmt.Errorf("wglDXUnlockObjectsNV failed")
	}
	s.locked = false
	return nil
}

func (s *sharedLayerImport) Close() {
	s.Unlock()
	if s.registered != 0 {
		syscall.SyscallN(s.unregister, s.interop, s.registered)
	}
	if s.interop != 0 {
		syscall.SyscallN(s.closeDevice, s.interop)
	}
	if s.GLTexture != 0 {
		ptDeleteTex.Call(1, uintptr(unsafe.Pointer(&s.GLTexture)))
	}
	if s.event != 0 {
		ptCloseH.Call(s.event)
	}
	for _, object := range []uintptr{s.local, s.texture11, s.device, s.context11, s.device11, s.fence, s.device12} {
		ptRelease(object)
	}
	*s = sharedLayerImport{}
}
