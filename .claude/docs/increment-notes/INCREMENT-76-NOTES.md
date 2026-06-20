# Increment 76 — Literature acquisition: the wanted list + OA re-check + coverage (C)

## Implemented
Closes the acquisition arc's **track** loop. A persistent **wanted list** of papers you want an open-access
copy of (unified: auto-includes PDF-less library papers AND lets you add external not-yet-owned papers by
DOI), a manual async **"Re-check OA"** job that runs the resolver cascade over the whole list and
**auto-acquires** anything newly available, and a **coverage readout**. Spec:
`.claude/docs/future-tracks/opus4.8_future-tracks_acquisitionclean.md`.

- `app/backend/persistence/schema.py` + `alembic/versions/0008_wanted_items.py` — the `wanted_items` table
  (migration head 0007 → **0008**; idempotent inspect-guard): `paper_id` (nullable — set = library-linked,
  NULL = external), `doi/pmid/title`, `note`, `status` (wanted | fulfilled), `last_checked_at`, `last_result`.
- `app/backend/persistence/wanted_repo.py` — data access (split out like `tags_repo`/`dedup_repo`):
  `add_wanted` (get-or-create), `list_wanted` (LEFT JOIN papers), `get/remove_wanted`, `sync_from_library`
  (insert a row for every **live PDF-less** paper not yet listed), `list_open`, `mark_checked`,
  `mark_fulfilled`, `coverage_stats`. All bound-param.
- `app/backend/acquisition/wanted.py` — `run_recheck(engine, registry, *, crossref_client, download, import_)`,
  kept out of the router so it is directly testable. Per open row: build a `PaperRef` (library → the paper's
  doi/pmid/title; external → its doi/pmid, **required**), `registry.resolve`, on a hit download (outside any
  txn) then import — library wants fill the paper; external wants `create_paper` then `import_oa_pdf` (which
  enriches from Crossref). Per-item errors; a logged per-run cap (`MAX_RECHECK_PER_RUN`).
- `app/backend/api/routers/wanted.py` + `app.py` wiring — `GET /wanted`, `POST /wanted`,
  `DELETE /wanted/{id}`, `POST /wanted/sync-library`, `GET /wanted/coverage`, async `POST /wanted/recheck` +
  `GET /wanted/recheck/{job_id}` (a `wanted_jobs` JobStore + an `acquire_registry` test seam on state).
- Frontend `app/frontend/js/26_wanted.jsx` + a **Wanted** button in the `.lib-head` (`10_pdf_layer.jsx`) +
  `40_app.jsx` wiring: a coverage line, **Sync from library** / **Re-check OA** (job → summary) / **Add by
  DOI**, and the list with status chips + remove. Reuses the inc-74 `.oa-chip` recipe; rebuilt
  `callosum-app.html`.
- Help corpus: a new **"Acquiring an open-access copy"**-adjacent section *"… the wanted list & re-checking"*
  (see help_content) — the corpus is current through inc 76.

## Key technical detail
The re-check's OA-only bright line is **free and structural**: `run_recheck` resolves only through the
`ResolverRegistry`, which can return only an `OaLocation` (database-asserted OA, https) — there is no path to
fetch a non-OA / arbitrary URL (a test asserts the only download is the registry-produced location). External
wants are fulfilled **only with a doi/pmid** (title-only → skipped `needs-id`), so the re-check never mints a
paper or downloads a PDF from a fuzzy title match. Soft-deleted papers are excluded from sync/coverage/re-check.

## Manual verification script
1. `CALLOSUM_OPENALEX_MAILTO` (+ optionally `CALLOSUM_CORE_API_KEY`) in `.env`; start the app.
2. Library pane head → **Wanted**. Click **Sync from library** → your PDF-less papers appear; **Add by DOI** an
   external paper. Click **Re-check OA** → found copies import (library papers gain a PDF; the external one
   becomes a new paper) with the right OA color/version label (bronze distinct), the summary lists them, and the
   coverage line updates; a closed-only item stays "wanted".
   _(Hermetic tests cover the service/repo/endpoints; a real live re-check is worth a pass.)_

## Pytest
**347 passed, 1 skipped** (+13: repo add/dedup/remove/sync/coverage; run_recheck library-fulfill +
external-create + title-only-skip + miss + error-isolation + registry-only; endpoints CRUD + 422 + sync +
coverage). `ruff` clean; migration head **0008**; route surface extended with the `/wanted*` routes. Security
audit `.claude/security-audits/2026-06-20_wanted-list.md` — **PASS**. This completes Acquisition A/B/C; the
legally-ambiguous lane stays deferred/counsel-gated (its inbox spec is gitignored).
