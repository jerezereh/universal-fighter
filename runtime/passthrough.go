package main

import (
	"bytes"
	"crypto/rand"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"strconv"
	"time"
)

const passthroughVersion = 1
const passthroughLimit = 8 << 20

// One connection per fighter. Game identifiers are configuration, never host branches.
type PassthroughConfig struct {
	Version   int               `json:"version"`
	Address   string            `json:"address"`
	Game      string            `json:"game"`
	TimeoutMS int               `json:"timeout_ms"`
	Buttons   map[string]string `json:"buttons"`
}
type GuestOpponent struct {
	X, Y, Facing        float32
	Life                int32
	AttackID            uint64
	Hitboxes, Hurtboxes [][4]float32
}
type GuestRequest struct {
	Version   int             `json:"version"`
	Session   string          `json:"session"`
	Game      string          `json:"game"`
	Sequence  uint64          `json:"sequence"`
	Tick      uint64          `json:"tick"`
	Operation string          `json:"operation"`
	Input     map[string]bool `json:"input,omitempty"`
	Context   FrameContext    `json:"context"`
	X, Y      float32
	Life      int32
	Opponent  *GuestOpponent `json:"opponent,omitempty"`
	Result    *HitResult     `json:"result,omitempty"`
}

// Pixels are tightly packed, top-down, straight-alpha RGBA; geometry faces right.
// The guest maps source units to character-local IKEMEN units, Y negative upwards.
type GuestImage struct {
	Width, Height int
	Pivot         [2]int16
	RGBA          []byte
}
type GuestResponse struct {
	Version      int          `json:"version"`
	Session      string       `json:"session"`
	Game         string       `json:"game"`
	Sequence     uint64       `json:"sequence"`
	Tick         uint64       `json:"tick"`
	Error        string       `json:"error,omitempty"`
	Capabilities []string     `json:"capabilities,omitempty"`
	State        FighterState `json:"state"`
	Pose         FighterPose  `json:"pose"`
	Defense      DefenseQuery `json:"defense"`
	Attack       AttackSpec   `json:"attack"`
	Hitboxes     [][4]float32 `json:"hitboxes"`
	Hurtboxes    [][4]float32 `json:"hurtboxes"`
	Image        GuestImage   `json:"image"`
}
type PassthroughRuntime struct {
	config         PassthroughConfig
	conn           net.Conn
	session        string
	sequence, tick uint64
	latest         GuestResponse
	x, y           float32
	life           int32
	opponent       *GuestOpponent
	latency        time.Duration
}

func strictJSON(data []byte, target any) error {
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(target); err != nil {
		return err
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return fmt.Errorf("trailing JSON data")
	}
	return nil
}
func loadPassthroughConfig(data []byte) (PassthroughConfig, error) {
	var c PassthroughConfig
	if len(data) > 16384 {
		return c, fmt.Errorf("passthrough config too large")
	}
	if err := strictJSON(data, &c); err != nil {
		return c, err
	}
	host, port, err := net.SplitHostPort(c.Address)
	n, portErr := strconv.Atoi(port)
	ip := net.ParseIP(host)
	if err != nil || portErr != nil || n < 1 || n > 65535 || ip == nil || !ip.IsLoopback() {
		return c, fmt.Errorf("passthrough address must be a numeric loopback endpoint")
	}
	if c.Version != passthroughVersion || len(c.Game) == 0 || len(c.Game) > 128 {
		return c, fmt.Errorf("invalid passthrough version/game identity")
	}
	if c.TimeoutMS == 0 {
		c.TimeoutMS = 250
	}
	if c.TimeoutMS < 50 || c.TimeoutMS > 2000 {
		return c, fmt.Errorf("timeout_ms must be 50..2000")
	}
	seen := map[string]bool{"forward": true, "back": true, "up": true, "down": true, "left": true, "right": true}
	for button, name := range c.Buttons {
		if len(button) != 1 || !bytes.ContainsRune([]byte("abcxyzsdwm"), rune(button[0])) || len(name) == 0 || len(name) > 32 || seen[name] {
			return c, fmt.Errorf("invalid or duplicate button mapping %q -> %q", button, name)
		}
		seen[name] = true
	}
	return c, nil
}

