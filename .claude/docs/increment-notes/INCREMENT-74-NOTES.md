# Increment 74 — Literature acquisition: the legally-clear open-access lane (A)

## Implemented
The keystone of the **track → acquire → read → interrogate → cite** ecosystem — the *legally-clear lane only*
(the ambiguous lane is deferred, counsel-gated, strictly out of scope). Resolve a PDF-less paper
(DOI/PMID/title) → an OpenAlex-asserted **authorized open-access** PDF → download + validate → import locally as
a `managed` attachment labeled with OA color / version / source. Spec:
`.claude/docs/future-tracks/opus4.8_future-tracks_acquisitionclean.md`.

- `app/backend/acquisition/registry.py` — the OA-only seam: frozen `OaLocation` (required OA color, **no
  "closed" member**; https/non-IP validated; `bronze_unstable` derived), `PaperRef`, the `Resolver` Protocol,
  `ResolverRegistry` (ordered cascade, first authorized hit wins), `build_default_registry`.
- `integrations/openalex/adapter.py` (+ `__init__.py`) — `OpenAlexClient`, mirroring the Crossref adapter
  (injectable fetcher, polite-pool `CALLOSUM_OPENALEX_MAILTO`, `external_api_cache` `provider="openalex"`,
  fail-closed) → `app/backend/acquisition/resolvers/openalex_resolver.py` (the registry provider).
- `app/backend/acquisition/fetch.py` — `download_oa_pdf(OaLocation, …)` (https-only manual-redirect stream +
  mid-stream size cap + `%PDF-`/PyMuPDF validation; temp name from uuid), `library_filename_for` (the existing
  library convention `Authors - Year - Venue.pdf`, item-type-aware, sanitized, collision-suffixed),
  `import_oa_pdf` (copy into the managed library dir → `attach_pdf_to_paper` → label → enrich).
- `app/backend/pdf_processing/ingest.py` — extracted the reusable `attach_pdf_to_paper` (attach a PDF to an
  EXISTING paper); `ingest_pdf_scaffold` now calls it (behavior-preserving).
- `alembic/versions/0007_attachment_oa_labels.py` + `schema.py` — additive nullable OA-label columns on
  `attachments`; `persistence/acquisition_repo.py::set_attachment_oa_labels`; the 6 fields on
  `AttachmentResponse`.
- `app/backend/api/routers/acquisition.py` — async `POST /papers/{id}/acquire-oa` + `GET
  /papers/acquire-oa/{job_id}` (mirrors duplicates; the network download runs **outside** the DB txn); wired in
  `app.py` (the `openalex_client` param + the `acquire_jobs` store + included **before** `papers.router`).
- Frontend: `25_detail.jsx` — an **"Acquire OA copy"** button on PDF-less papers (async poll → refresh) + OA
  color/version chips on the Files list (bronze rendered distinct); `styles.css` OA-chip recipe (verified pair =
  durable, flag pair = bronze); rebuilt `callosum-app.html`.

## Key technical detail
The bright lines are enforced **structurally**, not by convention: a resolver returns a frozen `OaLocation`
whose `oa_color` is required and has no "closed"/"none" member, and the downloader's only entry takes an
`OaLocation` — there is **no function anywhere that fetches a bare URL**. So OA-ness is decided by the OA
database, never by callosum, and an arbitrary/non-OA fetch is not expressible (same seam-enforcement idea as the
inc-58 egress gate). Two structural tests pin it. The fetched copy lands in the local library (`managed`
storage); nothing transits a server.

## Manual verification script
1. `pip install -r requirements-dev.txt`; set `CALLOSUM_OPENALEX_MAILTO=<your email>` in the gitignored `.env`.
2. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`; open `http://127.0.0.1:8080/`.
3. Select a metadata-only (PDF-less) paper that has a DOI → the Details pane shows **Acquire OA copy**.
4. Click it → on success an authorized OA PDF imports, named `Authors - Year - Venue.pdf` in the library dir,
   renders in the viewer, and its Files row shows an OA-color chip (**bronze** rendered distinct) +
   version/source; a paper with no OA copy shows the honest *"no authorized open-access copy found."*
   _(Headless functional check of the live OpenAlex fetch not run here; the e2e smoke confirms the UI loads with
   0 console errors. Flag for a real manual pass.)_

## Pytest
**303 passed, 1 skipped** (+24: `OaLocation`/registry structural guarantees, OpenAlex adapter mapping + cache +
fail-closed, download validation, managed import + labeling, the filename convention). `ruff` clean; the e2e
smoke green. Security audit `.claude/security-audits/2026-06-20_oa-acquisition.md` — **PASS**. **NEXT:**
Increment B (resolver cascade — DOAJ / CORE / arXiv·bioRxiv·PsyArXiv·PMC / Crossref) then C (wanted-list +
OA-only re-check + coverage).
