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


def test_at_text_missing_exits_1_and_writes_nothing(media, tmp_path):
    out = tmp_path / "no.png"
    proc = run_cli("shot", str(media["flash"]), "--out", str(out),
                   "--at-text", "ZEBRA")
    assert proc.returncode == 1
    assert not out.exists()
