package main

import (
	"encoding/json"
	"testing"
)

func authored(t *testing.T, rules string) *SyntheticRuntime {
	t.Helper()
	r, err := newSynthetic(rules)
	if err != nil {
		t.Fatal(err)
	}
	return r
}

var liveFrame = FrameContext{Advance: true, AcceptInput: true, Facing: 1}

func TestAuthoredParry(t *testing.T) {
	r := authored(t, "parry-test")
	attacker := authored(t, "airdash-test")
	r.Step(InputFrame{Special: true}, liveFrame)
	before, _ := r.StateHash()
	for i := 0; i < 10; i++ {
		h := resolveContact(attacker.Normal(), r.QueryDefense())
		if !h.Accepted || !h.Parried || h.Guarded || h.Damage != 0 || h.Stun != 0 {
			t.Fatalf("parry negotiation: %+v", h)
		}
	}
	after, _ := r.StateHash()
	if before != after {
		t.Fatal("defense query/negotiation mutated state")
	}
	h := resolveContact(attacker.Normal(), r.QueryDefense())
	r.CommitHit(h)
	if r.Extra.Parries != 1 || r.Extra.Parry != 0 || r.State.Hitstop != 2 {
		t.Fatal("parry did not consume window once")
	}
	if resolveContact(attacker.Normal(), r.QueryDefense()).Parried {
		t.Fatal("spent window parried again")
	}
	r.Reset(0, 0)
	r.Step(InputFrame{Special: true}, liveFrame)
	for i := 0; i < 5; i++ {
		r.Step(InputFrame{Special: true}, liveFrame)
	}
	if !r.QueryDefense().Parry {
		t.Fatal("sixth collision tick missing")
	}
	r.Step(InputFrame{Special: true}, liveFrame)
	if resolveContact(attacker.Normal(), r.QueryDefense()).Parried {
		t.Fatal("expired window accepted contact / held X retriggered")
	}
	for i := 0; i < 30; i++ {
		r.Step(InputFrame{Special: true}, liveFrame)
	}
	if r.Extra.Parry != 0 {
		t.Fatal("held X opened another window")
	}
	r.Step(InputFrame{}, liveFrame)
	r.Step(InputFrame{Special: true}, liveFrame)
	if !r.QueryDefense().Parry {
		t.Fatal("released/repressed X failed")
	}
}

func TestAuthoredMobilityAndResources(t *testing.T) {
	r := authored(t, "airdash-test")
	r.Step(InputFrame{Up: true}, liveFrame)
	for r.State.Y == 0 {
		r.Step(InputFrame{}, liveFrame)
	}
	r.Step(InputFrame{Special: true}, liveFrame)
	if r.Extra.Meter != 80 || r.Extra.Charges != 0 || r.Extra.Dashes != 1 {
		t.Fatal("air dash cost/charge")
	}
	r.Step(InputFrame{}, liveFrame)
	r.Step(InputFrame{Special: true}, liveFrame)
	if r.Extra.Meter != 80 || r.Extra.Dashes != 1 {
		t.Fatal("second dash allowed before landing")
	}
	landed := false
	for i := 0; i < 180; i++ {
		r.Step(InputFrame{}, liveFrame)
		if r.State.Y == 0 {
			landed = true
			break
		}
	}
	if !landed || r.Extra.Charges != 1 || r.Extra.Dash != 0 {
		t.Fatal("landing did not restore charge")
	}
	r.Reset(0, 0)
	r.Step(InputFrame{Punch: true}, liveFrame)
	r.Step(InputFrame{Special: true}, liveFrame)
	if r.Extra.Cancels != 0 || r.Extra.Meter != 100 {
		t.Fatal("whiff cancel allowed")
	}
	r.CommitAttack(HitResult{Accepted: true, Parried: true})
	if r.Extra.Confirmed {
		t.Fatal("parry granted cancel confirmation")
	}
	r.CommitAttack(HitResult{Accepted: true, Guarded: true})
	r.Step(InputFrame{}, liveFrame)
	r.Step(InputFrame{Special: true}, liveFrame)
	if r.Extra.Cancels != 1 || r.Extra.Meter != 85 || r.State.Action == 68 {
		t.Fatal("confirmed cancel failed")
	}
	r.Reset(0, 0)
	a := r.Normal()
	if a.Chip == 0 {
		t.Fatal("authored chip must make barrier observable")
	}
	for i := 0; i < 10; i++ {
		r.Step(InputFrame{Back: true, Down: true, Special: true}, liveFrame)
		h := resolveContact(a, r.QueryDefense())
		if !h.Barrier || !h.Guarded || h.Damage != 0 || h.ResourceCost != 10 {
			t.Fatalf("barrier %d: %+v", i, h)
		}
		r.CommitHit(h)
		for r.State.Hitstop > 0 {
			r.Step(InputFrame{Back: true, Down: true, Special: true}, liveFrame)
		}
	}
	if r.Extra.Meter != 0 || r.Extra.Barriers != 10 {
		t.Fatal("resource accounting")
	}
	h := resolveContact(a, r.QueryDefense())
	if h.Barrier || !h.Guarded || h.Damage != a.Chip {
		t.Fatal("exhausted guard still waived chip")
	}
	r.CommitHit(h)
	if r.Extra.Meter != 0 {
		t.Fatal("meter underflow")
	}
	r.Extra.Meter = 19
	r.State.Hitstop, r.State.Stun, r.State.Y, r.State.Action = 0, 0, -30, 12
	r.Extra.Charges = 1
	r.Step(InputFrame{}, liveFrame)
	r.Step(InputFrame{Special: true}, liveFrame)
	if r.Extra.Dashes != 0 {
		t.Fatal("unaffordable dash")
	}
	r.Reset(0, 0)
	r.Extra.Meter = 14
	r.Step(InputFrame{Punch: true}, liveFrame)
	r.CommitAttack(HitResult{Accepted: true})
	r.Step(InputFrame{Special: true}, liveFrame)
	if r.Extra.Cancels != 0 || r.Extra.Meter != 14 {
		t.Fatal("unaffordable confirmed cancel")
	}
	r.Defeat()
	r.Reset(40, 0)
	if r.Extra != (SyntheticState{Meter: 100, Charges: 1}) || r.State.Defeated || r.State.X != 40 {
		t.Fatal("round reset left private state")
	}
}

