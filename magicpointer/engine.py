"""Deterministic, timestamp-driven gesture engine. Never touches the OS."""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional, Tuple

from .scrolling import PitchScroll
from .motion import CursorSmoother

Point = Tuple[float, float, float]


class Gesture(str, Enum):
    FIST = "fist"
    POINT = "point"
    LEFT = "left click"
    RIGHT = "right click"
    SCROLL = "scroll"
    PALM = "open palm"
    UNKNOWN = "unrecognized"


@dataclass(frozen=True)
class Observation:
    gesture: Gesture
    wrist: Point
    tip: Point
    scroll_pitch: Optional[float] = None
    point_shape: bool = False
    thumb_tap: bool = False
    pointer_pause: bool = False


@dataclass(frozen=True)
class Event:
    kind: str
    value: object = None


class Engine:
    """Coordinates use camera X right/Y down; workspace dimensions use metres.

    Mono preview supplies coordinates normalized to activation palm size instead.
    A chord is latched until POINT/FIST, preventing left->right->left cascades.
    """

    def __init__(self, width=0.40, height=0.25, mirror_x=True,
                 dwell=0.18, activation_dwell=0.45, loss_timeout=0.30,
                 retain_activation_on_loss=False, activation_grace=0.):
        values = (width, height, dwell, activation_dwell, loss_timeout)
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("Workspace sizes and timing thresholds must be positive and finite")
        self.width, self.height, self.mirror_x = width, height, mirror_x
        self.dwell, self.activation_dwell = dwell, activation_dwell
        if not math.isfinite(activation_grace) or activation_grace < 0:
            raise ValueError("Activation grace must be finite and nonnegative")
        self.loss_timeout = loss_timeout
        self.retain_activation_on_loss = retain_activation_on_loss
        self.activation_grace = activation_grace
        self.paused = False
        self.reset_activation()
        self.active = False
        self.origin = None
        self.cursor = (0.5, 0.5)
        self._candidate = None
        self._since = 0.0
        self._last_time = None
        self._last_seen = None
        self._action_latched = False
        self.scrolling = False
        self.scroll = PitchScroll()
        self._exit_since = None
        self._offset = (0., 0.)
        self._rebase = False
        self._last_move = None
        self.motion = CursorSmoother()
        self._pointing_started = False

    def reset_activation(self):
        self._fist_seconds = 0.
        self._last_fist = None
        self._previous_fist = False

    def rebase_motion(self):
        """Preserve the cursor when its coordinate source changes."""
        self._rebase = True
        self._last_move = None
        self.motion.reset()
        self.scroll.reset()

    @property
    def activation_progress(self):
        return 1. if self.active else min(1., self._fist_seconds/self.activation_dwell)

    def diagnostics(self, now):
        return {'active': self.active, 'paused': self.paused,
                'gesture_candidate': self._candidate, 'candidate_since': self._since,
                'last_seen': self._last_seen,
                'missing_seconds': None if self._last_seen is None else now-self._last_seen,
                'fist_valid_seconds': self._fist_seconds, 'last_fist': self._last_fist,
                'click_latched': self._action_latched, 'scrolling': self.scrolling,
                'rebase_pending': self._rebase}

    def _pause(self):
        if not self.paused:
            self._candidate = None
            self._action_latched = True
            self._rebase = True
            self._last_move = self._exit_since = None
            self.motion.reset()
            self.scroll.reset()
        self.paused = True

    def stop(self, reason):
        self.active = False
        self.paused = False
        self.reset_activation()
        self.origin = None
        self._candidate = None
        self._action_latched = False
        self.scrolling = False
        self.scroll = PitchScroll()
        self._exit_since = None
        self._offset = (0., 0.)
        self._rebase = False
        self._last_move = None
        self.motion.reset()
        self._pointing_started = False
        return [Event("deactivate", reason)]

    def step(self, observation: Optional[Observation], now: float):
        if not math.isfinite(now) or (self._last_time is not None and now < self._last_time):
            raise ValueError("Timestamps must be finite and monotonic")
        dt = 0.0 if self._last_time is None else now - self._last_time
        self._last_time = now
        valid = observation is not None and all(
            math.isfinite(v) for point in (observation.wrist, observation.tip) for v in point)
        # A selected owner pauses through gaps; legacy stand-alone engines can
        # still deactivate. Recovery never reuses a pending click or scroll rate.
        if self.active and self.retain_activation_on_loss:
            late = self._last_seen is not None and now-self._last_seen > self.loss_timeout
            if not valid or late:
                self._pause()
                if valid:
                    self._last_seen = now
                return []
            if self.paused:
                self.paused = False
        if self.active and self._last_seen is not None and now-self._last_seen > self.loss_timeout:
            events = self.stop("tracking lost")
            self._last_seen = now if valid else self._last_seen
            return events
        if not self.active and self.activation_grace > 0:
            gesture = observation.gesture if valid else Gesture.UNKNOWN
            if gesture == Gesture.FIST:
                if self._last_fist is None or now-self._last_fist > self.activation_grace:
                    self.reset_activation()
                if self._previous_fist:
                    self._fist_seconds += dt
                self._last_fist, self._previous_fist = now, True
                if self._fist_seconds >= self.activation_dwell:
                    self.active = True
                    self.origin, self.cursor = observation.wrist, (.5, .5)
                    self._last_seen = now
                    self._candidate, self._since = gesture, now
                    self._action_latched = False
                    return [Event("activate"), Event("move", self.cursor)]
            elif gesture == Gesture.UNKNOWN:
                self._previous_fist = False
                if self._last_fist is not None and now-self._last_fist > self.activation_grace:
                    self.reset_activation()
            else:
                self.reset_activation()
            return []
        if not valid:
            self._candidate = None
            self.scroll.update(None, now)
            self._exit_since = None
            return []
        self._last_seen = now
        gesture = observation.gesture
        if gesture != self._candidate:
            self._candidate, self._since = gesture, now
        elapsed = now - self._since
        if not self.active:
            if gesture == Gesture.FIST and elapsed >= self.activation_dwell:
                self.active = True
                self.origin = observation.wrist
                self.cursor = (0.5, 0.5)
                self._action_latched = False
                return [Event("activate"), Event("move", self.cursor)]
            return []
        # Stop motion immediately on a palm candidate, then confirm the transition.
        if gesture == Gesture.PALM:
            self.scroll.update(None, now)
            self._exit_since = None
            return self.stop("open palm") if elapsed >= self.dwell else []
        if (not self.scrolling and gesture == Gesture.SCROLL and elapsed >= self.dwell
                and not self._action_latched and observation.scroll_pitch is not None):
            self.scrolling = True
            self.scroll.reset()
        if self.scrolling:
            # Thumb is deliberately irrelevant once latched. Only a stable
            # index-only shape/fist releases the mode; a palm stops globally.
            exiting = (observation.scroll_pitch is None and
                       (observation.point_shape or gesture in (Gesture.POINT, Gesture.FIST)))
            if exiting:
                self.scroll.update(None, now)
                if self._exit_since is None:
                    self._exit_since = now
                if now-self._exit_since >= self.dwell:
                    self.scrolling = False
                    self.scroll.reset()
                    self._rebase = True
                    self._last_move = None
                    self._action_latched = gesture not in (Gesture.POINT, Gesture.FIST)
                return []
            self._exit_since = None
            lines = self.scroll.update(observation.scroll_pitch, now)
            return [Event("scroll", lines)] if lines else []
        if observation.pointer_pause:
            self.rebase_motion()
        if gesture == Gesture.FIST and self._pointing_started:
            # Keep the cursor parked while the hand is lowered/repositioned.
            # First returning point establishes the new relative origin.
            self.rebase_motion()
        if gesture in (Gesture.FIST, Gesture.POINT) and elapsed >= self.dwell:
            self._action_latched = False
        events = []
        if gesture in (Gesture.POINT, Gesture.LEFT, Gesture.RIGHT):
            x = (observation.tip[0] - self.origin[0]) / self.width
            y = (observation.tip[1] - self.origin[1]) / self.height
            raw = (.5 + (-x if self.mirror_x else x), .5 + y)
            if self._rebase:
                self._offset = tuple(a-b for a, b in zip(self.cursor, raw))
                self._rebase = False
            target = tuple(max(0., min(1., value+offset)) for value, offset in zip(raw, self._offset))
            if self._last_move is None:
                self.motion.reset()
                self.cursor = target
            else:
                self.cursor = self.motion.update(target, self.cursor, now-self._last_move)
            self._pointing_started = True
            self._last_move = now
            events.append(Event("move", self.cursor))
        if gesture == Gesture.POINT and observation.thumb_tap and not self._action_latched:
            self._action_latched = True
            events.append(Event("click", "left"))
        if elapsed < self.dwell:
            return events
        if gesture in (Gesture.LEFT, Gesture.RIGHT) and not self._action_latched:
            self._action_latched = True
            events.append(Event("click", "left" if gesture == Gesture.LEFT else "right"))
        return events
