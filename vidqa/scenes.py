"""Scene-cut detection (PySceneDetect content detector)."""
from .ffutil import r4

EVENT_CAP = 50


def scenes(path, threshold=27.0):
    from scenedetect import ContentDetector, detect

    scene_list = detect(path, ContentDetector(threshold=threshold))
    if not scene_list:
        return {"scene_count": 1, "cuts": []}
    cuts = [r4(start.seconds) for start, _ in scene_list[1:]]
    return {"scene_count": len(scene_list), "cuts": cuts[:EVENT_CAP]}
