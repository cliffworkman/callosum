<!-- qa-coverage
api: /help*
fe: 18_help.jsx
-->

# ROUTE 58 - Help and assistant

**Tier:** 2 egress/external
**Goal:** Exhaust help corpus navigation and assistant ask flow while keeping the default run hermetic and egress-gated.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Run hermetically by default:** use `create_app(...)` with an injected fake help assistant/generator client so asks do not contact Gemini or other providers. Keep `CALLOSUM_ALLOW_DATA_EGRESS` unset unless running an explicit integration pass. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open Help (`18_help.jsx`). Confirm corpus loads (`GET /help/corpus`) with table of contents and sections.
2. Click every TOC entry. Confirm scroll/focus behavior, visible section state, and no layout overlap.
3. Search or filter help content if the control is present. Submit empty and whitespace-only queries.
4. Ask the assistant (`POST /help/ask`) with the injected fake client. Confirm answer, cited/help-source context, loading, cancellation/retry if present, and no hidden verdict language.
5. Double-submit and navigate away mid-answer. Confirm no duplicate answer, stuck spinner, or console error.
6. In a negative egress-unset pass without the fake assistant, ask a question and confirm a clear egress-disabled/provider-required message and zero genai network requests.

## Pass criteria

- Help corpus navigation and assistant ask complete.
- Hermetic default uses injected fake assistant; no genai-host requests with egress unset.
- Assistant answers cite/source themselves and do not present hidden scores or accusations.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_58_help_assistant.md` + `screenshots/` (see `_TEMPLATE.md`).
