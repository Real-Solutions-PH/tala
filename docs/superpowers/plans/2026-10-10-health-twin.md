# Kapiling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Tala store assistant into **Kapiling**, rebranded: a local-first personal health record you talk to,
with streaming chat, document retrieval over photographed records, a low-latency voice mode, an
emergency card, bilingual UI (English/Tagalog) and a new elderly-first design system.

**Architecture:** A FastAPI backend (Python package `kapiling`) on top of four local model servers
(llama-server for chat and vision, llama-server for embeddings, llama-server for reranking, whisper-server).
SQLite holds structured health facts, conversations, the FTS5 keyword index and the `sqlite-vec` vector
index. Chat and voice share one AG-UI-over-SSE run endpoint. A Vite + React + TypeScript single-page app,
built into `backend/static/`, is served by the same FastAPI process, so the deployment is still one
process plus the model servers.

**Tech Stack:** Python 3.11+, uv, FastAPI, httpx, sqlite3 + sqlite-vec + FTS5, Docling (`HybridChunker`),
langchain-core (`Document`), transformers (MMS-TTS), pytest. On the frontend: Vite, React 19, TypeScript,
React Router, TanStack Query, lucide-react, Recharts, react-markdown, @ricky0123/vad-web, Vitest + Testing
Library, Playwright. Models: Qwen3-VL-8B-Instruct Q4_K_M (with mmproj), Qwen3-Embedding-0.6B Q8_0,
bge-reranker-v2-m3 Q8_0, whisper large-v3-turbo, facebook/mms-tts-tgl and facebook/mms-tts-eng.

**Spec:** `docs/superpowers/specs/2026-10-10-health-twin-design.md`. Read it before starting any task.

## Global Constraints

- Work on branch `health-twin`. The store assistant stays in `main`'s history. Never rewrite history.
- Everything works with networking off once the models are downloaded. No CDN, no Google Fonts URL, no cloud AI API. Fonts and VAD/ONNX assets are self-hosted under `frontend/public/`.
- All model endpoints and paths come from environment variables read in `backend/kapiling/config.py` only.
- No diagnosis and no medication advice. The disclaimer and the refusal are fixed catalogue strings rendered as blocks. The model never writes them.
- Every UI string lives in `frontend/src/i18n/en.ts` and `frontend/src/i18n/tl.ts` with identical keys, added in the same commit.
- Contrast is at least 4.5:1 for text in both themes. Touch targets are at least 48 px (64 px for primary actions). Body text is 18 px, with a 15 px minimum. Every icon is paired with a word.
- Demo data is fictional. Every generated card image carries a "SAMPLE – HINDI TOTOO" watermark and uses no real agency logo.
- Passwords and PINs are hashed with `hashlib.scrypt`. No PHI goes in URLs or logs. Request logs print paths and timings only.
- Sync database calls never run inside `async def` handlers. Use `def` handlers or `run_in_threadpool` (G-C-058).
- Every task leaves its tests green: `cd backend && uv run pytest -q` and `cd frontend && bun run test --run && bun run typecheck`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

## File structure

```
backend/
  pyproject.toml
  kapiling/
    __init__.py
    config.py            # env → settings (model URLs, paths, keys)
    db.py                # connect(), schema, migrations (PRAGMA user_version)
    main.py              # FastAPI app, routers, static mount, pairing middleware
    auth/
      lock.py            # PIN hash/verify, sessions, representatives, access log, require_unlocked dependency
      routes.py
    records/
      repo.py            # CRUD for profile, conditions, allergies, meds, med_logs, vaccines, cards, visits, observations, contacts
      summary.py         # essential_summary(profile_id) -> str (goes into the system prompt) and emergency_card(profile_id)
      routes.py          # REST for pages
    docs/
      store.py           # documents table + files on disk
      vision.py          # VLM transcription + lab-value extraction (JSON schema)
      ingest.py          # parse → HybridChunker → LangChain Document → batch embed → batch write; job runner
      index.py           # sqlite-vec + FTS5 write/delete
      retrieve.py        # hybrid search + RRF + rerank + floor → list[Hit]
      routes.py
    chat/
      agui.py            # AG-UI event constructors + SSE encoder
      runs.py            # run registry, cancel, composing deadline
      agent.py           # the agent loop (streaming, tools, blocks, steps)
      tools.py           # tool schemas + implementations (records, search, form, recommendations)
      prompts.py         # system prompt per language
      safety.py          # disclaimer/refusal block builders
      conversations.py   # conversations + messages persistence, titles
      routes.py          # POST /api/runs, POST /api/runs/{id}/cancel, conversations REST
    voice/
      stt.py             # whisper-server client
      tts.py             # MMS-TTS tgl/eng, clean(), synth in threadpool
      sentences.py       # SentenceAggregator for token streams
      timing.py          # TurnTimer stamps → turn_timings
  seed/
    persona.py           # fictional Lola Remedios + child Mika
    make_images.py       # renders sample cards and lab-result photos (Pillow)
    assets/              # generated PNGs (committed)
  eval/
    questions.jsonl      # NOT indexed; retrieval + safety questions
    run_eval.py
  tests/                 # pytest, one file per module
  static/                # vite build output (gitignored)
frontend/
  package.json, vite.config.ts, tsconfig.json, index.html, playwright.config.ts
  public/fonts/*.woff2, public/vad/*  (self-hosted)
  src/
    main.tsx, App.tsx, routes.tsx
    design/tokens.css, base.css
    i18n/en.ts, tl.ts, index.tsx      # I18nProvider, useT(), formatDate/formatNumber
    api/client.ts, queries.ts, agui.ts (SSE parser + run reducer)
    components/  Button, Card, Sheet, Toast, Skeleton, EmptyState, ErrorState, Badge, Chip, TopBar, BottomNav, Disclaimer
    features/
      chat/   ChatPage, MessageList, Composer, StepList, blocks/*, HistoryDrawer
      voice/  UsapMode, useVad, audioQueue
      cards/  CardsPage, CardViewer
      meds/   MedsPage
      records/ RecordsPage, HealthSummary, Timeline, LabDetail, DocumentViewer, ReviewExtraction
      emergency/ EmergencyPage
      lock/   LockScreen, useLock
      settings/ SettingsPage, ProfilePage, AccessLog
  e2e/*.spec.ts
DESIGN.md                # rewritten for the health design system
run.sh                   # starts 4 model servers + app
```

The old root files (`app.py`, `store.py`, `tools.py`, `life.py`, `db.py`, `seed.py`, `tts.py`, `test_tools.py`,
`static/index.html`) are deleted in Task 1 once their reusable parts have moved.

---

## Shared contracts

Every task's implementer must use these exact names. If a task needs to change a contract, it updates this
section in the same commit.

### C1. Database schema (`backend/kapiling/db.py`, `user_version = 1`)

```sql
CREATE TABLE profiles (id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, nickname TEXT, birth_date TEXT NOT NULL,
  sex TEXT CHECK (sex IN ('F','M')), blood_type TEXT, photo_path TEXT, address TEXT, phone TEXT,
  philhealth_no TEXT, senior_id_no TEXT, language TEXT NOT NULL DEFAULT 'tl', created TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE emergency_fields (profile_id INTEGER PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
  fields TEXT NOT NULL DEFAULT '["photo","age","blood_type","allergies","conditions","meds","contacts","doctor","philhealth_last4"]');
CREATE TABLE contacts (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL, relation TEXT, phone TEXT NOT NULL, is_emergency INTEGER NOT NULL DEFAULT 1, is_doctor INTEGER NOT NULL DEFAULT 0,
  specialty TEXT, clinic TEXT);
CREATE TABLE conditions (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL, since TEXT, status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','resolved')), notes TEXT);
CREATE TABLE allergies (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  substance TEXT NOT NULL, reaction TEXT, severity TEXT CHECK (severity IN ('mild','moderate','severe')));
CREATE TABLE family_history (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  relation TEXT NOT NULL, condition TEXT NOT NULL);
CREATE TABLE medications (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL, strength TEXT, form TEXT, purpose TEXT, prescriber TEXT,
  schedule TEXT NOT NULL DEFAULT '[]',          -- JSON list of "HH:MM"
  start_date TEXT, end_date TEXT, supply_left INTEGER, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE med_logs (med_id INTEGER NOT NULL REFERENCES medications(id) ON DELETE CASCADE, date TEXT NOT NULL,
  slot TEXT NOT NULL, taken_at TEXT NOT NULL, PRIMARY KEY (med_id, date, slot));
CREATE TABLE vaccines (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL, dose TEXT, date TEXT, next_due TEXT, facility TEXT, document_id INTEGER REFERENCES documents(id));
CREATE TABLE cards (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('philhealth','senior','hmo','pwd','vaccination','national_id','other')),
  label TEXT NOT NULL, number TEXT, front_path TEXT NOT NULL, back_path TEXT, expires TEXT, sort INTEGER NOT NULL DEFAULT 0);
CREATE TABLE visits (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  date TEXT NOT NULL, facility TEXT, doctor TEXT, reason TEXT, notes TEXT, document_id INTEGER REFERENCES documents(id));
CREATE TABLE observations (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  code TEXT NOT NULL,          -- normalised key: 'bp_systolic','bp_diastolic','fbs','hba1c','total_chol','ldl','hdl','trig','creatinine','weight','hemoglobin', or 'other:<name>'
  label TEXT NOT NULL, value REAL, value_text TEXT, unit TEXT, ref_low REAL, ref_high REAL, date TEXT NOT NULL,
  facility TEXT, document_id INTEGER REFERENCES documents(id), status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('proposed','confirmed')));
CREATE TABLE documents (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('lab','record','prescription','discharge','imaging','other')),
  date TEXT, facility TEXT, file_path TEXT NOT NULL, mime TEXT NOT NULL, pages INTEGER NOT NULL DEFAULT 1,
  sha256 TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','reading','indexed','failed')),
  error TEXT, transcript_md TEXT, created TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE (profile_id, sha256));
CREATE TABLE chunks (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  profile_id INTEGER NOT NULL, ord INTEGER NOT NULL, text TEXT NOT NULL, meta TEXT NOT NULL,  -- JSON: title, headings[], page, bbox
  content_hash TEXT NOT NULL);
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
-- created in docs/index.py after loading sqlite-vec:
-- CREATE VIRTUAL TABLE chunks_vec USING vec0(chunk_id INTEGER PRIMARY KEY, profile_id INTEGER PARTITION KEY, document_id INTEGER, embedding FLOAT[1024] distance_metric=cosine);
CREATE TABLE conversations (id TEXT PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL, created TEXT NOT NULL DEFAULT (datetime('now')), updated TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user','assistant')), content TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'text' CHECK (mode IN ('text','voice','usap','listen')),
  status TEXT NOT NULL DEFAULT 'complete' CHECK (status IN ('complete','stopped','interrupted','failed')),
  blocks TEXT NOT NULL DEFAULT '[]', steps TEXT NOT NULL DEFAULT '[]', sources TEXT NOT NULL DEFAULT '[]',
  attachments TEXT NOT NULL DEFAULT '[]', created TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE turn_timings (message_id TEXT PRIMARY KEY, stamps TEXT NOT NULL);  -- JSON {stamp: ms since speech_end or request}
CREATE TABLE representatives (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL, relation TEXT, pin_hash TEXT NOT NULL);
CREATE TABLE owner_lock (profile_id INTEGER PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE, pin_hash TEXT NOT NULL,
  webauthn TEXT);  -- JSON list of credentials
CREATE TABLE access_log (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  target TEXT, at TEXT NOT NULL DEFAULT (datetime('now')));
```

### C2. REST API (all under `/api`, JSON, locked unless marked public)

