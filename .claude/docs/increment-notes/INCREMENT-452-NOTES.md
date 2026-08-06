# Increment 452 — NLM MEDLINE indexing as a fifth PUBLISHERS legitimacy source (backlog #40)

## Implemented

Closes another slice of backlog #40's still-open list. PUBLISHERS ("where to submit,"
`app/backend/methods/publishers.py`, Discover → Journals) already wired DOAJ, SciELO, TOP Factor (inc 448), and
AJOL (inc 451). This increment adds a fifth source, **NLM/MEDLINE indexing status**, via a live per-ISSN lookup
against NCBI's free, no-key **E-utilities** `esearch` endpoint (`db=nlmcatalog`) — mirroring SciELO's live-lookup
shape exactly, not TOP Factor/AJOL's periodic-mirror shape (no new schema, migration, or Settings UI).

New: `integrations/nlm/journals.py` (`NlmJournalsClient.fetch_medline_indexed(conn, issn) -> bool`), mirroring
`integrations/scielo/journals.py`'s ISSN-validate-before-request / injectable-fetcher / `integrations/api_cache.py`
/ never-raises shape, but returning a plain `bool` instead of a dataclass (no sub-fields to carry). Reuses
`app/backend/discovery/pubmed_provider.py`'s existing `EUTILS`/`TOOL`/`resolved_mailto("CALLOSUM_CROSSREF_MAILTO")`
convention for the same NCBI host family rather than inventing a second one. Wired into
`app/backend/methods/publishers.py` (`build_profiles()` gains a 6th positional `medline_by_issn` param, appended
after `ajol_by_issn`; `JournalProfile.indexed_in_medline`; `"Indexed in MEDLINE"` in `legitimacy_signals`;
`LEGITIMACY_DEFERRED` narrowed) and `app/backend/api/routers/publishers.py` (a new sequential per-candidate fetch
loop mirroring SciELO's, no pre-filter). **Zero frontend changes** — `08e_methods_publishers.jsx`'s
`legitimacy_signals` chip list is already a generic `.map()`, so the new chip renders for free.

## Key technical detail

**A real overclaim caught live before ship: "MEDLINE" and "PubMed" are independent NLM indexing statuses, and
the query only checks the former.** NLM's own catalog record gives each journal a separate `IndexingSourceName`
entry per source (MEDLINE, PubMed, PMC, ...), each with its own status. The first implementation pass named the
new field `indexed_in_pubmed` and the chip "Indexed in MEDLINE/PubMed" — but live manual verification (running a
real broad Publishers search, not just the hermetic fake-fetcher tests) surfaced *World Psychiatry* reading
`False`, which is wrong: WPA's flagship journal is unambiguously legitimate and PubMed-searchable. Direct `curl`
verification against NLM's real catalog record confirmed why: World Psychiatry has a `PubMed` source marked
"Currently-indexed," but **no MEDLINE source entry at all**. The `currentlyindexed[all]` search-field term this
client uses empirically tracks MEDLINE status specifically (confirmed against two real MEDLINE-indexed journals
as positive controls, and this negative control) — so the query itself was always correct; only the label
overclaimed what it checks. Fixed by renaming end-to-end, not by changing the query: `indexed_in_medline` (was
`indexed_in_pubmed`), `"Indexed in MEDLINE"` (was `"Indexed in MEDLINE/PubMed"`), `fetch_medline_indexed()` (was
`fetch_indexed()`). Broader raw-PubMed presence (including PubMed-only, non-MEDLINE-curated content) stays out
of scope and unclaimed — MEDLINE indexing is a complete, well-defined legitimacy signal on its own terms; the
codebase's existing `NLM_PROVIDER = "nlm-medline-index"` cache-provider string had already, independently, named
the check correctly from the first draft, which is what made the mismatch with the field/chip name visible on
inspection once the bug was suspected. This is the same class of finding as inc 451's AJOL `"NA"`-marker catch —
a correctness bug findable only by exercising the real system, not the synthetic test fixtures.

**A single search query does the indexing-status filtering server-side, avoiding a second, separate real
ambiguity found live.** `term=<ISSN>[issn] AND currentlyindexed[all]` returns `count > 0` only when the ISSN is
currently MEDLINE indexed. This also sidesteps a distinct trap: some ISSNs resolve to **more than one** NLM
catalog record (an old vs. current incarnation of the same title — confirmed live for the British Journal of
Psychiatry's print ISSN, where `idlist[0]` was a "Ceased-publication" record and `idlist[1]` was the real
"Currently-indexed" one). Picking the first `esearch` id blind would have misread a live, major journal as
ceased; letting NCBI's own combined filter resolve it avoids the bug entirely rather than requiring a second
`efetch` + manual disambiguation.

**A deliberate, user-confirmed scope choice: binary, not richer.** NLM's catalog *can* express "never indexed"
vs. "indexed, since deselected" as separate statuses, but the user explicitly chose the simpler binary signal
over building that distinction — matching SciELO's own existing precedent (a plain "indexed: yes/no" fact, no
richer status), and shipping faster. `fetch_medline_indexed()` returns a plain `bool`, never `bool | None` — a
malformed ISSN, a well-formed-but-unindexed ISSN, and a network error all legitimately collapse to "not
(confirmed) currently MEDLINE-indexed," with no information lost by never distinguishing them.

