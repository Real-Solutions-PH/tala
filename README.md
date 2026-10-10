# Kapiling

**Your health, always by your side.** (*Laging kapiling ang kalusugan mo.*)

## What it is

Kapiling (ka-PI-ling, "by your side") is a personal health record that Filipino seniors talk to, in Tagalog or English, with every AI model running on their own device. It keeps profile, allergies, conditions, maintenance medicines, vaccines, ID and insurance cards, and photos and scans of old records, and it hands them over when a nurse or doctor asks. It is a companion, not a doctor: it never diagnoses, never advises on medicines, and every recommendation carries a fixed disclaimer.

Screenshots (fictional demo data, in `docs/screenshots/`):
[lock](docs/screenshots/lock.png) ·
[emergency card](docs/screenshots/emergency-card.png) ·
[emergency QR](docs/screenshots/emergency-qr.png) ·
[ID wallet](docs/screenshots/cards.png) ·
[card viewer](docs/screenshots/card-viewer.png) ·
[medicines](docs/screenshots/medicines.png) ·
[records](docs/screenshots/records.png) ·
[lab trend](docs/screenshots/lab-trend.png) ·
[document with highlighted citation](docs/screenshots/document-citation.png) ·
[extraction review](docs/screenshots/extraction-review.png) ·
[access log](docs/screenshots/access-log.png) ·
[settings](docs/screenshots/settings.png) ·
[profile](docs/screenshots/profile.png) ·
[design components](docs/screenshots/design-components.png)

> **Name note.** The product is Kapiling, but the repository and folder are still called `tala` (the earlier store assistant this was built from). Renaming the GitHub repository is the owner's call and has not been done.

> **Current state.** The chat screen, push-to-talk button and hands-free Usap mode are not merged into the web app yet: the Chat tab is a placeholder. The server side of chat and voice is merged and tested. See the status column below.

## Why local AI

- **Health records are sensitive.** Under the Data Privacy Act (RA 10173), health information is sensitive personal information. Kapiling keeps it on the person's own device and sends it nowhere. There is no cloud AI API to leak it to.
- **Hospitals have weak signal.** Clinics and wards are often dead zones. The record has to open at the counter, not when the signal returns.
- **Emergencies.** The emergency card (allergies, blood type, conditions, contacts) opens from a QR code without unlocking the phone, with no network.
- **Cost.** No per-question cloud bill, so a lola's family can use it for free.

Everything runs on the laptop: chat and vision, document reading, search, speech to text, text to speech, storage. **Nothing needs internet after the one-time model download** (about 1.4 GB of retrieval and voice models, plus the chat model, plus 669 MB of Docling models). `run.sh` sets `HF_HUB_OFFLINE=1`. No cloud AI API is used anywhere. See [docs/architecture.md](docs/architecture.md).

## Features

Status key: **Built** = server and screen merged. **Server only** = the backend is merged and tested, the screen is not. **Not built** = specified, no code.

### Talk and ask

| # | Feature | Status |
|---|---|---|
| 1 | Ask by text; answers come from the record through tools (profile, medicines, labs, cards, vaccines, document search) | Server only |
| 2 | Streaming replies with live step lines, Stop button, saved conversations (AG-UI over SSE) | Server only (stream client merged) |
| 3 | Rich answer blocks: card, profile fields, medicine list, lab table, chart, document, form answers | Server only |
| 4 | Voice questions: audio sent to local whisper.cpp | Server only |
| 5 | Spoken replies in Tagalog and English (MMS-TTS) | Server only |
| 6 | Hands-free Usap mode and consultation listen-in | Not built |

### Records

| # | Feature | Status |
|---|---|---|
| 7 | Health summary: conditions, allergies, latest vitals and labs | Built |
| 8 | Timeline of visits, labs, vaccines and documents | Built |
| 9 | Lab trend charts with reference band and a table alternative | Built |
| 10 | Add a photo or PDF of an old record; it is read by the local vision model and Docling | Built |
| 11 | Review and confirm extracted lab values (they stay "proposed" until confirmed) | Built |
| 12 | Search scanned records with citations (hybrid retrieval, rerank, score floor) | Server and document viewer built; score floor is provisional |

### Wallet and medicines

| # | Feature | Status |
|---|---|---|
| 13 | ID and insurance card wallet (PhilHealth, Senior Citizen, HMO, PWD, vaccination) | Built |
| 14 | Full-screen card viewer for handing to the nurse | Built |
| 15 | Add a card from a photo (front and back) | Built |
| 16 | Today's medicine checklist, tap to mark taken | Built |
| 17 | Refill warnings from remaining supply | Built |