| Method + path | Returns |
|---|---|
| `GET /profiles` (public) | `[{id, nickname, full_name, photo_url}]`. Used by the lock screen and the profile switcher. |
| `POST /unlock` (public) `{profile_id, pin}` | 204 + `kapiling_s` cookie, or 401 `{detail}`. Actor = owner or representative name. |
| `POST /lock` | 204 |
| `GET /emergency/{profile_id}` (public) | `EmergencyCard` (below) |
| `GET /profiles/{pid}/summary` | `{profile, conditions[], allergies[], meds[], latest: {code: Observation}, contacts[]}` |
| `GET/PUT /profiles/{pid}` | profile fields |
| `GET /profiles/{pid}/cards` | `[{id, kind, label, number_masked, front_url, back_url, expires}]` |
| `GET /files/{card_id}/{side}` (side = front/back) | the card image. Locked and logged as `view_cards`. Card `front_url`/`back_url` point here. |
| `GET /profiles/{pid}/photo` (public) | the profile photo, used by the lock screen and the emergency card |
| `POST /profiles/{pid}/cards` (multipart `kind`, `label`, `number?`, `front`, `back?`) | created card |
| `GET /emergency/{pid}/qr.svg` (public) | SVG |
| `GET /profiles/{pid}/meds?date=YYYY-MM-DD` | `{meds: [...], today: [{med_id, slot, taken_at|null}]}` |
| `POST /profiles/{pid}/meds/{mid}/taken` `{date, slot}` / `DELETE` same | 204 |
| `GET /profiles/{pid}/timeline?kind=` | `[{kind:'visit'|'lab'|'vaccine'|'document', date, title, ref_id}]` newest first |
| `GET /profiles/{pid}/observations?code=` | `[Observation]` oldest first |
| `GET/POST /profiles/{pid}/documents` (multipart `file`, `title?`, `kind?`) | Document list / created Document `{id, status}` |
| `GET /documents/{id}` / `GET /documents/{id}/file` / `GET /documents/{id}/page/{n}.png` | metadata / original / page image |
| `POST /documents/{id}/observations/confirm` `{ids: [..], edits: {id: {value, unit, date}}}` | 204 |
| `GET /profiles/{pid}/conversations` | `[{id, title, updated}]` |
| `GET /conversations/{id}` | `{id, title, messages: [Message]}` |
| `PATCH /conversations/{id}` `{title}` / `DELETE /conversations/{id}` | 204 |
| `POST /runs` (multipart: `profile_id`, `conversation_id?`, `message?`, `lang`, `mode`, `speak` (0/1), `files[]?`, `audio?`) | `text/event-stream` of AG-UI events (C3) |
| `POST /runs/{run_id}/cancel` | 204 |
| `GET /access-log?profile_id=` | `[{actor, action, target, at}]` |
| `GET /health` (public) | `{llm, embed, rerank, whisper, tts: bool}` |

`EmergencyCard = {profile_id, name, photo_url|null, age|null, blood_type|null, allergies: [{substance, reaction, severity}], conditions: [str], meds: [{name, strength, schedule}], contacts: [{name, relation, phone}], doctor: {name, clinic, phone}|null, philhealth_last4|null, qr_text}`. Fields not selected in `emergency_fields` are `null` or empty.

### C3. AG-UI events (`backend/kapiling/chat/agui.py`)

Each SSE frame is `data: <json>\n\n`, where the JSON is one of these:

```json
{"type":"RUN_STARTED","threadId":"<conversation_id>","runId":"<run_id>"}
{"type":"STEP_STARTED","stepName":"search_records"}            // stepName is a key into i18n "steps.*"
{"type":"STEP_FINISHED","stepName":"search_records"}
{"type":"TOOL_CALL_START","toolCallId":"c1","toolCallName":"get_medications"}
{"type":"TOOL_CALL_END","toolCallId":"c1"}
{"type":"TEXT_MESSAGE_START","messageId":"<msg_id>","role":"assistant"}
{"type":"TEXT_MESSAGE_CONTENT","messageId":"<msg_id>","delta":"Losartan"}
{"type":"TEXT_MESSAGE_END","messageId":"<msg_id>"}
{"type":"CUSTOM","name":"transcript","value":{"text":"anong gamot ko"}}
{"type":"CUSTOM","name":"block","value":<Block>}
{"type":"CUSTOM","name":"sources","value":[<Source>]}
{"type":"CUSTOM","name":"audio","value":{"seq":0,"wav_b64":"..."}}
{"type":"CUSTOM","name":"timing","value":{"first_token":812, "...": 0}}
{"type":"RUN_ERROR","message":"<i18n key>","code":"llm_unavailable|timeout|cancelled|bad_input|internal"}
{"type":"RUN_FINISHED","threadId":"<conversation_id>","runId":"<run_id>","result":{"messageId":"<saved id>","status":"complete|stopped|interrupted|failed"}}
```

Step names: `reading_photo`, `transcribing`, `search_records`, `check_profile`, `check_meds`, `check_labs`,
`check_cards`, `reading_form`, `answering_form`, `planning_meals`, `planning_activities`.

`Block` is a discriminated union on `type`:

```ts
type Block =
 | {type:'card', card_id:number, label:string, front_url:string, back_url:string|null}
 | {type:'profile_fields', fields:{key:string, value:string}[]}          // key = i18n "fields.*"
 | {type:'med_list', meds:{name:string, strength:string|null, schedule:string[], purpose:string|null}[]}
 | {type:'lab_table', rows:{label:string, value:string, unit:string|null, ref:string|null, date:string, flag:'low'|'high'|null}[]}
 | {type:'chart', code:string, label:string, unit:string|null, points:{date:string, value:number}[], ref_low:number|null, ref_high:number|null}
 | {type:'document', document_id:number, title:string, date:string|null, thumb_url:string}
 | {type:'form_answers', items:{field:string, answer:string|null, source:string|null}[]}   // answer null = not on record
 | {type:'disclaimer'}                                                   // text from i18n "safety.disclaimer"
 | {type:'refusal', kind:'diagnosis'|'medication'}                       // text from i18n "safety.refusal.*"
type Source = {n:number, chunk_id:number, document_id:number, title:string, page:number|null, before:string, match:string, after:string}
```

### C4. Python interfaces used across tasks

```python
# kapiling/config.py
class Settings: llm_url: str; embed_url: str; rerank_url: str; whisper_url: str; data_dir: Path; db_path: Path
settings: Settings

# kapiling/db.py
def connect() -> sqlite3.Connection           # row_factory=Row, foreign_keys=ON, sqlite-vec loaded, schema applied

# kapiling/records/summary.py
def essential_summary(con, profile_id: int, lang: str) -> str          # <= 1,500 tokens, used in the system prompt
def emergency_card(con, profile_id: int) -> dict                       # EmergencyCard

# kapiling/docs/retrieve.py
@dataclass
class Hit: chunk_id: int; document_id: int; title: str; page: int | None; text: str; score: float
def search(con, profile_id: int, query: str, k: int = 6) -> list[Hit]

# kapiling/docs/ingest.py
def enqueue(con, profile_id: int, data: bytes, filename: str, mime: str, title: str | None, kind: str | None) -> int
async def run_pending() -> None                                         # detached worker loop

# kapiling/voice/tts.py
def speak(text: str, lang: str) -> bytes                                # WAV, sync; call via run_in_threadpool
# kapiling/voice/sentences.py
class SentenceAggregator: def push(self, delta: str) -> list[str]; def flush(self) -> list[str]
# kapiling/voice/stt.py
async def transcribe(audio: bytes, mime: str, lang: str) -> str

# kapiling/chat/tools.py
ToolResult = tuple[dict, list[dict], str | None]                        # (result for the model, blocks, step name)
TOOLS: dict[str, Callable[[sqlite3.Connection, int, dict, "RunCtx"], ToolResult]]
SCHEMAS: list[dict]
```

---

## Execution waves

Tasks in the same wave touch disjoint files and can run in parallel, one subagent and one worktree each.
A wave starts after the previous wave has merged.

| Wave | Tasks | Notes |
|---|---|---|
| 0 | 1 | Scaffold. Must land first. |
| 1 | 2, 3, 4 | Schema and seed / design system and i18n / model servers and run.sh |
| 2 | 5, 6, 7, 8, 9, 10 | Records API / lock and emergency backend / ingestion / AG-UI and conversations / TTS and sentences / app shell |
| 3 | 11, 12, 13, 14, 15 | Retrieval / agent and tools / Cards, Meds, Emergency, Lock UI / Records UI / Settings and profile UI |
| 4 | 16, 17, 18 | Chat UI / form filling / voice (Usap and listen-in) |
| 5 | 19, 20, 21 | Evaluation and floor calibration / end-to-end journeys and latency report / docs and cloud demo packaging |

---

### Task 1: Scaffold the new layout

**Files:**
- Create: `backend/pyproject.toml`, `backend/kapiling/__init__.py`, `backend/kapiling/config.py`, `backend/kapiling/main.py`, `backend/tests/test_health.py`
- Create: `frontend/` via `bun create vite frontend --template react-ts`, then `frontend/vite.config.ts`
- Do not carry over the old brand: `static/fonts`, `static/icon-*.png` and the star mark go with `static/` (Task 3 creates the Kapiling assets)
- Delete: `app.py store.py tools.py life.py db.py seed.py tts.py test_tools.py static/ kapiling.db *.log run.out`
- Modify: `.gitignore` (add `backend/static/`, `backend/data/`, `frontend/node_modules/`, `frontend/test-results/`)

**Interfaces:**
- Produces: `kapiling.config.settings`, `kapiling.main.app`, `GET /api/health`, the Vite dev proxy `/api → 127.0.0.1:8787`.

- [ ] **Step 0: Protect uncommitted work.** `main` has an uncommitted change to `static/index.html` and an untracked `DESIGN.md` (store assistant). Ask the owner whether to commit them on `main` first; never discard them.
- [ ] **Step 1: Create the branch.** `git switch -c health-twin`
- [ ] **Step 2: Write the failing test** `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient
from kapiling.main import app

def test_health_reports_each_model_server():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert set(r.json()) == {"llm", "embed", "rerank", "whisper", "tts"}
```

- [ ] **Step 3: Run it.** `cd backend && uv run pytest tests/test_health.py -q` → fails: no module `kapiling`.
- [ ] **Step 4: Implement.** `backend/pyproject.toml` with the deps from the Tech Stack line (`fastapi uvicorn python-multipart httpx pypdf qrcode sqlite-vec docling langchain-core transformers torch scipy num2words pillow`, dev: `pytest`), `[tool.uv] package = false`, `[tool.pytest.ini_options] pythonpath = ["."]`. `config.py`:

```python
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    llm_url: str = os.getenv("LLM_URL", "http://127.0.0.1:8080")
    embed_url: str = os.getenv("EMBED_URL", "http://127.0.0.1:8082")
    rerank_url: str = os.getenv("RERANK_URL", "http://127.0.0.1:8083")
    whisper_url: str = os.getenv("WHISPER_URL", "http://127.0.0.1:8081")
    data_dir: Path = Path(os.getenv("KAPILING_DATA", ROOT / "data"))
    pair_key: str = os.getenv("KAPILING_KEY", "")
    demo: bool = os.getenv("KAPILING_DEMO", "0") == "1"
    @property
    def db_path(self) -> Path: return self.data_dir / "kapiling.db"

settings = Settings()
```

