#!/usr/bin/env bash
# Starts the two local model servers and the app. Ctrl-C stops all three.
set -euo pipefail
cd "$(dirname "$0")"

MODELS="${MODELS:-$HOME/models}"
LLM="${LLM:-$MODELS/Qwen3VL-8B-Instruct-Q4_K_M.gguf}"
MMPROJ="${MMPROJ:-$MODELS/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf}"
WHISPER="${WHISPER:-$MODELS/ggml-large-v3-turbo.bin}"

trap 'kill 0' EXIT

llama-server -m "$LLM" --mmproj "$MMPROJ" --jinja -c 16384 -ngl 99 \
  --host 127.0.0.1 --port 8080 > llama.log 2>&1 &
# The prompt biases whisper toward Taglish spelling ("nag-jeep" instead of "Gibaco").
whisper-server -m "$WHISPER" -l auto --convert \
  --prompt "Taglish expenses: nag-jeep ako, nag-Grab, gastos, lunch sa Jollibee, GCash, Meralco, piso, kahapon, kanina." \
  --host 127.0.0.1 --port 8081 > whisper.log 2>&1 &

[ -f tala.db ] || uv run python seed.py
echo "Tala → http://127.0.0.1:8000  (model logs: llama.log, whisper.log)"
uv run uvicorn app:app --host 127.0.0.1 --port 8000
