import time

import cv2
import numpy as np

from .audio import Chimes
from .cameras import Cameras
from .engine import Engine, Gesture, Observation
from .debug_log import DebugLog
from .stereo import Stereo
from .tracking import Tracker, distance, gesture_metrics
from .approximate import ApproximateMotion
from .tilt import measure, measure_wrist, direction_pitch
from .fusion import canonical, combine
from .ownership import HandOwner

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
            metrics = (chosen.diagnostics or {}).get('gesture_metrics')
            if metrics is None:
                metrics = gesture_metrics(chosen.world, profile=chosen.profile)
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
    else:
        status = selection.reason.upper()
    for text, baseline, scale in ((label, 83, 2.6), (status, 147, 1.5)):
        width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)[0][0]
        scale *= min(1., 1240/max(1, width))
        width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)[0][0]
        cv2.putText(panel, text, ((1280-width)//2, baseline), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 3, cv2.LINE_AA)


def index_only(hand):
    metrics = gesture_metrics(hand.world, profile=hand.profile)
    return metrics['valid'] and [metrics['fingers'][name]['state'] for name in
                                 ('index', 'middle', 'ring', 'little')] == [1, 0, 0, 0]


def observe(left, right=None, *, stereo=None, scrolling=False, mono_scale=1., combined=None,
            approximate=None, reference=None):
    left = left if canonical(left) is not None else None
    right = right if canonical(right) is not None else None
    hands = [left] if right is None else [left, right]
    if combined is None:
        combined, reason, _ = combine(hands, ignore_thumb=scrolling)
        if combined is None:
            return None, reason
    tap_info = (combined.diagnostics or {}).get('thumb_tap', {})
    tap = bool(tap_info.get('click'))
    pointer_pause = bool(tap_info.get('pointer_pause'))
    pitch = None
    shape, _ = measure(combined, allow_thumb=True)
    if shape is not None:
        directions = [direction_pitch(np.asarray(hand.world)[[5, 8, 9, 12]])[0] for hand in hands if hand is not None]
        if directions and all(value is not None for value in directions):
            pitch = float(np.mean(directions))
    if stereo is None:
        available = left if left is not None else right
        if available is None:
            return None, 'No selected hand visible'
        points = available.pixels/mono_scale
        return Observation(combined.gesture, (*points[0], 0.), (*points[8], 0.), pitch, index_only(combined), tap, pointer_pause), 'Combined gesture; approximate image-space pointer'
    indices = [0]+list(range(5, 21)) if scrolling or combined.gesture == Gesture.SCROLL else list(range(21))
    points = stereo.reconstruct(left.pixels[indices], right.pixels[indices]) if left is not None and right is not None else None
    if points is not None and np.linalg.norm(points[0]) > 3.6576:
        return None, 'Measured hand position beyond 12-foot target range'
    if points is None:
        if approximate is None:
            return None, 'Depth unreliable or selected view missing'
        view = 0 if left is not None else 1
        available = left if left is not None else right
        if available is None:
            return None, 'No selected hand visible'
        mapped, _ = approximate.map(available, view, reference)
        return Observation(combined.gesture, tuple(mapped[0]), tuple(mapped[8]), pitch, index_only(combined), tap, pointer_pause), 'APPROXIMATE single-camera pointer; no measured depth'
    if approximate is not None:
        approximate.reset()
    indexed = dict(zip(indices, points))
    if shape is not None:
        pitch, _ = direction_pitch([indexed[i] for i in (5, 8, 9, 12)])
    return Observation(combined.gesture, tuple(indexed[0]), tuple(indexed[8]), pitch, index_only(combined), tap, pointer_pause), 'Combined gesture; calibrated stereo position'


def run(args):
    wilor = args.hand_backend == 'wilor'
    tap_mode = args.left_click == 'thumb-tap'
    if tap_mode and not wilor:
        raise ValueError('Experimental thumb-tap requires --hand-backend wilor')
    two_cameras = args.right is not None
    if not args.uncalibrated and not two_cameras:
        raise ValueError("Calibrated stereo requires two cameras; omit --calibrated for one-camera control")
    stereo, calibration_issue = None, None
    if args.uncalibrated:
        calibration_issue = 'Calibration-free image-space control selected'
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
                    activation_dwell=2.5, retain_activation_on_loss=True, activation_grace=.4)
    if wilor:
        from .wilor_gestures import ThumbFilter
    gesture_filter = ThumbFilter() if wilor else None
    if tap_mode:
        from .thumb_tap import ThumbTapFilter
        gesture_filter = ThumbTapFilter()
    owner = HandOwner(2 if two_cameras else 1, gesture_filter=gesture_filter)
    previous_key = None
    trackers, audio, desktop = [], None, None
    log = None
    wilor_tracker = None
    window = "MagicPointer - Q / Escape stops"
    mono_scale = 1.
    verified, verification_count = not two_cameras, 0
    next_marker_check = 0.
    previous_wrist, previous_wrist_time = None, None
    approximate = ApproximateMotion()
    previous_source = None
    missing_owner_since = None
    try:
        if args.debug:
            log = DebugLog(args.output, {'camera_indices': [args.left] + ([args.right] if two_cameras else []),
                           'requested_fps': args.fps, 'stereo': stereo is not None,
                           'hand_backend': args.hand_backend,
                           'classifier_profile': 'wilor-fixed-v1' if wilor else 'mediapipe',
                           'left_click_method': args.left_click,
                           'preview_only': preview_only, 'calibration_issue': calibration_issue,
                           'gesture_recognition': 'available palm-aligned landmark fusion', 'fusion_version': 2,
                           'missing_view_policy': 'recognize available geometry; approximate relative pointer',
                           'approximate_pointer_units': 'relative control coordinates; 0.10 nominal metres per captured palm length, not measured depth',
                           'fused_landmarks_frame': 'normalized palm', 'max_hands_per_view': args.max_hands,
                           'workspace_width': engine.width, 'workspace_height': engine.height,
                           'mirror_x': engine.mirror_x, 'coordinate_units': 'metres' if stereo else 'activation_palm_sizes',
                           'dwell_seconds': engine.dwell, 'activation_dwell_seconds': engine.activation_dwell,
                           'loss_timeout_seconds': engine.loss_timeout, 'retain_activation_on_loss': True,
                           'activation_grace_seconds': engine.activation_grace,
                           'palm_release_policy': 'fused geometry held for 0.18s; no per-view gesture votes',
                           'termination': 'normal'})
            if wilor:
                log.metadata['model_sha256'] = None  # MediaPipe's task is not used by this backend.
        # Verify model/dependencies before opening camera devices.
        if wilor:
            from .wilor_debug import WiLoRDebug
            wilor_tracker = WiLoRDebug(args, 2 if two_cameras else 1)
            if log:
                log.metadata['hand_model'] = wilor_tracker.info
            print('WiLoR settings:', wilor_tracker.info)
        else:
            trackers.append(Tracker(args.model, num_hands=args.max_hands))
            if two_cameras:
                trackers.append(Tracker(args.model, num_hands=args.max_hands))
        if not args.debug:
            from .desktop import Desktop
            desktop = Desktop()
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
            if preview_only:
                print("CALIBRATION-FREE: shared gestures and approximate image-space pointer; no metric depth.")
                print("Calibration:", calibration_issue)
            print("Camera negotiated settings:", cameras.info)
            print("DEBUG: preview only; no OS pointer input" if args.debug else "DESKTOP CONTROL: Q/Escape or close window to stop")
            print("Show one fist for 2.5 seconds to select that hand; open its palm to release. Other hands are ignored.")
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
                if stereo and (not verified or now >= next_marker_check):
                    good, marker_message = stereo.check_markers([f.image for f in frames], require_visible=not verified)
                    if not verified:
                        verification_count = verification_count + 1 if good and paired else 0
                        verified = verification_count >= 3
                    elif not good:
                        raise ValueError(marker_message)
                    next_marker_check = now + 1.
                detections = []
                if wilor_tracker:
                    detections = wilor_tracker.detect(frames, owner, now)
                    timings.update(wilor_tracker.timings)
                else:
                    for index, (tracker, frame) in enumerate(zip(trackers, frames)):
                        phase = time.perf_counter()
                        detections.append(tracker.detect_all(frame.image, frame.grabbed_at))
                        timings[f'detect_camera_{index}_ms'] = (time.perf_counter()-phase)*1000
                phase = time.perf_counter()
                selection = owner.select(detections, frames, now, stereo=stereo, scrolling=engine.scrolling)
                timings['selection_ms'] = (time.perf_counter()-phase)*1000
                phase = time.perf_counter()
                if not paired:
                    owner.palm_since, owner.release_ready = None, False
                hands = selection.hands or [None]*len(frames)
                if owner.owner and not any(hand is not None for hand in hands):
                    if missing_owner_since is None:
                        missing_owner_since = now
                else:
                    missing_owner_since = None
                owner_timed_out = (missing_owner_since is not None and
                                   now-missing_owner_since >= 5.)
                observation, reason = None, selection.reason
                left = hands[0]
                available = next((hand for hand in hands if hand is not None), None)
                if stereo and not verified:
                    reason = marker_message
                elif not paired:
                    reason = "Camera pair timing mismatch"
                elif selection.combined is not None:
                    if stereo is None and not engine.active:
                        mono_scale = max(10., float(np.linalg.norm(available.pixels[0]-available.pixels[9])))
                    observation, reason = observe(left, hands[1] if two_cameras else None,
                                                  stereo=stereo, scrolling=engine.scrolling,
                                                  mono_scale=mono_scale, combined=selection.combined,
                                                  approximate=approximate, reference=previous_wrist)
                source = ('approximate', approximate.source) if approximate.source is not None and observation is not None else (
                    ('stereo',) if stereo else ('image', next((i for i, hand in enumerate(hands) if hand is not None), None)))
                source_changed = source != previous_source
                if observation is not None and source_changed:
                    engine.rebase_motion()
                    previous_source = source
                # Reject implausible same-label hand switches in metric stereo mode.
                if observation is not None and stereo and source == ('stereo',) and not source_changed and engine.active and previous_wrist is not None:
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
                events = engine.step(observation, engine_now)
                if owner_timed_out:
                    events += engine.stop('hand absence timeout')
                    missing_owner_since = None
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
                        if event.value in ('open palm', 'hand absence timeout'):
                            owner.release()
                            approximate.reset()
                            previous_source = None
                            previous_key = None
                            selection.reason = 'HAND RELEASED - SHOW ONE FIST'
                        audio.play(False)
                    elif event.kind == "move" and desktop:
                        desktop.move(event.value)
                    elif event.kind == "click":
                        last_action, action_until = f"{event.value} click", now + .5
                        if desktop:
                            desktop.click(event.value)
                        audio.play(event.value)
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
                               timings=timings, engine_before=engine_before, position_source=source,
                               detector_diagnostics=wilor_tracker.diagnostics if wilor_tracker else None)
                    previous_log_ms = (time.perf_counter()-phase)*1000
                phase = time.perf_counter()
                color = COLORS[state]
                if args.debug:
                    panel = debug_views(frames, hands, [args.left, args.right], color, detections)
                else:
                    panel = np.full((540, 960, 3), (25, 25, 25), dtype=np.uint8)
                # Primary-camera raw view is intentionally labelled: controls mirror X by default.
                title = "DEBUG / NO DESKTOP INPUT" if args.debug else ("CALIBRATED STEREO / DESKTOP CONTROL" if stereo else "CALIBRATION-FREE / DESKTOP CONTROL")
                if args.debug and two_cameras:
                    title = "TWO-CAMERA DEBUG / NO OS INPUT / " + ("UNCALIBRATED TEST" if preview_only else "CALIBRATED STEREO")
                lines = [title,
                         f"State: {state} | Shared gesture: {selection.combined.gesture.value if selection.combined else 'unavailable'}" +
                         (" (clicks ignored)" if engine.scrolling else ""),
                         reason if observation is None or source[0] == 'approximate' else (last_action if now < action_until else "Tracking"),
                         f"Processing: {measured_fps:.1f} FPS | Q / Esc / close window to stop"]
                if wilor_tracker:
                    info = wilor_tracker.info
                    lines.append(f"WILOR | {info['device']} / {info['precision']} | threshold {args.wilor_confidence:.2f} | validated fresh hands")
                if tap_mode:
                    tap_info = ((selection.combined.diagnostics or {}).get('thumb_tap', {})
                                if selection.combined else {})
                    thumb_text = {1: 'open', 0: 'closed', -1: 'uncertain'}.get(tap_info.get('thumb_state'), '--')
                    lines.append('LEFT: CLOSE/REOPEN | ' + tap_info.get('state', 'no selected hand') +
                                 f' | thumb {thumb_text} | RIGHT: thumb chord')
                if engine.scrolling:
                    scroll = engine.scroll
                    feedback = "Hold two fingers steady: setting scroll neutral"
                    if scroll.neutral is not None:
                        feedback = (f"Wrist scroll: {scroll.delta:+.1f} deg | {scroll.speed:+.1f}/s (down +)"
                                    if scroll.delta is not None else "Scroll paused: restore two-finger pose")
                    lines.append(feedback + " | Index-only exits")
                if args.debug and two_cameras:
                    skew = abs(frames[0].grabbed_at-frames[1].grabbed_at)*1000
                    depth = f"Wrist range: {np.linalg.norm(observation.wrist):.2f} m" if observation and stereo and source == ('stereo',) else "NO METRIC DEPTH - approximate pointer"
                    lines.append(f"Pair grab skew: {skew:.1f} ms ({'OK' if paired else 'over 40 ms'}) | {depth}")
                if log:
                    lines.append("REC: diagnostic data (auto-saved on exit)")
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
                log.close()
        finally:
            if audio:
                if engine.active:
                    audio.play(False)
                audio.close()
            for tracker in trackers:
                tracker.close()
            if wilor_tracker:
                wilor_tracker.close()
            cv2.destroyAllWindows()
