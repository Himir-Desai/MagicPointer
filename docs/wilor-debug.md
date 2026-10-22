# WiLoR in regular debug (17)

This opt-in backend runs the normal virtual pointer, fist selection, clicks,
scrolling, palm release and automatic data-only diagnostics. It sends no desktop
input. `run --hand-backend wilor` without `--debug` is rejected before model,
camera or desktop initialization. MediaPipe remains the default backend.

Use the existing [WiLoR environment/model setup](model-comparison.md). There are
no additional dependencies or weights for this experiment. After obtaining this
branch's source, try your existing pair:

```powershell
.\.venv\Scripts\python.exe -m magicpointer run --debug --uncalibrated --hand-backend wilor --left 1 --right 2 --fps 30 --max-hands 2
```

The default detector threshold is **0.50**. To try the user's requested lower
end of the range, append `--wilor-confidence 0.45`. The same threshold applies
to both views and every frame; there is no temporary cross-camera sensitivity
change. A higher threshold may reject real distant/occluded hands as well as
false detections. Omit `--right` for one-camera debug. For calibrated virtual
testing, omit `--uncalibrated` and retain the existing calibration/marker checks.

The preview identifies WiLoR, device, precision and threshold. Hold one fist
for 2.5 seconds to select the controlling hand. Point to move the virtual pointer;
use the usual thumb click chords and two-finger wrist scrolling. Hold the selected
palm for 0.18 seconds to release. One usable selected view is sufficient; two
associated views contribute aligned geometry to one gesture decision.

## Performance changes

- `--wilor-precision auto` uses FP16 pose/detector inference on CUDA and FP32 on
  CPU. `--wilor-precision fp32` provides a reference if reduced precision causes
  a problem. Explicit FP16 on CPU is rejected. GPU precision/throughput still
  require validation on the RTX 4060.
- The detector receives both fresh images in one batch. Accepted hand crops from
  both cameras are combined into one WiLoR pose-model forward call. The native
  256-pixel crops, BGR handling, padding and antialiasing are retained.
- After selection, only the uniquely associated selected-hand box in each bound
  view reaches expensive reconstruction. A not-yet-bound view can still inspect
  candidates to establish the second perspective. Lost selected detections yield
  no geometry; old joints or boxes are never passed off as a fresh observation.
- Only joints/camera parameters are copied from pose inference to the CPU. The
  upstream model still computes mesh geometry internally because its refinement
  uses that geometry. Raw images travel in memory to the isolated worker once
  per capture pair, without making an extra bytes copy for each write.

These changes reduce redundant work; they do not establish a promised FPS. The
normal debug preview reports a rolling processing rate rather than the original
comparison experiment's cumulative rate. Avoid comparing that rate directly with
`compare-models` A mode, which also evaluates other models. Stage timings in the
archive separate detector batch, crop preparation, pose batch, projection,
validation, worker total and parent round trip. Parent round trip also includes
transport/serialization overhead; its difference is not a pure GPU timer.

## Validation and preserving the hand

New boxes require two fresh detector observations spanning at least 0.08 seconds,
with unique position/size/handedness continuity. At 5 FPS, the second observation
arrives about 0.2 seconds later: confirmation cannot be faster than fresh frames.
Repeated timestamps do not count. A missing detection breaks confirmation, and
gaps over 0.6 seconds discard accumulated evidence.

Once bound, the selected hand uses the existing local identity plus a conservative
box-continuity gate. Nearby ambiguous candidates pause rather than choosing one.
A tight exception permits a nearby handedness-label flip, consistent with the
existing owner policy. Another object elsewhere cannot become the controlling
hand just because the selected hand disappears. Releasing the owner requires
fresh confirmation before a new selection.

Degenerate/nonfinite joints, collapsed projections and extreme bone proportions
are rejected. These checks are not proof that an object is a real hand: a stable,
confident false positive with a plausible reconstructed hand can still pass.
Record a no-hands interval during the trial to assess that case.

## Fixed thumb geometry, not training

The WiLoR-specific `wilor-fixed-v1` profile keeps the existing finger rules and
replaces the thumb decision with palm-relative evidence: how far its tip extends
beyond the index side of the palm, the outward direction of the thumb chain,
thumb IP bend and the closest 3D distance between its distal segment and the
four finger chains. A straight thumb across the palm remains tucked. Proximity
to a finger chain supplies additional tucked evidence. Literal 2D overlap is not
required: perspective overlap can happen without physical contact.

Opening the thumb requires stronger geometry than retaining an already-open
thumb, plus two fresh fused observations spanning 0.08 seconds. A clearly tucked
thumb returns immediately to point/scroll/fist as appropriate. Borderline geometry
is unrecognized and cannot initiate a click. This adds some confirmation latency
on top of the normal gesture dwell. Missing evidence, a changed identity or a
long gap resets thumb confirmation. Shared gestures are classified from fused
geometry; per-camera labels are not votes. No gesture model is trained.

The original comparison command retains its baseline classifier/settings. The
new rules apply only to the opt-in regular WiLoR debug backend. Desktop control
and MediaPipe's default gesture rules remain available as the prior reference.

## Logs and live acceptance

Each `diagnostics/debug-*.zip` retains the normal session/sample/summary files,
without camera images, video or audio. It records the actual WiLoR worker/GPU/
precision/model hashes, threshold, raw detector boxes/scores, pending/accepted/
rejected decisions, reconstruction batch size, selected-hand continuity, raw
thumb measurements, hysteresis/confirmation and filtered shared gesture. The
unused MediaPipe model hash is explicitly absent for this backend.

Test near and at the seating distance, both cameras together and each alone,
with point/left/right transitions, a tucked straight thumb, open palm, wrist
scrolling, selected-hand occlusion and unrelated objects. Check that faster
processing preserves stable joints, that false hands decline without losing real
hands, and that pointing no longer becomes a left click. A satisfactory live
debug trial is required before considering desktop promotion.
