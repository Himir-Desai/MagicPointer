from concurrent.futures import ThreadPoolExecutor
import ctypes
import platform
import time

import cv2
import numpy as np

from .audio import Chimes
from .cameras import Cameras
from .engine import Engine, Gesture, Observation
from .debug_log import DebugLog
from .stereo import Stereo
from .tracking import Tracker, distance, gesture_metrics
from .tilt import measure, measure_wrist, direction_pitch
from .fusion import combine
from .ownership import HandOwner
from .adaptive_detection import AdaptiveDetection
from .recovery import CropRecovery

COLORS = {"inactive": (150, 150, 150), "active": (70, 210, 70),
          "click": (220, 120, 240), "scroll": (240, 180, 30), "unavailable": (0, 160, 255)}


def draw_hand(image, hand, color):
    if hand is None:
        return
    points = hand.pixels.astype(int)
    x, y = points.min(axis=0) - 15
    x2, y2 = points.max(axis=0) + 15
    cv2.rectangle(image, (int(x), int(y)), (int(x2), int(y2)), color, 3)
    for start in (1, 5, 9, 13, 17):
        cv2.line(image, tuple(points[0]), tuple(points[start]), color, 2)
        for index in range(start, start+3):
            cv2.line(image, tuple(points[index]), tuple(points[index+1]), color, 2)
    for point in points:
        cv2.circle(image, tuple(point), 4, color, -1)


def debug_views(frames, hands, indices, color, all_hands=None):
    """All visible hands in gray, chosen hand highlighted; shared result above."""
    panel = np.full((900, 1280, 3), 25, dtype=np.uint8)
    for column, (frame, chosen, index) in enumerate(zip(frames, hands, indices)):
        image = frame.image.copy()
        for hand in (all_hands[column] if all_hands else []):
            draw_hand(image, hand, (110, 110, 110))
        draw_hand(image, chosen, color)
        height, width = image.shape[:2]
        scale = min(640/width, 360/height)
        resized = cv2.resize(image, (max(1, round(width*scale)), max(1, round(height*scale))))
        h, w = resized.shape[:2]
        start = column*640 if len(frames) == 2 else 320
        x, y = start+(640-w)//2, 360+(360-h)//2
        panel[y:y+h, x:x+w] = resized
        label = f'Camera {index} | {width}x{height} | {len(all_hands[column]) if all_hands else int(chosen is not None)} hands'
        pose = f'View estimate: {chosen.gesture.value} | {chosen.label}' if chosen else 'No matched controlling hand'
        for line, text in enumerate((label, pose)):
            cv2.putText(panel, text, (12+column*640, 747+line*25), cv2.FONT_HERSHEY_SIMPLEX, .57, color, 1, cv2.LINE_AA)
        if chosen:
            metrics = gesture_metrics(chosen.world)
            if metrics['valid']:
                cv2.putText(panel, f"Thumb/index/middle/ring/little: {metrics['signature']}",
                            (12+column*640, 797), cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1, cv2.LINE_AA)
    return panel


