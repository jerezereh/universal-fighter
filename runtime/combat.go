package main

// A contact carries attacker intent. The defender decides whether it can guard;
// the arbiter returns one result for both runtimes to commit.
type AttackSpec struct {
	Damage, Chip, Hitstun, Blockstun int
	Hitstop, Guardstop               [2]int
	BlockHigh, BlockLow              bool
	PushX, PushY, Gravity, GuardPush float32
	Knockdown                        bool
}
type DefenseQuery struct {
	CanGuard, Back, Crouch, Air, Down bool
}
type HitResult struct {
	Accepted, Guarded, Knockdown bool
	Damage, Stun                 int
	Hitstop                      [2]int
	PushX, PushY, Gravity        float32
}

func compatibilityAttack(damage, stop int) AttackSpec {
	return AttackSpec{Damage: damage, Hitstun: 15, Blockstun: 14, Hitstop: [2]int{stop, stop},
		Guardstop: [2]int{stop, stop}, BlockHigh: true, BlockLow: true, PushX: 2.4, GuardPush: 1.6, Gravity: .35}
}

func resolveContact(a AttackSpec, d DefenseQuery) HitResult {
	if d.Down {
		return HitResult{}
	}
	r := HitResult{Accepted: true, Damage: a.Damage, Stun: a.Hitstun,
		Hitstop: a.Hitstop, PushX: a.PushX, PushY: a.PushY, Gravity: a.Gravity, Knockdown: a.Knockdown}
	if d.CanGuard && d.Back && !d.Air && ((!d.Crouch && a.BlockHigh) || (d.Crouch && a.BlockLow)) {
		r.Guarded, r.Knockdown = true, false
		r.Damage, r.Stun, r.Hitstop = a.Chip, a.Blockstun, a.Guardstop
		r.PushX, r.PushY, r.Gravity = a.GuardPush, 0, 0
	}
	return r
}

func (r *KOFRuntime) QueryDefense() DefenseQuery {
	s := &r.State
	neutral := s.Action == 1 || s.Action == 2 || s.Action == 3 || s.Action == 25 || s.Action == 26 || s.Action == 27
	return DefenseQuery{CanGuard: neutral || s.Guarded,
		Back: s.BackHeld, Crouch: s.DownHeld, Air: s.Y < 0, Down: s.Knockdown && s.Y == 0}
}
func (r *KOFRuntime) CommitHit(hit HitResult) {
	if !hit.Accepted {
		return
	}
	s := &r.State
	s.Hitstop, s.Stun = hit.Hitstop[1], hit.Stun
	s.DownTime = 0
	s.Guarded, s.Knockdown = hit.Guarded, hit.Knockdown
	s.PushX, s.PushY, s.Gravity = hit.PushX, hit.PushY, hit.Gravity
	s.VX, s.VY, s.YTarget, s.YRate = 0, 0, 0, 0
	action := 106
	if s.DownHeld {
		action = 112
	}
	if hit.Guarded {
		action = 34
		if s.DownHeld {
			action = 36
		}
	}
	r.action(action)
	s.RenderAction, s.RenderElement = action, 0
}

func (r *KOFRuntime) Defeat() {
	r.State.Defeated, r.State.Knockdown = true, true
}
