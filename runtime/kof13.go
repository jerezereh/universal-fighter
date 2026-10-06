package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"math"
)

type KOFFrame struct {
	Duration int
	Calls    []json.RawMessage
	VX, VY   *int `json:"-"`
	Spawn    bool `json:"-"`
}
type KOFSpec struct {
	Fingerprint [32]byte `json:"-"`
	Schema      int
	Backend     string
	Scale       float32
	Actions     map[int][]KOFFrame
	Moves       map[int][]json.RawMessage
	Normal      struct {
		Damage, Hitstop int
		SourceHitback   float32 `json:"source_hitback"`
	}
	Projectile struct {
		Damage, Hitstop, Lifetime, Animation int
		RemoveAnimation                      int `json:"remove_animation"`
		Speed                                float32
		VelocityMul                          float32 `json:"velocity_mul"`
		SpawnX                               float32 `json:"spawn_x"`
	}
}
type KOFRuntime struct {
	Spec  *KOFSpec
	State FighterState
}

func (r *KOFRuntime) Backend() string            { return "kof13" }
func (r *KOFRuntime) View() FighterState         { return r.State }
func (r *KOFRuntime) SetPosition(x, y float32)   { r.State.X, r.State.Y = x, y }
func (r *KOFRuntime) Clone() FighterRuntime      { clone := *r; return &clone }
func (r *KOFRuntime) Presentation() FighterState { return r.presentation() }
func (r *KOFRuntime) CommitAttack(HitResult)     {}
func (r *KOFRuntime) Pose(s FighterState) FighterPose {
	return FighterPose{
		Crouch:    s.Action == 25 || s.Action == 26 || s.Action == 36 || s.Action == 112,
		Moving:    s.Action == 2 || s.Action == 3,
		Attacking: s.Action == 68 || s.Action == 475, Normal: s.Action == 68,
		Down: s.Knockdown && s.Y == 0,
		CanTurn: s.Hitstop == 0 && s.RenderAction != 68 && s.RenderAction != 475 &&
			(s.Action == 1 || s.Action == 2 || s.Action == 3 || s.Action == 26),
	}
}
func (r *KOFRuntime) Normal() AttackSpec {
	return compatibilityAttack(r.Spec.Normal.Damage, r.Spec.Normal.Hitstop)
}
func (r *KOFRuntime) Projectile() (RuntimeProjectile, bool) {
	p := r.Spec.Projectile
	return RuntimeProjectile{Attack: compatibilityAttack(p.Damage, p.Hitstop), Animation: p.Animation,
		RemoveAnimation: p.RemoveAnimation, Lifetime: p.Lifetime, Scale: r.Spec.Scale,
		Speed: p.Speed, VelocityMul: p.VelocityMul, SpawnX: p.SpawnX}, true
}

