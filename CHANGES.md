# Changes — 2026-07-23

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
