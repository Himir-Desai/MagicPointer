# Thumb close-and-reopen left-click trial (18.1, B24)

This revision replaces the previous contact-tap detector, which the user found
awkward. In `--left-click thumb-tap` mode, **thumb + index extended** is now the
pointing pose. Briefly close the thumb, then reopen it to left click. Middle,
ring and little stay curled throughout. Physical finger contact is not required.
Right click keeps its existing thumb-plus-index-and-middle chord.

```powershell
.\.venv\Scripts\python.exe -m magicpointer run --left 1 --right 2 --left-click thumb-tap
```

Hold a fist for 2.5 seconds to activate first. Keep the thumb open while pointing.
Closure pauses movement; a confirmed reopen emits one left click, plays its
sound, and rebases pointing at the parked cursor. Holding the thumb closed does
not repeatedly click. Closure lasting more than 0.8 seconds cancels the click;
reopen to return to pointing. A fist still lets you reposition, a palm releases
ownership, and five seconds without the selected hand releases a forgotten lock.

This branch also uses slightly stronger smoothing and a smaller default workspace:
0.32 by 0.20, down from 0.40 by 0.25. The same motion moves the cursor 25% farther.
In default calibration-free mode, this maps 3.2 palm lengths horizontally and
2.0 vertically, not measured metres. Calibrated mode uses metric dimensions.
Use `--workspace-width 0.40 --workspace-height 0.25` to restore the old gain;
smaller values increase cursor travel. These workspace flags do not change the
recognizer. Smoothing now uses a soft 0.003 screen-unit deadband and time constants
from 180 ms near a target to 75 ms for large motion.

Append `--debug` to simulate input and save data-only diagnostics. The panel
shows cycle state and whether the thumb is open/closed/uncertain. The combined
hand's `model_diagnostics.thumb_tap` records those states, timing, pause flags
and click pulses. Full thumb geometry remains in gesture metrics. Normal runs
control the actual desktop and do not record diagnostics.

Omit `--left-click thumb-tap` (or use `--left-click thumb-chord`) for the original
chord interaction. This trial requires WiLoR, reuses existing dependencies and
weights, and requires no calibration. It remains on `feat/thumb-tap-click`;
main integration awaits a satisfactory user trial.

The recognizer uses the existing WiLoR palm-relative thumb state after geometry
fusion. An open thumb uses the existing stronger entry/weaker retention rules
and at least two fresh observations spanning 0.08 seconds. Closing must remain
clearly closed for at least two observations spanning 0.04 seconds. Reopening
uses the same confirmed-open rule and emits a single pulse. Ambiguous closure,
lost geometry, changed selected identity or contributing camera views, stale
frames or a gap over 0.6 seconds cancel an incomplete cycle. Two extended fingers
switch to the existing right-click/scroll rules and cancel the left-click cycle.

At low processing FPS, an instantaneous closure may fall between frames. Start
with a deliberate close/reopen visible in at least two processed frames, then
try a natural pace. Landmark errors can still hide or invent a thumb transition;
synthetic tests do not establish reliability on your hand. Try both hands,
resting/held/brief thumb closures, pointing, right clicking and scrolling at your
usual seating distance. Report missed/accidental clicks and pointer drift; a
debug archive contains useful states without images, video or audio.
