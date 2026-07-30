import shutil

import pytest

from vidqa.diff import diff
from vidqa.ffutil import ToolError


def test_identical_frames_pass(media):
    result = diff(str(media["same"]), str(media["golden"]))
    assert result["pass"] is True
    assert result["ssim"] >= 0.999
    assert result["phash_distance"] == 0
    assert result["scene_match"] is True


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
