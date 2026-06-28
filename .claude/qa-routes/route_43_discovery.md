<!-- qa-coverage
api: /discovery/search, /discovery/save
fe: 30d_discover.jsx
-->

# ROUTE 43 — Literature discovery (Search/Discover tab)

**Tier:** 2 external (Crossref metadata)
**Goal:** Exercise the discovery Search flow end to end — the **Discover** center tab's query box →
`GET /discovery/search` (fans out to the SourceProvider registry, dedups across sources, marks `in_library`, returns
the **complete** list — no AI filtering, that is SP1b) → keyboard-triage results → one-click **Save** →
`POST /discovery/save` (a **metadata-only, deduped** library paper; **no PDF fetch** — acquisition stays the OA lane).
Public-metadata search (Crossref now) — **never** the Gemini library-text gate. Backend = inc 183; the Discover tab UI
(`30d_discover.jsx`) = inc 184.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never fire;
Crossref metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the real Crossref search hits the network. To exercise the flow **offline + deterministically**,
inject `app.state.discovery_registry` with a `SourceRegistry` holding a fake provider (mirror `tests/test_discovery.py`'s
`_FakeProvider` → returns `Item(...)` rows with DOIs, one matching a seeded library paper so `in_library` is true). The
`POST /discovery/save` path is fully local (no provider call) and can be driven directly.

**Use a free port** — stray uvicorns from prior runs can serve a stale app (assert your own process is alive + that
`/discovery/search` doesn't 404).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (discovery is public
  metadata only — Crossref, never the library-text gate).
- **Complete list, AI augments-never-filters.** `GET /discovery/search` returns every deduped result; nothing is
  hidden by a relevance score (axis-relevance highlight is SP1b, a hint not a gate).
- **Dedup honesty.** A result returned by two providers appears **once**, with both source labels unioned (`sources`);
  the `dedup_key` is DOI → PMID → normalized-title precedence.
- **`in_library` truth.** A result whose DOI/identity matches a live library paper is flagged `in_library:true` (so
  the UI can show "already have it"); a novel result is `false`.
- **Save = metadata-only, deduped, no PDF.** `POST /discovery/save` creates a paper with `imported_source` =
  `discovery-import` (kept out of the crossref-update allowlist, like user-edited); saving the same identity twice
  returns `created:false` with the **same** `paper_id` (no duplicate row); **no PDF is fetched** (the OA-acquire lane
  is untouched → no paywall circumvention).
- **Fail closed.** A blank `q` → 422; a provider that raises is skipped (one bad source never sinks the search).

## Adversarial checklist

- Search a term → results carry title/authors/year/journal + `sources` + `in_library` + `dedup_key`
- A result already in the library is flagged `in_library:true`; a novel one is `false`
- The same DOI from two providers collapses to one row with both source labels
- Save a novel result → `created:true`; save it again → `created:false`, same `paper_id`, no duplicate in `/papers`
- Save a result matching an existing paper → deduped onto it (`created:false`)
- Blank `q` → 422; oversized `limit` → 422 (capped at 50)
- **0** genai-host requests throughout

## UI flow (the Discover tab, inc 184)

- The center frame has a persistent **Discover** tab (beside Library). Opening it shows a query box + a "the complete
  list is shown (nothing filtered)" hint + keyboard-triage hints (`j/k` move, `s` save, `Enter` abstract).
- Searching renders dense result rows: serif title, authors/year/journal meta, **source pill(s)** (e.g. `crossref`),
  and either a **Save** button or a green **✓ in library** marker. **j/k** move the cursor (`.discover-item.cur`
  highlight), **s** saves the focused row, **Enter** toggles its abstract.
- Save flips the row to **✓ in library** (no duplicate save) and refreshes the Library tab so the new paper appears.

## Steps

1. (Offline, fake registry as above) `GET /discovery/search?q=<seeded topic>` → confirm the response shape:
   `{items:[{title, authors, year, journal, doi, sources, in_library, dedup_key, ...}]}`; one item `in_library:true`
   (matches a seeded paper), the rest `false`.
2. Confirm cross-provider dedup: a DOI returned by two fake providers appears once with `sources` unioned.
3. `POST /discovery/save {title, doi, ...}` for a novel result → `{paper_id, created:true}`; verify it now appears in
   `GET /papers` with `imported_source: discovery-import` and **no attachment/PDF**.
4. `POST /discovery/save` again with the same identity → `{paper_id:<same>, created:false}`; `GET /papers` shows no
   duplicate.
5. Adversarial: blank `q` → 422; `limit=999` → 422; **0** genai-host requests.

## Pass criteria

- Search returns the complete deduped list with `sources` + `in_library` + `dedup_key`; nothing AI-filtered.
- Save creates a metadata-only, deduped paper (`discovery-import`); re-save is idempotent (same id, `created:false`);
  **no PDF fetched**.
- Bad inputs fail closed (422); a failing provider is skipped, not fatal.
- 0 console/page errors; **0 genai-host requests**.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_43_discovery.md` + `screenshots/` (see `_TEMPLATE.md`).
