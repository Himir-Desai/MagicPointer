import unittest
import numpy as np

from magicpointer.engine import Gesture
from magicpointer.tracking import Hand, classify, gesture_metrics
from magicpointer.wilor_gestures import PROFILE, ThumbFilter, metrics, segment_distance
from magicpointer.wilor_validation import DetectionValidator, valid_geometry
from test_tracking import hand


class WiLoRGestureTests(unittest.TestCase):
    def test_fixed_poses_survive_rotations_reflections_and_scale(self):
        rng = np.random.default_rng(174)
        for thumb, fingers, expected in [
                (False, [0,0,0,0], Gesture.FIST), (False, [1,0,0,0], Gesture.POINT),
                (True, [1,0,0,0], Gesture.LEFT), (True, [1,1,0,0], Gesture.RIGHT),
                (False, [1,1,0,0], Gesture.SCROLL), (True, [1,1,1,1], Gesture.PALM)]:
            for _ in range(8):
                rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
                rotation[:, 0] *= rng.choice([-1, 1])
                points = hand(thumb, fingers) @ rotation * rng.uniform(.5, 3.) + rng.normal(size=3)
                self.assertEqual(classify(points, profile=PROFILE), expected)

    def test_straight_thumb_across_palm_is_point_instead_of_false_click(self):
        points = hand(False, [1,0,0,0])
        points[2:5] = [[-.04,-.03,0],[-.02,-.05,0],[0.,-.07,0]]
        self.assertEqual(classify(points), Gesture.LEFT)  # original failure mechanism
        self.assertEqual(classify(points, profile=PROFILE), Gesture.POINT)
        self.assertLess(metrics(points)['thumb']['radial_beyond_index_widths'], .08)

    def test_actual_3d_overlap_rejects_open_thumb_without_assuming_2d_overlap_is_contact(self):
        points = hand(True, [1,0,0,0])
        points[2:5] = [[.01,-.14,0],[0.,-.13,0],[-.07,-.12,0]]
        self.assertTrue(metrics(points)['thumb']['near_finger_chain'])
        self.assertEqual(classify(points, profile=PROFILE), Gesture.POINT)
        points[2:5, 2] = .08
        self.assertFalse(metrics(points)['thumb']['near_finger_chain'])
        self.assertEqual(classify(points, profile=PROFILE), Gesture.LEFT)

    def test_segment_distance_handles_crossing_parallel_and_degenerate_segments(self):
        zero = np.zeros(3)
        self.assertAlmostEqual(segment_distance(zero, np.array([2.,0,0]), np.array([1.,-1,0]), np.array([1.,1,0])), 0.)
        self.assertAlmostEqual(segment_distance(zero, np.array([2.,0,0]), np.array([0.,1,0]), np.array([2.,1,0])), 1.)
        self.assertAlmostEqual(segment_distance(zero, zero, np.array([-1.,0,0]), np.array([1.,0,0])), 0.)

    def test_open_thumb_requires_fresh_confirmation_and_clears_on_loss_or_identity_change(self):
        filt = ThumbFilter()
        def sample(points):
            return Hand(points[:,:2]*1000, points, 'Right', Gesture.UNKNOWN, profile=PROFILE)
        left = hand(True, [1,0,0,0])
        self.assertEqual(filt.update((1,), sample(left), 1.).gesture, Gesture.UNKNOWN)
        self.assertEqual(filt.update((1,), sample(left), 1.).gesture, Gesture.UNKNOWN)
        self.assertEqual(filt.update((1,), sample(left), 1.1).gesture, Gesture.LEFT)
        self.assertEqual(filt.update((1,), sample(hand(False, [1,0,0,0])), 1.2).gesture, Gesture.POINT)
        self.assertEqual(filt.update((1,), sample(left), 1.3).gesture, Gesture.UNKNOWN)
        self.assertEqual(filt.update((1,), sample(left), 1.4).gesture, Gesture.LEFT)
        self.assertIsNone(filt.update((1,), None, 1.5))
        self.assertEqual(filt.update((1,), sample(left), 1.6).gesture, Gesture.UNKNOWN)
        self.assertEqual(filt.update((2,), sample(left), 1.7).gesture, Gesture.UNKNOWN)

    def test_ambiguous_thumb_stays_unknown_without_changing_legacy_rules(self):
        points = hand(True, [1,0,0,0])
        points[2:5] = [[-.029,-.02,0],[-.034,-.04,0],[-.039,-.06,0]]
        self.assertEqual(metrics(points)['signature'][0], -1)
        self.assertEqual(classify(points, profile=PROFILE), Gesture.UNKNOWN)
        self.assertEqual(gesture_metrics(points)['classifier_version'], 2)


def proposal(x=10., label='Right', score=.7):
    return {'box': [x,10.,x+100.,130.], 'label': label, 'score': score}


class DetectorValidationTests(unittest.TestCase):
    def test_single_frame_false_positive_and_low_score_do_not_reach_pose_model(self):
        validator = DetectionValidator(.50)
        self.assertEqual(validator.update([proposal(score=.49)], 1.), [])
        self.assertEqual(validator.update([proposal()], 1.1), [])
        self.assertEqual(validator.update([], 1.2), [])
        self.assertEqual(validator.update([proposal()], 1.3), [])
        self.assertEqual(len(validator.update([proposal()], 1.4)), 1)

    def test_requested_045_threshold_and_no_stale_replay_or_expired_confirmation(self):
        validator = DetectionValidator(.45)
        self.assertEqual(validator.update([proposal(score=.46)], 1.), [])
        self.assertEqual(validator.update([proposal(score=.46)], 1.), [])
        self.assertEqual(len(validator.update([proposal(score=.46)], 1.1)), 1)
        self.assertEqual(validator.update([proposal()], 2.), [])

    def test_selected_hand_only_and_missing_owner_cannot_promote_another_object(self):
        validator = DetectionValidator()
        owner = {'box': proposal()['box'], 'label': 'Right', 'age': .1}
        result = validator.update([proposal(), proposal(x=600.)], 1., owner)
        self.assertEqual(result, [proposal()])
        self.assertEqual(validator.update([proposal(x=600.)], 1.2, owner), [])
        self.assertEqual(validator.update([], 1.3, owner), [])
        self.assertEqual(validator.update([proposal()], 1.3, owner), [])

    def test_ambiguous_nearby_candidates_pause_and_release_requires_new_confirmation(self):
        validator = DetectionValidator()
        owner = {'box': proposal()['box'], 'label': 'Right', 'age': .1}
        self.assertEqual(validator.update([proposal(), proposal(x=12.)], 1., owner), [])
        self.assertTrue(validator.trace['ambiguous'])
        self.assertEqual(validator.update([proposal()], 1.1, owner), [proposal()])
        self.assertEqual(validator.update([proposal()], 1.2), [])
        self.assertEqual(len(validator.update([proposal()], 1.3)), 1)

    def test_invalid_geometry_does_not_become_a_valid_hand(self):
        points = hand(True, [1,0,0,0])
        self.assertTrue(valid_geometry({'pixels': points[:,:2]*1000, 'world': points}))
        self.assertFalse(valid_geometry({'pixels': np.zeros((21,2)), 'world': points}))
        self.assertFalse(valid_geometry({'pixels': points[:,:2]*1000, 'world': np.full((21,3), np.nan)}))
