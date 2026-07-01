<!-- qa-coverage
api: GET /papers/{paper_id}, PATCH /papers/{paper_id}, POST /papers/{paper_id}/re-resolve, GET /papers/{paper_id}/suggested-tags, POST /papers/{paper_id}/tags, DELETE /papers/{paper_id}/tags/{tag_id}, POST /papers/export, POST /citations/render
fe: 24_detail_fields.jsx, 25_detail.jsx
-->

<!-- B5 SP2 (inc 238): the inline-editable field primitives (EditableRow/EditableText/TypeSelect/IdentifierRow) live
in 24_detail_fields.jsx (split from 25_detail.jsx, rule #1). On a read-only companion they render as static text and
the write controls (Fill / re-resolve / +Queue / OCR / tag add-remove) are hidden — see readOnly threading + the
`/health.read_only` flag. -->


# ROUTE 30 — Editable Detail pane (bibliographic edit, tags, DOI re-resolve, cite)

**Tier:** 1 local-stateful (mutating against the throwaway DB — fine to mutate freely)
**Goal:** Exhaust every editable field and action in the Details pane (`25_detail.jsx`) — the Mendeley-style
inline editor — and assert edits persist correctly, the user-edited guard holds, and the honesty invariants
are honored on the cite surface. (Statcheck moved to the METHODS "Statistics check" section in inc 122 — see
route_33.)

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (re-resolve hits public Crossref,
which is metadata egress, NOT the Gemini gate — but assert no genai host is contacted). Listeners registered.

## Standing assertions

All of `_TEMPLATE.md` → Standing assertions. Specifically here:
- **Egress gate:** editing/saving/cite must contact **no** genai host. (Re-resolve may contact a
  Crossref host; that is allowed. A Gemini host is **Critical**.)

## Steps

1. Open a seeded paper; screenshot the Details pane. Confirm core fields (title, authors, year, venue, DOI)
   and the collapsible **Identifiers** + **More** sections render.
2. **Inline edit + persist** (`PATCH /papers/{id}`): edit the title, blur to auto-save, reload, confirm it
   persisted. Repeat for year and venue. Confirm the change appears in the library card too.
3. **More → + add field:** add an arbitrary CSL field (e.g. `publisher`); confirm it saves and re-renders.
   Try a reserved/core key and a non-letter-led key — confirm a clean 422-style rejection, not a crash.
4. **User-edited guard:** after a hand-edit, confirm the paper is marked `user-edited` (it should now be
   skipped by batch enrich — verify it is NOT silently clobbered if you trigger a library enrich).
5. **Identifier re-fetch** (`POST /papers/{id}/re-resolve {source}`, inc 226): each of **DOI / PMID / ArXiv ID**
   has its own 🔎 (`IdentifierRow`) that force-re-fetches the record from that source — DOI→Crossref (default
   source, back-compat), PMID→PubMed-via-OpenAlex, arXiv→the arXiv DOI via OpenAlex (public metadata, NOT the
   Gemini gate). Correct/replace the identifier, trigger its 🔎 → confirm the record overwrites (or a graceful
   miss leaves the record unchanged, never a 500/crash). **422** if that identifier is absent. A DOI-UNIQUE clash
   surfaces a 409-style message, not a crash. ISBN/ISSN/Cite-key stay plain (no per-paper source).
6. **Tags** (`/suggested-tags`, `POST/DELETE …/tags`): add a tag; confirm the chip appears without a paper
   switch; click ✨ Suggest, accept a candidate; remove a tag; confirm the orphan tag is pruned.
7. **Cite** (`POST /citations/render`): open "Cite as…", switch styles, confirm a live formatted preview +
   copy. Trigger the bulk "bibliography…" `.html` export and the per-paper BibTeX copy
   (`POST /papers/export`). Confirm the downloaded/copied output is well-formed for the chosen style.

## Adversarial

- Paste ~50KB into the title and into a new "More" field; confirm a sane cap/error, not a hang.
- Blur an empty title (should reject — empty title is 422-class).
- Double-click 🔎 re-resolve; navigate away mid-fetch — confirm no orphaned spinner / no console error.
- Add the same tag twice — confirm idempotent (no duplicate chip).

## Pass criteria

- Every edit persists and projects to the library card; the user-edited guard holds.
- Re-resolve, tags, cite all complete through the UI; 0 console/page errors.
- 0 genai-host requests; citations render per style.
- Adversarial inputs fail closed (clean rejection), never crash.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_30_detail_pane.md` + `screenshots/` (see `_TEMPLATE.md`).
