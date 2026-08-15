"""Index every text line the screen ever showed, with visibility intervals.

One ffmpeg pass samples frames at a fixed step; each sample is OCR'd and
every distinct line gets its visibility intervals — a searchable
"transcript" of the UI over time. Short-lived lines (toasts, snackbars)
are flagged: they are exactly what humans miss when scrubbing.
"""
import os
import tempfile

import cv2

from .ffutil import ToolError, r4, run, sample_fps
from .when import _intervals

STEP_DEFAULT = 1.0
LINE_CAP = 30
INTERVALS_PER_LINE = 3
TEXT_CAP = 60
TOAST_MAX_S = 2.5


def text(path, step=STEP_DEFAULT, contains=None):
    if step <= 0:
        raise ToolError("--step must be positive")
    from .ocr import _engine
    engine = _engine()
    seen = {}  # line -> set of sample indices where visible
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", sample_fps(step),
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        for i, name in enumerate(names):
            frame = cv2.imread(os.path.join(td, name))
            out = engine(frame)
            for raw in getattr(out, "txts", None) or []:
                line = " ".join(str(raw).split())
                if line:
                    seen.setdefault(line, set()).add(i)
    n = len(names)
    lines = []
    for line, idxs in seen.items():
        if contains is not None and contains.lower() not in line.lower():
            continue
        ivs = _intervals([i in idxs for i in range(n)], step)
        lines.append({
            "text": line[:TEXT_CAP],
            "first_s": ivs[0]["start_s"],
            "total_s": r4(sum(iv["end_s"] - iv["start_s"] for iv in ivs)),
            "toast": all(iv["end_s"] - iv["start_s"] <= TOAST_MAX_S for iv in ivs),
            "intervals": ivs[:INTERVALS_PER_LINE],
        })
    lines.sort(key=lambda e: (e["first_s"], e["text"]))
    return {
        "line_count": len(lines),
        "lines": lines[:LINE_CAP],
        "sampled": n,
        "step_s": r4(step),
    }
