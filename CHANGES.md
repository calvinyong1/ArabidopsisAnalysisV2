# Changes — 2026-09-03

## `analysis/imageUtils/seg.py`

### 1. Added a hard horizontal-distance gate to hypocotyl component selection

**Symptom:** When two plants' hypocotyls both fall inside one plant's ROI
(rectangular ROI forced wide by e.g. a diagonally-growing root), the neighbor's
hypocotyl could get tracked as this plant's own — specifically when the
neighbor's hypocotyl becomes a valid, trackable blob *before* this plant's own
hypocotyl does. At that point the only candidate component in the ROI belongs
to the neighbor.

**Cause:** `extract_hypocotyl_length()`'s anchor selection (added in an earlier
session to fix largest-blob-wins picking the wrong plant) always picked
whichever component was *closest* to `fixed_seed_position`, with no rejection
threshold — unlike the sibling root-selection code in
`extract_root_segmentation()`, which already had one (`distance_to_root_base <
100`, falling back to `found_root=False` otherwise). So if this plant had no
hypocotyl blob yet, the neighbor's blob — the only one present — was accepted
regardless of how far away it actually was.

**Fix:** Replaced the Euclidean `cv2.pointPolygonTest` distance used for
anchor scoring with a horizontal-only distance (candidate bounding-rect vs.
`root_origin`'s x-coordinate), and added a hard cutoff
`max_horizontal_distance=80` (a new keyword arg on `extract_hypocotyl_length`,
default `80`). If the closest candidate is farther than that, the function now
returns `(zeros, 0)` — no hypocotyl detected — instead of forcing a pick.

Horizontal-only distance was chosen over Euclidean because plants are plated
in a row (measured minimum seed spacing ~170px) and a hypocotyl grows
vertically from its own seed: neighboring plants separate cleanly on the
x-axis, while a real hypocotyl can legitimately sit far away in y once it's
tall. `80` = half of the ~170px minimum spacing, minus a small margin for
blob width.

**Known residual risk (not fixed):** the stitching step just below the anchor
check (`GAP_THRESHOLD = 100` in the same function) that grows the accepted
mask outward from the anchor is still a full 2D gap check, not horizontally
scoped. If a real hypocotyl is accepted as anchor near the 80px edge, and a
neighbor's blob sits within a 100px 2D gap of it, stitching could still pull
in a sliver of the neighbor's hypocotyl. Narrower/less likely than the bug
this fix addresses; left alone rather than tightened blind. Revisit only if
seen in production data.

**How to revert if this proves error-prone in testing:** in
`extract_hypocotyl_length()`, restore the previous signature (drop the
`max_horizontal_distance=80` parameter) and replace the anchor-selection block
with:

```python
origin_pt = (int(root_origin[0]), int(root_origin[1]))
anchor_index = 0
best_distance = None
for i, (area, comp, rect) in enumerate(components_data):
    contains_origin = cv2.pointPolygonTest(comp, origin_pt, False) > 0
    distance = 0 if contains_origin else abs(cv2.pointPolygonTest(comp, origin_pt, True))
    if best_distance is None or distance < best_distance:
        best_distance = distance
        anchor_index = i

if anchor_index != 0:
    components_data.insert(0, components_data.pop(anchor_index))
```

This restores "always pick nearest available, no rejection" behavior (still
proximity-anchored, just without the horizontal-only metric or the hard
cutoff). Alternatively, `git log -- singlePlantAnalysis/analysis/imageUtils/seg.py`
and revert this specific commit.

# Changes — 2026-08-24

## `environment.yml` / `environment_no_nnunet.yml`, `singlePlantAnalysis/3_generateReport.py`

### Fixed report generation crashing entirely on fresh installs due to an unpinned `multimethod` regression

**Symptom:** A user on a freshly-installed WSL environment ran `3_generateReport.py`
and it crashed immediately at import time, before doing anything:

```
TypeError: metaclass conflict: the metaclass of a derived class must be a
(non-strict) subclass of the metaclasses of all its bases
```

with the traceback rooted in `skfda`'s `Identity` operator registering
`gram_matrix_optimization` via `multimethod`.

**Cause:** `environment.yml` pins `scikit-fda=0.10.1` (released April 2025) but
never pins its transitive dependency `multimethod`. `scikit-fda`'s own metadata
only excludes `multimethod==1.11`/`1.11.1` (an older, unrelated bug fixed in
Feb 2024) — it has no upper bound. `multimethod==2.0.2` (Nov 2025) shipped a
change ("Nested `subtype` allowed") that breaks `skfda`'s `Identity` operator
registration with exactly this metaclass-conflict error. Any environment
solved before Nov 2025 still resolves to an older, working `multimethod` and
never sees this; any environment solved fresh today resolves to the latest
release (`2.1` as of this writing) and crashes immediately.

Compounding the impact: `3_generateReport.py` imported `performFPCA` from
`analysis.fpca_analysis` unconditionally at the top of the file, even though
FPCA only actually runs behind `if conf['doFPCA']:`. So the broken import took
down report generation entirely — the temporal plots, convex hull analysis,
Fourier plots, and lateral angle plots never ran either, even for configs with
`doFPCA` disabled.

**Fix:**
- `environment.yml` / `environment_no_nnunet.yml`: added `multimethod<2.0.2` to
  pin the solver to the last known-good release.
- `3_generateReport.py`: moved `from analysis.fpca_analysis import performFPCA`
  out of the top-level imports and into the `if conf['doFPCA']:` block, wrapped
  in a `try/except` that logs and skips FPCA on failure instead of crashing —
  so a broken/incompatible FPCA dependency can no longer take down the rest of
  the report.



## `analysis/dataWork.py`

### 1. Fixed `expected_hour_count` hardcoded to a 15-minute capture interval

**Symptom:** Growth chart came out empty (or badly truncated) whenever the capture
interval was set to anything other than 15 minutes — worst at 180 minutes, where
only the first ~24 hours of a multi-day experiment survived.

**Cause:** After resampling the per-frame data to hourly bins, the code reconciled
the resulting row count against the expected frame count (`N_exp`) using a formula
that assumed a fixed 4 frames/hour (15-min interval):

```python
expected_hour_count = (N_exp + 3) // 4
```

This silently ignored `conf['timeStep']` (the actual configured capture interval),
so at 180 minutes it computed a duration ~12x too short and truncated the
hourly dataframe down to just the first day.

**Fix:** Generalized the formula to use the real capture interval, accounting for
the fencepost relationship between frame count and elapsed time (`N_exp` frames
span `N_exp - 1` intervals, since the first frame defines t=0):

```python
expected_hour_count = (N_exp - 1) * timeStep // 60 + 1
```

### 2. Fixed `medfilt` zero-padding artifact flattening the last few data points

**Symptom:** The last `kernel_size // 2` (4, for kernel=9) measurements of
`MainRootLength`, `LateralRootsLength`, `NumberOfLateralRoots`, and
`HypocotylLength` were identical, even though the raw segmentation data kept
increasing right up to the last frame.

**Cause:** `scipy.signal.medfilt(x, 9)` implicitly zero-pads past the array
boundary. Near the end of a short series, the window's zero-padding pulled the
median down, and the "values never decrease" clamp locked all subsequent points
to that same value — producing an artificial flat plateau at the end of every
plant's curve.

**Fix:** Replaced `signal.medfilt(x, 9)` with a centered rolling median that
shrinks its window near the edges instead of padding with fabricated data:

```python
pd.Series(x).rolling(window=9, center=True, min_periods=1).median().to_numpy()
```

This keeps full 9-point smoothing wherever a full window is available, and uses
only real neighboring points (no padding) near the start/end of the sequence.

Applied to `mainRoot`, `lateralRoots`, `numlateralRoots`, and `hypocotylLength`
(lines ~175-178). The `medfilt(..., 5)` calls used for `MainOverTotal`,
`LateralDensity`, and `DiscreteLateralDensity` were left unchanged.

## `analysis/plantAnalysis.py` / `analysis/graphUtils/save.py` — 2026-08-19

### 3. Fixed `HypocotylLength` being discarded whenever the root graph wasn't valid yet

**Symptom:** `Results_raw.csv` reported `HypocotylLength = 0` on early frames
where the segmentation mask visibly showed hypocotyl growth, whenever the main
root hadn't been detected/tracked yet. Confirmed empirically against real masks
(`experiment_20260707_092606_Output/.../plant_2/Results_0/`) — frames 11-18 had
real, growing hypocotyl lengths (1px → 22px) computed correctly by the
pipeline, but recorded as `0`.

**Cause:** `plantAnalysis.py`'s Phase 1 loop ("Find first frame with valid root
structure") computes `hypocotyl_length` independently each frame (a separate
class-4-mask routine, unrelated to root graph success), but every early-return
path in the loop — `not found_root`, `not is_valid_skeleton`, the
`extract_root_segmentation` exception handler, and the `graphInit`/`createTree`
exception handler — hardcoded `saveProps(..., 0, 0)`, discarding the
already-computed value. `graphUtils/save.py`'s `saveProps()` reinforced this by
writing a literal all-zero row whenever `graph=False`, ignoring whatever
hypocotyl value was passed in. Zeroing `MainRootLength`/`LateralRootsLength`
during this search is intentional and correct (tracking can't begin before a
root structure exists) — only the hypocotyl discard was a bug.

