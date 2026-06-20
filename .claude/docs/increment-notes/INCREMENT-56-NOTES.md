# Increment 56 Notes — Duplicate detection (layered, flag-only) + review modal (backlog E)

A library accrues duplicates (a preprint + its published version; a re-import where identity didn't
resolve; a pdf-scaffold whose title differs from the enriched copy). **E** surfaces likely-duplicate
groups with a confidence + reason for review. **Flag-only** — the user resolves by trashing the redundant
copy (reusing inc-54 soft-delete); **merge stays deferred** (the last backlog item).

## Implemented
### Backend — `app/backend/clustering/duplicate_detection.py` (new; mirrors `axis_suggestion`)
`find_duplicate_groups(conn, *, model)` builds pairs from three **layered** signals (deterministic first,
fuzzy last so it doesn't false-positive on same-topic papers):
- **shared identifier** — same `csl_json` PMID or arXiv (DOI can't collide — it's UNIQUE). conf 0.99.
- **title + author + year** — identical canonical title (`normalize_text(strip_punctuation(title))`,
  min length) + same first-author + same year → 0.97; same title+author, year differs → 0.85
  (preprint ↔ published).
- **embedding near-dup** — reuses axis_suggestion's in-memory encode + numpy `V @ V.T`; pairs with cosine
  ≥ **0.92** (high → only near-identical text). conf = the cosine. Guarded `MAX_EMBED_PAPERS=3000`.
Pairs are merged via **union-find** into groups (≥2), each carrying its strongest pair's reason +
confidence. Live papers only (`deleted_at IS NULL`). Ephemeral — nothing persisted.

### Backend — async endpoint (mirrors `/axes/suggest`)
`papers.py`: `_DedupJobStore` + `DuplicateGroupResponse`/`DedupJobResponse`; **`POST /papers/duplicates`**
(202 + job id) → `_run_dedup_job` (local, no egress); **`GET /papers/duplicates/{job_id}`**. Registered
before `/papers/{paper_id}` (literal "duplicates" segment). `app.py` wires `api.state.dedup_jobs`.

### Frontend — `19_duplicates.jsx` (new) + wiring
A **"Duplicates"** button in the library head (`.lib-head`, next to Trash) opens `DuplicatesModal`: POST +
poll the job; each group is a card with a confidence badge + reason, then each paper (title · authors ·
year) with **open** / **delete** (soft-delete → the paper drops from the group; the group resolves when <2
remain; the library list refreshes) / a per-group **dismiss** (session-only). Reuses the `SuggestAxesModal`
lifecycle + the soft-delete handlers. `40_app.jsx` mounts it (`onOpenPaper=openPdf`,
`onChanged=bump libRefresh`).

## Key technical detail
Layering + a high embedding threshold (0.92) is what keeps the scan from flagging same-topic papers (the
backlog's warning): exact identifier and title+author+year are near-certain; the fuzzy layer only catches
near-identical text. Union-find means a paper appears in exactly one group even when multiple signals link
it. The scan is **entirely local** (no Gemini) and **read-only** — the only mutation is the user's
reversible soft-delete.

## Manual verification script
1. Rebuild + restart uvicorn + hard-reload.
2. Click **Duplicates** in the library head → "Scanning…" → groups appear (confidence + reason + the
   papers). Open one to inspect; **delete** the redundant copy → it moves to Trash and the group resolves.
   **Dismiss** a false positive to hide it.

## Verification
- **pytest: 199** (+9): `test_duplicate_detection.py` (7 — each layer, union-find, no-dupes, trashed
  excluded) + `test_papers.py` (2 — endpoint flags a pair / empty). Route-surface invariant updated.
- **Live E2E** (`.local/duplicates_e2e/`, fake model, no network): scan → one group → delete the redundant
  copy → group resolves + library updates; **0 console errors**. Screenshot captured.
- **Audit:** `.claude/security-audits/2026-06-19_duplicate-detection.md` → PASS.
- New module 150; `papers.py` 521 — all < 600. No new dependency.

## Backlog
Done: **E** (duplicate detection, flag-only). Deferred: library **merge** (the real consolidation, last);
**persistent "not a duplicate"** dismiss (needs a table); synthesis split (F); terms-as-first-class.
