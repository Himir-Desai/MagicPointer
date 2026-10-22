import unittest

from magicpointer.engine import Gesture
from test_ownership_fusion import pose
from test_two_camera_debug import dual_session


class OwnerTimeoutTests(unittest.TestCase):
    def test_absent_owner_releases_after_five_seconds_and_new_fist_can_select(self):
        def scene(frame, side):
            if 55 <= frame < 150:
                return []
            return [pose(Gesture.FIST if frame < 55 or frame < 205 else Gesture.POINT,
                         x=400.+side*80+(250. if frame >= 150 else 0.))]
        _, rows, _, _, _, audio, _ = dual_session('missing',scene=scene,frame_count=220)
        events = [(i,event) for i,row in enumerate(rows) for event in row['events']]
        released = [(i,event) for i,event in events if event['kind']=='deactivate']
        self.assertEqual(len(released),1)
        index,event = released[0]
        self.assertEqual(event['value'],'hand absence timeout')
        self.assertGreaterEqual(rows[index]['monotonic_seconds']-rows[55]['monotonic_seconds'],5.)
        self.assertLess(rows[index]['monotonic_seconds']-rows[55]['monotonic_seconds'],5.1)
        self.assertTrue(all(row['active'] for row in rows[55:index]))
        self.assertFalse(rows[index]['active'])
        self.assertIsNone(rows[index]['selection']['owner_ids'])
        self.assertEqual(sum(event['kind']=='activate' for _,event in events),2)
        self.assertTrue(rows[-1]['active'])
        self.assertNotEqual(rows[54]['selection']['owner_ids'], rows[-1]['selection']['owner_ids'])
        # Final False is the normal app-exit sound for the newly active owner.
        self.assertEqual([call.args[0] for call in audio.play.call_args_list],
                         [True,False,True,False])

    def test_return_in_either_view_cancels_timeout(self):
        def scene(frame, side):
            if frame < 55:
                return [pose(Gesture.FIST,x=400.+side*80)]
            if frame in (110,165,220) and side == 1:
                return [pose(Gesture.POINT,x=400.+side*80)]
            return []
        _, rows, _, _, _, _, _ = dual_session('missing',scene=scene,frame_count=250)
        self.assertFalse(any(event['kind']=='deactivate' for row in rows for event in row['events']))
        self.assertTrue(rows[-1]['active'])
        self.assertEqual(rows[54]['selection']['owner_ids'],rows[-1]['selection']['owner_ids'])
