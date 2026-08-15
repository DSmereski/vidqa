"""Perceived loading behavior from video alone — zero instrumentation.

first_content_s: when the first non-blank frame appears.
settled_s: when the picture stopped changing (last consecutive-sample
pHash change above the run-to-run threshold).
"""
import os
import tempfile

import cv2
import numpy as np

from .diff import _phash
from .ffutil import ToolError, r4, run, sample_fps

STEP_DEFAULT = 0.25
BLANK_STD = 3.0
CHANGE_THRESHOLD = 8


def load(path, step=STEP_DEFAULT, content_by=None, settled_by=None):
    if step <= 0:
        raise ToolError("--step must be positive")
    blanks = []
    hashes = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", sample_fps(step) + ",scale=256:-2",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        for name in names:
            gray = cv2.cvtColor(cv2.imread(os.path.join(td, name)), cv2.COLOR_BGR2GRAY)
            blanks.append(bool(gray.std() < BLANK_STD))
            hashes.append(_phash(gray))
    first_content = next((i for i, blank in enumerate(blanks) if not blank), None)
    changes = [i for i in range(1, len(hashes))
               if int(np.count_nonzero(hashes[i] != hashes[i - 1])) > CHANGE_THRESHOLD]
    settled = changes[-1] if changes else (first_content or 0)
    result = {
        "changed_samples": len(changes),
        "first_content_s": r4(first_content * step) if first_content is not None else None,
        "sampled": len(hashes),
        "settled_s": r4(settled * step),
        "step_s": r4(step),
    }
    ok = first_content is not None
    if ok and content_by is not None:
        ok = result["first_content_s"] <= content_by
    if ok and settled_by is not None:
        ok = result["settled_s"] <= settled_by
    result["pass"] = bool(ok)
    return result
