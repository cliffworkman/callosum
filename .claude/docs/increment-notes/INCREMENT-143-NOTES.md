# Increment 143 — Deleting an imported keyword tag is durable (Librarian ↔ backlog #3)

## Experience pass (rule #11)

**Persona:** the **Librarian** (curating an established library — fixing metadata, organizing tags — who must
trust curation is non-destructive). A dispatched persona agent drove the Details-edit + tags + 🔎 re-resolve flow.
**Found:** the good news — tags don't *duplicate* (`add_tag_to_paper` is get-or-create + `INSERT OR IGNORE`), and
imported-vs-typed is distinguishable (muted vs accent + a source tooltip). **The one real gap:** deleting an
imported keyword tag is **not durable** — `apply_crossref_subject_tags` re-adds *every* `subject` unconditionally,
so the very button a librarian reaches for to *clean up* a record (🔎 re-resolve) silently **resurrects** a keyword
they deliberately removed, with no memory of the deletion. Verdict: *trusts it not to lose/pile up tags, but not to
honor a deliberate keyword removal.* (4th persona run → 4th real, specific gap.)

## Implemented

Persist a per-paper **suppressed-keyword** set so a deleted imported keyword stays gone across re-resolve / backfill
— the tag analogue of the inc-49 user-edit guard. Backend-only:

- **`suppressed_paper_tags` table** (migration **0020**, additive/guarded): `(paper_id, tag_name)` — names only (the
  tag row is pruned on delete, so we can't key by id).
- **`tags_repo`:** `suppress_paper_tag` / `unsuppress_paper_tag` / `suppressed_tag_names`. `remove_tag_from_paper`
  now reads the removed tag's `(name, import_source)` *before* pruning and, if it's an imported `keyword:*` tag,
  records a suppression. `add_tag_to_paper` **clears** the suppression for that name (re-adding means the user wants
  it again).
- **`enrichment.apply_crossref_subject_tags`** filters the `subject` list by the paper's suppressed names before
  `add_tags_to_paper`, so 🔎 re-resolve and `backfill_keyword_tags.py` both respect a deletion.

## Key technical detail

Suppression is gated to imported keywords (`import_source.startswith("keyword:")`) — removing a **user** tag never
suppresses (user tags aren't enrich-re-added anyway). Keyed by **name** (not id) because the tag row is pruned when
its last link is removed; `add_tag_to_paper`'s un-suppress keeps the round-trip consistent (delete → suppressed;
re-add → cleared). No new endpoint or response shape — the existing `DELETE /papers/{id}/tags/{tag_id}` and the
re-resolve path just got non-destructive.

## Manual verification

Backend-only (no UI change — the existing TagsRow ×-remove + 🔎 re-resolve call the now-suppression-aware
functions). The exact librarian scenario is unit-tested end-to-end at the repo + enrichment level: import keyword
tags → delete one → it's suppressed → re-run `apply_crossref_subject_tags` (= what re-resolve does) → it stays gone
→ re-add it manually → suppression cleared → apply re-adds it. Plus: removing a user tag does not suppress.

## Triage of the remaining librarian findings (filed to backlog #3 / #9)

Shipped: durable keyword deletion. **Remaining:** a confirm before 🔎 re-resolve overwrites hand-edited metadata
(`force=True` clobbers silently); a tag's source as a small always-on label/icon (not only on hover); a "what
re-resolve changed" diff toast; a "lock this tag" affordance. (Filed under #3 + the tag-provenance item #9.)

## Pytest

**+2** (`test_tags.py`: deleted-keyword-not-re-added round-trip; user-tag-removal-doesn't-suppress). `ruff` clean;
migration head **0020** (derived by `alembic_head()`, no test edit); apply-callers (enrichment/backfill) unchanged.
No new endpoint/egress; no surface change (the suppression rides the existing DELETE + re-resolve).

## Next (the slate)

- **Close reader ↔ dogfood the reading flow** (inc 144).
- **Skeptical synthesizer ↔ multi-paper focus query** (inc 145).
- **Then BYOK** (user-prioritized after the slate).
