import sqlite3
from collections.abc import Iterator

import sqlite_vec

from kapiling import config

# Schema C1 (documents is declared after the tables that reference it; SQLite allows forward REFERENCES).
_V1 = """
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
"""

# Migrations indexed by version: MIGRATIONS[0] takes user_version 0 -> 1.
MIGRATIONS: list[str] = [_V1]


def connect() -> sqlite3.Connection:
    settings = config.settings
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for v in range(version, len(MIGRATIONS)):
        con.executescript(MIGRATIONS[v])
        con.execute(f"PRAGMA user_version={v + 1}")
    con.commit()
    return con


def get_con() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, closed when the request ends (R17). A shared
    connection let one request's commit or rollback land in the middle of another's. connect() is cheap:
    migrations only run when user_version is behind. Work that outlives the request (a chat run) opens its
    own connection. check_same_thread=False because setup and teardown may run on different threadpool
    threads. Tests override this dependency."""
    con = connect()
    try:
        yield con
    finally:
        con.close()
