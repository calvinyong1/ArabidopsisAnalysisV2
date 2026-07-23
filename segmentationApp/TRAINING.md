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
| Ignore | 7 | — |

`Ignore` (7) is nnUNet's ignore label — paint it over pixels you want excluded from
the training loss (e.g. ambiguous/uncertain regions), rather than forcing them into
one of the real classes. It's already declared in `dataset.json`'s `labels` block
(`"ignore": 7`) for `Dataset789_ChronoRoot2`.

## Prerequisites

- nnUNetv2 installed and environment variables set (`nnUNet_raw`, `nnUNet_preprocessed`, `nnUNet_results`)
- ITK-SNAP installed for annotation
- The ChronoRoot Jupyter notebooks for dataset organization
- Original dataset downloaded from HuggingFace (see below)

## Step 1 — Download the Original Training Dataset

The full annotated dataset (911 Arabidopsis cases) is available on HuggingFace.
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
- Name the new cases following nnUNet convention, continuing from the current
  dataset's highest existing case number. **Case numbering is 0-indexed**
  (`numTraining: 937` means cases run `Case0`–`Case936`, not `Case1`–`Case937`) —
  don't derive the next case number from `numTraining` by adding 1; check the
  actual highest filename in `labelsTr/` instead (e.g. `ls labelsTr | sed
  's/Case//;s/\.png//' | sort -n | tail -1`). `corrected_to_nnunet_cases.py`'s
  `--start-case` default is stale — always pass it explicitly:
  - Image: `Case937_0000.png`, `Case938_0000.png`, ...
  - Mask:  `Case937.png`, `Case938.png`, ...
- Copy the new files into `nnUNet_raw/Dataset789_ChronoRoot2/imagesTr/` and `labelsTr/`
- Update `numTraining` in `dataset.json` to reflect the new total

## Step 6 — Generate the Custom Validation Split (splits_final.json)

There is no pre-existing `splits_final.json` (the file assigning cases to
train/val for each fold) from the original training run — it lived wherever that
run happened. Without one, nnUNet auto-generates a random 5-fold split across
**all** cases (old + new) the first time you preprocess, which means your new
correction cases could by chance land in fold 0's validation set instead of its
training set — i.e. not actually influence the fine-tuned weights.

To guarantee your correction cases are always trained on, generate a custom
`splits_final.json` that forces them into every fold's training set, and only
draws each fold's validation cases from the original base dataset. Run this
**locally**, next to your `nnUNet_raw/Dataset789_ChronoRoot2` folder:

```bash
python3 -c "
import json, random, os

dataset_dir = 'nnUNet_raw/Dataset789_ChronoRoot2'   # has case_mapping.json + labelsTr/
out_path = 'splits_final.json'

case_mapping = json.load(open(os.path.join(dataset_dir, 'case_mapping.json')))
new_cases = sorted(case_mapping.keys(), key=lambda c: int(c.replace('Case', '')))
new_case_set = set(new_cases)

all_cases = sorted(
    (f.replace('.png', '') for f in os.listdir(os.path.join(dataset_dir, 'labelsTr'))),
    key=lambda c: int(c.replace('Case', ''))
)
base_cases = [c for c in all_cases if c not in new_case_set]

random.seed(42)
shuffled = base_cases[:]
random.shuffle(shuffled)

n_splits = 5
folds = [[] for _ in range(n_splits)]
for i, case in enumerate(shuffled):
    folds[i % n_splits].append(case)

splits = []
for i in range(n_splits):
    val = sorted(folds[i], key=lambda c: int(c.replace('Case', '')))
    train_base = [c for j, f in enumerate(folds) if j != i for c in f]
    train = sorted(train_base + new_cases, key=lambda c: int(c.replace('Case', '')))
    splits.append({'train': train, 'val': val})

json.dump(splits, open(out_path, 'w'), indent=2)
"
```

This only matters if `case_mapping.json` (produced in Step 5) exists — it's what
identifies which case IDs are new corrections versus original base cases. If
you're not tracking that, you can skip the custom split and accept nnUNet's
default random one.

Note: putting *all* correction cases into training (none held out for validation)
means fold 0's validation loss won't tell you whether the specific correction is
generalizing — it only reflects overfitting on the broader base dataset. Verify the
fix worked by visually inspecting predictions on held-out misclassification frames
after training, rather than relying on the validation loss curve alone.

