import shutil
import subprocess
import sys

import pytest

from vidqa.diff import diff
from vidqa.ffutil import ToolError


def test_identical_frames_pass(media):
    result = diff(str(media["same"]), str(media["golden"]))
    assert result["pass"] is True
    assert result["ssim"] >= 0.999
    assert result["phash_distance"] == 0
    assert result["scene_match"] is True


def _panel_frame(color, out):
    """Dark page with a filled panel; used for luma-matched hue-swap pairs."""
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=c=0x12141a:duration=0.1:size=320x240:rate=25",
         "-vf", f"drawbox=x=80:y=60:w=160:h=120:color={color}@1:t=fill",
         "-frames:v", "1", str(out)], check=True)
    return out


def test_hue_swap_fails_via_color_worst_cell(tmp_path):
    """Green panel vs red panel at matched gray value: SSIM and pHash are
    grayscale and blind to it — only the color worst-cell catches it."""
    green = _panel_frame("0x12301e", tmp_path / "green.png")
    red = _panel_frame("0x4a1010", tmp_path / "red.png")
    result = diff(str(red), str(green))
    assert result["pass"] is False
    assert result["worst_cell"]["mad"] > 25.0
    assert result["ssim"] >= 0.95          # grayscale SSIM misses it
    assert result["phash_distance"] <= 8   # pHash misses it too


def test_corrupt_region_fails_and_is_located(media):
    result = diff(str(media["corrupt"]), str(media["golden"]))
    assert result["pass"] is False
    # magenta box at x=200..280, y=150..210 -> grid cells rows 5-6, cols 5-6
    assert result["worst_cell"]["mad"] > 25.0
    assert result["worst_cell"]["row"] in (5, 6)
    assert result["worst_cell"]["col"] in (5, 6)


def test_wrong_scene_detected(media):
    result = diff(str(media["other"]), str(media["golden"]))
    assert result["pass"] is False
    assert result["scene_match"] is False


def test_mask_written(media, tmp_path):
    mask = tmp_path / "mask.png"
    result = diff(str(media["corrupt"]), str(media["golden"]), mask_out=str(mask))
    assert result["mask"] == str(mask)
    assert mask.exists()


def test_video_frame_extraction(media):
    result = diff(str(media["clean"]), str(media["golden"]), at=0.5)
    assert result["pass"] is True
    assert result["ssim"] >= 0.999


def test_size_mismatch_keeps_schema(media):
    result = diff(str(media["small"]), str(media["golden"]))
    assert result["pass"] is False
    assert result["reason"] == "size-mismatch"
    assert result["ssim"] is None
    assert result["golden_size"] == [320, 240]


def test_unicode_paths(media, tmp_path):
    target = tmp_path / "gøldén_频.png"
    shutil.copy(str(media["golden"]), str(target))
    result = diff(str(target), str(media["golden"]))
    assert result["pass"] is True


def test_mask_write_failure_raises(media, tmp_path):
    missing_dir = tmp_path / "nope" / "mask.png"
    with pytest.raises(ToolError):
        diff(str(media["corrupt"]), str(media["golden"]), mask_out=str(missing_dir))


def test_ignore_rect_excuses_dynamic_region(media):
    bare = diff(str(media["corrupt"]), str(media["golden"]))
    assert bare["pass"] is False
    excused = diff(str(media["corrupt"]), str(media["golden"]),
                   ignore=[[200, 150, 80, 60]])  # exactly the seeded box
    assert excused["pass"] is True
    assert excused["ignored"] == [[200, 150, 80, 60]]


def test_ignore_out_of_bounds_raises(media):
    with pytest.raises(ToolError):
        diff(str(media["same"]), str(media["golden"]), ignore=[[300, 0, 100, 50]])


def test_threshold_knobs_route(tmp_path):
    """cell_max and ssim_min are the two verdict gates; each provably owns
    the pass/fail on its own (hue pair measures mad 55, ssim 0.9976)."""
    green = _panel_frame("0x12301e", tmp_path / "green.png")
    red = _panel_frame("0x4a1010", tmp_path / "red.png")
    assert diff(str(red), str(green))["pass"] is False
    loosened = diff(str(red), str(green), cell_max=100)
    assert loosened["pass"] is True
    strict = diff(str(red), str(green), cell_max=100, ssim_min=0.999)
    assert strict["pass"] is False
    proc = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "diff", str(red),
         "--golden", str(green), "--cell-max", "100"],
        capture_output=True, text=True)
    assert proc.returncode == 0  # the CLI flag reaches the same gate
