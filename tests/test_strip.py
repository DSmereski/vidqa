import hashlib
import subprocess
import sys

import cv2

from vidqa.strip import strip


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_grid_geometry(media, tmp_path):
    out = tmp_path / "sheet.png"
    result = strip(str(media["clean"]), str(out), every=1.0)
    assert out.exists()
    assert result["frames"] == 2  # 2 s clip sampled at 1 s
    assert result["cols"] == 2 and result["rows"] == 1
    img = cv2.imread(str(out))
    assert [img.shape[1], img.shape[0]] == result["size"]
    assert result["size"][0] == result["cols"] * result["thumb"][0]
    assert result["size"][1] == result["rows"] * result["thumb"][1]


def test_deterministic_bytes(media, tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    first = run_cli("strip", str(media["clean"]), "--out", str(a))
    second = run_cli("strip", str(media["clean"]), "--out", str(b))
    assert first.returncode == second.returncode == 0
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_bad_every_exits_2(media, tmp_path):
    proc = run_cli("strip", str(media["clean"]), "--out", str(tmp_path / "x.png"),
                   "--every", "0")
    assert proc.returncode == 2
