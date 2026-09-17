"""Reproducible lexical presence only. Never establishes answerability or ground truth."""

import re
import shutil
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from .contracts import ContractError
from .hashing import digest, file_hash, text_hash

DASHES = "‐‑‒–—−﹘﹣－"


def normalize(raw):
    chars, offsets = [], []
    for index, char in enumerate(raw):
        for converted in unicodedata.normalize("NFKC", char).casefold():
            if converted in DASHES:
                converted = "-"
            if converted.isspace():
                if chars and chars[-1] == " ":
                    continue
                converted = " "
            chars.append(converted)
            offsets.append(index)
    return "".join(chars), offsets


def frozen_copy(source, target, expected):
    source, target = Path(source), Path(target)
    wal = Path(str(source) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ContractError("CORPUS_HAS_NONEMPTY_WAL")
    if file_hash(source) != expected:
        raise ContractError("CORPUS_SOURCE_HASH_MISMATCH")
    if target.exists():
        raise ContractError("CORPUS_COPY_ALREADY_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    if file_hash(target) != expected or file_hash(source) != expected:
        raise ContractError("CORPUS_CHANGED_DURING_COPY")
    if wal.exists() and wal.stat().st_size:
        raise ContractError("CORPUS_WAL_CHANGED_DURING_COPY")


@contextmanager
def readonly_database(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.execute("PRAGMA query_only=ON")
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}

    def authorize(action, arg1, arg2, db, trigger):
        if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() == "load_extension":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    connection.set_authorizer(authorize)
    try:
        yield connection
    finally:
        connection.close()


def audit(path, procedure):
    before = file_hash(path)
    if before != procedure["corpus_expected_sha256"]:
        raise ContractError("CORPUS_HASH_MISMATCH")
    patterns = {
        g: re.compile(r"(?<!\w)(?:" + "|".join(ps) + r")(?!\w)") for g, ps in procedure["term_patterns"].items()
    }
    matches = []
    positive_by_paper, all_by_paper = {}, {}
    counts = {g: 0 for g in patterns}
    examined = {"metadata_fields": 0, "chunks": 0, "empty_fields": 0, "positive_excluded_chunks": 0}

    def scan(paper_id, chunk_id, field, raw, eligible, role, char_start=None):
        if not raw:
            examined["empty_fields"] += 1
            return
        normalized, offsets = normalize(raw)
        for group, pattern in patterns.items():
            found = list(pattern.finditer(normalized))
            if not found:
                continue
            all_by_paper.setdefault(paper_id, set()).add(group)
            if eligible:
                positive_by_paper.setdefault(paper_id, set()).add(group)
            for match in found:
                start, end = offsets[match.start()], offsets[match.end() - 1] + 1
                counts[group] += 1
                matches.append(
                    {
                        "paper_id": paper_id,
                        "chunk_id": chunk_id,
                        "field": field,
                        "group": group,
                        "start": start,
                        "end": end,
                        "exact_match": raw[start:end],
                        "source_text_sha256": text_hash(raw),
                        "positive_eligible": eligible,
                        "evidence_role": role,
                        "chunk_char_start": char_start,
                    }
                )

    with readonly_database(path) as db:
        schema = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        papers = db.execute(
            "SELECT id,title,abstract FROM papers WHERE deleted_at IS NULL AND merged_into IS NULL ORDER BY id"
        ).fetchall()
        for paper_id, title, abstract in papers:
            for field, raw in (("title", title), ("abstract", abstract)):
                examined["metadata_fields"] += 1
                scan(paper_id, None, field, raw, True, "metadata")
        rows = db.execute("""SELECT c.paper_id,c.id,c.text,s.evidence_role,s.reference_region,c.char_start
            FROM chunks c JOIN papers p ON p.id=c.paper_id LEFT JOIN chunk_structure s ON s.chunk_id=c.id
            WHERE p.deleted_at IS NULL AND p.merged_into IS NULL ORDER BY c.paper_id,c.id""")
        for pid, cid, raw, role, reference, char_start in rows:
            eligible = role not in ("bibliographic", "structural") and not reference
            examined["chunks"] += 1
            examined["positive_excluded_chunks"] += not eligible
            scan(pid, cid, "text", raw, eligible, role or "unknown", char_start)
    outcomes = {}
    for item, groups in procedure["positive_groups"].items():
        ids = sorted(pid for pid, present in positive_by_paper.items() if set(groups) <= present)
        outcomes[item] = {
            "status": "PRESENCE_QUALIFIED" if ids else "BLOCKED_PENDING_DOMAIN_REPLACEMENT",
            "qualifying_paper_ids": ids,
            "required_groups": groups,
            "semantic_answerability": "NOT_ESTABLISHED",
            "referent_correctness": "NOT_ESTABLISHED",
        }
    negative_ids = sorted(
        pid
        for pid, groups in all_by_paper.items()
        if "parkinson" in groups and ("microbiome" in groups or {"gut", "microbial"} <= groups)
    )
    outcomes[procedure["negative_id"]] = {
        "status": "NEGATIVE_CONTROL_REPLACEMENT_REQUIRED" if negative_ids else "ABSENT_UNDER_DECLARED_PROCEDURE",
        "disqualifying_lexical_paper_ids": negative_ids,
        "scientific_absence": "NOT_ESTABLISHED",
    }
    if file_hash(path) != before:
        raise ContractError("CORPUS_CHANGED_DURING_AUDIT")
    summary = {
        "version": 1,
        "procedure_sha256": digest(procedure),
        "corpus_sha256": before,
        "schema_version": schema,
        "live_unmerged_papers": len(papers),
        "examined": examined,
        "term_occurrences": counts,
        "outcomes": outcomes,
        "matches_sha256": digest(matches),
        "complete": True,
        "inference_calls": 0,
        "limits": procedure["limits"],
    }
    from .hashing import read_json
    from .validation import validate

    validate(summary, read_json(Path(__file__).parent / "schemas/corpus_presence.schema.json"))
    return summary, matches
