"""Sidecar database for derived hygiene facts. Never writes to the library database.

Every derived row carries ``raw_sha`` (sha256 of the exact ``chunks.text`` it was computed from) and
``chunk_version``. A re-ingest changes both, so a stale row is *invalidated* rather than silently
reused against text it never saw.

Nothing here is written back into ``chunks``. That is what keeps the B0/B1 comparison a pure set
operation over eligibility, and what makes a future production schema an obvious migration rather
than a redesign.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDY_DIR = REPO / ".local" / "evidence-hygiene"
SIDECAR = STUDY_DIR / "hygiene.sqlite"

# The library under study. Read-only, always.
LIBRARY_DB = REPO / ".local" / "validation-summarize" / "validation.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS run_manifest (
  run_id TEXT PRIMARY KEY, git_sha TEXT, created_at TEXT, params_json TEXT, source_db TEXT
);

-- Level 1 of the text model: normalized text + alignment back to raw.
CREATE TABLE IF NOT EXISTS chunk_norm (
  chunk_id INTEGER, raw_sha TEXT, recipe_id TEXT,
  normalized_text TEXT,          -- NULL when the chunk holds an unresolved artifact
  variants_json TEXT,            -- bounded candidate set; ALWAYS populated
  align_rle_json TEXT,           -- [[norm_start, raw_start, length], ...]
  resolved INTEGER,              -- 0 when any occurrence stayed unresolved
  PRIMARY KEY (chunk_id, raw_sha, recipe_id)
);

CREATE TABLE IF NOT EXISTS chunk_geom (
  chunk_id INTEGER, raw_sha TEXT,
  n_spans INTEGER, n_lines INTEGER,
  x0 REAL, y0 REAL, x1 REAL, y1 REAL,
  width_ratio REAL, line_fill REAL, y_top_frac REAL, y_bot_frac REAL,
  mean_span_h REAL, grid_support INTEGER, col_index INTEGER,
  PRIMARY KEY (chunk_id, raw_sha)
);

CREATE TABLE IF NOT EXISTS chunk_shape (
  chunk_id INTEGER, raw_sha TEXT,
  n_words INTEGER, n_chars INTEGER,
  alpha_ratio REAL, digit_ratio REAL, punct_ratio REAL,
  terminal_punct INTEGER, caps_frac REAL, stop_frac REAL,
  biblio_score REAL, caption_match INTEGER, heading_prefix_key TEXT,
  contamination_ratio REAL,
  PRIMARY KEY (chunk_id, raw_sha)
);

CREATE TABLE IF NOT EXISTS chunk_label (
  chunk_id INTEGER, raw_sha TEXT,
  chunk_type TEXT, confidence REAL, rule_id TEXT, evidence_json TEXT,
  PRIMARY KEY (chunk_id, raw_sha)
);

CREATE TABLE IF NOT EXISTS eligibility (
  policy_id TEXT, chunk_id INTEGER, eligible INTEGER, reason_codes_json TEXT,
  PRIMARY KEY (policy_id, chunk_id)
);

-- Paper-local hyphen decisions. `decision` is one of join | keep | unresolved.
CREATE TABLE IF NOT EXISTS hyphen_decision (
  paper_id INTEGER, left TEXT, right TEXT,
  decision TEXT, rule_id TEXT,
  joined_count INTEGER, hyphenated_count INTEGER, n_occurrences INTEGER,
  PRIMARY KEY (paper_id, left, right)
);

CREATE TABLE IF NOT EXISTS acronym (
  paper_id INTEGER, short_form TEXT, long_form TEXT,
  defining_chunk_id INTEGER, method TEXT,
  PRIMARY KEY (paper_id, short_form, long_form)
);

CREATE TABLE IF NOT EXISTS repetition_layout (
  paper_id INTEGER, key_sha TEXT, n_pages INTEGER, x0_sigma REAL, y_band TEXT,
  member_chunk_ids_json TEXT, sample_text TEXT,
  PRIMARY KEY (paper_id, key_sha)
);

CREATE TABLE IF NOT EXISTS paper_calibration (
  paper_id INTEGER PRIMARY KEY,
  col_w REAL, page_x0 REAL, page_y0 REAL, page_x1 REAL, page_y1 REAL,
  n_columns INTEGER, body_median_span_h REAL, n_chunks INTEGER, ref_start_page INTEGER
);

CREATE TABLE IF NOT EXISTS adjudication (
  fixture_id TEXT PRIMARY KEY, subject_kind TEXT, subject_ref TEXT,
  verdict TEXT, rationale TEXT, adjudicated_at TEXT
);

CREATE TABLE IF NOT EXISTS metric (
  run_id TEXT, scope TEXT, name TEXT, value REAL, detail_json TEXT
);
"""


def study_dir() -> Path:
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    return STUDY_DIR


def raw_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def connect() -> sqlite3.Connection:
    study_dir()
    conn = sqlite3.connect(SIDECAR)
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def library_readonly() -> sqlite3.Connection:
    """Open the library strictly read-only. A study script that can write it is a one-keystroke disaster."""
    uri = f"file:{LIBRARY_DB.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def record_run(conn: sqlite3.Connection, run_id: str, params: dict) -> None:
    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False
        ).stdout.strip()
    except Exception:
        git_sha = "unknown"
    from datetime import datetime, timezone

    conn.execute(
        "INSERT OR REPLACE INTO run_manifest VALUES (?,?,?,?,?)",
        (run_id, git_sha, datetime.now(timezone.utc).isoformat(), json.dumps(params), str(LIBRARY_DB)),
    )
    conn.commit()
