# Security audit — Gemini axis synonym suggester (increment 41)

Date: 2026-06-19
Scope: a new egress-gated external fetch — `POST /axes/suggest-terms` calls Gemini to propose related
terms for a user-defined axis; the user curates them in a modal and the chosen terms fold into the axis
description. Triggered the audit gate: a new external/LLM integration + a new endpoint.

## Threat review
- **Data egress (the key control).** Axis scoring is otherwise fully local; this is the only new path
  that sends data off-machine. It is **gated by explicit consent**: `GeminiAxisTermSuggester.suggest`
  raises `DataEgressDisabledError` **before importing or calling `google.genai`** when
  `CALLOSUM_ALLOW_DATA_EGRESS` is not set — identical to `GeminiSummaryGenerator`. The endpoint maps that
  to **HTTP 503** with guidance. So with egress off, nothing leaves the machine (proven by
  `test_suggest_terms_egress_off_returns_503`, which touches no network). Only the user's own axis
  **label + description** is sent — never library/paper/PDF content.
- **Authn/authz.** Unchanged — local, single-user, loopback-bound, CORS GET-only. New route is POST;
  no new auth surface. Pre-public auth/rate-limiting still tracked in CLAUDE.md.
- **Input validation.** `SuggestTermsRequest.label` is `Field(min_length=1, max_length=200)` (+ a
  whitespace-only guard → 422); `description` capped at 4000. Stateless (no DB write; the frontend
  applies via the existing validated `PATCH /axes/{id}`).
- **Untrusted model output.** `_parse_terms` defensively handles Gemini's response: malformed JSON →
  `[]`; non-list → `[]`; each term stripped, **deduped (case-insensitive), length-capped (≤60), count-
  capped (≤12)**, and label-word echoes dropped. Terms reach the DOM only as React text children
  (auto-escaped) — no `innerHTML`. The curated terms are applied as plain text appended to the
  description (visible + editable by the user), embedded locally on the next score.
- **No 500s.** `DataEgressDisabledError` → 503; any other Gemini/network error → 502 with a detail
  string (caught in the handler). No unhandled exception path.
- **Injection / SQL / path / ingestion.** None — the endpoint does no DB write and no file access; the
  prompt is built with `json.dumps` of the user's own text. No new ingestion or file-serving surface.
- **Supply chain.** Reuses the already-present `google-genai` dependency + the existing `GeminiConfig`
  egress/key handling (`GOOGLE_API_KEY` from env, never in code). No new dependency.
- **Route-surface invariant.** `test_api_exposes_only_read_only_get_routes` updated to admit exactly
  `("/axes/suggest-terms", {POST})`.

## Negative-path checks (covered by tests)
egress-off → 503 (no network); empty label → 422; malformed model output → `[]`; over-long / duplicate
terms dropped; the live E2E uses a fake suggester (no real Gemini) and shows graceful curate→apply.

## Verdict
**Security Audit: PASS** for the current local, single-user context. The only off-machine data is the
user's own axis text, sent strictly under explicit egress consent (default-deny, fails closed to 503),
with model output validated/capped and surfaced honestly for human curation. Auth + rate-limiting before
any public deployment remain tracked in CLAUDE.md.
