"""Regular debug adapter; all selection/control remains in the normal app loop."""
import time
import numpy as np

from .engine import Gesture
from .tracking import Hand, gesture_metrics
from .wilor_gestures import PROFILE
from .worker_client import WiLoRWorker


class WiLoRDebug:
    def __init__(self, args, views):
        self.worker = WiLoRWorker(args, views, optimized=True)
        self.info = self.worker.info
        self.diagnostics = {}
        self.timings = {}

    def detect(self, frames, owner, now):
        contexts = []
        for view, tracker in enumerate(owner.locals):
            track = tracker.tracks.get(owner.owner[view]) if owner.owner else None
            if track is None:
                contexts.append(None)
                continue
            hand, _, _, last_seen = track
            box = hand.model_box
            if box is None:
                box = np.r_[hand.pixels.min(axis=0), hand.pixels.max(axis=0)].tolist()
            contexts.append({'box': box, 'label': hand.label, 'age': max(0., now-last_seen)})
        started = time.perf_counter()
        response = self.worker.detect_batch(frames, contexts)
        self.timings = {**response['timings_ms'], 'wilor_worker_ms': response['inference_ms'],
                        'wilor_round_trip_ms': (time.perf_counter()-started)*1000}
        self.diagnostics = {'views': response['validation'], 'pose_batch_size': response['pose_batch_size']}
        detections = []
        for hands in response['views']:
            values = []
            for item in hands:
                metrics = gesture_metrics(item['world'], profile=PROFILE)
                values.append(Hand(np.asarray(item['pixels']), np.asarray(item['world']), item['label'],
                    Gesture(metrics['gesture']), profile=PROFILE, detection_score=item['detection_score'],
                    model_box=item['box'], diagnostics={'gesture_metrics': metrics}))
            detections.append(values)
        return detections

    def close(self):
        self.worker.close()
