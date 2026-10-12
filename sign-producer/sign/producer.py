"""The producer for one game. Replace the TODOs in PRODUCER_GUIDE.md's order; `python produce.py --fake` serves
ufproducer's reference fighter meanwhile, so the arena and the conformance kit work from day one.

Frame fields use the wire's names (uf-arena docs/WIRE.md "Reply contents"). The library validates every reply
before sending, turns exceptions into error replies (the host then ends the match) and closes the connection on
protocol violations.
"""
from ufproducer import Producer

from . import attach


class SignProducer(Producer):
    game = 'ggxrd-sign-376300-1028441'
    # Add protocol.STEP_EVENTS once apply_event works inside step; SHARED_LAYER (and LAYER_RELEASE) once the GPU
    # layer works. Extensions (protocol.EXTENSIONS: units, pushbox, throws, world-time, camera-hints) each once their
    # Frame fields work; see uf-arena docs/WIRE.md "Extensions" and ufproducer.fake for all of them in use.
    capabilities = ()  # Native SIGN producer is not connected; promote only after live verification.

    def __init__(self, source):
        super().__init__()
        self.source = source   # attach.Source: the running, verified, hooked game

    def reset(self, transform):
        # TODO (guide steps 3-5): clear fighter state and input edges, place the fighter at the host position
        # (transform.x, transform.y, transform.facing), tick 0.
        raise NotImplementedError('reset')

    def step(self, input, transform, opponent):
        # TODO (steps 3-7): adopt the host transform, write `input` for exactly one source tick, allow exactly one
        # tick, then read that tick's state, boxes and image.
        raise NotImplementedError('step')

    def apply_event(self, event):
        # TODO (step 7): event.operation is "hit" (this fighter was hit) or "contact" (its attack connected);
        # apply event.result through the source's own hit pipeline. No tick.
        raise NotImplementedError('apply_event')

    def defeat(self):
        # TODO: put the source fighter into its KO on following steps.
        pass

    def frame(self):
        # TODO: the current tick's state without advancing (replies to hit/contact/defeat).
        raise NotImplementedError('frame')

    def close(self):
        # The connection ended. Never leave the source waiting for this host (e.g. settle a release fence).
        pass


__all__ = ['SignProducer']

