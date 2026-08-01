"""Golden-frame comparison.

Two-tier tolerance (the pattern proven by Unity/Unreal screenshot gates):
a global SSIM floor AND a worst-cell local check on an 8x8 grid, so localized
breakage can't hide inside a good global average. pHash answers the cheaper
question "is this even the same scene?" first.
"""
import os
import tempfile

import cv2
import numpy as np

from .ffutil import ToolError, r4, run, safe_path

GRID = 8
PHASH_SCENE_MAX = 20   # hamming distance above this = not the same scene
MASK_PIXEL_DELTA = 25  # per-pixel gray delta counted as changed in the mask
SSIM_MIN_DEFAULT = 0.95
CELL_MAX_DEFAULT = 25.0

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}


def diff(candidate, golden, at=None, mask_out=None,
         ssim_min=SSIM_MIN_DEFAULT, cell_max=CELL_MAX_DEFAULT, ignore=None):
    img = load_frame(candidate, at)
    ref = load_frame(golden)
    result = {
        "pass": False,
        "reason": None,
        "ssim": None,
        "phash_distance": None,
        "scene_match": None,
        "worst_cell": None,
        "size": [img.shape[1], img.shape[0]],
        "golden_size": [ref.shape[1], ref.shape[0]],
        "mask": None,
    }
    if img.shape != ref.shape:
        result["reason"] = "size-mismatch"
        return result
    ga = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    if ignore:
        zero_rects(ga, ignore)
        zero_rects(gb, ignore)
        result["ignored"] = [list(r) for r in ignore]
    ph = int(np.count_nonzero(_phash(ga) != _phash(gb)))
    score = _ssim(ga.astype(np.float64), gb.astype(np.float64))
    cell_val, (row, col) = _worst_cell(ga, gb)
    result.update({
        "pass": bool(score >= ssim_min and cell_val <= cell_max),
        "ssim": r4(score),
        "phash_distance": ph,
        "scene_match": bool(ph <= PHASH_SCENE_MAX),
        "worst_cell": {"mad": r4(cell_val), "row": row, "col": col},
    })
    if mask_out:
        delta = cv2.absdiff(ga, gb)
        mask = np.where(delta > MASK_PIXEL_DELTA, 255, 0).astype(np.uint8)
        _imwrite_png(mask_out, mask)
        result["mask"] = mask_out
    return result


def load_frame(path, at=None):
    """Read an image, or extract one frame from a video at a timestamp.

    An explicit `at` means the caller says this is a video, whatever the
    extension.
    """
    if at is not None or os.path.splitext(path)[1].lower() in VIDEO_EXTS:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        try:
            run(["ffmpeg", "-hide_banner", "-y", "-ss", str(at or 0),
                 "-i", safe_path(path), "-frames:v", "1", tmp.name])
            img = _imread(tmp.name)
        finally:
            os.unlink(tmp.name)
    else:
        img = _imread(path)
    if img is None:
        raise ToolError(f"could not read frame from {path}")
    return img


def _imread(path):
    """cv2.imread silently fails on non-ASCII Windows paths; go through numpy."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as exc:
        raise ToolError(f"could not read {path}: {exc}")
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite_png(path, image):
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ToolError(f"could not encode mask png for {path}")
    try:
        buf.tofile(path)
    except OSError as exc:
        raise ToolError(f"could not write mask to {path}: {exc}")


def zero_rects(gray, rects):
    """Blank dynamic regions (clock, fps counter) so they can't fail a compare."""
    for x, y, w, h in rects:
        if w <= 0 or h <= 0 or x < 0 or y < 0 \
                or x + w > gray.shape[1] or y + h > gray.shape[0]:
            raise ToolError(
                f"--ignore {x},{y},{w},{h} is outside the "
                f"{gray.shape[1]}x{gray.shape[0]} frame"
            )
        gray[y:y + h, x:x + w] = 0


def _phash(gray):
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    coeffs = cv2.dct(small)[:8, :8].flatten()[1:]
    return coeffs > np.median(coeffs)


def _ssim(a, b):
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    kernel = cv2.getGaussianKernel(11, 1.5)
    window = kernel @ kernel.T

    def smooth(x):
        return cv2.filter2D(x, -1, window, borderType=cv2.BORDER_REFLECT)

    mu_a, mu_b = smooth(a), smooth(b)
    var_a = smooth(a * a) - mu_a * mu_a
    var_b = smooth(b * b) - mu_b * mu_b
    cov = smooth(a * b) - mu_a * mu_b
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    return float((num / den).mean())


def _worst_cell(a, b):
    delta = cv2.absdiff(a, b).astype(np.float64)
    h, w = delta.shape
    worst, where = -1.0, (0, 0)
    for row in range(GRID):
        for col in range(GRID):
            cell = delta[
                row * h // GRID:(row + 1) * h // GRID,
                col * w // GRID:(col + 1) * w // GRID,
            ]
            mean = float(cell.mean())
            if mean > worst:
                worst, where = mean, (row, col)
    return worst, where
