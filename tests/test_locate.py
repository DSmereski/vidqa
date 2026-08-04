import subprocess
import sys

from vidqa.ffutil import jdump
from vidqa.locate import locate
from vidqa.ocr import ocr


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_locate_finds_last_good_first_bad(media, tmp_path):
    # flash shows ERROR 500 only for t=1..2; step 0.5 puts first-bad at 1.0
    result = locate(str(media["flash"]), "ERROR", shots=str(tmp_path))
    assert result["found"] is True
    assert abs(result["first_bad_s"] - 1.0) <= 0.5  # text turns on at t=1
    assert result["last_good_s"] == result["first_bad_s"] - 0.5
    good, bad = result["shots"]
    assert good.endswith("last_good.png") and bad.endswith("first_bad.png")
    assert "ERROR" not in ocr(good)["joined"].upper()
    assert "ERROR" in ocr(bad)["joined"].upper()


def test_locate_stops_scanning_at_first_hit(media):
    # 3 s clip at step 0.5 has 6-7 samples; the scan must stop at the hit
    result = locate(str(media["flash"]), "ERROR")
    assert result["sampled"] == int(result["first_bad_s"] / 0.5) + 1
    assert "shots" not in result


def test_locate_respects_step(media):
    # step 1.2 samples t=0, 1.2 -> first hit is sample 1 (inside the t=1..2 window)
    result = locate(str(media["flash"]), "ERROR", step=1.2)
    assert result["first_bad_s"] == 1.2 and result["last_good_s"] == 0.0


def test_locate_hit_on_first_sample_has_no_last_good(media, tmp_path):
    always = tmp_path / "always.mp4"
    drawtext = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                "text='ERROR 500':fontsize=40:fontcolor=white:"
                "box=1:boxcolor=black:boxborderw=12:x=40:y=100")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=duration=1:size=320x240:rate=25",
         "-vf", drawtext, "-c:v", "libx264", "-qp", "0",
         "-pix_fmt", "yuv420p", str(always)], check=True)
    result = locate(str(always), "ERROR", shots=str(tmp_path / "s"))
    assert result["first_bad_s"] == 0.0 and result["last_good_s"] is None
    assert [p for p in result["shots"]] == \
        [str(tmp_path / "s" / "first_bad.png")]


def test_locate_missing_text_exits_1(media, tmp_path):
    proc = run_cli("locate", str(media["flash"]), "ZEBRA",
                   "--shots", str(tmp_path / "none"))
    assert proc.returncode == 1
    import json
    assert json.loads(proc.stdout)["found"] is False
    assert not (tmp_path / "none" / "first_bad.png").exists()


def test_locate_deterministic(media):
    assert jdump(locate(str(media["flash"]), "ERROR")) == \
        jdump(locate(str(media["flash"]), "ERROR"))


def test_locate_empty_text_errors(media):
    proc = run_cli("locate", str(media["flash"]), "  ")
    assert proc.returncode == 2