func loadKOFSpec(data []byte) (*KOFSpec, error) {
	var spec KOFSpec
	if err := json.Unmarshal(data, &spec); err != nil {
		return nil, err
	}
	if spec.Schema != 3 || spec.Backend != "kof13" || spec.Scale <= 0 || spec.Scale > 1 || math.IsNaN(float64(spec.Scale)) {
		return nil, fmt.Errorf("unsupported foreign manifest; reimport the Kyo projectile slice")
	}
	if spec.Normal.Damage < 1 || spec.Normal.Hitstop < 0 || spec.Normal.Hitstop > 60 {
		return nil, fmt.Errorf("invalid imported normal")
	}
	p := spec.Projectile
	if p.Damage < 1 || p.Hitstop < 0 || p.Hitstop > 60 || p.Lifetime < 1 || p.Lifetime > 600 || p.Animation != 534 || p.RemoveAnimation != 538 ||
		p.Speed <= 0 || math.IsInf(float64(p.Speed), 0) || math.IsNaN(float64(p.Speed)) || p.VelocityMul < 0 || p.VelocityMul > 1 || math.IsNaN(float64(p.VelocityMul)) || math.IsInf(float64(p.SpawnX), 0) || math.IsNaN(float64(p.SpawnX)) {
		return nil, fmt.Errorf("invalid imported projectile")
	}
	spawns := 0
	for _, action := range []int{1, 2, 3, 5, 11, 12, 14, 15, 19, 20, 25, 26, 27, 34, 36, 68, 106, 112, 161, 475, 534, 538} {
		frames := spec.Actions[action]
		if len(frames) == 0 {
			return nil, fmt.Errorf("missing action %d", action)
		}
		for i := range frames {
			frame := &frames[i]
			if frame.Duration < 1 {
				return nil, fmt.Errorf("invalid frame duration")
			}
			for _, raw := range frame.Calls {
				var call []json.RawMessage
				if err := json.Unmarshal(raw, &call); err != nil || len(call) != 2 {
					return nil, fmt.Errorf("invalid frame call")
				}
				var name string
				if err := json.Unmarshal(call[0], &name); err != nil {
					return nil, err
				}
				switch name {
				case "CreateObject":
					var args []json.RawMessage
					var object string
					if json.Unmarshal(call[1], &args) != nil || len(args) != 5 || json.Unmarshal(args[0], &object) != nil || object != "闇払い" || action != 475 {
						return nil, fmt.Errorf("unsupported foreign object spawn")
					}
					var x, y float32
					var relativeX, relativeY bool
					if json.Unmarshal(args[1], &x) != nil || json.Unmarshal(args[2], &y) != nil || json.Unmarshal(args[3], &relativeX) != nil || json.Unmarshal(args[4], &relativeY) != nil ||
						x*spec.Scale != p.SpawnX || y != 0 || relativeX || relativeY {
						return nil, fmt.Errorf("unsupported foreign object transform")
					}
					frame.Spawn = true
					spawns++
				case "SetMoveVx", "SetMoveVy":
					var args []float64
					if err := json.Unmarshal(call[1], &args); err != nil || len(args) != 1 || args[0] < 0 || args[0] != math.Trunc(args[0]) {
						return nil, fmt.Errorf("invalid velocity selector")
					}
					id := int(args[0])
					move, ok := spec.Moves[id]
					if !ok || (len(move) != 2 && len(move) != 4) {
						return nil, fmt.Errorf("unsupported velocity move %d", id)
					}
					for _, value := range move[:len(move)-1] {
						var number float32
						if json.Unmarshal(value, &number) != nil || math.IsNaN(float64(number)) || math.IsInf(float64(number), 0) {
							return nil, fmt.Errorf("invalid move number")
						}
					}
					if name == "SetMoveVx" {
						frame.VX = &id
					} else {
						frame.VY = &id
					}
				case "Opt_00", "Opt_01", "Opt_06", "Opt_07", "ChangeTransition", "CreateSound", "CreateEffect":
					// ponytail: source cancels, effects/audio and option flags remain unexecuted.
				default:
					return nil, fmt.Errorf("unsupported behavior method %s", name)
				}
			}
		}
	}
	if spawns != 1 {
		return nil, fmt.Errorf("expected one source projectile spawn")
	}
	spec.Fingerprint = sha256.Sum256(data)
	return &spec, nil
}

