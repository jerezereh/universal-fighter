package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"io"
	"math"
	"net"
	"sync/atomic"
	"testing"
	"time"
)

func TestPassthroughStraightAlphaTexture(t *testing.T) {
	rgba := []byte{240, 120, 60, 128, 255, 255, 255, 0, 35, 185, 225, 255}
	before := append([]byte(nil), rgba...)
	want := []byte{120, 60, 30, 128, 0, 0, 0, 0, 35, 185, 225, 255}
	if !bytes.Equal(guestTexturePixels(rgba), want) || !bytes.Equal(rgba, before) {
		t.Fatal("wrong alpha conversion or mutated wire frame")
	}
}

func testPeer(t *testing.T, game string, transform func(GuestRequest, *GuestResponse)) (PassthroughConfig, *atomic.Int32) {
	t.Helper()
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { l.Close() })
	count := new(atomic.Int32)
	go func() {
		conn, err := l.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		for {
			var header [4]byte
			if _, err := io.ReadFull(conn, header[:]); err != nil {
				return
			}
			data := make([]byte, binary.BigEndian.Uint32(header[:]))
			if _, err := io.ReadFull(conn, data); err != nil {
				return
			}
			var q GuestRequest
			if json.Unmarshal(data, &q) != nil {
				return
			}
			count.Add(1)
			p := GuestResponse{Version: 1, Session: q.Session, Game: game, Sequence: q.Sequence, Tick: q.Tick,
				Capabilities: []string{"host-step", "isolated-rgba", "universal-contact"},
				State:        FighterState{Frame: q.Tick, X: q.X, Y: q.Y}, Image: GuestImage{Width: 1, Height: 1, RGBA: []byte{255, 0, 0, 255}}}
			if transform != nil {
				transform(q, &p)
			}
			data, _ = json.Marshal(p)
			binary.BigEndian.PutUint32(header[:], uint32(len(data)))
			if _, err := conn.Write(append(header[:], data...)); err != nil {
				return
			}
		}
	}()
	return PassthroughConfig{Version: 1, Address: l.Addr().String(), Game: game, TimeoutMS: 100, Buttons: map[string]string{"c": "kick", "z": "heavy"}}, count
}

func TestPassthroughIndependentPeersAndInputs(t *testing.T) {
	inputs1, inputs2 := make(chan map[string]bool, 8), make(chan map[string]bool, 8)
	c1, n1 := testPeer(t, "game-one", func(q GuestRequest, p *GuestResponse) {
		if q.Operation == "step" {
			inputs1 <- q.Input
			p.State.X = q.X + 1
		}
	})
	c2, n2 := testPeer(t, "game-two", func(q GuestRequest, p *GuestResponse) {
		if q.Operation == "step" {
			inputs2 <- q.Input
			p.State.X = q.X + 2
		}
	})
	c2.Buttons = map[string]string{"x": "slash", "m": "macro"}
	a, err := newPassthrough(c1)
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := newPassthrough(c2)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	a.Reset(10, 0)
	b.Reset(-10, 0)
	i := InputFrame{Forward: true}
	i.Buttons[2] = true
	i.Buttons[5] = true
	a.Step(i, FrameContext{true, true, 1})
	i = InputFrame{Back: true}
	i.Buttons[3] = true
	i.Buttons[9] = true
	b.Step(i, FrameContext{true, true, -1})
	input1, input2 := <-inputs1, <-inputs2
	if a.View().X != 11 || b.View().X != -8 || !input1["kick"] || !input1["heavy"] || !input1["right"] || !input2["slash"] || !input2["macro"] || !input2["right"] || input2["kick"] {
		t.Fatal("crossed peer state/input mapping", a.View(), b.View(), input1, input2)
	}
	count := n1.Load()
	before := a.View()
	for n := 0; n < 5; n++ {
		a.Step(i, FrameContext{})
	}
	if n1.Load() != count || a.View() != before || n2.Load() != 3 {
		t.Fatal("paused guest advanced")
	}
	a.Step(i, FrameContext{true, false, 1})
	input1 = <-inputs1
	for _, pressed := range input1 {
		if pressed {
			t.Fatal("accepted input outside active round")
		}
	}
	a.CommitHit(HitResult{Accepted: true})
	a.CommitAttack(HitResult{Accepted: true})
	if a.View().Frame != 2 {
		t.Fatal("combat commit advanced source clock")
	}
	a.Reset(0, 0)
	if a.View().Frame != 0 || b.View().Frame != 1 {
		t.Fatal("crossed reset")
	}
	if _, err := a.StateBlob(); err == nil {
		t.Fatal("advertised unsupported snapshot")
	}
}

