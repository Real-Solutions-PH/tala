# API reference

Generated from the route decorators in `backend/kapiling/**` (`@router.*` and `@app.*`). All paths are under `/api`; bodies are JSON unless noted.

**Public** means no PIN session is needed. **Locked** means a live session cookie (`kapiling_s`) is required (401 otherwise). Routes with `{pid}` also require the session's profile to match (403 otherwise); routes that look up an object by id check ownership in the handler. Separately, a client that is not on the laptop itself must also hold the pairing cookie, except for a short allow-list of paths (health, profile list, unlock, profile photo, emergency card and QR). See [security-and-privacy.md](security-and-privacy.md).

## Health and demo

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Whether llm, embed, rerank, whisper and tts are up |
| GET | `/api/demo` | Public | `{demo: bool}`; drives the "Fictional data" banner |
| POST | `/api/demo/reset` | Public, 404 unless `KAPILING_DEMO=1` | Wipe and reseed the demo data folder |

## Lock and sessions

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/unlock` | Public | `{profile_id, pin}`; 204 and session cookie, 401 wrong PIN, 429 after repeated failures |
| POST | `/api/lock` | Public | End the caller's session |
| GET | `/api/access-log` | Locked, owner only | Who unlocked or viewed what, newest first (500 rows) |
| GET | `/api/profiles/{pid}/settings` | Locked | Settings page data; representatives listed for the owner only |
| POST | `/api/profiles/{pid}/representatives` | Locked, owner only | Add a representative with a 6-digit PIN |
| DELETE | `/api/profiles/{pid}/representatives/{rid}` | Locked, owner only | Remove one and end their sessions |
| PUT | `/api/profiles/{pid}/pin` | Locked, owner only | Change the owner PIN (current PIN required) |

## Biometric (WebAuthn)

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/webauthn/register/options` | Locked, owner only | Start enrolment (current PIN required) |
| POST | `/api/webauthn/register/verify` | Locked, owner only | Finish enrolment |
| DELETE | `/api/webauthn/credentials` | Locked, owner only | Remove biometrics |
| POST | `/api/webauthn/login/options` | Public | Start biometric unlock |
| POST | `/api/webauthn/login/verify` | Public | Finish unlock; sets the session cookie |

## Profile, emergency and contacts

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/profiles` | Public | Id, nickname, name, photo URL for the lock screen |
| GET | `/api/profiles/{pid}/photo` | Public | Profile photo |
| GET | `/api/emergency/{pid}` | Public | Emergency card (only the fields the owner chose) |
| GET | `/api/emergency/{pid}/qr.svg` | Public | QR code holding the same text |
| PUT | `/api/profiles/{pid}/emergency-fields` | Locked | Choose which fields appear on the emergency card |
| GET | `/api/profiles/{pid}/summary` | Locked | Profile, conditions, allergies, medicines, latest results, contacts |
| GET | `/api/profiles/{pid}` | Locked | Profile fields |
| PUT | `/api/profiles/{pid}` | Locked | Update profile fields |
| GET | `/api/profiles/{pid}/family-history` | Locked | List family history |
| POST | `/api/profiles/{pid}/family-history` | Locked | Add an entry (201) |
| DELETE | `/api/profiles/{pid}/family-history/{fid}` | Locked | Remove an entry |
| POST | `/api/profiles/{pid}/contacts` | Locked | Add a contact or doctor (201) |
| DELETE | `/api/profiles/{pid}/contacts/{cid}` | Locked | Remove a contact |

## Cards, medicines, history

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/profiles/{pid}/cards` | Locked | Cards with masked numbers and image URLs |
| POST | `/api/profiles/{pid}/cards` | Locked | Add a card (multipart `kind`, `label`, `number?`, `front`, `back?`) |
| GET | `/api/files/{card_id}/{side}` | Locked | Card image (`front` or `back`); logged as a card view |
| GET | `/api/profiles/{pid}/meds` | Locked | Medicines and today's doses (`?date=`) |
| POST | `/api/profiles/{pid}/meds/{mid}/taken` | Locked | Mark a dose taken `{date, slot}` |
| DELETE | `/api/profiles/{pid}/meds/{mid}/taken` | Locked | Undo it |
| GET | `/api/profiles/{pid}/timeline` | Locked | Visits, labs, vaccines, documents (`?kind=`) |
| GET | `/api/profiles/{pid}/observations` | Locked | Lab and vital values, oldest first (`?code=`) |

