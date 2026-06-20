# Security Audit — AI help assistant (increment 60)

**Date:** 2026-06-20
**Trigger:** New API endpoint (`POST /help/ask`) + a new external LLM integration (Gemini help assistant)
+ a new consent gate. Net-new feature spanning 3+ files.

## What changed
- New provider-neutral `HelpAssistant` Protocol + dataclasses (`app/backend/help/assistant.py`).
- New `GeminiHelpAssistant` (`integrations/gemini/help_assistant.py`) — answers a help question from the
  **public help corpus only** (stuffed whole; NO RAG), defensively parsed.
- New **independent** gate: `EgressGatedHelpAssistant` + `HelpAssistantDisabledError`
  (`app/backend/llm/egress.py`), gated on `CALLOSUM_HELP_ASSISTANT_ENABLED` (new
  `GeminiConfig.help_assistant_enabled`) — **separate from the library `CALLOSUM_ALLOW_DATA_EGRESS`
  gate**. Applied at the `_help_assistant` factory seam (inc-58 pattern).
- New `POST /help/ask` (`routers/help.py`) + `help_assistant` `create_app` param/state.

## Threat review
- **Data egress (the critical design point):** the help assistant sends ONLY (a) the user's typed
  question + conversation history and (b) the **public, app-owned** help corpus — it **never** sends
  library text, paper content, abstracts, or metadata. It is therefore gated by its **own** toggle and is
  **independent** of the library egress gate: it works with `CALLOSUM_ALLOW_DATA_EGRESS` off (so a
  sensitive library never blocks help, and users are never trained to flip the library gate for help).
  A test asserts this independence. Off by default (opt-in), like every external call.
- **Enforcement boundary:** the gate is authoritative at the `_help_assistant` factory (covers an injected
  assistant AND the default), raising `HelpAssistantDisabledError` before the provider runs; the provider
  also self-checks before importing/calling `genai` (defense-in-depth) — so a disabled help assistant
  never touches the network. A hole-closed test injects a non-self-gating fake with the toggle off and
  asserts 503.
- **Untrusted model output:** the model's JSON is parsed defensively (reuse `_strip_code_fence`); a parse
  failure degrades to the answer text with **no references, never a 500**. The answer is length-capped;
  references are deduped/capped, and the **router drops any `section_id` not in the live corpus** (a
  hallucinated id can't reach the frontend). The answer renders as **plain text** in the chat (no HTML
  injection); references render as buttons that only call `flashHelpSection(id)` (scroll, no nav).
- **Input validation (rule #4):** `message` 1–4000 chars; `history` ≤ 20 turns, each `content` 1–4000,
  `role` ∈ {user, assistant} (Pydantic). Empty message → 422. Provider/network failure → 502 (never 500).
- **Secrets:** `GOOGLE_API_KEY` read only inside the provider; never logged/returned.
- **SSRF / file paths / SQL:** none — no DB, no request-derived paths, the only external call is the
  gated Gemini call.
- **Supply chain:** no new dependency (`google-genai` already present).
- **API surface:** one new POST route, added to the route-surface invariant allowlist. CORS unchanged.

## Negative-path checks (results)
- Injected fake + help ON → 200 with answer + references. **PASS.**
- `CALLOSUM_ALLOW_DATA_EGRESS` unset/false + help ON → 200 (gate independence). **PASS.**
- Injected non-self-gating fake + help OFF → **503** (seam closes the bypass hole). **PASS.**
- `GeminiHelpAssistant.answer` with help-off config → raises `HelpAssistantDisabledError` before any genai
  import (defense-in-depth). **PASS.**
- Malformed model JSON → answer text returned, no references, no 500. **PASS.**
- Reference to an unknown `section_id` → dropped by the router. **PASS.**
- Empty message → 422. **PASS.**

Full suite: **217 passed** (+7 help-assistant tests). Live E2E (`.local/help_assistant_e2e/`, injected
fake, library egress OFF) — ask → answer + reference chips → chip scrolls+flashes the section, 0 console
errors — also proving gate independence in a running app.

**Security Audit: PASS.**