func newPassthrough(c PassthroughConfig) (*PassthroughRuntime, error) {
	conn, err := net.DialTimeout("tcp", c.Address, time.Duration(c.TimeoutMS)*time.Millisecond)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, 16)
	if _, err = rand.Read(nonce); err != nil {
		conn.Close()
		return nil, err
	}
	r := &PassthroughRuntime{config: c, conn: conn, session: hex.EncodeToString(nonce)}
	if err = r.exchange("hello", nil, FrameContext{}, nil); err != nil {
		r.Close()
		return nil, err
	}
	required := map[string]bool{"host-step": false, "isolated-rgba": false, "universal-contact": false}
	for _, cap := range r.latest.Capabilities {
		if _, ok := required[cap]; ok {
			required[cap] = true
		}
	}
	for cap, supported := range required {
		if !supported {
			r.Close()
			return nil, fmt.Errorf("guest %s lacks %s", c.Game, cap)
		}
	}
	return r, nil
}

// ponytail: CPU RGBA in bounded JSON, replace with shared GPU frames only after profiling.
func (r *PassthroughRuntime) exchange(op string, input map[string]bool, ctx FrameContext, result *HitResult) error {
	if r.conn == nil {
		return fmt.Errorf("guest connection closed")
	}
	started := time.Now()
	r.sequence++
	q := GuestRequest{Version: passthroughVersion, Session: r.session, Game: r.config.Game, Sequence: r.sequence, Tick: r.tick,
		Operation: op, Input: input, Context: ctx, X: r.x, Y: r.y, Life: r.life, Opponent: r.opponent, Result: result}
	data, err := json.Marshal(q)
	if err != nil {
		return err
	}
	if err = r.conn.SetDeadline(time.Now().Add(time.Duration(r.config.TimeoutMS) * time.Millisecond)); err != nil {
		return err
	}
	var header [4]byte
	binary.BigEndian.PutUint32(header[:], uint32(len(data)))
	if _, err = io.Copy(r.conn, bytes.NewReader(append(header[:], data...))); err != nil {
		return err
	}
	if _, err = io.ReadFull(r.conn, header[:]); err != nil {
		return err
	}
	size := binary.BigEndian.Uint32(header[:])
	if size == 0 || size > passthroughLimit {
		return fmt.Errorf("guest message exceeds bounds: %d", size)
	}
	data = make([]byte, size)
	if _, err = io.ReadFull(r.conn, data); err != nil {
		return err
	}
	var reply GuestResponse
	if err = strictJSON(data, &reply); err != nil {
		return err
	}
	if reply.Version != passthroughVersion || reply.Session != r.session || reply.Game != r.config.Game || reply.Sequence != r.sequence || reply.Tick != r.tick || reply.State.Frame != r.tick {
		return fmt.Errorf("guest identity/sequence/frame mismatch")
	}
	if reply.Error != "" {
		return fmt.Errorf("guest error: %s", reply.Error)
	}
	if err = validateGuestResponse(reply); err != nil {
		return err
	}
	r.latest = reply // Publish image, collision and state together, only after validation.
	r.x, r.y = reply.State.X, reply.State.Y
	r.latency = time.Since(started)
	return nil
}
func finiteGuest(v float32) bool {
	return !math.IsNaN(float64(v)) && !math.IsInf(float64(v), 0) && math.Abs(float64(v)) <= 1e6
}