def large_gesture(panel, selection, owner, engine, color, ready=True, available=True):
    label = selection.combined.gesture.value.upper() if selection.combined else ('OWNER PAUSED' if owner.owner else 'SHOW ONE FIST')
    if not ready:
        status = 'INPUT PAUSED - CHECK CAMERA PAIR / WALL MARKERS'
    elif owner.owner:
        status = 'HAND LOCKED' if engine.active else 'HAND LOCKED - HOLD FIST TO RESUME'
        if not available:
            status = 'INPUT PAUSED - CHECK BOTH VIEWS'
        if selection.combined is None:
            status = 'INPUT PAUSED - RETURN THE SELECTED HAND'
            lost = owner.diagnostics.get('owner_lost_seconds')
            if owner.timeout and lost is not None:
                status = f'RETURN THE SELECTED HAND - RELEASING IN {max(0., owner.timeout-lost):.1f}S'
    else:
        status = selection.reason.upper()
    for text, baseline, scale in ((label, 83, 2.6), (status, 147, 1.5)):
        width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)[0][0]
        scale *= min(1., 1240/max(1, width))
        width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)[0][0]
        cv2.putText(panel, text, ((1280-width)//2, baseline), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 3, cv2.LINE_AA)


def high_resolution_timer():
    """Request 1 ms Windows timers; otherwise waitKey(1) and short sleeps take ~15.6 ms."""
    if platform.system() != "Windows":
        return lambda: None
    try:
        winmm = ctypes.WinDLL("winmm")
        winmm.timeBeginPeriod(1)
        return lambda: winmm.timeEndPeriod(1)
    except (OSError, AttributeError):
        return lambda: None


class MarkerWatch:
    """Periodic wall-marker checks off the processing loop.

    ArUco detection on two full frames can take tens to hundreds of
    milliseconds, which used to stall control once a second. A single bad
    check (for example a partly occluded marker) no longer ends the session:
    displacement must be seen on `failures` consecutive checks.
    """

    def __init__(self, stereo, interval=1., failures=3):
        self.stereo, self.interval, self.failures = stereo, interval, failures
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending, self.next_check, self.failed = None, 0., 0

    def poll(self, images, now):
        if self.pending is not None and self.pending.done():
            good, message = self.pending.result()
            self.pending = None
            self.failed = 0 if good else self.failed + 1
            if self.failed >= self.failures:
                raise ValueError(message)
        if self.pending is None and now >= self.next_check:
            self.pending = self.pool.submit(self.stereo.check_markers, list(images), require_visible=False)
            self.next_check = now + self.interval

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def detect_views(trackers, frames, pool):
    """Run each camera's detector, in parallel when a pool is given (MediaPipe releases the GIL)."""
    def timed(tracker, frame):
        start = time.perf_counter()
        hands = tracker.detect_all(frame.image, frame.grabbed_at)
        return hands, (time.perf_counter() - start) * 1000
    results = list(pool.map(timed, trackers, frames)) if pool else [timed(t, f) for t, f in zip(trackers, frames)]
    return [hands for hands, _ in results], [ms for _, ms in results]


def index_only(hand):
    metrics = gesture_metrics(hand.world)
    return metrics['valid'] and [metrics['fingers'][name]['state'] for name in
                                 ('index', 'middle', 'ring', 'little')] == [1, 0, 0, 0]


def observe(left, right=None, *, stereo=None, scrolling=False, mono_scale=1., combined=None):
    hands = [left] if right is None else [left, right]
    if combined is None:
        combined, reason, _ = combine(hands, ignore_thumb=scrolling)
        if combined is None:
            return None, reason
    pitch = None
    shape, _ = measure(combined, allow_thumb=True)
    if shape is not None:
        directions = [direction_pitch(np.asarray(hand.world)[[5, 8, 9, 12]])[0] for hand in hands]
        if all(value is not None for value in directions):
            pitch = float(np.mean(directions))
    if stereo is None:
        points = left.pixels/mono_scale
        return Observation(combined.gesture, (*points[0], 0.), (*points[8], 0.), pitch, index_only(combined)), 'Combined gesture; approximate image-space pointer'
    if right is None:
        return None, 'Selected hand missing from a camera'
    # Check the joints used for position and pitch, plus the thumb as click
    # evidence outside scrolling; an occluded, unused curled finger must not
    # reject the whole pair.
    indices = [0, 5, 8, 9, 12] if scrolling or combined.gesture == Gesture.SCROLL else [0, 1, 2, 3, 4, 5, 8, 9, 12]
    points = stereo.reconstruct(left.pixels[indices], right.pixels[indices])
    if points is None or np.linalg.norm(points[0]) > 3.6576:
        return None, 'Depth unreliable or beyond 12-foot target range'
    indexed = dict(zip(indices, points))
    if shape is not None:
        pitch, _ = direction_pitch([indexed[i] for i in (5, 8, 9, 12)])
    return Observation(combined.gesture, tuple(indexed[0]), tuple(indexed[8]), pitch, index_only(combined)), 'Combined gesture; calibrated stereo position'


def run(args):
    if args.adaptive_detection and (not args.debug or args.right is None):
        raise ValueError("Adaptive detection requires two-camera --debug; desktop control is unchanged")
    if not args.debug and args.right is None and not args.uncalibrated:
        raise ValueError("Calibrated pointer control needs two cameras. For one camera use run --uncalibrated, "
                         "or run --debug for a preview")
    two_cameras = args.right is not None
    stereo, calibration_issue = None, None
    if args.uncalibrated:
        calibration_issue = 'Uncalibrated testing requested explicitly'
    if two_cameras and not args.uncalibrated:
        try:
            stereo = Stereo.load(args.calibration)
            if stereo.data.get("camera_indices") != [args.left, args.right]:
                raise ValueError("Camera indices/order differ from calibration; select the calibrated pair or recalibrate")
        except ValueError as error:
            if not args.debug:
                raise
            stereo, calibration_issue = None, str(error)
    preview_only = two_cameras and stereo is None
    engine = Engine(width=args.workspace_width * (10 if stereo is None else 1),
                    height=args.workspace_height * (10 if stereo is None else 1), mirror_x=args.mirror_x,
                    activation_dwell=args.activation_seconds, retain_activation_on_loss=True, activation_grace=.4)
    owner = HandOwner(2 if two_cameras else 1, dwell=args.activation_seconds, timeout=args.owner_timeout)
    previous_key = None
    trackers, audio, desktop = [], None, None
    log, adaptive, pool, watch, recovery = None, None, None, None, None
    end_timer = high_resolution_timer()
    window = "MagicPointer - Q / Escape stops"
    mono_scale = 1.
    verified, verification_count = not two_cameras, 0
    previous_wrist, previous_wrist_time = None, None
    try:
        if args.debug:
            log = DebugLog(args.output, {'camera_indices': [args.left] + ([args.right] if two_cameras else []),
                           'requested_fps': args.fps, 'stereo': stereo is not None,
                           'preview_only': preview_only, 'calibration_issue': calibration_issue,
                           'gesture_recognition': 'palm-aligned landmark fusion', 'fusion_version': 1,
                           'fused_landmarks_frame': 'normalized palm', 'max_hands_per_view': args.max_hands,
                           'workspace_width': engine.width, 'workspace_height': engine.height,
                           'mirror_x': engine.mirror_x, 'coordinate_units': 'metres' if stereo else 'activation_palm_sizes',
                           'dwell_seconds': engine.dwell, 'activation_dwell_seconds': engine.activation_dwell,
                           'loss_timeout_seconds': engine.loss_timeout, 'retain_activation_on_loss': True,
                           'activation_grace_seconds': engine.activation_grace,
                           'palm_release_policy': 'immediate two-view and fused agreement, otherwise 0.18s',
                           'owner_timeout_seconds': owner.timeout,
                           'pipeline': {'capture': 'background newest-frame threads', 'parallel_detection': two_cameras,
                                        'crop_recovery': args.crop_recovery, 'marker_checks': 'background, 3 consecutive failures stop'},
                           'termination': 'normal'})
            if args.adaptive_detection:
                log.metadata['adaptive_detection'] = {'enabled': True, 'version': 1,
                    'regular_detection_confidence': .65, 'regular_presence_confidence': .65,
                    'recovery_detection_confidence': AdaptiveDetection.confidence,
                    'recovery_presence_confidence': AdaptiveDetection.confidence,
                    'minimum_retry_interval_seconds': AdaptiveDetection.interval,
                    'recovery_mode': 'IMAGE', 'requires_both_views': True}
                adaptive = AdaptiveDetection(args.model, args.max_hands)
        # Verify model/dependencies before opening camera devices.
        trackers.append(Tracker(args.model, num_hands=args.max_hands))
        if two_cameras:
            trackers.append(Tracker(args.model, num_hands=args.max_hands))
        if two_cameras:
            pool = ThreadPoolExecutor(max_workers=2)
        if args.crop_recovery:
            recovery = CropRecovery(lambda: Tracker(args.model, num_hands=1, image_mode=True), len(trackers))
        if not args.debug:
            from .desktop import Desktop, SmoothDesktop
            desktop = SmoothDesktop(Desktop(), smooth_scroll=args.smooth_scroll)
        audio = Chimes(args.mute)
        with Cameras(args.left, args.right, args.fps, backend=args.camera_backend,
                     width=args.capture_width, height=args.capture_height) as cameras:
            if stereo and args.debug and any((camera['width'], camera['height']) != stereo.size for camera in cameras.info):
                stereo = None
                preview_only = True
                calibration_issue = "Camera resolution differs from calibration; recalibrate at this resolution"
                verified = False
                if log:
                    log.metadata.update(stereo=False, preview_only=True, calibration_issue=calibration_issue, coordinate_units='activation_palm_sizes')
                engine.width = args.workspace_width*10
                engine.height = args.workspace_height*10
            if log:
                log.metadata.update(cameras=cameras.info, workspace_width=engine.width, workspace_height=engine.height)
            if not args.debug and stereo is None:
                print("UNCALIBRATED CONTROL: the real pointer follows an approximate image-space position; "
                      "no metric depth or wall-marker checks. Open palm, Q or Escape stops input.")
            elif preview_only:
                print("UNCALIBRATED TEST: shared gestures and approximate virtual pointer; no metric depth.")
                print("Calibration:", calibration_issue)
            print("Camera negotiated settings:", cameras.info)
            print("DEBUG: preview only; no OS pointer input" if args.debug else
                  ("STEREO CONTROL" if stereo else "DESKTOP CONTROL") + ": Q/Escape or close window to stop")
            release = f", or keep it away for {owner.timeout:g} seconds," if owner.timeout else ""
            print(f"Show one fist for {args.activation_seconds:g} seconds to select that hand; open its palm{release} to release. Other hands are ignored.")
            print("Two fingers toward screen: hold steady to set scroll neutral; tilt up/down. Index-only exits scrolling.")
            start, count, measured_fps = time.monotonic(), 0, 0.
            last_action, action_until = "", 0.
            previous_log_ms = previous_render_ms = 0.
            while True:
                phase = time.perf_counter()
                frames = cameras.read()
                timings = {'capture_ms': (time.perf_counter()-phase)*1000,
                           'previous_log_ms': previous_log_ms, 'previous_render_ms': previous_render_ms}
                now = time.monotonic()
                paired = (abs(frames[0].grabbed_at-frames[1].grabbed_at) <= .04) if two_cameras else True
                if stereo:
                    paired = stereo.check_frames(frames)
                marker_message = "Mono preview: depth is not measured"
                if stereo and not verified:
                    good, marker_message = stereo.check_markers([f.image for f in frames], require_visible=True)
                    verification_count = verification_count + 1 if good and paired else 0
                    verified = verification_count >= 3
                elif stereo:
                    if watch is None:
                        watch = MarkerWatch(stereo)
                    watch.poll([f.image for f in frames], now)
                phase = time.perf_counter()
                detections, detect_ms = detect_views(trackers, frames, pool)
                for index, value in enumerate(detect_ms):
                    timings[f'detect_camera_{index}_ms'] = value
                timings['detect_total_ms'] = (time.perf_counter()-phase)*1000
                baseline_detections, adaptive_trace = detections, None
                if recovery:
                    phase = time.perf_counter()
                    detections = recovery.apply(detections, frames, now, pool)
                    timings['crop_recovery_ms'] = (time.perf_counter()-phase)*1000
                if adaptive:
                    phase = time.perf_counter()
                    detections, adaptive_trace = adaptive.apply(detections, frames, now, paired=paired)
                    timings['adaptive_detection_ms'] = (time.perf_counter()-phase)*1000
                phase = time.perf_counter()
                selection = owner.select(detections, frames, now, stereo=stereo, scrolling=engine.scrolling)
                timings['selection_ms'] = (time.perf_counter()-phase)*1000
                if recovery:
                    # Search where the selected owner was, or the nearest hand before selection.
                    for view, hands_in_view in enumerate(detections):
                        if owner.owner:
                            if selection.hands and selection.hands[view] is not None:
                                recovery.remember(view, selection.hands[view], now)
                        elif hands_in_view:
                            recovery.remember(view, max(hands_in_view, key=lambda hand: float(np.ptp(np.asarray(hand.pixels)[:, 0]))), now)
                phase = time.perf_counter()
                if not paired:
                    owner.palm_since, owner.release_ready = None, False
                hands = selection.hands or [None]*len(frames)
                observation, reason = None, selection.reason
                left = hands[0]
                if stereo and not verified:
                    reason = marker_message
                elif not paired:
                    reason = "Camera pair timing mismatch"
                elif selection.combined is not None:
                    if stereo is None and not engine.active:
                        mono_scale = max(10., float(np.linalg.norm(left.pixels[0]-left.pixels[9])))
                    observation, reason = observe(left, hands[1] if two_cameras else None,
                                                  stereo=stereo, scrolling=engine.scrolling,
                                                  mono_scale=mono_scale, combined=selection.combined)
                # Reject implausible same-label hand switches in metric stereo mode.
                if observation is not None and stereo and engine.active and previous_wrist is not None:
                    elapsed = now - previous_wrist_time
                    if elapsed > 0 and distance(observation.wrist, previous_wrist) / elapsed > 4.:
                        observation, reason = None, "Hand moved too abruptly; reacquire"
                if observation is not None:
                    previous_wrist, previous_wrist_time = observation.wrist, now
                if observation is None and not owner.owner:
                    owner.candidate = owner.since = None
                    selection.progress = 0.
                timings['observation_ms'] = (time.perf_counter()-phase)*1000
                engine_now = time.monotonic()
                if not engine.active and selection.key is not None and selection.key != previous_key:
                    engine.reset_activation()
                if selection.key is not None:
                    previous_key = selection.key
                engine_before = engine.diagnostics(engine_now)
                phase = time.perf_counter()
                # A timed-out owner ends control before another hand's frame can resume it.
                events = engine.stop('owner timeout') if owner.expired and engine.active else []
                events += engine.step(observation, engine_now)
                timings['engine_ms'] = (time.perf_counter()-phase)*1000
                if not engine.active and engine.activation_progress > 0:
                    selection.progress = engine.activation_progress
                    selection.reason = f'HOLD FIST: {engine.activation_dwell*(1-selection.progress):.1f}s'

                if owner.owner and owner.release_ready and engine.active:
                    events += engine.stop('open palm')
                for event in events:
                    if event.kind == "activate":
                        owner.lock(selection.key)
                        audio.play(True)
                    elif event.kind == "deactivate":
                        previous_wrist = None
                        if event.value == 'open palm':
                            owner.release()
                            selection.reason = 'HAND RELEASED - SHOW ONE FIST'
                        audio.play(False)
                    elif event.kind == "move" and desktop:
                        desktop.move(event.value)
                    elif event.kind == "click":
                        last_action, action_until = f"{event.value} click", now + .5
                        if desktop:
                            desktop.click(event.value)
                    elif event.kind == "scroll":
                        last_action, action_until = f"scroll {event.value:+d}", now + .3
                        if desktop:
                            desktop.scroll(event.value)
                if owner.owner and owner.release_ready:
                    owner.release()
                    selection.reason = 'HAND RELEASED - SHOW ONE FIST'
                    if not any(event.kind == 'deactivate' for event in events):
                        audio.play(False)
                if observation is None:
                    selection.reason = reason
                state = "inactive" if not engine.active else "active"
                if observation is None or engine.paused:
                    state = "unavailable"
                elif engine.scrolling:
                    state = "scroll"
                elif now < action_until:
                    state = "click"
                if log:
                    phase = time.perf_counter()
                    log.append(frames, hands, observation, engine, events, engine_now,
                               reason=reason, paired=paired, verified=verified, state=state,
                               detections=detections, ownership=owner, selection=selection,
                               timings=timings, engine_before=engine_before,
                               baseline_detections=baseline_detections if adaptive else None,
                               adaptive_detection=adaptive_trace)
                    previous_log_ms = (time.perf_counter()-phase)*1000
                phase = time.perf_counter()
                color = COLORS[state]
                if args.debug:
                    panel = debug_views(frames, hands, [args.left, args.right], color, detections)
                else:
                    panel = np.full((540, 960, 3), (25, 25, 25), dtype=np.uint8)
                # Primary-camera raw view is intentionally labelled: controls mirror X by default.
                title = "DEBUG / NO DESKTOP INPUT" if args.debug else ("STEREO / DESKTOP CONTROL" if stereo else "UNCALIBRATED / DESKTOP CONTROL")
                if args.debug and two_cameras:
                    title = "TWO-CAMERA DEBUG / NO OS INPUT / " + ("UNCALIBRATED TEST" if preview_only else "CALIBRATED STEREO")
                lines = [title,
                         f"State: {state} | Shared gesture: {selection.combined.gesture.value if selection.combined else 'unavailable'}" +
                         (" (clicks ignored)" if engine.scrolling else ""),
                         reason if observation is None else (last_action if now < action_until else "Tracking"),
                         f"Processing: {measured_fps:.1f} FPS | Q / Esc / close window to stop"]
                if engine.scrolling:
                    scroll = engine.scroll
                    feedback = "Hold two fingers steady: setting scroll neutral"
                    if scroll.neutral is not None:
                        feedback = (f"Wrist scroll: {scroll.delta:+.1f} deg | {scroll.speed:+.1f}/s (down +)"
                                    if scroll.delta is not None else "Scroll paused: restore two-finger pose")
                    lines.append(feedback + " | Index-only exits")
                if args.debug and two_cameras:
                    skew = abs(frames[0].grabbed_at-frames[1].grabbed_at)*1000
                    depth = f"Wrist range: {np.linalg.norm(observation.wrist):.2f} m" if observation and stereo else "NO METRIC DEPTH - approximate pointer"
                    lines.append(f"Pair grab skew: {skew:.1f} ms ({'OK' if paired else 'over 40 ms'}) | {depth}")
                if log:
                    lines.append("REC: diagnostic data (auto-saved on exit)")
                if adaptive_trace:
                    view = adaptive_trace['attempted_view']
                    attempt = '' if view is None else f" camera {[args.left, args.right][view]}"
                    lines.append(f"ADAPTIVE TEST{attempt}: {adaptive_trace['reason']}")
                for i, line in enumerate(lines):
                    y = 192+i*22 if args.debug else 27+i*26
                    cv2.putText(panel, line, (15, y), cv2.FONT_HERSHEY_SIMPLEX, .50 if args.debug else .58, (0, 0, 0), 4)
                    cv2.putText(panel, line, (15, y), cv2.FONT_HERSHEY_SIMPLEX, .50 if args.debug else .58, color, 1)
                if args.debug:
                    large_gesture(panel, selection, owner, engine, color, ready=paired and (not stereo or verified), available=observation is not None and not engine.paused)
                for i, (name, value) in enumerate(COLORS.items()):
                    cv2.putText(panel, name, (15+i*185, panel.shape[0]-18), cv2.FONT_HERSHEY_SIMPLEX, .5, value, 1)
                # Small virtual screen shows motion even when using just one camera.
                cursor_x, cursor_y = (1050, 190) if args.debug else (730, 120)
                cv2.rectangle(panel, (cursor_x, cursor_y), (cursor_x+215, cursor_y+135), (220, 220, 220), 1)
                if engine.active:
                    cv2.circle(panel, (cursor_x+round(engine.cursor[0]*215), cursor_y+round(engine.cursor[1]*135)), 5, color, -1)
                cv2.imshow(window, panel)
                key = cv2.waitKey(1) & 255
                previous_render_ms = (time.perf_counter()-phase)*1000
                if key in (27, ord('q')) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    return 0
                count += 1
                if now - start >= 1:
                    measured_fps, start, count = count/(now-start), now, 0
    except BaseException as error:
        if log:
            log.metadata['termination'] = type(error).__name__
            log.metadata['error'] = str(error)
        raise
    finally:
        try:
            if log:
                if recovery:
                    log.metadata['crop_recovered_frames_per_camera'] = recovery.recovered
                log.close()
        finally:
            if audio:
                if engine.active:
                    audio.play(False)
                audio.close()
            if desktop:
                desktop.close()
            if watch:
                watch.close()
            if recovery:
                recovery.close()
            if pool:
                pool.shutdown(wait=True)
            for tracker in trackers:
                tracker.close()
            if adaptive:
                adaptive.close()
            cv2.destroyAllWindows()
            end_timer()
