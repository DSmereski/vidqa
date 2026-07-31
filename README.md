# vidqa

Local, deterministic video QA — for humans, CI gates, and AI agents.

Every command prints **one compact JSON object** (sorted keys, ≤4KB) and
exits **0** (pass) / **1** (gate failed) / **2** (error — a crash never
masquerades as a gate failure). Deterministic checks are byte-identical
run-to-run, so you can diff them and gate on them. Nothing is uploaded
anywhere: analysis is ffmpeg + OpenCV, and the optional semantic layer
talks to a local Ollama model.

Built for game/build QA — "is this capture smooth?", "did rendering
break vs the golden frame?", "what does this clip actually show?" — at
zero API cost, but nothing about it is game-specific.

## Requirements

- Python 3.11+
- [ffmpeg/ffprobe](https://ffmpeg.org/) on `PATH` (installed separately;
  not bundled)
- Optional, for `ask`: [Ollama](https://ollama.com/) with a vision model
  (default `qwen3-vl:8b`)
- Optional, for `live` (Windows only): Intel PresentMon — a copy is
  bundled in `tools/`

## Install

```sh
git clone https://github.com/DSmereski/vidqa
cd vidqa
python -m venv .venv
.venv/Scripts/pip install -e .[dev]   # Windows; use .venv/bin/pip elsewhere
```

## Commands

| Command | What it answers |
|---|---|
| `vidqa report <video> [--golden ref --at t]` | One-call verdict: probe + timing + scenes (+ audio, + golden diff). Start here. |
| `vidqa probe <video>` | Streams, resolution, duration, CFR/VFR. |
| `vidqa timing <video>` | Stutter, duplicate frames, freezes; frame-time p50/p95/p99. |
| `vidqa diff <cand> --golden ref [--at t] [--mask-out m.png]` | Golden-frame gate: SSIM floor + 8×8-grid worst-cell error + pHash scene check. |
| `vidqa scenes <video>` | Scene-cut timestamps. |
| `vidqa audio <video>` | Silences, clipping, volume levels. |
| `vidqa ocr <video\|image> [--at t]` | Read on-screen text (RapidOCR, CPU, offline after first model download). |
| `vidqa find <video\|image> --template t.png [--at t]` | Locate a known UI element; exit 1 if absent. |
| `vidqa ask <video> "question" [--enum a,b,c] [--expect a]` | Local-VLM Q&A; `--expect` turns it into a gate. |
| `vidqa live <process.exe> [--seconds 10]` | Real frametimes of a *running* app via PresentMon ETW (Windows). |

Example:

```sh
$ vidqa timing capture.mp4
{"dup_ratio":0.0,"frame_count":3600,"frame_time_ms":{"p50":16.6667,"p95":16.6667,"p99":16.6833},"freeze_count":0,...}

$ vidqa ask capture.mp4 "What color is the health bar?" --enum red,yellow,green --expect green
{"answer":"green","confidence":"high","evidence":"...","frames_used":6,"model":"qwen3-vl:8b"}
```

## Design contract

- **One JSON object on stdout.** Sorted keys, 4-decimal floats, no
  timestamps or hostnames — reruns of deterministic commands are
  byte-identical.
- **Exit codes mean one thing each.** `1` always means "the check
  genuinely failed"; internal errors are always `2`.
- **Gate on determinism.** VLM answers are schema-constrained (Ollama
  structured outputs at temperature 0). Enum answers are argmax-stable;
  free-prose `evidence` is best-effort context, never something to
  compare byte-wise. Automated gates should use deterministic fields or
  `--enum`/`--expect` only.
- **Cheap first.** For agents: deterministic metrics → OCR/template →
  local VLM. Most questions never need a model at all.

## MCP server

`vidqa-mcp` exposes every command as an MCP tool over stdio, for clients
that speak Model Context Protocol:

```json
{"mcpServers": {"vidqa": {"command": "/path/to/.venv/Scripts/vidqa-mcp"}}}
```

## Live frametimes (Windows)

`vidqa live` wraps [Intel PresentMon](https://github.com/GameTechDev/PresentMon)
(bundled, MIT — see `tools/PresentMon-LICENSE.txt`) to measure the real
present-to-present frametimes of a running process via ETW. ETW capture
needs elevation once: run from an admin terminal, or add your user to
the "Performance Log Users" group and sign back in.

## Testing

```sh
.venv/Scripts/python -m pytest -q
```

42 tests; fixtures are synthesized on the fly with ffmpeg (injected
freezes, dropped frames, seeded corruption, silence, clipping, drawn
text), so no test media is checked in. `eval/run_eval.py --runs 3`
exercises the VLM lane end-to-end against a local Ollama model.

## License

MIT (see `LICENSE`). The repository bundles the Intel PresentMon binary
under its own MIT license (`tools/PresentMon-LICENSE.txt`). ffmpeg is a
separate install and is not distributed here.