func TestAuthoredSnapshotAndStops(t *testing.T) {
	for _, rules := range []string{"parry-test", "airdash-test"} {
		r := authored(t, rules)
		r.Step(InputFrame{Special: true}, liveFrame)
		if rules == "airdash-test" {
			r.Extra.Meter, r.Extra.Dash, r.Extra.Confirmed, r.Extra.Charges = 45, 4, true, 0
		}
		r.State.Y, r.State.Action, r.State.RenderAction = -20, 12, 12
		r.State.Time, r.State.Element, r.State.RenderElement = 10, 1, 1
		r.State.Hitstop = 3
		e := r.Extra
		blob, _ := r.StateBlob()
		r.Step(InputFrame{}, FrameContext{})
		paused, _ := r.StateBlob()
		if string(blob) != string(paused) {
			t.Fatal("pause mutated state")
		}
		r.Step(InputFrame{}, liveFrame)
		if r.Extra != e || r.State.Hitstop != 2 {
			t.Fatal("hitstop advanced private clocks")
		}
		clone := r.Clone().(*SyntheticRuntime)
		if rules == "parry-test" {
			clone.Extra.Parries++
		} else {
			clone.Extra.Barriers++
		}
		if r.Extra != e {
			t.Fatal("clone shared private state")
		}
		originalHash, _ := r.StateHash()
		cloneHash, _ := clone.StateHash()
		if originalHash == cloneHash {
			t.Fatal("hash omitted private state")
		}
		r.LoadBlob(blob)
		want := [40][32]byte{}
		for i := range want {
			r.Step(InputFrame{Special: i%9 == 0}, liveFrame)
			want[i], _ = r.StateHash()
		}
		if err := r.LoadBlob(blob); err != nil {
			t.Fatal(err)
		}
		for i := range want {
			r.Step(InputFrame{Special: i%9 == 0}, liveFrame)
			got, _ := r.StateHash()
			if got != want[i] {
				t.Fatalf("%s replay differs at %d", rules, i)
			}
		}
		before, _ := r.StateHash()
		var b syntheticBlob
		json.Unmarshal(blob, &b)
		var body runtimeStateBlob
		json.Unmarshal(b.Body, &body)
		body.Spec[0]++
		wrongSpec, _ := json.Marshal(body)
		otherRules := b.Extra
		if rules == "parry-test" {
			otherRules.Dash = 1
		} else {
			otherRules.Parry = 1
		}
		for _, bad := range []syntheticBlob{
			{Version: 2, Backend: rules, Body: b.Body, Extra: b.Extra},
			{Version: 1, Backend: "wrong", Body: b.Body, Extra: b.Extra},
			{Version: 1, Backend: rules, Body: b.Body, Extra: SyntheticState{Meter: -1}},
			{Version: 1, Backend: rules, Body: wrongSpec, Extra: b.Extra},
			{Version: 1, Backend: rules, Body: b.Body, Extra: otherRules},
		} {
			data, _ := json.Marshal(bad)
			if r.LoadBlob(data) == nil {
				t.Fatal("invalid blob accepted")
			}
			after, _ := r.StateHash()
			if before != after {
				t.Fatal("invalid blob partially committed")
			}
		}
	}
}
