# Deploy

A cloud demo for a GPU VM. It is **packaged, not deployed**: nothing in this repository has been run on a server. It still uses only self-hosted open models, with no cloud AI API.

## Files

| File | Role |
|---|---|
| `../Dockerfile` | App image: bun builds the frontend, then python slim with `uv` runs the API |
| `compose.yaml` | Services: `llm` (:8080), `embed` (:8082), `rerank` (:8083), `whisper` (:8081), `app` (:8787), `caddy` (80 and 443) |
| `Caddyfile` | TLS for `$KAPILING_DOMAIN`, reverse proxy to the app with response flushing off so SSE streams |

## Run

```sh
export KAPILING_DOMAIN=demo.example.com MODELS=/path/to/models   # filled by scripts/fetch_models.sh
docker compose -f deploy/compose.yaml up -d --build
```

The three llama.cpp containers and whisper need an NVIDIA GPU and the model files under `$MODELS`.

## Demo mode

`KAPILING_DEMO=1` (set in `compose.yaml`) does three things: `GET /api/demo` reports demo mode so the app can show a "Fictional data" banner, `POST /api/demo/reset` wipes and reseeds only the demo data folder (it returns 404 when demo mode is off), and pairing is turned off. Use fictional data only.

## `--proxy-headers`

The app runs `uvicorn ... --proxy-headers --forwarded-allow-ips "*"` behind Caddy. Without it the app would see the proxy's address and plain HTTP, which breaks secure cookies and the WebAuthn origin check. Only expose the app through Caddy.
