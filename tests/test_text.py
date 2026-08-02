import json
import subprocess
import sys

import pytest

from vidqa.ffutil import jdump
from vidqa.text import text


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def ui_video(tmp_path_factory):
    """6 s clip: a persistent banner plus a 1.5 s toast at t=2."""
    path = tmp_path_factory.mktemp("textmedia") / "ui.mp4"
    banner = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
              "text='WELCOME HOME':fontsize=40:fontcolor=white:"
              "box=1:boxcolor=black:boxborderw=12:x=40:y=60")
    toast = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
             "text='SAVED OK':fontsize=40:fontcolor=white:"
             "box=1:boxcolor=black:boxborderw=12:x=40:y=200:"
             "enable='between(t,2,3.5)'")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=duration=6:size=640x360:rate=25",
         "-vf", f"{banner},{toast}", "-c:v", "libx264", "-qp", "0",
         "-pix_fmt", "yuv420p", str(path)],
        check=True)
    return str(path)


def find_line(result, needle):
    hits = [e for e in result["lines"] if needle in e["text"].upper()]
    assert hits, f"{needle} not indexed: {[e['text'] for e in result['lines']]}"
    return hits[0]


def test_index_banner_and_toast(ui_video):
    result = text(ui_video)
    banner = find_line(result, "WELCOME")
    toast = find_line(result, "SAVED")
    assert banner["first_s"] == 0.0
    assert banner["toast"] is False
    assert 1.5 <= toast["first_s"] <= 2.5  # +/- one sample step of t=2
    assert 1.0 <= toast["total_s"] <= 3.0
    assert toast["toast"] is True


def test_contains_filters_and_gates(ui_video):
    result = text(ui_video, contains="saved")
    assert result["line_count"] >= 1
    assert all("SAVED" in e["text"].upper() for e in result["lines"])
    proc = run_cli("text", ui_video, "--contains", "ZEBRA")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["line_count"] == 0
    assert run_cli("text", ui_video, "--contains", "saved").returncode == 0


def test_deterministic(ui_video):
    assert jdump(text(ui_video)) == jdump(text(ui_video))
