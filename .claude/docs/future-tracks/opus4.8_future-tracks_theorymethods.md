<!-- TAGS HOOK (added 2026-06-20, after tagging shipped in inc 71/72 — this doc predates tags).
     The findings subsystem below (retraction → "retracted" mark; transparency → descriptive open-data/
     open-code/prereg tags) generates per-paper FACTS that are conceptually SYSTEM TAGS. Callosum now has a
     real tag mechanism (inc 71: tags + a library `?tag_id=` filter + "Filtered to tag …" banner; inc 72:
     local c-TF-IDF suggestion). When this track is built, system-facts must be FILTERABLE the way tags are
     ("locate every RETRACTED paper across the library") — REUSE/extend the tag-filter affordance rather than
     inventing a parallel filter/chip surface. Keep system-facts visually DISTINCT + non-editable (a fact is
     not a user label); a per-paper-link provenance (vs the global `tags.import_source`) is likely needed.
     See `.claude/docs/INCREMENT-BACKLOG.md` → "Tags & keywords" → "Tags ↔ findings / system-facts". -->

Goal: Reorganize the side panels around a THEORY / METHODS distinction, replacing the
within-pane draggable top/bottom sub-split with an accordion built on an extensible module
registry, and establish DESIGN.md as the project's UI/AI principles document. This is a
structural refactor of existing working UI — behavior-preserving for the actual functionality,
changing only how sections are arranged and selected.

SCOPE: UI shell + DESIGN.md ONLY. Do NOT build the findings/flag/review subsystem, statcheck,
OpenAlex, OSF, or any METHODS check here — those are separate prompts. METHODS will have only
DETAILS as a real section after this; that is expected and fine.

STEP 1 — Discover current structure. Inspect app/frontend/js/40_app.jsx (the App shell: a
5-column grid with a left panel, center LibraryFrame, right RightPane, and Divider components
for panel resize/collapse). Identify the left panel's contents (axes; 15_axes.jsx), where the
synthesis UI currently lives (20_synthesis.jsx), and the RightPane's internal top/bottom
draggable sub-split (detail view; 25_detail.jsx). Report the current composition before changing
anything.

STEP 2 — Rename panes. Left → "THEORY", right → "METHODS". Update user-facing labels/headers.
Keep the localStorage layout keys (callosum.leftW etc.) backward-compatible or migrate cleanly
so existing saved widths and collapse state survive.

STEP 3 — Accordion via module registry. Replace the within-pane top/bottom draggable sub-split
with an accordion: each pane holds a list of registered section modules, one expanded at a time,
its header always visible, collapsed headers stacked. Build it as a REGISTRY — each section a
self-registering unit ({ id, label, paneId, render }) so adding a future section is additive; do
NOT hard-code the section list inline. Persist the open section per pane via the existing
localStorage layout pattern.
- THEORY sections: AXES (15_axes.jsx), SYNTHESIS (20_synthesis.jsx) — relocate synthesis into
  the THEORY pane if it is not already there.
- METHODS sections: DETAILS (25_detail.jsx), re-homed as the topmost section.
- PRESERVE the outer Divider behavior (panel-width resize + collapse-to-focus-the-viewer). You
  are replacing the INNER sub-split, not the outer panel resize.
- PRESERVE the center LibraryFrame tab system (30_viewer.jsx) untouched.

STEP 4 — DESIGN.md at repo root, the referenceable principles document consulted on major UI
revisions. Encode:
- Pane semantics: THEORY = knowing the thing (axes, synthesis); METHODS = evaluating how it was
  studied. Place a tool by the user's COGNITIVE TASK, not by its implementation — AI-powered is
  orthogonal to the theory/methods distinction.
- AI usage: the AI's job is to make verification cheap, never to substitute for it. Verdict
  becomes pointer; opaque selector becomes checkable selector. Test for any AI feature: "where
  did the judgment go?" — it must land on a checkable computation or on the human, never hide in
  an opaque selection step. Cosmetic-recovery failure modes to avoid: judgment hidden in the
  selection; absence-of-flag read as a verdict; irreducibly-evaluative tasks with no factual
  substrate.
- METHODS principle: deterministic checks are the substrate; AI may only narrate/organize their
  results, never freelance a methodological verdict.
