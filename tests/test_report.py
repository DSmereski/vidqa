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