### Safety and privacy

| # | Feature | Status |
|---|---|---|
| 18 | 6-digit PIN lock, 5-minute idle lock, lockout after repeated failures | Built |
| 19 | Emergency card and QR code without unlocking | Built |
| 20 | Representatives with their own PIN, and an owner-readable access log | Built |
| 21 | Biometric unlock (WebAuthn), where the browser allows it | Built |
| 22 | Fixed disclaimer and refusal text, deterministic pre-check, never written by the model | Server and component built; chat display pending |

### Personal

| # | Feature | Status |
|---|---|---|
| 23 | Profile, family history, emergency contacts | Built |
| 24 | Fill a clinic form from a photo using only the record; blanks marked "not on record" | Module and tests merged; not yet wired into chat |
| 25 | Meal and activity ideas that respect conditions and allergies, with the disclaimer | Server only |

### Platform

| # | Feature | Status |
|---|---|---|
| 26 | Tagalog and English UI, three text sizes, light and dark | Built |
| 27 | Phone pairing over LAN HTTPS with a QR code; web app manifest | Built |
| 28 | Cloud demo packaging (Docker, Caddy) with fictional data and a reset | Packaged, not deployed |

## Quick start

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

Open http://127.0.0.1:8787. `run.sh` starts the four model servers and the app, seeds the demo data on first start, and stops everything on Ctrl-C. A smaller, faster chat model works with `LLM=... MMPROJ=... ./run.sh`. Backend tests: `cd backend && uv run pytest -q`. Frontend tests: `cd frontend && bun run test --run`.

**On a phone.** `run.sh` prints a QR code. Put the phone and laptop on the same Wi-Fi (or the laptop on the phone's hotspot; no internet is needed), scan it, and accept the one-time certificate warning (the laptop signs its own HTTPS certificate; phones only allow the microphone over HTTPS). Only devices that scanned the QR can open the app; it carries a random pairing key, new on every start.

Full steps and troubleshooting: [docs/getting-started.md](docs/getting-started.md).

## Demo PINs (fictional)

All data in the demo is **fictional**: invented people, invented card numbers, generated images. Do not enter real health information in a demo.

| Who | PIN |
|---|---|
| Owner (Lola Remy and Mika) | `123456` |
| Representative (Ana Dela Cruz, for Lola Remy) | `246810` |

## Docs index

| Doc | What is in it |
|---|---|
| [docs/README.md](docs/README.md) | Index of every document |
| [docs/getting-started.md](docs/getting-started.md) | Install, run, pair a phone, test, troubleshoot |
| [docs/architecture.md](docs/architecture.md) | Diagram, components, chat and voice flows, ingestion, retrieval, data model |
| [docs/api.md](docs/api.md) | Every REST route, AG-UI events, block types |
| [docs/security-and-privacy.md](docs/security-and-privacy.md) | Lock, sessions, representatives, pairing, uploads, RA 10173 |
| [docs/safety.md](docs/safety.md) | What Kapiling refuses and how that is enforced |
| [docs/demo-guide.md](docs/demo-guide.md) | The 5-minute live demo and the 1-minute video script |
| [docs/market-and-business.md](docs/market-and-business.md) | Market size estimates, competitors, SWOT, business model |
| [docs/submission.md](docs/submission.md) | Hackathon submission pack |
| [DESIGN.md](DESIGN.md) | Brand and design system |
| [backend/eval/README.md](backend/eval/README.md) | Retrieval and safety evaluation |

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

## Disclosures

- **Models:** see the table above. All run locally.
- **Frameworks and libraries:** FastAPI, llama.cpp, whisper.cpp, Docling, LangChain-core, sqlite-vec, React, Vite (also uvicorn, httpx, Transformers, PyTorch, SQLite).
- **Cloud AI APIs:** none. No request leaves the machine at runtime.
- **Internet:** only for the one-time model download.
- **Existing code reused:** parts of the earlier Tala store assistant (the local llama.cpp and whisper.cpp serving, `run.sh`, the streaming chat plumbing and the voice pipeline) were reused and reworked for Kapiling.
- **AI development tools:** Claude Code.
- **Not medical advice.** Kapiling stores and retrieves records. It does not diagnose or advise on medicines.
- **Cloud demo:** `Dockerfile` and `deploy/compose.yaml` package the app for a GPU VM. They are not deployed by this repository. See [deploy/README.md](deploy/README.md).

## Team

Real Solutions PH, AppBuildersPH Hackathon 2026:

- Kairus Noah Tecson ([@SchadenKai](https://github.com/SchadenKai))
- Ervin Piol ([@ervinpiol](https://github.com/ervinpiol))
