"""Where do two recordings of the same test diverge?

Start-aligned sampling of both runs, per-pair pHash hamming distance
(resolution-robust, compression-tolerant). Divergence = distance above
the same-scene threshold diff.py already uses.
"""
import os
import tempfile

import cv2
import numpy as np

from .diff import _imwrite_png, _phash, load_frame
from .ffutil import ToolError, r4, run

STEP_DEFAULT = 0.5
# same-content re-encodes measure 0-2 bits apart; real UI changes 10+.
# (diff.py's 20 answers "different scene entirely" — too lax for run-to-run.)
THRESHOLD_DEFAULT = 8
DIVERGENCE_CAP = 50
SAMPLE_WIDTH = 256


def rundiff(a, b, step=STEP_DEFAULT, threshold=THRESHOLD_DEFAULT, shots=None):
    if step <= 0:
        raise ToolError("--step must be positive")
    ha = _hashes(a, step)
    hb = _hashes(b, step)
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
    if shots is not None and first is not None:
        os.makedirs(shots, exist_ok=True)
        paths = []
        for tag, src in (("a", a), ("b", b)):
            p = os.path.join(shots, f"diverge_{tag}.png")
            _imwrite_png(p, load_frame(src, first))
            paths.append(p)
        result["shots"] = paths
    return result


def _hashes(path, step):
    hashes = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step},scale={SAMPLE_WIDTH}:-2",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError(f"no frames sampled from {path}")
        for name in names:
            gray = cv2.cvtColor(cv2.imread(os.path.join(td, name)), cv2.COLOR_BGR2GRAY)
            hashes.append(_phash(gray))
    return hashes