Modules read settings as `from kapiling import config` then `config.settings.<field>` **at call time** (never `from kapiling.config import settings`), so tests can swap `config.settings`. `main.py`: the app, the pairing middleware carried over from the old `app.py` (same cookie logic, with `/api/emergency/*` and `/api/profiles` also allowed through), `/api/health` probing each server's `/health` with a 1 s timeout (TTS = model loaded), and the static mount of `backend/static` when it exists.
- [ ] **Step 5: Frontend scaffold.** In `frontend/`: `bun add react-router @tanstack/react-query lucide-react recharts react-markdown @ricky0123/vad-web onnxruntime-web` and `bun add -d vitest @testing-library/react @testing-library/user-event jsdom @playwright/test`. Scripts: `dev`, `build` (outputs to `../backend/static`), `test` (`vitest --passWithNoTests`), `typecheck` (`tsc -b --noEmit`). The Vite proxy sends `/api` to `http://127.0.0.1:8787`.
- [ ] **Step 6: Verify.** `uv run pytest -q` passes. `bun run build` writes `backend/static/index.html`.
- [ ] **Step 7: Commit.** `chore: scaffold backend package and Vite frontend for Kapiling`

---

### Task 2: Schema, migrations and the fictional seed

**Files:**
- Create: `backend/kapiling/db.py`, `backend/seed/persona.py`, `backend/seed/make_images.py`, `backend/seed/assets/*.png`, `backend/tests/test_db.py`, `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `settings` (Task 1).
- Produces: `connect()`, schema C1, the fixture `con` (a temp DB with the seed loaded) in `conftest.py`, and `persona.seed(con) -> {"lola": int, "mika": int}`.

- [ ] **Step 1: Failing tests** `backend/tests/test_db.py`:

```python
def test_schema_applies_and_vec_loads(con):
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1
    assert con.execute("select vec_version()").fetchone()[0]

def test_seed_has_two_profiles_with_essentials(con):
    lola = con.execute("select * from profiles where nickname='Lola Remy'").fetchone()
    assert lola["blood_type"] == "O+"
    assert con.execute("select count(*) from allergies where profile_id=?", (lola["id"],)).fetchone()[0] >= 1
    assert con.execute("select count(*) from medications where profile_id=? and active=1", (lola["id"],)).fetchone()[0] == 3
    assert con.execute("select count(*) from cards where profile_id=?", (lola["id"],)).fetchone()[0] == 4
    assert con.execute("select count(*) from observations where code='fbs' and profile_id=?", (lola["id"],)).fetchone()[0] >= 6

def test_profile_delete_cascades(con):
    pid = con.execute("select id from profiles where nickname='Mika'").fetchone()[0]
    con.execute("delete from profiles where id=?", (pid,))
    assert con.execute("select count(*) from vaccines where profile_id=?", (pid,)).fetchone()[0] == 0
```

`conftest.py` provides fixtures `con`, `lola` (int id) and `mika` (int id). It points `config.settings` at a `tmp_path` data dir (monkeypatch `kapiling.config.settings` with `dataclasses.replace`), calls `connect()` and then `persona.seed(con)`.
- [ ] **Step 2: Run it** and see it fail.
- [ ] **Step 3: Implement `db.py`.** `connect()` creates `data_dir`, opens the DB with `check_same_thread=False`, sets `PRAGMA foreign_keys=ON` and `journal_mode=WAL`, runs `sqlite_vec.load(con)`, and applies the C1 schema when `user_version < 1`, then sets it to 1. Migrations are a list of SQL strings indexed by version.
- [ ] **Step 4: Implement the seed.** The persona, all fictional:
  - **Lola Remy:** Remedios "Lola Remy" Santos Dela Cruz, born 1953-04-12, F, O+, Marikina.
    - Conditions: hypertension (since 2011), type 2 diabetes (since 2016), osteoarthritis of the knee.
    - Allergies: penicillin (rash, moderate) and shrimp (hives, mild).
    - Medicines: Losartan 50 mg at 08:00, Metformin 500 mg at 08:00 and 20:00, Amlodipine 5 mg at 20:00.
    - Vaccines: influenza on 2025-04-10 (next due 2026-04), PCV13 on 2023-06-02, COVID-19 booster on 2023-01-15.
    - Contacts: daughter Ana (emergency) and Dr. Jose Reyes, internal medicine (doctor).
    - Family history: mother, stroke; father, diabetes.
    - 8 quarterly FBS and BP observations from 2024-07 to 2026-07, plus 2 HbA1c and 1 lipid panel.
    - Visits matching those dates.
    - Cards: PhilHealth, Senior Citizen, HMO, vaccination card.
  - **Mika:** Mika Dela Cruz, born 2020-02-03. The DOH routine childhood vaccines up to the age-6 boosters, with one overdue so the reminder has something to show.
  - **Representative:** Ana, PIN `246810`. The owner PIN is `123456`. These are documented in the README as demo-only.
- [ ] **Step 5: Implement `make_images.py`** (Pillow). It renders 4 card fronts and backs and 6 lab-result "photos" into `seed/assets/`:
  - The lab results: CBC, FBS+HbA1c, lipid panel, creatinine, an old 2019 discharge summary, and a handwritten-style prescription.
  - Each photo is rendered as a paper sheet at about 1600 px wide, then rotated ±3°, given slight blur and noise, and set on a desk-coloured background, so the vision model is tested on realistic input.
  - Every card says "SAMPLE – HINDI TOTOO" diagonally, and no image uses a real agency logo.
  - The seed copies these images into `data_dir/files/` and inserts the card rows. Documents are **not** inserted here; Task 7 ingests them through the real pipeline.
- [ ] **Step 6: Run** `uv run pytest -q` → pass. Run `uv run python -m seed.make_images` and look at the images (open two of them).
- [ ] **Step 7: Commit.** `feat: health schema, fictional demo persona and sample record images`

---

### Task 3: Brand, design system, i18n and base components

**Files:**
- Create: `DESIGN.md` (replace), `frontend/src/design/tokens.css`, `frontend/src/design/base.css`, `frontend/public/fonts/` (Atkinson Hyperlegible Next 400/700 and Figtree 600/700 woff2, latin + latin-ext, copied from the `@fontsource/atkinson-hyperlegible-next` and `@fontsource/figtree` packages), `frontend/src/brand/{Mark.tsx,mark.svg}`, `frontend/public/{favicon.svg,icon-180.png,icon-192.png,icon-512.png,icon-maskable-512.png}`, `frontend/scripts/icons.ts` (renders the PNGs from `mark.svg` with sharp), `frontend/public/manifest.webmanifest` (`name`/`short_name` "Kapiling", `theme_color` `#1F4E8C`, `background_color` `#FBF8F3`), `frontend/src/i18n/{en.ts,tl.ts,index.tsx}`, `frontend/src/components/*.tsx`, `frontend/src/i18n/i18n.test.ts`, `frontend/src/components/components.test.tsx`

**Interfaces:**
- Produces: `useT(): (key: Key, vars?: Record<string, string|number>) => string`, `useLang(): ['en'|'tl', (l) => void]`, `formatDate(d, lang)`, `formatNumber(n, lang)`, `type Key = keyof typeof en` (flattened dotted keys). Components: `Button({variant:'primary'|'secondary'|'danger'|'ghost', size:'md'|'lg', icon?, children, loading?})`, `Card`, `Sheet`, `ToastProvider` + `useToast()`, `Skeleton`, `EmptyState({icon, title, body, action?})`, `ErrorState({onRetry})`, `Badge({tone:'ok'|'warn'|'danger'|'info', children})`, `Chip`, `Disclaimer`.

- [ ] **Step 1: Failing tests** `i18n.test.ts`:

```ts
import { en } from './en'; import { tl } from './tl'
import { readFileSync } from 'node:fs'; import { globSync } from 'node:fs'
const flat = (o: object, p = ''): string[] => Object.entries(o).flatMap(([k, v]) => typeof v === 'string' ? [p + k] : flat(v, p + k + '.'))
test('catalogues have identical keys', () => { expect(flat(tl).sort()).toEqual(flat(en).sort()) })
test('no catalogue value is empty', () => { for (const c of [en, tl]) for (const k of flat(c)) expect(k).toBeTruthy() })
test('every t("...") key used in src exists', () => {
  const keys = new Set(flat(en))
  for (const f of globSync('src/**/*.tsx')) for (const m of readFileSync(f, 'utf8').matchAll(/\bt\(\s*'([\w.]+)'/g)) expect(keys, `${f}: ${m[1]}`).toContain(m[1])
})
test('placeholders match between languages', () => {
  const ph = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join()
  const get = (o: any, k: string) => k.split('.').reduce((a, p) => a[p], o)
  for (const k of flat(en)) expect(ph(get(tl, k)), k).toBe(ph(get(en, k)))
})
```

`tl.ts` is typed `export const tl: Catalogue = {...}` where `type Catalogue = DeepStringify<typeof en>`, so a missing key also fails `tsc`.
- [ ] **Step 2: Run** `bun run test --run` → fails.
- [ ] **Step 3: Write the catalogues.** Namespaces: `nav`, `chat`, `steps`, `blocks`, `fields`, `cards`, `meds`, `records`, `emergency`, `lock`, `settings`, `safety`, `errors`, `toasts`, `voice`, `common`. `safety.disclaimer` and `safety.refusal.diagnosis` / `.medication` use the exact text in spec §2. Tagalog is everyday Tagalog with English medical terms people already use (BP, blood sugar, maintenance, PhilHealth), polite with *po*. Get a fluent reader to check it before Wave 5.
- [ ] **Step 4: Write `tokens.css`** with the token table from spec §10, light under `:root` and dark under `@media (prefers-color-scheme: dark)`. Also: `--text-scale` (1 / 1.25 / 1.5, set on `<html>` from Settings), `--fs-body: calc(18px * var(--text-scale))`, a type scale of 15/18/22/28/34, spacing 4/8/12/16/24/32/48, `--tap: 48px`, `--tap-lg: 64px`, `--radius-card: 20px`, `--radius-btn: 14px`, `font-variant-numeric: tabular-nums` on numbers, one shadow, motion `--dur: 200ms` with an ease-out curve, zeroed under `prefers-reduced-motion`. Add a script `frontend/scripts/contrast.ts` that parses `tokens.css` and asserts every `--ink`, `--muted`, `--primary`, `--accent`, `--warn` and `--danger` pair against `--bg` and `--surface` is at least 4.5:1 in both themes, asserts `--ink` on `--gold` is at least 4.5:1, and **fails if any CSS rule sets `color: var(--gold)`** (gold is never text). Run it from the `test` script.
- [ ] **Step 5: Write the components** using the tokens only (no raw hex). Every interactive component has a visible focus ring (3 px `--primary`), at least a `--tap` hit area, and a pressed state. `ToastProvider` uses `aria-live="polite"` and auto-dismisses after 4 s (G-C-079). `Skeleton` is a block with a shimmer that is off under reduced motion.
- [ ] **Step 6: Component tests** (`components.test.tsx`): the Button renders its label and is `aria-busy` while loading; a toast is announced in the live region and disappears after 4 s (fake timers); `EmptyState` renders its action button.
- [ ] **Step 7: Build the brand assets** (spec §9).
  - `mark.svg` is the two-circle mark: the large circle is `--primary`; the smaller circle overlaps it on the right, raised slightly; the overlap lens is `--gold`. Use a 24×24 viewBox with no strokes, so it stays crisp at 16 px.
  - `Mark.tsx` renders it inline with a `size` prop and an `eyes` prop. With `eyes`, the large circle gets two calm eye dots and becomes the Usap character, with states `idle`, `listening`, `thinking` and `speaking`. Each state is a small scale or opacity change, which is off under reduced motion.
  - `icons.ts` writes the PNG icons (white large circle and gold lens on a `#1F4E8C` rounded square, with a 20% maskable padding) and `favicon.svg`.
  - Set `<title>Kapiling</title>`, the theme-color meta and the apple-touch-icon in `index.html`.
  - Look at the icons at 180 px and 32 px before committing.
