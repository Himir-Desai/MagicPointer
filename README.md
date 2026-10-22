# MagicPointer

Windows-first stereo hand pointer, with an optional macOS input adapter and a
one-/two-camera debug preview. The implementation is an initial prototype: real
Windows input, camera-rig accuracy, gesture recognition on real hands, and the
12-foot target require hardware validation. See [VALIDATION.md](VALIDATION.md).

## Install

Use 64-bit Python **3.11** on Windows 10/11. The package supports Python 3.9–3.12;
3.11 is the CI target. Open a terminal in this checkout:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m magicpointer download-model
python -m magicpointer cameras --fps auto
```

If PowerShell activation is restricted, run `.venv\Scripts\python.exe` directly
instead of `python`. Model download requires internet access once; normal camera
processing is local. The versioned official MediaPipe model is checksum-verified.

On macOS, use a compatible Python installation:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[macos]'
python -m magicpointer download-model
```

Allow camera access for the terminal/Python. Actual macOS pointer control also
needs Accessibility permission in System Settings, followed by a restart of the
terminal/app. Debug mode does not request desktop input permission. Windows uses
native input APIs, with no macOS-only dependencies in the default installation.

If OpenCV prints `not authorized to capture video (status 0)` on macOS, the
camera permission request has not completed. Choose **Allow** in the macOS
prompt, then rerun the command. If it still fails, open **System Settings →
Privacy & Security → Camera**, enable the app launching Python (such as VS Code,
Terminal, or iTerm), then fully quit and reopen that app. An IDE's integrated
terminal may use the IDE's permission rather than Terminal's. Reopen this project
and retry the debug command below. The program cannot grant itself camera access.
If permission is already enabled, check the device connection and camera index.

The initial Matplotlib font-cache message, GPU/Metal information, XNNPACK CPU
delegate message and feedback-tensor warnings do not explain this permission
failure; the model has initialized before the camera is opened.

## Compare hand models (debug experiment)

Use the [three-model setup and trial guide](docs/model-comparison.md) for the
separate `compare-models` command: **1** MediaPipe, **2** RTMPose-Hand, **3** WiLoR,
or **A** to compare identical frames. It records data only and sends no desktop
input. WiLoR has a separate CUDA environment for the RTX 4060. No filters or
adaptive sensitivity retries are used. RTMPose offers 2D joints; MediaPipe/WiLoR
also exercise the shared 3D geometry classifier.

## Try optimized WiLoR in regular debug

After the [WiLoR setup](docs/model-comparison.md), the opt-in regular debug backend
supports the normal virtual pointer/click/scroll flow:

```powershell
.\.venv\Scripts\python.exe -m magicpointer run --debug --uncalibrated --hand-backend wilor --left 1 --right 2 --fps 30 --max-hands 2
```

It uses CUDA FP16 by default on a CUDA device, batches both views, validates fresh
detections at confidence **0.50**, preserves the selected hand, and applies fixed
palm-relative thumb geometry. Append `--wilor-confidence 0.45` for the lower
threshold or `--wilor-precision fp32` for a precision reference. See the
[WiLoR debug trial guide](docs/wilor-debug.md) for timings, confirmation latency
and limitations. WiLoR is restricted to `--debug`; MediaPipe remains the default.

## Try one camera first

```sh
python -m magicpointer run --debug --left 0 --fps 30
```

This displays the primary camera, hand box/skeleton, gesture, system state,
processing FPS, and a small virtual screen. It **never moves or clicks the OS
pointer**. Gray is inactive, green active, purple click feedback, blue scrolling,
and orange unavailable tracking. The feed is the raw camera view; horizontal
pointer mapping is mirrored by default for a user facing the TV.

Every `run --debug` session now automatically records diagnostic data from start
to exit, including frames with no detected hand. A REC label appears in the
preview. On Q, Escape, window close, Ctrl+C or a handled runtime error, it saves
`diagnostics/debug-<UTC timestamp>-<unique id>.zip` and prints the archive path.
Use `run --debug --output PATH` to choose another directory. Both one-camera and
stereo debug runs are recorded; normal desktop-control runs are not recorded.

