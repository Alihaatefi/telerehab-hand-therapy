# Assets

Game artwork and audio produced for the thesis, released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

| File | Used by | Notes |
|------|---------|-------|
| `images/background_garden.jpg` | both modes | the exercise backdrop |
| `images/background_form.jpg` | login / settings screens | |
| `images/butterfly.png` | both modes | driven by hand openness |
| `images/flower.png` | both modes | the scoring target |
| `images/hand_open.jpg` | tests | reference photograph, open posture |
| `images/hand_closed.jpg` | tests | reference photograph, closed posture |
| `sounds/score.wav` | both modes | scoring chime |

The two hand photographs are not decorative: `tests/test_vision_integration.py`
runs the real MediaPipe pipeline over them to verify that the openness metrics
separate the two postures by a margin wide enough to calibrate on. Replacing
them will change what those tests assert.

## Optimisation

The originals totalled 3.9 MB — 1024×1024 PNGs displayed at 800×600, sprites
stored at 5× their drawn size, and a 24-bit 96 kHz stereo chime for a 0.68 s
sound effect. Re-encoding to the sizes actually used brought that to 0.5 MB
with no visible or audible difference.
