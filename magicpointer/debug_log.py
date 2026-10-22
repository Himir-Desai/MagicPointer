"""Continuous local diagnostics for main-app debug sessions."""
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from importlib.metadata import version, PackageNotFoundError
import subprocess
import statistics
import math
from pathlib import Path
import platform
import time
import uuid
import zipfile

from . import __version__
from .tracking import CLASSIFIER_VERSION, gesture_metrics


def json_value(value):
    """Keep malformed model output inspectable in standards-compliant JSON."""
    if hasattr(value, 'tolist'):
        value = value.tolist()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def hand_sample(hand):
    if hand is None:
        return None
    pixels = hand.pixels.tolist() if hasattr(hand.pixels, 'tolist') else hand.pixels
    geometry = None
    if pixels and all(math.isfinite(value) for point in pixels for value in point):
        geometry = {'bounding_box_pixels': [min(point[0] for point in pixels), min(point[1] for point in pixels),
                                           max(point[0] for point in pixels), max(point[1] for point in pixels)],
                    'palm_size_pixels': math.hypot(pixels[0][0]-pixels[9][0], pixels[0][1]-pixels[9][1])}
    metrics = (hand.diagnostics or {}).get('gesture_metrics')
    if metrics is None:
        metrics = gesture_metrics(hand.world, profile=hand.profile)
    return {'gesture_estimate': hand.gesture.value, 'handedness': hand.label,
            'handedness_score': hand.handedness_score, 'pixels': hand.pixels,
            'world_landmarks': hand.world, 'image_landmarks': hand.image_landmarks,
            'metrics': metrics,
            'classifier_profile': hand.profile, 'detection_score': hand.detection_score,
            'model_box': hand.model_box, 'model_diagnostics': hand.diagnostics, 'image_geometry': geometry}


def runtime_info():
    packages = {}
    for name in ('mediapipe', 'numpy', 'opencv-contrib-python'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                          cwd=Path(__file__).resolve().parents[1],
                                          stderr=subprocess.DEVNULL, timeout=1, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'],
                                             cwd=Path(__file__).resolve().parents[1], stderr=subprocess.DEVNULL, timeout=1, text=True).strip())
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    from .model import MODEL_SHA256
    return {'dependencies': packages, 'git_revision': revision, 'git_dirty': dirty, 'model_sha256': MODEL_SHA256,
            'architecture': platform.machine(), 'diagnostics_version': 2}


class DebugLog:
    def __init__(self, output, metadata):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.path = Path(output)/f'debug-{stamp}-{uuid.uuid4().hex[:8]}'
        self.path.mkdir(parents=True, exist_ok=False)
        self.metadata = {'schema_version': 2, 'kind': 'debug-run', **runtime_info(),
                         'created_utc': stamp, 'app_version': __version__,
                         'classifier_version': CLASSIFIER_VERSION,
                         'os': platform.system(), 'python': platform.python_version(),
                         'images_recorded': False, 'desktop_input': False, **metadata}
        self.started = time.monotonic()
        self.counts = Counter()
        self.reasons = Counter()
        self.timing_samples = {}
        self.last_frame_time = None
        self.closed = False
        self._write('session.json', self.metadata)
        self.stream = (self.path/'samples.jsonl').open('w', encoding='utf-8')
        print(f'Debug data recording: {self.path}')

    def _write(self, name, value):
        (self.path/name).write_text(json.dumps(json_value(value), allow_nan=False, indent=2), encoding='utf-8')

    def append(self, frames, hands, observation, engine, events, now, *, reason, paired, verified, state, detections=None, ownership=None, selection=None, timings=None, engine_before=None, position_source=None, detector_diagnostics=None):
        sample = {'elapsed_seconds': now-self.started, 'monotonic_seconds': now,
                  'cameras': [{'grabbed_at': frame.grabbed_at,
                               'image_size': [frame.image.shape[1], frame.image.shape[0]],
                               'hand': hand_sample(hand)} for frame, hand in zip(frames, hands)],
                  'pair_grab_skew_ms': abs(frames[0].grabbed_at-frames[1].grabbed_at)*1000 if len(frames) == 2 else None,
                  'observation': asdict(observation) if observation else None,
                  'reason': reason, 'pair_timing_valid': paired, 'markers_verified': verified,
                  'position_source': position_source,
                  'detector_diagnostics': detector_diagnostics,
                  'state': state, 'active': engine.active, 'scrolling': engine.scrolling,
                  'cursor': engine.cursor, 'origin': engine.origin,
                  'scroll': {'neutral_degrees': engine.scroll.neutral,
                             'smoothed_degrees': engine.scroll.filtered,
                             'delta_degrees': engine.scroll.delta,
                             'down_steps_per_second': engine.scroll.speed},
                  'events': [asdict(event) for event in events],
                  'engine_before': engine_before, 'engine_after': engine.diagnostics(now),
                  'timings_ms': timings or {},
                  'frame_interval_ms': None if self.last_frame_time is None else (now-self.last_frame_time)*1000}
        if sample['frame_interval_ms'] is not None:
            self.timing_samples.setdefault('frame_interval_ms', []).append(sample['frame_interval_ms'])
        self.last_frame_time = now
        for name, value in (timings or {}).items():
            self.timing_samples.setdefault(name, []).append(value)
        self.reasons[reason] += 1
        self.counts['paused_frames'] += engine.paused
        self.counts['timing_rejected_frames'] += not paired
        if ownership is not None:
            sample['tracking_decisions'] = [tracker.diagnostics for tracker in ownership.locals]
            sample['matching_decisions'] = ownership.diagnostics
        if detections is not None:
            for index, hands in enumerate(detections):
                visible = ownership.visible[index] if ownership else {}
                sample['cameras'][index]['hands'] = [
                    {'track_id': next((key for key, tracked in visible.items() if tracked is hand), None),
                     **hand_sample(hand)} for hand in hands]
        if selection is not None:
            sample['selection'] = {'owner_ids': ownership.owner, 'candidate_ids': ownership.candidate,
                                   'visible_ids': [list(view) for view in ownership.visible],
                                   'progress': selection.progress, 'reason': selection.reason,
                                   'palm_since': ownership.palm_since, 'release_ready': ownership.release_ready,
                                   'shape_disagreement': selection.spread,
                                   'combined_hand': hand_sample(selection.combined)}
        self.stream.write(json.dumps(json_value(sample), allow_nan=False)+'\n')
        self.stream.flush()
        self.counts['frames'] += 1
        self.counts['accepted_observations'] += observation is not None
        self.counts['scrolling_frames'] += engine.scrolling
        for event in events:
            self.counts[event.kind+'_events'] += 1

    def close(self):
        if self.closed:
            return
        self.stream.close()
        self._write('session.json', self.metadata)
        timing = {}
        for name, values in self.timing_samples.items():
            if values:
                ordered = sorted(values)
                timing[name] = {'median': statistics.median(values),
                                'p95': ordered[min(len(ordered)-1, math.ceil(.95*len(ordered))-1)],
                                'max': max(values)}
        self._write('summary.json', {**self.counts, 'rejection_and_status_counts': dict(self.reasons), 'timings_ms': timing})
        archive = self.path.with_suffix('.zip')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in ('session.json', 'samples.jsonl', 'summary.json'):
                bundle.write(self.path/name, arcname=name)
        self.closed = True
        print(f'Debug diagnostics saved: {archive}')
