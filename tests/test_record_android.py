import json
import os
import subprocess
import sys

import pytest

from vidqa.record_android import record_android

pytestmark = pytest.mark.skipif(sys.platform != "win32",
                                reason="fake adb shim is a .bat file")

OK_ADB = """@echo off
if "%1"=="get-state" (echo device) & (exit /b 0)
if "%1"=="pull" (copy /y "%VIDQA_FAKE_PULL_SRC%" "%~3" >nul) & (exit /b 0)
exit /b 0
"""

DEAD_ADB = """@echo off
if "%1"=="get-state" (echo offline) & (exit /b 1)
exit /b 1
"""


@pytest.fixture()
def fake_adb(tmp_path, media, monkeypatch):
    (tmp_path / "adb.bat").write_text(OK_ADB, encoding="ascii")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("VIDQA_FAKE_PULL_SRC", str(media["clean"]))
    return tmp_path


def test_records_runs_cmd_and_reports(fake_adb, tmp_path):
    out = tmp_path / "rec.mp4"
    ok = f'"{sys.executable}" -c "pass"'
    result = record_android(ok, str(out), settle=0.05)
    assert out.exists()
    assert result["cmd_exit"] == 0
    assert result["duration_s"] > 0
    assert result["size"] == [320, 240]


def test_cmd_failure_maps_to_exit_1(fake_adb, tmp_path):
    out = tmp_path / "rec.mp4"
    bad = f'"{sys.executable}" -c "import sys; sys.exit(3)"'
    proc = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "record-android",
         "--while", bad, "--out", str(out)],
        capture_output=True, text=True, env=os.environ.copy(),
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["cmd_exit"] == 3
    assert out.exists()  # the recording still lands even when the test fails


def test_no_device_is_clean_error(tmp_path, monkeypatch):
    (tmp_path / "adb.bat").write_text(DEAD_ADB, encoding="ascii")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    with pytest.raises(Exception) as exc:
        record_android("echo hi", str(tmp_path / "x.mp4"), settle=0.05)
    assert "no Android device" in str(exc.value)
