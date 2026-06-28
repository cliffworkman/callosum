# Literature Discovery — design (backlog #28; future-track: librarypaneltabadditions)

**Goal:** bring *finding* the literature into the same place you read + understand it — center library-frame tabs
(**Search** now, **Feed** later) on a shared, extensible **SourceProvider** registry. Stay true to the Fraser
method: fast comprehensive triage; **AI augments but never filters** the complete list; lightweight at intake
(organize downstream via auto-axis on save).

Approved with Cliff 2026-06-28: **Search-tab-first**; **all sources** wanted (sequenced — Crossref leads,
PubMed/bioRxiv as drop-ins); **axis-relevance highlight is a fast-follow (SP1b)**; **bioRxiv lands in the Feed**
(its API is category/date-based, not keyword search; Crossref already surfaces bioRxiv/medRxiv preprints in Search).

## Architecture (the reusable spine)
- **`SourceProvider` registry** (`app/backend/discovery/providers.py`): a Protocol `search(query, limit) ->
  list[Item]` + `name`/metadata; a self-registering registry with `build_default_registry()` (mirrors the
  acquisition-resolver registry + the pane registry). **Adding a source = register one module — no endpoint/UI
  edit** (the registry test proves this).
- **Normalized `Item`** (frozen dataclass): `sources: list[str]`, `external_id` (DOI or PMID), `title`,
  `abstract`, `authors: list[str]`, `journal`, `date` (year/ISO), `url`, `dedup_key`, `in_library: bool`. **Dedup
  across providers** by DOI → PMID → normalized title (one paper from two sources = one item carrying both source
  labels).
- **Search service** (`discovery/search.py`): fan out to the registry's providers, normalize, dedup, mark
  `in_library` (reuse `find_existing_paper_by_identity`), cap results.
- **Save** (`discovery/save.py` or reuse): metadata-only create from an Item's CSL-ish fields, deduped — reuses the
  gap-finder / citing-import path (`import_*_work` family) with `imported_source="discovery-import"`. **No PDF
  fetch** (acquisition stays the separate OA lane).
- **Endpoints** (`routers/discovery.py`): `GET /discovery/search?q=&limit=` → `{items:[…]}`; `POST /discovery/save`
  → create + return the new paper id (409/idempotent if already in library). Same fail-closed posture as the other
  external-fetch routers.
- **Frontend:** a **Search** center tab via the LibraryFrame tab system (sibling to the PDF viewer) — a query box →
  a dense, **keyboard-triage** results list (`j`/`k` move, `s`/Enter save, staged title → abstract on expand) →
  one-click save. **The complete list is always shown** (no filter; with relevance deferred, trivially true).

## SP decomposition
- **SP0 (inc 182) — prerequisite split:** extract `LibraryFrame` from `30_viewer.jsx` (MAXED at 599/600) into its
  own chunk so the Search-tab branch fits. Behavior-preserving (verify via the existing e2e/headed drivers).
- **SP1 (inc 183) — the Search tab, Crossref provider:** the registry + `Item` + dedup + the 2 endpoints + the
  save path + the Search tab + keyboard triage. Crossref leads (extends the existing adapter with `/works?query=`;
  covers journals **and** preprints). Audit + a QA route + tests + headed verify.
- **SP1a:** PubMed provider (a new app-side NCBI **E-utilities** httpx client — the PubMed MCP is the assistant's,
  not the app's — + its own audit). Drops into the registry, no UI change.
- **SP1b:** the **axis-relevance highlight** — score each item's title+abstract against the user's axis embeddings
  (reuse `axis_scoring` + embeddings); **highlight likely matches WITHIN the complete list** with the matched axis
  + similarity + the uncertainty tag. **Never hide/filter/reorder-away.** Relevance is a hint on the save step.
- **SP2:** the **Feed tab** — subscriptions (journals by ISSN / PubMed keyword / **bioRxiv by category**) + polling
  on a cadence + a read/unread/starred items store (alembic) + the same triage components. Pull-first;
  notifications opt-in, gentle, source-level only.

## Principles gate (rule #9)
A discovery **signal**. Load-bearing commitments, all honored: **augment never filter** (the complete list is the
anti-offloading safeguard; relevance is a highlight, never a gate/reorder — SP1b); **candidates not verdicts** (the
human saves; nothing auto-imports); **user-derived defaults** (Feed suggestions come from the user's own library;
never auto-subscribe — SP2). No ranking-by-citation-count, no "importance" verdict. The misaligned easy path (a
filtered/AI-curated "here's what matters" list) is **declined** — the complete list is the product.

## Gates / constraints
- **Audit:** new external fetch (Crossref *search* — same host as the audited adapter; PubMed E-utilities in SP1a is
  its own audit) + a new save/ingestion path. SSRF n/a (fixed hosts); validate/​cap response shape (rule #4);
  bound-param SQL on the save (rule #3); mailto from Settings → Metadata access (polite pool); no egress gate (this
  is public-metadata search, like the gap-finder/acquisition — NOT the Gemini gate).
- **QA (rule #10):** a new `route_43_discovery.md` (the `/discovery/*` endpoints + the Search tab surface).
- **No new dependency** (Crossref reuses httpx via the existing adapter).
- **Tests:** provider mapping; dedup across two providers (a shared DOI → one item, both sources); `in_library`
  marking; search-endpoint shape; save creates a deduped metadata paper (no PDF); the registry accepts a new
  provider with no service/endpoint edit.

## Verification
pytest (hermetic, injected fake provider/Crossref); headed (no egress, a seeded fake provider): query → results →
keyboard `s` save → the paper lands in the library; the complete list is never filtered. The real Crossref query is
a light live spot-check.
