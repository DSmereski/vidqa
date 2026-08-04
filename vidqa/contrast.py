"""Flag low-contrast on-screen text: a cheap, deterministic accessibility probe.

For every OCR text box, split text from background with Otsu and compute the
WCAG contrast ratio between the mean relative luminance of the two sides.
This is an approximation of the per-glyph WCAG measure — good enough to
flag gray-on-gray labels, not a compliance certificate. Exit 1 when any
text falls below the floor (WCAG AA normal text = 4.5).
"""
import cv2
import numpy as np

from .diff import load_frame
from .ffutil import ToolError, r4
from .ocr import _engine

RATIO_MIN_DEFAULT = 4.5
FLAG_CAP = 30


def contrast(path, at=None, min_ratio=RATIO_MIN_DEFAULT):
    if min_ratio <= 1.0:
        raise ToolError("--min-ratio must be > 1 (WCAG ratios run 1..21)")
    img = load_frame(path, at)
    out = _engine()(img)
    txts = list(getattr(out, "txts", None) or [])
    boxes = getattr(out, "boxes", None)
    checked = 0
    flagged = []
    for i, text in enumerate(txts):
        if boxes is None or i >= len(boxes):
            continue
        xs = [int(p[0]) for p in boxes[i]]
        ys = [int(p[1]) for p in boxes[i]]
        x0, y0 = max(0, min(xs)), max(0, min(ys))
        x1, y1 = min(img.shape[1], max(xs)), min(img.shape[0], max(ys))
        region = img[y0:y1, x0:x1]
        if region.size == 0:
            continue
        ratio = _wcag_ratio(region)
        if ratio is None:
            continue
        checked += 1
        if ratio < min_ratio:
            flagged.append({"box": [x0, y0, x1 - x0, y1 - y0],
                            "ratio": r4(ratio), "text": str(text)[:60]})
    return {
        "checked": checked,
        "flagged": flagged[:FLAG_CAP],
        "min_ratio": r4(min_ratio),
        "pass": not flagged,
    }


def _wcag_ratio(region_bgr):
    lum = _rel_luminance(region_bgr)
    gray = (lum * 255).astype(np.uint8)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg = lum[mask > 0]
    bg = lum[mask == 0]
    if fg.size == 0 or bg.size == 0:
        return None
    hi, lo = sorted((fg.mean(), bg.mean()), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _rel_luminance(bgr):
    c = bgr.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 2] + 0.7152 * c[..., 1] + 0.0722 * c[..., 0]
