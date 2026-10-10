# Kapiling

**Your health, always by your side.** (*Laging kapiling ang kalusugan mo.*)

Kapiling (ka-PI-ling, "by your side") is a personal health record you talk to. It keeps a person's profile, allergies, conditions, maintenance medicines, vaccines, ID and insurance cards, and photos and scans of old records on their own device. When a nurse or doctor asks for something, you ask Kapiling: it finds the PhilHealth card, reads the last blood sugar result, says it out loud, or fills in the clinic intake form from what is on record. It is a companion, not a doctor: it never diagnoses, never advises on medicines, and every recommendation carries a fixed disclaimer.

The mark is two rounded forms side by side, a large circle (the person) and a smaller one leaning in (the companion), with a sun-gold lens where they overlap.

> **Name note.** The product is Kapiling, but the repository and folder are still called `tala` (the earlier store assistant this was built from). Renaming the GitHub repository is the owner's call and has not been done.

## Why local

Why does this product benefit from running AI locally?

- **Health records are sensitive.** Under the Data Privacy Act (RA 10173), health information is sensitive personal information. Kapiling keeps it on the person's own device and sends it nowhere. There is no cloud AI API to leak it to.
- **Hospitals have weak signal.** Clinics and wards are often dead zones. The record has to open at the counter, not when the signal returns.
- **Emergencies.** The emergency card (allergies, blood type, conditions, contacts) opens from a QR code without unlocking the phone, with no network.
- **Cost.** No per-question cloud bill, so a lola's family can use it for free.

## What runs where, and what needs internet

Everything runs on the laptop: chat and vision, document reading, search, speech to text, text to speech, storage. **Nothing needs internet after the one-time model download** (about 1.4 GB of retrieval and voice models, plus the chat model, plus 669 MB of Docling models). `run.sh` sets `HF_HUB_OFFLINE=1`. No cloud AI API is used anywhere.

```
 Phone / laptop browser (React + Vite PWA, push-to-talk, camera)
              |  HTTPS on the LAN, pairing QR
              v
 FastAPI app (backend/kapiling)  --  SQLite + sqlite-vec + FTS5 (one file)
   |        |           |                |
   |        |           |                +-- Docling ingestion worker (layout + TableFormer) -> chunks -> embeddings
   |        |           +-- MMS-TTS (Tagalog / English voice, in process)
   |        +-- whisper.cpp server :8081   (speech to text)
   +-- llama.cpp servers: chat+vision :8080, embeddings :8082, reranker :8083
```

## Models and licences

| Model | Used for | Licence |
|---|---|---|
| Qwen3-VL-8B-Instruct (Q4_K_M GGUF, with mmproj) | chat, tool calling, reading photos | Apache-2.0 |
| Qwen3-Embedding-0.6B (Q8_0 GGUF) | document search embeddings | Apache-2.0 |
| bge-reranker-v2-m3 (Q8_0 GGUF) | reranking search results | Apache-2.0 |
| Whisper large-v3-turbo (ggml) | speech to text | MIT |
| Meta MMS-TTS `mms-tts-tgl` and `mms-tts-eng` | spoken replies in Tagalog and English | CC-BY-NC 4.0 (non-commercial) |
| Docling layout (heron) and TableFormer models | PDF layout and table reading | Apache-2.0 |
| Silero VAD (via `@ricky0123/vad-web`) | detecting when you stop speaking, in the browser | MIT |

Check each model card for the current licence terms before you redistribute anything.

## Setup (macOS, Apple Silicon)

```sh
brew install llama.cpp whisper-cpp ffmpeg      # plus uv and bun
# Chat + vision model and whisper (one time):
mkdir -p ~/models && cd ~/models
curl -LO https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/Qwen3VL-8B-Instruct-Q4_K_M.gguf
curl -LO https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
curl -LO https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
cd -   # back to this repo
./scripts/fetch_models.sh     # embeddings, reranker, tokenizer, MMS-TTS voices, Docling models
./run.sh
```

Open http://127.0.0.1:8787. `run.sh` starts the four model servers and the app, seeds the demo data on first start, and stops everything on Ctrl-C. A smaller, faster chat model works with `LLM=... MMPROJ=... ./run.sh`. Backend tests: `cd backend && uv run pytest -q`.

### On a phone

`run.sh` prints a QR code. Put the phone and laptop on the same Wi-Fi (or the laptop on the phone's hotspot; no internet is needed), scan it, and accept the one-time certificate warning (the laptop signs its own HTTPS certificate; phones only allow the microphone over HTTPS). Only devices that scanned the QR can open the app; it carries a random pairing key, new on every start.

## Demo PINs (fictional)

All data in the demo is **fictional**: invented people, invented card numbers, generated images. Do not enter real health information in a demo.

| Who | PIN |
|---|---|
| Owner (Lola Remy and Mika) | `123456` |
| Representative (Ana Dela Cruz, for Lola Remy) | `246810` |

## Cloud demo (optional, not deployed by this repository)

`Dockerfile` and `deploy/compose.yaml` package the same app for a GPU VM: three llama.cpp servers (chat and vision, embeddings, reranker), a whisper.cpp server, the app image, and Caddy for TLS on your domain. It still uses self-hosted open models only. `KAPILING_DEMO=1` shows a "Fictional data" banner flag (`GET /api/demo`), enables `POST /api/demo/reset` (wipes and reseeds only the demo data folder; a 404 otherwise) and turns off pairing. uvicorn runs with `--proxy-headers` behind Caddy, which secure cookies and the WebAuthn origin need.

```sh
export KAPILING_DOMAIN=demo.example.com MODELS=/path/to/models   # filled by scripts/fetch_models.sh
docker compose -f deploy/compose.yaml up -d --build
```

Settings are environment variables (`LLM_URL`, `EMBED_URL`, `RERANK_URL`, `WHISPER_URL`, `KAPILING_DATA`, `KAPILING_KEY`, `KAPILING_DEMO`, `DOCLING_ARTIFACTS`), so the same build runs locally and in the cloud.

## Disclosures

- **Models:** see the table above. All run locally.
- **Frameworks and libraries:** FastAPI, llama.cpp, whisper.cpp, Docling, LangChain-core, sqlite-vec, React, Vite (also uvicorn, httpx, Transformers, PyTorch, SQLite).
- **Cloud AI APIs:** none. No request leaves the machine at runtime.
- **Internet:** only for the one-time model download.
- **Existing code reused:** parts of the earlier Tala store assistant (the local llama.cpp and whisper.cpp serving, `run.sh`, the streaming chat plumbing and the voice pipeline) were reused and reworked for Kapiling.
- **AI development tools:** Claude Code.
- **Not medical advice.** Kapiling stores and retrieves records. It does not diagnose or advise on medicines.
