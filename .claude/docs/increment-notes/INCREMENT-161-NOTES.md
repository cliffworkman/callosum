# Increment 161 — non-destructive merge of duplicate papers

**The user's case:** a researcher has two records of one paper — a **preprint** and the **published** version — and
wants to *merge* them, **not delete** one: keep the preprint's PDF, ensure the OSF link survives, and never risk
losing crucial information by mis-identifying which line item to delete. Today the Duplicates flow only offers
*delete the redundant copy* (lossy). This scales the long-deferred library **merge** into the dedup system as a
guided, union-preserving operation.

## Design (forks, confirmed with the user)

1. The merged-away copy → **Trash** (a restorable husk that keeps its own `csl_json` = an audit trail).
2. **Always record lineage** — a "Merged from…" note on the survivor capturing every identifier the merged copy
   had (DOI, URL/OSF, PMID, arXiv), so a link can never be silently lost even if Trash is emptied.
3. Launch from **both** the Duplicates modal (per group) **and** the library bulk bar (≥2 selected).

## Implemented

- **`app/backend/metadata/paper_merge.py`** (new) — `merge_papers(conn, *, survivor_id, merged_ids, metadata,
  primary_attachment_id)`. Fail-fast validation (`MergeValidationError`→422 / `MergeConflictError`→409), then:
  - re-point **source rows** to the survivor: `attachments`, `chunks`, `annotations`, `notes`,
    `paper_external_identifiers` via `UPDATE paper_id` (no per-paper UNIQUE — verified); `paper_tags` via the
    idempotent `tags_repo.add_tag_to_paper`; `collection_papers` + manual `cluster_node_papers` (`confidence IS
    NULL`) via `INSERT OR IGNORE … SELECT` (composite-PK safe); `profile.starred_paper_ids` +
    `research_domains[].paper_ids` via the new `profile_repo.replace_paper_id`.
  - **free the husk's UNIQUE id columns** first (`doi`/`openalex_work_id`/`semantic_scholar_paper_id`/`zotero_*`
    → NULL; the husk's `csl_json` keeps the values for audit) so the survivor can adopt them; auto-adopt
    `openalex_work_id`/`semantic_scholar_paper_id` the survivor lacks.
  - compose the survivor's metadata from the user's picks via `paper_edits.build_paper_update`, append the lineage
    note to `csl_json["note"]`, stamp `imported_source = MERGED_SOURCE` (new constant in `enrichment.py`, kept OUT
    of the crossref-update allowlist like `user-edited`), then one `update_paper_metadata`.
  - set the chosen **primary** attachment (both PDFs are kept — re-pointed, not chosen-one); **soft-delete** the
    husks.
- **No embedding/vector surgery:** a chunk's `paper_id` re-point keeps its `id`, so its embedding still resolves
  (now attributed to the survivor); the husk's paper-level embedding stays harmless (trashed → excluded from
  retrieval, inc 66). So the engine needs no `vector_store`.
- **Endpoint** `POST /papers/merge` in `routers/duplicates.py` (registered before `papers.router`): `MergeMetadata`
  (typed, `extra="forbid"`), maps the engine errors to 422/409, `conn.commit()` (all-or-nothing). No migration.
- **Frontend:** new `38_merge.jsx` `MergePapersModal` (survivor pick + per-conflict-field radios + primary-PDF
  pick; reads each paper via `GET /papers/{id}`; sends only fields differing from the survivor). Wired into
  `19_duplicates.jsx` (per-group **merge**), `10_pdf_layer.jsx` (bulk-bar **merge** at ≥2), `40_app.jsx`
  (`mergeIds` state + `MergePapersModal` render; `onMerged` selects the survivor + refreshes lib/axes/tags). One
  small `.merge-*` CSS recipe (tokens; DESIGN.md read first).

## Gates

- **Audit `.claude/security-audits/2026-06-27_paper-merge.md` PASS** — local, bound-param, fail-fast-validated,
  non-destructive (soft-delete only; no file/vector deletion), transaction all-or-nothing, no egress/dependency.
- **Principles (rule #9):** touches provenance + inspectability but *preserves* them (lineage note + Trash husk
  inspectable; human drives every pick; nothing auto-decided). The misaligned easy path is the current lossy
  delete; this merge is the aligned, union-preserving alternative. No new claim/signal; no A-A veto in play.
- **QA (rule #10):** `route_24_duplicates.md` extended (`api: …, /papers/merge`; `fe: …, 38_merge.jsx`; merge
  steps from both entry points + a non-destructive-merge Critical assertion + 422/409 adversarial). Surface
  **111/111 API + 595/595 FE, 0 uncovered**.
- **Experience (rule #11):** inhabited the preprint+published researcher in the headed drive (below) — selection
  bar "merge" is discoverable, the dialog is legible (keep-record / differing-fields / primary-PDF), and the
  outcome serves the goal (both PDFs + the OSF link survive, the duplicate is in Trash not gone).
- **Help corpus:** "Finding possible duplicates" gained a "Merging duplicates (keeps everything)" subsection; the
  stale "does not merge" gotcha corrected (`HELP-DOCS-SYNCED` → 161).

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc161_merge.py`): seeds a preprint (OSF URL + PDF) + the published
copy (DOI + PDF) → select both → bulk-bar **merge** → the dialog (survivor + primary radios) → **Merge**. Asserts
via the API: the survivor kept the **DOI**, the **OSF URL** (gap-filled), **both PDFs** (`attachment_count == 2`),
and a **"Merged from…"** note; the preprint is in **Trash** (`/papers?deleted=true`), not gone. 0 console / 0 page
/ 0 genai. (Also covered by the Duplicates-modal "merge" path.)

## Pytest

**591** (+10 `test_paper_merge.py`: migration of every source row to the survivor; husk trashed + survivor live;
lineage note carries the merged identifiers incl. the OSF URL; openalex-id adoption + husk freeing; primary pick;
idempotent shared-tag merge; validation 422s; DOI-clash 409; endpoint happy/422/409). `ruff` clean; build +
assembly green; surface 111/111 API + 595/595 FE, 0 uncovered; no migration.

## Watch (rule #1)

`app/frontend/js/40_app.jsx` is now **630/600** — it was already **609** at HEAD (a prior slip; the App
god-component accreted modal/bulk wiring since the inc-128 split to 514). A behavior-preserving split (extract the
modal-render block or another `use*` hook, the inc-128 precedent) is the **immediate next chore**.

## Deferred (noted)

Migrating derived `open_science_signals`/`paper_findings` (they recompute via their producers); rewriting
`summaries.scope_ref_json` for a merged-away id; a true "undo merge" (restore gives an empty-metadata husk);
per-attachment delete to drop the non-preferred PDF; merging across Trash.
