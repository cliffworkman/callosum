<!-- qa-coverage
api: /references/resolve
fe: 30h_reference_finder.jsx, 30g_pdf_selection.jsx
-->

# ROUTE 94 — Reader "Find referenced paper…" (selection → resolve → add)

**Tier:** 2 external (Crossref metadata)
**Goal:** Exercise the in-reader reference-lookup flow end to end — select a cited reference in the PDF →
the selection popover's **🔎 find paper** action (`30g_pdf_selection.jsx` `SelectionPicker`) → the
`ReferenceFinderModal` (`30h_reference_finder.jsx`) → `POST /references/resolve` (DOI-first, else Crossref
`query.bibliographic`, gated by inspectable title/author/year agreement) → confirm a candidate → the EXISTING
canonical add + OA path (`POST /discovery/save` then `POST /papers/{id}/acquire-oa`). Transient: **no highlight
or annotation is created**. Public bibliographic lookup — **never** the Gemini library-text gate. Inc 595.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never
fire; Crossref metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the resolver hits the real Crossref network. To exercise offline + deterministically, inject
`app.state.crossref_client` with a fake whose `resolve_doi` returns a fixed `CrossrefResolution` (DOI path),
and monkeypatch `app.backend.metadata.reference_resolver.bibliographic_search` for the free-text path — mirror
`tests/test_reference_lookup.py`. Seed one library paper whose DOI matches a candidate so `in_library` is true.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **Egress gate (Critical).** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** — this
  is public bibliographic lookup (Crossref), never the library-text gate. A reference string is bibliographic
  metadata (the same posture as Discover → Search), not gated library text.
- **Explicit egress only.** `POST /references/resolve` fires **only** on the explicit **🔎 find paper** click
  (which opens the modal + runs one lookup) or the modal's **Look up** button — **never** on selecting or
  highlighting text. Selecting text and NOT clicking must produce **0** `/references/resolve` requests.
- **Four inspectable states, no confidence score.** `classification` ∈
  `identifier_match | one_candidate | multiple_candidates | none`. A DOI in the selection → `identifier_match`
  (exact). Free-text results are candidates. `error` (separate from `none`) means the lookup could not
  **complete** (Crossref unreachable) — distinct from "completed, nothing plausible". No numeric/opaque
  confidence is shown anywhere.
- **Never silently choose.** `multiple_candidates` shows a chooser with **no** pre-selection; a candidate is
  added only on an explicit **Add to library** click. `none` says so ("No defensible match") and offers the
  editable text + **Look up again** — it never invents a match.
- **Already in library → surface, never duplicate.** A candidate whose identity matches a live paper renders
  **✓ In your library** + **Open** (no Add button). Confirming any candidate routes through the deduped
  `POST /discovery/save`, so a racing/duplicate save returns the same `paper_id` with `created:false`.
- **Transient — no persistence.** The flow creates **no** annotation/highlight; `GET /papers/{id}/annotations`
  is unchanged by a lookup. The modal snapshots the selected text at open (a later selection change or a stale
  in-flight response never alters the shown result).
- **OA failure ≠ add failure.** On confirm, `POST /discovery/save` creates the metadata paper first; a failed
  `POST /papers/{id}/acquire-oa` shows "No open-access copy was available — the record was still added" and the
  paper remains present in `GET /papers`.
- **Fail closed.** Blank/oversized `text` → 422; a Crossref transport error → `error` set, **zero** papers
  created.

## Adversarial checklist

- Select a reference, do **not** click → **0** `/references/resolve` requests
- Click **🔎 find paper** → exactly one `/references/resolve`; DOI selection → `identifier_match`, one candidate
- Full citation string → `one_candidate` / `multiple_candidates`; ordinary prose → `none` (agreement gate)
- Ambiguous selection → `multiple_candidates`, nothing pre-selected, nothing added without a click
- A candidate already in the library → **✓ In your library** + **Open**, no Add, no duplicate on `/papers`
- Add a novel candidate → `POST /discovery/save {created:true}` then `POST /papers/{id}/acquire-oa`; a failing
  OA fetch leaves the paper present
- Blank `text` → 422; `text` > 2000 chars → 422; Crossref error → human-readable `error`, 0 papers created
- **0** genai-host requests throughout; no annotation created by the flow

## Steps

1. Open a seeded paper in the reader; select a reference-looking span of text. Confirm the popover shows
   **🔎 find paper** beside the highlight controls, and that selecting alone issues **0** `/references/resolve`.
2. Click **🔎 find paper** → the modal opens and runs one lookup. With a DOI in the selection (fake
   `resolve_doi`), confirm `classification:"identifier_match"` and a single candidate with title/authors/year/
   venue/DOI, **no** `abstract` field (minimal contract).
3. Edit the text to a full citation string (monkeypatched `bibliographic_search` returning 2 plausible items)
   and click **Look up** → `multiple_candidates`; confirm no candidate is pre-selected.
4. Point the fake at an in-library DOI → confirm **✓ In your library** + **Open** (Open switches to that paper's
   reader tab), and **no** Add button.
5. Add a novel candidate → confirm `POST /discovery/save {created:true}` then `POST /papers/{id}/acquire-oa`;
   `GET /papers` shows the new `discovery-import` paper with no duplicate. Re-confirm the same identity →
   `created:false`, same id.
6. Force the free-text fetch to raise → confirm the modal shows a human-readable error and `GET /papers` count
   is unchanged (zero mutation).
7. Adversarial: blank/oversized `text` → 422; **0** genai-host requests; no annotation created by the flow.

## Pass criteria

- The lookup fires only on explicit clicks; selection alone never egresses.
- The four classifications behave per the assertions; no opaque confidence; ambiguity never auto-picks.
- Confirm reuses the canonical deduped add + OA path; OA failure never undoes the add; already-in-library is
  surfaced, not duplicated; the flow creates no annotation.
- Bad inputs / transport errors fail closed (422 / `error`, zero mutation); **0** genai-host requests.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_94_reference_lookup.md` + `screenshots/` (see `_TEMPLATE.md`).
