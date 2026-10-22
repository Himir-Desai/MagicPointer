# Thumb-tap left-click trial (18, B24)

This branch tests the user's proposed slight thumb lift and tap against the
three curled fingers, in the **actual desktop app**. It includes the B20–B23
smoothing, fist repositioning, five-second owner timeout and click sounds.
It does not change right click. It remains separate from main until a successful
user trial; synthetic testing cannot establish natural-tap accuracy.

Use the existing WiLoR environment and weights; no new dependencies are needed.
For the user's camera indices:

```powershell
.\.venv\Scripts\python.exe -m magicpointer run --left 1 --right 2 --left-click thumb-tap
```

Hold one fist for 2.5 seconds to select the hand. Point with the index, keeping
middle/ring/little curled. Slightly lift the thumb away from those fingers,
tap it down against them, then lift it again. **Left click fires on separation
after the tap**, with the normal left-click sound. Resting it against the curled
fingers or holding it extended does not click. The right-click thumb-plus-index-
and-middle chord, scroll mode, fist repositioning and palm release are unchanged.
Cursor movement still comes from the pointing index, with smoothing; this trial
does not add cursor freezing or a dwell-to-lock target.

Append `--debug` to simulate input and automatically record the data-only archive.
That preview displays the tap state. The archive's combined-hand
`model_diagnostics.thumb_tap` records distances, thresholds, timing, eligibility
and one-frame click pulses. Raw per-view thumb gesture metrics remain available
as reference; a thumb extension with only the index extended is treated as
pointing rather than the old left-click chord in tap mode.

Omit `--left-click thumb-tap` (or use `--left-click thumb-chord`) for the existing
left-click method. Tap mode currently requires WiLoR. Both run modes use the same
recognition; debug sends no desktop input. No calibration is required.

## What the detector measures

The [WiLoR model](https://github.com/rolpotamias/WiLoR) reconstructs hand geometry.
This trial uses its existing 21 joints, not a learned contact classifier or a
physical touch measurement. It estimates the shortest 3D thumb-tip distance to
the distal chains of the curled middle/ring/little fingers, normalized by palm
width. Geometry from associated views is fused before tap recognition; views do
not vote independently.

Initial trial thresholds: at least 0.24 palm widths away arms the tap; at most
0.12 estimates contact; at least 0.24 again confirms release. Each transition
needs two fresh observations, spanning 0.08 seconds for initial arming and 0.04
seconds for contact/release. Contact lasting over 0.8 seconds cancels the cycle.
The index must remain extended and all three other fingers curled throughout.
Changing selected identity or contributing camera views, missing geometry,
stale timestamps or a gap over 0.6 seconds cancels an incomplete tap.

At low processing FPS, short taps may fall entirely between observations. Start
with a deliberate tap long enough to show up in at least two processed frames;
then try your natural speed. Occlusion/model error can invent or hide proximity.
The thresholds are initial engineering choices, not a measured contact accuracy.

Try both hands, seated distance and camera viewpoints, resting the thumb,
ordinary pointing, isolated taps, repeated taps, right clicks and scrolling.
Report missed/accidental clicks and pointer drift. If unreliable, a debug archive
can show whether the motion was observed and which transition failed. It contains
no camera images, video or audio.
