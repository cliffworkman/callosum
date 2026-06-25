# Security audit — synthesis evidence-traceable Overview (inc 124)

**Date:** 2026-06-25 · **Feature:** a second LLM pass that narrativizes the verified claims of a synthesis into a
short Overview, with per-sentence trace links back to the verified claims. Backend + frontend + a migration.

**Audit-gate triggers:** net-new feature spanning 3+ files (#5). NOT a new external service — reuses the existing
Gemini provider + the inc-58 egress seam.

## Threat review

- **Data egress (invariant #3).** The Overview pass sends **library-derived text** (the verified claim
  sentences) to Gemini. It rides the **library egress gate**: `EgressGatedOverviewGenerator` raises
  `DataEgressDisabledError` when `CALLOSUM_ALLOW_DATA_EGRESS` is off, and `_overview_generator(api)` returns
  `None` unless egress is on AND a key is set. In practice the **summary generation upstream already raised**
  with egress off, so the Overview pass is never reached. Verified: `test_egress_gate_blocks_overview_when_disabled`,
  `test_no_overview_generator_leaves_overview_null`, and the headed run made **0 requests** to any
  `generativelanguage`/genai host with egress unset.
- **Untrusted model output.** The Gemini response is parsed defensively (`_parse_overview_response`): non-dict
  items dropped; empty/missing `text` dropped; non-list `claim_indices` dropped; non-int refs dropped (JSON
  `true`/`false` excluded via the `bool`-is-`int` guard); sentence text capped at `MAX_SENTENCE_CHARS`; at most
  `MAX_OVERVIEW_SENTENCES` returned; inputs capped at `MAX_CLAIMS` / `MAX_CLAIM_CHARS`. In `pipeline.py`,
  `claim_indices` are validated `0 <= i < len(verified)` and **mapped to the verified sentences' ordinals** — so a
  stored trace can only point at a real verified claim (no LLM-invented citations). Verified:
  `test_parse_overview_response_drops_malformed_items`, `test_overview_drops_out_of_range_claim_indices`.
- **Fail-closed.** Any generator error (egress, network, parse) is caught in `_maybe_store_overview` → the
  Overview is simply absent; the synthesis + its verified claims are unaffected (never a 500/blocked synthesis).
- **Injection / SQL.** Storage is a bound-parameter `update(summaries).values(overview_json=items)` (SQLAlchemy
  Core; rule #3). No string interpolation. No new file/path/network-fetch surface.
- **Output encoding (frontend).** The Overview text is rendered as React text content (`{item.text}`) — escaped,
  no `dangerouslySetInnerHTML`. Trace refs are integers rendered as `[n]`. No XSS surface.
- **No new endpoint.** The Overview rides the existing `/summarize` + `/summaries/{id}` responses (additive
  `overview` field). Migration 0015 is additive + idempotent (guarded column-add); head derived by tests (inc 99).

## Negative-path checks (run)

- Egress off → Overview NULL, synthesis still returns its verified claims (test + headed run, 0 genai hits). ✔
- Malformed / out-of-range model refs → dropped; a sentence with no valid refs dropped entirely. ✔
- 0 verified claims → no overview (`_maybe_store_overview` early-returns). ✔

## Principles alignment (rule #9)

Aligned: the Overview is **traceable-to-evidence** (per-sentence links to verified claims that carry
quote/page/confidence), **restates only verified claims** (prompt + the validated index mapping), its citations
are **inherited from verified claims, never LLM-invented**, it sits **above/secondary to** the evidence, is
**egress-gated**, and is **omitted when nothing is verified**. The declined easy path: a polished authoritative
prose summary presented on its own authority, eclipsing the evidence. The deterministic/verified substrate
remains the source of truth; the model only narrates it.

**Security Audit: PASS**
