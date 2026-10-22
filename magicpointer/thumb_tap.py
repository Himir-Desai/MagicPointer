"""Experimental thumb-to-curled-finger tap from fused WiLoR joints.

Distances indicate estimated proximity, never proof of physical contact.
"""
import math

import numpy as np

from .engine import Gesture
from .tracking import gesture_metrics
from .wilor_gestures import ThumbFilter, segment_distance


class ThumbTapFilter:
    contact_distance = .12
    release_distance = .24
    max_contact_seconds = .8

    def __init__(self):
        self.chords = ThumbFilter()
        self.reset()

    def reset(self):
        self.chords.reset()
        self._reset_tap()

    def _reset_tap(self):
        self.key = self.last = self.since = self.contact_since = None
        self.zone = None
        self.hits = 0
        self.state = 'waiting for thumb lift'

    def _confirm(self, zone, now, duration):
        if zone != self.zone:
            self.zone, self.since, self.hits = zone, now, 0
        self.hits += 1
        return self.hits >= 2 and now-self.since >= duration

    def update(self, key, hand, now):
        if hand is None:
            self.reset()
            return None
        if not math.isfinite(now):
            self.reset()
            hand.gesture = Gesture.UNKNOWN
            hand.diagnostics = {'thumb_tap': {'state': 'invalid time', 'click': False}}
            return hand
        # A missing view/source change must not supply the far end of a tap.
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
        distance, pulse = None, False
        if eligible:
            p = np.asarray(hand.world, float)
            width = float(np.linalg.norm(p[5]-p[17]))
            eligible = width > 1e-6
            if eligible:
                # Only the distal chains of middle/ring/little are tap surfaces;
                # the extended index and knuckles are intentionally excluded.
                distance = min(segment_distance(p[4], p[4], p[start+i], p[start+i+1])
                               for start in (9,13,17) for i in (1,2))/width
        if not eligible:
            self.state = 'waiting for thumb lift'
            self.zone = self.since = self.contact_since = None
            self.hits = 0
        else:
            # Thumb extension is no longer a left-click chord in this mode.
            # Two-finger right click, scrolling, fist and palm remain unchanged.
            hand.gesture = Gesture.POINT
            zone = ('near' if distance <= self.contact_distance else
                    'away' if distance >= self.release_distance else 'between')
            duration = .08 if self.state == 'waiting for thumb lift' else .04
            confirmed = self._confirm(zone, now, duration)
            if self.contact_since is not None and now-self.contact_since > self.max_contact_seconds:
                self.state = 'waiting for thumb lift'
                self.zone = self.since = self.contact_since = None
                self.hits = 0
            elif self.state == 'waiting for thumb lift' and zone == 'away' and confirmed:
                self.state = 'ready'
                self.zone = None
            elif self.state == 'ready' and zone == 'near':
                self.contact_since = now
                self.state = 'approaching fingers'
            elif self.state == 'approaching fingers':
                if zone == 'near' and confirmed:
                    self.state = 'contact estimated'
                    self.zone = None
                elif zone == 'away':
                    self.state = 'ready'
                    self.contact_since = None
                    self.zone = None
            elif self.state == 'contact estimated' and zone == 'away' and confirmed:
                pulse = True
                self.state = 'waiting for thumb lift'
                self.zone = self.since = self.contact_since = None
                self.hits = 0
        hand.diagnostics['thumb_tap'] = {
            'state': self.state, 'eligible': eligible, 'click': pulse,
            'distance_palm_widths': distance, 'contact_threshold': self.contact_distance,
            'release_threshold': self.release_distance, 'max_contact_seconds': self.max_contact_seconds,
            'contact_since': self.contact_since, 'fresh_samples': self.hits,
            'note': 'estimated 3D proximity; not physical contact or calibrated confidence'}
        return hand
