//go:build windows

package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"runtime"
	"syscall"
	"testing"
	"time"
	"unsafe"
)

// Emulates a guest (the Rev2 producer's description: B8G8R8A8, render-target + simultaneous access,
// shared committed heap, named shared fence), clears the texture and signals the fence, then imports
// both through openSharedLayer into a hidden GL context and reads the texture back.
func TestSharedLayerImportRoundTrip(t *testing.T) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	gl, err := ptTestGLContext()
	if err != nil {
		t.Skipf("no OpenGL context: %v", err)
	}
	defer gl()
	const width, height = 64, 48
	layer, cleanup, err := ptTestGuest(width, height, [4]float32{0.2, 0.4, 0.6, 0.8})
	if err != nil {
		t.Skipf("no shareable D3D12 device: %v", err)
	}
	defer cleanup()
	s, err := openSharedLayer(layer)
	if err != nil {
		t.Fatalf("import: %v", err)
	}
	defer s.Close()
	if !s.Matches(layer) || s.GLTexture == 0 {
		t.Fatal("import does not describe the guest layer")
	}
	if err := s.Update(1, time.Second); err != nil {
		t.Fatalf("update: %v", err)
	}
	pixels := make([]byte, width*height*4)
	ogl := syscall.NewLazyDLL("opengl32.dll")
	ogl.NewProc("glBindTexture").Call(ptGLTexture2D, uintptr(s.GLTexture))
	ogl.NewProc("glPixelStorei").Call(0x0D05, 1) // PACK_ALIGNMENT
	ogl.NewProc("glGetTexImage").Call(ptGLTexture2D, 0, 0x1908, 0x1401, uintptr(unsafe.Pointer(&pixels[0])))
	if e, _, _ := ogl.NewProc("glGetError").Call(); e != 0 {
		t.Fatalf("readback GL error 0x%x", e)
	}
	want := []byte{51, 102, 153, 204} // logical RGBA of the clear: DX interop maps B8G8R8A8
	for i := 0; i < len(pixels); i += 4 {
		for c := 0; c < 4; c++ {
			if d := int(pixels[i+c]) - int(want[c]); d < -1 || d > 1 {
				t.Fatalf("pixel %d = %v, want %v", i/4, pixels[i:i+4], want)
			}
		}
	}
	// A fence value the guest never signals times out instead of blocking the host.
	if err := s.Update(2, 50*time.Millisecond); err == nil {
		t.Fatal("unsignalled fence value accepted")
	}
}

func ptTestGLContext() (func(), error) {
	user32, gdi32, ogl := syscall.NewLazyDLL("user32.dll"), syscall.NewLazyDLL("gdi32.dll"), syscall.NewLazyDLL("opengl32.dll")
	hwnd, _, _ := user32.NewProc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(ptWide("STATIC"))), uintptr(unsafe.Pointer(ptWide("pt-layer-test"))),
		0, 0, 0, 16, 16, 0, 0, 0, 0)
	if hwnd == 0 {
		return nil, fmt.Errorf("CreateWindowExW failed")
	}
	dc, _, _ := user32.NewProc("GetDC").Call(hwnd)
	var pfd [40]byte // PIXELFORMATDESCRIPTOR
	binary.LittleEndian.PutUint16(pfd[0:], 40)
	binary.LittleEndian.PutUint16(pfd[2:], 1)
	binary.LittleEndian.PutUint32(pfd[4:], 0x25) // DRAW_TO_WINDOW | SUPPORT_OPENGL | DOUBLEBUFFER
	pfd[9] = 32
	format, _, _ := gdi32.NewProc("ChoosePixelFormat").Call(dc, uintptr(unsafe.Pointer(&pfd[0])))
	gdi32.NewProc("SetPixelFormat").Call(dc, format, uintptr(unsafe.Pointer(&pfd[0])))
	rc, _, _ := ogl.NewProc("wglCreateContext").Call(dc)
	if rc == 0 {
		user32.NewProc("DestroyWindow").Call(hwnd)
		return nil, fmt.Errorf("wglCreateContext failed")
	}
	if ok, _, _ := ogl.NewProc("wglMakeCurrent").Call(dc, rc); ok == 0 {
		return nil, fmt.Errorf("wglMakeCurrent failed")
	}
	return func() {
		ogl.NewProc("wglMakeCurrent").Call(0, 0)
		ogl.NewProc("wglDeleteContext").Call(rc)
		user32.NewProc("DestroyWindow").Call(hwnd)
	}, nil
}

