package main

type InputFrame struct{ Forward, Back, Up, Down, Punch, Special bool }
type FrameContext struct {
	Advance, AcceptInput bool
	Facing               float32
}
type FighterState struct {
	Frame                                      uint64
	Action, Element, Time, AirAction           int
	X, Y, VX, VY                               float32
	YTarget, YRate                             float32
	UpHeld                                     bool
	PunchHeld, BackHeld, DownHeld              bool
	SpecialHeld, Defeated                      bool
	ProjectileID                               uint64
	AttackID                                   uint64
	Hitstop, Stun, RenderAction, RenderElement int
	DownTime                                   int
	Guarded, Knockdown                         bool
	PushX, PushY, Gravity                      float32
}

// The view is common presentation/body state; blobs and Clone own backend-private state.
type FighterPose struct{ Crouch, Moving, Attacking, Normal, Down, CanTurn bool }
type RuntimeProjectile struct {
	Attack                               AttackSpec
	Animation, RemoveAnimation, Lifetime int
	Scale, Speed, VelocityMul, SpawnX    float32
}
type FighterRuntime interface {
	Backend() string
	View() FighterState
	Pose(FighterState) FighterPose
	Step(InputFrame, FrameContext) FighterState
	Presentation() FighterState
	SetPosition(float32, float32)
	Reset(float32, float32)
	Clone() FighterRuntime
	StateBlob() ([]byte, error)
	LoadBlob([]byte) error
	StateHash() ([32]byte, error)
	QueryDefense() DefenseQuery
	CommitHit(HitResult)
	CommitAttack(HitResult)
	Defeat()
	Normal() AttackSpec
	Projectile() (RuntimeProjectile, bool)
}
