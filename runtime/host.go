package main

import (
	"fmt"
	"os"
	"path/filepath"
)

var traceForeign = os.Getenv("UF_FOREIGN_TRACE") == "1"

// Host scheduling treats native and foreign simulation through one small seam.
type FighterBackend interface {
	Prepare()
	Run()
	Finish()
	Update()
	Tick()
}
type nativeBackend struct{ c *Char }

func (b nativeBackend) Prepare() { b.c.actionPrepare() }
func (b nativeBackend) Run()     { b.c.actionRun() }
func (b nativeBackend) Finish()  { b.c.actionFinish() }
func (b nativeBackend) Update()  { b.c.update() }
func (b nativeBackend) Tick()    { b.c.tick() }

type kofBackend struct{ c *Char }

func (c *Char) fighterBackend() FighterBackend {
	if c.foreign != nil {
		return kofBackend{c}
	}
	return nativeBackend{c}
}
func (c *Char) bindForeign(def string) error {
	c.foreign = nil
	if c.foreignName == "" {
		return nil
	}
	if c.foreignName != "kof13-locomotion" {
		return fmt.Errorf("unsupported fighter runtime %s", c.foreignName)
	}
	data, err := os.ReadFile(filepath.Join(filepath.Dir(def), "foreign.json"))
	if err != nil {
		return err
	}
	spec, err := loadKOFSpec(data)
	if err != nil {
		return err
	}
	c.foreign = &KOFRuntime{Spec: spec}
	c.foreign.Reset(c.pos[0], c.pos[1])
	LogMessage("[foreign] bound %s: %d actions", def, len(spec.Actions))
	return nil
}
func (c *Char) foreignAutoTurn() {
	action := c.foreign.State.Action
	if (action == 1 || action == 2 || action == 3 || action == 26) && sys.stage.autoturn && c.shouldFaceP2() {
		c.setFacing(-c.facing)
	}
}
func (b kofBackend) Prepare() {
	c := b.c
	if c.minus != 3 || c.scf(SCF_disabled) {
		return
	}
	c.pauseBool = sys.supertime > 0 && c.superMovetime == 0 || sys.supertime == 0 && sys.pausetime > 0 && c.pauseMovetime == 0
	c.acttmp = 0
	if !c.pauseBool {
		c.acttmp = 1
	}
	c.setCSF(CSF_stagebound | CSF_screenbound | CSF_depthbound | CSF_movecamera_x | CSF_movecamera_y | CSF_movecamera_z | CSF_playerpush)
	c.setSCF(SCF_ctrl)
	c.ss.moveType, c.ss.physics = MT_I, ST_N
	c.widthEdge = [2]float32{}
}
func (b kofBackend) Run() {
	c := b.c
	if c.minus != 3 || c.pauseBool || c.scf(SCF_disabled) {
		return
	}
	input := InputFrame{}
	if len(c.cmd) > 0 {
		buf := c.cmd[0].Buffer
		input = InputFrame{buf.Fb > 0, buf.Bb > 0, buf.Ub > 0, buf.Db > 0}
	}
	// Stage bounds and player pushing are host policy; adopt their last committed transform.
	c.foreign.State.X, c.foreign.State.Y = c.pos[0], c.pos[1]
	frame := c.foreign.Step(input, FrameContext{true, sys.roundState() == 2, c.facing})
	c.setPosX(frame.X, false)
	c.setPosY(frame.Y, false)
	c.vel = [3]float32{} // Foreign simulation already integrated the transform.
	c.ss.no, c.ss.stateType = 0, ST_S
	if frame.Y < 0 {
		c.ss.stateType = ST_A
	} else if frame.Action == 25 || frame.Action == 26 {
		c.ss.no, c.ss.stateType = 11, ST_C
	} else if frame.Action == 2 || frame.Action == 3 {
		c.ss.no = 20
	}
	c.ss.time = int32(frame.Frame)
	if c.animNo != int32(frame.Action) || c.anim == nil {
		c.changeAnim(int32(frame.Action), -1, -1, "")
	}
	if c.anim != nil {
		c.anim.SetAnimElem(int32(frame.Element+1), 0)
		c.anim.UpdateSprite()
		c.updateCurFrame()
		c.animBackup = c.anim
	}
	c.atktmp = 0
	c.minus = 1
	if traceForeign && sys.roundState() == 2 {
		rendered := c.anim != nil && c.anim.spr != nil && c.anim.spr.Tex != nil
		LogMessage("[foreign-frame] frame=%d action=%d x=%.3f y=%.3f rendered=%t", frame.Frame, frame.Action, frame.X, frame.Y, rendered)
	}
}
func (b kofBackend) Finish() {
	c := b.c
	if c.scf(SCF_disabled) {
		return
	}
	c.zScale = sys.updateZScale(c.pos[2], c.localscl)
	if c.palfx != nil && !c.pauseBool {
		c.palfx.step()
	}
	c.inguarddist = false
}
func (b kofBackend) Update() {
	c := b.c
	if c.acttmp > 0 {
		for i := range c.interPos {
			c.interPos[i] = c.pos[i] - (c.pos[i]-c.oldPos[i])*(1-sys.tickInterpolation())
		}
	}
	if sys.tickNextFrame() {
		c.oldPos = c.pos
		c.pushed = false
		c.minus = 3
	}
}
func (b kofBackend) Tick() {} // Animation and simulation clocks belong to the runtime.
