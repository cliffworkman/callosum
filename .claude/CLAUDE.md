# CLAUDE.md — callosum base of operations

This file is the session-start briefing for any Claude Code session opened at the callosum
project root. It describes what callosum is, the non-negotiable design invariants every
change must honor, how to run and verify the project, the rules every edit follows, and the
operational conventions that keep the project sane across sessions. **Read it before changing
anything.**

`.claude/` (this file's home) is **dev-only working space — never part of the shipped
application.** Temporary scripts, backups, research, audits, and plan files all live here.

---

## Project overview

**callosum** is a **local-first scholarly research environment** that keeps literature, evidence,
methods, manuscripts, and scientific provenance connected throughout the research and writing process.
It began with one thesis: *LLM summaries are only trustworthy if every citation is independently
verified against the source PDF.* You import a library (Zotero first), the app extracts and
chunks each PDF with page + bounding-box coordinates, embeds everything locally, clusters
papers along user-defined semantic axes, and generates citation-grounded summaries where
**every sentence is checked back against the source and shown with its evidence** (quote,
page, confidence).

It is currently at **Increment 500** (see Increment workflow) with **2486 root-suite pytest tests
passing** (+ 11 opt-in Chromium smoke tests + the inc-120 Codex-driven QA route suite). It is a working MVP backed by a
thorough planning suite in `.claude/docs/`.
(A substantial "backend-free public demo" subsystem — `demo/`, `tools/demo/`, `app/backend/demo_*.py`,
`tools/qa/check_demo_experience_coverage.py`/`check_website_coverage.py`, plus a new `www/how-it-works.html`
pipeline-explainer page — landed between incs 479 and 480 without its own increment number: it was built across
several Codex sessions this same calendar week and only got committed to git in bulk once its handoff was
picked up mid-session. See `.claude/security-audits/2026-08-10_static-online-demo.md` and `demo/README.md` for
its own design/threat-model documentation; a proper retroactive increment-notes entry for it is a known gap,
not yet backfilled.)
(Increments 109–116 — frontend/UX TDL items incl. the inc-110 PDF page-view — are journaled in `RECOVERY-LOG.md`;
the full per-increment narrative for all other increments now lives in the relocated
`.claude/session-kickoff-log.md`, and the detailed per-increment diary in `.claude/docs/increment-notes/`.)

**Stack:**
- **Backend:** Python 3.11+, FastAPI + Uvicorn (`app/backend/api/app.py`).
- **Persistence:** SQLite via SQLAlchemy Core 2.0; Alembic migrations (`alembic/`).
- **Vectors:** `sqlite-vec` (in-process, no separate daemon) + sentence-transformers
  (default embed model `all-MiniLM-L6-v2`; `bge-base-en-v1.5` also supported).
- **Clustering:** scikit-learn agglomerative clustering + local axis scoring.
- **Explicit feedback (inc 439):** the top-menu Feedback dialog builds either a bug or feature report and shows the
  exact strict version-1 JSON before explicit egress. The local API can reach only `CALLOSUM_FEEDBACK_RELAY_URL`; the
  separately deployed `feedback_relay/` repeats validation, rate-limits by existing verified account or source IP,
  and injects a generic publisher. Slack webhook/config/formatting stays server-only and uses neutralized plain-text
  blocks. No scholarly diagnostics, persistence/outbox, silent retry, device identifier, or GitHub publisher exists.
- **Axis-scoring identity (inc 438):** the deterministic scoring stream is one row per paper even if a long-lived
  database contains duplicate current embedding records from overlapping first-time jobs. Scoring keeps the strongest
  hit per paper and breaks identical-vector ties by the oldest embedding id before assignment/status calculation, so
  legacy storage duplication cannot inflate counts or violate the `cluster_node_papers` primary key. Existing embedding
  history is left intact; this is a read-time canonicalization invariant, not a destructive repair migration.
- **Document scope (inc 425):** chunk reads are explicit about canonical attachment roles
  (`article-fulltext`, `supplement`, `preregistration`, `protocol`, `other`). The ordinary paper/synthesis/search
  paths cannot read registration chunks by fallback; exact attachment reads remain available for future paired
  comparison. Legacy `primary`/null/supplement roles are normalized without a destructive migration, and an AST
  regression test rejects new ambiguous paper-level chunk, embedding, or semantic-retrieval calls.
- **Registration references (inc 426):** Transparency distinguishes registration language from an actionable,
  evidence-bearing reference; local extraction covers OSF/AsPredicted/ClinicalTrials.gov/PROSPERO plus contextual
  DOI/URL references and PDF link targets hidden behind text such as “here.” References are persisted separately from
  future candidate/confirmed links. Manual URL/DOI saving, local PDF attachment, and existing-attachment role marking
  perform no provider request; local registration PDFs are stored under `preregistration` role and remain excluded
  from ordinary article consumers by the inc-425 invariant.
- **Registration discovery (inc 427):** an explicit per-run consent step sends only paper DOI/title and detected
  registration identifiers to bounded OSF/DataCite metadata providers; authors/year stay local for contextual
  matching and no document text leaves. Candidate links persist separately with provenance, a three-class evidence
  ladder, confirm/reject state, and provider errors. Discovery never runs on panel open, never auto-attaches, and
  confirmation does not acquire content. Direct AsPredicted/manual references require no provider request.
- **Registration acquisition (inc 428):** only an explicit action on a user-confirmed link downloads a public OSF
  structured record or validated AsPredicted PDF. Deterministic local rendering preserves raw ordered responses,
  schema/amendment/source metadata, and every content hash in an immutable version row; changed content creates a new
  managed `preregistration` attachment and leaves the prior basis intact. Local PDFs use the same version seam without
  egress. Panel load and confirmation do not acquire, and acquisition is never presented as comparison or verification.
- **Registration commitments (inc 429):** an acquired version is locally/deterministically mapped into bounded plan
  fields with verbatim registration evidence, structured value, question/section, attachment/chunk/page locator,
  extraction method/confidence/version, study label, and exact registration hash. Structured OSF/AsPredicted mappings
  are preferred; conservative local-PDF text mapping leaves unknowns unmapped. This is extraction, not comparison or
  a judgment, and no model/provider is called.
- **Registration publication retrieval (inc 430):** each commitment searches compatible article section families
  first using cached local embeddings, adds same-attachment context, and expands to the whole article only after a
  weak bounded search. Supplements are explicit opt-in scope; registration chunks are unreachable as publication
  candidates. Results preserve sections searched, expansion/supplement state, exact evidence anchors, and study labels;
  multi-study uncertainty is `ambiguous`, and a miss is never proof of non-reporting.
- **Registration comparisons (inc 431):** a local background job persists versioned, paired-evidence crosswalk rows
  with bounded statuses, explanations/uncertainty, exact search scope, timing detail, and human review/note state.
  Deterministic numeric/threshold/outcome/model checks surface inspectable candidates; unresolved semantics remain
  `not-comparable`. Registration/article/included-supplement and pipeline fingerprints visibly/persistently stale old
  runs. There is no overall compliance/integrity/risk/deviation score, author judgment, or positive certificate.
- **Registration comparison UI (inc 432):** the reader-facing state machine covers reference/candidate through
  acquisition/version choice, compare/re-run options, responsive side-by-side evidence, source opening/raw
  inspection, timing/scope/uncertainty, row review/dismiss/note, stale recovery, and incorrect-match correction.
  Incorrect links cannot start a comparison. The all-aligned state still denies a positive certificate;
  amber/indigo/neutral chrome never turns the crosswalk into a green paper grade. Inc 434 gives the rich workflow its
  dedicated Synthesize workspace while leaving reference evidence in Transparency.
- **Registration workflow hardening (inc 433):** OSF collections/file manifests are bounded and paginated; provider
  status and user confirmation are rechecked at transactional writes; empty extraction fails closed; exact searched
  chunks/source checksums constrain timing and remain visible; attachment-role changes invalidate local links; and
  timing incorporates existing-data/update evidence. Every curated evaluation case traces to an executable test.
- **Meta-Preregistration workspace (inc 434):** the information-dense discovery/acquisition/comparison workflow now
  lives in **Synthesize → Meta-Preregistration** after Critique. Transparency retains local disclosure/reference
  evidence plus a compact handoff. General cards, fields, inputs, action rows, notices, spacing, and radii reuse the
  Settings vocabulary; paired evidence and semantic flag rules remain domain-specific. Navigation or workspace mount
  performs no registry request, acquisition, or comparison.
- **Registration-comparison AI triage (inc 435):** an explicit, existing-gate model call can annotate a current saved
  crosswalk as prioritize/uncertain/likely lower-yield from bounded paired passages. It is a reversible display layer:
  **All rows** restores the unchanged crosswalk, missing/malformed labels fail open, and evidence/prompt/document drift
  makes annotations stale. Whole documents, source locators, chunk IDs, notes, and review state are not sent.
- **Status/progress invariant (inc 436):** every backend job family has a bounded click destination, every shared
  `ProgressBar` registers with the Status popover unless a backend job or tracked request owns the same operation, and
  all synchronous provider-AI and installed-local-AI routes are explicitly tracked. Status names the compute boundary,
  shows real completion/ETA when measurable and an honest indeterminate state otherwise, works on mobile, and never
  serializes job results, prompts, passages, file paths, or arbitrary URLs. New `JobStore`s must extend
  `JOB_NAV_DEFAULTS`; new synchronous AI endpoints must extend `TRACKED_AI_REQUESTS`. **Inc 437 noise exception:**
  routine `library_scan_jobs` and `wip_scan_jobs` retain inline progress but never enter Status (running or finished),
  because their frequency crowds out actionable work; `STATUS_HIDDEN_STORES` and a regression test pin that choice.
- **Methods (deterministic, local, no-LLM):** statcheck NHST p-value recomputation (`scipy.stats`), inc 95;
  inc 387 conservatively adds clearly headed table rows from local PDF/JATS/XML/HTML/DOCX/ODT attachments
  without mixing reconstructed rows into prose chunks or embeddings; inc 388 keeps the evidence-bearing PDF
  attachment with page-anchored statcheck/Bayesian/LMM/meta-analysis/transparency source jumps; inc 392 closes
  the same gap for Work → Cite suggestions and visibly names the active local PDF in the viewer toolbar; inc 393
  gives explicit registry correction records their positive, evidence-linked surface and system-fact tag without
  inferring replication or turning absence into a certificate; inc 400 caches the per-paper statcheck result
  (`paper_statcheck_cache`, storing the itemized bbox-bearing payload verbatim so a cached redisplay is
  byte-identical to a live run) instead of recomputing on every paper selection, with an explicit Rescan control
  and a passive content-fingerprint "may be stale" hint that never blocks the cached result or auto-refreshes it;
  inc 401 makes GRIM/GRIMMER paper-aware and lets a user save a reported mean/SD/N check to the specific paper,
  recalled whenever the Data section is open for it — the save endpoint always re-derives the verdict
  server-side from the raw inputs rather than trusting a client-supplied one; inc 402 surfaces WIP's own
  already-working statcheck integration (`app/backend/api/routers/wip_checks.py`, previously buried only in
  the WIP tab's own Checks sub-tab) in the Methods panel's Statistics section too, branching on
  `ctx.researchContext.kind === "manuscript"` (the same pattern the Details section already used) — a
  WIP manuscript has no `papers.id`, so `ctx.selectedPaper` stays null for it by design; the two concurrent
  surfaces stay in sync via the existing `wip.refresh` counter, now also exposed as `ctx.wipRefresh`; inc 403
  extends the same WIP integration to Discover > Funding — a run made against a manuscript (its already-existing
  paper-free "Describe research" mode, now pre-filled from the manuscript) tags
  `research_funding_profiles.source_kind="wip-manuscript"` (an already-generic column, no schema change) and
  surfaces in the manuscript's own Checks tab via a new scoped `GET /wip/manuscripts/{id}/funding-runs`; inc 404
  closes the third "quick win" — Discover > Journals (which, unlike Funding, has no persistence at all even for
  Library papers, by deliberate "ephemeral job result" design) gains a small new receipt table
  (`wip_journal_runs` — topic/weighting/counts only, never the full ranked profile list) written only when a run
  is manuscript-tagged, leaving the existing paper/abstract paths untouched. Live verification also caught and
  fixed a real latent bug shared by both Funding and Journals: their input-mode only initialized once and never
  self-corrected when a stale "paper" mode became unusable (e.g. a WIP manuscript became active after a Library
  paper had been selected earlier in the same session) — both now correct to the freeform mode automatically;
  **inc 441** brings the existing seven-rule Transparency disclosure detector to WIP as the first Checklists tool.
  Each explicit run reads only the registered primary manuscript, records the exact file/hash snapshot and all
  detector statuses, and persists positive quoted detections as non-reviewable FACTs; not-detected/not-applicable
  rows never become negative findings, a score, or a manuscript judgment. The same stored run appears in the WIP
  Checks tab and Methods → Checklists → Transparency. It remains local-only, deterministic, and migration-free;
  non-PDF extractors' synthetic page 1 is cleared rather than presented as real coordinate precision. **Inc 442**
  adds the mixed-model reporting auditor through the same exact-snapshot run/UI seam while preserving its distinct
  meaning: all seven statuses remain in the receipt, each `not-found` row becomes one reviewable `info` candidate,
  and present/not-applicable rows do not become findings. A gate-off run records that no checklist was applied and
  creates no finding; it never proves that the manuscript uses no mixed model. No model, provider, score, verdict,
  migration, or egress is involved. **Inc 443** brings the combined Bayesian auditor to the same WIP seam: the exact
  receipt preserves supported inline BF recomputations, fixed default-prior/tolerance assumptions, all three
  checklist rows, and bounded advisories. Default-prior mismatches, `not-found`/`coherence-flag` rows, and advisories
  become separate reviewable `info` candidates only when Bayesian language is detected; reproduced/present/n-a rows
  remain receipt-only and gate-off creates no findings. A mismatch commonly reflects a different prior or design,
  and every prompt remains local, non-scoring, non-verdict, migration-free, and exact-snapshot-bound. **Inc 444**
  completes the four-tool Checklists group by bringing the existing seven-item meta-analysis reporting audit to WIP.
  Its receipt retains every present/not-found/not-applicable row; one `info` candidate is created per `not-found`
  row only when the meta-analysis gate is on. Present/n-a rows remain receipt-only, gate-off creates no findings,
  and the copy repeatedly states that detector silence is not proof of omission. It never pools, models, recomputes,
  scores, or judges the analysis, and adds no provider, migration, egress, or paper-row shim.
  **Inc 445** adds an explicit local critical read for WIP in Synthesize → Critique. The registered primary file is
  prepared synchronously as an exact checkpoint; a separate background job composes only same-hash WIP method
  receipts, extracts at most 12 bounded claim sentences, transiently embeds them, and searches only matching-model
  article-fulltext embeddings from live Library papers. Local NLI surfaces high-confidence contrast as paired
  verbatim draft/Library evidence with paper, attachment, page, confidence, and model provenance. It never persists
  a draft embedding, borrows stale receipts, creates a defect finding, invents a `papers` row, auto-runs, scores, or
  calls a provider. Status labels it Local AI and receives only a typed manuscript id, never the result passages.
  **Inc 490** preserves that evidence contract while batching its local inference shape: single-paper, set, and WIP
  Critical Read encode every bounded claim collection once, retain per-claim retrieval and explicit positional
  claim/hit metadata, then classify every resolved claim/passage pair in one ordered NLI call. The same batch seam
  verifies grounded Tier-2 critique candidates. Thresholds, labels, top-k, source scopes, evidence order, persistence,
  and API/UI contracts are unchanged; WIP progress now honestly advances from preparation to batch completion rather
  than implying model-visible per-claim progress.
  **Inc 447 completes backlog #48** by bringing reference-integrity and citation-concentration to WIP under
  Work → Meta-Reference, reusing both Library-paper pure detectors (`inspect_reference`/`audit_reference_list`)
  completely unmodified against the manuscript's own "cited" `wip_references`-linked Library papers instead of a
  discovered reference list. Reference-integrity persists into two new, purely additive tables
  (`wip_reference_signals`/`wip_reference_reviews`) rather than retrofitting the Library-paper
  `reference_instances` (a NOT NULL FK to `papers.id`) or the generic file-shaped `wip_tool_runs`/`wip_findings`;
  citation-concentration stays fully ephemeral like its Library-paper version, with an honest no-field-
  comparison/self-citation-not-computed degraded path rather than a fabricated author or field proxy.
  Citation-context remains permanently out of scope for WIP (no DOI, no citation graph), stated plainly rather
  than silently omitted. **Inc 448** wires two more legitimacy sources into the PUBLISHERS "where to submit"
  journal-finder (`app/backend/methods/publishers.py`, Discover → Journals, backlog #40): a live per-ISSN
  **SciELO** regional-index lookup (`integrations/scielo/journals.py`, mirrors the DOAJ client pattern) and a
  locally-mirrored **TOP Factor** transparency rubric (`integrations/top_factor/adapter.py`, mirrors the
  Retraction Watch download→parse→replace pattern; new `top_factor_records` table). TOP Factor's `Total` renders
  only inside an expanded "show the basis" block beside its category sub-scores — never as a bare per-journal
  score (no opaque composite, commitment #7); the never-downloaded mirror state is an honest report-level note.
  **Inc 451** wires in a fourth source, **AJOL** (African Journals Online): a locally-mirrored, third-party
  CC-BY-4.0 Zenodo snapshot (`integrations/ajol/adapter.py`, Alonso-Álvarez 2025, mirrors TOP Factor's exact
  download→parse→replace shape; new `ajol_records` table) of AJOL's own public journal metadata, including its
  official positive-to-cautionary JPPS rating — shown plainly for every value (never filtered for `Ceased`/
  `Inactive Title`; only `1/2/3 Stars` ever elevates, gated by set membership, not an exclusion list). The real
  CSV encodes a missing ISSN as the literal string `"NA"`, not an empty cell — caught before ship, not after.
  Unlike TOP Factor's periodically-republished file, this is a one-time, immutable, Feb-2024-dated dataset with
  no update guarantee, so its Settings action reads "Download database," never "Refresh," with the fixed snapshot
  date kept visibly separate from the local download timestamp. **Inc 452** wires in a fifth source, **NLM
  MEDLINE indexing**: a live per-ISSN lookup (`integrations/nlm/journals.py`, mirroring SciELO's live-lookup
  shape, not a mirror) against NCBI's free, no-key E-utilities `esearch` endpoint — one combined
  `ISSN AND currentlyindexed[all]` query sidesteps a real multi-catalog-record ambiguity found live (an ISSN can
  resolve to more than one NLM record; picking the first blind can misread a live journal as "ceased"). Confirmed
  live that NCBI rate-limits unauthenticated bursts (~3 req/s); rather than an API-key env var, the client
  self-paces its own live calls, protecting every user with zero setup. A second live check caught a real
  overclaim before ship: MEDLINE and PubMed are independent NLM indexing statuses — a real, major journal (World
  Psychiatry) is PubMed-"Currently-indexed" with no MEDLINE entry at all — so the field/chip is named
  `indexed_in_medline`/"Indexed in MEDLINE," never "PubMed," matching exactly what the query checks.
  `LEGITIMACY_DEFERRED`'s old "PubMed / Scopus indexing" entry is dropped whole — Scopus stays permanently out of
  scope (proprietary, no free API) and is never named; broader PubMed-only coverage was never promised. **Inc 453**
  adds **thumb auditability**, the design doc's own "far reach" item: `fit_rank`/`weighted_rank` (1-based ranks
  over the full considered pool, sorted by fit alone vs. the actual blended order) surface per-card only when
  weighting is on and the ranks diverge — "Ranked #N here with weighting on · #M by topical fit alone," an
  ordinal derivation of already-shown values, never a new score. Its sibling design-doc item, user
  exclusion/filtering, stays **deliberately** unbuilt — the same doc flags it as ethically fraught ("the
  disfavored extreme — it reintroduces the 'these are bad' valence"), surfaced to and confirmed by the user before
  any code was written. COPE/OASPA membership was live re-checked too and reconfirmed not buildable (COPE:
  Cloudflare-bot-blocked; OASPA: a real WordPress REST API with no structured members endpoint). Backlog #40 stays
  open (self-archiving/green-route + Redalyc — a documented API doubly blocked by a live TLS hostname mismatch and
  a maintainer-only registration requirement — + Latindex, reconfirmed closed, + COPE/OASPA + user
  exclusion/filtering, remain unwired). **Inc 456/457 close backlog #25/#37's long-open self-citation field
  baseline** in Citation Concentration: inc 456 built the reusable `OpenAlexClient.fetch_self_citation_hit_count`
  primitive and empirically calibrated its sample size (a bootstrap-resampling pilot study across 6 real fields,
  mirroring stimulus-norming methodology — population self-citation rates varied ~3x by field and "computable"
  coverage varied 18%–74%, so N=40 was chosen as a disclosed judgment call rather than a guess); inc 457 wires it
  into the live signal via a router-local `_compute_self_citation_baseline` helper with a deliberate dual cap
  (target N=40, hard-capped at 100 raw checks so a low-coverage field's added cost stays bounded and disclosed,
  never silently padded). `audit_reference_list`/`_self_citation` gained backward-compatible keyword params, so
  the WIP call site's own honest no-field-comparison degraded path needed no changes. **Inc 467 adds DEBIT**
  (Heathers & Brown 2019, an unpublished OSF working paper — no DOI), the binary-data analog of GRIM/GRIMMER:
  for a variable that can only take values 0/1, the sample SD is fully determined by the mean and N
  (`sqrt(K(n-K)/(n(n-1)))` for the integer count K the mean implies), so a reported mean+SD+N triple can be
  checked the same deterministic way. Extends `app/backend/methods/grim.py` (reuses `grim_test` for the mean's
  own consistency) and the inc-401 paper-aware-save pattern exactly. Research before design found backlog #44's
  original "DEBIT/duplication analysis and perhaps a z-curve" phrasing had conflated three separate things;
  duplicate-publication detection (#54) and z-curve (#55) were spun off as their own gated backlog items rather
  than built here — duplicate-detection risks the no-accusation boundary (it compares a paper against *other*
  papers/authors, unlike DEBIT), and z-curve needs LLM-assisted "focal statistic" extraction. **Inc 469 closes
  #54**, but narrower than first framed: research found the original "duplicate-publication detection" idea
  conflated two different things. Salami-slicing (redundant publication across separate papers) has no
  algorithmic detection method — declined outright, same disposition as #24. `scrutiny`'s actual
  `duplicate_count`/`duplicate_tally` functions are something else: a within-one-paper repeated-exact-value
  counter, architecturally GRIM/GRIMMER/DEBIT-shaped but with no peer-reviewed method behind it. Shipped only
  the latter (`app/backend/methods/duplicate_values.py::count_repeated_values`, its own sibling router/tables
  since `methods.py` had no headroom left) with a deliberately weaker presentation than its three neighbors: no
  `consistent`/`flagged` field or pill anywhere, just a plain frequency list — a validated check earns its
  verdict pill; an unvalidated heuristic sitting right next to one must not visually borrow that credibility.
  Text-only credit line (no citable paper exists to add to the library). **Inc 470 closes #55** with z-curve,
  p-curve's more quantitative sibling: the source design doc's "auto-zcurve" proposed Gemini-assisted "focal
  statistic" extraction, its own words "more dangerous... judgment-laden" — the exact misaligned path
  PRINCIPLES.md Example 3 warns about. Research found the aligned path already built: p-curve (inc 126) already
  solves this identical problem by reusing statcheck's exhaustive deterministic extraction instead of an
  LLM-picked focal test. Z-curve extends that pattern — `app/backend/methods/zcurve.py` implements Bartoš &
  Schimmack (2022) Z-curve 2.0's full EDR/ERR mixture-model estimator, verified against the reference `zcurve` R
  package's own source (not derived from memory): 7 fixed-mean truncated folded-normal components, EM-fit
  weights, the published population-weight extrapolation and calibrated bootstrap-CI widening. No LLM, no
  egress. EDR/ERR are quantitative rate estimates — more verdict-shaped than p-curve's abstract right-skew
  statistic — so the design adds three safeguards beyond p-curve: a hard, non-dismissible reliability warning
  below the reference implementation's own N=300 threshold (expected on nearly every realistic personal-library
  run — the honest outcome, not a defect), CIs always shown beside the point estimate, and no per-paper/
  per-author breakdown anywhere. A real performance bug (an absolute log-likelihood convergence criterion that
  never converges for large N) was caught by a stress test before shipping, fixed with a scale-invariant
  parameter-change criterion.
- **Analytic-flexibility surfacing (backlog #37, inc 481) — LLM-assisted, deliberately NOT in the deterministic/
  local Methods list above.** The 5th Checklists-family tool (Library Methods → Checklists and the WIP Checks
  tab both surface it, the same dual-surface seam as statcheck/transparency/LMM/Bayes/meta-analysis), but the
  first one that calls a model at all: an egress-gated LLM (`integrations/gemini/analytic_flexibility_
  assistant.py`) proposes candidate analytic-decision points — exclusion criteria, covariate/control choices,
  statistical test/model selections, outcome/measure choices, and other reported branch points — from a paper's
  or manuscript's methods-section text (`paper_methods_text`/`wip_methods_text`,
  `app/backend/citations/section_scope.py` / `app/backend/wip/analytic_flexibility_text.py`, GROBID-preferred
  with a heuristic fallback on the Library side per inc 479's section-scoping infra). The model's own output is
  a **closed, five-value taxonomy** plus a verbatim quote, nothing else — no page, no confidence, no location;
  any category outside the fixed set is silently dropped, never coerced (`parse_proposals`). Every proposed
  quote is anchored **afterward, deterministically and locally** by a new `anchor_quote`
  (`app/backend/pdf_processing/quote_matching.py`) — the model never asserts a location, honoring invariant #2
  structurally. Candidates persist into the existing `paper_findings`/`wip_findings` stores as
  `kind="candidate"` (AI funnel, human filter, PRINCIPLES.md) via the Library orchestration endpoint
  (`POST /papers/{paper_id}/analytic-flexibility`, `app/backend/analytic_flexibility.py`) and the WIP
  orchestration endpoint (`POST /wip/manuscripts/{manuscript_id}/checks/analytic-flexibility`,
  `routers/wip_checks.py`) — both egress-gated exactly like every other LLM feature, the refusal firing before
  any paper/manuscript lookup (mirrors `grobid.py`'s ordering, so the 403 wins over even a 404). No aggregate,
  count, index, or "flexibility score" appears anywhere in either panel, by design — decomposed, passage-linked
  decision points only. `wip_findings.coordinate_precision`'s CHECK constraint permits only `NULL`/`exact`/
  `region`; a local `unanchored` anchor (no PDF, or the quote wasn't found in one) maps to `NULL` there, with
  the fuller `anchor_state` value preserved in `details_json` rather than silently dropped. The WIP side also
  carries a disclosed, honest scoping asymmetry: non-PDF WIP files have real per-block section headings to
  classify, but PDF WIP files' text blocks carry no per-block heading text at all (unlike the Library ingest
  pipeline's stateful `SectionTracker`) — rather than a fragile per-PDF heuristic, `wip_methods_text` degrades
  to "whole manuscript, capped" and reports `scoped=False` so the UI can disclose the degrade rather than
  present it as equivalent real scoping. This work also fixed a real, latent bug in the shared `FindingCard`
  (`app/frontend/js/08x_methods_critical.jsx`): its "show in paper" action had hardcoded `precision: "region"`
  regardless of a candidate's real anchor — harmless for every prior Checklists tool (none of them ever produced
  an `exact` anchor), but this feature's own `exact` anchors would otherwise have been silently understated.
- **Citations (formatted):** **citeproc-js** run as a Node sidecar (same subprocess pattern as esbuild) over
  bundled CSL styles/locales → formatted in-text citations + bibliographies from `papers.csl_json`
  (`app/backend/citations/`, inc 106). The **word-processor-integration spine** (adapters ride this engine):
  inc 106 renders a *selection* per-item; **inc 107 adds position-aware *document* render** (`render_document` /
  `POST /citations/render-document`, `rebuildProcessorState` — numeric renumbering + author-date disambiguation
  across an ordered document — the contract the LibreOffice/Word/Docs adapters call). Local, no egress.
  `citeproc` is an npm dep (`package.json`); see `THIRD-PARTY-NOTICES.md`. **inc 108** ships the **first adapter**:
  a LibreOffice (UNO) cite-while-you-write macro (`adapters/libreoffice/`) that places ReferenceMark live fields +
  rides `render-document`; **inc 362** adds native Writer footnotes for note-family styles and a validated
  one-based `noteIndex` to the shared render contract so citeproc can distinguish first/subsequent notes;
  **inc 363** adds a document-level footnote/endnote selector and native Writer endnote insertion; **inc 364**
  adds explicit, fail-closed inline/footnote/endnote conversion with verified one-step Undo/Redo and separate-copy
  isolation; **inc 365** adds the shared citation-style catalog/search/preview/preferences manager and makes blank
  Writer documents inherit its application default while existing documents retain embedded style/locale;
  **inc 366** validates and atomically installs local custom/dependent CSL styles outside the repository, making
  them first-class across the same browser, API, and Writer paths; **inc 367** adds portable personal-style export
  with stable cross-device ids and guarded removal that protects defaults and installed dependents; **inc 368**
  adds on-demand search/install from the public CSL/Zotero catalog plus explicit guarded HTTPS URL import,
  resolving and preflighting dependent-style parent chains before any write; **inc 369** validates imports against
  the official CSL 1.0.2 schema/macro rules, persists visible source/update provenance, adds explicit
  dependency-aware update checks, and creates independent personal copies before editing; **inc 370** adds the
  local source editor for independent personal styles with unsaved citeproc preview, stable canonical identity,
  exact-revision conflict protection, and local edit provenance; **inc 371** hardens the ordered note-index
  contract and proves imported-style ibid, locator-aware ibid, near-note, and far-subsequent behavior against
  native Writer footnote numbering, including gaps from ordinary user-authored notes; **inc 372** lets Add
  citation place another independent live cluster at a caret inside an existing configured footnote/endnote,
  preserving user prose through refresh and per-cluster deletion while unsafe placement conversion still
  refuses without mutation; **inc 373** completes P1 note-style item #10 with tracked-change-aware placement
  conversion that preserves unrelated Writer redlines and refuses managed-range conflicts before mutation;
  **inc 374** adds a bounded per-document Writer bibliography heading with explicit paused-mode refresh,
  save/reopen persistence, failure rollback, and blank reset to `References`; **inc 375** adds opt-in
  document-local links from unambiguous single-work citations to stable managed bibliography-entry bookmarks,
  preserving grouped citations and unrelated external links across refresh, placement conversion, and reopen;
  **inc 376** adds opt-in HTTP(S) links for DOI/URL text already rendered by the bibliography style, with bounded
  validated spans and persistence across refresh, bibliography moves, placement conversion, and reopen;
  **inc 377** adds bounded document-local bibliography categories through the existing Writer citations panel,
  preserving citeproc order within alphabetized groups and retaining unassigned entries under `Other references`;
  **inc 378** adds multi-select batch assignment/removal and a reusable existing-category picker, with one
  transactional bibliography refresh and whole-map rollback; **inc 379** adds bounded document-local custom
  category precedence with Move up/down, alphabetical reset, reopen persistence, and failure rollback;
  **inc 380** adds multiple bounded heading-scoped bibliography blocks alongside the full bibliography, with
  exact section membership, shared refresh, reopen persistence, diagnostics/removal, and fail-closed conversion;
  **inc 381** adds one-step placement conversion across the full and every non-empty section bibliography with
  exact Undo/Redo, rollback, and converted-copy isolation; **inc 382** extends the opt-in bibliography web-link
  setting with a fail-plain title fallback when the active style omits visible DOI/URL text, using only one
  source's safe DOI/URL and one uniquely matched rendered title without changing bibliography text; **inc 383**
  adds a bounded grouped-source chooser for opening a specific cited work or jumping to its stable full-
  bibliography entry, without making grouped rendered text structurally ambiguous; **inc 384** completes
  bibliography editing with a document-ordered section-bibliography manager, deterministic jump,
  selected/confirmed bulk removal, and verified Writer Undo/Redo recovery that leaves citations and the full
  bibliography unchanged; **inc 385** closes the active LibreOffice adapter for now with document-local
  library/MEDLINE/full journal-title modes, a bundled local NLM abbreviation index, honest unknown coverage,
  immutable embedded metadata, and real-Writer rollback/save/reopen proof. **Inc 459** reopens it for the
  roadmap's P2 leapfrog track (backlog #33/#34) with a **"Citation integrity preflight…"** command: a new,
  scoped, synchronous `POST /methods/retraction/check-selected` re-checks retraction status right now for
  exactly the papers cited in the open manuscript (reusing `detect_retraction`/`apply_retraction` unchanged, so
  the fresh check also persists), folded together with `diagnose_document`'s existing local mechanics report
  (malformed/duplicate/orphaned marks, bibliography health) into one combined dialog. Document-scoped and
  reuse-first by design — no new detector, no job/poll infra (the adapter has none today), and the rest of the
  roadmap's #19 checklist (DOI resolution, metadata completeness, preprint-vs-VoR, etc.) is a deliberate v1
  scope boundary, not built. **Inc 460** continues the P2 track with the **evidence-aware Suggest-Citation
  composer** (roadmap #17): "Suggest citations" is now multi-select (several sources for one sentence become
  one grouped citation via the existing `insert_citation_items`), and a new **Details…** dialog surfaces the
  full quote, the complete 3-way support/contrast/mention stance breakdown, a "why retrieved" narration, a
  weak-evidence warning (reusing invariant #1's own 0.7/0.55 `VerificationConfig` thresholds, not new numbers),
  an editable page locator (auto-pre-filled from the matched passage, never silently inserted), and an
  **Open in PDF** button (extends the `?open_paper=` deep link with `page`/`precision`, `40_app.jsx` — the only
  backend-adjacent file touched; zero actual backend Python changed, since `/citations/suggest`'s response
  already carried everything needed). Each inserted citation also gets a compact **evidence-audit locator**
  (`evidence_chunk_id`/page/a hard-truncated ~150-char snippet, new optional keys on `_ITEM_DEFAULTS`, no
  `SCHEMA_VERSION` bump needed) surfaced later in the "Citations in this document" panel's new **View
  evidence…** button — recording provenance with nowhere to see it again would be inert. Filters
  (study-type/year/tag/collection — study-type isn't a modeled concept anywhere in callosum) stay a deliberate
  v1 scope boundary, filed as its own follow-up. **Inc 461** continues the P2 track with **Citavi-style "Insert
  evidence"** (roadmap #20): a new sibling module `adapters/libreoffice/evidence_insert.py` adds a three-dialog
  flow — search any library paper (not just already-cited ones), pick one of its saved PDF highlights
  (`GET /papers/{id}/annotations`, an existing endpoint the adapter had never called before), and configure +
  insert. The configure step includes a basic claim-vs-evidence stance check via a new sibling endpoint
  `POST /citations/classify-stance` (`app/backend/api/routers/citation_stance.py` — `citations.py` was already
  at the 600-line cap), the first pairwise `(sentence, passage)` stance endpoint in the codebase (every other
  call site bundles classification with retrieval). Four insertion formats — quote only (plain text, **no**
  citation, by design), quote + citation, paraphrase (the saved note) + citation, structured card — via
  `insert_evidence`, the adapter's first two-step insertion (free body text via the `insert_statement`
  precedent, then a citation mark via the unchanged `insert_citation_items`, reusing the same cursor so the
  mark lands right after its body). A new `evidence_annotation_id` key on `_ITEM_DEFAULTS` (the annotation
  analog of inc 460's `evidence_chunk_id`) rides the same additive mark-payload mechanism; no `SCHEMA_VERSION`
  bump needed. **Inc 462** completes the P2 track's authoring-aid pair with **open-science statement
  insertion** (roadmap #21): a new Work → Statements tab extends CRediT's own build→stage→LibreOffice-insert
  pattern (`/credit/pending`, inc 261) to 7 more author-asserted disclosures — data availability, code
  availability, preregistration, funding, conflict of interest, ethics, and AI use — each with click-to-fill
  canned starting phrases (the CRediT role-bundle pattern: a one-click starting point, never silently applied).
  A new generalized backend store (`app/backend/api/routers/statements.py`, `POST`/`GET /statements/pending`,
  a dict keyed by kind rather than CRediT's single slot, since several statements may be staged at once) backs
  one new LibreOffice "Insert statement…" command that reuses the existing `_choice_box` dropdown picker
  unchanged — no new dialog construction, unlike inc 461's multi-step flow. None of the 7 has any structured
  source of truth in callosum (confirmed against `wip_manuscripts` and the funding-search tables); every one is,
  like CRediT itself, something only the author can assert — callosum never infers or verifies funding/ethics/
  AI-use/availability facts about the user's own study. CRediT's own tab/endpoint/command are untouched.
  **Inc 463** closes the P2 leapfrog track's #18 ("manuscript-level citation coverage analysis") with a
  reuse-first slice: a new synchronous `POST /methods/citation-equity/check-selected` reuses
  `audit_reference_list` unchanged, scoped to exactly the papers cited in the open Writer document (self-
  citation honestly left "not computed" — no fabricated author identity, the `wip_citation_equity.py`
  precedent), surfaced via a new "Citation coverage audit…" command. Paired with a new, purely local structural
  scan (`_uncited_paragraph_stretches`, no network/NLI) flagging runs of 3+ consecutive substantive paragraphs
  with no citation — a footnote/endnote citation counts via the note's own main-text anchor
  (`XTextContent.getAnchor()`), so a note-style-cited paragraph is never misread as uncited. "Claims supported
  only by retracted/corrected papers" needed no new work (inc 459's preflight already covers it); the rest of
  the roadmap's 9-item #18 checklist needs real claim-level semantic parsing nothing in callosum does today — a
  deliberate v1 boundary. A real `compareRegionStarts`/`compareRegionEnds` polarity bug in the new paragraph
  scan was caught before shipping by cross-checking `order_by_comparator`'s own already-documented convention
  (`>0` iff the first range precedes the second), not assumed — a duck-typed unit test alone had "passed" with
  the same wrong polarity baked into both the fake and the code under test; only the real-UNO spike (which
  needed a genuine two-document redesign after its first draft hit `citation_placement_error`'s real, deliberate
  refusal to mix inline and note-style citations in one document) proved it fixed. **Inc 464 closes the P2
  leapfrog track's #22 ("cross-manager conversion") and the whole track with it**, scoped to **Zotero only**
  (the competitive-review doc shows only Zotero has documented first-party LibreOffice integration; Mendeley
  Cite is Word-only, EndNote's is undocumented). The citation format was **verified against Zotero's own
  open-source `zotero-libreoffice-integration`** (`Document.java`/`ReferenceMark.java`), per an explicit
  research-first direction rather than reverse-engineering a sample file: a Writer ReferenceMark whose *name*
  is `ZOTERO_ITEM CSL_CITATION {json} RND<random>`, self-contained CSL-JSON, matching the literal
  `"ZOTERO_ITEM CSL_CITATION {}"` this codebase's own foreign-mark test already assumed. A new "Convert Zotero
  citations…" command scans read-only first, confirms with the user, then resolves every distinct cited work
  via a new local-only `POST /citations/zotero/resolve` (`find_existing_paper_by_identity` reused unchanged;
  an unmatched work auto-adds a metadata-only paper straight from its embedded CSL-JSON — the exact
  `imported_source="zotero"`/`processing_tier="metadata-only"` trust posture the existing Zotero *library*
  importer already uses), replaces each mark via the unchanged `insert_citation_items`, and swaps Zotero's own
  bibliography TextSection for a callosum-managed one via the unchanged `refresh()`. Zotero's Bookmark-mode
  fallback storage (an unverified internal format) and note-style Zotero citations are detected and counted but
  not converted — disclosed in both the confirm dialog and the summary, never silently dropped.
  **Inc 474** closes backlog #33/#34's long-open keyboard/screen-reader accessibility item: all 13 UNO
  dialog-construction sites (`composer.py`, `callosum_cite.py`, `citations_panel.py`, `evidence_insert.py`) now
  give LibreOffice's own accessibility bridge a real field name, a real Tab order, and initial focus on open,
  plus Enter-to-add/remove in the composer (Zotero's own shortcut) — via a new shared `a11y.py` module. Found
  and fixed a real bug before ship: an assumed `LabelControl` property doesn't exist on plain AWT dialog
  controls (only on the separate *forms* API); the real, empirically-verified mechanism is a `TabIndex`-adjacent,
  `Tabstop=False` `FixedText` label, which VCL's accessibility bridge auto-detects. Proven headless via a new
  `spike_dialog_accessibility_wiring` (real `AccessibleName` + a real `XKeyListener`); real focus-landing and
  screen-reader announcement need the manual script (real `--headless` soffice grants no window real OS focus
  at all, confirmed empirically, so that half can't be headlessly proven).
- **Cross-editor adapters — Microsoft Word and Google Docs (`adapters/word/`, `adapters/googledocs/`, incs
  164-166 and 169-171).** Both ride the same citation engine as the LibreOffice adapter (`render_document`,
  the CSL style catalog) but reach it over a fundamentally different transport, since neither host runs a
  local UNO-style macro: a Word add-in is a **web page** Office loads over **HTTPS only** (it cannot reach
  `http://localhost`), and a Google Docs add-on runs entirely in **Google's cloud**, with no access to the
  user's machine at all. **Word** (`adapters/word/`, Office.js, desktop Windows/Mac): callosum serves the
  add-in's task pane over **HTTPS on the same origin as its own API** (`tools/run_https.py`, a trusted local
  dev cert via `office-addin-dev-certs`), so the add-in's calls stay same-origin, local-only, no egress.
  **Google Docs** (`adapters/googledocs/`, Apps Script): since a cloud add-on categorically cannot reach
  `localhost`, a small opt-in bridge exposes **only the five cite endpoints** through a **`cloudflared`
  tunnel** (outbound-only, no inbound port) at a bearer-token-gated, cite-only ingress — reusing the existing
  Remote-access token gate (inc 168) unmodified, with a `cloudflared`-level path allowlist as defense in
  depth (verified via `ingress validate`). A zero-setup **Quick Tunnel** mode (inc 193,
  `tools/run_tunnel.py --quick`) skips the Cloudflare-account/domain migration for a throwaway session URL,
  at the cost of losing the ingress allowlist (the bearer token becomes the sole boundary). Both adapters
  ship the same three-stage arc: **SP1** search-and-insert; **SP2** live Content-Control citations
  (Zotero's embedded-CSL-JSON-in-field-name pattern, reused as a pattern not code) + Refresh/renumber +
  bibliography rebuild; **SP3** Suggest-from-the-sentence (the same stance+quote relevance engine as
  LibreOffice's Suggest-Citation) + one-click document-wide style switch + Flatten-to-static-text. Both are
  the first Checklists-adjacent surfaces with **no headless host to test against** — only the pure
  request/response logic (`taskpane_core.js` / `gdocs_core.js`) is unit-tested (`node --test`); the in-host
  behavior ships best-effort-correct per each platform's own docs and is explicitly flagged untested until
  run for real. **Inc 482 (SP4) closes the desktop-only gap**: the Word add-in's task pane now also runs in
  **Word on the web**, riding the SAME cloudflared relay Google Docs already uses (`cloudflared-config.yml`
  extended with one more ingress rule forwarding the 5 task-pane GET files, never the manifest routes — those
  are downloaded locally, Office never fetches them over the tunnel) rather than a new transport. A second
  manifest variant (`manifest.web.xml`, its own distinct GUID) points at the tunnel hostname instead of
  `localhost:8443`; the task-pane JS (`isLocalOrigin`/`authHeaders`, both unit-tested) detects which origin
  it loaded from and only attaches the Remote-access Bearer token when tunneled — desktop is provably
  unchanged either way. **A real bug was found and fixed in the same increment, caught by a negative-path
  test written before the fix, not discovered live**: `AccessControlMiddleware`'s exemption list didn't
  cover the task-pane's own static files, and Office's fetch of those (a plain resource load, not a
  header-carrying `fetch()`) can never carry a token — meaning Word-on-the-web could never have loaded the
  task pane at all until the 5 fixed files joined the exemption list (same "carries no library data"
  rationale the pre-existing `/` shell exemption already used); every real API endpoint stays fully gated,
  confirmed by an explicit same-test assertion. **Genuinely still open** (mirroring the LibreOffice
  adapter's own P0→P1 arc): grouped citations/locators (both already store an `items` array per citation
  cluster but only ever populate one — the same "anticipated but not wired up" gap the LibreOffice roadmap
  doc found there first), section-scoped bibliographies, and true document-order citation scanning on the
  Google Docs side (Refresh currently renumbers in insertion order — Word's own Refresh already scans in
  true document order, unrelated to SP4, confirmed against `taskpane.js`'s pre-existing SP2 comments).
  Security audits: `2026-06-27_word-addin.md`, `2026-06-28_googledocs-tunnel.md`,
  `2026-06-28_googledocs-addon.md`, `2026-08-18_word-online-relay.md` (all PASS; the tunnel audit is the
  binding one for `2026-06-27_remote-access-auth.md`'s token-gate reuse, and inc 482's own audit for
  `access_control.py`'s exemption-list fix). **Not yet live-verified in real Word or Word-on-the-web** — the
  maintainer doesn't have desktop Word installed as of inc 482; see `INCREMENT-482-NOTES.md`'s manual
  verification script.
- **My Publications grounded prospection:** **inc 386** starts Layer 4 with an explicit-refresh, LLM-free
  co-citation gap scan. It follows reference anchors shared by at least two confirmed own publications to
  bounded OpenAlex candidates, excludes directly cited/already-held works, stores atomic local snapshots,
  and carries every candidate's exact shared references plus clickable source publications. Ordinary dashboard
  reads make no request; visible graph counts order candidates without an opaque score, and coverage/caps are
  stated. **Inc 389** adds server-validated, multi-domain union scopes with independent bounded snapshots and
  scope-named coverage while keeping all-publications as the default. **Inc 390** adds grounded emerging citing
  topics: equal three-year OpenAlex windows, visible recent/earlier counts and differences, exact citing-work plus
  own-publication evidence, the same all/domain-union snapshot posture, and explicit caps/omissions. It is a
  descriptive signal, never a forecast or importance score. **Inc 391** completes deterministic Layer 4 with
  grounded authors citing your work: stable author ids must appear across at least two retrieved citing works and
  two own publications; self and checked coauthors are excluded; every visible count opens to exact work/publication
  evidence; and bounded coauthor coverage is stated. It is a private inspection lead, never inferred collaboration
  fit or a recommendation of a person. Optional grounded-data narration remains deferred. **Inc 410** fixes a real
  external bug report: an author whose OpenAlex profile was never linked to their ORCID iD (OpenAlex and ORCID
  are separate systems; the gap is common, not user error) got an honest but avoidable "no match." ORCID-keyed
  resolution (`resolve_author`/`cached_author` in `integrations/openalex/author.py`) now falls back to a name
  search when the ORCID lookup alone 404s, and the frontend finally renders the pre-existing `matched_by` field
  so a name-fallback match is visibly labeled lower-confidence rather than presented with an ORCID match's
  authority. A Help-doc note explains linking OpenAlex to ORCID at the source.
- **Literature gap-finder (backlog #29, incs 135/137/454/455):** backward gap (works your library cites but
  doesn't hold) and forward gap (works that cite your library but aren't in it) — axis-scoped, cached,
  cited-by-N-of-your-papers evidence, never a quality rank. **Inc 454** adds a third source, **followed
  authors**: follow an OpenAlex author (by name/ORCID, or directly from an already-resolved id via a
  My-Publications citing-authors quick-action — zero extra egress) and Refresh fetches their works (cached,
  capped at 50/author, `app/backend/clustering/followed_authors.py`), surfacing those absent from the library as
  "by \<author\> (followed)." A **sibling module**, not a third `gap_candidates.direction` — `GapCandidate` has
  no room for author provenance, so it gets its own two tables (`followed_authors`/`followed_author_candidates`)
  and its own Discover sub-tab (`30f_followed_authors.jsx`), while reusing gap-finder's own shared dismissal list
  (`dismiss_gap`/`dismissed_gaps` — a dismissal is about the work, not which generator re-derived it). **Not**
  ranked by axis relevance in v1 — disclosed plainly in the persistent UI note, not silently omitted, since that
  machinery was never actually built even for backward/forward gap (there, `axis_id` is only an input scope
  filter, never an output rank). **Inc 455** additionally wires followed authors into the literature **Feed**
  (Discover → Feed, `app/backend/discovery/followed_author_feed_source.py`) via a new `FeedSource` (`kind=
  "followed_author"`) registered on the existing `FeedRegistry` — a followed author's new works flow into the
  same chronological, read/starred stream as bioRxiv/PubMed/journal items, badged "Followed"
  (`.feed-followed-badge`, an indigo/`--accent` pill per DESIGN.md's provenance pair). Deliberately does **not**
  dedupe against the library at write time (unlike the Followed-Authors tab's own gap list) — Feed's own
  established convention is to show everything and compute `in_library` at read time, so the two views stay
  purpose-built (a full stream vs. a library-gap triage list) rather than redundant. `followed_authors` and
  `feed_subscriptions` are kept in sync bidirectionally on follow/unfollow from either UI surface, plus a
  startup self-heal backfills a matching subscription for any author followed before inc 455 shipped. The
  registry-source `kind` is deliberately excluded from the generic "Add source" picker (`user_addable=false`) —
  a raw OpenAlex author id is not something a user should type; the Followed-Authors tab's resolve flow stays
  the only sanctioned way to follow an author. **Inc 458 closes backlog #28's known date-precision gap**: `AuthorWork`
  now carries OpenAlex's real `publication_date` (validated `YYYY-MM-DD`, added to the existing works `select=`
  param), and Feed's `posted_date` prefers it over the bare-year fallback — additive/backward-compatible, so a
  pre-458 cached work (or one OpenAlex itself never dated precisely) keeps the old bare-year behavior.
- **Beyond-library saved queue (backlog #30's last open piece, inc 465):** a "Save for later" button on every
  beyond-library suggestion card (`app/backend/citations/beyond_library.py`'s live, per-sentence search — both
  the web Cite pane and the LibreOffice adapter's Suggest dialog) persists the suggestion verbatim into a new
  `saved_beyond_library_suggestions` table, keyed by the suggestion's own stable `dedup_key`. Faithfully mirrors
  how "Gaps" is itself actually built — a modal (`36c_beyond_library_saved.jsx`'s `BeyondLibrarySavedModal`)
  opened from a Discover → Search button, not a workspace tab — but simpler than gap-finder: a beyond-library
  suggestion is inherently per-sentence, so there's no recompute/Refresh concept, only "remember this one
  candidate I explicitly flagged." Add reuses `save_item` (the same write path `/discovery/save`/`/gaps/add`
  already use); Dismiss is a soft status flip, never a hard delete. Explicit-save-only by design — never
  automatic accumulation of every suggestion merely shown.
- **Section-scoped Suggest-Citation + the GROBID integration (backlog #30's actual last open piece, inc 479):**
  closes Highlight-to-suggest/evaluate for good. A new `app/backend/citations/section_scope.py` gives
  Suggest-Citation a section-aware ranking pass: `expected_section_family` classifies the draft's current
  heading (LibreOffice already knew it, inc 380) into the same canonical family taxonomy
  `pdf_processing/sections.py` already tags every chunk with at ingest time, and `partition_by_phase` reorders
  (never filters) candidates so same-family matches lead — a disclosed `search_phase`, not a hidden re-rank.
  `candidate_section_family` is a strict either/or lookup with its source always disclosed
  (`"grobid"`/`"heuristic"`/`"none"`), which is what makes it safe to *extend* rather than redesign once real
  section data exists. That real data comes from **GROBID** (`integrations/grobid/`), a separately-run,
  opt-in, self-hosted Docker service (never bundled) a user points callosum at from Settings — a loopback URL
  needs no consent; a non-loopback one is egress-gated exactly like a custom AI provider endpoint (invariant
  #3, `_egress_refused`/`requires_egress`, verified to win over even a 404 for a nonexistent paper). The TEI-XML
  client sends `teiCoordinates=div,head,p` as multipart fields (a real bug — it was first tried as a query
  param — fixed before ship); the parser (`integrations/grobid/tei_parse.py`) hand-closes a genuine XXE/entity-
  expansion gap `xml.etree.ElementTree` leaves open by default (external entities are already blocked; internal
  "billion laughs" expansion isn't) — a strict-UTF-8-decode-then-reject-DOCTYPE-or-NUL guard that closes both
  the obvious raw-byte-substring bypass and a deeper no-BOM UTF-16 variant found while fixing the first, with
  no new `defusedxml` dependency. `app/backend/grobid_pipeline.py` maps GROBID's own section bounding boxes
  onto callosum's **existing** PyMuPDF chunk bboxes by real coordinate overlap — never fuzzy text matching
  between the two independent parses — and writes only the new `paper_sections` table +
  `chunks.grobid_section_id` (migration 0074, which needed `op.batch_alter_table` for a SQLite-safe
  `ForeignKey` add, a real Alembic/SQLite constraint confirmed against Alembic's own dialect source); the
  pre-existing heuristic `chunks.section` column is **never** written by this pipeline, so deleting the whole
  GROBID subsystem would leave the heuristic-only baseline exactly as it was. `candidate_section_family` then
  prefers a mapped GROBID section over the heuristic when one exists — strictly either/or, never blended — which
  needed **zero** changes at any Suggest-Citation call site, proving the original interface design held.
  Settings gets a GROBID URL field + test-connection ping (deliberately **not** egress-gated itself — a bare
  liveness check carries no library content, so invariant #3 doesn't apply to it) plus a per-paper "Parse
  document structure…" action and a bulk "Parse structure for library" job, both Status-tracked (invariant #5)
  through one shared `grobid_parse_jobs` `JobStore` labeled "Local processing + self-hosted GROBID" — a
  deliberately distinct compute-kind, since this is neither pure local computation nor a hosted provider call.
  Live-verified end-to-end (not just faked-client unit tests) against a real GROBID 0.8.1 container and a real
  open-access PLOS ONE article: 28 real sections extracted with correct verbatim titles, 48 of 229 real chunks
  correctly coordinate-mapped to the right section by content (spot-checked), and `candidate_section_family`
  confirmed honestly reporting `"grobid"` provenance only where a real overlap was found and `"none"`/
  `"heuristic"` everywhere else — closing a gap the pipeline's own implementation task had explicitly disclosed
  as unverified. See `.claude/security-audits/2026-08-15_grobid-integration.md` and
  `.claude/docs/increment-notes/INCREMENT-479-NOTES.md`.
- **Response-size caps on external HTTP reads (backlog #56, inc 480):** a shared `integrations/http_bounds.py`
  (`bounded_get`/`bounded_post`, streamed + a hard byte cap, fails closed with `ResponseTooLargeError` before
  the rest of a response body is read) wired into every previously-unbounded external fetch. The real gap was
  narrower than the backlog item's own description: the three "mirror download" adapters it named by name
  (AJOL/Retraction Watch/TOP Factor) already had correct per-adapter caps, confirmed by reading each rather than
  trusting the summary — left untouched (rule #7, no drive-by refactor of already-correct code). The genuine gap
  was 16 sites across 15 files: 15 metadata `httpx.get()` lookups (arXiv/bioRxiv/CORE/Crossref/DOAJ ×2/Europe
  PMC/NLM/OpenAlex ×3/OSF/SciELO/Semantic Scholar ×2) plus GROBID's one `httpx.post()` call — the latter needed
  a bespoke catch since it wraps every `httpx.HTTPError` into its own `GrobidError` type.
- **Local usage instrumentation (backlog #38A, inc 450):** a zero-egress local event log + a personal
  Settings → **Your usage** dashboard — the buildable-now half of the "Research-impact analytics" future track
  (`.claude/docs/future-tracks/opus4.8_future-tracks_researchimpactanalytics.md`; the cross-user Project B stays
  far-future/gated, untouched). `app/backend/usage.py::record_event()` is the single seam five instrumented
  operations route through (citation export, duplicate resolution, metadata re-resolve, locating a quote,
  reviewing a flagged reference) — counts and timestamps only, structurally no payload column in
  `usage_events` (`persistence/schema_usage.py`), so a call-site bug can't leak content into it. On by default
  (nothing here ever egresses, unlike every other Settings toggle); the local log is always inspectable,
  exportable, and deletable regardless of the toggle's state. No opaque "flourishing score" — five separately
  labeled counts, never blended (Principles #7).
- **Admin-gated plugins foundation (backlog #41, inc 483):** a `plugins_enabled` Settings toggle
  (default OFF, mirroring `agent_writes_enabled`'s pattern exactly, incl. a `CALLOSUM_DISABLE_PLUGINS`
  recovery hatch) plus marker comments at the two real existing internal registries
  (`registerPaneTab`, `build_default_feed_registry`) naming them as candidate future extension
  points for user-authored plugin modules. **Deliberately inert** — the toggle controls nothing
  else in the app; no plugin data model, loader, sandbox, or store exists yet. See the design doc
  for the vision and its open blocking questions: `.claude/docs/specs/2026-08-19-admin-gated-plugins-design.md`.
- **Native Zotero library import shipped (backlog #57 Phase 1, inc 484):** the already-built,
  full-fidelity Zotero importer (`app/backend/importers/zotero.py` — copy-then-read `zotero.sqlite`,
  never the live file, `integrations/zotero/adapter.py`) previously had no entry point beyond the
  dev validation harness and tests. A new sibling router (`app/backend/api/routers/
  library_zotero.py` — `library.py` was already at the 600-line cap) adds `POST
  /library/zotero/import` (async job, the `library_import_jobs` pattern) plus a Library "+ Add"
  entry and a third onboarding-wizard option. Unlike the generic BibTeX/RIS/CSL-JSON path
  (metadata-only), this reads collections/tags/notes/annotations and extracts + chunks any
  locally-resolvable PDF. The importer itself gained two small additive fields
  (`ZoteroImportResult.created_paper_ids`/`chunk_ids_by_paper`) so its caller can embed +
  retraction-check newly-created papers — and, a real subtlety, embed newly-created chunks on a
  *matched* (pre-existing) paper too, since a re-run can discover a PDF that wasn't locally
  resolvable before. The importer/adapter code itself is zero egress (confirmed by direct grep of both
  touched files); the only non-loopback traffic the job can produce is the same already-audited
  retraction-check metadata lookup every other import path already makes. Same
  local-single-user file-read posture as the already-audited `/library/scan`. **Zotero annotation
  position fidelity shipped in inc 485 (backlog #57 Phase 4):** attachment-owned PDF highlight/
  underline rectangles are bounded and transformed from standard PDF bottom-left coordinates into
  the viewer's `pdf-points-top-left` basis through the owning PDF's PyMuPDF page transform. The PDF
  response identifies the attachment and the viewer requests attachment-scoped annotations, so an
  exact imported overlay cannot cross onto a sibling PDF. Unsupported/malformed/out-of-page input,
  missing PDFs, and rotated pages retain raw Zotero provenance but receive no guessed bbox. **Inc 489
  hardening:** once an imported row is exact, re-import cannot move it to a relinked/replacement PDF merely
  because the old rectangle still fits; exact attachment identity stays pinned, while raw-only rows can still
  gain their first proven location. All three native annotation-creation flows carry the active attachment id:
  both `30_viewer.jsx` create flows, including "highlight + note," plus the Synthesize-pane "Save highlight"
  action (`saveCitationHighlight`, `40_app.jsx`) — a separate creation path a later whole-branch review found
  still missing it, fixed to carry the citation's own `attachment_id` (backlog #57 fixwave). Audits
  `2026-08-20_zotero-library-import.md` and
  `2026-08-21_zotero-annotation-position-fidelity.md` PASS.
- **EndNote whole-library handoff partially verified (backlog #57 Phase 2, inc 486):** current EndNote 2025
  documentation recommends **RefMan (RIS) Export** for transfer to another program; Callosum's existing local,
  metadata-only `POST /library/import` route already accepts `.ris` and EndNote's possible `.txt` extension.
  The RIS parser now covers Clarivate's documented `CPAPER`, `A4`, alternate title/journal/year aliases, and Help
  gives the two-step EndNote export/import path; inc 489 also names **EndNote RIS** on the visible onboarding and
  + Add actions rather than requiring format knowledge or a hover tooltip. No current primary source verified a
  suspected parenthesized-
  BibTeX EndNote convention, so the parser does not guess at it. The backlog phase remains explicitly partial
  until the same path is exercised against a genuine EndNote-created file; the checked-in alias fixture is only
  a contract stand-in. Research: `.claude/docs/research/2026-08-21_endnote_generic_import.md`.
- **Mendeley-via-Zotero feasibility confirmed (backlog #57 Phase 3, inc 487):** Zotero currently documents a
  desktop **File → Import → Mendeley Reference Manager (online import)** path that brings a personal Mendeley
  library's data, files, and folder structure into an ordinary Zotero library; Callosum then uses its unchanged
  copy-then-read Zotero importer. Onboarding, the Zotero modal, + Add, and Help surface that handoff; inc 489
  names the Mendeley bridge on both visible entry-point labels rather than only in explanatory copy/tooltips. The
  upstream step requires Mendeley data/files online and authenticates inside Zotero (Callosum never receives the
  credentials); group libraries, invalid/custom fields, and Mendeley Cite document citations retain documented
  limits. Direct Mendeley database read/decryption remains a hard avoidance boundary. Research:
  `.claude/docs/research/2026-08-21_mendeley_via_zotero_bridge.md`.
- **Foreign Word citation conversion researched and gated (backlog #57 Phase 5, inc 488):** current first-party
  documentation confirms Mendeley Cite uses Word content controls and EndNote Cite While You Write uses Word fields
  (`ADDIN EN.CITE`) with a Traveling Library, but neither vendor publishes the complete, versioned payload contract
  needed for lossless conversion. No parser may be built from third-party reverse engineering alone: reopen only
  with a vendor schema/supported API or an explicitly approved multi-version fixture corpus, fail-closed version
  handling, and byte-preserving fallback. Existing foreign fields remain owned by their source tool; vendor
  flattening produces static text, not editable migration. Research:
  `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`.
- **PDF:** PyMuPDF (`fitz`) for text + bbox extraction.
- **LLM (selective, multi-provider — inc 149; unified editable roster — inc 256):** all generators route through
  one `app/backend/llm/providers.py::complete(config, prompt)` seam. The provider set is **one editable list**
  (`app/backend/providers_store.py`): four pre-seeded builtins — **Gemini** (`google-genai`, default
  `gemini-2.5-flash-lite`) / **OpenAI** / **Anthropic** / a **local** OpenAI-compatible endpoint (Ollama etc.) —
  **plus user-added custom providers** `{name, base_url, api_key, wire_format ∈ messages|chat_completions|responses,
  models[]}` (any OpenAI/Anthropic-compatible endpoint: DeepSeek, Together, Groq, OpenRouter, vLLM). The builtins
  are **synthesized on read** (never persisted); only `custom_providers` + id-keyed secrets are stored (additive,
  no migration; the active selection reuses the flat inc-149 `provider`/`model` fields). `complete()` dispatches on
  `config.wire_format` (gemini-SDK / `{base}/v1/messages` / `{base}/v1/chat/completions` / `{base}/v1/responses`),
  all non-gemini via **httpx** (no new dep). LLM is **generation only** (summary, axis-terms, research summary,
  overview, help, and — inc 259 — **assisted extraction**) and **OFF by default** (egress gate, invariant #3). The
  **assisted-extraction funnel** (inc 259: `routers/workbench.py` propose/accept/reject
  + `integrations/gemini/extraction_assistant.py` + `app/backend/workbench_assist.py`) has the LLM *propose* meta-analysis
  cell values as **candidates** (the isolated `ma_proposals` table + `ma_cells.origin`, migration 0034) that a human
  verifies/accepts before any enters the trusted `ma_cells`/converter/exports — **AI funnel, human filter**; each
  candidate's anchor is decided **deterministically-locally** (`locate_quote` → exact/region/unanchored, invariant #2),
  never by the model, and egress rides the same `EgressGatedExtractionAssistant`. **Egress is endpoint-based** (inc 256):
  `requires_egress(config)` gates any **non-loopback** base URL exactly like Gemini, while a **loopback** provider
  (local or a custom `127.0.0.1` endpoint) runs with **zero egress** — so an arbitrary user URL honors #3 for free.
  Verification NLI runs locally (`cross-encoder/nli-MiniLM2-L6-H768`). **Inc 411** hardens the shared
  `complete()` seam itself: when the active provider needs egress and has no resolved API key, it now refuses
  before any network call with a friendly local message (mirroring `/settings/test-key`'s existing pre-check)
  instead of letting a raw provider auth error (e.g. Anthropic's bare "x-api-key header is required" JSON)
  reach the user — fixed at the one shared seam, so every LLM feature benefits without a per-router change.
  **Inc 413** extends this to real (not just missing) provider rejections that only surface once the network
  call actually happens: `_post()` now classifies 401/403 ("check the saved API key"), 429 ("rate limited"),
  and 5xx ("temporarily unavailable") with a friendly lead-in, always keeping the raw `HTTP {code}: {body}`
  detail appended rather than hidden (invariant #4); an unclassified status keeps the original plain format.
  **Inc 492** gives each FastAPI app one `ProviderClientRuntime`: compatible raw HTTP calls share a lazy persistent
  HTTPX pool and compatible Gemini calls share a lazy SDK client. Endpoint and credential identities are
  non-reversible fingerprints; config rotation cannot reuse stale Gemini credentials, explicit injected clients
  still win, and lifespan shutdown closes app-owned clients. Per-identity construction is race-guarded and
  retryable, while ordinary provider calls are not serialized or otherwise made concurrent by this change.
  **Inc 493** hardens synthesis-generation cache identity separately from transport reuse: a cache hit now requires
  the same provider roster id, model, resolved wire mode, canonical endpoint, fixed request semantics, credential
  fingerprint, prompt/generator version, and exact ordered prompt inputs. Old under-specified rows miss once without
  migration, raw secrets/endpoints never enter stored signatures, and local citation verification still reruns.
  **Inc 494** commits the complete verified synthesis trust spine before optional Overview generation. The primary
  job is marked done from a committed reread; persisted Overview lifecycle/CAS state makes supplementary generation
  retryable, first-success-wins, and crash-visible. No database connection is held during the Overview provider call,
  and any provider/parser/write failure leaves the primary synthesis intact and usable.
  **Inc 498** adds an explicitly developer-only managed-local Overview POC. Tauri alone owns a developer-supplied
  llama-server process, strict loopback port, private per-launch bearer token, authenticated readiness, crash
  invalidation, and process-tree shutdown; Python validates the immutable `DEVELOPER_TEST_ONLY` descriptor and uses
  the existing `complete()`/Overview parser/lifecycle without cloud fallback. No runtime, model, downloader, router,
  hardware policy, LAN target, Settings control, or product qualification ships with it.
  **Inc 499** makes that developer POC's execution identity truthful: hashing streams through a bounded heap buffer;
  zero/partial/full GPU-layer requests are always explicit; startup observation separately records actual backend and
  layer count and fails readiness on mismatch; and a canonical allowlisted launcher-plus-library manifest identifies
  backend packages whose launchers are byte-identical. No unqualified target is published from requested intent alone.
- **Frontend:** modular source under `app/frontend/` (`index.html` shell + `styles.css` +
  ordered `js/*.jsx` React chunks, React/ReactDOM + pdf.js via CDN), assembled by
  `app/backend/api/frontend.py`: the JSX chunks are concatenated and **precompiled to plain JS by
  esbuild at build time** (inc 102 — `package.json` pins esbuild; `npm install` once), then injected
  into one `<script>`. (Through inc 101 the JSX was transpiled in-browser by `babel-standalone`;
  precompiling dropped that ~500KB CDN download + runtime transform + its dev-console warnings.)
  `tools/build_frontend.py` rebuilds the single-file `callosum-app.html`; FastAPI serves it at `/`
  by default, falling back to live assembly if it's absent. No bundler (just a transpile pass), no
  extra file-serving surface (esbuild emits one IIFE, so the chunks' shared scope is preserved); the
  **server stays Python-only** — it serves the prebuilt file, never running Node at serve time.
  **Run `npm install` once, then re-run `python tools/build_frontend.py` after editing anything under
  `app/frontend/`.**
- **HTTP client:** httpx (external metadata/discovery APIs).
- **External-client surfaces (backlog "B1"; incs 213/216, inc 472):** two ways to drive callosum besides the
  web UI, both pure HTTP clients over the existing API — no new backend endpoints, no new trust boundary beyond
  what already exists. **MCP server** (`mcp_server/`, incs 213/216): a stdio Model Context Protocol server for
  agent hosts (Claude Desktop, Cursor). SP1 (inc 213) exposes five **read-only** tools
  (`search_library`/`get_paper`/`full_text_search`/`find_passages`/`format_citation`); SP2 (inc 216) adds four
  **gated, audited, reversible** write tools (`add_tag`/`add_to_axis`/`save_reference`/`annotate`) behind the
  default-off `agent_writes_enabled` Settings toggle, each write provenance-stamped `imported_source="ai-agent"`
  and logged to `agent_writes` (`app/backend/api/routers/agent.py`, `persistence/agent_repo.py`) with a
  per-write Revert. No destructive `/agent/*` route exists — structurally inexpressible, not just
  documentation. Security audits: `2026-06-30_mcp-server.md` / `2026-06-30_mcp-agent-writes.md`. **TUI terminal
  client** (`tui/`, inc 472): a numbered-menu REPL (`python -m tui`) plus a one-shot CLI
  (`python -m tui <group> <action> --format json`) covering the *entire* API surface as of its own snapshot
  (~140 actions across 13 groups), both generated from one declarative registry
  (`tui/registry.py`) so the two surfaces can't drift. `--agent` mode restricts it to reads plus the same four
  gated `/agent/*` writes above (never wider — enforced by `registry.validate()` + tests, mirroring the MCP
  server's own structural guarantee); destructive actions are human-only and always confirmed. **Callosum's
  first external code contribution** — written by Jeffrey Vadala, submitted as GitHub PR #1, reviewed against
  `PRINCIPLES.md` + the security-audit gate before merge (`2026-08-10_tui-external-contribution-review.md`:
  PASS — a pure client with no judgment/scoring logic of its own, zero direct external calls, the agent surface
  provably bounded to `/agent/*`) and merged as inc 472. The registry is a point-in-time snapshot of the app's
  feature set (~inc 258) and will drift as new endpoints ship — extending it is additive, low-risk, and not yet
  scheduled.
- **Concurrency (inc 418):** the backend runs single-process/single-worker uvicorn with no concurrency anywhere
  by default — CPU-bound and I/O-bound batch jobs alike looped strictly sequentially until inc 418 introduced
  two deliberate, narrow exceptions: the citation-verification loop batches its NLI/embedding model calls (one
  call for a whole summary instead of one per sentence-citation pair — same model, same math, just batched;
  `summarization/verification.py`'s `verify_many`/`support_and_contradiction_many`, also used by
  `embeddings/pipeline.py`'s `embed_chunks`/`embed_papers`), and the two sequential external-HTTP batch jobs
  (`citation_counts.py`, `library_enrich.py`) fetch concurrently via a small bounded `ThreadPoolExecutor` (stdlib,
  no new dependency) instead of one paper at a time — safe because `persistence/sqlite_retry.py`'s `run_write`
  already opens a fresh connection per call with retry-on-lock, and SQLAlchemy's default `QueuePool` (no special
  `poolclass` set) is built for exactly this. CPU-bound batch jobs (statcheck-all, PDF scan/import, axis
  scoring's pre-embed loop) remain deliberately sequential — see `INCREMENT-418-NOTES.md` for why each was left
  alone. GPU is not used anywhere; nothing constructs a model with an explicit `device=`, so sentence-transformers'
  own cuda→mps→cpu auto-detection already applies for free to anyone running the dev server on a GPU-equipped
  machine — only the packaged desktop installer forces CPU-only torch (bundle-size, not a code constraint).
- **Local model lifetime (inc 491):** `api/app.py` owns one `ModelRuntimeRegistry` per FastAPI app instance and
  `api/dependencies.py` is the centralized resolver. Compatible feature wrappers share lazy SentenceTransformer
  and CrossEncoder runtimes by model name/revision/device/local-files-only/backend identity; support and stance
  scorers retain their separate probability/threshold semantics above the shared NLI weights. Per-identity load
  locks prevent duplicate first construction and leave failures retryable. Separate per-identity inference locks
  conservatively serialize access to a shared runtime without locking DB/retrieval/provider work or unrelated
  identities. Explicit injected models/scorers always win, and lifespan shutdown releases app-owned references.
- **Desktop packaging (backlog #21, incs 394-395):** `app/desktop-shell/` — a Tauri v2 shell that
  spawns callosum's own FastAPI/uvicorn backend as a child process (a bundled portable CPython + this
  project's real dependencies via `bundle.resources`, CPU-only torch, not PyInstaller/Nuitka freezing)
  and shows the real UI in a native window once `GET /health` returns 200. **All three platforms now
  have a CI workflow that builds AND actually verifies the real installer** (`.github/workflows/
  desktop-shell-{windows,macos,linux}.yml`) — Windows/macOS runners keep a real interactive desktop
  session, so these mount/install the real artifact, launch it for real, and screenshot the actual
  running window (not just process/log inspection); Linux (arm64→x86_64 `.deb` only — its AppImage
  bundler fought the embedded ML stack across four separate failures, not worth chasing further, see
  inc 395 notes) runs under Xvfb since `ubuntu-latest` has no display server by default. **A real,
  structural macOS bug was found and fixed this way**: Tauri's default ad-hoc signing happened before
  `bundle.resources` was copied in, so Gatekeeper reported the app as "damaged" (no override at all)
  instead of the milder unidentified-developer flow — fixed by re-signing the whole bundle
  (`codesign --force --deep`) after resources are placed, then wrapping the `.dmg` by hand. No code
  signing/notarization (real Apple/Microsoft certs) on any platform yet — see `app/desktop-shell/
  FIRST-LAUNCH-NOTE.md` for the SmartScreen/Gatekeeper mitigation. **Inc 396** replaced the default
  Tauri placeholder icon with callosum's own brain/neuron mark (`src-tauri/icons/*` regenerated via
  `npx tauri icon` from a squared, transparent `logo_dm.png`) across window/taskbar/installer, and
  fixed two post-install UX bugs surfaced by real desktop use: Library/WIP cards not refreshing after
  an edit (a Detail/WIP mutation now bumps the same `libRefresh`/WIP-card refresh counter the queue
  already did) and a new import landing off the visible page (ingest paths now reset to page 1, since
  the default sort is oldest-first). See `INCREMENT-394-NOTES.md` / `INCREMENT-395-NOTES.md` /
  `INCREMENT-396-NOTES.md`. **Inc 422** regenerated the same icon set again from a new source
  (`.claude/media/logo_app.png`) after the inc-396 mark turned out to be a near-white line stroke on
  transparency, invisible against light backgrounds — the new source fills the mark solid black with
  a white outline, visible against light and dark backgrounds alike. **Inc 409** adds the in-app auto-updater (backlog #49): Windows/macOS check
  periodically, silently download in the background, and prompt (never force) a restart once ready —
  driven entirely from Rust (`src-tauri/src/updater.rs`, `tauri-plugin-updater`) since the frontend's
  transform-only esbuild pipeline can't resolve npm imports; the frontend side (`04d_update.jsx`) is
  just one event listener + one `invoke()` via the already-enabled `window.__TAURI__` global. Linux
  (`.deb`-only) gets an "Open release page" fallback instead, since Tauri's updater plugin needs
  AppImage. CI now signs builds and publishes a `latest.json` manifest; the signing keypair is the
  maintainer's own (never generated by an assistant). Code-complete; live only once the maintainer sets
  the GitHub signing secrets and runs a rehearsal release — see `INCREMENT-409-NOTES.md`. **Inc 417**
  (prompted by watching v0.3.2's release + auto-update go live) fixes the connection tooltip showing an
  unrelated internal `verification_version` constant instead of the real app version (`/health` gains
  `app_version`, sourced from a new `CALLOSUM_APP_VERSION` env var `backend.rs` sets when spawning the
  backend); surfaces the silent download's progress in the Status popover as a frontend-only synthetic
  entry (the updater lives entirely in the Tauri process, never a backend `JobStore`) via a shared
  `useDesktopUpdate()` hook also read by the toast; and adds a Settings → Account & sync → Desktop app
  (relocated there from its own card in inc 420) → "Check for updates" on-demand button
  (`check_for_updates_now`, reusing the same check functions the periodic loop already calls, with a
  `downloading` guard against a concurrent double-download). **Inc 421 fixes a real, since-day-one bug
  this button's first-ever click surfaced**: Tauri v2 requires an explicit ACL permission grant per
  custom `#[tauri::command]` (`src-tauri/capabilities/*.json` + `src-tauri/permissions/*.toml`) — this
  app never had a `permissions/` directory at all, so `retry_backend`/`install_update_now`/
  `open_release_page`/`check_for_updates_now` were **all** silently unreachable from the frontend since
  inc 409 (v0.3.0), just never caught until this button became the first of the four a real user
  actually clicked. **Any future custom Tauri command needs its own `allow-<name>` permission added to
  both files, or it will fail identically** — verify a new command's ACL by checking that
  `src-tauri/gen/schemas/acl-manifests.json`'s `__app-acl__` entry resolves it after `cargo check`, the
  same empirical check that found and confirmed this fix. **Inc 423 found the fix was incomplete**: Tauri
  v2 capabilities gate on a *second, independent* axis besides the permission grant — origin scoping
  (`local`/`remote`). The app's `main` window loads its own bundled backend via
  `WebviewUrl::External(http://127.0.0.1:{port})` (`src-tauri/src/lib.rs`), which Tauri's ACL does **not**
  treat as "local" even though it's loopback — so every `invoke()` from `main` (the entire user-facing
  update flow) was still rejected until `capabilities/default.json` also gained
  `"remote": {"urls": ["http://127.0.0.1:*/*"]}`. **Any future window that loads external/non-bundled
  content (including another loopback server) needs its own matching `remote.urls` entry, or its commands
  will fail identically even with a correct permission grant** — verify by confirming
  `gen/schemas/capabilities.json`'s capability gained a `"remote"` key after `cargo check`, same empirical
  method, now covering both axes.

> **README:** brought current in **inc 178** (the contributor front door — accurate feature list + the
> `npm install`/`build_frontend` step + privacy/security notes). Shipped as a **draft pending the maintainer's
> voice pass + a screenshot** (a `<!-- TODO(maintainer) -->` placeholder marks the screenshot). Still defer to this
> file + the code for the authoritative current state; keep the README current opportunistically.

---

## Core design invariants (NON-NEGOTIABLE)

These are the soul of the project. A change that violates one is wrong even if it passes
tests. The analogue of a brand promise: never break it.

1. **External LLM output is never authoritative citation evidence.** Gemini proposes summary
   sentences and *candidate* citations; the app then **independently verifies** each sentence
   against the source via local embedding similarity + NLI stance classification + verbatim
   quote extraction (`app/backend/summarization/verification.py`,
   `VerificationConfig`: retrieval ≥ 0.7, quote = 1.0, support ≥ 0.55). A sentence is shown
   as verified, contrasted, or **flagged** — never silently trusted.

2. **The coordinate honesty contract.** A citation's `coordinate_precision` is one of
   `exact` / `region` / `null`. **Exact** draws precise bbox rectangles; **region** scrolls to
   the page and shows an approximate-location note; **null** opens the page (if known) and
   draws nothing. Region-level or absent coordinates are **never** presented as exact passage
   highlights. The stored coordinate system is `pdf-points-top-left` (`COORDINATE_SYSTEM` in
   `app/backend/pdf_processing/extraction.py`); overlays are positioned as percentages of the
   page so they stay aligned across zoom. Rotated pages: open the page, draw no exact rect.

3. **Local-first, egress-off by default.** All heavy lifting — extraction, embeddings, vector
   search, clustering, verification — runs **locally**, and the app stays useful **offline**
   after import. The *only* thing that can leave the machine is Gemini summary generation, and
   it is **disabled unless the user explicitly opts in** via `CALLOSUM_ALLOW_DATA_EGRESS`
   (`1`/`true`/`yes`); otherwise `DataEgressDisabledError` is raised
   (`integrations/gemini/generator.py`). Never add a code path that sends library text to a
   remote service without routing through that consent gate.

4. **Evidence always shown; verification is probabilistic, not proof.** Confidence scores,
   quotes, and page numbers are always visible. The score reflects semantic + lexical overlap,
   not logical entailment — the user sees the quote and decides. Never hide a low-confidence or
   flagged claim.

5. **Visible work is globally findable.** Any operation that uses AI—whether a consent-gated external provider, a
   loopback model, or Callosum's installed local embedding/NLI/OCR/clustering tools—must show a progress indicator and
   a live entry in the global **Status** popover. The same is true of every other lengthy operation represented by a
   progress bar. A Status entry must identify local/provider computation, expose honest completion and ETA only when
   measurable, and click back to the exact relevant workspace, pane/tab, modal, and entity. Use `JobStore` plus
   `JOB_NAV_DEFAULTS` for background work, `TRACKED_AI_REQUESTS` for synchronous AI HTTP calls, and the shared
   `ProgressBar`/`StatusScope` path for other visible work; set `managedBy` when one operation already has an owner so
   duplicate rows are impossible. Never invent percentages or ETAs, and never put prompts, passages, results, paths,
   secrets, or arbitrary URLs in a status navigation payload. The deliberate exception is routine library/WIP folder
   scanning: it remains visible inline at its source but is excluded from the global popover because its high frequency
   overwhelms more actionable work. Add any future exclusion only to `STATUS_HIDDEN_STORES`, with an explicit noise
   rationale and regression test; do not silently bypass Status at a call site.

6. **Model-backed latency is an architectural constraint, not an optional polish pass.** Any backend work that uses
   local models, remote models, reusable provider clients, model-backed jobs, or latency-sensitive inference must
   follow [`.claude/LATENCY.md`](LATENCY.md). Preserve the live batching, runtime/client reuse, positional
   reconstruction, and completion-notification invariants documented there unless an intentional, measured change
   justifies replacing one. Functional correctness alone does not excuse an avoidable user-visible latency regression.

---

## Principles alignment gate (read `.claude/PRINCIPLES.md`)

The Core design invariants above are the load-bearing few; **`.claude/PRINCIPLES.md` is the full charter** —
ten commitments (every claim carries its evidence; signal not verdict; facts ≠ candidates; the deterministic
substrate is the source of truth and the model only narrates it; the human is the filter / the AI is the
funnel; silence is not a certificate; no opaque composite scores; inspectability over authority; defaults are
the user's; local-first & provider-swappable), the strict **THEORY contract**, and four worked
**aligned-vs-misaligned** examples. The misaligned path is almost always the smaller, faster, demo-friendlier
one — so it has to be declined on purpose.

**The gate is a *reflective pause*, not an absolute block.** Before you **add or remove** functionality that
produces a claim / signal / judgment about the literature, or that changes the inspectability, provenance,
fact-vs-candidate, or egress posture:

1. **Name the principle(s) it touches** and the worked example in PRINCIPLES.md it most resembles — read that
   example's real implementation (it points at one) before building the analogous thing.
2. **Name the misalignment it is most at risk of** — usually the easier implementation.
3. **If the change is at odds with a principle, don't just flag it — propose the aligned alternative.** The
   deliverable is *what could be right*: a design that honors the feature's intent while cohering to the
   principles. Surfacing the conflict is the cheap half; the valuable half is the version that keeps the
   commitment. (*Easy to see what's wrong; harder and more valuable to see what could be right.*)

If a feature genuinely cannot be built to honor the principles, that is a **finding about the feature, not a
reason to relax them** — report it as such. This applies to **removals** too: deleting an evidence surface, a
confidence display, a provenance field, or a fact/candidate distinction is itself a principle-level change.

**Values layer — `.claude/APPROACH-AVOIDANCE.md` (the deeper, *conditional* layer).** Beneath the charter sits
the **value substrate** — the commitments that *generate* the principles (8 approach values + standalone
avoidance boundaries + a four-way drift typology). It is reached for **only when the principle pass above
doesn't resolve or doesn't trigger** — i.e. for a **novel / value-level / future-track** change — **never** as
a second mandatory read on an ordinary gated edit (PRINCIPLES + the Core invariants stay the first, primary
pass; this layer adds depth without taxing the cases the principles already cover). Consult it when:
- **No principle or worked example fits** (a genuinely novel case) → **derive the check from the relevant value.**
- The change touches **value-level** posture the principle triggers can miss: **access / licensing /
  distribution (equity), the acquisition boundary, anything that could introduce accusation, or a
  cost-vs-verification/consent trade-off** — or it **adopts an emergent value** (a commitment not yet in the
  built artifact).
- It is **future-track / planned** work → run A-A's **drift typology** (confirmed / extended / emergent /
  divergent); **flag emergent values** ("adopt deliberately, don't drift into it") and **divergent tensions**.
- **Veto-level:** A-A's **standalone hard boundaries** (no paywall circumvention; no reaching into other
  tools' protected stores; no accusation of individuals) are **veto-level**, alongside the Core invariants —
  they have no "aligned alternative"; they are lines the tool does not cross.

Same philosophy throughout: a **reflective pause, not a block**, and *propose the aligned alternative, don't
just object*. A feature that cannot honor the values is a **finding about the feature** too.

**Governance layer — `.claude/GOVERNANCE-COMMITMENTS.md` (founder/organizational, not product design).** Cliff's
own signed, dated public precommitment on how the project is governed while it remains founder-led — founder
accountability practices, the triggers for expanding governance beyond one person, and the composition/limits
of a future external advisory body. It restates several PRINCIPLES/A-A themes (illumination not substitution,
signal not verdict, provenance) but at the level of *how the founder holds himself accountable*, not *how a
feature is designed*. **Narrower trigger than the two gates above — not a third mandatory read on ordinary
gated edits.** Consult it when a change touches: founder/governance-authority structure itself; workplace power
or surveillance dynamics (a PI/admin-facing feature, anything that could enable monitoring workers rather than
coordinating work); external advisory-body composition or authority; or a decision under commercial/adoption
pressure to weaken a stated commitment (§"Conflicts between mission and growth"). For an ordinary claim/signal/
judgment feature, PRINCIPLES.md (+ A-A when novel) remains the whole gate — don't inflate this into a third
ceremony step.

---

## Rule priority & exceptions

When instructions conflict, apply this order:

1. **Security + data safety** (incl. the egress gate) — never bypass.
2. **Verification requirements** — follow unless the tooling is genuinely unavailable; if so,
   say so explicitly and flag it as a follow-up.
3. **Workflow defaults** (planning, backups, hygiene) — adaptable for trivial edits.

If a hard requirement can't be met, report: what failed, the impact, and the follow-up action.

---

## Commands

Run from the project root. The shell is **PowerShell** (Windows).

| Command | Description |
|---|---|
| `uv sync` | Install the pinned dev/CI toolchain from `uv.lock` into `.venv` (backlog #20; `pyproject.toml` + `[dependency-groups] dev` is the source of truth — `requirements.txt`/`requirements-dev.txt` are a kept-in-sync pip fallback) |
| `pre-commit install` | Wire the fast pre-commit gate (`.pre-commit-config.yaml`: ruff format/check, whitespace/EOF/large-file hygiene, the line-budget script, `tach check`) — install once per clone |
| `python -m tach check` | Module-boundary check (`tach.toml`, activated inc 473 — see staged-harnesses/tach.md): `app.backend.persistence` can't import `app.backend.api`; `sync_server`/`mcp_server`/`tui` can't import `app.backend` at all. Run `tach sync` (then review the diff) after a legitimate new cross-module import |
| `$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"` | Point the app at a SQLite DB (default if unset: `sqlite:///.local/validation/validation.sqlite`) |
| `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080` | Start the FastAPI app; then open `http://127.0.0.1:8080/` |
| `npm install` | Install the build-time frontend toolchain (pinned `esbuild`) — required once before `tools/build_frontend.py` / live assembly (inc 102) |
| `python tools/build_frontend.py` | Rebuild `callosum-app.html` from `app/frontend/` (esbuild-precompiles the JSX) — run after any `app/frontend/` edit |
| `pytest tests/test_<area>.py -q` | **Default dev loop — run only the changed area's tests** (seconds, not ~45 min). See the Verification protocol §1. |
| `pytest --testmon -q` | Run only tests whose covered code changed since the last run (pytest-testmon, inc 300; first run builds `.testmondata`) |
| `pytest -n auto -q` | Full suite in **parallel** (pytest-xdist, inc 300) — ~3-4× faster; use before merge (CI runs this) |
| `pytest` | Full test suite, **serial** (`testpaths=tests`, `pythonpath=.`) — slow; prefer `-n auto` for full runs |
| `pytest tests/test_api.py -k summary` | Run a focused subset (by name) |
| `alembic upgrade head` | Apply DB migrations |
| `alembic revision -m "<desc>"` | Create a new migration (no down-migrations by design) |
| `python tools/validation_harness.py` | Run the PDF→extract→embed→retrieve→summarize validation harness (writes a `validation.sqlite` + report + debug images under `.local/`) |
| `python tools/enrich_metadata.py` | Batch metadata enrichment (OpenAlex/Crossref) |
| `python tools/backfill_keyword_tags.py` | Backfill Crossref `subject` categories as `keyword:crossref` tags across the library (cache-first; tag-only; idempotent — inc 73) |
| `$env:GOOGLE_API_KEY = "..."; $env:CALLOSUM_ALLOW_DATA_EGRESS = "1"` | Enable Gemini summary generation (off by default) |

`CALLOSUM_FRONTEND_PATH` overrides the served frontend with a single prebuilt HTML file; unset (the
default) assembles the modular source under `app/frontend/` at serve time.

---

## Directory layout

IF NEEDED, see "directory-layout.md."

---

## The rules

### 1. 600-line hard limit on application source

Any file under `app/` or `integrations/` must stay **under 600 lines**. Files approaching it
are split proactively; a file that crosses it MUST be modularized before the next feature
lands in it. Split by concern — routers, repositories, pipeline stages, adapters — and keep
shared/core code loading first.

**Exempt-but-watched:** `tests/` and `tools/` (the validation harness is allowed to be large),
and non-code (Markdown, SQL, config).

**Standing split tasks:** none — the tree is **fully under the 600-line cap.** (The long-flagged
`app/frontend/js/15_axes.jsx` violation — 614 since inc 211/212 — was cleared in **inc 222**: the axis-card subsystem
[`AxisItem` + its presentational helpers `axisConfidenceLabel`/`AxisTierBadge`/`AxisPaperRow`/`AxisCutoffFlipper`/
`_tierRank`] moved verbatim → new `js/15b_axis_card.jsx` [224]; `15_axes.jsx` 614→**395** [`AxesPanel` + `MyPubsPrompt`
+ `registerPaneTab`]. Hoists across the shared IIFE — the inc-208 `10b_libmenus.jsx` precedent. Behavior-preserving,
proven by baseline-then-after on `drive_inc212_dragreorder.py` + `drive_inc204_hide_uncertain.py`.) **Inc 221** split the App god-component
`app/frontend/js/40_app.jsx` (599→**212**): the library-list subsystem (filters/fetch/bulk/saved-searches/chips/findings)
→ `js/03_library.jsx`'s **`useLibrary`** hook (351; the focus↔library cycle broken with two refs). **Inc 167** split `app/frontend/js/40_app.jsx` (630→551:
the axis focus-mode → `js/39_focus.jsx`'s `useFocusMode` hook; the citation-download helpers → `js/00_lib.jsx`) —
**frontend chunks count too** (they're under `app/`). **Inc 176** extracted the Notes panel from `js/30_viewer.jsx`
(595→573) into `js/30b_notes.jsx` (`AnnotationsPanel`); the reading-pane run (175–179) re-grew it to 599/600, then **inc 182 extracted `LibraryFrame` → `js/30c_frame.jsx`**
(30_viewer 599→**557**). **Inc 207** split `js/25_detail.jsx` (609→**522**): `TagsRow` → new `js/25b_tags.jsx`. **Inc 208** split
`js/10_pdf_layer.jsx` (602→**547**, over the cap when the SavedSearchMenu landed): both library-header dropdowns
(`AddMenu` + `SavedSearchMenu`) → new `js/10b_libmenus.jsx` (62) — called via the shared-IIFE function hoist.
**Inc 209** kept the full-text mode self-contained (`js/10c_fulltext.jsx`'s `FulltextResults` does its own fetch) so
`js/40_app.jsx` stayed at 599 + `js/10_pdf_layer.jsx` rose only to **555** (the scope option + the swap branch).
**Inc 210** (A2 citation counts): `CitationCountsButton` → `js/10b_libmenus.jsx` (**93**); `js/10_pdf_layer.jsx`
**562** (chip + Most-cited option + control); `js/40_app.jsx` held at **599/600** (the new prop folded onto an
existing line — split before the next addition there). **Inc 211** (A7 SP1 curated axis): `js/15_axes.jsx` grew to
**551** (the `isCurated` branch + freeze/convert/reorder) — comfortably under; `js/40_app.jsx` untouched.
**Watch (re-measure):** `js/30_viewer.jsx` (**580**, +23 from the inc-215 minimap; was 557, NOT the stale-noted
599/600 — inc-182's LibraryFrame extraction had relieved it), `js/10_pdf_layer.jsx` (**581**) — the closest frontend
chunks now that inc-221 took `js/40_app.jsx` to **212** and inc-222 took `js/15_axes.jsx` to **395**. **Inc 214** split `routers/papers.py` (604→**510**, over the cap when the #5 `extra_urls`
field landed): the request-normalisation cluster (`edits_from_request` + `_clean_*`/`_validate_csl_patch` + the caps
constants) → new `routers/paper_edit_input.py` (111; duck-typed on the request → no import cycle). **Inc 137** split
`schema.py` (611→558, over the cap
since inc 130/132): the findings/signals/retraction/gap tables moved to `persistence/schema_findings.py` on a
shared `persistence/schema_base.py` `metadata`, re-exported from `schema.py` (zero blast radius). **Inc 91** split
`repository.py` (625→538, → `persistence/annotations_repo.py`) and `routers/papers.py` (600→539, → `routers/paper_files.py`).
**Inc 220** split `repository.py` (662→**565**, a pre-existing violation the watch note had drifted on at "~556"; the
read/priority feature landed in it): the paper-lifecycle cluster (trash/purge/tier + the new read/priority setters)
→ `persistence/paper_lifecycle_repo.py` (121) and the synthesis CRUD → `persistence/summaries_repo.py` (61), both
**re-exported** from `repository` (`# noqa: E402,F401`; zero call-site change — the inc-137 pattern).
**Inc 226** split `routers/papers.py` (598→**528**, was at the 600 cap when the per-identifier `source` field landed):
the enrichment-action endpoints (`reresolve_paper` + `fill_metadata` + `FillMetadataResponse` + `_crossref`) → new
`routers/paper_enrich.py` (113; imports `PaperDetailResponse`/`_detail_for` from papers.py, no cycle).
**Inc 256** split `js/35_settings.jsx` (604→**471**, over the cap when the unified-provider-roster UI landed): the
whole AI-features block (`AiSettings` + `ProviderRow` + `AddProviderForm`/`ProviderFields`/`ProviderModelsEditor`)
→ new `js/35b_providers.jsx` (**362**) via the shared-IIFE function hoist (the inc-208/222 precedent — `AiSettings()`
is called unchanged from `SettingsModal`).
**Inc 262** cleared two pre-existing violations (backlog #47; both had drifted over-cap through inc 261 while the
watch-list stayed stale): `routers/methods.py` (619→**450**) peeled the retraction endpoint cluster (per-DOI
detection + the Retraction Watch DB mirror) → new `routers/methods_retraction.py` (186; shares `request.app.state`,
mounted beside `methods.router` in `app.py` — the inc-226 `paper_enrich.py` sibling-router pattern; also removed
the dead `import logging`/`_log`), and `persistence/schema.py` (628→**558**) extracted the summary/citation-mapping/
evidence-quote table group → new `persistence/schema_summaries.py` (107) on the shared `schema_base` `metadata`
(the inc-137 pattern; the `enum_check`/`non_empty_check` helpers + `CITATION_MAPPING_STATUSES` moved to
`schema_base` too so both files share one definition without a circular import; re-exported from `schema.py`).
**Inc 264** cleared two more drifted files — caught by the new line-budget gate, not a human: `routers/axes.py`
(609→**513**) peeled its 14 request/response models + their field-cap constants → new leaf `routers/axes_models.py`
(125; imports only pydantic/stdlib, re-imported into axes.py — the inc-137 leaf pattern), and `js/10_pdf_layer.jsx`
(604→**507**) moved the paper-card cluster (`ClipboardIcon`/`CheckIcon`/`PaperCopyButton`/`PaperCard`) → new
`js/10d_papercard.jsx` (100; the inc-208/222 shared-IIFE hoist).
**The 600-cap is now machine-enforced (backlog #20 ratchet step 1) — the hand-maintained watch list is retired.**
`tools/check_line_budget.py` fails on any over-cap `app/`/`integrations/` `.py`/`.jsx`, wired into the **pre-commit
framework** (`.pre-commit-config.yaml`; install once per clone: `pre-commit install` — backlog #20 ratchet step 2
replaced the earlier hand-rolled `tools/git-hooks/pre-commit` + `core.hooksPath` mechanism with this standard tool)
**and CI**. Run **`python tools/check_line_budget.py --list`** for the live closest-to-cap files instead of trusting
prose — the old watch list kept drifting stale (it missed axes.py at 609 and 10_pdf_layer.jsx at 604), which is
exactly why the check is now automated.
(The editable Detail pane lives in its own chunk `app/frontend/js/25_detail.jsx`; the edit-mapping logic is
`app/backend/metadata/paper_edits.py`.)

**Watch (exempt but large):** `tools/validation_harness.py` (~898 — inc 37 extracted the report
dataclasses + markdown renderer to `tools/validation/`; the probes remain, a candidate for a future
per-probe split). Tests are now per-resource (`tests/test_papers.py`, etc.) sharing
`tests/conftest.py` + `tests/api_helpers.py`.

### 2. Secrets in the environment, never in code

`GOOGLE_API_KEY` (Gemini) and `CALLOSUM_DB_URL` come from the environment. Never commit a key
or hardcode one in a `.py` file. Non-secret constants (model names, thresholds, table names)
are fine as literals. When a `.env` is introduced, it must be gitignored. **BYOK (inc 146):** a user can also
set the Gemini key + egress consent from Settings; they persist either in the **OS keychain** (inc 152, optional `keyring`) or in a local file at
`~/.callosum/app-settings.json` (`app/backend/app_settings.py`; override `CALLOSUM_SETTINGS_PATH`) — outside the repo
+ the synced Dropbox folder; multi-provider (Gemini/OpenAI/Anthropic/local) since inc 149.
The key is **write-only over the wire** (`GET /settings` returns a set/not-set status, never the value), never
logged, and `GeminiConfig.from_environment()` overlays it over the env fallback. Egress stays default-off.

### 3. Parameterized SQL only

Use SQLAlchemy Core bound parameters. Never interpolate user/external input into SQL text.
Table and column names come from constants or allowlists, never from request data. This
discipline is what keeps a single flaw from becoming a compromise if callosum ever goes public.

### 4. Validate untrusted input at the boundary

PDFs and external-API responses are **untrusted**:
- **PDFs:** validate/decode on ingest (`app/backend/pdf_processing/ingest.py`), cap sizes,
  never build a filesystem path from an unsanitized user-supplied name.
- **External APIs** (OpenAlex, Crossref, Gemini, sci-hub/Unpaywall): validate response shape,
  set httpx timeouts, fail closed. The local-app threat model is **resource exhaustion** and
  **untrusted-content handling**, not SQLi — but rule #3 still holds.

### 5. Delete dead code immediately

If a function, file, variable, or asset is unused, remove it — don't comment it out or rename
it with a leading underscore. Zip snapshots + Dropbox history are the recovery net. Leave every
file you touch leaner than you found it. The project is pre-release with one user — there is no
backwards-compatibility debt to preserve.

### 6. Keep CLAUDE.md current

When a change affects architecture, conventions, the directory layout, commands, the design
invariants, or any workflow documented here, **update this file in the same session**. Drift
here is how institutional knowledge rots.

### 7. Minimal diffs; understand before changing

Make the smallest change that solves the problem. No drive-by refactors bundled into a feature
change. Read and comprehend the relevant code — and this file — before modifying. Rules apply to
the edit you're about to make; they aren't retroactively reinterpreted.

### 8. Design consistency: read `DESIGN.md` before any CSS change

**Before editing `app/frontend/styles.css` or any inline `style={{…}}`, read
[`.claude/DESIGN.md`](DESIGN.md)** — the design dictionary (tokens, element recipes, the fixed semantics
of color/type, and the consolidation worklist). New controls conform to an existing recipe + reference a
token; never re-type a raw hex a token already names, and don't borrow one semantic color for another
(indigo = provenance/primary; green = verified; amber `--flag` = unresolved/uncertain/region status; red
`--danger` = destructive). If a change reveals a new inconsistency, record it in `DESIGN.md`'s Pass-2
worklist. This exists to stop design-by-committee drift as new UI lands in the existing codebase.

### 9. Principle fidelity: run the Principles alignment gate before claim/signal features

**Before adding or removing any functionality that produces a claim/signal/judgment about the literature — or
that changes inspectability, provenance, the fact-vs-candidate distinction, or the egress posture — run the
[Principles alignment gate](#principles-alignment-gate-read-claudeprinciplesmd)** (read `.claude/PRINCIPLES.md`
first). Name the principle(s) touched + the worked example it resembles; name the easier, misaligned path; and
when at odds, **propose the aligned alternative** — design *what could be right*, don't just object. A feature
that can't honor the principles is a finding about the feature. For **novel / value-level / future-track**
changes (where no principle directly fits), the gate also consults the deeper **values layer**
(`.claude/APPROACH-AVOIDANCE.md`) — derive the check from the value, run its drift typology, and honor its
veto-level boundaries; it is conditional, not a second mandatory read. For anything touching **founder/
governance authority, workplace power or surveillance dynamics, or external advisory-body questions**, also
consult `.claude/GOVERNANCE-COMMITMENTS.md` — narrower still, not a third mandatory read on ordinary edits.

### 10. QA coverage: read `.claude/QA-POLICY.md` before changing an end-user surface

**Before adding or altering any end-user surface — a new API endpoint, a changed request/response contract, a
new interactive control, a new view-state, or a new async job — read [`.claude/QA-POLICY.md`](QA-POLICY.md) and
add or extend a QA route in the same increment.** QA coverage is a **computed property**:
`python tools/qa/build_surface_map.py check` diffs the surfaces declared by the routes in `.claude/qa-routes/`
against the surfaces that actually exist (88 API + ~460 frontend at inc 119). An uncovered **API** surface fails
the check (hard gate); uncovered **frontend** elements are reported as a checklist. Shipping a surface without a
route is the QA analogue of CLAUDE.md drift. Every route also asserts the project's honesty invariants (egress
gate, coordinate honesty, signal-not-verdict), so QA tests the soul of the app, not just that buttons click.
Security-class findings open a `.claude/security-audits/` stub via the existing audit gate — QA feeds it, never
duplicates it. The Codex-`exec` supervisor (`tools/qa/supervisor.py`) runs the routes and deposits reports to the
watched `.claude/qa-inbox/`; you are the triage-and-fix half (Session-kickoff step #11).

### 11. End-user experience: read `.claude/EXPERIENCE-PASS.md` before calling a user-facing change done

**Before any user-facing change is "done" — a new feature, a revised flow, a moved control, a new signal/output —
run the [end-user experience pass](EXPERIENCE-PASS.md).** Where DESIGN (#8) asks *does it look right*, PRINCIPLES
(#9) *is it honest*, and QA (#10) *does the surface work + is it covered*, this asks **does it actually serve the
user** — a change can pass all three and still strand a real person mid-task (a correct signal with no obvious path
to the action it implies; a feature buried where no one finds it; a number with no way to reach the evidence
behind it). **Inhabit the end user of the thing you touched** and ask: (1) **reception** — is it discoverable,
legible, is the next step obvious; (2) **intended use** — what does the user reach for next, does the built thing
support it or dead-end (vigilance: a desire that conflicts with our commitments — accusation, paywall
circumvention, an opaque score — is **declined** per #9 + APPROACH-AVOIDANCE, not served). For a **newly
rolled-out or materially-changed** feature, **dispatch a persona-grounded experience agent** (or more than one) per
the doc's mechanism — a subagent *in character* as a concrete user with a goal-in-the-moment (e.g. the **deadline
citer** vetting a paper's stats before citing it), driving the feature and reporting what's left to be desired. A
**reflective pause, not a block**; the output is a finding — fix what's cheap in the same increment, else file a UX
follow-up to `INCREMENT-BACKLOG.md` (tagged to the persona it blocks) and record the pass in the increment notes.

### 12. Latency and model-backed backend work

Any addition or modification to backend code that uses local models, cloud/remote models, model-provider clients,
model-backed background jobs, or latency-sensitive inference **MUST** comply with the repository latency contract at
[`.claude/LATENCY.md`](LATENCY.md).

Before implementing such a change:

1. Read `.claude/LATENCY.md`.
2. Identify the affected user-visible critical path.
3. Preserve the applicable current performance invariants documented there.
4. Do not introduce per-item inference, repeated compatible model/client construction, unnecessary fixed polling,
   uncontrolled transformer padding waste, or unnecessary serialized remote calls.
5. Preserve scientific semantics and positional ordering unless the task explicitly intends to change them.
6. Benchmark material performance changes using representative workloads and the measurement requirements in
   `.claude/LATENCY.md`.
7. Separate correctness tests from performance benchmarks.
8. Report any intentional deviation from `.claude/LATENCY.md`, why it is necessary, and the measurements supporting it.

A model-backed change is not complete merely because it is functionally correct; it must also avoid unjustified
latency regressions.

---

## Increment workflow

callosum is built in **numbered increments** (currently at 497). Each increment of real work
produces an `INCREMENT-NN-NOTES.md` in **`.claude/docs/increment-notes/`** (all notes, oldest→newest,
live there) with this shape:

- **Implemented** — what changed, in which files.
- **Key technical detail** — the non-obvious math/contract (e.g., the coordinate transform).
- **Manual verification script** — exact steps to reproduce the check (start app, load X,
  click Y, confirm Z).
- **Pytest** — the passing count.

When you complete a meaningful increment, write its notes file in this shape and bump the
number. These notes are the running design diary; read the most recent few at session start.
**Keep this briefing small:** the per-increment *narrative* lives in `.claude/docs/increment-notes/`
(the historical narrative CLAUDE.md once carried in a footer is archived in
`.claude/session-kickoff-log.md`) — CLAUDE.md itself carries **no per-increment footer**; don't
recreate one here.

**Backlog closure discipline (2026-08-09).** `.claude/docs/INCREMENT-BACKLOG.md` is the **open queue only** —
every entry there describes work not yet done. When an item closes: **delete its entry from
`INCREMENT-BACKLOG.md` entirely** (never leave a growing "✅ CLOSED [paragraph]" bullet in place — that
paragraph-in-place growth is exactly the drift that made the file balloon past 900 lines by inc 465) and
**append exactly one compressed `- [x]` line to `INCREMENT-BACKLOG-DONE.md`**, keyed by the item's stable `#N`
tag where it has one (numbers are never reassigned, so `grep "#N" INCREMENT-BACKLOG-DONE.md` finds it
precisely) and pointing at the relevant `INCREMENT-NN-NOTES.md` for full narrative — the increment notes are
already the source of truth for *what happened*; the DONE file is an index, not a second diary, so don't
re-narrate there either. A partially-closed item (some sub-pieces shipped, one genuinely still open) gets
trimmed in place to just its open remainder in `INCREMENT-BACKLOG.md`, with the shipped detail moved to the
DONE file the same way. This keeps the open file cheap to read in full every session, which is the point.

---

## Verification protocol

No change is "done" without verification appropriate to the surface it touches.

1. **pytest is the primary gate — but run it *targeted*, not whole, during dev (inc 300).** The full serial suite is
   ~45 min; **don't run everything for a localized change.** The suite is split per-resource, so:
   - **While developing:** run only the changed area's file(s) — `pytest tests/test_<area>.py -q` (feed →
     `test_feed.py`, discovery → `test_discovery.py`, queue → `test_reading_queue.py`, …); for any `app/frontend/`
     edit also run `pytest tests/test_frontend_assembly.py -q`. Or let **`pytest --testmon -q`** pick the affected
     tests automatically (change-based selection). These finish in **seconds**.
   - **Before merging / calling a multi-file change done:** run the full suite once — **`pytest -n auto -q`**
     (parallel, ~3-4× faster) — and it must be green. CI also runs `pytest -n auto -q`, so you can lean on CI for the
     full gate. Add/update tests for new behavior (the suite covers API, persistence, PDF extraction, embeddings,
     clustering, summarization, NLI). Report the actual pass count from whichever run you cite.
2. **Pipeline / retrieval / extraction changes:** run `python tools/validation_harness.py`
   against the library and eyeball the generated report + debug images in `.local/`. This is
   how extraction accuracy, chunking, embedding, and retrieval quality are checked end-to-end.
3. **UI changes (`app/frontend/*`):** start the app and run a **manual verification script**
   (the INCREMENT-29 pattern) — load a real synthesis, exercise the control you changed,
   confirm citations open the right PDF/page and that exact/region/null precision renders per
   the honesty contract. There is **no browser-automation dependency in the repo**; the
   Playwright MCP is session-level and optional. If you can't run a visual check, say so and
   flag it as a follow-up — don't claim a UI change is done on a static read alone.
4. **Word-processor adapter changes (`adapters/libreoffice/`, and its Word/Google-Docs siblings):** real UNO
   mutation logic is **never faked in pytest** — only pure/decidable logic (encode/decode, ordering, request
   shape) gets pytest coverage, via small duck-typed fakes where a real collection is simple enough to fake
   faithfully (e.g. `_snapshot_marks`, `diagnose_document`'s tests). Everything that touches a real `doc` object
   is verified by `adapters/libreoffice/selftest_uno.py`, run via `python adapters/libreoffice/run_roundtrip.py`
   (a real headless LibreOffice + a real callosum server against a seeded temp DB) — run this for any change
   under `adapters/libreoffice/`. This also runs in CI (`.github/workflows/libreoffice-adapter.yml`, inc
   327-adjacent), path-scoped and **non-blocking** (a real headless-UNO session has observed transient startup
   flakiness even locally) — lean on it for visibility, but a local run is still the fast feedback loop.
5. **API/backend changes:** hit the endpoint, confirm status + response shape; for DB-writing
   paths, query before/after and confirm the delta.

---

## Workflow best practices

1. **Planning mode first for non-trivial work** (3+ files, architectural change, risky
   refactor). Single-file edits and typo fixes: execute directly.
2. **Understand before changing** — read the code and this file first.
3. **Minimal diffs** — no drive-by refactors in a feature change.
4. **Clean as you go** — remove dead code you encounter (rule #5).
5. **Security first** — never weaken an invariant; invoke the audit gate when triggered.
6. **Timestamped backups before risky edits** — zip snapshot or copy affected files into
   `.claude/backups/` before large refactors, schema migrations, or deletions.
7. **Verify, don't assume** — see the Verification protocol.

---

## Security baseline & audit gate

callosum is **local, single-user, no network exposure** today, but it is designed so it *could*
be made public later — so the discipline below is enforced now, not retrofitted.

**Currently in place:**
- No remote exposure; the app binds to `127.0.0.1` and CORS is restricted to
  `localhost`/`127.0.0.1`, GET-only, no credentials (`app/backend/api/app.py`).
- **Egress off by default** — Gemini calls require explicit `CALLOSUM_ALLOW_DATA_EGRESS`
  consent (invariant #3); the API key lives in `GOOGLE_API_KEY`, never in code.
- **Optional account is opt-in + identity-only (accounts SP1, inc 194).** "Sign in with ORCID"
  (`app/backend/api/auth/`, OIDC + PKCE) is **default-OFF** (no issuer/client_id env → no sign-in) and sends **no
  library text** — it verifies identity + populates My-Pubs only. Tokens are write-only (keychain/file, never in
  `GET /settings`); the redirect is loopback-validated; the `/oauth/callback` navigation is the only new gate
  exemption (opaque code+state).
- **Opt-in, E2E-encrypted cross-device sync (accounts SP3, incs 197–202).** The crypto + engine are local/no-egress
  (197–201); the **egress channel** is the opt-in `/sync/*` endpoints + the self-hostable **`sync_server/`** (inc 202):
  **default-off**, runs only when enabled + configured + signed-in, and **only opaque AES-GCM ciphertext** leaves (the
  DEK never does — E2E; the server can't read it). The Gemini library-text gate (#3) is a *separate* channel, untouched.
  Audits `2026-06-29_sync-crypto-sp3a.md` + `…_sync-engine-sp3b.md` + `…_sync-server.md` (PASS, + a 2026-07-20
  addendum on the latter). **SP3c (the Settings → Sync UI + conflict review) shipped incs 310–311** — conflict
  list/resolve endpoints, the setup/enable/run UI, and a conflict-review panel; browser-verified with Playwright.
  **The maintainer's own account platform is live (inc 312, 2026-07-20):** Authentik + `sync_server` self-hosted on
  a home LAN box, exposed via an outbound-only Cloudflare Tunnel (no hosting cost) — a real ORCID sign-in and a
  real 1,514-record sync both verified end-to-end. Getting the live round-trip working surfaced + fixed three real
  bugs (zero-leeway JWT timestamp checks, a JWKS-verifier issuer-string mismatch, and `/sync/run` never refreshing
  a stale access token) — see `INCREMENT-312-NOTES.md`. Follow-ons (yours, not code): per-user rate-limiting/
  retention on the server before any public/multi-tenant deploy (this remains a single-maintainer self-host).
  **SP4a — sharing identity (inc 475, round 3 item #4 of #15's last open thread) starts the SP4 sharing arc**:
  a per-account X25519 keypair (`app/backend/sync/identity.py`), private key sealed under the existing sync DEK
  (reuses `crypto.py`'s `encrypt_payload`/`decrypt_payload` unmodified — no new KEK), a server-side public-key
  directory (`sync_server/identity_store.py`, reachable only by exact `sub`, structurally never a listing/search
  surface), and a fingerprint-verification UI (`35c_sync.jsx`'s `SharingIdentityPanel`, Signal's "safety number"
  pattern — never trust a lookup alone). **No record is shared in this stage** — it only makes "who is this
  collaborator, cryptographically" answerable. Audit `2026-08-10_sync-identity-sp4a.md` PASS. **SP4b — share
  (inc 476)** is the sender-only next stage: `app/backend/sync/sharing.py`'s `wrap_content_key`/
  `unwrap_content_key` is a "sealed" hybrid-encryption envelope (fresh ephemeral X25519 ECDH + HKDF-SHA256 +
  AES-256-GCM — the same construction shape as libsodium's `crypto_box_seal` / an HPKE base-mode ciphersuite;
  no sender authentication in the envelope itself, since the sync-server's bearer-token-derived `sender_sub`
  column already authenticates who created a share) that wraps a fresh one-time content key to a
  fingerprint-confirmed recipient's public key. The share's plaintext content reuses the already-audited B2
  `build_bundle(scope="selection", ...)` completely unmodified (no PDFs) — a new bulk-bar "share…" action
  (`28c_share.jsx`) resolves the recipient via SP4a's own lookup before the passphrase/Share button render.
  Audit `2026-08-12_sync-sharing-sp4b.md` PASS. **SP4c — receive (inc 477)** closes the send→receive loop: a
  new "Shared with me…" entry (Library "+ Add" menu, `28d_shared_with_me.jsx`) lists shares addressed to me
  (no passphrase — sender + timestamp only), then decrypts one on explicit per-row action using my own SP4a
  identity's private key (`unlock_private_key` + `unwrap_content_key` + `decrypt_payload`, all reused
  unmodified) and merges it via `import_bundle()` (a new backward-compatible `source=` kwarg stamps a
  share-imported paper `imported_source="share-import"`, distinct from a file-bundle's `"bundle-import"`,
  without touching a merged paper's own prior provenance). A non-recipient can never fetch a share's content —
  the sync-server 403s `GET /shares/{id}` to anyone but the addressed recipient, propagated locally as a clean,
  distinct signal (never lumped into the generic "unexpected server error" path). A new local `received_shares`
  table is the cross-user provenance log (one row per share acted on — imported or dismissed). Independent
  re-verification needed zero new code — B2 SP3's existing "Re-verify against my library" action already works
  on any relayed synthesis regardless of how it arrived. No new sender-verification mechanism or allow-list —
  the honest, minimal answer links to SP4a's existing fingerprint-lookup tool instead. Audit
  `2026-08-12_sync-sharing-sp4c.md` PASS. **SP4d (inc 478) closes the SP4 arc**: a sender-only soft-revoke
  (`revoked_at` on `sync_server`'s `shares` table) lets a share be withdrawn before import — never after, since
  the server structurally has no read-receipt concept and can't know if a recipient already decrypted it; a
  local-only, never-egressed blocked-senders list (`app_settings.py`) replaces the originally-sketched "roles"
  territory, which turned out to have no target in the shipped one-shot-snapshot share architecture.
- SQLAlchemy bound parameters (rule #3); PDF + external-input validation at the boundary
  (rule #4).

**Audit gate for major additions.** Any one of these triggers a security review **before** the
work is called done:
1. A new API endpoint or major request-schema change.
2. A new external fetch/integration (a new metadata/discovery/LLM service).
3. A new file-ingestion or file-write path.
4. Any new auth/session/authorization logic (e.g., when adding multi-user / public access).
5. A net-new feature spanning 3+ files or ~300+ added LOC.
6. A new third-party dependency.

**Required audit actions:**
1. Create `.claude/security-audits/YYYY-MM-DD_<feature>.md`.
2. Document the threat review: input validation, output encoding, injection, SSRF / external
   calls, secret handling, data egress, resource caps, file-path safety, supply-chain (pin deps).
3. Run negative-path checks (malformed input, oversized files, unauthorized access, egress
   while disabled) and record the concrete results.
4. End with **Security Audit: PASS** or **Security Audit: RISK ACCEPTED BY USER**. Unresolved
   risk blocks the change until the user signs off.

**Before any public/internet-facing deployment** (not done today — track it):
- **Auth + rate-limiting now EXIST as an opt-in foundation (inc 168, default-OFF):** `AccessControlMiddleware`
  (`app/backend/api/access_control.py`) — when **Remote access** is enabled (Settings, for the Google Docs add-on
  via a cloudflared tunnel), a constant-time **bearer token** is required on every endpoint except `GET /health` +
  `GET /` (the static shell), plus a hand-rolled sliding-window **rate limiter** (429). Default-off → a pure
  pass-through (zero change for localhost-only users). The token is stored like the BYOK key (keychain/file,
  write-only over the wire); the frontend sends it via a same-origin fetch shim (`00_lib.jsx`, token in
  localStorage, never injected into HTML). Recovery hatch: `CALLOSUM_DISABLE_REMOTE_ACCESS=1` — **or the in-app
  lockout recovery (inc 254):** a 401 raises one honest `AccessLockOverlay` (`01_recovery.jsx`) offering paste-the-token
  or `POST /access/recover` — a **gate-exempt-but-rate-limited, disable-only** path that proves local-machine possession
  via a one-time code written to `~/.callosum/recovery-code.txt` (returns only the path; only ever turns Remote access
  OFF; never reveals the token). Audit `2026-07-02_access-recovery.md` PASS. **The cloudflared
  ingress allowlist (forward ONLY the cite endpoints — `/papers`, `/papers/export`, `/citations/*`) is a REQUIRED
  SP1 control** so the file-read/scan routes + `/` are unreachable via the tunnel (recorded in the inc-168 audit).
  Re-audit before a *general* hosted deployment (this foundation targets the single-user add-on tunnel, not
  multi-tenant hosting).
- **Read-only mobile reading (B5 SP1, inc 237, default-OFF):** `CALLOSUM_READ_ONLY=1` (an env var) makes the
  `AccessControlMiddleware` return **403** for every mutating method (anything but GET/HEAD/OPTIONS) — the *method*
  boundary the cloudflared path allowlist can't provide (a path like `/papers/5` serves both a GET read and a DELETE
  write; cloudflared matches path only). The recommended deploy runs a **second, read-only callosum** for the tunnel
  (the inc-170 isolated-instance pattern) with `CALLOSUM_READ_ONLY=1` + Remote access on, behind the read-only
  cloudflared ingress (`adapters/mobile/`, defense in depth) — the desktop instance stays read-write. Audit
  `2026-07-01_mobile-reading.md` PASS.
- The localhost-only CORS + PDF/file-serving paths must be re-reviewed for a hosted context.
- **`POST /library/scan` reads a user-supplied folder server-side** (inc 87), **watched folders (inc 98)
  persist those paths + auto-read them on launch** (`POST /library/watched/rescan`), and **the library folder
  (`library_dir()` = `CALLOSUM_LIBRARY_DIR` / project `library/`) is auto-read on every launch/focus rescan
  (inc 160)** — fine on 127.0.0.1 (the server is the user's machine), but a remote caller could enumerate/read
  server files. **Gate or remove these before any hosted deployment.**
- Re-audit the egress gate, secret storage, and per-IP resource caps.

---

## File containment policy

**All temporary, working, and Claude-generated files go inside `.claude/`** (scratch scripts,
working copies, audit outputs, diagnostic probes, plan backups). **Generated databases, debug
images, and validation runs go inside `.local/`** (gitignored). Never scatter scratch files
across `app/`, `integrations/`, `tools/`, or the project root, where they get confused with
real code. If in doubt, put it in `.claude/`.

---

## Codebase hygiene & storage economy

- **`.local/` and `.claude/backups/` bloat fastest.** Validation runs write a `validation.sqlite`
  + a report + debug-image PNGs per run; zip snapshots accumulate. Prune old runs and snapshots
  (see Backup lifecycle).
- The `library/` PDFs (~77 files) and all `.local/` DBs are gitignored — they are data, not code.
- Delete dead code and stray artifacts as you go (rule #5).

---

## Backup & snapshot protocol

callosum is a **git repo** (remote `origin` → `github.com/cliffworkman/callosum`, public, AGPL-3.0):

1. **Git + GitHub is the primary, off-machine backup.** **Convention: commit + push at the end of each work
   session by default** (no need to be asked) so the remote — the user's geographically-orthogonal backup —
   never drifts behind; a single catch-up commit for a span is fine (the per-increment story lives in
   `changes.md` + the increment notes). The base "commit/push only when asked" default is overridden for the
   end-of-session case on this project. **Before pushing, run `ruff format` (not just `ruff check`)** — CI's
   lint job runs `ruff format --check .` too (see the verification note below) — and confirm CI goes green.
2. **Zip snapshots** of the working tree land in `.claude/backups/` (`callosum_HHMMpm.zip`,
   `callosum_inc29.zip` style). Take one before a risky refactor or at the end of a substantial
   increment.
3. **Dropbox version history** is the always-on safety net for individual files.
4. **Plan-file backups:** plan files at `~/.claude/plans/*.md` are per-conversation and get
   cleared. For any plan worth continuing, copy it to
   `.claude/backups/plans/YYYY-MM-DD_<short-description>.md` and keep it updated. On startup,
   check there when the user asks to continue earlier work.
5. **Cutting a public desktop-shell release (inc "release engineering," 2026-07-28).** Item #1's
   "commit + push to `main` by default" is unchanged and still happens every session — but since real
   colleagues now run real installers, **`main` moving is not the same event as a release reaching
   anyone.** A release is a separate, deliberate act, gated on a **version tag**:
   - Bump the three desktop-shell version fields **in lockstep** — `app/desktop-shell/src-tauri/
     tauri.conf.json`, `src-tauri/Cargo.toml`, `app/desktop-shell/package.json` (+ their lockfiles) —
     to the new `X.Y.Z`. **Never bump `pyproject.toml` for this** — it's inert Python-package metadata
     with its own independent lifecycle, unrelated to the desktop shell's version.
   - Commit + push that bump to `main` exactly like any other change; confirm the three
     `desktop-shell-{windows,macos,linux}.yml` CI runs (they trigger on this push same as always) are
     green.
   - `git tag -a vX.Y.Z -m "<real release notes — this message becomes the GitHub Release body>"`,
     then `git push origin vX.Y.Z`. **The tag push is the only thing that ever reaches colleagues** —
     it fires `.github/workflows/desktop-shell-release.yml`, which rebuilds all three platforms fresh
     (as reusable-workflow calls into the same three files, not a separate build path) and, only once
     all three succeed, publishes one public GitHub Release with all three installers attached. A fast
     preflight step in each platform workflow hard-fails before the expensive build if the tag's
     version disagrees with the three files above — the guardrail against tagging without bumping or
     bumping without tagging.
   - No separate `CHANGELOG.md` — the annotated tag's own message *is* the release's changelog entry
     (extracted verbatim as the GitHub Release body), so there's exactly one place release notes live,
     not two that can drift apart. Revisit only if a colleague specifically wants an offline/in-repo
     changelog file.
   - `README.md`'s Download section and `www/index.html` link at GitHub's stable `.../releases/latest/
     download/<file>` URLs — these never need editing on subsequent releases; only bump-and-tag when
     shipping something new. The in-app auto-updater (Tauri's updater plugin + a signing keypair +
     background check-for-updates) is a deliberate, separate later increment — not built yet; see
     `INCREMENT-BACKLOG.md` for the sketch.

---

## Change tracking

Keep `.claude/changes.md` as a running, human-readable log of every non-trivial change
(increment notes are the design diary; this is the chronological "what & why" record).

```markdown
## 2026-06-16 — short title
- **Files:** `path/a`, `path/b`
- **What:** one-sentence description
- **Why:** one-sentence motivation
- **Revert:** restore from `.claude/backups/<snapshot>.zip` OR specific instructions
```

Skip trivial edits (typos, whitespace). Log everything else.

**Help-doc sync marker.** The served help corpus (`app/backend/help/help_content.md`) must track user-facing
behavior. To find what's changed since it was last refreshed *without* re-scanning the code, `changes.md`
carries a `<!-- HELP-DOCS-SYNCED … -->` marker line at the top of the entry of any increment that brought the
corpus current. Because the log is **newest-first**, every entry **above the topmost marker** is a change
made since the last help sync — the candidate set to review. When an increment updates the corpus, move the
sync point forward by adding a new marker at the top of its entry. (See the Session-kickoff check.)

---

## Backup lifecycle

`.claude/` and `.local/` accumulate. Keep them lean:

- `.claude/backups/*.zip` — older than 30 days → delete (keep the latest per increment).
- `.local/` validation runs (DBs + debug images) — delete once their report has been acted on;
  hard-prune anything older than ~30 days.
- `.claude/security-audits/` and `.claude/backups/plans/` — **keep indefinitely** (institutional
  memory).

---

## MCP server usage

callosum ships **no committed `.mcp.json`.** The only session-level MCP tool used in practice is
**Playwright**, for optional manual UI checks of the assembled frontend — it is not a project
dependency, and the repo never relies on it. If you expect an MCP server and it isn't available,
say so and adjust the plan. Keep this section updated if a project-level MCP config is added.

**Playwright is already registered for this project (2026-07-29), local scope, private to the maintainer's
own machine** (`claude mcp get playwright` → `Scope: Local config (private to you in this project)`; browser
binaries were already installed via a prior `playwright install` on this machine — nothing to install). This
is **not** a committed `.mcp.json` (the paragraph above stays true for the repo itself) — it's a per-user
config Claude Code stores outside the repo. Because MCP tool availability is fixed at session start, a
session that started before this was registered (or that never called `ToolSearch` for it) will report no
browser automation available even though it's configured — **always `ToolSearch` for `mcp__playwright__*`
before concluding it's unavailable**, and if a long-running session genuinely doesn't have it, tell the user
to restart with `claude --continue` (resumes the same conversation in a fresh process that picks up the
already-configured server) rather than assuming a manual verification step must be skipped.

---

## Reference docs

The planning + research suite under `.claude/` is the institutional-memory layer — consult it
before large design changes:

| Path | Content |
|---|---|
| `.claude/PRINCIPLES.md` | **The project charter — read before ANY claim/signal/judgment feature (rule #9 / Principles alignment gate): the 10 commitments, the THEORY contract, and four aligned-vs-misaligned worked examples. When at odds, propose the aligned alternative.** |
| `.claude/APPROACH-AVOIDANCE.md` | **The value substrate *beneath* the charter — the deeper, *conditional* layer of the gate (consulted for novel / value-level / future-track changes only, not every gated edit): 8 approach values + standalone veto-level avoidance boundaries (no paywall circumvention / no reaching into other tools' stores / no accusation of individuals) + the confirmed/extended/emergent/divergent drift typology. Derive the check from the value when no principle directly applies.** |
| `.claude/GOVERNANCE-COMMITMENTS.md` | **Cliff's signed, dated public precommitment on founder/organizational governance (not product design): founder-accountability practices, triggers for expanding governance beyond one person, and the composition/limits of a future external advisory body. Narrowest-trigger of the three gate documents — consult for founder-authority, workplace-power/surveillance, or advisory-body questions; not a third mandatory read on ordinary feature work.** |
| `.claude/CREDIT-THE-LINEAGE.md` | **Values-layer cross-cutting principle (inbox-captured 2026-06-21): any tool that implements/operationalizes/is-built-on identifiable scholarly work must credit it *in-context* + offer the source paper(s) to the library (one-click), and credit a prior *tool* by citation + library-add, never by appropriating its name. Apply to every method-implementing feature; the retroactive credit-help backfill is in the backlog. Not yet wired as a hard rule-#9 gate trigger.** |
| `.claude/DESIGN.md` | **Design dictionary — read before ANY CSS/inline-style change (rule #8): tokens, element recipes, fixed color/type semantics, consolidation worklist** |
| `.claude/QA-POLICY.md` | **The QA contract — read before changing any end-user surface (rule #10): the fixture contract, the computed coverage gate (`tools/qa/build_surface_map.py`), the honesty-invariant assertions, the severity rubric, and the Codex-exec supervisor + watched-inbox loop. Add/extend a QA route in the same increment as a surface change.** |
| `.claude/EXPERIENCE-PASS.md` | **The end-user experience pass — read before calling any user-facing change done (rule #11): the two questions (reception / intended-use, the latter bounded by the #9 + A-A vetoes), the persona-grounded experience-agent mechanism (dispatch a subagent in-character as a concrete user with a goal-in-the-moment), the extensible persona/scenario library (deadline citer / corpus builder / skeptical synthesizer), and the statcheck worked example. A reflective pause → a finding (fix-cheap or backlog). The 4th gate: DESIGN=looks, PRINCIPLES=honest, QA=works+covered, EXPERIENCE=serves the user.** |
| `.claude/LATENCY.md` | **The latency contract — read before adding or modifying local/remote model work, provider-client use, model-backed jobs, or latency-sensitive inference (rule #12). It records the live batching, runtime reuse, provider reuse, token-shape, long-poll, measurement, and scientific-equivalence invariants that performance-sensitive changes must preserve or intentionally revalidate.** |
| `.claude/docs/future-tracks/` | The 7 longer-horizon track docs (statcheck/open-science, word-plugin, highlight-to-suggest/evaluate, full-text acquisition, my-publications, theory/methods, plugins, gapfinder, library Feed/Search). Referenced by `INCREMENT-BACKLOG.md`. |
| `.claude/staged-harnesses/REGISTRY.md` | **Dormant fitness-function drafts (backlog #20 ratchet, session-kickoff #11): Pyright, tach, a coverage gate, Hypothesis property tests, an embedding-drift harness, performance monitoring, bandit — each drafted with its activation trigger, not wired in until the trigger fires.** |
| `app/backend/help/help_content.md` | **The served help corpus (inc 59) — the source of truth for user-facing help.** Edit here (then it renders in the `?` modal). Keep current via the `HELP-DOCS-SYNCED` marker. |
| `.claude/HELP.md` | Historical tip text (superseded by the served corpus above; kept as a dev note) |
| `.claude/docs/INCREMENT-BACKLOG.md` | The running nearer-term to-do list — **open items only** (reference-manager-first). Shipped/closed items live in `INCREMENT-BACKLOG-DONE.md` (split 2026-06-20). |
| `.claude/docs/product-scope.md` | What's in/out of scope |
| `.claude/docs/architecture.md` | Intended architecture |
| `.claude/docs/data-contracts.md` | Schema + payload contracts |
| `.claude/docs/risk-register.md` | Known risks + mitigations |
| `.claude/deprecated/roadmap.md` | **Archived (Phase 6, 2026-06-20, stale)** — the old staged skeleton→discovery roadmap; current status lives in the increment diary + `INCREMENT-BACKLOG.md`. |
| `.claude/docs/glossary.md` | Domain terms |
| `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md` | Per-increment design diary (all increments, oldest→newest) |
| `.claude/docs/research/opus4.8_deepresearch_callosum_plan.md` | Architecture + tech survey baseline |
| `.claude/docs/research/opus4.8_deepresearch_callosum_feedback.md` | Review of the planning skeleton |
| `.claude/deprecated/backlog-future-tracks.md` | **Archived (Phase 6, 2026-06-20)** — earlier capture of the external tracks, superseded by `.claude/docs/future-tracks/` (the canonical source). |

---

## Architectural decision log

IF NEEDED, see ".\architectural-decisions-log.md"

---

## Session kickoff

When starting any non-trivial work:

1. **Read this file in full.** Rules apply to the edit you're about to make, not to history.
2. **Scan the most recent notes in `.claude/docs/increment-notes/`** and `.claude/changes.md` — they tell you
   what shifted recently and what the current state is.
3. **Confirm the environment:** Python 3.11+, deps installed (`requirements.txt` /
   `requirements-dev.txt`), `CALLOSUM_DB_URL` pointed at the right SQLite DB.
4. **If a plan file gets created**, back it up to `.claude/backups/plans/` immediately.
5. **For security-sensitive edits** (new endpoint, new external fetch, new ingestion path,
   any future auth), open a `.claude/security-audits/` stub at task-start and fill it as you go.
6. **For UI edits**, plan the manual verification script up front; flag it if you can't run it.
7. **Check whether the help docs need updating.** Grep `.claude/changes.md` for the topmost
   `<!-- HELP-DOCS-SYNCED … -->` marker; if any entry **above** it changed user-facing behavior (a new
   feature, a renamed control, a changed workflow), the served help corpus
   (`app/backend/help/help_content.md`) is likely stale — flag it to the user and offer to refresh the
   affected section(s). (Leverages the changelog instead of a blind code scan.)
8. **Run the Principles alignment gate (rule #9) for any claim/signal/judgment feature.** Read
   `.claude/PRINCIPLES.md`; name the principle(s) + the worked example it resembles + the misaligned easy
   path; when at odds, **propose the aligned alternative**, don't just object. For **novel / value-level /
   future-track** work, also consult the deeper values layer `.claude/APPROACH-AVOIDANCE.md` (derive from the
   value; run its drift typology; honor its veto-level boundaries). For anything touching **founder/governance
   authority, workplace power/surveillance, or advisory-body questions**, also consult
   `.claude/GOVERNANCE-COMMITMENTS.md` — narrower still, not a routine read.
9. **For model-backed or latency-sensitive backend work, read `.claude/LATENCY.md` (rule #12).** Name the
   user-visible critical path, the live performance invariants affected, and the representative benchmark needed;
   keep correctness assertions separate from scheduler-sensitive performance receipts.
10. **Check the future-tracks watched inbox** (Phase 8). Glance at `.claude/docs/future-tracks-import/`. It
   normally sits empty bar its `README.md` + the items the README's **Parked** list names — **anything else is
   unprocessed input a prior session or the user dropped in.** For each new file, **surface it to the user**
   (report it, never act silently) and handle it per the inbox `README.md`: a genuine **future-track** → run the
   Principles + `APPROACH-AVOIDANCE.md` gate framing, fold it into `INCREMENT-BACKLOG.md` + the
   `future-tracks/README.md` index, then **move** it to `future-tracks/`; a **meta / CLAUDE.md directive** →
   action it, then remove it; a **counsel-gated / sensitive** drop → leave it **parked** (it stays in the
   gitignored inbox, named in the README's Parked list — never auto-processed or published).
11. **Check the QA inbox.** Glance at `.claude/qa-inbox/` (gitignored, local-only — like the future-tracks
   inbox). It is normally empty bar `_processed/`. For each unprocessed `<run-id>/`, read its `run-summary.md`
   (Critical/High first): **fix Critical/High in-session**, file Medium/Low to `INCREMENT-BACKLOG.md`, open a
   `security-audits/` stub for any security-class finding, then move the run to `.claude/qa-inbox/_processed/`.
   Do not act on a run silently — surface what you found and what you're fixing. The supervisor
   (`tools/qa/supervisor.py`) deposits these via headless Codex `exec` runs (the QA-POLICY loop, rule #10).
12. **Glance at `.claude/staged-harnesses/REGISTRY.md`.** Has any dormant harness's activation trigger fired
   (a type-clean baseline, an outside contributor, a library crossing ~1-2k PDFs, an embedding-model change, a
   public deployment)? Keep this a single glance, not a ritual.
13. **When in doubt, ask.** This project is pre-release with one user — a 30-second confirmation
   is cheaper than a wrong turn.

IF NEEDED, see ".\session-kickoff-log.md"
