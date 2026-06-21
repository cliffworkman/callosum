# Increment 78 — My Publications: the auto-axis of your own papers (Part 1)

## Implemented
A pinned, OpenAlex-resolved **"My Publications"** axis of the researcher's own papers — **LLM-free**, ORCID-first,
confirm-and-learn, incremental. Spec: `future-tracks/opus4.8_future-tracks_mypublications.md` (Part 1; the
Part-2 impact **dashboard tab** is deferred).

- **Migration 0009** (`schema.py` + `0009_my_publications.py`, idempotent per-part): `axes.kind`
  (`standard`/`my_publications`), a single-row **`profile`** table (display_name / name_variants / orcid /
  cached `openalex_author_id` / `my_publications_dismissed`), and a **`my_publication_decisions`** table
  (confirmed/rejected, one row per paper). `AxisResponse` gained `kind`.
- **`integrations/openalex/author.py`** — `OpenAlexAuthorClient` (mirrors the inc-74 OA-location adapter +
  Crossref pattern: injectable fetcher, `external_api_cache`, fail-closed, polite-pool): `resolve_author(orcid
  |name)` (ORCID → high confidence; name → lower) + `fetch_author_works` (cursor-paginated, capped, DOIs
  normalized). **Metadata egress, not the Gemini gate; LLM-free.**
- **`persistence/profile_repo.py`** — profile get/upsert + `set_openalex_author_id` / `set_my_publications_dismissed`
  + decisions get/set.
- **`clustering/my_publications.py`** — `resolve_my_publications` (resolve → works → intersect the library by
  DOI = confirmed [0.95]; conservative name-only fallback = candidates [0.25]; honor decisions; rewrite the
  AUTO memberships, preserve manual) + `maybe_add_to_my_publications` (the **cache-based import hook**, zero
  extra egress). The axis is get-or-created on first resolve.
- **Import hook** in `metadata/enrichment.py` (after `apply_crossref_subject_tags`): a lazy-imported,
  try/except-guarded call — a no-op when the feature is unused, so existing import/enrichment is untouched.
- **`routers/my_publications.py`** (+ `app.py` wiring: `openalex_author_client` + `mypubs_jobs`): GET/PUT
  profile, async `POST /my-publications/refresh` (+ poll), `POST /my-publications/decide`, `DELETE
  /my-publications` (dismiss — deletes the axis via CASCADE, keeps the profile/decisions).
- **Frontend:** a Settings → **My Publications** section (name / variants / ORCID + Refresh, `apiPut` added to
  `00_lib.jsx`); a **pinned** variant card at the top of the axes panel (`15_axes.jsx` branches `AxisItem` on
  `kind`: 📄 label, indigo `.axis-mypubs` styling, no score controls, count badge = filter; candidate ✓/× route
  to `/decide`); a `MyPubsPrompt` when unset; granular empty-state messaging. Rebuilt `callosum-app.html`.

## Key technical detail
Authorship is **facts vs candidates**: DOI/ORCID matches are confirmed members; name-only matches are
candidates (the existing "uncertain" tier), confirmed/rejected by the user and **persisted** (a rejected paper
is never re-proposed; a confirmed one becomes a manual `confidence IS NULL` member surviving every re-match).
The resolver rewrites only the AUTO (non-NULL) memberships each run, preserving manual ones. The import hook
reads the **cached** author-works (no per-import egress) and is a guarded no-op when unconfigured, so it is
strictly additive. OpenAlex author resolution is metadata egress (public identifiers), explicitly **not** the
Gemini library-text gate, and the whole feature is **LLM-free**.

## Manual verification script
1. Hard-refresh; Settings (⚙) → **My Publications** → enter your **name + ORCID** → **Refresh my papers**.
2. Confirm a pinned 📄 **My Publications** card appears at the top of the axes panel with your DOI-confirmed
   papers (assigned) + any name-only **candidates** (uncertain) to ✓ confirm / ✕ reject; the count badge filters
   the library to your papers; importing a matching paper adds it; 🗑 dismisses the card (Refresh rebuilds it).
   A no-match identity shows the honest "No OpenAlex author found for [name]". _(Visual check delegated to the
   user — no in-repo browser this session; the live OpenAlex resolution is worth a real pass.)_

## Pytest
**361 passed, 1 skipped** (+14: resolver confirmed/candidate/decisions/no-identity/no-match/dismissed; import
hook add + no-op; author client ORCID/name/works-cache/fail-closed; profile/decide/dismiss endpoints). `ruff`
clean; migration head **0009**; route surface extended with `/my-publications/*`; **no model tokens consumed**.
Security audit `.claude/security-audits/2026-06-20_my-publications.md` — **PASS**. **NEXT:** Part 2 — the impact
dashboard tab (charts, citation graph, prospection), deferred.
