# Increment 100 — statcheck "flagged" header chip + tag-source aesthetic differentiation

A "2 chores" half-patter (the carrot, a distraction-free **Reading mode**, follows separately). Both chores
surface existing data more legibly — no new data, no migration, no egress.

## Implemented

### Chore 1 — a "⚠ N flagged" chip in the Library header
The inc-97 library-wide statcheck filter was only reachable from **⚙ Settings → Show flagged papers**. Now,
when the last batch run flagged any papers, a **`⚠ N flagged`** chip appears in the Library header as a direct
shortcut to that same filter.

- **`persistence/signals_repo.py`** — new `count_statcheck_flagged(conn)` counts `open_science_signals` rows with
  `signal_type="statcheck"` and `status="inconsistent"` (the per-paper summaries inc-97 persists).
- **`routers/methods.py`** — new `GET /methods/statcheck/summary` → `StatcheckLibrarySummary{flagged}` (sync,
  read-only; cache-only count, no run).
- **`40_app.jsx`** — a `statcheckFlagged` state, fetched on mount + whenever Settings closes (a batch run happens in
  Settings, so closing it refreshes the count); threaded into the library props with `onShowStatcheckFlagged`
  (reuses the inc-97 `showStatcheckFlagged` → `setLibrarySignalFilter("statcheck-inconsistent")`).
- **`10_pdf_layer.jsx`** — the chip (a `.trash-toggle.statcheck-chip`), shown only outside Trash, only when
  `flagged > 0`, and only when not already viewing the flagged filter (so it doesn't duplicate the active banner).
- **`styles.css`** — `.statcheck-chip { color: var(--flag); font-weight: 600; }` (amber = status, per DESIGN.md;
  no new token/hex).

### Chore 2 — tell imported keyword tags from your own, by style not by label
The user asked to distinguish tags from different sources **aesthetically**, to avoid cluttering the Details pane
with source labels. So the `import_source` already stored on each tag (inc 73) is now exposed on the API and
drives a **muted visual style** + a **source tooltip** — no extra on-screen text.

- **`persistence/tags_repo.py`** — `get_tags_for_paper`, `list_tags`, and the two get/create selects in
  `add_tag_to_paper` now return `tags.c.import_source`.
- **`routers/papers.py`** — `PaperTagRef` gained `source`; `_paper_detail` maps it from `import_source`.
- **`routers/tags.py`** — `TagRef` + `TagSummary` gained `source`; `list_all_tags` and `add_paper_tag` populate it.
- **`00_lib.jsx`** — `tagIsImported(source)` (`source && source !== "user"`) + `tagSourceLabel(source)` (maps
  `keyword:crossref` / `keyword:openalex` / `keyword:pubmed` / `zotero` / user / other → a human tooltip).
- **`25_detail.jsx`** (Details `TagsRow`) + **`10_pdf_layer.jsx`** (sidebar `TagsPanel`) — add
  `tag-chip-imported` / `tags-panel-item-imported` classes + the source tooltip on each chip/item.
- **`styles.css`** — imported tags get a neutral border + muted text (`--line-2`/`--bg`/`--ink-2`/`--ink-3`) vs the
  user's accent-colored `.tag-chip`; behavior (click-to-filter, ×-to-remove) is identical.

## Key technical detail
Both chores are **read-only projections of already-persisted facts** — the statcheck chip counts the inc-97
`open_science_signals` summaries; the tag styling reads the inc-73 `import_source` column. No migration, no
egress, no LLM. The tag `source` field is additive on the existing tag responses (default `None`), so older
callers are unaffected. The statcheck count is cache-only (it never triggers a run — the inc-97 batch endpoint
stays the only persister).

**Principles note (rule #9):** neither chore makes a new claim. The statcheck chip is a more prominent door to
the inc-97 **filter** (still a list-to-review, never a rank/score/verdict — the no-accusation boundary holds);
the tag styling is provenance made visible (it strengthens the inc-73 fact-vs-candidate distinction by showing
where a label came from), aligned with "inspectability over authority."

## Manual verification script
1. `⚙ Settings → Statistics check → Check all papers`; close Settings → a **⚠ N flagged** chip appears in the
   Library header (if any paper has an inconsistency). Click it → the library filters to the flagged papers + the
   inc-97 banner; the chip hides while that filter is active; **clear** restores both.
2. Open a paper with both a typed tag and an imported keyword (e.g. a Crossref-resolved paper): in Details, the
   imported keyword chips read in a muted/neutral style, your own tags keep the accent color; hover each → the
   tooltip names the source. Same in the sidebar **Tags** panel. Clicking either still filters; **×** still removes.

## Pytest
**411 passed, 1 skipped** (+1: `test_tags.py::test_tag_source_exposed_on_responses`; the statcheck-summary
assertion folded into `test_statcheck.py::test_statcheck_batch_run_then_filter`; `/methods/statcheck/summary`
added to the `test_health.py` route allowlist). `ruff` clean; `callosum-app.html` rebuilt; help corpus's tags +
statcheck sections updated (`HELP-DOCS-SYNCED` → 100).
