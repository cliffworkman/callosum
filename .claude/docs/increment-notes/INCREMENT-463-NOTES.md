# Increment 463 — Citation coverage audit for the LibreOffice adapter (backlog #33/#34, P2 item #18)

## Implemented

Fifth item in the confirmed P2-leapfrog roadmap (#19 → #17 → #20 → #21 → **#18** → #22; see memory
`callosum-p2-leapfrog-roadmap`). Roadmap #18's original checklist ("manuscript-level citation coverage
analysis") lists 9 sub-items, most needing real claim-level semantic parsing nothing in callosum does today.
Narrowed to a reuse-first v1 (confirmed with Cliff): citation-concentration structural signals scoped to the
document's own cited papers, plus a new local structural scan for long uncited prose stretches.
"Claims supported only by retracted/corrected papers" needed no new work — inc 459's "Citation integrity
preflight…" already covers it. Everything needing real claim-level semantic parsing (evidence relatedness,
review-vs-primary preference, secondhand citation) stays a deliberate v1 boundary, matching every prior item.

### New backend endpoint: `POST /methods/citation-equity/check-selected`

Added directly to `app/backend/api/routers/citation_equity.py` (355→~400 lines, well under the cap — no new
file needed). Synchronous (no `JobStore`, unlike the Library-paper and WIP versions, which run full
reference-graph traversals / self-citation field-baseline checks as background jobs) — bounded to the
document's own distinct cited papers via a 100-id cap mirroring `methods_retraction.py`'s own check-selected
precedent. Reuses `audit_reference_list` completely unmodified, with the exact honest-degraded path
`wip_citation_equity.py` already established: `focal_author_families=set()`, `field=[]`, `field_topic=None` — a
live Writer document, like a WIP manuscript, has no stored author identity and no OpenAlex record of its own to
draw a field comparison from.

### Adapter: `adapters/libreoffice/callosum_cite.py`

**Refactor first**: extracted `citation_integrity_preflight`'s inline "collect distinct, non-orphaned cited
paper ids" loop into a shared `_distinct_cited_paper_ids(doc, orphaned)` helper, now used by both it and the
new audit — behavior-preserving (all 7 existing `citation_integrity_preflight` tests pass unchanged).

**The one genuinely new piece**: `_uncited_paragraph_stretches(doc)` — a pure local structural scan (no
network, no NLI, no claim judgment) walking the document's paragraphs, tracking runs of consecutive
substantive paragraphs (≥15 words each, skipping headings/short transitions) with no citation anchor, and
flagging a run once it reaches 3 consecutive paragraphs. `_citation_anchor_ranges(doc)` collects every citation
mark's main-text anchor — an inline mark contributes its own anchor; a note-style mark (inside a footnote/
endnote) contributes the *note's own* main-text anchor instead (`XTextContent.getAnchor()` on the footnote/
endnote itself), the exact pattern `_insert_note_mark` already relies on — so a footnote-cited paragraph isn't
misread as uncited.

`citation_coverage_audit`/`_interactive` fold both pieces into one combined `_msgbox` report, mirroring
`citation_integrity_preflight`'s own "fold related read-only reports into one dialog" precedent. Registered as
`_ACTIONS["citationCoverageAudit"]`, a new macro `CallosumCitationCoverageAudit` + export, and a new Addons.xcu
menu node ("Citation coverage audit…", grouped next to "Citation integrity preflight…").

## Key technical detail

**A real bug was caught by cross-checking already-shipped code, not assumed.** My first implementation of
`_paragraph_has_citation`'s `compareRegionStarts`/`compareRegionEnds` containment check had the comparison
operators **backwards** — a plausible mistake, since I initially worked from a half-remembered recollection of
the raw UNO API docs. Before writing it into production, I grepped this same file for existing
`compareRegionStarts` usage and found `order_by_comparator`'s own docstring (line 349) stating the convention
explicitly: **`compare(a, b)` is `>0` iff `a` precedes `b`** — the opposite polarity from what I'd assumed. A
duck-typed smoke test built with my own (wrong) assumption baked into the fake had "passed" — both the fake and
the code under test shared the same wrong premise, so they cancelled out and looked correct. Only re-deriving
the containment logic against the *documented, already-battle-tested* convention (and rebuilding the smoke test
to match) caught it. This is exactly why this piece — the one part of the increment with no exact existing
precedent to copy verbatim — got its own dedicated real-UNO spike (`spike_citation_coverage_audit`) rather than
relying on unit tests alone: a unit test's fake can silently encode the same wrong assumption as the code it's
testing, but a real UNO document cannot.

