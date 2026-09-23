"""Build the frozen supervisory battery from REAL run9 artifacts (no regeneration, no library query, no cloud).

    python -m experiments.ask_cli_revised.supervisor_eval.build_battery build   # writes manifest + private battery
    python -m experiments.ask_cli_revised.supervisor_eval.build_battery freeze  # writes FREEZE.txt
    python -m experiments.ask_cli_revised.supervisor_eval.build_battery verify  # checks the freeze

Public-safe split: `battery_manifest.json` (claims/obligations/expected judgments/per-case input hashes) and
`FREEZE.txt` are committed; the verbatim source quotes and every rendered prompt live in the gitignored
private battery, which the freeze hash-pins. `cases.py` is verified against the source byte-for-byte, so the
committed constants cannot silently drift from the evidence they claim to come from.
"""

import hashlib
import json
import sys
from pathlib import Path

from experiments.ask_070.hashing import digest
from experiments.ask_cli_revised.supervisor_eval import cases, freeze, models, prompts, schemas

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[2]
EXPECTED_QUESTION_HASH = "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
REAL_RUN_DIR = REPO_ROOT / ".local" / "ask-060-fix-run" / "run9-schema-obligations"
PRIVATE_DIR = REPO_ROOT / ".local" / "ask-070-supervisor-bakeoff" / "battery"
MANIFEST_NAME = "battery_manifest.json"
PRIVATE_NAME = "battery.private.json"
FREEZE_NAME = "FREEZE.txt"
BATTERY_VERSION = "supervisor-eval-v1"
SOURCE_FILES = ("01_request_contract.json", "09_propositions.jsonl", "10_verification.jsonl", "11_verified_ledger.json")
FROZEN_CODE = ("cases.py", "prompts.py", "schemas.py", "scoring.py", "models.py", "ollama_client.py", "freeze.py")


class SourceMismatch(Exception):
    """The real artifacts do not match what the frozen battery says they contain."""


def _read(run_dir, name):
    path = Path(run_dir) / name
    if not path.exists():
        raise SourceMismatch(f"missing source file {name} in {run_dir}")
    return path.read_bytes()


def _jsonl(raw):
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def verify_source(run_dir, expected_question_hash=EXPECTED_QUESTION_HASH):
    raw = {name: _read(run_dir, name) for name in SOURCE_FILES}
    problems = []
    contract = json.loads(raw["01_request_contract.json"])
    if contract.get("question_hash") != expected_question_hash:
        problems.append("the source run answers a different question (question hash differs)")
    if contract.get("original_question") != cases.ORIGINAL_QUESTION:
        problems.append("the original question text differs from the source")
    ledger = json.loads(raw["11_verified_ledger.json"])

    real_obligations = {o["field_id"]: o["note"] for s in ledger["subquestions"] for o in s["obligations"]}
    for o in cases.OBLIGATIONS:
        if real_obligations.get(o["field_id"]) != o["note"]:
            problems.append(f"obligation {o['field_id']} text differs from the source")

    by_id = {p["proposition_id"]: p for p in ledger["verified_propositions"]}
    quotes = {}
    for p in cases.PROPOSITIONS:
        real = by_id.get(p["proposition_id"])
        pid = p["proposition_id"]
        if real is None:
            problems.append(f"{pid} is not in the verified ledger")
            continue
        if real["proposition_text"] != p["claim"]:
            problems.append(f"{pid} claim text differs from the verified ledger")
        if f"{real['subquestion_id']}-o1" != p["retrieved_for"] or real["paper_id"] != p["paper_id"]:
            problems.append(f"{pid} retrieval context (obligation/paper) differs from the verified ledger")
        if real["verification"]["status"] != "verified":
            problems.append(f"{pid} is not verified in the source")
        if not (real.get("quote") or "").strip():
            problems.append(f"{pid} has no source quote")
        quotes[pid] = real.get("quote", "")

    props, vers = _jsonl(raw["09_propositions.jsonl"]), _jsonl(raw["10_verification.jsonl"])
    for base in cases.build_case_specs():
        if base["ordering"] != "original" or base["family"] != "A":
            continue
        src = base["claim_source"]
        if not src["origin"].startswith("09_propositions.jsonl["):
            continue
        index = int(src["origin"].split("[")[1].rstrip("]"))
        row, status = (props[index], vers[index]["status"]) if index < len(props) else ({}, None)
        if (
            row.get("proposition_text") != base["claim"]
            or status != src["status"]
            or row.get("paper_id") != src["paper_id"]
        ):
            problems.append(f"{base['base_id']} candidate claim/status/paper differs at 09_propositions.jsonl[{index}]")
    if problems:
        raise SourceMismatch("; ".join(problems))
    return {
        "quotes": quotes,
        "source": {
            "run": Path(run_dir).name,
            "question_hash": contract["question_hash"],
            "ledger_sealed_hash": ledger.get("sealed_hash"),
            "file_sha256": {n: hashlib.sha256(raw[n]).hexdigest() for n in SOURCE_FILES},
        },
    }


def _dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def build(run_dir, public_dir, private_dir, *, expected_question_hash=EXPECTED_QUESTION_HASH):
    source = verify_source(run_dir, expected_question_hash)
    manifest_cases, private_cases = [], []
    for spec in cases.build_case_specs():
        prompt = prompts.render(spec, quotes=source["quotes"] if spec["family"] == "B" else None)
        schema = schemas.build_schema(spec)
        input_sha = digest({"prompt": prompt, "schema": schema})
        private_cases.append(
            {"case_id": spec["case_id"], "prompt": prompt, "schema": schema, "input_sha256": input_sha}
        )
        manifest_cases.append({**spec, "input_sha256": input_sha})
    manifest = {
        "battery_version": BATTERY_VERSION,
        "source": source["source"],
        "envelope": dict(models.ENVELOPE),
        "obligations": cases.OBLIGATIONS,
        "propositions": cases.PROPOSITIONS,
        "cases": manifest_cases,
        "public_note": "Claims and obligations are the user's own request units and one-sentence claims. "
        "Verbatim source quotes and rendered prompts are private and hash-pinned by FREEZE.txt.",
    }
    private = {"battery_version": BATTERY_VERSION, "quotes": source["quotes"], "cases": private_cases}
    _dump(Path(public_dir) / MANIFEST_NAME, manifest)
    _dump(Path(private_dir) / PRIVATE_NAME, private)
    return manifest, private


def freeze_spec(manifest_path, private_path):
    return {
        "code_files": {name: PACKAGE_DIR / name for name in FROZEN_CODE},
        "json": {"battery_manifest": json.loads(Path(manifest_path).read_text(encoding="utf-8"))},
        "private_files": {PRIVATE_NAME: Path(private_path)},
    }


def default_freeze_spec():
    return freeze_spec(PACKAGE_DIR / MANIFEST_NAME, PRIVATE_DIR / PRIVATE_NAME)


def main(argv):
    command = argv[0] if argv else "verify"
    if command == "build":
        manifest, _ = build(REAL_RUN_DIR, PACKAGE_DIR, PRIVATE_DIR)
        print(f"built {len(manifest['cases'])} cases; source {manifest['source']['run']}")
    elif command == "freeze":
        freeze.write(PACKAGE_DIR / FREEZE_NAME, freeze.compute(default_freeze_spec()))
        print(f"wrote {FREEZE_NAME}")
    elif command == "verify":
        problems = freeze.verify(PACKAGE_DIR / FREEZE_NAME, default_freeze_spec())
        print("\n".join(problems) if problems else "freeze intact")
        return 1 if problems else 0
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
