from vidqa.probe import probe


def test_probe_clean(media):
    result = probe(str(media["clean"]))
    assert result["video"]["width"] == 320
    assert result["video"]["height"] == 240
    assert result["video"]["fps_avg"] == 25.0
    assert result["video"]["fps_mode"] == "cfr"
    assert 1.9 <= result["duration_s"] <= 2.1
    assert result["audio"] is None