func TestPassthroughRejectsUntrustedReplies(t *testing.T) {
	cases := map[string]func(GuestRequest, *GuestResponse){
		"wrong-game":     func(q GuestRequest, p *GuestResponse) { p.Game = "other" },
		"wrong-session":  func(q GuestRequest, p *GuestResponse) { p.Session = "stale" },
		"stale-sequence": func(q GuestRequest, p *GuestResponse) { p.Sequence-- },
		"wrong-tick":     func(q GuestRequest, p *GuestResponse) { p.State.Frame++ },
		"bad-image":      func(q GuestRequest, p *GuestResponse) { p.Image.Width = 1025 },
		"inverted-box":   func(q GuestRequest, p *GuestResponse) { p.Hurtboxes = [][4]float32{{2, 0, 1, 5}} },
		"no-stepping":    func(q GuestRequest, p *GuestResponse) { p.Capabilities = []string{"isolated-rgba"} },
		"projectile":     func(q GuestRequest, p *GuestResponse) { p.State.ProjectileID = 1 },
		"timeout":        func(q GuestRequest, p *GuestResponse) { time.Sleep(150 * time.Millisecond) },
	}
	for name, change := range cases {
		t.Run(name, func(t *testing.T) {
			c, _ := testPeer(t, "bad", change)
			r, err := newPassthrough(c)
			if r != nil {
				r.Close()
			}
			if err == nil {
				t.Fatal("accepted invalid peer")
			}
		})
	}
	// A rejected response must not publish any part of its state or image.
	c, _ := testPeer(t, "atomic", func(q GuestRequest, p *GuestResponse) {
		if q.Operation == "step" {
			p.State.X = 999
			p.Sequence--
		}
	})
	r, err := newPassthrough(c)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	before := r.View()
	r.tick++
	if r.exchange("step", nil, FrameContext{}, nil) == nil || r.View() != before {
		t.Fatal("partially published bad reply")
	}
}

func TestPassthroughConfigBounds(t *testing.T) {
	for _, data := range []string{
		`{"version":1,"game":"x","address":"example.com:1234"}`,
		`{"version":1,"game":"x","address":"192.168.1.2:1234"}`,
		`{"version":1,"game":"x","address":"127.0.0.1:0"}`,
		`{"version":1,"game":"x","address":"127.0.0.1:1234","buttons":{"a":"up"}}`,
		`{"version":1,"game":"x","address":"127.0.0.1:1234","buttons":{"a":"p","b":"p"}}`,
		`{"version":1,"game":"x","address":"127.0.0.1:1234","typo":1}`,
		`{"version":1,"game":"x","address":"127.0.0.1:1234} {}`,
	} {
		if _, err := loadPassthroughConfig([]byte(data)); err == nil {
			t.Fatal("accepted", data)
		}
	}
	if _, err := loadPassthroughConfig([]byte(`{"version":1,"game":"x","address":"[::1]:1234","buttons":{"a":"p"}}`)); err != nil {
		t.Fatal(err)
	}
}

func sharedLayerPeer(t *testing.T, caps []string, layer func(GuestRequest) *GuestLayer) PassthroughConfig {
	t.Helper()
	c, _ := testPeer(t, "shared-game", func(q GuestRequest, p *GuestResponse) {
		p.Capabilities = caps
		if l := layer(q); l != nil {
			p.Layer, p.Image = l, GuestImage{}
		}
	})
	c.SharedLayer = true
	return c
}

