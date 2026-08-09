<!-- qa-coverage
api: /citations/beyond-library/saved, /citations/beyond-library/add, /citations/beyond-library/dismiss
fe: 36c_beyond_library_saved.jsx
-->

# ROUTE 89 — Beyond-library saved queue (backlog #30's last open piece, inc 465)

**Tier:** 1 local-stateful
**Goal:** Exhaust the persistent, dismissible beyond-library suggestion queue opened via Discover → Search's
"Saved for later" button — a flat list (no direction/axis/Refresh, unlike Gaps: nothing here is recomputed,
only remembered) of suggestions explicitly flagged from Work → Cite (route 42's own "Save for later" button,
`POST /citations/beyond-library/save`) — with **Add** (metadata-only import, matching the `save_item` write
path `/discovery/save`/`/gaps/add` already use) and **Dismiss** (soft-hides, never a hard delete). This route
covers the queue's own read/add/dismiss surface; the save action itself is route 42's.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** Register listeners before navigation.

**Seed note:** this surface has no external-provider call at all (unlike Gaps/beyond-library search itself) —
seed directly via `POST /citations/beyond-library/save` with a fabricated suggestion payload (title/doi/
reason/evidence_text/relationship_label/source_query), then drive the modal against that real row. No fake
client injection needed.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** — this whole surface
  is local DB read/write only (the suggestion was already fetched elsewhere; nothing here re-fetches).
- **Candidates not verdicts.** Nothing is auto-added; each row has **Add** + **Dismiss**; the human decides.
  Explicit-save-only (route 42's own standing assertion) — this route never itself adds a row to the queue.
- **Verbatim, not re-derived.** A saved row's title/authors/abstract/reason/evidence/relationship must match
  exactly what the original suggestion card showed — no re-fetch, no drift, no new signal computed here.
- **Read-time in-library filter.** A saved row whose DOI now resolves to a live library paper (added via ANY
  path, not just this queue's own Add) must disappear from the list without needing a Dismiss click.
- **Add = metadata-only into the general library; no PDF** (the OA-acquire lane is untouched). Dismiss removes
  it from this list only — it must never touch the library.

## Adversarial checklist

- Save the same suggestion twice (same dedup_key) → one row, not two (upsert, not a duplicate)
- Add a saved row → it drops from the list; re-fetch confirms it's now a real library paper
- Dismiss a saved row → it drops; confirm `GET /papers` gained nothing
- Add or Dismiss an unknown/already-consumed dedup_key → 404, no crash
- A row whose DOI is added to the library through an unrelated path (e.g. Discover → Search's own Save) also
  disappears from this queue on next open, without a Dismiss click
- double-click Add / Dismiss; resize to `375x812` → no horizontal overflow

## Steps

1. Seed one saved suggestion via `POST /citations/beyond-library/save` (a real title/doi/reason/evidence/
   relationship_label/source_query payload).
2. Open Discover → Search → **Saved for later** → the modal. Confirm the row renders the title, authors/year/
   journal, the relationship label or reason, and the `source_query` sentence it came from ("from: “…”").
3. **Add** the row → confirm `POST /citations/beyond-library/add` fires, the row drops from the list, and the
   paper now appears in `GET /papers` with no attachment/PDF.
4. Seed a second suggestion, open the modal, **Dismiss** it → confirm `POST /citations/beyond-library/dismiss`
   fires, the row drops, and `GET /papers` gained nothing.
5. Seed a third suggestion whose DOI matches an existing (or freshly-added) library paper → confirm it never
   appears in the list at all (read-time filter), without needing an explicit Dismiss.
6. Save the identical dedup_key twice → confirm exactly one row exists (upsert, not duplicated).
7. Adversarial: Add/Dismiss an unknown dedup_key → 404 surfaced cleanly, no crash; mobile viewport has no
   horizontal overflow; **0** genai-host requests throughout.

## Pass criteria

- The queue lists exactly the explicitly-saved, still-pending, not-yet-in-library rows, each with its original
  evidence intact and Add/Dismiss actions.
- Add imports metadata-only and removes the row; Dismiss removes the row without touching the library; both are
  idempotent-safe against a re-click and fail closed (404) on an unknown identity.
- Re-saving the same suggestion never duplicates a row.
- 0 console/page errors; **0 genai-host requests**; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_89_beyond_library_saved.md` + `screenshots/` (see `_TEMPLATE.md`).
