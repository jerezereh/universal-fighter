package main

import (
	"encoding/json"
	"testing"
)

func TestStateBlobAndHash(t *testing.T) {
	r := &KOFRuntime{Spec: testSpec()}
	r.Reset(40, 0)
	r.CommitHit(HitResult{Accepted: true, Stun: 15, Hitstop: [2]int{7, 7}, PushX: 2})
	r.State.ProjectileID = 3
	blob, err := r.StateBlob()
	if err != nil {
		t.Fatal(err)
	}
	want, err := r.StateHash()
	if err != nil {
		t.Fatal(err)
	}
	ctx := FrameContext{Advance: true, AcceptInput: true, Facing: 1}
	for i := 0; i < 30; i++ {
		r.Step(InputFrame{}, ctx)
	}
	end := r.SaveState()
	if err := r.LoadBlob(blob); err != nil {
		t.Fatal(err)
	}
	got, _ := r.StateHash()
	if got != want {
		t.Fatal("blob restore hash differs")
	}
	for i := 0; i < 30; i++ {
		r.Step(InputFrame{}, ctx)
	}
	if r.State != end {
		t.Fatal("blob replay differs")
	}
	r.LoadBlob(blob)
	r.State.ProjectileID++
	got, _ = r.StateHash()
	if got == want {
		t.Fatal("hash omitted entity activation")
	}
	before := r.SaveState()
	var invalid runtimeStateBlob
	json.Unmarshal(blob, &invalid)
	invalid.Backend = "parry-test"
	bad, _ := json.Marshal(invalid)
	if r.LoadBlob(bad) == nil || r.State != before {
		t.Fatal("wrong backend accepted or mutated state")
	}
	invalid.Backend = r.Backend()
	invalid.Version = 1
	bad, _ = json.Marshal(invalid)
	if r.LoadBlob(bad) == nil || r.State != before {
		t.Fatal("old version accepted or mutated state")
	}
	invalid.Version = 2
	invalid.Spec[0]++
	bad, _ = json.Marshal(invalid)
	if r.LoadBlob(bad) == nil || r.State != before {
		t.Fatal("wrong spec accepted or changed runtime")
	}
	invalid.Spec = r.Spec.Fingerprint
	invalid.State.Element = 999
	bad, _ = json.Marshal(invalid)
	if r.LoadBlob(bad) == nil || r.State != before {
		t.Fatal("invalid element accepted or changed runtime")
	}
	invalid.State.Element, invalid.State.Time = 0, 0
	invalid.State.Action, invalid.State.AirAction = 11, 0
	bad, _ = json.Marshal(invalid)
	if r.LoadBlob(bad) == nil || r.State != before {
		t.Fatal("missing jump transition accepted or changed runtime")
	}
}

func TestRuntimeOwnership(t *testing.T) {
	original := &KOFRuntime{Spec: testSpec()}
	original.Reset(40, 0)
	var runtime FighterRuntime = original
	before, _ := runtime.StateBlob()
	clone := runtime.Clone()
	clone.SetPosition(12, 0)
	clone.Step(InputFrame{Punch: true}, FrameContext{Advance: true, AcceptInput: true, Facing: 1})
	clone.CommitHit(HitResult{Accepted: true, Stun: 12})
	after, _ := runtime.StateBlob()
	if string(before) != string(after) || clone.View() == runtime.View() {
		t.Fatal("runtime clone aliased mutable state")
	}
	view := runtime.View()
	view.X = 99
	if runtime.View().X != 40 {
		t.Fatal("view exposed mutable storage")
	}
	if err := clone.LoadBlob(before); err != nil || clone.View() != runtime.View() {
		t.Fatal("clone restore failed", err)
	}
}
