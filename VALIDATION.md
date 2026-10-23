# Validation record

Validation date: October 20, 2026 (user timezone: America/Los_Angeles).

## Completed locally

- Host: Apple Silicon macOS, Python 3.9.6, isolated .venv. The recommended Windows
  runtime and CI target are 64-bit Python 3.11.
- The combined automated suite ran 33 tests: **32 passed, 1 skipped**. The skipped
  test inspects the native Windows SendInput ABI and runs only on Windows.
- Synthetic stereo reconstruction passed at multiple depths and room positions,
  including the requested 3.6576 m target depth. This verifies mathematics, not
  real-world landmark accuracy or camera resolution at that distance.
- Synthetic rotated/distorted camera geometry, invalid pairs, stereo solve from
  18 varied synthetic checkerboard poses, actual ArUco detection on generated
  images, wall-marker displacement and missing markers were checked.
- All six intended gesture shapes passed synthetic 3D rotation/scale checks.
  These checks do not establish recognition accuracy on real hands.
- Timing checks covered activation, centering, click chord arbitration, click
  latching, scroll entry/direction, palm stop, tracking loss, stalls and rearming.
- A synthetic single-camera application session exercised the actual rendering,
  gesture engine, state changes, chime dispatch and shutdown with OS input disabled.
  A rendered 960 by 540 preview was visually inspected for clipping and legibility.
- Mocked camera-open failures, second-device failure and disconnect paths released
  resources. CLI startup, invalid options, printable target dimensions, package
  install/entry point, byte compilation, dependency checks and whitespace checks
  were validated.
- The official checksum-verified hand model loaded with MediaPipe 0.10.32 and
  processed a blank frame successfully on this Mac. The sandbox blocked macOS
  graphics initialization, so that smoke test ran outside the sandbox without
  opening cameras or sending pointer input.
- MediaPipe 0.10.21 was replaced before delivery after newer pip detected its
  incorrect macOS wheel architecture metadata. Dependency checks pass with the
  selected 0.10.32 build. Native input avoids the initially considered mouse
  library's conflicting macOS build dependencies.

## Completed in GitHub Actions