func guestTexturePixels(rgba []byte) []byte {
	data := append([]byte(nil), rgba...)
	for n := 0; n < len(data); n += 4 {
		for channel := 0; channel < 3; channel++ {
			data[n+channel] = byte((int(data[n+channel])*int(data[n+3]) + 127) / 255)
		}
	}
	return data
}
func validateGuestResponse(p GuestResponse) error {
	i, s, a := p.Image, p.State, p.Attack
	if i.Width < 1 || i.Height < 1 || i.Width > 1024 || i.Height > 1024 || len(i.RGBA) != i.Width*i.Height*4 {
		return fmt.Errorf("invalid RGBA dimensions/payload")
	}
	for _, v := range []float32{s.X, s.Y, s.VX, s.VY, s.YTarget, s.YRate, s.PushX, s.PushY, s.Gravity, a.PushX, a.PushY, a.Gravity, a.GuardPush} {
		if !finiteGuest(v) {
			return fmt.Errorf("invalid guest transform")
		}
	}
	for _, n := range []int{s.Action, s.RenderAction, s.Element, s.RenderElement, s.Time, s.Hitstop, s.Stun, s.DownTime, a.Damage, a.Chip, a.Hitstun, a.Blockstun, a.Hitstop[0], a.Hitstop[1], a.Guardstop[0], a.Guardstop[1]} {
		if n < 0 || n > 100000 {
			return fmt.Errorf("invalid guest clock/attack value")
		}
	}
	if s.ProjectileID != 0 {
		return fmt.Errorf("passthrough v1 does not support projectile entities")
	}
	if p.Pose.Normal && (!p.Pose.Attacking || s.AttackID == 0) {
		return fmt.Errorf("normal lacks attack activation")
	}
	for _, boxes := range [][][4]float32{p.Hitboxes, p.Hurtboxes} {
		if len(boxes) > 64 {
			return fmt.Errorf("too many guest collision boxes")
		}
		for _, b := range boxes {
			for _, v := range b {
				if !finiteGuest(v) {
					return fmt.Errorf("invalid guest collision")
				}
			}
			if b[0] > b[2] || b[1] > b[3] {
				return fmt.Errorf("inverted guest collision")
			}
		}
	}
	if len(p.Hitboxes) > 0 && !p.Pose.Normal {
		return fmt.Errorf("hitboxes outside normal activation")
	}
	return nil
}
func (r *PassthroughRuntime) call(op string, input map[string]bool, ctx FrameContext, result *HitResult) {
	if err := r.exchange(op, input, ctx, result); err != nil {
		r.Close()
		panic(fmt.Sprintf("passthrough %s %s: %v", r.config.Game, op, err))
	}
}
func (r *PassthroughRuntime) Backend() string               { return "passthrough:" + r.config.Game }
func (r *PassthroughRuntime) View() FighterState            { return r.latest.State }
func (r *PassthroughRuntime) Presentation() FighterState    { return r.View() }
func (r *PassthroughRuntime) Pose(FighterState) FighterPose { return r.latest.Pose }
func (r *PassthroughRuntime) Step(i InputFrame, ctx FrameContext) FighterState {
	if !ctx.Advance {
		return r.View()
	} // Pause/hitpause produces no guest tick or IPC input.
	buttons := i.Buttons
	buttons[0], buttons[1] = buttons[0] || i.Punch, buttons[1] || i.Special
	input := map[string]bool{"forward": i.Forward, "back": i.Back, "up": i.Up, "down": i.Down,
		"left":  i.Back && ctx.Facing > 0 || i.Forward && ctx.Facing < 0,
		"right": i.Forward && ctx.Facing > 0 || i.Back && ctx.Facing < 0}
	for n, key := range "abcxyzsdwm" {
		if name, ok := r.config.Buttons[string(key)]; ok {
			input[name] = buttons[n]
		}
	}
	if !ctx.AcceptInput {
		for name := range input {
			input[name] = false
		}
	}
	r.tick++
	r.call("step", input, ctx, nil)
	return r.View()
}
func (r *PassthroughRuntime) SetPosition(x, y float32) { r.x, r.y = x, y }
func (r *PassthroughRuntime) Reset(x, y float32) {
	if r.conn == nil {
		fresh, err := newPassthrough(r.config)
		if err != nil {
			panic(err)
		}
		fresh.life = r.life
		*r = *fresh
	}
	r.x, r.y, r.tick, r.opponent = x, y, 0, nil
	r.call("reset", nil, FrameContext{}, nil)
}
func (r *PassthroughRuntime) QueryDefense() DefenseQuery { return r.latest.Defense }
func (r *PassthroughRuntime) Normal() AttackSpec         { return r.latest.Attack }
func (r *PassthroughRuntime) Projectile() (RuntimeProjectile, bool) {
	return RuntimeProjectile{}, false
}
func (r *PassthroughRuntime) CommitHit(h HitResult) {
	if h.Accepted {
		r.call("hit", nil, FrameContext{}, &h)
	}
}
func (r *PassthroughRuntime) CommitAttack(h HitResult) {
	if h.Accepted {
		r.call("contact", nil, FrameContext{}, &h)
	}
}
func (r *PassthroughRuntime) Defeat() {
	if !r.View().Defeated {
		r.call("defeat", nil, FrameContext{}, nil)
	}
}
func (r *PassthroughRuntime) Close() {
	if r.conn != nil {
		r.conn.Close()
		r.conn = nil
	}
}
func (r *PassthroughRuntime) Diagnostics() string {
	return fmt.Sprintf("seq:%d tick:%d rgba:%dx%d boxes:%d/%d latency_us:%d", r.sequence, r.tick, r.latest.Image.Width, r.latest.Image.Height, len(r.latest.Hitboxes), len(r.latest.Hurtboxes), r.latency.Microseconds())
}
func (r *PassthroughRuntime) Clone() FighterRuntime {
	panic("passthrough v1 has no source snapshot support")
}
func (r *PassthroughRuntime) StateBlob() ([]byte, error) {
	return nil, fmt.Errorf("passthrough v1 has no source snapshot support")
}
func (r *PassthroughRuntime) LoadBlob([]byte) error {
	return fmt.Errorf("passthrough v1 has no source snapshot support")
}
func (r *PassthroughRuntime) StateHash() ([32]byte, error) {
	return [32]byte{}, fmt.Errorf("passthrough v1 has no source snapshot support")
}
