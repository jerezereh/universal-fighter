package main

import (
	"encoding/json"
	"os"
	"testing"
)

func testSpec() *KOFSpec {
	s := &KOFSpec{Scale: 1, Actions: map[int][]KOFFrame{}, Moves: map[int][]json.RawMessage{
		0: {json.RawMessage("0"), json.RawMessage("false")},
		1: {json.RawMessage("2"), json.RawMessage("false")},
		2: {json.RawMessage("-2"), json.RawMessage("false")},
		4: {json.RawMessage("8"), json.RawMessage("-8"), json.RawMessage("0.2"), json.RawMessage("false")},
	}}
	zero, one, two, four := 0, 1, 2, 4
	for _, a := range []int{1, 2, 3, 5, 11, 12, 14, 15, 19, 20, 25, 26, 27, 34, 36, 68, 106, 112, 161} {
		s.Actions[a] = []KOFFrame{{Duration: 2, VX: &zero, VY: &zero}}
	}
	s.Actions[2][0].VX = &one
	s.Actions[3][0].VX = &two
	for _, a := range []int{12, 15, 20} {
		s.Actions[a] = []KOFFrame{{Duration: 100, VY: &four}}
	}
	return s
}

func exercise(t *testing.T, spec *KOFSpec) {
	t.Helper()
	r := &KOFRuntime{Spec: spec}
	r.Reset(0, 0)
	ctx := FrameContext{Advance: true, AcceptInput: true, Facing: 1}
	r.Step(InputFrame{Forward: true}, ctx)
	if r.State.X <= 0 || r.State.Action != 2 {
		t.Fatal("forward movement did not use foreign runtime")
	}
	x := r.State.X
	r.Step(InputFrame{Back: true}, ctx)
	if r.State.X >= x {
		t.Fatal("back movement did not reverse")
	}
	r.Step(InputFrame{Down: true}, ctx)
	for i := 0; i < 30 && r.State.Action != 26; i++ {
		r.Step(InputFrame{Down: true}, ctx)
	}
	if r.State.Action != 26 {
		t.Fatal("crouch startup did not finish")
	}
	r.Step(InputFrame{}, ctx)
	for i := 0; i < 30 && r.State.Action != 1; i++ {
		r.Step(InputFrame{}, ctx)
	}
	if r.State.Action != 1 {
		t.Fatal("crouch release did not finish")
	}
	r.Step(InputFrame{Up: true}, ctx)
	air, land := false, false
	for i := 0; i < 240; i++ {
		f := r.Step(InputFrame{Up: true}, ctx)
		if f.Y < 0 {
			air = true
		}
		if air && f.Y == 0 {
			land = true
			break
		}
	}
	if !air || !land {
		t.Fatal("source movement did not complete jump/landing")
	}
	for i := 0; i < 40; i++ {
		r.Step(InputFrame{Up: true}, ctx)
	}
	if r.State.Y != 0 {
		t.Fatal("held up retriggered jump")
	}
	saved := r.SaveState()
	paused := ctx
	paused.Advance = false
	for i := 0; i < 20; i++ {
		r.Step(InputFrame{Forward: true}, paused)
	}
	if r.State != saved {
		t.Fatal("paused runtime changed")
	}
	r.Step(InputFrame{Forward: true}, ctx)
	if r.State.Frame != saved.Frame+1 {
		t.Fatal("frame advance did not step exactly once")
	}
	r.LoadState(saved)
	for i := 0; i < 60; i++ {
		r.Step(InputFrame{Forward: true}, ctx)
	}
	expected := r.SaveState()
	r.LoadState(saved)
	for i := 0; i < 60; i++ {
		r.Step(InputFrame{Forward: true}, ctx)
	}
	if r.State != expected {
		t.Fatal("restore/replay diverged")
	}
	r.Reset(40, 0)
	if r.State.Frame != 0 || r.State.X != 40 || r.State.Action != 1 {
		t.Fatal("round reset leaked state")
	}
}
func TestLocomotion(t *testing.T) { exercise(t, testSpec()) }
func TestInstalledLocomotion(t *testing.T) {
	path := os.Getenv("UF_KOF_SPEC")
	if path == "" {
		t.Skip("set UF_KOF_SPEC to validate a locally imported manifest")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	spec, err := loadKOFSpec(data)
	if err != nil {
		t.Fatal(err)
	}
	exercise(t, spec)
}
