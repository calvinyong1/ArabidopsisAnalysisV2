# TODO

## Temporal accumulator causes mask "ghosting" after lateral plant movement

`postprocess.py:211-218` (arabidopsis branch) and `postprocess.py:198-201` (tomato branch):

```python
accum[0] = ensemble[0]                                    # background: fully replaced every frame
accum[1:] = float(alpha) * accum[1:] + ensemble[1:]       # foreground classes: EMA
segmentation = np.argmax(accum, axis=0)
```

`accum` is a `(num_classes, H, W)` buffer allocated once before the per-frame loop and never
reset. The background channel is replaced fresh each frame, but foreground channels (hypocotyl,
roots, etc.) are blended with the previous frame's accumulated value for temporal smoothing
(controlled by `alpha`, default 0.85 for Arabidopsis).

This is missing the `(1 - alpha)` weight a proper exponential moving average needs. As written,
it keeps *adding* the new frame's full-confidence value on top of the decayed old one instead of
blending them, so at a pixel where a class sits for many consecutive frames, `accum[class]`
compounds up to a steady state of roughly `1/(1-alpha) ≈ 6.7`, not 1. When the plant moves away
from that pixel, the channel starts decaying from ~6.7 by `×alpha` each frame while the
background channel resets to ~1 immediately — so `argmax` keeps picking the stale class for
~12 frames (`0.85^n < 1/6.7` around n≈12) after the plant has actually moved. This produces the
observed bug: the mask (e.g. hypocotyl) appears to "carry over" from the plant's previous
lateral position into several subsequent frames.

**Fix**: normalize into a proper EMA:

```python
accum[1:] = float(alpha) * accum[1:] + (1 - float(alpha)) * ensemble[1:]
```

Steady state then converges to ~1 (matching the background channel's scale), so after the plant
moves, the stale channel drops below the background's argmax within a frame or two instead of
~12 — still smooths single-frame noise, but stops the multi-frame ghosting. Apply to both the
arabidopsis (`postprocess.py:216`) and tomato (`postprocess.py:200`) branches.
