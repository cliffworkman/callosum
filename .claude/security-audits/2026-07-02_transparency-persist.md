# Security audit — Transparency persistence (inc 251, backlog #44 increment 1b)

**Date:** 2026-07-02
**Feature:** persist the inc-250 transparency audit as library-wide signal.
- `methods/transparency_findings.py::persist_transparency` — runs `detect_transparency` (inc 250) over a paper's
  chunks; writes **present-disclosure FACTs** to `paper_findings` (inc 130 `upsert_findings`) + per-disclosure
  **check status** to `open_science_signals` (`signals_repo.store_transparency_status`).
- `routers/transparency.py` (inc 250) gains `POST /methods/transparency/run` + `GET /methods/transparency/run/{job_id}`
  (async JobStore batch over `list_live_paper_ids`) + `GET /methods/transparency/summary`.
- `repository.SIGNAL_FILTERS` generalized `(signal_type, status)` → `(signal_type, source|None, status)` + 7 new
  transparency review-queue entries; the `08h` panel gains a **Check all papers** batch + review-queue links; the
  Library header gains a **review-queue chip**.

**Audit-gate trigger:** #1 (new API endpoints — the batch run/status/summary) + #5 (a net-new persistence producer
+ frontend across 3+ files). Light review — local, no external fetch / egress / LLM / migration / new dependency.
Extends the audited inc-250 endpoint + the audited inc-97 (statcheck) / inc-131 (retraction) persistence pattern.

## The load-bearing constraint (the A-A no-accusation boundary)

This is the whole reason the feature needed a design pass, and it is enforced **structurally**, not by copy:

- **Present-only FACTs.** `persist_transparency` builds FACTs **only** for `status == "present"` checks — an absence
  is **never** written as a fact (the inc-250-declined "NO open data" fact). Pinned by
  `test_bare_paper_writes_no_absence_facts` (a paper disclosing nothing → `_fact_keys == set()`).
- **Status rows are check results, not claims.** `open_science_signals` stores every disclosure's status
  (detected / not-detected / not-applicable) — a record that *the auditor ran and did/didn't find it in the text*,
  never a claim the paper lacks the artifact. The review-queue chip + links are worded "not detected — go look",
  the chip tooltip says explicitly "never a claim that they hide it". No score/rank/verdict field exists in any
  response (there is no such column, and the summary is a plain count).
- **Precondition scoping for free.** The registration review queue matches `status == "not-detected"` only; a
  non-trial paper stores `registration = "not-applicable"`, so it is **excluded** — no registration flag on every
  paper (the failure mode). `upon_request` is the *present* case (its absence is the norm — never a "not detected").
  Pinned by `test_registration_filter_excludes_non_trial_and_upon_request_is_present`.

## Threat review

- **Input validation / boundary (rule #4):** the batch endpoints take no body (the run is over all live papers);
  the summary/status take a job-id path string (JobStore lookup, 404 on miss). The review-queue `signal` param on
  `GET /papers` is matched against the **`SIGNAL_FILTERS` allowlist** (rule #3) — an unknown value is ignored, never
  reaching SQL. The detector input is the paper's own already-ingested chunk text (inc-250 posture, unchanged).
- **Injection / SQL (rule #3):** all writes use SQLAlchemy Core bound parameters (`store_transparency_status` OR-REPLACE
  insert, `upsert_findings`); the generalized filter builds a bound `IN`-subquery with the `source` clause added only
  when the allowlisted tuple pins a source (a fixed literal, never request data). No string-built SQL.
- **Output encoding:** responses are Pydantic models (JSON). The panel + chip render `label`/`desc`/`note`/`basis`
  as React text nodes (no `dangerouslySetInnerHTML`) — no XSS surface. Evidence snippets stay `_snippet`-capped.
- **SSRF / external calls:** NONE. The producer + endpoints read only the local DB; the detector makes no network
  call. Not the Gemini egress gate (no library text leaves the machine).
- **Data egress:** NONE. Fully local — no LLM, no external fetch. Invariant #3 untouched.
- **Resource caps:** the batch is O(live papers × chunks × patterns), each check short-circuiting on first match;
  one FACT-set + 7 status rows per paper (OR-REPLACE — idempotent, no growth on re-run). The JobStore streams
  progress; no unbounded loop.
- **Persistence safety:** **no migration** — `paper_findings` (inc 130) + `open_science_signals` (inc 97) already
  exist; the `open_science_signals` unique `(paper, signal_type, source)` makes re-runs idempotent (one row per
  disclosure). `upsert_findings`' content_key diffing supersedes stale FACTs when a re-run detects fewer
  (`test_rerun_supersedes_a_now_absent_disclosure`). `paper_findings.target_paper_id`/FK CASCADE unchanged.
- **Supply chain:** no new dependency.

## Negative-path checks (from `tests/test_transparency_findings.py`, hermetic)

- A bare paper (no disclosures) → **no FACTs written** + 7 `not-detected` status rows (the A-A pin).
- Re-run over changed text supersedes a now-absent disclosure's FACT + flips its status to `not-detected`.
- Re-run over the same text is idempotent (same content_keys → unchanged; one status row per disclosure).
- The batch endpoint 202→poll→done persists FACTs + statuses; the review queue returns only papers where the
  auditor didn't detect the disclosure (a present-data paper is excluded); the registration queue excludes an n/a
  (non-trial) paper; the upon_request queue returns the *present* paper; the summary count is honest; an unknown
  job id → 404.
- `SIGNAL_FILTERS` back-compat: the statcheck (`source=None`) filter still works after the tuple generalization.

## Verdict

**Security Audit: PASS.** Local read-only detection persisted to existing tables with bound-param SQL; no external
fetch / egress / LLM / migration / new dependency; the no-accusation boundary is structural (present-only FACTs,
review-queue-not-verdict wording, precondition-scoped filters, no score field) and test-pinned.
