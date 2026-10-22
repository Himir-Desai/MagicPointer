from contextlib import nullcontext, redirect_stderr
import io
import sys
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from magicpointer import app
from magicpointer.cli import parser
from magicpointer.engine import Gesture
from magicpointer.wilor_batch import BatchedWiLoR
from magicpointer.wilor_gestures import PROFILE
from magicpointer.cameras import Frame
from magicpointer.worker_client import WiLoRWorker
from test_ownership_fusion import pose
from test_tracking import hand
from test_two_camera_debug import dual_session


class Tensor:
    def __init__(self, value):
        self.value = np.asarray(value)
    def detach(self): return self
    def cpu(self): return self
    def float(self): return self
    def numpy(self): return self.value
    def to(self, **_): return self


class BatchedPipelineTests(unittest.TestCase):
    def test_confirmed_camera_crops_share_one_pose_forward_and_owner_limits_cost(self):
        model = BatchedWiLoR.__new__(BatchedWiLoR)
        model.device, model.dtype, model.precision = 'cpu', 'float32', 'fp32'
        model.limit, model.confidence, model.validators = 4, .50, {}
        model.torch = SimpleNamespace(inference_mode=nullcontext, from_numpy=Tensor)
        box_data = np.array([[10.,10.,110.,130.,.8,1.], [400.,10.,500.,130.,.7,0.]])
        detector = MagicMock(side_effect=lambda images, **_: [SimpleNamespace(boxes=SimpleNamespace(data=Tensor(box_data))) for image in images])
        batches = []
        def forward(batch):
            batches.append(batch.value.copy())
            count = len(batch.value)
            return {'pred_cam': Tensor(np.tile([1.,0.,0.], (count,1))),
                    'pred_keypoints_3d': Tensor(np.tile(hand(True,[1,0,0,0]), (count,1,1)))}
        model.pipeline = SimpleNamespace(hand_detector=detector, wilor_model=forward, FOCAL_LENGTH=5000.)
        helpers = SimpleNamespace(
            generate_image_patch_cv2=lambda image, *_, **__: (np.full((256,256,3), image[0,0,0], np.uint8), None),
            cam_crop_to_full=lambda *args: np.zeros((1,3)),
            perspective_projection=lambda points, *_: points[:,:,:2]*1000+300)
        modules = {'wilor_mini': SimpleNamespace(), 'wilor_mini.utils': SimpleNamespace(utils=helpers),
                   'skimage': SimpleNamespace(), 'skimage.filters': SimpleNamespace(gaussian=lambda value, **_: value)}
        images = [np.full((480,640,3), color, np.uint8) for color in (10,70)]
        with patch.dict(sys.modules, modules):
            first = model.detect_batch(images, [1.,1.005], [None,None])
            self.assertEqual(first['pose_batch_size'], 0)
            second = model.detect_batch(images, [1.2,1.205], [None,None])
            self.assertEqual(second['pose_batch_size'], 4)
            self.assertEqual(len(batches), 1)
            np.testing.assert_array_equal(batches[0][:,0,0,0], [10,10,70,70])
            self.assertEqual([len(view) for view in second['views']], [2,2])
            self.assertEqual(second['views'][0][1]['label'], 'Left')
            self.assertGreater(second['views'][0][1]['world'][4][0], 0.)
            owners = [{'box': box_data[0,:4].tolist(), 'label': 'Right', 'age': .2}]*2
            third = model.detect_batch(images, [1.4,1.405], owners)
            self.assertEqual(third['pose_batch_size'], 2)
            self.assertEqual(len(batches), 2)
            self.assertEqual([len(view) for view in third['views']], [1,1])
        self.assertEqual(detector.call_args.kwargs['conf'], .50)
        self.assertFalse(detector.call_args.kwargs['half'])


class FakeDebug:
    info = {'device': 'cuda', 'precision': 'fp16', 'implementation': 'synthetic test'}
    timings = {'detector_batch_ms': 1., 'pose_batch_ms': 2.}
    diagnostics = {'views': [{'accepted': 1}, {'accepted': 1}], 'pose_batch_size': 2}
    def __init__(self):
        self.index = 0
        self.closed = False
    def detect(self, frames, owner, now):
        index = self.index
        self.index += 1
        if index < 2:
            return [[], []]
        gesture = (Gesture.FIST if index < 56 else Gesture.POINT if index < 65 or 73 <= index < 81
                   else Gesture.LEFT if index < 73 else Gesture.RIGHT if index < 91 else Gesture.PALM)
        results = []
        for side in range(2):
            value = pose(gesture, x=400.+side*80)
            if gesture == Gesture.POINT:
                value.world[2:5] = [[-.04,-.03,0],[-.02,-.05,0],[0.,-.07,0]]
            value.profile = PROFILE
            value.detection_score = .75
            value.model_box = [300.+side*80,300.,500.+side*80,650.]
            results.append([] if side == 1 and 58 <= index < 62 else [value])
        return results
    def close(self):
        self.closed = True


