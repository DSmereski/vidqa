import subprocess
import sys

import pytest

from vidqa.load import load


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    """1 s blank, 1 s of changing content, then 2 s visually settled."""
    clip = tmp_path_factory.mktemp("load") / "staged.mp4"
    drawtext = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                "text='LOADED':fontsize=40:fontcolor=white:x=90:y=100")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=black:duration=1:size=320x240:rate=25",
         "-f", "lavfi", "-i", "smptebars=duration=0.5:size=320x240:rate=25",
         "-f", "lavfi", "-i", "testsrc2=duration=0.5:size=320x240:rate=25",
         "-f", "lavfi", "-i", "color=steelblue:duration=2:size=320x240:rate=25",
         "-filter_complex",
         f"[3:v]{drawtext}[d];[0:v][1:v][2:v][d]concat=n=4:v=1:a=0[out]",
         "-map", "[out]", "-c:v", "libx264", "-qp", "0",
         "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )
    return clip


def test_content_and_settle_located(staged):
    result = load(str(staged))
    assert result["pass"] is True
    assert abs(result["first_content_s"] - 1.0) <= 0.5
    assert abs(result["settled_s"] - 2.0) <= 0.5


def test_deadline_gates(staged):
    ok = run_cli("load", str(staged), "--settled-by", "3")
    assert ok.returncode == 0
    late = run_cli("load", str(staged), "--settled-by", "1.5")
    assert late.returncode == 1
    slow_content = run_cli("load", str(staged), "--content-by", "0.5")
    assert slow_content.returncode == 1


def test_never_blank_clip(media):
    result = load(str(media["clean"]))
    assert result["first_content_s"] == 0.0
    assert result["pass"] is True


def test_deterministic(staged):
    first = run_cli("load", str(staged))
    second = run_cli("load", str(staged))
    assert first.stdout == second.stdout
