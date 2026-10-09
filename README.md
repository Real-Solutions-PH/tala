# Tala

**Just say what happened. Tala logs it. Offline.**

Tracking apps die because logging is a chore. Tala removes the chore: say "Hey Tala, lunch sa Jollibee 165, nag-gym ako, remind me to pay Meralco on Friday" and a local AI agent logs the expense, checks off the habit and adds the task — in one breath. Snap a receipt or drop in a bank statement PDF and it logs those too. Ask "saan napunta pera ko this month?" and it answers with a chart drawn from your own data, and can read the answer back to you.

Speech recognition, the wake word, the agent, reading photos and documents, and the spoken replies all run on your laptop. Turn Wi-Fi off and it still works.

## Features

- **Money** — log by voice/chat/receipt photo/statement PDF; budgets; spending charts in the chat.
- **Tasks** — "remind me to…", due dates in plain words ("on Friday"), "done na yung…".
- **Habits** — "nag-workout ako", streaks and 7-day history.
- **Hands-free** — toggle *Hey Tala*: say "Hey Tala" (or "Tala, lunch 150" in one go).
- **Voice replies** — answers read aloud with the OS's on-device voices.

Built for the AppBuildersPH Hackathon 2026 (theme: Local AI), 2026-10-09 → 2026-10-10.

## On your phone (iPhone or Android, nothing to install)

The laptop runs the AI; the phone is the app. `./run.sh` prints a QR code (also under **Phone** in the laptop UI).

1. Put the phone and laptop on the same Wi-Fi, or connect the laptop to the phone's hotspot (mobile data can stay off; no internet is needed).
2. Scan the QR with the camera, accept the one-time certificate warning (the laptop signs its own HTTPS certificate; phones only allow the microphone over HTTPS).
3. Optional: Share → **Add to Home Screen** for a full-screen app.

Only devices that scanned the QR (it carries a random pairing key, new on every start) can open Tala; anyone else on the network gets a 403.

## Why local

- **Your money data never leaves your device.** Receipts, bank statements and spending habits are exactly what people don't want on someone else's server.
- **Zero cost per capture.** A cloud vision/LLM call per receipt or voice note adds up; here it's free after download.
- **Works on bad signal.** Log on the jeep, in the mall basement, or with no load.

## What runs where

| Part | Runs | Model / tool |
|---|---|---|
| Chat agent + tool calling | Local | Qwen3-VL-8B-Instruct, Q4_K_M GGUF, via llama.cpp `llama-server` |
| Receipt / photo reading | Local | same model (vision projector `mmproj-Qwen3VL-8B-Instruct-Q8_0`) |
| Voice dictation + "Hey Tala" wake word | Local | whisper.cpp `whisper-server`, `ggml-large-v3-turbo` (wake word = short utterances transcribed locally and matched) |
| Spoken replies | Local | Web Speech API restricted to `localService` voices (macOS system voices) |
| PDF statements | Local | pypdf text extraction → agent |
| Storage | Local | SQLite |
| Charts, fonts | Local | Chart.js 4.4.1, Lexend + Source Sans 3 (vendored, no CDN) |

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

Open http://127.0.0.1:8787 in Chrome (allow the microphone for voice). First run seeds ~75 days of sample spending (`uv run python seed.py` resets it). Needs ~8 GB free RAM.

Tests: `uv run python test_tools.py`.

## Disclosures

- **Models:** Qwen3-VL-8B-Instruct (Alibaba Qwen, Apache-2.0); Whisper large-v3-turbo (OpenAI, MIT) in ggml format.
- **Frameworks / libraries:** llama.cpp, whisper.cpp, FastAPI, uvicorn, httpx, pypdf, SQLite, Chart.js, Lexend and Source Sans 3 fonts (OFL), Lucide icon shapes (ISC), macOS system voices via the Web Speech API.
- **APIs / cloud services:** none at runtime.
- **Existing code / assets:** none; this repository was started at the hackathon. The idea (Taglish quick capture) comes from the author's earlier personal project, but no code was reused.
- **AI development tools:** Claude Code (Claude Opus).
