# Security audit — Workbench SP2b assisted-extraction funnel (inc 259)

**Status: PASS** (opened at task-start per the audit gate; finalized in Task 5 with the negative-path results recorded).

**Trigger:** new API endpoints (`POST /workbench/rows/{id}/propose`, `POST /workbench/proposals/{id}/accept`,
`POST /workbench/proposals/{id}/reject`) + a new egress path (paper text → LLM) + a DB migration (0034) + spans 3+ files.

## Scope
An egress-gated LLM proposes meta-analysis cell values from a paper's PDF as **candidates** (`ma_proposals`, physically
isolated from the trusted `ma_cells`). A deterministic local locator (`locate_quote` → `anchor_proposal`) decides each
proposal's anchor state; the model never asserts a location or a confidence. Nothing enters `ma_cells` / the converter /
exports until a human accepts a proposal per cell. AI = funnel, human = filter (Principle: "the human is the filter").

## Threat review (results)
- **Library-text egress channel.** The paper's page-tagged text is sent to the configured LLM — the consent-gated
  channel. It rides the EXISTING gate: `EgressGatedExtractionAssistant` (`app/backend/llm/egress.py:181`) raises
  `DataEgressDisabledError` (→ **403**) for a non-loopback provider without `data_egress_enabled`; a loopback / local
  provider is honestly no-egress (endpoint-based gate, inc 256). No new bypass. Off by default (invariant #3).
  Verified: `test_propose_egress_off_returns_403`.
- **Untrusted model response.** A user can point the roster at an arbitrary endpoint, so the response is untrusted.
  `parse_proposals` (`integrations/gemini/extraction_assistant.py:58`) tolerates markdown fences + surrounding prose,
  ignores unknown keys + malformed entries, caps value (≤ 500) / quote (≤ 4000), and returns `[]` on any parse failure —
  never a crash. Verified: `test_parse_proposals_defensive` / `test_parse_proposals_caps_lengths`.
- **Resource exhaustion.** Paper text is capped at 50 000 chars before egress (`MAX_TEXT_CHARS`,
  `app/backend/workbench_assist.py:20`); `truncated` is reported honestly. Propose runs only over one row's empty
  structured fields (bounded); synchronous, one provider call.
- **File-path safety.** `anchor_proposal` runs `locate_quote` (`app/backend/pdf_processing/quote_matching.py:35`) on the
  server-resolved primary-PDF path only (`primary_pdf_path`, `workbench_assist.py:113` — from the trusted attachment
  rows: PDF-preferred, role=primary, present on disk); never a request-derived path (rule #4).
- **Injection / SQL.** SQLAlchemy bound-param SQL throughout (`ma_proposals` CRUD); `proposal_id` / `row_id` are int
  path params; request bodies are `ConfigDict(extra="forbid")` Pydantic models. Proposed values render as TEXT in React
  (no HTML), and ride the existing number-aware `_csv_safe` formula-injection guard on export once accepted.
- **Candidate isolation (the load-bearing property).** Proposals live only in `ma_proposals`; the converter
  (`cell_values`) and every export read `ma_cells`, which only ever holds human-accepted values. Accept is the sole
  promotion path. Verified: `test_propose_accept_reject_candidate_safety` (no proposed value in the CSV pre-accept).
- **Coordinate honesty (invariant #2).** Accepted precision is derived from `anchor_state`, not the model's claim: the
  accept endpoint stores `bbox_json` ONLY when `anchor_state == "exact"` AND the value was not edited before accept;
  an edit or a region/unanchored proposal stores `bbox_json = None` (opens at region, never a fake exact rect).
  Verified: `test_propose_edit_before_accept_drops_exact_to_region`.
- **Secret handling.** Unchanged — the key/token is write-only over the wire, never logged (the provider seam redacts).
  The funnel adds no new secret surface.
- **Supply chain.** No new dependency (reuses `google-genai` / `httpx` via the provider seam + `fitz` via
  `locate_quote`).

## Negative-path checks (results)
- Propose with egress OFF + a cloud provider → **403**, nothing sent (`test_propose_egress_off_returns_403`).
- Malformed / junk / markdown-fenced model JSON → **0 proposals**, clean 200, no crash
  (`test_parse_proposals_defensive`).
- Oversized paper text → **capped at 50 000 chars**, `truncated=true` (page-tag cap unit test).
- Row with no linked paper → **422**; row with no PDF on disk / no extracted text → **422**; unknown row → **404**;
  unknown proposal on accept/reject → **404** (`test_propose_requires_linked_paper`, `test_propose_no_pdf_returns_422`,
  `test_propose_no_extracted_text_returns_422`, router 404 paths).
- Provider failure (a raising assistant) → **502**, no partial write (`test_propose_provider_failure_returns_502`).
- No empty proposable structured fields → the endpoint **short-circuits with `{proposals: [], truncated: false}` and
  never calls the provider** (so a fully-filled row makes no egress even with AI on)
  (`test_propose_short_circuits_no_model_call_when_all_fields_filled`).

**Security Audit: PASS**

---

## 2026-07-23 addendum — inc 348 retrieval-narrowed extraction context

**Status: PASS.** The egress route, consent gate, provider roster, request shape, response parser, and candidate
isolation are unchanged. What changes is the bounded paper-text selection before the existing provider call:

- Papers with more than 12 chunks embed the empty structured field labels and candidate chunks locally, then use
  vector search restricted to those exact chunk target IDs. No other paper's text can enter the prompt.
- At most 12 page-tagged chunks are selected, and the existing 50,000-character cap remains a second resource bound.
  The response's compatibility `truncated` flag now also reports relevance narrowing; the UI describes locally
  selected passages rather than falsely claiming that the document head was sent.
- Embedding/vector failure is caught before egress and falls back to the prior bounded document-order assembly.
  Retrieval runs inside a database savepoint, so a partial embedding failure is rolled back before fallback. It
  neither disables the existing egress gate nor writes a proposal.
- No new endpoint, user input, host, dependency, secret, or persistence surface was added. The shared retrieval API's
  additive `candidate_target_ids` filter is expressed through SQLAlchemy bound parameters.

Hermetic coverage: `test_relevant_text_ranks_only_this_papers_chunks_from_field_labels`,
`test_relevant_text_falls_back_to_bounded_document_order`, and
`test_retrieval_can_restrict_hits_to_candidate_target_ids`.
