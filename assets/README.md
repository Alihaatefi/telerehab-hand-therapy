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

## Encoding

Each file is stored at the size it is actually drawn or played at, which keeps
the whole set under 0.5 MB. Backgrounds are JPEG; the two sprites are PNG
because they need an alpha channel; the chime is 16-bit mono at 44.1 kHz, which
is indistinguishable from a higher-rate master for a 0.68 s sound effect.
