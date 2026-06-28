# Increment 184 — Literature discovery SP1 frontend: the Discover (Search) tab

The frontend half of backlog #28 SP1 (the backend — registry + Crossref + `GET /discovery/search` + `POST
/discovery/save` — was inc 183). Brings the Search tab into the center library-frame, on the LibraryFrame tab system.

Design spec: `.claude/docs/specs/2026-06-28-discovery-search-design.md` (Frontend section).

## Implemented

- **`app/frontend/js/30d_discover.jsx`** (NEW) — `DiscoverPane({ onSaved })`:
  - A query box (reuses `.searchbar input` + `.btn-primary`) → `api(/discovery/search?q=&limit=25)` → result rows.
  - Each row (`.discover-item`): serif title, `.paper-meta` (authors[≤3]+et al. / year / journal), source pill(s)
    (`.discover-source`), and either a **Save** `.btn-link` or a green **✓ in library** marker (`.discover-inlib`);
    an **Abstract** toggle expands `.discover-abstract`.
  - **Keyboard triage:** `onKeyDown` on the pane — Enter *in the input* searches; otherwise **j/k** (or arrows) move
    the cursor (`.discover-item.cur`, scrolled into view), **s** saves the focused row, **Enter** toggles its abstract.
  - **Save** = `apiPost(/discovery/save, {title, doi, abstract, authors, journal, year, url})` → flips the row to ✓
    in library (no double-save) + calls `onSaved()`.
  - Empty/idle/error states; **the complete list is always rendered** (no client-side filter — augment-never-filter).
- **`app/frontend/js/30c_frame.jsx`** — a persistent **Discover** tab (beside Library) + a `frame-pane` shown when
  `activeTab === "search"` rendering `<DiscoverPane onSaved={onDiscoverSaved} />`. New `onDiscoverSaved` prop.
- **`app/frontend/js/40_app.jsx`** — passes `onDiscoverSaved={() => setLibRefresh(n => n + 1)}` so a saved paper
  appears in the Library tab. (`activeTab` already free-form; "search" needs no extra state.)
- **`app/frontend/styles.css`** — a `.discover-*` block (DESIGN rule #8): mirrors the `.paper` card recipe + reuses
  `--sel`/`--hover`/`--verified`/`--radius-pill`/`--mono` etc. — **tokens only**, no new hex.
- **`app/backend/help/help_content.md`** — new "Finding new papers (Discover)" section; "Highlights and notes" brought
  current for the inc 175–179 reading-pane run (Notes search/Noted filter, Copy/Export, ◂/▸ mark nav + [ / ] keys,
  remembered scroll). `HELP-DOCS-SYNCED` → 184.

## Key technical detail

- **Function-hoist across chunks:** `DiscoverPane` is a top-level `function` in `30d_discover.jsx`; `LibraryFrame`
  (30c) references it. The esbuild IIFE hoists top-level function declarations, so chunk order is irrelevant — the
  inc-182/30c precedent (raw-assembly inclusion + a successful build is the gate, not chunk order).
- **Augment-never-filter is structural:** the pane renders every item the endpoint returns, in order; there is no
  client-side relevance filter/reorder (SP1b's axis-relevance highlight will *mark* likely matches without hiding any).

## Manual verification script

Headed, no egress (a fake registry injected via a throwaway server module):

```
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python .local/visual/drive_inc184_discover.py
```

→ seeds a library paper (DOI 10.1/inlib), serves `create_app(discovery_registry=<fake 3 items>)`, opens the Discover
tab, searches → **3 rows** (complete list), **1 ✓-in-library + 2 Save**, **j** moves the cursor to row 1, **Save** row
0 → it flips to ✓ in library, switch to Library → the saved "Attention Is All You Need" appears. **0
console/page/genai. PASS.**

## Gates

- **pytest 634** unchanged (frontend-only; `test_frontend_assembly` 5/5 confirms `30d_discover.jsx` is in the build +
  `callosum-app.html` in sync). `ruff` n/a (no Python). Build green.
- **QA (rule #10):** `route_43_discovery.md` gained `fe: 30d_discover.jsx` + the UI flow → surface **123/123 API +
  631/631 FE, 0 uncovered**.
- **Principles:** non-triggering — discovery search returns the complete list (augment, never filter); save is
  metadata-only + the human decides; no claim/judgment. (Values: public-metadata egress + no PDF fetch / no paywall
  circumvention — already covered by the inc-183 audit; no new endpoint/egress here.)
- **No backend change, no migration, no new dependency.**

## NEXT

- **SP1a:** a PubMed provider (a new NCBI E-utilities httpx client + its own audit) — `register()` one provider, no UI
  edit.
- **SP1b:** the axis-relevance highlight — score each item against the user's axis embeddings; **highlight** likely
  matches within the complete list (a hint on Save), never hide/filter/reorder.
- **SP2:** the Feed tab (subscriptions + polling + a read/unread store; bioRxiv by category).
