# Backend

FastAPI app for Kapiling, Python 3.11 or newer, managed with `uv`. It serves the REST and SSE API and the built web app (`backend/static`). Every model endpoint and path is read from environment variables in `kapiling/config.py` only.

## Layout

| Path | Contents |
|---|---|
| `kapiling/main.py` | App, pairing middleware, `/api/health`, startup tasks |
| `kapiling/config.py` | Settings: `LLM_URL`, `EMBED_URL`, `RERANK_URL`, `WHISPER_URL`, `KAPILING_DATA`, `KAPILING_KEY`, `KAPILING_DEMO`, `DOCLING_ARTIFACTS` |
| `kapiling/db.py` | SQLite connection, schema (`user_version = 1`), sqlite-vec |
| `kapiling/auth/` | PIN hashing, sessions, lockout, access log, WebAuthn |
| `kapiling/records/` | Profiles, cards, medicines, observations, emergency card, summary |
| `kapiling/docs/` | Upload, vision transcript, Docling chunking, index, hybrid retrieval |
| `kapiling/chat/` | Agent loop, tools, AG-UI events, run registry, safety, form filler |
| `kapiling/voice/` | Whisper client, MMS-TTS, sentence aggregation, turn timing |
| `kapiling/demo.py` | Cloud demo mode (inert unless `KAPILING_DEMO=1`) |
| `seed/` | Fictional persona, generated card and document images, seed ingestion |
| `eval/` | Retrieval and safety evaluation, see `eval/README.md` |
| `tests/` | pytest suite |

Routes are listed in [../docs/api.md](../docs/api.md); design in [../docs/architecture.md](../docs/architecture.md).

## Run and test

`./run.sh` from the repository root starts everything. To run only the tests:

```sh
cd backend && uv run pytest -q
```

Tests that touch the model servers or the ingestion worker use switches such as `KAPILING_WORKER=0`, `KAPILING_TTS_WARM=0` and `KAPILING_LLM_WARM=0`. Seed a database by hand with `uv run python -m seed.persona`.
