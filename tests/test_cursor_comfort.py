import math
import unittest

from magicpointer.engine import Engine, Gesture, Observation
from magicpointer.motion import CursorSmoother


class CursorComfortTests(unittest.TestCase):
    def test_vibration_rejected_and_deliberate_motion_still_reaches_target(self):
        smoother = CursorSmoother()
        cursor = (.5, .5)
        values = []
        for i in range(180):
            target = (.5 + .001*math.sin(i*1.7), .5+.001*math.cos(i*1.7))
            cursor = smoother.update(target, cursor, 1/30)
            values.append(cursor)
        self.assertLess(max(p[0] for p in values)-min(p[0] for p in values), .0002)
        for _ in range(60):
            cursor = smoother.update((.8,.7), cursor, 1/30)
        self.assertLess(math.dist(cursor, (.8,.7)), .0031)

    def test_smoothing_is_similar_at_different_frame_rates(self):
        results = []
        for fps in (15,30,60):
            smoother = CursorSmoother()
            cursor = (.5,.5)
            for i in range(fps):
                cursor = smoother.update((.5+.1*(i+1)/fps,.5), cursor, 1/fps)
            results.append(cursor[0])
        self.assertLess(max(results)-min(results), .004)

    def test_fist_repositions_without_moving_or_recentering_cursor(self):
        engine = Engine(mirror_x=False)
        now = 0.
        def step(gesture, tip, wrist=(0.,0.,2.)):
            nonlocal now
            now += .03
            return engine.step(Observation(gesture, wrist, tip), now)
        for _ in range(20):
            step(Gesture.FIST,(0.,0.,2.))
        for _ in range(20):
            step(Gesture.POINT,(.08,-.03,2.))
        parked = engine.cursor
        for _ in range(30):
            self.assertEqual(step(Gesture.FIST,(.2,.3,2.),(.2,.3,2.)), [])
        events = step(Gesture.POINT,(.25,.2,2.),(.2,.3,2.))
        self.assertEqual(events[-1].value, parked)
        self.assertTrue(engine.active)
        for _ in range(20):
            events = step(Gesture.POINT,(.29,.2,2.))
        self.assertGreater(engine.cursor[0], parked[0]+.08)
        self.assertAlmostEqual(engine.cursor[1], parked[1])
        self.assertFalse(any(event.kind in ('activate','deactivate','click') for event in events))

    def test_rebase_discards_old_smoothing_target(self):
        engine = Engine(mirror_x=False)
        for i in range(20):
            engine.step(Observation(Gesture.FIST,(0.,0.,2.),(0.,0.,2.)),i*.03)
        engine.step(Observation(Gesture.POINT,(0.,0.,2.),(.1,0.,2.)), .6)
        parked = engine.cursor
        engine.rebase_motion()
        events = engine.step(Observation(Gesture.POINT,(0.,0.,2.),(-.1,.2,2.)),.63)
        self.assertEqual(events[-1].value,parked)


    def test_default_app_workspace_increases_gain_by_twenty_five_percent(self):
        from magicpointer.cli import parser
        args = parser().parse_args(['run'])
        self.assertAlmostEqual(.40/args.workspace_width,1.25)
        self.assertAlmostEqual(.25/args.workspace_height,1.25)
        custom = parser().parse_args(['run','--workspace-width','.4','--workspace-height','.25'])
        self.assertEqual((custom.workspace_width,custom.workspace_height),(.4,.25))

    def test_closing_thumb_rebases_reopening_at_the_parked_cursor(self):
        engine = Engine(mirror_x=False)
        for i in range(20):
            engine.step(Observation(Gesture.FIST,(0.,0.,2.),(0.,0.,2.)),i*.03)
        engine.step(Observation(Gesture.POINT,(0.,0.,2.),(.08,0.,2.)),.6)
        parked = engine.cursor
        for i in range(5):
            self.assertEqual(engine.step(Observation(Gesture.UNKNOWN,(0.,0.,2.),(.2,.2,2.),
                             pointer_pause=True),.63+i*.03),[])
        events = engine.step(Observation(Gesture.POINT,(0.,0.,2.),(.2,.2,2.),thumb_tap=True),.8)
        self.assertEqual(engine.cursor,parked)
        self.assertEqual([e.value for e in events if e.kind=='click'],['left'])
