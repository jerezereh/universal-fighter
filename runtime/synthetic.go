package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
)

// ponytail: authored rules share the existing body/reaction clock, not a second physics engine.
// These are compatibility experiments, not SFIII or Guilty Gear implementations.
type SyntheticRuntime struct {
	KOFRuntime
	Rules string
	Extra SyntheticState
}

type SyntheticState struct {
	Meter, Parry, Cooldown, Dash, Charges int
	Confirmed, DefenseHeld                bool
	Parries, Dashes, Cancels, Barriers    uint64
}

func newSynthetic(rules string) (*SyntheticRuntime, error) {
	if rules != "parry-test" && rules != "airdash-test" {
		return nil, fmt.Errorf("unknown authored ruleset %s", rules)
	}
	spec := &KOFSpec{Scale: 1, Actions: map[int][]KOFFrame{}, Moves: map[int][]json.RawMessage{}}
	for _, a := range []int{1, 2, 3, 5, 11, 12, 14, 15, 19, 20, 25, 26, 27, 34, 36, 106, 112, 161} {
		spec.Actions[a] = []KOFFrame{{Duration: 4}}
	}
	spec.Actions[68] = []KOFFrame{{Duration: 4}, {Duration: 3}, {Duration: 11}}
	spec.Normal.Damage, spec.Normal.Hitstop = 30, 5
	for id, values := range map[int]string{0: "[0,0]", 1: "[2,0]", 2: "[-1.5,0]", 3: "[8,-9,0.08,0]", 4: "[2.4,0]", 5: "[-2.4,0]"} {
		var move []json.RawMessage
		json.Unmarshal([]byte(values), &move)
		spec.Moves[id] = move
	}
	for a, id := range map[int]int{1: 0, 2: 1, 3: 2, 5: 0, 11: 0, 14: 4, 19: 5, 25: 0, 68: 0} {
		value := id
		spec.Actions[a][0].VX = &value
	}
	for _, a := range []int{12, 15, 20} {
		value := 3
		spec.Actions[a] = []KOFFrame{{Duration: 1}, {Duration: 600}}
		spec.Actions[a][0].VY = &value
	}
	// Includes durations, move data and explicit selector associations (selectors aren't JSON fields).
	data, _ := json.Marshal(spec)
	spec.Fingerprint = sha256.Sum256(append(data, []byte("synthetic-v1: VX=1:0,2:1,3:2,5:0,11:0,14:4,19:5,25:0,68:0; VY=12:3,15:3,20:3")...))
	r := &SyntheticRuntime{KOFRuntime: KOFRuntime{Spec: spec}, Rules: rules}
	r.Reset(0, 0)
	return r, nil
}

func (r *SyntheticRuntime) Backend() string       { return r.Rules }
func (r *SyntheticRuntime) Clone() FighterRuntime { clone := *r; return &clone }
func (r *SyntheticRuntime) Reset(x, y float32) {
	r.KOFRuntime.Reset(x, y)
	r.Extra = SyntheticState{Meter: 100, Charges: 1}
}
func (r *SyntheticRuntime) Projectile() (RuntimeProjectile, bool) { return RuntimeProjectile{}, false }
func (r *SyntheticRuntime) Normal() AttackSpec {
	a := r.KOFRuntime.Normal()
	a.Chip = 3
	return a
}
func (r *SyntheticRuntime) Diagnostics() string {
	e := r.Extra
	return fmt.Sprintf("meter:%d parry:%d cooldown:%d dash:%d charge:%d confirm:%t parries:%d dashes:%d cancels:%d barriers:%d", e.Meter, e.Parry, e.Cooldown, e.Dash, e.Charges, e.Confirmed, e.Parries, e.Dashes, e.Cancels, e.Barriers)
}
func (r *SyntheticRuntime) Overlay() string {
	return fmt.Sprintf("meter:%d parry:%d dash:%d charge:%d", r.Extra.Meter, r.Extra.Parry, r.Extra.Dash, r.Extra.Charges)
}

