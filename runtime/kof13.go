package main

import (
	"encoding/json"
	"fmt"
	"math"
)

type InputFrame struct{ Forward, Back, Up, Down bool }
type FrameContext struct {
	Advance, AcceptInput bool
	Facing               float32
}
type FighterState struct {
	Frame                            uint64
	Action, Element, Time, AirAction int
	X, Y, VX, VY                     float32
	YTarget, YRate                   float32
	UpHeld                           bool
}

// This is the current locomotion subset of the runtime API. Combat is a later gate.
type FighterRuntime interface {
	Step(InputFrame, FrameContext) FighterState
	Reset(float32, float32)
	SaveState() FighterState
	LoadState(FighterState)
}

type KOFFrame struct {
	Duration int
	Calls    []json.RawMessage
	VX, VY   *int `json:"-"`
}
type KOFSpec struct {
	Schema  int
	Backend string
	Scale   float32
	Actions map[int][]KOFFrame
	Moves   map[int][]json.RawMessage
}
type KOFRuntime struct {
	Spec  *KOFSpec
	State FighterState
}

func loadKOFSpec(data []byte) (*KOFSpec, error) {
	var spec KOFSpec
	if err := json.Unmarshal(data, &spec); err != nil {
		return nil, err
	}
	if spec.Schema != 1 || spec.Backend != "kof13-locomotion" || spec.Scale <= 0 || spec.Scale > 1 {
		return nil, fmt.Errorf("unsupported foreign manifest")
	}
	for _, action := range []int{1, 2, 3, 5, 11, 12, 14, 15, 19, 20, 25, 26, 27} {
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
				case "Opt_01", "Opt_07", "ChangeTransition", "CreateSound", "CreateEffect":
					// ponytail: locomotion only; effects/audio and source transition flags are retained but not executed.
				default:
					return nil, fmt.Errorf("unsupported behavior method %s", name)
				}
			}
		}
	}
	return &spec, nil
}

func (r *KOFRuntime) Reset(x, y float32)       { r.State = FighterState{Action: 1, X: x, Y: y} }
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
	if s.Action == 0 {
		r.action(1)
	}
	if !context.AcceptInput {
		input = InputFrame{}
	}
	airborne := s.Action == 12 || s.Action == 15 || s.Action == 20
	locked := airborne || s.Action == 11 || s.Action == 14 || s.Action == 19 || s.Action == 5 || s.Action == 25 || s.Action == 27
	if !locked {
		switch {
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
	frame := r.Spec.Actions[s.Action][s.Element]
	if s.Time == 0 {
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
			case 27, 5:
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
