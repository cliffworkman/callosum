<!-- qa-coverage
api: /gaps, /gaps/refresh, /gaps/refresh/{job_id}, /gaps/add, /gaps/dismiss
fe: 36_gaps.jsx
-->

# ROUTE 41 — Literature gap-finder (backward + forward, axis-scoped, cached)

**Tier:** 2 external (OpenAlex metadata)
**Goal:** Exhaust the gap-finder — both directions (works your papers cite ⇄ works that cite your papers), an
axis scope, the persistent cache (GET reads instantly, Refresh recomputes), and the "cited by / cites N of your
papers" candidate list → Add / Dismiss — while preserving candidates-not-verdicts, evidence-carried,
coverage-stated, and the no-quality-rank framing. Public OpenAlex/Crossref metadata, **never** the Gemini gate.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never fire;
OpenAlex/Crossref metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the real gap scan hits OpenAlex per library paper (network + slow); `_seed_library`'s 3 papers
won't deterministically yield a gap. To exercise the flow **offline + deterministically**, either (a) inject
`app.state.openalex_client` with a fake (the unit-test `_FakeOA`), or (b) **pre-seed the `external_api_cache`**
so the real client reads from cache (mirror `.local/visual/drive_inc137_gaps.py`):
- **backward**: cache `provider="openalex", cache_key="doi:<each paper doi>"` → `{id, referenced_works:["https://openalex.org/W1"]}`,
  and `cache_key="work:W1"` → a work with a DOI **not** in the library.
- **forward**: cache the same `doi:<...>` work objects (they carry the `id`), and `cache_key="citing:<each work id>"`
  → a `{results:[{id, doi, title, ...}]}` whose DOI is **not** in the library.
- For Add, also cache `provider="crossref", cache_key="<gap doi>"`.

**Use a free port** — stray uvicorns from prior runs can serve a stale app (assert your own process is alive + that
newer routes like `/gaps` don't 404).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (gap-finder is public
  metadata only).
- **Candidates not verdicts.** Nothing is auto-added; each row has **Add** + **Dismiss**; the human decides.
- **Evidence + not a rank.** Each row shows **"cited by N of your papers"** (backward) or **"cites N of your
  papers"** (forward) — a count over the user's *own* library, explicitly **not** a global importance/quality
  ranking. The modal note says so for the active direction.
- **Coverage stated.** After a Refresh, a "scanned M of N papers (the rest have no DOI) … coverage is partial"
  line; the cache shows a "Last refreshed <date>" line — a missing work is never implied "unimportant".
- **Cache, not a live recompute.** GET `/gaps` reads the persisted scope cache; opening / toggling direction or
  axis re-reads instantly (no scan). **Refresh** is the only recompute.
- **Add = metadata-only into the general library; no PDF** (the OA-acquire lane is untouched → no paywall
  circumvention). Dismiss persists (excluded at read time on the next GET).

## Adversarial checklist

- Toggle backward ⇄ forward → the note + the count label switch; each direction is its own cache row
- Switch the axis dropdown → the scope re-reads (its own cache row)
- Add a candidate → it drops from the list (now in library); adding again is idempotent (no duplicate)
- Dismiss → it drops and never resurfaces (read-time filter)
- Refresh a scope with no library DOIs → an honest empty state, no crash
- double-click Refresh / Add; resize to `375x812` → no horizontal overflow

## Steps

1. Open the **Gaps** button in the library header → the modal. Note the direction toggle (**Works you cite** /
   **Works citing you**), the axis dropdown (**All papers** + each axis), and the "count is how many of *your*
   papers … not a measure of importance" note.
2. **Refresh** (offline, seeded as above) → a candidate row: **"<title> · cited by N of your papers · authors ·
   year"** + **Add** / **Dismiss**, plus the **coverage** line ("Last refreshed … Scanned M of N papers …").
3. **Toggle to forward** → the note + count label change to "cites N of your papers"; Refresh the forward scope →
   its own candidates (the backward cache is untouched).
4. **Add** a candidate → the row drops (a metadata-only import; verify in the library list); adding again is
   idempotent. Confirm **no PDF** was fetched.
5. **Dismiss** another candidate → it drops; re-open / re-GET does not resurface it.
6. Adversarial: a Refresh with no DOIs → empty state; mobile viewport has no overflow; **0** genai-host requests.

## Pass criteria

- Both directions surface candidates from the cache, each with an evidence count + Add/Dismiss; Add imports
  metadata-only, Dismiss persists; toggling direction/axis re-reads the right cache scope.
- The count is framed as the user's-library relation, never a quality rank; coverage + last-refreshed are stated.
- 0 console/page errors; **0 genai-host requests**.
- Bad inputs fail closed (422 on a blank-DOI add); mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_41_gaps.md` + `screenshots/` (see `_TEMPLATE.md`).
