"""Auto-locate a failure moment: last-good and first-bad frames.

Feed it the failure text from the test's assertion (or the error the UI
showed). One OCR sampling pass finds the first sample containing it; that
sample is first-bad, the sample before is last-good. The written shots are
the exact sampled frames the OCR verdict was made on, so they can never
disagree with it. Accuracy is +/- one step, like `when`.
"""
import os
import tempfile

import cv2

from .diff import _imwrite_png
from .ffutil import ToolError, r4, run

STEP_DEFAULT = 0.5


def locate(path, fail_text, step=STEP_DEFAULT, shots=None):
    if not fail_text or not fail_text.strip():
        raise ToolError("give the failure text to look for")
    if step <= 0:
        raise ToolError("--step must be positive")
    needle = fail_text.lower()
    first_bad = None
    sampled = 0
    shot_paths = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step}",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        from .ocr import scan_text
        prev = None
        for i, name in enumerate(names):
            sampled = i + 1
            frame = cv2.imread(os.path.join(td, name))
            if needle in scan_text(frame).lower():
                first_bad = i
                if shots is not None:
                    os.makedirs(shots, exist_ok=True)
                    for tag, img in (("last_good", prev), ("first_bad", frame)):
                        if img is None:
                            continue
                        p = os.path.join(shots, f"{tag}.png")
                        _imwrite_png(p, img)
                        shot_paths.append(p)
                break
            prev = frame
    result = {
        "found": first_bad is not None,
        "first_bad_s": None,
        "last_good_s": None,
        "query": fail_text,
        "sampled": sampled,
        "step_s": r4(step),
    }
    if first_bad is None:
        return result
    result["first_bad_s"] = r4(first_bad * step)
    if first_bad > 0:
        result["last_good_s"] = r4((first_bad - 1) * step)
    if shots is not None:
        result["shots"] = shot_paths
    return result