- Output contract: a finding is either a FACT (persistent mark, not resolvable) or a CANDIDATE
  concern (reviewable). Badges describe the user's WORK STATE ("N to review"), not the paper's
  quality.
- Criterion-as-function-of-verification-cost: surface candidates generously only to the degree
  per-item verification is one-click cheap; the human is the filter.
- Extensibility: panel sections are a module registry; design for addable (and someday
  user-supplied) modules.
- Accessibility: differentiate with color PLUS icon/label, never color alone; prefer a
  highlight/glow over a blink; gate motion behind prefers-reduced-motion.

CONSTRAINTS:
- Behavior-preserving: axes, synthesis, and details functionality is unchanged; only arrangement
  and selection change. Existing saved layout state must survive.
- The section list is DATA (registry), not hard-coded markup.
- No new backend, no METHODS checks, no findings subsystem here.

TESTS:
- Panes render as THEORY (left) and METHODS (right); outer resize/collapse still works; center
  tabs unaffected.
- THEORY accordion switches AXES <-> SYNTHESIS; METHODS shows DETAILS; one section open at a
  time; the open section persists across reload.
- Registering a new dummy section adds it to a pane WITHOUT editing the accordion component
  (proves the registry).
- DESIGN.md exists at root with the principles above.

OUTPUT: the Step 1 current-structure report, a summary of what was renamed/relocated/replaced,
confirmation the outer resize and center tabs are intact, and the DESIGN.md path.

=================================================================================================

Goal: Build the shared findings + review subsystem that every METHODS check emits into — a store
for per-paper findings, the facts-vs-candidates contract, the library "N to review" badge, and
the typed review workflow. No real check is built here; a fake finding exercises the UI.
Producers (retraction, statcheck, prereg, transparency) are later prompts that emit into this.

DEPENDS ON: the UI-shell prompt (THEORY/METHODS panes, accordion module registry, DESIGN.md). If
absent, report and stop.

