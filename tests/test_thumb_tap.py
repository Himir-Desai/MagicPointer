from unittest.mock import patch
import unittest

import numpy as np

from magicpointer import app
from magicpointer.cli import parser
from magicpointer.engine import Engine, Gesture, Observation
from magicpointer.thumb_tap import ThumbTapFilter
from magicpointer.tracking import Hand
from magicpointer.wilor_gestures import PROFILE
from test_tracking import hand
from test_wilor_debug import FakeDebug
from test_two_camera_debug import dual_session


def tap_hand(gap, *, transform=None, fingers=(1,0,0,0), views=(0,1)):
    world = hand(False, fingers)
    width = np.linalg.norm(world[5]-world[17])
    world[4] = [0.,-.09,.03+gap*width]
    if transform:
        rotation, scale, offset = transform
        world = world @ rotation * scale + offset
    return Hand(world[:,:2]*1000,world,'Right',Gesture.UNKNOWN,profile=PROFILE,
                diagnostics={'fusion_views': list(views)})


class ThumbTapTests(unittest.TestCase):
    def sequence(self, gaps, *, transform=None):
        filt = ThumbTapFilter()
        results = [filt.update((1,2),tap_hand(gap,transform=transform),1.+i*.1)
                   for i,gap in enumerate(gaps)]
        return results

    def test_complete_tap_emits_once_and_extension_alone_never_clicks(self):
        results = self.sequence([.35]*4+[.05]*3+[.35]*5)
        self.assertEqual(sum(r.diagnostics['thumb_tap']['click'] for r in results),1)
        self.assertTrue(all(r.gesture == Gesture.POINT for r in results))
        results = self.sequence([.35]*15)
        self.assertFalse(any(r.diagnostics['thumb_tap']['click'] for r in results))

    def test_resting_thumb_hold_or_one_frame_spike_never_clicks(self):
        for gaps in ([.05]*15,[.35]*3+[.05]*12+[.35]*3,
                     [.35]*3+[.05]+[.35]*5):
            self.assertFalse(any(r.diagnostics['thumb_tap']['click'] for r in self.sequence(gaps)))

    def test_loss_identity_source_change_and_stale_frames_cancel_tap(self):
        for interruption in ('missing','identity','views','stale','gap'):
            filt = ThumbTapFilter()
            for i,gap in enumerate([.35]*3+[.05]*3):
                filt.update((1,2),tap_hand(gap),1.+i*.1)
            if interruption == 'missing':
                filt.update((1,2),None,1.55)
            elif interruption == 'stale':
                filt.update((1,2),tap_hand(.35),1.5)
            key = (3,4) if interruption == 'identity' else (1,2)
            views = (0,) if interruption == 'views' else (0,1)
            start = 2.5 if interruption == 'gap' else 1.6
            for i in range(4):
                result = filt.update(key,tap_hand(.35,views=views),start+i*.1)
                self.assertFalse(result.diagnostics['thumb_tap']['click'],interruption)

    def test_rotated_scaled_reflected_geometry_preserves_tap(self):
        rng = np.random.default_rng(18)
        for _ in range(10):
            rotation,_ = np.linalg.qr(rng.normal(size=(3,3)))
            rotation[:,0] *= rng.choice([-1,1])
            transform = rotation,rng.uniform(.4,3.),rng.normal(size=3)
            results = self.sequence([.35]*3+[.05]*3+[.35]*3,transform=transform)
            self.assertEqual(sum(r.diagnostics['thumb_tap']['click'] for r in results),1)

    def test_right_click_and_palm_keep_existing_thumb_filter(self):
        from magicpointer.wilor_gestures import ThumbFilter
        for fingers, expected in (([1,1,0,0],Gesture.RIGHT),([1,1,1,1],Gesture.PALM)):
            tap, reference = ThumbTapFilter(),ThumbFilter()
            for i in range(4):
                world = hand(True,fingers)
                a = Hand(world[:,:2],world,'Right',Gesture.UNKNOWN,profile=PROFILE)
                b = Hand(world[:,:2],world,'Right',Gesture.UNKNOWN,profile=PROFILE)
                self.assertEqual(tap.update((1,),a,1.+i*.1).gesture,
                                 reference.update((1,),b,1.+i*.1).gesture)
            self.assertEqual(a.gesture,expected)

    def test_invalid_geometry_or_time_cannot_click(self):
        for invalid_time in (float('nan'),float('inf')):
            result = ThumbTapFilter().update((1,),tap_hand(.05),invalid_time)
            self.assertEqual(result.gesture,Gesture.UNKNOWN)
            self.assertFalse(result.diagnostics['thumb_tap']['click'])
        value = tap_hand(.05)
        value.world[:] = 0.
        value.diagnostics = None
        result = ThumbTapFilter().update((1,),value,1.)
        self.assertFalse(result.diagnostics['thumb_tap']['click'])
        self.assertFalse(result.diagnostics['thumb_tap']['eligible'])

    def test_tap_cannot_click_before_activation_or_while_scrolling(self):
        engine = Engine()
        point = Observation(Gesture.POINT,(0.,0.,2.),(0.,0.,2.),thumb_tap=True)
        self.assertEqual(engine.step(point,1.),[])
        engine.active = True
        engine.origin = (0.,0.,2.)
        engine.scrolling = True
        self.assertFalse(any(e.kind=='click' for e in engine.step(point,1.03)))


