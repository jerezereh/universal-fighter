package main

import (
	"fmt"
	"os"
	"path/filepath"
)

var traceForeign = os.Getenv("UF_FOREIGN_TRACE") == "1"
var foreignInputProbe = os.Getenv("UF_FOREIGN_INPUT_PROBE")
var syntheticInputProbe = os.Getenv("UF_SYNTHETIC_PROBE")

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

type guestBackend struct{ c *Char }

func (c *Char) fighterBackend() FighterBackend {
	if c.foreign != nil {
		return guestBackend{c}
	}
	return nativeBackend{c}
}
func (c *Char) bindForeign(def string) error {
	if old, ok := c.foreign.(*PassthroughRuntime); ok {
		old.Close()
	}
	c.foreign = nil
	if c.foreignName == "" {
		return nil
	}
	switch c.foreignName {
	case "passthrough":
		if sys.netplay() || sys.usesRollbackMatch() {
			return fmt.Errorf("passthrough v1 supports offline matches only; replay/rollback unavailable")
		}
		data, err := os.ReadFile(def + ".passthrough.json")
		if err != nil {
			return err
		}
		config, err := loadPassthroughConfig(data)
		if err != nil {
			return err
		}
		runtime, err := newPassthrough(config)
		if err != nil {
			return err
		}
		c.foreign = runtime
	case "kof13":
		data, err := os.ReadFile(filepath.Join(filepath.Dir(def), "foreign.json"))
		if err != nil {
			return err
		}
		spec, err := loadKOFSpec(data)
		if err != nil {
			return err
		}
		c.foreign = &KOFRuntime{Spec: spec}
	case "parry-test", "airdash-test":
		runtime, err := newSynthetic(c.foreignName)
		if err != nil {
			return err
		}
		c.foreign = runtime
	default:
		return fmt.Errorf("unsupported fighter runtime %s", c.foreignName)
	}
	c.foreign.Reset(c.pos[0], c.pos[1])
	if foreignDebug {
		sys.clsnDisplay, sys.debugDisplay = true, true
	}
	LogMessage("[foreign] bound %s: backend=%s", def, c.foreign.Backend())
	return nil
}
func (c *Char) foreignAutoTurn() {
	if !c.hitPause() && c.foreign.Pose(c.foreign.View()).CanTurn && sys.stage.autoturn && c.shouldFaceP2() {
		c.setFacing(-c.facing)
	}
}
func (b guestBackend) Prepare() {
	c := b.c
	if c.minus != 3 || c.scf(SCF_disabled) {
		return
	}
	c.pauseBool = sys.supertime > 0 && c.superMovetime == 0 || sys.supertime == 0 && sys.pausetime > 0 && c.pauseMovetime == 0
	c.acttmp = 0
	if !c.pauseBool && !c.hitPause() && c.foreign.View().Hitstop == 0 {
		c.acttmp = 1
	}
	c.setCSF(CSF_stagebound | CSF_screenbound | CSF_depthbound | CSF_movecamera_x | CSF_movecamera_y | CSF_movecamera_z | CSF_playerpush)
	c.resetClsnModifiers() // Host collision transforms default to zero until preparation resets them.
	c.stchtmp = false      // Foreign simulation never commits a buffered native CNS transition.
	c.setSCF(SCF_ctrl)
	c.ss.moveType, c.ss.physics = MT_I, ST_N
	if c.foreign.View().Stun > 0 || c.foreign.View().Knockdown || c.life <= 0 {
		c.unsetSCF(SCF_ctrl)
		c.ss.moveType = MT_H
	}
	c.widthEdge = [2]float32{}
}
func (b guestBackend) Run() {
	c := b.c
	if c.minus != 3 || c.pauseBool || c.scf(SCF_disabled) {
		return
	}
	input := InputFrame{}
	if len(c.cmd) > 0 {
		buf := c.cmd[0].Buffer
		input = InputFrame{Forward: buf.Fb > 0, Back: buf.Bb > 0, Up: buf.Ub > 0, Down: buf.Db > 0, Punch: buf.ab > 0, Special: buf.bb > 0}
		input.Buttons = [10]bool{buf.ab > 0, buf.bb > 0, buf.cb > 0, buf.xb > 0, buf.yb > 0, buf.zb > 0, buf.sb > 0, buf.db > 0, buf.wb > 0, buf.mb > 0}
	}
	// Opt-in local smoke policy exercises repeated normals. Normal play consumes
	// only the sampled buffer above; this probe is disabled for human/network play.
	offlineSync := sys.rollback.session != nil && sys.rollback.session.syncTest && sys.netConnection == nil && sys.replayFile == nil
	localProbe := !sys.netplay() || offlineSync
	if syntheticInputProbe != "" && localProbe {
		input = syntheticProbeInput(c)
	}
	if (foreignInputProbe == "melee" || foreignInputProbe == "projectile" || foreignInputProbe == "receive" || foreignInputProbe == "guard-high" || foreignInputProbe == "guard-low") && (c.controller < 0 || offlineSync) && localProbe {
		input = InputFrame{}
		if enemy := c.enemyNearTrigger(0); enemy != nil {
			input.Forward = Abs(c.distX(enemy, c)) > 38
			input.Punch = foreignInputProbe == "melee" && c.foreign.View().Frame%40 == 0
			if foreignInputProbe == "projectile" {
				input.Forward = false
				input.Special = c.foreign.View().Frame%80 == 0
			}
			if foreignInputProbe == "guard-high" || foreignInputProbe == "guard-low" {
				input.Forward, input.Back = false, true
				input.Down = foreignInputProbe == "guard-low"
			}
		}
	}
	// Stage bounds and player pushing are host policy; adopt their last committed transform.
	c.foreign.SetPosition(c.pos[0], c.pos[1])
	if r, ok := c.foreign.(*PassthroughRuntime); ok {
		r.life = c.life
		if sys.netplay() || sys.usesRollbackMatch() {
			panic("passthrough v1 cannot enter replay/rollback")
		}
		r.opponent = nil
		if enemy := c.enemyNearTrigger(0); enemy != nil {
			r.opponent = &GuestOpponent{X: enemy.pos[0] * enemy.localscl / c.localscl, Y: enemy.pos[1] * enemy.localscl / c.localscl, Facing: enemy.facing, Life: enemy.life, AttackID: enemy.foreignAttack}
			for group := int32(1); group <= 2; group++ {
				for _, box := range enemy.getClsnWorld(group) {
					rect := box.rect
					for n := range rect {
						rect[n] /= c.localscl
					}
					if group == 1 {
						r.opponent.Hitboxes = append(r.opponent.Hitboxes, rect)
					} else {
						r.opponent.Hurtboxes = append(r.opponent.Hurtboxes, rect)
					}
				}
			}
		}
	}
	// A lethal contact still drains its foreign hitstop before the host KO flag.
	if c.life <= 0 {
		c.foreign.Defeat()
	}
	frame := c.foreign.Step(input, FrameContext{!c.hitPause(), sys.roundState() == 2 && c.life > 0, c.facing})
	if c.hitPause() {
		frame = c.foreign.Presentation()
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
	pose := c.foreign.Pose(frame)
	c.ss.no, c.ss.stateType = 0, ST_S
	if frame.Y < 0 {
		c.ss.stateType = ST_A
	} else if pose.Crouch {
		c.ss.no, c.ss.stateType = 11, ST_C
	} else if pose.Moving {
		c.ss.no = 20
	}
	c.ss.time = int32(frame.Frame)
	if pose.Attacking {
		c.ss.moveType = MT_A
		c.unsetSCF(SCF_ctrl)
		if pose.Normal && c.foreignAttack != frame.AttackID {
			c.foreignAttack = frame.AttackID
			c.foreignNormal()
		}
	}
	if frame.Guarded || frame.Stun > 0 || frame.Knockdown {
		c.ss.moveType = MT_H
	}
	if pose.Down {
		c.ss.stateType = ST_L
	}
	if _, remote := c.foreign.(*PassthroughRuntime); remote {
		c.syncPassthroughRender()
	} else {
		if c.animNo != int32(frame.Action) || c.anim == nil {
			c.changeAnim(int32(frame.Action), -1, -1, "")
		}
		if c.anim != nil {
			c.anim.SetAnimElem(int32(frame.Element+1), 0)
			c.anim.UpdateSprite()
			c.updateCurFrame()
			c.animBackup = c.anim
		}
	}
	c.atktmp = 0
	if pose.Normal && c.acttmp > 0 && sys.roundState() == 2 && len(c.getClsnWorld(1)) > 0 && c.hitdef.hitonce >= 0 {
		c.atktmp = 1
	}
	c.minus = 1
	if traceForeign && (sys.roundState() == 2 || c.foreign.View().Defeated) {
		if d, ok := c.foreign.(interface{ Diagnostics() string }); ok && !foreignReplaying() {
			LogMessage("[ruleset-frame] owner=%d round=%d frame=%d %s %s", c.playerNo, sys.roundNo, frame.Frame, c.foreign.Backend(), d.Diagnostics())
		}
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
func (b guestBackend) Finish() {
	c := b.c
	if c.scf(SCF_disabled) {
		return
	}
	c.zScale = sys.updateZScale(c.pos[2], c.localscl)
	if c.palfx != nil && !c.pauseBool {
		c.palfx.step()
	}
	c.inguarddist = false
	if c.life <= 0 && !c.pauseBool && !c.hitPause() && c.foreign.View().Hitstop == 0 {
		if traceForeign && !c.scf(SCF_ko) {
			LogMessage("[foreign-ko] owner=%d round=%d action=%d y=%.3f", c.id, sys.roundNo, c.foreign.View().RenderAction, c.foreign.View().Y)
		}
		c.setSCF(SCF_ko)
		if c.foreign.View().Y == 0 && c.foreign.View().RenderAction == 161 {
			c.setSCF(SCF_over_ko)
		}
		c.unsetSCF(SCF_ctrl)
	}
	c.minus = 2
}
func (b guestBackend) Update() {
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
func (b guestBackend) Tick() {
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
	n := c.foreign.Normal()
	c.hitdef.reset(c, nil)
	hd := &c.hitdef
	hd.attr = int32(c.ss.stateType) | int32(AT_NA)
	foreignAttackParams(hd, n)
	hd.finalizeParams(c, nil)
}

func foreignAttackParams(hd *HitDef, a AttackSpec) {
	hd.hitdamage = int32(a.Damage)
	hd.guarddamage = int32(a.Chip)
	hd.pausetime = [2]int32{int32(a.Hitstop[0]), int32(a.Hitstop[1])}
	hd.guard_pausetime = [2]int32{int32(a.Guardstop[0]), int32(a.Guardstop[1])}
	hd.guardflag = 0
	if a.BlockHigh {
		hd.guardflag |= int32(HF_H)
	}
	if a.BlockLow {
		hd.guardflag |= int32(HF_L)
	}
	hd.ground_type, hd.air_type = HT_High, HT_High
	// ponytail: source damage/hitstop/active boxes; compatibility reaction and push.
	hd.ground_hittime, hd.ground_slidetime = int32(a.Hitstun), int32(a.Hitstun)
	hd.guard_hittime, hd.guard_slidetime, hd.guard_ctrltime = int32(a.Blockstun), int32(a.Blockstun), int32(a.Blockstun)
	hd.ground_velocity = [3]float32{-a.PushX, a.PushY, 0}
	hd.guard_velocity = [3]float32{-a.GuardPush, 0, 0}
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
	spec, ok := c.foreign.Projectile()
	if !ok {
		panic("runtime emitted an unsupported projectile")
	}
	p.foreignEntity = c.foreignProjectile
	p.id, p.animNo = 475, int32(spec.Animation)
	p.hitanim, p.remanim, p.cancelanim = int32(spec.RemoveAnimation), int32(spec.RemoveAnimation), int32(spec.RemoveAnimation)
	p.scale, p.clsnScale = [2]float32{spec.Scale, spec.Scale}, [2]float32{spec.Scale, spec.Scale}
	p.velocity[0], p.velmul[0] = spec.Speed, spec.VelocityMul
	p.removetime = int32(spec.Lifetime) // ponytail: finite source timeline; no original Lua object lifecycle.
	p.hitdef.attr = int32(ST_S) | int32(AT_SP)
	foreignAttackParams(&p.hitdef, spec.Attack)
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
	if r, ok := defender.foreign.(*PassthroughRuntime); ok {
		r.life = defender.life
	}
	defender.foreign.CommitHit(result)
	if attacker.foreign != nil {
		attacker.foreign.CommitAttack(result)
	}
	if traceForeign && !foreignReplaying() {
		LogMessage("[ruleset-contact] attacker=%d defender=%d parried=%t barrier=%t damage=%d cost=%d projectile=%t", attacker.id, defender.id, result.Parried, result.Barrier, result.Damage, result.ResourceCost, projectile != nil)
	}
	if projectile == nil {
		attacker.hitdefTargetsBuffer = append(attacker.hitdefTargetsBuffer, defender.id)
	}
	if !result.Parried {
		defender.receivedHits++
	}
	code := int32(1)
	if result.Guarded || result.Parried {
		code = 2
	}
	return code // Existing melee loop commits native attacker hitpause/contact flags.
}

func foreignReplaying() bool { return sys.rollback.session != nil && sys.rollback.session.inRollback }

// Authored offline input oracle only. This is never a matchup branch in combat.
// Human/network/replay operation leaves UF_SYNTHETIC_PROBE empty.
func syntheticProbeInput(c *Char) InputFrame {
	s := c.foreign.View()
	enemy := c.enemyNearTrigger(0)
	if enemy == nil {
		return InputFrame{}
	}
	if c.playerNo == 0 {
		i := InputFrame{Forward: Abs(c.distX(enemy, c)) > 38, Punch: s.Frame%40 == 0}
		if syntheticInputProbe == "parry" {
			pose := c.foreign.Presentation()
			i.Special = c.foreign.Pose(pose).Normal && pose.Element == 2
		}
		if syntheticInputProbe == "cancel" {
			i.Up = s.Frame%120 == 60
			if d, ok := c.foreign.(*SyntheticRuntime); ok {
				i.Special = d.Extra.Confirmed || (s.Y < 0 && s.Frame%16 == 0)
			}
		}
		return i
	}
	switch syntheticInputProbe {
	case "barrier":
		return InputFrame{Back: true, Down: true, Special: true}
	case "native-parry":
		return InputFrame{Special: enemy.ss.no == 200 && enemy.ss.time < 4}
	case "parry", "miss":
		if enemy.foreign != nil {
			pose := enemy.foreign.Presentation()
			elem := 0
			if syntheticInputProbe == "miss" {
				elem = 2
			}
			return InputFrame{Special: enemy.foreign.Pose(pose).Normal && pose.Element == elem}
		}
	}
	return InputFrame{}
}
