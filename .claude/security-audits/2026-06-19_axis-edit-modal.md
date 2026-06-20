# Security audit — Axis edit modal + title/term decoupling + click-to-open (increment 44)

**Date:** 2026-06-19
**Feature:** Unify axis create/edit/term-search into one **Edit Axis modal**; decouple the title
(cosmetic) from the search vocabulary (terms list embedded via the description's `Related:` block);
clicking an axis-listed article opens its PDF (A′).
**Audit trigger:** gate criterion #5 (a net-new feature spanning 3+ files). Recorded for completeness —
the threat surface is **unchanged**.

## Surface review
- **No new endpoint.** Create/edit reuse the existing `POST /axes` + `PATCH /axes/{id}`; the term search
  reuses `POST /axes/suggest-terms` (egress-gated since inc 41). The frontend modal merely composes the
  `description` string (prose + `Related:` terms) before calling those existing, already-audited routes.
- **No new external fetch / egress path.** The only off-machine call remains the inc-41 suggester behind
  `CALLOSUM_ALLOW_DATA_EGRESS` (off → 503, surfaced as guidance in the modal). The single backend change
  (`_axis_text` now embeds the description with a label fallback, `axis_scoring.py`) is **local-only** and
  touches no I/O.
- **No new file-write / ingestion path; no new auth; no new dependency.**
- **A′ (click-to-open)** routes an axis paper through the **existing** `openPdf` tab flow (which serves
  `/papers/{id}/pdf`, an existing audited read route). No new data exposure.

## Threat notes
- **Input validation (rule #4):** unchanged — `POST /axes` / `PATCH /axes/{id}` still enforce label
  (1..200) and description (≤4000) via Pydantic; the modal cannot bypass them.
- **Injection / SQL (rule #3):** `_axis_text` reads `axis["description"]`/`axis["label"]` from already
  parameterized ORM rows; no SQL constructed. Untrusted Gemini term output is still deduped/echo-stripped/
  capped by the inc-41 `_parse_terms` before it can reach a chip.
- **Data safety:** the decoupling changes only *which stored text is embedded* (description vs.
  label+description), with a label fallback so no axis embeds an empty string. Existing axes show stale →
  user re-scores (no data loss, no migration).

## Negative paths (verified)
- Full `pytest` green (**147**), incl. new `test_axis_scoring_keys_on_description_not_label` and
  `test_axis_label_only_falls_back_to_label_for_embedding`; existing label-only/punctuation tests still
  pass via the fallback.
- Live E2E: term suggestions arrive **deselected** (user must opt in); modal flow has **0 console errors**.
- Egress-off behavior inherited from inc 41 (503 → guidance), unchanged.

## Verdict
**Security Audit: PASS** — UI/UX consolidation + an internal embedding-text change over existing,
already-audited routes; no new endpoint, egress, ingestion, auth, dependency, or file-path surface.
