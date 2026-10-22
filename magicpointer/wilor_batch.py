"""WiLoR debug path: validate boxes, then one pose batch across fresh views."""
import time
import numpy as np

from .comparison_models import WiLoRModel, prediction
from .wilor_validation import DetectionValidator, valid_geometry


class BatchedWiLoR(WiLoRModel):
    def __init__(self, directory, device, limit, confidence=.50, precision='auto'):
        super().__init__(directory, device, limit, precision=precision)
        self.confidence = confidence
        self.validators = {}
        self.info.update(implementation='WiLoR debug / batched views', detection_threshold=confidence,
                         validation='2 fresh observations spanning >=0.08s; selected-hand continuity',
                         pose_batching='all accepted hand crops across camera views',
                         owner_only_reconstruction=True, gesture_profile='wilor-fixed-v1')

    def sync(self):
        if self.device == 'cuda':
            self.torch.cuda.synchronize()

    def detect_batch(self, images, timestamps, owners):
        if not 1 <= len(images) <= 2 or len(timestamps) != len(images) or len(owners) != len(images):
            raise ValueError('WiLoR batch needs matching one-/two-view images, timestamps and owner contexts')
        import cv2
        from skimage.filters import gaussian
        from wilor_mini.utils import utils
        self.sync()
        start = time.perf_counter()
        with self.torch.inference_mode():
            detections = self.pipeline.hand_detector(images, conf=self.confidence, verbose=False,
                half=self.precision == 'fp16', max_det=self.limit)
        self.sync()
        detected = time.perf_counter()
        selected, traces = [], []
        for view, (result, timestamp, owner) in enumerate(zip(detections, timestamps, owners)):
            boxes = result.boxes.data.detach().cpu().float().numpy()
            proposals = [{'box': row[:4].tolist(), 'score': float(row[4]),
                          'label': 'Right' if row[5] else 'Left'} for row in boxes]
            validator = self.validators.setdefault(view, DetectionValidator(self.confidence))
            selected.append(validator.update(proposals, timestamp, owner))
            traces.append({**validator.trace, 'proposals': proposals, 'geometry_rejected': []})
        validated = time.perf_counter()
        patches, records = [], []
        for view, (image, proposals) in enumerate(zip(images, selected)):
            for proposal in proposals:
                box = np.asarray(proposal['box'])
                center = (box[:2]+box[2:])/2
                side = float(np.max(box[2:]-box[:2])*2.5)
                source = image
                # Retain the pinned wrapper's native crop antialiasing behavior.
                reduction = side/512.
                if reduction > 1.1:
                    source = gaussian(source, sigma=(reduction-1)/2, channel_axis=2, preserve_range=True)
                patch, _ = utils.generate_image_patch_cv2(source, *center, side, side, 256, 256,
                    proposal['label'] == 'Left', 1., 0, border_mode=cv2.BORDER_CONSTANT)
                patches.append(patch)
                records.append((view, proposal, center, side, np.array(image.shape[1::-1])))
        prepared = time.perf_counter()
        results = [[] for _ in images]
        if patches:
            with self.torch.inference_mode():
                batch = self.torch.from_numpy(np.stack(patches)).to(device=self.device, dtype=self.dtype)
                output = self.pipeline.wilor_model(batch)
                # Only joints/camera parameters cross back to CPU. Mesh outputs
                # remain internal to the upstream reconstruction model.
                joints = output['pred_keypoints_3d'].detach().cpu().float().numpy()
                cameras = output['pred_cam'].detach().cpu().float().numpy()
            self.sync()
        inferred = time.perf_counter()
        for index, (view, proposal, center, side, size) in enumerate(records):
            world = joints[index:index+1].copy()
            camera = cameras[index:index+1].copy()
            handed = 1 if proposal['label'] == 'Right' else -1
            camera[:, 1] *= handed
            world[:, :, 0] *= handed
            focal = self.pipeline.FOCAL_LENGTH/256.*max(size)
            translation = utils.cam_crop_to_full(camera, center[None], np.array([side]), size[None], focal)
            pixels = utils.perspective_projection(world, translation, np.array([[focal, focal]]), size[None]/2)
            try:
                value = prediction(pixels[0], world=world[0], label=proposal['label'],
                                   box=proposal['box'], detection_score=proposal['score'])
                if not valid_geometry(value):
                    raise ValueError('degenerate/projected hand geometry')
            except ValueError as error:
                traces[view]['geometry_rejected'].append({'box': proposal['box'], 'reason': str(error)})
                continue
            results[view].append(value)
        finished = time.perf_counter()
        return {'views': results, 'validation': traces,
                'timings_ms': {'detector_batch_ms': (detected-start)*1000,
                               'validation_ms': (validated-detected)*1000,
                               'crop_prepare_ms': (prepared-validated)*1000,
                               'pose_batch_ms': (inferred-prepared)*1000,
                               'projection_ms': (finished-inferred)*1000},
                'pose_batch_size': len(patches)}
