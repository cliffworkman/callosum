# Transparency-signals METHODS auditor — design (backlog #44 increment 1; inc 250)

**Status:** approved (maintainer, 2026-07-02). Single-increment. The persistence / `system:transparency:*` tags / the
library-wide "papers with open data" filter (the #19 tags→system-facts pass) are the deliberate **increment 1b**, not
this one. Later #44 increments (DocumentTextProvider adapters; RegCheck; CRediT; a consistency registry) are further out.

## One line

A METHODS **"Transparency signals"** panel — the direct sibling of the statcheck / LMM / meta-analysis auditors
(incs 95 / 247 / 249) — that reads a paper's extracted text and detects whether it **discloses** 7 open-science
artifacts (ODDPub / rtransparent-derived), each `detected` / `not-detected` / `not-applicable`, with the matched
sentence as evidence opening its page at region precision, an always-on literacy explainer, and the in-context
`basis`. **Signal-not-verdict; silence≠certificate; never an accusation; no composite score.** Fully local — regex
only, no AI, no egress, no migration, no new dependency.

## Principles + A-A gate (run) — this track lives right on the no-accusation veto

- **Principle(s) + worked example:** PRINCIPLES Example 3 (the per-paper deterministic-signal class — the statcheck /
  LMM / meta / retraction siblings) + the **A-A no-accusation veto** as a veto-level boundary.
- **Aligned shape:** evidence-carrying (#4 — every detected signal shows the matched sentence + page; ODDPub's own
  design returns the detected sentences, so it maps straight onto our evidence contract); signal-not-verdict (#2 — a
  labeled "data-availability statement present · links to OSF", never "this paper is transparent"); **silence≠certificate
  (#6 — the load-bearing control: "no statement detected" is NEVER "no open data" / "not shared" / "concealed", only
  "not detected in the extracted text — check the paper");** no composite (#7 — no transparency score/grade/rank); no
  accusation (A-A — never "the authors failed to share their data").
- **Misaligned easy path (declined):** a "transparency score / open-science badge / this paper hides its data"
  verdict; persisting a *"NO open data"* fact from an absence (silence-as-certificate); any accusation of the authors.
- **Deterministic + local:** ODDPub / rtransparent are rule-based (regex/keyword) — so increment 1 is **regex-only, no
  LLM, no egress, no new dependency** (the LLM part is increment 3, RegCheck). The aligned default, not a fork.

## The 7 detectors

Each is a `TransparencySignal{key, label, status, evidence, page, note, explainer, basis}` — `status` is
`present`/`not-found`/`not-applicable`, **exactly mirroring `MetaCheck`** (so the panel clone renders unchanged; no
extra `detected` bool). `present` carries the matched sentence + page; `not-found` → "not detected in the extracted
text — check the paper" (never "absent"). Two checks are precondition-scoped to `not-applicable` (see below).

1. **data_availability** — a data-availability statement and/or a **repository link**. `_DATA` = "data (are|is|will be)
   (available|accessible|deposited|shared)|data availability|availability of data|(all |the )?(raw )?data (and materials
   )?(are|is)? (openly )?available|supporting data|underlying data". `_DATA_REPO` = the repository-domain list (see
   `_REPO_URL` below). basis: "ODDPub (Riedel et al. 2020)". Present iff `_DATA` OR `_DATA_REPO` matches.
2. **code_availability** — analysis code / scripts + a repo link. `_CODE` = "(analysis |source |the )?(code|scripts?|
   software) (are|is|will be)? (available|accessible|shared|provided|deposited)|code availability|reproducib(le|ility)
   (code|scripts?)|R (scripts?|code)|(Python|MATLAB|Stata|SPSS|Jupyter) (code|scripts?|notebooks?)" + `_CODE_REPO`
   (GitHub/GitLab/OSF/Zenodo/CodeOcean). basis: "ODDPub (Riedel et al. 2020)".
3. **conflict_of_interest** — `_COI` = "conflicts? of interest|competing interests?|(no|declare[sd]?) .{0,20}(competing|
   conflict)|financial (disclosure|interest)|declaration of interest|the authors declare". basis: "rtransparent
   (Serghiou et al. 2021)".
4. **funding** — `_FUNDING` = "funded by|funding|financial support|grant(s)? (from|number|no)|supported (in part )?by|
   received no (specific )?(funding|grant)|no funding was received|award(ed)? (number|by)|\b(NIH|NSF|ERC|Wellcome|
   MRC|DFG|NSFC|NIHR)\b". basis: "rtransparent (Serghiou et al. 2021)".