CORE CONTRACT (document in code; reference DESIGN.md's output-contract section):
A Finding is one of two kinds:
- FACT: an established truth about the paper (e.g. retracted). Rendered as a persistent mark.
  NOT resolvable — nothing to adjudicate.
- CANDIDATE: a possible concern surfaced for the user to check. Reviewable. Carries an optional
  TIER ('primary' = structural/high-confidence vs 'speculative' = semantic/low-confidence) and
  optional text-location anchors for click-to-highlight.
Badges describe the user's WORK STATE ("N to review" = unreviewed candidate count), never paper
quality.

BACKEND:
1. Schema (alembic): paper_findings — id, paper_id (FK), source (string: producing check),
   kind ('fact'|'candidate'), tier (nullable), payload (JSON: the finding; for candidates include
   location anchors), content_key (stable hash of source + normalized payload + paper
   content-version, for idempotency), review_state (nullable:
   'unreviewed'|'confirmed'|'accepted'|'noted'; null for facts), review_reason (nullable),
   reviewed_at (nullable), created_at. Unique on (paper_id, source, content_key).
2. Findings repository (provider-neutral — this is the contract producers call):
   - upsert_findings(conn, paper_id, source, findings): IDEMPOTENT and REVIEW-STATE-PRESERVING.
     If a content_key already exists, do NOT reset its review_state (the user's review survives
     re-runs). A new content_key is a fresh unreviewed finding; mark superseded findings from the
     same source as stale.
   - reads: findings for a paper (grouped facts vs candidates; candidates by review_state and
     tier); library overview (per-paper { unreviewed_count, has_facts }).
   - set_review_state(conn, finding_id, state, reason): candidates only; ENFORCE that
     state='accepted' requires a non-empty reason; 'confirmed'/'noted' allow an optional one.
3. API (routers/findings.py, via create_app DI + get_connection):
   - GET /papers/{id}/findings ; GET /findings/overview ; POST /findings/{id}/review {state,reason?}.
4. Seed: a FakeFindingProducer (or seed fixture) writing two findings to a paper — one FACT and
   one CANDIDATE (with a tier and a dummy anchor) — mirroring the existing fake-injection style.

FRONTEND (new module, e.g. 26_findings.jsx):
- FactMark: neutral persistent indicator (e.g. a "retracted" tag), VISUALLY DISTINCT from the
  review badge so a fact is never mistaken for an unreviewed candidate.
- FindingCard: renders a candidate — description, tier (speculative shown distinctly; consider an
  "also check these" expander), and review controls. If it has anchors, wire click-to-highlight
  through the EXISTING quote-routing mechanism (synthesis/openCitation) — do not build a new
  highlighter.
- Review controls: Confirmed / Accepted / Noted one-click; 'Accepted' opens a required one-line
  reason; others commit immediately with optional "add note". Optimistic update + POST; badge
  updates.
- Library badge: on each paper card (locate where cards render — Sidebar in 10_pdf_layer.jsx /
  the LibraryFrame library view), show the neutral "N to review" count and, separately, the
  FactMark. Zero unreviewed shows NO review badge (reads as "nothing surfaced", not "passed").
- Register a "Review" METHODS section via the module registry so the seeded candidate is
  reviewable end-to-end.

CONSTRAINTS:
- No real producers here. Only contract, store, API, UI, seeded fake.
- Idempotent, review-state-preserving upsert is non-negotiable: re-running a producer must NOT
  wipe reviews on unchanged findings.
- Facts are not resolvable; the badge counts only unreviewed candidates.
- Reuse the existing highlighter; register the METHODS section via the existing registry; state
  lives in the table, not localStorage.

TESTS:
- Seeded fact renders as a distinct persistent mark; seeded candidate as a reviewable card.
- Reviewing (Confirmed/Noted one click; Accepted needs a reason) persists and drops the count;
  reload preserves it.
- Re-running the seed (same content_key) does NOT reset a reviewed finding; a changed payload
  (new content_key) creates a fresh unreviewed one.
- Library badge shows the count and the fact mark independently.

OUTPUT: the migration + table, the repository contract (the signatures producers will call), the
endpoints, the new frontend module + registered METHODS section, and confirmation the seed
exercises the full path.

=================================================================================================

Goal: First real METHODS producer — a retraction check that emits FACT findings into the
findings contract, sourced from Crossref. Reuses the existing Crossref adapter and the FactMark
UI; builds no new contract or component.

DEPENDS ON: the findings subsystem prompt (contract, upsert_findings, FactMark, library badge)
and the existing Crossref adapter (integrations/crossref/adapter.py). If absent, report and stop.

DEFAULT SOURCE: Crossref (the integrated Retraction Watch data). Scite MCP is a deliberate later
enrichment, not used here.

BACKEND:
1. Retraction check: given a paper's DOI, use CrossrefClient to fetch the work record and detect
   retraction / correction / expression-of-concern status. NOTE: this signal lives in the RAW
   Crossref message (update-to / relation / assertion fields), which may not survive the CSL
   projection the adapter returns — read the raw cached response_json, and VERIFY the current
   Crossref field semantics for retraction relations before relying on them.
2. Emit FACTs via upsert_findings(conn, paper_id, source='retraction', findings=[...]): kind=
   'fact', payload = { status: 'retracted'|'correction'|'concern', notice_doi, notice_url, date,
   reason? }. content_key derived from the notice + paper version, so re-runs are idempotent.
3. WORLD-STATE / TTL caching: retraction is the one deterministic check whose INPUT is world
   state, not paper text — a paper can be retracted years after import. So cache the Crossref
   retraction lookup with a TTL (it changes), and refresh on a cadence / explicit trigger, NOT
   only at import. This is exactly the case where TTL invalidation is correct because the signal
   isn't captured by the paper's content key. Provide: an initial check at import, a per-paper
   "refresh retraction status", and a library-wide refresh.
4. COVERAGE / silence-doesn't-lie: absence of a retraction mark means "none found among CHECKED
   papers." For papers that couldn't be checked (no DOI, or Crossref didn't resolve), record
   status = unknown — do NOT imply "clean." Surface "retraction status unchecked" subtly in the
   paper's findings detail, NOT as a loud card-level mark.

FRONTEND:
- Feed the EXISTING FactMark (from the findings subsystem) with retraction data: the card shows a
  neutral "retracted" / "correction" / "concern" mark with click-through to the notice. The
  paper's findings detail shows reason / date / notice link, and for uncheckable papers the
  subtle "unchecked (no DOI)" note. Reuse FactMark and the findings detail view — build no new
  components.

CONSTRAINTS:
- Reuse the Crossref adapter, the findings contract (upsert_findings), and FactMark.
- Facts are not resolvable.
- Cache the Crossref lookup with a TTL; never imply "clean" for an unchecked paper.
- Crossref is free (polite-pool mailto via the existing CALLOSUM_CROSSREF_MAILTO) — no key, but
  stay within polite rate limits and lean on the cache.

TESTS:
- A known-retracted DOI produces a retraction FactMark + populated detail; a clean DOI produces
  no mark; a no-DOI paper records status=unknown (no card mark, not "clean").
- Re-running the check does NOT duplicate findings (idempotent content_key) and does NOT disturb
  unrelated findings.
- A TTL-expired refresh picks up a newly-retracted paper on the next refresh.

OUTPUT: the retraction check module, how it emits into the findings contract, the import/refresh
triggers and TTL, and confirmation it reuses FactMark and the Crossref adapter.

=================================================================================================

Goal: statcheck producer — port the deterministic APA-NHST p-value recomputation to Python and
emit CANDIDATE findings (the computed mismatch as evidence) into the findings contract. Whether a
mismatch matters is the user's judgment, so these are reviewable, not facts.

DEPENDS ON: the findings subsystem (upsert_findings, FindingCard, review workflow, the existing
highlighter) and the paper's extracted text. If absent, report and stop.

BACKEND:
1. Port statcheck's deterministic logic to Python (do NOT add an R dependency): regex-extract
   APA-style NHST results (t, F, r, chi-square, z, etc. with degrees of freedom and a reported
   p), recompute p from the test statistic + df via the appropriate distribution, and compare to
   the reported p. VALIDATE against statcheck's documented behavior and edge cases — one- vs
   two-tailed, p reported as "ns"/"<.05"/"=.000", rounding, corrected df.
2. Classify each mismatch: 'minor' (reported and recomputed differ) vs 'gross' (the difference
   crosses the significance threshold — could flip the stated conclusion).
3. Emit CANDIDATES via upsert_findings(conn, paper_id, source='statcheck', ...): kind='candidate',
   tier='primary' (high-confidence detection — uniform), payload = { reported:{stat,df,p},
   recomputed_p, severity:'gross'|'minor', text_anchor }. Severity lives in the payload (the card
   surfaces it); tier is confidence, not consequence — keep them separate.
4. Run timing: STATIC given the paper text — run on import and on re-extraction (content_key keyed
   on the paper's text version). No TTL (unlike retraction, the input doesn't change).
5. COVERAGE / silence-doesn't-lie: record what was parsed. Absence of statcheck flags means "no
   inconsistencies among the parseable APA-NHST results," NOT "the statistics are sound." Surface
   the scope in the paper's findings detail: "checked N APA-NHST results; does not assess Bayesian
   stats, confidence intervals, or statistics in tables/figures."
6. EXTRACTION-ERROR mitigation: a misread digit from PDF extraction can produce a false
   inconsistency. The text_anchor (click-to-source showing the actual reported statistic) is the
   mitigation — the user sees the real text and catches extraction artifacts in one click. Make
   the anchor mandatory on every flag.

FRONTEND:
- Reuse FindingCard: render the computed mismatch as the evidence ("reported t(28)=2.10, p=.02;
  recomputed p=.045"), emphasize 'gross' ones, and wire the text_anchor to click-to-highlight the
  reported statistic in the paper via the EXISTING highlighter. Reuse the existing review controls
  (Confirmed = typo/not consequential; Accepted = real but doesn't change the conclusion; Noted =
  affects how I'll cite). Build no new components.

CONSTRAINTS:
- Reuse the findings contract, FindingCard, review workflow, and highlighter.
- Port the logic; no R dependency.
- Candidates are reviewable; tier='primary' uniform; severity in payload.
- Bound the claim — never let absence of flags imply the stats are fine.

TESTS:
- A paper with a known reporting inconsistency yields a primary candidate showing reported vs
  recomputed plus a working source anchor; a conclusion-flipping case is marked 'gross'.
- A clean paper yields no flags but records coverage (N results checked, scope note present).
- Re-running is idempotent (content_key); a re-extraction with changed text refreshes flags.
- Reviewing a flag (Accepted requires a reason) persists and drops the "N to review" count.

OUTPUT: the ported statcheck module, how it emits candidates into the contract, the import/
re-extraction run timing, the coverage/scope handling, and confirmation it reuses FindingCard and
the highlighter.

=================================================================================================

Goal: Transparency-indicator producer — port oddpub/rtransparent positive detection to Python and
emit neutral, descriptive FACT findings (open-data / code / registration / COI / funding
statements). POSITIVE detections only. Feed any detected registration link forward to the
prereg-deviation producer.

DEPENDS ON: the findings subsystem (FactMark, upsert_findings) and the paper's extracted text.
If absent, report and stop.

KEY DESIGN — error asymmetry drives positive-only surfacing:
- High specificity, moderate sensitivity. A POSITIVE detection is reliable; an ABSENCE is
  "not detected" (often a miss), NOT "absent." Surface positives; do NOT surface "no data
  statement" as a concern — it would false-alarm on transparent papers, and verifying the absence
  costs a full read.
- BOUNDED MEANING: these detect the STATEMENT, not the reality. "Data available on request"
  counts as a statement but is not actual access. Every mark must carry "statement detected; not
  verified that the resource is accessible or usable."

BACKEND:
1. Port the oddpub/rtransparent detection logic to Python (keyword/regex/text-mining; no R
   dependency): open-data statement, open-code statement, protocol/registration statement, COI
   statement, funding statement. VALIDATE against the documented behavior.
2. Emit POSITIVE detections as FACTS via upsert_findings(conn, paper_id, source='transparency',
   ...): kind='fact', payload = { indicator, detected_statement_text, resource_url?, text_anchor,
   meaning:'statement detected; not verified accessible', provenance:'biomed-validated;
   psych/neuro revalidation pending' }. Run on import / re-extraction (content_key on the text
   version); no TTL.
3. COVERAGE / silence: record that absence = not-detected, not absent. Surface this in the paper's
   findings detail; do not render any "missing transparency" concern.
4. PREREG HANDOFF: when a registration/protocol statement is detected with a registry or OSF link,
   store that link in a form the prereg-deviation producer (next prompt) consumes as its input.

FRONTEND:
- Use FactMark in a NEUTRAL/DESCRIPTIVE variant, visually distinct from the negative retraction
  mark (these are descriptive tags, not warnings, and not quality endorsements). Tags like
  "open data (detected)", "code (detected)", "preregistered (detected)". Click -> the resource
  URL plus the source anchor via the existing highlighter. The detail view shows the detected
  statement text, the bounded-meaning note, and the biomed-revalidation caveat. Do NOT render
  these as a score, a checkmark, or anything implying "trustworthy paper."

CONSTRAINTS:
- Positive-only; facts (not reviewable); bounded meaning on every mark; visible revalidation
  caveat from day one.
- Port the detection; no R dependency.
- Reuse FactMark (neutral variant) and the highlighter; never imply absence means non-transparent
  or that a detected statement means verified access.

TESTS:
- A paper with a data-availability statement yields a neutral "open data (detected)" fact linking
  to the resource and a working source anchor.
- A paper with an absent or oddly-phrased statement yields NO "missing data" concern (positive-
  only holds).
- The bounded-meaning note and the biomed-revalidation caveat are visible on the marks/detail.
- A detected registration link is stored in the form the prereg producer will consume.
- Idempotent (content_key); re-extraction refreshes; the marks never render as a quality verdict.

OUTPUT: the ported detection module, how positives emit as descriptive facts, the prereg-link
handoff, the neutral FactMark variant, and confirmation absence is never surfaced as a concern.

=================================================================================================

Goal: Prereg-deviation producer — compare a paper's preregistration (structured OSF) against its
published analyses and surface potential discrepancies as reviewable CANDIDATES in two tiers.
Builds the OSF registration-fetch adapter. The AI does alignment/extraction only; the verdict on
any mismatch stays with the user.

DEPENDS ON: the findings subsystem (FindingCard, review workflow, tiers, highlighter), the
transparency producer's registration-link handoff, and the paper's extracted text. Builds a new
OSF adapter. If dependencies are absent, report and stop.

BACKEND:
1. OSF adapter (new: integrations/osf/, following the crossref adapter pattern — injectable
   fetcher, httpx, external_api_cache caching, frozen-dataclass result). OSF's public API is free
   (Apache-2.0, public nodes need no login). Given a registration GUID/DOI/URL, fetch the
   structured registration and extract the analysis-plan field(s). VERIFY the current OSF API
   schema for registration responses (registration_responses / registered_meta) before relying on
   field names. Cache responses.

2. Registration resolution + HANDOFF CONTRACT: consume the registration link emitted by the
   transparency producer, OR a manual per-paper attachment. Attempt to resolve it as an OSF
   registration. If it is not an OSF registration, or the link is dead/unparseable, emit an
   informational "registered, not verifiable here" state — NOT a candidate, NOT a clean
   implication. Provide a manual attach/override of the registration URL per paper.

3. ENUMERATION layer (deterministic, tier='primary'): from the structured analysis plan, enumerate
   registered analyses and check presence in the paper's analysis section. Emit primary candidates
   for: registered-but-not-reported, and reported-but-not-registered ("unregistered analysis").
   High confidence. Runs when a registration resolves (cheap: free OSF fetch + local presence
   check).

4. CORRESPONDENCE layer (semantic, tier='speculative'): for matched pairs, a grounded LLM
   alignment call (reuse the summary-generator pattern) that aligns registered analysis i to
   reported analysis j and EXTRACTS the differing attribute (test type, DV, covariates,
   exclusions, N). It retrieves and extracts over two real texts; it does NOT judge whether the
   difference is acceptable. Emit speculative candidates stating the concrete attribute mismatch.
   ON-DEMAND and CACHED (content_key over registration version + paper text version + model +
   prompt-template version), per the token-optimization pass.

5. DUAL ANCHORS: every candidate carries both a registration-text anchor and a paper-text anchor,
   so click-to-highlight shows both sides via the existing highlighter. One-click side-by-side
   verification is what justifies surfacing generously.

6. Emit via upsert_findings(source='prereg', kind='candidate', tier=...). content_key over
   registration + paper text versions; idempotent and review-state-preserving.

7. COVERAGE / silence-doesn't-lie: record what was compared and what wasn't. Absence of flags is
   NOT "faithful to prereg." Surface scope in detail: "compared the registered analysis plan
   against the paper's analysis section; does not assess hypotheses, sampling, or design fidelity."

FRONTEND:
- Reuse FindingCard. Each candidate states the concrete mismatch ("Registered: 2x2 ANOVA on
  accuracy. Reported: linear mixed model on accuracy.") with DUAL click-to-highlight
  (registration | paper). Primary candidates shown directly; speculative ones behind the "also
  check these" expander, visually distinct, NEVER promoted to primary.
- "Registered, not verifiable here" renders as a neutral informational note (not a concern, not a
  clean checkmark).
- A manual registration-URL attach/override control per paper.
- Reuse review controls (Confirmed = not a real deviation; Accepted = real but acceptable; Noted =
  affects how I'll cite).

CONSTRAINTS:
- Recovered execution: never characterize a mismatch as good/bad — state it, route to both texts,
  leave the verdict to review.
- The two tiers stay distinct; speculative never promoted; semantic behind the expander.
- The LLM does alignment/extraction only (grounded, cached); no methodological judgment.
- Bounded claim; uncheckable prereg gets the honest unverifiable state, never "clean."
- Reuse the findings contract, FindingCard, review workflow, and highlighter; build the OSF
  adapter on the crossref pattern; cache both the OSF fetch and the LLM alignment.

TESTS:
- An analysis registered-but-not-reported yields a primary candidate; reported-but-not-registered
  yields a primary "unregistered analysis" candidate.
- A matched pair with a changed test/DV yields a speculative candidate stating the attribute
  mismatch, behind the expander.
- Each candidate's dual anchors highlight the registration and the paper text.
- A dead/non-OSF registration link yields "registered, not verifiable here" — not clean, not a
  candidate.
- Manual URL attach runs the check on a paper whose link wasn't auto-detected.
- Absence of flags surfaces the coverage note, never "faithful."
- The LLM alignment is cached (content_key); re-runs don't re-call or reset reviews; idempotent.

OUTPUT: the OSF adapter surface, the resolution/handoff and manual-attach path, the enumeration
and correspondence layers and how each emits into the contract, the caching, and confirmation it
reuses FindingCard, the review workflow, and the highlighter.

=================================================================================================

Goal: EVALUATE — the narration-and-container layer over all METHODS producers. A consolidated,
grounded per-paper view that organizes the findings, consolidates their coverage into one honest
scope statement, and optionally adds a grounded methods-and-limitations summary. It produces NO
new findings and makes NO judgments — it organizes what the producers emitted and what the user
reviews.

DEPENDS ON: the findings subsystem and the producers (retraction, statcheck, transparency,
prereg). It reads their output; it can be built against whatever producers are present plus the
seeded fake. If the findings subsystem is absent, report and stop.

BACKEND:
1. COVERAGE CONSOLIDATION (the spine — deterministic): gather each producer's coverage/scope
   metadata for the paper into ONE structured scope statement — per dimension, "checked / not
   checked / not verifiable." A dimension whose producer did not run shows "not checked," NEVER
   blank-implies-clean. (Producers from the prior prompts already record coverage; consolidate it.
   Define the shared coverage shape if it isn't already uniform.)
2. FINDINGS NARRATION (deterministic templating — NO LLM): a plain-language organization of the
   paper's findings (facts + candidates, grouped by source, with counts and severity/tier), every
   clause linking to its finding_id / source anchor. It states only what is in the findings table;
   it introduces no new claim. (An LLM-smoothed variant is a possible future knob, but the default
   is templated and grounded-by-construction.)
3. METHODS SUMMARY (optional, DEFERRABLE — the only LLM touch): a grounded summarization of the
   paper's methods section via the existing summary generator + verification, with click-to-text.
   Limitations: DETECT the method/modality from the text (retrieval), then attach CURATED known
   limitations from a small curated knowledge base — never freelance limitations. If no curated
   source exists, omit limitations rather than generate them. Cached and token-gated per the
   optimization pass.

FRONTEND:
- An EVALUATE METHODS accordion section (registered via the module registry). For the selected
  paper, render, in order: (1) the consolidated coverage/scope statement; (2) the organized
  findings — reuse FactMark for facts and FindingCard (with the review workflow) for candidates,
  grouped by source, primary above speculative; (3) optionally the methods summary with
  click-to-text. This becomes the primary consolidated METHODS view, extending the basic Review
  section from the findings subsystem.
- Every rendered claim traces to a finding or an anchor — no orphan statements.

CONSTRAINTS:
- EVALUATE introduces NO findings and NO judgments. Where-did-the-judgment-go: it stays with the
  producers (deterministic) and the user (review); EVALUATE adds none.
- Narration is deterministic templating; the only LLM call is the deferrable methods summary
  (grounded, verified, cached). Limitations are curated-lookup, never freelanced.
- Coverage consolidation must be honest: a dimension with no producer run is "not checked," never
  implied clean.
- Reuse FactMark, FindingCard, the review workflow, the highlighter, the summary generator, and
  the module registry. Build no parallel components.

TESTS:
- For a paper with findings from multiple producers, EVALUATE shows them organized plus a
  consolidated coverage statement listing checked / not-checked / not-verifiable dimensions.
- The findings narration contains no claim that doesn't trace to a finding (templating is
  grounded-by-construction).
- A paper not run through a given producer shows that dimension as "not checked," not clean.
- The methods summary, if built, is grounded/verified with working click-to-text and is cached;
  disabling it leaves the consolidated view fully functional (it is deferrable).
- EVALUATE writes no findings and no review state to the store.

OUTPUT: the coverage-consolidation logic and shared shape, the deterministic narration, the
optional methods summary and its grounding, the EVALUATE section wiring, and confirmation it
reuses every existing component and adds nothing the user has to trust unverified.
