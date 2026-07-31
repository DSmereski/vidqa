"""Record an Android device's screen while a command runs (adb screenrecord)."""
import os
import shutil
import subprocess
import time

from .ffutil import ToolError

DEVICE_TMP = "/sdcard/vidqa-record.mp4"


def _wait_gone(base, tries=20):
    """True once no screenrecord process remains on the device."""
    for _ in range(tries):
        check = subprocess.run(base + ["shell", "pgrep", "screenrecord"],
                               capture_output=True, text=True)
        if not check.stdout.strip():
            return True
        time.sleep(0.5)
    return False


def record_android(cmd, out, serial=None, settle=1.0):
    adb = shutil.which("adb") or os.environ.get("VIDQA_ADB")
    if adb is None:
        raise ToolError("adb not found on PATH (set VIDQA_ADB or install platform-tools)")
    base = [adb] + (["-s", serial] if serial else [])
    state = subprocess.run(base + ["get-state"], capture_output=True, text=True)
    if state.returncode != 0 or state.stdout.strip() != "device":
        raise ToolError(
            f"no Android device ready: {(state.stderr or state.stdout).strip() or 'unknown'}"
        )
    rec = subprocess.Popen(base + ["shell", "screenrecord", DEVICE_TMP],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(settle)
        proc = subprocess.run(cmd, shell=True)
    finally:
        # ONE SIGINT finalizes the mp4; a second one lands mid-finalize and
        # kills the muxer before the moov atom is written (verified on the
        # android-35 emulator). Escalate only if the first signal didn't land.
        subprocess.run(base + ["shell", "killall", "-2", "screenrecord"],
                       capture_output=True)
        if not _wait_gone(base):
            subprocess.run(base + ["shell", "pkill", "-2", "screenrecord"],
                           capture_output=True)
            _wait_gone(base)
        try:
            rec.wait(timeout=15)
        except subprocess.TimeoutExpired:
            rec.kill()
        time.sleep(max(settle, 1.0))
    pull = subprocess.run(base + ["pull", DEVICE_TMP, out],
                          capture_output=True, text=True)
    subprocess.run(base + ["shell", "rm", "-f", DEVICE_TMP], capture_output=True)
    if pull.returncode != 0 or not os.path.isfile(out):
        raise ToolError(f"adb pull failed: {(pull.stderr or pull.stdout).strip()}")
    from .probe import probe
    info = probe(out)
    return {
        "cmd": cmd,
        "cmd_exit": proc.returncode,
        "duration_s": info["duration_s"],
        "out": out,
        "size": [info["video"]["width"], info["video"]["height"]],
    }
