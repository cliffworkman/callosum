"""Offline demonstration of the citation-boundary repair (NLI_REPAIR_DESIGN.md Section 2/3) against the REAL
saved c9+c11 raw model responses -- not a fresh model/NLI/network call anywhere in this script.

Reads `03_raw_response.json` from both `gate2-diagnostic-002` and `gate-integration-live-002` (the model's own
raw `{"overview": [...]}` JSON, unmodified by anything downstream) and `04_final_record.json` for the matching
`units`. Re-screens those exact raw proposals through the REAL, now-modified `overview.screen_proposals`, using
a STUBBED entail scorer (arbitrary fixed placeholder scores, clearly labeled -- never a claim about what a real
NLI call would return). This demonstrates the marker-boundary MECHANISM works against real data; it does NOT
and cannot validate that the stripped hypothesis actually scores differently -- that needs a separately
authorized live call (see the handback's "smallest next live evaluation" note).

Writes only to a NEW directory (`runs/nli-repair-demo-001/`), created fresh by this script. Never opens any
existing `04_final_record.json` for writing, never touches `gate2-diagnostic-*`/`gate-integration-live-*`/
`nli-boundary-diagnostic-*`, and never retroactively marks a historically-withheld candidate as grounded.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised.contract_directed import gate1_evidence_fixture as fixture
from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as renderer

SLICE_ROOT = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice")
RUNS_DIR = SLICE_ROOT / "runs"
DEMO_DIR = RUNS_DIR / "nli-repair-demo-001"

# Every existing run this script must never write into.
PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "nli-boundary-diagnostic-002",
        "nli-premise-population-eval-001",
        "nli-prospective-corpus-eval-001",
        "nli-prospective-pilot-001",
        "pilot-001",
        "pilot-prep-003",
        "replay-eligibility-001",
        "replay-eligibility-001-offline-analysis",
    }
)


class StubEntail:
    """A clearly-labeled STUB, not a real NLI call. Returns a fixed, arbitrary (support, contradiction) pair
    per call, chosen only to exercise both the "grounded" and "withheld" code paths in this demonstration --
    never presented as an empirical prediction of what the real cross-encoder would return."""

    def __init__(self, score: tuple[float, float] = (0.90, 0.05)):
        self.score = score
        self.calls: list[list[tuple[str, str]]] = []

    def __call__(self, pairs):
        self.calls.append(list(pairs))
        return [self.score] * len(pairs)


def _load_raw_overview(run_id: str) -> list[dict]:
    with open(RUNS_DIR / run_id / "03_raw_response.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["answer"]["overview"]


def _load_units(run_id: str) -> dict[str, dict]:
    with open(RUNS_DIR / run_id / "04_final_record.json", encoding="utf-8") as f:
        record = json.load(f)["record"]
    return {u["unit_id"]: u for u in record["units"]}


def main() -> None:
    if DEMO_DIR.name in PROTECTED_RUN_DIRS:
        raise RuntimeError("refusing to target a protected run directory")
    if DEMO_DIR.exists() and any(DEMO_DIR.iterdir()):
        raise RuntimeError(f"refusing to overwrite an already-populated directory: {DEMO_DIR}")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 1. The real saved raw responses, read verbatim (not re-typed) ----------------------------------
    raw_live = _load_raw_overview("gate-integration-live-002")  # c9 WITH marker, c11 WITH marker
    raw_diag = _load_raw_overview("gate2-diagnostic-002")  # c9 WITHOUT marker (the acceptance comparison)
    units_live = _load_units("gate-integration-live-002")
    part_ids = {"c9", "c11"}

    # ---- 2. Re-screen the REAL raw proposals through the actual, now-modified screen_proposals -----------
    # Deliberately a LOW stub score (below both thresholds) for every REAL saved candidate: both c9 and c11's
    # real candidates stay "withheld" here regardless of marker stripping, exactly as their real history --
    # this demo must never show a real, previously-withheld candidate as "displayed" merely because a stub
    # score was chosen generously. The marker mechanism is demonstrated on the INPUT TEXT, not on the outcome.
    stub = StubEntail(score=(0.10, 0.05))
    records_live = ov.screen_proposals(raw_live, units_live, part_ids, stub)
    records_diag = ov.screen_proposals(raw_diag, units_live, part_ids, StubEntail(score=(0.10, 0.05)))

    before_after = []
    for rec in records_live:
        before_after.append(
            {
                "raw_text": rec["text"],
                "nli_hypothesis_text": rec["nli_hypothesis_text"],
                "marker_outcome": rec["marker_outcome"],
                "stripped_marker": rec["stripped_marker"],
                "screen_reasons": rec["screen_reasons"],
                "status_under_stub_score": rec["status"],  # a STUB score, not a real NLI result
            }
        )

    # ---- 3. Acceptance check: the stripped live-002 c9 hypothesis matches diag-002's own real c9 text ----
    live_c9 = next(r for r in records_live if r["unit_ids"] == ["U1"])
    diag_c9 = next(r for r in records_diag if r["unit_ids"] == ["U1"])
    acceptance_match = live_c9["nli_hypothesis_text"] == diag_c9["text"]

    # ---- 4. A SYNTHETIC conflicting-marker example (no real saved candidate has one) ----------------------
    synthetic_conflict_proposal = {
        "text": "The scale measures fairness beliefs in participants (U9).",  # SYNTHETIC, not real model output
        "unit_ids": ["U1"],
        "bears_on": ["c9"],
    }
    conflict_records = ov.screen_proposals(
        [synthetic_conflict_proposal], units_live, part_ids, StubEntail(score=(0.99, 0.0))
    )
    conflict_record = conflict_records[0]

    # ---- 5. Full pipeline replay through the HARDENED renderer, preserving Gate 1 + W21 -------------------
    manifest_rows = fixture.build_c9_c11_manifest()
    demo_record = {"units": list(units_live.values()), "proposals": records_live}
    markdown, render_manifest = renderer.render_partial_slice(manifest_rows, demo_record)

    m10 = next(c for c in render_manifest["classifications"] if c["unit_id"] == "M10")
    w21 = next(c for c in render_manifest["classifications"] if c["unit_id"] == "W21")
    m12 = next(c for c in render_manifest["classifications"] if c["unit_id"] == "M12")

    # ---- write outputs (new directory only) ---------------------------------------------------------------
    with open(DEMO_DIR / "00_demo_manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "note": "STUBBED entail scores throughout -- not a real NLI call. Demonstrates the marker-"
                "boundary and renderer-hardening MECHANISM against real saved raw responses; does not and "
                "cannot validate what a real cross-encoder call would score.",
                "before_after_live_002": before_after,
                "acceptance_fixture_match": acceptance_match,
                "synthetic_conflict_example": {
                    "text": conflict_record["text"],
                    "marker_outcome": conflict_record["marker_outcome"],
                    "screen_reasons": conflict_record["screen_reasons"],
                    "status": conflict_record["status"],
                },
                "renderer_m10_outcome": m10["outcome"],
                "renderer_w21_outcome": w21["outcome"],
                "renderer_m12_outcome": m12["outcome"],
                "renderer_m12_evidence_present": bool(m12["evidence_spans"]),
                "no_real_candidate_shown_as_displayed": m10["outcome"] != renderer.DISPLAYED
                and m12["outcome"] != renderer.DISPLAYED,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    lines = [
        "# Citation-boundary repair -- offline demonstration (STUBBED scores, real saved raw text)\n",
        "**Every NLI score below is a fixed stub, not a real model call.** This demonstrates the marker-"
        "stripping and renderer-hardening mechanism against the actual saved raw model responses; it does not "
        "validate what a real cross-encoder would score for the stripped hypothesis.\n",
        "## Before / after: the real saved gate-integration-live-002 raw responses\n",
    ]
    for row in before_after:
        lines.append(f"**Raw text (unchanged, saved verbatim):**\n> {row['raw_text']}\n")
        lines.append(f"**NLI hypothesis (what the scorer actually sees now):**\n> {row['nli_hypothesis_text']}\n")
        lines.append(
            f"`marker_outcome={row['marker_outcome']}` `stripped_marker={row['stripped_marker']!r}` "
            f"`screen_reasons={row['screen_reasons']}` `status(under stub score)={row['status_under_stub_score']}`\n"
        )
    lines.append(
        f"## Acceptance fixture check: does the stripped live-002 c9 hypothesis match diagnostic-002's own "
        f"real (unmarked) c9 text, byte-for-byte?\n\n**{acceptance_match}**\n"
    )
    lines.append("## Synthetic conflicting-marker example (not real model output, fails closed)\n")
    lines.append(f"> {conflict_record['text']}\n")
    lines.append(
        f"`marker_outcome={conflict_record['marker_outcome']}` "
        f"`screen_reasons={conflict_record['screen_reasons']}` "
        f"`status={conflict_record['status']}` -- withheld regardless of the (deliberately high) stub score.\n"
    )
    lines.append("## Full pipeline replay through the hardened renderer\n")
    lines.append(
        f"- M10 (c9's candidate, marker-stripped input, LOW stub score) outcome: `{m10['outcome']}` -- stays "
        f"withheld under this deliberately-low stub, exactly matching its real history; NOT claimed grounded.\n"
    )
    lines.append(f"- W21 (c9's unresolved obligation) outcome: `{w21['outcome']}` -- never closed.\n")
    lines.append(
        f"- M12 (c11's source-supported population evidence) outcome: `{m12['outcome']}`, "
        f"evidence present: `{bool(m12['evidence_spans'])}` -- source support intact regardless of the "
        f"still-open c11 premise-reliability question; NOT claimed grounded.\n"
    )
    lines.append(
        "\n**This demo intentionally uses a low stub score so neither real candidate is ever shown as "
        "displayed/grounded here** -- the point is the marker-boundary mechanism on the INPUT text, not a "
        "claim about what score either candidate would really receive.\n"
    )
    with open(DEMO_DIR / "01_demonstration.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote demonstration to {DEMO_DIR}")
    print(f"Acceptance fixture match (stripped live-002 c9 == diag-002 c9, byte-for-byte): {acceptance_match}")
    print(f"Synthetic conflict example status: {conflict_record['status']} ({conflict_record['screen_reasons']})")
    print(f"M10 outcome: {m10['outcome']}  |  W21 outcome: {w21['outcome']}  |  M12 outcome: {m12['outcome']}")
    print(f"M12 evidence present: {bool(m12['evidence_spans'])}")
    print(
        "No real candidate shown as displayed/grounded (deliberately low stub score): "
        f"{m10['outcome'] != renderer.DISPLAYED and m12['outcome'] != renderer.DISPLAYED}"
    )


if __name__ == "__main__":
    main()