class TappingDebug(FakeDebug):
    def detect(self, frames, owner, now):
        results = super().detect(frames,owner,now)
        index = self.index-1
        if 56 <= index < 81:
            gap = .05 if 65 <= index < 70 else .35
            for side, view in enumerate(results):
                if view:
                    view[0].world = tap_hand(gap).world
        return results


class ThumbTapAppTests(unittest.TestCase):
    def test_real_desktop_dispatches_tap_left_and_unchanged_right(self):
        fake = TappingDebug()
        with patch('magicpointer.wilor_debug.WiLoRDebug',return_value=fake):
            data, _, _, _, _, audio, _ = dual_session(frame_count=102,
                force_uncalibrated=True,desktop_control=True,
                capture_args=('--hand-backend','wilor','--left-click','thumb-tap'))
        clicks = [call.args[0] for call in data['desktop_commands'] if call[0]=='click']
        self.assertEqual(clicks,['left','right'])
        self.assertEqual([call.args[0] for call in audio.play.call_args_list
                          if call.args[0] in ('left','right')],clicks)
        self.assertTrue(fake.closed)

    def test_debug_records_tap_geometry_without_desktop_input(self):
        with patch('magicpointer.wilor_debug.WiLoRDebug',return_value=TappingDebug()):
            metadata, rows, _, _, _, _, _ = dual_session(frame_count=102,
                force_uncalibrated=True,
                capture_args=('--hand-backend','wilor','--left-click','thumb-tap'))
        self.assertEqual(metadata['left_click_method'],'thumb-tap')
        clicks = [event for row in rows for event in row['events'] if event['kind']=='click']
        self.assertEqual([event['value'] for event in clicks],['left','right'])
        taps = [row['selection']['combined_hand']['model_diagnostics']['thumb_tap'] for row in rows
                if row['selection']['combined_hand'] is not None]
        self.assertTrue(any(tap['click'] for tap in taps))
        self.assertTrue(any(tap['distance_palm_widths'] is not None for tap in taps))

    def test_wrong_backend_rejected_before_model_camera_and_input(self):
        args = parser().parse_args(['run','--hand-backend','mediapipe','--left-click','thumb-tap'])
        with patch.object(app,'Tracker') as tracker,patch.object(app,'Cameras') as cameras:
            with self.assertRaisesRegex(ValueError,'requires'):
                app.run(args)
            tracker.assert_not_called()
            cameras.assert_not_called()
