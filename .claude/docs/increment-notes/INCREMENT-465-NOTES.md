# Increment 465 — Persistent, dismissible beyond-library saved queue (backlog #30's last open piece)

## Implemented

Second item in the confirmed post-P2 backlog sequence (memory `callosum-next5-backlog-roadmap`; item #1, the
scratch/ephemeral axis, was researched and declined as already-covered — see `INCREMENT-BACKLOG.md` §6).

Backlog #30 ("Highlight-to-suggest/evaluate") was mostly closed already: `app/backend/citations/
beyond_library.py` (inc 271/272) does OpenAlex/Semantic-Scholar/Crossref/PubMed beyond-library search from a
draft sentence, wired into both the web Cite pane and the LibreOffice adapter's "Suggest citations" dialog.
What was still explicitly flagged open: *"a persistent, dismissible cache surface in the `gaps.py` style — what's
shipped is a live, per-sentence, ephemeral flow."* A beyond-library suggestion you didn't act on immediately
(add or insert) was gone the moment you cleared the sentence or closed the dialog — no way to flag one as
"worth a second look later" and come back to it.

Confirmed with Cliff: the trigger is an **explicit "Save for later"** action (never automatic accumulation),
the review surface is a **new modal** (faithfully mirroring how "Gaps" itself is actually built — a modal
opened from a Discover → Search button, not a separate workspace tab), and **both surfaces** (web Cite pane and
the LibreOffice adapter) got the save action in this same pass.

### New table + backend router

`saved_beyond_library_suggestions` (`app/backend/persistence/schema_findings.py`, migration
`0070_saved_beyond_library_suggestions.py`) — one row per explicitly-saved suggestion, keyed by the suggestion's
own stable cross-provider `dedup_key` (`Item.dedup_key`, already `"doi:…"`/`"pmid:…"`/`"title:…"`). Unlike
`gap_candidates` (a whole-library citation-graph scan cached per `(direction, axis_id)` scope, wholesale-
replaced on Refresh), a beyond-library suggestion is inherently per-sentence — there's no "recompute" concept
here, only "remember this one candidate I explicitly flagged." `status` is a soft state
(`pending`/`dismissed`/`added`), never a hard delete — matches this codebase's consistent soft-delete-over-
hard-delete posture (the same reasoning that declined literal axis auto-expiry for item #1 of this sequence).

New `app/backend/api/routers/beyond_library_saved.py`: `POST /citations/beyond-library/save` (upsert by
`dedup_key` — a re-save after a dismiss returns it to the queue, an explicit, visible action, never a silent
resurrection), `GET /citations/beyond-library/saved` (read-time filtered against the live library, mirroring
`gaps_list`'s own filter), `POST .../add` (reuses `save_item`, the exact write path `/discovery/save`/`/gaps/add`
already use), `POST .../dismiss` (soft status flip). No egress anywhere in this router — the suggestion was
already fetched by the pre-existing `POST /citations/suggest`.

### Web frontend

`BeyondSaveForLaterButton` on every `BeyondSuggestionCard` (`37_cite.jsx`), alongside the existing "Add to
library"/"Source" actions. New `36c_beyond_library_saved.jsx`'s `BeyondLibrarySavedModal` — a slimmed
`GapsModal` clone (same `.axis-modal`/`.gap-row` shell, no direction/axis/Refresh controls) opened via a new
"Saved for later" button in Discover → Search, wired through `40_app.jsx`'s existing modal-state pattern
(`beyondSavedOpen`/`anyModalOpen`/`onOpenBeyondSaved`).

### LibreOffice adapter

New `save_beyond_library_item_for_later(base, item, source_query)` — a sibling to the existing
`save_beyond_library_item` (which posts to `/discovery/save` and adds outright; this one posts to
`/citations/beyond-library/save` and only queues). `_suggest_dialog` gained a non-closing **"Save for later"**
button — the exact same pattern the existing "Details…" button already established — operating on every
currently-selected `"beyond"`-kind row (library rows are skipped with an explanatory message, never silently
ignored). No new top-level menu command: reviewing/adding/dismissing the queue stays a web-app action
(Discover → Search → "Saved for later"), consistent with how this adapter has never duplicated read-heavy
review UIs the web app already owns.

## Key technical detail

**The real-UNO spike proved the button's callback LOGIC, not the click-to-callback wiring** — following the
exact precedent `spike_beyond_library_checkbox_listener` already established for this same dialog: a
programmatic UNO control mutation does not reliably fire the same event a real user click does, and there is no
headless way to synthesize a real click. The spike builds a minimal standalone dialog (never calling
`.execute()`, which would block), replicates `_SaveForLaterListener`'s exact logic, and invokes it directly —
proving the real end-to-end round trip against the real local server (no external network at all, since
`/citations/beyond-library/save` is purely local — mirroring `spike_save_beyond_library_item_and_cite`'s own
"no faking needed" reasoning), while the literal click-fires-listener wiring remains a manual-verification-only
question like every other dialog interaction in this adapter.

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-08-09_beyond-library-saved-queue.md` — 4 new endpoints,
  zero egress (statically confirmed by grep), unreachable via the cite-only cloudflared tunnel allowlist,
  bounded text fields (untrusted provider-shaped metadata, rule #4), soft-delete-only dismiss.
- **QA route**: new dedicated `route_89_beyond_library_saved.md` (mirroring `route_41_gaps.md`'s own precedent
  of a standalone route for a modal opened from Discover → Search, not folded into route_43); `route_42_cite.md`
  extended with the Save-for-later step + a new standing assertion. `build_surface_map.py check`:
  `392/392` API, `1645/1645` FE, 0 uncovered.
- `.claude/docs/INCREMENT-BACKLOG.md`: backlog #30's remaining piece marked **✅ CLOSED inc 465**.
- Memory `callosum-next5-backlog-roadmap` updated: item #2 closed, item #3 (credit-the-lineage backfill) next.
- `.claude/CLAUDE.md`: counter bumped to 465; pytest count updated to the actual measured total.

## Manual verification script

1. In Work → Cite, check "Also search beyond my library" and run a Suggest search that surfaces at least one
   beyond-library candidate.
2. Click **Save for later** on a card — confirm it becomes disabled reading "Saved for later" and nothing is
   added to the library or inserted.
3. Open Discover → Search → **Saved for later** — confirm the row shows the exact same title/reason/evidence/
   relationship label as the original card, plus the draft sentence it came from.
4. Click **Add** — confirm the paper appears in the library (metadata-only, no PDF) and the row disappears from
   the queue. Save a second suggestion and **Dismiss** it — confirm it disappears without touching the library.
5. In LibreOffice, run **Suggest citations…** with "Also search beyond my library" checked, select one or more
   beyond-library rows, click **Save for later**, confirm the confirmation message, then verify the same rows
   appear in the web app's Saved-for-later queue.

## Verification

- `pytest tests/test_beyond_library_saved.py tests/test_libreoffice_adapter.py tests/test_gapfinder.py
  tests/test_discovery.py -q` → **230 passed** (8 new backend tests, 6 new adapter tests, all UNO-free via
  monkeypatching; gap-finder/discovery included as a regression check on shared conventions).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: all application-source files within the 600-line cap
  (`40_app.jsx` is the closest watch item at 583/600 after this pass's small additions — not split this
  increment, but worth re-measuring before the next edit lands there).
- `alembic upgrade head` + `alembic check` against a fresh temp DB: migration applies cleanly, zero
  model/migration drift.
- `python tools/qa/build_surface_map.py check`: `392/392` API, `1645/1645` FE, 0 uncovered.
- Real-UNO: `python adapters/libreoffice/run_roundtrip.py` — the new `spike_beyond_library_save_for_later`
  proves the button logic end-to-end against the real local server (see the run's own output for the final
  pass/fail).

## Rollback

Revert the new router (`app/backend/api/routers/beyond_library_saved.py`, its mount in `app.py`), the new table
(`schema_findings.py` + migration `0070_saved_beyond_library_suggestions.py` — additive-only, safe to leave even
if reverted), the new frontend file (`36c_beyond_library_saved.jsx`) and its wiring in `37_cite.jsx`/
`30d_discover.jsx`/`04b_workspaces.jsx`/`40_app.jsx`, and the new adapter function/button in
`adapters/libreoffice/callosum_cite.py`, to their pre-465 state. All changes additive/backward-compatible; no
existing endpoint, table, or command was modified.
