"""Fresh detector evidence before reconstruction; never invent missing landmarks."""
import math
import numpy as np


def box_cost(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    size_a, size_b = a[2:]-a[:2], b[2:]-b[:2]
    scale = max(float(np.linalg.norm(size_a)), float(np.linalg.norm(size_b)), 1.)
    center = float(np.linalg.norm((a[:2]+a[2:]-b[:2]-b[2:])/2))/scale
    ratio = abs(math.log(max(float(np.prod(size_a)), 1.)/max(float(np.prod(size_b)), 1.)))
    return center+.15*ratio


class DetectionValidator:
    def __init__(self, confidence=.50):
        self.confidence = confidence
        self.tracks = []
        self.locked = False
        self.trace = {}
        self.last_timestamp = None

    def update(self, proposals, timestamp, owner=None):
        if not math.isfinite(timestamp) or (self.last_timestamp is not None and timestamp <= self.last_timestamp):
            self.trace = {'raw': len(proposals), 'accepted': 0, 'reason': 'stale/nonfinite capture timestamp'}
            return []
        self.last_timestamp = timestamp
        rejected, eligible = [], []
        for proposal in proposals:
            box = np.asarray(proposal['box'], dtype=float)
            if (box.shape != (4,) or not np.isfinite(box).all()
                    or np.min(box[2:]-box[:2]) < 8 or not math.isfinite(proposal['score'])
                    or proposal['score'] < self.confidence):
                rejected.append({'box': box.tolist(), 'reason': 'confidence or invalid/tiny box'})
            else:
                eligible.append(proposal)
        if self.locked != bool(owner):
            self.tracks = []
        self.locked = bool(owner)
        if owner:
            matches = []
            for proposal in eligible:
                cost = box_cost(owner['box'], proposal['box'])
                flipped = proposal['label'] != owner['label']
                limit = .8+min(.6, max(0., owner.get('age', 0.)))
                if cost <= limit and (not flipped or cost <= .2):
                    matches.append((cost, proposal))
                else:
                    rejected.append({'box': proposal['box'], 'reason': 'outside selected-hand continuity gate'})
            matches.sort(key=lambda item: item[0])
            ambiguous = len(matches) > 1 and matches[1][0]-matches[0][0] < .20
            accepted = [] if not matches or ambiguous else [matches[0][1]]
            self.trace = {'mode': 'selected-hand', 'raw': len(proposals), 'accepted': len(accepted),
                          'ambiguous': ambiguous, 'rejected': rejected,
                          'fresh_only': True, 'owner': owner}
            return accepted
        previous = [track for track in self.tracks if 0 <= timestamp-track['last'] <= .6]
        tracks, accepted = [], []
        used = set()
        for proposal in eligible:
            matches = sorted((box_cost(track['box'], proposal['box']), index)
                             for index, track in enumerate(previous) if track['label'] == proposal['label'])
            track = None
            if matches and matches[0][0] <= .65:
                cost, index = matches[0]
                # Reciprocal uniqueness: an overlapping object/hand must not
                # acquire another candidate's accumulated confirmation evidence.
                rivals = sorted(box_cost(previous[index]['box'], other['box'])
                                for other in eligible if other['label'] == proposal['label'])
                unique = ((len(matches) == 1 or matches[1][0]-cost >= .20)
                          and (len(rivals) == 1 or rivals[1]-rivals[0] >= .20))
                if unique and index not in used:
                    track = previous[index].copy()
                    used.add(index)
            if track is None:
                track = {'first': timestamp, 'last': timestamp, 'hits': 0}
            fresh = track['hits'] == 0 or timestamp > track['last']
            track.update(box=proposal['box'], label=proposal['label'], last=timestamp,
                         hits=track['hits']+int(fresh))
            tracks.append(track)
            if track['hits'] >= 2 and timestamp-track['first'] >= .08:
                accepted.append(proposal)
        self.tracks = tracks
        self.trace = {'mode': 'confirmation', 'raw': len(proposals), 'accepted': len(accepted),
                      'pending': len(eligible)-len(accepted), 'rejected': rejected,
                      'minimum_samples': 2, 'minimum_seconds': .08, 'fresh_only': True}
        return accepted


def valid_geometry(value):
    """Reject broken projections/degenerate geometry, not a promise of a real hand."""
    points, world = np.asarray(value['pixels']), np.asarray(value['world'])
    if points.shape != (21, 2) or world.shape != (21, 3):
        return False
    if not np.isfinite(points).all() or not np.isfinite(world).all():
        return False
    palm = np.linalg.norm(world[9]-world[0])
    if palm < 1e-6 or np.linalg.norm(points[9]-points[0]) < 2.:
        return False
    lengths = [np.linalg.norm(world[start+i+1]-world[start+i])/palm
               for start in (1, 5, 9, 13, 17) for i in range(3)]
    return all(.015 < length < 2. for length in lengths)
