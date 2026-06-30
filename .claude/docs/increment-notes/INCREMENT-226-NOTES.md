# Increment 226 — per-identifier re-fetch 🔎 for PMID + arXiv

## Implemented

The maintainer asked: "can we add search to the other options under identifiers? like how doi has the little
search icon?" — and (via AskUserQuestion) chose **"re-fetch metadata from that source."** So the Details →
Identifiers 🔎 (DOI → Crossref re-resolve, inc 49) is generalized to **PMID** and **arXiv**; ISBN/ISSN/Cite-key
stay plain (no per-paper source).

- **`app/backend/api/routers/paper_enrich.py`** (NEW, 113) — a forced rule-#1 split (see below): holds
  `reresolve_paper` (`POST /papers/{id}/re-resolve`) + `fill_metadata` (`POST /papers/{id}/fill-metadata`) +
  `FillMetadataResponse` + `_crossref`, moved verbatim out of `papers.py`. New `ReResolveRequest{source:
  Literal["crossref","pmid","arxiv"] = "crossref"}` (default keeps the DOI 🔎 byte-for-byte + back-compat with the
  no-body POST). `reresolve_paper` branches: `crossref` → the existing 422-if-no-DOI +
  `enrich_paper_metadata_from_crossref(force=True)`; `pmid`/`arxiv` → read the identifier from `csl_json` (422 if
  absent) + `enrich_paper_metadata_from_identifier(..., openalex_client=request.app.state.openalex_client,
  force=True)`. Both branches keep the inc-224 `auto_check_retractions` + the `conn.commit()` + return `_detail_for`.
- **`app/backend/metadata/enrichment.py`** — `OPENALEX_SOURCE = "openalex"` added to the `_can_update_from_crossref`
  allowlist (so a re-fetched record is resolved+updatable, like `crossref`, never protected like `user-edited`) +
  new `enrich_paper_metadata_from_identifier(conn, paper_id, *, source, openalex_client=None, force=False)`. Builds
  the ref (`PaperRef(pmid=…)` / `PaperRef(doi="10.48550/arXiv.<id>")`), calls
  `openalex_client.fetch_work_csl(conn, ref)`, and on a hit `setdefault`s the clicked identifier back onto the
  resolved CSL (the projector replaces `csl_json` wholesale, and `_csl_from_work` doesn't echo the arXiv id) then
  `update_paper_metadata(conn, paper_id, **_paper_values_from_csl(record, imported_source=OPENALEX_SOURCE))`. On a
  miss → no overwrite, `status="unresolved"`.
- **`app/backend/metadata/__init__.py`** — re-exports `enrich_paper_metadata_from_identifier`.
- **`app/backend/api/app.py`** — imports `paper_enrich` + `include_router(paper_enrich.router)` **before**
  `papers.router` (the literal `/papers/{id}/re-resolve` + `/fill-metadata` paths keep winning).
- **`app/frontend/js/25_detail.jsx`** — `DoiRow` → generic **`IdentifierRow({label, value, fieldKey, source,
  paper, onSave, onResolve, resolving})`** (the input + 🔎 + the inc-174 user-edited confirm guard + a per-row
  in-flight state via `resolving === source`); used for DOI (`source="crossref"`), **PMID** (`source="pmid"`),
  **ArXiv ID** (`source="arxiv"`). `reresolve(source="crossref")` posts `{source}`; the success note reflects the
  source. ISBN/ISSN/Cite-key stay plain `EditableRow`.

## Key technical detail

`_paper_values_from_csl` projects the resolved CSL into **all** scalar columns and replaces `csl_json` wholesale.
`_csl_from_work` (OpenAlex → CSL) echoes PMID but **not** the arXiv id — so a naive arXiv re-fetch would drop the
arXiv id the user clicked on. The orchestrator `setdefault`s the source identifier (`PMID`/`arxiv`) back onto the
record before the overwrite, so re-fetching from an identifier never silently drops it. `force=True` from the
endpoint matches the DOI 🔎's intent ("re-fetch from *that* source" — the user's explicit ask); the inc-174 confirm
guard still gates overwriting a `user-edited` record.

## Manual verification script

- **Unit/integration** (`tests/test_papers.py`, hermetic via an injected fake OpenAlex): PMID re-resolve overwrites
  via OpenAlex (`imported_source == "openalex"`); arXiv re-resolve calls `fetch_work_csl` with
  `PaperRef(doi="10.48550/arXiv.<id>")`; a fetch miss leaves the record unchanged (graceful 200); a missing
  identifier → 422.
- **Headed, no egress** (`.local/visual/drive_inc226_identifier_resolve.py`, fake OpenAlex injected): top paper
  auto-selects → Details → Identifiers → the PMID + ArXiv rows each show a 🔎 → click the PMID 🔎 → the title
  re-renders to "Resolved by OpenAlex", `GET /papers/{id}` shows `imported_source == "openalex"` + the PMID
  preserved; 0 console/page/genai.

## Pytest

**795 passed, 1 skipped** (+4 `test_papers.py`). ruff `check` + `format --check` clean; frontend rebuilt
(`callosum-app.html` in sync, `test_frontend_assembly` 5/5). **QA surface unchanged** (161/161 API + 719/719 FE,
0 uncovered — the `source` param rides the existing `/re-resolve` route; noted on `route_30_detail_pane.md`).
**Rule #1:** `routers/papers.py` 598 → **528**; new `routers/paper_enrich.py` **113**; `25_detail.jsx` **583**;
`enrichment.py` **450** — all under cap. **No migration / new dependency / new external host** (reuses the
already-audited OpenAlex client + the inc-49 overwrite primitive; public bibliographic metadata, NOT the Gemini
gate). Audit: inc-226 addendum to `.claude/security-audits/2026-06-30_metadata-enrich.md` (PASS).
