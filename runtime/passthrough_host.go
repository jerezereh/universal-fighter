package main

import (
	"fmt"
	"math"
	"time"

	gl "github.com/go-gl/gl/v3.3-core/gl"
)

// Shared-layer imports, keyed by runtime. Touched only on IKEMEN's main (GL) thread.
var passthroughLayers = map[*PassthroughRuntime]*sharedLayerImport{}

func init() {
	passthroughLayerRelease = func(r *PassthroughRuntime) {
		sys.mainThreadTask <- func() {
			if s := passthroughLayers[r]; s != nil {
				s.Close()
				delete(passthroughLayers, r)
			}
		}
	}
}

// syncPassthroughLayer draws the guest's shared GPU layer (docs/PASSTHROUGH_V2.md item 4): the import is
// (re)opened when the guest's resources change, then each frame waits for that frame's fence value and
// hands the texture to GL. Colours are already premultiplied, as IKEMEN's true-colour sprites expect.
func syncPassthroughLayer(r *PassthroughRuntime, sprite *Sprite, l GuestLayer) {
	sprite.Size = [2]uint16{uint16(l.Width), uint16(l.Height)}
	sprite.Offset = [2]int16{int16(math.Round(float64(l.Pivot[0]))), int16(math.Round(float64(l.Pivot[1])))}
	sprite.coldepth = 32
	timeout := time.Duration(r.config.TimeoutMS) * time.Millisecond
	sys.mainThreadTask <- func() {
		renderer, ok := gfx.(*Renderer_GL33)
		if !ok {
			panic(fmt.Sprintf("passthrough %s: shared GPU layers need the OpenGL 3.3 renderer", r.config.Game))
		}
		s := passthroughLayers[r]
		if s == nil || !s.Matches(l) {
			if s != nil {
				s.Close()
			}
			var err error
			if s, err = openSharedLayer(l); err != nil {
				panic(fmt.Sprintf("passthrough %s: shared GPU layer import failed: %v", r.config.Game, err))
			}
			passthroughLayers[r] = s
			// Owned by the import (no finalizer): IKEMEN only samples it.
			tex := &Texture_GL33{width: int32(l.Width), height: int32(l.Height), depth: 32, handle: s.GLTexture}
			renderer.bindTextureToUnitForced(0, gl.TEXTURE_2D, tex, 0)
			gl.TexParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
			gl.TexParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
			gl.TexParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
			gl.TexParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
			renderer.bindTextureToUnitForced(0, gl.TEXTURE_2D, nil, 0)
			sprite.Tex = tex
		}
		if err := s.Update(l.Value, timeout); err != nil {
			panic(fmt.Sprintf("passthrough %s: shared GPU layer frame %d: %v", r.config.Game, l.Value, err))
		}
	}
}

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
		syncPassthroughLayer(r, c.foreignSprite, *p.Layer)
		return
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