[Validation run 39482390199](https://github.com/Himir-Desai/MagicPointer/actions/runs/39482390199)
passed on implementation commit `0758819`:

- **Windows / Python 3.11:** all 33 tests passed, including the native SendInput
  structure ABI check. Package installation, dependency checks, CLI startup,
  model download and blank-frame model inference passed.
- **macOS / Python 3.11:** 32 tests passed, with the Windows-only ABI test skipped.
  Package installation, dependency checks, CLI startup, model download and
  blank-frame model inference passed.

These hosted checks use synthetic frames and do not send real pointer events.

## Not yet validated

- Physical cameras: device enumeration, 1080p bandwidth, achievable 30/60 FPS,
  paired-frame timing, lens focus, exposure, real calibration and rig stability.
- Real-hand classification, camera association, varied user positions and hand
  orientations, occlusion, false clicks, pointer latency/jitter and scroll tuning.
- Real 12-foot recognition and pointing accuracy. The code is an initial prototype
  until these measurements are made with the actual rig.
- Native Windows cursor/button/wheel injection, DPI scaling, chimes and camera
  backend; macOS Accessibility input and actual sound playback. Native input APIs
  were implemented but no OS pointer events were sent during local validation.

## Hardware acceptance session

1. Install on the Windows target and run the one-camera debug preview. Confirm
   each gesture, state color, bounding box and orderly exit without desktop input.
2. Generate/measure targets, mount both cameras, collect varied checkerboard
   views, and verify marker size and spacing. Record baseline and RMS errors.
3. Run stereo debug. Check that bad resolution, swapped devices, moved markers,
   missing hands and unmatched pairs prevent control. Confirm fist activation
   works at several positions in the shared view.
4. Test real control on the primary display: center, edges, fine movements,
   single left/right clicks, scroll, palm stop, reactivation and camera disconnect.
5. Repeat at near, middle and 12-foot distances and varied yaw/pitch/roll. Record
   false/missed gestures, jitter, latency, processing FPS and occlusion behavior.
   Adjust thresholds only against measured results; do not label range/orientation
   support verified until this session passes.

## B1: macOS camera authorization guidance

The reported first-use camera authorization failure now provides Allow/rerun,
Camera privacy settings and launcher restart instructions. A mocked macOS failure
regression verifies this guidance and resource cleanup. Local regression run:
34 tests, 33 passed, 1 Windows-only check skipped. No system permissions were
changed; actual permission grant and successful capture require user action.

## Feature 9 / B2: guided real-hand diagnostics

Local validation: 39 tests, 38 passed, 1 Windows-only ABI check skipped. Tests
cover all six gestures/five orientations, raw measurement/classifier consistency,
missing-hand denominators, summaries, unique sessions, archive contents and
partial recording on quit. A mocked live collection exercised rendering and
cleanup without constructing desktop input; the prompt rendering was visually
inspected. CLI help and whitespace checks passed. Recognition thresholds and
pose decisions are unchanged; their metrics are now exported by the classifier.
No user hand recordings have yet been collected. B2 remains unfixed pending
labelled samples and a measured recognition correction.

## B2 correction from supplied landmark recording

The supplied archive was replayed locally without OS input. Recognition matches
improved from 373/2,592 (14.4%) to 2,553/2,592 (98.5%). All 30 labelled clips
reach the engine confirmation dwell. Left/right click, scroll and full-palm
recordings match in every frame. The 39 remaining uncertain frames are confined
to right-rolled pointing. See reports/B2-analysis.md and reports/B2-replay.json
for reproducible aggregate results and limitations. The session informed the
correction; these are not independent test accuracy figures.

Local regression suite: 43 tests, 42 passed, one Windows-only ABI check skipped.
No cameras or pointer events were used. Real-time replay, natural transitions,
false click rates, stereo control and other users still require live validation.
B2 remains open for live confirmation and remaining pointing uncertainty.

[B2 CI run 39486515772](https://github.com/Himir-Desai/MagicPointer/actions/runs/39486515772)
passed on commit `c59a8cf` for Windows and macOS with Python 3.11: package install,
dependency checks, regression suite, CLI help, model download and blank-frame
inference. These hosted checks do not establish live recognition accuracy.

## Feature 10: palm-relative finger-tilt experiment

Local regression suite: 52 tests, 51 passed, one Windows-only ABI check skipped.
New checks cover geometric invariance under whole-hand translation/rotation/scale,
calibration in both direction conventions, neutral dead zone, signed capped
speed, invalid/missing/one-finger/palm poses, tracking loss, processing stalls,
handedness changes, rejected calibration windows, monotonic timestamps and invalid
configuration. A synthetic UI session verified no desktop construction, archive
contents, resource cleanup and partial-session preservation after camera failure.
The 1200-by-720 simulated page and camera preview were rendered and visually
inspected for legibility and clipping; CLI help and whitespace checks passed.

No physical camera capture or OS pointer/scroll events were used. Calibration,
comfort, model angle jitter and usability need the user's live experiment. The
real scroll controller and pointer mapping were not modified. Tilt logs contain
landmarks, angles and calibration events locally under ignored diagnostics/.

[Feature 10 CI run 39488485036](https://github.com/Himir-Desai/MagicPointer/actions/runs/39488485036)
passed on `2da63b7` for Windows and macOS with Python 3.11, including installation,
dependency checks, tests, CLI startup and model inference. Physical-camera tilt
comfort and reliability remain to be tested by the user.

## Experiment 10.1: camera-relative wrist tilt

Local regression suite: 59 tests, 58 passed, one Windows-only ABI check skipped.
Tests cover whole-hand pitch response, yaw/translation/scale behavior, neutral
roll, captured neutral with a symmetric 10-degree dead zone, up/down speed and
capping, sideways/away/folded rejection, tracking loss, reset and invalid full-speed
angles. A mocked wrist UI session verified separate archive kind/filename,
metadata, no desktop construction and camera/tracker cleanup. Existing finger
tilt tests continue to pass. Wrist CLI help and whitespace checks passed, and a
1200-by-720 rendered preview was visually inspected for clipping and legibility.

The command is `wrist-tilt`; the old `tilt` experiment and real `run` behavior
are preserved. One steady neutral capture starts simulated scrolling, with no D
calibration. The direction estimate uses model camera-frame landmarks rather
than calibrated stereo geometry. No real camera, pointer events or near-lens
reliability tests were run; the user must evaluate foreshortening, comfort and
noise using the local wrist-tilt diagnostic archive.

[Experiment 10.1 CI run 39490932959](https://github.com/Himir-Desai/MagicPointer/actions/runs/39490932959)
passed on `c63f7aa` for Windows and macOS with Python 3.11: installation,
dependencies, regression tests, CLI startup and model inference. This does not
verify physical-camera wrist direction or foreshortened hand tracking.

## B5: wrist experiment thumb exclusion

Local regression suite: 62 tests, 61 passed, one Windows-only ABI check skipped.
The supplied 1,952-frame wrist archive was replayed through the updated controller
with its original neutral/reset key events. Accepted frames increased 586 → 938,
down command frames 2 → 96, maximum down output 2.09 → 12 lines/sec. These are
simulated output counts, not labelled intent accuracy; the recording informed
the correction. No raw recordings were committed or OS input emitted.

Synthetic tests cover open-thumb downscroll, unchanged ordinary gesture/finger
experiment semantics, retained fist/full-palm rejection and offline replay.
Remaining no-hand, folded-finger and direction failures are still rejected. See
reports/B5-wrist-analysis.md and reports/B5-wrist-replay.json for the source hash,
calibration events, exact aggregates and live-test limitations.

[B5 CI run 39492043757](https://github.com/Himir-Desai/MagicPointer/actions/runs/39492043757)
passed on `91c798b` for Windows and macOS with Python 3.11: installation,
dependencies, regression tests, CLI startup and model inference. Live wrist
tracking and intended-direction accuracy remain to be confirmed by the user.

## B5 live confirmation

The user reports that wrist-tilt-20261020T203236Z-0dbdfdbb.zip looks good. Replay
exactly reproduces recorded counts, speeds, rejection totals and both neutral
captures. The 815 live-mode frames include 799 valid frames (98.04%) and 16
finger-chain rejections. Outputs include 275 down, 288 up and 236 stop frames;
both directions reach 12 lines/sec. Longest continuous down/up commands are
7.43/6.84 seconds. No thumb-related rejection remains. See
reports/B5-live-confirmation.md and reports/B5-confirmation-replay.json.

This validates the reported fix for one user/session, not general gesture
accuracy or stereo/12-foot/OS-scroll behavior. Runtime code and thresholds were
unchanged; no new unit or UI tests were run for this documentation-only review.

## Feature 7: integrated wrist scrolling; B6 thumb investigation

`run` now replaces translation scrolling with automatic-neutral wrist-rate
scrolling, using the experiment's shared 10-degree dead zone, 30-degree full-speed
angle and bounded 12-step/sec response. Stereo uses triangulated index/middle
direction after both model shapes pass; mono debug uses estimated pitch. Scroll
mode freezes the pointer, ignores thumb labels and suppresses clicks. Index-only
or fist exits; pointer mapping rebases on resume. Valid straight-pair pitch takes
priority over fist-like labels during tilt. Palm stop, timing/depth/hand-identity
checks, tracking-loss deactivation and normal clicks outside scroll remain.

Final local checks: 74 tests run, 73 passed, one Windows-only ABI check skipped.
Coverage includes automatic neutral, dead zone/rate cap, up/down wheel sign,
30/60-Hz accumulation, thumb-label changes, invalid-pitch pause/recalibration,
mode exit without pointer jump, click rearming, palm/tracking-loss stop, stereo
pitch from reconstructed geometry, invalid depth/hand mismatch, and the main
preview/render/dispatch loop without desktop input. Dependency check, CLI startup
and diff whitespace checks passed. Main scroll preview was rendered and visually
inspected. The real model blank-frame smoke initially could not create a graphics
context inside the sandbox; rerunning outside it passed without opening a camera.

Latest user archive through the main engine after seeded activation/scroll entry:
1,048 frames, 90 up wheel steps, 101 down, zero click events and zero pointer
moves; one later tracking-loss deactivation. This is a replay of unlabelled model
landmarks, not intended-direction accuracy. Experiment Space/reset events are not
main-app controls and are ignored after seeding. It does not validate actual mode
entry, stereo camera noise or OS/application scroll distance. Synthetic tests
cover entry and exit; physical stereo and live automatic-neutral checks remain.
See reports/7-scroll-replay.json and reports/B6-thumb-estimates.md. B6 remains open;
no ordinary click-classifier threshold has been changed.

[Feature 7 CI run 39494816348](https://github.com/Himir-Desai/MagicPointer/actions/runs/39494816348)
passed on `fe2a60c` for Windows and macOS with Python 3.11: dependency installation,
regression suite, CLI startup, official model download and blank-frame inference.
Physical stereo cameras and live OS scrolling were not exercised by CI.


## Features 6/7 clarification: B7 entry timing and fresh neutral

Read-only deterministic engine probes with 20-ms samples confirmed one right-click
for simultaneous index/middle/thumb recognition and for an 80-ms two-finger
intermediate. A 240-ms two-finger intermediate latched scrolling first and emitted
no click when the thumb chord followed. This is B7; no runtime fix is included.
Separate entries at +18 and -12 degrees captured +18 and -12 as their respective
neutrals, confirming reset on every entry. Neutral uses at least 300 ms of stable
samples after mode entry, rather than a persisted angle or the first frame alone.
No camera/OS input or full regression suite was run for this documentation-only
clarification; the probes used the unchanged, previously validated engine.

## Feature 11: automatic main-debug diagnostic recording

All valid `run --debug` sessions now create a unique local debug directory and
record continuous samples for mono or stereo preview. Existing tilt experiment
recordings and labelled collection intervals retain their formats. The common
diagnostic-data component is implemented independently of the pending user choice
about additionally saving camera video (subsequently resolved as data only). No
image/video/audio capture was added.

Local checks: 80 tests run, 79 passed, one Windows-only ABI test skipped. New
coverage checks full-session recording including no-hand frames, actual simulated
scroll events and neutral changes, both-camera data and rejection reasons,
nonfinite landmark serialization, flushed samples before close, idempotent
archiving, Ctrl+C/capture/model errors, resource cleanup when archiving fails,
and no recorder for normal desktop-control runs. An existing camera-failure
fixture was updated to supply realistic camera metadata. CLI help and whitespace
checks passed. A synthetic main-preview frame was rendered and visually inspected
for the REC indicator. No live camera capture, OS input or disk-throughput/long-run
performance measurements were performed. Data is flushed per frame; a hard kill
may leave the session folder without its final ZIP.

[Feature 11 CI run 39495901172](https://github.com/Himir-Desai/MagicPointer/actions/runs/39495901172)
passed on `9d8547b` for Windows and macOS with Python 3.11, including installation,
dependency checks, regression tests, CLI startup, model download and blank-frame
inference. Live recording performance and optional camera-video recording remain
outside these checks. The user subsequently confirmed data-only recording; no
video is requested and no runtime change is needed.

Feature 11 clarification: data-only preference confirmed. Documentation and ledger
updated; whitespace checks passed. No tests rerun for this documentation-only
confirmation; runtime remains the CI-validated implementation above.

## Feature 12: two-camera debug preview and calibrated stereo simulation

Two-camera debug now renders both raw feeds side by side with per-view hand
boxes/skeletons, camera indices, handedness/pose/finger estimates, pair grab skew
and calibrated wrist range/virtual pointer when available. Missing, invalid,
wrong-index or wrong-resolution calibration leaves a labelled preview without
joint pointer simulation. Valid calibrated mode retains wall-marker, timing,
hand agreement, depth and tracking-loss checks. Normal desktop control still
requires calibration. Both preview modes record only diagnostic data.

Local final checks: 86 tests run, 85 passed, one Windows-only ABI check skipped.
New end-to-end synthetic coverage exercises both feeds and trackers, all four
calibration-preview fallbacks, marker/hand/timing rejection with visible feeds,
calibrated metric activation and pointer simulation, two-stream archive contents,
partial capture-error archiving and cleanup, and strict real-control calibration.
Existing mono debug, scroll and recording regressions also passed. CLI help and
diff whitespace checks passed. Synthetic pre-calibration and calibrated panels
were rendered and visually inspected for legibility, layout and virtual pointer.

A live macOS smoke test opened camera indices 0 and 1 simultaneously at negotiated
1920x1080 and approximately 30 FPS, initialized both real trackers, displayed 18
pairs, saved a data-only archive and closed successfully. Desktop construction was
explicitly blocked in the test. The archive was checked for exactly the three JSON
files, 18 two-camera samples, no accepted observations/events in uncalibrated mode,
no image recording and normal termination. The local archive is
`diagnostics/debug-20261021T230215Z-300b51ff.zip` (not committed). A separate probe
found usable indices 0-3; these are device indices, not verified physical model
identities. The user should select the intended pair by viewing their feeds.

There is no calibration.json for this rig, so live calibrated depth/gesture
accuracy, wall-marker acceptance, long-run throughput and Windows hardware have
not been established by this prompt. Calibrated mode is covered with synthetic
stereo geometry and mocked marker results; actual marker geometry retains its
existing unit coverage. No camera images or video were saved.

[Feature 12 CI run 39690791082](https://github.com/Himir-Desai/MagicPointer/actions/runs/39690791082)
passed on `06fc40c` for Windows and macOS with Python 3.11: dependency installation,
regression suite, CLI startup, model download and blank-frame inference. The live
macOS preview test above additionally exercises real simultaneous capture;
calibrated stereo hardware accuracy remains unverified.

## 3.1 / 4 revamp / 12.1 / B8: readable shared gestures and one-hand ownership

Main debug now displays a large shared gesture label and a separate fist-countdown,
locked-hand or paused status banner. Main capture detects up to four hands per view
(configurable 1-8); local spatial tracking preserves IDs independently of model
list order. One continuous matched fist held for 2.5 seconds selects the owner and
emits the activation chime. Input uses only that owner until its palm releases it.
Tracking loss pauses/deactivates input but retains ownership; other hands do not
get to activate or release an existing lock. Ambiguous crossings/pairs pause.

Both camera views are normalized into a palm coordinate frame, their landmark
geometry is averaged, and the gesture is classified once. Raw per-view gesture
labels remain in the small diagnostics and recording; they are not independent
input decisions. Both views must support an unambiguous match, with no one-view
fallback (user-confirmed). Handedness, shape consistency and temporal continuity
support association before calibration; calibrated mode also validates stereo
anchors. These are heuristic tracking/association checks, not biometric identity
or a trained multi-view gesture network. Similar same-handed hands can require
separation before a match becomes unambiguous.

Uncalibrated debug now permits shared-gesture activation and simulated pointer,
click and wrist-scroll events without printouts. Position is primary-view image
space normalized by activation palm size; this does not estimate metric depth.
`--uncalibrated` explicitly forces testing even with an existing calibration file.
The flag cannot enable real OS input. Normal desktop control retains calibrated
stereo geometry and wall-marker checks. Session archives now include every detected
hand, track IDs, candidate/owner IDs, selection progress and combined geometry.

Validation checkpoints:

- Tracking/fusion foundation staged tree: tested in an isolated snapshot of the
  previous commit plus staged component changes, 96 tests run, 95 passed, one
  Windows ABI skip. This confirms that rollback checkpoint still runs with the
  original application/fixtures. No intermediate integration files were included.
- Final integration: 100 tests run, 99 passed, one Windows ABI skip. Coverage adds
  view rotation/scale/translation normalization, shared classification independent
  of raw pose labels, required two-view evidence, model multi-hand extraction and
  legacy single-hand compatibility, ID order changes, ambiguous crossings, unique
  fist selection, palm release, selection after loss, and uncalibrated bypass guards.
- An end-to-end two-camera scene switches the fist between hands before the dwell,
  locks only after a continuous 2.5 seconds, ignores the other hand's palm, pauses
  when the owner's second view disappears, resumes the same IDs, releases on the
  owner's palm and then selects the other hand. No click originates from distractors.
- Countdown and locked/shared-point panels were rendered from synthetic data and
  visually inspected. The main banner is substantially larger than per-view text;
  paused state and no-metric-depth labels remain separate. CLI help and whitespace
  checks passed. CI model smoke now initializes the four-hand model configuration.
- Live macOS capture/model/render/archive smoke: cameras 0 and 1, 1920x1080, about
  30 negotiated FPS, two four-hand trackers, 24 displayed pairs, normal exit and
  data-only archive. Desktop construction was explicitly prohibited. The archive
  contains both-camera hand lists and selection diagnostics, but no hands were
  detected during this short test. It does not establish live gesture accuracy,
  owner recovery under occlusion, audible chime acceptance or long-run latency.

The live local archive is `diagnostics/debug-20261021T233028Z-b47554b5.zip` and is
not committed. B8 remains open for actual multi-hand confirmation. B6 thumb-estimate
accuracy and B7 click/scroll entry timing were not independently changed by this
work. Calibrated hardware/12-foot acceptance remains pending.

[Ownership/fusion CI run 39694283068](https://github.com/Himir-Desai/MagicPointer/actions/runs/39694283068)
passed on integration commit `98f6295` for Windows and macOS with Python 3.11:
installation, dependency checks, complete regression suite, CLI startup, official
model download and real four-hand model blank-frame inference. The watcher briefly
lost its network connection; the final run/job API result independently confirmed
success for both jobs. No test rerun or code correction was needed. Live hand
selection and fusion accuracy remain pending user testing; B8 stays open for that
confirmation. Rollback foundation commit `60c9be8` was separately snapshot-tested.

## B9 / B8 / 11.1: recorded reliability failures and advanced diagnostics

The user reports both selection and gesture-action failures in
`diagnostics/debug-20261021T234500Z-bd89e971.zip`. Analysis and reproducible aggregates
are in reports/B9-reliability-analysis.md and reports/B9-debug-analysis.json. The
1,086-frame, 142.34-second session runs about 7.75 processing FPS, rejects 105
camera pairs, and records five activations followed by five tracking-loss stops.
One missed frame can exceed the old 0.30-second loss timeout at that loop rate.
A nearby owner handedness flip and blocked click estimates also appear; the data
has no intended-gesture labels/images to establish true physical identity or
recognition accuracy. Raw recordings and landmarks were not committed.

Corrections keep activation with the selected owner through invalid/rejected
views, immediately suppress input, and resume without fist rearming. Recovery
clears click/scroll state, rebases pointing and reacquires scroll neutral. Initial
selection preserves but does not credit valid fist evidence across unknown/missing
gaps up to 0.4 seconds; known other gestures or identity changes reset it. Bound
owner label flips are accepted only within 0.75 palm lengths with a soft penalty
and unchanged uniqueness tests; unbound matching stays strict. The user confirmed
immediate release when both raw camera estimates and fused result agree on a
matched full palm; other palm evidence retains the 0.18-second confirmation.
Rejected camera pairs cannot release the owner. The pair timing limit and no
one-camera-fallback policy are unchanged.

The isolated control replay seeds both policies at the same first activation and
feeds identical recorded selected observations. Legacy reproduces every original
event: 5 activations, 58 moves and 5 tracking-loss stops. Retained-owner control
has no tracking-loss stops; recorded palm evidence produces 3 palm stops, with
4 activations and 117 moves. Activation grace is disabled in both isolated replay
policies. These are controller outputs, not intended-direction or gesture accuracy;
identity reassociation and new palm-consensus selection are not replayed there.

New data-only debug archives use schema 2: tracking history/cost/rejection and
assignment traces, all pair candidates and ambiguity margins, per-finger/landmark
disagreement, palm-release evidence, pre/post engine state, valid fist evidence,
pause/rebase/latch state, image-space hand size, per-phase timings, and model,
package/source fingerprints. Logging/render timings describe the preceding frame;
summary reports median/p95/max durations and status counts. No images/video/audio,
credentials or environment values are stored. The analyzer accepts schema 1/2.

Final isolated fix-branch validation: 112 tests run, 111 passed, one Windows ABI
skip. The earlier shared checkout also passed 114 tests, including two unrelated
marker-styling tests; those marker changes are excluded from this fix branch. New tests
cover low-FPS one-frame gaps, long loss with held click chords, no-jump recovery,
fresh scroll neutral, evidence grace/reset, nearby owner label flips without remote
hand takeover, immediate two-view palm release, held single-view/uncertain release,
no palm release on a rejected pair, and advanced archive/reporter fields. Existing
hand-order, crossing, multi-camera fusion, legacy engine and diagnostics tests
remain passing. The main synthetic paused panel was visually inspected. Whitespace
checks passed. No new dependency or global classifier threshold changes were made.

A bounded live macOS smoke opened both four-hand trackers/cameras, displayed 18
frames and saved `diagnostics/debug-20261022T000107Z-690d7448.zip` normally. Its ZIP
has only the three JSON files and contains new timing/decision fields, schema 2,
source/model metadata and no images. This short startup had no hand detections;
it does not validate live gestures. Illustrative no-hand phase medians: capture
49.70 ms, camera inference 21.80/11.36 ms, preceding render 15.81 ms and preceding
logging 0.11 ms. Those measurements are not a benchmark of the user's hand session.
B9's forced-rearming control fault is fixed; B8 remains open for live owner/fusion
confirmation. A new user session is needed before claiming broad reliability.

Windows and macOS CI passed for isolated fix commit `3832f8d` in
[run 39697441435](https://github.com/Himir-Desai/MagicPointer/actions/runs/39697441435).
Both jobs completed installation/dependency checks, the full regression suite,
CLI startup, official model download and real four-hand blank-frame inference.
The shared checkout switched externally to the printable-marker branch during
development; its commits were preserved. The reliability-only commit was copied
into an isolated worktree on `fix/ownership-reliability-diagnostics`, tested there
and pushed without including the marker styling or rewriting either branch.

## Main integration checkpoint before B10 distance investigation

Combined the completed app and printable-marker branch with the reliability fix
and its CI record. Merge conflicts were confined to documentation; preserved
marker history and the newer validation results. Integrated local regression suite:
114 tests run, 113 passed, one Windows ABI skip. Whitespace checks passed. No
runtime behavior changed during integration. B10 is recorded as unmeasured and
open; this checkpoint does not claim that far-distance detection works.

Windows and macOS CI passed on main integration commit `d50562f` in
[run 39698466522](https://github.com/Himir-Desai/MagicPointer/actions/runs/39698466522).
Both jobs passed dependency checks, regression tests, CLI startup, model download
and real blank-frame inference. Preliminary B10 analysis is recorded in
reports/B10-distance-analysis.md using the exact archive confirmed by the user;
no distance fix is included in the validated main checkpoint.


## B13 Windows simultaneous camera startup

User reports each external camera works alone, but whichever opens second fails
under DirectShow, even with requested 640x480/30 FPS and separate laptop ports.
The Media Foundation diagnostic returned valid frames from both camera indices.
This supports an explicit MSMF workaround; it does not identify a specific driver
or USB fault or establish 1080p operation.

Added --camera-backend and requested capture dimensions to run, calibrate and
camera probing. The default policy remains DirectShow on Windows and the system
backend elsewhere. Both streams use the selected backend, and MSMF negotiates
its format without forcing MJPG, matching the successful diagnostic. Actual
backend and negotiated size/FPS are included in capture metadata. README documents
camera assignment and calibration consistency after switching capture settings.

Local final validation: 120 tests run, 119 passed, one Windows-only ABI skip;
`python -m pip check`, run/calibrate/cameras help and `git diff --check` passed.
Regression checks cover both streams using MSMF, default Windows/macOS selection,
rejected settings/platform combinations, release on second-open failure, camera
probe routing and the full synthetic low-resolution debug path. Windows capture
calls are mocked locally. Full Windows debug preview, physical feed identity,
long-running simultaneous capture and higher-resolution behavior need live retest.


## B13 Windows default and startup confirmation

User confirms that the full debug app now opens with MSMF on Windows, explicitly
without claiming correct gestures, pointing, scrolling, tracking or other runtime
quality. B13's opening failure is fixed; broader feature acceptance remains pending.

MSMF is now the default for every Windows Cameras caller, including one-/two-camera
run, calibration, camera probing and the diagnostic/tilt tools. Removed DirectShow
selection and its format setup on Windows. Explicit --camera-backend msmf commands
remain valid. macOS uses the same system backend and format setup as before.
Resolution defaults remain 1920x1080; README's user-confirmed startup command requests
640x480/30 FPS without a backend flag. No 1080p Windows claim is made.

Final local validation: 120 tests run, 119 passed, one Windows ABI skip. The default
Windows pair test verifies both captures use MSMF without forcing MJPG, reads both
streams and releases both. Default second-open failure cleanup and low-resolution
debug/probe routing pass; removed dshow settings are rejected. macOS capture remains
covered. pip check, all three capture-command help checks and git diff --check pass.

User authorized merging into main and updating branches. All other existing local
and remote feature/fix branches were already ancestors of this work; they contain
no independent active changes to update. The B13 branch is to be retired after main
is pushed, with historical branches/worktrees preserved.


Windows and macOS CI passed for default-change commit `a63b0f2` in
[run 39704393639](https://github.com/Himir-Desai/MagicPointer/actions/runs/39704393639).
Both jobs passed dependency checks, the regression suite, CLI startup, official
model download and real blank-frame four-hand tracker inference. Camera calls
remain mocked in CI; the user's confirmation covers live app opening only.


## Feature 13: debug-only adaptive detection; B14 swap evidence

The supplied swapped archive records [2,1], both MSMF 1920x1080 / 30 FPS.
Camera index 2 still has fewer samples with detections: 1,002/1,516 (66.09%)
versus index 1 at 1,186/1,516 (78.23%). See reports/B14-camera-comparison.md.
This supports a camera/view effect; no images distinguish focus, lighting,
occlusion or device hardware. The two sessions are not identical labelled poses.

User chose a debug-only experiment. --adaptive-detection requires two-camera
--debug and remains opt-in. Both normal 0.65 detectors run every sampled pair.
Exactly one nonempty regular view cues a missing-view IMAGE detector at 0.50
palm-detection/presence thresholds, at most one attempt per 0.25 seconds per view.
Lower-threshold candidates use the current image only. Existing hand ownership,
shape/timing matching and calibrated geometry checks remain mandatory. No one-view
input fallback, edge filtering or desktop-control adaptation is introduced.
Missing selected-owner cases where another raw hand is present are not retried.

Data-only logs retain baseline hands, effective hands and detection source,
retry outcomes/configuration, added inference time and counters. Analyzer output
separates baseline/effective availability and candidate/observation counts. None
of these metrics establishes intended-hand or gesture accuracy. Additional model
initialization/inference can reduce FPS; candidates may add false detections.

Final local validation: 129 tests run, 128 passed and one Windows-only ABI check
skipped. Tests cover symmetric missing-view retries on actual current-frame
objects, cooldown without stale candidates, no retry for both/neither detections
or bad timing, mismatched-hand rejection, failure cleanup, debug-only gating,
synthetic full-app logging/analyzer integration and fresh IMAGE inference routing.
Dependency check, CLI help and git diff --check passed. Real model VIDEO (0.65)
and IMAGE (0.50) CPU blank-frame inference both passed. The initial sandboxed
model smoke could not initialize macOS OpenGL; the same no-camera check passed
outside the sandbox. CI now includes real IMAGE-mode model initialization/inference.
No live camera trial, false-positive measurement or ten-foot benefit is claimed.

User subsequently explicitly authorized publishing. Commit 34fdd7a was pushed
to origin/feat/adaptive-debug-detection; CI run 39713215389 was in progress at
publication. Local validation above is complete.
## B15 Gesture stability under landmark jitter

Synthetic anatomical hands (relaxed pointing fingers, loosely curled others) were
jittered per landmark in two views and run through fusion, ownership-equivalent
stabilization and the engine with the app's retained-owner settings. Previous and
revised code ran the same scripts. A session holds a fist, then point, left,
point, right, point; it succeeds with exactly one left then one right click.

| Landmark jitter | Previous success | Revised success | Activation median (2.5 s hold) |
| --- | --- | --- | --- |
| 3 mm | 96% | 100% | 3.0 s → 2.6 s |
| 4 mm | 42% | 96% | 3.4 s → 2.8 s |
| 5 mm | 2% | 63% | 4.0 s → 3.1 s |
| 6 mm | 0% | 14% | 5.1 s → 3.7 s |

Holding point or two-finger poses (without latched scrolling) for 33 simulated
minutes per condition produced no false clicks before or after, at 5 and 6 mm.
Variants that resumed dwell across a different pose, credited bridged frames, or
used a symmetric thumb margin did produce false clicks and were rejected; see the
report. Local regression run (Python 3.11): 146 tests, 145 passed, 1 Windows-only
check skipped. Real-hand and live validation remain pending.

## 14 Real-time pipeline audit and B16

Full debug-loop benchmark with real MediaPipe detection on 1080p frames and two
simulated free-running 30 FPS cameras with one-frame buffers: 27.7 → 30.0 FPS
(camera-limited), median frame age at detection 25.0 → 11.9 ms (p95 46.6 → 23.3
ms). With Windows' default ~15 ms `waitKey` modelled before and the 1 ms timer
after: 17.1 → 30.0 FPS. Two 1080p detections take 32.7 ms sequentially and 16.7
ms in parallel. Wall-marker checks measured 5–122 ms per 1080p image and now run
in the background (B16).

New tests cover newest-frame capture without repeats, pair catch-up, background
reopening and the 5 s give-up error with simulated devices; smooth pointer glide,
exact click landing, settled-pointer idling, fine scroll draining and background
error reporting; crop recovery mapping, clamping, gating, expiry, duplicate
suppression and ownership continuity; marker-check debouncing and non-blocking
checks; parallel detection order and timing; and an uncalibrated one-camera real
control session that activates, moves the patched desktop pointer and clicks once.
The previous test that rejected real uncalibrated control now checks it starts
without loading calibration. The adaptive-detection log test now
runs with `--no-crop-recovery` to keep that experiment isolated.

Local regression run (Python 3.11): 168 tests, 167 passed, 1 Windows-only check
skipped. `pip check`, CLI help and both blank-frame tracker checks pass. Not
validated: real cameras, Windows timer and input behaviour, macOS pixel
scrolling, and crop recovery on real distant hands.

## 6.1 Index + little finger right click (resolves B7)

Right click is now index and little finger extended with middle and ring curled,
thumb ignored; the thumb + index + middle chord is unrecognized. Synthetic
jittered two-view sessions through fusion, stabilization and the engine:

| Landmark jitter | Exactly one left + one right click (previous chord → new) |
| --- | --- |
| 4 mm | 96% → 99% |
| 5 mm | 63% → 80% |
| 6 mm | 14% → 33% |

Holding point, two-finger and fist poses for 33 simulated minutes per condition
at 4, 5 and 6 mm produced no false clicks. A half-raised ring finger is
unrecognized on a fresh hand and keeps an established right click. Local
regression run (Python 3.11): 170 tests, 169 passed, 1 Windows-only check
skipped. Live comfort and detection of the little finger at distance are pending.

## B17 Owner timeout

A selected owner with no usable matched pose for `--owner-timeout` seconds
(default 5) is released. Unit checks: the owner is kept at 4.9 s missing and
released at 5.1 s, while another visible fist only becomes a new candidate at
zero progress; returning before the timeout restarts it; `0` keeps the owner
through 60 s missing. End-to-end debug loop: with a 0.5 s timeout, fist,
absence and a second fist give activation, release, reactivation and exit
chimes; with `0` the returning hand resumes silently as the same owner. Local
regression run (Python 3.11): 173 tests, 172 passed, 1 Windows-only check
skipped. Live behaviour with real hand exits and re-entries is pending.
