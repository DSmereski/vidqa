"""Extract a precise frame (optionally annotated/cropped) as PNG evidence."""
import cv2

from .diff import _imwrite_png, load_frame
from .ffutil import ToolError, r4

STEP_DEFAULT = 0.5
BOX_COLOR = (0, 0, 255)  # BGR red


def shot(path, out, at=None, at_text=None, crop=None, step=STEP_DEFAULT,
         annotate=None):
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
    _imwrite_png(out, img)
    result.update({"at_s": r4(at), "width": img.shape[1], "height": img.shape[0]})
    return result
