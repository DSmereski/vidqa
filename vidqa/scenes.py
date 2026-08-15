"""Scene-cut detection (PySceneDetect content detector)."""
from .ffutil import r4

EVENT_CAP = 50


def scenes(path, threshold=27.0):
    import logging

    from scenedetect import ContentDetector, detect

    # scenedetect logs "Detecting scenes..." at INFO; with any root handler
    # installed (e.g. by an embedding MCP host) that leaks to stderr, and
    # vidqa's contract is a silent stderr on success — pin it, like ocr.py
    # pins rapidocr.
    logging.getLogger("pyscenedetect").setLevel(logging.ERROR)
    scene_list = detect(path, ContentDetector(threshold=threshold))
    if not scene_list:
        return {"scene_count": 1, "cuts": []}
    cuts = [r4(start.seconds) for start, _ in scene_list[1:]]
    return {"scene_count": len(scene_list), "cuts": cuts[:EVENT_CAP]}
