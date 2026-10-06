package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"math"
)

type runtimeStateBlob struct {
	Version int
	Backend string
	Spec    [32]byte
	State   FighterState
}

func (r *KOFRuntime) StateBlob() ([]byte, error) {
	return json.Marshal(runtimeStateBlob{2, r.Backend(), r.Spec.Fingerprint, r.State})
}

func (r *KOFRuntime) LoadBlob(data []byte) error {
	var blob runtimeStateBlob
	if err := json.Unmarshal(data, &blob); err != nil {
		return err
	}
	if blob.Version != 2 || blob.Backend != r.Backend() || blob.Spec != r.Spec.Fingerprint {
		return fmt.Errorf("runtime state version/spec mismatch")
	}
	s := blob.State
	frames, render := r.Spec.Actions[s.Action], r.Spec.Actions[s.RenderAction]
	needsAirAction := s.Action == 11 || s.Action == 14 || s.Action == 19
	if s.Element < 0 || s.Element >= len(frames) || s.RenderElement < 0 || s.RenderElement >= len(render) ||
		((s.AirAction != 0 || needsAirAction) && len(r.Spec.Actions[s.AirAction]) == 0) ||
		s.Time < 0 || s.Time >= frames[s.Element].Duration || s.Hitstop < 0 || s.Stun < 0 || s.DownTime < 0 {
		return fmt.Errorf("invalid runtime action/clock state")
	}
	for _, value := range []float32{s.X, s.Y, s.VX, s.VY, s.YTarget, s.YRate, s.PushX, s.PushY, s.Gravity} {
		if math.IsNaN(float64(value)) || math.IsInf(float64(value), 0) {
			return fmt.Errorf("non-finite runtime transform")
		}
	}
	r.LoadState(s)
	return nil
}

func (r *KOFRuntime) StateHash() ([32]byte, error) {
	data, err := r.StateBlob()
	if err != nil {
		return [32]byte{}, err
	}
	return sha256.Sum256(data), nil
}
