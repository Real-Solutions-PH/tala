# Kapiling — AppBuildersPH Hackathon 2026 submission pack

Copy these fields into the Cerebral Valley form (cerebralvalley.ai/e/appbuildersph-hackathon-2026). Deadline 10:00 AM, 10 Oct 2026. One submission only.

## Project name
Kapiling

## Short description
Kapiling ("by your side") is a personal health record that Filipino seniors talk to, in Tagalog or English, with every AI model running on their own device. It keeps their ID and insurance cards, maintenance medicines, lab results and old hospital records; reads photographed records with a local vision model; answers a nurse's or doctor's questions by voice; shows an emergency card without unlocking; and never diagnoses or gives medicine advice.

## Team members
[fill in: official team name and member names exactly as listed on appbuildersph.com/hackathon]

## Public GitHub repository
https://github.com/Real-Solutions-PH/tala  (must be public before 10:00)

## Why does this product benefit from running AI locally?
Health records are the most sensitive data a person has (sensitive personal information under the Data Privacy Act, RA 10173), so Kapiling never uploads them: every model runs on the family's own laptop and phones connect over home Wi-Fi. Hospitals and clinics often have weak signal, so search, voice and reading a photographed lab result all work in airplane mode. In an emergency the card and its QR code need no network and no login. And with no per-request cloud AI fees, seniors can use it for free.

## What runs locally
- Chat and reading photos: Qwen3-VL 8B (llama.cpp)
- Search: Qwen3-Embedding 0.6B embeddings + bge-reranker-v2-m3 reranker (llama.cpp), sqlite-vec + SQLite FTS5
- Speech to text: whisper large-v3-turbo (whisper.cpp)
- Text to speech: Meta MMS-TTS Tagalog and English
- Document parsing: Docling (layout and TableFormer models)
- Voice activity detection: Silero VAD in the browser
- All data: one SQLite file and photos on the laptop

## What requires internet
Nothing after the one-time model download. No cloud AI API is used.

## Models used
Qwen3-VL-8B-Instruct (Q4_K_M), Qwen3-Embedding-0.6B (Q8_0), bge-reranker-v2-m3 (Q8_0), whisper large-v3-turbo, facebook/mms-tts-tgl, facebook/mms-tts-eng, Docling layout and TableFormer, Silero VAD v5.

## Technologies and frameworks
FastAPI (Python), llama.cpp, whisper.cpp, Docling, LangChain-core, sqlite-vec, React 19, Vite, TypeScript, TanStack Query, Recharts.

## APIs and cloud services
None for AI. GitHub for source hosting.

## Existing code and assets
Built during the hackathon. It reuses parts of our own earlier hackathon prototype in the same repository (Tala, an offline store assistant built on Build Day): the local model server setup, phone pairing over LAN HTTPS, and the Tagalog TTS cleaner. All demo patient data and card images are fictional and marked SAMPLE.

## AI development tools
Claude Code (Anthropic).

## Demo PINs (fictional demo data)
Owner 123456 · representative 246810

---

## X / LinkedIn post (required: tag Devin / Cognition and #AppBuildersPH)

Kapiling — a health record Lola can talk to. 🇵🇭

Show your PhilHealth card by voice, photograph a lab result and let a local AI read it, open an emergency card without unlocking, answer the doctor in Tagalog. Every AI model runs on the family's own laptop: no uploads, works offline.

Built for the AppBuildersPH Hackathon 2026 (Local AI). @Cognition @DevinAI #AppBuildersPH

[attach the ~1-minute demo video]

## 1-minute demo video script (phone in airplane mode)

1. (0:00) Lock screen: "Kapiling keeps Lola's health record on her own device." Tap Emergency: blood type, allergies, QR, no PIN.
2. (0:12) Unlock with PIN. Cards tab: PhilHealth full-screen for the nurse.
3. (0:20) Chat: "Ano ang maintenance ko?" → medicine list streams in, live steps visible.
4. (0:32) "Puwede ko bang itigil ang Metformin?" → fixed refusal card.
5. (0:40) Records: FBS trend with the normal range; photo of a lab result read by the local model.
6. (0:52) "Everything runs locally. No cloud AI." Show airplane mode.
