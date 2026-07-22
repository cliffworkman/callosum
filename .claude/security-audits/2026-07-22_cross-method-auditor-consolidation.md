# Security audit — cross-method auditor consolidation (backlog #23, F1/F4)

**Scope:** the LMM/meta-analysis/Bayesian checkers gain a **library-wide batch endpoint** + a **persistence side
effect on the existing ad-hoc per-paper GET** (F4), plus a **library-header chip + `GET /papers?signal=...`
filter** (F1), mirroring the existing statcheck/retraction pattern. This audit covers the write path + new
endpoints these additions introduce (each auditor's own read-only text-scanning logic was already audited —
`2026-07-02_lmm-auditor.md`, `2026-07-02_metaanalysis-auditor.md`, `2026-07-01_bayes-auditor.md` — and is
unchanged here). Triggers the gate: new API endpoints (3 per checker) + a new persistence write path.

**Landed incrementally: LMM (inc 336) done; meta-analysis and Bayesian to follow in this same document.**

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

## Result

**Security Audit: PASS (LMM)** — reuses already-audited persistence primitives and the already-audited
statcheck/retraction batch-job shape; the one genuinely new pattern (a GET with a persistence side effect) is
idempotent, additive, and scoped to two already-hardened tables. Re-run the negative-path checks (not a fresh
threat-model pass — the pattern is unchanged) when meta-analysis and Bayesian land in this same document.