class WiLoRAppTests(unittest.TestCase):
    def test_regular_debug_simulates_selection_point_clicks_release_and_missing_view(self):
        fake = FakeDebug()
        with patch('magicpointer.wilor_debug.WiLoRDebug', return_value=fake) as factory:
            metadata, rows, panels, trackers, _, _, _ = dual_session('missing', frame_count=102,
                capture_args=('--hand-backend','wilor','--wilor-confidence','0.45'))
        self.assertEqual(metadata['hand_backend'], 'wilor')
        self.assertEqual(metadata['classifier_profile'], PROFILE)
        self.assertIsNone(metadata['model_sha256'])
        self.assertTrue(fake.closed)
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args[0].wilor_confidence, .45)
        for tracker in trackers:
            tracker.detect_all.assert_not_called()
        events = [event for row in rows for event in row['events']]
        self.assertEqual(sum(event['kind']=='activate' for event in events), 1)
        self.assertEqual([event['value'] for event in events if event['kind']=='click'], ['left','right'])
        self.assertEqual(sum(event['kind']=='deactivate' for event in events), 1)
        self.assertTrue(all(row['observation']['gesture'] == Gesture.POINT.value for row in rows[58:62]))
        self.assertEqual(panels[-1].shape, (900,1280,3))
        self.assertTrue(all(row['detector_diagnostics']['pose_batch_size'] == 2 for row in rows))
        self.assertTrue(all('pose_batch_ms' in row['timings_ms'] for row in rows))

    def test_capture_error_finalizes_partial_data_and_closes_worker(self):
        fake = FakeDebug()
        with patch('magicpointer.wilor_debug.WiLoRDebug', return_value=fake):
            metadata, rows, _, _, _, _, _ = dual_session('missing', capture_error=True,
                                                      capture_args=('--hand-backend','wilor'))
        self.assertEqual(metadata['termination'], 'ValueError')
        self.assertEqual(len(rows), 2)
        self.assertTrue(fake.closed)

    def test_desktop_wilor_rejected_before_models_capture_or_input(self):
        args = parser().parse_args(['run','--right','1','--hand-backend','wilor'])
        with patch('magicpointer.wilor_debug.WiLoRDebug') as model, patch.object(app,'Cameras') as cameras, \
                patch('magicpointer.desktop.Desktop') as desktop:
            with self.assertRaisesRegex(ValueError, 'debug-only'):
                app.run(args)
            model.assert_not_called()
            cameras.assert_not_called()
            desktop.assert_not_called()

    def test_invalid_confidence_rejected_and_cpu_precision_is_explicit(self):
        for value in ('0','1.1','nan','inf'):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser().parse_args(['run','--wilor-confidence',value])
        args = parser().parse_args(['run','--debug','--hand-backend','wilor','--wilor-device','cpu','--wilor-precision','fp32'])
        self.assertEqual(args.wilor_precision, 'fp32')


class BatchedWorkerTests(unittest.TestCase):
    def test_two_raw_frames_and_owner_contexts_round_trip_in_one_request(self):
        source = '''import json,sys
print('MAGICPOINTER_JSON '+json.dumps({'info': {'device':'cpu','precision':'fp32'}}),flush=True)
while True:
 header=sys.stdin.buffer.readline()
 if not header: break
 request=json.loads(header)
 sums=[]
 for frame in request['frames']:
  size=1
  for dimension in frame['shape']: size*=dimension
  data=sys.stdin.buffer.read(size)
  sums.append(sum(data))
 print('MAGICPOINTER_JSON '+json.dumps({'sums':sums,'owners':request['owners']}),flush=True)
'''
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'batch_worker.py'
            script.write_text(source)
            original = subprocess.Popen
            args = parser().parse_args(['run','--debug','--hand-backend','wilor'])
            args.wilor_python = Path(sys.executable)
            commands = []
            def start(command, **kwargs):
                commands.append(command)
                return original([sys.executable,'-u',str(script)], **kwargs)
            with patch('magicpointer.worker_client.subprocess.Popen', side_effect=start):
                worker = WiLoRWorker(args, 2, optimized=True)
                try:
                    frames = [Frame(np.full((3,4,3), value, np.uint8), 1.+index*.005)
                              for index,value in enumerate((7,11))]
                    owners = [None, {'box':[1,2,3,4], 'label':'Right', 'age':.1}]
                    result = worker.detect_batch(frames, owners)
                    self.assertEqual(result['sums'], [252,396])
                    self.assertEqual(result['owners'], owners)
                    self.assertIn('--optimized', commands[0])
                    self.assertEqual(commands[0][commands[0].index('--confidence')+1], '0.5')
                finally:
                    worker.close()
                self.assertEqual(worker.process.poll(), 0)
