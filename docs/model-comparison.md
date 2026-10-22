# Model comparison experiment (16)

This separate debug command compares MediaPipe, RTMDet + RTMPose-Hand and WiLoR.
It never sends desktop input. Video frames stay in memory; automatic archives
contain landmarks, model/config fingerprints, labels, timings and summaries only.
No filters or adaptive/lowered-threshold retries are used.

MediaPipe and WiLoR supply 3D joints and use the same available-view geometry
classifier/hand-selection logic as the app. RTMPose supplies 21 **2D** joints with
scores: its preview tests finding hands and locating joints, without inventing
depth or reporting equivalent 3D gesture/control support. WiLoR's joint mapping
is the upstream MANO-to-OpenPose 21-point ordering. Its geometry classifier is an
experiment; live gesture accuracy has not been established.

## Windows setup (Python 3.11, RTX 4060)

Run these from the repository root, using the existing app environment:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[comparison]"
.venv\Scripts\python.exe -m venv .venv-wilor
.venv-wilor\Scripts\python.exe -m pip install "setuptools<81" wheel
.venv-wilor\Scripts\python.exe -m pip install torch==2.5.0 torchvision==0.20.0 --index-url https://download.pytorch.org/whl/cu121
.venv-wilor\Scripts\python.exe -m pip install -r requirements-wilor.txt
.venv-wilor\Scripts\python.exe -m pip install --no-build-isolation chumpy==0.70
.venv-wilor\Scripts\python.exe -m pip install --no-deps git+https://github.com/warmshao/WiLoR-mini.git@ebec42f94c389070cdd7dda6fd1bf0b4a659c960
.venv-wilor\Scripts\python.exe -c "import torch; print('CUDA:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
.venv\Scripts\python.exe -m magicpointer compare-models --prepare --max-hands 2
```

The browser page is https://github.com/warmshao/WiLoR-mini. The
`git+...git@<commit>` argument above is pip syntax, not a browser page URL. If
that Git-based install fails, install the same pinned source archive instead:

```powershell
.\.venv-wilor\Scripts\python.exe -m pip install --no-deps "https://github.com/warmshao/WiLoR-mini/archive/ebec42f94c389070cdd7dda6fd1bf0b4a659c960.zip"
```

This alternative does not require Git for installing WiLoR. If it also fails,
retain the complete pip error output so the access/build failure can be diagnosed.

The last command downloads/checks selected weights and performs blank-frame
inference without opening cameras. WiLoR's first run downloads several GB of
assets under `models/comparison/wilor`; allow it to finish. Increase
`--worker-timeout 1200` if the first download takes over ten minutes. Git is
needed for the pinned wrapper installation. The two virtual environments are
intentional: WiLoR has its own OpenCV/PyTorch stack. Do not install its requirements
into `.venv`. Small legacy chumpy/NumPy/Python compatibility aliases are confined
to the worker process when reading MANO assets.

The [official WiLoR project](https://github.com/rolpotamias/WiLoR) links this
[simplified inference wrapper](https://github.com/warmshao/WiLoR-mini). WiLoR
weights, MANO and Ultralytics have their own terms, linked by those projects;
review these for the intended use. This repository does not redistribute weights.
The CUDA installation follows [PyTorch's versioned instructions](https://pytorch.org/get-started/previous-versions/).
CUDA availability and actual performance still need checking on the Windows rig.

For MediaPipe/RTMPose alone, only the first install command is needed, then:

```powershell
.venv\Scripts\python.exe -m magicpointer compare-models --prepare --models mediapipe rtmpose
```

RTMPose uses pinned rtmlib 0.0.13 and ONNX Runtime CPU; MediaPipe uses the existing
CPU VIDEO configuration with fixed 0.65 thresholds. RTMDet and WiLoR use their
0.30 detector thresholds, which are different score scales, not comparable
confidence probabilities. RTMPose joint scores below 0.30 are hidden in the
preview but retained in logs; a detector box with poor joints can still count
as a detected hand. Inspect the skeleton rather than equating count with success.

## Run and switch

Use your actual camera indices (the previously used pair was 1 and 2):

```powershell
.venv\Scripts\python.exe -m magicpointer compare-models --left 1 --right 2 --fps 30 --max-hands 2
```

Omit `--right` for a one-camera trial. For a smaller installed set, append
`--models mediapipe rtmpose`. Each selected backend loads before cameras open;
missing dependencies or failed CUDA initialization produce an error rather than
silently substituting another model/device. Q/Escape, window close, Ctrl+C or a
handled error closes models/cameras and finalizes any started archive.

| Key | Action |
| --- | --- |
| 1 / 2 / 3 | Switch to MediaPipe / RTMPose-Hand / WiLoR alone |
| A | Compare all enabled models on the identical current frames; A again returns to single mode |
| H | Label that at least one real hand is visible in each camera |
| N | Label no real hands visible in either camera |
| U | Unknown/unlabelled visibility (default) |
| D | Toggle the user-supplied near/far condition label; this does not measure distance |
| Q / Escape | Exit and save the diagnostic ZIP |

For 3D models, hold one fist for 2.5 seconds to bind the hand whose fused gesture
is displayed. Its palm held for 0.18 seconds releases selection. One visible view
can supply geometry; a second view must associate with that hand. This tool has
no virtual pointer, click/scroll simulation or OS input. Use normal `run --debug`
to test the revised pointer behavior with MediaPipe. Mode/label changes start
new trials and clear selection; MediaPipe VIDEO trackers restart on mode changes
to avoid carrying old crop tracking across a long inactive gap.

## Decide which works best

Start in single mode to assess practical responsiveness on both cameras. Then
press A to compare skeletons on the same images. This mode runs models serially
with rotating evaluation order; its loop FPS is the **combined experiment rate**,
not any backend's standalone FPS. Slower sampling can itself affect tracking.
Per-camera inference milliseconds exclude rendering/logging; WiLoR additionally
records inference plus raw-frame subprocess transport time. CUDA inference is
synchronized before timing ends. First-use/warmup calls remain in the logs.

Repeat near and at the troublesome seating distance, with the same gestures,
hand rotations, lighting and camera positions. Include hands-empty periods and
the physical camera that previously detected less. Use H/N only when the label
is true for both views; otherwise use U. Compare missed visible hands, false
hands, missing/bad joints, stable finger shapes, responsiveness and the shared
3D gesture for MediaPipe/WiLoR. Simply producing more landmarks is not proof of
accuracy. Two views can also share a model error.

Each session saves `diagnostics/model-compare-<time>-<id>.zip` containing
`session.json`, `samples.jsonl`, `summary.json`. Results separate backend,
physical camera index, execution mode and near/far label. They include detection
denominators, labelled present/absent counts, longest consecutive missing-sample
run (reset at trial boundaries), median/p95 inference latency, raw 2D/native 3D
joints and shared gesture evidence where supported. Missing-sample runs are
counts, not seconds. Neither user presence labels nor these statistics establish
per-joint accuracy. Existing data-only debug archives cannot be fed back into
visual models because they contain no images.

Local smoke checks found 2/1/2 hands with MediaPipe/RTMPose/WiLoR respectively
on one upstream demo image, and 0/1/0 on an all-black image. RTMPose's blank-frame
false detection is recorded as B15. These tiny checks establish functioning
adapters and a known false-positive case; they do not rank room-scale accuracy.

RTMPose model sources and crop/decode behavior:
[official hand model zoo](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose#hand-2d-21-keypoints),
[rtmlib](https://github.com/Tau-J/rtmlib). An empty detector result explicitly
skips the pose stage, preventing its whole-image fallback from inventing a hand.
WiLoR receives BGR, matching the wrapper's tests and internal BGR-to-RGB conversion.

On macOS, replace `.venv\Scripts\python.exe` with `.venv/bin/python` (likewise
for `.venv-wilor`), install the macOS torch/torchvision wheels without the CUDA
index URL, and pass `--wilor-device cpu`. CPU WiLoR is a setup check, not an RTX
4060 performance estimate.