- [ ] **Step 8: Rewrite `DESIGN.md`** for Kapiling, following the old file's structure:
  - Who we design for.
  - Brand: name, tagline, idea, mark, voice, what it isn't.
  - Principles: big and plain, two taps to anything the hospital asks for, label everything, one plane, colour plus icon plus word, Tagalog first and polite, gold is never text.
  - The token table with contrast figures, type, components and states.
- [ ] **Step 9: Run** tests, typecheck and the contrast script. **Commit:** `feat: Kapiling brand, elderly-first design system, EN/TL catalogues and base components`

---

### Task 4: Model servers and run.sh

**Files:**
- Modify: `run.sh`
- Create: `scripts/fetch_models.sh`, `backend/tests/test_run_sh.py`

**Interfaces:**
- Produces: ports 8080 (chat and vision), 8081 (whisper), 8082 (embeddings), 8083 (rerank), 8787 (app on localhost), 8443 (app on LAN over HTTPS).

- [ ] **Step 1: `scripts/fetch_models.sh`** downloads with `hf download` (the user approves; about 1.3 GB), skipping files that already exist in `~/models`:
  - `Qwen/Qwen3-Embedding-0.6B-GGUF` file `Qwen3-Embedding-0.6B-Q8_0.gguf`
  - `gpustack/bge-reranker-v2-m3-GGUF` file `bge-reranker-v2-m3-Q8_0.gguf`

  - `Qwen/Qwen3-Embedding-0.6B` tokenizer files only (`tokenizer.json tokenizer_config.json vocab.json merges.txt special_tokens_map.json config.json`) into the HF cache, for Docling's chunker
  - `facebook/mms-tts-tgl` and `facebook/mms-tts-eng` into the HF cache
  After this script runs, nothing needs the network. Add `embed_tokenizer: str = os.getenv("EMBED_TOKENIZER", "Qwen/Qwen3-Embedding-0.6B")` to `Settings`, and set `HF_HUB_OFFLINE=1` in `run.sh`.
- [ ] **Step 2: Rewrite `run.sh`.** Keep the existing chat/vision and whisper lines, the certificate, the pairing QR and the warm-up, and add:

```bash
llama-server -m "$EMBED" --embedding --pooling last -c 8192 -ub 8192 -ngl 99 --host 127.0.0.1 --port 8082 > embed.log 2>&1 &
llama-server -m "$RERANK" --reranking -c 8192 -ub 8192 -ngl 99 --host 127.0.0.1 --port 8083 > rerank.log 2>&1 &
```

  Further changes:
  - Change the whisper `--prompt` to health vocabulary: "Kapiling. PhilHealth, Senior Citizen ID, maintenance, Losartan, Metformin, Amlodipine, blood sugar, FBS, HbA1c, BP, cholesterol, bakuna, flu vaccine, allergy sa penicillin."
  - Build the frontend if `backend/static` is missing.
  - Run uvicorn as `kapiling.main:app` from `backend/`.
  - Logs go to `logs/`.
  - Wait on all four `/health` endpoints before the warm-up.
- [ ] **Step 3: A smoke test that runs only when the servers are up** (`test_run_sh.py`). It is skipped with an explicit reason when `GET :8082/health` fails, and the skip count is reported (G-C-027). It checks that an embedding has 1024 dimensions and that the reranker ranks "Losartan 50 mg" above "pancit canton" for "gamot sa BP".
- [ ] **Step 4: Run** `./run.sh`, and confirm all four health checks pass and the smoke test passes, not skips.
- [ ] **Step 5: Commit.** `feat: run embeddings and reranker servers alongside chat, vision and whisper`

---

### Task 5: Records repository, summary and REST

**Files:**
- Create: `backend/kapiling/records/{repo.py,summary.py,routes.py}`, `backend/tests/test_records.py`
- Modify: `backend/kapiling/main.py` (include router)

**Interfaces:**
- Consumes: `connect()`, the `con` fixture.
- Produces: the C2 records endpoints (including `POST /profiles/{pid}/cards`, `GET /files/{card_id}/{side}` and `GET /profiles/{pid}/photo`), `essential_summary`, `emergency_card`, and repo functions `get_profile(con, pid)`, `list_meds(con, pid, active=True)`, `meds_today(con, pid, date)`, `mark_taken(con, mid, date, slot)`, `unmark_taken(...)`, `list_cards(con, pid)`, `list_vaccines(con, pid)`, `observations(con, pid, code=None, status='confirmed')`, `latest_observations(con, pid) -> dict[str, Row]`, `timeline(con, pid, kind=None)`. These are used by Task 12's tools.

- [ ] **Step 1: Failing tests:**

```python
def test_meds_today_lists_each_slot(con, lola):
    today = meds_today(con, lola, "2026-10-10")
    assert {(t["name"], t["slot"]) for t in today} == {("Losartan", "08:00"), ("Metformin", "08:00"), ("Metformin", "20:00"), ("Amlodipine", "20:00")}

def test_mark_taken_is_idempotent(con, lola):
    mid = list_meds(con, lola)[0]["id"]
    mark_taken(con, mid, "2026-10-10", "08:00"); mark_taken(con, mid, "2026-10-10", "08:00")
    assert sum(1 for t in meds_today(con, lola, "2026-10-10") if t["taken_at"]) == 1

def test_essential_summary_has_the_hospital_questions(con, lola):
    s = essential_summary(con, lola, "en")
    for must in ["O+", "Penicillin", "Losartan 50 mg", "Hypertension", "Ana", "FBS"]:
        assert must in s
    assert len(s) < 6000

def test_emergency_card_respects_field_choice(con, lola):
    con.execute("update emergency_fields set fields='[\"blood_type\"]' where profile_id=?", (lola,))
    card = emergency_card(con, lola)
    assert card["blood_type"] == "O+" and card["allergies"] == [] and card["philhealth_last4"] is None

def test_card_numbers_are_masked_in_list(client, lola_unlocked):
    cards = client.get(f"/api/profiles/{lola_unlocked}/cards").json()
    assert all(c["number_masked"].startswith("••••") for c in cards if c["number_masked"])
```

  Add the `client` and `lola_unlocked` fixtures to `conftest.py`. They use `TestClient` and a direct session-insert helper from Task 6. Until Task 6 lands, `require_unlocked` is a stub that allows everything, and its behaviour is tested in Task 6.
- [ ] **Step 2: Run, fail. Step 3: Implement.** The summary is a compact plain-text block with headings ("Profile", "Allergies", "Conditions", "Maintenance medicines", "Latest results", "Vaccines", "Emergency contact", "Doctor") in the requested language, with dates in ISO format. Write `qr_text` as a short multi-line text that stays under 600 characters.
- [ ] **Step 4: Run, pass. Step 5: Commit.** `feat: records repository, essential summary, emergency card and records API`

---

### Task 6: Lock, representatives, access log and the emergency endpoint

**Files:**
- Create: `backend/kapiling/auth/{lock.py,routes.py}`, `backend/tests/test_lock.py`
- Modify: `backend/kapiling/records/routes.py` (replace the stub dependency), `backend/kapiling/main.py`

**Interfaces:**
- Produces: `hash_pin(pin) -> str`, `verify_pin(pin, h) -> bool`, `require_unlocked(request) -> Actor` (a FastAPI dependency; `Actor = {profile_id, name, role:'owner'|'representative'}`), `log_access(con, pid, actor, action, target)`, the `POST /api/unlock` and `POST /api/lock` endpoints, `GET /api/emergency/{pid}`, `GET /api/emergency/{pid}/qr.svg` (public, a `qrcode` SVG of `qr_text`), `GET /api/access-log`.

- [ ] **Step 1: Failing tests:**

```python
def test_wrong_pin_is_refused_and_logged(client, con, lola):
    r = client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    assert r.status_code == 401
    assert con.execute("select action from access_log order by id desc").fetchone()[0] == "unlock_failed"

def test_representative_unlock_is_attributed(client, con, lola):
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "246810"}).status_code == 204
    client.get(f"/api/profiles/{lola}/cards")
    actors = {r[0] for r in con.execute("select actor from access_log where action='view_cards'")}
    assert actors == {"Ana"}

def test_locked_routes_refuse_without_session(client, lola):
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 401

def test_emergency_is_public(client, lola):
    r = client.get(f"/api/emergency/{lola}")
    assert r.status_code == 200 and r.json()["blood_type"] == "O+"

def test_session_cannot_read_another_profile(client, lola, mika):
    client.post("/api/unlock", json={"profile_id": mika, "pin": "123456"})
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 403

def test_five_failures_back_off(client, lola):
    for _ in range(5): client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"}).status_code == 429
```

- [ ] **Step 2: Run, fail. Step 3: Implement.**
  - PINs are hashed with `hashlib.scrypt(n=2**14, r=8, p=1)` and a random 16-byte salt, stored as `scrypt$salt$hash` in hex. Comparison uses `hmac.compare_digest`.
  - Sessions are an in-memory dict `token -> (Actor, expires)` with a 5-minute idle expiry that refreshes on each request. The cookie `kapiling_s` is httponly, samesite strict, and secure when served over HTTPS.
    `# ponytail: in-memory sessions; a restart locks everyone, which is the safe direction`
  - Backoff: 5 failures within 5 minutes per profile returns 429 for 60 s.
  - Access-log actions: `unlock`, `unlock_failed`, `view_cards`, `view_document`, `view_summary`, `export`.
  - The WebAuthn columns exist, but the endpoints come in Task 15.
- [ ] **Step 4: Run, pass. Step 5: Commit.** `feat: PIN lock with representatives, access log and a public emergency card`

---

### Task 7: Document ingestion (vision → Docling → chunks → embeddings → index)

**Files:**
- Create: `backend/kapiling/docs/{store.py,vision.py,ingest.py,index.py,routes.py}`, `backend/tests/test_ingest.py`, `backend/tests/fixtures/lab_fbs.md`

**Interfaces:**
- Consumes: `connect()`, settings URLs, `require_unlocked`.
- Produces: `enqueue(...)`, `run_pending()` (started on app startup as a detached task with its own connection, G-C-015), `index.write_chunks(con, document_id, profile_id, docs: list[langchain_core.documents.Document], vectors: list[list[float]])`, `index.delete_document(con, document_id)`, `embed_texts(texts: list[str]) -> list[list[float]]` (batched POST `/v1/embeddings`), `vision.transcribe(image_bytes, mime) -> str` (markdown), `vision.extract_observations(markdown) -> list[dict]`, and the document REST endpoints from C2.

**Pipeline per document** (spec §7, G-C-077):

```python
TEMPLATE_VERSION = "v1"   # part of content_hash: changing embed_text() wording must bump this

def embed_text(title: str, headings: list[str], text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip().lower() == title.strip().lower():
        lines = lines[1:]                     # drop a first line that repeats the title
    return "\n".join([title, *headings, "\n".join(lines)])    # plain newline join, no labels (G-C-077 measurement)

async def ingest(con, doc) -> None:
    if doc.mime.startswith("image/"):
        md = await vision.transcribe(read(doc), doc.mime)          # Qwen3-VL: "transcribe to markdown, keep tables"
        dl = DocumentConverter(allowed_formats=[InputFormat.MD]).convert(DocumentStream(name="t.md", stream=BytesIO(md.encode()))).document
    else:                                                           # PDF: Docling directly; OCR only if no text layer
        dl = DocumentConverter().convert(path).document
        md = dl.export_to_markdown()                                # kept for display and extraction only, never for chunking
    chunker = HybridChunker(tokenizer=HuggingFaceTokenizer.from_pretrained(config.settings.embed_tokenizer, max_tokens=512), merge_peers=True)
    docs = [Document(page_content=c.text, metadata={"title": doc.title, "headings": c.meta.headings or [],
            "page": first_page(c), "bbox": first_bbox(c), "ord": i})
            for i, c in enumerate(chunker.chunk(dl))]
    vectors = await embed_texts([embed_text(doc.title, d.metadata["headings"], d.page_content) for d in docs])   # one batched call
    index.write_chunks(con, doc.id, doc.profile_id, docs, vectors)                                               # one transaction
    obs = await vision.extract_observations(md)                     # JSON-schema-constrained; stored as status='proposed'
```

