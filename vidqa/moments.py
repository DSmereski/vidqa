"""Auto-index a recording into chapter markers so nobody scrubs blind.

One timeline of everything the detectors can see: freezes, stutter, scene
cuts, silences (srt's collector), blank-frame spans, and — when a query is
given — where that text first and last appears. Purely informational:
always exits 0.
"""
import os
import tempfile

import cv2

from .ffutil import ToolError, r4, run
from .srt import collect_events
from .when import _intervals

STEP_DEFAULT = 0.5
BLANK_STD = 3.0  # same near-uniform floor ci uses
MOMENT_CAP = 100


def moments(path, text=None, step=STEP_DEFAULT):
    if step <= 0:
        raise ToolError("--step must be positive")
    out = [{"at_s": r4(start), "end_s": r4(end), "type": kind, "label": label}
           for start, end, kind, label in collect_events(path)]
    for iv in _blank_spans(path, step):
        out.append({"at_s": iv["start_s"], "end_s": iv["end_s"],
                    "type": "blank", "label": "blank screen"})
    if text is not None:
        from .when import when
        hit = when(path, text=text, step=step)
        if hit["found"]:
            first = hit["intervals"][0]
            last = hit["intervals"][-1]
            out.append({"at_s": first["start_s"], "end_s": first["end_s"],
                        "type": "text_first", "label": f"'{text}' appears"})
            if last != first:
                out.append({"at_s": last["start_s"], "end_s": last["end_s"],
                            "type": "text_last", "label": f"'{text}' last seen"})
    out.sort(key=lambda m: (m["at_s"], m["end_s"], m["type"]))
    counts = {}
    for m in out:
        counts[m["type"]] = counts.get(m["type"], 0) + 1
    result = {
        "counts": counts,
        "moment_count": len(out),
        "moments": out[:MOMENT_CAP],
        "step_s": r4(step),
    }
    if text is not None:
        result["query"] = text
        result["query_found"] = counts.get("text_first", 0) > 0
    return result


def _blank_spans(path, step):
    hits = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step}",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        for name in names:
            gray = cv2.cvtColor(cv2.imread(os.path.join(td, name)),
                                cv2.COLOR_BGR2GRAY)
            hits.append(bool(gray.std() < BLANK_STD))
    return _intervals(hits, step)