**Alternative — hold out one correction video for validation.** Instead of forcing
*all* new cases into training, you can hold out the new cases from one source video
(e.g. all of "plate2"'s corrected frames) as fold 0's validation set, and force only
the rest into training. This does let fold 0's validation Dice reflect whether the
correction generalizes, at the cost of that held-out video's corrections not
directly influencing the trained weights. Use `case_mapping.json` (case ID → source
filename) to pick which cases belong to the video you want held out.

**Only building fold 0?** Since `nnUNet_wrapper.py` only ever loads fold 0, if
you're not training the other 4 folds there's no need to run the script above across
all 5 — just edit fold 0 of the existing `splits_final.json` (add the forced-train
cases to `folds[0]['train']` and any held-out cases to `folds[0]['val']`) and leave
folds 1–4 untouched.

## Step 7 — Transfer Files to the VM

Reuse the existing model's plans and fingerprint instead of letting nnUNet
regenerate them — otherwise nnUNet may pick a different network configuration
and the existing checkpoint's weights won't load into it.

**On the VM**, create the destination folders first (so `scp -r` nests the
copied folder correctly instead of renaming it):

```bash
mkdir -p ~/ChronoRoot/nnUNet_raw ~/ChronoRoot/nnUNet_preprocessed ~/ChronoRoot/nnUNet_results
```

**On your local machine** (a separate terminal, not the VM's SSH session), push
the files over:

```bash
scp -r nnUNet_raw/Dataset789_ChronoRoot2 <vm-user>@<vm-host>:~/ChronoRoot/nnUNet_raw/

scp -r nnUNet_preprocessed/Dataset789_ChronoRoot2 <vm-user>@<vm-host>:~/ChronoRoot/nnUNet_preprocessed/

scp segmentationApp/models/Arabidopsis/fold_0/checkpoint_final.pth \
    <vm-user>@<vm-host>:~/ChronoRoot/checkpoint_final.pth
```

The `nnUNet_preprocessed/Dataset789_ChronoRoot2` folder you're pushing should
contain, before transfer:

| File | Where it comes from |
|---|---|
| `dataset_fingerprint.json` | copied from `segmentationApp/models/Arabidopsis/dataset_fingerprint.json` |
| `nnUNetResEncUNetMPlans.json` | copied from `segmentationApp/models/Arabidopsis/plans.json`, **renamed** (matches the `plans_name` field inside the file) |
| `splits_final.json` | generated in Step 6 |
| `dataset.json` | copied from the `nnUNet_raw/Dataset789_ChronoRoot2/dataset.json` you're also transferring — nnUNet expects a copy of it here too (normally done automatically by `plan_and_preprocess`, which this workflow skips since we reuse an existing plan instead) |

## Step 8 — Set Up nnUNetv2 on the VM

Run these **on the VM** (bash):

1. Confirm the GPU and note the CUDA version:
   ```bash
   nvidia-smi
   ```
2. Check whether conda/Python already exist (skip install if so):
   ```bash
   which conda
   which python3
   ```
3. Install Miniconda if needed:
   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
   bash ~/miniconda.sh -b -p $HOME/miniconda3
   source $HOME/miniconda3/etc/profile.d/conda.sh
   ```
4. Create the environment and install PyTorch + nnUNetv2 (swap `cu124` for
   whatever `nvidia-smi` reported — pick the right build from
   https://pytorch.org/get-started/locally/):
   ```bash
   source $HOME/miniconda3/etc/profile.d/conda.sh
   conda create -y -n ChronoRoot python=3.10
   conda activate ChronoRoot
   pip install torch --index-url https://download.pytorch.org/whl/cu124
   pip install nnunetv2
   ```
5. Verify the GPU is visible to PyTorch:
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```
   Must print `True` — if `False`, the CUDA build doesn't match the driver;
   recheck `nvidia-smi` and reinstall torch with the right `cuXXX`.
6. Set the three environment variables, persisted and exported for the current
   session:
   ```bash
   cat >> ~/.bashrc << 'EOF'
   export nnUNet_raw=~/ChronoRoot/nnUNet_raw
   export nnUNet_preprocessed=~/ChronoRoot/nnUNet_preprocessed
   export nnUNet_results=~/ChronoRoot/nnUNet_results
   EOF
   source ~/.bashrc
   ```
7. Confirm the transferred files landed correctly:
   ```bash
   ls ~/ChronoRoot/nnUNet_raw/Dataset789_ChronoRoot2
   ls ~/ChronoRoot/nnUNet_preprocessed/Dataset789_ChronoRoot2
   ```
   First should show `imagesTr`, `labelsTr`, `dataset.json`; second should show
   `dataset_fingerprint.json`, `nnUNetResEncUNetMPlans.json`, `splits_final.json`.

## Step 9 — Preprocess New Cases

Run **on the VM**. This prepares all cases (old + new) using the transferred
plans, rather than generating a new (potentially incompatible) configuration.

`-plans_name` must be passed explicitly — it defaults to `nnUNetPlans`, but the
plans file we transferred is `nnUNetResEncUNetMPlans.json` (matching the
original model's `plans_name`), so without this flag preprocessing fails with
`FileNotFoundError: .../nnUNetPlans.json`:

```bash
nnUNetv2_preprocess -d 789 -plans_name nnUNetResEncUNetMPlans -c 2d --verify_dataset_integrity
```

## Step 10 — Fine-tune Fold 0

Only fold 0 is needed because the inference code in `nnUNet_wrapper.py` loads
only fold 0.

Run **on the VM**, using `--pretrained_weights` to warm-start from the existing
final checkpoint. `-p` needs the same plans identifier as Step 9, for the same
reason:

```bash
nnUNetv2_train 789 2d 0 -p nnUNetResEncUNetMPlans -pretrained_weights ~/ChronoRoot/checkpoint_final.pth
```

Training will be much shorter than the original run since the model already has a
strong starting point — monitor the validation loss and stop (Ctrl+C) once it
stabilizes.

Only use `--c` instead if you're resuming a fine-tuning run that was itself
interrupted mid-training (it looks for `checkpoint_latest.pth`). Don't use `--c`
against the original `checkpoint_final.pth` — nnUNet treats a `checkpoint_final.pth`
as "training already complete" and won't continue from it.

## Step 11 — Replace the Model Checkpoint

`nnUNet_wrapper.py:71` hardcodes `checkpoint_name='checkpoint_final.pth'` — the
inference code will only load a file with that exact name, regardless of how
training actually ended.

nnUNet only writes `checkpoint_final.pth` if training runs to completion (the
full default of 1000 epochs). Since you'll typically stop fine-tuning early with
`Ctrl+C` once validation stabilizes, that file won't exist. Use
`checkpoint_best.pth` instead (saved automatically whenever EMA pseudo dice
improves — watch for the `Yayy! New best EMA pseudo Dice: ...` log lines) and
rename it on the way in:

```bash
# On your local machine:
scp <vm-user>@<vm-host>:~/ChronoRoot/nnUNet_results/Dataset789_ChronoRoot2/nnUNetTrainer__nnUNetResEncUNetMPlans__2d/fold_0/checkpoint_best.pth \
    segmentationApp/models/Arabidopsis/fold_0/checkpoint_final.pth
```

(If you did let training run all the way to completion, use `checkpoint_final.pth`
from the VM instead — no rename needed.)

Back up the old checkpoint first in case you need to roll back.

## Alternative: Full Retrain from Scratch

Use this instead of Steps 6–11 above when you're not warm-starting from an existing
checkpoint — e.g. training a brand-new model, adding a new class, or making a large
enough data change that reusing the base model's plans/fingerprint no longer makes
sense. This is nnUNet's standard (non-fine-tuning) workflow: fresh
`plan_and_preprocess`, video-grouped splits, and a full 5-fold ensemble train. It costs
roughly 5x the compute of the fine-tuning path, and the extra folds only help at
inference once `nnUNet_wrapper.py` is also updated to load them — it currently
hardcodes `use_folds=(0,)` (line 70).

### Prepare dataset.json

This path assumes a fresh `Dataset` folder rather than merging into the existing
`Dataset789_ChronoRoot2`, so there's no existing `dataset.json` to bump `numTraining`
on. Copy the matching template from this repo instead:

- Arabidopsis: copy `trainerOrganization/dataset_Arabidopsis.json`
- Tomato: copy `trainerOrganization/dataset_Tomato.json`

Rename the copy to `dataset.json` inside `nnUNet_raw/DatasetXXX/`, and update the
`numTraining` field to match the actual number of cases in `imagesTr/`.

### Generate splits_final.json (grouped by video)

Group cases by Robot/Camera ID before splitting, so frames from the same video are
never split across train and validation — a plain random split lets the model
memorize plate geometry instead of learning to generalize, and validation loss will
look better than it actually is. The ChronoRoot Jupyter notebook does this grouping
and writes out `splits_final.json`.

Copy the generated file to `nnUNet_preprocessed/DatasetXXX/splits_final.json` **before**
preprocessing — otherwise nnUNet auto-generates its own random split the first time
you run `plan_and_preprocess`.

### Plan, Preprocess, and Train

Run on the VM (see Step 8 above for environment setup):

```bash
nnUNetv2_plan_and_preprocess -d [DATASET_ID] -c 2d
```

Then train all 5 folds of the ensemble:

```bash
nnUNetv2_train [DATASET_ID] 2d 0
nnUNetv2_train [DATASET_ID] 2d 1
nnUNetv2_train [DATASET_ID] 2d 2
nnUNetv2_train [DATASET_ID] 2d 3
nnUNetv2_train [DATASET_ID] 2d 4
```

Unlike the fine-tuning path, let each fold run to completion rather than stopping early
— there's no warm-start, so `checkpoint_final.pth` is expected to be written normally
per fold. Plan for full training time, not the shortened runs the fine-tuning path gets.

To actually use the ensemble at inference, update `nnUNet_wrapper.py`:

```python
use_folds=(0, 1, 2, 3, 4),
```

and copy all 5 folds' checkpoints into `segmentationApp/models/<Model>/fold_X/`
instead of just `fold_0/`.

## Notes

- **Why only fold 0?** The inference wrapper (`nnUNet_wrapper.py:68`) uses
  `use_folds=(0,)`. Training all 5 folds would give marginally better ensemble
  accuracy but requires 5× the compute, and you would also need to update the
  inference code to load all folds.
- **How many new frames do you need?** 20–50 well-corrected failure frames is
  typically sufficient for a targeted fine-tuning correction.
- **Rollback**: Keep the original `checkpoint_final.pth` backed up before replacing
  it so you can revert if the fine-tuned model introduces regressions elsewhere.
