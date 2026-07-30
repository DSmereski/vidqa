import urllib.request

import pytest


def _ollama_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=3)
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _ollama_up(), reason="ollama not running")


def test_ask_enum_answer(media):
    from vidqa.ask import ask

    result = ask(
        str(media["red"]), "What is the dominant color of the video?",
        frames=2, enum=["red", "green", "blue"],
    )
    assert result["answer"] == "red"
    assert result["frames_used"] == 2
    assert result["model"] == "qwen3-vl:8b"
