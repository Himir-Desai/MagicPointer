import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import numpy as np

from magicpointer import app
from magicpointer.cameras import Frame
from magicpointer.cli import parser
from magicpointer.debug_log import DebugLog
from magicpointer.engine import Engine, Gesture
from test_app import debug_session
from test_wrist_tilt import camera_pose


def read_archive(directory):
    path = next(Path(directory).glob('debug-*.zip'))
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {'session.json', 'samples.jsonl', 'summary.json'}
        return (json.loads(archive.read('session.json')),
                [json.loads(line) for line in archive.read('samples.jsonl').splitlines()],
                json.loads(archive.read('summary.json')))


class DebugRecordingTests(unittest.TestCase):
    def test_main_debug_automatically_records_entire_session_including_no_hand(self):
        poses = [None]*3+[Gesture.FIST]*55+[Gesture.POINT]*6+[camera_pose()]*20+[camera_pose(30., thumb=True)]*25
        with tempfile.TemporaryDirectory() as directory:
            result, _, _, _, _ = debug_session(poses, directory)
            metadata, rows, summary = read_archive(directory)
        self.assertEqual(result, 0)
        self.assertEqual(len(rows), len(poses))
        self.assertEqual(summary['frames'], len(poses))
        self.assertEqual(metadata['kind'], 'debug-run')
        self.assertEqual(metadata['termination'], 'normal')
        self.assertFalse(metadata['desktop_input'])
        self.assertFalse(metadata['images_recorded'])
        self.assertIsNone(rows[0]['cameras'][0]['hand'])
        self.assertIsNone(rows[0]['observation'])
        self.assertEqual(metadata['cameras'][0]['width'], 1920)
        self.assertTrue(all(b['elapsed_seconds'] > a['elapsed_seconds'] for a, b in zip(rows, rows[1:])))
        scrolling = [row for row in rows if row['scrolling']]
        self.assertTrue(scrolling)
        self.assertTrue(any(row['scroll']['neutral_degrees'] is not None for row in scrolling))
        self.assertTrue(any(row['scroll']['down_steps_per_second'] > 0 for row in scrolling))
        self.assertTrue(any(row['cameras'][0]['hand']['metrics']['thumb']['state'] == 1 for row in scrolling))
        self.assertTrue(any(event['kind'] == 'scroll' for row in scrolling for event in row['events']))
        self.assertFalse(any(event['kind'] == 'click' for row in scrolling for event in row['events']))

    def test_advanced_recording_preserves_matching_costs_engine_state_and_phase_timings(self):
        with tempfile.TemporaryDirectory() as directory:
            debug_session(output=directory)
            metadata, rows, summary = read_archive(directory)
            self.assertEqual(metadata['schema_version'], 2)
            self.assertEqual(metadata['diagnostics_version'], 2)
            self.assertIn('model_sha256', metadata)
            self.assertIn('dependencies', metadata)
            self.assertTrue(all('engine_before' in row and 'engine_after' in row for row in rows))
            self.assertTrue(all('detect_camera_0_ms' in row['timings_ms'] for row in rows))
            self.assertTrue(any(row['tracking_decisions'][0]['costs'] for row in rows))
            self.assertTrue(any(row['matching_decisions']['pairs'] for row in rows))
            self.assertTrue(any(pair.get('finger_disagreement') for row in rows for pair in row['matching_decisions']['pairs']))
            self.assertIn('frame_interval_ms', summary['timings_ms'])
            self.assertIn('rejection_and_status_counts', summary)

    def test_debug_analysis_accepts_new_schema_without_camera_or_os_input(self):
        from scripts.analyze_debug import analyze
        with tempfile.TemporaryDirectory() as directory:
            debug_session(output=directory)
            report = analyze(next(Path(directory).glob('debug-*.zip')))
            self.assertGreater(report['frames'], 0)
            self.assertIn('retain_owner_and_pause', report['owned_control_replay']['policies'])

    def test_data_is_flushed_and_both_camera_results_and_rejections_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DebugLog(directory, {'stereo': True})
            hand = camera_pose()
            hand.pixels[0, 0] = float('nan')
            frame = Frame(np.zeros((20, 30, 3), np.uint8), 1.)
            engine = Engine()
            log.append([frame, frame], [hand, None], None, engine, [], log.started+.01,
                       reason='Hands/gestures disagree between cameras', paired=False, verified=False, state='unavailable')
            # Read before close: an interrupted process still leaves JSONL data.
            row = json.loads((log.path/'samples.jsonl').read_text())
            self.assertEqual(len(row['cameras']), 2)
            self.assertIsNone(row['cameras'][1]['hand'])
            self.assertIsNone(row['cameras'][0]['hand']['pixels'][0][0])
            self.assertFalse(row['pair_timing_valid'])
            self.assertIn('disagree', row['reason'])
            log.close()
            log.close()
            read_archive(directory)

    def test_interrupt_and_capture_error_save_partial_archive_and_clean_up(self):
        for error in (KeyboardInterrupt(), ValueError('Camera disconnected')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                args = parser().parse_args(['run', '--hand-backend', 'mediapipe', '--debug', '--output', directory])
                camera, tracker, audio = MagicMock(), MagicMock(), MagicMock()
                camera.__enter__.return_value = camera
                camera.info = [{'index': 0}]
                camera.read.side_effect = error
                with patch.object(app, 'Cameras', return_value=camera), patch.object(app, 'Tracker', return_value=tracker), \
                        patch.object(app, 'Chimes', return_value=audio), patch.object(app.cv2, 'destroyAllWindows'):
                    with self.assertRaises(type(error)):
                        app.run(args)
                metadata, rows, _ = read_archive(directory)
                self.assertEqual(metadata['termination'], type(error).__name__)
                self.assertEqual(rows, [])
                tracker.close.assert_called_once()
                audio.close.assert_called_once()
                camera.__exit__.assert_called_once()

    def test_model_startup_error_still_saves_session_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(['run', '--hand-backend', 'mediapipe', '--debug', '--output', directory])
            with patch.object(app, 'Tracker', side_effect=ValueError('missing model')), patch.object(app.cv2, 'destroyAllWindows'):
                with self.assertRaisesRegex(ValueError, 'missing model'):
                    app.run(args)
            metadata, rows, _ = read_archive(directory)
            self.assertEqual(metadata['termination'], 'ValueError')
            self.assertEqual(metadata['error'], 'missing model')
            self.assertEqual(rows, [])

    def test_recording_close_failure_still_releases_camera_and_tracker(self):
        def fail_close(log):
            log.stream.close()
            raise OSError('disk full')
        resources = {}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(DebugLog, 'close', fail_close):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    debug_session([None], directory, resources)
        resources['tracker'].close.assert_called_once()
        resources['audio'].close.assert_called_once()
        resources['camera'].__exit__.assert_called_once()

    def test_non_debug_control_does_not_construct_recorder(self):
        args = parser().parse_args(['run', '--hand-backend', 'mediapipe', '--right', '1'])
        with patch.object(app.Stereo, 'load') as load, patch.object(app, 'DebugLog') as recorder, \
                patch.object(app, 'Tracker', side_effect=ValueError('stop before opening cameras')), \
                patch.object(app.cv2, 'destroyAllWindows'):
            load.return_value.data = {'camera_indices': [0, 1]}
            with self.assertRaisesRegex(ValueError, 'stop before opening cameras'):
                app.run(args)
            recorder.assert_not_called()
