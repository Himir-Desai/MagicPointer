"""Experimental open-thumb pointing with close/reopen left clicks."""
import math

from .engine import Gesture
from .tracking import gesture_metrics
from .wilor_gestures import ThumbFilter


class ThumbTapFilter:
    max_closed_seconds = .8

    def __init__(self):
        self.chords = ThumbFilter()
        self.reset()

    def reset(self):
        self.chords.reset()
        self._reset_tap()

    def _reset_tap(self):
        self.key = self.last = self.closed_since = None
        self.since = None
        self.hits = 0
        self.state = 'waiting for open thumb'

    def update(self, key, hand, now):
        if hand is None:
            self.reset()
            return None
        if not math.isfinite(now):
            self.reset()
            hand.gesture = Gesture.UNKNOWN
            hand.diagnostics = {'thumb_tap': {'state': 'invalid time', 'click': False}}
            return hand
        tap_key = (key, tuple((hand.diagnostics or {}).get('fusion_views', ())))
        if tap_key != self.key or self.last is None or now-self.last > .6:
            self._reset_tap()
            self.key = tap_key
        if self.last is not None and now <= self.last:
            self.reset()
            hand.gesture = Gesture.UNKNOWN
            hand.diagnostics = {'thumb_tap': {'state': 'stale sample', 'click': False}}
            return hand
        self.last = now
        hand = self.chords.update(key, hand, now)
        hand.diagnostics = hand.diagnostics or {}
        base = gesture_metrics(hand.world)
        eligible = base['valid'] and base['signature'][1:] == [1,0,0,0]
        thumb = hand.diagnostics.get('gesture_metrics', {}).get('signature', [-1])[0]
        pulse, pause = False, False
        if not eligible:
            self.state = 'waiting for open thumb'
            self.closed_since = self.since = None
            self.hits = 0
        else:
            # The original thumb hysteresis/opening confirmation is reused.
            # Only an open thumb with the pointing index moves the cursor.
            hand.gesture = Gesture.POINT if thumb == 1 else Gesture.UNKNOWN
            pause = thumb != 1
            if self.closed_since is not None and now-self.closed_since > self.max_closed_seconds:
                self.state = 'waiting for open thumb'
                self.closed_since = self.since = None
                self.hits = 0
            elif self.state == 'waiting for open thumb':
                if thumb == 1:
                    self.state = 'ready'
            elif self.state == 'ready':
                if thumb == 0:
                    self.state = 'closing thumb'
                    self.closed_since = self.since = now
                    self.hits = 1
            elif self.state == 'closing thumb':
                if thumb == 0:
                    self.hits += 1
                    if self.hits >= 2 and now-self.since >= .04:
                        self.state = 'thumb closed'
                else:
                    # A single closed sample/uncertain interruption is not a tap.
                    self.state = 'ready' if thumb == 1 else 'waiting for open thumb'
                    self.closed_since = self.since = None
                    self.hits = 0
            elif self.state == 'thumb closed' and thumb == 1:
                pulse = True
                self.state = 'ready'
                self.closed_since = self.since = None
                self.hits = 0
        hand.diagnostics['thumb_tap'] = {
            'method': 'open-close-reopen', 'state': self.state,
            'eligible': eligible, 'click': pulse, 'pointer_pause': pause,
            'thumb_state': thumb, 'closed_since': self.closed_since,
            'max_closed_seconds': self.max_closed_seconds,
            'closed_samples': self.hits, 'minimum_closed_seconds': .04,
            'note': 'estimated thumb state; no finger contact required'}
        return hand