- [ ] **Step 1: Failing tests.** Model calls are substituted through one seam each: `vision._post` and `ingest._embed_post` (G-C-026). Never patch Docling.

```python
def test_embed_text_drops_repeated_title_and_uses_no_labels():
    s = embed_text("FBS 2026-03-02", ["Results"], "FBS 2026-03-02\nGlucose 132 mg/dL")
    assert s == "FBS 2026-03-02\nResults\nGlucose 132 mg/dL" and "title:" not in s

def test_markdown_lab_is_chunked_with_heading_path(con, lola, fake_models):
    did = enqueue(con, lola, FIXTURE_IMG, "fbs.jpg", "image/jpeg", "FBS and HbA1c — 2026-03-02", "lab")
    asyncio.run(process_one(con, did))
    rows = con.execute("select text, meta from chunks where document_id=?", (did,)).fetchall()
    assert rows and all(json.loads(r["meta"])["title"].startswith("FBS") for r in rows)
    assert con.execute("select count(*) from chunks_vec where document_id=?", (did,)).fetchone()[0] == len(rows)
    assert con.execute("select status from documents where id=?", (did,)).fetchone()[0] == "indexed"

def test_stored_text_is_bare_not_templated(con, lola, fake_models):
    ...  # chunk.text never starts with the title line added by embed_text

def test_embeddings_are_one_batched_call(con, lola, fake_models):
    ...  # fake_models.embed_calls == 1 for a 3-chunk document

def test_duplicate_upload_returns_existing_id(con, lola):
    a = enqueue(con, lola, b"x", "a.jpg", "image/jpeg", None, None); b = enqueue(con, lola, b"x", "b.jpg", "image/jpeg", None, None)
    assert a == b

def test_extracted_values_are_proposed_until_confirmed(con, lola, fake_models):
    ...  # observations from the doc have status='proposed'; POST confirm flips them; summary ignores proposed

def test_failure_marks_document_failed_with_reason(con, lola, failing_vision):
    ...  # status='failed', error='vision_unavailable'; no partial chunks remain

def test_reindex_replaces_chunks_atomically(con, lola, fake_models):
    ...  # processing the same document twice leaves exactly one set of chunks (delete + insert in one transaction)
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement `vision.py`.** POST to `{llm_url}/v1/chat/completions` with the image as a data URL and `temperature 0`.
  - Transcription prompt: "Transcribe this medical document exactly into Markdown. Use '#' for the facility or document title, '##' for sections, and Markdown tables for results with columns Test | Result | Unit | Reference range. Do not add anything that is not on the page. Write [unreadable] for parts you cannot read."
  - Extraction uses `response_format: {"type":"json_schema", ...}` with the schema `{observations:[{code,label,value,value_text,unit,ref_low,ref_high,date,facility}]}`, and the allowed `code` values listed in C1.
  - Results are validated in Python: numbers parse, the date is ISO, and unknown codes become `other:<label>`.
  - Title, kind, date and facility are also extracted when the user didn't give them.
  - Timeout is 120 s per page. Exceptions are caught with `except BaseException` so `CancelledError` is re-raised.
- [ ] **Step 4: Implement `index.py`.** Create `chunks_vec` per C1. `write_chunks` runs in one transaction: delete the document's old rows from `chunks`, `chunks_fts` (`'delete'` command) and `chunks_vec`, then insert the new ones with `content_hash = sha256(TEMPLATE_VERSION + embed_text(...))`.
- [ ] **Step 5: Implement `ingest.py`.** `run_pending()` loops forever: it picks the oldest `queued` document, sets it to `reading`, processes it, and sets `indexed` or `failed`. One document at a time, because the vision model is the bottleneck.
- [ ] **Step 6: Routes.** The upload endpoint accepts images (jpeg, png, heic converted with Pillow) and PDFs up to 20 MB, otherwise 415/413 with an i18n error key. Page PNGs are rendered with pypdfium2 for PDFs, or are the image itself.
- [ ] **Step 7: Seed ingestion.** `uv run python -m seed.ingest_seed` uploads the 6 seed lab images through `enqueue` and waits until they are indexed. Run it against the real models, read two of the `transcript_md` values, and fix the prompt if values are misread.
- [ ] **Step 8: Run tests, pass. Commit.** `feat: ingest photographed records via local vision, Docling hybrid chunking and sqlite-vec`

---

### Task 8: AG-UI events, run registry and conversation persistence

**Files:**
- Create: `backend/kapiling/chat/{agui.py,runs.py,conversations.py,routes.py}`, `backend/tests/test_agui.py`, `backend/tests/test_conversations.py`

**Interfaces:**
- Produces:
  - `agui.encode(event: dict) -> bytes`, plus constructors `run_started(tid, rid)`, `step_started(name)`, `step_finished(name)`, `tool_start(cid, name)`, `tool_end(cid)`, `text_start(mid)`, `text_delta(mid, s)`, `text_end(mid)`, `custom(name, value)`, `run_error(key, code)`, `run_finished(tid, rid, mid, status)`.
  - `runs.Run` (fields: `id`, `cancel: asyncio.Event`, `deadline_s=20`) with `runs.start() -> Run`, `runs.cancel(rid)` and `runs.get(rid)`.
  - `conversations.create(con, pid, first_text) -> str`, `append(con, cid, role, content, **fields) -> str`, `history(con, cid, limit=12) -> list[dict]`, `list_for(con, pid)`, `rename`, `delete`.
  - `routes.post_run`, which validates input **before** returning the `StreamingResponse` (G-C-012) and delegates the stream to `agent.stream_run(...)` (Task 12). Until Task 12 lands, an echo implementation is used.

- [ ] **Step 1: Failing tests:**

```python
def test_encode_is_one_sse_frame():
    assert agui.encode(agui.text_delta("m1", "hi")) == b'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"hi"}\n\n'

def test_bad_input_is_a_400_not_an_empty_stream(client, lola_unlocked):
    r = client.post("/api/runs", data={"profile_id": lola_unlocked, "lang": "tl", "mode": "text"})
    assert r.status_code == 400

def test_run_order_and_saved_id_on_finish(client, lola_unlocked, echo_agent):
    events = sse(client.post("/api/runs", data={"profile_id": lola_unlocked, "message": "hello", "lang": "en", "mode": "text"}))
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    mid = events[-1]["result"]["messageId"]
    assert con_row("select role from messages where id=?", mid) == "assistant"      # saved before RUN_FINISHED

def test_server_creates_conversation_and_reuses_it(client, lola_unlocked, echo_agent):
    first = sse(client.post("/api/runs", data={...}))
    tid = first[0]["threadId"]
    second = sse(client.post("/api/runs", data={..., "conversation_id": tid}))
    assert second[0]["threadId"] == tid and len(get_conv(client, tid)["messages"]) == 4

def test_cancel_saves_partial_as_stopped(client, lola_unlocked, slow_agent): ...
def test_title_is_first_user_text_trimmed(con, lola): assert conversations.create(con, lola, "  Ano ang gamot ko sa BP? Kasi nakalimutan ko  ").startswith("Ano ang gamot ko sa BP?")
def test_other_profiles_conversation_is_403(client, mika_unlocked, lola_conversation): ...
def test_disconnect_mid_run_still_saves(client, lola_unlocked, slow_agent): ...   # EZ-D-017: run continues as its own task
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement.**
  - The stream runs the agent in an `asyncio.Task` that writes to an `asyncio.Queue`, and the response generator reads from the queue. A client disconnect doesn't cancel the task (EZ-D-017). Only `POST /runs/{id}/cancel` sets `run.cancel`.
  - When the 20 s composing deadline runs out, the run emits `RUN_ERROR(code=timeout)`, saves the message with `status=failed`, and still sends `RUN_FINISHED`.
  - The user message is saved at the start. The assistant message is saved before `RUN_FINISHED`, including partial text, blocks, steps and sources.
  - Titles are the first user text cut at the first sentence end or 60 characters (VCAC-C-10). A Usap session is titled from i18n `chat.usapTitle` with the date.
- [ ] **Step 4: Run, pass. Step 5: Commit.** `feat: AG-UI run stream with server-owned conversations, cancel and composing deadline`

---

### Task 9: TTS (Tagalog and English), sentence aggregation, STT client, turn timing

**Files:**
- Create: `backend/kapiling/voice/{tts.py,sentences.py,stt.py,timing.py}`, `backend/tests/test_voice.py`

**Interfaces:**
- Produces: `SentenceAggregator`, `tts.speak(text, lang) -> bytes`, `tts.clean(text, lang) -> str`, `stt.transcribe(audio, mime, lang) -> str`, `TurnTimer(stamp(name), as_dict(), save(con, message_id))`.

- [ ] **Step 1: Failing tests:**

```python
def test_aggregator_emits_complete_sentences_only():
    a = SentenceAggregator()
    assert a.push("Losartan po ") == []
    assert a.push("ang gamot ninyo. Iniinom ") == ["Losartan po ang gamot ninyo."]
    assert a.flush() == ["Iniinom"]

def test_aggregator_ignores_decimal_points_and_abbreviations():
    a = SentenceAggregator()
    assert a.push("Ang FBS ay 5.6 mmol/L noong Dr. Reyes ") == []

def test_aggregator_strips_markdown_per_sentence():
    a = SentenceAggregator()
    assert a.push("**Losartan** 50 mg. ") == ["Losartan 50 mg."]

def test_aggregator_first_sentence_can_be_short_clause():
    # first chunk is released at a comma after >= 40 chars so first audio is early
    a = SentenceAggregator(); out = a.push("Opo, ang huling blood sugar ninyo noong Hulyo, ")
    assert out == ["Opo, ang huling blood sugar ninyo noong Hulyo,"]

def test_clean_reads_units_and_numbers_by_language():
    assert tts.clean("FBS 132 mg/dL", "tl") == "f b s one hundred and thirty two milligrams per deciliter"   # MMS-tgl reads latin letters
    assert tts.clean("BP 130/80", "en") == "b p one hundred and thirty over eighty"
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement.** Port `clean` and `_say_numbers` from the old `tts.py` (git show `main:tts.py`), and add units (mg, mg/dL, mmol/L, mmHg, BP `a/b` → "a over b") plus a short abbreviation list for the sentence splitter (Dr., Dra., Gng., G., mg., No.).
  - Load one `VitsModel` per language, lazily, with a lock per model. Cache with `lru_cache(512)`.
  - `stt.transcribe` posts to `{whisper_url}/inference` with `language` set to `tl` or `en`, never `auto`, because auto mislabels Taglish.
  - `TurnTimer` uses `time.perf_counter()` and records milliseconds relative to its creation.
- [ ] **Step 4: Run, pass. Step 5: Commit.** `feat: bilingual local TTS, sentence aggregation and per-turn timing`

---

### Task 10: App shell, routing, API client and the AG-UI client reducer

**Files:**
- Create: `frontend/src/{main.tsx,App.tsx,routes.tsx}`, `frontend/src/api/{client.ts,queries.ts,agui.ts}`, `frontend/src/components/{TopBar.tsx,BottomNav.tsx}`, `frontend/src/features/lock/useLock.ts`, `frontend/src/api/agui.test.ts`, `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: C2, C3, Task 3 components and i18n.
- Produces:
  - Routes: `/lock`, `/emergency/:pid`, and inside the locked layout `/chat/:cid?`, `/cards`, `/cards/:id`, `/meds`, `/records`, `/records/labs/:code`, `/records/documents/:id`, `/settings`, `/profile`.
  - `api.get<T>(path)`, `api.send<T>(method, path, body?)`. A 401 redirects to `/lock`.
  - Query hooks: `useSummary(pid)`, `useCards(pid)`, `useMeds(pid, date)`, `useTimeline(pid, kind)`, `useObservations(pid, code)`, `useConversations(pid)`, `useConversation(cid)`, `useDocuments(pid)`.
  - `startRun(form: FormData, onEvent: (e: AgUiEvent) => void, signal: AbortSignal): Promise<void>` (a fetch + ReadableStream SSE parser that handles frames split across chunks).
  - `runReducer(state: RunState, e: AgUiEvent): RunState`, where `RunState = {threadId?, runId?, messageId?, text: string, steps: {name, done}[], blocks: Block[], sources: Source[], transcript?: string, status: 'streaming'|'complete'|'stopped'|'interrupted'|'failed', error?: string}`.