5. **registration** (PRECONDITION-SCOPED) — trial/protocol registration. `_REGISTRATION` = "registered (at|on|with|
   in|under)|registration (number|no|id)|\bNCT\d{6,}\b|PROSPERO|CRD\d{6,}|ClinicalTrials\.gov|(ISRCTN|ANZCTR|UMIN|
   EudraCT)|trial registration|study (was )?registered|OSF registration|registered report". Precondition: a
   **clinical/trial** cue (`_TRIAL` = "randomi[sz]ed (controlled )?trial|\bRCT\b|clinical trial|systematic review|
   meta[-\s]?analysis|study protocol|pre[-\s]?registered|preregistration|registered report") — if NO trial/registration
   cue at all, status = `not-applicable` ("not a registered/trial design where a registration is expected"), else
   present/not-found. basis: "rtransparent (Serghiou et al. 2021); CONSORT/PRISMA".
6. **preregistration** — `_PREREG` = "pre[-\s]?regist(ered|ration)|preregistered|AsPredicted|registered report|
   (analysis|study) (plan|protocol) (was )?(pre[-\s]?)?registered|OSF (pre[-\s]?)?registration|time[-\s]?stamped
   (analysis|hypothes[ei]s)". basis: "Nosek et al. 2018 (preregistration); AsPredicted / OSF Registries".
7. **upon_request** (a WEAK-SIGNAL QUALIFIER, not a standalone category) — `_UPON_REQUEST` = "(available|obtained|
   provided|shared) (from the (corresponding )?author )?(up)?on (reasonable )?request|request(ed)? from the (corresponding
   )?author|contact the (corresponding )?author". Shown as an **amber ⚠ note** ("data/code offered only 'upon request'
   — a weaker signal than a repository link", cited to the ODDPub literature) — a **legibility fact, never an
   accusation**. It fires only if `_UPON_REQUEST` matches; otherwise `not-applicable` ("no 'upon request' language
   detected"). basis: "ODDPub (Riedel et al. 2020) — 'upon request' is a weak availability signal".

**Repository domains** (`_REPO_URL`, a constant list, matched as a substring/regex): `osf\.io`, `zenodo\.org`,
`datadryad\.org`/`dryad`, `figshare\.com`, `github\.com`, `gitlab\.com`, `codeocean\.com`, `bitbucket\.org`,
`dataverse`, `openneuro\.org`, `10\.5281/zenodo`, `10\.17605/OSF`, `re3data`, `data\.mendeley\.com`. Used by
`data_availability` + `code_availability`.

**No `is_transparency` gate:** transparency applies to any empirical paper, so — unlike statcheck/LMM/meta which gate
on detecting the method — the auditor always returns the 7 checks (registration + upon_request carry their own
precondition scoping). The endpoint's only "off" state is a paper with no extracted chunks (honest-empty).

Each `explainer` is a one-line "what it is / why a reader cares" note; each `note` on a fired absence is a grounded
reader's-prompt (worded "not detected …"); the caveat block states the honest-scope + silence≠certificate contract.
**No score, no grade, no aggregate.**

## Architecture (mirrors inc 249's meta auditor — 3 new files + 1 wire)

### 1. `app/backend/methods/transparency.py` (NEW, pure)

- `@dataclass(frozen=True) class TransparencySignal: key, label, status(str: 'present'|'not-found'|'not-applicable'),
  evidence, page, note, explainer, basis` + `to_dict()` — the exact `MetaCheck` shape (no extra `detected` field).
- `@dataclass(frozen=True) class TransparencyReport: checks(list)` + `to_dict()` → `{"checks": [...]}`.
- Self-contained regex helpers (`_rx`, `_chunk_rows`, `_snippet`, `_first`, `_has`, `_NOT_DETECTED`), duplicated from
  `metaanalysis.py`/`lmm.py` (the per-module precedent — keeps the module reviewable in isolation).
- `detect_transparency(chunks) -> TransparencyReport` — runs the 7 detectors; a `_present_or_absent(key, label,
  pattern-or-repo, …)` helper builds present/not-found rows (evidence via `_first`); registration + upon_request use
  their precondition-scoped branches. No I/O, no LLM, no statistical computation.

### 2. `app/backend/api/routers/transparency.py` (NEW)

`GET /papers/{paper_id}/transparency` — sync, read-only; mirrors `routers/metaanalysis.py`:
- `TransparencyCheckOut(BaseModel)` = the same 8 fields as `MetaCheckOut` (key/label/status/evidence/page/note/
  explainer/basis); `TransparencyResponse{checks: list[TransparencyCheckOut]}`.
- handler `paper_transparency(paper_id, conn=Depends(get_connection))`: `get_paper` → **404** on `NoResultFound`;
  `detect_transparency(get_chunks_for_paper(conn, paper_id))`. A paper with no chunks → the detectors run over `[]` and
  return all-not-detected — the frontend shows a "process a PDF first" state (matching the meta panel's `hasText`
  gate), so the endpoint stays honest (never a crash, never a fabricated "not transparent").

### 3. `app/backend/api/app.py` (wire)

Import `transparency` (alphabetical, after `tags`) + `api.include_router(transparency.router)` near the methods
cluster. 3-segment sub-path (`/papers/{id}/transparency`) — no `/papers/{id}` collision.

### 4. `app/frontend/js/08h_methods_transparency.jsx` (NEW panel)

Clone `08g_methods_metaanalysis.jsx`: `TransparencyCredit` manifest + `TransparencyPaper` (self-fetches title +
chunk_count; auto-runs when `ctx.methodsOpen === "transparency"`; "Process a PDF first" when no chunks) +
`TransparencyChecklist` (per-signal `✓ detected` / `not detected` / `n/a` pills + evidence page-open at **region**
precision + the note + explainer + `basis` + the factual status tally + the honest-scope caveat; the `upon_request`
qualifier rendered as an **amber ⚠** note using the existing `--flag` family, NOT green) + `TransparencyCredit`
(`＋ add methods sources` via `apiPost("/library/import", …)`). `registerPaneSection({id:"transparency", label:
"Transparency signals", paneId:"methods", order:36, hideInReadOnly:true, render:(ctx)=><TransparencySection ctx={ctx}/>})`.
**Reuses `.bayes-check-*` / `.method-credit` / `.lmm-*`** — **no new CSS** (the amber ⚠ uses the existing `.flag`/
`--flag` tokens; DESIGN note that a weak-signal qualifier reuses the amber status family). No `09_placeholders.jsx`
change (transparency was never stubbed).

## Credit-the-lineage — the manifest

Bundled CSL-JSON (confident DOIs only; omit any unsure — no fabrication). `THIRD-PARTY-NOTICES.md` gains a
"Transparency-signals auditor" lineage block.
- Riedel, N., Kip, M., & Bobrov, E. (2020). *ODDPub — a text-mining algorithm to detect data sharing in biomedical
  publications.* Data Science Journal, 19, 42. DOI 10.5334/dsj-2020-042.
- Serghiou, S., Contopoulos-Ioannidis, D. G., Boyack, K. W., Riedel, N., Wallach, J. D., & Ioannidis, J. P. A. (2021).
  *Assessment of transparency indicators across the biomedical literature: How open is open?* PLOS Biology, 19(3),
  e3001107. DOI 10.1371/journal.pbio.3001107 (rtransparent).
- output-it-forward — a phrase/repository-domain list resource (credited by name; no DOI — carried as a software
  credit in the NOTICE block, not the CSL manifest).
- Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). *The preregistration revolution.* PNAS,
  115(11), 2600–2606. DOI 10.1073/pnas.1708274114 (for the preregistration category).

