# Increment 71 Notes — Tags (per-paper labels + filter the library by tag)

Lightweight free-form **tags** — the manual-label complement to callosum's heavyweight semantic **axes**.
The `tags`/`paper_tags` tables already existed (the Zotero importer populates them via `_upsert_tags`), so
imported papers may have carried **invisible** tags; now you can view, add, remove, and filter by them. **No
migration.** (User scoped this to **Details-pane-only**; a sidebar tag browser is deferred.)

## Implemented
- **New `app/backend/persistence/tags_repo.py`** (cohesive data access, split out so `repository.py` stays
  < 600 — mirrors inc-67's `dedup_repo.py`): `get_tags_for_paper` (`paper_tags ⨝ tags`, name-sorted),
  `list_tags` (all tags + `paper_count` via LEFT JOIN — powers autocomplete), `add_tag_to_paper`
  (trim/cap 100; **get-or-create** by UNIQUE name; `INSERT OR IGNORE` the link → idempotent),
  `remove_tag_from_paper` (unlink; **prune the orphan tag** if no papers remain). All bound-param.
- **`repository.list_papers(..., tag_id=None)`** — a bound-param `IN` subquery over `paper_tags` (mirrors the
  inc-63 `axis_id` branch; composes with q/deleted/sort; trashed excluded).
- **`routers/papers.py`** — `PaperDetailResponse.tags: list[PaperTagRef]` (populated in `paper_detail` +
  `_detail_for` via `get_tags_for_paper`) + a `tag_id` Query param on `GET /papers`.
- **New `routers/tags.py`** — `GET /tags` (`{id, name, paper_count}`), `POST /papers/{id}/tags {name}` (404
  missing paper / 422 blank / 201), `DELETE /papers/{id}/tags/{tag_id}` (404 if not linked / 204). Registered
  in `app.py`.
- **Frontend:**
  - `25_detail.jsx` `TagsRow` (after the Abstract; **keyed by paper id** so it resets on paper switch): the
    paper's tags as `.tag-chip` pills — the **name** click → `onFilterToTag`, a **×** → DELETE — plus an add
    `<input list="tag-suggestions">` (Enter/blur → POST) with a `<datalist>` from `GET /tags`. Optimistic
    local update (idempotent backend makes the Enter+blur double-fire harmless). `onFilterToTag` threaded
    App → RightPane → DetailContent (alongside `onOpenPaper`).
  - `40_app.jsx` — `libraryTagFilter` `{id, name}` + `filterToTag`/`clearTagFilter` (mirror the inc-63 axis
    filter; **mutually exclusive** with the axis filter — each clears the other, as do trash/focus); the
    `/papers` fetch adds `&tag_id=` (+ dep).
  - `10_pdf_layer.jsx` — a "Filtered to tag …" banner (reuses the `.focus-card` recipe). `styles.css` —
    `.detail-tags*` + `.tag-chip*` (token-based pill). Rebuilt `callosum-app.html`.

**No migration, no egress, no new dependency.** repository.py 591 / papers.py 565 / tags_repo.py 65 /
tags.py 60 — all < 600.

## Verification
- **pytest 248** (+4, `tests/test_tags.py`): add/get/dedupe/idempotent; remove + **orphan prune** + not-linked;
  `list_papers(tag_id=)` composes with q + excludes trashed; the endpoints (201 add + in-detail, idempotent,
  422 blank, 404 unknown paper, `GET /tags` counts, `?tag_id=` filter, 204 delete + 404 re-delete).
  Route-surface invariant += `/tags`, `/papers/{paper_id}/tags`, `/papers/{paper_id}/tags/{tag_id}`.
- **Live E2E** (`.local/tags_e2e/`): add "method" (chip + datalist) → click it → "Filtered to tag method" +
  the library narrows 2→1 → clear (2 again) → **×** removes the chip. **0 console errors.**
- Audit `.claude/security-audits/2026-06-20_tags.md` — **PASS** (local, non-destructive, bound-param, name
  validated + rendered as text).

## Manual verification script
1. Click a paper → Details → the **Tags** row. Type a tag + Enter (autocomplete suggests existing tags).
2. Click a tag chip's name → the library filters to it ("Filtered to tag …" banner) → **clear**.
3. **×** a chip to remove it. Imported Zotero tags now appear on those papers.

## Next / deferred
- **Inc 72 (chosen next):** **auto-suggest tags** per paper — local c-TF-IDF over the paper's tokens vs the
  library (the per-paper analogue of inc-52's axis suggester), **purely local, no Gemini** (user's call);
  candidate term chips the user curates → added via this increment's tag-add path.
- Deferred: a **sidebar Tags browser** (all tags + counts); bulk-tagging from the library selection;
  rename/merge tags; collections (the hierarchical Zotero folders — tables exist, out of scope).
