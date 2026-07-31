"""Read text off a frame with RapidOCR (PP-OCR models on ONNX Runtime, CPU)."""
from .diff import load_frame
from .ffutil import r4

BLOCK_CAP = 50

_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def scan_text(img):
    """OCR a BGR frame array -> joined text (internal reuse, e.g. `when`)."""
    out = _engine()(img)
    return " ".join(str(t) for t in (getattr(out, "txts", None) or []))


def ocr(path, at=None):
    img = load_frame(path, at)
    out = _engine()(img)
    txts = list(getattr(out, "txts", None) or [])
    scores = list(getattr(out, "scores", None) or [])
    boxes = getattr(out, "boxes", None)
    blocks = []
    for i, text in enumerate(txts):
        conf = scores[i] if i < len(scores) else 0.0
        box = None
        if boxes is not None and i < len(boxes):
            xs = [int(p[0]) for p in boxes[i]]
            ys = [int(p[1]) for p in boxes[i]]
            box = [min(xs), min(ys), max(xs), max(ys)]
        blocks.append({"text": str(text), "conf": r4(conf), "box": box})
    capped = blocks[:BLOCK_CAP]
    return {
        "block_count": len(blocks),
        "blocks": capped,
        "joined": " ".join(b["text"] for b in capped),
    }
