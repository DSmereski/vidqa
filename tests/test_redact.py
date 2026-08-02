import subprocess
import sys

from vidqa.diff import load_frame
from vidqa.probe import probe
from vidqa.redact import redact
from vidqa.when import when


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_redacted_text_is_gone(media, tmp_path):
    out = tmp_path / "red.mp4"
    result = redact(str(media["flash"]), str(out), [[20, 80, 260, 90]])
    assert result["regions"] == [[20, 80, 260, 90]]
    frame = load_frame(str(out), 1.5)  # mid error-flash
    assert frame[80:170, 20:280].mean() < 8.0  # solid black (crf noise aside)
    assert when(str(out), text="ERROR")["found"] is False


def test_audio_passes_through(media, tmp_path):
    out = tmp_path / "reda.mp4"
    redact(str(media["av"]), str(out), [[0, 0, 50, 50]])
    assert probe(str(out))["audio"] is not None


def test_bad_region_errors_and_writes_nothing(media, tmp_path):
    out = tmp_path / "x.mp4"
    proc = run_cli("redact", str(media["flash"]), "--out", str(out),
                   "--region", "300,0,100,50")
    assert proc.returncode == 2
    assert not out.exists()
