---
layout: default
title: Fine-tuning nnU-Net
---

# Fine-tuning nnU-Net

This page summarizes the training gotchas worth knowing before you start.
Replace this stub with the full content of `TRAINING.md`.

## Preprocessing

`nnUNetv2_preprocess` — the lower-level command used to reuse an existing
plan — does **not** populate
`nnUNet_preprocessed/<dataset>/gt_segmentations/`. Only the higher-level
`nnUNetv2_plan_and_preprocess` does that copy. After adding new cases:

```bash
cp labelsTr/*.png gt_segmentations/
```

Otherwise validation crashes with `FileNotFoundError` at the very end of
training, after all epochs — `gt_segmentations` should mirror **all** of
`labelsTr`, not just one split.

## Splits and resuming

`splits_final.json` is read once into memory when `nnUNetv2_train` starts and
never re-read. Editing it on disk does not affect an already-running or
checkpointed process — a full restart (not `--c` resume) is required for
split changes to take effect.

## Checkpointing

`checkpoint_latest.pth` is only written every `save_every=50` epochs. A crash
can lose up to 49 epochs of progress on resume.

## Sampling

`num_iterations_per_epoch=250` is fixed regardless of dataset size, and case
sampling is uniform random *with replacement* (`infinite=True`) — there's no
built-in oversampling, so small correction-case batches get diluted and
there's no per-epoch guarantee every case is even seen once.

## Device fallback

`segmentationApp/nnUNet_wrapper.py` falls back `cuda` &rarr; `mps` (Apple
Silicon only) &rarr; `cpu`. There's no DirectML/Intel-XPU path, so Windows
integrated graphics always fall through to CPU-only inference.

## Model weights

Weights are hosted at
[`huggingface.co/calvinyong1/arabidopsis-segmentation-model`](https://huggingface.co/calvinyong1/arabidopsis-segmentation-model)
— this fork's own fine-tuned model. `download_weights.sh` pulls this
explicitly for Arabidopsis, and separately scans `ngaggion`'s account for
other species models (e.g. tomato) that aren't forked here.

---

*Replace this page with the full contents of `TRAINING.md`.*
