#!/usr/bin/env bash
# One-time download of the models Kapiling needs. Safe to re-run: existing files are skipped.
# After this, nothing needs the network (run.sh sets HF_HUB_OFFLINE=1).
set -euo pipefail

MODELS="${MODELS:-$HOME/models}"
HF="${HF:-$(command -v hf || echo "$HOME/.pyenv/shims/hf")}"
mkdir -p "$MODELS"

# fetch_gguf REPO FILE: into $MODELS, skipped when already there.
fetch_gguf() {
  if [ -f "$MODELS/$2" ]; then echo "have $2"; return; fi
  "$HF" download "$1" "$2" --local-dir "$MODELS"
}

fetch_gguf Qwen/Qwen3-Embedding-0.6B-GGUF Qwen3-Embedding-0.6B-Q8_0.gguf
fetch_gguf gpustack/bge-reranker-v2-m3-GGUF bge-reranker-v2-m3-Q8_0.gguf

# Tokenizer files only (for Docling's chunker); hf skips what the cache already holds.
"$HF" download Qwen/Qwen3-Embedding-0.6B tokenizer.json tokenizer_config.json vocab.json \
  merges.txt special_tokens_map.json config.json
# Text-to-speech voices (Tagalog and English).
"$HF" download facebook/mms-tts-tgl
"$HF" download facebook/mms-tts-eng
echo "Models ready."
