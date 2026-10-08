//go:build !windows

package main

import (
	"fmt"
	"time"
)

// Shared D3D12 layers are Windows-only; a negotiated layer fails explicitly elsewhere.
type LayerTimes struct{ Unlock, Wait, Copy, Lock time.Duration }

type sharedLayerImport struct {
	Times         LayerTimes
	Width, Height int
	GLTexture     uint32
}

func openSharedLayer(l GuestLayer) (*sharedLayerImport, error) {
	return nil, fmt.Errorf("shared GPU layers require Windows")
}
func (s *sharedLayerImport) Matches(GuestLayer) bool            { return false }
func (s *sharedLayerImport) Update(uint64, time.Duration) error { return fmt.Errorf("unsupported") }
func (s *sharedLayerImport) Unlock() error                      { return nil }
func (s *sharedLayerImport) Close()                             {}
