"""Screen-space jitter suppression, independent of the hand model."""
import math


class CursorSmoother:
    def __init__(self):
        self.reset()

    def reset(self):
        self.target = None

    def update(self, target, cursor, dt):
        # A soft radial deadband rejects tiny vibrations without quantizing axes.
        if self.target is None:
            self.target = tuple(target)
        else:
            delta = tuple(a-b for a, b in zip(target, self.target))
            length = math.hypot(*delta)
            radius = .0025
            if length > radius:
                self.target = tuple(a+d*(1-radius/length) for a, d in zip(self.target, delta))
        distance = math.dist(self.target, cursor)
        # More damping for precise/slow motion, less lag for large movements.
        tau = .14 - .085*min(1., distance/.08)
        alpha = 1-math.exp(-max(0., dt)/tau)
        return tuple(a+alpha*(b-a) for a, b in zip(cursor, self.target))
