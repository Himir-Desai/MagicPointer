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


## 12.2: Available-view geometry and approximate pointer continuation

The user explicitly supersedes the earlier mandatory two-view/no-fallback policy
and chooses approximate single-camera pointer continuation. The estimator already
aligned/averaged landmarks; it now uses valid available geometry, classifies once,
and records contributing views and residuals. Bound identities no longer require
shape agreement or independent gesture labels. View count/residuals are evidence,
not calibrated confidence probabilities. Fused palm geometry confirms release
at 0.18 s; per-view palm labels no longer trigger immediate release.

One-view fist selection is supported. An unbound perspective joins only through
unique shape association (or calibrated geometry); another hand cannot take over
when the known view disappears. Ambiguous identities still pause. Normal desktop
control still requires valid calibration, both capture devices and verified wall
markers. Pair timing and measured positions beyond the 12-foot target remain
rejected. No input behavior has been physically confirmed on Windows.

Without usable stereo position, a visible selected view supplies relative image
motion at 0.10 nominal control metres per captured palm length, with no measured
depth claim. Source changes rebase the existing cursor and reset scroll neutral.
The preview and per-frame `position_source` distinguish this from stereo position.
This mapping is approximate and does not solve distant-camera raw detection.

Local regression validation covers aligned 3D fusion with misleading independent
labels, bound shape disagreement, missing/invalid views, unique second-view joining,
ambiguous/no-takeover cases, single-view activation, fused-palm dwell, real app
render/engine/log paths, cursor continuity across stereo/left/right/stereo, and
mocked desktop dispatch with one detecting view. Camera frames and OS adapters
were synthetic/mocked; no real desktop input was sent. Live control/accuracy and
Windows acceptance remain pending.


## 16: Switchable MediaPipe / RTMPose-Hand / WiLoR debug experiment

`compare-models` is a separate preview with 1/2/3 model switching, A for identical
frames across enabled backends, H/N/U presence labels, D near/far labels and
automatic data-only JSON/JSONL/ZIP output. It has no OS input or virtual pointer.
MediaPipe and WiLoR exercise the shared 3D gesture estimator/selection; RTMPose
is explicitly a 2D joint/detection comparison without fabricated depth. All models
receive original BGR frames plus their own native preprocessing; no classical
filters or adaptive threshold retries are present.

MediaPipe keeps CPU VIDEO 0.65 detection/presence/tracking settings and independent
trackers per camera. RTMDet-nano 320x320 + RTMPose-m Hand5 256x256 uses rtmlib
0.0.13/ONNX Runtime 1.19.2 CPU and official checksummed model archives. An empty
RTMDet result skips RTMPose's whole-image fallback. WiLoR uses pinned WiLoR-mini
`ebec42f94c389070cdd7dda6fd1bf0b4a659c960`, PyTorch 2.5.0 float32, an isolated
worker environment and in-memory raw-BGR transport. Its CUDA mode fails clearly
if CUDA is unavailable; local checks used CPU. Native GPU work is synchronized
for inference timing. Upstream auto-installation is disabled; the concrete dill
dependency discovered by loading detector.pt is now in requirements-wilor.txt.
Legacy chumpy aliases are confined to the worker. Hashes of the large assets are
streamed rather than loading extra GB into memory. Assets/environments are ignored
by Git and no weights or external demo images are committed.

The final batched local suite ran **141 tests: 140 passed, one Windows ABI skip**.
It covers actual render/engine/archive paths with synthetic camera input, all
available-view regression cases from 12.2, switch/same-frame behavior, absent-3D
handling, false/no-detection denominators, trial-boundary gap resets, worker raw
byte transport and cleanup, duplicate-camera rejection and no desktop creation
for the comparison command. Both environments pass pip check. CLI help,
compilation (with writable /tmp bytecode cache) and git whitespace checks pass.
Initial compilation only failed because macOS selected a cache outside the
sandbox; the explicit writable cache check passed.

