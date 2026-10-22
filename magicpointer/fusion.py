"""A single gesture from palm-aligned landmark evidence in matched camera views."""
import numpy as np

from .tracking import Hand, classify


def canonical(hand):
    if hand is None:
        return None
    points = np.asarray(hand.world, dtype=float)
    if points.shape != (21, 3) or not np.isfinite(points).all():
        return None
    points = points-points[0]
    scale = np.linalg.norm(points[9])
    across = points[5]-points[17]
    if scale < 1e-6 or np.linalg.norm(across) < 1e-6:
        return None
    across /= np.linalg.norm(across)
    forward = points[9]-across*np.dot(points[9], across)
    if np.linalg.norm(forward) < 1e-6:
        return None
    forward /= np.linalg.norm(forward)
    normal = np.cross(across, forward)
    return points @ np.column_stack((across, forward, normal)) / scale


def combine(hands, *, ignore_thumb=False, bound_pair=False, diagnostics=None):
    """Normalize each view, average geometry, then classify ONCE.

    Labels are diagnostics, not votes. Missing/invalid views contribute no
    geometry. Bound identities can disagree in shape: classify their combined
    evidence instead of requiring two independent gesture estimates to agree.
    Canonical coordinates are not metric stereo depth.
    """
    evidence = [(index, hand, canonical(hand)) for index, hand in enumerate(hands or []) if hand is not None]
    evidence = [(index, hand, points) for index, hand, points in evidence if points is not None]
    if not evidence:
        return None, 'No usable selected-hand geometry', None
    indices_used, hands, points = zip(*evidence)
    if not bound_pair and len({hand.label for hand in hands}) != 1:
        return None, 'Handedness differs between views', None
    indices = list(range(5, 21)) if ignore_thumb else list(range(21))
    spread = max(float(np.sqrt(np.mean(np.sum((point[indices]-points[0][indices])**2, axis=1)))) for point in points)
    if diagnostics is not None:
        residual = np.max([np.linalg.norm(point-points[0], axis=1) for point in points], axis=0)
        diagnostics.update(shape_spread=spread, spread_limit=.40,
                           contributing_views=list(indices_used), evidence_views=len(points),
                           fusion_method='equal mean of palm-aligned valid 3D geometry',
                           confidence_note='view count and residual are evidence measures, not calibrated probabilities',
                           landmark_disagreement=residual.tolist(),
                           finger_disagreement={name: float(np.sqrt(np.mean(residual[start:start+4]**2)))
                                                for name, start in zip(('thumb','index','middle','ring','little'), (1,5,9,13,17))},
                           handedness_agrees=len({hand.label for hand in hands}) == 1,
                           bound_pair=bound_pair)
    if spread > .40 and not bound_pair:
        return None, 'Views disagree on hand shape', spread
    world = np.mean(points, axis=0)
    profile = hands[0].profile
    fused = Hand(hands[0].pixels, world, hands[0].label, classify(world, profile=profile), profile=profile,
                 diagnostics={'fusion_views': list(indices_used)})
    return fused, 'Combined landmark geometry' if len(hands) > 1 else 'Single-view hand geometry', spread
