# Getting started

## Requirements

- macOS or Linux. `run.sh` finds the LAN address with `ipconfig getifaddr`, so phone pairing as written is macOS-tested; on Linux, set `KAPILING_PHONE_URL` yourself or use the laptop browser.
- About 24 GB RAM (the size this was tested on). A smaller chat model is possible: `LLM=... MMPROJ=... ./run.sh`.
- Tools: `llama.cpp` (`llama-server`), `whisper-cpp` (`whisper-server`), `ffmpeg`, `uv`, `bun`, `openssl`, `curl`, and the Hugging Face CLI `hf`.
- Internet only for the one-time model download.

## 1. Download the models

```sh
brew install llama.cpp whisper-cpp ffmpeg
mkdir -p ~/models && cd ~/models
curl -LO https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/Qwen3VL-8B-Instruct-Q4_K_M.gguf
curl -LO https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
curl -LO https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
cd -
./scripts/fetch_models.sh
```

`fetch_models.sh` downloads the embedding model, the reranker, the tokenizer files, the Tagalog and English MMS-TTS voices and the Docling models into `$MODELS` (default `~/models`). It skips what is already there, so it is safe to re-run.

## 2. Run

```sh
./run.sh
```

`run.sh` refuses to start if ports 8080, 8081, 8082, 8083, 8787 or 8443 are taken, builds the frontend if `backend/static/index.html` is missing, starts the four model servers, seeds the fictional demo data, starts the app, waits until `/api/health` reports every server up, warms the chat model, and prints the URLs and a QR code. Ctrl-C stops everything. Open http://127.0.0.1:8787.

Log in with a demo PIN (fictional data): owner `123456`, representative `246810`.

## 3. Pair a phone

1. Put the phone and laptop on the same Wi-Fi, or the laptop on the phone's hotspot. No internet is needed.
2. Scan the QR code printed by `run.sh`.
3. Accept the one-time certificate warning (the laptop signs its own certificate; browsers allow the microphone only over HTTPS).

Only a device that opened the QR link can use the app: the link carries a random key, new on every start, which becomes a cookie. Biometric unlock does not work on a bare LAN IP; use the PIN.

## Seeding

`run.sh` runs `uv run python -m seed.persona` from `backend/`, which seeds a fresh database once (Lola Remy, Mika, cards, medicines, labs). To index the seeded documents for search: `cd backend && KAPILING_DATA=<dir> uv run python -m seed.ingest_seed`. Card and document images are generated and marked SAMPLE.

## Tests

```sh
cd backend && uv run pytest -q
cd frontend && bun run test --run
```

The frontend `test` script first runs the colour-contrast check (`scripts/contrast.ts`), then vitest. Also available: `bun run typecheck`, `bun run lint`.

## Troubleshooting

| Problem | What to do |
|---|---|
| `Port N is already in use` | `run.sh` never kills other processes. Stop whatever holds the port (it prints the listener), then run again. |
| `Timed out waiting for: ...` | A model server did not become healthy in time (default 300 s). Raise it with `KAPILING_START_TIMEOUT=600 ./run.sh`, then read the matching log. |
| `The X server died` | `run.sh` prints the last 20 lines of that log. |
| Anything else | Logs are in `logs/`: `llama.log`, `embed.log`, `rerank.log`, `whisper.log`, `app.log`, `phone.log`. |
| Phone shows "Scan the pairing QR code" | Open the link from this run's QR code; the key changes on every start. |
| Microphone blocked on the phone | The page must be opened over the HTTPS address. |
