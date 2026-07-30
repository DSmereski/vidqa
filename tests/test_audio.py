import pytest

from vidqa.audio import audio
from vidqa.ffutil import ToolError


def test_silence_detected(media):
    result = audio(str(media["silence_wav"]))
    assert result["silence_count"] >= 1
    longest = max(s["duration_s"] or 0 for s in result["silences"])
    assert 1.7 <= longest <= 2.3
    assert result["clipping_suspected"] is False


def test_clipping_detected(media):
    result = audio(str(media["clipped_wav"]))
    assert result["clipping_suspected"] is True
    assert result["max_volume_db"] >= -0.1


def test_no_audio_stream_is_an_error(media):
    with pytest.raises(ToolError, match="no audio stream"):
        audio(str(media["clean"]))
