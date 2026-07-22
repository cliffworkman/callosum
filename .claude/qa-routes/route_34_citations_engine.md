<!-- qa-coverage
api: /citations*
fe: 25_detail.jsx
-->

# ROUTE 34 - Citations engine

**Tier:** 1 local-stateful
**Goal:** Exhaust citation style listing, single citation rendering, and document bibliography rendering.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

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

1. Open "Cite as..." for a seeded paper. Confirm styles load (`GET /citations/styles`).
2. Switch styles and render (`POST /citations/render`). Confirm preview updates, copy succeeds, and missing CSL fields degrade cleanly.
3. Render a bibliography/document export (`POST /citations/render-document`) using multiple selected papers. Confirm ordering, escaping, and selected style are honored.
4. Try an unknown style, no selected papers, and malformed paper id state. Confirm validation messaging and no crash.
5. Confirm no citation surface presents papers as good/bad or ranked by hidden score.

## Pass criteria

- Style list, citation preview, copy, and document render complete.
- 0 console/page errors and 0 genai-host requests.
- Bad inputs fail cleanly; output is visibly tied to the selected style.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_34_citations_engine.md` + `screenshots/` (see `_TEMPLATE.md`).
