---
layout: default
title: WSL / Install guide
---

# WSL / install guide

This page summarizes the setup path. Replace this stub with the full content
of `WSL_INSTALL.md` from the repository, or `include` it directly — see the
note at the bottom of this file.

## Before you start

ArabidopsisAnalysisV2 ships three GUI apps — `imageAligner`, `segmentationApp`,
and `singlePlantAnalysis` — each with its own `run.py`. The installer scripts
(`installer_conda_{wsl,linux,mac}.sh`) set up a conda environment and clone
the repo into a dedicated install directory.

## A known WSL gotcha

If `$DISPLAY` is completely empty inside WSL despite everything else
installing correctly, check `wsl --list --verbose` on the **Windows** side.
The distro may be running as WSL1, which has no GUI/WSLg support and never
populates `$DISPLAY`.

**Fix**, from PowerShell:

```powershell
wsl --set-version <DistroName> 2
wsl --shutdown
```

Then reopen your WSL terminal.

## System dependencies

The installers set up Qt/X11 libraries (`libxcb-cursor0` and friends). If
you're on a fresh or minimal WSL/Linux image and see
`"no Qt platform plugin could be initialized"`, this step is what fixes it.

## GPU verification

After install, the script checks `torch.cuda.is_available()` to confirm the
right `torch` build was actually installed — not just that `nvidia-smi`
reports a driver.

---

*Replace this page with the full contents of `WSL_INSTALL.md`, or point
Jekyll at the file directly with:*

```liquid
{% raw %}{% include_relative WSL_INSTALL.md %}{% endraw %}
```

*(copy `WSL_INSTALL.md` into this `docs/` folder first if you use `include_relative`).*