Real-model validation used a black 640x480 image and the pinned upstream
WiLoR-mini assets/img.png. The positive image ran in both view slots (duplicate
demo images, not physical stereo); the blank image used the primary view slot. All model outputs had finite 21x2 original-image joints;
MediaPipe/WiLoR supplied finite 21x3 native joints, RTMPose supplied no 3D. Hand
counts on that one positive image were MediaPipe 2/2, RTMPose 1/1, WiLoR 2/2.
The blank image produced 0/1/0 hands respectively: RTMPose's false detection is
recorded as B15, without hiding it or tuning a threshold during comparison.
These are adapter smoke checks, not a model-quality ranking. The six-cell actual
model preview was rendered and visually inspected. No user camera images,
video/audio, real cameras or desktop input were recorded or used in these checks.

Windows Python 3.11 installation, RTX 4060 CUDA execution, sustained two-camera
performance, near/far landmark accuracy, identity recovery and the new approximate
control policy still require the user's live trial. No replacement for MediaPipe
is selected. See docs/model-comparison.md for setup, controls, caveats and sources.


## 17: Optimized WiLoR in regular debug (B17/B18/B19)

The user approves the recommended optimization/validation/fixed-geometry approach,
chooses detector confidence around 0.45–0.50 and explicitly declines training.
Added opt-in `run --debug --hand-backend wilor` on feat/wilor-debug. This uses the
normal selection/virtual pointer/click/scroll/palm/log loop; a guard rejects WiLoR
without --debug before initializing a model, camera or Desktop. MediaPipe remains
the default; the comparison experiment keeps its original 0.30/FP32/legacy-rule
baseline. Existing dependency environments/weights are reused.

The optimized worker uses CUDA FP16 by default (auto selects FP32 on CPU), batches
detector views, and collects all validated hand crops into one pose-model forward.
Bound views reconstruct only the uniquely associated selected hand. The native
BGR crop/padding/antialias/projection behavior is retained; mesh computation still
happens internally, while only joints/camera parameters are copied back to CPU.
One raw frame pair travels through the existing isolated worker in memory, with
no image recording and no stale landmark fallback. Legacy comparison requests
keep their original writable copy; the optimized path uses read-only raw views.

Default confidence is 0.50; --wilor-confidence 0.45 is supported. New candidates
need unique continuity and at least two fresh observations spanning 0.08 s;
missing/repeated frames do not supply evidence. Selection uses the existing local
IDs plus a conservative box gate; ambiguity pauses rather than replacing the
owner. Nonfinite/degenerate geometry is rejected. These measures do not guarantee
rejection of a persistent high-confidence object with plausible reconstructed
joints, and raising the threshold can reduce recall of real distant hands.

The WiLoR-only fixed thumb profile combines index-side palm extent, outward chain
direction, thumb bend and 3D distance to finger chains. It uses stronger entry
than exit thresholds and fresh thumb-opening confirmation. Literal projected
intersection is neither required nor treated as physical contact. A straight
thumb inside/across the palm remains tucked; ambiguous geometry stays unknown.
No model is trained. Two associated views still contribute geometry to one
classification; independent gesture labels are not votes. Open-thumb confirmation
adds latency before the existing action dwell. Data-only logs retain model/profile,
raw thumb metrics, filter state, scores, validation decisions and stage timings.

Final batched local suite: **158 tests run; 157 passed, one Windows-only ABI skip**.
Coverage includes six fixed poses through rotations/reflections/scales, a straight
across-palm false-click mechanism, 3D contact versus projected overlap, segment
distance edge cases, ambiguous/open/closed thumb transitions and stale/identity
resets; 0.45/0.50 candidate filtering, temporal confirmation, selected-hand-only
work and ambiguity; one-forward crop routing and left-hand coordinates; real
binary two-frame worker transport; normal-debug activation, pointing, both clicks,
palm release, one-view loss, error archive finalization and worker cleanup. Default
MediaPipe/control/calibration/ownership/scroll regressions pass. After restoring
the legacy writable input, targeted comparison (7) and WiLoR debug (6) tests also
pass. Both environments pass pip check; CLI help, bytecode compilation with a
writable cache and whitespace checks pass. No native OS input was sent.

Actual-weight CPU validation (Python 3.9.6, PyTorch 2.5.0, upstream pinned demo
image duplicated across views): the first unconfirmed pair performs no pose
forward; the confirmed pair makes one forward with four crops, and bound owner
contexts make one forward with two crops. A subsequent blank pair gives no old
or replacement geometry; one-view inference also passes. Against the pinned
wrapper's serial predict_with_bboxes path on the same selected crops, maximum
pixel difference is 0.00008414 and native 3D difference is 1.49e-8. This checks
implementation parity, not true joint accuracy. CUDA availability/device-name and
pipeline creation were separately mocked to verify auto selects torch.float16
and CPU FP16 is rejected; no actual GPU kernels were run here.

