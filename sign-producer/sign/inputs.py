"""uf-arena's held input names to the pinned SIGN native input word."""

BITS = dict(up=1, down=2, left=4, right=8, punch=16, kick=32,
            slash=64, heavy=128, dust=256)


def encode(held):
    """Absolute directions; simultaneous opposites are neutral."""
    if type(held) is not dict or any(name not in BITS or type(on) is not bool
                                     for name, on in held.items()):
        raise ValueError('unsupported SIGN host input')
    on = {name for name, active in held.items() if active}
    for a, b in (('left', 'right'), ('up', 'down')):
        if a in on and b in on:
            on.difference_update((a, b))
    return sum(BITS[name] for name in on)