## Housekeeping / gates

- **Security audit**: new addendum to `.claude/security-audits/2026-06-30_citation-equity.md` — new endpoint,
  same public-OpenAlex-metadata egress class as the already-audited base feature + the inc-457 addendum,
  bounded (100-id cap), no new dependency, the local structural scan touches no network/file at all.
- **QA route**: `.claude/qa-routes/route_51_methods_citation_equity.md`'s existing `api: /methods/citation-
  equity*` wildcard already covered the new endpoint (confirmed via `build_surface_map.py check`, 386→387
  surfaces, 0 uncovered) — added an explanatory note anyway (the route_39/route_42 precedent) naming the real
  end-to-end caller as the LibreOffice adapter via `run_roundtrip.py`, not this browser-driven route.
- `.claude/docs/INCREMENT-BACKLOG.md`: P2 item #18 marked **✅ CLOSED inc 463**; roadmap-order note updated.
- Memory `callosum-p2-leapfrog-roadmap` updated: item #18 marked closed, #22 named as the last item.
- `.claude/CLAUDE.md`: counter bumped to 463; pytest count updated to the actual measured total.

## Manual verification script

1. In Writer, cite 2+ papers with known citation counts/venues via any existing insert command.
2. Leave a stretch of 3+ substantive paragraphs with no citation, and a shorter (≤2) uncited stretch elsewhere.
3. Run **Citation coverage audit…** → confirm the concentration signals render (reliance on highly-cited work,
   venue/institutional concentration; self-citation reads "not computed," never a fabricated value).
4. Confirm exactly the 3+-paragraph stretch is flagged (with a text preview), the shorter one is not, and the
   report copy frames it as a structural note, never a claim that a citation is missing.
5. Confirm **Citation integrity preflight…** and every other existing command still works unchanged.

## Verification

- `pytest tests/test_citation_equity.py tests/test_libreoffice_adapter.py -q` → **201 passed** (3 new backend
  endpoint tests + 9 new adapter tests [the extraction regression + duck-typed structural-scan tests + audit
  orchestration tests], all UNO-free via monkeypatching).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: unaffected (`citation_equity.py` still well under the cap).
- `python tools/qa/build_surface_map.py check`: `API surfaces: 387 | covered: 387 | uncovered: 0`.
- Real-UNO: `python adapters/libreoffice/run_roundtrip.py` — the new `spike_citation_coverage_audit` proves the
  real endpoint call, the real paragraph-scan (correctly flagging exactly the 3-paragraph run and correctly
  treating the note-style-cited paragraph as cited — this is where the `compareRegionStarts`/`Ends` polarity
  bug above was empirically confirmed fixed, not merely unit-tested), and the combined interactive report. A
  **second real finding** surfaced on the spike's first live run: its original single-document design (one
  paragraph gets an inline citation, another gets a note-style citation) hit `citation_placement_error`'s real,
  pre-existing, deliberate refusal to mix inline and note-style citations in one document ("Automatic
  conversion between inline citations, footnotes, and endnotes is not available yet") — a genuine app invariant
  the spike's own setup violated, not a bug in the code under test. Fixed by splitting into two documents (one
  all-inline, one all-note-style), which also more cleanly isolates which citation-anchor mechanism each half
  of `_citation_anchor_ranges` is proving.

## Rollback

Revert the new endpoint in `app/backend/api/routers/citation_equity.py`, `adapters/libreoffice/callosum_cite.py`,
`adapters/libreoffice/oxt/Addons.xcu`, and `adapters/libreoffice/selftest_uno.py` to their pre-463 state. The
`_distinct_cited_paper_ids` extraction is a pure, no-behavior-change refactor, safe to keep even if the rest is
reverted. All changes additive/backward-compatible; no schema/migration.
