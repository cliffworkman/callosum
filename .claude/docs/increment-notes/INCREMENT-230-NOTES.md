# Increment 230 — drop the user-facing "we don't categorize people" note (close-out of the inc-229 rework)

The maintainer, on the inc-229 rework: *"if we have dropped it now, we should just drop it — time to move on."*
Inc 229 removed the geography signal + gender framing but left a prominent in-app note (and a help paragraph)
*explaining* that the tool deliberately doesn't categorize authors by gender/race/nationality. Keeping that note
visible is itself a way of keeping the removed idea alive — the exact logic that removed the geography signal
(visibility-by-category and erasure-by-category are the same machinery). So the clean "dropped" is a tool that just
measures concentration, with no monument to what it refuses to do.

## Implemented

- **`app/frontend/js/08b_methods_citation_equity.jsx`** — removed the `.cite-equity-deferred` note block from
  `CiteEquityFoot`; trimmed the intro's "…it never looks at who the cited authors are" clause and the long
  header-comment paragraph down to a terse "it measures WHAT is cited, never WHO wrote it (a guard test keeps it
  that way)."
- **`app/frontend/styles.css`** — removed the now-dead `.cite-equity-deferred` rule.
- **`app/backend/help/help_content.md`** — dropped the "It never categorizes the people you cite" paragraph,
  leaving one trailing clause on the coverage sentence ("…never at who the authors are").
- **`.claude/qa-routes/route_51_methods_citation_equity.md`** — the no-people-categorization assertion now checks
  the absence is *clean* (no identity/origin shown, and **no note about it either**), rather than looking for a note.

## What stays (deliberately)

The **regression guard test** (`test_analyzer_source_has_no_people_categorization` + the behavioral
`test_no_people_categorization_in_core`) — invisible to users, it fails CI if a future contributor re-adds
`country_code`/`GLOBAL_NORTH`/gender/race/sex keying. A protective rail is not a monument; it keeps the removed
thing from creeping back without advertising it.

## Manual verification script

`HF_HUB_OFFLINE=1 python .local/visual/drive_inc229_concentration.py` → **PASS**: Run audit → 4 signals, **0
geography mentions AND 0 gender/identity-disclaimer mentions anywhere on the page**, the ⚠ low-coverage flag still
works; 0 console/page/genai.

## Pytest

No Python changed → full suite **819 passed, 1 skipped** (unaffected). QA surface **165/165 API + 727/727 FE, 0
uncovered**. Frontend + docs only; no migration/egress/dependency.
