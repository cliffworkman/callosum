# Security audit — statcheck (inc 95)

**Date:** 2026-06-21
**Feature:** `GET /papers/{paper_id}/statcheck` — recompute reported NHST p-values from a paper's extracted text;
a deterministic, local, no-LLM per-paper signal rendered in the Details pane.
**Trigger(s):** new API endpoint; new compute path over (untrusted) extracted PDF text; a dependency change
(`scipy` made explicit). No file write, no auth, no migration.

## Surface
- `app/backend/methods/statcheck.py` — regex NHST detection + `scipy.stats` p-recomputation + classification.
- `app/backend/api/routers/methods.py` — `GET /papers/{paper_id}/statcheck` (sync, read-only).
- `app/backend/api/app.py` — registers the router.
- `requirements.txt` — `scipy` made explicit.
- Frontend `25_detail.jsx` — a "Check statistics" button + results list (read-only display).

## Threat review
- **Untrusted input / malformed content (rule #4).** The input is a paper's extracted chunk text (untrusted —
  PDF-derived). The detectors are anchored regexes capturing only well-formed APA NHST patterns; anything that
  doesn't match is ignored. Every parse is guarded: `_to_float` failures `continue`, `recompute_p` returns
  `None` on degenerate inputs (e.g. `|r| ≥ 1`, df ≤ 0, scipy domain errors) and those matches are dropped — a
  garbled statistic is skipped, **never crashes** the request (tested: `test_no_statistics_text`,
  `recompute_p` degenerate case, the endpoint over real chunk text).
- **Resource exhaustion.** `MAX_RESULTS = 500` caps matches per paper; scanning stops once reached. The regexes
  are **linear / non-backtracking** (no nested unbounded quantifiers — fixed structure `name(df)=num,p<num`),
  so no catastrophic-backtracking DoS on adversarial text. Work is bounded by the paper's chunk count.
- **SSRF / external calls / EGRESS.** **None.** Pure local computation over stored text — no network call, no
  LLM, no file read. Nothing leaves the machine; the egress gate is not in play.
- **File-path / write safety.** No filesystem access; no writes (read-only `get_chunks_for_paper`). The endpoint
  does not persist (v1 computes on demand), so no injection into stored state.
- **SQL injection.** Reads go through `get_paper` / `get_chunks_for_paper` (SQLAlchemy Core bound params,
  rule #3). `paper_id` is an int path param. No interpolation.
- **Output encoding.** Results (`raw`, `reported_p`, `computed_p`, `consistency`, `page`) render as React text
  (auto-escaped). The `raw` matched string is shown verbatim by design (so the user can spot PDF artifacts) —
  it's plain text in a `<span>`, not HTML.
- **Supply chain.** `scipy` is added to `requirements.txt` but is **already installed transitively** (scikit-learn
  depends on it) — net-zero new install, made explicit for honesty. scipy is a mainstream, widely-audited
  package; version-bounded `>=1.11,<2`. `pip-audit` is unaffected (already in the resolved tree).
- **Principle/values posture (not a security risk, but the load-bearing design constraint).** Signal, not
  verdict; no composite score; **no accusation** (inconsistencies framed as commonly-innocent, amber not red);
  coverage stated. See the inc-95 notes' gate write-up.

## Negative-path checks (run)
- Paper with no chunks (metadata-only) → `checked: 0`, empty results — **not** a 500 (test). ✓
- Missing paper → 404 (test). ✓
- Garbled / degenerate statistic (`|r| ≥ 1`) → dropped, no crash (test). ✓
- Correctly-rounded p and one-tailed p → **not** flagged (no false positive — tests). ✓
- No statistics in text → `checked: 0` (test). ✓

## Result
**Security Audit: PASS.** statcheck is local-only (zero egress, no LLM, no writes), bounded (match cap +
non-backtracking regexes), defensive (malformed/degenerate input dropped, never fatal), read-only bound-param
SQL, and adds no net-new dependency. Its v1 limits (APA-inline NHST only; per-chunk so cross-chunk stats are
missed) are coverage trade-offs stated to the user, not security risks.
