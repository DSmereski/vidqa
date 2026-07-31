"""Container/stream facts: codecs, fps, duration, CFR/VFR hint."""
from .ffutil import ToolError, ffprobe_json, r4


def probe(path):
    data = ffprobe_json(path, "-show_format", "-show_streams")
    fmt = data.get("format", {})
    video = None
    audio = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and video is None:
            avg = _fps(s.get("avg_frame_rate"))
            real = _fps(s.get("r_frame_rate"))
            if avg is None or real is None:
                mode = "unknown"
            elif abs(avg - real) < 0.01:
                mode = "cfr"
            else:
                mode = "vfr-suspected"
            video = {
                "codec": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "pix_fmt": s.get("pix_fmt"),
                "fps_avg": r4(avg) if avg else None,
                "fps_mode": mode,
            }
        elif s.get("codec_type") == "audio" and audio is None:
            rate = _num(s.get("sample_rate"))
            audio = {
                "codec": s.get("codec_name"),
                "sample_rate": int(rate) if rate is not None else None,
                "channels": s.get("channels"),
            }
    if video is None:
        raise ToolError(f"no video stream in {path}")
    duration = _num(fmt.get("duration"))
    return {
        "container": fmt.get("format_name"),
        "duration_s": r4(duration) if duration is not None else None,
        "video": video,
        "audio": audio,
    }


def _num(value):
    """ffprobe emits "N/A"/null for missing numerics; treat those as absent."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fps(rate):
    if not rate or "/" not in rate:
        return None
    num, den = rate.split("/")
    if int(den) == 0:
        return None
    return int(num) / int(den)
