<!-- qa-coverage
api: /gaps/find, /gaps/find/{job_id}, /gaps/add, /gaps/dismiss
fe: 36_gaps.jsx
-->

# ROUTE 41 — Literature gap-finder (backward citation gap)

**Tier:** 2 external (OpenAlex metadata)
**Goal:** Exhaust the gap-finder — Find gaps → the "cited by N of your papers" candidate list → Add / Dismiss —
while preserving candidates-not-verdicts, evidence-carried, coverage-stated, and the no-quality-rank framing.
Public OpenAlex/Crossref metadata, **never** the Gemini gate.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never fire;
OpenAlex/Crossref metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the real gap scan hits OpenAlex per library paper (network + slow); `_seed_library`'s 3 papers
won't deterministically yield a gap. To exercise the flow **offline + deterministically**, either (a) inject
`app.state.openalex_client` with a fake (the unit-test `_FakeOA`), or (b) **pre-seed the `external_api_cache`**
so the real client reads from cache (mirror `.local/visual/drive_inc135_gaps.py`): cache
`provider="openalex", cache_key="doi:<each paper doi>"` → `{referenced_works:["https://openalex.org/W1"]}`, and
`cache_key="work:W1"` → a work with a DOI **not** in the library; for Add, also cache
`provider="crossref", cache_key="<gap doi>"`. **Use a free port** — stray uvicorns from prior runs can serve a
stale app (assert your own process is alive + that newer routes like `/findings/overview` don't 404).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (gap-finder is public
  metadata only).
- **Candidates not verdicts.** Nothing is auto-added; each row has **Add** + **Dismiss**; the human decides.
- **Evidence + not a rank.** Each row shows **"cited by N of your papers"** — a count over the user's *own*
  library, explicitly **not** a global importance/quality ranking. The modal note says so.
- **Coverage stated.** A "scanned M of N papers (the rest have no DOI) … coverage is partial" line — a missing
  work is never implied "unimportant", just not surfaced.
- **Add = metadata-only into the general library; no PDF** (the OA-acquire lane is untouched → no paywall
  circumvention). Dismiss persists (excluded on the next Find).

## Adversarial checklist

- Add a candidate twice → idempotent ("in library", no duplicate)
- Dismiss → it never resurfaces on a re-Find
- Find gaps with no library DOIs → an honest empty state ("no gaps found …"), no crash
- double-click Find / Add; resize to `375x812` → no horizontal overflow

## Steps

1. Open the **Gaps** button in the library header → the modal (with the "count is how many of *your* papers
   cite each one, not a measure of importance" note).
2. **Find gaps** (offline, seeded as above) → a candidate row: **"<title> · cited by N of your papers · authors ·
   year"** + **Add** / **Dismiss**, plus the **coverage** line ("scanned M of N papers …").
3. **Add** a candidate → the row shows **"✓ in library"** (a metadata-only import; verify in the library list);
   adding again is idempotent. Confirm **no PDF** was fetched (the row offers no acquire here).
4. **Dismiss** another candidate → it disappears; a re-**Find** does not resurface it.
5. Adversarial: an empty-state Find; mobile viewport has no overflow; **0** genai-host requests throughout.

## Pass criteria

- The modal finds candidates, each with an evidence count + Add/Dismiss; Add imports metadata-only, Dismiss persists.
- The count is framed as the user's-library citing, never a quality rank; coverage is stated.
- 0 console/page errors; **0 genai-host requests**.
- Bad inputs fail closed (422 on a blank-DOI add); mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_41_gaps.md` + `screenshots/` (see `_TEMPLATE.md`).
