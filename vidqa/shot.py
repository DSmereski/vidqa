"""Extract a precise frame (optionally annotated/cropped) as PNG evidence."""
import os

import cv2
import numpy as np

from .diff import _imwrite_png, load_frame
from .ffutil import ToolError, r4

STEP_DEFAULT = 0.5
GAP_DEFAULT = 0.5
BOX_COLOR = (0, 0, 255)  # BGR red
ZOOM_DIFF_MIN = 25  # per-channel delta that counts as a change
ZOOM_PAD = 16


def shot(path, out, at=None, at_text=None, crop=None, step=STEP_DEFAULT,
         annotate=None, around=None, gap=GAP_DEFAULT, zoom=False):
    if sum(x is not None for x in (at, at_text, around)) != 1:
        raise ToolError("give exactly one of --at, --at-text, or --around")
    if zoom and around is None:
        raise ToolError("--zoom only makes sense with --around")
    if around is not None:
        return _pair(path, out, around, gap, annotate, crop, zoom)
    result = {"found": True, "out": out}
    if at_text is not None:
        from .when import when
        hit = when(path, text=at_text, step=step)
        if not hit["found"]:
            return {"found": False, "out": None, "query": at_text}
        at = hit["first_s"] + step / 2  # land inside the visible interval
        result["query"] = at_text
    img = _render(load_frame(path, at), annotate, crop, result)
    _imwrite_png(out, img)
    result.update({"at_s": r4(at), "width": img.shape[1], "height": img.shape[0]})
    return result


def _pair(path, out, around, gap, annotate, crop, zoom=False):
    """Before/after evidence pair for "what changed" at a moment."""
    if gap <= 0:
        raise ToolError("--gap must be positive")
    if zoom and crop is not None:
        raise ToolError("--zoom and --crop are mutually exclusive")
    from .probe import probe
    duration = probe(path)["duration_s"]
    end = max(0.0, (duration if duration is not None else around) - 0.05)
    times = (("before", max(0.0, around - gap)),
             ("after", min(end, around + gap)))
    imgs = {tag: load_frame(path, t) for tag, t in times}
    result = {"found": True, "around_s": r4(around), "gap_s": r4(gap)}
    if zoom:
        crop = _change_rect(imgs["before"], imgs["after"])
        result["zoom"] = crop  # None = nothing changed, full frames written
    root, ext = os.path.splitext(out)
    for tag, t in times:
        img = _render(imgs[tag], annotate, crop, result)
        p = f"{root}_{tag}{ext or '.png'}"
        _imwrite_png(p, img)
        result[tag] = p
        result[f"{tag}_s"] = r4(t)
    result.update({"width": img.shape[1], "height": img.shape[0]})
    return result


def _change_rect(a, b):
    """Padded bounding box of where two frames differ, or None if they don't."""
    delta = cv2.absdiff(a, b).max(axis=2)
    ys, xs = np.nonzero(delta > ZOOM_DIFF_MIN)
    if len(xs) == 0:
        return None
    x0 = max(0, int(xs.min()) - ZOOM_PAD)
    y0 = max(0, int(ys.min()) - ZOOM_PAD)
    x1 = min(a.shape[1], int(xs.max()) + 1 + ZOOM_PAD)
    y1 = min(a.shape[0], int(ys.max()) + 1 + ZOOM_PAD)
    return [x0, y0, x1 - x0, y1 - y0]


def _render(img, annotate, crop, result):
    if annotate:  # video pixel space, drawn before any --crop
        for x, y, w, h, label in annotate:
            if w <= 0 or h <= 0 or x < 0 or y < 0 \
                    or x + w > img.shape[1] or y + h > img.shape[0]:
                raise ToolError(
                    f"--annotate {x},{y},{w},{h} is outside the "
                    f"{img.shape[1]}x{img.shape[0]} frame"
                )
            cv2.rectangle(img, (x, y), (x + w, y + h), BOX_COLOR, 3)
            if label:
                cv2.putText(img, label, (x, max(y - 8, 16)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, BOX_COLOR, 2)
        result["annotations"] = [[x, y, w, h] + ([label] if label else [])
                                 for x, y, w, h, label in annotate]
    if crop is not None:
        x, y, w, h = crop
        if w <= 0 or h <= 0 or x < 0 or y < 0 \
                or x + w > img.shape[1] or y + h > img.shape[0]:
            raise ToolError(
                f"--crop {x},{y},{w},{h} is outside the {img.shape[1]}x{img.shape[0]} frame"
            )
        img = img[y:y + h, x:x + w]
    return img
