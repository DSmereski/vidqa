"""Find WHEN text or a template element is visible in a video.

One ffmpeg pass samples frames at a fixed step; each sample is checked by
OCR substring (text mode) or template match (template mode). Reported
interval endpoints are accurate to +/- one step.
"""
import os
import tempfile

import cv2

from .diff import load_frame
from .ffutil import ToolError, r4, run

STEP_DEFAULT = 0.5
THRESHOLD_DEFAULT = 0.8
INTERVAL_CAP = 50


def when(path, text=None, template=None, step=STEP_DEFAULT, threshold=THRESHOLD_DEFAULT):
    if (text is None) == (template is None):
        raise ToolError("give exactly one of a text query or --template")
    if step <= 0:
        raise ToolError("--step must be positive")
    tpl = load_frame(template) if template is not None else None
    hits = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step}",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        for name in names:
            frame = cv2.imread(os.path.join(td, name))
            hits.append(_present(frame, text, tpl, threshold))
    intervals = _intervals(hits, step)
    return {
        "found": bool(intervals),
        "first_s": intervals[0]["start_s"] if intervals else None,
        "intervals": intervals[:INTERVAL_CAP],
        "mode": "text" if text is not None else "template",
        "query": text if text is not None else os.path.basename(template),
        "sampled": len(hits),
        "step_s": r4(step),
    }


def _present(frame, text, tpl, threshold):
    if text is not None:
        from .ocr import scan_text
        return text.lower() in scan_text(frame).lower()
    if tpl.shape[0] > frame.shape[0] or tpl.shape[1] > frame.shape[1]:
        raise ToolError("template is larger than the video frame")
    _, best, _, _ = cv2.minMaxLoc(cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED))
    return bool(best >= threshold)


def _intervals(hits, step):
    out = []
    start = None
    for i, hit in enumerate(hits):
        if hit and start is None:
            start = i
        elif not hit and start is not None:
            out.append({"start_s": r4(start * step), "end_s": r4(i * step)})
            start = None
    if start is not None:
        out.append({"start_s": r4(start * step), "end_s": r4(len(hits) * step)})
    return out
