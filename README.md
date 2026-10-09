# Tala

**Free, offline store assistant for sari-sari stores and small shops. Just say what you sold.**

Most of the Philippines' small stores still keep sales, stock and *utang* in a notebook, one that tears, gets wet in a typhoon, and never tells the owner what to restock. Bookkeeping apps exist, but typing every sale into a form is slower than the notebook, so owners go back to pen and paper.

Tala replaces the typing with talking. The owner says *"2 Coke, 1 canton, tapos 3 Kopiko"*, snaps a photo of the handwritten *listahan*, or a supplier receipt, and a local AI records the sales and updates the stock. Ask *"Ano ang best seller ko this week?"* or *"Kumusta ang tindahan?"* and it answers with real charts from the store's own records and one practical tip, out loud if you want.

## Features

- **Record sales by voice, chat or photo**: Taglish, any order ("2 Coke, 1 canton"), handwritten sales lists.
- **Inventory that updates itself**: restocks by voice or supplier receipt ("dumating ang 2 box ng Coke, 24 each"), low-stock alerts the moment you sell.
- **Insights in charts, not paragraphs**: sales, profit (*kita*) and pieces by day, week, product or category; best sellers; items not selling.
- **Talk mode**: hands-free turns (listen, think, speak, listen) with a camera button to show Tala a shelf or receipt.
- **A phone app with nothing to install**: the laptop runs the AI; any iPhone or Android opens the app by scanning a QR.

## On your phone (iPhone or Android, nothing to install)

The laptop runs the AI; the phone is the app. `./run.sh` prints a QR code (also under **Open on your phone** on the laptop page).

1. Put the phone and laptop on the same Wi-Fi, or connect the laptop to the phone's hotspot (mobile data can stay off; no internet is needed).
2. Scan the QR with the camera and accept the one-time certificate warning (the laptop signs its own HTTPS certificate; phones only allow the microphone over HTTPS).
3. Optional: Share → **Add to Home Screen** for a full-screen app.

Only devices that scanned the QR (it carries a random pairing key, new on every start) can open Tala; anyone else on the network gets a 403.

## Why local

- **Free to run, so it can be free to use.** No cloud AI bill per sale recorded, the only way a tool for ₱20-margin stores can stay free.
- **Works with no signal or load.** Stores run in places and weeks (typhoons) without data.
- **The store's numbers stay in the store.** Sales and margins never leave the owner's own devices.

## What runs where

| Part | Runs | Model / tool |
|---|---|---|
| Chat agent + tool calling | Local | Qwen3-VL-8B-Instruct, Q4_K_M GGUF, via llama.cpp `llama-server` |
| Receipt / photo reading | Local | same model (vision projector `mmproj-Qwen3VL-8B-Instruct-Q8_0`) |
| Voice dictation + Talk mode | Local | whisper.cpp `whisper-server`, `ggml-large-v3-turbo` |
| Spoken replies (Tagalog voice) | Local | Meta MMS-TTS `facebook/mms-tts-tgl` (VITS) on the laptop CPU, sentence by sentence; falls back to the phone's own on-device voice |
| PDF supplier statements | Local | pypdf text extraction → agent |
| Storage | Local | SQLite |
| Charts, fonts | Local | Chart.js 4.4.1, Lexend + Source Sans 3 (vendored, no CDN) |

**Requires internet:** only the one-time model download. No cloud AI API is used at runtime.

The agent never writes numbers itself: every total and chart comes from a SQL query run by a tool (`store.py`), so it cannot invent figures.

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

Open http://127.0.0.1:8787 in Chrome (allow the microphone for voice). First run seeds a sample sari-sari store with 8 weeks of sales (`uv run python seed.py` resets it). Needs ~8 GB free RAM.

Tests: `uv run python test_tools.py`.

## Disclosures

- **Models:** Qwen3-VL-8B-Instruct (Alibaba Qwen, Apache-2.0); Whisper large-v3-turbo (OpenAI, MIT) in ggml format; MMS-TTS Tagalog `facebook/mms-tts-tgl` (Meta, CC-BY-NC 4.0, downloaded from Hugging Face on first run).
- **Frameworks / libraries:** llama.cpp, whisper.cpp, FastAPI, uvicorn, httpx, pypdf, SQLite, PyTorch, Hugging Face Transformers, num2words, Chart.js, Lexend and Source Sans 3 fonts (OFL), Lucide icon shapes (ISC), macOS system voices via the Web Speech API.
- **APIs / cloud services:** none at runtime.
- **Existing code / assets:** none; this repository was started at the hackathon. No code was reused from earlier projects.
- **AI development tools:** Claude Code (Claude Opus).