**Fix:**
- `plantAnalysis.py`: initialize `hypocotyl_length = 0` at the top of each
  Phase 1 loop iteration (so a genuinely failed frame still defaults safely,
  without carrying over a stale value from a previous frame), and pass the
  real `hypocotyl_length` through at all four early-return `saveProps()` calls
  instead of hardcoding `0`.
- `graphUtils/save.py`: `saveProps()`'s no-graph branch now writes
  `[image_name, frame_number, 0, 0, number_lateral_roots, 0, hypocotyl_length]`
  instead of an all-zero row — root/lateral lengths correctly stay `0` (no
  graph to derive them from), but the independently-measured hypocotyl length
  and lateral count now survive.

**Effect:** frames can now correctly show `HypocotylLength > 0` while
`MainRootLength = 0`, reflecting that hypocotyl elongation and root emergence
are separate biological events that don't have to start at the same time.
Early-experiment growth curves will look different (hypocotyl growth appears
several frames earlier) than before this fix — this is a correction, not a
regression.

## Known remaining issue (not yet fixed)

`PostProcess_Hour.csv` still has `NaN` in 2 of every 3 hourly rows whenever the
capture interval doesn't divide 60 minutes evenly (e.g. 180 min). Since
`plot_individual_plant` (`analysis/report.py`) plots this hourly data without
markers, isolated non-`NaN` points don't render as visible line segments — the
chart can still look empty even though the data is correct.

Proposed fix (not applied): interpolate the hourly gaps right after the resample
in `dataWork.py`:

```python
hour_data = data.resample(f'60{FREQ_MIN}', origin=reference_timestamp).mean()
hour_data = hour_data.interpolate(method='linear').ffill().bfill()
```
