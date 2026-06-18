# Fine-tuning the Arabidopsis Segmentation Model

This guide covers fine-tuning the existing Arabidopsis nnUNetv2 model to correct
specific misclassification issues — specifically hypocotyl pixels being labeled as
leaf (class 5) instead of hypocotyl (class 4).

## Class Label Reference

| Class | Value | Color in viewer |
|-------|-------|-----------------|
| Background | 0 | Black |
| Main root | 1 | Red |
| Lateral root | 2 | Green |
| Seed | 3 | Blue |
| Hypocotyl | 4 | Yellow |
| Leaf | 5 | Purple |
| Petiole | 6 | Purple |

## Prerequisites

- nnUNetv2 installed and environment variables set (`nnUNet_raw`, `nnUNet_preprocessed`, `nnUNet_results`)
- ITK-SNAP installed for annotation
- The ChronoRoot Jupyter notebooks for dataset organization
- Original dataset downloaded from HuggingFace (see below)

## Step 1 — Download the Original Training Dataset

The full annotated dataset (797 Arabidopsis cases) is available on HuggingFace.
Download it so your new cases can be merged with the existing ones.

```
https://huggingface.co/datasets/ngaggion/ChronoRoot2
```

The dataset should be placed/merged into:
```
nnUNet_raw/Dataset789_ChronoRoot2/
    imagesTr/       ← grayscale input PNGs
    labelsTr/       ← mask PNGs (pixel values = class IDs above)
    dataset.json
```

## Step 2 — Identify Failure Frames and Locate Their Masks

You do not need to label every frame. Only select frames where the misclassification
is visible — frames where the hypocotyl appears purple instead of yellow. A few
frames per affected video is sufficient.

Use the plant viewer (Tab 3 in the main app, "View full sequence") with segmentation
toggled on to scrub through and identify these frames. Note the frame filenames.

The existing segmentation masks (your silver standard) are already at:
```
<video_folder>/Segmentation/Ensemble/
```

These pre-filled masks are your starting point for correction in ITK-SNAP — you
only need to repaint the wrong regions, not label the entire image from scratch.

## Step 4 — Correct Labels in ITK-SNAP

1. Open the original image and its corresponding segmentation mask in ITK-SNAP.
2. ITK-SNAP works in NIfTI format (`.nii.gz`) — convert your PNGs first using
   the ChronoRoot Jupyter notebooks if needed.
3. Using the paintbrush tool, repaint the incorrectly labeled hypocotyl pixels
   from class `5` (leaf) to class `4` (hypocotyl).
4. Save the corrected mask in NIfTI format.

Focus corrections on the hypocotyl region only. You do not need to re-annotate
the rest of the image.

## Step 5 — Organize New Cases for nnUNet

Use the ChronoRoot Jupyter notebooks (`trainerOrganization/`) to:
- Convert corrected NIfTI masks back to PNG
- Name the new cases following nnUNet convention, continuing from case 797:
  - Image: `Case797_0000.png`, `Case798_0000.png`, ...
  - Mask:  `Case797.png`, `Case798.png`, ...
- Copy the new files into `nnUNet_raw/Dataset789_ChronoRoot2/imagesTr/` and `labelsTr/`
- Update `numTraining` in `dataset.json` to reflect the new total

## Step 6 — Preprocess New Cases

Re-run preprocessing so nnUNet prepares the new cases. It will skip cases already
processed and only handle the new ones.

```bash
nnUNetv2_preprocess -d 789 -c 2d --verify_dataset_integrity
```

## Step 7 — Fine-tune Fold 0

Continue training from the existing checkpoint. Only fold 0 is needed because the
inference code in `nnUNet_wrapper.py` loads only fold 0.

```bash
nnUNetv2_train 789 2d 0 --c
```

The `--c` flag resumes from the last checkpoint. Training will be much shorter than
the original run since the model already has a strong starting point — monitor the
validation loss and stop once it stabilizes.

If you want to start specifically from the final checkpoint:

```bash
nnUNetv2_train 789 2d 0 --pretrained_weights \
    segmentationApp/models/Arabidopsis/fold_0/checkpoint_final.pth
```

## Step 8 — Replace the Model Checkpoint

Once training finishes, copy the new checkpoint into the app's model folder:

```bash
cp $nnUNet_results/Dataset789_ChronoRoot2/nnUNetTrainer__nnUNetResEncUNetMPlans__2d/fold_0/checkpoint_final.pth \
   segmentationApp/models/Arabidopsis/fold_0/checkpoint_final.pth
```

Back up the old checkpoint first in case you need to roll back.

## Notes

- **Why only fold 0?** The inference wrapper (`nnUNet_wrapper.py:68`) uses
  `use_folds=(0,)`. Training all 5 folds would give marginally better ensemble
  accuracy but requires 5× the compute, and you would also need to update the
  inference code to load all folds.
- **How many new frames do you need?** 20–50 well-corrected failure frames is
  typically sufficient for a targeted fine-tuning correction.
- **Rollback**: Keep the original `checkpoint_final.pth` backed up before replacing
  it so you can revert if the fine-tuned model introduces regressions elsewhere.
