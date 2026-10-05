package main

import "testing"

func TestProjectileSpawnAndDefeat(t *testing.T) {
	r := &KOFRuntime{Spec: testSpec()}
	r.Spec.Actions[475] = []KOFFrame{{Duration: 15}, {Duration: 3, Spawn: true}, {Duration: 39}}
	r.Reset(0, 0)
	ctx := FrameContext{Advance: true, AcceptInput: true, Facing: 1}
	for i := 0; i < 15; i++ {
		r.Step(InputFrame{Special: true}, ctx)
	}
	if r.State.ProjectileID != 0 || r.State.Action != 475 {
		t.Fatal("projectile spawned before the source spawn frame")
	}
	saved := r.SaveState()
	paused := ctx
	paused.Advance = false
	r.Step(InputFrame{}, paused)
	if r.State != saved {
		t.Fatal("pause altered pending projectile spawn")
	}
	r.Step(InputFrame{Special: true}, ctx)
	if r.State.ProjectileID != 1 {
		t.Fatal("source spawn frame did not emit")
	}
	for i := 0; i < 100; i++ {
		r.Step(InputFrame{Special: true}, ctx)
	}
	if r.State.ProjectileID != 1 {
		t.Fatal("held special or multi-tick element duplicated spawn")
	}
	want := r.SaveState()
	r.LoadState(saved)
	for i := 0; i < 101; i++ {
		r.Step(InputFrame{Special: true}, ctx)
	}
	if r.State != want {
		t.Fatal("spawn restore/replay diverged")
	}
	r.CommitHit(HitResult{Accepted: true, Hitstop: [2]int{3, 3}, PushY: -4, Gravity: .5})
	r.Defeat()
	for i := 0; i < 3; i++ {
		r.Step(InputFrame{Special: true}, ctx)
	}
	if r.State.Hitstop != 0 || r.State.Y != 0 {
		t.Fatal("lethal hitstop did not freeze then drain")
	}
	for i := 0; i < 100; i++ {
		r.Step(InputFrame{Special: true}, ctx)
	}
	if r.State.Action != 161 || r.State.Y != 0 || !r.State.Defeated || r.State.ProjectileID != 1 {
		t.Fatal("KO recovered or spawned a new attack")
	}
	r.Reset(40, 0)
	if r.State.Defeated || r.State.ProjectileID != 0 || r.State.SpecialHeld || r.State.Hitstop != 0 {
		t.Fatal("round reset retained lifecycle state")
	}
}

func TestDefenseNegotiation(t *testing.T) {
	a := AttackSpec{Damage: 40, Chip: 3, Hitstun: 20, Blockstun: 12,
		Hitstop: [2]int{7, 8}, Guardstop: [2]int{4, 5}, BlockHigh: true, PushX: 2, PushY: -4, Gravity: .35, Knockdown: true}
	d := DefenseQuery{CanGuard: true, Back: true}
	guard := resolveContact(a, d)
	if !guard.Guarded || guard.Damage != 3 || guard.Stun != 12 || guard.Hitstop != [2]int{4, 5} || guard.Knockdown || guard.PushY != 0 {
		t.Fatal("high guard did not negotiate one complete guard result", guard)
	}
	d.Crouch = true
	if resolveContact(a, d).Guarded {
		t.Fatal("crouch guarded an overhead")
	}
	a.BlockHigh, a.BlockLow = false, true
	if !resolveContact(a, d).Guarded {
		t.Fatal("low guard failed")
	}
	d.Crouch = false
	if resolveContact(a, d).Guarded {
		t.Fatal("standing guard blocked a low")
	}
	d.Air = true
	if resolveContact(a, d).Guarded {
		t.Fatal("slice unexpectedly supports air guard")
	}
	d.Down = true
	if resolveContact(a, d).Accepted {
		t.Fatal("downed defender accepted another contact")
	}
}

func TestNormalAndReactionClocks(t *testing.T) {
	r := &KOFRuntime{Spec: testSpec()}
	r.Reset(0, 0)
	ctx := FrameContext{Advance: true, AcceptInput: true, Facing: 1}
	r.Step(InputFrame{Punch: true}, ctx)
	if r.State.AttackID != 1 {
		t.Fatal("normal did not acquire an activation id")
	}
	for i := 0; i < 30; i++ {
		r.Step(InputFrame{Punch: true}, ctx)
	}
	if r.State.AttackID != 1 {
		t.Fatal("held punch repeated normal")
	}
	r.Step(InputFrame{}, ctx)
	r.Step(InputFrame{Punch: true}, ctx)
	if r.State.AttackID != 2 {
		t.Fatal("second press did not acquire a new activation")
	}
	hit := resolveContact(AttackSpec{Hitstun: 12, Hitstop: [2]int{3, 4}, PushX: 2}, DefenseQuery{})
	r.CommitHit(hit)
	saved := r.SaveState()
	paused := ctx
	paused.Advance = false
	r.Step(InputFrame{Forward: true}, paused)
	if r.State != saved {
		t.Fatal("global pause drained contact hitstop")
	}
	for i := 0; i < 4; i++ {
		f := r.Step(InputFrame{Forward: true}, ctx)
		if f.X != saved.X || f.Frame != saved.Frame || f.Action != 106 || r.State.Stun != 12 {
			t.Fatal("hitstop advanced motion, pose or hitstun")
		}
	}
	r.Step(InputFrame{Forward: true}, ctx)
	if r.State.X <= saved.X || r.State.Stun != 11 || r.State.Action != 106 {
		t.Fatal("reaction did not resume with knockback")
	}
	for i := 0; i < 30; i++ {
		r.Step(InputFrame{}, ctx)
	}
	want := r.SaveState()
	r.LoadState(saved)
	for i := 0; i < 35; i++ {
		r.Step(InputFrame{}, ctx)
	}
	if r.State != want {
		t.Fatal("contact restore/replay diverged")
	}
	r.Reset(0, 0)
	// Hitstun expires before landing; down recovery must still be visible.
	hit.Knockdown, hit.PushY, hit.Gravity, hit.Stun = true, -4, .5, 5
	r.CommitHit(hit)
	air, down, recovered := false, false, false
	downFrames := 0
	for i := 0; i < 100; i++ {
		f := r.Step(InputFrame{}, ctx)
		air = air || f.Y < 0
		down = down || f.Action == 161
		if f.Action == 161 {
			downFrames++
		}
		recovered = recovered || (air && r.State.Action == 1)
	}
	if !air || !down || !recovered || downFrames < 10 {
		t.Fatal("launch/down/recovery lifecycle failed")
	}
	r.Reset(0, 0)
	if r.State.AttackID != 0 || r.State.Stun != 0 || r.State.Hitstop != 0 || r.State.Knockdown {
		t.Fatal("round reset leaked combat state")
	}
}