func (r *KOFRuntime) Reset(x, y float32) {
	r.State = FighterState{Action: 1, RenderAction: 1, X: x, Y: y}
}
func (r *KOFRuntime) SaveState() FighterState  { return r.State }
func (r *KOFRuntime) LoadState(s FighterState) { r.State = s }
func (r *KOFRuntime) action(a int)             { r.State.Action, r.State.Element, r.State.Time = a, 0, 0 }
func (r *KOFRuntime) move(id int) (initial, target, rate float32) {
	values := r.Spec.Moves[id]
	json.Unmarshal(values[0], &initial)
	target = initial
	if len(values) == 4 {
		json.Unmarshal(values[1], &target)
		json.Unmarshal(values[2], &rate)
	}
	return
}
func (r *KOFRuntime) Step(input InputFrame, context FrameContext) FighterState {
	if !context.Advance {
		return r.State
	}
	s := &r.State
	if !context.AcceptInput {
		input = InputFrame{}
	}
	s.BackHeld, s.DownHeld = input.Back, input.Down
	if s.Hitstop > 0 {
		s.Hitstop--
		return r.presentation()
	}
	if s.Action == 0 {
		r.action(1)
	}
	if s.Stun > 0 || s.Knockdown || s.Defeated || ((s.Action == 106 || s.Action == 112) && s.Y < 0) {
		s.X += s.PushX
		s.Y += s.PushY
		s.PushX *= 0.85 // ponytail: compatibility friction; original hitback formula is not emulated.
		if s.Y < 0 || s.PushY < 0 {
			s.PushY += s.Gravity
		}
		if s.Y >= 0 {
			s.Y, s.PushY = 0, 0
		}
		if s.Knockdown && s.Y == 0 && s.Action != 161 {
			r.action(161)
			s.DownTime = 20 // ponytail: compatibility down recovery, not KOF's recovery rules.
		}
		if s.DownTime > 0 {
			s.DownTime--
		}
		if s.Stun > 0 {
			s.Stun--
		}
		if !s.Defeated && s.Stun == 0 && s.DownTime == 0 && s.Y == 0 {
			s.Guarded, s.Knockdown = false, false
			s.PushX, s.PushY, s.Gravity = 0, 0, 0
			r.action(1)
		}
		s.Frame++
		s.RenderAction, s.RenderElement = s.Action, s.Element
		present := r.presentation()
		r.advanceReaction()
		s.PunchHeld, s.UpHeld, s.SpecialHeld = input.Punch, input.Up, input.Special
		return present
	}
	airborne := s.Action == 12 || s.Action == 15 || s.Action == 20
	locked := airborne || s.Action == 68 || s.Action == 475 || s.Action == 11 || s.Action == 14 || s.Action == 19 || s.Action == 5 || s.Action == 25 || s.Action == 27
	if !locked {
		switch {
		case input.Special && !s.SpecialHeld && !input.Down:
			r.action(475)
		case input.Punch && !s.PunchHeld && !input.Down:
			s.AttackID++
			r.action(68)
		case input.Up && !s.UpHeld:
			s.AirAction = 12
			startup := 11
			if input.Forward != input.Back {
				if input.Forward {
					startup, s.AirAction = 14, 15
				} else {
					startup, s.AirAction = 19, 20
				}
			}
			r.action(startup)
		case input.Down:
			if s.Action != 26 {
				r.action(25)
			}
		case s.Action == 26:
			r.action(27)
		case input.Forward != input.Back:
			a := 2
			if input.Back {
				a = 3
			}
			if s.Action != a {
				r.action(a)
			}
		default:
			if s.Action != 1 {
				r.action(1)
			}
		}
	}
	s.UpHeld = input.Up
	s.PunchHeld = input.Punch
	s.SpecialHeld = input.Special
	frame := r.Spec.Actions[s.Action][s.Element]
	if s.Time == 0 {
		if frame.Spawn && context.AcceptInput {
			s.ProjectileID++
		}
		if frame.VX != nil {
			s.VX, _, _ = r.move(*frame.VX)
		}
		if frame.VY != nil {
			s.VY, s.YTarget, s.YRate = r.move(*frame.VY)
		}
	}
	if context.AcceptInput {
		s.X += s.VX * r.Spec.Scale * context.Facing
		s.Y -= s.VY * r.Spec.Scale
		s.VY += (s.YTarget - s.VY) * s.YRate
	}
	if airborne && s.Y >= 0 && s.VY < 0 {
		s.Y, s.VX, s.VY = 0, 0, 0
		s.YTarget, s.YRate = 0, 0
		r.action(5)
	}
	s.Frame++
	s.RenderAction, s.RenderElement = s.Action, s.Element
	// The returned element is the one simulated this frame, not the next frame's.
	present := *s
	s.Time++
	if s.Time >= r.Spec.Actions[s.Action][s.Element].Duration {
		s.Element++
		s.Time = 0
		if s.Element == len(r.Spec.Actions[s.Action]) {
			switch s.Action {
			case 11, 14, 19:
				r.action(s.AirAction)
			case 25:
				r.action(26)
			case 27, 5, 68, 475:
				r.action(1)
			case 12, 15, 20:
				s.Element-- // Hold final airborne pose until landing.
			default:
				s.Element = 0
			}
		}
	}
	return present
}

func (r *KOFRuntime) presentation() FighterState {
	s := r.State
	s.Action, s.Element = s.RenderAction, s.RenderElement
	return s
}
func (r *KOFRuntime) advanceReaction() {
	s := &r.State
	s.Time++
	frames := r.Spec.Actions[s.Action]
	if s.Time >= frames[s.Element].Duration {
		s.Time = 0
		if s.Element+1 < len(frames) {
			s.Element++
		}
	}
}
