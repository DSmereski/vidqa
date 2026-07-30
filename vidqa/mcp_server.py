"""Thin MCP wrapper so non-Claude-Code clients (Hive bots, other harnesses)
get the same vidqa tools over stdio. All heavy lifting stays in the modules."""
from mcp.server import MCPServer

server = MCPServer("vidqa")


@server.tool()
def probe(path: str) -> dict:
    """Container/stream facts for a video: codecs, fps, duration, CFR/VFR."""
    from .probe import probe as impl
    return impl(path)


@server.tool()
def timing(path: str) -> dict:
    """Frame-timing QA: stutter events, duplicate frames, freezes, percentiles."""
    from .timing import timing as impl
    return impl(path)


@server.tool()
def diff(candidate: str, golden: str, at: float | None = None) -> dict:
    """Compare a frame (or video frame at a timestamp) against a golden image."""
    from .diff import diff as impl
    return impl(candidate, golden, at=at)


@server.tool()
def scenes(path: str) -> dict:
    """Scene-cut timestamps."""
    from .scenes import scenes as impl
    return impl(path)


@server.tool()
def report(path: str, golden: str | None = None, at: float | None = None) -> dict:
    """One-call composite QA verdict over a video."""
    from .report import report as impl
    return impl(path, golden=golden, at=at)


@server.tool()
def audio(path: str) -> dict:
    """Audio glitch checks: silences, clipping, volume stats."""
    from .audio import audio as impl
    return impl(path)


@server.tool()
def ocr(path: str, at: float | None = None) -> dict:
    """Read text off a frame (RapidOCR, local CPU)."""
    from .ocr import ocr as impl
    return impl(path, at=at)


@server.tool()
def find(path: str, template: str, at: float | None = None) -> dict:
    """Locate a known UI element in a frame via template matching."""
    from .find import find as impl
    return impl(path, template, at=at)


@server.tool()
def ask(path: str, question: str, enum: list[str] | None = None,
        model: str = "qwen3-vl:8b", frames: int = 6) -> dict:
    """Ask a local VLM a question about a video (fully on-device)."""
    from .ask import ask as impl
    return impl(path, question, model=model, frames=frames, enum=enum)


def main():
    server.run()


if __name__ == "__main__":
    main()
