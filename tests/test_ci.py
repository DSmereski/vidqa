import json
import subprocess
import sys

import pytest

from vidqa.ci import ci


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def rules_file(tmp_path, *rules):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"rules": list(rules)}), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def error_page(tmp_path_factory):
    """2 s clip showing a classic error page phrase."""
    clip = tmp_path_factory.mktemp("ci") / "error.mp4"
    drawtext = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                "text='Internal Server Error':fontsize=28:fontcolor=white:"
                "box=1:boxcolor=black:boxborderw=10:x=20:y=100")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=duration=2:size=320x240:rate=25",
         "-vf", drawtext, "-c:v", "libx264", "-qp", "0",
         "-pix_fmt", "yuv420p", str(clip)], check=True)
    return clip


def test_all_rules_pass(media, tmp_path):
    rules = rules_file(
        tmp_path,
        {"type": "expect_text", "text": "ERROR", "by_s": 2.5},
        {"type": "expect_template", "file": str(media["flash_tpl"]), "by_s": 2.5},
        {"type": "max_freeze_s", "seconds": 2},
        {"type": "no_blank_frames"},
    )
    result = ci(str(media["flash"]), rules)
    assert result["pass"] is True
    assert all(r["pass"] for r in result["rules"])


def test_deadline_miss_fails_with_detail(media, tmp_path):
    rules = rules_file(tmp_path, {"type": "expect_text", "text": "ERROR", "by_s": 0.5})
    proc = run_cli("ci", str(media["flash"]), "--rules", rules)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["pass"] is False
    assert "after by_s" in out["rules"][0]["detail"]["reason"]


def test_builtin_error_wordlist_catches_error_page(error_page, media, tmp_path):
    rules = rules_file(tmp_path, {"type": "forbid_text", "builtin": "error_pages"})
    bad = ci(str(error_page), rules)
    assert bad["pass"] is False
    assert bad["rules"][0]["detail"]["word"] == "internal server error"
    good = ci(str(media["clean"]), rules)
    assert good["pass"] is True


def test_blank_frames_fail(media, tmp_path):
    rules = rules_file(tmp_path, {"type": "no_blank_frames"})
    assert ci(str(media["red"]), rules)["pass"] is False
    assert ci(str(media["clean"]), rules)["pass"] is True


def test_freeze_rule(media, tmp_path):
    rules = rules_file(tmp_path, {"type": "max_freeze_s", "seconds": 0.3})
    proc = run_cli("ci", str(media["freeze"]), "--rules", rules)
    assert proc.returncode == 1  # fixture has a 0.52 s freeze
    ok = rules_file(tmp_path, {"type": "max_freeze_s", "seconds": 1.0})
    assert run_cli("ci", str(media["freeze"]), "--rules", ok).returncode == 0


def test_malformed_rules_exit_2_not_1(media, tmp_path):
    bogus = rules_file(tmp_path, {"type": "bogus"})
    assert run_cli("ci", str(media["clean"]), "--rules", bogus).returncode == 2
    notjson = tmp_path / "bad.json"
    notjson.write_text("{nope", encoding="utf-8")
    assert run_cli("ci", str(media["clean"]), "--rules", str(notjson)).returncode == 2