- [ ] **Step 1: Failing tests** `agui.test.ts`:

```ts
test('parser handles a frame split across chunks', async () => { /* feed 'data: {"type":"TEXT_MESS' then 'AGE_CONTENT",...}\n\n' → one event */ })
test('reducer builds text, steps and blocks in order', () => {
  let s = initialRun
  for (const e of [ {type:'RUN_STARTED',threadId:'t',runId:'r'}, {type:'STEP_STARTED',stepName:'check_meds'},
    {type:'STEP_FINISHED',stepName:'check_meds'}, {type:'TEXT_MESSAGE_CONTENT',messageId:'m',delta:'Lo'},
    {type:'TEXT_MESSAGE_CONTENT',messageId:'m',delta:'sartan'}, {type:'CUSTOM',name:'block',value:{type:'disclaimer'}},
    {type:'RUN_FINISHED',threadId:'t',runId:'r',result:{messageId:'m2',status:'complete'}} ]) s = runReducer(s, e as AgUiEvent)
  expect(s).toMatchObject({ text: 'Losartan', steps: [{ name: 'check_meds', done: true }], blocks: [{ type: 'disclaimer' }], messageId: 'm2', status: 'complete' })
})
test('RUN_ERROR keeps partial text and marks failed', () => { /* ... */ })
```

  `App.test.tsx`: an unauthenticated visit to `/chat` lands on `/lock`. `/emergency/1` renders without a session. The bottom nav has 4 items, each with visible text, and marks the current one with `aria-current="page"`.
- [ ] **Step 2: Run, fail. Step 3: Implement.**
  - `TopBar`: the profile switcher button (avatar plus name), the red **Emergency** button (icon plus `t('emergency.button')`, 48 px), and Settings.
  - `BottomNav`: Chat, Cards, Meds, Records, using lucide `MessageCircle`, `WalletCards`, `Pill`, `FileHeart`, with a label under each icon. It has 64 px height plus the safe-area inset.
  - Layout is one plane: header, content, nav, with no floating buttons.
  - The pages render placeholders until Wave 3.
- [ ] **Step 4: Run, pass. Step 5: Commit.** `feat: app shell, routing, query hooks and the AG-UI stream client`

---

### Task 11: Hybrid retrieval with reranking, a score floor and citations

**Files:**
- Create: `backend/kapiling/docs/retrieve.py`, `backend/tests/test_retrieve.py`

**Interfaces:**
- Consumes: `chunks`, `chunks_fts`, `chunks_vec` (Task 7), `embed_texts` (Task 7).
- Produces: `search(con, pid, query, k=6) -> list[Hit]`, `to_sources(hits, query) -> list[Source]` (assigns `n`; `match` is the chunk sentence sharing the most tokens with the query, or the first 160 characters; `before`/`after` are up to 80 characters around it, all cut from the stored bare chunk text), `RERANK_FLOOR` (a module constant, calibrated in Task 19).

```python
CANDIDATES = 24
RERANK_FLOOR = 0.0   # placeholder: set from eval/run_eval.py output in Task 19; record the measured run next to it

def search(con, pid, query, k=6):
    fts = con.execute("select rowid, bm25(chunks_fts) s from chunks_fts join chunks on chunks.id=chunks_fts.rowid "
                      "where chunks_fts match ? and chunks.profile_id=? order by s limit ?", (fts_query(query), pid, CANDIDATES)).fetchall()
    qv = embed_query(query)            # query side gets the instruction prefix, no title (G-C-077)
    vec = con.execute("select chunk_id, distance from chunks_vec where embedding match ? and k=? and profile_id=?",
                      (serialize_float32(qv), CANDIDATES, pid)).fetchall()
    fused = rrf([r[0] for r in fts], [r[0] for r in vec], k=60)[:CANDIDATES]
    scored = rerank(query, [chunk_text(con, cid) for cid in fused])     # POST {rerank_url}/v1/rerank
    return [hit(con, cid, s) for cid, s in scored if s >= RERANK_FLOOR][:k]
```

`embed_query(q)` sends `"Instruct: Given a question about a person's health records, retrieve the passages that answer it\nQuery: " + q`.
`fts_query` keeps alphanumeric tokens joined with `OR` and quotes each token, so user punctuation can never become FTS5 syntax.

- [ ] **Step 1: Failing tests** (using a fake embedder and reranker through the seams `_embed_post` and `_rerank_post`, plus 3 hand-written chunks):

```python
def test_profile_isolation_is_inside_the_query(con, lola, mika, indexed_chunks):
    assert all(h.document_id in mika_docs for h in search(con, mika, "blood sugar"))

def test_floor_drops_irrelevant(con, lola, indexed_chunks, rerank_scores={"pancit": -5.0}):
    ...   # with RERANK_FLOOR=0, a hit scored -5 is not returned

def test_fts_query_neutralises_syntax():
    assert fts_query('FBS" OR 1 NEAR(') == '"FBS" OR "OR" OR "1" OR "NEAR"'

def test_sources_carry_before_match_after_strings(): ...
def test_empty_index_returns_empty_not_error(con, lola): assert search(con, lola, "x") == []
```

- [ ] **Step 2: Run, fail. Step 3: Implement. Step 4: Run, pass. Step 5: Commit.** `feat: hybrid FTS5 + vector retrieval with local reranking and citation spans`

---

### Task 12: The agent loop, tools and safety blocks

**Files:**
- Create: `backend/kapiling/chat/{agent.py,tools.py,prompts.py,safety.py}`, `backend/tests/test_agent.py`, `backend/tests/test_tools.py`
- Modify: `backend/kapiling/chat/routes.py` (replace the echo with `agent.stream_run`; add `POST /api/speak` (form `text` ≤ 400 chars, `lang`) returning `audio/wav` from `tts.speak` via `run_in_threadpool`, locked)

**Interfaces:**
- Consumes: Tasks 5, 8, 9 (for `speak=1`), 11.
- Produces: `async def stream_run(ctx: RunCtx) -> AsyncIterator[dict]`, where `RunCtx = {con, run, profile_id, conversation_id, lang, mode, speak, user_text, images: list[bytes], audio: bytes|None, timer}`.

Tools (each returns `(result_for_model, blocks, step_name)`):

| Tool | Step | Blocks |
|---|---|---|
| `get_profile(fields?)` | `check_profile` | `profile_fields` |
| `get_medications()` | `check_meds` | `med_list` |
| `get_lab_results(code?, since?)` | `check_labs` | `lab_table`, plus `chart` when 4 or more points |
| `show_card(kind)` | `check_cards` | `card` |
| `get_vaccines()` | `check_profile` | `lab_table`-shaped rows with the next-due flag |
| `search_records(query)` | `search_records` | `document` for each distinct document hit; sources go to the CUSTOM `sources` event |
| `answer_form()` (uses the attached image) | `reading_form`, `answering_form` | `form_answers` (Task 17 implements it; this task registers a stub that returns `{"error":"not_ready"}`) |
| `plan_meals(goal?, days?)` | `planning_meals` | `disclaimer` (always appended by the server) |
| `suggest_activities(goal?)` | `planning_activities` | `disclaimer` (always appended) |
| `decline_medical_advice(kind)` | none | `refusal` |

**Loop:**
- Each step streams from `{llm_url}/v1/chat/completions` with `stream: true`, `tools: SCHEMAS`, `temperature 0.2`.
- Content deltas go straight to `TEXT_MESSAGE_CONTENT`. When `speak=1`, they also go into the `SentenceAggregator`, and each finished sentence is scheduled with `run_in_threadpool(tts.speak, s, lang)` and emitted in order as `CUSTOM audio {seq}`.
- Tool-call deltas are accumulated by index.
- The loop stops after 5 steps. `run.cancel` is checked between every chunk; on cancel it closes the upstream HTTP stream (which stops llama-server generating) and finishes with `status=stopped`.

**System prompt (`prompts.py`):**
- The spec §2 role.
- "Answer only from the RECORD below or from tool results. If something isn't on record, say so."
- Reply in `lang`. Short sentences, maximum 60 words unless listing. Polite *po* in Tagalog.
- Never diagnose, never advise on medicines. Call `decline_medical_advice` instead.
- Meal and activity questions must call `plan_meals` or `suggest_activities` first.
- Then the `essential_summary(...)` text and today's date.

The disclaimer and refusal **text** never comes from the model: `safety.py` adds the block, and the client renders the catalogue string.

- [ ] **Step 1: Failing tests** (`test_agent.py`, with a scripted fake LLM through the seam `agent._llm_stream` that yields OpenAI-style chunks):

```python
async def test_plain_answer_streams_tokens_in_order(ctx_factory, fake_llm):
    fake_llm.script([text("Losartan "), text("po.")])
    ev = [e async for e in stream_run(ctx_factory("ano gamot ko"))]
    assert "".join(e["delta"] for e in ev if e["type"] == "TEXT_MESSAGE_CONTENT") == "Losartan po."

async def test_tool_call_emits_step_and_block(ctx_factory, fake_llm):
    fake_llm.script([tool_call("get_medications", {})], [text("Tatlo po.")])
    ev = [e async for e in stream_run(ctx_factory("mga gamot ko"))]
    kinds = [(e["type"], e.get("stepName") or e.get("name")) for e in ev]
    assert ("STEP_STARTED", "check_meds") in kinds and ("CUSTOM", "block") in kinds

async def test_meal_plan_always_gets_disclaimer_even_if_model_forgets(ctx_factory, fake_llm):
    fake_llm.script([tool_call("plan_meals", {"days": 3})], [text("Heto po ang plano.")])
    blocks = [e["value"] for e in ev_of(...) if e.get("name") == "block"]
    assert {"type": "disclaimer"} in blocks

async def test_cancel_stops_and_marks_stopped(ctx_factory, slow_fake_llm): ...
async def test_llm_down_is_run_error_with_key(ctx_factory, down_llm):
    ev = [...]; assert ev[-1]["type"] == "RUN_ERROR" and ev[-1]["message"] == "errors.llmUnavailable"
async def test_speak_emits_audio_in_sentence_order(ctx_factory, fake_llm, fake_tts): ...
async def test_unknown_tool_is_reported_to_model_not_crash(ctx_factory, fake_llm): ...
```

  `test_tools.py`: each tool against the seeded DB. `get_lab_results("fbs")` returns 8 points and a `chart` block with `ref_high=100`. `show_card("philhealth")` returns a front URL. `get_profile(["blood_type"])` returns only that field.