**Self-pacing over an API key.** Live-confirmed via `curl` before implementation: NCBI enforces roughly 3
requests/second without a key (real 429s reproduced after 4 rapid requests). A `PUBLISHERS` run makes one live
call per candidate, sequentially, up to `MAX_CANDIDATES` — an unthrottled loop could 429 partway through and
silently misreport later candidates as "not indexed," a real correctness defect (a false negative on a real
journal), not just slower output. Rather than add an optional `CALLOSUM_NCBI_API_KEY` (config surface most users
would never set up, so it wouldn't protect the default path — this was the first draft's recommendation, revised
during planning), `NlmJournalsClient` self-paces: it tracks the monotonic timestamp of its last live call and
sleeps the remainder of a ~350ms window before firing the next one, only on a cache miss. Live-verified
end-to-end: a real 25-candidate broad run against `Mental Health Treatment and Access` completed with consistent
`indexed_in_medline` values across two identical re-runs (BMC Psychiatry, PLoS Medicine, PLoS ONE, British
Journal of Psychiatry, American Journal of Psychiatry, Lancet Psychiatry, and 14 others all correctly True or
False, no 429-driven flip between runs).

**`LEGITIMACY_DEFERRED` narrows by dropping, not splitting.** The old `"PubMed / Scopus indexing"` string bundled
two orgs; only MEDLINE indexing became buildable (Scopus is proprietary with no free API; raw PubMed-broad
coverage was never promised, see above). The string is dropped whole rather than replaced with a residual entry
— mirroring exactly how "AJOL" silently dropped out of the old "AJOL, Redalyc, Latindex" string once AJOL was
wired (inc 451). Neither Scopus nor "PubMed" is named anywhere in the tool's own response shape (test-pinned);
the increment notes + security audit carry the record of what was considered.

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-07-01_publishers.md` gains `## Addendum — SP4` — PASS. Zero
  request-time credential of any kind (no API key at all, unlike DOAJ's optional one); the pacing guard's
  correctness rationale documented explicitly; the MEDLINE-vs-PubMed overclaim documented as a found-and-fixed
  finding, not silently corrected.
- **QA route**: extended `.claude/qa-routes/route_60_publishers.md` only — no new route file (mirrors SciELO's
  precedent; this source has no Settings UI, unlike AJOL/TOP Factor's routes 85/86) — new standing assertions
  (never elevates, never overclaims "PubMed," abstract-never-transmitted extended to NLM), an
  adversarial-checklist line, a new step 8 (a broad multi-candidate run proving the pacing guard end-to-end), and
  a frontend note that no new JSX exists for this source.
- `THIRD-PARTY-NOTICES.md` / `.claude/CREDIT-THE-LINEAGE.md`: new NLM entry, matching the existing MEDLINE
  abbreviation-index entry's "Courtesy of the U.S. National Library of Medicine" phrasing (inc 385's precedent),
  explicit that MEDLINE and PubMed are distinct statuses and only the former is checked.
- `.claude/docs/INCREMENT-BACKLOG.md` #40 updated: MEDLINE indexing wired (named precisely); Scopus explicitly
  recorded as permanently out of scope rather than silently vanishing from the doc's own tracking.

## Manual verification script

1. Run PUBLISHERS (Discover → Journals) for a topic likely to surface a well-known MEDLINE-indexed journal (e.g.
   a mainstream biomedical/psychiatric abstract). Confirm a hit's card shows an "Indexed in MEDLINE" chip
   alongside the existing DOAJ/SciELO/TOP-Factor/AJOL chips, with no elevation reason attached to it, and that
   "PubMed" never appears anywhere in the rendered card.
2. Re-run at full open-science weighting — confirm the MEDLINE chip persists but never appears as an "elevated
   for" reason.
3. Run a **broad** (~25-candidate) search and re-run the identical search a second time — confirm every
   candidate's `indexed_in_medline` value is identical across both runs (proves the pacing guard prevents a
   429-driven false negative on a live, unbatched ~25-call sequential loop). Live-verified during this
   increment: 25/25 candidates matched across two runs, including a real, major journal (World Psychiatry)
   correctly reading `False` for MEDLINE while a chip-adjacent AJOL/SciELO run would separately confirm it's a
   real, legitimate journal by other signals — proving the MEDLINE-specific claim doesn't read as a blanket
   "not indexed anywhere" verdict.

## Verification

- `pytest tests/test_publishers.py -q` → **29 passed** (25 pre-existing + 4 new: ISSN validation/fail-closed,
  cache-roundtrip, pacing-guard-fires, `build_profiles` wiring) — re-confirmed green after the MEDLINE rename.
- `python tools/check_line_budget.py`: clean — `integrations/nlm/journals.py` well under the cap;
  `methods/publishers.py` and `routers/publishers.py` both with headroom.
- `python tools/qa/build_surface_map.py check`: no new API/FE surface (an additive field on an existing endpoint's
  response, not a new route) — unaffected.
- `ruff format` + `ruff check`: clean.
- Live Playwright verification: zero console errors; the "Indexed in MEDLINE" chip renders correctly across a
  real 25-candidate broad run; a live re-run of the same search via the frontend's own "Recent journal searches"
  recall confirmed stable results.
- Full `pytest -n auto -q` (or CI's own run, per this session's documented local xdist-flakiness fallback).

## Rollback

No schema/migration to revert (additive field only). Remove `integrations/nlm/`; revert
`methods/publishers.py`/`routers/publishers.py`'s medline params (each a clearly separable addition, appended
last); revert `app.py`'s 3-line client wiring. No other source's behavior (DOAJ/SciELO/TOP Factor/AJOL) is
touched by any of this. No frontend file to revert — none was changed.
