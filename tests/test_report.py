import json
import subprocess
import sys

from vidqa.report import report


def test_clean_video_passes(media):
    result = report(str(media["clean"]))
    assert result["verdict"]["pass"] is True
    assert result["verdict"]["issues"] == []
    assert "audio" not in result  # no audio stream, no audio section


def test_freeze_video_fails_with_named_issues(media):
    result = report(str(media["freeze"]))
    assert result["verdict"]["pass"] is False
    joined = " ".join(result["verdict"]["issues"])
    assert "freeze@" in joined
    assert "dup_ratio" in joined


def test_audio_section_included_when_present(media):
    result = report(str(media["av"]))
    assert "audio" in result
    assert result["audio"]["clipping_suspected"] is False


def test_audio_dropout_with_unknown_duration_fails_gate(media, monkeypatch):
    import vidqa.audio

    monkeypatch.setattr(vidqa.audio, "audio", lambda path: {
        "silence_count": 1,
        "silences": [{"start_s": 0.7, "duration_s": None}],
        "max_volume_db": -18.1, "mean_volume_db": -30.0,
        "clipping_suspected": False,
    })
    result = report(str(media["av"]))
    assert result["verdict"]["pass"] is False
    assert "silence@0.7s(to-end)" in result["verdict"]["issues"]


def test_golden_gate_wired_in(media):
    good = report(str(media["clean"]), golden=str(media["golden"]), at=0.5)
    assert "golden_diff_failed" not in good["verdict"]["issues"]
    bad = report(str(media["clean"]), golden=str(media["other"]), at=0.5)
    assert "golden_diff_failed" in bad["verdict"]["issues"]


def test_stutter_composes_into_verdict(media):
    result = report(str(media["gap"]))  # one 280 ms pts gap
    assert result["verdict"]["pass"] is False
    assert any(i.startswith("stutter_events=") for i in result["verdict"]["issues"])


def test_audio_clipping_composes_into_verdict(tmp_path):
    clipped = tmp_path / "clipav.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=duration=2:size=320x240:rate=25",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-af", "volume=20", "-c:v", "libx264", "-qp", "0",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clipped)],
        check=True)
    result = report(str(clipped))
    assert result["verdict"]["pass"] is False
    assert "audio_clipping" in result["verdict"]["issues"]


def test_finite_silence_threshold_both_ways(media, monkeypatch):
    import vidqa.audio

    def fake_audio(silences):
        return lambda path: {
            "silence_count": len(silences), "silences": silences,
            "max_volume_db": -18.1, "mean_volume_db": -30.0,
            "clipping_suspected": False,
        }

    monkeypatch.setattr(vidqa.audio, "audio",
                        fake_audio([{"start_s": 0.5, "duration_s": 3.0}]))
    long_silence = report(str(media["av"]))
    assert "silence@0.5s(3.0s)" in long_silence["verdict"]["issues"]
    monkeypatch.setattr(vidqa.audio, "audio",
                        fake_audio([{"start_s": 0.5, "duration_s": 1.5}]))
    short_silence = report(str(media["av"]))
    assert short_silence["verdict"]["pass"] is True


def test_cli_report_exit_codes_and_size(media):
    ok = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "report", str(media["clean"])],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0
    assert len(ok.stdout.encode()) <= 4096
    json.loads(ok.stdout)
    bad = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "report", str(media["freeze"])],
        capture_output=True, text=True,
    )
    assert bad.returncode == 1
