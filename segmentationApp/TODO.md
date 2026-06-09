# segmentationApp TODO

## Alignment Guard

Before segmentation begins, check that input images have been aligned by the imageAligner module.

**How alignment is detected:** The imageAligner (`../imageAligner/run.py`) writes aligned images into a subfolder named `aligned/` inside the source folder (e.g. `<folder>/aligned/*_aligned.tif`). A folder is considered aligned when `aligned/` exists and contains at least as many images as the source folder.

### Tasks

- [ ] In `run.py` (or `cli.py`), add a pre-flight check before launching a segmentation job:
  - Look for `<input_folder>/aligned/` and count image files inside it.
  - If `aligned/` is missing or empty, block the job and show a warning dialog (PyQt `QMessageBox`) prompting the user to run the Image Aligner first.
  - If `aligned/` is present but the count is less than the source folder image count, warn but allow the user to proceed anyway (partial alignment).
- [ ] Pass the `aligned/` subfolder path as the actual input to the segmentation pipeline instead of the parent folder, so the pipeline runs on aligned images automatically.
- [ ] Update the table row status display to reflect alignment state (e.g., "Not Aligned" status color).
