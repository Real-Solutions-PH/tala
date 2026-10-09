# Tala

Offline, Taglish-first expense logging. Speak, chat, or attach a receipt photo or PDF statement — a local AI agent logs it, answers questions about your spending, and draws charts in the chat. Everything runs on your laptop; it works with Wi-Fi off.

Built for the AppBuildersPH Hackathon 2026 (Local AI), 2026-10-09 → 2026-10-10.

## What runs locally

| Part | Model / tool |
|---|---|
| Chat agent, tool calls, photo reading | Qwen3-VL-8B-Instruct (Q4_K_M GGUF) via llama.cpp `llama-server` |
| Voice dictation | whisper.cpp `large-v3-turbo` |
| PDF text | pypdf |
| Storage | SQLite |

Nothing requires internet at runtime.

_Setup instructions: in progress._