## Documents

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/profiles/{pid}/documents` | Locked | List documents and their reading status |
| POST | `/api/profiles/{pid}/documents` | Locked | Upload a photo or PDF (multipart `file`, `title?`, `kind?`) |
| GET | `/api/documents/{doc_id}` | Locked | Metadata |
| GET | `/api/documents/{doc_id}/file` | Locked | The original file |
| GET | `/api/documents/{doc_id}/page/{n}.png` | Locked | A rendered page |
| POST | `/api/documents/{doc_id}/observations/confirm` | Locked | Confirm (and optionally edit) proposed values |
| DELETE | `/api/documents/{doc_id}/observations/{oid}` | Locked | Remove a proposed value |

## Chat and speech

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/profiles/{pid}/conversations` | Locked | List conversations |
| GET | `/api/conversations/{cid}` | Locked | One conversation with its messages |
| PATCH | `/api/conversations/{cid}` | Locked | Rename `{title}` |
| DELETE | `/api/conversations/{cid}` | Locked | Delete |
| POST | `/api/runs` | Locked | Start a run (multipart: `profile_id`, `lang` `en` or `tl`, `mode` `text`, `voice`, `usap` or `listen`, `message?`, `conversation_id?`, `speak` 0 or 1, `files[]?`, `audio?`); returns an SSE stream |
| POST | `/api/runs/{run_id}/cancel` | Locked | Stop a run |
| POST | `/api/speak` | Locked | Read text aloud (form `text` up to 400 characters, `lang`); returns `audio/wav` |

Any other path is served by the single-page app (deep links and reloads return `index.html`).

## AG-UI events (contract C3)

Each SSE frame is `data: <json>`. Types:

| Event | Fields |
|---|---|
| `RUN_STARTED` | `threadId` (conversation id), `runId` |
| `STEP_STARTED`, `STEP_FINISHED` | `stepName` |
| `TOOL_CALL_START` | `toolCallId`, `toolCallName` |
| `TOOL_CALL_END` | `toolCallId` |
| `TEXT_MESSAGE_START` | `messageId`, `role` |
| `TEXT_MESSAGE_CONTENT` | `messageId`, `delta` |
| `TEXT_MESSAGE_END` | `messageId` |
| `CUSTOM` `transcript` | `{text}` |
| `CUSTOM` `block` | one block (below) |
| `CUSTOM` `sources` | list of `{n, chunk_id, document_id, title, page, before, match, after}` |
| `CUSTOM` `audio` | `{seq, wav_b64}` |
| `CUSTOM` `timing` | stamps in milliseconds |
| `RUN_ERROR` | `message` (i18n key), `code`: `llm_unavailable`, `timeout`, `cancelled`, `bad_input`, `internal` |
| `RUN_FINISHED` | `threadId`, `runId`, `result: {messageId, status}` with status `complete`, `stopped`, `interrupted`, `failed` |

Step names: `reading_photo`, `transcribing`, `search_records`, `check_profile`, `check_meds`, `check_labs`, `check_cards`, `reading_form`, `answering_form`, `planning_meals`, `planning_activities`.

### Block types

| `type` | Contents |
|---|---|
| `card` | `card_id`, `label`, `front_url`, `back_url` |
| `profile_fields` | `fields[{key, value}]` |
| `med_list` | `meds[{name, strength, schedule, purpose}]` |
| `lab_table` | `rows[{label, value, unit, ref, date, flag}]` |
| `chart` | `code`, `label`, `unit`, `points[{date, value}]`, `ref_low`, `ref_high` |
| `document` | `document_id`, `title`, `date`, `thumb_url` |
| `form_answers` | `items[{field, answer, source}]`; `answer` null means not on record |
| `disclaimer` | none; text comes from the client catalogue |
| `refusal` | `kind`: `diagnosis` or `medication`; text comes from the client catalogue |

Tools the agent can call: `get_profile`, `get_medications`, `get_lab_results`, `show_card`, `get_vaccines`, `search_records`, `answer_form` (a stub that returns `not_ready`; the form filler is not yet wired in), `plan_meals`, `suggest_activities`, `decline_medical_advice`.
