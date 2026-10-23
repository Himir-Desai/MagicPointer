"""Track local hand identities and bind one matched hand across camera views."""
from dataclasses import dataclass
import itertools
import math

import numpy as np

from .engine import Gesture
from .fusion import combine
from .tracking import PoseStabilizer


class LocalHands:
    """Conservative spatial continuity; detector list order never identifies a hand."""
    def __init__(self):
        self.tracks = {}
        self.next_id = 1
        self.labels = {}
        self.diagnostics = {}

    def update(self, hands, now, size, keep=None):
        self.tracks = {key: value for key, value in self.tracks.items()
                       if now-value[3] <= 1. or key == keep}
        self.labels = {key: self.labels[key] for key in self.tracks}
        trace = {'owner_id': keep, 'tracks_before': [
            {'id': key, 'wrist': value[1].tolist(), 'scale': value[2], 'last_seen': value[3], 'stable_label': self.labels[key]}
            for key, value in self.tracks.items()], 'costs': [], 'assignments': [], 'ambiguous_tracks': []}
        self.diagnostics = trace
        diagonal = math.hypot(*size)
        current = []
        for hand in hands:
            pixels = np.asarray(hand.pixels)
            current.append((hand, pixels[0]/diagonal,
                            max(.008, float(np.linalg.norm(pixels[0]-pixels[9]))/diagonal)))
        costs = {}
        for key, (old, wrist, scale, seen) in self.tracks.items():
            for index, (hand, position, length) in enumerate(current):
                spatial = float(np.linalg.norm(position-wrist))/max(scale, length)
                mismatch = self.labels[key] != hand.label
                allowed_flip = key == keep and spatial <= .75
                cost = spatial + .3*abs(math.log(length/scale)) + (.35 if mismatch else 0.)
                rejected = 'handedness' if mismatch and not allowed_flip else ('distance' if cost > 3. else None)
                trace['costs'].append({'track_id': key, 'detection': index, 'spatial_cost': spatial,
                                       'total_cost': cost, 'label_mismatch': mismatch,
                                       'allowed_owner_label_flip': allowed_flip and mismatch, 'rejected': rejected})
                if rejected is None:
                    costs[key, index] = cost
        assigned = {}
        used = set()
        for key in self.tracks:
            choices = sorted((cost, index) for (track, index), cost in costs.items() if track == key)
            if not choices:
                continue
            cost, index = choices[0]
            rivals = sorted((value, track) for (track, detection), value in costs.items() if detection == index)
            if rivals[0][1] != key or (len(choices) > 1 and choices[1][0]-cost < .5) or (len(rivals) > 1 and rivals[1][0]-cost < .5):
                trace['ambiguous_tracks'].append(key)
                continue
            assigned[key] = index
            used.add(index)
        for index in range(len(current)):
            if index not in used and not any(detection == index for _, detection in costs):
                assigned[self.next_id] = index
                self.labels[self.next_id] = current[index][0].label
                self.next_id += 1
        visible = {}
        for key, index in assigned.items():
            hand, wrist, scale = current[index]
            self.tracks[key] = (hand, wrist, scale, now)
            visible[key] = hand
            trace['assignments'].append({'track_id': key, 'detection': index})
        trace['unassigned_detections'] = [index for index in range(len(current)) if index not in assigned.values()]
        return visible


@dataclass
class Selection:
    key: object = None
    hands: object = None
    combined: object = None
    reason: str = 'Show one fist to select a hand'
    progress: float = 0.
    spread: object = None


