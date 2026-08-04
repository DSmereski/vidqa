import subprocess
import sys

import cv2
import numpy as np

from vidqa.diff import load_frame
from vidqa.shot import shot


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_shot_at_matches_direct_extraction(media, tmp_path):
    out = tmp_path / "frame.png"
    result = shot(str(media["clean"]), str(out), at=1.0)
    assert result["found"] is True and out.exists()
    assert np.array_equal(cv2.imread(str(out)), load_frame(str(media["clean"]), 1.0))


def test_crop_dimensions(media, tmp_path):
    out = tmp_path / "crop.png"
    result = shot(str(media["clean"]), str(out), at=1.0, crop=[10, 20, 100, 50])
    assert (result["width"], result["height"]) == (100, 50)
    assert cv2.imread(str(out)).shape[:2] == (50, 100)


def test_crop_out_of_bounds_errors(media, tmp_path):
    proc = run_cli("shot", str(media["clean"]), "--out", str(tmp_path / "x.png"),
                   "--at", "1", "--crop", "300,0,100,50")
    assert proc.returncode == 2


def test_at_text_lands_on_visible_text(media, tmp_path):
    out = tmp_path / "err.png"
    result = shot(str(media["flash"]), str(out), at_text="ERROR")
    assert result["found"] is True
    assert 1.0 <= result["at_s"] <= 2.5
    from vidqa.ocr import ocr
    assert "ERROR" in ocr(str(out))["joined"].upper()


def test_annotate_draws_box_and_echoes(media, tmp_path):
    out = tmp_path / "ann.png"
    result = shot(str(media["clean"]), str(out), at=1.0,
                  annotate=[[10, 20, 100, 50, "bug here"]])
    assert result["annotations"] == [[10, 20, 100, 50, "bug here"]]
    img = cv2.imread(str(out))
    assert tuple(img[20, 60]) == (0, 0, 255)  # top edge stroke, BGR red
    assert tuple(img[70, 60]) == (0, 0, 255)  # bottom edge stroke


def test_annotate_out_of_bounds_errors(media, tmp_path):
    proc = run_cli("shot", str(media["clean"]), "--out", str(tmp_path / "x.png"),
                   "--at", "1", "--annotate", "300,0,100,50,oops")
    assert proc.returncode == 2


def test_around_writes_before_after_pair(media, tmp_path):
    result = shot(str(media["cut"]), str(tmp_path / "pair.png"), around=1.0)
    before, after = tmp_path / "pair_before.png", tmp_path / "pair_after.png"
    assert before.exists() and after.exists()
    assert result["found"] is True
    assert result["before_s"] == 0.5 and result["after_s"] == 1.5
    assert result["before"] == str(before) and result["after"] == str(after)
    # cut switches red -> smpte bars at t=1, so the pair must differ
    assert not np.array_equal(cv2.imread(str(before)), cv2.imread(str(after)))


def test_around_clamps_to_video(media, tmp_path):
    result = shot(str(media["clean"]), str(tmp_path / "p.png"), around=0.1)
    assert result["before_s"] == 0.0
    result = shot(str(media["clean"]), str(tmp_path / "q.png"), around=1.9)
    assert 1.8 <= result["after_s"] <= 2.0  # clean is 2 s


def test_around_crop_applies_to_both(media, tmp_path):
    result = shot(str(media["clean"]), str(tmp_path / "c.png"), around=1.0,
                  crop=[10, 20, 100, 50])
    for p in (result["before"], result["after"]):
        assert cv2.imread(p).shape[:2] == (50, 100)


def test_around_excludes_at(media, tmp_path):
    proc = run_cli("shot", str(media["clean"]), "--out", str(tmp_path / "x.png"),
                   "--at", "1", "--around", "1")
    assert proc.returncode == 2


def test_at_text_missing_exits_1_and_writes_nothing(media, tmp_path):
    out = tmp_path / "no.png"
    proc = run_cli("shot", str(media["flash"]), "--out", str(out),
                   "--at-text", "ZEBRA")
    assert proc.returncode == 1
    assert not out.exists()