The ZIP contains `session.json`, `samples.jsonl` and `summary.json`: camera settings,
timestamps, both cameras' landmark/pose estimates when applicable, thumb/finger
metrics, accepted observations or rejection reasons, pointer state, scroll neutral
and angle, and simulated input events. Main debug sessions also include all detected
hands, local track IDs, selected owner IDs and the combined gesture geometry. These recordings currently contain no
camera images, video or audio. Data stays local; share the ZIP for diagnosis.
The uncompressed session folder is retained, and samples are flushed each frame;
a forced process kill may leave that folder without a finalized ZIP. The `tilt`
and `wrist-tilt` experiments continue saving their existing recordings; `collect`
continues recording the labelled intervals selected with Space.

Schema-2 debug archives additionally explain matching decisions: track histories,
assignment costs and rejected pairs, per-finger disagreement, engine pre/post state,
fist evidence, pause/recovery state and per-stage processing times. Session metadata
records package/model/build versions; summary gives status counts and timing
percentiles. Logging/render times are for the previous frame. Analyse an archive
with `python scripts/analyze_debug.py diagnostics/debug-YOUR-SESSION.zip`.

Fist selection counts 2.5 seconds of valid evidence. Unknown or missing samples
for up to 0.4 seconds pause the countdown without crediting that time; another
recognized gesture, a different hand ID or a longer gap resets it.

Mono preview estimates scale from palm size at activation. It cannot measure
stereo depth or establish 12-foot accuracy. The main app detects up to four hands per view by default (`--max-hands 1` through
`8` changes that limit). Hold **one fist for 2.5 seconds** to choose the controlling
hand and hear the activation chime. After selection, only that hand can control
the virtual/real pointer; other hands are ignored for input. Open the selected
hand's full palm to release it. Hold the shared palm geometry for 0.18 seconds.
The large debug banner shows the shared gesture,
fist countdown, hand lock or paused state so it can be read from farther away.

Detection list order never identifies the owner. Spatial continuity preserves
local hand IDs; ambiguous crossings or loss of every selected view pause input instead
of selecting a different hand. Tracking loss retains ownership, although input
pauses immediately without discarding activation: return the same hand near its
last tracked position to resume. Recovery does not fire a held click chord; point
or make a fist before clicking again. Scrolling captures a fresh neutral. If tracking cannot be recovered, Q/Escape and
restart lets you select afresh. This is visual tracking, not biometric identity.

## Try two cameras

```sh
python -m magicpointer run --debug --left 0 --right 1 --fps 30
```

The window shows **both feeds side by side**, with camera indices, independent
hand boxes/skeletons, handedness and finger/pose estimates. It also shows pair grab
timing and, when available, calibrated wrist range and a virtual pointer. Debug
mode sends no OS pointer, click or scroll input. Data-only recording automatically
includes both cameras in the same diagnostic ZIP; no images/video/audio are saved.

Before calibration, or if calibration cannot be loaded or does not match the
selected indices/resolution, it starts in **UNCALIBRATED TEST**. Both views now
contribute to one shared gesture decision and hand selection, and approximate
virtual pointing/clicking/scrolling can be tested without printouts. Pointer
position uses the primary view normalized by palm size; it has no metric depth.
The console and archive explain why calibration was unavailable. To force this
mode even when a calibration file exists, use:

```sh
python -m magicpointer run --debug --uncalibrated --left 0 --right 1 --fps 30
```

`--uncalibrated` is allowed only with `--debug`. After completing
calibration, restart without `--uncalibrated`: **CALIBRATED STEREO** checks wall markers
before enabling the usual fist/point/click/scroll virtual-pointer simulation.
Pair timing, hand association, depth validity and tracking-loss checks still apply.