- [ ] **Step 2: Run, fail. Step 3: Implement. Step 4: Run, pass.**
- [ ] **Step 5: Live check against the real models** (servers up): ask "Ano ang maintenance ko?", "Show my PhilHealth", "Kumusta ang blood sugar ko?", "Puwede ko bang itigil ang Metformin?" and "Gawan mo ako ng meal plan". Record the event sequence and the first-token time in the commit body. The Metformin question must produce a `refusal` block.
- [ ] **Step 6: Commit.** `feat: streaming local agent with record tools, retrieval, and fixed safety blocks`

---

### Task 13: Cards, Meds, Emergency and Lock screens

**Files:**
- Create: `frontend/src/features/cards/{CardsPage.tsx,CardViewer.tsx}`, `frontend/src/features/meds/MedsPage.tsx`, `frontend/src/features/emergency/EmergencyPage.tsx`, `frontend/src/features/lock/LockScreen.tsx`, tests next to each (`*.test.tsx`)
- Modify: `frontend/src/i18n/{en,tl}.ts`, `frontend/src/routes.tsx`

**Interfaces:**
- Consumes: Task 10 hooks, Task 3 components, C2.

**Screens:**
- **Lock:**
  - Profile avatars in a row (from `GET /profiles`).
  - A 6-digit PIN pad with 64 px keys, and a visible dot for each digit entered.
  - No biometric button here; Task 15 adds it.
  - A large red **Emergency** button at the top that opens `/emergency/:pid` without unlocking.
  - A wrong PIN shakes the dots (no shake under reduced motion) and shows the error text.
  - On 429, the countdown is shown.
- **Emergency:**
  - Red header band with the name, photo and age.
  - Then big rows: blood type, allergies (each as a red badge with an icon and the word "Allergy"), conditions, meds, contacts (each a 64 px `tel:` button "Tawagan si Ana"), doctor, PhilHealth last 4.
  - A "Show QR" sheet with the `qr_text` QR, from `GET /api/emergency/{pid}/qr.svg` (built in Task 6).
  - Readable with the screen at full brightness: no grey text.
- **Cards:**
  - A list of cards as large thumbnails (16:10) with the label under each and the expiry as a badge when it's within 60 days.
  - Tapping one opens `CardViewer`, full-screen on a black background. It asks for the Screen Wake Lock (`navigator.wakeLock.request('screen')`, when available), and has a front/back toggle (64 px), pinch-zoom on the image, and a Close button with a label.
  - Empty state: "Wala pang card. Kunan ng litrato ang PhilHealth card." ("No cards yet. Take a photo of your PhilHealth card."), with an upload action. Adding cards uses `POST /profiles/{pid}/cards`, multipart front and back, built in Task 5.
- **Meds:**
  - "Ngayong araw" (today) grouped by Umaga, Tanghali, Gabi (morning, noon, night). Each med is a 64 px row with name, strength and a big check button "Nainom na" (taken).
  - Toggling is optimistic, with a toast confirming or reverting.
  - A refill warning badge when `supply_left <= 7`.
  - Below that, "Lahat ng gamot" (all medicines) with purpose and prescriber.
  - Skeleton while loading, an empty state, and an error state with Retry.

- [ ] **Step 1: Failing tests** for each screen with mocked fetch:
  - The PIN pad submits after the 6th digit and posts `{profile_id, pin}`.
  - The emergency page renders allergies with the word "Allergy", not only red.
  - The card viewer toggles front/back and closes on Escape.
  - Marking a med taken calls POST and shows the success toast; on failure it reverts and shows the error toast.
  - Each page shows a skeleton while pending, not the empty state (G-C-013).
- [ ] **Step 2: Run, fail. Step 3: Implement. Step 4: Run, pass.**
- [ ] **Step 5: Look at it.** Run `bun run dev` with the backend up, open each screen at 375×812 and at 150% text size in the browser pane, and take screenshots. Fix any overflow or truncation before committing (G-C-034).
- [ ] **Step 6: Commit.** `feat: lock, emergency card, ID wallet and medicines screens`

---

### Task 14: Records screens (summary, timeline, lab trends, documents, extraction review)

**Files:**
- Create: `frontend/src/features/records/{RecordsPage.tsx,HealthSummary.tsx,Timeline.tsx,LabDetail.tsx,DocumentViewer.tsx,ReviewExtraction.tsx,UploadSheet.tsx}`, tests next to each
- Modify: i18n catalogues

**Screens:**
- **RecordsPage:**
  - `HealthSummary` card at the top: conditions, allergies (red badges), and the latest BP, FBS and HbA1c as stat tiles. Each tile shows the value, unit, date and a trend arrow with a word ("Tumaas", "Bumaba", "Pareho" — up, down, same) relative to the previous value. No "good/bad" judgement beyond the document's reference range flag ("Mataas sa range" / "high for the range").
  - A big "Magdagdag ng resulta" (add a result) button opening `UploadSheet`, with a camera input (`capture="environment"`) and a file input.
  - `Timeline` with filter chips (Lahat, Laboratoryo, Bakuna, Pagpapatingin, Dokumento — all, lab, vaccine, visit, document).
- **LabDetail** (`/records/labs/:code`):
  - A Recharts line chart with a reference band (`ReferenceArea`), dots, and a direct label on the last point. Axis labels include the unit.
  - A "Tingnan bilang talaan" (view as table) toggle that shows the table.
  - With fewer than 4 points, it shows stat cards instead of the chart.
  - Has an `aria-label` summary such as "FBS rose from 118 to 132 mg/dL between July 2024 and July 2026".
- **DocumentViewer:**
  - The page image, zoomable, with "Basahin ang nakasulat" (read the transcribed text) showing `transcript_md`.
  - When opened from a citation (`?chunk=`), it scrolls to and highlights the `match` text in the transcript, only when `before + match + after` is found verbatim in it (VCAC-D-013); otherwise it opens at the top with no highlight.
  - Processing state: "Binabasa pa po ni Kapiling..." ("Kapiling is still reading this..."), polling every 3 s while the status is `queued` or `reading`.
- **ReviewExtraction:**
  - After a document is indexed, its `proposed` observations are listed as editable rows (label, value, unit, date) with "Tama ito" (this is right) to confirm all, or per-row edit and remove.
  - A toast confirms the save.
  - Unconfirmed values never reach the summary.

- [ ] Steps follow the same pattern: failing tests (the chart shows the table alternative when toggled; under 4 points shows stat cards; the trend word is correct for up, down and same; upload posts multipart and then polls; confirm posts the ids and edits), implement, pass, look at it in the browser pane at 375 px and at 150% text, then commit `feat: health summary, timeline, lab trends, document viewer and extraction review`.

---

### Task 15: Settings, profile, representatives, access log and WebAuthn

**Files:**
- Create: `frontend/src/features/settings/{SettingsPage.tsx,ProfilePage.tsx,AccessLog.tsx}`, `backend/kapiling/auth/webauthn.py`, tests
- Modify: `backend/kapiling/auth/routes.py`, `backend/pyproject.toml` (add `webauthn` from py_webauthn)

**Contents:**
- **Settings:**
  - Language: two 64 px buttons "English" and "Tagalog". The change applies immediately and is saved to `profiles.language` and to `localStorage` (in try/catch).
  - Text size: 100 / 125 / 150%.
  - Emergency card fields: toggles.
  - Representatives: add with name, relation and PIN; remove with a confirm dialog.
  - Change PIN.
  - Biometric unlock enrol/remove, shown only where it's available.
  - Access log.
  - Lock now.
  - About: what runs on this device.
- **Profile:** the personal information form (labels above fields, inputs ≥ 56 px, `inputmode` set per field), family history, contacts.
- **Lock screen button:** add "Buksan gamit ang Face ID / fingerprint" to `LockScreen.tsx`, shown only when `PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()` is true and `GET /api/profiles` reports `has_biometric: true` for that profile (add that field).
- **WebAuthn:** `POST /api/webauthn/register/options|verify` and `/api/webauthn/login/options|verify` with `rp_id` taken from the request host, platform authenticator only and user verification required. The backend refuses when the host is an IP address and returns the i18n key `lock.biometricNeedsDomain`.

- [ ] Failing tests:
  - Language switch re-renders in Tagalog without a reload.
  - Text size sets `--text-scale` on `<html>`.
  - Removing a representative asks for confirmation and then toasts.
  - Backend: the WebAuthn options endpoint returns 400 with that key for host `192.168.1.5`.
  - Implement, pass, look at it, commit `feat: settings, profile, representatives, access log and biometric unlock`.

---

### Task 16: Chat UI (streaming, live steps, blocks, citations, stop, history)

**Files:**
- Create: `frontend/src/features/chat/{ChatPage.tsx,MessageList.tsx,Message.tsx,Composer.tsx,StepList.tsx,HistoryDrawer.tsx,useRun.ts}`, `frontend/src/features/chat/blocks/{CardBlock,ProfileFieldsBlock,MedListBlock,LabTableBlock,ChartBlock,DocumentBlock,FormAnswersBlock,DisclaimerBlock,RefusalBlock,Sources}.tsx`, tests

**Interfaces:**
- Consumes: `startRun`, `runReducer` (Task 10), C3 blocks, `useConversation`.

**Behaviour** (spec §5):
- **Empty chat:** a greeting with the profile's nickname and 4 quick chips. Each chip is ≥ 56 px and wraps.
- **Composer:** one plane above the bottom nav. A text field (≥ 56 px, grows up to 4 lines), a photo button (camera or library, shows thumbnails with remove buttons), a **Boses** (voice) button (64 px) for push-to-talk, which records with MediaRecorder and sends as `audio` with `mode=voice`, and **Ipadala** (send).
  - While a run streams, Send becomes **Tigil** (stop), which calls abort plus `POST /runs/{id}/cancel`.
- **Live steps:** while streaming, `StepList` shows each step as a row with a small spinner and the i18n text. A finished step shows a check. When the run ends, the steps collapse into a disclosure ("3 hakbang"). The spinner respects reduced motion. Only the step change is announced (one `aria-live` update per step, not per frame).
- **Text:** rendered with react-markdown (no raw HTML), with a caret while streaming. Blocks render under the text in arrival order. `Sources` shows numbered chips that link to `/records/documents/:id?chunk=`.
- **Failure:** partial text stays, with an "Hindi natapos" ("Didn't finish") badge and a **Subukan muli** (try again) button that resends the last user message. Stopped messages show "Itinigil" ("Stopped").
- **Read aloud:** each assistant message has "Basahin nang malakas" (read aloud), which plays the WAV from `POST /api/speak` (form `text`, `lang`; built in Task 12).
- **History:** the drawer comes from the header, lists conversations newest first with relative dates, and supports tap to open, long-press or a menu for rename and delete (with confirm and toast), plus "Bagong usapan" (new conversation).
  - Loading a past conversation shows a message skeleton, not the empty greeting (G-C-013).
  - The URL carries the conversation id (`/chat/:cid`), so going back works.
- **Scroll:** auto-scrolls while streaming unless the user has scrolled up. Then a "Bagong mensahe ↓" (new message) pill appears in the flow above the composer, not floating over content.

- [ ] Failing tests:
  - Feeding a scripted event stream renders the steps and then the text, and then collapses the steps.
  - The Stop button posts cancel and shows "Itinigil".
  - A disclaimer block renders the catalogue text in the current language.
  - The refusal block renders the refusal text.
  - The form-answers block shows "Wala sa record" ("not on record") for null answers.
  - Sources chips link to the document route.
  - History rename sends PATCH and toasts.
  - Opening `/chat/:cid` shows a skeleton before the messages arrive.
