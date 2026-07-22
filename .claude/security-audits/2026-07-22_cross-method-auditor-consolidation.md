# Security audit — cross-method auditor consolidation (backlog #23, F1/F4)

**Scope:** the LMM/meta-analysis/Bayesian checkers gain a **library-wide batch endpoint** + a **persistence side
effect on the existing ad-hoc per-paper GET** (F4), plus a **library-header chip + `GET /papers?signal=...`
filter** (F1), mirroring the existing statcheck/retraction pattern. This audit covers the write path + new
endpoints these additions introduce (each auditor's own read-only text-scanning logic was already audited —
`2026-07-02_lmm-auditor.md`, `2026-07-02_metaanalysis-auditor.md`, `2026-07-01_bayes-auditor.md` — and is
unchanged here). Triggers the gate: new API endpoints (3 per checker) + a new persistence write path.

**Landed incrementally: LMM (inc 336), meta-analysis (inc 337), Bayesian (inc 338) — all three done. #23 closed.**

## Threat review

- **Input validation / injection:** identical shape to the existing statcheck/retraction batch jobs — no new
  user input surface. `POST /methods/lmm/run` takes no body; `paper_id` path params are FastAPI-coerced ints.
  All persistence goes through bound-param SQLAlchemy Core (rule #3) — `store_lmm`/`upsert_findings`, both
  pre-existing, audited functions reused as-is (no new SQL construction).
- **The new write-on-GET side effect (F4):** `GET /papers/{id}/lmm` now also calls `apply_lmm` via `run_write`
  after building its response. This is a deliberate, user-approved design choice (not a default REST
  convention) — flagged explicitly here because a GET normally shouldn't mutate. Mitigations: (1) the write is
  **idempotent** — `store_lmm`'s OR-REPLACE and `upsert_findings`'s content-hash keying mean repeated views of
  the same paper never duplicate a row; (2) the write is **narrowly scoped** — only `open_science_signals` and
  `paper_findings`, both already-audited tables, never `papers`/`attachments`/anything user-authored; (3) it is
  **additive/reversible** — no delete of user data, and a paper's own status can only flip between
  `complete`/`incomplete`/absent based on its own text, never cross-contaminating another paper.
- **Resource caps:** the batch job iterates `list_live_paper_ids` exactly like statcheck's/retraction's batch
  (already audited, already bounded by library size); each paper is a `run_write`-wrapped short transaction (lock
  released between papers, per the existing `commit_each`/`run_write` discipline) — a large library can't hold
  the writer lock for the whole run.
- **SSRF / external calls / secrets / egress:** none — same as the underlying auditors (local text only, no
  network, no LLM).
- **Fact-vs-candidate discipline (Principles #3):** the new `paper_findings` write is always `kind:"candidate"`
  (never `"fact"`) — a completeness *gap* is a prompt to look, not an established claim the way a retraction
  record is. Cleared (`upsert_findings(..., [])`) whenever the checklist becomes complete or the paper stops
  gating as LMM, so a stale candidate never survives past the state that produced it.
- **Supply-chain:** no new dependency.

## Negative-path checks (run — LMM)

- A non-LMM paper viewed via the ad-hoc GET → no `open_science_signals` row written (confirmed via
  `get_lmm_summary` returning `None`), and any *prior* row is cleared if the paper's detected genre changes
  (`test_apply_lmm_un_gates_clears_a_prior_signal`).
- Re-viewing the same paper twice, or re-running the batch twice, produces exactly one signal row and one
  candidate finding — no duplication (`test_apply_lmm_reapply_is_idempotent`).
- A batch run over an empty/no-DOI/no-text library completes cleanly (mirrors the existing statcheck/retraction
  batch's own already-audited empty-library behavior — shared `list_live_paper_ids` + `run_write` machinery).
- `GET /methods/lmm/run/{unknown-job-id}` → 404, matching the existing statcheck/retraction job-store contract.
- The chip/filter never shows a count exceeding what a fresh `GET /papers?signal=lmm-incomplete` actually returns
  (same query path the chip's number is sourced from — no separate, driftable cache).

## Negative-path checks (run — meta-analysis)

Identical checks re-run against `apply_meta_analysis`/`store_meta`/`POST /methods/meta-analysis/run` —
`test_metaanalysis.py`'s `test_apply_meta_*` + `test_endpoint_persists_signal_on_ad_hoc_view` +
`test_batch_run_summary_and_library_filter` (mirroring the LMM test names exactly). Same result: idempotent,
additive, correctly un-gates when a paper stops detecting as a meta-analysis. No new threat surface — the
pattern is byte-for-byte the same code shape as LMM, just against `methods/metaanalysis.py`'s own report.

## Negative-path checks (run — Bayesian)

Same shape again, plus one Bayes-specific case: the combination rule (`flagged = not_reproduced>0 OR any
completeness item is not-found/coherence-flag`) is verified in isolation with directly-constructed
`BayesReport`/`BayesCompleteness` objects (`test_apply_bayes_flags_on_bf_mismatch_alone`,
`test_apply_bayes_flags_on_completeness_gap_alone`, `test_apply_bayes_clean_stores_signal_no_candidate`,
`test_apply_bayes_not_bayesian_stores_nothing`, `test_apply_bayes_reapply_is_idempotent`) — decoupling the
persistence/combination logic from the text-detection logic (already covered by the existing `run_bayes`/
`audit_completeness` tests), so each of the three flagging paths (mismatch-only, gap-only, neither) is tested
independently rather than relying on a single real-text sample to exercise all three at once. Plus the same
ad-hoc-persists + batch+chip+filter end-to-end tests as LMM/meta-analysis.

One additional structural change this checker needed: `GET /papers/{id}/bayes` (previously inline in
`methods.py`, which was approaching the 600-line cap) was extracted to its own `methods_bayes.py` router,
mirroring the inc-262 `methods_retraction.py` precedent — a pure file-organization move, verified by the full
existing `test_bayes.py` suite passing unchanged (the endpoint's URL/behavior is identical) plus a direct
`create_app` import smoke-check.

## Result

**Security Audit: PASS (LMM, meta-analysis, Bayesian) — backlog #23 closed.** All three checkers reuse
already-audited persistence primitives and the already-audited statcheck/retraction batch-job shape; the one
genuinely new pattern (a GET with a persistence side effect) is idempotent, additive, and scoped to two
already-hardened tables across all three. The Bayesian checker's two-signal combination is tested in isolation
to avoid a false sense of coverage from only ever exercising both signals at once.