Each camera extracts landmarks for all detected hands. A matched pair is normalized
into a common palm frame; its geometry is averaged and classified once. Independent
per-view gesture labels are only diagnostic. One usable view supplies a gesture;
two associated views contribute their aligned geometry to that same decision.
The selected hand can continue when one view loses it. Similar
same-handed hands may be ambiguous without calibration: keep only one fist raised
and separate overlapping hands. Calibrated mode additionally uses stereo geometry
to validate initial pairing and supply metric position. Without usable stereo
position, the app continues approximate relative single-camera pointer movement,
explicitly labelled with no measured depth. It rebases the cursor on source
changes and resets scroll neutral to avoid carrying angles between perspectives.
An unbound returning view joins only after a unique association with the selected
hand; a different visible hand cannot take over. Bound views' shape disagreement
is recorded, and their geometry is classified once without a gesture vote.
The shared gesture estimator is
landmark fusion, not an end-to-end trained multi-view neural network.

Use `python -m magicpointer cameras --limit 4 --fps 30` to probe camera indices,
then select the pair you want with `--left` and `--right`. Index numbers may
include built-in or virtual cameras and can change after reconnecting devices.
The feeds are labelled raw views, with pointer X mirroring controlled separately.
Q, Escape, closing the window or Ctrl+C stops both streams and saves the archive.

### Windows capture

Windows uses **Media Foundation (MSMF)** for all camera commands, including
single-camera debug, stereo debug and calibration. DirectShow support has been
removed. No backend flag is needed. For cameras at indices 1 and 2, the following
640x480 / 30 FPS configuration has user-confirmed app startup:

```powershell
python -m magicpointer run --debug --uncalibrated --left 1 --right 2 --capture-width 640 --capture-height 480 --fps 30
```

Use your actual camera indices. Confirm both displayed feeds belong to the intended
cameras: index ordering can differ between backends. The console and diagnostic
archive report the backend and actual negotiated resolution/FPS; drivers may ignore
requested settings. Startup confirmation establishes that the app opens; gesture,
tracking and distant-hand accuracy remain unconfirmed.

The same `--capture-width` and `--capture-height` options work
with `cameras` and `calibrate`. Probe indices with
`python -m magicpointer cameras --capture-width 640 --capture-height 480 --fps 30`.
For a higher-resolution trial, request `--capture-width 1920 --capture-height 1080`.
Calibrate with the backend, camera order and resolution you intend to use, then
retain those settings for calibrated runs. Recalibrate after changing capture
geometry or camera assignment. The default request remains 1920x1080; higher-resolution
Windows operation still needs live testing. macOS retains its system backend.
Existing commands with `--camera-backend msmf` remain valid on Windows.

## Prepare and calibrate the fixed stereo rig

Place both 1080p cameras near the TV with overlapping views and a rigid mount.
Use separate camera indices. Do not move either camera, change its lens/zoom, or
change capture geometry after calibration. Generic USB cameras use software-paired
frames; they are not hardware synchronized. Fast hand motion can reduce accuracy.

Generate printable targets:

```sh
python -m magicpointer targets --square-mm 25
```

Print the generated SVGs at **100% scale**, using tiled printing or a larger sheet
where necessary. Measure the print: the checkerboard has 10 × 7 squares (9 × 6
inner corners); `--square-mm` is one square's measured edge. Marker size is the
outer **black square** edge, excluding the surrounding white margin.
The default wall markers have **80 mm black squares** in muted sage and ivory
cards, with discreet I/II numbering (IDs 0/1). Print **`targets/markers-pair.svg`
on one portrait A4 sheet at 100% / actual size**, then cut out the two 130 × 134 mm
cards. Keep the full white border around each code. Individual SVGs are also
provided. Explicit `--marker-mm` sizes above 80 mm produce a larger paired sheet;
do not shrink it with fit-to-page. Smaller markers occupy fewer camera pixels,
so check both cameras can detect them at the installed distance. Moving or
resizing existing markers requires fresh calibration.

Attach ArUco markers **0 and 1** (`DICT_4X4_50`) to the opposite wall so both are
visible in both cameras. Record their black-square size and center-to-center
spacing. The example below uses 8 cm markers separated by 1 m; substitute your
actual measurements:

```sh
python -m magicpointer calibrate --left 0 --right 1 --fps 30 --square-mm 25 --marker-size 0.08 --marker-spacing 1.00
```

Move and tilt the checkerboard through both cameras' shared field of view. Press
**Space** for each of at least 15 distinct views at varied positions, tilts and
depths. Press **C** to solve. After solving, remove the board, show both permanent
wall markers, and press **Space** to verify measured size/spacing and save.
Calibration errors over 2 pixels are rejected. Use Q/Escape or close the window
to cancel without replacing the previous calibration.

The checkerboard establishes lens intrinsics/distortion and stereo pose in metric
units. Permanent markers verify the fixed setup at each startup; two marker
centers alone do not replace camera calibration. Camera-to-wall distances are
inferred from calibrated stereo geometry rather than required as extra inputs.

## Run stereo control

Preview the complete stereo path before using desktop input:

```sh
python -m magicpointer run --debug --left 0 --right 1 --fps 30
python -m magicpointer run --left 0 --right 1 --fps 30
```

With a matching `calibration.json`, debug verifies the wall markers before
allowing simulated activation. Without usable calibration, debug uses the
uncalibrated testing mode described above. Real desktop control always requires valid
calibration and marker verification. Marker verification replaces repeating the full checkerboard process
when the rig stays fixed. During use, visible markers are checked periodically;
a detected displacement stops the app and requires recalibration. Hidden markers
cannot reveal a moved rig, so keep them visible when possible.

**Q, Escape, Ctrl+C, or closing the window stops the application.** An open palm
also deactivates pointer control while keeping the application running. Camera
failures end the app with a readable error. Losing all selected views, an ambiguous
identity, invalid pair timing or a processing stall pauses input while retaining
the selected owner and activation. A single visible selected view continues
gesture recognition and approximate movement. Input resumes with the same hand, with
pending click/scroll state cleared and pointer position rebased.

## Gestures

| Gesture | Result |
| --- | --- |
| One closed fist in the shared view, held 2.5 s | Select and lock that hand; activation chime; fist wrist becomes origin; cursor centers on primary display |
| Index extended, other fingers curled | Index tip moves pointer within the local workspace |
| Index + thumb | One left click after 0.18 s of stable recognition |
| Index + middle toward screen | Enter wrist scrolling; hold steady to capture neutral automatically, then tilt up/down |
| Index + thumb + middle outside scrolling | One right click after 0.18 s of stable recognition |
| Selected hand fully open | Stop motion immediately; shared palm geometry held 0.18 s releases control; deactivation chime |

Open the fingers for a click chord together: holding thumb-only long enough is a
left click, even if you later add the middle finger. After a click, return to
index-only or a fist for 0.18 s before another click or scroll. Holding a click
pose does not repeat clicks. Unrecognized poses produce no pointer actions.

While scrolling, the pointer stays over its current target and thumb estimates
are ignored. Hold the two fingers toward the screen steadily for about half a
second on entry: this captures your comfortable neutral. Tilt your whole hand up
or down to scroll continuously; **±10 degrees** around neutral stops scrolling.
Speed increases up to 12 wheel steps/sec at 30 degrees from neutral and stays
capped beyond it. Actual distance per wheel step depends on the OS/application.
Moving your hand vertically without tilting does not scroll.

Return to index-only for 0.18 s to resume pointing. The pointer resumes at its
frozen location without jumping; subsequent finger motion moves it from there.
Exit scrolling before making a click. A fist also exits scrolling; a full palm
still deactivates control. An invalid two-finger pose pauses scrolling immediately;
after 0.30 s without valid pitch, hold steady to capture a new neutral. Tracking
loss pauses input while retaining the selected owner. A tilted straight pair takes priority over a
fist-like classifier label while scrolling, provided its pitch remains valid.

Stereo control uses triangulated finger direction in the primary camera's axes.
The one-camera debug mode previews the same interaction using model-estimated
pitch. Keep the cameras approximately level near the screen. Right-click entry
still requires the normal thumb chord; once scrolling has started, that chord
cannot click until you exit. Model thumb-estimation discrepancies during tilt
are tracked in B6; ignoring them during scrolling does not correct the classifier.

