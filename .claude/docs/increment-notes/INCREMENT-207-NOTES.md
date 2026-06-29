# Increment 207 — A5: color tags (no ratings) + split TagsRow → 25b_tags.jsx

## Implemented

The fifth close-out of the cheapest-first wrap-up pass, and the first migration-bearing one. **A5 was scoped down to
color tags only — ratings were deliberately declined** (Cliff): a unidimensional star reduces a paper to one number,
erasing the multi-dimensionality tags capture ("I'd give bad science 5 stars for teachability"). This coheres with the
charter (#7 no opaque composite, inspectability over authority) — tags stay the orthogonal, inspectable judgment.

**Backend**
- **Migration 0024** (additive, guarded, mirrors 0003): a nullable `color` column on `tags`. Head via `alembic_head()`.
- **`tags_repo.py`:** a fixed **`TAG_COLORS`** palette (`red/orange/amber/green/teal/blue/purple/gray`) — a tag stores
  a palette **key**, never arbitrary hex (rule #3/#4); `set_tag_color(tag_id, color)` (UPDATE; returns the row or None);
  `color` added to `get_tags_for_paper`/`list_tags`/`add_tag_to_paper` reads.
- **`routers/tags.py`:** `color` on `TagRef`/`TagSummary`; **`GET /tags/colors`** (the palette) + **`POST /tags/{tag_id}/color`**
  `{color}` (validate color ∈ `TAG_COLORS` ∪ {null} → 422; 404 if no tag; set + commit). `PaperTagRef` (papers.py) +
  `_paper_detail` carry `color` too.

**Frontend**
- A fixed **8-key palette** as theme-aware CSS tokens (`--tag-<key>`, light in `:root` + lighter dark overrides). The
  colored-chip recipe sets `--tag-c` via `.tag-color-<key>` and **`color-mix(in srgb, var(--tag-c) 16%, var(--panel))`**
  for the fill → auto-adapts to light/dark. A colored chip **overrides** the inc-100 provenance styling (uncolored
  keeps it). DESIGN.md records the recipe (rule #8).
- A **swatch popover** off each chip's color dot in the Details Tags row (8 swatches + a "none" ×); the sidebar Tags
  tab renders a matching color dot.

**Rule #1 split (forced):** the color picker pushed `25_detail.jsx` to **609/600** (it was the watched closest at
584). Extracted **`TagsRow` → `js/25b_tags.jsx`** verbatim (self-contained; the inc-176 precedent) → 25_detail.jsx
**522**, 25b_tags.jsx 95. `DetailContent` calls it via the shared-IIFE function hoist (chunk order is irrelevant for a
hoisted declaration). `route_20`'s `fe:` claim gained `25b_tags.jsx`.

## Key technical detail

A tag stores a palette **key**, not a hex — so theming is a token lookup (`--tag-blue`) and the value is allowlist-
validated at the write boundary (no arbitrary CSS/value injection). `color-mix` lets one ink token per key produce a
legible soft fill on both the light and dark `--panel` with a single recipe. The migration mirrors 0003's guarded
pattern (fresh DB → `create_all` already has `color` → no-op; existing DB → ADD COLUMN).

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_tags.py -q` → 10 passed, incl. the new
`test_set_tag_color_endpoint_and_responses` (palette exposed; set valid → reflected in `/tags` + the paper detail +
a re-add; invalid `#ff0000` → 422 with the stored color unchanged; clear via null; unknown tag → 404).
**Headed (no egress):** `.local/visual/drive_inc207_tag_color.py` — seed a paper + tag, open Details, click the chip's
color dot → swatch popover → pick blue → the chip recolors (`tag-color-blue`) and `POST /tags/{id}/color` persists it
(`GET /tags` shows blue); re-run after the TagsRow extraction confirms it's behavior-preserving. 0 console/page/genai.

## Gates

- **pytest:** full suite green — **714 passed, 1 skipped** (+1 `tests/test_tags.py`).
- **ruff** check + format clean; frontend rebuilt; migration head **0024** via `alembic_head()`.
- **QA surface** — **138/138 API** (+2: `/tags/colors`, `/tags/{id}/color`) **+ 667/667 FE, 0 uncovered**;
  `route_20_tags.md` claims the 2 endpoints + `25b_tags.jsx` + a color step + the **no-rating** assertion.
- **Audit:** none triggered (a color column + 2 local endpoints; no egress/fetch/dependency). **Principles:** the
  declined-ratings decision *is* the principle pass (#7 / inspectability); a color is a user label, not a score.
- **DESIGN.md** records the tag-color palette + recipe (rule #8). **Help corpus** gained a "Coloring a tag" paragraph +
  the no-rating framing (`HELP-DOCS-SYNCED` → 207).

## NEXT (continuing the cheapest-first close-out)

**Inc 208 — A1** saved searches (persist a named bundle of the existing facets — item_type/axis/tag/needs-review/signal
+ sort + search-scope — recalled from the library header; a `saved_searches` table; distinct from axes — a metadata
predicate, not a semantic lens). Then **A3** full-text FTS5 search (migration + a security audit), **A2** citation
counts, and **A7 Curated Axis** (its own design pass). **Rule-#1 watch:** `10_pdf_layer.jsx` 565, `papers.py` 568,
`30_viewer.jsx` 557 — all under 600 but closest.
