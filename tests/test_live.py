import pytest

from vidqa.ffutil import ToolError
from vidqa.live import parse_csv

V1_CSV = (
    "Application,ProcessID,SwapChainAddress,Runtime,SyncInterval,PresentFlags,"
    "AllowsTearing,PresentMode,Dropped,TimeInSeconds,msBetweenPresents,"
    "msBetweenDisplayChange,msInPresentAPI,msUntilRenderComplete,msUntilDisplayed\n"
    + "\n".join(
        f"game.exe,123,0x0,DXGI,1,0,0,Composed,0,{i * 0.0167:.4f},16.7,16.7,0.5,10.0,20.0"
        for i in range(20)
    )
)

V2_CSV = (
    "Application,ProcessID,SwapChainAddress,PresentRuntime,SyncInterval,PresentFlags,"
    "AllowsTearing,PresentMode,FrameType,CPUStartTime,FrameTime,CPUBusy,CPUWait,"
    "GPULatency,GPUTime,GPUBusy,GPUWait,DisplayLatency,DisplayedTime\n"
    + "\n".join(
        f"game.exe,123,0x0,DXGI,1,0,0,Composed,Application,{i * 0.0167:.4f},16.7,"
        "10.0,6.7,5.0,8.0,7.0,1.0,25.0,16.7"
        for i in range(20)
    )
)


def test_parse_v1_columns():
    result = parse_csv(V1_CSV, process="game.exe", seconds=10)
    assert result["frame_count"] == 20
    assert result["skipped_rows"] == 0
    assert 59.0 <= result["fps_avg"] <= 61.0
    assert result["frame_time_ms"]["p50"] == 16.7


def test_parse_v2_columns():
    result = parse_csv(V2_CSV)
    assert result["frame_count"] == 20
    assert result["frame_time_ms"]["p99"] == 16.7


def test_empty_capture_is_an_error():
    with pytest.raises(ToolError):
        parse_csv("")


def test_unknown_columns_is_an_error():
    with pytest.raises(ToolError, match="no frame-time column"):
        parse_csv("A,B\n1,2\n")