The initial interaction plane is parallel to the camera image plane, centered at
the activation fist. Resuming after scrolling shifts its mapping to keep the
pointer at its frozen location. Both whole-hand motion and index-tip motion affect it. A default
40 × 25 cm workspace maps to the primary display; depth changes do not resize it.
The cursor is driven by tip **position**, rather than a ray projected along the
finger. Ring and little fingers stay curled for pointing/clicking/scrolling.

```sh
python -m magicpointer run --left 0 --right 1 --fps 60 --workspace-width 0.50 --workspace-height 0.30
```

`--fps` accepts `auto`, `30`, or `60`. Auto requests 60, falling back to 30 when
the driver reports a lower rate. Hardware may ignore these requests; the console
reports negotiated resolution/FPS and the window reports actual processing FPS.
Two 1080p cameras can exceed shared USB bandwidth, especially at 60 FPS.

Other options: `--no-mirror-x`, `--mute`, `--model PATH`, `--calibration PATH`.
Run `python -m magicpointer run --help` for details.

## Limits and development

### Try wrist-tilt scrolling (experiment 10.1)

```sh
python -m magicpointer wrist-tilt --camera 0 --fps 30
```

Keep index and middle fingers straight and curl ring/little fingers. Let the
thumb rest comfortably; its position is ignored in this isolated wrist experiment
because it has no click actions. The normal classifier readout may say `right click`
regardless of its estimated thumb state; this does not trigger a click or cancel wrist scrolling. With the camera approximately level near the screen, point the two
fingers toward the screen/camera in a comfortable neutral direction. Hold steady
for half a second and press **Space**. This starts the simulated scroll controller
immediately; no D calibration is needed.

Tilt the **whole hand at the wrist**, keeping the fingers straight. Upward tilt
scrolls up and downward tilt scrolls down. The neutral stop zone is **±10 degrees**
from the captured direction. Speed ramps outside it to 12 simulated lines/second
at 30 degrees from neutral in either direction, then stays capped. Try holding
neutral and tilts in both directions without moving your arm through the room.
The cross stays fixed while the virtual page moves.

`--dead-zone 12` adjusts the stop zone and `--full-speed-angle 25` changes the
angle needed for maximum speed. **Space** recaptures neutral, **R** resets, and
**Q/Escape**, closing the window or Ctrl+C saves and exits. Invalid poses pause;
loss/stalls over 0.30 seconds or a handedness change require neutral capture again.

