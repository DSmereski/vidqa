"""Locate a known UI element in a frame via template matching."""
import cv2

from .diff import load_frame
from .ffutil import ToolError, r4

THRESHOLD_DEFAULT = 0.8


def find(path, template, at=None, threshold=THRESHOLD_DEFAULT):
    img = load_frame(path, at)
    tpl = load_frame(template)
    if tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
        raise ToolError("template is larger than the frame")
    scores = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, best, _, loc = cv2.minMaxLoc(scores)
    return {
        "found": bool(best >= threshold),
        "score": r4(best),
        "x": int(loc[0]),
        "y": int(loc[1]),
        "template_size": [tpl.shape[1], tpl.shape[0]],
    }
