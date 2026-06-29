<!-- qa-coverage
api: GET /tags, GET /tags/colors, POST /tags/{tag_id}/color, GET /papers/{paper_id}/suggested-tags, POST /papers/{paper_id}/tags, DELETE /papers/{paper_id}/tags/{tag_id}
fe: 10_pdf_layer.jsx, 25_detail.jsx, 25b_tags.jsx
-->

# ROUTE 20 - Tags and tag filters

**Tier:** 1 local-stateful
**Goal:** Exercise global tag browsing, library tag filters, per-paper tag add/remove, and local suggested tags.

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

1. Load the library and open the **Tags tab** — the second tab of the **AXES** section in the left (THEORY) pane
   (inc 139: Tags is a tab, not its own section). Confirm `/tags` counts match visible seeded filters.
2. Filter by a tag. Confirm the paper list updates, empty states are explicit, and counts do not imply ranking or quality.
3. Open a paper detail pane. Add a new tag (`POST /papers/{paper_id}/tags`); confirm the chip appears in detail and the global tag panel (the AXES → Tags tab) without switching papers.
4. Add the same tag again by rapid double-submit. Confirm idempotent behavior or a clean duplicate message, never duplicate chips.
5. Request suggested tags (`GET /papers/{paper_id}/suggested-tags`). Confirm suggestions are local, exclude existing tags, and accepting one creates exactly one chip.
6. Remove a tag (`DELETE /papers/{paper_id}/tags/{tag_id}`). Confirm the chip disappears and orphaned tags are pruned from the global list. **inc 143 (Librarian):** removing an **imported keyword** tag (`keyword:*`, the muted chips) is **durable** — it is recorded as suppressed, so a later **🔎 re-resolve** / batch enrich does **not** silently re-add it (re-adding it by name clears the suppression). Removing a **user** tag does not suppress.
7. **Tag colors (inc 207, A5):** click a chip's color dot in the Details Tags row → a swatch popover (the palette from `GET /tags/colors`). Pick a color → `POST /tags/{tag_id}/color` sets it; the chip recolors and the sidebar Tags-tab row shows a color dot. Clearing (the × swatch) sends `color:null`. An invalid color → **422** (allowlist). **A color is a user label, NOT a rating/score** — there is no per-paper rating field anywhere (ratings were deliberately declined: a star reduces a paper to one dimension; tags stay orthogonal + inspectable). Confirm no UI presents a numeric paper rating.

## Pass criteria

- Tag create, suggest, filter, and remove flows complete through the UI.
- 0 console/page errors and 0 genai-host requests.
- Empty/duplicate/oversized input fails cleanly.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_20_tags.md` + `screenshots/` (see `_TEMPLATE.md`).

