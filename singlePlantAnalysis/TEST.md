# ArUco Marker Detection — Test Documentation

## What was added

**File modified:** `1_analysis.py`

### 1. New imports

```python
from analysis.qr import aruco_detect, aruco_get_pixel_size
from analysis.utils.fileUtilities import getImages
```

- `aruco_detect` — detects ArUco markers in a given image using OpenCV's `ArucoDetector`. Returns a list of corner arrays, or `None` if no marker is found.
- `aruco_get_pixel_size` — takes a single marker's corner array and returns the Euclidean distance between corner 0 and corner 1 (i.e. the width of the top edge of the marker in pixels).
- `getImages` — loads the ordered list of image paths from the config, the same way the main analysis pipeline does.

---

### 2. Debug block

```python
# --- ArUco debug: print the detected marker pixel width ---
if conf.get('videoHasArucoButton', False) or conf.get('videoHasAruco', False):
    print("[ArUco Debug] ArUco checkbox is selected — scanning for markers...")
    try:
        image_paths, _ = getImages(conf)
        found = False
        for img_path in image_paths[:20]:
            aruco_result = aruco_detect(img_path)
            if aruco_result is not None:
                pixel_width = aruco_get_pixel_size(aruco_result[0])
                print(f"[ArUco Debug] Marker found in: {img_path}")
                print(f"[ArUco Debug] Marker width (pixel distance): {pixel_width:.2f} px")
                found = True
                break
        if not found:
            print("[ArUco Debug] No ArUco marker detected in the first 20 images.")
    except Exception as e:
        print(f"[ArUco Debug] Error during detection: {e}")
```

**Trigger condition:**  
Runs when the config key `videoHasArucoButton` (set by the "Video has ArUco markers" checkbox in `run.py`) or its alias `videoHasAruco` is `True`.

**Behaviour step by step:**

| Step | What happens |
|------|-------------|
| 1 | Loads the full image list using `getImages(conf)`, identical to how the main pipeline loads images. |
| 2 | Iterates over the first **20** images to avoid a long scan at startup. |
| 3 | Calls `aruco_detect(img_path)` on each image. |
| 4 | On the first successful detection, calls `aruco_get_pixel_size(aruco_result[0])` to get the top-edge pixel width. |
| 5 | Prints the matched image path and pixel width (2 decimal places), then stops. |
| 6 | If no marker is found in 20 frames, prints a "not detected" warning. |
| 7 | Any exception is caught and printed rather than crashing the analysis. |

**Placement in script:**  
The block runs **after** the manual calibration check and **before** `plantAnalysis()` is called, so it does not affect the analysis itself — it is read-only and diagnostic only.

---

## How to trigger the output

1. Launch the app: `python run.py`
2. On **Tab 1 (Plant Analysis)**, check **"Video has ArUco markers"**.
3. Fill in the Project Folder, Video Folder, and other required fields.
4. Click **"Analyze Plant"**.
5. Watch the terminal where `run.py` was launched — the `[ArUco Debug]` lines will appear before the ROI selection window opens.

### Example expected output (marker found)

```
[ArUco Debug] ArUco checkbox is selected — scanning for markers...
[ArUco Debug] Marker found in: /path/to/images/frame_001.png
[ArUco Debug] Marker width (pixel distance): 243.87 px
```

### Example expected output (marker not found)

```
[ArUco Debug] ArUco checkbox is selected — scanning for markers...
[ArUco Debug] No ArUco marker detected in the first 20 images.
```

---

## Related files

| File | Role |
|------|------|
| `analysis/qr.py` | Defines `aruco_detect()` and `aruco_get_pixel_size()` |
| `analysis/utils/fileUtilities.py` | Defines `getImages()` |
| `2_postprocess.py` | Where ArUco pixel size is actually used for mm/px calibration |
| `run.py` | UI — contains `videoHasArucoButton` checkbox and the `analysis()` method that launches `1_analysis.py` |
