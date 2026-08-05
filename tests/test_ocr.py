import subprocess
import sys

from vidqa.ocr import ocr


def test_reads_hud_text(media):
    result = ocr(str(media["text"]))
    joined = result["joined"].upper()
    assert "GAME" in joined
    assert "12345" in joined
    assert result["block_count"] >= 1


def test_textless_frame_yields_empty_result(media):
    result = ocr(str(media["red"]), at=0.5)
    assert result["block_count"] == 0
    assert result["joined"] == ""


def test_textless_frame_keeps_stderr_clean(media):
    """rapidocr logs a WARNING per textless frame; it must not reach stderr."""
    proc = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "ocr", str(media["red"]), "--at", "0.5"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert proc.stderr == ""
