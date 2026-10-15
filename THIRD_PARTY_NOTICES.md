# Third-party notices

This project's own code and materials are covered by the Evaluation and
Presentation License in `LICENSE`. That license does not apply to, and does not
change the licenses of, the third-party components below, which it depends on or
borrows conventions from.

## Icons

The interface icons in `src/telerehab/ui/icons.py` are 24x24 outline glyphs that
follow the geometry conventions of the [Feather](https://github.com/feathericons/feather)
and [Lucide](https://github.com/lucide-icons/lucide) icon sets. Several glyph
paths are derived from them, so their notices are reproduced here.

**Feather** - MIT License

> Copyright (c) 2013-2023 Cole Bemis
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of
> this software and associated documentation files (the "Software"), to deal in
> the Software without restriction, including without limitation the rights to
> use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
> of the Software, and to permit persons to whom the Software is furnished to do
> so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

**Lucide** - ISC License

> Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part
> of Feather (MIT). All other copyright (c) for Lucide are held by Lucide
> Contributors 2022.
>
> Permission to use, copy, modify, and/or distribute this software for any
> purpose with or without fee is hereby granted, provided that the above
> copyright notice and this permission notice appear in all copies.
>
> THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
> REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
> FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
> INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
> LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
> OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
> PERFORMANCE OF THIS SOFTWARE.

The application mark, the garden scene, the butterfly and the flower are
original, drawn in code, and covered by this project's license (`LICENSE`).

## Runtime dependencies

Installed from PyPI; not redistributed in this repository.

| Package | Licence | Role |
|---------|---------|------|
| [PySide6](https://doc.qt.io/qtforpython-6/) (Qt for Python) | LGPL-3.0 / GPL / commercial | the user interface |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) | Apache-2.0 | hand-landmark detection |
| [OpenCV](https://opencv.org/) (`opencv-python`) | Apache-2.0 | camera capture and image handling |
| [NumPy](https://numpy.org/) | BSD-3-Clause | numerics |
| [Requests](https://requests.readthedocs.io/) | Apache-2.0 | the backend client |

PySide6 is licensed under the LGPL: it is used here as an unmodified, dynamically
linked library, which that licence permits for applications under other licences.
Redistributing a bundled build (for example with PyInstaller) is outside what
`LICENSE` allows; anyone given permission to do so should also read the LGPL
terms for Qt.

## Not included

The third-party clinical backend this application integrates with, the thesis
document, and the papers listed in `docs/references.md` are not part of this
repository (see `LICENSE`).
