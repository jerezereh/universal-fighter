package main

import (
	"fmt"
	"os"
	"strings"
)

var mixedDiagnostics = os.Getenv("UF_MIXED_DIAGNOSTICS") == "1"
var foreignDebug = os.Getenv("UF_FOREIGN_DEBUG") == "1"

func traceForeignKey(key Key, down bool) {
	if foreignDebug && traceForeign {
		LogMessage("[foreign-key] key=%s code=%d down=%t tick=%d paused=%t step=%t running=%t", KeyToString(key), key, down, sys.tickCount, sys.paused, sys.frameStepFlag, sys.gameRunning)
	}
}

// A gameplay projection, not a serialization of loaded textures or pointer IDs.
// Ordered host slices and value fields make it stable across snapshot clones.
func mixedStateRecord(chars [MaxPlayerNo][]*Char, projs [MaxPlayerNo][]*Projectile) string {
	found := false
	for _, side := range chars {
		for _, c := range side {
			found = found || c.foreign != nil
		}
	}
	if !found {
		return ""
	}
	var out strings.Builder
	for _, side := range chars {
		for _, c := range side {
			fmt.Fprintf(&out, "Shell id=%d type=%v move=%v flags=%v/%v pause=%t/%d pos=%v vel=%v facing=%v ledger=%v/%v activation=%d/%d contact=%v/%d/%v/%d\n",
				c.id, c.ss.stateType, c.ss.moveType, c.specialFlag, c.systemFlag, c.pauseBool, c.hitPauseTime, c.pos, c.vel, c.facing, c.hitdefTargets, c.hitdefTargetsBuffer, c.foreignAttack, c.foreignProjectile, c.mctype, c.mctime, c.pctype, c.pctime)
			fmt.Fprintf(&out, "Attack %+v\nDefense %+v\nAnim %s\n", c.hitdef, c.ghv, mixedAnimState(c.anim))
			if c.foreign != nil {
				data, err := c.foreign.StateBlob()
				if err != nil {
					panic(err)
				}
				fmt.Fprintf(&out, "Foreign %s\n", data)
			}
		}
	}
	for _, side := range projs {
		for _, p := range side {
			fmt.Fprintf(&out, "Projectile owner=%d id=%d entity=%d status=%d age=%d pos=%v old=%v velocity=%v accel=%v mul=%v facing=%v scale=%v/%v hits=%d/%d stop=%d miss=%d life=%d contact=%t frozen=%t removed=%t anim=%d:%s attack=%+v\n",
				p.ownerId, p.id, p.foreignEntity, p.status, p.time, p.pos, p.oldPos, p.velocity, p.accel, p.velmul, p.facing, p.localscl, p.clsnScale, p.hits, p.totalhits, p.hitpause, p.curmisstime, p.removetime, p.contactflag, p.freezeflag, p.removeDone, p.animNo, mixedAnimState(p.anim), p.hitdef)
		}
	}
	return out.String()
}

func mixedAnimState(a *Animation) string {
	if a == nil {
		return "nil"
	}
	return fmt.Sprintf("%d/%d/%d/%d/%d/%d/%t", a.curtime, a.curelem, a.curelemtime, a.drawidx, a.lastActionFrame, a.loopcount, a.loopend)
}

func (gs *GameState) mixedStateRecord() string {
	var chars [MaxPlayerNo][]*Char
	for i := range gs.charData {
		for j := range gs.charData[i] {
			chars[i] = append(chars[i], &gs.charData[i][j])
		}
	}
	record := mixedStateRecord(chars, gs.projs)
	if record == "" {
		return ""
	}
	return fmt.Sprintf("MixedWorld seed=%d match=%d timer=%d tick=%d/%d/%v next=%v paused=%t/%t stop=%d/%d\n%s", gs.randseed, gs.matchTime, gs.curRoundTime, gs.tickCount, gs.oldTickCount, gs.tickCountF, gs.nextAddTime, gs.paused, gs.frameStepFlag, gs.pausetime, gs.supertime, record)
}

func mixedSyncTrace(gs *GameState, replay bool) {
	if !mixedDiagnostics {
		return
	}
	tags := []string{}
	var coreFrame uint64
	for _, side := range gs.charData {
		for _, c := range side {
			if c.ss.moveType == MT_H {
				tags = append(tags, "contact")
			}
			if c.hitPauseTime > 0 {
				tags = append(tags, "hitstop")
			}
			if c.life <= 0 {
				tags = append(tags, "ko")
			}
			if c.foreign == nil {
				continue
			}
			s := c.foreign.View()
			coreFrame = s.Frame
			if (s.RenderAction == 68 || s.RenderAction == 475) && s.RenderElement == 0 {
				tags = append(tags, "startup")
			}
			if s.Stun > 0 {
				tags = append(tags, "contact")
			}
			if s.Hitstop > 0 || c.hitPauseTime > 0 {
				tags = append(tags, "hitstop")
			}
			if s.Defeated || c.life <= 0 {
				tags = append(tags, "ko")
			}
		}
	}
	for _, side := range gs.projs {
		if len(side) > 0 {
			tags = append(tags, "projectile")
		}
		for _, p := range side {
			if p.hitpause > 0 {
				tags = append(tags, "hitstop")
			}
		}
	}
	if gs.roundNo > 1 {
		tags = append(tags, "reset")
	}
	if gs.pausetime > 0 || gs.supertime > 0 {
		tags = append(tags, "pause")
	}
	LogMessage("[mixed-sync] round=%d tick=%d replay=%t checksum=%08x core=%d phases=%s", gs.roundNo, gs.tickCount, replay, uint32(gs.Checksum()), coreFrame, strings.Join(tags, ","))
}

// Debug records are opt-in and contain no extracted assets.
func mixedDebugOverlay(c *Char, x, y float32) {
	if c.foreign == nil {
		return
	}
	s := c.foreign.View()
	line := float32(sys.debugFont.fnt.Size[1]) * sys.debugFont.yscl / sys.heightScale
	// Keep the state label above the standing size box, clear of the bottom panel.
	y += c.size.standbox[1]*c.localscl*sys.cam.Scale - 3*line
	for _, text := range []string{
		fmt.Sprintf("%s P%d action:%d elem:%d frame:%d", c.foreign.Backend(), c.playerNo+1, s.RenderAction, s.RenderElement, s.Frame),
		fmt.Sprintf("stop:%d stun:%d atk:%d shot:%d", s.Hitstop, s.Stun, s.AttackID, s.ProjectileID),
	} {
		sys.debugClsnText = append(sys.debugClsnText, DebugClsnText{x: x, y: y, text: text, r: 255, g: 220, b: 100, a: 255, viewportBound: true})
		y += line
	}
}
