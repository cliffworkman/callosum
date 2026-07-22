<!-- qa-coverage
api: /axes*
fe: 14_axes_edit.jsx, 15_axes.jsx, 15b_axis_card.jsx, 16_axes_merge.jsx, 17_axes_suggest.jsx
-->

# ROUTE 15 - Axes, assignments, merge, and suggestions

**Tier:** 1 local-stateful
**Goal:** Exhaust axis creation, editing, scoring, assignment correction, merge, and egress-gated suggestion controls without allowing unapproved genai traffic.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register console/pageerror/request listeners before navigating.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Curated axis is an Axis, never a "folder" (A7).** A curated axis is the umbrella "Axis" with a subtle cue (a 📌 by the label), never labeled "folder". It hides ALL scoring UI (no cutoff flipper / Score / 👁) and has no score/verdict — a hand-picked, hand-ordered set (manual members only). The keyword↔curated switch never loses members.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open the axes sidebar. Confirm existing axes render with assigned/uncertain counts and no rank/verdict language.
2. Create an axis with label + description (`POST /axes`). Confirm it appears immediately, reload, and confirm persistence.
3. Edit label and description (`PATCH /axes/{axis_id}`). Confirm stale state is shown until re-score, not silently hidden.
4. Run score (`POST /axes/{axis_id}/score`, `GET /axes/score/{job_id}`). Poll through pending/running/done. Navigate away during one run and return; no orphan spinner.
5. Open clusters (`GET /axes/{axis_id}/clusters`). Confirm assigned, uncertain, and manual statuses are visible as signals, never truth labels.
6. Add and remove a manual paper assignment (`POST/DELETE /axes/{axis_id}/papers...`). Confirm manual rows are marked and survive re-score.
   - **A10 (shown == summarized):** click an axis's count badge to filter the library (`GET /papers?axis_id=`). With the card's hide-uncertain (👁) view ON, the library filter must show the SAME set as the card — `axis_hide_uncertain=true` returns only assigned (confidence >= cutoff) + manual (NULL) papers, never the uncertain ones; the banner reads "… · assigned only". With hide OFF, every member shows. A library filter that disagrees with the card's shown count is a bug (the user would summarize papers the card hid).
   - **A6 (drag-to-add, inc 206):** drag a Library `.paper` card onto a (non-My-Pubs) `.axis` card — the card shows a `.drag-over` highlight, and the drop posts `POST /axes/{axis_id}/papers` (a manual override, `status:"manual"`), bumping the badge count. The **My Publications** axis is **not** a drop target (authorship is resolved, not dragged) — confirm a drop on it is a no-op. (HTML5 DnD: dispatch dragstart/dragover/drop with a shared DataTransfer handle.)
7. Open merge view (`16_axes_merge.jsx`). Merge two disposable axes (`POST /axes/merge`) and confirm the survivor has the combined label/description and assignments.
8. Open suggestion UI (`17_axes_suggest.jsx`). With egress unset, term suggestions and optimal-axis suggestions (`POST /axes/suggest-terms`, `POST /axes/suggest`, `GET /axes/suggest/{job_id}`) must fail closed with a clear egress-disabled message and no genai request.
9. Delete a disposable axis (`DELETE /axes/{axis_id}`). Confirm the UI removes it and a direct deep link to it handles 404 cleanly.
10. **Curated axis (A7, inc 211).** Create a curated axis via the **📌** toolbar button (`POST /axes {kind:"curated"}`) — confirm the card hides the scoring UI (no cutoff/Score/👁), shows the 📌 cue + a neutral count badge, and is never labeled "folder". Drag a Library `.paper` onto it (drop-to-add appends at the end). Reorder members by **dragging a member by its ⠿ grip** onto another (inc 212; HTML5 DnD via the `application/x-callosum-axismember` MIME → `PUT /axes/{axis_id}/order` — order persists across reload; foreign-id / non-curated → 422). The member-drag MIME is distinct from A6's `…-paper`, so dragging a member never triggers the card-level drop-to-add. **Freeze** a keyword axis (the **❄** action → `PATCH {kind:"curated"}`): its assigned + manual members are kept + ordered, uncertain ones dropped, scoring UI disappears — **no membership loss**. **Convert** back (the **↩** action → `PATCH {kind:"standard"}`, warned): members are kept, manual order lost, axis goes stale. A switch to/from `my_publications`, or a bad `kind`, → 422.

## Pass criteria

- Every declared surface is reachable and completable.
- 0 console errors / 0 page errors; no unexpected 4xx/5xx except deliberate validation/egress-disabled cases.
- No genai-host requests with egress unset.
- Axis counts and statuses remain signal-only; no composite quality verdict.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_15_axes.md` + `screenshots/` (see `_TEMPLATE.md`).
