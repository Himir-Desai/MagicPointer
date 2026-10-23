from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from magicpointer import app
from magicpointer.cameras import Frame
from magicpointer.cli import parser
from magicpointer.engine import Gesture
from magicpointer.tracking import Hand
from test_tracking import hand


def debug_session(poses=None, output=None, resources=None, argv=('run', '--debug', '--mute')):
    """Exercise actual render/engine/dispatch loop, with synthetic camera input."""
    args = parser().parse_args(list(argv))
    poses = poses or [Gesture.FIST]*55 + [Gesture.POINT]*5 + [Gesture.LEFT]*8 + [Gesture.POINT]*5 + [Gesture.PALM]*8
    pixels = np.array([(900.+(i%4)*25, 650.-(i//4)*30) for i in range(21)])
    camera = MagicMock()
    camera.__enter__.return_value = camera
    camera.info = [{'index': 0, 'width': 1920, 'height': 1080, 'reported_fps': 30}]
    frame = np.full((1080, 1920, 3), (45, 40, 35), dtype=np.uint8)
    tracker = MagicMock()
    index = [0]
    now = [1.]
    displays = []
    audio = MagicMock()

    def tick():
        now[0] += .03
        return now[0]

    def read():
        return [Frame(frame, now[0])]

    def detect(*_):
        pose = poses[min(index[0], len(poses)-1)]
        if pose is None:
            return None
        if isinstance(pose, Hand):
            pose.pixels = pixels.copy()
            return pose
        thumb, fingers = {
            Gesture.FIST: (False, [0, 0, 0, 0]), Gesture.POINT: (False, [1, 0, 0, 0]),
            Gesture.LEFT: (True, [1, 0, 0, 0]), Gesture.RIGHT: (False, [1, 0, 0, 1]),
            Gesture.SCROLL: (False, [1, 1, 0, 0]), Gesture.PALM: (True, [1, 1, 1, 1]),
        }[pose]
        return Hand(pixels.copy(), hand(thumb, fingers), 'Right', pose)

    def key(_):
        index[0] += 1
        return ord('q') if index[0] >= len(poses) else -1

    if resources is not None:
        resources.update(tracker=tracker, camera=camera, audio=audio)
    camera.read.side_effect = read
    tracker.detect_all.side_effect = lambda *_: ([result] if (result := detect()) is not None else [])
    with tempfile.TemporaryDirectory() as directory, \
            patch.object(app, 'Cameras', return_value=camera), patch.object(app, 'Tracker', return_value=tracker), \
            patch.object(app, 'Chimes', return_value=audio), patch.object(app.time, 'monotonic', side_effect=tick), \
            patch.object(app.cv2, 'imshow', side_effect=lambda _, panel: displays.append(panel.copy())), \
            patch.object(app.cv2, 'waitKey', side_effect=key), patch.object(app.cv2, 'getWindowProperty', return_value=1), \
            patch.object(app.cv2, 'destroyAllWindows'), patch('magicpointer.desktop.Desktop') as desktop:
        native = desktop.return_value
        native.pixel.side_effect = lambda point: (round(point[0] * 1919), round(point[1] * 1079))
        native.wheel_step = 1 / 120
        if resources is not None:
            resources['desktop'] = desktop
        args.output = Path(output or directory)
        result = app.run(args)
        if args.debug:
            desktop.assert_not_called()
    return result, displays, tracker, camera, audio


class AppTests(unittest.TestCase):
    def test_uncalibrated_one_camera_session_moves_and_clicks_real_pointer(self):
        resources = {}
        poses = [Gesture.FIST]*95 + [Gesture.POINT]*10 + [Gesture.LEFT]*10 + [Gesture.POINT]*5 + [Gesture.PALM]*8
        with patch('builtins.print'):
            result, displays, _, _, audio = debug_session(poses, resources=resources,
                                                         argv=('run', '--uncalibrated', '--mute'))
        self.assertEqual(result, 0)
        native = resources['desktop'].return_value
        self.assertTrue(native.move.called)
        self.assertEqual([call.args for call in native.click.call_args_list], [('left',)])
        self.assertEqual([c.args for c in audio.play.call_args_list][:1], [(True,)])
        self.assertEqual(displays[0].shape, (540, 960, 3))

    def test_debug_session_renders_states_and_never_constructs_desktop(self):
        result, displays, tracker, camera, audio = debug_session()
        self.assertEqual(result, 0)
        self.assertEqual(displays[0].shape, (900, 1280, 3))
        self.assertGreater(len(displays), 30)
        self.assertIn(((True,), {}), [(c.args, c.kwargs) for c in audio.play.call_args_list])
        self.assertIn(((False,), {}), [(c.args, c.kwargs) for c in audio.play.call_args_list])
        tracker.close.assert_called_once()
        camera.__exit__.assert_called_once()
        audio.close.assert_called_once()

    def test_owner_that_stays_away_is_released_and_a_new_fist_selects_again(self):
        poses = [Gesture.FIST]*70 + [None]*40 + [Gesture.FIST]*70
        chimes = {}
        for timeout in ('0.5', '0'):
            with patch('builtins.print'):
                result, *_, audio = debug_session(poses, argv=('run', '--debug', '--mute', '--owner-timeout', timeout))
            self.assertEqual(result, 0)
            chimes[timeout] = [call.args for call in audio.play.call_args_list]
        # Timeout: release chime, then a fresh fist hold selects and activates again; exit chime last.
        self.assertEqual(chimes['0.5'], [(True,), (False,), (True,), (False,)])
        # No timeout: the returning hand resumes silently as the same owner.
        self.assertEqual(chimes['0'], [(True,), (False,)])

    def test_capture_failure_cleans_up_tracker_audio_and_camera(self):
        args = parser().parse_args(['run', '--debug'])
        camera, tracker, audio = MagicMock(), MagicMock(), MagicMock()
        camera.__enter__.return_value = camera
        camera.info = [{'index': 0}]
        camera.read.side_effect = ValueError('Camera disconnected')
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(app, 'Cameras', return_value=camera), patch.object(app, 'Tracker', return_value=tracker), \
                patch.object(app, 'Chimes', return_value=audio), patch.object(app.cv2, 'destroyAllWindows'):
            args.output = Path(directory)
            with self.assertRaisesRegex(ValueError, 'disconnected'):
                app.run(args)
        tracker.close.assert_called_once()
        audio.close.assert_called_once()
        camera.__exit__.assert_called_once()
