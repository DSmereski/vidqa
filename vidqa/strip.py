"""Filmstrip contact sheet: one glanceable PNG instead of scrubbing."""
import math
import os
import tempfile

import cv2
import numpy as np

from .diff import _imwrite_png
from .ffutil import ToolError, r4, run

EVERY_DEFAULT = 1.0
THUMB_WIDTH = 256
COLS = 5
FONT = cv2.FONT_HERSHEY_SIMPLEX


def strip(path, out, every=EVERY_DEFAULT):
    if every <= 0:
        raise ToolError("--every must be positive")
    thumbs = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / every},scale={THUMB_WIDTH}:-2",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        for i, name in enumerate(names):
            img = cv2.imread(os.path.join(td, name))
            label = f"{i * every:.1f}s"
            cv2.putText(img, label, (6, 20), FONT, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, label, (6, 20), FONT, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            thumbs.append(img)
    cols = min(COLS, len(thumbs))
    rows = math.ceil(len(thumbs) / cols)
    h, w = thumbs[0].shape[:2]
    blank = np.zeros_like(thumbs[0])
    thumbs += [blank] * (rows * cols - len(thumbs))
    sheet = cv2.vconcat([cv2.hconcat(thumbs[r * cols:(r + 1) * cols])
                         for r in range(rows)])
    _imwrite_png(out, sheet)
    return {
        "cols": cols,
        "every_s": r4(every),
        "frames": len(names),
        "out": out,
        "rows": rows,
        "size": [sheet.shape[1], sheet.shape[0]],
        "thumb": [w, h],
    }
