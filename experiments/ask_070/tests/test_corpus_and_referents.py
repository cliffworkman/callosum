import sqlite3
from pathlib import Path

import pytest

from experiments.ask_070.contracts import ContractError
from experiments.ask_070.corpus_presence import audit, frozen_copy, normalize, readonly_database
from experiments.ask_070.hashing import file_hash, read_json, text_hash
from experiments.ask_070.referents import inventory, validate_review

ROOT = Path(__file__).parents[1]


def database(path, *, negative=False, reference=False):
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES('fixture');
    CREATE TABLE papers(id INTEGER,title TEXT,abstract TEXT,deleted_at TEXT,merged_into INTEGER);
    CREATE TABLE chunks(id INTEGER,paper_id INTEGER,text TEXT,char_start INTEGER);
    CREATE TABLE chunk_structure(chunk_id INTEGER,evidence_role TEXT,reference_region INTEGER);""")
    db.execute("INSERT INTO papers VALUES(1,'neutral','',NULL,NULL)")
    text = "5‑HT2A human brain. Expert and laypeople face fixation. Images and truthiness."
    if negative:
        text += " Parkinson’s gut microbiome."
    db.execute("INSERT INTO chunks VALUES(1,1,?,0)", (text,))
    db.execute(
        "INSERT INTO chunk_structure VALUES(1,?,?)", ("bibliographic" if reference else "scientific", int(reference))
    )
    db.commit()
    db.close()
    spec = read_json(ROOT / "specifications/heldout_selection_v0.json")
    spec["corpus_expected_sha256"] = file_hash(path)
    return spec


def test_deterministic_positive_absence_and_offsets(tmp_path):
    p = tmp_path / "source.sqlite"
    spec = database(p)
    first, matches = audit(p, spec)
    assert audit(p, spec) == (first, matches)
    assert all(v["status"] == "PRESENCE_QUALIFIED" for k, v in first["outcomes"].items() if k != spec["negative_id"])
    assert first["outcomes"][spec["negative_id"]]["status"] == "ABSENT_UNDER_DECLARED_PROCEDURE"
    assert next(m for m in matches if m["group"] == "receptor")["exact_match"] == "5‑HT2A"


def test_negative_reference_material_blocks_and_positive_reference_only_fails(tmp_path):
    p = tmp_path / "source.sqlite"
    spec = database(p, negative=True, reference=True)
    result, _ = audit(p, spec)
    assert result["outcomes"][spec["negative_id"]]["status"] == "NEGATIVE_CONTROL_REPLACEMENT_REQUIRED"
    assert result["outcomes"]["eval_5ht2a"]["status"] == "BLOCKED_PENDING_DOMAIN_REPLACEMENT"


def test_readonly_db_no_mutation_or_extension(tmp_path):
    p = tmp_path / "source.sqlite"
    database(p)
    before = file_hash(p)
    with readonly_database(p) as db:
        for command in [
            "DELETE FROM papers",
            "CREATE TABLE nope(id)",
            "ATTACH DATABASE ':memory:' AS x",
            "SELECT load_extension('anything')",
        ]:
            with pytest.raises(sqlite3.DatabaseError):
                db.execute(command)
    assert file_hash(p) == before
    frozen_copy(p, tmp_path / "copy.sqlite", before)
    assert file_hash(tmp_path / "copy.sqlite") == before
    Path(str(p) + "-wal").write_bytes(b"notempty")
    with pytest.raises(ContractError):
        frozen_copy(p, tmp_path / "copy2.sqlite", before)


def test_question_inventory_not_ground_truth():
    q = read_json(ROOT / "specifications/questions_v0.json")["questions"][0]
    inv = inventory(q)
    assert "".join(s["text"] for s in inv["literal_spans"]) == q["text"]
    assert not inv["ground_truth_accepted"] and inv["review_status"] == "HUMAN_REFERENT_REVIEW_REQUIRED"
    assert not validate_review(inv, {})
    for span in inv["literal_spans"]:
        assert q["text"].encode()[span["utf8_start"] : span["utf8_end"]].decode() == span["text"]


def test_dev_eval_separation():
    questions = read_json(ROOT / "specifications/questions_v0.json")["questions"]
    dev = read_json(ROOT / "frozen/dev_inputs_v0.json")["historical_content"]
    hashes = {v["question_hash"] for v in dev.values()}
    assert not hashes & {q["question_sha256"] for q in questions}
    assert all(text_hash(q["text"]) == q["question_sha256"] for q in questions)


def test_normalization_keeps_raw_mapping():
    normalized, offsets = normalize("A\t  B ５–HT2A")
    assert normalized == "a b 5-ht2a" and len(normalized) == len(offsets)
