"""Repeatable offline driver: renders the c9+c11 partial-answer vertical slice from already-saved records.

Reads only:
  - the two frozen packet files `gate1_evidence_fixture.py` already names,
  - the saved `runs/gate2-diagnostic-002/04_final_record.json` Gate 2 overview record.

Writes only:
  - `runs/gate2-diagnostic-002/06_partial_answer_slice.md`
  - `runs/gate2-diagnostic-002/07_partial_answer_manifest.json`

Makes no model, NLI, embedding, retrieval, localization, or eligibility call. Modifies no existing file.

    python -m experiments.ask_cli_revised.contract_directed.tools.render_c9_c11_partial_slice
"""

from __future__ import annotations

import json

from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.contract_directed import gate1_evidence_fixture as fixture
from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as renderer

RUN_DIR = freeze.SLICE_ROOT / "runs" / "gate2-diagnostic-002"
RECORD_PATH = RUN_DIR / "04_final_record.json"


def main() -> int:
    if not fixture.available():
        raise SystemExit("the frozen c9/c11 packet files are not present on this machine")
    if not RECORD_PATH.is_file():
        raise SystemExit(f"{RECORD_PATH} is not present; nothing to render from")

    rows = fixture.build_c9_c11_manifest()
    gate2_record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))["record"]

    markdown, manifest = renderer.render_partial_slice(rows, gate2_record)

    md_path = RUN_DIR / "06_partial_answer_slice.md"
    manifest_path = RUN_DIR / "07_partial_answer_manifest.json"
    md_path.write_text(markdown, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"wrote {md_path}")
    print(f"wrote {manifest_path}")
    print()
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
