"""Extract a precise frame (optionally cropped) as PNG evidence."""
from .diff import _imwrite_png, load_frame
from .ffutil import ToolError, r4

STEP_DEFAULT = 0.5


def shot(path, out, at=None, at_text=None, crop=None, step=STEP_DEFAULT):
    if (at is None) == (at_text is None):
        raise ToolError("give exactly one of --at or --at-text")
    result = {"found": True, "out": out}
    if at_text is not None:
        from .when import when
        hit = when(path, text=at_text, step=step)
        if not hit["found"]:
            return {"found": False, "out": None, "query": at_text}
        at = hit["first_s"] + step / 2  # land inside the visible interval
        result["query"] = at_text
    img = load_frame(path, at)
    if crop is not None:
        x, y, w, h = crop
        if w <= 0 or h <= 0 or x < 0 or y < 0 \
                or x + w > img.shape[1] or y + h > img.shape[0]:
            raise ToolError(
                f"--crop {x},{y},{w},{h} is outside the {img.shape[1]}x{img.shape[0]} frame"
            )
        img = img[y:y + h, x:x + w]
    _imwrite_png(out, img)
    result.update({"at_s": r4(at), "width": img.shape[1], "height": img.shape[0]})
    return result
