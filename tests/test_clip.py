import subprocess
import sys

from vidqa.clip import clip


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_mp4_excerpt_duration(media, tmp_path):
    out = tmp_path / "cut.mp4"
    result = clip(str(media["clean"]), str(out), 0.4, 1.6)
    assert out.exists()
    assert abs(result["duration_s"] - 1.2) <= 0.25
    assert result["format"] == "mp4"


def test_av_excerpt_keeps_audio(media, tmp_path):
    out = tmp_path / "cut.mp4"
    clip(str(media["av"]), str(out), 0.5, 1.5)
    from vidqa.probe import probe
    info = probe(str(out))
    assert info["audio"] is not None
    assert abs(info["duration_s"] - 1.0) <= 0.25


def test_gif_excerpt(media, tmp_path):
    out = tmp_path / "cut.gif"
    result = clip(str(media["clean"]), str(out), 0.0, 1.0)
    assert out.exists() and result["format"] == "gif"
    assert abs(result["duration_s"] - 1.0) <= 0.35


def test_bad_range_exits_2(media, tmp_path):
    proc = run_cli("clip", str(media["clean"]), "--out", str(tmp_path / "x.mp4"),
                   "--from", "1.5", "--to", "1.0")
    assert proc.returncode == 2