func goodLayer(value uint64) *GuestLayer {
	return &GuestLayer{Kind: "d3d12-shared", Memory: "rev2-layer-1-memory", Fence: "rev2-layer-1-fence", Value: value,
		Width: 500, Height: 510, Size: 1 << 20, Pivot: [2]float32{250, 480}, Premultiplied: true}
}

func TestPassthroughSharedLayerNegotiation(t *testing.T) {
	all := []string{"host-step", "isolated-rgba", "universal-contact", sharedLayerD3D12}
	var accepted []string
	r, err := newPassthrough(sharedLayerPeer(t, all, func(q GuestRequest) *GuestLayer {
		if q.Operation == "hello" {
			accepted = q.Accept
		}
		return goodLayer(q.Sequence)
	}))
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	if len(accepted) != 1 || accepted[0] != sharedLayerD3D12 || !r.sharedLayer || r.latest.Layer == nil || r.latest.Image.Width != 0 {
		t.Fatalf("negotiation/layer not published: accept=%v shared=%v", accepted, r.sharedLayer)
	}
	r.Step(InputFrame{}, FrameContext{Advance: true, AcceptInput: true, Facing: 1})
	if r.latest.Layer.Value != 2 {
		t.Fatal("layer for the step not published")
	}
	// Without the capability the requested extension fails explicitly.
	if _, err := newPassthrough(sharedLayerPeer(t, all[:3], func(GuestRequest) *GuestLayer { return nil })); err == nil {
		t.Fatal("missing shared-layer capability accepted")
	}
}

func TestPassthroughSharedLayerValidation(t *testing.T) {
	bad := map[string]func(*GuestLayer){
		"name":     func(l *GuestLayer) { l.Memory = `..\evil name` },
		"same":     func(l *GuestLayer) { l.Fence = l.Memory },
		"size":     func(l *GuestLayer) { l.Size = 16 },
		"dims":     func(l *GuestLayer) { l.Width = 5000 },
		"straight": func(l *GuestLayer) { l.Premultiplied = false },
		"pivot":    func(l *GuestLayer) { l.Pivot[0] = float32(math.Inf(1)) },
		"kind":     func(l *GuestLayer) { l.Kind = "vulkan" },
	}
	for name, mutate := range bad {
		l := goodLayer(1)
		mutate(l)
		if validateGuestLayer(*l) == nil {
			t.Errorf("%s: invalid layer accepted", name)
		}
	}
	p := GuestResponse{Layer: goodLayer(1)}
	if validateGuestResponse(p, false) == nil {
		t.Error("layer accepted without negotiation")
	}
	if err := validateGuestResponse(p, true); err != nil {
		t.Errorf("layer-only reply rejected: %v", err)
	}
	if validateGuestResponse(GuestResponse{}, true) == nil {
		t.Error("reply without layer or image accepted")
	}
}

func TestPassthroughSharedLayerFenceOrder(t *testing.T) {
	all := []string{"host-step", "isolated-rgba", "universal-contact", sharedLayerD3D12}
	values := map[uint64]*GuestLayer{1: goodLayer(5), 2: goodLayer(6), 3: goodLayer(6)}
	renamed := goodLayer(1)
	renamed.Memory, renamed.Fence = "rev2-layer-2-memory", "rev2-layer-2-fence"
	values[4] = renamed // recreated resources restart their fence values
	r, err := newPassthrough(sharedLayerPeer(t, all, func(q GuestRequest) *GuestLayer { return values[q.Sequence] }))
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	ctx := FrameContext{Advance: true, AcceptInput: true, Facing: 1}
	if err := r.exchange("step", nil, ctx, nil); err != nil {
		t.Fatalf("increasing fence rejected: %v", err)
	}
	if err := r.exchange("step", nil, ctx, nil); err == nil {
		t.Fatal("repeated fence value accepted")
	}
	if err := r.exchange("step", nil, ctx, nil); err != nil {
		t.Fatalf("renamed layer with restarted fence rejected: %v", err)
	}
}
