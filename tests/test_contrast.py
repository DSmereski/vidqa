import subprocess
import sys

import pytest

from vidqa.contrast import contrast
from vidqa.ffutil import ToolError, jdump


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def _text_png(path, fontcolor, boxcolor):
    drawtext = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                f"text='SCORE 12345 GAME OVER':fontsize=48:fontcolor={fontcolor}:"
                f"box=1:boxcolor={boxcolor}:boxborderw=20:x=40:y=150")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"color={boxcolor}:size=640x360:rate=1:duration=1",
         "-frames:v", "1", "-vf", drawtext, str(path)], check=True)
    return str(path)


def test_high_contrast_passes(media):
    # conftest's text fixture is white-on-black 48px (ratio ~21)
    result = contrast(str(media["text"]))
    assert result["checked"] >= 1
    assert result["pass"] is True and result["flagged"] == []


def test_low_contrast_flagged(tmp_path):
    img = _text_png(tmp_path / "gray.png", "0x999999", "0x555555")
    result = contrast(img)
    assert result["checked"] >= 1, "OCR must still detect the gray text"
    assert result["pass"] is False
    assert result["flagged"][0]["ratio"] < 4.5
    assert "box" in result["flagged"][0]
    proc = run_cli("contrast", img)
    assert proc.returncode == 1


def test_min_ratio_floor_is_adjustable(tmp_path):
    img = _text_png(tmp_path / "gray2.png", "0x999999", "0x555555")
    result = contrast(img, min_ratio=1.05)
    assert result["pass"] is True  # same text passes a permissive floor


def test_bad_min_ratio_errors(media):
    with pytest.raises(ToolError):
        contrast(str(media["text"]), min_ratio=0.5)


def test_deterministic(media):
    assert jdump(contrast(str(media["text"]))) == \
        jdump(contrast(str(media["text"])))
