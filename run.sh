#!/usr/bin/env bash
# Faster but less reliable: LLM=~/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf MMPROJ=~/models/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf ./run.sh
# First time: ./scripts/fetch_models.sh (downloads the embedding and reranker models).
# Starts the local model servers and the app. Ctrl-C stops everything.
# Seeding: run.sh runs `uv run python -m seed.persona` from backend/, which seeds a fresh database once.
# KAPILING_START_TIMEOUT (default 300) is how many seconds to wait for the servers.
set -euo pipefail
cd "$(dirname "$0")"

MODELS="${MODELS:-$HOME/models}"
LLM="${LLM:-$MODELS/Qwen3VL-8B-Instruct-Q4_K_M.gguf}"
MMPROJ="${MMPROJ:-$MODELS/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf}"
WHISPER="${WHISPER:-$MODELS/ggml-large-v3-turbo.bin}"
EMBED="${EMBED:-$MODELS/Qwen3-Embedding-0.6B-Q8_0.gguf}"
RERANK="${RERANK:-$MODELS/bge-reranker-v2-m3-Q8_0.gguf}"

# Everything is local after scripts/fetch_models.sh.
export HF_HUB_OFFLINE=1

# Never kill another process: refuse to start when a port is taken.
for port in 8080 8081 8082 8083 8787 8443; do
  if lsof -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then
    echo "Port $port is already in use, so Kapiling cannot start:" >&2
    lsof -iTCP:"$port" -sTCP:LISTEN >&2
    exit 1
  fi
done

trap 'kill 0' EXIT
mkdir -p logs

[ -f backend/static/index.html ] || (cd frontend && bun install && bun run build)

llama-server -m "$LLM" --mmproj "$MMPROJ" --jinja -c 16384 -ngl 99 \
  --host 127.0.0.1 --port 8080 > logs/llama.log 2>&1 &
PIDS="llama:$!"
llama-server -m "$EMBED" --embedding --pooling last -c 8192 -ub 8192 -ngl 99 \
  --host 127.0.0.1 --port 8082 > logs/embed.log 2>&1 &
PIDS="$PIDS embed:$!"
llama-server -m "$RERANK" --reranking -c 8192 -ub 8192 -ngl 99 \
  --host 127.0.0.1 --port 8083 > logs/rerank.log 2>&1 &
PIDS="$PIDS rerank:$!"
# The prompt biases whisper toward Taglish health vocabulary.
whisper-server -m "$WHISPER" -l auto --convert \
  --prompt "Kapiling. PhilHealth, Senior Citizen ID, maintenance, Losartan, Metformin, Amlodipine, blood sugar, FBS, HbA1c, BP, cholesterol, bakuna, flu vaccine, allergy sa penicillin." \
  --host 127.0.0.1 --port 8081 > logs/whisper.log 2>&1 &
PIDS="$PIDS whisper:$!"

# Phone access: HTTPS on the LAN (phones only allow the mic over HTTPS), self-signed, behind a pairing key.
IP="$(ipconfig getifaddr en0 || ipconfig getifaddr en1 || echo 127.0.0.1)"
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=Kapiling" \
  -addext "subjectAltName=IP:$IP,DNS:localhost" -keyout certs/key.pem -out certs/cert.pem 2> /dev/null
export KAPILING_KEY="${KAPILING_KEY:-$(openssl rand -hex 16)}"
export KAPILING_PHONE_URL="https://$IP:8443/?k=$KAPILING_KEY"

(cd backend && uv run python -m seed.persona)

(cd backend && uv run uvicorn kapiling.main:app --host 127.0.0.1 --port 8787 > ../logs/app.log 2>&1) &
PIDS="$PIDS app:$!"
(cd backend && uv run uvicorn kapiling.main:app --host 0.0.0.0 --port 8443 \
  --no-access-log --ssl-keyfile ../certs/key.pem --ssl-certfile ../certs/cert.pem > ../logs/phone.log 2>&1) &
PIDS="$PIDS phone:$!"
echo "Loading models…"
# tts stays false until the TTS task lands, so it is not waited on.
# Fail fast: a dead server or a missed deadline ends the wait instead of spinning forever.
HEALTH_CHECK='import json,sys; h=json.load(sys.stdin); bad=[k for k in ("llm","embed","rerank","whisper") if not h.get(k)]; print(" ".join(bad)); sys.exit(1 if bad else 0)'
DEADLINE=$((SECONDS + ${KAPILING_START_TIMEOUT:-300}))
while true; do
  for entry in $PIDS; do
    if ! kill -0 "${entry#*:}" 2> /dev/null; then
      echo "The ${entry%%:*} server died. Last lines of logs/${entry%%:*}.log:" >&2
      tail -n 20 "logs/${entry%%:*}.log" >&2
      exit 1
    fi
  done
  STILL_FALSE="$(curl -sf 127.0.0.1:8787/api/health 2> /dev/null | python3 -c "$HEALTH_CHECK" 2> /dev/null)" && break
  if [ "$SECONDS" -ge "$DEADLINE" ]; then
    echo "Timed out waiting for: ${STILL_FALSE:-the app (no health answer)}. See logs/ for details." >&2
    exit 1
  fi
  sleep 1
done
# Warm the model and cache the system prompt so the first real question is fast.
curl -s --max-time 60 -o /dev/null -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":1}' 127.0.0.1:8080/v1/chat/completions
echo "Kapiling → http://127.0.0.1:8787  (logs in logs/)"
echo "Phone (same Wi-Fi or hotspot) → scan this, then accept the one-time certificate warning:"
echo "$KAPILING_PHONE_URL"
(cd backend && uv run python -c "import qrcode, sys; q = qrcode.QRCode(border=1); q.add_data(sys.argv[1]); q.print_ascii(invert=True)" "$KAPILING_PHONE_URL")
wait
