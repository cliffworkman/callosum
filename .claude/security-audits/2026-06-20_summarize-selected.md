# Security Audit — Summarize selected papers (increment 62)

**Date:** 2026-06-20
**Trigger:** Net-new feature spanning 3+ files (frontend wiring + a backend chunk-selection change). Audited
because it touches the summarization (trust-critical) path — though it adds **no new external surface**.

## What changed
- Frontend: a **"summarize"** action in the library bulk bar drives the Synthesis pane to run a
  **papers-scope** `/summarize` over the checkbox-selected paper ids.
- Backend: `_round_robin_by_paper` in `pipeline.py` — for a multi-paper, no-query scope, interleave chunks
  across the selected papers within the `top_k` budget (so the summary covers all selected papers).

## Threat review
- **No new endpoint, no new egress, no new ingestion, no migration.** The feature reuses the **existing**
  `POST /summarize` `scope_type:"papers"` path (already shipped + tested) — the same egress gate
  (`EgressGated(Cached(real))`), the same local citation-verification spine, the same inc-61 cache. Egress
  off → the job errors with the consent message, surfaced in the pane (unchanged behavior).
- **Data egress:** a multi-paper summary sends the selected papers' chunk text to the (egress-gated) LLM —
  exactly the same kind of data, through the same gate, as a query-scope summary. The round-robin selection
  changes *which* chunks (representative across papers), not *whether* the gate applies. No library text
  leaves without consent.
- **Input validation:** `paper_ids` is validated server-side (`scope_type:"papers"` requires a non-empty
  list → 400; `top_k` is `1..50`). The frontend only sends ids from the user's own selection; the client
  `top_k` is bounded (`min(max(8, n), 24)`). No request-derived SQL/paths.
- **Verification unchanged:** every citation in a multi-paper summary is locally verified (quote + NLI +
  confidence) exactly as for a query summary; nothing is auto-trusted.
- **No DB writes beyond the existing summarize persistence** (summary + sentences + verifications), which is
  already audited. The round-robin is a pure in-memory reordering of the retrieved chunks.

## Negative-path checks
- Multi-paper coverage: a papers-scope summary over 2 papers (2 chunks each) with `top_k=2` selects chunks
  spanning **both** papers (test). **PASS.**
- Single-paper / query scopes unchanged (round-robin is identity for ≤1 paper; query path untouched). **PASS.**
- Egress off → job error surfaced (reuses the audited gate). **PASS** (inc-58 suite green).
- Empty selection → the bulk bar (and the button) only render when ≥1 paper is selected.

Full suite: **226 passed** (+3). Live E2E (`.local/summarize_selected_e2e/`, injected fake, egress on) —
select 2 → summarize → verified multi-paper result + scope note, 0 console errors.

## Deferred (own audits when built)
The **critical-review supplement** (a stronger, opinionated AI action) is deferred — it must clear the
**Auditability standard** (`.claude/docs/INCREMENT-BACKLOG.md`) and gets its own egress/audit review.

**Security Audit: PASS.**
