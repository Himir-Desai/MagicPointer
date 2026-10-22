"""Optional model adapters. Outputs stay in original-image pixels and native 3D."""
from pathlib import Path
import hashlib
from importlib.metadata import distribution, version
import json
import platform

import numpy as np


RTM_MODELS = {
    'detector': 'https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmdet_nano_8xb32-300e_hand-267f9c8f.zip',
    'pose': 'https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-m_simcc-hand5_pt-aic-coco_210e-256x256-74fb594_20230320.zip',
}
RTM_SHA256 = ('568d3ea97a5b142488366b67e036b6a5cb0a1fef9087a710cb8e66b6979fbac2',
              '39e858936bca0f94c09847d4e70b68a51d6c0adac61f36b457fcadb54621cd29')


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def prediction(pixels, *, world=None, scores=None, label=None, box=None, detection_score=None):
    points = np.asarray(pixels, dtype=float)
    if points.shape != (21, 2) or not np.isfinite(points).all():
        raise ValueError('Model returned invalid 21-point image coordinates')
    if world is not None:
        world = np.asarray(world, dtype=float)
        if world.shape != (21, 3) or not np.isfinite(world).all():
            raise ValueError('Model returned invalid 3D hand coordinates')
    return {'pixels': points.tolist(), 'world': None if world is None else world.tolist(),
            'joint_scores': None if scores is None else np.asarray(scores).tolist(),
            'label': label, 'box': box, 'detection_score': detection_score}


class MediaPipeModel:
    def __init__(self, args, views):
        from .tracking import Tracker
        self.trackers = []
        try:
            for _ in range(views):
                self.trackers.append(Tracker(args.model, num_hands=args.max_hands))
        except BaseException:
            self.close()
            raise
        self.info = {'implementation': 'MediaPipe HandLandmarker VIDEO / CPU',
                     'model_sha256': fingerprint(args.model), 'thresholds': [.65, .65, .65]}

    def detect(self, image, timestamp, view):
        return [prediction(hand.pixels, world=hand.world, label=hand.label)
                for hand in self.trackers[view].detect_all(image, timestamp)]

    def close(self):
        for tracker in self.trackers:
            tracker.close()
        self.trackers = []


class RTMPoseModel:
    def __init__(self, args, views):
        try:
            from rtmlib import RTMDet, RTMPose
            import onnxruntime
        except ImportError as error:
            raise ValueError('RTMPose dependencies missing; see docs/model-comparison.md') from error
        directory = Path(args.model_dir)
        paths = [directory / f'{name}.onnx' for name in ('detector', 'pose')]
        if not all(path.is_file() for path in paths):
            raise ValueError('RTMPose weights missing. Run compare-models --prepare --models rtmpose')
        hashes = [fingerprint(path) for path in paths]
        if tuple(hashes) != RTM_SHA256:
            raise ValueError('RTMPose model checksum mismatch; run compare-models --prepare --models rtmpose')
        self.detector = RTMDet(str(paths[0]), model_input_size=(320, 320),
                               backend='onnxruntime', device='cpu')
        self.pose = RTMPose(str(paths[1]), model_input_size=(256, 256),
                           backend='onnxruntime', device='cpu', to_openpose=False)
        self.limit = args.max_hands
        self.info = {'implementation': 'rtmlib RTMDet-nano + RTMPose-m Hand5 / ONNX CPU',
                     'rtmlib': version('rtmlib'),
                     'onnxruntime': onnxruntime.__version__,
                     'model_sha256': hashes,
                     'detection_threshold': .3, 'joint_display_threshold': .3,
                     'world_coordinates_available': False}

    def detect(self, image, timestamp, view):
        boxes = self.detector(image)
        # RTMPose treats an empty bbox list as a request to estimate a hand
        # across the whole image. A negative detector result must stay negative.
        if len(boxes) == 0:
            return []
        boxes = boxes[:self.limit]
        points, scores = self.pose(image, bboxes=boxes)
        return [prediction(p, scores=s, box=np.asarray(box).tolist())
                for p, s, box in zip(points, scores, boxes)]

    def close(self):
        self.detector = self.pose = None


def wilor_predictions(outputs, limit):
    result = []
    for output in outputs[:limit]:
        values = output['wilor_preds']
        result.append(prediction(values['pred_keypoints_2d'][0],
                                 world=values['pred_keypoints_3d'][0],
                                 label='Right' if output['is_right'] else 'Left',
                                 box=np.asarray(output['hand_bbox']).tolist()))
    return result


class WiLoRModel:
    """Runs only inside the separate optional PyTorch environment."""
    def __init__(self, directory, device, limit, precision='fp32'):
        # Legacy MANO pickles reference chumpy, whose published release uses
        # aliases removed by NumPy 1.24 and Python 3.11. Confine compatibility
        # names to this isolated worker; the main app's modules stay untouched.
        import inspect
        for name, value in {'bool': bool, 'int': int, 'float': float, 'complex': complex,
                            'object': object, 'str': str, 'unicode': str}.items():
            if name not in np.__dict__:
                setattr(np, name, value)
        if not hasattr(inspect, 'getargspec'):
            inspect.getargspec = inspect.getfullargspec
        import torch
        from wilor_mini.pipelines.wilor_hand_pose3d_estimation_pipeline import WiLorHandPose3dEstimationPipeline
        if device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('WiLoR requested CUDA but PyTorch cannot use it. Install the CUDA build in .venv-wilor.')
        if precision == 'fp16' and device != 'cuda':
            raise ValueError('WiLoR FP16 requires CUDA; use auto or fp32 for CPU checks')
        self.precision = 'fp16' if precision == 'fp16' or (precision == 'auto' and device == 'cuda') else 'fp32'
        self.dtype = torch.float16 if self.precision == 'fp16' else torch.float32
        self.torch, self.device, self.limit = torch, device, limit
        # Follow upstream's BGR tests and model.forward's internal BGR->RGB;
        # converting to RGB here would reverse colors twice.
        self.pipeline = WiLorHandPose3dEstimationPipeline(
            device=torch.device(device), dtype=self.dtype, verbose=False,
            wilor_pretrained_dir=str(Path(directory).resolve()))
        self.pipeline.hand_detector.overrides['max_det'] = limit
        source = distribution('wilor-mini').read_text('direct_url.json')
        revision = json.loads(source).get('vcs_info', {}).get('commit_id') if source else None
        self.info = {'implementation': 'WiLoR-mini', 'device': device, 'precision': self.precision,
                     'wilor_mini': version('wilor-mini'), 'source_revision': revision,
                     'python': platform.python_version(),
                     'torch': torch.__version__, 'detection_threshold': .3,
                     'model_sha256': {path.name: fingerprint(path)
                        for path in (Path(directory) / 'pretrained_models').glob('*') if path.is_file()},
                     'gpu': torch.cuda.get_device_name(0) if device == 'cuda' else None}

    def detect(self, image, timestamp, view):
        with self.torch.inference_mode():
            outputs = self.pipeline.predict(image, hand_conf=.3)
        if self.device == 'cuda':
            self.torch.cuda.synchronize()
        return wilor_predictions(outputs, self.limit)

    def close(self):
        self.pipeline = None
        if self.device == 'cuda':
            self.torch.cuda.empty_cache()
