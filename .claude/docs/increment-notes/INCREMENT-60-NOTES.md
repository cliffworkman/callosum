# Increment 60 Notes — AI help assistant (separate gate, deep-linked references)

Increment 59 made help a navigable corpus. This adds the **AI help assistant**: ask a natural-language
question in the help modal, get a concise answer + structured **references** to the help subsections it
used, and clicking a reference scrolls the modal to and highlights that section — recapitulating the
synthesis tool's "probe → matches → route to source", over the app's own help (to condition the same
workflow). Additive: no summary/axis/verification/embedding/persistence path or API shape was modified.

## Implemented
- **Provider-neutral** `app/backend/help/assistant.py` — `HelpAssistant` Protocol + `HelpTurn` /
  `HelpReference` / `HelpAnswer` dataclasses.
- **Concrete** `integrations/gemini/help_assistant.py` — `GeminiHelpAssistant` (reuses `genai.Client` +
  `GeminiConfig` + `_strip_code_fence`). **NO RAG** — the whole corpus is stuffed via `help_corpus_prompt()`
  each call (a comment marks RAG as the upgrade path). Multi-turn (history passed in; server stateless).
  Defensive JSON parse → `HelpAnswer`; **parse failure degrades to the answer text with no references,
  never raising**.
- **Separate, independent gate** — `GeminiConfig.help_assistant_enabled` reads a NEW
  **`CALLOSUM_HELP_ASSISTANT_ENABLED`** env var (parallel to `data_egress_enabled`; off by default).
  Following the inc-58 **seam-gate pattern**, `app/backend/llm/egress.py` gains `HelpAssistantDisabledError`
  + `EgressGatedHelpAssistant` (keyed on the help toggle, **not** the library egress flag); the provider
  also self-checks for defense-in-depth (before importing genai).
- **`POST /help/ask`** (`routers/help.py`) `{message, history}` → `{answer, references:[{section_id,
  reason}]}` (sync, mirrors `suggest_axis_terms`: `HelpAssistantDisabledError → 503`, other `Exception →
  502`). Inputs validated/capped at the boundary (message + per-turn 1–4000, history ≤ 20, role enum). The
  router **drops any `section_id` not in the live corpus** so a hallucinated id can't reach the UI.
  `_help_assistant` factory + `help_assistant` `create_app` param/`api.state` mirror `_summary_generator`.
- **Frontend** (`18_help.jsx`): a `HelpChat` panel above the docs — input, conversational log, answer +
  clickable **reference chips** → `flashHelpSection(id)` (the inc-59 helper). When the assistant is off
  (503), the chat shows the actionable guidance and the written docs still work.
- **Corpus**: added an `ai-help-assistant` help section documenting the feature (so the docs cover it) —
  which re-syncs the `HELP-DOCS-SYNCED` marker forward to inc 60.

## "PR description" (no git repo — recorded here, as requested at task start)
**Confirmation: no existing path was modified.** All changes are additive — new files
(`help/assistant.py`, `gemini/help_assistant.py`, the egress wrapper, the `/help/ask` handler) plus a new
optional `help_assistant=` injection point and a new `GeminiConfig` field. Existing summary/axis/
verification/embedding/persistence code and every existing API response shape are untouched (one new POST
route added to the allowlist). **The help gate is independent of the library gate:** the assistant is
keyed on `CALLOSUM_HELP_ASSISTANT_ENABLED`, never `CALLOSUM_ALLOW_DATA_EGRESS`; it sends only the user's
question + the **public** help corpus (never library text), so it works with the library egress flag off —
proven by `test_help_ask_works_when_library_egress_off` and a live E2E that runs with library egress OFF.

## Verification
- **pytest: 217** (+7: answer+references via injected fake; **gate independence** [library egress off +
  help on → 200]; **hole closed** [injected non-self-gating fake + help off → 503]; unknown-`section_id`
  dropped; empty message → 422; parse-failure degradation; provider self-check). Route-surface invariant
  updated (+`/help/ask` POST).
- **Live E2E** (`.local/help_assistant_e2e/`, injected fake, **library egress OFF**): ask → answer + 2
  reference chips → first chip scrolled the docs (0→6479px) + flashed `creating-and-editing-axes`; 0
  console errors; screenshot confirms the layout.
- Audit: `.claude/security-audits/2026-06-20_help-assistant.md` — **PASS**.

## Backlog
The help feature (docs + assistant) is complete. Remaining queued items unchanged: library **merge** (last,
destructive); terms-as-first-class; DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup; permanent-delete/
empty-trash; persistent dedup-dismiss. Possible help follow-ups: a Settings status line for the help toggle;
streaming answers; RAG if the corpus ever outgrows the prompt.