This is a **one-camera model estimate**, not calibrated stereo orientation. Depth
and direction may be unstable when fingers point at the lens. The experiment
rejects estimated directions facing sideways/away from the camera and displays
the rejection reason. Physical accuracy, camera placement and comfort need live
testing. The camera-frame depth convention is described in the
[MediaPipe landmark interface](https://developers.google.cn/edge/api/mediapipe/js/tasks-vision.landmark).

It sends no OS input and saves no images/audio/video. Share the printed
`diagnostics/wrist-tilt-...zip` with observations; it records landmarks, estimated
angle, calibration and simulated speed. The original `tilt` experiment and real
`run` uses the integrated wrist-scrolling behavior described above.

### Try finger-tilt scrolling

```sh
python -m magicpointer tilt --camera 0 --fps 30
```

This one-camera experiment moves a **simulated document** beside the camera feed.
It sends no OS pointer, click or scroll events. Use regular `run` for the integrated wrist-scrolling behavior described above.

1. Support your arm comfortably. Extend index and middle, keep them reasonably
   straight, and curl ring/little fingers with the thumb tucked.
2. Hold your fingers in a comfortable neutral position for half a second, then
   press **Space** to capture neutral.
3. Keeping the palm steady, tilt the two fingers **at their base knuckles** in
   your desired downscroll direction. Hold steady, then press **D**. Aim for
   about 15–30 degrees of comfortable tilt; at least 10 degrees is required with
   the default dead zone. This establishes direction and full-speed range for
   either hand. Whole-wrist rotation alone is intentionally ignored.
4. Return to neutral to stop. Tilt down to scroll continuously down; tilt the
   opposite way for upscroll. Tilt farther for greater speed. The yellow cross
   stays fixed over the simulated document.
5. Try holding neutral, down and up; then translate or rotate the whole hand while
   keeping the fingers fixed relative to the palm. Note unwanted drift, jitter,
   pose loss or an uncomfortable range. **R** resets calibration.

**Q/Escape**, closing the window, or Ctrl+C saves and exits. Normal classifier
results are displayed beside the experimental shape check, which allows base
knuckle tilt while still requiring extended finger chains. Invalid/one-finger/
open-palm poses stop simulated scrolling immediately. Loss of a valid shape for
over 0.30 seconds, a processing stall or a handedness change clears calibration;
capture neutral and down again when prompted.

The default neutral dead zone is 5 degrees (`--dead-zone 7` increases it). Speed
is capped at 12 simulated lines per second with 0.10-second smoothing. Calibration
captures require a steady 0.30-second window with no more than 6 degrees of range.
This is a feasibility experiment, not evidence of tracking accuracy at 12 feet.

The terminal prints a `diagnostics/tilt-...zip` containing palm-relative angles,
landmarks, normal pose classification, simulated speed, calibration key events
and summary counts. No images, video or audio are stored or uploaded. Share this
zip with your observations so tilt reliability can be evaluated before changing
the actual scroll controller.

### Record gesture diagnostics

If real poses become unrecognized when you rotate your hand, use the guided
one-camera collector:

```sh
python -m magicpointer collect --camera 0 --fps 30
```

The window guides you through six gestures at five wrist angles (30 short clips).
Use the same hand and typical room lighting/distance throughout a session. Keep
only that hand in view. For each prompt, make the requested pose **first**, then
press **Space** and hold it for three seconds. The expected pose is your manual
label, independent of what the classifier predicts; keep recording even if it
says unrecognized. Each new prompt waits for Space so transitions are not labelled
as the next gesture. **S** skips a pose; **Q/Escape**, closing the window or Ctrl+C
saves a partial session. Incomplete clips are marked in the summary.

This mode never controls the pointer. It saves no photos, video or audio and
uploads nothing. Files contain hand landmarks, timing, camera settings,
handedness, predicted versus requested poses and the classifier's joint-angle,
extension and thumb measurements. Handedness score is not gesture confidence.
The on-screen state values are 1 extended, 0 curled, -1 uncertain.

The terminal prints a timestamped `.zip` under `diagnostics/` containing
`session.json`, `samples.jsonl`, and `summary.json`. Share that archive in this
chat so the real failures can be measured and the classifier corrected. Different
distances or hands should use separate sessions. `--seconds 5` records longer
clips; `--output PATH` changes the local destination. The default diagnostics
directory is excluded from Git. Recordings can be replayed against the current classifier using
`python scripts/evaluate_gestures.py PATH_TO_ZIP`. Classifier version 2 corrects
the strict joint-angle and thumb-spacing rules identified in the first session;
see [B2 analysis](reports/B2-analysis.md) for measured improvements and remaining
limits. Live confirmation is still needed.

The requested 12-foot range (3.6576 m) is a validation target, not a measured
claim. Real control rejects wrists beyond that measured range. Resolution,
lighting, exposure, camera spacing, occlusion and model quality affect results.
Joint-angle classification is rotation invariant in landmark coordinates, but
real landmark estimation is not guaranteed at every orientation. Fingers hidden
from both cameras cannot be reliably observed.

Tests do not move the real cursor:

```sh
python -m unittest discover -s tests -v
python -m pip check
```

[FEATURES.md](FEATURES.md) tracks the eight numbered features;
[DEVELOPMENT.md](DEVELOPMENT.md) records the design and commit boundaries;
[BUGS.md](BUGS.md) preserves reported bugs. Each implementation stage is intended
to start cleanly with unavailable later features; stage commits share this final
validation phase before being recorded.
