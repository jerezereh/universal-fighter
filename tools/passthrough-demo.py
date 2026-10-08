"""Authored guest process for the generic IKEMEN receiver. No retail game behavior/assets.

Framing: uint32 big endian byte count, then UTF-8 JSON. Ready file reports a private
loopback endpoint. No wall-clock simulation: requests alone advance the fighter.
"""
import argparse
import base64
import json
from pathlib import Path
import socket
import struct
import time

LIMIT = 8 << 20
CAPABILITIES = ['host-step', 'isolated-rgba', 'universal-contact']


def read_exact(conn, size):
    parts = bytearray()
    while len(parts) < size:
        data = conn.recv(size - len(parts))
        if not data:
            raise EOFError
        parts.extend(data)
    return bytes(parts)


class Fighter:
    def __init__(self, game, variant, layer=None):
        self.game, self.variant, self.layer = game, variant, layer   # layer: optional shared GPU layer
        self.reset()

    def reset(self):
        self.x = self.y = self.vy = 0
        self.tick = self.activation = self.age = self.stop = self.stun = 0
        self.held = self.back = self.down = self.guarded = self.defeated = False
        self.push = 0
        self.session, self.sequence, self.accepted = None, 0, []

    def apply(self, q):
        op = q['operation']
        if q['version'] != 1 or q['game'] != self.game:
            raise ValueError('wrong protocol/game')
        if op == 'hello':
            if self.session is not None or q['sequence'] != 1 or q['tick'] != 0:
                raise ValueError('duplicate hello')
            self.session = q['session']
            self.accepted = q.get('accept') or []
        if q['session'] != self.session or q['sequence'] != self.sequence + 1:
            raise ValueError('stale session/sequence')
        sequence, session = q['sequence'], self.session
        if op == 'reset':
            accepted = self.accepted
            self.reset()
            self.session, self.accepted = session, accepted   # negotiation lasts for the connection
        expected_tick = self.tick + (op == 'step')
        if q['tick'] != expected_tick:
            raise ValueError('unsynchronized guest tick')
        if op in ('step', 'reset'):
            self.x, self.y = q['X'], q['Y']
        if op == 'step':
            if not q['context']['Advance']:
                raise ValueError('step without advance')
            self.tick += 1
            i = q.get('input', {}) if q['context']['AcceptInput'] else {}
            attack = i.get('punch' if self.variant == 'amber' else 'light', False)
            self.back, self.down = i.get('back', False), i.get('down', False)
            if self.stop:
                self.stop -= 1
            elif self.stun:
                self.stun -= 1
                self.x += self.push
                self.push *= .85
            elif self.defeated:
                pass
            else:
                if attack and not self.held and not self.age and not self.y:
                    self.age, self.activation = 1, self.activation + 1
                elif self.age:
                    self.age = self.age + 1 if self.age < 18 else 0
                if not self.age:
                    self.x += (i.get('right', False) - i.get('left', False)) * (2 if self.variant == 'amber' else 2.5)
                    if i.get('up') and not self.y:
                        self.vy = -5
                self.held = attack
            if self.y < 0 or self.vy:
                self.y += self.vy
                self.vy += .3
                if self.y >= 0:
                    self.y = self.vy = 0
        elif op in ('hit', 'contact'):
            h = q['result']
            if not h['Accepted']:
                raise ValueError('unaccepted contact')
            self.stop = h['Hitstop'][1 if op == 'hit' else 0]
            if op == 'hit':
                self.age, self.stun = 0, h['Stun']
                self.push, self.vy = h['PushX'], h['PushY']
                self.guarded = h['Guarded']
        elif op == 'defeat':
            self.defeated, self.age = True, 0
        elif op not in ('hello', 'reset'):
            raise ValueError('unsupported operation')
        self.sequence = sequence
        return self.reply(q)

    def reply(self, q):
        active = 4 <= self.age <= 6
        top = -45 if self.down else -80
        action = 161 if self.defeated else 106 if self.stun else 68 if self.age else 1
        state = dict(Frame=self.tick, X=self.x, Y=self.y, VY=self.vy,
                     Action=action, RenderAction=action, Hitstop=self.stop, Stun=self.stun,
                     AttackID=self.activation, Guarded=self.guarded and bool(self.stun),
                     Defeated=self.defeated, Knockdown=self.defeated)
        pose = dict(Crouch=self.down, Attacking=bool(self.age), Normal=bool(self.age),
                    Down=self.defeated, CanTurn=not self.age and not self.stun)
        image = self.image(top, active)
        shared = self.layer is not None and 'shared-layer:d3d12' in self.accepted
        extra = {}
        if shared:   # the same rectangles, rendered on the GPU into the shared texture; no RGBA bytes
            extra = dict(layer=self.layer_frame(top, active))
            image = dict(Width=0, Height=0, Pivot=[0, 0], RGBA='')
        capabilities = CAPABILITIES + (['shared-layer:d3d12'] if self.layer is not None else [])
        return dict(version=1, session=q['session'], game=self.game, sequence=q['sequence'],
                    tick=self.tick, capabilities=capabilities, state=state, pose=pose, **extra,
                    defense=dict(CanGuard=not self.age and not self.stun, Back=self.back,
                                 Crouch=self.down, Air=self.y < 0, Down=self.defeated),
                    attack=dict(Damage=60 if self.variant == 'amber' else 45, Chip=2,
                                Hitstun=15, Blockstun=12, Hitstop=[5, 5], Guardstop=[4, 4],
                                BlockHigh=True, BlockLow=True, PushX=2.4, GuardPush=1.6, Gravity=.3),
                    hitboxes=[[15, -60, 55, -20]] if active else [],
                    hurtboxes=[[-15, top, 15, 0]], image=image)

    WIDTH, HEIGHT, PIVOT = 96, 96, (24, 88)

    def rects(self, top, active):
        color = (235, 162, 40, 255) if self.variant == 'amber' else (35, 185, 225, 255)
        if self.defeated:
            return [(-15, -12, 35, 0, color)]
        shapes = [(-12, top, 12, 0, color), (12, top + 6, 18, top + 12, (255, 255, 255, 255)),  # right-facing nose
                  (-5, top + 5, 1, top + 10, (20, 20, 20, 255))]
        return shapes + ([(12, -52, 55, -35, color)] if active else [])

    def image(self, top, active):
        width, height, (px, py) = self.WIDTH, self.HEIGHT, self.PIVOT
        rgba = bytearray(width * height * 4)
        for left, upper, right, lower, tint in self.rects(top, active):
            for y in range(max(0, py + upper), min(height, py + lower)):
                for x in range(max(0, px + left), min(width, px + right)):
                    offset = 4 * (y * width + x)
                    rgba[offset:offset + 4] = bytes(tint)
        return dict(Width=width, Height=height, Pivot=[px, py], RGBA=base64.b64encode(rgba).decode('ascii'))

    def layer_frame(self, top, active):
        px, py = self.PIVOT
        # Opaque authored colours: premultiplied equals straight.
        self.layer.render([(px + l, py + u, px + r, py + d, tuple(c / 255 for c in tint))
                           for l, u, r, d, tint in self.rects(top, active)])
        return self.layer.describe(self.PIVOT)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', required=True)
    p.add_argument('--variant', choices=('amber', 'cyan'), required=True)
    p.add_argument('--ready', type=Path, required=True)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--shared-layer', action='store_true', help='offer shared-layer:d3d12 (Windows, D3D12)')
    args = p.parse_args()
    layer = None
    if args.shared_layer:
        from shared_layer_demo import SharedLayer, unique_stem
        layer = SharedLayer(Fighter.WIDTH, Fighter.HEIGHT, unique_stem(args.variant))
    with socket.socket() as listener, args.log.open('w', encoding='utf-8') as log:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        ready_tmp = args.ready.with_suffix('.tmp')
        ready_tmp.write_text(json.dumps(dict(version=1, game=args.game,
                                            address=f'127.0.0.1:{listener.getsockname()[1]}')))
        ready_tmp.replace(args.ready)
        while True:
            conn, _ = listener.accept()
            f = Fighter(args.game, args.variant, layer)
            with conn:
                conn.settimeout(30)
                try:
                    while True:
                        size, = struct.unpack('!I', read_exact(conn, 4))
                        if not 0 < size <= LIMIT:
                            raise ValueError('invalid message size')
                        q = json.loads(read_exact(conn, size))
                        started = time.perf_counter()
                        reply = f.apply(q)
                        q['guest_ms'] = round((time.perf_counter() - started) * 1000, 3)   # diagnostics only
                        # Frame identity and input/contact evidence, never image bytes in logs.
                        log.write(json.dumps({k: v for k, v in q.items()}) + '\n')
                        log.flush()
                        data = json.dumps(reply, separators=(',', ':')).encode('utf-8')
                        conn.sendall(struct.pack('!I', len(data)) + data)
                except (EOFError, ConnectionError, TimeoutError):
                    pass


if __name__ == '__main__':
    main()
