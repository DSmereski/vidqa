import pytest

from vidqa.ffutil import ToolError
from vidqa.probe import probe


def test_probe_clean(media):
    result = probe(str(media["clean"]))
    assert result["video"]["width"] == 320
    assert result["video"]["height"] == 240
    assert result["video"]["fps_avg"] == 25.0
    assert result["video"]["fps_mode"] == "cfr"
    assert 1.9 <= result["duration_s"] <= 2.1
    assert result["audio"] is None


def test_probe_audio_stream_reported(media):
    result = probe(str(media["av"]))
    assert result["audio"] == {"codec": "aac", "sample_rate": 44100,
                               "channels": 1}


def test_probe_flags_vfr(media):
    # the gap fixture keeps timestamps across dropped frames -> irregular pts
    assert probe(str(media["gap"]))["video"]["fps_mode"] == "vfr-suspected"


def test_probe_audio_only_raises(media):
    with pytest.raises(ToolError):
        probe(str(media["silence_wav"]))
