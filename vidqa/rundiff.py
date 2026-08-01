"""Where do two recordings of the same test diverge?

Start-aligned sampling of both runs, per-pair pHash hamming distance
(resolution-robust, compression-tolerant). Divergence = distance above
the same-scene threshold diff.py already uses.
"""
import os
import tempfile

import cv2
import numpy as np

from .diff import _imwrite_png, _phash, load_frame, zero_rects
from .ffutil import ToolError, r4, run

STEP_DEFAULT = 0.5
# same-content re-encodes measure 0-2 bits apart; real UI changes 10+.
# (diff.py's 20 answers "different scene entirely" — too lax for run-to-run.)
THRESHOLD_DEFAULT = 8
DIVERGENCE_CAP = 50
SAMPLE_WIDTH = 256


def rundiff(a, b, step=STEP_DEFAULT, threshold=THRESHOLD_DEFAULT, shots=None,
            ignore=None, trace_a=None, trace_b=None):
    if step <= 0:
        raise ToolError("--step must be positive")
    if (trace_a is None) != (trace_b is None):
        raise ToolError("--trace-a and --trace-b go together")
    if trace_a is not None:
        return _step_diff(a, b, trace_a, trace_b, threshold, ignore, shots)
    ha = _hashes(a, step, ignore)
    hb = _hashes(b, step, ignore)
    n = min(len(ha), len(hb))
    distances = [int(np.count_nonzero(ha[i] != hb[i])) for i in range(n)]
    over = [{"at_s": r4(i * step), "distance": distances[i]}
            for i in range(n) if distances[i] > threshold]
    first = over[0]["at_s"] if over else None
    result = {
        "diverged": bool(over),
        "divergences": over[:DIVERGENCE_CAP],
        "duration_a_s": r4(len(ha) * step),
        "duration_b_s": r4(len(hb) * step),
        "first_divergence_s": first,
        "mean_distance": r4(sum(distances) / n),
        "sampled": n,
        "step_s": r4(step),
        "threshold": threshold,
    }
    if ignore:
        result["ignored"] = [list(r) for r in ignore]
    if shots is not None and first is not None:
        os.makedirs(shots, exist_ok=True)
        paths = []
        for tag, src in (("a", a), ("b", b)):
            p = os.path.join(shots, f"diverge_{tag}.png")
            _imwrite_png(p, load_frame(src, first))
            paths.append(p)
        result["shots"] = paths
    return result


def _hashes(path, step, ignore=None):
    hashes = []
    scaled = None
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step},scale={SAMPLE_WIDTH}:-2",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError(f"no frames sampled from {path}")
        for name in names:
            gray = cv2.cvtColor(cv2.imread(os.path.join(td, name)), cv2.COLOR_BGR2GRAY)
            if ignore:
                if scaled is None:
                    scaled = _scale_rects(ignore, path, gray.shape)
                zero_rects(gray, scaled)
            hashes.append(_phash(gray))
    return hashes


def _scale_rects(rects, path, sample_shape):
    """Map ignore rects from the video's own pixel space to sample resolution."""
    from .probe import probe
    video = probe(path)["video"]
    ow, oh = video["width"], video["height"]
    for x, y, w, h in rects:
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > ow or y + h > oh:
            raise ToolError(f"--ignore {x},{y},{w},{h} is outside the {ow}x{oh} video")
    sx = sample_shape[1] / ow
    sy = sample_shape[0] / oh
    return [
        [round(x * sx), round(y * sy), max(1, round(w * sx)), max(1, round(h * sy))]
        for x, y, w, h in rects
    ]


def _step_diff(a, b, trace_a, trace_b, threshold, ignore, shots):
    from .trace import _parse
    sa, sb = _parse(trace_a), _parse(trace_b)
    steps = []
    mismatch = None
    first = None
    for i in range(min(len(sa), len(sb))):
        if sa[i]["title"] != sb[i]["title"]:
            mismatch = {"index": i, "a": sa[i]["title"], "b": sb[i]["title"]}
            break
        d = int(np.count_nonzero(
            _step_hash(a, sa[i]["end_s"], ignore) != _step_hash(b, sb[i]["end_s"], ignore)))
        entry = {
            "a_s": sa[i]["end_s"],
            "b_s": sb[i]["end_s"],
            "distance": d,
            "diverged": bool(d > threshold),
            "title": sa[i]["title"],
        }
        steps.append(entry)
        if first is None and entry["diverged"]:
            first = entry
    diverged = bool(first) or mismatch is not None or len(sa) != len(sb)
    result = {
        "diverged": diverged,
        "first_divergent_step": first["title"] if first else None,
        "mode": "steps",
        "step_count_a": len(sa),
        "step_count_b": len(sb),
        "step_mismatch": mismatch,
        "steps": steps[:DIVERGENCE_CAP],
        "threshold": threshold,
    }
    if ignore:
        result["ignored"] = [list(r) for r in ignore]
    if shots is not None and first is not None:
        os.makedirs(shots, exist_ok=True)
        paths = []
        for tag, src, at in (("a", a, first["a_s"]), ("b", b, first["b_s"])):
            p = os.path.join(shots, f"diverge_{tag}.png")
            _imwrite_png(p, load_frame(src, _clamped(src, at)))
            paths.append(p)
        result["shots"] = paths
    return result


def _step_hash(path, at, ignore):
    gray = cv2.cvtColor(load_frame(path, _clamped(path, at)), cv2.COLOR_BGR2GRAY)
    if ignore:
        zero_rects(gray, ignore)
    return _phash(gray)


def _clamped(path, at):
    from .probe import probe
    dur = probe(path)["duration_s"]
    if dur is None:
        return at
    return min(at, max(0.0, dur - 0.05))
