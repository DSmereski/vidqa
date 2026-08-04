"""Speech transcription via faster-whisper (optional dependency, local CPU)."""
import os
import tempfile

from .ffutil import ToolError, r4, run

MODEL_DEFAULT = "large-v3-turbo"
TEXT_CAP = 3500


FIND_CAP = 20


def speech(path, model=MODEL_DEFAULT, expect=None, full=False, find=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ToolError(
            "faster-whisper is not installed: pip install faster-whisper "
            "(or pip install vidqa[speech])"
        )
    wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.close()
    try:
        try:
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav.name])
        except ToolError as exc:
            if "does not contain any stream" in getattr(exc, "stderr", str(exc)).lower():
                raise ToolError("no audio stream to transcribe")
            raise
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segments, info = m.transcribe(wav.name, temperature=0.0, beam_size=1)
        segs = [{"start": r4(s.start), "end": r4(s.end), "text": s.text.strip()}
                for s in segments]
    finally:
        os.unlink(wav.name)
    text = " ".join(s["text"] for s in segs)
    out = {
        "language": info.language,
        "language_prob": r4(info.language_probability),
        "model": model,
        "segment_count": len(segs),
        "text": text if full else text[:TEXT_CAP],
        "truncated": bool(not full and len(text) > TEXT_CAP),
    }
    if expect is not None:
        out["expect_found"] = expect.lower() in text.lower()
    if find is not None:
        matches = [s for s in segs if find.lower() in s["text"].lower()]
        out["find_matches"] = matches[:FIND_CAP]
        out["find_found"] = bool(matches)
    if full:
        out["segments"] = segs
    return out
