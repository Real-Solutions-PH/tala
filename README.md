# Tala

**Log your gastos by just talking. Offline.**

Tala is a money log you talk to. Say "nag-jeep ako 15 tapos lunch sa Jollibee 165", snap a receipt, or drop in a bank statement PDF — a local AI agent logs it. Ask "saan napunta pera ko this month?" and it answers with a chart drawn from your own data. Everything — speech recognition, the agent, reading photos and documents — runs on your laptop. Turn Wi-Fi off and it still works.

Built for the AppBuildersPH Hackathon 2026 (theme: Local AI), 2026-10-09 → 2026-10-10.

## Why local

- **Your money data never leaves your device.** Receipts, bank statements and spending habits are exactly what people don't want on someone else's server.
- **Zero cost per capture.** A cloud vision/LLM call per receipt or voice note adds up; here it's free after download.
- **Works on bad signal.** Log on the jeep, in the mall basement, or with no load.

## What runs where

| Part | Runs | Model / tool |
|---|---|---|
| Chat agent + tool calling | Local | Qwen3-VL-8B-Instruct, Q4_K_M GGUF, via llama.cpp `llama-server` |
| Receipt / photo reading | Local | same model (vision projector `mmproj-Qwen3VL-8B-Instruct-Q8_0`) |
| Voice dictation | Local | whisper.cpp `whisper-server`, `ggml-large-v3-turbo` |
| PDF statements | Local | pypdf text extraction → agent |
| Storage | Local | SQLite |
| Charts | Local | Chart.js 4.4.1 (vendored, no CDN) |

**Requires internet:** only the one-time model download. No cloud AI API is used at runtime.

The agent never writes numbers itself: every total and chart comes from a SQL query run by a tool (`tools.py`), so it cannot invent figures.

## Run it (macOS, Apple Silicon)

```sh
brew install llama.cpp whisper-cpp ffmpeg
# uv: https://docs.astral.sh/uv/
mkdir -p ~/models && cd ~/models
curl -LO https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/Qwen3VL-8B-Instruct-Q4_K_M.gguf
curl -LO https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
curl -LO https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
cd -  # back to this repo
uv sync
./run.sh
```

Open http://127.0.0.1:8787. First run seeds ~75 days of sample spending (`uv run python seed.py` resets it). Needs ~8 GB free RAM.

Tests: `uv run python test_tools.py`.

## Disclosures

- **Models:** Qwen3-VL-8B-Instruct (Alibaba Qwen, Apache-2.0); Whisper large-v3-turbo (OpenAI, MIT) in ggml format.
- **Frameworks / libraries:** llama.cpp, whisper.cpp, FastAPI, uvicorn, httpx, pypdf, SQLite, Chart.js.
- **APIs / cloud services:** none at runtime.
- **Existing code / assets:** none; this repository was started at the hackathon. The idea (Taglish quick capture) comes from the author's earlier personal project, but no code was reused.
- **AI development tools:** Claude Code (Claude Opus).