func (r *SyntheticRuntime) Step(input InputFrame, context FrameContext) FighterState {
	s, e := &r.State, &r.Extra
	if !context.Advance || s.Hitstop > 0 {
		return r.KOFRuntime.Step(input, context)
	}
	if !context.AcceptInput {
		input = InputFrame{}
	}
	specialHeld := input.Special
	special := specialHeld && !s.SpecialHeld
	neutral := r.QueryDefense().CanGuard && s.Stun == 0 && !s.Knockdown && !s.Defeated
	e.DefenseHeld = r.Rules == "airdash-test" && input.Back && input.Special
	if e.Parry > 0 {
		e.Parry--
	}
	if e.Cooldown > 0 {
		e.Cooldown--
	}
	if r.Rules == "parry-test" && special && neutral && s.Y == 0 && e.Cooldown == 0 {
		e.Parry, e.Cooldown = 6, 18
	}
	if r.Rules == "airdash-test" && special && !e.DefenseHeld && !s.Defeated && s.Stun == 0 && !s.Knockdown {
		switch {
		case s.Action == 68 && e.Confirmed && e.Meter >= 15:
			e.Meter -= 15
			e.Cancels++
			e.Confirmed = false
			r.action(1)
		case s.Y < 0 && e.Charges > 0 && e.Meter >= 20:
			e.Meter -= 20
			e.Charges--
			e.Dashes++
			e.Dash = 8
		}
	}
	if e.Dash > 0 && s.Stun == 0 && !s.Knockdown {
		s.VX, s.VY = 6, 0
		e.Dash--
	}
	previous := s.AttackID
	input.Special = false // Special belongs to the authored rules, never the Kyo projectile action.
	present := r.KOFRuntime.Step(input, context)
	s.SpecialHeld = specialHeld
	if s.AttackID != previous {
		e.Confirmed = false
	}
	if s.Y == 0 {
		e.Charges, e.Dash = 1, 0
	}
	if e.Dash == 0 && present.Y < 0 && present.VX == 6 {
		s.VX = 0
	}
	return present
}

func (r *SyntheticRuntime) QueryDefense() DefenseQuery {
	d := r.KOFRuntime.QueryDefense()
	d.Parry = r.Rules == "parry-test" && r.Extra.Parry > 0 && d.CanGuard && !d.Air && r.State.Stun == 0
	d.Barrier = r.Rules == "airdash-test" && r.Extra.DefenseHeld && r.Extra.Meter >= 10
	return d
}
func (r *SyntheticRuntime) CommitHit(hit HitResult) {
	if !hit.Accepted {
		return
	}
	r.Extra.Parry, r.Extra.Dash, r.Extra.Confirmed = 0, 0, false
	if hit.Parried {
		r.Extra.Parries++
		r.State.Hitstop = hit.Hitstop[1]
		return
	}
	if hit.Barrier {
		r.Extra.Meter -= hit.ResourceCost
		r.Extra.Barriers++
	}
	r.KOFRuntime.CommitHit(hit)
}
func (r *SyntheticRuntime) CommitAttack(hit HitResult) {
	if r.Rules == "airdash-test" && hit.Accepted && !hit.Parried && r.State.Action == 68 {
		r.Extra.Confirmed = true
	}
}

type syntheticBlob struct {
	Version int
	Backend string
	Body    json.RawMessage
	Extra   SyntheticState
}

func (r *SyntheticRuntime) StateBlob() ([]byte, error) {
	body, err := r.KOFRuntime.StateBlob()
	if err != nil {
		return nil, err
	}
	return json.Marshal(syntheticBlob{1, r.Backend(), body, r.Extra})
}
func (r *SyntheticRuntime) LoadBlob(data []byte) error {
	var b syntheticBlob
	if err := json.Unmarshal(data, &b); err != nil {
		return err
	}
	e := b.Extra
	if b.Version != 1 || b.Backend != r.Backend() || e.Meter < 0 || e.Meter > 100 || e.Parry < 0 || e.Parry > 6 || e.Cooldown < 0 || e.Cooldown > 18 || e.Dash < 0 || e.Dash > 8 || e.Charges < 0 || e.Charges > 1 {
		return fmt.Errorf("invalid authored ruleset snapshot")
	}
	if (r.Rules == "parry-test" && (e.Dash != 0 || e.Meter != 100 || e.Confirmed || e.DefenseHeld || e.Dashes != 0 || e.Cancels != 0 || e.Barriers != 0)) ||
		(r.Rules == "airdash-test" && (e.Parry != 0 || e.Cooldown != 0 || e.Parries != 0)) {
		return fmt.Errorf("snapshot contains mechanics from a different ruleset")
	}
	clone := *r
	if err := clone.KOFRuntime.LoadBlob(b.Body); err != nil {
		return err
	}
	clone.Extra = e
	*r = clone
	return nil
}
func (r *SyntheticRuntime) StateHash() ([32]byte, error) {
	data, err := r.StateBlob()
	return sha256.Sum256(data), err
}
