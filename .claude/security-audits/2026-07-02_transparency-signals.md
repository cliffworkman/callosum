# Security audit — Transparency-signals auditor (inc 250, backlog #44 increment 1)

**Date:** 2026-07-02
**Feature:** `methods/transparency.py` (pure regex auditor) + `GET /papers/{id}/transparency`
(`routers/transparency.py`) + the `08h_methods_transparency.jsx` METHODS panel. Reads a paper's extracted text and
detects whether it *discloses* 7 open-science artifacts (data/code availability, conflict-of-interest, funding,
protocol/trial registration, preregistration, an "available upon request" weak-signal qualifier) — present /
not-found / not-applicable. ODDPub / rtransparent-derived, rule-based. Near-exact clone of the inc-249 meta-analysis
auditor (`2026-07-02_metaanalysis-auditor.md`).

**Audit-gate trigger:** #1 (a new API endpoint) + #5 (a net-new feature spanning 3 files). Light review — the feature
is local, read-only over the paper already in the library, with no external fetch / egress / LLM / migration / new
dependency.

## Threat review

- **Input validation / boundary (rule #4):** the only endpoint input is `paper_id` (a path int, coerced by FastAPI)
  + the paper's own extracted chunk text (already ingested + validated at import; untrusted-content posture unchanged).
  The regexes are literal / anchored token patterns with no catastrophic backtracking (bounded alternations, `\b`
  anchors, character classes; no nested quantifiers), run over each chunk's text; no user-supplied pattern reaches `re`.
- **Injection / SQL (rule #3):** the router writes no SQL — it reads via the audited repo helpers `get_paper` +
  `get_chunks_for_paper` (SQLAlchemy Core bound parameters). No string-built SQL.
- **Output encoding:** the response is a Pydantic `TransparencyResponse` (JSON); the panel renders `label`/`note`/
  `explainer`/`basis`/`evidence` as React text nodes (no `dangerouslySetInnerHTML`) — no XSS surface. Evidence
  snippets are whitespace-collapsed + length-capped (200 chars) in `_snippet`.
- **SSRF / external calls:** NONE. The auditor makes no network call; it reads only the local DB. Not the Gemini
  egress gate (no library text leaves the machine).
- **Data egress:** NONE. Fully local — no LLM, no external fetch. The egress invariant (#3) is untouched.
- **Resource caps:** the auditor is O(chunks × patterns) over a single paper's already-bounded chunk set; each check
  short-circuits on the first match (`_first`/`_has`). No unbounded loop / recompute. It emits a fixed 7-check list,
  not a per-match list.
- **File-path safety:** no filesystem access.
- **Secret handling:** none involved.
- **Supply-chain:** no new dependency (stdlib `re` + dataclasses; the credit ＋add reuses the existing inc-93
  `/library/import`).

## The no-accusation boundary (the load-bearing security-relevant property)

This auditor sits on the A-A veto-level **no-accusation of individuals** boundary — an absence of a disclosure must
NEVER read as "this paper hides its data / has an undisclosed conflict / did no open science". This is enforced
**structurally + test-pinned**:

- The auditor emits only presence/absence of *reported* text; it never derives a "transparency score", a rank, or a
  verdict about the paper or authors (no such field; `test_no_verdict_no_score`).
- A not-found row is worded **"not detected in the extracted text — check the paper"**, never "absent" / "missing" /
  "concealed" / "no open data" / "not shared". `test_no_accusatory_language` asserts none of `concealed` / `failed to`
  / `hiding` / `no open data` / `not shared` appears in any emitted note or explainer, and that the not-found note
  carries the "not detected in the extracted text" wording.
- The `upon_request` row is a cited legibility qualifier ("a weaker signal than an open link, not a concern in
  itself"), never a flag/accusation.

## Precondition-scoping (verified)

- **Registration** → `not-applicable` unless a trial/registration cue is present (a registration flag on a lab
  experiment or an observational study is the failure mode).
- **Available upon request** → `present` only when the phrase appears, else `not-applicable` (never "not found" — its
  absence is the norm, not a gap).

## Negative-path checks (run)

- A bare survey paper with no open-science footer → all five core detectors `not-found` with the "check the paper"
  wording, no banned/accusatory strings.
- A non-trial paper → registration `n/a` (not a false "not found").
- A registered RCT → registration `present`; an unregistered RCT → registration `not-found`.
- A repository URL alone (no "data available" phrase) → data availability `present` (a real disclosure signal).
- 404 on an unknown paper id; a paper with no extracted chunks → 200, 7 checks, none `present`, honest-empty (not a crash).
- No `score`/`grade`/verdict field anywhere in the report.

All covered by `tests/test_transparency.py` (13 tests, hermetic; no network/model).

## Conclusion

Local, read-only over the paper in hand; no external fetch / egress / LLM / migration / dependency; anchored regexes
with no backtracking; the flag-not-adjudicate / silence-≠-certificate / precondition-scoped controls uphold the
A-A no-accusation boundary (test-pinned by `test_no_accusatory_language`).

**Security Audit: PASS**
