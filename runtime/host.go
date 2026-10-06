package main

import (
	"fmt"
	"os"
	"path/filepath"
)

var traceForeign = os.Getenv("UF_FOREIGN_TRACE") == "1"
var foreignInputProbe = os.Getenv("UF_FOREIGN_INPUT_PROBE")

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
	if c.foreignName != "kof13" {
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
	if foreignDebug {
		sys.clsnDisplay, sys.debugDisplay = true, true
	}
	LogMessage("[foreign] bound %s: %d actions", def, len(spec.Actions))
	return nil
}
func (c *Char) foreignAutoTurn() {
	if c.hitPause() || c.foreign.State.Hitstop > 0 || c.foreign.State.RenderAction == 68 || c.foreign.State.RenderAction == 475 {
		return
	}
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
	if !c.pauseBool && !c.hitPause() && c.foreign.State.Hitstop == 0 {
		c.acttmp = 1
	}
	c.setCSF(CSF_stagebound | CSF_screenbound | CSF_depthbound | CSF_movecamera_x | CSF_movecamera_y | CSF_movecamera_z | CSF_playerpush)
	c.resetClsnModifiers() // Host collision transforms default to zero until preparation resets them.
	c.stchtmp = false      // Foreign simulation never commits a buffered native CNS transition.
	c.setSCF(SCF_ctrl)
	c.ss.moveType, c.ss.physics = MT_I, ST_N
	if c.foreign.State.Stun > 0 || c.foreign.State.Knockdown || c.life <= 0 {
		c.unsetSCF(SCF_ctrl)
		c.ss.moveType = MT_H
	}
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
		input = InputFrame{Forward: buf.Fb > 0, Back: buf.Bb > 0, Up: buf.Ub > 0, Down: buf.Db > 0, Punch: buf.ab > 0, Special: buf.bb > 0}
	}
	// Opt-in local smoke policy exercises repeated normals. Normal play consumes
	// only the sampled buffer above; this probe is disabled for human/network play.
	offlineSync := sys.rollback.session != nil && sys.rollback.session.syncTest && sys.netConnection == nil && sys.replayFile == nil
	localProbe := !sys.netplay() || offlineSync
	if (foreignInputProbe == "melee" || foreignInputProbe == "projectile" || foreignInputProbe == "receive" || foreignInputProbe == "guard-high" || foreignInputProbe == "guard-low") && (c.controller < 0 || offlineSync) && localProbe {
		input = InputFrame{}
		if enemy := c.enemyNearTrigger(0); enemy != nil {
			input.Forward = Abs(c.distX(enemy, c)) > 38
			input.Punch = foreignInputProbe == "melee" && c.foreign.State.Frame%40 == 0
			if foreignInputProbe == "projectile" {
				input.Forward = false
				input.Special = c.foreign.State.Frame%80 == 0
			}
			if foreignInputProbe == "guard-high" || foreignInputProbe == "guard-low" {
				input.Forward, input.Back = false, true
				input.Down = foreignInputProbe == "guard-low"
			}
		}
	}
	// Stage bounds and player pushing are host policy; adopt their last committed transform.
	c.foreign.State.X, c.foreign.State.Y = c.pos[0], c.pos[1]
	// A lethal contact still drains its foreign hitstop before the host KO flag.
	if c.life <= 0 {
		c.foreign.Defeat()
	}
	frame := c.foreign.Step(input, FrameContext{!c.hitPause(), sys.roundState() == 2 && c.life > 0, c.facing})
	if c.hitPause() {
		frame = c.foreign.presentation()
	}
	if c.foreignProjectile != frame.ProjectileID {
		c.foreignProjectile = frame.ProjectileID
		if sys.roundState() == 2 && c.life > 0 {
			c.spawnForeignProjectile()
		}
	}
	if sys.roundState() != 2 || c.life <= 0 {
		for _, p := range sys.projs[c.playerNo] {
			if p.ownerId == c.id && p.foreignEntity > 0 && p.isActive() {
				p.hits, p.status = 0, ProjRem
			}
		}
	}
	c.setPosX(frame.X, false)
	c.setPosY(frame.Y, false)
	c.vel = [3]float32{} // Foreign simulation already integrated the transform.
	c.ss.no, c.ss.stateType = 0, ST_S
	if frame.Y < 0 {
		c.ss.stateType = ST_A
	} else if frame.Action == 25 || frame.Action == 26 || frame.Action == 36 || frame.Action == 112 {
		c.ss.no, c.ss.stateType = 11, ST_C
	} else if frame.Action == 2 || frame.Action == 3 {
		c.ss.no = 20
	}
	c.ss.time = int32(frame.Frame)
	if frame.Action == 68 || frame.Action == 475 {
		c.ss.moveType = MT_A
		c.unsetSCF(SCF_ctrl)
		if frame.Action == 68 && c.foreignAttack != frame.AttackID {
			c.foreignAttack = frame.AttackID
			c.foreignNormal()
		}
	}
	if frame.Guarded || frame.Stun > 0 || frame.Knockdown {
		c.ss.moveType = MT_H
	}
	if frame.Knockdown && frame.Y == 0 {
		c.ss.stateType = ST_L
	}
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
	if frame.Action == 68 && c.acttmp > 0 && sys.roundState() == 2 && len(c.getClsnWorld(1)) > 0 && c.hitdef.hitonce >= 0 {
		c.atktmp = 1
	}
	c.minus = 1
	if traceForeign && (sys.roundState() == 2 || c.foreign.State.Defeated) {
		rendered := c.anim != nil && c.anim.spr != nil && c.anim.spr.Tex != nil
		LogMessage("[foreign-frame] frame=%d action=%d x=%.3f y=%.3f rendered=%t", frame.Frame, frame.Action, frame.X, frame.Y, rendered)
		if frame.Frame%60 == 0 {
			if enemy := c.enemyNearTrigger(0); enemy != nil {
				LogMessage("[mixed-state] native_state=%d native_time=%d native_atk=%d gap=%.3f native_facing=%.0f foreign_facing=%.0f native_attr=%d native_clsn1=%d native_clsn2=%d foreign_clsn1=%d foreign_clsn2=%d", enemy.ss.no, enemy.ss.time, enemy.atktmp, c.distX(enemy, c), enemy.facing, c.facing, enemy.hitdef.attr, len(enemy.getClsnWorld(1)), len(enemy.getClsnWorld(2)), len(c.getClsnWorld(1)), len(c.getClsnWorld(2)))
				for _, p := range sys.projs[enemy.playerNo] {
					LogMessage("[mixed-projectile] id=%d x=%.3f hits=%d attr=%d p1state=%d p2state=%d eligible=%t overlap=%t boxes=%d", p.id, p.pos[0], p.hits, p.hitdef.attr, p.hitdef.p1stateno, p.hitdef.p2stateno, c.foreignEligible(enemy, &p.hitdef), c.projClsnCheck(p, p.hitdef.p2clsncheck, 1, true), len(p.getClsn(1)))
				}
			}
		}
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
	if c.life <= 0 && !c.pauseBool && !c.hitPause() && c.foreign.State.Hitstop == 0 {
		if traceForeign && !c.scf(SCF_ko) {
			LogMessage("[foreign-ko] owner=%d round=%d action=%d y=%.3f", c.id, sys.roundNo, c.foreign.State.RenderAction, c.foreign.State.Y)
		}
		c.setSCF(SCF_ko)
		if c.foreign.State.Y == 0 && c.foreign.State.RenderAction == 161 {
			c.setSCF(SCF_over_ko)
		}
		c.unsetSCF(SCF_ctrl)
	}
	c.minus = 2
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
func (b kofBackend) Tick() {
	c := b.c
	// Only native-owned contact bookkeeping; no native state/animation tick.
	if len(c.hitdefTargetsBuffer) > 0 {
		c.hitdefTargets = append(c.hitdefTargets, c.hitdefTargetsBuffer...)
		c.hitdefTargetsBuffer = c.hitdefTargetsBuffer[:0]
	}
	if !c.pauseBool && c.hitPauseTime > 0 {
		c.hitPauseTime--
	}
	c.hitdefContact = false
}

func (c *Char) foreignNormal() {
	n := c.foreign.Spec.Normal
	c.hitdef.reset(c, nil)
	hd := &c.hitdef
	hd.attr = int32(ST_S) | int32(AT_NA)
	foreignAttackParams(hd, n.Damage, n.Hitstop)
	hd.finalizeParams(c, nil)
}

func foreignAttackParams(hd *HitDef, damage, hitstop int) {
	hd.hitdamage = int32(damage)
	hd.guarddamage = 0
	hd.pausetime = [2]int32{int32(hitstop), int32(hitstop)}
	hd.guard_pausetime = hd.pausetime
	hd.guardflag = int32(HF_H | HF_L)
	hd.ground_type, hd.air_type = HT_High, HT_High
	// ponytail: source damage/hitstop/active boxes; compatibility reaction and push.
	hd.ground_hittime, hd.ground_slidetime = 15, 15
	hd.guard_hittime, hd.guard_slidetime, hd.guard_ctrltime = 14, 14, 14
	hd.ground_velocity = [3]float32{-2.4, 0, 0}
	hd.guard_velocity = [3]float32{-1.6, 0, 0}
	hd.air_velocity = [3]float32{-2.4, -3, 0}
	hd.air_hittime, hd.air_fall = 20, 1
	hd.hitonce, hd.numhits, hd.id = 1, 1, 68
	hd.guard_dist_x = [2]float32{80, 0}
}

func (c *Char) spawnForeignProjectile() {
	p := c.spawnProjectile()
	if p == nil {
		return
	}
	spec := c.foreign.Spec.Projectile
	p.foreignEntity = c.foreignProjectile
	p.id, p.animNo = 475, int32(spec.Animation)
	p.hitanim, p.remanim, p.cancelanim = int32(spec.RemoveAnimation), int32(spec.RemoveAnimation), int32(spec.RemoveAnimation)
	p.scale, p.clsnScale = [2]float32{c.foreign.Spec.Scale, c.foreign.Spec.Scale}, [2]float32{c.foreign.Spec.Scale, c.foreign.Spec.Scale}
	p.velocity[0], p.velmul[0] = spec.Speed, spec.VelocityMul
	p.removetime = int32(spec.Lifetime) // ponytail: finite source timeline; no original Lua object lifecycle.
	p.hitdef.attr = int32(ST_S) | int32(AT_SP)
	foreignAttackParams(&p.hitdef, spec.Damage, spec.Hitstop)
	p.hitdef.id = 475
	p.hitdef.finalizeParams(c, p)
	p.hitdef.statePN = c.playerNo
	c.commitProjectile(p, PT_P1, spec.SpawnX, 0, 0, false, 1, 1, true)
	if traceForeign {
		LogMessage("[foreign-projectile] spawn owner=%d entity=%d round=%d x=%.3f facing=%.0f", c.id, p.foreignEntity, sys.roundNo, p.pos[0], p.facing)
	}
}

// Foreign defenders accept ordinary melee/projectile envelopes, never native
// custom-state ownership, throws or reversals.
func (c *Char) foreignEligible(attacker *Char, hd *HitDef) bool {
	if sys.roundState() != 2 || c.life <= 0 || hd.reversal_attr > 0 || hd.attr&int32(AT_AT) != 0 ||
		hd.p1stateno >= 0 || hd.p2stateno >= 0 || c.foreign.QueryDefense().Down || attacker.scf(SCF_disabled) {
		return false
	}
	s := c.ss.stateType
	return (s == ST_S && hd.hitflag&int32(HF_H) != 0) || (s == ST_C && hd.hitflag&int32(HF_L) != 0) ||
		(s == ST_A && hd.hitflag&int32(HF_A) != 0)
}
func (attacker *Char) commitForeignHit(defender *Char, projectile *Projectile) int32 {
	hd := &attacker.hitdef
	facing, scale, attackMul := attacker.facing, attacker.localscl, attacker.attackMul[0]
	if projectile != nil {
		if projectile.platform || attacker.ss.stateType == ST_L {
			return 0
		}
		hd, facing, scale, attackMul = &projectile.hitdef, projectile.facing, projectile.localscl, projectile.parentAttackMul[0]
	}
	if !defender.foreignEligible(attacker, hd) {
		return 0
	}
	velocity, stun, fall := hd.ground_velocity, hd.ground_hittime, hd.ground_fall
	if defender.pos[1] < 0 {
		velocity, stun, fall = hd.air_velocity, hd.air_hittime, hd.air_fall != 0
	}
	ratio := scale / defender.localscl
	attack := AttackSpec{Damage: int(hd.hitdamage), Chip: int(hd.guarddamage), Hitstun: int(Max(1, stun)),
		Blockstun: int(Max(1, hd.guard_ctrltime)), Hitstop: [2]int{int(Max(0, hd.pausetime[0])), int(Max(0, hd.pausetime[1]))},
		Guardstop: [2]int{int(Max(0, hd.guard_pausetime[0])), int(Max(0, hd.guard_pausetime[1]))},
		BlockHigh: hd.guardflag&int32(HF_H) != 0 && !attacker.asf(ASF_unguardable),
		BlockLow:  hd.guardflag&int32(HF_L) != 0 && !attacker.asf(ASF_unguardable),
		PushX:     -velocity[0] * facing * ratio, PushY: velocity[1] * ratio,
		Gravity: hd.yaccel * ratio, GuardPush: -hd.guard_velocity[0] * facing * ratio, Knockdown: fall}
	result := resolveContact(attack, defender.foreign.QueryDefense())
	if !result.Accepted {
		return 0
	}
	kill := hd.kill
	if result.Guarded {
		kill = hd.guard_kill
	}
	result.Damage = int(defender.computeDamage(float64(result.Damage), kill, false,
		attackMul*float32(attacker.gi().attackBase)/100, attacker, true))
	defender.lifeAdd(-float64(result.Damage), kill, true)
	defender.foreign.CommitHit(result)
	if projectile == nil {
		attacker.hitdefTargetsBuffer = append(attacker.hitdefTargetsBuffer, defender.id)
	}
	defender.receivedHits++
	code := int32(1)
	if result.Guarded {
		code = 2
	}
	return code // Existing melee loop commits native attacker hitpause/contact flags.
}