class HandOwner:
    def __init__(self, cameras, dwell=2.5, timeout=5.):
        self.locals = [LocalHands() for _ in range(cameras)]
        self.visible = [{} for _ in range(cameras)]
        self.owner = self.candidate = self.since = None
        self.dwell = dwell
        # Release an owner that stays missing or unusable this long; 0 never releases.
        self.timeout = timeout
        self.lost_since = None
        self.expired = False
        self.palm_since = None
        self.release_ready = False
        self.diagnostics = {}
        self.stabilizers = {}

    def release(self):
        self.owner = self.candidate = self.since = None
        self.lost_since = None
        self.palm_since = None
        self.release_ready = False

    def lock(self, key):
        self.owner = key
        self.candidate = self.since = None
        self.lost_since = None
        self.palm_since = None
        self.release_ready = False

    def select(self, detections, frames, now, *, stereo=None, scrolling=False):
        self.visible = [tracker.update(hands, now, frame.image.shape[1::-1],
                                      self.owner[index] if self.owner else None)
                        for index, (tracker, hands, frame) in enumerate(zip(self.locals, detections, frames))]
        self.diagnostics = {'timestamp': now, 'pairs': [], 'ambiguous_pair_margins': []}
        self.expired = False
        self.stabilizers = {key: value for key, value in self.stabilizers.items() if value.time is not None and now-value.time <= 1.}
        def result(key):
            hands = [view.get(track) for view, track in zip(self.visible, key)]
            details = {}
            fused, reason, spread = combine(hands, ignore_thumb=scrolling, bound_pair=self.owner is not None, diagnostics=details)
            if fused is not None and stereo:
                anchors = (0, 5, 9, 13, 17)
                points = stereo.reconstruct(hands[0].pixels[list(anchors)], hands[1].pixels[list(anchors)])
                if points is None:
                    fused, reason = None, 'Hands do not form a valid stereo pair'
            if fused is not None:
                # Each matched pair keeps its own digit hysteresis across frames.
                details['frame_gesture'] = fused.gesture
                fused.gesture = self.stabilizers.setdefault(key, PoseStabilizer()).update(fused.world, now)
            self.diagnostics['pairs'].append({'ids': key, 'reason': reason, 'valid': fused is not None,
                                               'gesture': fused.gesture if fused else None, **details})
            return Selection(key, hands, fused, reason, spread=spread)
        if self.owner:
            selected = result(self.owner)
            if selected.combined is None:
                if self.lost_since is None:
                    self.lost_since = now
                lost = now-self.lost_since
                self.diagnostics['owner_lost_seconds'] = lost
                if self.timeout and lost >= self.timeout:
                    # The selected hand is gone; any hand can now be selected with a new fist hold.
                    self.release()
                    self.expired = True
                    self.diagnostics['owner_released'] = 'timeout'
                else:
                    release = f' (releases in {self.timeout-lost:.1f}s)' if self.timeout else ''
                    selected.reason = 'OWNER PAUSED'+release+': '+selected.reason
            else:
                self.lost_since = None
        if self.owner:
            if selected.combined is not None and selected.combined.gesture == Gesture.PALM:
                if self.palm_since is None:
                    self.palm_since = now
                agreed_palm = len(selected.hands) == 2 and all(hand.gesture == Gesture.PALM for hand in selected.hands)
                self.release_ready = agreed_palm or now-self.palm_since >= .18
                self.diagnostics['palm_release_evidence'] = 'two_view_agreement' if agreed_palm else 'temporal_dwell'
            else:
                self.palm_since, self.release_ready = None, False
            return selected
        candidates = [result(key) for key in itertools.product(*(view.keys() for view in self.visible))]
        candidates = [item for item in candidates if item.combined is not None]
        # Uncalibrated association needs a unique reciprocal shape match. Similar
        # same-handed hands cannot be disambiguated reliably; wait, never guess.
        if len(self.locals) == 2:
            accepted = []
            for item in candidates:
                unique = True
                for camera in (0, 1):
                    rivals = sorted(other.spread for other in candidates
                                    if other.key[camera] == item.key[camera] and other.key != item.key)
                    if rivals and rivals[0]-item.spread < .08:
                        self.diagnostics['ambiguous_pair_margins'].append({'ids': item.key, 'camera': camera,
                                                                          'margin': rivals[0]-item.spread, 'required': .08})
                        unique = False
                if unique:
                    accepted.append(item)
            self.diagnostics['accepted_pair_ids'] = [item.key for item in accepted]
            candidates = accepted
        fists = [item for item in candidates if item.combined.gesture == Gesture.FIST]
        if len(fists) != 1:
            self.candidate = self.since = None
            if len(fists) > 1:
                return Selection(reason='MULTIPLE FISTS: keep only one fist raised')
            if len(candidates) == 1:
                item = candidates[0]
                item.reason = 'Show a fist for 2.5 seconds to select this hand'
                return item
            return Selection(reason='Show one clear fist in all views; separate overlapping hands')
        item = fists[0]
        if item.key != self.candidate:
            self.candidate, self.since = item.key, now
        item.progress = min(1., (now-self.since)/self.dwell)
        item.reason = f'HOLD FIST: {max(0., self.dwell-(now-self.since)):.1f}s'
        return item
