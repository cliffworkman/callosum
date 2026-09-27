# Contract-directed child-answer slice

Ask R&D arc, 2026-09-26. Research-assistant / PI analogy: a thinking-OFF Qwen (the assistant) answers **one approved child
contract** from **exact source evidence** found for that contract; a later thinking-ON parent synthesis (the PI) is **out of scope
here**. The approved decomposition, the library and the baseline are frozen; nothing in this package edits them.

Issues: R&D #2 (contracts), #3 (paper-first navigator), #4 (corpus bridges), #5 (within-paper evidence), #18 (abstract-first
triage and original-finding provenance). Lineage is preserved in those issues; this file records only what this implementation
decided. Follow [Credit the lineage](../../../.claude/CREDIT-THE-LINEAGE.md).

## What runs, in order

| Stage | Module | Model? | Receipt |
|---|---|---|---|
| S0 freeze | `freeze.py` | no | hashes of question, hierarchy, model-facing contract, library, baseline artifacts |
| S1 nominate | `nominate.py` | no | `01_nominations.jsonl` (each paper with every route, rank, score; overflow `capped_out`) |
| S2 triage | `model_stages.triage_paper` | yes | `02_triage.jsonl` (abstract-only lead; verbatim quote checked; no abstract stays reachable) |
| S3 anchors, neighborhoods | `anchors.py`, `neighborhood.py`, `sections.py` | no | `04_anchors.jsonl`, `05_neighborhoods.jsonl` (`read` / `budget_capped`), `05b_seam_states.jsonl` |
| S4 localize | `model_stages.localize_neighborhood` | yes | `06_localization.jsonl` (ids only) |
| S5 packet | `packet.py`, `links.py`, `attribution.py`, `seams.py`, `units.py` | no | `07_packets.jsonl` |
| S6 eligibility | `model_stages.judge_packet`, `closure.py` | yes | `08_eligibility.jsonl`, `13_assignment_matrix.json` |
| S7 coverage | `coverage.py` | no | `09_coverage.json` |
| S8 recovery (one pass) | `recovery.py` | yes | `10_recovery.jsonl` |
| conditional bridge | `bridge.py` | (yes if triggered) | `11_bridge.jsonl` |
| S9 answer | `model_stages.answer_child`, `answer.py` | yes | `12_answers/cN_raw_answer.txt`, `cN_record.json` |
| S10 report | `report.py`, `expectations.py` | no | `15_..`, `16_..`, `17_review_sheet.md`, `trace_cN.md` |

`pipeline.py` sequences them. `run.py prepare` runs every deterministic stage offline; `run.py live` runs everything and refuses
without a confirmed authorization file, a clean tree, an unchanged library and baseline, and the recorded model digest.

## The rules that carry the science

**The model returns ids and short labels only.** Sentence-unit ids, span ids, enums. It never writes a quote, a claim or a
locator; code resolves ids to exact substrings and checks every piece against its own chunk with `canonical_text_contains`
(never relaxed). A joined sentence is never checked as one string.

**Source order is verified, not inferred (`seams.py`).** A sentence split across chunks is joined only if the seam verifier
establishes continuity from: same attachment, same source checksum (equal to the attachment row), same extraction, contiguous
stream offsets, same page, same column with the right block below the left within a bounded gap, no block between them, and a
text continuation. Chunk ids alone never suffice. A chain of any length joins only if every seam verifies; one failure cuts it
into flagged fragments. Column switches are implemented but **disabled**: a spot-check found about 4 of 12 verified joins wrong
(footnote joined to a methods sentence, a heading to a footer, "reported at an" to an unrelated line). Geometry cannot prove a
cross-column continuation; the honest outcome is an unresolved seam.

**Attribution comes from what the sentence says (`attribution.py`).** Section labels are clues, never gates: an Introduction can
preview this study's findings and a Discussion can recount another study's. States: `own_established | other_study |
speculation | mixed | unresolved`. Own-study bases: explicit first-person / this-study wording, reported test statistics, or a
result sentence that also appears in the paper's own abstract with no contrary cue. The model's provenance label can only
downgrade a result, never upgrade it. Only `own_established` closes a finding.

**One defensible, source-grounded finding (`closure.py`, `links.py`).** A unit closes only if every required slot for its
frozen kind is filled by valid span ids inside one finding bundle: a core proposition plus links the source itself establishes
(a definition acronym, a named measure present verbatim in both spans, an explicit Table/Study reference; a study-label conflict
refuses the link). Linked spans may supply only descriptive slots (instrument, procedure, population); relation, polarity,
direction and outcome must come from the core. Relata must be tied to the stated relation (same unit or a declared adjacent
referent). Two packets are never summed. Co-occurrence is not a link.

**Coverage never certifies.** `evidence_attached | partial_only | unresolved_mechanical | unresolved_budget |
unresolved_searched`, always with `completeness: not_certified`. Mechanical failure (NO ANSWER) is counted apart from a valid
"nothing relevant" (`none_established`) at every stage.

**Raw answers are saved first and never gated.** The prompt instruction text is byte-identical to the baseline diagnostic; the
evidence block adds deterministic source metadata only. Advisory diagnostics (acronym expansions absent from the passages,
directional wording absent from the cited text, composite citations, leakage) prompt review and never change or hide an answer.

## Budgets (computed by `budget.py`, frozen in the run manifest)

Per child: T=25 triage papers, I=6 inspected papers, N=18 neighborhoods (= I x (1 abstract page + at most 2 content units)),
R=6 recovery neighborhoods, B=3 bridge neighborhoods (only if triggered), 9,000 characters per neighborhood. Per run: 40 (pilot)
or 60 (full) unique packets for eligibility, each checked against every child in the run. Worst-case calls are computed from
these numbers, enforced as ceilings at run time, and overflow is recorded (`capped_out`, `budget_capped`,
`not_checked_budget`, `not_run_budget`), never dropped.

## Offline gates

```
python -m pytest experiments/ask_cli_revised/contract_directed -q                          # ordinary suite
python -m experiments.ask_cli_revised.contract_directed.offline_pytest                      # every socket refused
python -m experiments.ask_cli_revised.contract_directed.distribution                        # seams over every chunk
python -m experiments.ask_cli_revised.contract_directed.run prepare --run-id NAME --children pilot
```

Tests that touch the private frozen data skip when it is absent. Nothing here launches a model.

## Known limitations (measured, not hoped away)

- One question, one library, one run per arm; no variance estimate; no claim of generalization.
- About 4.7% of sentence pieces remain unverifiable fragments (column switches, cross-page joins, plain-text chunks).
- 11 of 43 nominated papers in the pilot dry-run have no readable text (metadata only), including two direct intervention
  studies for c12. Evidence must be chunk-anchored, so abstract-only leads are reported, not cited.
- Chunk-first retrieval is polluted by running heads; they are demoted by the H1a structure table, never deleted.
- Citation-context bridges are not runnable here (parsed references exist for 5 of 256 papers).
- Eligibility slot judgments are model-made and cannot be deterministic (no substrate exists for "this span states the
  relation"); ids-only output, mechanical status derivation and negative controls are the mitigation, not a proof.
- c9's Methods chunk was checked during development, so that specific check is development-informed, not blind.
