"""Fixed palm-relative thumb rules for WiLoR; no trained gesture classifier."""
import numpy as np

from .engine import Gesture
from .tracking import gesture_metrics

PROFILE = 'wilor-fixed-v1'


def segment_distance(a, b, c, d):
    """Closest distance of two finite 3D segments, including parallel segments."""
    u, v, w = b-a, d-c, a-c
    uu, uv, vv = np.dot(u, u), np.dot(u, v), np.dot(v, v)
    if uu < 1e-12 and vv < 1e-12:
        return float(np.linalg.norm(a-c))
    if uu < 1e-12:
        return float(np.linalg.norm(a-c-np.clip(np.dot(a-c, v)/vv, 0., 1.)*v))
    if vv < 1e-12:
        return float(np.linalg.norm(c-a-np.clip(np.dot(c-a, u)/uu, 0., 1.)*u))
    determinant = uu*vv-uv*uv
    candidates = []
    if determinant > 1e-12:
        s = (uv*np.dot(v, w)-vv*np.dot(u, w))/determinant
        t = (uu*np.dot(v, w)-uv*np.dot(u, w))/determinant
        if 0 <= s <= 1 and 0 <= t <= 1:
            candidates.append(np.linalg.norm(w+s*u-t*v))
    for point in (a, b):
        t = np.clip(np.dot(point-c, v)/vv, 0., 1.)
        candidates.append(np.linalg.norm(point-(c+t*v)))
    for point in (c, d):
        s = np.clip(np.dot(point-a, u)/uu, 0., 1.)
        candidates.append(np.linalg.norm(point-(a+s*u)))
    return float(min(candidates))


def metrics(points, *, was_open=False):
    base = gesture_metrics(points)
    if not base['valid']:
        return base
    p = np.asarray(points, dtype=float)
    across = p[5]-p[17]
    width = float(np.linalg.norm(across))
    if width < 1e-6:
        return {'valid': False, 'gesture': Gesture.UNKNOWN.value, 'reason': 'degenerate palm width'}
    across /= width
    radial = float(np.dot(p[4]-p[5], across)/width)
    direction = p[4]-p[2]
    outward = float(np.dot(direction, across)/max(np.linalg.norm(direction), 1e-9))
    clearance = min(segment_distance(p[3], p[4], p[start+i], p[start+i+1])
                    for start in (5, 9, 13, 17) for i in range(3))/width
    ip = base['thumb']['ip_degrees']
    # A straight thumb lying across/inside the palm is still tucked. Apparent
    # overlap is a proximity cue in 3D, not a literal 2D-intersection requirement.
    near_fingers = clearance < .12
    closed = radial <= .08 or ip < 125 or outward <= .05 or near_fingers
    limits = (.14, 130., .10, .12) if was_open else (.22, 140., .20, .18)
    opened = (radial >= limits[0] and ip >= limits[1] and outward >= limits[2]
              and clearance >= limits[3] and not closed)
    state = 0 if closed else (1 if opened else -1)
    signature = [state, *base['signature'][1:]]
    gesture = from_signature(signature)
    base.update(classifier_profile=PROFILE, gesture=gesture.value, signature=signature)
    base['thumb'].update(state=state, radial_beyond_index_widths=radial,
                         outward_direction=outward, finger_clearance_widths=clearance,
                         near_finger_chain=near_fingers, using_open_exit_thresholds=was_open)
    return base


def from_signature(signature):
    return {(0, 0, 0, 0, 0): Gesture.FIST, (0, 1, 0, 0, 0): Gesture.POINT,
            (1, 1, 0, 0, 0): Gesture.LEFT, (1, 1, 1, 0, 0): Gesture.RIGHT,
            (0, 1, 1, 0, 0): Gesture.SCROLL, (1, 1, 1, 1, 1): Gesture.PALM}.get(tuple(signature), Gesture.UNKNOWN)


class ThumbFilter:
    """Geometric hysteresis plus two fresh observations before thumb opening."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.key = self.last = self.since = None
        self.open = False
        self.hits = 0

    def update(self, key, hand, now):
        if hand is None:
            self.reset()
            return None
        if key != self.key or self.last is None or now-self.last > .6:
            self.reset()
            self.key = key
        fresh = self.last is None or now > self.last
        self.last = now
        result = metrics(hand.world, was_open=self.open)
        if not result['valid']:
            self.reset()
            hand.gesture = Gesture.UNKNOWN
            return hand
        thumb = result['signature'][0]
        if thumb == 0:
            self.open = False
            self.hits, self.since = 0, None
        elif thumb == 1 and not self.open:
            if self.since is None:
                self.since = now
            self.hits += int(fresh)
            self.open = self.hits >= 2 and now-self.since >= .08
            if not self.open:
                result['signature'][0] = -1
        elif thumb == -1:
            self.open = False
            self.hits, self.since = 0, None
        result['thumb']['state'] = result['signature'][0]
        hand.gesture = from_signature(result['signature'])
        result['gesture'] = hand.gesture.value
        hand.diagnostics = {**(hand.diagnostics or {}), 'gesture_metrics': result,
                            'thumb_confirmation': {'open': self.open, 'fresh_samples': self.hits,
                                                   'minimum_samples': 2, 'minimum_seconds': .08}}
        return hand
