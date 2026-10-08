package main

import "fmt"

// GPU uploads use IKEMEN's main-thread queue; reuse each fighter's texture.
func (c *Char) syncPassthroughRender() {
	r, ok := c.foreign.(*PassthroughRuntime)
	if !ok {
		return
	}
	if c.foreignSprite == nil {
		c.foreignSprite = newSprite()
	}
	if c.anim == nil || c.anim.spr != c.foreignSprite {
		c.anim = newAnimation(nil, &c.gi().sff.palList)
		c.anim.mask = 0 // -1 forces RGBA alpha to one in IKEMEN's sprite shader.
		c.anim.frames = []AnimFrame{*newAnimFrame()}
		c.anim.spr = c.foreignSprite
	}
	p := r.latest
	// Native ChangeAnim normally initializes this conversion. Remote sprites skip it.
	c.animPN, c.spritePN, c.animlocalscl = c.playerNo, c.playerNo, 320/c.localcoord
	c.animNo = int32(p.State.Action)
	c.anim.frames[0].Clsn1, c.anim.frames[0].Clsn2 = p.Hitboxes, p.Hurtboxes
	c.anim.UpdateSprite()
	c.updateCurFrame()
	c.animBackup = c.anim
	if c.foreignRenderSequence == p.Sequence {
		return
	}
	c.foreignRenderSequence = p.Sequence
	if p.Layer != nil {
		// docs/PASSTHROUGH_V2.md item 2: the shared-layer importer is not wired into IKEMEN yet.
		panic(fmt.Sprintf("passthrough %s: shared GPU layer negotiated but the importer is not available", r.config.Game))
	}
	i, sprite := p.Image, c.foreignSprite
	sprite.Size, sprite.Offset, sprite.coldepth = [2]uint16{uint16(i.Width), uint16(i.Height)}, i.Pivot, 32
	// IKEMEN's true-color path expects premultiplied RGB, unlike the wire format.
	data := guestTexturePixels(i.RGBA)
	sys.mainThreadTask <- func() {
		if sprite.Tex == nil || sprite.Tex.GetWidth() != int32(i.Width) || sprite.Tex.GetHeight() != int32(i.Height) {
			tex, err := gfx.newTexture(int32(i.Width), int32(i.Height), 32, false)
			if err != nil {
				panic(err)
			}
			sprite.Tex = tex
		}
		sprite.Tex.SetData(data)
	}
}

func hasPassthrough() bool {
	for _, side := range sys.chars {
		for _, c := range side {
			if _, ok := c.foreign.(*PassthroughRuntime); ok {
				return true
			}
		}
	}
	return false
}

// Never create a shell-only snapshot of a live guest. Debug keys are nonfatal.
func rejectPassthroughSnapshot() bool {
	if !hasPassthrough() {
		return false
	}
	LogMessage("[passthrough] save/load rejected: guest source snapshots unavailable")
	return true
}