## Honesty controls (structural + test-pinned)

- **Silence≠certificate (the load-bearing veto-adjacent control):** "not detected" is worded "not detected in the
  extracted text — check the paper" and framed as the reader's prompt; the caveat states absence-in-text ≠
  artifact-doesn't-exist (may be in an appendix / structured journal metadata the extractor doesn't fully read). A test
  asserts no output string says "absent" / "no open data" / "concealed" / "not shared" / "failed to".
- **Signal-not-verdict / no composite:** statuses are only `present`/`not-found`/`not-applicable`; no `score`/`grade`/
  rank field (a test asserts absence). The tally is a factual status count, explicitly "not a score".
- **Never an accusation (A-A veto):** a detected signal describes a shown disclosure; an absence is a look-here prompt;
  the `upon_request` qualifier is a cited legibility fact, never "the authors are hiding data". No per-author aggregate.
- **Precondition-scoped:** registration + upon_request → `not-applicable` when their precondition fails (a registration
  flag on every paper, or an "upon request" flag when the phrase is absent, is the failure mode).

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_transparency-signals.md` (light — local read-only over the
  paper in hand; only inputs are a path int + the paper's own text; bounded/anchored regexes, no catastrophic
  backtracking; no SQL written [reads via the audited repo]; no SSRF/egress/secret/LLM/migration/dependency; the
  no-accusation / silence-≠-certificate controls uphold the A-A veto). End PASS.
- **QA (rule #10):** new `route_63_methods_transparency.md` (`api: /papers/{paper_id}/transparency`, `fe:
  08h_methods_transparency.jsx`) + the honesty assertions (no score/verdict; "not detected" ≠ "absent"/"concealed";
  the upon_request qualifier is amber-not-green + not an accusation; coordinate honesty; credit ＋add). Keep
  `build_surface_map.py check` at 0-uncovered.
- **Experience pass (rule #11):** dispatch a persona-grounded agent (deadline-citer / open-science-vetter vetting a
  paper's disclosures before relying on it) after the build; fix-cheap in-increment, else backlog.
- **Rule #1:** all new files well under 600. **No migration, no new dependency, no egress, no LLM.**

## Tests / acceptance criteria (`tests/test_transparency.py`, ~12, hermetic)

A `_Chunk` fake (text + page_start) like `test_metaanalysis.py`; no network/model.
- A paper with a full open-science footer (data at OSF + code on GitHub + COI + funding + preregistration) → those 5
  `present` with evidence.
- Each detector present / not-found (data, code, COI, funding, registration, preregistration).
- Repository-link detection: a bare `osf.io/ab12c` (no "data available" phrase) still trips `data_availability`.
- **registration precondition scoping:** a paper with no trial/registration cue → registration `not-applicable`; an RCT
  with a registered `NCT…` → `present`; an RCT with no registration → `not-found`.
- **upon_request qualifier:** "data available from the corresponding author upon request" → upon_request `present`
  (amber); a paper with a repo link and no upon-request phrase → upon_request `not-applicable`.
- "not detected" wording says "check the paper", never "absent"/"missing"/"concealed"/"no open data".
- No `score`/`grade`/verdict field anywhere; the report is exactly the 7-check list.
- `test_no_accusatory_language` — the module source + a sample report contain none of "concealed"/"failed to"/"hiding"/
  "no open data"/"not shared" as an emitted status.
- Endpoint: `GET /papers/{id}/transparency` → 404 unknown; a paper with no chunks → 200 all-not-detected (the frontend
  gates the "process a PDF first" state).

## Verification

- pytest full suite green (+ ~12); `ruff check` + `ruff format --check`; frontend rebuilt (`test_frontend_assembly`
  5/5); QA `check` 0-uncovered; headed `.local/visual/drive_inc250_transparency.py` (seed a paper with data-at-OSF +
  code-on-GitHub + COI + funding but NO preregistration and a non-trial design → open METHODS → Transparency signals →
  the section auto-runs → the 7-row checklist with detected rows [data ✓ with the OSF sentence, code ✓, COI ✓, funding
  ✓], a not-detected row [preregistration, "check the paper"], and n/a rows [registration — non-trial; upon_request —
  no phrase]; the tally + the in-context basis + credit ＋add; 0 console/page/genai). **The live spot-check on real
  papers is the maintainer's** (regex precision/recall on real disclosures is the first live read).
- Docs: `INCREMENT-250-NOTES.md`; `changes.md` (+ `HELP-DOCS-SYNCED` → 250 — help corpus gains an "Auditing
  transparency signals" section); CLAUDE footer + decision-log + count + directory-layout (methods/transparency.py +
  routers/transparency.py + 08h); `THIRD-PARTY-NOTICES.md`. Backlog: mark #44 increment 1 shipped; note 1b (findings +
  system-tags + filter) as the next slice.

## Deferred (out of this increment)

- **Increment 1b:** persist detected-present signals as findings-FACTs (the inc-130 store) + read-only
  `system:transparency:*` tags + a library-wide "papers with open data" filter — the #19 tags→system-facts pass (its
  own focused design + increment).
- Later #44 increments: DocumentTextProvider adapters (JATS/DOCX/HTML); RegCheck (registration↔paper delta,
  auditability-gated); CRediT builder/extractor; the consistency-check registry (DEBIT / more statcheck forms / z-curve).
- LLM-assisted detection for fuzzier disclosures (consent-gated); a per-detector precision/recall pass on real papers.
