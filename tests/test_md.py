import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_ci_md_pass(media, tmp_path):
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps({"rules": [{"type": "expect_text", "text": "ERROR"}]}),
        encoding="utf-8")
    md = tmp_path / "report.md"
    proc = run_cli("ci", str(media["flash"]), "--rules", str(rules),
                   "--md", str(md))
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["md"] == str(md)
    content = md.read_text(encoding="utf-8")
    assert "PASS" in content and "expect_text" in content and "✅" in content


def test_ci_md_fail_marks_the_failing_rule(media, tmp_path):
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"rules": [
        {"type": "expect_text", "text": "ERROR"},
        {"type": "expect_text", "text": "ZEBRA"},
    ]}), encoding="utf-8")
    md = tmp_path / "report.md"
    proc = run_cli("ci", str(media["flash"]), "--rules", str(rules),
                   "--md", str(md))
    assert proc.returncode == 1
    content = md.read_text(encoding="utf-8")
    assert "FAIL" in content and "❌" in content and "never visible" in content
    assert "✅" in content  # the passing rule still shows


def test_rundiff_md_diverged(media, tmp_path):
    md = tmp_path / "diff.md"
    proc = run_cli("rundiff", str(media["clean"]), str(media["cut"]),
                   "--md", str(md))
    assert proc.returncode == 1
    content = md.read_text(encoding="utf-8")
    assert "diverged" in content and "first divergence" in content


def test_rundiff_md_same(media, tmp_path):
    md = tmp_path / "same.md"
    proc = run_cli("rundiff", str(media["clean"]), str(media["clean"]),
                   "--md", str(md))
    assert proc.returncode == 0
    assert "same" in md.read_text(encoding="utf-8")