func ptTestGuest(width, height int, colour [4]float32) (GuestLayer, func(), error) {
	var objects []uintptr
	var handles []uintptr
	cleanup := func() {
		for _, h := range handles {
			ptCloseH.Call(h)
		}
		for i := len(objects) - 1; i >= 0; i-- {
			ptRelease(objects[i])
		}
	}
	fail := func(err error) (GuestLayer, func(), error) { cleanup(); return GuestLayer{}, nil, err }
	var device uintptr
	if r, _, _ := ptD3D12.NewProc("D3D12CreateDevice").Call(0, 0xb000, uintptr(unsafe.Pointer(ptIIDDevice12)), uintptr(unsafe.Pointer(&device))); ptOK(r, "D3D12CreateDevice") != nil {
		return fail(ptOK(r, "D3D12CreateDevice"))
	}
	objects = append(objects, device)
	create := func(what string, hr uintptr, out *uintptr) error {
		if err := ptOK(hr, what); err != nil {
			return err
		}
		objects = append(objects, *out)
		return nil
	}
	var queue, allocator, list, fence, texture, rtvHeap uintptr
	var queueDesc [16]byte
	if err := create("CreateCommandQueue", ptCall(device, 8, uintptr(unsafe.Pointer(&queueDesc[0])), uintptr(unsafe.Pointer(ptGUID("0ec870a6-5d7e-4c22-8cfc-5baae07616ed"))), uintptr(unsafe.Pointer(&queue))), &queue); err != nil {
		return fail(err)
	}
	if err := create("CreateCommandAllocator", ptCall(device, 9, 0, uintptr(unsafe.Pointer(ptGUID("6102dee4-af59-4b09-b999-b44d73f09b24"))), uintptr(unsafe.Pointer(&allocator))), &allocator); err != nil {
		return fail(err)
	}
	if err := create("CreateCommandList", ptCall(device, 12, 0, 0, allocator, 0, uintptr(unsafe.Pointer(ptGUID("5b160d0f-ac1b-4185-8ba8-b3ae42a5a455"))), uintptr(unsafe.Pointer(&list))), &list); err != nil {
		return fail(err)
	}
	if err := create("CreateFence", ptCall(device, 36, 0, 1, uintptr(unsafe.Pointer(ptIIDFence)), uintptr(unsafe.Pointer(&fence))), &fence); err != nil {
		return fail(err)
	}
	heap := [5]uint32{1, 0, 0, 0, 0}
	var desc [56]byte
	binary.LittleEndian.PutUint32(desc[0:], 3) // TEXTURE2D
	binary.LittleEndian.PutUint64(desc[16:], uint64(width))
	binary.LittleEndian.PutUint32(desc[24:], uint32(height))
	binary.LittleEndian.PutUint16(desc[28:], 1)
	binary.LittleEndian.PutUint16(desc[30:], 1)
	binary.LittleEndian.PutUint32(desc[32:], 87) // B8G8R8A8_UNORM
	binary.LittleEndian.PutUint32(desc[36:], 1)
	binary.LittleEndian.PutUint32(desc[48:], 0x21) // ALLOW_RENDER_TARGET | ALLOW_SIMULTANEOUS_ACCESS
	if err := create("CreateCommittedResource", ptCall(device, 27, uintptr(unsafe.Pointer(&heap[0])), 1, uintptr(unsafe.Pointer(&desc[0])), 0, 0,
		uintptr(unsafe.Pointer(ptGUID("696442be-a72e-4059-bc79-5b5c98040fad"))), uintptr(unsafe.Pointer(&texture))), &texture); err != nil {
		return fail(err)
	}
	var info [2]uint64
	ptCall(device, 25, uintptr(unsafe.Pointer(&info[0])), 0, 1, uintptr(unsafe.Pointer(&desc[0]))) // struct return via hidden pointer
	stem := fmt.Sprintf("pt-layer-test-%d-%d", os.Getpid(), time.Now().UnixNano())
	layer := GuestLayer{Kind: "d3d12-shared", Memory: stem + "-memory", Fence: stem + "-fence", Value: 1,
		Width: width, Height: height, Size: info[0], Premultiplied: true}
	for _, shared := range []struct {
		object uintptr
		name   string
	}{{texture, layer.Memory}, {fence, layer.Fence}} {
		var h uintptr
		if err := ptOK(ptCall(device, 31, shared.object, 0, ptGenericAll, uintptr(unsafe.Pointer(ptWide(shared.name))), uintptr(unsafe.Pointer(&h))), "CreateSharedHandle"); err != nil {
			return fail(err)
		}
		handles = append(handles, h)
	}
	heapDesc := [4]uint32{2, 1, 0, 0} // RTV, 1 descriptor
	if err := create("CreateDescriptorHeap", ptCall(device, 14, uintptr(unsafe.Pointer(&heapDesc[0])), uintptr(unsafe.Pointer(ptGUID("8efb471d-616c-4f49-90f7-127bb763fa51"))), uintptr(unsafe.Pointer(&rtvHeap))), &rtvHeap); err != nil {
		return fail(err)
	}
	var cpu uintptr
	ptCall(rtvHeap, 9, uintptr(unsafe.Pointer(&cpu))) // GetCPUDescriptorHandleForHeapStart (hidden pointer)
	ptCall(device, 20, texture, 0, cpu)               // CreateRenderTargetView
	ptCall(list, 48, cpu, uintptr(unsafe.Pointer(&colour[0])), 0, 0)
	if err := ptOK(ptCall(list, 9), "Close"); err != nil {
		return fail(err)
	}
	lists := [1]uintptr{list}
	ptCall(queue, 10, 1, uintptr(unsafe.Pointer(&lists[0])))
	if err := ptOK(ptCall(queue, 14, fence, 1), "Signal"); err != nil {
		return fail(err)
	}
	return layer, cleanup, nil
}
