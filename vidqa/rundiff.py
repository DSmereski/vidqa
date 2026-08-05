"""Where do two recordings of the same test diverge?

Start-aligned sampling of both runs, per-pair pHash hamming distance
(resolution-robust, compression-tolerant) plus a mean-color-cell gap,
because pHash is grayscale and blind to luma-matched hue swaps.
Divergence = either measure above its threshold.
"""
import os
import tempfile

import cv2
import numpy as np

from .diff import _imwrite_png, _phash, color_sig, load_frame, zero_rects
from .ffutil import ToolError, r4, run

STEP_DEFAULT = 0.5
# same-content re-encodes measure 0-2 bits apart; real UI changes 10+.
# (diff.py's 20 answers "different scene entirely" — too lax for run-to-run.)
THRESHOLD_DEFAULT = 8
# measured on real Playwright reruns: jitter <=3, luma-matched hue swap 45.
COLOR_GAP_MAX = 20
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
    sa = _samples(a, step, ignore)
    sb = _samples(b, step, ignore)
    n = min(len(sa), len(sb))
    distances = [int(np.count_nonzero(sa[i][0] != sb[i][0])) for i in range(n)]
    gaps = [int(np.abs(sa[i][1] - sb[i][1]).max()) for i in range(n)]
    over = [{"at_s": r4(i * step), "color_gap": gaps[i], "distance": distances[i]}
            for i in range(n)
            if distances[i] > threshold or gaps[i] > COLOR_GAP_MAX]
    first = over[0]["at_s"] if over else None
    result = {
        "color_threshold": COLOR_GAP_MAX,
        "diverged": bool(over),
        "divergences": over[:DIVERGENCE_CAP],
        "duration_a_s": r4(len(sa) * step),
        "duration_b_s": r4(len(sb) * step),
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


def _samples(path, step, ignore=None):
    """Per-sample (phash, color_sig) pairs."""
    samples = []
    scaled = None
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step},scale={SAMPLE_WIDTH}:-2",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError(f"no frames sampled from {path}")
        for name in names:
            img = cv2.imread(os.path.join(td, name))
            if ignore:
                if scaled is None:
                    scaled = _scale_rects(ignore, path, img.shape)
                zero_rects(img, scaled)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            samples.append((_phash(gray), color_sig(img)))
    return samples


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
        pha, siga = _step_sample(a, sa[i]["end_s"], ignore)
        phb, sigb = _step_sample(b, sb[i]["end_s"], ignore)
        d = int(np.count_nonzero(pha != phb))
        g = int(np.abs(siga - sigb).max())
        entry = {
            "a_s": sa[i]["end_s"],
            "b_s": sb[i]["end_s"],
            "color_gap": g,
            "distance": d,
            "diverged": bool(d > threshold or g > COLOR_GAP_MAX),
            "title": sa[i]["title"],
        }
        steps.append(entry)
        if first is None and entry["diverged"]:
            first = entry
    diverged = bool(first) or mismatch is not None or len(sa) != len(sb)
    result = {
        "color_threshold": COLOR_GAP_MAX,
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


def _step_sample(path, at, ignore):
    img = load_frame(path, _clamped(path, at))
    if ignore:
        zero_rects(img, ignore)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return _phash(gray), color_sig(img)


def _clamped(path, at):
    from .probe import probe
    dur = probe(path)["duration_s"]
    if dur is None:
        return at
    return min(at, max(0.0, dur - 0.05))
