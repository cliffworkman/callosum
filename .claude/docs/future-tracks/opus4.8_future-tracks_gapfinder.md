Goal: A literature GAP-FINDER in the research tab — surface papers likely relevant to the user's
library but absent from it, via established citation-based methods, each candidate carrying
transparent PROVENANCE, ranked by axis relevance, surfaced as reviewable add-or-dismiss
candidates. Augments the user's judgment; never decides what they read. (Recorded for future
implementation.)

DEPENDS ON: the OpenAlex adapter (build first as shared infra — referenced_works for backward,
cited_by for forward, author resolution for follow-authors; cache in external_api_cache; this is
its fourth consumer); the research tab (lit feed/search); embeddings + axis_scoring for relevance;
the candidate/dismissal pattern from My-Publications; the library save/import path.

CANDIDATE GENERATORS (build in cost/precision order):
1. BACKWARD GAP (cheapest, highest precision — FIRST): from each library paper's referenced_works
   (already in its OpenAlex record), count references across the library; surface references cited
   by >= k library papers but ABSENT. Provenance: "cited by N of your papers on [axis]."
   Whole-library is fine (cheap).
2. FOLLOWED AUTHORS (cheap — SECOND; reuses My-Publications author resolution): store followed
   OpenAlex author IDs; fetch their works (cached/TTL); surface works absent from the library and
   relevant to axes. Provenance: "by [followed author], matches [axis]." A lightweight subscription.
3. FORWARD GAP (moderate cost — THIRD; SCOPE to a selected axis): for the axis's papers, fetch
   citing works (cited_by), find citers that cite >= k library members; surface absent citers.
   Provenance: "cites M of your papers on [axis]." Cap citers per paper; on-demand only.
4. CO-CITATION PROPER (DEFER): forward + another hop; richest, most expensive; the above three
   approximate most of its value.

RANKING & PROVENANCE (the principle core):
- The citation graph PROPOSES; axis embeddings RANK/FILTER (damp citation-central-but-off-topic
  papers, e.g. ubiquitous methods refs).
- Every candidate carries explicit PROVENANCE (the citation evidence + axis match + similarity).
  The suggestion is a pointer to a verifiable citation relationship, never an opaque "you'll like
  this."
- Surfaced as reviewable CANDIDATES: one-click add-to-library (flows into the pipeline) or dismiss;
  dismissals PERSIST (reuse the My-Publications decisions pattern) so the same false positive does
  not recur.

ANTI-OFFLOADING CONSTRAINTS (adapted — this cannot be comprehensive):
- Because it cannot show all missing papers, its honesty mechanism is PROVENANCE + DISCLOSED
  PARTIALITY, not completeness: it surfaces SOME grounded candidate gaps; absence of a suggestion
  NEVER implies the library is complete. State this in the UI.
- PULL tool: on-demand ("find gaps in [axis]" / "check followed authors"), never auto-surfaced; the
  user points it.
- The user stays the one who adds; the tool proposes with evidence, the user judges.

SHARED REUSE:
- The forward-citation engine ("who cites this set, weighted by overlap") is the SAME computation
  for the library (gap-finding) and the user's own publications (My-Publications engaged-audience /
  candidate-collaborators). Build it ONCE as a shared who-cites-this-set service; two consumers,
  different sets.

COST DISCIPLINE:
- OpenAlex is paid/rate-limited: all generators on-demand, cached, scoped (backward whole-library
  is cheap; forward scoped to an axis; follow-authors per author). Never eager; manual refresh.

HONEST LIMITS (document in the coverage note):
- Citation lag — forward signal weak for very recent papers (backward unaffected).
- OpenAlex field coverage varies (strong in the sciences).
- Foundational/methods papers surface as "gaps" you may not need — axis-filter + dismissal handle
  this.
- Partial by construction.

PLACEMENT: a section/sub-tab in the research tab (with lit feed + search), reusing the
triage/candidate-list and save components.

TESTS:
- Backward: a reference cited by k+ library papers but absent surfaces with "cited by N" provenance
  and an axis match; one already in the library never surfaces.
- Follow-authors: a followed author's relevant absent work surfaces with provenance; their in-library
  works do not.
- Forward (axis-scoped): a paper citing multiple library members surfaces with "cites M" provenance;
  single-citation citers rank lower/filtered.
- Dismissals persist; add-to-library flows into the pipeline.
- All OpenAlex calls cached; nothing runs eagerly; partiality is disclosed (no "complete" implication).
- The who-cites-this-set service returns correct results for both a library set and a publications set.

OUTPUT: the OpenAlex adapter extensions, the generators in build order, the shared who-cites-this-set
service, the provenance + dismissal handling, the research-tab section, and confirmation it is
pull-only, cached, and never implies completeness.