An actual optimized subprocess completed a five-frame normal-debug session using
mocked cameras and the upstream demo image. The real render/log/cleanup path
passed, produced only session.json/samples.jsonl/summary.json in its ZIP, identified
CPU/FP32/0.50/WiLoR hashes, included profile/stage/validation data and used no
MediaPipe tracker or Desktop. The 1280x900 preview was rendered and visually
inspected. This was not a physical camera, Windows CUDA or intended-pose trial.

RTX 4060 FP16 numerical behavior, Windows sustained two-camera FPS, far-hand recall,
false-hand reduction and natural pointing/left-click separation remain pending
user testing. B17/B18/B19 remain open for live acceptance; there is no promised
FPS or desktop promotion. Commands and limits are in docs/wilor-debug.md.


## 17.1 — Calibration-free WiLoR desktop promotion

The user confirms the optimized debug build works perfectly on their setup and
authorizes normal desktop control and publication to main. This is qualitative
live acceptance of the debug trial, superseding the pending-trial status above;
it is not a measured FPS or recognition benchmark.

The default run now uses the same optimized WiLoR/profile/validation path with
CUDA auto-FP16, confidence 0.50, 30 FPS and two candidates per view. It ignores
calibration unless --calibrated is explicit. Image-space motion retains the
successful debug mapping, single-view continuation and source-change rebasing.
Only normal mode constructs the native Desktop adapter; no recorder is created.

Final local suite: 159 tests run, 158 passed, one Windows ABI skip. A synthetic
WiLoR two-view session produces identical desktop-adapter move/click commands
to debug events, including left/right clicks, selected-view loss and palm release.
Calibration/marker/recorder bypass, worker cleanup and defaults are checked.
Existing scroll/ownership/loss regressions pass. Both Python environments pass
pip check; compileall, CLI help and whitespace checks pass. The 960x540 desktop
panel was rendered and visually inspected with synthetic inputs. No real cursor
events were sent. Actual Windows SendInput and sustained desktop use require
the user's live trial; no new GPU performance claim is made.


## B20–B24 — Desktop interaction follow-up

B20: A screen-space soft deadband (0.0025 normalized screen units) suppresses
small oscillations. Smoothing time constants vary from 140 ms for precision
to 55 ms for large motion. Tests verify vibration rejection, deliberate target
acquisition, comparable behavior at 15/30/60 Hz, and filter reset on rebase.
These are deterministic traces, not a comfort or tremor study.

B21: The user clarifies background detection already works. The actual request
is to release forgotten ownership after five seconds with no selected hand.
Synthetic app sessions verify one timeout/deactivation, no early release, a new
fist selecting a different identity, and cancellation when just one selected
view returns before five seconds. Capture/processing failure and identity gates
remain unchanged. No focus or low-FPS activation changes were retained.

B22: After pointing has begun, an active fist parks the pointer. The first
returning pointing pose rebases at the parked cursor; subsequent motion is
relative to it. Tests verify no downward jump/recentering, no reactivation and
continued movement. Initial activation retains its original fist origin.

B23: Short mono PCM WAVs distinguish left/right clicks and both existing chimes.
Tests verify valid distinct waveforms, sub-100-ms click cues, mute suppression
and exactly one corresponding cue for emitted simulated/native-adapter clicks.
Playback stays on the existing queue thread. Actual speakers were not used.

Final validation covers 169 tests: 168 pass and one Windows ABI check skips.
The full run initially failed the new timeout test because it used the wrong
archive timestamp key, then because it omitted the existing exit chime from its
expected sequence. Corrected timeout tests both pass; all other full-suite tests
passed. pip check, compileall and git diff --check pass. No real cursor events
were sent. Windows live feel/audio/timeout acceptance remains pending.

B24: User reports index drift while extending the thumb for either click chord,
mirrored with handedness. First freeze/chord and pinch proposals were rejected.
A two-step target lock/confirmation alternative was proposed for discussion;
click rules are unchanged pending the user's choice.