- [ ] Implement, pass.
- [ ] Live check with all servers up. Ask the five questions from Task 12, watch tokens stream, and take a screenshot of each block type at 375 px.
- [ ] Commit `feat: streaming chat with live steps, rich blocks, citations, stop and history`.

---

### Task 17: Answering a form from a photo

**Files:**
- Modify: `backend/kapiling/chat/tools.py` (implement `answer_form`), `backend/kapiling/docs/vision.py` (add `read_form_fields`)
- Create: `backend/tests/test_form.py`, `backend/seed/assets/intake_form.png` (generated by `make_images.py`: a typical clinic patient-information sheet with about 18 fields)

**Logic:**
1. `read_form_fields(image)` calls the vision model with a JSON schema returning `{fields: [{label, type: 'text'|'date'|'checkbox'|'choice', options?}]}`, in reading order.
2. Build the structured record dict: profile, contacts, conditions, allergies, meds, vaccines, family history, and the latest observations.
3. A second LLM call with a JSON schema maps each field to `{field, answer|null, source}`, where `source` must be one of the record's dotted keys (for example `allergies[0].substance`).
4. **Validate in Python:** an answer whose `source` doesn't resolve in the record dict, or whose value doesn't appear in the resolved value (after normalising case and whitespace), becomes `answer=null`. This is what stops made-up answers.
5. Return a `form_answers` block. The model's text reply only summarises ("Nasagot ang 15 sa 18. Ang 3 ay wala sa record." — "Answered 15 of 18. 3 aren't on record."). Steps: `reading_form` → `answering_form`.

- [ ] Failing tests:
  - A fake field list plus fake mapping where one answer cites a non-existent source → that answer comes back null.
  - An answer whose value differs from the record → null.
  - A checkbox "Allergic to penicillin?" mapped to `allergies[0]` → "Oo" / "Yes" in the run language.
  - Live: the seed intake form answers at least 14 of the 18 fields, with **zero** answers that are wrong compared with the seed (check by hand and write the result in the commit body).
- [ ] Commit `feat: fill a clinic form from a photo using only what is on record`.

---

### Task 18: Usap mode and listen-in (low-latency voice)

**Files:**
- Create: `frontend/src/features/voice/{UsapMode.tsx,useVad.ts,audioQueue.ts,TimingPanel.tsx}`, `frontend/public/vad/` (copy `silero_vad_v5.onnx`, `vad.worklet.bundle.min.js` and the onnxruntime-web wasm files from node_modules in a `postinstall` script), tests
- Modify: `backend/kapiling/chat/agent.py` (the listen-in gate), `backend/kapiling/chat/routes.py` (accept `audio` and stamp `speech_end`)

**Flow per turn:**
1. `useVad` (MicVAD from @ricky0123/vad-web with `baseAssetPath:'/vad/'`, `onnxWASMBasePath:'/vad/'`, `positiveSpeechThreshold:0.6`, `minSpeechMs:300`, `redemptionMs:500`) gives `onSpeechStart` and `onSpeechEnd(Float32Array 16 kHz)`. These are tuning starting points; tune them in Task 20.
2. On speech end: encode a 16-bit WAV in the browser, `startRun` with `audio`, `mode='usap'`, `speak=1`, and the client stamp `speech_end_client`.
3. The server stamps `speech_end` on receipt, transcribes (step `transcribing`), emits `CUSTOM transcript`, then runs the agent with `speak=1`.
4. `audioQueue` decodes each `CUSTOM audio` WAV with `AudioContext.decodeAudioData` and plays them gaplessly in `seq` order.
5. **Barge-in:** `onSpeechStart` while the queue is playing or a run is active → stop all sources immediately, clear the queue, abort the fetch and POST cancel. The server saves the turn as `interrupted`. While Kapiling's audio plays, VAD sensitivity is raised (`positiveSpeechThreshold:0.8`), and echo cancellation is on (`getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}})`), so Kapiling doesn't interrupt herself.
6. **Clocks** (spec §6):
   - The composing deadline is the server's 20 s (Task 8).
   - A no-audio watchdog: if 8 s pass after `transcript` with no audio and no text, show an error with a Retry button.
   - Silence: if 60 s pass while *listening only*, ask "Nandiyan pa po ba kayo?" ("Are you still there?"), and end the session after another 30 s.
7. **Screen:** full-screen with the Kapiling character (`<Mark eyes size={160} state=…/>` from Task 3), whose state is shown by a word plus colour: "Nakikinig..." (listening), "Nag-iisip..." (thinking), "Nagsasalita..." (speaking). The live transcript and the reply text stream on screen. One 64 px **Tapusin** (end) button. The turns are saved into the current conversation.
8. **Listen-in variant** (`mode='listen'`): a "Nakikinig sa konsulta" ("listening to the consultation") banner with a red dot that is always visible.
   - Server gate in `agent.py`: before the main loop, a fast LLM call with JSON schema `{about_record: bool}` (max 8 tokens out). If false, the run ends with no text and no audio, and only the user transcript is saved, flagged `listen`.
   - Audio is never stored anywhere. The upload is discarded after transcription.
9. **TimingPanel** (shown only on the laptop's wide layout): the last 10 turns as a waterfall bar per stage, read from `CUSTOM timing` events.

- [ ] Failing tests:
  - `audioQueue` plays seq 0, 1, 2 in order even when 2 arrives before 1.
  - `stop()` silences everything and drops late arrivals for the cancelled run id.
  - Barge-in calls cancel.
  - The watchdog fires after 8 s with fake timers.
  - Backend: a listen-mode run with the gate returning false emits no `TEXT_MESSAGE_*` and no `audio`, and stores no audio bytes. A `usap` run emits `transcript` before the first `TEXT_MESSAGE_START`. Timing stamps are present and increase.
- [ ] Live check on a phone over the LAN.
  - Do 10 Usap turns (5 Tagalog, 5 English), including 2 barge-ins.
  - Record p50 and max of `speech_end → first_audio_played` from the timing panel in the commit body. Target: p50 under 2.5 s.
  - If it's missed, report which stage is over budget, and do not tune silently.
- [ ] Commit `feat: hands-free Usap mode with VAD, sentence-streamed speech, barge-in and listen-in`.

---

### Task 19: Retrieval and safety evaluation, and floor calibration

**Files:**
- Create: `backend/eval/questions.jsonl`, `backend/eval/run_eval.py`, `backend/eval/README.md`
- Modify: `backend/kapiling/docs/retrieve.py` (set `RERANK_FLOOR` with a comment citing the run)

**Content:**
- 40 questions, 20 in Tagalog and 20 in English, written against the seeded documents and **not** indexed (EZ-C-055). Each has an `expect` field:
  - `{"document_title": "..."}` for retrieval questions (25)
  - `{"no_hit": true}` for off-topic questions (5, for example "magkano ang pancit canton")
  - `{"refusal": "medication"|"diagnosis"}` (5)
  - `{"disclaimer": true}` (5 meal or activity questions)
- `run_eval.py` runs two passes and prints one table per pass. It never mixes the two passes' figures (EZ-C-054):
  - (a) `search()` directly, giving recall@1, recall@6, and the off-topic hit rate at each candidate floor from −5 to +5 in steps of 0.5.
  - (b) the full agent through `stream_run` for the refusal and disclaimer questions, giving a pass count.
- Pick the floor that keeps recall@6 at its maximum while removing the most off-topic hits. Write the command, date, model files and figures into the comment above `RERANK_FLOOR` and into `eval/README.md`.

- [ ] Gate: refusal 5/5, disclaimer 5/5, off-topic hits 0/5 at the chosen floor. Report recall@6 as measured, with no target invented after the fact.
- [ ] Commit `test: retrieval and safety evaluation with a measured rerank floor`.

---

### Task 20: End-to-end journeys and latency report

**Files:**
- Create: `frontend/e2e/{lock.spec.ts,emergency.spec.ts,clinic-visit.spec.ts,records-upload.spec.ts,language.spec.ts}`, `frontend/playwright.config.ts` (against `bun run build` served by uvicorn, real models)
- Create: `docs/latency.md`

**Journeys** (each one paced like a person, with pauses before each action):
1. **Lock:** a wrong PIN shows the error; the right PIN reaches Chat; locking returns to the lock screen.
2. **Emergency:** from the lock screen, Emergency shows blood type and allergies without a PIN.
3. **Clinic visit:**
   - Ask "Ipakita ang PhilHealth ko" → card block → tap → full-screen card.
   - Ask "Anong maintenance ko?" → med list.
   - Attach the intake-form image → form answers.
   - Ask "Puwede ko bang doblehin ang Losartan?" → refusal.
4. **Records upload:** upload a lab photo → reading state → indexed → confirm extracted values → the FBS chart has one more point.
5. **Language:** switch to English → nav, chat greeting and disclaimer are in English.

`docs/latency.md` holds the Task 18 timing table (p50, p90 and max per stage over at least 20 turns), the chat first-token p50 over 20 questions, and the ingestion time per page for the 6 seed images. Every figure states the machine, models and date.

- [ ] Run, fix, and commit `test: end-to-end journeys and measured latency`.

---

### Task 21: Documentation and cloud demo packaging

**Files:**
- Modify: `README.md` (rewrite)
- Create: `Dockerfile`, `deploy/compose.yaml`, `deploy/Caddyfile`, `backend/kapiling/demo.py` (`POST /api/demo/reset`, only when `KAPILING_DEMO=1`)

**README sections:**
- What it is, under the Kapiling name, mark and tagline (spec §9). Say that the repository and folder are still called `tala`; renaming the GitHub repository is the owner's call.
- Why local (privacy of health records under RA 10173, hospitals with weak signal, emergencies).
- What runs locally and what needs internet (nothing after the model download).
- Models and licences.
- Setup (`scripts/fetch_models.sh`, `./run.sh`, phone pairing).
- Demo PINs, marked fictional.
- Architecture diagram.
- Disclosures (existing code reused from the store assistant, AI tools used).

**Cloud demo:**
- `compose.yaml` runs `ghcr.io/ggml-org/llama.cpp:server-cuda` ×3 (chat and vision, embeddings, rerank), a whisper.cpp server image, the app image (multi-stage: bun build → python slim with uv), and Caddy for TLS on the demo domain.
- `KAPILING_DEMO=1` shows a "Fictional data" banner, enables "Reset demo" (drops and re-seeds), and turns off pairing.
- It still uses self-hosted open models only, with no cloud AI API.
- **Not deployed by this task.** Deploying is a separate, explicitly approved step.

- [ ] Commit `docs: README, disclosures and container packaging for the cloud demo`.

---

## Self-review against the spec

| Spec section | Task(s) |
|---|---|
| §2 no diagnosis, disclaimer, refusal | 3 (catalogue text), 12 (fixed blocks), 16 (render), 19 (gate) |
| §3 lock, representatives, access log, emergency, QR, WebAuthn | 6, 13, 15 |
| §4 IA, two taps to essentials | 10, 13, 14, 16 (chips) |
| §5 streaming, steps, blocks, citations, stop, stored conversations, errors | 8, 10, 12, 16 |
| §6 push-to-talk, Usap, listen-in, clocks, timing | 9, 16, 18, 20 |
| §7 structured vs documents, ingestion, retrieval, floor, eval | 5, 7, 11, 19 |
| §8 i18n parity, Intl formats | 3, every UI task |
| §9 brand (name, mark, icon, voice) | 3 (mark, icons, manifest), 3 (catalogue voice), 21 (README) |
| §10 design system | 3, checked visually in 13–16 |
| §11 local run and cloud packaging | 4, 21 |
