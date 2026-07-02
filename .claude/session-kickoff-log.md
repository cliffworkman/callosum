*Last updated: 2026-07-02 — increment 252 (**effect-size converter** — the meta-analysis extraction workbench's first
buildable slice, SP1). Brainstormed → Principles-gated → spec'd → planned → built inline. **Maintainer scope
(AskUserQuestion):** converter-first (over workspace-first / full-v1-vertical) + the fullest converter (core-3 +
alternate inputs + cross-metric). **What it is:** a free-standing METHODS-panel calculator (the GRIM/Bayes hand-entry
shape — *reading* a paper's stats is deliberately the LLM/SP2 job). Hand-enter one study's reported statistics → a
common meta-analytic metric (Hedges' g / Fisher's z / log OR/RR / risk difference) + variance + a 95% CI, via standard
**cited formulas**, with the conversion **path shown**, the **formula source cited**, and every **derivation/continuity/
approximation choice recorded** + a **copy value + variance** button. The safe, deterministic, egress-free core of the
workbench — the trusted sink the later LLM-drafted extraction pipeline hands its verified data into; genuinely useful
standalone. **New files/edits:** `app/backend/methods/effectsize.py` (NEW pure — a frozen `Conversion` dataclass +
`smd`/`smd_from_t`/`smd_from_f` / `sd_from_{se,ci,iqr}`+`sd_derivation` / `correlation` / `binary` [+ Haldane–Anscombe
zero-cell] / `d_to_r`/`r_to_d`/`logor_to_d`/`cross` + a `convert(family, inputs)` dispatch + `NO_AGGREGATION`; scipy
for the CI multiplier only) + `app/backend/api/routers/methods.py` (`POST /methods/effect-size`, sync stateless —
mirrors `POST /methods/grim`; `EffectSizeRequest {family: Literal, inputs: dict}` → `EffectSizeResponse`; `convert`
wrapped → 422 on bad input) + `app/frontend/js/08i_methods_effectsize.jsx` (NEW `EffectSizeSection`; `registerPaneSection`
order 38, `hideInReadOnly`; family picker + sub-selector + form → result card + the "converts one study — never pools;
hand off to metafor/JASP/RevMan" note + credit ＋add) + `app/frontend/styles.css` (`.es-*`, tokens only, mirrors
`.grim-*`). **The load-bearing boundary — convert, never synthesize — is enforced STRUCTURALLY + test-pinned:** the
module converts one study at a time and defines **no** pooling / heterogeneity / meta-regression / bias-inference
function, and imports no meta-analysis/aggregation library (metafor/JASP/RevMan territory) — pinned by
`test_no_aggregation_code_path` (an AST scan + `NO_AGGREGATION is True`); the endpoint takes a single study's inputs,
and there is no code path that combines two `Conversion`s. **Show-the-work honesty (#7):** every result carries its
ordered `path` + a cited `formula_source` + the recorded per-study `choices` (SD-derivation SE/CI/IQR / Haldane
zero-cell continuity / cross-metric approximation) + a 95% CI — nothing is an opaque number; cross-metric always carries
an "APPROXIMATION" caveat. **Verification anchors:** hand + scipy-checked Borenstein-et-al.-(2009)-formula anchors baked
into the tests (the Bayes-vs-pingouin precedent, citeable to the textbook — no metafor/R in-env). **Fully local — no
egress, no LLM, no migration, no new dependency** (scipy already in). **Audit `.claude/security-audits/2026-07-02_effectsize-converter.md`
PASS** (local, stateless, deterministic arithmetic; bounded/validated inputs; fail-closed 422; no external fetch/egress/
LLM/migration/dependency; the never-synthesize boundary structural + test-pinned). **Principles + A-A gate (rule #9) —
aligned** (the deterministic-recompute class — Bayes inc-241 / statcheck / GRIM: a per-value computation carrying its
evidence; the misaligned "run the meta-analysis / pool these" button + hiding the derivation/approximation choice
declined). **QA (rule #10)** — new `route_64_methods_effectsize.md`; surface **183/183 API + 828/828 FE, 0 uncovered**.
**Experience pass (rule #11, meta-analyst persona, inline)** — the converter serves the meta-analyst (a bare t converts
via the "t + group Ns" path; a zero-cell 2×2 records Haldane; cross-metric is flagged; the "just pool these" desire is
declined, pointed at metafor/JASP); fixed-cheap in-increment: a **copy value + variance** button (tab-separated,
spreadsheet-paste) closing the extract loop (the inc-156 Cite-pane "vet-but-can't-extract" lesson). pytest **983 passed,
1 skipped** (+12 hermetic `tests/test_effectsize.py`: SMD means / t+F agree / degenerate-raise; SD derivations;
correlation + out-of-range-raise; binary measures; binary Haldane zero-cell; binary empty-raise; cross-metric +
always-caveated; `convert` dispatch + unknown-family-raise; the **no-aggregation AST assert**; the endpoint per family +
degenerate/unknown → 422); `ruff check` + `ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5).
help corpus gained "Converting effect sizes" (`HELP-DOCS-SYNCED` → 252); `THIRD-PARTY-NOTICES.md` credits the
conversion-formula lineage (Borenstein 2009 / metafor / Fisher 1915 / Hedges 1981 / Wan 2014 / Haldane / Hasselblad &
Hedges 1995). **Credit-the-lineage:** each conversion names its source in-context + a one-click ＋add-methods-source-
to-library. **Headed-verified, no egress** (`.local/visual/drive_inc252_effectsize.py` — open METHODS → **Effect-size
converter** → SMD means 103/5.5/50 vs 100/4.5/50 → **Hedges' g = 0.592442** [Var 0.041143] + a 4-step path + the
Borenstein source; switch to **Binary** [10/20/5/25, OR] → **log OR = 0.916291**; switch to **Cross-metric** [d→r,
0.5/50/50] → **r = 0.242536** WITH the "APPROXIMATION" caveat; no pool/aggregate control; the hand-off note + credit
＋add + the copy button; **0 console/page errors, 0 genai-host requests**). **Rule-#1:** all new files well under cap
(`methods/effectsize.py` ~300, `routers/methods.py` ~590, `08i_methods_effectsize.jsx` ~155). Notes:
`INCREMENT-252-NOTES.md`; spec `.claude/docs/specs/2026-07-02-metaanalysis-converter-design.md`; plan
`.claude/backups/plans/2026-07-02_metaanalysis-converter.md`. **NEXT — SP2+ (deferred):** the extraction **workspace**
proper (a REVIEW/SYNTHESIS surface + a user-defined *included set* + an extraction **template** + **LLM-drafted,
provenance-anchored, human-verified** extraction [the egress + heavy-A-A slice: mandatory human verification,
LLM-never-an-independent-coder] + a persisted **dataset** that feeds *this* converter + **export** to metafor/JASP/RevMan
+ an audit log); further deferred (per the doc): screening/PRISMA, double-coding/IRR, RoB instruments, figure extraction
(point at WebPlotDigitizer, don't build). Or a fresh track — the maintainer's pick.

Earlier — increment 251 (**persist transparency signals** — backlog #44 increment 1b: turns the
inc-250 ephemeral transparency panel into persistent, library-wide signal). Designed → Principles+A-A-gated → spec'd →
plan'd → built inline. **Maintainer forks (AskUserQuestion):** all 7 disclosures get a review-queue filter + a
Library-header chip. **What it does:** a **Whole library → Check all papers** batch persists each paper's
*detected-present* disclosures as evidence-carrying **findings-FACTs** (`paper_findings`, inc 130 — render as marks in
the Review pane) + every disclosure's **check status** (`open_science_signals`, inc 97), powering **7 review-queue
library filters** (data / code / COI / funding / registration / preregistration "not detected — go look", + the
*present* "available upon request" case) + a Library-header **🔎 N · open data not detected** chip (indigo work-queue
color, never the amber status-flag or red destructive). **New files/edits:** `app/backend/methods/transparency_findings.py`
(NEW producer — `persist_transparency` runs `detect_transparency` [inc 250]; builds present-only FACTs → `upsert_findings`
+ per-disclosure status → `store_transparency_status`) + `app/backend/persistence/signals_repo.py`
(+`TRANSPARENCY_SIGNAL` / `store_transparency_status` [OR-REPLACE one row per disclosure, `source=<key>`, idempotent] /
`count_transparency_review`) + `app/backend/api/routers/transparency.py` (+async `POST/GET /methods/transparency/run` +
`GET /methods/transparency/summary` + `_run_transparency_all_job` over `list_live_paper_ids`) + `app/backend/api/app.py`
(`api.state.transparency_jobs`) + `app/backend/persistence/repository.py` (SIGNAL_FILTERS values generalized
`(signal_type, status)` → `(signal_type, source|None, status)` — back-compat: statcheck/retraction pass `source=None`;
+ 7 transparency review-queue entries) + `app/frontend/js/08h_methods_transparency.jsx` (`TransparencyLibrary` batch +
`TRANSPARENCY_QUEUES` 7 review-queue links) + `03_library.jsx` (`useLibrary`: `transparencyReview` count +
`showTransparencyReview` + `refreshTransparencyChip`) + `10_pdf_layer.jsx` (the `.transparency-chip`) + `40_app.jsx`
(paneCtx `onTransparencyRan` / `onShowTransparencyReview`) + `styles.css` (`.transparency-chip` + `.transparency-queues`,
tokens only). **The A-A no-accusation boundary is enforced STRUCTURALLY, not by copy (the load-bearing constraint):**
(1) **present-only FACTs** — a FACT is written only for `status=="present"`; an absence is **NEVER** a fact (the
inc-250-declined "NO open data" fact), pinned by `test_bare_paper_writes_no_absence_facts`; (2) **status rows are check
results, not claims** — the review-queue chip/links/banner are worded "not detected — go look" / "it may still share
elsewhere", never "hides data / no open data"; (3) **no score/rank field** anywhere (the summary is a plain
`data_not_detected` count); (4) **precondition scoping for free** — the registration queue matches `not-detected` only,
so a non-trial paper's `not-applicable` is excluded (no registration flag on every paper); upon_request is the *present*
case (its absence is the norm). A re-run that detects fewer supersedes the stale FACT (via `upsert_findings` content_key)
+ flips its status row to `not-detected`. **No migration** — `paper_findings` (inc 130) + `open_science_signals` (inc
97, unique `(paper, signal_type, source)`) already exist; **no egress, no LLM, no new dependency.** **Audit
`.claude/security-audits/2026-07-02_transparency-persist.md` PASS** (local read-only persisted to existing tables with
bound-param SQL; the no-accusation boundary structural + test-pinned; no external fetch/egress/LLM/migration/dependency).
**Principles + A-A gate (rule #9) — aligned** (the statcheck-persist / retraction-FACT class; the declined "transparency
score / no-open-data verdict / persist-an-absence-as-a-fact" refused structurally). **QA (rule #10)** — `route_63`
extended (the 3 batch endpoints + the review-queue chip/filter + the present-only-FACT / review-queue-not-verdict
assertions); surface **182/182 API + 814/814 FE, 0 uncovered**. **Experience pass (rule #11, open-science-vetter,
inline)** — this increment **delivers the inc-250 F4** (library-wide surfacing + a review queue + on-card FACTs) that
the vetter needed; residual: the batch trigger stays behind the METHODS panel (the standing **F1** "buried panel"
finding — an on-paper report-card chip / on-import auto-run — already filed cross-method to #23). pytest **971 passed,
1 skipped** (+8 hermetic `tests/test_transparency_findings.py`: present→FACTs + detected status; a bare paper → **NO
absence facts** + not-detected status [the A-A pin]; re-run supersedes a now-absent disclosure + flips its status;
re-run idempotent [one status row per disclosure]; `count_transparency_review`; facts-are-facts-only; the batch endpoint
202→poll→done + the review-queue filter [data queue excludes a present-data paper; both papers in the preregistration
queue] + summary + 404; registration filter excludes n/a [non-trial] + upon-request is the present case); `ruff check` +
`ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5). help corpus's "Auditing transparency
signals" gained the whole-library batch + review queues + the chip (`HELP-DOCS-SYNCED` → 251). **Credit-the-lineage:**
unchanged from inc 250 (the detectors' ODDPub / rtransparent / Nosek credit + `THIRD-PARTY-NOTICES.md`). **Headed-verified,
no egress** (`.local/visual/drive_inc251_transparency_persist.py` — seeds an OPEN paper [data@OSF / code@GitHub / COI /
funding] + a BARE paper [nothing disclosed]: open METHODS → Transparency signals → **Whole library → Check all papers**
→ the async run → the summary "2 papers checked · 1 with ≥1 disclosure detected" + 7 review-queue links → the Library
header shows **🔎 1 · open data not detected** → click → the library narrows to the BARE paper only [the OPEN one, which
has a data FACT, excluded] → `GET /findings/overview` shows only the open paper has FACTs [the bare has none — the
absence-is-never-a-fact pin]; **0 console/page errors, 0 genai-host requests**). **Rule-#1:** all touched files under
cap (`methods/transparency_findings.py` ~51, `routers/transparency.py` ~127, `signals_repo.py` ~180, `repository.py`
~560, `08h_methods_transparency.jsx` ~230). Notes: `INCREMENT-251-NOTES.md`; spec
`.claude/docs/specs/2026-07-02-transparency-persist-design.md`. **The live spot-check on real papers is the maintainer's**
(the detection + persistence + a seeded round-trip are proven; per-detector precision/recall on real footers is the
first live read). **NEXT within #44:** the `system:transparency:*` **tags** thread (#19, deferred — the tag-provenance
model is an open design problem; FACTs + filter already deliver the value); then increments 2–5 (a full-text
`DocumentTextProvider` for JATS/DOCX/HTML so the detectors see the whole paper; a registration-consistency check; a
CRediT parser; a reported-vs-registered consistency registry). Or a fresh track — the maintainer's pick.

Earlier — increment 250 (**transparency-signals auditor** — backlog #44 increment 1, the Lakens
integration track: ODDPub/rtransparent-derived open-science-disclosure detectors, the consumer-side sibling of
statcheck/LMM/meta). Brainstormed → Principles+A-A-gated → spec'd → planned → built. **Maintainer scope
(AskUserQuestion):** an ephemeral METHODS panel + the **full ODDPub + rtransparent detector set**. **What it does:** a
METHODS **"Transparency signals"** panel reads a paper's extracted text and detects whether it *discloses* seven
open-science artifacts — data availability (a statement and/or a repository link: OSF/Zenodo/Dryad/figshare) / code &
software availability (GitHub/GitLab/Code Ocean) / conflict-of-interest / funding / protocol-trial registration /
preregistration / an `"available upon request"` weak-signal qualifier — each **present / not-found / not-applicable**,
with the matched sentence opening its **page at region precision**, an always-on literacy explainer, and the in-context
`basis`. Rule-based (regex over the ODDPub/rtransparent vocabularies); local, no AI, no egress. **The A-A no-accusation
boundary is the load-bearing line this whole track lives on:** an absence of a disclosure must NEVER read as "this paper
hides its data / has an undisclosed conflict / did no open science" — enforced structurally (no score/rank/verdict
field) + test-pinned (`test_no_accusatory_language` forbids `concealed`/`failed to`/`hiding`/`no open data`/`not
shared` in any emitted note and requires the not-found wording *"not detected in the extracted text — check the
paper"*). **NO gate (the difference from the siblings):** transparency has no `is_transparency` gate — every paper gets
the 7 checks (a non-open paper is a legitimate all-not-detected result, not an "off" state); the endpoint response is
just `{checks}`. **FLAG-not-ADJUDICATE:** no transparency score/rank/verdict (a test asserts no `score`/`grade`; the
panel tally is a factual status *count*, not a grade — #7); **precondition-scoped** — registration is `n/a` unless a
trial/registration cue is present (a registration flag on every paper is the failure mode), upon-request is `n/a` when
the phrase is absent (never "not found"); "not found" ≠ "absent"/"missing" (silence≠certificate #6). **New files/edits:**
`app/backend/methods/transparency.py` (NEW pure — `detect_transparency` = 7 regex detectors + `TransparencySignal`/
`TransparencyReport` [the exact `MetaCheck` shape] + `_present_or_absent` + self-contained `_rx`/`_chunk_rows`/
`_snippet`/`_first`/`_has`; no I/O/LLM) + `app/backend/api/routers/transparency.py` (NEW `GET /papers/{id}/transparency`,
sync read-only, mirrors `/meta-analysis`; 404 unknown, no-chunks → 200 with 7 all-not-detected) + `app/backend/api/app.py`
(import after `tags` + `include_router` after the meta-analysis include) + `app/frontend/js/08h_methods_transparency.jsx`
(NEW `TransparencySection`/`TransparencyPaper`/`TransparencyChecklist`/`TransparencyCredit`; `registerPaneSection` order
36, `hideInReadOnly`; auto-runs when its section is open; reuses `.bayes-check-*`/`.method-credit`/`.lmm-*` — **no new
CSS**). **Fully local — no egress, no LLM, no migration, no new dependency.** **Audit
`.claude/security-audits/2026-07-02_transparency-signals.md` PASS** (local read-only over the paper in hand; no external
fetch/egress/LLM/migration/dependency; anchored regexes, no catastrophic backtracking; the no-accusation boundary
structural + test-pinned). **Principles + A-A gate (rule #9) — aligned** (PRINCIPLES Example 3 / the statcheck-LMM-meta
class; the A-A veto-level no-accusation boundary is the load-bearing constraint; the misaligned "transparency score /
this paper hides its data / no open science" verdict + persisting a "NO open data" fact from an absence declined).
**QA (rule #10)** — new `route_63_methods_transparency.md`; surface **179/179 API + 808/808 FE, 0 uncovered**.
**Experience pass (rule #11, open-science-vetter, run inline)** — a near-exact clone of the inc-247/249 auditors whose
persona-agent passes already surfaced this reception/intended-use and whose in-increment fixes (the factual tally +
the `lmm-na` de-emphasis of n/a rows) this panel inherits; the vetter's need to *rely on a paper* is served once the
section is reached (the 7-row checklist + tally give the at-a-glance disclosure picture; each row self-explains). The
desire declined per #9 + A-A — a "transparency score" to rank papers, or to flag authors who "hide data" — is refused
structurally. **Filed cross-method to #44 / the shared #23 chip item:** (F1) an on-paper **"open-science report card"
chip** (the panel is buried behind a METHODS section — the statcheck-inc-141 pattern) + (F4) persisting the audit as a
findings **candidate** (inc 130) for a library-wide "open data not detected" filter + (F2) suppressing the
methods-credit footer on the metadata-only / not-applicable state (uniform across the LMM/meta/statcheck/bayes/
transparency siblings). pytest **963 passed, 1 skipped** (+13 hermetic `tests/test_transparency.py` — full-open
[all present]; exactly-7 + order; a bare repo link trips data availability; each detector not-found + the
silence-≠-certificate wording; registration precondition scoping [non-trial → n/a; registered trial → present;
unregistered trial → not-found]; upon-request present + n/a; no-verdict/no-score; the no-accusatory-language contract;
evidence/basis on a present row; the endpoint 404 + no-chunks 7-all-not-detected honest-empty); `ruff check` + `ruff
format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5). help corpus gained "Auditing transparency
signals" (`HELP-DOCS-SYNCED` → 250); `THIRD-PARTY-NOTICES.md` credits the ODDPub / rtransparent / Nosek-preregistration
manifest. **Credit-the-lineage:** each detector names its source in-context + a one-click ＋add-methods-sources-to-
library. **Headed-verified, no egress** (`.local/visual/drive_inc250_transparency.py` — a seeded open-footer non-trial
paper [data@OSF / code@GitHub / a COI statement / funding; no preregistration; a lab-experiment design]: open METHODS →
**Transparency signals** → the section auto-runs → a **7-row checklist** [**Data availability / Code / COI / Funding ✓
detected** with the ODDPub basis; **Preregistration "not detected"** with the "not detected in the extracted text —
check the paper" wording, no banned/accusatory strings; **registration + "available upon request" "n/a"** — precondition
scoping], the factual tally "4 disclosed · 1 not detected · 2 not applicable · 7 checks", the credit ＋add button, a
present row's evidence opening its page; **0 console/page errors, 0 genai-host requests**). **Rule-#1:** all new files
well under cap (`methods/transparency.py` ~262, `routers/transparency.py` ~53, `08h_methods_transparency.jsx` ~186).
Notes: `INCREMENT-250-NOTES.md`; spec `.claude/docs/specs/2026-07-02-transparency-signals-design.md`; plan
`.claude/backups/plans/2026-07-02_transparency-signals.md`; the track doc
`.claude/docs/future-tracks/chatgpt5.5_future-tracks_integratinglakens.md`. **The live spot-check on real papers is the
maintainer's** (the regex detection + contracts + a seeded round-trip are proven; per-detector precision/recall on real
footers is the first live read). **NEXT within #44:** increment 1b — persist the detected-present disclosures as
**findings-FACTs** (inc 130) + `system:transparency:*` **tags** (the tags↔system-facts cross-cut, #19) + a library-wide
"open data not detected" filter; then increments 2–5 (a `DocumentTextProvider` for JATS/DOCX/HTML full text so the
detectors see the whole paper; a registration-consistency check; a CRediT parser; a reported-vs-registered consistency
registry). Or a fresh track — the standing new-METHODS-auditor candidates are largely done; the maintainer's pick.

Earlier — increment 249 (**meta-analysis reporting auditor** — backlog #36, consumer-side slice:
the statcheck/LMM sibling for published meta-analyses). Brainstormed → Principles-gated → spec'd → planned → built.
**Maintainer fork (AskUserQuestion):** the "Meta-analysis" stub is two different tools — build the **reporting auditor
now** (a METHODS panel, the direct LMM/Bayesian sibling), the **producer-side extraction workbench next** (the
future-track doc's protocol → screening → LLM-drafted-verified-extraction → export; its own REVIEW/SYNTHESIS workspace,
deferred); then **all 7 checks + recommendation-and-explainer scaffolding**. **What it does:** a METHODS
**"Meta-analysis reporting"** panel reads a *published* meta-analysis's extracted text and flags whether it *reports*
seven key methodological choices a reader needs to trust the pooled result — effect-size metric (Borenstein 2009,
Viechtbauer 2010 metafor); model (fixed vs random-effects + estimator; DerSimonian & Laird 1986, IntHout 2014);
heterogeneity (I²/τ²/Q; Higgins et al. 2003); publication-bias assessment (funnel/Egger/trim-and-fill/PET-PEESE; Egger
1997, Duval & Tweedie 2000, Sterne 2011 — the note carries the k≥10 convention); sensitivity/influence (leave-one-out/
outlier diagnostics; Viechtbauer & Cheung 2010); number of studies (k) + participants (PRISMA 2020); and search &
selection reporting (databases/inclusion criteria/PRISMA flow/PROSPERO; PRISMA 2020) — each **present / not-found /
not-applicable**, with the matched evidence opening its **page at region precision**, a grounded cited recommendation,
an always-on literacy explainer, and the in-context `basis`. **The identity boundary is load-bearing:** it **never
pools, models heterogeneity, meta-regresses, computes an effect size, or does bias inference** (metafor/JASP/RevMan
territory) — enforced structurally (there is no statistical-computation code path — no numeric aggregation of study
data) + pinned by `test_no_statistical_computation_import` (the module imports none of numpy/scipy/statsmodels/sklearn/
pandas). **FLAG-not-ADJUDICATE:** no score/verdict/rank (a test asserts no `score`/`grade`; the panel tally is a factual
status *count*, not a grade — #7); search & selection is **precondition-scoped** (n/a for a within-study "mini
meta-analysis" that isn't a systematic review — a flag on every meta-analysis is the failure mode); the publication-bias
k<10 caveat lives in the note, not a suppression (silence≠certificate); "not found" is worded *"not detected in the
extracted text — check the paper"*, never "missing"; never an accusation (A-A veto). **New files/edits:**
`app/backend/methods/metaanalysis.py` (NEW pure — the `_META` gate [a meta-analysis word cue + an analytic cue, so a
paper merely *citing* one doesn't trip] + 7 precondition-scoped checks + `MetaCheck`/`MetaReport` + `audit_meta_analysis`;
self-contained regex helpers, the per-module precedent) + `app/backend/api/routers/metaanalysis.py` (NEW
`GET /papers/{id}/meta-analysis`, sync read-only, mirrors `/lmm`/`/bayes`) + `app/backend/api/app.py` (import + include
after `lmm`) + `app/frontend/js/08g_methods_metaanalysis.jsx` (NEW `MetaSection`/`MetaPaper`/`MetaChecklist`/`MetaCredit`;
`registerPaneSection` order 35, `hideInReadOnly`; auto-runs when its section is open; reuses `.bayes-check-*`/
`.method-credit`/`.lmm-*` — **no new CSS**) + `app/frontend/js/09_placeholders.jsx` (removed the `id:"meta-analysis"`
coming-soon stub — its real feature has landed, the inc-163 convention). **Fully local — no egress, no LLM, no
migration, no new dependency.** **Audit `.claude/security-audits/2026-07-02_metaanalysis-auditor.md` PASS** (local
read-only over the paper in hand; no external fetch/egress/LLM/migration/dependency; the never-computes-statistics
identity boundary structural + test-pinned; flag-not-adjudicate / precondition-scoped / not-found-≠-missing uphold the
no-accusation boundary). **Principles gate (rule #9) — aligned** (PRINCIPLES Example 3 / the statcheck-LMM class; the
misaligned "meta-analysis quality/reproducibility score / this analysis is low-quality" verdict + re-pooling/re-computing
declined). **QA (rule #10)** — new `route_62_methods_metaanalysis.md`; surface **178/178 API + 802/802 FE, 0
uncovered**. **Experience pass (rule #11, deadline-citer persona agent)** — the panel serves the citer once reached (it
already inherits the LMM auditor's factual tally + n/a de-emphasis); the remaining findings are all reception/
cross-cutting → **filed cross-method to #23:** (F1) an on-paper **"report card" chip** ("reports a meta-analysis · report
card →", the statcheck-inc-141 pattern — the shared reception gap: the panel is buried behind a METHODS section) +
(F4) persisting the audit as a findings **candidate** (inc 130) for the library-wide review queue + (F2) suppressing the
methods-credit footer on the explicit not-applicable state (uniform across the LMM/meta/statcheck/bayes siblings; a
small state-lift). pytest **950 passed, 1 skipped** (+12 hermetic `tests/test_metaanalysis.py` — gate off [non-meta /
cite-only] / on; each check present/not-found; publication-bias k≥10 caveat; search precondition scoping [mini-meta →
n/a; systematic-but-unreported → not-found]; not-found-≠-missing wording; no-verdict/no-score; the identity-boundary
static import assert; the endpoint 404 + no-chunks honest-empty); `ruff check` + `ruff format --check` clean; frontend
rebuilt (`test_frontend_assembly` 5/5). help corpus gained "Auditing meta-analysis reporting" (`HELP-DOCS-SYNCED` →
249); `THIRD-PARTY-NOTICES.md` credits the 10-source manifest. **Credit-the-lineage:** each check names its source
in-context + a one-click ＋add-methods-sources-to-library. **Headed-verified, no egress**
(`.local/visual/drive_inc249_metaanalysis.py` — a seeded within-study **mini meta-analysis** [Hedges' g / random-effects
/ I² / a study count reported; no publication bias / no sensitivity analysis; no systematic search]: open METHODS →
**Meta-analysis reporting** → the section auto-runs → a **7-row checklist** [**Effect-size metric ✓ present** with the
Borenstein basis; **Publication-bias assessment "not found"** with the k≥10 caveat + "check the paper" wording, no
"missing"; **Search & selection "n/a"** — a mini-meta], the factual tally "4 reported · 2 not detected · 1 not
applicable · 7 checks", the credit ＋add button, a present row's evidence opening its page; **0 console/page errors, 0
genai-host requests**). **Rule-#1:** all new files well under cap (`methods/metaanalysis.py` ~290, `routers/metaanalysis.py`
~65, `08g_methods_metaanalysis.jsx` ~250). Notes: `INCREMENT-249-NOTES.md`; spec
`.claude/docs/specs/2026-07-02-metaanalysis-auditor-design.md`; plan
`.claude/backups/plans/2026-07-02_metaanalysis-auditor.md`. **The live spot-check on a real published meta-analysis is
the maintainer's** (the math-free regex detection + contracts + a seeded round-trip are proven; per-check precision/
recall on real papers is the first live read). **NEXT (the maintainer's pick):** the **producer-side extraction
workbench** — the full #36 future-track (protocol → screening → LLM-drafted provenance-anchored human-verified
extraction → deterministic effect-size conversion → export to metafor/JASP/RevMan), its own REVIEW/SYNTHESIS workspace +
spec + heavy Principles/A-A pass; or another new-METHODS-auditor candidate; or another future-track.

Earlier — increment 248 (**accordion panels polish** — the maintainer's three next-up UX asks,
all frontend). **(A) Headers always visible** (maintainer chose "open section scrolls internally"): the two accordion
side-panes (`.pane-sidebar`, `.pane-detail`) are now `display:flex; flex-direction:column; overflow:hidden` — they no
longer scroll as a whole (the center `.pane-list` keeps normal scroll); `.pane-accordion` `flex:1; min-height:0`, a
collapsed `.acc-section` `flex:0 0 auto`, the **open** section `flex:0 1 auto` (natural height when short → headers sit
right below it; shrinkable when the pane is full, at which point `.acc-section.open .acc-body{overflow-y:auto}` scrolls
the body internally) — so a long section (Details) never buries the section headers below it (height-agnostic: desktop
100vh + mobile 100%). **(C) Section-body padding:** `.acc-body` gained `padding: 2px 14px 14px` (tokens; matches the
header's 14px) so the 9 previously-flush section bodies (GRIM, statcheck, Cite, citation-concentration/context, Review,
mixed-model, bayesian, meta-analysis) aren't against the resize bar; DETAILS' `.detail-edit-pane` inline padding →
vertical-only (`10px 0 24px`) to avoid doubling. **(B) Cite tabs** (maintainer chose "per-tab hideInReadOnly; keep
'Cite'"): Citation concentration (`08b_methods_citation_equity.jsx`) + How-it's-cited (`08c_methods_citation_context.jsx`)
moved from standalone METHODS sections → **tabs of the THEORY "Cite" section** `[Suggest | Citation concentration | How
it's cited]`. `05_panes.jsx` reworked — `registerPaneSection` now **owns** the section metadata authoritatively
regardless of chunk-load order (08b/08c load before 37_cite, so they only seed a placeholder) + a `tabLabel` option
(Cite's own first tab reads "Suggest"); `registerPaneTab` accepts a per-tab `hideInReadOnly`; `sectionTabs(section,
readOnly)` drops those tabs on a mobile read-only companion + `PaneAccordion` hides a section only when explicitly
hideInReadOnly OR every tab is (Cite keeps **Suggest** read-only, drops the two analysis tabs). **Stale-stub cleanup
(rule #5 + the inc-163 convention):** verification surfaced a **duplicate "Bayesian statistics"** header + a mis-ordered
"Mixed-model reporting" — `09_placeholders.jsx` still had coming-soon stubs whose real panels shipped (`id:"bayesian"`,
real = inc 241 `id:"bayes"`; `id:"lmm"`, real = inc 247, same id → collided; my inc-248 metadata-override would've
mis-ordered the real one). Removed both; META-ANALYSIS (#37, no real feature) + the statcheck "More checks" tab (#27)
stay. **All frontend** — no backend/migration/egress/dependency/endpoint; **no security audit** (a layout + IA move, no
new fetch/data-path); **Principles non-triggering** (no new claim/signal; the moved panels' honesty posture — same
endpoints, signal-not-verdict — is unchanged). **QA (rule #10):** `route_51`/`route_53` prose repointed to the THEORY
Cite tabs, `route_42` notes the tabbed Cite section; coverage keys on the unchanged jsx files → surface **177/177 API +
796/796 FE, 0 uncovered**. **DESIGN.md (rule #8):** recorded the internal-scroll accordion layout + per-tab
hideInReadOnly + section-definer-owns-metadata + `tabLabel`. pytest **938 passed, 1 skipped** (unchanged — inc 248
touched no Python; `test_frontend_assembly` 5/5 confirms the rebuilt `callosum-app.html` is in sync); `ruff check` +
`ruff format --check` clean; frontend rebuilt. help corpus's "Checking citation concentration" + "Seeing how a paper is
cited" now point to the THEORY → Cite tabs (`HELP-DOCS-SYNCED` → 248). **Headed-verified, no egress**
(`.local/visual/drive_inc248_panels.py` at 1440×900: METHODS headers correctly ordered + **no duplicate Bayesian** +
Citation-concentration/How-cited **gone from METHODS**; `.pane-detail` overflow `hidden` + the open `.acc-body`
overflow-y `auto` + the last header within the pane viewport; open GRIM → `.acc-body` padding-left `14px`; open THEORY →
Cite → tab strip `[Suggest | Citation concentration | How it's cited]` + switching to Citation concentration renders its
Run-audit panel; **0 console/page errors, 0 genai-host requests**). **Rule-#1:** all touched files under cap
(`05_panes.jsx` ~115, `25_detail.jsx` ~528, `08b`/`08c` unchanged size, `09_placeholders.jsx` shrank). Notes:
`INCREMENT-248-NOTES.md`. **NEXT (the maintainer's pick):** a fresh track — the standing new-METHODS-auditor candidate
is the LMM auditor's sibling; or the #23 deferrals (discoverability chip F1; persist-as-candidate F4; LLM-assisted
detection SP2); or another future-track (the A-list, B-list, #24, #25, #40 SP1 are all done, #23 shipped).

Earlier — increment 247 (**LMM-reporting completeness auditor** — backlog #23: the statcheck
sibling for linear mixed models). The standing new-METHODS-auditor candidate, brainstormed → Principles-gated →
spec'd → planned → built to the future-track doc's exact **FLAG-not-ADJUDICATE** shape (a near-mirror of the Bayesian
SP2 completeness checklist). Maintainer forks (AskUserQuestion): **all 7 checks** + **"also 'what this means' for
present items"**. **What it does:** a METHODS **"Mixed-model reporting"** panel reads a mixed-model paper's extracted
text and flags whether it *reports* seven things a careful reader needs — random-effects structure (Barr 2013;
Matuschek 2017), df/inference method (Luke 2017), convergence/singular fit (Bates 2015 lme4), estimation REML/ML, ICC,
marginal/conditional R² (Nakagawa & Schielzeth 2013), and (for longitudinal designs with dropout) a missing-data
sensitivity analysis (FDA ICH E9(R1); Troendle 2025; Cro 2020; Moreno-Betancur & Chavance 2016) — each **present /
not-found / not-applicable**, with the matched evidence opening its **page at region precision**, a grounded cited
recommendation, an always-on literacy explainer, and the in-context `basis`. **The identity boundary is load-bearing:**
it **never runs a model, an imputation, or a sensitivity analysis, and never ingests raw data** — enforced structurally
(there is no model-fitting code path) + pinned by `test_no_model_fitting_import`. **FLAG-not-ADJUDICATE:** no
score/verdict/rank (a test asserts no `score`/`grade`; the experience-pass tally is a plain status *count*, not a grade
— #7); ICC + missing-data are **precondition-scoped** (n/a when not applicable — a flag on every LMM is the failure
mode); "not found" is worded *"not detected in the extracted text — check the paper"*, never "missing" (silence≠certificate
#6); never an accusation (A-A veto). **New files/edits:** `app/backend/methods/lmm.py` (NEW pure — the `_LMM` gate + 7
precondition-scoped checks + `LmmCheck`/`LmmReport` + `audit_lmm`; regex over chunk text, self-contained
`_snippet`/`_first`/`_has`) + `app/backend/api/routers/lmm.py` (NEW `GET /papers/{id}/lmm`, sync read-only, mirrors
`/bayes`/`/statcheck`) + `app/backend/api/app.py` (import + `include_router` after the methods cluster) +
`app/frontend/js/08f_methods_lmm.jsx` (NEW `LmmSection`/`LmmPaper`/`LmmChecklist`/`LmmCredit`; `registerPaneSection`
order 33, `hideInReadOnly`; auto-runs when its section is open) + `app/frontend/styles.css` (`.lmm-*`, tokens only;
reuses `.bayes-check-*`/`.method-credit`/`.statcheck-caveat`). **Fully local — no egress, no LLM, no migration, no new
dependency.** **Audit `.claude/security-audits/2026-07-02_lmm-auditor.md` PASS** (local read-only over the paper-in-hand;
no external fetch / egress / LLM / migration / dependency; the never-runs-a-model boundary structural + test-pinned;
flag-not-adjudicate / precondition-scoped / not-found-≠-missing uphold the no-accusation boundary). **Principles gate
(rule #9) — aligned** (PRINCIPLES Example 3 / the Bayesian-SP2 class; the misaligned "reporting-quality score / this
analysis is inadequate" verdict + running-a-model declined). **QA (rule #10)** — new `route_61_methods_lmm.md`; surface
**177/177 API + 796/796 FE, 0 uncovered**. **Experience pass (rule #11, deadline-citer persona agent)** — the panel
serves the citer once reached; fixed-cheap in-increment: a factual status **tally** (reported/not-detected/n-a/checks —
explicitly not a score) + de-emphasized n/a rows; **filed to backlog #23:** (F1) an on-paper discoverability chip
("runs an LMM · report card →", the statcheck-inc-141 pattern — the panel's own reception gap) + (F4) persisting the
audit as a findings candidate (inc 130). pytest **938 passed, 1 skipped** (+14 hermetic `tests/test_lmm.py` — gate
off/on; each check present/not-found; ICC + missing-data precondition scoping [n/a]; not-found-≠-missing wording;
no-verdict/no-score; the identity-boundary static import assert; the endpoint 404 + no-chunks honest-empty); `ruff
check` + `ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5). help corpus gained "Auditing
mixed-model reporting" (`HELP-DOCS-SYNCED` → 247); `THIRD-PARTY-NOTICES.md` credits the check lineage. **Credit-the-
lineage:** each check names its source in-context + a one-click ＋add-methods-sources-to-library. **Headed-verified,
no egress** (`.local/visual/drive_inc247_lmm.py` — a seeded mixed-model paper [random effects/REML/converged/R²
reported, df method NOT, non-longitudinal single-grouping]: open METHODS → **Mixed-model reporting** → the section
auto-runs → a **7-row checklist** [Random-effects ✓ present; df method **not found** with "check the paper" wording;
ICC + missing-data **n/a**], the in-context basis, the credit ＋add button; the tally line + de-emphasized n/a rows;
**0 console/page errors, 0 genai-host requests**). **Rule-#1:** all new files well under cap (`methods/lmm.py` ~290,
`routers/lmm.py` ~65, `08f_methods_lmm.jsx` ~210). Notes: `INCREMENT-247-NOTES.md`; spec
`.claude/docs/specs/2026-07-02-lmm-auditor-design.md`; plan `.claude/backups/plans/2026-07-02_lmm-auditor.md`. **The
live spot-check on a real mixed-model paper is the maintainer's** (the math-free regex detection + contracts + a
seeded round-trip are proven; per-check precision/recall on real papers is the first live read). **NEXT (the
maintainer's pick):** the #23 deferrals (the discoverability chip F1; persist-as-candidate F4; LLM-assisted detection
SP2) — or a fresh track (the A-list, B-list, #24, #25, and #40 SP1 are all done; the LMM auditor #23 is now shipped).

Earlier — increment 246 (PUBLISHERS **"where to submit" SP1b** — the METHODS panel + the
open-science weighting + the first-use choice gate; **completes backlog #40 SP1**). The frontend half of #40 (SP1a =
the backend engine + endpoint, inc 245), built to the future-track **choice-gate** doc's exact shape. **What it is:**
a METHODS **"Where to submit"** panel (`08e_methods_publishers.jsx`, `registerPaneSection` order 34 + `hideInReadOnly`)
— a **Selected paper** OR **Paste abstract + subject** input → the SP1a `/methods/publishers/run` (the 08b run/poll
pattern) → **uniform per-journal profile cards** (fit / OA color / cost [APC + waiver] / license / open impact [+ a
Matthew-bias caveat] / legitimacy chips / `elevated_for`; **each fact links to its source** — journal homepage,
OpenAlex, DOAJ; positive framing). **The first-use choice gate is structural** (the doc's veto lines): the panel
yields **no output** until the user actively sets **both** the open-science weighting **and** the result breadth —
**nothing pre-selected** (`app_settings.publisher_defaults_set()` = both non-None; **Save disabled until both are
chosen**), so the open-science weighting is **one forced choice among peers**, never the lone spotlighted field (the
de-singularization). It fires **once**; thereafter the panel runs inline and the prefs stay editable in **Settings →
Where to submit** + via the **always-visible output weighting thumb** (shows the state inline + adjusts + re-runs —
output legibility is non-negotiable). **The prefs are local + never transmitted** — file-stored (the `contact_email`
posture, not a secret), validated at the `PUT /settings` boundary (weighting 0..1 → 422; breadth `{focused,broad}` →
422; a rejected PUT writes nothing), and they reach **only** the local endpoint as ordering params — **SP1a's
recording-transport test proves the weighting is in no OpenAlex/DOAJ request**. **No SP1a endpoint change** (the panel
reads `GET /settings` + maps breadth → `top_k` client-side). **New files/edits:** `app/backend/app_settings.py`
(`set/stored_publisher_weighting` [float|None], `set/stored_publisher_breadth` [str|None], `publisher_defaults_set()`)
+ `app/backend/api/routers/settings.py` (additive `publisher_weighting`/`publisher_breadth`/`publisher_defaults_set` on
`SettingsStatus`; `set_publisher_*` fields on `SettingsUpdate` + validation; `PUBLISHER_BREADTHS`) +
`app/frontend/js/08e_methods_publishers.jsx` (NEW — `PublishersGate`/`PublishersPanel`/`PubProfileCard`/`PubSegmented`
+ the output thumb) + a `35_settings.jsx` **Where to submit** section (reusing `PubSegmented`/`PUB_WEIGHTS`/
`PUB_BREADTHS` hoisted from 08e) + `app/frontend/styles.css` (`.pub-*`, tokens only — OA-color badges are **neutral
chips** [green = verified is a different semantic]; `elevated_for` uses `--accent-soft`; `legitimacy_absent` is muted
`--ink-3`, never the amber flag; segmented controls reuse `.tags-srcfilter`). **No migration, no new dependency, no
new API endpoint** (additive `/settings` fields). **Audit addendum to `.claude/security-audits/2026-07-01_publishers.md`
PASS** (prefs local + boundary-validated + never transmitted; the gate withholds output, not access; no new fetch/
endpoint/migration/dependency). **Principles + A-A (rule #9)** — the choice-gate doc is the gate output; the vetoes
(no pre-selection, weighting-never-alone, never-transmitted, PUBLISHERS-scoped, output legibility) are honored
structurally. **QA (rule #10)** — `route_60_publishers.md` gained the `fe:` panel claim + the first-use-gate /
output-legibility / no-composite-shown assertions; surface **176/176 API + 790/790 FE, 0 uncovered**. pytest **924
passed, 1 skipped** (+2 hermetic `tests/test_settings.py` — the gate is satisfied only when BOTH prefs are set [not
one]; validation: weighting 0..1 + breadth allowlist → 422, a rejected PUT writes nothing); `ruff check` + `ruff
format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5). help corpus gained "Where to submit (choosing
a journal)" (`HELP-DOCS-SYNCED` → 246). **Headed-verified, no egress** (`.local/visual/drive_inc246_publishers.py` —
in-process fake OpenAlex/DOAJ + a fake embed model, isolated settings store: open METHODS → **Where to submit** → the
gate shows **two segmented controls with nothing pre-selected + Save disabled**; picking only one keeps Save disabled
[de-singularization]; picking both → Save → the gate is gone → **Paste an abstract** + subject → **Find journals** →
**2 profile cards incl. the closed journal** + the output weighting thumb; **no "predatory" text; 0 external [sensitive-
host] requests; 0 console/page errors**). **Rule-#1:** `08e_methods_publishers.jsx` ~250, `35_settings.jsx` ~600 (a
watch item — re-measure before the next addition), `routers/settings.py` ~230 — all under cap. **The live OpenAlex
`/sources` + DOAJ round-trip from the panel is the maintainer's spot-check** (needs network; the flow + contracts are
hermetically + headed-proven). Notes: `INCREMENT-246-NOTES.md`. **This completes backlog #40 SP1** (SP1a engine inc
245 + SP1b UI inc 246). **Deferred within #40 (no data source yet):** green-route / TOP-factor / regional-index
(AJOL/SciELO/Redalyc/Latindex) legitimacy signals; user exclusion/filtering; thumb auditability; a real *field*
self-citation baseline. **NEXT (the maintainer's pick):** a fresh track — the standing new-METHODS-auditor candidate
is the **LMM-reporting auditor** (#23); or another future-track (the A-list, B-list, #24, #25, and #40 SP1 are all
done).

Earlier — increment 245 (PUBLISHERS **"where to submit" journal-finder** — backlog #40 SP1a: the
backend engine + endpoint; the graduation of the deliberately-controversial future-track, gated through Principles +
A-A at graduation and built to the exact shape its two future-track docs worked out). Maintainer scope (AskUserQuestion):
**full principled core · OpenAlex + DOAJ · both inputs** (a library-paper picker OR a pasted abstract). **What it does:**
from an abstract, derive a candidate-journal pool **from a topic** (never the abstract), enrich each journal's facts
(OpenAlex `/sources` + DOAJ), embed the abstract **locally** (SPECTER), and return a **uniform, fully-sourced factual
profile** per journal — fit / OA color / APC+waiver / license / DOAJ Seal / open impact — ranked by fit, optionally
re-ordered by an open-science `weighting` (0.0 = fit-only). **The load-bearing constraint — the abstract never leaves
the machine:** the candidate pool is seeded from a **topic** (a library paper's OpenAlex `primary_topic`, or an OpenAlex
`/topics?search=<subject>` resolution of a user-typed subject keyword — a coarse public term, *not* the abstract); the
abstract is embedded **locally** and only re-ranks the pool. Only topic ids / a subject keyword / source ids / ISSNs
leave (public bibliographic metadata — the inc-183/227 posture, **NOT** the Gemini library-text gate). **New files:**
`integrations/openalex/sources.py` (`OpenAlexSourcesClient` — `fetch_topic_for_subject` / `fetch_candidate_sources`
[`/works?filter=primary_topic.id:<T>&select=primary_location`, aggregate distinct `primary_location.source` by
frequency] / `fetch_source_details` [batch `/sources?filter=openalex_id:S1|S2|…`, ≤50/call]; injectable fetcher,
`api_cache.py`, `resolved_mailto`, fail-closed; every id `^T\d+$`/`^S\d+$`-validated **before** any request → no SSRF)
+ `integrations/doaj/journals.py` (`DoajJournalsClient.fetch_journal(issn)` → APC amount+currency, waiver, license
family, Seal, subjects, keywords; ISSN `^\d{4}-\d{3}[\dX]$`-validated; optional `CALLOSUM_DOAJ_API_KEY` write-only) +
`methods/publishers.py` (pure — `JournalProfile`/`PublishersReport`, `derive_oa_color` [diamond/gold/oa-other/closed],
`build_profiles` = local unit-cosine fit [the `overlooked_work.py::rank_overlooked` mechanics] + an **internal** openness
ordering key that re-orders but is **never displayed** + `elevated_for` goods shown only when weighting>0) + async
`routers/publishers.py` (`POST/GET /methods/publishers/run`; paper_id XOR abstract+subject → 422 on ambiguous/missing/
no-DOI, 404 on missing paper/unknown job; `_publishers_model` = injected `embedding_model` wins else cached SPECTER) +
`app.py` wiring (`create_app(openalex_sources_client=, doaj_journals_client=)` injection + `api.state.publishers_jobs`
+ `include_router` before papers). **The Principles/A-A vetoes are structural + test-pinned:** **no composite score**
(the response has no `*score*` key — a test asserts it; the shown rationale is `elevated_for` + the raw facts), **no
"predatory" label** (no such field/string), **every candidate appears** incl. closed journals (gate the boost, not the
listing), **elevate-don't-denigrate** (absence of a legitimacy signal is a neutral `legitimacy_absent` fact, never a
flag; the deferred sources — COPE/OASPA, PubMed/Scopus, AJOL/SciELO/Redalyc/Latindex, self-archiving/TOP — are named
honestly per silence≠certificate). **Legitimacy SP1 subset** = DOAJ inclusion + DOAJ Seal. Egress = public
bibliographic metadata, cached + fail-closed, **NOT** the Gemini gate. **No migration, no new dependency** (SPECTER
rides the existing sentence-transformers stack — a ~440 MB first-use model download, like MiniLM/overlooked-work; httpx
already present). **Audit `.claude/security-audits/2026-07-01_publishers.md` PASS** (SSRF closed; abstract never
transmitted [recording-transport test]; egress = public metadata; fail-closed + bounded; no dependency/migration).
**Principles + A-A (rule #9)** — the future-track docs are the gate output; the vetoes are encoded as acceptance-criteria
tests. **QA (rule #10)** — new `route_60_publishers.md` (`api: /methods/publishers*` + the honesty assertions; the `fe:`
panel claim lands in SP1b); surface **176/176 API + 771/771 FE, 0 uncovered**. pytest **922 passed, 1 skipped** (+13
hermetic `tests/test_publishers.py` — fake OpenAlex/DOAJ fetchers + a fake deterministic keyword embed model, no
network/model download: topic resolution [subject→T-id; paper→primary_topic]; candidate aggregation + id validation;
source-details parse; DOAJ merge [OA journal gains APC/waiver/Seal/license; a **closed** journal shows OpenAlex facts
only + still appears]; `derive_oa_color`; `build_profiles` fit-orders at weighting 0, weighting>0 re-orders to elevate
diamond/Seal with `elevated_for`; no-composite/no-predatory; endpoint 202→poll→done + 422 [both-inputs / neither] +
404; **the abstract appears in no outbound request** via a recording transport). `ruff check` + `ruff format --check`
clean; **no frontend build** (SP1a is backend-only; `test_frontend_assembly` unaffected). **Rule-#1:** all new files
well under 600 (`methods/publishers.py`, `routers/publishers.py`, `integrations/openalex/sources.py`,
`integrations/doaj/journals.py`). help corpus **deferred to SP1b** (no usable UI yet — honest; `HELP-DOCS-SYNCED` stays
at 243). **The live OpenAlex `/sources` + DOAJ round-trip is the maintainer's spot-check** (needs network; the mapping
+ contracts + the endpoint round-trip are hermetically proven). Notes: `INCREMENT-245-NOTES.md`; plan
`.claude/backups/plans/2026-07-01_publishers-where-to-submit-sp1a.md` (see below). **NEXT — SP1b:** the METHODS
**"Where to submit"** panel (`08e_methods_publishers.jsx`, `registerPaneSection` + `hideInReadOnly`): a paper-picker OR
abstract+subject input → the async run/poll → the uniform per-journal profile cards (each fact links to its source;
positive framing) + a visible **open-science weighting** slider (re-runs on change, always shows its state inline) +
the **first-use no-pre-selected-default choice gate** (local `app_settings` `publisher_weighting`/`publisher_sort`/
`publisher_defaults_set`, never transmitted; force the weighting AND ≥1 other publisher default together so the
weighting isn't the lone forced choice; PUBLISHERS-scoped); audit addendum (settings never transmitted); help corpus
"Where to submit"; headed-verified. Deferred within #40 (no data source yet): green-route / TOP-factor / regional-index
legitimacy signals; user exclusion/filtering.

Earlier — increment 244 (Bayesian auditor SP4 — **Tier-3 textual-coherence advisory prompts**;
**FULLY CLOSES future-track #24**). The last of the "build all three" threads the maintainer chose to close #24 out.
Two conservatively-gated **advisory** prompts (the future-track doc's **Stage 3**, never flags/verdicts) added to the
`completeness` block of the existing `GET /papers/{paper_id}/bayes` (`methods/bayes.py::_advisory_notes` + an additive
`advisories` list): **credible-vs-confidence** — a Bayesian paper that mentions a "confidence interval" but never a
"credible interval" (→ verify a *credible* interval wasn't intended; a common Bayesian/frequentist conflation) — and
**BF-direction** — a `BF01` reported near a claim of support for the alternative (→ BF01 quantifies evidence for the
*null*, so verify the direction/label). **The honesty is the whole point** (advisory flags are the riskiest thing in
the auditor): they are **clearly demarcated** from the Tier-1/Tier-2 signals — a separate panel block with a **neutral
`--accent-soft` tint (NOT the amber flag)**, headed **"Advisory — requires expert judgment"**, worded as **exploratory
prompts** ("verify whether…", "a common conflation", "exploratory prompts, not verdicts") — **never a flag or verdict**
(#2 signal-not-verdict; the A-A no-accusation veto). **Conservatively gated** (the doc's explicit prefer-false-negatives
guidance): they run **only on a Bayesian paper** (the `_BAYESIAN` gate); credible-vs-confidence is **suppressed** if the
paper also says "credible interval" (assume it distinguishes them); BF-direction fires only on the *specific* `BF01`
within ±120 chars of an "alternative-support" phrase — one is enough (advisory, not an exhaustive scan). A non-Bayesian
paper → `advisories: []`. **Fully local — no egress, no LLM, no migration, no new dependency** (literal/anchored
regexes, no catastrophic backtracking); rides the existing endpoint additively (**no new API surface**). **Principles
gate (rule #9) run — aligned** (built to the doc's Stage-3 advisory-not-verdict prescription; the maintainer's strong
no-false-positive stance honored by the conservative gating + prompt-not-verdict wording + visual separation).
**Audit addendum 3 to `.claude/security-audits/2026-07-01_bayes-auditor.md` PASS** (additive read-only field;
literal/anchored regexes; Bayesian-gated / conservative / advisory-not-verdict controls uphold the no-accusation
boundary; local/bounded/no-egress/no-dependency). pytest **909 passed, 1 skipped** (+5 hermetic `tests/test_bayes.py`,
no network/model: credible-vs-confidence fires [confidence, no credible] / **suppressed** when both interval types
appear; BF-direction fires [BF01 near "supported the alternative"]; **none** for a clean Bayesian paper; **none** for a
non-Bayesian paper; + the endpoint `advisories` field + the empty-completeness dict). `ruff check` + `ruff format
--check` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 174/174 API + 771/771 FE, 0 uncovered**
(`route_59_methods_bayes.md` extended — the advisory block rides the existing endpoint + panel). help corpus unchanged
(the advisory prompts are self-describing UI; the "Checking Bayes factors" section already frames the auditor as
signal-not-verdict; `HELP-DOCS-SYNCED` stays at 243). **Headed-verified, no egress**
(`.local/visual/drive_inc244_advisory.py` — a seeded Bayesian paper with both triggers: open METHODS → **Bayesian
statistics** → the recompute + checklist render AND an **Advisory** block shows **2** prompts under **"ADVISORY —
REQUIRES EXPERT JUDGMENT"**, worded as prompts ("verify…", "not verdicts"), with a **neutral left-border, not the amber
flag**; 0 console/page errors, 0 genai-host requests). **Rule-#1:** `methods/bayes.py` **506**, `routers/methods.py`
**583**, `js/08d_methods_bayes.jsx` **204** — all under cap. Notes: `INCREMENT-244-NOTES.md`. **This FULLY CLOSES
future-track #24 — the Bayesian auditor is complete** (SP1 t-test recompute 241 · SP2 completeness checklist 242 · SP3
Pearson-correlation recompute 243 · SP4 advisory prompts 244). ANOVA / regression BFs remain a **documented deferral**
(not faithfully recomputable/verifiable from F + df alone — inc 243 audit addendum 2), pending a trusted anchor (R
BayesFactor). **NEXT (a fresh track — the maintainer's pick):** the standing new-METHODS-auditor candidate is the
**LMM-reporting auditor** (#23); or another future-track (the tree's A-list + B-list + #24/#25 are all done).

Earlier — increment 243 (Bayesian auditor SP3 — the **Pearson-correlation recompute** [Ly et al.
2016], verified exactly against pingouin; **ANOVA/regression declined as a documented finding**; the "more designs"
close-out of future-track #24). The maintainer asked to **close #24 out** and (AskUserQuestion) chose **"build all
three"** remaining threads. **Correlation (built + verified):** `run_bayes` now also recognizes an inline `r(df) = …,
BF10 = …` (APA, n = df+2) and recomputes the **default correlation Bayes factor** — `methods/bayes.py::corr_bf10`,
the exact **Ly, Verhagen & Wagenmakers (2016)** / Wetzels & Wagenmakers (2012, eq. 25) closed form via the Gaussian
hypergeometric `scipy.special.hyp2f1` (stretched-beta prior κ = 1). **No new dependency** — scipy is already an
explicit dep. **Verified EXACTLY against `pingouin.bayesfactor_pearson`** (the `ly` method — the same formula JASP +
the BayesFactor R package use) at 7 anchors incl. negative r: (0.6,20)=10.634, (0.5,30)=9.904, (0.3,50)=1.5555,
(0.0,40)=0.19693, (0.8,25)=12721, (0.42,60)=37.389, (−0.5,30)=9.904; pingouin is a **dev-only verification tool** (its
anchor values baked into `tests/test_bayes.py`), **not a runtime dependency** — the SP1 t-test-anchor posture.
**Extraction:** a new `_RSTAT` matches `r(df) = value` (leading-dot + negative r); `_scan_text` now collects **both**
t-test and correlation statistics and checks each BF against whichever is **nearest within the window**, branching on
type. A correlation `r(df)` is **unambiguous** (n = df+2, a single recompute, `matched_design="correlation"`) — no
paired/two-sample fork. The response gains an additive `computed_correlation`; the panel shows `recomputed …
(correlation)`; the `＋ add to library` credit now adds **both** source papers (Rouder 2009 + Ly 2016). **ANOVA /
regression — declined as a FINDING, not shipped:** the default Bayesian ANOVA/regression BF is **not faithfully
recomputable from `F(df1, df2)` + N alone** (it depends on the design — balance, cell sizes, the g-prior structure)
and there is **no in-env anchor** (pingouin has no ANOVA BF; no R BayesFactor). A candidate g-prior/R² recompute was
tested against the **only** available check — the J=2 → two-sample-t reduction against the *already-verified*
`jzs_bf10` — and it **did not reduce** (ratios 0.63 → 0.52, not 1.0), confirming an incorrect/unverifiable form.
Shipping an unverified statistical recompute would produce **false "couldn't reproduce" flags** — precisely the
accusation the whole design forbids (rule #2: no "done" without verification; the A-A no-accusation veto). Per the
charter, **a feature that cannot be built to honor the principles is a finding about the feature, not a reason to relax
them** — so ANOVA/regression is deferred until a trusted anchor exists (R BayesFactor / a Rouder-2012 quadrature
validated against it). The panel + docstring state this coverage limit honestly (silence≠certificate #6). **The
fuzzier textual-coherence advisory flags (credible-vs-confidence mislabel, BF-direction) are inc 244.** **Fully local
— no egress, no LLM, no migration, no new dependency**; rides the existing `GET /papers/{paper_id}/bayes` additively
(no new API surface). **Principles gate (rule #9) run — aligned** (a deterministic per-paper signal carrying its
evidence, the statcheck/SP1 class; the ANOVA decline is itself the aligned move — honoring #2 signal-not-verdict, #6
silence-≠-certificate, and the A-A no-accusation veto over shipping an unverified recompute). **Audit addendum 2 to
`.claude/security-audits/2026-07-01_bayes-auditor.md` PASS** (additive read-only field; verified recompute [exact
pingouin anchor]; local/bounded/no-egress/no-dependency; ANOVA correctly declined as an unverifiable/false-flag risk).
pytest **904 passed, 1 skipped** (+5 hermetic `tests/test_bayes.py`, no network/model: `corr_bf10` pingouin anchors +
degenerate [|r|>1 / n<3] → None; `run_bayes` correlation reproduce [r(58)=.42, BF10=37.4 → 37.39 (correlation)] /
gross-mismatch→flagged / leading-dot + negative r / the nearest-statistic-wins branch [a far t + an adjacent r →
correlation]); `ruff check` + `ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA
surface 174/174 API + 769/769 FE, 0 uncovered** (`route_59_methods_bayes.md` extended — correlation ride the existing
endpoint + panel). help corpus's "Checking Bayes factors" now covers correlation + the ANOVA-not-recoverable caveat +
credits Ly et al. 2016; `THIRD-PARTY-NOTICES.md` credits Ly 2016 / Wetzels 2012 (`HELP-DOCS-SYNCED` → 243).
**Headed-verified, no egress** (`.local/visual/drive_inc243_correlation.py` — seed a paper + a chunk with `r(58) = .42,
BF10 = 37.4`: open METHODS → **Bayesian statistics** → the section auto-runs → **"1 checked · 0 couldn't reproduce"** +
one row **"reported BF₁₀ = 37.4 · recomputed 37.3886 (correlation)"** with a green "reproduces" pill → **＋ add to
library** lands **both** Rouder et al. 2009 + Ly et al. 2016; 0 console/page errors, 0 genai-host requests).
**Rule-#1:** `methods/bayes.py` **444**, `routers/methods.py` **570**, `js/08d_methods_bayes.jsx` **181** — all under
cap. Notes: `INCREMENT-243-NOTES.md`. **NEXT — inc 244:** the fuzzier **textual-coherence** advisory flags
(credible-vs-confidence mislabel, BF-direction error) as clearly-demarcated Tier-3 *advisory* annotations (the doc's
Stage 3) — the last remaining #24 thread. Then #24 is fully closed (SP1 t-test recompute 241 · SP2 checklist 242 ·
SP3 correlation 243 · SP4 advisory flags 244; ANOVA/regression a documented deferral).

Earlier — increment 242 (Bayesian auditor SP2 — a Tier-2 **BARG/WAMBS/JASP reporting checklist**;
completes future-track #24; brainstormed → fork → Principles gate → built inline). The completeness half of the
Bayesian auditor, on the SP1 endpoint. Via AskUserQuestion the maintainer picked the **BARG/WAMBS core** — three
presence/absence items over the riskier "core + textual-coherence" path: **(1) prior stated** (family/scale; "default
priors" with no scale → present-but-under-specified — the BARG point), **(2) convergence diagnostics** (R-hat / ESS /
divergent transitions), **(3) prior sensitivity / robustness analysis** — each keyed to the published guidelines
(BARG — Kruschke 2021; WAMBS — Depaoli & van de Schoot 2017; the JASP guidelines — van Doorn et al. 2021). **The
load-bearing honesty controls (the future-track doc's own warnings, made structural):** the checklist **runs only on a
paper detectably doing Bayesian analysis** (BF / Bayesian / posterior / credible-interval / MCMC-Stan-brms-JAGS
keywords — else no checklist; a non-Bayesian paper cannot "fail" it); **convergence is `not-applicable`** when no
MCMC/sampler is reported (a closed-form default BF has no chains to diagnose → it is *not* "missing"); **"not found" is
worded "not detected in the extracted text — check the paper"** (statcheck can't read tables — silence≠certificate
cuts both ways; #6), **never "missing" / an accusation** (the A-A veto); a distinct **coherence flag** fires only when
a *reported* diagnostic breaches a **conservative** convention — R-hat > 1.1, ESS < 400, > 0 divergent transitions —
preferring false negatives (the doc's explicit guidance) and citing the thresholds as **conventions, not laws**. **The
surface:** the **same `GET /papers/{paper_id}/bayes`** gains an additive `completeness` block (`is_bayesian` + per-item
`{key, label, status, evidence, page, note}`) computed by `methods/bayes.py::audit_completeness` — one fetch drives
both the SP1 recompute rows and the checklist; the panel `08d_methods_bayes.jsx` gains a **Reporting checklist**
section below the recompute (per-item ✓present / not-found / n/a / ⚠check pills, the **matched evidence snippet**
opening its page at **region precision**, the BARG/WAMBS/JASP credit + the "presence/absence in the text, never a
verdict" caveat). A Bayesian paper with no *inline* default BFs still gets the checklist (the recompute part shows a
"no inline BFs to recompute" note). **Fully local — no egress, no LLM, no migration, no new dependency**
(bounded anchored regexes, no catastrophic backtracking). **Principles gate (rule #9) run — aligned** (the
presence/absence-checklist class + PRINCIPLES Example 3: evidence-carrying flags keyed to guidelines; #2 signal-not-
verdict, #4 evidence-shown, #6 silence-≠-certificate, #7 no-composite; the misaligned "Bayesian reproducibility score
/ this paper failed the checklist" verdict declined, and the fuzzier **textual-coherence** flags [credible-vs-confidence
mislabel, BF-direction] deferred per the doc's prefer-false-negatives guidance). **Audit addendum to
`.claude/security-audits/2026-07-01_bayes-auditor.md` PASS** (additive read-only response field; bounded regexes; the
Bayesian-gated / convergence-n/a / not-found-≠-missing / conventions-not-laws controls uphold the no-accusation
boundary; local, no egress/dependency). pytest **899 passed, 1 skipped** (+5 hermetic `tests/test_bayes.py`, no
network/model: gated-on-Bayesian [a non-Bayesian paper → `is_bayesian:false`, no items]; a closed-form BF paper →
prior present [Cauchy] / convergence **n/a** [no MCMC] / sensitivity not-found; an MCMC paper with R-hat = 1.21 →
convergence **coherence-flag** with the value + convention in the note + sensitivity present; "default priors" →
present-**under-specified**; good MCMC diagnostics → present; the endpoint returns the `completeness` block +
metadata-only → `is_bayesian:false`); `ruff check` + `ruff format --check` clean; frontend rebuilt
(`test_frontend_assembly` 5/5); **QA surface 174/174 API + 769/769 FE, 0 uncovered** (`route_59_methods_bayes.md`
extended). help corpus's "Checking Bayes factors" gained the reporting-checklist paragraph (`HELP-DOCS-SYNCED` → 242).
**Headed-verified, no egress** (`.local/visual/drive_inc242_bayes_completeness.py` — a seeded Bayesian paired t-test
[Cauchy prior + an inline BF, no MCMC, no sensitivity analysis]: open METHODS → **Bayesian statistics** → the section
auto-runs → the recompute reproduces AND the **Reporting checklist** shows [**Prior stated → ✓ present**, **Convergence
→ n/a**, **Sensitivity → not found**] + the BARG/WAMBS/JASP credit; the prior's evidence snippet opens its page at
region precision; 0 console/page errors, 0 genai-host requests). **Rule-#1:** `methods/bayes.py` **350**,
`routers/methods.py` **566**, `js/08d_methods_bayes.jsx` **167** — all under cap. Notes: `INCREMENT-242-NOTES.md`.
**This completes future-track #24 (SP1 inc 241 recompute + SP2 inc 242 checklist).** **NEXT — SP2's own deferred:**
correlation / ANOVA default BFs (Tier-1 recompute for more designs) + the fuzzier **textual-coherence** flags
(credible-vs-confidence mislabel, BF-direction error) as **advisory** annotations. Other new-auditor candidate: the
**LMM-reporting auditor** (#23).

Earlier — increment 241 (Bayesian auditor SP1 — recompute default **JZS Bayes factors**, the
deterministic statcheck sibling; future-track #24; brainstormed → forks → Principles gate → built inline). With the
whole competitive-benchmark A-list and B-list done, the maintainer picked a new **METHODS auditor** from the
longer-horizon tracks, then (AskUserQuestion) the **Bayesian auditor** (over the LMM-reporting one — for its genuine
deterministic recompute) with **SP1 = the recompute only** (the Tier-2 completeness checklist deferred to SP2). **What
it is:** for a paper that reports **default Bayes factors** for t-tests inline (`t(df) = …, BF10 = …`), it recomputes
the **default JZS BF** (Rouder, Speckman, Sun, Morey & Iverson, 2009) from the reported `t` + `df` and flags where the
reported value doesn't reproduce — the truest statcheck analogue (a deterministic, verifiable core). **The math** —
`methods/bayes.py::jzs_bf10(t, n, df)` is the Rouder 2009 closed form via **`scipy.integrate.quad`** over the Cauchy
prior; **verified against the published/pingouin anchor** (two-sample t=3.5, n_eff=10, df=38 → **26.744** vs pingouin's
26.743) + monotonicity sanity (t≈0 → BF<1, large t → BF≫1). **No new dependency** (scipy is already an explicit dep —
statcheck uses `scipy.stats`). **The load-bearing honesty design:** a bare `t(df)` doesn't reveal the design
(one-sample/paired [n = df+1] vs two-sample [needs the group sizes]), and the reported BF was computed under the
*authors'* prior — so the recompute is honest about **both** unknowns: it recomputes under the **default JZS prior**
(Cauchy scale r ≈ 0.707), under **both** the paired and the two-sample-equal-groups interpretations, and marks a BF
**reproduced if it matches EITHER within a factor of ~2** (`LOG10_TOLERANCE = 0.3`) — **erring toward "reproduced," the
non-accusatory direction** (statcheck's one-tailed-leniency principle); only a BF matching *neither* is flagged, and a
mismatch is framed **"couldn't reproduce under the default prior"**, never "wrong" or "p-hacked" (the A-A no-accusation
veto, honored structurally — no composite score, no per-author aggregate). **Extraction** anchors an inline
`BF10/BF01/BF = value` (with optional scientific notation; BF01 inverted to BF10) to the **nearest `t(df)` within a
character window** — a BF with no adjacent t-stat is **not-checkable** (counted invisible, never a guessed design;
silence≠certificate). **`GET /papers/{paper_id}/bayes`** (sync, read-only; mirrors `/statcheck` — reuses
`get_chunks_for_paper`/`get_paper`; **404** unknown, no-chunks → `checked:0` honest-empty; the additive `prior_scale`
is shown for inspectability) + a METHODS panel **`08d_methods_bayes.jsx`** (`registerPaneSection` order **32**,
`hideInReadOnly` — right after Statistics check; **auto-runs when its section is the open one**, the statcheck pattern;
per-BF rows show `reported BF₁₀ = …` + `recomputed … (paired|two-sample)` + a reproduce/couldn't-reproduce pill, each
routing to its **page at region precision** — page-open, never a fabricated exact rect; the default-prior + inline-only
caveats; a Rouder-et-al. credit block with a one-click **＋ add to library**). **Fully local — no egress, no LLM, no
migration** (an ephemeral job result, like statcheck/p-curve/GRIM). **Principles gate (rule #9) run — aligned** (the
statcheck / p-curve / GRIM class + PRINCIPLES Example 3: a deterministic per-paper signal carrying its evidence — the
verbatim match, the recomputed value, the assumed prior, the page; #2 signal-not-verdict, #4 evidence-shown, #6
silence-≠-certificate, #7 no-composite; the misaligned "Bayesian reproducibility score / pass-fail verdict / teaching
BF>3=significant" paths declined). **Audit `.claude/security-audits/2026-07-01_bayes-auditor.md` PASS** (local
read-only; the only input is a path int + the paper's own text; bounded `MAX_RESULTS=500` + wrapped parses → fail-closed;
no SQL written [reads via the audited repo]; no SSRF/egress/secret; no new dependency; coordinate honesty preserved).
**Credit-the-lineage:** Rouder et al. 2009 + the **BayesFactor** R package (Morey & Rouder) + Daniël Lakens'
automated-review catalog credited in `THIRD-PARTY-NOTICES.md` + one-click library-addable from the panel. pytest
**894 passed, 1 skipped** (+10 hermetic `tests/test_bayes.py`, no network/model: the JZS two-sample anchor +
monotonicity/degenerate-df→None; `_normalize_bf10` [bare-BF, BF01-inverts, non-positive→None]; `run_bayes`
extract-and-reproduce [paired] / two-sample / gross-mismatch→flagged / scientific-notation + BF01 / a BF with no
adjacent t → not-checked / no-BF-text → 0; the endpoint reproduces + page + `prior_scale`, no-chunks→checked:0, 404);
`ruff check` + `ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 174/174 API +
767/767 FE, 0 uncovered** (new `route_59_methods_bayes.md`); help corpus gained "Checking Bayes factors (the Bayesian
auditor)" (`HELP-DOCS-SYNCED` → 241). **Headed-verified, no egress** (`.local/visual/drive_inc241_bayes.py` — seed a
paper + a chunk with `t(19) = 2.53, BF10 = 2.9`: open METHODS → **Bayesian statistics** → the section auto-runs →
**"1 checked · 0 couldn't reproduce"** + one row **"reported BF₁₀ = 2.9 · recomputed 2.8452 (paired)"** with a green
"reproduces" pill + the default-prior caveat → **＋ add to library** lands the Rouder et al. paper; 0 console/page
errors, 0 genai-host requests). **Rule-#1:** `routers/methods.py` **542**, `js/08d_methods_bayes.jsx` **132**,
`methods/bayes.py` **184** — all under cap. Notes: `INCREMENT-241-NOTES.md`; specs referenced
`.claude/docs/future-tracks/opus4.8_future-tracks_bayesianauditing.md`. **The live spot-check on a real Bayesian paper
is the maintainer's** (needs a paper reporting an inline t-test BF; the math + contracts + a seeded round-trip are
proven). **NEXT — SP2 (deferred):** the Tier-2 **completeness checklist** (prior stated? convergence diagnostics
[R-hat/ESS]? a sensitivity/robustness analysis? — presence/absence flags, never a verdict; BARG/WAMBS) + more designs
(correlation / ANOVA default BFs). Other new METHODS-auditor candidate: the **LMM-reporting auditor** (#23).

Earlier — increment 240 (touch-native **highlighting on mobile** — the last B5 nicety;
brainstormed → forks → built inline). The reader's companion to the inc-239 mobile reader: **create highlights by
touch.** **The gap:** on desktop the color-picker pill is triggered by `mouseup`, which never fires on touch — so
after a long-press text selection on a phone the pill never appeared; everything downstream (the bbox-mapping,
`POST /papers/{id}/annotations`, the note editor, recolor) already works. **The fix (minimal):** a **mobile-only**
`useTouchSelectionPicker` hook (`js/30f_pdf_gestures.jsx`) watches `document.selectionchange` (debounced 350ms past
the drag) and calls the **same** `onPagesMouseUp` builder the desktop mouseup path uses — it reads
`window.getSelection()` → client-rects → bboxes → the `picker` state (or clears it if the selection collapsed).
`onPagesMouseUp` is a stable `useCallback` (deps `[]`), so the once-attached listener never re-attaches. **Maintainer
forks (AskUserQuestion):** the **contextual pill** (reuse the existing floating picker near the selection, not a
toolbar button — matches desktop + the iOS selection menu) + the **swatch row** (pick the color as you create, like
desktop; the pill also carries the "＋ note" action) — so the entire create/color/note flow is reused *verbatim*. The
only CSS is `.app.mobile` finger-sizing the swatches (18→28px) + the note button (rule #8; DESIGN.md updated). It sits
cleanly inside the inc-239 touch model — the pinch listener only `preventDefault`s **two**-finger moves (single-finger
selection is untouched), and `touch-action: pan-x pan-y` on `.pdf-scroll` governs pan/zoom, not text selection.
**Rule-#1:** `30_viewer.jsx` **577** (the hook lives in 30f, +1 call site); `30f_pdf_gestures.jsx` **79** — both under
cap. **Frontend-only** — **no new endpoint/flow/migration/new-dependency/egress** (reuses the already-audited
annotation-create path), so **no audit/Principles trigger** (a highlight is user-authored data — no claim/signal;
coordinate honesty #2 unchanged — the identical bbox-mapping; desktop is byte-for-byte unchanged, the hook is
`mobile`-gated). pytest **884 passed, 1 skipped** (frontend-only; `test_frontend_assembly` 5/5 confirms the build is in
sync); `ruff check` + `ruff format --check` clean (no Python changed); **QA surface 173/173 API + 761/761 FE, 0
uncovered** (the picker + hook ride `route_32_viewer_annotations.md`; no new API surface). **Headed-verified at
390×844, 0 console/page errors** (`.local/visual/drive_inc240_touchhighlight.py` — open the PDF → create a text
selection via the DOM Selection API [which fires the same `selectionchange` a long-press does] → **the picker pill
appears with 5 color swatches, the +note action, and 28px finger-sized swatches** → tap a swatch → **1 annotation
POST + the highlight renders on the page + the picker closes**). *(Real long-press selection isn't scriptable in
Playwright, so the driver drives the identical `selectionchange` → create path programmatically; the long-press
gesture that produces the selection is the browser's, unchanged.)* Notes: `INCREMENT-240-NOTES.md`. **This builds the
last B5 nicety — B5 is fully complete with nothing deferred, and B1–B5 are all done.**

Earlier — increment 239 (B5 SP3 — **the mobile PDF reader** — the deferred B5 slice; brainstormed →
forks → built inline). A phone-native reading experience. **Maintainer forks (AskUserQuestion):** a **"← Synthesis"
back pill** (the read→check→read loop) + **core + pinch-to-zoom**. **The half already built (the grounding win):** the
PDF viewer *already* had a fit-to-width mode (`pageView: "page"|"width"|"two"`, re-fits on resize) — it just defaulted
to `"page"` (manual zoom), which overflows a phone; and the exact-highlight overlays are already screen-agnostic (%
of page dims, inc 34), so synthesis→PDF highlights already land on any screen. So the reader is mostly three moves:
**(1) fit-width by default on mobile** — `mobile` threaded 40_app → `LibraryFrame` (30c_frame) → `PdfViewer`
(30_viewer); `pageView` inits to `"width"` when mobile, and **Two-up is hidden** (nonsensical on a phone). **(2)
pinch-to-zoom** (`usePinchZoom`, new `js/30f_pdf_gestures.jsx`): during a two-finger gesture apply a cheap CSS
`transform: scale()` to `.pdf-pages` (no per-move re-render), then on release **commit the final scale** (`setScale`
→ a crisp re-render through the inc-34 single-scale pipeline) + drop out of fit mode; a native `{passive:false}`
touch listener `preventDefault`s the 2-finger move (so the browser doesn't also scroll/zoom mid-pinch), and
`touch-action: pan-x pan-y` on `.pdf-scroll` (mobile) disables the browser's own pinch-zoom while keeping single-finger
pan. A `scaleRef` mirrors the current scale for the once-attached listener. **(3) the navigation** — the exact-highlight
geometry already worked on any screen; what was missing on mobile is *reachability*: tapping a verified citation in a
synthesis (on the "Panels" region) opened the PDF in the *reader* region, which the phone wasn't showing. Now
`openPdf`/`openCitation` switch `mobilePane` to the reader on mobile (the highlight lands in view), and a
**`.pdf-back-pill`** ("← Synthesis") — a fixed pill above the bottom nav, shown only while reading the source a citation
opened (`citationReturn` state; cleared on any manual nav or plain open) — returns you to the exact synthesis in one
tap. **Rule-#1 split:** `30_viewer.jsx` was **580 at HEAD**; the ~44-line pinch effect took it to **629 (>600)** → the
minimap (`MinimapTrack`, inc 215) + `usePinchZoom` extracted verbatim → new **`js/30f_pdf_gestures.jsx`** (64; both
hoist in the shared IIFE, so `PdfViewer` references them regardless of chunk load order — the inc-182/208/222/238
precedent); `30_viewer.jsx` **573**. **Frontend-only** — no backend/endpoint/migration/new-dependency/egress change,
so **no audit/Principles trigger** (a reading UX; the minimap positions by *page fraction*, never a fabricated exact
rect — coordinate honesty #2 unchanged; the desktop layout is byte-for-byte unchanged, the `mobile` branch never runs
above 760px). pytest **884 passed, 1 skipped** (frontend-only; `test_frontend_assembly` 5/5 confirms `30f_pdf_gestures.jsx`
is in the build + `callosum-app.html` in sync); `ruff` + `format` clean; **QA surface 173/173 API + 760/760 FE, 0
uncovered** (`route_32_viewer_annotations.md` claims `30f_pdf_gestures.jsx`; no new API surface). **Headed-verified at
390×844, 0 errors** (`.local/visual/drive_inc239_mobilereader.py` — seeds a paper + PDF + highlight + a native
synthesis citing it: open the PDF → **fit-width active + no Two-up + a minimap tick** [30f intact]; **pinch-out 74% →
148%**; go to Panels → load the synthesis → tap its citation → **the reader shows + the "← Synthesis" back pill
appears** → tap it → **the synthesis returns + the pill clears**; **0 console/page errors**). DESIGN.md records the
`.pdf-back-pill` recipe + the mobile fit-width/pinch/touch-action pattern (rule #8). Notes: `INCREMENT-239-NOTES.md`.
**This builds the B5 SP2-deferred slice; B5 is fully complete** (SP1 responsive+read-only tunnel 237 · SP2 read-only
companion UI 238 · SP3 mobile reader 239). All of B1–B5 done. (A further-deferred nicety, if ever wanted: a
mobile-tuned Notes/annotation authoring flow — creating highlights by touch, vs the current tap-a-citation reading.)

Earlier — increment 238 (B5 SP2 — **the read-only companion UI**; brainstormed →
fork → built inline). The SP1 tunnel *blocks* writes; SP2 makes the app *read clean* when it's a read-only instance —
no dead buttons. **Maintainer fork (AskUserQuestion): comprehensive** (hide every write control across all panels, not
just the reader core). **Detection:** `GET /health` gains an additive `read_only` field (`app_settings.read_only_mode()`)
— the one endpoint forwarded over the read-only tunnel AND token-exempt, so the app reads it to decide; a **UX signal,
not the boundary** (the SP1 method gate is). The App's `readOnly` is **tri-state** (`undefined` until `/health`
resolves, then true/false) so no background read-implemented-as-POST fires before it's known; threaded into `paneCtx`
+ `libraryProps` + a fixed **`.read-only-badge`**. **Comprehensive hiding:** the library-header write cluster + bulk
actions + per-card read/priority markers (`10_pdf_layer.jsx`, drops `selecting`); **Details rendered static** (a
`DetailReadOnly` React **context** consumed by `EditableRow`/`EditableText`/`IdentifierRow` → plain text, zero
call-site churn) + Fill/re-resolve(🔎)/OCR/+Reading-queue/tag add-remove hidden; **Synthesis** run + Re-verify +
Save-highlight + history-Delete hidden (reading saved syntheses still works); **Axes** create/score/freeze/convert/
delete/✓/×/drop-to-add/reorder + **Tags** add-remove/color + **Queue** add/reorder/✓/× hidden; the **METHODS analysis
sections** (statcheck/GRIM/findings/citation-equity/citation-context + the coming-soon placeholders) drop via a new
pane-registry **`hideInReadOnly`** flag (Details stays); **Discover/Feed tabs** hidden. **No doomed writes on load**
(the honest "a read-only companion never fires a write it will 403"): the on-launch watched-folder rescan is gated on
`healthLoaded && !readOnly`, and CiteRow's `/citations/render` (a read-implemented-as-POST) only fetches once
`readOnly === false` — headed shows **0 request-403s on load** (was 2). **Widened read ingress:** the read-only
cloudflared allowlist now forwards the core library **read** GETs (`/axes`, `/axes/{id}/clusters`, `/tags`,
`/tags/colors`, `/reading-queue`, `/papers/{id}/annotations`, `/papers/{id}/chunks`) so those panels *load* read-only
over the tunnel — every write on those paths is still 403'd by the method gate; the analysis/config routes stay 404.
**Rule-#1 split:** `25_detail.jsx` was **624 at HEAD** (a pre-existing violation the "583" watch note had drifted on;
the read-only additions worsened it) → the inline-field primitives (`EditableRow`/`EditableText`/`TypeSelect`/
`IdentifierRow` + the `DetailReadOnly` context) → new **`js/24_detail_fields.jsx`** (159; sorts before 25 so the
`const` initializes first; the functions hoist in the IIFE); `25_detail.jsx` **492**. **No new API endpoint** (an
additive `/health` field + a config file), **no migration, no new dependency**. **Audit addendum to
`.claude/security-audits/2026-07-01_mobile-reading.md` PASS** (the `/health` flag is a default-false non-secret UX
signal; the widened ingress is read-only-of-the-user's-own-library + method-gated; no doomed writes fire on load; the
SP1 guarantee unchanged). **Principles non-triggering** (a UX/deployment flag; no claim/signal; egress posture
unchanged). pytest **884 passed, 1 skipped** (+11 `tests/test_mobile_ingress.py` — the broadened forward list [`/axes`,
`/axes/3/clusters`, `/tags`, `/tags/colors`, `/reading-queue`, `/papers/5/annotations`, `/papers/5/chunks`] + the
broadened block list [`/methods/statcheck/run`, `/discovery/*`, `/feed`, `/gaps`, `/findings/overview`,
`/papers/citation-counts/refresh`, `/papers/ocr/run`, `/axes/3/score`, `/axes/suggest`, `/citations/render`] + a
`/health.read_only` truth test); `ruff` + `format` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA
surface 173/173 API + 758/758 FE, 0 uncovered** (`route_30_detail_pane.md` claims `24_detail_fields.jsx`; the
`read_only` flag rides the already-claimed `/health`). **Headed-verified, 0 errors** (`.local/visual/drive_inc238_readonly.py`
— serves twice: `CALLOSUM_READ_ONLY=1` → the badge shows, the library write cluster + Discover tab are hidden, 20
Details fields are static [`.detail-ro`], no Fill button, **0 console/page errors + 0 request-403s on load**; the
read-write control run → the badge is absent + the write cluster + Discover + Fill all return). Notes:
`INCREMENT-238-NOTES.md`; spec-context `.claude/docs/specs/2026-07-01-mobile-reading-sp1.md` (SP2 was the deferred
section). **This completes B5 — the last B-item; B1–B5 are all done.** (SP2's own deferred: a mobile-tuned PDF reader /
synthesis→PDF exact-highlight overlays on mobile.)

Earlier — increment 237 (B5 SP1 — **responsive mobile reading**, read-only over the tunnel; the
last B-item, started; brainstormed → forks → spec → built). **Read your library on a phone.** **Maintainer forks
(AskUserQuestion):** **make the desktop app responsive** (one app, not a separate `/m` companion) + **full reader**
(browse + paper metadata/abstract + PDF + read-only syntheses). **The responsive layout** (the deliverable):
`04_layout.jsx::useUiPrefs` gains a `mobile` flag (`window.matchMedia("(max-width: 760px)")` + a change listener — the
inc-34 DPR-listener pattern) + a transient `mobilePane`; `40_app.jsx` computes the three region nodes (Sidebar =
THEORY accordion, LibraryFrame = center/reader, pane-detail = METHODS) + the modals **once**, then branches —
**desktop** = the unchanged 5-cell grid + dividers; **mobile** = `.app.mobile`, a single column showing **one region
at a time** (`mobilePane`) + a bottom **`MobileNav`** (Library / Panels / Details), built on the inc-101
reading-mode collapse. New `02_mobilenav.jsx` (a presentational leaf; hoists in the IIFE) + `styles.css`
`.app.mobile`/`.mobile-body`/`.mobile-nav` (`height: 100dvh` for the mobile address bar; tokens only, rule #8).
Desktop is **byte-for-byte unchanged** (the `mobile` branch never runs above 760px). **The read-only GUARANTEE = two
boundaries** (the app **cannot** tell tunnel from local — the inc-168 lesson): **(1) the METHOD gate** —
`CALLOSUM_READ_ONLY=1` (an env var → `app_settings.read_only_mode()`) makes `AccessControlMiddleware` return **403**
for every mutating method (anything but GET/HEAD/OPTIONS), *before* the remote-access check; this is the **real**
boundary, because a path like `/papers/5` serves both a GET read and a DELETE/PATCH write and cloudflared matches
**path**, not method. **(2) the read-only cloudflared ingress allowlist** (`adapters/mobile/cloudflared-config.yml` —
forward only `/`, `/health`, `/papers`, `/papers/{id}`, `/papers/{id}/pdf`, `/summaries*`, `/help/corpus`; everything
else → **404** — defense in depth, keeping `/settings`, the scan/import routes, `/axes`, `/tags` unreachable at the
tunnel). Plus the inc-168 **bearer token** (Remote access) gating all access. **Recommended deploy:** a **second,
read-only callosum** for the tunnel (the inc-170 isolated-instance pattern) pointed at the library DB (SQLite WAL →
concurrent readers safe) with `CALLOSUM_READ_ONLY=1` + Remote access on — the desktop instance stays read-write.
`tools/run_tunnel.py --mobile` runs the read-only tunnel; `adapters/mobile/README.md` is the runbook (a `--quick
--mobile` Quick-Tunnel path drops the ingress allowlist → the method gate + token are then the sole boundaries,
documented). **Default-off, env-only** (a remote caller can't set env — the `CALLOSUM_DISABLE_REMOTE_ACCESS` hatch
pattern); unset → zero change. **No new API endpoint** (a middleware gate + a config file), **no migration, no new
dependency, no new served route** (the responsive app is the same `/`). **Audit
`.claude/security-audits/2026-07-01_mobile-reading.md` PASS** (read-only enforced at the method level with the ingress
allowlist as defense in depth; default-off + env-only; the token still gates; no new endpoint/dependency/migration/
egress). **Principles non-triggering** (responsive layout + a read-only deployment; no claim/signal); the **values
layer** applies — mobile reading is an *extended* value (the existing "read your library" made available on another
device, under the existing consent/egress discipline). pytest **872 passed, 1 skipped** (+22 `tests/test_mobile_ingress.py`,
hermetic: the ingress regex **forwards** each read path [`/`, `/papers`, `/papers/5`, `/papers/5/pdf`, `/summaries`,
`/summaries/7`, `/help/corpus`] and **does not match** the write/config paths [`/settings`, `/library/scan`, `/axes`,
`/tags`, `/papers/5/re-resolve`, `/summaries/5/reverify`, `/reading-queue`, `/agent/status`]; `CALLOSUM_READ_ONLY=1`
→ GET 200 but POST `/summarize` + DELETE `/papers/999` + a **path-matched** POST `/papers/export` → **403**;
off-by-default → DELETE reaches the handler [404, not 403]); `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5); **QA surface 173/173 API + 758/758 FE, 0 uncovered** (`route_00_smoke_readonly.md`
claims `02_mobilenav.jsx`; no new API surface — the gate is middleware, the ingress is config). **Headed-verified**
(`.local/visual/drive_inc237_mobile.py` — at 390×844: `.app.mobile` single-column, a bottom `.mobile-nav` with 3
tabs, **0 dividers**; tap Details → the pane-detail region + the active tab; tap Library → the library search; resize
to 1280×900 → the 3-pane grid restored + no mobile nav; 0 console/page errors). Notes: `INCREMENT-237-NOTES.md`; spec
`.claude/docs/specs/2026-07-01-mobile-reading-sp1.md`. **This starts B5 — the last B-item** (B1–B4 done; B2 fully
complete). **SP2 (deferred):** an app-side read-only *UI* that hides write controls for a clean companion (the tunnel
already blocks writes, so this is UX, not security), and a mobile-tuned PDF reader / citation highlights.

Earlier — increment 236 (library bundle SP3 — **"Re-verify against my library"** turns a relayed
synthesis native; **B2 fully complete**; brainstormed → forks → spec → built). A **"Re-verify against my library"**
button on an imported (relayed) synthesis re-runs the **local** verifier — retrieval + NLI + quote-location — over
the recipient's chunks for the same claims and **converts the synthesis in place to native**. **Fully local — no
egress, no LLM** (the sentences already exist; only verification runs; this is the aligned outcome of the SP2 relay —
verification becomes the recipient's substrate's job, invariants #1/#4). **Maintainer forks (AskUserQuestion):**
**convert in place** (the same summary becomes native — `imported_json` cleared, real verification rows,
`generated_by="re-verified-from-bundle"`) + scope = **the synthesis's source papers** (faithful — re-check the
sender's evidence in my copy). **The load-bearing reuse:** the SP2 blob already keeps the **sender's quote** + the
source **identity** per citation (SP3 added the identity to the blob), so `summarization/reverify.py` per citation:
re-resolve the source by identity (`find_existing_paper_by_identity` — picks up a paper added since import) →
`_best_chunk_for` (the local chunk containing the sender's quote, else best-by-similarity) →
`LocalCitationVerifier.verify(sentence, CandidateCitation(local_chunk, sender_quote), source_chunks=[])` → **exact
coordinates** when the sender's quote is verbatim in my PDF (same edition), else **region**; NLI
support/contradiction → verified/weak/contradicted. **A claim whose source paper I don't have → a flagged sentence
with no local citation** (silence≠certificate — the claim shows, unverified, never silently "verified"). Persist =
convert in place: delete any old rows, `update summaries` (`imported_json=NULL`, recomputed status,
`generated_by="re-verified-from-bundle"`, `overview_json=NULL` — the sender's overview traced *their* verified set,
not re-narrated/no-LLM, version stamps from `_combined_*`), write native `summary_sentences`/`citation_mappings`/
`evidence_quotes` (reuse `_persist_verification`). **`POST /summaries/{id}/reverify`** (sync — verification of a few
sentences is fast, no generation/egress; **404** unknown, **422** if not imported; reuses `_embedding_model` +
`_vector_store` + `api.state.support_scorer` over one `engine.begin()`) + a **"Re-verify against my library"** button
in the `.synth-imported` banner (`20_synthesis.jsx`) → on success the banner drops (`imported:false`), the pane shows
**my own** verified/flagged statuses (exact highlights where the quote matched). **The honesty is aligned, not a new
claim type** — it's the *existing* local verifier re-run, so the statuses become the recipient's own; the "sender's
assessment" caveat is *removed* precisely because it's now been re-checked locally. **No egress, no new dependency, no
migration** (reuses the SP2 `imported_json` column). **Audit addendum 2 to
`.claude/security-audits/2026-07-01_library-bundle.md` PASS** (no egress/LLM/dependency/migration; bound-param SQL in
one transaction; the honest native outcome — unsupported→flagged, absent-source→flagged-no-citation, exact-only-when-
the-quote-matches). **Principles gate run — aligned.** pytest **850 passed, 1 skipped** (+2 hermetic
`tests/test_reverify.py` — fake embed/vector/support models: convert-to-native [`imported:false`, a chunk-backed
citation, the row `imported_json` NULL + `generated_by="re-verified-from-bundle"`, no-longer-flagged, **re-resolved by
identity** from a blob `paper_id:None` + a `source` DOI now in the library] + **422** on a native summary + **404** on
a missing id; a claim whose source isn't present → a **flagged sentence with no citation**, the text kept); `ruff` +
`format` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 173/173 API + 755/755 FE, 0 uncovered**
(`route_54_library_bundle.md` extended; the endpoint rides `/summaries*`, the button rides `20_synthesis.jsx`); help
corpus's "Sharing a library" now covers the re-verify action (`HELP-DOCS-SYNCED` → 236). **Headed-verified, no egress**
(`.local/visual/drive_inc236_reverify.py` — a dest with a paper + an imported synthesis citing it, fake models: open
THEORY → Synthesis → load it → the imported banner shows → **Re-verify against my library** → the banner **disappears**
[now native] + a native citation renders; 0 console/page errors, 0 off-machine requests). Notes: `INCREMENT-236-NOTES.md`;
spec `.claude/docs/specs/2026-07-01-library-bundle-reverify-sp3.md`. **This completes B2 (SP1 234 + SP2 235 + SP3 236).**
**NEXT — the last unstarted B-item is B5** (mobile reading — responsive, read-only, over the tunnel; its own brainstorm).

Earlier — increment 235 (library bundle SP2 — syntheses travel as **relayed artifacts**;
**completes B2**; brainstormed → forks → spec → built). A synthesis is a **verification artifact** — its
verified/contrasted/flagged statuses were computed against the **sender's** chunks — so importing one must **not**
present it as the recipient's verified synthesis (that would violate invariant #1: external output is never
authoritative citation evidence; #4: verification is the recipient's substrate's job). **Maintainer forks
(AskUserQuestion):** **relay + flag** (a one-click "re-verify against my library" is a bigger, separate feature →
SP3) + syntheses in **both** whole-library + selection exports. **The honest structural design:** an imported
synthesis is a **self-contained display blob** (`summaries.imported_json`, **migration 0032**, additive/guarded;
`status="imported"`) — **never** written to `summary_sentences`/`citation_mappings`/`evidence_quotes`, so it can't
be read as, or mistaken for, a locally-verified synthesis. `summaries.py::_persisted_summary_response` branches on
the blob → `_imported_summary_response` (`imported=True`); `20_synthesis.jsx` shows the **"Imported — the sender's
assessment, not re-checked in your library"** banner (`.synth-imported`, `--flag` family); **every citation opens at
region precision** (`coordinate_precision="region"`, never a fabricated exact box — the sender's bbox is for the
sender's PDF); a citation whose source paper the recipient lacks shows its **quote** + "Source not in your library"
(evidence stays visible, no Open link — silence≠certificate). **Export** — `library_bundle.py::_synthesis_entries`
(NATIVE only, `imported_json IS NULL` → a bundle never re-relays a relayed artifact; a *selection* keeps only
papers-scope syntheses **fully contained** in the selection so the recipient has every cited paper); each citation
travels **by source identity** (resolved through the summaries.py chunks→papers read join), not chunk id. **Import**
— `_import_syntheses` (resolve each source by identity → local `paper_id` else None; build the region-precision blob;
insert one `summaries` row; **idempotent by content**; bounded `MAX_BUNDLE_SYNTHESES=2000` / `MAX_SYNTHESIS_SENTENCES=400`
/ `MAX_CITATIONS_PER_SENTENCE=50`; per-synthesis `begin_nested()` savepoint → a bad one is skipped). `SummaryCitationResponse`'s
`mapping_id`/`evidence_quote_id`/`chunk_id`/`paper_id` become **Optional**; `SummarizeJobResponse.imported` +
`SummaryListItem.imported` added; the modal + `BundleImportSummary.syntheses_imported` surface the count. **No egress
at all** (a local file), **no PDF bytes**, **no new dependency, no new endpoint** (rides the SP1 `/library/bundle/*`
+ the existing `/summaries*`). **Audit addendum to `.claude/security-audits/2026-07-01_library-bundle.md` PASS** (the
relay-not-re-verify separation upholds invariants #1/#2/#4; additive/guarded migration; bound-param SQL;
bounded/fail-closed; still no egress/PDFs). **Principles gate run — aligned** (the honesty gate; declined the
misaligned "import as a native verified synthesis" path). pytest **848 passed, 1 skipped** (+6 hermetic
`tests/test_library_bundle.py` synthesis tests: export carries the sentence + citation quote/status + **source-by-identity**;
imported→relayed + read via API [`GET /summaries/{id}` → `imported:true` + **region** citations from the blob, never in
the tables; `GET /summaries` flags it]; re-import idempotent [dedup by content]; a citation whose paper isn't present →
`paper_id:null` + quote carried; native-only never re-exports a relayed one; a selection carries a fully-contained
papers-scope synthesis, excludes an out-of-selection one); `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5); migration head **0032** via `alembic_head()`; **QA surface 172/172 API + 753/753 FE, 0
uncovered** (`route_54_library_bundle.md` extended with the relayed-synthesis honesty assertions; the `imported` flags
+ `syntheses_imported` ride existing endpoints, the banner is in the already-claimed `20_synthesis.jsx`); help corpus's
"Sharing a library" section now covers syntheses (`HELP-DOCS-SYNCED` → 235). **Headed-verified, no egress**
(`.local/visual/drive_inc235_syntheses.py` — a dest DB pre-loaded with a relayed synthesis: open THEORY → Synthesis →
load it from history → the **"Imported — the sender's assessment"** banner renders, the citation shows **REGION-LEVEL**
precision [no exact box] with its quote; 0 console/page errors, 0 off-machine requests). Notes: `INCREMENT-235-NOTES.md`;
spec `.claude/docs/specs/2026-07-01-library-bundle-syntheses-sp2.md`. **This completes B2 (SP1 inc 234 + SP2 inc 235).**
**NEXT — B2 SP3 (deferred):** a one-click **"re-verify against my library"** on an imported synthesis (re-run the local
verification pipeline — retrieval + NLI + quote-location — over the recipient's chunks for the same claims, turning the
relayed artifact into a native one). The remaining B-item overall is **B5** mobile reading (responsive, read-only, over
the tunnel).

Earlier — increment 234 (portable library bundle — B2 SP1, file-based collaboration; brainstormed
→ spec → built). **Share a library without a server and without shipping copyrighted PDFs:** export a library (or a
selection) to a **versioned JSON file** carrying **metadata + tags + annotations + axis definitions but NO PDFs**,
and import/merge it into another library. A file the user hands off — **no server, no automatic egress**;
copyright-safe (the recipient re-acquires their own PDFs via the OA lane). **Maintainer forks (AskUserQuestion):**
syntheses **deferred to SP2** (they'd need citation re-anchoring to travel honestly — SP1 is the clean "annotated
bibliography" bundle); **axis definitions in** (whole-library only — curated members travel by identity, keyword axes
are definition-only + re-scored locally); **both whole-library + selection** export. **Reuses two proven anchors:**
the inc-93 citation-import async-job pattern — with the load-bearing correction that `find_existing_paper_by_identity`
**keeps the matched row** as the merge target (citation-import discards it) — + the inc-70 export download (a raw
`Response` + `_downloadBlob`). New `metadata/library_bundle.py` (`build_bundle` + `import_bundle`, keyed on **natural
identifiers** — paper by identity, tag by name, axis by label — borrowing the sync feature's identity *idea* not its
crypto/`SyncTransport`/conflict engine [welded + private]) + 3 endpoints on `routers/library.py` (`POST
/library/bundle/export` [sync raw file, constant filename], `POST /library/bundle/import` [202 → an async job that
**embeds the new papers** so they join search/axis-scoring] + `GET .../import/{job_id}`) + `app.state.library_bundle_import_jobs`
+ a `BundleImportModal` (`28b_bundle.jsx`, clones `28_import.jsx`) + "+ Add ▾" **Import bundle…** / **Export library
bundle…** items + a selection bulk-bar **bundle** action + `downloadBundle` (a tokened raw POST). **Merge is additive
& non-destructive:** an existing paper (matched by identity) keeps its own metadata + provenance and only *gains* the
bundle's tags + annotations; new papers stamped `imported_source="bundle-import"` (kept out of the enrich-clobber
allowlist, like user-edited); tags get-or-create by name (a tag is colored only if uncolored); annotations dedup by
page/bbox/note + **drop `attachment_id`** (the box re-renders once the same PDF exists — coordinate honesty #2);
re-import is idempotent; curated axis members resolve by identity, keyword axes import definition-only; `my_publications`
axes are **never exported** (authorship). **No egress at all** (a local file the user hands off — not the Gemini gate,
no network call), **no PDF bytes** (honors the acquisition / no-paywall-circumvention veto), **no path traversal**
(text-in-body, the citation-import posture), bounded (20 MB / 20 000 papers / per-paper caps) + fail-closed
(`BundleError` → a graceful job error). **No new dependency, no migration.** **Audit
`.claude/security-audits/2026-07-01_library-bundle.md` PASS**; **Principles non-triggering** (no claim/signal/score);
the **values layer** applies (collaboration/sharing is an *emergent* value — adopted deliberately as the file-based,
copyright-safe slice of the accounts-SP4 sharing direction; strengthens A5 sovereignty — a portable, open, inspectable
JSON with no lock-in / no server). pytest **842 passed, 1 skipped** (+8 hermetic `tests/test_library_bundle.py` — two
throwaway SQLite DBs, no network/model: build-shape / selection-no-axes / round-trip-into-empty / re-import-idempotent
/ merge-non-destructive [existing paper keeps its title + `user-edited` provenance, gains the tags + highlight] /
curated-members-resolve-keyword-definition-only / annotation-attachment_id-dropped / parse-caps [malformed / unknown
version / oversized]); `ruff` + `format` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 172/172
API + 753/753 FE, 0 uncovered** (`route_54_library_bundle.md`); help corpus gained "Sharing a library
(bundle export/import)" (`HELP-DOCS-SYNCED` → 234). **Headed-verified, no egress**
(`.local/visual/drive_inc234_bundle.py` — a seeded library [paper + tag + highlight + curated axis] with a fake embed
model: **+ Add ▾ → Export library bundle…** downloads a `.json` [1 paper, tag + note + curated axis, **NO** pdf/
attachment], then **Import bundle…** → set the file → Import → the summary reports a **merged** round-trip; 0
console/page errors, 0 off-machine [non-loopback] requests). Notes: `INCREMENT-234-NOTES.md`; spec
`.claude/docs/specs/2026-07-01-library-bundle-design.md`. **NEXT — B2 SP2 (deferred):** syntheses in the bundle
(citations re-anchored as quote+page+source-DOI → region precision on the recipient's matching paper, flagged "the
sender's verification, not re-checked here"). Other remaining B-item: **B5** mobile reading (responsive, read-only,
over the tunnel).

Earlier — increment 233 (citation context SP2 — "how this paper cites its sources"; **completes
B4**). The outgoing mirror of the inc-232 SP1 panel. **The realization that made it easy:** Semantic Scholar's
**`/references`** edge returns, for each paper the focal cites, the **context sentences** — the sentences *in the
focal paper* where it cites that reference. **S2 has already linked every in-text citation to its reference**, so SP2
needs **no local citation-marker parsing** (the thing I'd flagged as fiddly) — it's a near-mirror of SP1. The S2
client was generalized into `_fetch_edge(edge=…)` (`fetch_citation_contexts` = the `citations` edge;
`fetch_reference_contexts` = the `references` edge; the edge name is a fixed literal, never request-derived → no new
SSRF surface); `CitingContext` gained a `claim` field — for `references` it's the **cited paper's own** title/abstract
(requested via `citedPaper.abstract`), the per-item NLI **hypothesis**; for `citations` it stays None and the constant
focal-paper claim is used. The classifier's hypothesis is `ctx.claim or focal_claim` (SP1 untouched). The endpoint
gained a strict `direction: Literal["citations","references"] = "citations"` param (the worker branches — references
→ per-item claims, `focal_claim=""`); the panel gained an **[How it's cited | How it cites its sources]** toggle
(`.citec-toggle`, resets to idle on switch), the intro/button/empty-state copy adapting to the direction. **Same
honesty** as SP1 — counts never a score, the citing sentence always the evidence, a labeled signal not a verdict, and
a "contrast" here describes the focal paper's *own* rhetorical move *in the shown sentence*, never an accusation.
**Egress = the DOI → Semantic Scholar** (public bibliographic metadata, cached under `references:{doi}`), **NOT** the
Gemini gate; the stance classification runs **fully locally**. **No new pip dependency, no migration.** Audit
**addendum** to `.claude/security-audits/2026-07-01_citation-context.md` **PASS** (same posture, a second edge — the
same DOI validation + `quote(safe='')` encoding + bounded/paginated/capped/non-poisoning-cache; the `direction` is a
strict Literal → 422 otherwise). **Principles** inherited from SP1 (signal-not-verdict / evidence-shown / no-composite
/ no-accusation). pytest **834 passed, 1 skipped** (+3 hermetic `tests/test_citation_context.py` — the `references`
edge parses `citedPaper` + the per-item claim [abstract else title] + requests `citedPaper.abstract`; the classifier
uses the per-item claim; the endpoint runs with `direction=references`); `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5); **QA surface 169/169 API + 737/737 FE, 0 uncovered** (`direction` rides the existing
endpoint; the toggle claimed by `route_53_citation_context.md`); help corpus's "Seeing how a paper is cited" now
covers the toggle (`HELP-DOCS-SYNCED` → 233). **The live Semantic Scholar round-trip on a real DOI is the maintainer's
spot-check** (needs network). Notes: `INCREMENT-233-NOTES.md`; spec `.claude/docs/specs/2026-07-01-citation-context-design.md`.
**This completes B4 (SP1 inc 232 + SP2 inc 233).** **NEXT — the remaining B-items:** B2 portable-bundle collaboration
(metadata + annotations + syntheses, no PDFs); B5 mobile reading (responsive, read-only, over the tunnel). Each its
own brainstorm + the maintainer's pick.

Earlier — increment 232 (citation context "how this paper is cited" — backlog B4 SP1, the scite
analogue; brainstormed → spec → built). When you're deciding whether to rely on a paper it matters *how the later
literature responded to it*: do subsequent papers **support**, **contrast**, or merely **mention** it? A new METHODS
panel fetches the actual **citing sentences** from **Semantic Scholar** and classifies each one's stance **locally**
with our own NLI. **Maintainer decisions (AskUserQuestion):** *incoming direction first* (the scite headline — outgoing
"how a paper cites its own refs" deferred, it needs fiddly in-text-citation→reference linking) + *our local NLI stance*
(reusing inc-156's `NLIStanceScorer`, not Semantic Scholar's black-box intents). **The honesty is the load-bearing
part** (scite-style tools drift toward verdicts): the aggregate is **counts, NEVER a composite "score"** (#7); every
citation shows its **real citing sentence** as the evidence (#4); the stance is a **labeled signal, not a verdict**
(#2, shown with confidence — an NLI reading of the citing sentence against the focal paper's own claim); an
unclassifiable citation (no sentence) is **counted, never guessed** (#6); a "contrast" describes the shown sentence's
rhetorical relationship, **never an accusation** of an author (A-A). New `integrations/semantic_scholar/adapter.py`
(`SemanticScholarClient.fetch_citation_contexts` — injectable fetcher + `external_api_cache`, paginated + capped
[`MAX_CITATIONS = 500`], **the DOI shape-validated + fully url-encoded** [`quote(safe='')`] → no SSRF, fail-closed with
**non-poisoning caching** [a transient first-page failure is NOT cached as "0 citations"], optional
`CALLOSUM_S2_API_KEY` write-only) + a pure `methods/citation_context.py` (`classify_citation_contexts` → counts +
per-citation evidence; no composite score) + an async `routers/citation_context.py` (`POST/GET
/papers/citation-context/run`, an `citation_context_jobs` JobStore, registered **before** `papers.router`;
`_stance_scorer(app)` mirrors `citations.py`) + a panel `08c_methods_citation_context.jsx` (order 36 — **Fetch
citations** → a counts breakdown [N supporting · M contrasting · K mentioning] + a list of citing sentences, each a
`.cite-stance` pill + confidence + the citing paper [link] + an "influential" marker + an honest coverage line +
credit). **Egress = the DOI → Semantic Scholar** (public bibliographic metadata, the OpenAlex/Crossref posture,
cached), **NOT** the Gemini library-text gate; the stance **classification runs entirely locally**. **No new pip
dependency** (httpx + the existing local NLI); **no migration** (ephemeral job result, like citation-equity).
**Credit-the-lineage:** scite (Nicholson et al. 2021, *Quantitative Science Studies* — the tool this echoes) credited
+ one-click library-addable from the panel; **Semantic Scholar** (Allen Institute for AI) credited in-panel +
`THIRD-PARTY-NOTICES.md`. **Audit `.claude/security-audits/2026-07-01_citation-context.md` PASS** (SSRF-safe validated+
encoded DOI, constant host; bounded/paginated/capped; fail-closed + non-poisoning cache; local classification;
public-metadata-not-Gemini; no dependency). **Principles gate run — aligned** (the statcheck / inc-156-suggest class: a
labeled signal about the literature carrying its evidence; the misaligned "smart-citation score / verdict" path
declined). pytest **831 passed, 1 skipped** (+6 hermetic `tests/test_citation_context.py` — a fake S2 fetcher + a fake
local NLI, no network/model: the client parses/paginates/caps/validates-DOI/fails-closed-without-poisoning-the-cache;
the classifier counts + keeps evidence + never guesses [no `score` key]; the endpoint 202→poll→done, 404/422,
no-citations→honest-empty); `ruff` + `format` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface
169/169 API + 733/733 FE, 0 uncovered** (`route_53_citation_context.md`); help corpus gained "Seeing how a paper is
cited" (`HELP-DOCS-SYNCED` → 232). **The live Semantic Scholar round-trip on a real DOI is the maintainer's
spot-check** (needs network; the classification + contracts are pytest-proven). Notes: `INCREMENT-232-NOTES.md`; spec
`.claude/docs/specs/2026-07-01-citation-context-design.md`. **NEXT — B4 SP2 (deferred):** the *outgoing* direction
("how this paper cites its own sources" — in-text-citation detection + reference linking + local stance). Other
B-items: B2 portable-bundle collaboration (no PDFs); B5 mobile reading.

Earlier — increment 231 (OCR scanned PDFs into a searchable copy — backlog B3, the first of the
design-gated B-items, brainstormed → planned → built). Scanned / image-only PDFs imported with **0 chunks** →
invisible to search, synthesis, and citation. Via AskUserQuestion the maintainer chose **local Tesseract, manual,
exact highlight boxes**. **The load-bearing discovery, mid-build:** exact citation highlights come from
`locate_quote_for_attachment` **re-reading the PDF's text layer** at display time — a scanned PDF has none — so
*storing* OCR word-boxes in the DB would never produce exact highlights (the code would fall back to region). The
clean answer (a second AskUserQuestion, the maintainer picked it) is a **searchable PDF**: new
`pdf_processing/ocr.py::make_searchable_pdf` renders each page → PNG → local `tesseract stdin stdout pdf` (a
single-page searchable PDF: the page image + an invisible, correctly-positioned OCR text layer) → merges via `fitz`
→ the worker attaches it as the new **primary** (the original scanned attachment kept, demoted — non-destructive) →
extracts + embeds through the **normal** `attach_pdf_to_paper`/`extract_pdf`/`embed_chunks` path. So a scanned paper
becomes fully first-class — searchable, embeddable, **exact** citation highlights, and selectable text in the viewer —
**with zero changes to the fragile quote-location / coordinate-honesty code** (it reads the real text layer Tesseract
embedded). Rebuilding pages from upright rasters means the copy has **no page rotation**, so the overlay's
rotated-page skip never applies. **No new pip dependency:** Tesseract is a *system binary* invoked via
`shutil.which("tesseract")` + a fail-closed `subprocess.run` with the image **piped via stdin** (fixed argv → no
injection) — the Node/esbuild/citeproc pattern, the cloudflared precedent; PyMuPDF renders + merges (no Pillow).
New `routers/ocr.py` (`POST/GET /papers/ocr/run`, an async `ocr_jobs` JobStore, registered **before** `papers.router`
so `/papers/ocr/*` wins); the Detail-pane **"OCR this paper (scanned)"** button (`OcrRow` in `25_detail.jsx`, reusing
the `.detail-acquire` recipe) is gated on **`hasPdf && chunk_count == 0`** — only true scanned PDFs, so the worker
only ever *adds* chunks (no delete / vector-cleanup; re-OCR is a follow-up). Fully **local — no egress** (like
statcheck), NOT the Gemini gate; **no migration** (reuses attachments/chunks/embeddings). **Audit
`.claude/security-audits/2026-07-01_ocr.md` PASS** (fixed-argv subprocess + stdin image → no command injection;
source path DB-derived [inc-91 resolver] never client input; managed write under `library_dir()` with a
sanitized/deduped `(OCR)` name → no traversal; bounded `MAX_OCR_PAGES`/per-page timeout; fail-closed
`TesseractUnavailable` → graceful job error, never a crash; non-destructive; no new dependency). **Principles
non-triggering** (OCR produces the same evidence-carrying chunks as normal extraction; coordinate honesty is
*preserved* precisely because the text layer is real, not fabricated). pytest **824 passed, 1 skipped** (+5 hermetic
`tests/test_ocr.py` — a fake page-runner returns a real text PDF, so CI never needs the binary: the engine builds a
searchable PDF the normal extractor reads; the endpoint 202→poll→done makes a scanned paper searchable + keeps the
original + the OCR copy primary [`import_source="ocr"`]; 404/422; graceful when Tesseract is absent); `ruff` +
`format` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 167/167 API + 729/729 FE, 0 uncovered**
(new `route_52_ocr.md`); help corpus gained "Making a scanned PDF searchable (OCR)" (`HELP-DOCS-SYNCED` → 231).
**Follow-up (same session):** the maintainer's `winget install UB-Mannheim.TesseractOCR` had **already** installed
Tesseract v5.4.0 but **not on PATH** (the UB-Mannheim installer's default), so `shutil.which` missed it. Added
`ocr.py::tesseract_exe()` — resolves via `CALLOSUM_TESSERACT_PATH` (env override) → PATH → a fixed list of common
install locations (`C:\Program Files\Tesseract-OCR\…`, Homebrew/apt) — so OCR **just works** after a standard install
without a manual PATH edit; the error message points at `CALLOSUM_TESSERACT_PATH` for non-standard installs. And with
the binary now resolvable, the **real Tesseract round-trip is verified live** (an image-only page → `tesseract stdin
stdout pdf` → a searchable PDF the normal extractor reads the recovered text from — "The ultimatum game…"). pytest
**825** (+1 resolver test); audit addendum PASS. Notes: `INCREMENT-231-NOTES.md`; plan
`.claude/backups/plans/2026-06-30_ocr-scanned-pdfs-b3.md`. **NEXT:** the remaining B-items (B4 citation-context
classifier — the maintainer chose *both* directions, but "how a paper is cited" needs an external full-text source;
B2 portable-bundle collaboration [no PDFs]; B5 mobile reading) — each its own brainstorm + build.

Earlier — increment 230 (the small close-out of the inc-229 values rework: **dropped the
user-facing "we don't categorize people" note — the absence is clean, not monumented**). The maintainer: *"if we
have dropped it now, we should just drop it — time to move on."* Keeping a prominent in-app/help note explaining what
the tool deliberately *doesn't* do (categorize authors by gender/race/nationality) is itself a way of keeping the
removed idea alive — the same logic that removed the geography signal. So the `.cite-equity-deferred` note block (+
its CSS) and the help paragraph were removed, and the intro/header comment trimmed; the panel now just measures
citation concentration, cleanly, with no disclaimer about the dropped feature. **The regression guard test stays** —
it's invisible to users but keeps people-categorization from creeping back in (the protective rail is not a monument).
**Frontend + docs only** — no Python changed (pytest **819** unaffected); QA surface **165/165 API + 727/727 FE, 0
uncovered**; help `HELP-DOCS-SYNCED → 230`. **Headed-verified, no egress** (`.local/visual/drive_inc229_concentration.py`
— 4 signals, **0 geography + 0 gender/identity-disclaimer mentions anywhere**, the ⚠ low-coverage flag intact; 0
console/page/genai). Notes: `INCREMENT-230-NOTES.md`. **NEXT:** genuinely moving on — the design-gated **B-items** (B2
collaboration, B3 OCR, B4 citation-context classifier, B5 mobile), each its own brainstorm + the maintainer's pick.

Earlier — increment 229 (a values rework of the citation-equity panel: **removed the
people-categorizing geography signal + all gender framing — rejected on principle — renamed it "Citation
concentration," + folded in a low-coverage flag**). **The maintainer caught it, and CC reached the same conclusion
independently:** a citation tool *cannot* measure who is under-cited by sorting cited authors into a group, because
that re-inscribes the very category the bias runs on — **"pushing people into categories to make them easy to see has
the same problem as pushing categories onto people to make them more difficult to be seen"** (the maintainer). The
inc-227 SP1 design had congratulated itself on rejecting name→gender inference, then shipped the **identical move on a
different axis**: the **geography ("Global South spread") signal** classified every cited author's
country-of-affiliation into a hardcoded `GLOBAL_NORTH` binary (and country-of-affiliation isn't even origin — a
Nigerian scholar at MIT coded "US"). So it's removed too, and the gender module is reframed from "deferred" to
**dropped, rejected on principle** (no gender code ever existed; the *framing* kept the rejected idea alive). The
surviving **4** signals — self-citation, reliance-on-highly-cited (Matthew), venue concentration, **institutional
concentration** — measure only **deference to concentrated power/prestige: the shape of WHAT is cited, never WHO wrote
it.** (Institutional concentration *stays* on the maintainer's call — surfacing Ivory-Tower over-emphasis is a power
*structure*, not a person's identity; it's the through-line for the whole set.) **SP2 Find overlooked work is
untouched** (it categorizes no one — a local topical embedding cosine). Removed `_geography` + `GLOBAL_NORTH`;
`integrations/openalex/adapter.py::_meta_from_work` **no longer even extracts `country_codes`** (rule #5 + making the
"we don't look at nationality" stance real at the data layer); a static guard test now forbids
`country_code`/`GLOBAL_NORTH`/gender/race/sex keying in the analyzer. Renamed the METHODS panel → **"Citation
concentration"** + scrubbed the intro/howto/note/help/spec; the API path keeps the historical
`/methods/citation-equity/*` slug (internal, not user-visible). **Also folded in the inc-227 experience-pass
low-coverage flag:** `_coverage()` (the single chokepoint every signal calls) now returns a frozen
**`Coverage{text, fraction}`** (`.low` < `LOW_COVERAGE = 0.5`; the *effective* fraction — `with_data/total` else
`resolved/total`), `SignalView.coverage: Coverage` is a type change → **zero call-site churn**, `to_dict` + the router
`SignalModel` emit additive `coverage_fraction`/`low_coverage`, and the frontend shows a **⚠ low coverage (N%)** amber
badge (`--flag-*`, rule #8) — the number stays shown. **Principles gate (rule #9) — aligned** (#2 signal-not-verdict,
#4 confidence shown, #7 no composite; the A-A no-accusation veto honored *structurally* — no people-categorization
remains, enforced by a guard test). **No migration / new dependency / audit-gate trigger** (egress posture unchanged
+ *narrowed* — less data extracted). pytest **819 passed, 1 skipped** (net 0: removed the geography test, added the
low-coverage test; `test_no_people_categorization_in_core` + the strengthened static guard now pin the stance);
`ruff` + `format` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 165/165 API + 727/727 FE, 0
uncovered** (`route_51` rewritten — 4 signals, a no-people-categorization veto incl. geography); help corpus →
"Checking citation concentration" + the canonical spec carries a SUPERSEDED banner (`HELP-DOCS-SYNCED` → 229).
**Headed-verified, no egress** (`.local/visual/drive_inc229_concentration.py` — Run audit → **exactly 4 signals, 0
geography/Global-South mentions anywhere**, all flagged **⚠ low coverage (30%)** with their numbers still rendered, the
never-categorize-people note; 0 console/page/genai). Notes: `INCREMENT-229-NOTES.md`. **NEXT:** the design-gated
**B-items** (B2 collaboration, B3 OCR, B4 citation-context classifier, B5 mobile) — each its own brainstorm + the
maintainer's pick; the last open #25 follow-up (a real *field* self-citation baseline) stays deferred (needs
per-field-paper ref fetches — a cost/design call).

Earlier — increment 228 (citation-equity SP2 — the topical overlooked-work remediation; "hell
yes!!!!!" → completes backlog #25). The SP1 panel (inc 227) literally promised it; this is it. **Find overlooked work**
(a separate, opt-in button on the Citation equity panel) surfaces **topically-relevant work a paper's reference list
OMITS** — candidates the author may have missed — ranked by callosum's **own local** scientific-paper embedding cosine,
each with an inspectable "why" (the labeled cosine + shared OpenAlex concepts) + its abstract, and a one-click
**metadata-only add**. **The A-A veto lines are honored STRUCTURALLY, not by prose:** there is **no "drop this
citation" path** (only surface/add); the reason is **topical relevance, never an author's identity** (no identity is
read/computed/shown — equity improves as a *byproduct* of better scholarship); **no quota/tokenism** ("work you may
have missed," never "add N to hit a target"); ranked by **topical cosine, never citation count** (which would amplify
the very Matthew effect SP1 measures). Via AskUserQuestion the maintainer chose **SPECTER-class scientific embeddings**
+ a **union candidate pool**. **Embedding decision (the aligned alternative, flagged):** **SPECTER v1**
(`sentence-transformers/allenai-specter`) through the *existing* sentence-transformers stack → **NO new dependency**
(only a ~440MB model download on first use, like MiniLM; tests/headed inject a fake deterministic keyword model so CI
never downloads it); SPECTER2 (needs the `adapters` lib) / SciNCL are documented swaps. **Candidate pool = union:** the
focal paper's OpenAlex **`related_works`** ∪ a **field sample** (its `primary_topic`), minus the **already-cited**
(`fetch_referenced_works`) + the focal itself. **Rides the audited OpenAlex client** — `_meta_from_work` extended
additively (+`related_works` [bare `W…` ids, capped `MAX_RELATED`] + `concepts` [top 8 display_names]; existing callers
ignore the new keys); new `fetch_works_by_ids` (one batched `?filter=openalex_id:W1|W2|…`, each id `^W\d+$`-validated
**before** the request → no SSRF, cached `byids:<sha>`, fail-closed) + `fetch_topic_candidates` (the topic sample WITH
abstract, sharing the `field:<id>` cache via a shared `_field_sample_body`); the candidate abstract via the existing
`_reconstruct_abstract`, kept on a `_meta_with_abstract` (out of the base `_meta_from_work` — too big for 500 refs).
New **pure** ranker `methods/overlooked_work.py` (`rank_overlooked` — numpy unit-cosine `cand_u @ focal_u`, `threshold=0.55`
floor [below it = *not shown*, no fabricated relevance], `top_k=12`; `OverlookedCandidate{openalex_work_id, doi, title,
authors, year, venue, match, shared_concepts, abstract, in_library}` + `to_dict`; the "why" = focal ∩ candidate
concepts; bounded `MAX_CANDIDATES=1000`, rule #4). A **2nd** async endpoint on `routers/citation_equity.py`
(`POST/GET /methods/citation-equity/overlooked` + `app.state.overlooked_jobs` JobStore + `_overlooked_model(app)`
[lazy-cached SPECTER; injected `embedding_model` wins]; the worker: `fetch_work_csl` focal title+abstract +
`fetch_work_meta_for` for `related_works`/topic → pool → exclude cited+focal → `fetch_works_by_ids` /
`fetch_topic_candidates` → `rank_overlooked` → mark `in_library` via `find_existing_paper_by_identity`;
report `{candidates, pool_size, considered, shown, field_topic}`; 404/422; fail-closed). **Add = metadata-only**
`POST /discovery/save` (`imported_source="discovery-import"`, deduped, **NO PDF fetch** → the OA lane untouched, no
paywall circumvention [A-A veto]). Frontend (`08b_methods_citation_equity.jsx`, +`OverlookedWork`/`OverlookedCard`):
the **Find overlooked work** button → ranked candidate cards (a **topical-match** chip + the shared-topics **why** +
an abstract `<details>` + an **Open ↗** external link + **＋ Add to library** / **✓ in library**) + a framing line +
an honest coverage/empty state. **Local embedding — only DOIs/W-ids + the topic id leave** (the OpenAlex fetches); the
focal+candidate **title+abstract** is embedded **locally**; **NOT** the Gemini library-text gate. **No migration, no
new dependency.** Audit = **addendum** to `.claude/security-audits/2026-06-30_citation-equity.md` **PASS** (SSRF-safe
ids/topics, metadata-only add, bounded, fail-closed, public-metadata-not-Gemini-gate). **Principles/A-A — aligned**
(the inc-156-suggest / inc-185-relevance class; the veto lines structural — no drop path, identity never the reason,
no quota). **Experience pass (rule #11, conscientious-author persona) — fixed-cheap in-increment:** the candidate
**abstract** (the backend already fetched it for ranking then *discarded* it — plumbed through `OverlookedCandidate` →
the card toggle, the highest-value cheap fix: read-before-add); an **Open ↗** external link; **＋ Add → ＋ Add to
library** / **✓ added → ✓ in library** relabels (clearer affordance); a "topical match" chip + the relevance-floor
caption ("only clearly-relevant matches, cosine ≥ 0.55, are shown"). **Rule #1:** all touched files under cap
(`methods/overlooked_work.py` 119, `routers/citation_equity.py` ~290 → re-measure before the next addition there,
`js/08b_methods_citation_equity.jsx` 255). pytest **819 passed, 1 skipped** (+10 `tests/test_overlooked_work.py`,
hermetic — a fake deterministic keyword embed model + a fake OpenAlex fetcher: the additive `_meta_from_work` keys,
`_meta_with_abstract`, `fetch_works_by_ids` [batch/validate/fail-close]; the ranker [order/threshold/shared-concepts/
no-identity]; the endpoint [produces candidates, excludes already-cited, 404/422, empty-state, unknown-job-404]);
`ruff check` + `format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface 165/165 API +
727/727 FE, 0 uncovered** (`route_51_methods_citation_equity.md` extended — overlooked step + the no-drop/no-identity/
no-quota/in-library-marked/metadata-only-add veto assertions); help corpus's "Checking citation equity" gained a
"Find overlooked work" paragraph (`HELP-DOCS-SYNCED` → 228). **Headed-verified, no egress**
(`.local/visual/drive_inc228_overlooked.py` — fake OpenAlex + fake embed model injected, empty `CALLOSUM_LIBRARY_DIR`:
**Find overlooked work** → 3 candidates, each a match chip + abstract toggle + Open ↗, the in-library one ✓-marked,
the off-topic "Plant cell biology" excluded below the 0.55 floor, **＋ Add to library** → the candidate lands in
`/papers`; 0 console/page/genai). Notes: `INCREMENT-228-NOTES.md`; spec
`.claude/docs/future-tracks/opus4.8_future-tracks_citationequitytool.md`; plan
`.claude/plans/would-you-mind-reading-wise-peacock.md`. **This completes the citation-equity track #25 (SP1 inc 227 +
SP2 inc 228).** **NEXT:** the design-gated **B-items** (B2 collaboration, B3 OCR, B4 citation-context classifier, B5
mobile) — each its own brainstorm + the maintainer's pick; or backlogged from the SP1 experience pass (a real *field*
self-citation baseline; a prominent low-coverage flag).

Earlier — increment 227 (citation-equity audit, SP1 — backlog #25; "let's pull something cool and
exciting from the backlog"). A new **Citation equity** METHODS panel: an **identity-agnostic, structural** audit of a
library paper's reference list (its OpenAlex `referenced_works`), shown against a sample of the paper's **field** (its
OpenAlex `primary_topic`). The project's own spec had the load-bearing design settled — **structural, not name→gender
inference** (which is cis-normative, >43% wrong for non-Western names, and crosses the no-accusation veto); the gender
module stays **deferred + absent**. Via AskUserQuestion the maintainer chose **"Full + field baseline"** (the maximal
slice). **5 descriptive signals** — self-citation (King et al. 2017), reliance on highly-cited work (Matthew; Merton
1968 / Perc 2014), venue + institutional concentration, geographic / Global-South spread — each carrying its **list
value**, the **field value**, an **inspectable basis** (the exact refs/venues/countries), and an honest **coverage**
count (a reference with no affiliation data is *unknown*, never assumed domestic). **Never a score / verdict / target /
accusation** (#2/#7); the field value is *context for you to interpret*. **Rides the audited OpenAlex client** — no new
host/dependency/migration: `_meta_from_work` extended (additively — venue/issn/institutions/country_codes/primary_topic
from the cached raw blob; existing gap-finder/citation-count callers ignore the new keys); new `fetch_field_sample`
(cached `field:<id>`; `topic_id` validated `^T\d+$` **before** any request → no SSRF; one query per audit) +
`fetch_work_meta_for` (the focal `primary_topic` from the already-cached by-DOI fetch — no extra HTTP). New pure
analyzer `methods/citation_equity.py` (a documented `GLOBAL_NORTH` ISO-2 set; **no gender/race code path** — proven by
test: injecting `gender`/`sex`/`race` into inputs changes nothing) + an async endpoint `routers/citation_equity.py`
(`POST/GET /methods/citation-equity/run`, the `citation_counts.py` JobStore scaffold; POST validates 404/422; the
worker resolves focal → topic → `referenced_works` → per-ref `fetch_work_meta` [progress] → field sample → audit) —
**ephemeral, no table/migration**. New METHODS panel `08b_methods_citation_equity.jsx` (order 35, among the real tools;
a **Run audit** button — user-initiated egress, not auto-run; the 5 signal rows with a `This list` vs `Field` mini-bar
+ summary + expandable basis + coverage; the credit block [King/Merton/Perc, ＋ add to library]; the deferred-module
note); the inc-163 **citation-equity placeholder removed** from `09_placeholders.jsx` (the inc-163/205 convention).
Egress = **public bibliographic metadata** (DOIs + a topic id), **NOT** the Gemini library-text gate. **Audit
`.claude/security-audits/2026-06-30_citation-equity.md` PASS**; **Principles aligned** (the statcheck/p-curve class +
value A8 access-equity; the A-A veto-level no-accusation boundary honored *structurally* — descriptive,
identity-agnostic, no target/quota/per-author label). **Experience pass (rule #11, conscientious-author persona) —
fixed-cheap in-increment** (two HIGH, charter-relevant): a neutral **"context, not a target; neither direction is a
verdict"** bar caption (the undirected bars otherwise implied higher=worse uniformly); a **"descriptive count, no field
baseline, not a judgment"** anchor on the baseline-less self-citation %; a **"mirror, not a report card — never drop a
relevant citation or add one to hit a number"** how-to (closes the SP1 diagnostic-only dead-end + bakes in the SP2 veto
framing); the geography **label** led with "affiliation outside high-income economies" (Global South kept as the
in-summary gloss + the full country breakdown); an egress reassurance at Run. pytest **809 passed, 1 skipped** (+14
`tests/test_citation_equity.py`, hermetic via an injected fake OpenAlex: the additive parser keys + `fetch_field_sample`;
each of the 5 signals; **no-identity-inference proven 2 ways**; the async endpoint [run→report, 404/422,
no-referenced-works→graceful, field-absent→own-shape, unknown-job→404]); `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5); **QA surface 163/163 API + 723/723 FE, 0 uncovered** (`route_51_methods_citation_equity.md`);
help corpus gained "Checking citation equity" (`HELP-DOCS-SYNCED` → 227). **Headed-verified, no egress**
(`.local/visual/drive_inc227_citation_equity.py` — fake OpenAlex injected: open the section → **Run audit** → 5 signals
+ the field attribution ("24 recent Decision neuroscience papers") + the geography country-breakdown basis + the
deferred note + credit; 0 console/page/genai). **Rule-#1:** all new files under cap (`citation_equity.py` analyzer ~292,
`routers/citation_equity.py` 166, `js/08b_methods_citation_equity.jsx` 178). Notes: `INCREMENT-227-NOTES.md`; spec
`.claude/docs/future-tracks/opus4.8_future-tracks_citationequitytool.md`. **NEXT — SP2:** the topical **overlooked-work
remediation** (surface relevant work the reference list omits, with a why-this-substitute trail; needs local embeddings
+ an OpenAlex candidate pool — reuses this audit's field machinery; its own audit + Principles pass). Also backlogged
from the experience pass: a real *field* self-citation baseline, and a prominent low-coverage flag.

Earlier — increment 226 (per-identifier re-fetch 🔎 for PMID + arXiv). The maintainer asked to
"add search to the other options under identifiers, like how DOI has the little search icon," and (via
AskUserQuestion) chose **re-fetch metadata from that source**. So the Details → Identifiers 🔎 (DOI → Crossref
re-resolve, inc 49) is **generalized to PMID** (→ PubMed via OpenAlex) **and arXiv** (→ the synthesized arXiv DOI
`10.48550/arXiv.<id>` via OpenAlex); **ISBN/ISSN/Cite-key stay plain** (no per-paper source). **The whole non-DOI
path reuses what already exists** — `OpenAlexClient.fetch_work_csl(conn, PaperRef(...))` (the inc-217 enrich client,
already audited) + the inc-49 force-overwrite primitive (`_paper_values_from_csl` + `update_paper_metadata`) — so
**no new external host / fetch path / dependency / migration**. New `enrich_paper_metadata_from_identifier(conn,
paper_id, *, source, openalex_client, force)` (`enrichment.py`): builds the ref (`PaperRef(pmid=…)` / `PaperRef(
doi="10.48550/arXiv.<id>")`), `setdefault`s the clicked identifier back onto the resolved CSL (the projector replaces
`csl_json` wholesale and `_csl_from_work` doesn't echo the arXiv id → the source id is never silently dropped), then
overwrites with `imported_source="openalex"` (a new `OPENALEX_SOURCE` added to the `_can_update_from_crossref`
allowlist → resolved+updatable like crossref, never protected like user-edited); a fetch miss → no overwrite
(`status="unresolved"`, graceful 200). **`POST /papers/{id}/re-resolve`** gains an allowlisted `source:
Literal["crossref","pmid","arxiv"] = "crossref"` (default keeps the DOI 🔎 byte-for-byte + back-compat with the
no-body POST); `crossref` → the existing 422-if-no-DOI + `enrich_paper_metadata_from_crossref`; `pmid`/`arxiv` →
read the identifier from `csl_json` (**422 if absent**) + the new fn with `force=True` (the user's explicit "re-fetch
from *that* source" intent — mirrors the DOI 🔎; the inc-174 user-edited confirm guard still gates in the UI). Both
branches keep the inc-224 `auto_check_retractions` + the `conn.commit()` + return `_detail_for`. **Forced rule-#1
split** (papers.py was at the **600** cap): the enrichment-action endpoints (`reresolve_paper` + `fill_metadata` +
`FillMetadataResponse` + `_crossref`) → new **`routers/paper_enrich.py`** (113; imports `PaperDetailResponse`/
`_detail_for` from papers.py → no cycle; included **before** `papers.router` so the literal paths keep winning) →
papers.py **598→528**. Frontend (`25_detail.jsx`): `DoiRow` → generic **`IdentifierRow`** (input + 🔎 + the inc-174
confirm guard + a per-row in-flight state via `resolving === source`) used for DOI/PMID/ArXiv; `reresolve(source)`
posts `{source}` + the success note reflects the source. **Egress = public bibliographic metadata** (DOI/PMID out;
SSRF-safe constant host + bound path), **NOT** the Gemini library-text gate. Audit = inc-226 **addendum** to
`.claude/security-audits/2026-06-30_metadata-enrich.md` **PASS** (reuses the audited client; force-overwrite is the
user's intent; identifier preserved; 422/miss negative paths). **Principles non-triggering** (bibliographic facts,
the inc-49/217 posture). pytest **795 passed, 1 skipped** (+4 `tests/test_papers.py`, hermetic via an injected fake
OpenAlex: PMID overwrite via OpenAlex; arXiv synthesized-DOI; miss-graceful; 422-when-absent); `ruff check` +
`format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5); **QA surface unchanged 161/161 API +
719/719 FE, 0 uncovered** (the `source` param rides the existing `/re-resolve`; noted on `route_30_detail_pane.md`);
no help-corpus change (the editing section is general; `HELP-DOCS-SYNCED` stays at 221). **Headed-verified, no egress**
(`.local/visual/drive_inc226_identifier_resolve.py` — fake OpenAlex injected: the PMID + ArXiv rows each show a 🔎,
clicking the PMID 🔎 re-fetches → title "Resolved by OpenAlex" + `imported_source == "openalex"` + PMID preserved;
0 console/page/genai). **Rule-#1:** `routers/papers.py` **528**, `routers/paper_enrich.py` **113**, `enrichment.py`
**450**, `js/25_detail.jsx` **583** — all under cap (`clustering/my_publications.py` ~594 now the closest backend
file). Notes: `INCREMENT-226-NOTES.md`. **NEXT:** the genuinely-clean autonomous partials are done; what remains is
decision/design/destructive/infra-gated (the #4 cancel + SQLite concurrency pass, etc.) or the design-gated B-items
(B2/B3/B4/B5) — each the maintainer's call.

Earlier — increment 225 (progress ETA on long async jobs — #4's close-out; the 3rd + final of
the "wrap up the partially-completed backlog items" session). Long jobs showed determinate "X / N" (inc 142) but
no time estimate. Added a rough **"~Ns left"** ETA, additive + no transaction risk: `Job.started_at` (monotonic,
stamped on `mark_running` and **preserved across every `mark_progress`** via a `_started_at` helper, so the elapsed
clock is continuous, not reset each tick) + **`Job.eta_seconds()`** (`elapsed / current × remaining`; None until
there's a `started_at` + ≥1 unit of progress, 0 once complete — computed at status-read time, so a method on `Job`
not a stored field). Surfaced as an additive `eta_seconds` on `JobProgressOut` (the shared `_progress_out(job)` →
**scan / watched-rescan / import / enrich** at once) + the `CitationRefreshProgress` mirror; rendered as
" · ~Ns left" by `ProgressBar` (a hoisted `_fmtEta` → "45s"/"3m"/"2h") + the `10b_libmenus.jsx` Citations/Enrich
menus. **Cancel is OUT of scope** — correct cooperative cancellation needs the four `_run_*_job`
single-`engine.begin()` blocks split into per-item transactions (the **same infra as the open SQLite read-then-write
concurrency item**); deferred to that pass (recorded in the backlog). **Additive** — no migration/egress/endpoint/
dependency, **no audit/Principles trigger**; **QA surface unchanged 161/161 API + 719/719 FE, 0 uncovered** (an
optional field on existing status payloads, no new route/element). pytest **791** (+2 `tests/test_job_store.py`:
`started_at` stamped-once-and-preserved-across-ticks; `eta_seconds` extrapolates / None-without-progress /
0-when-complete). **Verified three ways:** unit (above) + a **live-import API probe** (a real slowed import's
`GET /library/import/{id}` payload carries `progress.eta_seconds` decreasing 2→2→1→…→0 across the embed phase →
proves Job → JobProgressOut → endpoint) + **headed, no egress** (`.local/visual/drive_inc225_progress.py` → the
import modal's ProgressBar renders **`Embedding papers — 3 / 8 · ~2s left`**; 0 console/page/genai). **Harness note
(carry forward):** the inc-142-derived progress driver had **drifted** (even `drive_inc142_progress.py` failed) —
the inc-160 on-launch auto-rescan pulled the real 77-PDF `library/` into the seeded DB, and `seed()` didn't clean
the inc-219 `-wal`/`-shm` sidecars → stale rows survived across runs → DOI-collision "N failed" imports; both fixed
in the inc-225 driver (set an empty `CALLOSUM_LIBRARY_DIR`; unlink the sidecars). `ruff` clean; frontend rebuilt; no
help-corpus change (`HELP-DOCS-SYNCED` stays at 221). Notes: `INCREMENT-225-NOTES.md`. **This completes the
"wrap up the partials" session (inc 223 priority tiebreak + 224 retraction on-import + 225 progress ETA).** **NEXT:**
the genuinely-clean autonomous partial remainders are now done; what's left on the partials is decision/design/
destructive/infra-gated (the #4 cancel + SQLite concurrency pass, #27 statcheck test-stat `<`/`>`, #3/#5/#9/#11/#15
SP3c/#12-13/#17/#35-Layer4) — each needs the maintainer's call. Otherwise the design-gated B-items (B2/B3/B4/B5).

Earlier — increment 224 (retraction auto-check on the remaining DOI-bearing routes — #31's
on-import-lifecycle close-out; the 2nd of the "wrap up the partially-completed backlog items" session). The
inc-134 hook `auto_check_retractions(conn, paper_ids, *, checkers)` was wired into the **scan** + **citation-import**
jobs only; it now also fires after the Crossref/multi-pass enrich on the three remaining routes where a paper
gains/corrects a DOI: the **OA-acquire job** (`routers/acquisition.py::_run_acquire_job`, inside the existing
`engine.begin()` after `import_oa_pdf`) and the per-paper **`reresolve_paper`** + **`fill_metadata`** sync handlers
(`routers/papers.py`, after enrich + before `conn.commit()`), all reusing `app.state.retraction_checkers`.
**Best-effort by construction** (the fn swallows per-paper errors → can't break the acquire/enrich). **The backlog's
"Zotero / single-PDF import paths" remainder is partly MOOT** — `import_zotero_library` has **no API route** (only
the harness/tests call it), so there's no app-state-bearing caller to hook (a hook there would be dead code, rule
#5; recorded in the audit). **No new endpoint/migration/external-fetch-type/dependency** (reuses the inc-131
Crossref+OpenAlex+RW-mirror checkers + their already-audited public-DOI-metadata egress, **NOT** the Gemini
library-text gate) → audit = **addendum 2** to `.claude/security-audits/2026-06-26_retraction.md` **PASS**;
**Principles non-triggering** (reuses the established retraction FACT producer; no new claim type; no-accusation
boundary intact). **Rule-#1:** the three hooks + the import pushed `routers/papers.py` to **exactly 600** → condensed
the two new hook comments to one line each → **598** (now the closest backend file to the cap — split before the
next addition there); `acquisition.py` 148. pytest **789** (+3 hermetic `tests/test_retraction.py`:
`test_reresolve_auto_checks_retraction` [graceful Crossref fetcher + fake checker keyed on the DOI],
`test_fill_metadata_auto_checks_retraction` [empty `EnrichmentRegistry` → no fetch], `test_oa_acquire_auto_checks_retraction`
[monkeypatched `build_default_registry`/`download_oa_pdf` + a real minimal fitz PDF] — each flags a seeded retracted
DOI; a clean DOI gets no FACT); `ruff` clean; **QA surface unchanged 161/161 API + 719/719 FE, 0 uncovered** (the
behavior rides existing routes; `route_39_retraction.md` gained an on-import-lifecycle standing assertion); no
help-corpus change (`HELP-DOCS-SYNCED` stays at 221). Notes: `INCREMENT-224-NOTES.md`. **NEXT (this session):** inc
225 — progress ETA (#4). See the session plan `.claude/plans/would-you-mind-reading-wise-peacock.md`.

Earlier — increment 223 (the "By priority" sort gains a within-tier recency tiebreak — the
first of a "wrap up the partially-completed backlog items" close-out session, cheapest-first). Experience-pass
finding #4 (inc 220): the **"By priority"** library sort (high→normal→low→unset) tiebroke only on the global
`papers.id ASC` tail, so the large **unset** tier collapsed into one undifferentiated oldest-imported-first block.
Fix = a **one-line** ORDER-BY append at `app/backend/persistence/repository.py:107` —
`"priority": [_PRIORITY_RANK.asc(), papers.c.id.desc()]`; `id DESC` is the recency proxy `"recent"` (`:92`) already
uses, so within each priority tier the most-recently-added papers come first, and the global `papers.id.asc()` tail
(`:113`) stays as the deterministic pagination tiebreak (redundant-but-harmless after a unique-id DESC). **A
user-chosen sort, never an AI rank** (the inc-207 declined-ratings posture). **Backend-only** — no
migration/egress/endpoint/dependency, **no audit/Principles trigger**. pytest **786** (+1
`tests/test_papers.py::test_priority_sort_recency_tiebreak_within_tier` — two high + two unset papers →
`[high-new, high-old, unset-new, unset-old]`; the existing one-per-tier test still holds); `ruff` clean; **QA
surface unchanged 161/161 API + 719/719 FE, 0 uncovered**; no help-corpus change (`HELP-DOCS-SYNCED` stays at 221).
Notes: `INCREMENT-223-NOTES.md`. **NEXT (this session):** inc 224 — retraction on-import/on-enrich for the
DOI-bearing paths (OA-acquire + reresolve + fill-metadata, #31); then inc 225 — progress ETA (#4). See the
session plan `.claude/plans/would-you-mind-reading-wise-peacock.md`.

Earlier — increment 222 (split `15_axes.jsx` 614→395 — the axis-card subsystem →
`15b_axis_card.jsx`; clears the **last over-cap file**, so the tree is fully under the 600-line cap). A
**behavior-preserving** refactor (no feature), the standing rule-#1 split the maintainer picked: `15_axes.jsx` had
been **614** since inc 211/212's curated-axis work (the footers had mis-noted it). Extracted the **axis-card rendering
subsystem** verbatim → new **`js/15b_axis_card.jsx`** (224): **`AxisItem`** (the one-axis card — header + the
re-score/curated branches + the member list `renderPapers`, 166 lines) + its presentational helpers
(`axisConfidenceLabel`/`AxisTierBadge`/`AxisPaperRow`/`AxisCutoffFlipper`/`_tierRank`). `15_axes.jsx` (**395**) keeps
`MyPubsPrompt` + **`AxesPanel`** (the container — state, loaders, all the handlers
[score/remove/confirm/dropPaper/reorderToIndex/freeze/convertToKeyword/createCurated/bulkDelete/openMerge/…],
sort+filter, and the edit/merge/suggest modals) + the `registerPaneTab` registration. **The load-bearing detail —
the cross-chunk function hoist:** the chunks concatenate into one esbuild IIFE, so top-level `function`
declarations hoist across chunk boundaries — `AxesPanel` (textually *before*, in `15_axes.jsx`, which sorts before
`15b`) renders `<AxisItem/>` (in `15b_axis_card.jsx`) regardless of load order (the inc-208 `10b_libmenus.jsx` /
inc-182 `30c_frame.jsx` precedent; esbuild's DCE keeps `AxisItem` since `AxesPanel` references it). The cut was done
by a **deterministic line-range script** with per-function boundary assertions (no transcription of the 166-line
`AxisItem`). **Frontend-only** — no Python/migration/endpoint/egress change, so **no audit/Principles trigger** (a
pure refactor). **Behavior-preservation proven the inc-221 way** — the existing axis drivers ran **GREEN before and
after** the move: `.local/visual/drive_inc212_dragreorder.py` (the curated `AxisItem` path — `AxisPaperRow` + the ⠿
grip + HTML5 drag-reorder + persists-across-reload) + `.local/visual/drive_inc204_hide_uncertain.py` (the keyword
path — the re-score row + `AxisCutoffFlipper` + `AxisTierBadge` + the 👁 hide-uncertain toggle + the manual member),
0 console/page/genai each. (`drive_inc211_curated.py` is **stale** — it still clicks the ↑/↓ "Move down" buttons inc
212 replaced with drag; `212` is its current replacement.) pytest **785** unchanged (frontend-only;
`test_frontend_assembly` 5/5 confirms `callosum-app.html` is in sync + `15b_axis_card.jsx` is in the assembly);
`ruff check` + `ruff format --check` clean; **QA surface 161/161 API + 719/719 FE, 0 uncovered** (`route_15_axes.md`'s
`fe:` claim gained `15b_axis_card.jsx`, reclaiming the 36 moved FE surfaces); no help-corpus change (no user-facing
behavior change → `HELP-DOCS-SYNCED` stays at 221). **Rule-#1:** `15_axes.jsx` **614 → 395**, `15b_axis_card.jsx`
**224** — both under cap; **the tree is now fully under the 600-line cap** (closest: `js/10_pdf_layer.jsx` 581,
`js/30_viewer.jsx` 580, `clustering/my_publications.py` ~594). Notes: `INCREMENT-222-NOTES.md`. **NEXT:** the standing
rule-#1 backlog is empty; the remaining work is the design-gated **B-items** (B2 collaboration, B3 OCR, B4
citation-context classifier, B5 mobile) — each its own brainstorm + the maintainer's pick.

Earlier — increment 221 (the 40_app.jsx god-component split + the read/priority filter facet;
the maintainer chose "do the proper split first"). `40_app.jsx` had been pinned at the 600-line cap for 10+
increments, and the inc-220 read/priority **filter facet** (the experience-pass persona-blocking gap) needed
headroom there. Extracted the **library-list subsystem** (filter/query/list-fetch state, pagination, the bulk +
trash + view-filter actions, saved searches, the statcheck/retraction "N flagged" chips + the findings overview,
the watched-folder rescan, the p-curve/merge modal state) into a new **`useLibrary(opts)`** hook
(`js/03_library.jsx`, 351). App keeps the shell + cross-cutting state (selection, tabs, modals, focus) and spreads
the hook's `libraryBits` into LibraryFrame; the hook returns the handful App's paneCtx/modals need. **`40_app.jsx`
599 → 212.** **The load-bearing detail — the focus↔library circular dependency:** `useFocusMode.onEnterClearFilters`
must clear the library view filters, while the library's filter/merge actions call `cancelFocus`/`setAxisRefresh` —
but `useFocusMode` is declared *after* `useLibrary` (cancelFocus must exist first). Broken with two refs
(`cancelFocusRef`/`setAxisRefreshRef`, resolved in the render body after `useFocusMode`) + wiring focus's
`onEnterClearFilters` to the hook's `clearViewFilters` (so `39_focus.jsx` is untouched; `axisRefresh` stays owned by
useFocusMode). **Then** the deferred (inc-220, persona-blocking) read/priority **FILTER facet** landed: header
**Read** (all/unread/read) + **Priority** (all/high/normal/low) dropdowns (`10_pdf_layer.jsx`) → `libraryReading`
state in the hook → the `read_status`/`priority` `GET /papers` query params (already shipped inc 220); live-library
only (guarded `!trashView`); user facets, never a score. **Frontend-only** — no Python/migration/endpoint/egress
change (the backend read/priority + filter params + sorts are inc 220), so **no audit/Principles trigger** (a
refactor + a user-facet filter). **Behavior-preservation was verified by a baseline regression driver
(`.local/visual/drive_inc221_library.py`) run GREEN on the PRE-refactor code, then GREEN after** the extraction +
the facet (14/14: load / search+clear / sort / item-type filter+clear / Trash toggle+back / saved-search
save→reopen→delete / bulk-select / + the read/priority facet [Unread→5, High→1, clear→6]; deterministic 3/3, 0
console/page/genai) — the discipline for a god-component refactor with no pytest coverage (the build [esbuild] +
`test_frontend_assembly` catch scope/sync errors). The driver harness: own free port + own seeded DB (with
WAL-sidecar cleanup) + an empty `CALLOSUM_LIBRARY_DIR` (so the on-load auto-rescan doesn't scan the real library) +
`window.prompt` stubbed for the saved-search name. pytest **785** unchanged (frontend-only; `test_frontend_assembly`
confirms `callosum-app.html` is in sync); `ruff` clean; **QA surface 161/161 API + 719/719 FE, 0 uncovered**
(`route_50` gained a filter-facet step; the 2 new dropdowns are claimed via `10_pdf_layer.jsx`); help corpus's
read/priority section now covers filtering (`HELP-DOCS-SYNCED` → 221). **Rule-#1:** `40_app.jsx` **212**,
`03_library.jsx` **351**, `10_pdf_layer.jsx` **581** — all under cap; `15_axes.jsx` is **614 (>600, pre-existing from
inc 211/212)**, the only over-cap file, a separate behavior-preserving split (untouched here). Notes:
`INCREMENT-221-NOTES.md`. **This completes Bella's reading-workflow thread** (reading queue inc 219 + read/priority
markers inc 220 + the filter facet inc 221). **NEXT:** the standing `15_axes.jsx` (614) rule-#1 split; otherwise the
design-gated **B-items** (B2 collaboration, B3 OCR, B4 citation-context classifier, B5 mobile) — each its own
brainstorm + the maintainer's pick.

Earlier — increment 220 (read/unread + priority markers; beta feedback from Bella). Two
**user-set** per-paper reading markers on each library card — a **manual read/unread** toggle (`papers.read_at`;
opening a PDF does NOT auto-mark — the maintainer's call) + a **priority** picker (high/normal/low — "a few named
levels," the maintainer's call). **Both are hand triage labels, NEVER an AI score** — the inc-207 declined-ratings
logic is load-bearing: a *star* was declined as an AI-suggestible composite that flattens a paper, but a **user-set**
priority is a personal label (never computed; shown **neutrally** — no verified-green/flag-amber/danger-red; orthogonal
to tags/axes), so it's the inc-207 color-tag class, not the declined thing. **migration 0031** (guarded ADD COLUMN +
guarded downgrade) adds both nullable columns. `routers/papers.py`: `POST /papers/{id}/read` (404 if missing) + `POST
/papers/{id}/priority` (422 off-allowlist `{high,normal,low}`/null, 404); `read_status`/`priority` filter params + a
**"priority"** sort (high→normal→low→unset) + an **"unread"** sort on `GET /papers`; `read_at`/`priority` on the
list-item + detail responses. Frontend new chunk `16b_readmark.jsx` (`ReadPriorityControl` — a read toggle + a
priority badge/popover, **optimistic** local state → zero `40_app.jsx` change, dodging its 599/600 cap) rendered in
PaperCard's foot (`10_pdf_layer.jsx`, function-hoisted, the inc-208 pattern) + the **"By priority"** + **"Unread
first"** Sort options; `styles.css` `.paper-read`/`.paper-priority`/`.priority-pop` (neutral tokens, rule #8).
**Forced rule-#1 split:** `repository.py` was **662 at HEAD** (a pre-existing violation the watch note had drifted on
at "~556"); my additions took it to 698, so the paper-lifecycle cluster (trash/purge/tier + the new setters) →
**`paper_lifecycle_repo.py`** (121) and the synthesis CRUD → **`summaries_repo.py`** (61), both **re-exported** from
`repository` (`# noqa: E402,F401`; zero call-site change — the inc-137 schema_findings pattern; `compute_processing_tier`
inlines its paper query to avoid a cycle) → repository.py **565**. **No security audit** (local columns + 2 local
endpoints; no egress/fetch/dependency — the inc-207 color-tag precedent); **Principles non-triggering** (user labels,
not claims/scores — the declined-ratings call IS the principle pass). pytest **785** (+2 `tests/test_papers.py`:
read marker set/clear + read/unread filters + the unread sort + 404; priority set/clear + filter + 422-off-allowlist +
404 + the by-priority sort); the split is **behavior-preserving** (summaries/merge/health/reading-queue green
untouched); `ruff` clean; migration head **0031** via `alembic_head()`; **QA surface 161/161 API** (+2 `/papers/{id}/read`
+ `/priority`; new `route_50_reading_markers.md`) **+ 715/715 FE, 0 uncovered**; help corpus gained "Read/unread &
priority markers" (`HELP-DOCS-SYNCED` → 220). **Experience pass (rule #11, post-import-triager persona):** capture
works but *retrieval* was half-built (you could mark but only *sort* — not *filter* — back to "what's unread/hot") →
added the **"Unread first"** sort (a cap-free interim, the persona's top fix-cheap) in-increment; the library-HEADER
**read/priority filter facet** is **DEFERRED** (it needs a `40_app.jsx` split — the file is at the 600 cap) and bumped
to persona-blocking in the backlog. **Headed-verified deterministic (5/5, 0 console/page/genai)**
`.local/visual/drive_inc220_readmark.py` (read toggle → read/unread filter; priority popover → priority filter; the
by-priority sort; the harness sets an empty `CALLOSUM_LIBRARY_DIR` so the on-load auto-rescan [inc 98/136/160] doesn't
scan the real `library/` PDFs into the seeded DB — a test-harness fix, the read_status filter itself is correct, proven
by a direct-API check + the pytest). **Rule-#1:** `16b_readmark.jsx` **62**; `repository.py` **565**; `routers/papers.py`
**593**; `15_axes.jsx` is **614 (>600, pre-existing from inc 211/212)** — a separate behavior-preserving split,
untouched here. Notes: `INCREMENT-220-NOTES.md`. **NEXT (the fast-follow):** the **`40_app.jsx` split** (extract the
library filter/query state into a `useLibrary` hook, the inc-128/167 pattern) → then the read/priority **filter
facet** (Unread / High-priority header chips) the experience pass flagged. Then Bella's thread is complete; otherwise
the design-gated **B-items** (B2 collaboration, B3 OCR, B4 citation-context classifier, B5 mobile).

Earlier — increment 219 (reading queue — the to-read "Queue" tab — + a SQLite concurrency fix;
beta feedback from Bella). A **personal, ordered to-read list** as the **third tab of the left-pane AXES section**
([Axes | Tags | Queue]) — **not** an axis (no scoring): its own **`reading_queue`** table (migration **0030**, guarded
+ no-op downgrade; `paper_id` FK CASCADE + UNIQUE → idempotent add / purge-CASCADE-drop, nullable `position` for the
manual order). New `reading_queue_repo.py` (list [trashed-excluded, position NULLS-last] / add [append, idempotent] /
remove / `set_queue_order` [validate `paper_ids` == current members else ValueError]) + `routers/reading_queue.py`
(`GET`/`POST`[404 on a nonexistent paper, `{added}` idempotent]/`DELETE`[idempotent 204 — both ✓ and × call it]/
`PUT /reading-queue/order`[ValueError→422]; reuses `papers._authors_from_csl`). Frontend `16_queue.jsx`
(`registerPaneTab` order 30): **add** by dragging a library card (`application/x-callosum-paper`, inc 206) onto the
panel **or** the Details **+ Reading queue** button; **drag-to-reorder** via a queue-only MIME
`application/x-callosum-queueitem` (inc 212) → `PUT …/order`; **✓** (read→remove) / **×** (remove); click a row opens
the paper — **two distinct drag MIMEs** so add-drag vs reorder-drag never cross-fire. `05_panes.jsx`/`25_detail.jsx`/
`40_app.jsx` wire the Details button + `paneCtx` `queueRefresh`/`onQueueChanged`; `styles.css` `.queue-*` (tokens only,
rule #8). **The non-obvious half — `database.py::make_engine` now sets `PRAGMA journal_mode=WAL` + `busy_timeout=5000`:**
the headed verification reliably hit `sqlite3.OperationalError: database is locked` — uvicorn serves sync endpoints from
a threadpool (concurrent connections to one SQLite file), and the default rollback-journal + busy_timeout=0 made a write
racing the list-refresh GET fail *immediately*; WAL (readers don't block the writer) + busy_timeout (wait, don't error)
is the standard local-SQLite-under-a-web-server pairing — a real app-wide hardening. **`BEGIN IMMEDIATE` (the cure for
the residual read-then-write upgrade-deadlock) was rejected as unsafe** here — `_run_scan_job`/embed/import wrap a
multi-minute job in **one** `engine.begin()` transaction, so grabbing the write lock up front would block all requests
for the whole job; the upgrade-deadlock is rare (a human never fires two writes in the same millisecond) and is a
**filed backlog item** for a focused concurrency pass (transaction-retry scoped to short write endpoints, or
incremental-commit jobs first). **No security audit** (a local table + 4 local endpoints; no egress/fetch/dependency —
the inc-208 saved-searches precedent); **Principles non-triggering** (a user-ordered list, no claim/score). pytest **783**
(+6 `tests/test_reading_queue.py`: add/list/idempotent/authors; trashed-excluded; remove-idempotent; `set_queue_order`
reorders + rejects-foreign; CASCADE on paper delete; the 4 endpoints incl. 404 + 422); `ruff` clean; migration head
**0030** via `alembic_head()`; **QA surface 159/159 API** (+4 `/reading-queue*`; new `route_49_reading_queue.md`) **+
706/706 FE, 0 uncovered**; help corpus gained "Reading queue (your to-read list)" (`HELP-DOCS-SYNCED` → 219). **Headed-
verified deterministic (10/10, 0 console/page/genai)** `.local/visual/drive_inc219_queue.py` (drag-add / button-add /
drag-reorder-persists / ✓ / ×; the driver synchronizes on DOM state + drains in-flight fetches between mutations, and
tolerates only the known transient queue-write lock — retried — staying strict on every other error). **Rule-#1:**
`16_queue.jsx` **107**; `15_axes.jsx` is **614 (>600, pre-existing from inc 211/212)** — the queue does **not** touch
it (a separate behavior-preserving split is a flagged follow-up). Notes: `INCREMENT-219-NOTES.md`. **NEXT (Bella's other
beta asks, queued):** a durable **read/unread marker** (distinct from the queue's ✓-removes) + **priority markers** —
likely one small migration + a library facet/sort + a card control; plus the filed **SQLite upgrade-deadlock**
concurrency pass. Otherwise the design-gated **B-items** (B2 collaboration, B3 OCR, B4 citation-context classifier, B5
mobile).

Earlier — increment 218 (metadata enrichment SP2 — Europe PMC + PubMed sources; completes the
multi-pass enricher). Two more sources join the gap-fill cascade, each one `register()` + a response mapper on an
**already-existing** client — the registry's promise (no endpoint/UI/migration/dependency change). **Europe PMC**
(`EuropePmcClient.lookup_metadata`, DOI/PMID) maps the **same cached `resultType=core` record the OA resolver already
fetches** → a CSL fragment (title/authors/journal/year/abstract/DOI/PMID), so it costs no extra request for a paper
whose OA was already checked. **PubMed** (`PubMedEnrichSource`, reusing `pubmed_provider`'s `_eutils_search`/
`fetch_abstracts`/`summary_to_item`): a known **PMID → efetch abstract only**; else a **title-search → the matched
record's** journal/year/DOI/PMID + efetch abstract, adopted **only on a conservative `_title_overlap`** (normalized-equal
or token-Jaccard ≥ 0.7 — no wrong-paper enrichment). `build_default_enrich_registry` now registers
`crossref → openalex → europepmc → pubmed`. **Purely additive** — the orchestrator's gap-merge (fill-empty-only) +
the provenance/DOI/duplicate guards + the egress posture (public bibliographic metadata, NOT the Gemini gate) are all
SP1's, unchanged, so the non-destructiveness + honesty properties hold identically. **New `app.state.enrich_registry`
seam** (default None → built from the clients): the batch worker + per-paper endpoint use it when set, which keeps the
endpoint tests hermetic now that the default cascade carries **live** Europe PMC/NCBI clients. **No new
endpoint/host/dependency/migration.** Audit **addendum** in `2026-06-30_metadata-enrich.md` **PASS** (same posture;
SSRF-safe constant hosts + bound params; PubMed title-match guard + regex-not-XML-parser abstract → no XXE;
fail-closed). **Principles non-triggering.** pytest **777 passed, 1 skipped** (+3 `tests/test_metadata_multi_enrich.py`:
the Europe PMC `core`→CSL mapper; the PubMed PMID-abstract / title-adopt / title-reject paths; the default registry is
exactly `[crossref, openalex, europepmc, pubmed]`; the two endpoint tests repointed to an injected stub registry);
`ruff` clean; **QA surface unchanged 155/155 API + 697/697 FE, 0 uncovered** (sources behind the existing
`/library/enrich/*` + `/papers/{id}/fill-metadata`); help corpus's source list now present-tense (`HELP-DOCS-SYNCED` →
218). Rule-#1: `enrich_sources.py` **216**, `europepmc/adapter.py` **161**. **This completes the multi-pass metadata
enrichment feature (SP1 inc 217 + SP2 inc 218).** Notes `INCREMENT-218-NOTES.md`. **NEXT:** the live
Crossref/OpenAlex/Europe PMC/NCBI run over the real library is the maintainer's spot-check; queued (Bella's beta ask →
backlog) reading-queue / read-unread / priority markers; otherwise the design-gated B-items (B2 collaboration, B3 OCR,
B4 citation-context classifier, B5 mobile).

Earlier — increment 217 (multi-pass, gap-filling metadata enrichment — SP1; beta feedback from
Eileen, brainstorm → plan → built). Records come in with gaps (no DOI / no abstract / blank venue) and hand-fixing
them is the chore; the old enrichment was **Crossref-only + wholesale-overwrite**. The fix: a **multi-source,
gap-filling** enricher that **fills only a paper's EMPTY fields** from a source cascade — **never overwriting a value
the user typed**, and **never downgrading** a hand-edited/merged/agent record's provenance — left as a SEPARATE path
from the unchanged force-overwrite `enrich_paper_metadata_from_crossref` (re-resolve/scan/OA-acquire/my-pubs).
**Pluggable source registry** (`metadata/enrich_sources.py`, mirroring the discovery `SourceRegistry`):
`EnrichmentSource.fetch(conn, ref) -> CSL-fragment` run in order by `EnrichmentRegistry.fetch_all` (a source that
raises is skipped); **SP1** = `CrossrefEnrichSource` (by DOI → `resolve_doi().csl_json`) + `OpenAlexEnrichSource`
(by DOI/PMID/title → new `OpenAlexClient.fetch_work_csl` + the additive `_csl_from_work` surfacing venue/abstract
[reconstructed from the inverted index]/type/PMID — existing `_meta_from_work` callers untouched). **Orchestrator**
`enrich_paper_metadata_multi`: **Pass 0** recover a missing DOI (`_doi_for_paper` PDF scan → Crossref title-search,
adopted only on a conservative `_titles_match` [normalized-equal or token-Jaccard ≥ 0.7] + compatible year, and
**only if it doesn't already belong to another paper** — `find_existing_paper_by_identity`, honoring `papers.doi`
UNIQUE + leaving dups to dedup); **then** `gap_merge` (fill-empty-only dict merge; DOI handled separately) +
`_gap_fill_columns` (project the merged CSL → only the **empty** scalar columns). **Provenance never downgraded** —
a `user-edited`/`merged`/`ai-agent` paper keeps its `imported_source` (only its blanks fill), which is *why* the batch
can safely run over **all** live papers (the maintainer's chosen scope), not just the `_can_update_from_crossref`
allowlist; a `pdf-scaffold`/null paper that got enriched → `crossref`, else `crossref-unresolved`. **Controls (both,
per the maintainer):** a per-paper **Fill missing fields** (`25_detail.jsx`, beside 🔎 → `POST /papers/{id}/fill-metadata`
→ `FillMetadataResponse`) + a library-wide async batch **Enrich metadata ↻** (`EnrichMetadataButton` in
`10b_libmenus.jsx` → `POST/GET /library/enrich/refresh` in `routers/library.py`, the citation-counts JobStore shape;
worker iterates `list_live_paper_ids`; summary = papers/dois_recovered/fields_filled/still_missing_doi). New
`api.state.metadata_enrich_jobs` + `enrich_search_provider` (test seam); `metadata/__init__` re-exports
`enrich_paper_metadata_multi`/`MultiEnrichResult`. **Egress = public bibliographic metadata** (Crossref/OpenAlex —
DOI/PMID/title out), the inc-87/183/210 posture, **NOT** the Gemini library-text gate. **No migration, no new
dependency** (reuses existing clients). **Audit `2026-06-30_metadata-enrich.md` PASS** (SSRF-safe constant hosts;
gap-fill non-destructive; wrong-DOI + duplicate-DOI guards; fail-closed; public-metadata-not-Gemini-gate);
**Principles non-triggering / strengthening** (bibliographic facts; gap-fill is *more* honest than overwrite). pytest
**774 passed, 1 skipped** (+11 `tests/test_metadata_multi_enrich.py`, hermetic — stub sources + injected fake clients:
gap_merge fill-empty-only; cascade fills abstract from a later source; never-overwrite; DOI recovery
strong-adopts/weak+year-mismatch-reject; duplicate-DOI skipped; provenance preserved; scaffold → crossref-unresolved;
`_csl_from_work` mapper; the per-paper + batch endpoints; unknown job → 404); `ruff` clean; QA surface **155/155 API**
(+3 `/library/enrich/*` + `/papers/{id}/fill-metadata`) **+ 697/697 FE, 0 uncovered** (`route_48_metadata_enrich.md`);
help corpus gained "Filling in missing metadata (gap-fill enrichment)" (`HELP-DOCS-SYNCED` → 217). **Rule-#1:**
`40_app.jsx` folded back to **598**; engine in new `enrich_sources.py` (122) + `enrichment.py` (380). **Headed-verified,
no egress** (`.local/visual/drive_inc217_enrich.py`, fully offline via pre-seeded `external_api_cache`: **Enrich
metadata ↻** → the scaffold gains abstract + venue [→ `crossref`], the hand-edited paper's typed venue is **unchanged**
while its blank abstract fills [→ stays `user-edited`]; 0 console/page/genai). Plan
`.claude/backups/plans/2026-06-30_metadata-multi-enrich.md`; notes `INCREMENT-217-NOTES.md`. **NEXT: SP2 (inc 218)** —
`EuropePmcEnrichSource` + `PubMedEnrichSource` (each one `register()` + a response mapper on the existing client) +
abstract-coverage tests; the registry makes it purely additive. Also queued (Bella's beta ask → backlog): reading-queue
/ read-unread / priority markers. The live Crossref/OpenAlex run over the real library is the maintainer's spot-check.

Earlier — increment 216 (B1 SP2 — gated MCP agent writes; brainstorm → spec → plan → built inline).
The read-first MCP server (inc 213) gains **write** tools so an external agent (Claude Desktop/Cursor) can edit the
library **through** callosum: **add a tag, add a paper to an axis, save a reference by DOI, add a note** — each
**additive, reversible, `ai-agent`-stamped, and audited**, behind a **default-OFF opt-in**. The maintainer's
human-in-loop model = **review + revert after** (writes apply immediately; the agent host's native per-call prompt is
the in-the-moment gate — no elicitation, no approval queue), and **DOI-verified** `save_reference` (resolve via
Crossref, refuse the unresolvable — no fabrication). **The A4 value ("the user owns every irreversible act") is
honored structurally, not by a prompt:** there is **no delete/overwrite/merge/scan agent route**, and the MCP write
client exposes only the four write methods → an irreversible agent act is inexpressible (mirrors SP1's read-only
allowlist). **Backend:** `app_settings` gains `agent_writes_enabled` (default off; `CALLOSUM_DISABLE_AGENT_WRITES=1`
kill switch) on `GET`/`PUT /settings`; **`agent_writes`** table (`schema_findings.py` → re-exported; **migration 0029**,
guarded additive, no-op downgrade; `target_paper_id` has **no FK** so it outlives a purge) + `persistence/agent_repo.py`
(record/list/get/mark-reverted/delete_note); **`routers/agent.py`** (NEW, included after settings) = 7 endpoints —
`GET /agent/status`, the four writes (each gated by `_require_writes` → **403** when off), `GET /agent/writes`,
`POST /agent/writes/{id}/revert`. Writes stamp `imported_source="ai-agent"` (`AI_AGENT_SOURCE`, outside the
`_can_update_from_crossref` allowlist → never clobbered by a later enrich); **My-Publications axes are refused (422)**
(authorship is the user's — A-A no-accusation); **`save_reference`** dedups, else resolves the DOI via the audited
Crossref client + **422s the unresolvable**, building the paper from the resolved CSL. **Revert** dispatches per action
(tag→remove, axis→remove, reference→soft-delete *only if agent-created* [a re-found paper is left live], note→delete),
idempotent + dedup-safe. **MCP:** `mcp_server/client.py` gains `agent_status` + the four write methods; `server.py`
registers the write tools **only when `agent_status()` is true**. **Frontend:** `35_settings.jsx` `AgentSettings` (the
toggle + an activity list with per-row + Revert-all) + `.agent-activity*` CSS (tokens only); `callosum-app.html`
rebuilt. **Audit `2026-06-30_mcp-agent-writes.md` PASS** (default-off gate proven by negative path; additive+reversible
by construction; ai-agent provenance; authorship-boundary 422; bound-param SQL; DOI-verified → no SSRF, no fabrication;
local mutations + a public DOI lookup, NOT the Gemini library-text gate; no new app dependency). **A4/A-A pass ran in
the spec**; code-level **Principles non-triggering** (no new claim/signal). pytest **763 passed, 1 skipped** (+15:
`tests/test_agent_writes.py` [repo round-trip + the gated endpoints + revert dispatch + My-Pubs-422 + DOI-verify +
dedup-safe revert] + `test_settings.py` toggle + `test_mcp_server.py` write-tool registration/mapping/allowlist);
`ruff` clean; migration head **0029** via `alembic_head()`; **QA surface 152/152 API** (+7 `/agent/*`; new
`route_47_agent_writes.md`) **+ 693/693 FE, 0 uncovered**; help corpus + `mcp_server/README.md` cover the opt-in write
tools (`HELP-DOCS-SYNCED` → 216). **Headed-verified, no egress** (`.local/visual/drive_inc216_agent_writes.py` — enable
→ an agent tag-write → an activity row → Revert → the tag is removed + `reverted_at` set; 0 console/page/genai). **The
live MCP↔host write round-trip is the maintainer's manual check** (configure Claude Desktop/Cursor per
`mcp_server/README.md` with writes ON → the four write tools appear). Spec
`…/specs/2026-06-30-mcp-agent-writes-design.md`; plan (gitignored) `.claude/backups/plans/2026-06-30_mcp-agent-writes-sp2.md`;
notes `INCREMENT-216-NOTES.md`. **NEXT (the remaining backlog is design-gated B-items):** B2 collaboration/shared
libraries (≈ accounts SP4), B3 OCR, B4 citation-context classifier, B5 mobile reading — each its own brainstorm + the
maintainer's pick.

Earlier — increment 215 (PDF highlight minimap — the last close-out dreg). A thin gutter beside the
PDF page-scroller shows one tick per highlight, click-to-jump — the reading-pane bit the maintainer picked. New
`MinimapTrack({annotations, numPages, onJump})` in `js/30_viewer.jsx` (module-level, IIFE-hoisted): a `.pdf-minimap`
track with a `.pdf-minimap-tick` per annotation, positioned by **page fraction** (`top = ((page-1+0.5)/numPages)%`,
clamped) + tinted by the highlight's `color` (fallback `--flag`); each tick's title = page + note snippet; click →
`onJump(annotation)` = the inc-177 `jumpToAnnotation` (scroll-to + flash). Rendered as a flex sibling of `.pdf-scroll`
in `.pdf-body`, shown when `ready && annotations.length > 0 && !panelOpen` (**Notes panel closed** — the panel already
lists + jumps, so the minimap is its compact alternative; opening Notes hides it). `styles.css`: `.pdf-minimap`
(`flex: 0 0 14px`, `--panel-2`, `--line` border) + `.pdf-minimap-tick` (absolute `top: %`, `--radius-sm`, `--accent`
hover) — **tokens only** (rule #8; DESIGN.md gained the recipe). **Page-fraction, not pixel offset** → the minimap
never touches the fragile inc-34/35 render-core geometry (the equal-page-height approximation is honest for a nav aid;
the actual jump uses the real `[data-page=N]` scroll, so landing is exact). **No split was needed** — `30_viewer.jsx`
was **557** (inc-182's LibraryFrame extraction had relieved it; the rule-#1 "599/600 MAXED" note was stale), so the
minimap took it to **580**, under the cap. **Frontend-only** — pytest **748** unchanged (`test_frontend_assembly` in
sync; CI re-runs the full suite); no backend/endpoint/migration/egress/dependency/audit; **Principles non-triggering**
(a coordinate-honest navigation overlay — page-level, no fabricated rect). QA: `route_32_viewer_annotations.md`
extended with the minimap step; surface **145/145 API + 687/687 FE, 0 uncovered** (+2 FE = the track + tick, claimed
via `30_viewer.jsx`). **Headed-verified, no egress** (`.local/visual/drive_inc215_minimap.py` — seed a 4-page PDF + 2
highlights [p.1, p.4] → 2 ticks → click the lower tick → the p.4 highlight flashes → open Notes → the minimap hides;
0 console/page/genai). Notes: `INCREMENT-215-NOTES.md`. **This empties the autonomous close-out band** (A1–A10 closed
incs 203–212; the dregs #4/#5/minimap cleared incs 214–215). **NEXT:** the remaining backlog is **design-gated
B-items** — B1 SP2 (gated agent writes), B2 collaboration/shared libraries, B3 OCR, B4 citation-context classifier,
B5 mobile reading — each its own brainstorm + the maintainer's pick.

Earlier — increment 214 (close-out mop-up — two small autonomous "dregs" + a forced split). The
maintainer asked to clear the last cheap autonomous leftovers. **#4 — per-file scan progress:** `scan_library_folder`'s
`on_progress` callback is now `(current, total, filename)`; the scan/watched-rescan job lambdas put the basename in the
label (`f"Reading {name}"`), so the existing `ProgressBar` (which renders `progress.label — X / N`) shows
"Reading <file> — 12 / 80" for free — **no frontend change**. **#5 — first-class extra URLs:** a paper records
additional URLs beyond the primary CSL `URL` in `csl_json["extra_urls"]` (a list; the primary `URL` stays canonical) —
`paper_edits.build_paper_update` gains an `extra_urls` field (`_apply_extra_urls`; `"extra_urls"` added to
`RESERVED_CSL_KEYS` so the generic "More" passthrough can't clobber it), `PaperUpdateRequest.extra_urls` (≤50, each
≤2000) + `PaperDetailResponse.extra_urls` (read via `_extra_urls_from_csl`), and a **"More URLs"** `EditableText`
(one-per-line) in `25_detail.jsx` → `saveField("extra_urls", list)` (mirrors Authors/Translators; consistent with the
pane's other editable URL/identifier fields — clickable-link rendering deferred since the pane is an editor, not a
viewer). **The forced split (rule #1):** the `extra_urls` field pushed `routers/papers.py` to **604 (>600)**, so the
**request-normalisation cluster** (`edits_from_request` [was `_edits_from_request`] + `_norm_str`/`_clean_authors`/
`_clean_urls`/`_validate_csl_patch` + the caps constants) was extracted **verbatim** → new
**`routers/paper_edit_input.py`** (111; the inc-91/207 pattern). `edits_from_request` is duck-typed on the request
(`model_fields_set` + `getattr`) so it needn't import `PaperUpdateRequest` → **no import cycle**; `papers.py` 604→**510**
(dropped the now-unused `import re` + `RESERVED_CSL_KEYS`). **No migration / endpoint / egress / dependency / audit
trigger; Principles non-triggering** (recording fields + a behavior-preserving split, no claim/signal). pytest **748
passed, 1 skipped** (+6: `test_library_scan.py` +1 [the callback gets sorted basenames + total], `test_paper_edits.py`
+3 [extra_urls stored/cleared/reserved-against-passthrough], `test_papers.py` +2 [PATCH→GET round-trip; extra_urls
rejected via the generic `csl` patch]); ruff clean; **QA surface unchanged (145/145 API + 685/685 FE, 0 uncovered)** —
a request/response field on existing endpoints + an `EditableText` reusing already-claimed elements, no new route; help
corpus unchanged (the editing section is already general; the field is self-describing). **Headed-verified, no egress**
(`.local/visual/drive_inc214_extra_urls.py` — top paper auto-selects → Details → type two URLs into "More URLs" → blur
→ `GET /papers/{id}.extra_urls == [both]`; 0 console/page/genai). **Rule-#1:** `papers.py` 510, `paper_edit_input.py`
111, `25_detail.jsx` 529; `js/40_app.jsx` stays the closest at 599/600. Notes: `INCREMENT-214-NOTES.md`. **NEXT:** inc
215 — a **minimap/scrollbar highlight marker** in the PDF viewer (its own headed check). NB `30_viewer.jsx` is actually
**557**, not 599/600 (inc-182's LibraryFrame extraction relieved it; the rule-#1 "MAXED" note was stale), so the
planned split is **unnecessary** — the minimap fits under the cap directly. After it, the autonomous close-out band is
empty and the remaining backlog is design-gated B-items (B1 SP2 gated writes, B2–B5).

Earlier — increment 213 (B1 SP1 — the read-first MCP server; the first of the deferred B-items,
brainstormed → spec'd → planned → built). Expose callosum's own **Model Context Protocol** server so an external
agent (Claude Desktop / Cursor) uses the library **through** callosum — keeping callosum the provenance + grounding
authority — rather than bypassing it as a dumb store. **Architecture = a thin stdio adapter over the running app,
not a direct-DB reader:** new **`mcp_server/`** (a SEPARATE in-repo deployable mirroring `sync_server/` — `app/`
never imports it, it never imports `app/`; it talks HTTP). `client.py` `CallosumClient` = a thin httpx wrapper with
five **read** methods (injectable `http` for hermetic tests; `_ok` maps 401→a token hint / ≥400→a clean error;
httpx errors → `CallosumUnavailable`, never a fabricated result; `default_client()` from `CALLOSUM_BASE_URL`
[default loopback] + `CALLOSUM_MCP_TOKEN`). `server.py` `create_server(client)→FastMCP` registers five `@mcp.tool()`s
(docstrings = the agent-facing descriptions) + `build()`; `__main__.py` = `python -m mcp_server` →
`run(transport="stdio")`. **The five tools → endpoints:** `search_library`→`GET /papers`, `get_paper`→`GET
/papers/{id}`, `full_text_search`→`GET /papers/fulltext` (strips the U+E000/E001 FTS bold markers),
**`find_passages`→`POST /citations/suggest {evaluate:false}`** (the grounding primitive — each passage carries its
verbatim quote + page + `coordinate_precision`, so the agent can cite the source), `format_citation`→`POST
/papers/export`. **Read-only by construction** — `CallosumClient` exposes only those five read methods (no
write/scan/delete method exists); `test_server_only_issues_readonly_calls` drives every tool through a recording
transport and asserts only the four allowlisted `(method,path)` pairs (+ the `GET /papers/{id}` detail) are ever
issued, and `test_tool_registry_is_exactly_the_five_read_tools` pins the set. **No app change** → no migration, no
new app endpoint, **QA surface unchanged (145/145 API + 685/685 FE, 0 uncovered)**, no new QA route (the inc-157
LO-suggest-macro / inc-170 GDocs-add-on precedent — an external process reusing existing endpoints). **GOTCHA:**
this `mcp` SDK's `FastMCP.call_tool` is shape-inconsistent by return type — a non-dict return is `(content,
{"result": value})`, a **dict** return is a bare `list[TextContent]`; the test helper `_call` handles both. **New
dep `mcp>=1.2`** (justified — can't speak MCP without the SDK; **fenced** in `mcp_server/requirements.txt`, never
the app's prod deps; added to `requirements-dev.txt` only so CI runs the hermetic test). **Audit
`2026-06-30_mcp-server.md` PASS** (read-only by construction; local stdio with no listener; one configured [not
arg-derived] target → no SSRF; token write-only from env, never logged/returned; no egress of its own; honest
failures; one justified/fenced/pinned dependency; app surface unchanged). **Values gate ran in the spec**
(APPROACH-AVOIDANCE — emergent value "callosum as MCP provider", adopted deliberately; read-first carries evidence
[A2]; default-off/opt-in [A5]; SP1 mutates nothing [A4]; no A-A veto); code-level Principles non-triggering (no new
claim/signal). pytest **742 passed, 1 skipped** (+9 `tests/test_mcp_server.py`, hermetic via `httpx.MockTransport`:
the request/response mapping per tool, the auth header, honest failures [app-down/401], the read-only allowlist, the
tool registry); `ruff` clean; help corpus +1 paragraph ("Using Callosum from an AI agent (MCP)", `HELP-DOCS-SYNCED`
→ 213). **The live MCP↔host handshake is the maintainer's manual check** (configure Claude Desktop/Cursor per
`mcp_server/README.md` with callosum running → call a tool → see grounded results); what's proven in-repo is the
pure mapping + the read-only allowlist + the endpoints the tools call (covered by the main suite). Spec
`…/specs/2026-06-30-mcp-server-design.md`; plan (gitignored) `.claude/backups/plans/2026-06-30_mcp-server-sp1.md`;
notes `INCREMENT-213-NOTES.md`. **NEXT: B1 SP2 — gated writes** (`add_tag`/`add_to_axis`/`save_reference`/`annotate`,
each provenance-stamped `imported_source="ai-agent"` + reversible [session undo / soft-delete] + gated [a
writes-enabled opt-in + per-write confirmation] + an agent audit log; its own design spec + a heavy A4/A-A pass —
the A4 "user owns every irreversible act" value makes the gate mandatory). Other deferred B-items (B2 collaboration/
shared libraries [≈ accounts SP4], B3 OCR, B4 citation-context classifier, B5 mobile reading) remain larger, own
design passes.

Earlier — increment 212 (A7 SP2 — drag-to-reorder curated members; the frontend-only follow-on
that **completes A7**, and with it the **entire competitive-benchmark A-list, A1–A10**). The inc-211 per-row **↑/↓**
reorder is replaced by **HTML5 drag-to-reorder**: a curated member row shows a **⠿ grip** (`.axis-grip`) and each
`.axis-member-drag` wrapper is a drag **source + drop target** via a member-only MIME
**`application/x-callosum-axismember`** (distinct from A6's `…-paper`, so dragging a member never triggers the
card-level drop-to-add). Dropping member X onto Y moves X to Y's slot → `reorderToIndex` (splice on the current
`position` order) → **`PUT /axes/{id}/order`** (the inc-211 endpoint, reused unchanged — **no backend change**); a
`dragMemberOver` state drives a `.dragover` drop indicator (inset top `--accent` line). **Frontend-only** — `15_axes.jsx`
(↑/↓ → grip + DnD; `reorderToIndex` replaces `reorderPaper`) + `styles.css` (`.axis-grip` + `.axis-member-drag.dragover`,
replacing `.axis-reorder`). **No migration / no new endpoint / no audit / no dependency.** **Principles non-triggering**
(a reorder interaction over an existing endpoint). pytest unchanged (**733 passed, 1 skipped** — a frontend-only edit;
`test_frontend_assembly` confirms the rebuilt `callosum-app.html` is in sync; CI re-runs the full suite); `ruff` clean;
**QA surface 145/145 API + 685/685 FE, 0 uncovered** (FE −4 = the removed ↑/↓ buttons; `route_15_axes.md`'s curated
step updated to the drag mechanism). help corpus's curated paragraph now says "drag a member by its ⠿ grip"
(`HELP-DOCS-SYNCED` → 212); DESIGN.md records the grip/drag recipe. **Headed-verified, no egress**
(`.local/visual/drive_inc212_dragreorder.py` — a curated axis [Alpha,Beta,Gamma]; drag Alpha onto Gamma → [Beta,Alpha,
Gamma], **persists across a reload**; no ↑/↓ remain; 0 console/page/genai). **Rule-#1:** `js/15_axes.jsx` ends at
**562**. Notes: `INCREMENT-212-NOTES.md`. **This completes A7 (SP1 inc 211 + SP2 inc 212) and the A1–A10 list. NEXT:**
the deferred **B-items** — B1 read-first/write-gated MCP server, B4 citation-context classifier, B2 collaboration/
shared libraries, B3 OCR, B5 mobile reading — each a larger, own design pass (a brainstorm + the maintainer's pick).

Earlier — increment 211 (A7 SP1 — the Curated Axis primitive; the last A-item, brainstormed →
spec'd → planned → built, decomposed into SP1 [this] + SP2 [drag-reorder follow-on]). A **curated axis** is an axis
populated **by hand** rather than by keyword scoring — the bounded, ordered "manual container" the axis model needed,
**without becoming a folder**. **Architecture:** a curated axis is a normal `axes` row with a third **`kind="curated"`**;
its members are the existing **all-`confidence IS NULL` (manual)** rows on its single cluster node, ordered by a new
nullable **`cluster_node_papers.position`** (**migration 0028**, additive/guarded). Membership stays in
`cluster_node_papers`, so the inc-63 synthesis filter, the A6 drop-to-add, and axis merge keep working **unchanged**
(vs the rejected separate-table / JSON-order forks); the inc-50 `restore_manual_assignments` "manual survives
re-score" guarantee makes a curated axis the limit case (all-manual, never scored). **Backend:** `axis_assignments.py`
gains `CURATED_KIND`/`CREATABLE_KINDS` + `append_member_position` (new member → position max+1) + `set_member_order`
(validates the id set == members; writes position by index) + **`freeze_to_curated`** (keyword→curated: snapshot the
**shown** members [assigned `confidence >= cutoff` + manual], demote all to manual + position-ordered, **drop the
below-cutoff uncertain** — honors A10 *shown = frozen*; kind=curated) + **`revert_to_keyword`** (warned: members
**kept**, position cleared, axis → stale) + a curated short-circuit in `axis_score_state`; `repository.get_papers_for_cluster_node`
orders by `position` NULLS-last; `create_axis(kind=)`; `routers/axes.py` adds `kind` to `POST /axes` (allowlisted →
422) + the `PATCH /axes/{id}` freeze/revert switch (standard↔curated only — never to/from my_publications) +
**`PUT /axes/{id}/order`** (the full id list; 422 on a non-curated axis / foreign id set — SP2's drag reuses it
verbatim) + a position-append on `POST /axes/{id}/papers` + `ClusterPaperResponse.position`; `discovery/relevance.py`
excludes `curated` (no query text). **Frontend** (`15_axes.jsx`, mirroring the `isMyPubs` pattern): `isCurated` hides
the re-score row (cutoff/Score/👁); a **📌** label cue; a neutral **`.is-curated`** count badge (quiet `--accent-soft`
tint — distinct from unscored-grey / scored-green / stale-amber); members render in `position` order with per-row
**↑/↓** (→ `PUT /axes/{id}/order`); drop-to-add + ✕-remove still work; a **📌** toolbar button creates a curated axis
by name; a **❄ Freeze** action on keyword cards + a warned **↩ Convert** on curated cards. New CSS
(`.axis-count-badge.is-curated`, `.axis-reorder`, `.axis-curated-hint`) — tokens only. **Principles — aligned,
non-triggering:** a curated axis is a transparently human-authored, score-free, inspectable set (#3 facts-vs-candidates;
#7 no opaque score; #9 defaults are the user's); freeze is an explicit user act, revert is warned-not-silent; the
declined easy path (a "folder" / manual hierarchy) stays declined (flat; the umbrella is "Axis"). **No security audit**
(a local additive column + local endpoints; no egress/fetch/dependency — the saved-searches/color-tags precedent);
**no new dependency**. Tags need no change (already pure labels — A5 declined ratings). pytest **733 passed, 1
skipped** (+9 `tests/test_curated_axis.py`: the position column; manual-add appends + ordered read; `set_member_order`
writes + rejects-foreign; order-endpoint 422 on a non-curated axis; freeze keeps assigned+manual / drops uncertain /
orders / kind=curated; revert keeps members / clears order / kind=standard; create-curated + bad-kind/my_publications
→ 422; PATCH freeze→revert keeps the member; `test_axes.py` updated for the additive `position` field); `ruff` clean;
frontend rebuilt; migration head **0028** via `alembic_head()`; **QA surface 145/145 API** (+1 `/axes/{id}/order`,
claimed by the `/axes*` glob) **+ 689/689 FE, 0 uncovered** (`route_15_axes.md` extended + the never-"folder"
assertion). help corpus gained a "Curated axes" paragraph (`HELP-DOCS-SYNCED` → 211); DESIGN.md records the 📌 cue +
`.is-curated` badge. **Headed-verified, no egress** (`.local/visual/drive_inc211_curated.py` — **❄ Freeze** a seeded
axis → curated: 2 members [uncertain dropped] + 📌 + neutral badge + no scoring UI; **↓** reorder persists across a
reload; **📌** create-by-name; **↩ Convert** back → 📌 gone; 0 console/page/genai). **Rule-#1:** `js/15_axes.jsx` ends
at **551** (no split needed); `js/40_app.jsx` untouched at **599/600** (the chronic watch item). Notes:
`INCREMENT-211-NOTES.md`; spec `…/specs/2026-06-30-curated-axis-design.md`; plan (gitignored)
`.claude/backups/plans/2026-06-30_curated-axis-sp1.md`. **NEXT: A7 SP2** — swap the per-row ↑/↓ for HTML5
drag-to-reorder within the member list (frontend-only; reuses `PUT /axes/{id}/order`; its own small increment). With
SP2, the entire competitive-benchmark A-list (A1–A10) is closed; the deferred **B-items** (MCP server,
citation-context classifier, collaboration, OCR, mobile) remain larger, own design passes.

Earlier — increment 210 (A2 — library-wide per-paper citation counts; the eighth cheapest-first
close-out, the third migration-bearing one). Generalizes the My-Publications cited-by display (inc 119) so **every**
library card can show its OpenAlex `cited_by_count` — **verbatim + attributed** ("cited by N · OpenAlex, as of
<date>"), with an explicit opt-in **Most cited** sort. A displayed fact, never a composite or a silent rank.
**Backend:** **migration 0027** adds a dedicated **`paper_citation_counts`** table (PK `paper_id` FK CASCADE +
`cited_by_count` + `source` + `retrieved_at` [= the "as of"]) — kept OUT of the canonical `papers` row (consistent
with open_science_signals / gap_candidates; additive + guarded + no-op downgrade, the 0021 pattern; registered on the
shared metadata via `schema_findings.py`, re-exported from `schema.py`). **`OpenAlexClient.fetch_cited_by_count`** rides
the already-audited, **cached** DOI→work fetch (verbatim count; a real 0 kept; missing work/field → None; fail-closed).
**`repository.py`**: `list_papers` surfaces the count via two correlated scalar subqueries (`cited_by_count` +
`cited_by_as_of` — no JOIN → no row duplication) + a `citations_desc` sort key (NULL counts last) + `upsert_citation_count`
(OR-REPLACE on the PK → idempotent) + `list_live_papers_with_doi` (the bounded fetch set — DOI only, the reliable
identifier). `PaperListItem` (`routers/papers.py`) += `cited_by_count`/`cited_by_as_of`. **`routers/citation_counts.py`**
(new): async `POST /papers/citation-counts/refresh` + `GET …/{job_id}` (the statcheck/retraction batch shape — JobStore +
`mark_progress`; the worker fetches via `app.state.openalex_client`), registered **before** `papers.router` (so
`/papers/citation-counts/*` isn't captured by `/papers/{paper_id}` — the duplicates.py/fulltext.py precedent).
**Frontend:** the existing static `.paper-cite` chip (inc 119) now renders on library cards (`citeInfo={count,asOf}`, no
`workId` → the static span, tooltip "per OpenAlex · as of <date>"); a **"Most cited"** Sort option (`citations_desc`,
opt-in); a **"Citations ↻"** header control (`CitationCountsButton` in `js/10b_libmenus.jsx` — a self-contained POST→poll
that bumps the library refresh on completion + then reads "Citations · <date>"). **No new CSS** (reuses `.paper-cite` +
`.trash-toggle`). **Principles (Example 3, the per-paper-number case) — aligned:** raw not composite (#7); explicit
opt-in sort, never the default/silent (#2); honest "—" for no-record, never a fabricated 0 (#6); source+date visible
(#8); egress = DOI→OpenAlex (public metadata, bounded/cached/on-demand — #10), **NOT** the Gemini gate. **Audit
`2026-06-29_citation-counts.md` PASS** (no SSRF — constant host + DB-DOI path-quoted; bounded/cached; bound-param
upsert; additive guarded migration; **no new dependency**). pytest **724 passed, 1 skipped** (+5 `tests/test_citation_counts.py`:
`fetch_cited_by_count` [verbatim/0-kept/missing→None]; upsert + projection + Most-cited sort + idempotent re-fetch;
`list_live_papers_with_doi` [DOI-only]; the refresh endpoint stores counts + shows on `GET /papers` [404'd DOI → None
never 0; real 0 shown]; unknown job → 404); `ruff` clean; frontend rebuilt; migration head **0027** via `alembic_head()`;
**QA surface 144/144 API** (+2: the refresh POST + GET) **+ 679/679 FE, 0 uncovered** (`route_23_citation_counts.md`);
help corpus gained a "Citation counts" paragraph (`HELP-DOCS-SYNCED` → 210). **Headed-verified, no Gemini egress**
(`.local/visual/drive_inc210_citations.py` — a FAKE OpenAlex fetcher, offline: unknown job → 404; **Citations ↻** → 0
chips → **2 chips** + the control reads "Citations · 2026-06-29"; **Most cited** → "99 cited-by" first; 0
console/page/genai). **Rule-#1:** `js/40_app.jsx` stays **599/600** (the new prop folded onto an existing line — the
chronic watch item; a split is its own refactor); `js/10_pdf_layer.jsx` **562**; `js/10b_libmenus.jsx` **93**. Notes:
`INCREMENT-210-NOTES.md`. **NEXT (the cheapest-first A-items are now all closed — A9/A10/A8/A6/A5/A1/A3/A2):** the
remaining A-item is **A7 Curated Axis** (the largest; its own design pass). The deferred **B-items** (MCP server,
citation-context classifier) are larger, own design passes.

Earlier — increment 209 (A3 — full-text PDF search via SQLite FTS5; the seventh cheapest-first
close-out, the second migration-bearing one). Verbatim/lexical search over the already-extracted PDF chunk text — the
**exact-string complement** to the semantic axes/synthesis ("find 'ultimatum game' verbatim"). **Backend:** **migration
0026** creates an **external-content** FTS5 index `chunks_fts` over `chunks.text` (`content='chunks',
content_rowid='id'` — no text duplication; `snippet()`/`bm25()` available) + a **sync trigger trio** on `chunks`
(AFTER INSERT / DELETE / UPDATE) + a backfill. The **AFTER DELETE trigger is the crux** — it catches the **FK CASCADE**
from `purge_paper` (inc 65) that bypasses Python (a Python write-hook would miss it). `metadata.create_all` can't
express FTS5, so the migration is the source of truth + has a **real guarded `downgrade()`** (drops the triggers + FTS
table; 0001's metadata-loop can't drop an FTS5 vtable → no double-drop, the inc-208 0025 lesson applied in reverse).
New `persistence/fulltext_repo.py`: `_safe_match` token-quotes the raw query (each whitespace token → a double-quoted
phrase, AND-ed → neutralizes every FTS5 operator so it can't be a syntax error or inject the query language) + bound
`MATCH :q` (rule #3) + `snippet()` with U+E000/E001 markers + `ORDER BY bm25 LIMIT 50` + `try/except OperationalError →
[]` (never 500); excludes trashed papers (`deleted_at IS NULL`). `routers/fulltext.py` `GET /papers/fulltext?q=&limit=`
→ per-occurrence `FulltextHit`s (`coordinate_precision="region"`), registered in `app.py` **before** `papers.router`
(so `/papers/fulltext` isn't captured by `/papers/{paper_id}` — the duplicates.py precedent). **Frontend:** a **"Full
text (PDFs)"** option in the search-scope dropdown swaps `PaperList`'s body for a self-contained **`FulltextResults`**
(new chunk `js/10c_fulltext.jsx`) that does its own debounced `GET /papers/fulltext` fetch — so **`40_app.jsx` is
untouched** (it already threads `query`/`librarySearchField`/`onOpenPdf`, dodging its 599/600 cap). Per-occurrence
cards (reuse `.cite-card`/`.quote`): title + author·year, the snippet with matched terms **bolded** (split on the
U+E000/E001 markers → React `<b className="ft-mark">` nodes, **no `dangerouslySetInnerHTML`**), the page, and **Open
at page** → `citationTarget` → region-precision scroll (no fabricated exact rect). **Principles non-triggering** — a
verbatim lexical lookup, no claim/rank/score (bm25 is an internal ordering, never a displayed verdict);
coordinate-honest region open. **Audit `2026-06-29_fulltext-search.md` PASS** (sanitized + bound + fail-closed input;
escaped output, no XSS; local-only no egress/SSRF; bounded; trashed-excluded; trigger-synced incl. CASCADE; **no new
dependency** — FTS5 is core SQLite). pytest **719 passed, 1 skipped** (+4 `tests/test_fulltext.py`: `_safe_match`
sanitization; a hit returns snippet+page + trashed-excluded; malformed/empty queries → 200 `[]` never 500; the FTS
triggers stay in sync across a chunk insert **and a paper-delete CASCADE**); `ruff` clean; frontend rebuilt; migration
head **0026** via `alembic_head()`; **QA surface 142/142 API** (+1 `/papers/fulltext`) **+ 677/677 FE, 0 uncovered**
(new `route_22_fulltext.md` + the FE hit list); DESIGN.md records the result-card recipe (rule #8); help corpus gained
a "Searching inside your PDFs (full text)" paragraph (`HELP-DOCS-SYNCED` → 209). **Headed-verified, no egress**
(`.local/visual/drive_inc209_fulltext.py` — scope → Full text → "signal detection" → 1 hit, 2 bolded matches, p. 2 →
malformed `"` → 0 hits no error → Open at page → the PDF renders scrolled to page 2; 0 console/page/genai). **Rule-#1
watch:** `js/40_app.jsx` stays the closest at **599/600** (untouched); `js/10_pdf_layer.jsx` ends at **555**. Notes:
`INCREMENT-209-NOTES.md`. **NEXT (continuing the cheapest-first close-out):** **A2** — library-wide per-paper citation
counts (generalize the My-Pubs Layer-3 OpenAlex cited-by counts to all library cards — metadata egress, shown
verbatim-with-source, **never a silent rank**; trips the audit + Principles gates), and **A7 Curated Axis** (the
largest A item — its own design pass). The deferred **B-items** (MCP server, citation-context classifier) are larger,
own design passes.

Earlier — increment 208 (A1 — saved searches; the sixth cheapest-first close-out). A **saved
search** persists a named bundle of the existing library facets (q / search_field / item_type / axis / tag /
needs_review / signal / sort) and recalls it from a **Saved ▾** header menu (apply / save-current / delete) — a
metadata predicate over the existing `GET /papers` filters, **distinct from an axis** (a semantic lens that scores
papers; a saved search computes no claim/rank/score). **Backend:** **migration 0025** adds a `saved_searches` table
(`name` UNIQUE, `params` JSON, `created_at`); the `params` are validated at the write boundary by a typed
**`extra="forbid"`** model (`SavedSearchParams`) so only known facet keys are stored (unknown key → 422, blank name →
422 — rule #4). New `persistence/saved_search_repo.py` (`list`/`upsert_saved_search` [overwrite-by-name → re-saving a
name never duplicates]/`delete`) + `routers/saved_searches.py` (`GET`/`POST`/`DELETE /saved-searches`), registered in
`app.py`. **Frontend:** `40_app.jsx` gains `savedSearches` + `currentSearchParams()` (gather the live facets) +
`applySavedSearch(p)` (set search box + scope + sort + axis/tag/needs-review/signal at once; sets `query` AND
`debounced` → no 280ms double-fetch) + save/delete; a **`SavedSearchMenu`** ("Saved ▾", mirroring `AddMenu`) — a
popover with **Save current search…** + a row per search (apply / × delete). **Rule-#1 split (forced):**
`SavedSearchMenu` pushed `js/10_pdf_layer.jsx` to **602/600** → both header dropdowns (`AddMenu` + `SavedSearchMenu`)
extracted → new **`js/10b_libmenus.jsx`** (10_pdf_layer.jsx → **547**; referenced via the shared-IIFE function hoist).
`js/40_app.jsx` is now the closest at **599/600** (split before the next addition there). **Principles non-triggering**
(a saved facet-bundle, not a claim/signal; the copy reinforces "no score"). **No audit** (a local table + 3 local
endpoints; no egress/fetch/dependency). pytest **715 passed, 1 skipped** (+1 `tests/test_saved_searches.py`:
create / list / **upsert-by-name** [no duplicate] / unknown-key → 422 / blank name → 422 / delete 204 then 404);
`ruff` clean; frontend rebuilt; migration head **0025** via `alembic_head()`; **QA surface 141/141 API** (+3:
`/saved-searches` GET/POST/DELETE) **+ 675/675 FE, 0 uncovered** (new `route_21_saved_searches.md` + `10b_libmenus.jsx`
claimed by `route_00` [AddMenu] + `route_21` [SavedSearchMenu]); help corpus gained a "Saved searches" paragraph
(`HELP-DOCS-SYNCED` → 208). **Headed-verified, no egress** (`.local/visual/drive_inc208_saved_search.py` — type a
query → **Saved ▾ → Save current search…** → it lists with `q="memory"` → clear → **apply** → the search box restores
to "memory" → **×** delete → gone; **4/4 deterministic runs**, 0 console/page/genai. Harness notes: a real click→
`window.prompt` is racy under Playwright so the driver stubs `window.prompt`, and the debounced `/papers` refetch
re-renders `PaperList` so it settles on `networkidle` before menu clicks — both test-only). Notes:
`INCREMENT-208-NOTES.md`. **NEXT (continuing the cheapest-first close-out):** **A3** — basic full-text PDF search
(a SQLite **FTS5** index over the already-extracted `chunks` text, surfaced as a search field with hit highlighting;
the exact-string complement to the semantic axes) — **migration + a security audit** (a new query surface; validate
input); then **A2** library-wide citation counts, and **A7 Curated Axis** (its own design pass).

Earlier — increment 207 (A5 — color tags, with **ratings deliberately declined**; the fifth
cheapest-first close-out, the first migration-bearing one). The maintainer rejected ratings/flags: a unidimensional
star reduces a paper to one number, erasing the multi-dimensionality tags capture ("I'd give bad science 5 stars for
teachability") — which *is* the charter's logic (#7 no opaque composite, inspectability over authority). So A5 =
**color tags only.** **Backend:** **migration 0024** adds a nullable `tags.color`; a tag stores a fixed-palette **key**
(`red/orange/amber/green/teal/blue/purple/gray`), never arbitrary hex — allowlist-validated at the write boundary
(rule #3/#4). `tags_repo` gains `TAG_COLORS` + `set_tag_color` + `color` in the reads; `routers/tags.py` adds
**`GET /tags/colors`** (the palette) + **`POST /tags/{tag_id}/color`** `{color}` (422 off-palette / 404 no-tag) +
`color` on `TagRef`/`TagSummary`; `PaperTagRef` (papers.py) + `_paper_detail` carry it too. **Frontend:** theme-aware
`--tag-<key>` ink tokens (light in `:root` + lighter dark overrides) + a `.tag-chip.tag-colored` recipe using
**`color-mix(in srgb, var(--tag-c) 16%, var(--panel))`** for the fill (auto-adapts to light/dark; a colored chip
**overrides** the inc-100 provenance styling, uncolored keeps it); a **swatch popover** off each chip's color dot in the
Details Tags row (8 swatches + a "none" ×) + a matching color dot in the sidebar Tags tab. **Principles:** the
declined-ratings decision *is* the principle pass — a color is a user label, never an AI score; tags stay the
orthogonal, inspectable judgment. **Rule-#1 split (forced):** the picker pushed `js/25_detail.jsx` to **609/600** (the
watched closest at 584) → **`TagsRow` extracted verbatim → `js/25b_tags.jsx`** (25_detail.jsx → **522**, 25b 95;
`DetailContent` calls it via the shared-IIFE function hoist). **No audit** (a color column + 2 local endpoints; no
egress/fetch/dependency). pytest **714 passed, 1 skipped** (+1 `tests/test_tags.py`: palette exposed; set valid →
reflected in `/tags` + the paper detail + a re-add; invalid hex → 422, stored color unchanged; clear via null; unknown
tag → 404); `ruff` clean; frontend rebuilt; migration head **0024** via `alembic_head()`; **QA surface 138/138 API**
(+2: `/tags/colors`, `/tags/{id}/color`) **+ 667/667 FE, 0 uncovered** (`route_20_tags.md` claims the endpoints +
`25b_tags.jsx` + a color step + the **no-rating** assertion); DESIGN.md records the palette + recipe (rule #8); help
corpus gained a "Coloring a tag" paragraph + the no-rating framing (`HELP-DOCS-SYNCED` → 207). **Headed-verified, no
egress** (`.local/visual/drive_inc207_tag_color.py` — open Details → click a chip's color dot → swatch popover → pick
blue → the chip recolors + `GET /tags` shows blue; re-run after the TagsRow extraction confirms it's behavior-
preserving; 0 console/page/genai). Notes: `INCREMENT-207-NOTES.md`. **NEXT (continuing the cheapest-first close-out):**
**inc 208 — A1** saved searches (persist a named bundle of the existing facets — item_type/axis/tag/needs-review/signal
+ sort + search-scope — recalled from the library header; a `saved_searches` table; **distinct from axes** — a metadata
predicate, not a semantic lens); then **A3** full-text FTS5 search (migration + a security audit), **A2** library-wide
citation counts, and **A7 Curated Axis** (its own design pass).

Earlier — increment 206 (A6 — drag-and-drop a library paper onto an axis to add it; the fourth
cheapest-first close-out). A faster input for the existing manual-axis-add path, **frontend-only** — rides the inc-50
`POST /axes/{axis_id}/papers` manual-override endpoint (no backend/migration/endpoint/egress/dependency/audit).
**`10_pdf_layer.jsx`** — `PaperCard` is `draggable`; `onDragStart` writes the paper id to a custom MIME
`application/x-callosum-paper` (`effectAllowed="copy"`); click-to-select + double-click-open are unaffected.
**`15_axes.jsx`** — the `.axis` header is a drop target **for non-My-Pubs axes only** (`canDrop = !isMyPubs`): `onDragOver`
accepts the drag iff that MIME is present (→ a `dragOver` state + the `.drag-over` highlight), `onDrop` reads the id →
`AxesPanel.dropPaper` (`apiPost('/axes/{id}/papers',{paper_id})` → `loadDetail` + `loadAxes` + a "Added to <axis>"
flash). **`styles.css`** — `.axis.drag-over` = dashed `--accent` border + `--accent-soft` fill (a transient drop-invite,
distinct from the solid `.active`; recorded in DESIGN.md as a reusable recipe). The payload rides the **native
`dataTransfer`**, so a center-pane card drops on a left-pane axis card with **no React state plumbing across panes**.
**My-Pubs is deliberately not a drop target** — its membership is authorship-resolved (ORCID/DOI + ✓/✕), so a drag
gesture must not mint an own-paper claim. **Principles non-triggering** (a manual human choice, not a scorer/AI
decision). pytest **713 passed, 1 skipped** (unchanged — frontend-only; `POST /axes/{id}/papers` is already covered by
`test_axes.py`, the DnD wiring is headed-verified); `ruff` clean; frontend rebuilt; **QA surface unchanged** (136/136 API
+ 661/661 FE, 0 uncovered — the drag handlers ride existing claimed `.paper`/`.axis` elements; `route_15_axes.md` gained
an A6 drag-to-add + My-Pubs-no-drop step); help corpus's axes section + DESIGN.md updated (`HELP-DOCS-SYNCED` → 206).
**Headed-verified, no egress** (`.local/visual/drive_inc206_drag_axis.py` — dispatch an HTML5 drag [shared DataTransfer
handle] from a `.paper` card onto an `.axis` card → the badge count goes 0→1; 0 console/page/genai). Notes:
`INCREMENT-206-NOTES.md`. **NEXT (continuing the cheapest-first close-out):** **inc 207 — A5** color tags / ratings /
flags (a `color` on tags + a user `rating`/`flag` on papers + UI — a small migration; a rating is a **user field, never
an AI score**); then **A1** saved searches (a `saved_searches` table + header recall), **A3** full-text FTS5 search
(migration + a security audit), **A2** citation counts, and **A7 Curated Axis** (its own design pass).

Earlier — increment 205 (close A8 as covered + remove the redundant THEORY → Discover placeholder —
the third close-out of the wrap-up pass, two cheapest-first frontend-only items). **(1) A8** (synthesis scope label):
**closed-as-covered, not built** — the pre-run scope note ("N selected papers …", inc 145) + the inc-153 post-run
coverage readout ("Drew from M of N selected papers · top K chunks …") already give the honest scope. The literal
"uncertain excluded" wording is **declined on honesty grounds**: `summarize_scope` summarizes the **exact** `paper_ids`
selected regardless of certainty (no axis-cutoff notion; a selection can come from an unfiltered view), and **A10 (inc
204) already enforces the certainty boundary upstream at selection time** — where the user can see it. **(2) Removed the
THEORY → Discover `<ComingSoon>` placeholder** (Cliff's queued request): the inc-163 stub (Beyond library/Feed/Search
tabs in `09_placeholders.jsx`) is stale — the real Discover/Search (inc 184) + Feed (inc 188) ship as **center-pane
tabs in the library frame** (`30c_frame.jsx`); per the inc-163 convention a stub is dropped in the increment its real
feature lands. The 3 Discover `registerPaneTab` blocks were removed; the METHODS coming-soon stubs (Mixed-model/Bayesian/
Meta-analysis/Citation-equity) + the statcheck "More checks" tab + the `ComingSoon` component are untouched. **(3) Folded
in:** a ruff-format fix for the inc-204 `tests/test_papers.py` — the inc-204 push went **red on `ruff format --check`
only** (the suite was green; the A10 test's `cluster_nodes` insert needed wrapping). **GOTCHA (recurring): run `ruff
format` — not just `ruff check` — before pushing; CI runs `ruff format --check .`.** **Principles non-triggering** (an
honesty-preserving no-op-close + inert roadmap-UI removal). **No migration/endpoint/egress/dependency.** pytest **713
passed, 1 skipped** (unchanged — no new test; the removal is covered by `test_frontend_assembly`, A8 is a doc-close);
`ruff` clean; frontend rebuilt; **QA surface unchanged** (136/136 API + 661/661 FE, 0 uncovered — inert stubs claimed no
route); help corpus unchanged (it describes the real Discover tab, not the placeholder; `HELP-DOCS-SYNCED` stays at 204).
**Headed-verified, no egress** (`.local/visual/drive_inc205_no_discover.py` — the accordion headers no longer include
"DISCOVER" while "AXES" + "MIXED-MODEL REPORTING" still render; 0 console/page/genai). Notes: `INCREMENT-205-NOTES.md`.
**NEXT (continuing the cheapest-first close-out):** **inc 206 — A6** drag-and-drop a paper onto an axis (a faster input
for the existing manual-add path, rides `restore_manual_assignments`; frontend, no migration); then **A5** color tags/
ratings + **A1** saved searches (each a small migration + UI), **A3** full-text FTS5 search (migration + a security
audit), and finally **A2** citation counts + **A7 Curated Axis** (its own design pass).

Earlier — increment 204 (carry "hide uncertain" through to the library-pane axis filter — backlog
A10, the second close-out of the wrap-up pass): a straight *shown ≠ summarized* bug. The axis count-badge (inc 63)
filters the Library to that axis's papers, and the card's 👁 hide-uncertain toggle (inc 51) shows only **assigned**
(confidence ≥ the axis cutoff) + **manual** (NULL) papers — but clicking the badge while hide was on still filtered to
**every** axis member, so *select-all → summarize* could include papers the card had hidden. Fix: the badge now carries
the card's hide state. **`repository.py`** — `list_papers(..., axis_hide_uncertain=False)` + a new module constant
**`DEFAULT_AXIS_CUTOFF = 0.35`** (mirrors `routers/axes.py` + `discovery/relevance.py`); when set, the axis-member
subquery gains `WHERE (confidence IS NULL OR confidence >= cutoff)`, `cutoff = axes.scoring_gain` for that axis (queried
inline) else the default — the **exact** tiering `routers/axes.py::_axis_cutoff` + the read-time `assigned_ids`
computation use, so the SQL set == the card's "assigned + manual" set (bound params throughout, rule #3). **`routers/
papers.py`** — `GET /papers` gains `axis_hide_uncertain: bool = Query(False)`. **Frontend (4 boolean hops):**
`15_axes.jsx` — the badge `onClick` passes the card's `hideUncertain`; `AxesPanel.filterToAxis` folds it into the
`onFilterToAxis({id,label,hideUncertain})` payload. `40_app.jsx` — `filterToAxis` stores `libraryAxisFilter.hideUncertain`;
the `/papers` query-string builder adds `axis_hide_uncertain=true` when set. `10_pdf_layer.jsx` — the "Filtered to axis
…" banner appends "· assigned only". **Default false → the inc-63 all-members behavior is byte-for-byte unchanged.**
**Principles non-triggering** — a retrieval/filter-consistency fix (the inc-66 class); inspectability/provenance/egress
posture unchanged, no new claim/signal. **No endpoint added** (a query param on the existing `GET /papers`), **no
migration/egress/dependency** → no audit-gate trigger. pytest **713 passed, 1 skipped** (+1 `tests/test_papers.py`:
assigned[0.6]/uncertain[0.2]/manual[NULL] → `?axis_id=` all three, `&axis_hide_uncertain=true` only assigned+manual);
`ruff` clean; frontend rebuilt; **QA surface unchanged** (136/136 API + 661/661 FE, 0 uncovered — a query param + the
existing badge/banner, not a new surface; `route_15_axes.md` gained an A10 *shown==summarized* step); help corpus's
axis count-badge bullet updated (`HELP-DOCS-SYNCED` → 204); swept 4 stray `app/frontend/js/*.tmp.*` orphans (rule #5).
**Headed-verified, no egress** (`.local/visual/drive_inc204_hide_uncertain.py` — seed assigned/uncertain/manual, expand
the card, click 👁, click the badge → the Library shows only "Assigned paper" + "Manual paper" [not "Uncertain paper"]
+ the banner reads "· assigned only"; 0 console/page/genai). The aligned shape was pre-decided with the maintainer
(benchmark-revisions §A10). Notes: `INCREMENT-204-NOTES.md`. **NEXT (continuing close-outs):** **A8** (verify the
synthesis scope label vs the inc-153 coverage readout — likely a confirm pass), then the low-cost build-now items
(**A1** saved searches, **A5** color tags/ratings, **A6** drag-into-axes, **A3** full-text PDF search); the deferred
B-items + **A7 Curated Axis** are larger design passes. Queued (Cliff, non-urgent): remove the redundant THEORY →
**Discover** accordion placeholder (`09_placeholders.jsx`) now that Discover/Feed ship as center-pane tabs in the
library frame.

Earlier — increment 203 (activate the dormant `contradicted` verification status — backlog A9, the
first close-out of the wrap-up pass): the verification spine could flag a claim *not-supported* but **couldn't
surface that a cited source actively DISAGREES** — the most consequential citation error a verify-everything tool
exists to catch. The schema already defined `contradicted` (`CITATION_MAPPING_STATUSES`) and the NLI CrossEncoder
already produced a contradiction probability — it was just **discarded** (the support path softmaxed all 3 classes +
took only entailment). Fix (`summarization/verification.py`): `NLISupportScorer.support_and_contradiction()` reads
**both** probs from the **one** existing model call (no extra inference; `.score()` is now a wrapper); `_status()`
checks contradiction **first** → returns **`contradicted`** when `contradiction ≥ contradiction_threshold (0.55)`
**and** `contradiction > support` (conservative; overrides what would otherwise be `verified`, since a disagreeing
source is on-topic so retrieval+quote are high). The verifier **duck-types** the scorer
(`getattr(self.support_scorer, "support_and_contradiction")`), so the embedding fallback / a test double (plain
`.score()`) yields contradiction `None` → never a guessed contradiction. **`VerificationResult.contradiction_confidence`**
carries it; **no migration** (`contradicted` is a valid status string → flows through `citation_mappings.status` →
the response → the frontend). Frontend (`20_synthesis.jsx` + `styles.css`): a 3-way `citeStatusClass()` renders
`contradicted` as its **own distinct state** — a red **"⚠ source disagrees"** pill (`.cite-status.contradicted`,
`--danger` family) instead of the amber "flagged" lump; **DESIGN.md records the narrow exception** (red on ONE
non-interactive *status* pill — not the §4 destructive-action red; rule #8). **Principles gate (rule #9) run —
aligned:** activates an *already-designed* status; **signal not verdict** (#2/#3 — the contradicted citation shows its
verbatim quote/page/confidence, "these passages contradict this claim, your call," never "this claim is false");
strengthens invariant #1; evidence always shown (#4). The aligned shape was **pre-decided with the maintainer**
(the benchmark-revisions doc §A9). pytest **712 passed, 1 skipped** (+3 `tests/test_nli_support.py`: the dual-prob
read from one softmax; `_status` contradicted only when a confident contradiction dominates support, never without a
signal; an e2e `summarize_scope` → status `contradicted` + flagged + persisted); `ruff` clean; frontend rebuilt; QA
surface unchanged (132/132 API + 661/661 FE; `route_55` gained a contradicted=signal-not-verdict assertion); **no
endpoint/egress/migration/dependency**; help corpus updated (`HELP-DOCS-SYNCED` → 203); swept 2 stray `tests/*.tmp.*`
orphans (rule #5). Notes: `INCREMENT-203-NOTES.md`. **This is the first close-out from the inc-202 backlog-grooming
wrap-up** (the competitive-benchmark revisions folded into the backlog). **NEXT (continuing close-outs):** **A10**
(carry "hide uncertain" through to the library-pane axis-contents — a straight bug; *shown = summarized*), **A8**
(verify the synthesis scope label vs the inc-153 coverage readout), then the low-cost build-now items (**A1** saved
searches, **A5** color tags/ratings, **A6** drag-into-axes, **A3** full-text PDF search); the deferred B-items + **A7
Curated Axis** are larger design passes.

Earlier — increment 202 (accounts SP3b — the reference sync-server + client transport + opt-in: the
egress slice): the first path where data **leaves the machine**, built as the maintainer chose — **server + transport
+ opt-in together**, **FastAPI + Postgres** (SQLAlchemy Core, so SQLite-in-tests / Postgres-in-prod), in-repo under
**`sync_server/`** (a separate deployable; **the local app gains no dependency** — only an httpx transport). What
leaves is **opaque AES-GCM ciphertext** the server can't read (E2E; the DEK never leaves), so it's **opt-in,
default-off**. **`sync_server/`** is an OIDC **resource server** (validates an Authentik bearer via JWKS, scopes every
row to `sub`; an injectable `TokenVerifier` = a fake `sub` in tests) storing `sync_records` per user with a per-user
`seq` (the cursor, assigned from a locked `sync_cursor` row) over `GET/POST /sync/records` — LWW-by-version, ≤1000
records / ≤2 MB caps, never decodes a blob. **`HttpSyncTransport`** (`app/backend/sync/transport.py`) implements the
inc-198 Protocol over httpx, **fail-closed**. The opt-in vertical (`app/backend/api/routers/sync.py`): `GET
/sync/status`, `PUT /sync/settings` (lockout-safe enable — 422 unless configured + signed-in + URL), `POST /sync/setup`
(create keyring → the recovery code **once**, never in `/status`), `POST /sync/run` (unlock the DEK from the per-run
passphrase → `run_sync` over the transport → persist the cursor; **409** if any precondition unmet, **401** + **no
egress** on a wrong passphrase). `app_settings` gained the sync config + the sealed keyring (secret store) + the cursor
(the inc-198 deferral resolved). `create_app(sync_transport=…)` injects a transport bound to the in-process server →
**the whole stack is pytest-tested** (server round-trip / LWW / per-user tenant isolation / cursor / 401 / caps; a
**two-device convergence over the real HTTP transport**; the opt-in gate incl. wrong-passphrase-no-egress). **Audit
`2026-06-29_sync-server.md` PASS** (default-off egress of opaque E2E ciphertext only; per-user isolation behind
Authentik token validation; bounded inputs; fail-closed; no local-app dependency; server fenced from `app/`).
**Principles/A-A:** the SP3 gate ran in SP3a (A5 sovereignty via E2E + opt-in; A4 conflict-surfacing) — this realizes
that egress channel exactly as gated. pytest **709 passed, 1 skipped** (+17: `tests/test_sync_server.py` 9 +
`tests/test_sync_endpoints.py` 8); `ruff` clean; QA surface **136/136 API** (+4 `/sync/*`; new `route_46_sync.md`) **+
661/661 FE, 0 uncovered**; **no migration**; **no new dependency in the local app** (server-only deps in
`sync_server/requirements.txt`). Notes: `INCREMENT-202-NOTES.md`; design spec `…/specs/2026-06-29-sync-server-design.md`.
**The live deploy + live-Authentik token validation is the maintainer's MANUAL step** (the flow + contracts are
pytest-proven). **NEXT:** **SP3c** — the Settings → Sync UI (set up / enable / run, passphrase prompt) + the
**conflict-review screen** (read `sync_conflicts`, pick a side); then the live deploy + pre-public server hardening
(per-user rate-limiting, retention, a backup runbook, a migration tool). PDF-file sync / real-time / CRDTs / multi-user
sharing (SP4) deferred.

Earlier — increment 201 (accounts SP3b cont. — natural-key identity for tags, the cross-device
collision fix, no egress): closes the one real correctness gap left in the engine. `tags.name` is **UNIQUE**, so two
devices that *independently* created a same-named tag (a `to-read`, a `review`) would crash with an `IntegrityError`
on the **first** real sync — apply would INSERT a duplicate-named tag. Fix: a tag *is* its (UNIQUE) name, so its
`sync_uid` is now **deterministic from the name** (`_natural_uid("tags", name)` = `sha256("tags\0name")` hex) instead
of a random uuid → both devices independently pick the **same** uid for `"topic"`, so apply finds the existing local
tag by that uid and **UPDATEs** it (no INSERT, no UNIQUE violation, automatic convergence). The whole fix is in
`ensure_identities` (a new **`natural_key`** field on `SyncableCollection`); `collect_local`/apply/merge are untouched,
and paper_tags links converge for free (both reference the same tag uid). Only **`tags`** declares a natural key
(papers/axes titles/labels aren't UNIQUE; paper_tags is a link table); tag **rename** isn't an app flow (add/remove,
not rename), so the rename-changes-the-uid edge doesn't arise. **Audit addendum 3** to `2026-06-29_sync-engine-sp3b.md`
**PASS** (resolves the addendum-2 known limitation: convergence-not-collision, deterministic + collection-scoped uid).
**Principles/A-A:** the SP3 gate ran in SP3a → non-triggering (no egress; conflicts surfaced). pytest **692 passed, 1
skipped** (+2 `tests/test_sync_engine.py` — `test_tags_converge_by_name_not_collide` [two devices, same tag name →
exactly one row + the same uid, no crash, re-sync no-op] + `test_natural_uid_is_deterministic_and_scoped`); `ruff`
clean; **no migration / endpoint / egress / dependency / UI**; QA surface unchanged (132/132 API + 661/661 FE, 0
uncovered). Notes: `INCREMENT-201-NOTES.md`. **This leaves the client sync engine robust + collection-complete**
(papers · tags · axes · notes · annotations · tag-assignments; summaries deferred-as-not-synced; manual cluster
membership a later redesign). **NEXT:** the **reference sync-server** — the slice where ciphertext actually leaves the
machine → its own security audit + the maintainer standing up infra + a hosting decision (a pause-and-plan-together
step, not a solo build); then the `app_settings` cursor wiring + **SP3c** (the opt-in Settings → Sync UI + conflict
review).

Earlier — increment 200 (accounts SP3b cont. — the link-table model, paper_tags, no egress):
syncs the composite-PK **link table `paper_tags`** (tag assignments) — completing the engine's user-authored
relational coverage (papers · tags · axes · notes · annotations · **tag assignments**). A link has **no own id**, so a
per-row `sync_uid` (and a random one would never converge) is wrong — its identity is **derived from its endpoints**:
`record_id = "<paper sync_uid>|<tag sync_uid>"`, computed identically on every device. **`changeset.py`:**
`SyncableCollection.pk` → **`str | None`** (`pk=None` = a LINK table); a shared **`_outbound(c, row, maps)`** helper
returns `(record_id, payload)` — own sync_uid for a normal collection, the **joined endpoint uids** for a link (payload
= the translated endpoints); `ensure_identities` skips link tables; `SYNCABLE` += **paper_tags** (`pk=None`,
`fks={"paper_id":"papers","tag_id":"tags"}`, last → referenced-first). **`engine.py`:** **`_apply_link`** splits
`record_id` on `|` → resolves each endpoint uid → this device's local id (`local_id_for_uid`) → **INSERT-OR-IGNORE**
(existence-checked composite PK) / **DELETE** (tombstone); returns **False (skip, retry)** if an endpoint isn't local
yet (never a dangling link); the push-tombstone `forget_identity` is guarded (a link has no own identity).
**Also decided:** **`summaries` is NOT synced** (a regeneratable synthesis whose verification is keyed to device-local
chunk/embedding versions — like embeddings/signals); manual `cluster_node_papers` stays deferred (needs an
axis-membership identity, since `cluster_nodes` are derived). **Known limitation (pre-existing inc-198):** `tags.name`
is UNIQUE → two devices independently creating a same-named tag (different uids) would collide on apply — natural-key
reconciliation is a follow-on before the live server (the link path is unaffected). **Audit addendum 2** to
`2026-06-29_sync-engine-sp3b.md` **PASS** (device-independent link identity; skip-not-dangling apply; idempotent
insert / tombstone delete; referenced-first ordering). **Principles/A-A:** the SP3 gate ran in SP3a → non-triggering
beyond honoring it (no egress; conflicts surfaced). pytest **690 passed, 1 skipped** (+1
`tests/test_sync_engine.py::test_link_table_paper_tags_sync` — a paper↔tag link syncs to a device with offset ids and
lands on its local `(paper_id, tag_id)` [`bpid != pid`]; converged re-sync is a no-op; un-tag propagates as a
tombstone that removes the link while leaving the paper + tag); `ruff` clean; **no migration / endpoint / egress /
dependency / UI**; QA surface unchanged (132/132 API + 661/661 FE, 0 uncovered). Notes: `INCREMENT-200-NOTES.md`.
**NEXT:** the **reference sync-server** (the slice where ciphertext actually leaves the machine → its own audit) + the
`app_settings` cursor wiring + natural-key tag reconciliation; then **SP3c** (the opt-in Settings → Sync UI + conflict
review). The engine's collection coverage is complete (summaries deferred-as-not-synced; manual cluster membership a
later redesign).

Earlier — increment 199 (accounts SP3b cont. — the FK-translation layer + the child tables notes/
annotations, no egress): extends the inc-198 engine to the **FK-bearing child tables** — **notes** + **annotations**
(the user's notes + highlights, the high-value relational data) — via a generic **FK-translation layer**. A row's
foreign-key columns travel as the *referenced row's* **`sync_uid`** (device-independent) and are translated back to
each device's local id on apply, applied **referenced-collections-first**. **`changeset.py`:** `SyncableCollection`
gains **`fks`** (`{fk_column: referenced collection}`) + **`drop`** (device-local columns omitted from the payload);
`collect_local` builds every collection's uid_map once, then per row drops `pk`+`drop` cols + **translates each FK
local-id → the referenced row's sync_uid** (a row whose FK target lacks an identity is skipped). `SYNCABLE` extended
in **referenced-first order**: papers/tags/axes + **notes** (`fks={"paper_id":"papers"}`) + **annotations**
(`fks={"paper_id":"papers"}`, `drop=("attachment_id",)`). **`engine.py`:** `_apply_record(...)→bool` translates each
FK **sync_uid → this device's local id** (`local_id_for_uid`), returning **False (skip, don't advance sync_state)** if
a target isn't local yet (no dangling write); the apply loop runs **referenced-first** (sorted by `SYNCABLE` rank) so
FK targets exist before the referencing row; `SyncRunResult.applied` is the actually-applied count. **Device-local
data isn't leaked:** `annotations.attachment_id` (a per-device linked-PDF pointer — PDFs aren't synced) is in `drop`,
so it's omitted from the payload entirely + applied NULL on the far device (the highlight re-associates by paper+page
+bboxes, the inc-30 overlay model). The uid-form FK payload round-trips stably → a converged pair re-syncs to **0
push / 0 apply**. **Audit addendum** to `2026-06-29_sync-engine-sp3b.md` **PASS** (FK-translation safety; referenced-
first ordering + skip-not-corrupt; device-local-column drop; hash round-trip; unchanged egress posture).
**Principles/A-A:** the SP3 gate ran in SP3a → non-triggering beyond honoring it (E2E held; no egress; conflicts still
surfaced). pytest **689 passed, 1 skipped** (+1 `tests/test_sync_engine.py::test_child_tables_fk_translate_across_devices`
— a note + an annotation sync to a device with offset local ids; their `paper_id` re-points to that device's local
paper [`bpid != pid_a`]; `attachment_id` drops to NULL; the converged re-sync is a no-op); `ruff` clean; **no
migration / endpoint / egress / dependency / UI**; QA surface unchanged (132/132 API + 661/661 FE, 0 uncovered).
Notes: `INCREMENT-199-NOTES.md`. **NEXT:** the remaining FK-bearing collections that need a distinct shape —
**`paper_tags`** (a composite-PK **link table**: identity = its endpoint-uid pair, no own id), then **`summaries`**
(JSON-embedded scope refs + device-local version-keyed verification — possibly snapshot-only / not-synced) + manual
**`cluster_node_papers`** (depends on un-synced `cluster_nodes` → needs an axis-membership identity strategy); then
the **reference sync-server** (where ciphertext actually leaves → its own audit) + the `app_settings` cursor wiring;
then **SP3c** (the opt-in Settings → Sync UI + conflict review).

Earlier — increment 198 (accounts SP3b — the client sync engine + `sync_uid` identity, top-level
collections, no egress): the engine half of E2E multi-device sync (the maintainer chose **engine first, server next** +
**top-level collections first**). **No live egress this slice** — a fake in-memory transport drives the tests; the
reference sync-server (where ciphertext actually leaves) is the next slice. **The crux is cross-device identity:**
device-local auto-increment `id`s differ across devices, so sync keys every record on a global **`sync_uid`** (UUID) in
a new **`sync_identity`** map (collection, local_id ↔ sync_uid; **migration 0023**, additive/guarded, **local-only**)
and transports the row **minus its local PK** (device-independent content). **`changeset.py` revised** → keys on
`(collection, sync_uid)`; `SYNCABLE` narrowed to **papers/tags/axes**; new helpers `uid_map`/`local_id_for_uid`/
`bind_identity`/`forget_identity`/`ensure_identities` (lazily assigns a `uuid4` to any current row lacking a mapping).
**`engine.py` (new)** — `SyncBlob` + `PullResult` + a **`SyncTransport` Protocol** (`pull(since)→{records,seq}` /
`push(records)→seq`) + `run_sync(conn, dek, transport, *, since=0)`: pull → **decrypt** each non-tombstone blob
(`decrypt_payload`, **fails closed**) → `merge_remote` → **apply** (`_apply_record`: UPDATE-in-place / INSERT-and-bind /
DELETE-and-`forget_identity` **by sync_uid** — never INSERT-OR-REPLACE; `_coerce_for_write` writes only known columns
[rule #4] + parses decrypted ISO strings back to datetimes; `_typed_pk` int-compares an integer PK) → record conflicts
in `sync_conflicts` (`_json_safe`-normalized, A4) → push the post-apply changeset. **Cursor-store-agnostic** (`since`
in / `new_cursor` out — the caller persists; the endpoint/SP3c wires it) + **transport-agnostic** + holds only the
unsealed **DEK** (the transport sees only opaque AES-GCM blobs — the E2E boundary is intact). The **content-hash
round-trip is stable** (encrypt + hash both `default=str`; coerce ISO→datetime on apply), so a converged pair re-syncs
to **0 pushes / 0 applies**. **Audit `2026-06-29_sync-engine-sp3b.md` PASS** (sync_uid identity proven by a
two-device convergence test where the uid→local_id maps differ; fail-closed on a foreign blob; column-validated apply;
surfaced conflict recoverable; no egress). **Principles/A-A:** the SP3 gate ran in SP3a (A5 sovereignty via E2E+opt-in;
A4 via conflict-surfacing) → this slice non-triggering beyond honoring those. pytest **688 passed, 1 skipped** (+4
`tests/test_sync_engine.py` — converge-via-sync_uid + 0-push re-sync; concurrent-edit conflict surfaced + recoverable;
tombstone propagates + idempotent; foreign blob fails closed; the SP3a changeset test repointed to sync_uid); `ruff`
clean; migration head **0023** via `alembic_head()`; **QA surface unchanged** (132/132 API + 661/661 FE, 0 uncovered —
engine-only, no new route); **no new dependency, no egress, no UI.** Notes: `INCREMENT-198-NOTES.md`. **NEXT:** the
**FK-bearing collections** (paper_tags/notes/annotations/summaries/manual-cluster) + an **FK-translation layer**
(resolve a referenced row's sync_uid ↔ local id via `sync_identity`) — a focused follow-on; then the **reference
sync-server** (the slice where ciphertext leaves → its own audit) + the `app_settings` cursor wiring; then **SP3c**
(the opt-in Settings → Sync UI + conflict review). PDF-file sync / real-time / CRDTs deferred.

Earlier — increment 197 (accounts SP3a — E2E sync crypto + local change-tracking foundation, no egress):
the first slice of **opt-in, end-to-end-encrypted, multi-device, metadata-first sync** (the invariant-touching
feature → design spec `…/specs/2026-06-29-accounts-sync-design.md`; the **Principles/A-A gate was run** — A5
sovereignty honored by E2E+opt-in, A4 by conflict-surfacing; three non-negotiables = real-E2E / opt-in-default-off /
conflicts-surfaced). SP3a is the **local, hermetically-testable, no-egress** core. **`app/backend/sync/crypto.py`** —
a random **DEK** encrypts records (**AES-256-GCM**, fresh per-record nonce); the DEK is **sealed** under a
**passphrase** KEK *and* a **recovery-code** KEK (both **`scrypt`**, `cryptography.hazmat` — **no new dependency**);
the keyring persists only the sealed DEK+salts (no key/passphrase/plaintext); wrong key → **fails closed**; rotation
re-wraps without re-encrypting; **no server-side reset** (the recovery code is the only non-passphrase unlock).
**`app/backend/sync/changeset.py`** — change-tracking is a **hash-diff** vs `sync_state` (no write-hooks); the merge
is **per-record LWW that surfaces conflicts** (the overwritten local payload kept in `sync_conflicts`, recoverable —
A4), pure of network/crypto. New **`schema_sync.py`** (`sync_state` + `sync_conflicts`, **migration 0022**, additive/
guarded, **local-only — never synced**) re-exported from `schema.py`. **`SYNCABLE`** = papers/tags/paper_tags/notes/
annotations/axes/summaries; **NOT synced** (rebuilt/re-linked locally): embeddings/signals/caches + **PDF bytes**.
**No endpoint/egress/UI/surface change this slice.** Audit `2026-06-29_sync-crypto-sp3a.md` **PASS** (real E2E,
per-record nonces, fail-closed, the opaque-blob guarantee [a test asserts no plaintext in the ciphertext],
conflict-surfacing-not-clobber). pytest **684 passed, 1 skipped** (+14 `tests/test_sync_crypto.py`); `ruff` clean; QA
surface **132/132 API + 661/661 FE, 0 uncovered** (no new route); migration head via `alembic_head()`. Notes:
`INCREMENT-197-NOTES.md`. **NEXT: SP3b** — the account-authenticated sync **endpoint** (OIDC-gated; opaque per-record
blobs + sequences) + the client **push/pull engine** (the first slice where ciphertext leaves → its own audit; the
maintainer stands up the endpoint) → **SP3c** the opt-in Settings → Sync UI + conflict review. (PDF-file sync +
real-time + CRDTs deferred.)

Earlier — increment 196 (accounts SP2 — more login methods: email/password + Google, method-agnostic):
adds **email/password + Google** sign-in to the optional account. Because callosum is **one OIDC client of the account
platform (Authentik)**, the login *methods* are **Authentik connectors** → the **functional** part is platform config
(the runbook `ops/accounts-authentik-setup.md` gained an "Adding more login methods" section: a Google social source +
email/password enrollment); callosum needed only a **small refinement** on the SP1 seam: the sign-in button is now
**"Sign in"** (method-agnostic, was "Sign in with ORCID"; per-method buttons in callosum were **rejected** — they'd
couple callosum to Authentik connector slugs), it captures the **`email`** claim for display (`Identity.email` →
session → `account.email` on `GET /settings` — the signed-in user's own identity shown locally, never a token), and it
**populates My-Pubs only on an ORCID login** (`router.py`: `if identity.orcid:` — a Google/email login sets the
account identity but must not overwrite the My-Pubs profile from a non-authoritative display name; the signed-in line
shows name **or** email). **No new endpoint/surface/egress/migration** (relabel = text in the already-claimed
`35_settings.jsx`; `account.email` additive). **Audit addendum** to `2026-06-29_orcid-account.md` **PASS** (still
identity-only); **Principles non-triggering** (more login methods, same posture). pytest **670 passed, 1 skipped**
(+1 non-ORCID-login test in `tests/test_auth_oidc.py`, now 15: signs in, `orcid` None, `email` shown, not superuser,
**My-Pubs untouched**); `ruff` clean; QA surface **132/132 API + 661/661 FE, 0 uncovered**; help corpus updated
(`HELP-DOCS-SYNCED` → 196); headed driver re-verified (no unconfigured-UI regression). Notes:
`INCREMENT-196-NOTES.md`. **NEXT:** the maintainer's live Google/email standup (Authentik connectors) → **SP3 opt-in
sync** (the only step that moves library data off-machine — its own design + heavy A-A pass) → **SP4 sharing**;
superuser *capabilities* remain parked (backlog).

Earlier — increment 195 (superuser role + the Authentik standup runbook — accounts SP1 follow-ons):
two approved follow-ons to inc 194, in sequence. **(A) Runbook:** new **`ops/accounts-authentik-setup.md`** — the
step-by-step for the maintainer to stand up the account platform (Authentik) + wire ORCID so the **live** sign-in
works (host behind TLS → register an ORCID API client → add ORCID as an OIDC source → **emit the ORCID iD as an
`orcid` claim** → create the callosum **public/PKCE** provider with the loopback redirect → set `CALLOSUM_OIDC_*`
in `.env` → live-verify); referenced from the README + the design spec. **(B) Superuser role:** an **`is_superuser`**
flag keyed off the **verified ORCID claim** on the signed-in session, matched against a **`CALLOSUM_SUPERUSER_ORCIDS`**
env allowlist (`app_settings.py`: `_normalize_orcid`/`superuser_orcids`/`is_superuser_orcid`; surfaced in
`GET /settings`'s `account` block + a "· superuser" indicator in `35_settings.jsx`). **Verified, not self-asserted**
(keys off the id-token claim, not request data → can't be claimed via the API); **env-config, not hardcoded** — the
maintainer's ORCID `0000-0002-2206-0325` lives in the gitignored `.env`; *capabilities deferred* (the flag gates
nothing yet — a later decision, backlog). **No new endpoint/surface/egress/migration** (additive field + FE text in
the already-claimed `35_settings.jsx`). **Audit addendum** to `2026-06-29_orcid-account.md` **PASS** (verified-keyed,
env-config); **Principles → A-A** aligned (an authorization flag from a verified identity — non-accusatory, no opaque
score). pytest **669 passed, 1 skipped** (+3 superuser tests in `tests/test_auth_oidc.py`, now 13); `ruff` clean; QA
surface **132/132 API + 661/661 FE, 0 uncovered**; headed driver re-verified (no unconfigured-UI regression). (Also
corrected inc-194's "+12" test-count references to the actual **+10**.) Notes: `INCREMENT-195-NOTES.md`. **NEXT:** the
maintainer's live sign-in via the runbook (stand up Authentik) → then SP2 (email/Google = platform-config) → SP3
opt-in **sync** (the library-egress step — its own design + heavy A-A pass) → SP4 sharing; superuser *capabilities*
when a concrete need arises.

Earlier — increment 194 (accounts SP1 — optional "Sign in with ORCID", OIDC, identity-only):
the first slice of the optional-account arc (backlog #15), reframed via brainstorm into **local-first + an opt-in
account** (the Zotero shape; design spec `…/specs/2026-06-29-accounts-optional-identity-design.md`, platform eval
`…/research/2026-06-29-oidc-platform-eval.md` → **Authentik**, the maintainer's pick). The app stays fully
local/offline with **no account by default**; sign-in is opt-in + additive + **identity-only — no library data leaves
the machine**. New **`app/backend/api/auth/`** — `oidc.py` (authorization-code + **PKCE**, loopback redirect, JWKS
id-token verify via lazy **`PyJWT[crypto]`**, injectable for tests) + `router.py` (`GET /auth/login` → authorize URL
[503 unconfigured / 422 non-loopback], `GET /oauth/callback` → exchange+verify+store+**`profile_repo.upsert_profile`**
[the payoff: the verified ORCID populates My-Pubs], `POST /auth/logout`). **Key architecture:** callosum is **one OIDC
client of the callosum account platform** (Authentik), **not ORCID directly** — the platform brokers ORCID + passes
the **verified ORCID iD as a claim**, so SP2's email/Google = platform-config, **no app change**. Tokens stored via
the inc-152 `_set_secret` (keychain/file, **write-only** — `GET /settings`'s `account` block reports only the verified
identity, never tokens); `/oauth/callback` is exempt from the inc-168 gate (a browser navigation, the inc-172 gotcha;
opaque code+state); default-OFF (no issuer/client_id env → `/auth/login` 503). `35_settings.jsx` gained an **Account**
section (Sign in / Sign out / honest "not set up" note; no new CSS). **Audit `2026-06-29_orcid-account.md` PASS**
(PKCE+state, loopback-validated redirect → no open-redirect, JWKS id-token verify, write-only tokens, SSRF-safe
config-derived endpoints, safe callback exemption); **Principles → A-A consent value** (an emergent value adopted
deliberately; opt-in, default-off, identity-only — the egress invariant untouched). New dep **`PyJWT[crypto]`**
(justified — JWT verification must not be hand-rolled; lazy-imported); **no migration** (`profile.orcid` existed).
pytest **666 passed, 1 skipped** (+10 `tests/test_auth_oidc.py`); `ruff` clean; QA surface **132/132 API + 661/661 FE,
0 uncovered** (`route_45_account.md`); help corpus + README + CLAUDE updated (`HELP-DOCS-SYNCED` → 194). **The live
ORCID round-trip is the maintainer's MANUAL check** (stand up Authentik + the ORCID connector + the loopback redirect,
host-agnostic; set `CALLOSUM_OIDC_ISSUER`/`CLIENT_ID`); the flow + pure helpers are pytest-covered + the unconfigured
UI headed-verified (`.local/visual/drive_inc194_account.py` — renders the not-set-up note, no Sign-in button, no token
in `/settings`, 0 console/page/genai). Also this turn: fixed the **204 logout-route** bug (return a `Response`, the
house pattern); recorded the **superuser** as ▲ NEXT-UP in the backlog (a `CALLOSUM_SUPERUSER_ORCIDS` verified-ORCID
allowlist → an `is_superuser` flag for the maintainer's ORCID `0000-0002-2206-0325`; capabilities TBD). Notes:
`INCREMENT-194-NOTES.md`. **NEXT:** the **superuser role** (right after this), then **SP2** email/Google login
(platform-config, no app change) → **SP3** opt-in **sync** (the only step that moves library data off-machine — its
own design + a heavy Principles/A-A pass) → **SP4** sharing.

Earlier — increment 193 (Google Docs setup automation — Quick Tunnel + one-file add-on bundle):
the user flagged the Google Docs install ("migrate a domain + paste 3 files") as too much for an end user. Two of
the steps are Google's platform constraints (a cloud add-on can't reach localhost → a bridge must exist; no
"install a local add-on" button short of Marketplace publishing); the rest was setup tax, now cut (user-approved
scope = both). **`tools/run_tunnel.py --quick [--port N]`**: a **Cloudflare Quick Tunnel** (`cloudflared tunnel
--url http://localhost:<port>`) — **zero setup** (no account/domain/nameservers/`tunnel create`/config), prints a
throwaway `trycloudflare.com` URL to paste into the add-on; the named-tunnel (stable URL + cite-only ingress) stays
the default no-flag path. **`tools/build_gdocs_addon.py`** → committed **`adapters/googledocs/callosum-gdocs.gs`**:
concatenates `gdocs_core.js` + `Code.gs` + `sidebar.html` (inlined as a JSON string via
`HtmlService.createHtmlOutput(_callosumSidebarHtml())`, replacing `createHtmlOutputFromFile`) into **one** paste-able
file (Apps Script's single global scope makes `gdocs_core`'s `globalThis.CallosumCore` visible). README leads with an
"Easiest setup (Quick Tunnel — no account)" 4-step path. **Audit:** addendum to `2026-06-28_googledocs-tunnel.md`
**PASS** — `--quick` is opt-in/non-default/token-gated/**informed** (the runner prints the tradeoff) but drops the
cite-only ingress allowlist → the bearer token is the sole boundary (A-A consent value; the named cite-only path
remains for hardening); the bundle is not a security change. **Principles non-triggering** (tooling/packaging, not a
claim/signal). pytest **656** (+2 `tests/test_gdocs_bundle.py`: bundle-in-sync + inlines-core-and-sidebar — drift-safe
like `test_frontend_assembly`); `ruff` clean; `node --check` on the bundle (valid JS); **no app code / frontend /
migration / dependency change** (cloudflared already required), QA surface unchanged (132 API / 657 FE), no
help-corpus change (setup tooling, not in-app behavior). **The real quick-tunnel + in-Docs round-trip is the user's
manual check** (live cloudflared egress + Google's cloud — un-automatable from the repo). Also this turn: pointed the
user's gitignored `cloudflared-config.local.yml` cite rule at `localhost:8888` (their port). True one-click
"install from the Workspace Marketplace" remains the only thing not replaced (a GCP project + OAuth verification +
review — deliberately not taken for a local-first tool). Notes: `INCREMENT-193-NOTES.md`. **NEXT:** the user's pick —
their live Google Docs test (now ~4 steps) or a fresh track.

Earlier — increment 192 (Feed SP2c-3 part 2 — auto-refresh cadence; **#28 COMPLETE**): an opt-in,
staleness-gated auto-refresh-on-open, the last open item on the discovery track. **Frontend-only.** `FeedPane`
(`30e_feed.jsx`) gains an **"Auto-refresh on open"** checkbox (`localStorage["callosum.feedAutoRefresh"]`, **default
off**) + an `active` prop + an effect: when the Feed tab is open **&& autoRefresh && a source is stale** (newest
`last_polled_at` > 6h ago, or never polled), it fires the existing `refresh()`; **throttled ≤1/min**, skipped while
refreshing, self-quiescing after a poll (the naive-UTC timestamp is treated as UTC so the compare isn't tz-skewed).
`30c_frame.jsx` passes `active={activeTab==="feed"}`. **Pull-first, no background daemon** — the refresh fires only on
*your* open, only if opted in, only if stale (mirrors the inc-98/136 watched-folders rescan); default-off → zero change
for anyone who doesn't want it. **No backend change** (drives the audited `/feed/refresh` on a condition → no audit
gate); **Principles non-triggering** (a UI convenience; pull-only/opt-in posture preserved). `.feed-autorefresh` CSS,
tokens only. pytest **654** unchanged (`test_frontend_assembly` 5/5); QA surface **132/132 API + 657/657 FE, 0
uncovered** (the checkbox claimed by `route_44`); help corpus's Feed section documents the toggle (`HELP-DOCS-SYNCED`
→ 192). **Verified headed, no egress** (`.local/visual/drive_inc192_autorefresh.py` — a stale subscription: toggle off
→ 0 items, tick **Auto-refresh on open** → the stale source auto-polls with no manual Refresh → the item appears; 0
console/page/genai). Notes: `INCREMENT-192-NOTES.md`. **This COMPLETES the literature discovery track #28** — Search
(Crossref + PubMed + axis-relevance) + Feed (bioRxiv + medRxiv + PubMed-keyword + journal-ISSN, manual or opt-in
auto-refresh, with abstracts). No open #28 sub-tasks remain (a true background polling daemon is deliberately NOT built
— pull-first by design). **NEXT:** the user's pick — the live Google Docs add-on test (theirs) or a fresh track.

Earlier — increment 191 (Feed SP2c-3 part 1 — medRxiv source + PubMed abstracts via efetch): two
backend Feed enrichments, **no frontend change**. **medRxiv:** `BioRxivFeedSource` is now **server-configurable**
(`server="biorxiv"|"medrxiv"` → kinds `biorxiv_category`/`medrxiv_category`; one class, `kind`/`label`/`suggestions`
became instance attrs; the default fetcher bakes in the server; `_biorxiv_fetch` takes a `server` param — a **fixed
literal** in the URL path → no SSRF; `record_to_entry` derives the journal label + content-URL host from each record's
own `server` field; new `MEDRXIV_CATEGORIES`); `build_default_feed_registry` registers both servers → the data-driven
Follow picker shows both with **no frontend edit**. **PubMed abstracts:** `fetch_abstracts` (NCBI **efetch**
`rettype=abstract&retmode=xml`) + `_parse_abstracts` (a **targeted regex** — split on `<PubmedArticle>`, per-PMID
`<AbstractText>`, strip tags, `html.unescape` — **not an XML parser → no XXE**, rule #4 / the inc-75 pattern);
`PubMedKeywordFeedSource` gained an injectable `abstract_fetcher` (default `fetch_abstracts`) + enriches each entry's
abstract (fail-closed — a failed efetch never sinks the poll; abstracts fill the existing FeedPane Abstract toggle).
**Public-metadata egress** — NOT the Gemini gate. **Audit:** addendum 3 to `2026-06-28_feed.md` **PASS** (both on the
already-audited hosts; medRxiv server = fixed literal; efetch ids = digit-validated bound param + regex parse,
fail-closed). **Principles non-triggering**; pull-only/augment-never-filter unchanged. pytest **654** (+2: medRxiv
server config + server-aware label/URL; efetch parse/enrich/fail-closed; the default-registry test asserts 4 kinds);
`ruff` check + `format --check` clean; QA surface **132/132 API + 655/655 FE, 0 uncovered** (no new surface);
help corpus's Feed section lists all four source types (`HELP-DOCS-SYNCED` → 191). **Live spot-checks**
(`BioRxivFeedSource(server="medrxiv").fetch("epidemiology")` → 3 real medRxiv preprints; `PubMedKeywordFeedSource.fetch(
"crispr gene therapy")` → 3/4 entries enriched with real abstracts). **No headed run** (backend-only — medRxiv via the
data-driven picker [proven inc 189/190]; abstracts fill an existing UI element). **No migration/dependency/endpoint/
frontend change.** Notes: `INCREMENT-191-NOTES.md`. **NEXT — SP2c-3 part 2 (inc 192): the auto-refresh cadence** (a
frontend "auto-refresh on open" toggle, staleness-gated, mirroring the watched-folders on-launch rescan — pull-first,
opt-in) — closes #28 entirely.

Earlier — increment 190 (Feed SP2c-2 — the journal-by-ISSN source): a third Feed source —
**follow a journal by its ISSN** → its recent articles — that drops in with **no frontend/endpoint/surface change**
(the inc-189 data-driven Follow picker rendered the new option automatically; the QA surface map is **unchanged** at
132 API / 655 FE — the registry promise proven backend→UI). New **`journal_issn_source.py`** (`JournalIssnFeedSource`,
`kind="journal_issn"`, label "Journal (ISSN)"): polls Crossref `/works?filter=issn:<issn>&sort=published&order=desc`
(the **already-audited** Crossref host); the ISSN is **validated** (`^\d{4}-\d{3}[\dX]$`) before any request, then
passed only as a bound `filter` param (**no SSRF**); `record_to_feed_entry` reuses the audited
`crossref_provider.message_to_item` + `_published_date` (date-parts → `YYYY-MM-DD`); injectable fetcher.
`build_default_feed_registry` now registers bioRxiv + PubMed-keyword + journal-by-ISSN. **Public-metadata egress** —
NOT the Gemini gate. **Audit:** addendum 2 to `2026-06-28_feed.md` **PASS** (audited host; ISSN validated + bound
filter; no new dependency/endpoint/migration/surface). **Principles non-triggering** (a source; pull-only/augment-never
-filter unchanged). pytest **652** (+1: journal mapping/validation; the default-registry test asserts all three
sources); `ruff` check + `format --check` clean; **no migration/dependency/endpoint/frontend change**; help corpus's
Feed section lists all three source types (`HELP-DOCS-SYNCED` → 190). **Live spot-check** (`JournalIssnFeedSource.fetch(
"1476-4687", limit=3)` → 3 recent Nature articles) + **headed-verified, no egress** (`.local/visual/drive_inc190_journal.py`
— the REAL source with a fake fetcher: the `<select>` shows "Journal (ISSN)", the placeholder updates, **Follow**
`1476-4687` → a Journal-tagged subscription, **Refresh** → the polled article; 0 console/page/genai). Notes:
`INCREMENT-190-NOTES.md`. **This makes the literature discovery track #28 feature-complete — Search (Crossref + PubMed
+ axis-relevance) + Feed (bioRxiv + PubMed-keyword + journal-by-ISSN).** **NEXT (#28 optional/later, SP2c-3):** an
auto-refresh cadence; PubMed abstracts via efetch; medRxiv as a bioRxiv server option.

Earlier — increment 189 (Feed SP2c-1 — the PubMed-keyword source + a data-driven Follow picker):
makes the Feed **multi-source**. New **`PubMedKeywordFeedSource`** (`pubmed_provider.py`, `kind="pubmed_query"`): a
saved PubMed query as a Feed source — polls **`esearch` sorted by date** (`_eutils_search` gained a `sort` param,
default "relevance" for Search) → esummary → `record_to_feed_entry` (→ `FeedEntry`, posted_date from `sortpubdate`,
drops no-title-and-no-DOI); reuses the **already-audited** NCBI host (constant host, query a bound param → no SSRF).
`FeedSource` gained optional display metadata (`label`/`placeholder`/`suggestions`); **`FeedRegistry.source_meta`** +
`GET /feed/subscriptions`'s new `source_meta` field drive a **data-driven Follow picker** (a source `<select>` +
per-kind placeholder/datalist), so **adding the next Feed source is one backend `register()` — no frontend edit** (the
registry promise extended to the UI; `BIORXIV_CATEGORIES` moved to the backend). `build_default_feed_registry` now
registers bioRxiv + PubMed-keyword. `30e_feed.jsx`: the picker + a source tag on each subscription chip
(`.feed-sub-kind`); bioRxiv categories lowercased, PubMed queries keep casing. **Public-metadata egress** (PubMed) —
NOT the Gemini gate. **Audit:** addendum to `2026-06-28_feed.md` **PASS** (audited host; sort=date a bound param;
`source_meta` non-secret display metadata; no new endpoint/migration/dependency). **Principles non-triggering** (a
source + a picker; pull-only/augment-never-filter unchanged). **Rule #10:** no new API/FE surface beyond the existing
`/feed/*` + `30e_feed.jsx` (the new `<select>`/datalist claimed by `route_44`) → surface **132/132 API + 655/655 FE, 0
uncovered**. pytest **651** (+1 net: a PubMed-feed mapping/sort=date test; the default-registry test now asserts both
sources + `source_meta`; the endpoint test asserts `source_meta`); `ruff` check + `format --check` clean; **no
migration/dependency/endpoint**; help corpus's Feed section now covers the source picker (`HELP-DOCS-SYNCED` → 189).
**Live spot-check** (`PubMedKeywordFeedSource.fetch("crispr off-target", limit=3)` → 3 recent date-sorted records) +
**headed-verified, no egress** (`.local/visual/drive_inc189_feedsources.py` — two fake sources: the source `<select>`
shows both labels, switching to PubMed updates the placeholder, **Follow** → a PubMed-tagged subscription, **Refresh** →
1 polled item; 0 console/page/genai). **GOTCHA (headed harness):** kill stray `uvicorn`/`inc18*` python between rapid
re-runs (a lingering server holds the throwaway DB/port → flaky). Notes: `INCREMENT-189-NOTES.md`. **NEXT (#28
optional/later): SP2c-2** a journal-by-ISSN Feed source (Crossref `/works?filter=issn:…&sort=published`) — one
`register()` + its metadata, the Follow picker already supports it, its own audit; **SP2c-3** an optional auto-refresh
cadence + PubMed abstracts via efetch.

Earlier — increment 188 (literature Feed SP2b — the Feed tab UI): the frontend half of #28 SP2
(backend = inc 187); **completes #28 (Search + Feed)**. New **`app/frontend/js/30e_feed.jsx`** (`FeedPane`): a
persistent **Feed** center tab (beside Discover) — follow bioRxiv categories (chips with an unfollow ×; a `<datalist>`
of common categories) → **Follow** (`POST /feed/subscriptions`) → **Refresh** (async poll) → triage the polled items:
an unread dot + serif title (read rows dim), authors/posted-date/journal, a **★** star toggle, **Save** / **✓ in
library**, an **Abstract** toggle; an **All / Unread (N) / Starred** filter + **Mark all read**. Clicking a row marks
it read (optimistic + `POST /feed/items/{id}/state`); **Save** reuses `/discovery/save` (metadata-only, no PDF) +
bumps the Library refresh. **The complete polled list is shown** — read/starred are the user's own state, never an AI
filter (pull-only/opt-in posture from SP2a). Root class `discover feed` reuses the `.discover` layout; new `.feed-*`
CSS = accent-chip subscriptions + unread-dot/read-dim/star, tokens only (DESIGN rule #8). Wired via a Feed tab +
`frame-pane` in `30c_frame.jsx` (reuses `onDiscoverSaved` → `setLibRefresh`). **Frontend-only — no
backend/endpoint/migration/egress/dependency** (reuses the inc-187 `/feed/*` endpoints, already audited).
**Principles non-triggering** (a UI over the audited endpoints; pull-only/augment-never-filter unchanged). **Rule #10:**
`route_44_feed.md` gained `fe: 30e_feed.jsx` + the UI flow → surface **132/132 API + 653/653 FE, 0 uncovered**. help
corpus gained a "Following sources (Feed)" section (`HELP-DOCS-SYNCED` → 188; also covers the inc-186 PubMed line).
pytest **650** unchanged (`test_frontend_assembly` 5/5 confirms 30e is in the build + in sync); build green. **Verified
headed, no egress** (`.local/visual/drive_inc188_feed.py` — a fake FeedSource + a seeded library paper: empty state →
Follow `neuroscience` → a chip → Refresh → **3 items** [1 ✓ in library + 2 Save, unread 3] → click a row marks it read
→ ★ stars → **Save** flips a row + the paper appears in the Library tab; 0 console/page/genai). **GOTCHA (headed
harness):** kill stray `uvicorn`/`inc18*` python between rapid re-runs — a lingering throwaway server holds the DB/port
and makes the run flaky; the clean run is green. Notes: `INCREMENT-188-NOTES.md`. **This completes the literature
discovery track #28 — Search (Crossref + PubMed + axis-relevance) + Feed (bioRxiv).** **NEXT (#28 optional/later, SP2c):**
more Feed sources (journal-by-ISSN / PubMed-keyword — each a `register()` + its own audit), an optional auto-refresh
cadence, PubMed abstracts via efetch.

Earlier — increment 187 (literature Feed SP2a — engine + store + endpoints + the bioRxiv source):
the **backend** of #28 SP2 (the design-led, migration-bearing one; the user greenlit **pull-only, no auto-subscribe**;
the Feed tab UI is SP2b inc 188). **Pull-only, opt-in, no push** — you follow a source, then a refresh polls it. New
**`schema_feed.py`** (`feed_subscriptions` + `feed_items`, **migration 0021** — the discovery track's first; additive +
guarded; re-exported from `schema.py` like `schema_findings`), **`feed_repo.py`** (bound-param subscription CRUD +
`upsert_items` [INSERT-OR-IGNORE → re-poll never duplicates **or** resets read state] + list/state/mark-read/unread-
count), **`discovery/feed.py`** (a `FeedEntry` + a `FeedSource` Protocol + `FeedRegistry` + `build_default_feed_registry`
+ `refresh_subscriptions` [polls each subscription via its source; **a source that raises is skipped**] + `feed_view`
[computes `in_library` at read time, like Search]), **`discovery/biorxiv_source.py`** (`BioRxivFeedSource`,
`kind="biorxiv_category"`: pulls recent detail pages over a **server-derived date window** from the **constant**
`https://api.biorxiv.org` host, **filters the subscribed category client-side** [never in the URL → no SSRF], maps +
dedups; injectable fetcher), **`routers/feed.py`** (8 endpoints: subscription GET/POST[422 unknown kind]/DELETE,
async `POST /feed/refresh` + `GET …/{job_id}` [JobStore + a worker connection, mirrors the gap-finder], `GET /feed`
[items + unread_count], item `state`, `mark-read`), wired in `app.py` (`create_app(feed_registry=…)` +
`api.state.feed_registry`/`feed_jobs`). **Public-metadata polling** (bioRxiv) — **NOT** the Gemini gate; save reuses
`/discovery/save` (metadata-only, no PDF → no paywall circumvention). **Adding the next Feed source is one
`register()`** (the FeedRegistry mirrors the Search SourceRegistry). **Audit `.claude/security-audits/2026-06-28_feed.md`
PASS** (no SSRF; bound-param + non-destructive re-poll; additive guarded migration; no new dependency); **values
aligned** (pull-only/opt-in/no-auto-subscribe/augment-never-filter). **Rule #10:** new `route_44_feed.md` (the 8
endpoints) → surface **132/132 API + 631/631 FE, 0 uncovered**. pytest **650** (+7 `test_feed.py`: repo + cascade,
bioRxiv mapping/filter/dedup, registry, refresh-upsert + in_library view + re-poll-idempotent + failing-source-skipped,
the 8 endpoints); `ruff` check + `format --check` clean; migration head via `alembic_head()`. **help corpus deferred to
SP2b** (no UI yet — the `HELP-DOCS-SYNCED` marker stays at 186). **Live spot-check** (`BioRxivFeedSource(window_days=10,
max_pages=3).fetch("neuroscience", 5)` → 5 real preprints mapped end-to-end) confirms the live schema the hermetic
tests assume. Notes: `INCREMENT-187-NOTES.md`. **NEXT — SP2b (inc 188): the Feed tab UI** (`30c_frame.jsx`: a
subscription manager + the item list [unread/starred filters, mark-read/star, save-to-library, refresh] + an unread
badge; headed verify; help-corpus "Following sources (Feed)" + a `fe:` claim on `route_44`). Then SP2c (journal-by-ISSN
+ PubMed-keyword Feed sources — each one `register()` + its own audit; an optional auto-refresh cadence).

Earlier — increment 186 (literature discovery SP1a — the PubMed source): a second Search source
that drops into the discovery registry with **no endpoint/UI change** (the registry's promise: adding a source = one
`register()`). New **`app/backend/discovery/pubmed_provider.py`** (`PubMedSearchProvider`, `name="pubmed"`): an
injectable fetcher mirroring the Crossref one; `_eutils_search` = NCBI **esearch** (`term` → PMIDs) then **esummary**
(PMIDs → records), both GET to the **constant** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` host with the query as
a bound *param* (→ **no SSRF**), fail-closed (non-200/no-ids → `[]`); `summary_to_item` maps a record → a normalized
`Item` (title, `pmid` from `uid`, `doi` from `articleids`/`elocationid` [strict DOI regex], authors, journal, year,
the pubmed.ncbi.nlm.nih.gov URL; drops no-title-and-no-DOI; **v1 no abstract** — esummary doesn't carry it).
`build_default_registry()` now registers Crossref **+** PubMed → `/discovery/search` fans out to both with the inc-183
endpoint/UI/dedup/relevance **all unchanged**; a Crossref+PubMed overlap (same DOI) merges to one row, `sources=
("crossref","pubmed")`, pmid filled from the PubMed copy. **Public-metadata egress** (the search terms → NCBI), **NOT**
the Gemini gate; polite-pool `tool`+`email` (from Settings → Metadata access); **no new dependency** (httpx). **Audit
`.claude/security-audits/2026-06-28_pubmed-provider.md` PASS** (constant host + query-as-param; defensive response
parsing; fail-closed; no user-URL fetch; no new secret/endpoint/migration). **Principles non-triggering** (a search
*source*; the complete deduped list is still returned — augment, never filter). **Rule #10:** no new API/FE surface (a
provider behind `/discovery/search`) → surface map **unchanged 124/124 API + 631/631 FE, 0 uncovered**;
`route_43_discovery.md` notes PubMed as a registered source. help corpus's Discover section now says "Crossref +
PubMed" (`HELP-DOCS-SYNCED` → 186). pytest **643** (+4 `test_pubmed_provider.py`: summary→Item mapping,
DOI-from-elocationid + drop-empty, injected-fetcher + blank-query, cross-provider DOI dedup; the inc-183 registry test
updated to crossref+pubmed); `ruff` check + `format --check` clean; **no migration, no new dependency, no frontend
rebuild**. **Live schema spot-check** (a `crispr gene editing` query → 3 real records mapped: title/PMID/DOI/year/
`pubmed` source) confirms the live esearch→esummary schema the hermetic tests assume. Notes: `INCREMENT-186-NOTES.md`.
**NEXT (remaining #28): SP2 — the Feed tab** (subscriptions [journals by ISSN / PubMed keyword / **bioRxiv by
category**] + polling on a cadence + a read/unread/starred store; **needs a migration** — the larger, design-led one).
(Optional later: PubMed abstracts via efetch; an NCBI api_key for higher rate limits.)

Earlier — increment 185 (literature discovery SP1b — the axis-relevance highlight): a **signal**
feature (the Principles gate was run before building). New **`app/backend/discovery/relevance.py::score_axis_relevance`**
+ **`POST /discovery/relevance`** score each search result's title+abstract against the user's **axis** embeddings and
return the best-matching axis + similarity for items that clear that axis's cutoff; the Discover tab (`30d_discover.jsx`)
overlays a **"likely: &lt;axis&gt; · match 0.NN"** badge (`.discover-relevance`, an accent chip) on matched rows — a
**hint, never a filter/reorder**; a below-cutoff item carries **no badge** (= *no strong axis match*, **not
"irrelevant"** — silence-≠-certificate); my-publications excluded (authorship, not a topical lens). **Fully local — no
egress, no DB write** (axis vectors embedded fresh with the SAME prep the scorer uses, so the match is `round(cos, 2)`
= the number an axis card shows; numpy unit-cosine). Best-effort overlay (the inc-183 search endpoint is untouched; a
failed/empty call → the complete list still shows, no badges). `_discovery_model` caches the heavy embedding model on
`app.state` (injected wins for tests; mirrors citations.py `_suggest_model`). **Principles gate (rule #9) run —
aligned:** signal-not-verdict (#2) + silence-≠-certificate (#6) + human-is-the-filter (#3/#5, never hides/reorders) +
no-opaque-composite (#7, one labeled cosine); the declined misaligned path = a curated "here's what matters" list that
hides the rest. **Audit `.claude/security-audits/2026-06-28_discovery-relevance.md` PASS** (local read-only signal;
bounded inputs [items 1..50]; no egress/DB-write; bound-param read). **Rule #10:** `route_43_discovery.md` gained
`/discovery/relevance` + the highlight assertions → surface **124/124 API + 631/631 FE, 0 uncovered**. help corpus's
Discover section now describes the badge (`HELP-DOCS-SYNCED` → 185). pytest **639** (+5 `test_discovery_relevance.py`:
best-axis-above-cutoff, per-axis cutoff, my-pubs excluded, no-axes/no-items→{}, endpoint shape+422); `ruff` check +
`format --check` clean; build + assembly green; **no migration, no new dependency** (numpy already present). **Verified
headed, no egress** (`.local/visual/drive_inc185_relevance.py` — a fake registry + fake 2-D keyword model + a seeded
"Attention models" axis: 3 rows shown [complete list], **exactly 1** badge "likely: Attention models · match 1.00" on
the matching row, none on the others; 0 console/page/genai). Notes: `INCREMENT-185-NOTES.md`. **NEXT (remaining #28):**
SP1a (a PubMed provider — NCBI E-utilities httpx client, `register()` one provider, no UI edit, its own audit) / SP2
(the Feed tab — subscriptions + polling + a read/unread store; bioRxiv by category, needs a migration).

Earlier — increment 184 (literature discovery SP1 frontend — the Discover/Search tab): the frontend
half of #28 SP1 (backend = inc 183). New **`app/frontend/js/30d_discover.jsx`** (`DiscoverPane`): a query box →
`GET /discovery/search?q=&limit=25` → a dense, **keyboard-triage** results list — **j/k** move the cursor
(`.discover-item.cur`, scrolled into view), **s** saves the focused row, **Enter** toggles its abstract (Enter *in the
box* searches); each row shows a serif title + `.paper-meta` (authors≤3 + year + journal) + **source pill(s)** + either
a **Save** `.btn-link` or a green **✓ in library** marker; **Save** → `POST /discovery/save` (metadata-only, deduped,
**no PDF**) flips the row + bumps the Library refresh. **The complete deduped list is always rendered — no client
filter/reorder** (augment-never-filter; SP1b's axis-relevance highlight will *mark*, never hide). Wired via a persistent
**Discover** tab + a `frame-pane` in `30c_frame.jsx` (`onDiscoverSaved` → `setLibRefresh` in `40_app.jsx`). New
`.discover-*` CSS = the `.paper` card recipe, **tokens only** (DESIGN rule #8). **Function-hoist across chunks**
(30d's `DiscoverPane` referenced by 30c) — the inc-182 IIFE precedent. **Frontend-only — no backend/endpoint/migration/
egress/dependency** (reuses the inc-183 endpoints, already audited). **Principles non-triggering** (the complete list;
metadata-only save; the human decides). **Rule #10:** `route_43_discovery.md` gained `fe: 30d_discover.jsx` + the UI
flow → surface **123/123 API + 631/631 FE, 0 uncovered**. help corpus gained a "Finding new papers (Discover)" section
+ brought "Highlights and notes" current for the inc 175–179 reading-pane run (`HELP-DOCS-SYNCED` → 184). pytest **634**
unchanged (`test_frontend_assembly` 5/5 confirms 30d is in the build + in sync); build + assembly green. **Verified
headed, no egress** (`.local/visual/drive_inc184_discover.py` — a fake registry of 3 items, one already in the library:
3 rows shown, 1 ✓-in-library + 2 Save, **j** moves the cursor, **Save** flips row 0 + it appears in the Library tab; 0
console/page/genai). Notes: `INCREMENT-184-NOTES.md`. **This completes #28 SP1 (the Search tab — backend inc 183 +
frontend inc 184). NEXT:** SP1a (a PubMed provider — `register()` one provider, no UI edit, its own audit) / SP1b (the
axis-relevance highlight — score items vs the user's axis embeddings, *mark* likely matches without hiding any) / SP2
(the Feed tab — subscriptions + polling + a read/unread store; bioRxiv by category).

Earlier — increment 183 (literature discovery SP1 — the SourceProvider registry + Crossref search +
save endpoints): the backend of the **Discover/Search track (#28)** (the in-app Search tab is SP1's frontend half,
inc 184), built engine-first like inc-107→108. New **`app/backend/discovery/`**: `providers.py` (a frozen normalized
**`Item`** — `dedup_key` = DOI→PMID→normalized-title, `merged_with` unions `sources` + fills blank fields; a
`SourceProvider` Protocol + `SourceRegistry` whose `search_all` **skips a provider that raises**, so one bad source
never sinks the search, and adding a source = `register()` one provider with **no endpoint/UI edit** — mirrors the
acquisition-resolver + pane registries; `build_default_registry()` registers Crossref now, PubMed/bioRxiv drop in
later), `crossref_provider.py` (a keyword search over the **constant** `https://api.crossref.org/works` — injectable
fetcher for hermetic tests, polite-pool mailto from `resolved_mailto`, query as a bound *param* not the host → **no
SSRF**; `message_to_item` strips JATS via `abstract_plain_text` + **drops no-title-and-no-DOI**), `search.py`
(`run_search` fans out → dedups across providers → marks `in_library` via `find_existing_paper_by_identity`;
`save_item` is **metadata-only + dedup-aware** — `imported_source="discovery-import"` [kept out of the crossref-update
allowlist like user-edited], re-save returns the same id with `created:False`, and **fetches no PDF** so the
OA-acquire lane is untouched [no paywall circumvention]). New `routers/discovery.py` — **`GET /discovery/search?q=&limit=`**
→ `{items:[…]}` (registry from `app.state.discovery_registry`) + **`POST /discovery/save`** (bounded `SaveRequest` →
`save_item` + commit). Wired in `app.py` (import + `create_app(discovery_registry=None)` param + state init + include).
**AI augments, never filters** — the complete deduped list is returned (axis-relevance highlight is SP1b, a hint not a
gate); public-metadata egress, **NOT** the Gemini gate. **Audit `.claude/security-audits/2026-06-28_discovery-search.md`
PASS** (bounded inputs; bound-param persistence; constant host + query-as-param → no SSRF; no user-URL fetch / no PDF
retrieval; public-metadata not the library gate; no new dependency). **Principles non-triggering** (no claim/judgment).
**Rule #10:** new `route_43_discovery.md` declares the 2 API endpoints → surface **123/123 API + 618/618 FE, 0
uncovered**. pytest **634** (+15 `test_discovery.py`: Item dedup-key/merge, Crossref mapping + JATS strip +
drop-no-title-no-DOI, provider injected-fetcher + blank-query, registry skips-a-failing-provider + default-registry,
run_search dedup + in_library, save_item create + dedup, the 2 endpoints' shape/422/save→search-in_library cycle,
registry-accepts-a-new-provider); `ruff` check + `format --check` clean; **no migration, no new dependency, no
frontend change** (no `build_frontend`). **help corpus deferred to inc 184** (no usable UI yet — honest; the
`HELP-DOCS-SYNCED` marker stays). Notes: `INCREMENT-183-NOTES.md`. **NEXT — SP1 frontend (inc 184):** the **Search
tab** in `30c_frame.jsx` (query box → `/discovery/search` → result rows with source labels + an in-library marker +
one-click **Save** → `/discovery/save`; keyboard triage), headed verify, help-corpus + a `fe:` claim on `route_43`.
Then SP1a (PubMed provider — `register()` one provider) / SP1b (axis-relevance highlight) / SP2 (the Feed).

Earlier — increment 182 (extract LibraryFrame from 30_viewer — discovery SP0 prereq): the start of
the **literature-discovery track (#28)**, approved with Cliff (Search-tab-first; all sources [Crossref leads,
PubMed/bioRxiv as drop-ins]; axis-relevance highlight as SP1b; bioRxiv in the Feed). Design spec:
`.claude/docs/specs/2026-06-28-discovery-search-design.md`. **This increment is the prerequisite split:**
`LibraryFrame` (the center tab shell) moved from the maxed `30_viewer.jsx` (599/600) → new **`js/30c_frame.jsx`**
(verbatim; hoists in the IIFE so it still renders PdfViewer/PaperList/MyPubsDashboard; App unchanged) → 30_viewer
**599→557** (room for the Search-tab branch, which lands in 30c_frame). **QA:** `route_00` `fe:` repointed to claim
30c_frame.jsx → surface **121/121 API + 618/618 FE, 0 uncovered**. Frontend-only — no backend/migration/egress;
`test_frontend_assembly` 5/5; pytest **619**. **Behavior-preserving (headed)** — re-ran the inc-176 driver: a PDF
tab opens via LibraryFrame + the notes filter works; 0 console/page/genai. Notes: `INCREMENT-182-NOTES.md`. **NEXT:
SP1 (inc 183)** — the SourceProvider registry + Crossref provider + `GET /discovery/search` + `POST /discovery/save`
+ the Search tab (keyboard triage, one-click metadata save) in `30c_frame.jsx`; audit + a `route_43_discovery.md`.

Earlier — increment 181 (third-party software NOTICE pass — credit-the-lineage Lane B, backlog #8):
`THIRD-PARTY-NOTICES.md` credited citeproc/CSL/the methods but **no runtime/build dependencies** — a gap for a public
AGPL repo. Added a **Runtime & build dependencies** section crediting every shipped Python (`requirements.txt`) + JS
(`package.json` + CDN) dep with its license, grouped (MIT: FastAPI/SQLAlchemy/Alembic/esbuild/React; BSD-3-Clause:
Starlette/Uvicorn/httpx/scikit-learn/NumPy/SciPy; Apache-2.0: sentence-transformers/google-genai/pdf.js;
Apache/MIT: sqlite-vec; AGPL-3.0: **PyMuPDF** [noted as reinforcing callosum's license] + citeproc-js) + a note that
the first-run models are author-distributed (not redistributed). **Docs-only** — no app/migration/egress/surface
change; pytest **619**. **#8 status:** Lane A (method credit + add-to-library across statcheck/p-curve/GRIM, inc 180)
+ Lane B (this) done → **#8 effectively complete** (retraction/gap-finder are data-source-driven, credited at the
NOTICE level, not the add-a-paper pattern). Notes: `INCREMENT-181-NOTES.md`. **NEXT — the clean-autonomous queue is
genuinely empty:** reading-pane is split-gated; the big tracks (#28 discovery, #23–25 auditors) need a brainstorm +
the user's graduation call; #3/#5 need a decision; the Google Docs live test is the user's.

Earlier — increment 180 (credit-the-lineage: statcheck in-context credit + a shared .method-credit
recipe — backlog #8): honors the credit-the-lineage values principle for the one method that lacked it. statcheck
(inc 95) now has the in-context credit block + one-click **＋ add to library** (Nuijten, Hartgerink, van Assen,
Epskamp & Wicherts 2016, *Behavior Research Methods* 48:1205–1226 — verbatim from THIRD-PARTY-NOTICES) that GRIM
(127) + p-curve (126) already had, via a new `STATCHECK_CSL` + `StatcheckCredit` in `06_methods_statcheck.jsx`
(reuses the inc-93 `/library/import`). **DESIGN Pass-2 consolidation:** the byte-identical `.grim-credit` +
`.pcurve-credit` duplicates → one canonical **`.method-credit`**/`.method-credit-sub`; grim + p-curve repointed
(className-only, no visual change). Frontend-only — no new endpoint/migration/egress; **Principles-aligned**
(strengthens credit, the cautionary gate is non-triggering); QA surface **121/121 API + 618/618 FE** (statcheck's
add-to-library button covered by route_33); assembly 5/5; pytest **619**. **Headed-verified, no egress**
(`.local/visual/drive_inc180_credit.py`: statcheck ＋ add-to-library → the Nuijten paper lands in `/papers`; the
repointed GRIM credit still styles; 0 console/page/genai). Notes: `INCREMENT-180-NOTES.md`. **Remaining on #8:**
in-context credit for the retraction / gap-finder surfaces + the Lane-B dependency NOTICE pass. **NEXT:** the
clean-autonomous queue stays thin (reading-pane is split-gated; #3/#5 + bigger tracks need the user's call; the
Google Docs live test is the user's).

Earlier — increment 179 (mark-nav keyboard hotkeys — reading-pane): **`[`** / **`]`** step to the
prev/next highlight (the keyboard pairing for the inc-177 Mark buttons) — a `window` keydown effect gated to the
**visible** viewer (`scrollRef.current.offsetParent !== null`, so a mounted-but-hidden tab doesn't respond) + not
typing (`activeElement` not INPUT/TEXTAREA/contentEditable); button tooltips show the keys. Frontend-only — no
backend/migration/egress; QA surface **121/121 API + 616/616 FE** (a window listener, not a tracked element);
assembly 5/5; pytest **619**. **Headed-verified** (`.local/visual/drive_inc179_markkeys.py`: `]`/`[` flash
next/prev; 0 console/page/genai). **⚠ RULE-#1: `30_viewer.jsx` is now 599/600 — MAXED. Any further viewer feature
MUST be preceded by another split** (extract a cohesive low-coupling unit, the inc-176 precedent). The reading-pane
run (175 scroll · 176 split+filter+search · 177 mark buttons · 179 mark hotkeys) is **complete for now**. Notes:
`INCREMENT-179-NOTES.md`. **NEXT — the clean-autonomous queue is genuinely dry:** further reading features are
split-gated + diminishing; #3/#5 are decision-gated; the high-value **Google Docs live test** is the user's; bigger
moves (discovery #28, credit-the-lineage backfill #8, statcheck test forms #27) are below-the-cut tracks needing a
design pass + the user's go.

Earlier — increment 178 (README front-door — backlog #11): rewrote the stale ("Increment 73")
`README.md` into a current contributor front door. Brought the feature list current (LibreOffice/Word/Google Docs
adapters, BYOK multi-provider AI incl. zero-egress local, retraction/p-curve/GRIM/statcheck, gap-finder, My
Publications, OA acquisition, merge, reading-pane, import-beyond-Zotero) + added the missing onboarding essentials:
the **`npm install` + `python tools/build_frontend.py`** step (was absent — a real trap), venv + cross-platform
commands, first-run model-download + auto-migrate notes, a **Configuration & privacy** table (both egress gates +
BYOK + `CALLOSUM_DB_URL`/`CALLOSUM_LIBRARY_DIR`), a **Security note** (127.0.0.1 / no auth / opt-in cite-only Remote
access), **Known limitations**, an honest **"Built with AI assistance"** note, and credit/license pointers (only
files that exist: `THIRD-PARTY-NOTICES.md` / `CONTRIBUTING.md` / `LICENSE` — SECURITY/CITATION/.env.example are
backlog #20, not linked). **Docs-only** — no app/migration/egress/surface change; pytest **619**. Per #11's "your
voice — never auto-shipped": shipped as an **accurate draft** (replacing actively-stale public content, the
CLAUDE "fix README opportunistically" directive) with the **voice pass + a screenshot left to the maintainer** (a
`<!-- TODO(maintainer) -->` placeholder). Notes: `INCREMENT-178-NOTES.md`. **NEXT:** mark-nav hotkeys (the keyboard
pairing for the inc-177 buttons), or — honestly — the clean-autonomous queue is dry (reading-pane remainder is
cap-tight/diminishing; #3/#5 are decision-gated; the high-value Google Docs live test is the user's).

Earlier — increment 177 (next/prev-mark navigation — reading-pane): **◂ Mark** / **Mark ▸**
toolbar buttons cycle through a paper's highlights in page order (wrapping), flashing each via `jumpToAnnotation` —
review marks without hunting the Notes panel. `markCursorRef` + `stepMark(dir)` (sorts `annotations` by page then
id; uses the always-fresh `annotationsRef`); buttons reuse `.pdf-annot-toggle` (no new CSS, rule #8). 30_viewer
573→**586**. Frontend-only — no backend/migration/egress; QA surface **121/121 API + 616/616 FE** (buttons covered
by route_32); assembly 5/5; pytest **619**. **Headed-verified, no egress** (`.local/visual/drive_inc177_marknav.py`:
Mark ▸/◂ flash next/prev; 0 console/page/genai). **Reading-pane run (175–177) shipped:** remembered scroll · Notes
extraction + noted-only filter + note/text search · next/prev-mark nav. Remaining (diminishing/nuanced): fit-page
(cap-risky), mark-nav hotkeys (active-tab gating), note colors, minimap. Notes: `INCREMENT-177-NOTES.md`. **NEXT:**
the high-value move is the **Google Docs add-on live test** (yours); autonomous remainder is design-gated (#3/#5) or
diminishing. **Watch (rule #1):** `25_detail.jsx` 584/600 closest.

Earlier — increment 176 (Notes-panel extraction + noted-only filter + note search — reading-pane):
unblocks the reading-pane follow-ups by relieving the `30_viewer.jsx` 595/600 cap, then ships the first two panel
features. **Split:** new chunk **`30b_notes.jsx`** = a purely-presentational **`AnnotationsPanel`** (Copy/Export +
the jump/edit/delete list); all state/handlers stay in `PdfViewer`, passed as props → 30_viewer **595→573**.
Function declaration hoists in the shared IIFE (load order moot; raw-assembly inclusion + build is the gate).
**Verified behavior-preserving** by re-running the inc-144 driver (Copy/Export digest identical). **Features (in the
extracted panel):** a **Noted** checkbox (only highlights with a note) + a **search** box (matches note OR
highlighted text, case-insensitive; head shows `shown/total`). CSS `.pdf-annot-filter`/`.pdf-annot-search`
(conforms to `.searchbar input` + tokens, rule #8). **QA (rule #10):** the panel's elements moved chunks →
`route_32_viewer_annotations.md` `fe:` repointed to `30_viewer.jsx, 30b_notes.jsx`; surface **121/121 API +
612/612 FE, 0 uncovered**. Frontend-only — no backend/migration/egress; assembly 5/5; pytest **619**; no Python →
ruff n/a. **Headed-verified, no egress** (`.local/visual/drive_inc176_notesfilter.py`: search 'positional'→1 [text]
/ 'core'→1 [note] / Noted→1; 0 console/page/genai). **Watch (rule #1):** `25_detail.jsx` now the closest at
**584/600**; 30_viewer relieved to 573. Notes: `INCREMENT-176-NOTES.md`. **NEXT:** more reading-pane (next/prev-mark
hotkeys, fit-page, note colors, minimap) now fit in 30_viewer's headroom; or the design-gated #3/#5; or elsewhere.

Earlier — increment 175 (remembered scroll position per paper — reading-pane follow-up): reopening
a PDF now **resumes where you left off**. `PdfViewer.onScroll` persists the scroller's `scrollTop` to
`localStorage["callosum.pdfScroll.<paperId>"]` (throttled ≤1/500ms); the render effect's post-render block restores
it **once per paper-open** (`restoredPaperRef`) — a citation/annotation **`target` wins**, and never on a zoom
re-render. **Did NOT restructure the fragile render core** (the inc-34/35 alignment invariants) — only added a
throttled save + a guarded restore. **Rule-#1 headroom:** 30_viewer was 595/600 → relocated the **pure**
`buildAnnotationDigest` (inc-144 digest) to `00_lib.jsx` (its proper home; `copyDigest`/`exportDigest` still call it
via the shared IIFE scope) → 30_viewer back to **595** with the feature (briefly hit 602, compacted the new blocks).
"Follow your heart" pick over keyboard-zoom (Ctrl+± fights the browser's own zoom — a UX call left for Cliff).
Frontend-only — no backend/migration/egress; QA surface unchanged (121/121 API + 608/608 FE); assembly 5/5; pytest
**619**. **Headed-verified, no egress** (`.local/visual/drive_inc175_scroll.py`: tall 4-page PDF → scroll to 600 →
saved 600 → **reload (new session) + reopen → restored 600**; PDF renders post-refactor; 0 console/page/genai).
**WATCH (rule #1): `30_viewer.jsx` is again at 595/600 — a real Notes-panel extraction is the proper next headroom
move before more viewer features.** Remaining reading-pane follow-ups (keyboard-zoom [browser-conflict], next/prev-mark
hotkeys, noted-only filter + note search, free-form note colors, minimap marker) need that split / a decision.
Notes: `INCREMENT-175-NOTES.md`. **NEXT:** the autonomous backlog above the cut is now down to design-gated items
(#3 always-on label [reverses inc-100], #5 multiple-URLs [needs a CSL convention]) + the cap-blocked reading-pane
remainder — a Cliff steer, or slide a below-cut item up.

Earlier — increment 174 (confirm before re-resolve overwrites hand-edited metadata — autonomous
backlog #3): 🔎 re-resolve passes `force=True` (inc 49) → silently overwrites a paper's metadata from Crossref,
including hand-edited papers (`imported_source == "user-edited"`). `DoiRow.resolve()` in `25_detail.jsx` now requires
a `window.confirm` (the established convention) before re-resolving a user-edited paper; non-edited papers are
unaffected. Frontend-only — no backend/migration/egress; 25_detail 579→584 (under the 600 cap); QA surface unchanged
(121/121 API + 608/608 FE); assembly 5/5; pytest **619**. **Remaining #3 (needs Cliff):** the **always-on tag-source
label** would *reverse* the inc-100 decision ("differentiate sources aesthetically, no Details labels" — your
explicit ask), so it's design-gated, not autonomous; plus a diff toast / lock-tag (design). Notes:
`INCREMENT-174-NOTES.md`. **NEXT:** the remaining above-cut autonomous items are thin — #5 multiple-URLs needs a
CSL storage convention (one `URL` field), and the reading-pane follow-ups need a delicate `30_viewer.jsx` (595/600)
split before they fit — both want a Cliff steer.

Earlier — increment 173 (import reports parse-time skipped records — autonomous backlog #4): the
BibTeX/RIS/CSL-JSON import (inc 93) **silently dropped** entries with no title AND no DOI *at parse* (before any
count), so a 50-entry `.bib` could quietly become 47 imported. Now the three parsers in `metadata/citation_import.py`
return `(records, skipped)` (real entries whose `_*_to_csl` yielded None; CSL array items that are non-dict / lack
title+DOI), `parse_records` folds record-cap overflow into `skipped` too, `import_citations` returns `skipped`,
`ImportSummary.skipped` (additive) carries it, and `28_import.jsx` shows "· N skipped (no title or DOI)" (fixing the
old mislabel where `failed` was shown as "skipped" — `failed` [per-record create errors] and `skipped` [parse drops]
are now distinct). Symmetric with inc-155's scan "which files couldn't be read." Backend-additive — no
migration/egress/endpoint → no audit; Principles non-triggering ("silence is not a certificate"); QA surface
unchanged (121/121 API + 608/608 FE). `test_citation_import` **9/9** (bibtex junk→skipped 1, ris→0, csl malformed
array→2, import result skipped==1); frontend rebuilt; `test_frontend_assembly` 5/5; pytest **619**; ruff clean.
**Remaining on #4 (not autonomous):** per-item filename + ETA in the progress label + a cancel button (needs
cooperative job cancellation). Notes: `INCREMENT-173-NOTES.md`. **NEXT (autonomous backlog):** #5 multiple URLs
(small frontend), #3 always-on tag-source label, the reading-pane follow-ups (#mind the `30_viewer.jsx` 595/600 cap).

Earlier — increment 172 (download links carry the token under Remote access — bug fix): debugging
a user "Couldn't install: Not Found" on Settings → LibreOffice plugin → Install. **Root cause: a stale running
uvicorn** (predating the inc-162 `/integrations/libreoffice/*` routes) → 404; the current code serves them (200,
confirmed via in-process TestClient with the OS-open stubbed) → **the fix is to restart uvicorn** (no code change
for the 404). **Fixed a related latent bug found while debugging:** the **Download .oxt** + **Download manifest**
plain `<a href={API_BASE+…} download>` links bypass the inc-168 auth fetch shim (it wraps `window.fetch`, not anchor
navigations), so under **Remote access ON** they send no token → **401**. New `downloadAsset(path, filename)` in
`00_lib.jsx` (GET `fetch` → blob → `_downloadBlob`, the inc-70 tokened pattern); both links in `35_settings.jsx`
became `<button className="btn-link" onClick={downloadAsset(...)}>`. Frontend-only — no backend/migration/egress; QA
surface covered (121/121 API + **608**/608 FE, the `<a>`→`<button>` claimed by `route_35_settings`); rebuilt
`callosum-app.html`; `test_frontend_assembly` 5/5; pytest **619** unchanged; no audit/Principles trigger. **GOTCHA
(carry forward): any plain `<a download>`/`<a href>` to a callosum endpoint breaks under Remote access — use a
tokened `fetch` (e.g. `downloadAsset`).** Notes: `INCREMENT-172-NOTES.md`. **NEXT:** the user restarts uvicorn →
Install works + the Download links work under Remote access → the live in-Docs Google Docs check.

Earlier — increment 171 (Google Docs SP3 — Suggest-from-the-selection + Flatten): parity for the
Google Docs add-on (mirrors Word SP3), all in `adapters/googledocs/`, **no callosum code change**. **Suggest:**
`Code.gs::suggestFromSelection` reads the selected text (`_selectionText`, else the cursor's paragraph
`_cursorParagraphText`) → `CallosumCore.pickQueryText` → POST **`/citations/suggest`** (inc 156,
`buildSuggestRequest` caps text 4000) → the sidebar renders `formatSuggestRows`
(`[stance] Author Year · match N.NN — "quote…"` — the quote IS the reason) with **Insert** buttons. **Insert now
collapses a selection to its END** (`_cursorOrSelectionEnd`) so a Suggest insert lands *after* the sentence
(mirrors Word SP3). **Flatten:** `flattenCitations` removes every citation + bibliography NamedRange + clears the
side-store; **the text stays** — Apps Script `remove()` keeps content (the OPPOSITE of the LibreOffice
ReferenceMark trap; like Word Content Controls) — one-way, two-click-confirm in the sidebar. `gdocs_core.js` gained
`pickQueryText`/`buildSuggestRequest`/`formatSuggestRows` (mirrors the Word core) → `node --test` **13/13** (+3);
`sidebar.html` gained the Suggest + Flatten buttons; README §7 updated. **GOTCHA:** order is **still insertion-order**
(reliable NamedRange *document-order* in Apps Script is hard + untestable → the lone remaining deferred piece).
**Gates:** no new audit (reuses `/citations/suggest` [inc 156] over the audited bridge [inc 169] + the add-on audit
[inc 170]; Flatten is local DOM; no new endpoint/secret/dependency); Principles non-triggering (displays the inc-156
contract — signal not verdict, the author picks); QA surface unchanged (**121/121 API + 604/604 FE**). **Verification
reality:** the in-Docs glue runs only in Google's cloud (the user's manual check); the value is the pure mapping
(`gdocs_core.test.js` 13/13) + the proven contracts. pytest **619** unchanged (no Python touched); `node --check`
clean; no frontend rebuild. CI green (inc 170 confirmed `success`). **This completes the Google Docs adapter (SP1
bridge 168/169 + SP2 add-on 170 + SP3 171)** — and the cite-while-you-write surfaces: LibreOffice (108/162) + Word
(164–166) + Google Docs (168–171). Notes: `INCREMENT-171-NOTES.md`. **NEXT:** the user's live in-Docs check (install
per README §7 with the tunnel + callosum running) — the only thing that exercises the Apps Script glue; then
optionally true document-order on Refresh, or the broader backlog (beyond-library discovery #30 SP2, etc.).

Earlier — increment 170 (Google Docs SP2 — the Apps Script cite-while-you-write add-on, + the
inc-169 bridge LIVE-verified): the third word-processor adapter's add-on (after LibreOffice + Word), riding the
inc-169 cloudflared bridge. **First, the SP1 bridge was completed + verified LIVE end-to-end this session:** the
user did the whole-domain `clffwrkmn.net` → Cloudflare migration (records imported, all set "DNS only"/grey,
MX/SPF/**DKIM** confirmed by `nslookup` against Cloudflare's NS = exact match vs HostGator; nameservers
`veda`/`vin.ns.cloudflare.com` switched + propagated), then `cloudflared login` → `tunnel create callosum`
(id `653c4da3-…`) → `route dns` → ran the tunnel + an **isolated** throwaway callosum on :8080 (Remote access ON +
a known token, empty library, file key-store forced). **Through `https://callosum.clffwrkmn.net`:** `/papers?q=`
no-token → **401**; with token → **200**; `/citations/styles` → **200**; `/settings` + `/` → **404** even with a
valid token — both boundaries (the inc-168 token + the cite-only ingress) confirmed live; throwaway instances torn
down. Also (SP1 refinement): `tools/run_tunnel.py` now prefers a **gitignored** `cloudflared-config.local.yml`
(the user's filled copy) over the committed placeholder template (`_config()`), so the tunnel id/creds path never
get committed; `.gitignore` covers it. **Then SP2 — the add-on** (all in `adapters/googledocs/`, **no callosum
code change**): `Code.gs` (the Apps Script glue — `onOpen`/`showSidebar`; Settings in UserProperties [bridge URL +
token; **token never returned to the sidebar**]; `_fetch` via UrlFetchApp with `Authorization: Bearer` + friendly
401/404/4xx; `searchPapers`/`insertCitation`/`refreshDocument`/`listStyles`/`setStyle`; DOM helpers
`_wrapNamedRange`/`_setRangeText`[replace+recreate — the setString-destroys-the-mark trap]/`_rebuildBibliography`),
`sidebar.html` (HtmlService UI, `google.script.run`), `appsscript.json` (V8; scopes `documents.currentonly` +
`script.external_request` + `script.container.ui`), and **`gdocs_core.js`** — the pure mapping, **BOTH `node --test`-ed
AND loaded by GAS** (IIFE → `module.exports` in Node / `globalThis.CallosumCore` in Apps Script → no duplication).
**Citation model = the Zotero pattern:** each citation a **NamedRange** (`CALLOSUM_CITATION_<uuid>`) + its CSL-JSON
in **DocumentProperties** (`cite:<uuid>`) + an insertion-order id list (`CALLOSUM_ORDER`); Refresh renders the
ordered set via `/citations/render-document` → writes each range's text back + rebuilds a managed **References**
block. The add-on **never formats** (citeproc does, server-side → matches the in-app "Cite as…"). **Reuses
`/papers?q=` + `/papers/export` (csl-json) + `/citations/render-document` + `/citations/styles`** — all already
audited/tested → **no new endpoint/surface/migration/dependency**. **Verification reality:** the in-Docs glue runs
only in Google's cloud (exercised by no one in-repo); ships best-effort-correct per the Apps Script docs — the value
is the pure mapping (`gdocs_core.test.js` **10/10**) + the proven contracts (the bridge live-verified above;
`/citations/render-document` pytest-proven, inc 107). **GOTCHAs:** order is **insertion-order v1** (cut/paste-reorder
not reflected on Refresh — reliable NamedRange document-order is hard + untestable in GAS, deferred); `gdocs_core.js`
must be added to the GAS project alongside `Code.gs` (it sets `globalThis.CallosumCore`). **Audit
`.claude/security-audits/2026-06-28_googledocs-addon.md` PASS** (token also in Google UserProperties = the user's
opt-in, inherent to a cloud add-on, write-only to the sidebar + not logged + revocable; least-privilege scopes; no
new egress vector beyond the audited bridge; cite-only ingress = the hard boundary). **Principles:** a field-placer
reusing the audited citeproc render → non-triggering. **QA (rule #10):** no new callosum API/FE surface (an external
add-on reusing existing endpoints) → surface map unchanged (**121/121 API + 604/604 FE, 0 uncovered**), no new route
(like the inc-157 LO suggest macro). help corpus's Remote-access note now points to the add-on (`HELP-DOCS-SYNCED` →
170). pytest **619** unchanged (SP2 touches no Python app code); `node --test` 10/10; `node --check` on
`gdocs_core.js` + `Code.gs`; `appsscript.json` valid; `ruff` clean; no frontend rebuild. **This completes the
cite-while-you-write surfaces: LibreOffice (108/162) + Word (164–166) + Google Docs bridge & add-on (168–170).**
Notes: `INCREMENT-170-NOTES.md`. **NEXT (Google Docs SP3):** Suggest-from-the-selection (`/citations/suggest`,
inc 156) + Flatten (live → static) + true document-order scanning; then the user's live in-Docs check (install per
README §7 with the tunnel + callosum running).

Earlier — increment 169 (Google Docs SP1 — the cloudflared bridge, cite-only): the user wanted
`callosum.clffwrkmn.net` but "only touch the callosum element" + granted SSH/winget. **Read-only recon (via the
granted, key-authed SSH) killed the reverse-tunnel path:** clffwrkmn.net is **HostGator cPanel shared hosting**
(`gator3026`, jailshell) that **prohibits `ssh -R`** (tested: "remote port forwarding failed"), reaps long-running
processes, no Node → it can't be the relay. The fitting path (chosen): **Cloudflare subdomain delegation** — add
ONLY `callosum.clffwrkmn.net` as a free Cloudflare zone + **two NS records at HostGator** (the rest of clffwrkmn.net
untouched), then a **cloudflared** named tunnel runs on the user's PC (**outbound-only, no inbound port**) and serves
it. **Cite-only at the tunnel:** new `adapters/googledocs/cloudflared-config.yml` ingress forwards ONLY `/papers`,
`/papers/export`, `/citations/{render-document,suggest,styles}` → `http://localhost:8080`; everything else (`/`,
`/settings`, the folder-scan routes, `/papers/{id}` edit/delete) → **404** — **validated locally** (`cloudflared
tunnel --config … ingress validate` → OK; per-URL `ingress rule`: the five cite paths → localhost, `/settings` +
`/papers/5` + `/` → 404). **Two boundaries:** the inc-168 **bearer token** (callosum's — the app can't distinguish
tunnel from local) + the **cite-only ingress** (the tunnel's). New `tools/run_tunnel.py` (locates cloudflared, runs
the cite-only tunnel; refuses while the config still has placeholders) + `adapters/googledocs/README.md` (the full
setup runbook: Remote access token → Cloudflare subdomain zone → the 2 NS records → `cloudflared login/create/route`
→ run → `curl` verify). **cloudflared installed via winget** (`Cloudflare.cloudflared` 2026.5.2) — the permitted
deploy. **No callosum code/endpoint/dependency/migration change** (cloudflared = an external binary; the increment is
config + a runner + docs); **no new API/FE surface** (the tunnel reuses existing endpoints) → surface map unchanged,
pytest **619** unchanged. Audit `.claude/security-audits/2026-06-28_googledocs-tunnel.md` PASS (outbound-only; two
boundaries; one delegated subdomain = minimal blast radius; **no secret committed** — the config has `<TUNNEL_ID>`
placeholders + the creds live in `~/.cloudflared/`; egress is the user's opt-in, transits Cloudflare+Google).
Principles → the A-A consent value (explicit opt-in egress). help corpus's inc-168 "Remote access" note already
covers it. **The live tunnel needs the user's Cloudflare account + NS records (manual);** I verified the cite-only
ingress + the install, not the live tunnel. **GOTCHAs:** HostGator jailshell blocks `ssh -R` (so the reverse-tunnel
path is dead — recon, not guesswork); `cloudflared --config` goes *after* `tunnel`; winget's PATH update doesn't
reach an already-open shell (use the full exe path). Notes: `INCREMENT-169-NOTES.md`. **NEXT: SP2** — the Apps
Script Google Docs add-on (`adapters/googledocs/` — a sidebar; `UrlFetchApp` → `https://callosum.clffwrkmn.net` with
the bearer token; citations as **NamedRange + DocumentProperties**, the Zotero pattern; reuses the cite contracts);
manual-test-only (Google's cloud). Then the user's live setup + end-to-end check.

Earlier — increment 168 (Google Docs SP0 — the remote-access security foundation: auth +
rate-limiting): the user approved the **Google Docs adapter** (the third word-processor adapter) and chose
**cloudflared on the local machine** as the bridge (Google's cloud can't reach localhost). The make-or-break safety
fact: cloudflared forwards to `localhost`, so the app **can't tell a tunnel request from the local browser** (both
loopback; `Host` spoofable) → **a bearer token is the only safe boundary**. callosum had no auth/rate-limiting (the
Security baseline mandates both before exposure), so SP0 builds that foundation first — **fully in-codebase +
pytest-verifiable**; the tunnel (SP1) + the Apps Script add-on (SP2, manual-test-only) follow. **Default-OFF →
zero change for every current user.** New **`app/backend/api/access_control.py`** (`AccessControlMiddleware`: ON →
require `Authorization: Bearer <token>`, constant-time `secrets.compare_digest`, except `GET /health` + `GET /` +
`OPTIONS`; OFF → pure pass-through; + a hand-rolled in-memory sliding-window **`RateLimiter`** → 429), wired in
`app.py` after CORS. **`app_settings.py`** gained `remote_access_enabled` + `access_token` (the keychain/file secret
store refactored to reusable `_get_secret`/`_set_secret`; provider keys now route through it, behavior-preserving) +
`generate_access_token`/`stored_remote_access` (the latter honors the `CALLOSUM_DISABLE_REMOTE_ACCESS=1` recovery
hatch). **`routers/settings.py`**: `remote_access_enabled` + `access_token_set` on `GET /settings` (**never the
value**), the toggle on `PUT` (**422 if enabling with no token minted** — lockout-safe), + `POST /settings/access-token`
(mint→return once). Frontend: a same-origin **fetch shim** in `00_lib.jsx` (token in localStorage, **never injected
into HTML** → no leak path) so the `api*` helpers + every raw fetch + the PDF bytes carry the token uniformly; a
`RemoteAccessSettings` section in `35_settings.jsx` (toggle: mint→save-locally→enable; regenerate; recovery note).
**Audit `.claude/security-audits/2026-06-27_remote-access-auth.md` PASS** (token the sole constant-time boundary;
default-off; secret never logged/returned/injected; local-only recovery; **the cloudflared ingress allowlist is a
recorded REQUIRED SP1 control** so `/`, `/settings`, scan routes are unreachable via the tunnel). **Principles →
the A-A consent value** (explicit, opt-in, default-off, user-controlled egress; not a claim/signal). **Rule #10:**
`route_35_settings.md` extended (`/settings/access-token` + the off-by-default / token-never-returned / 401-when-on
assertions) → surface **121/121 API + 604/604 FE, 0 uncovered**. help corpus's privacy section gained a "Remote
access" note (`HELP-DOCS-SYNCED` → 168). pytest **619** (+8 `tests/test_access_control.py`: the limiter, gate
off→no-op, on→401/200, health-exempt, disable-env-hatch, 429, enable-without-token-422, mint-once-then-status-only;
+ route-surface). **No new dependency** (hand-rolled limiter; `secrets`/`keyring` already present), **no migration**.
`ruff` clean; build + assembly green. **Verified headed, no egress** (`.local/visual/drive_inc168_remote_access.py`:
enable → token shown once → `GET /settings` has **no token value** → reload still loads the library under the gate
[the shim works] → toggle off; 0 console/page/genai). **GOTCHA (carry to SP1):** cloudflared makes tunnel==local at
the app, so the ingress allowlist (forward only the cite endpoints) is mandatory before pointing a tunnel at
callosum. Notes: `INCREMENT-168-NOTES.md`. **NEXT: SP1** — the cloudflared bridge (a `tools/` helper + the ingress
allowlist + a Settings field for the public URL; its own audit for the live egress) → then **SP2** — the Apps Script
Google Docs add-on (`adapters/googledocs/`; NamedRange + DocumentProperties, the Zotero pattern; manual-test-only).

Earlier — increment 167 (split `40_app.jsx` 630→551 — clear the carried 600-line violation): a
**behavior-preserving** refactor (no feature change), done autonomously to clear the rule-#1 violation flagged as
"the immediate next chore" across the last six footers (the App god-component had crept to 630/600). The inc-128
precedent (extract a hook into an earlier-loading chunk): the **axis focus-mode subsystem** → new
**`app/frontend/js/39_focus.jsx`** (`useFocusMode({setActiveTab, onEnterClearFilters})` — owns
`focusAxis`/`focusMembers`/`focusPending`/`axisRefresh` + `enterFocus`/`cancelFocus`/`toggleFocusPaper`/`saveFocus`,
lifted verbatim); the two big **citation-download helpers** (`downloadCitationExport` inc-70 / `downloadBibliography`
inc-106 + a shared `_downloadBlob`) → **`app/frontend/js/00_lib.jsx`** (the utils home). `40_app.jsx`: removed the
focus state + its 4 callbacks + the two ~18-line download bodies; calls `useFocusMode(...)` after the library
`useState`s (so the filter setters it closes over exist) + destructures the bundle; `bulkExport`/`bulkBibliography`
are now 1-line wrappers. **Chunk-order-safe** (00 < 39 < 40; esbuild DCE keeps all three since App references them).
**Frontend-only — no backend/surface/migration/egress/dependency; no audit/Principles trigger; help corpus
unchanged.** pytest **611** unchanged (`test_frontend_assembly` confirms `39_focus.jsx` is in the build + in sync);
`node --test` 11/11; surface **120/120 API + 599/599 FE, 0 uncovered**; `ruff` clean. **Verified headed, no egress**
(`.local/visual/drive_inc167_app_split.py` — seeds a real library + axis: the list renders, **bulk export** downloads
`callosum-citations.bib` [the moved `downloadCitationExport`], **focus-mode** enters via the axis ＋ + cancels [the
`useFocusMode` hook], the **axis filter** applies [uses the hook's `cancelFocus`]; 0 console/page/genai). **New
rule-#1 watch: `app/frontend/js/30_viewer.jsx` 595/600** (split before the next addition there). Notes:
`INCREMENT-167-NOTES.md`. **NEXT (both need the user's steering):** **Google Docs** via the authenticated
clffwrkmn.net relay (tunnel + auth + rate-limiting + opt-in egress; its own design-led increment) and/or
**beyond-library discovery** (#30 SP2 — feeds Word's Suggest + the in-app Cite pane; trips the audit + Principles
gates).

Earlier — increment 166 (Microsoft Word add-in, Office.js — SP3: parity — Suggest + style-switch +
Flatten): completes the Word adapter. **Suggest from the sentence** — `taskpane.js` reads the selection (else the
cursor's paragraph), `POST /citations/suggest {text≤4000, top_k, evaluate}` (inc 156), renders ranked candidates as
`[stance] Author Year · match N.NN — "quote…"` (the quote IS the reason — signal not verdict), pick → insert.
**Insert now collapses to the selection END** (`getRange(Word.RangeLocation.end)`) so Suggest inserts *after* the
sentence rather than replacing it (also safer for the search path). **One-click style switch** — the style dropdown's
`change` re-renders the whole document (`refreshDocument`) + persists per-document (`Office.context.document.settings`,
loaded on `Office.onReady`). **Flatten** — two-click confirm (no dialog dependency) → `cc.delete(true)` on every
citation + bibliography Content Control (keeps the text, drops the live field; one-way). New pure helpers in
`taskpane_core.js` (`pickQueryText`, `buildSuggestRequest`, `formatSuggestRows`) → `node --test "adapters/word/*.test.js"`
**11/11** (8 SP2 + 3 SP3). HTML gained a **Suggest** button + a suggestions list + a **Flatten** button; CSS a
`.secondary` recipe. **No backend change** — reuses `/citations/suggest` (inc 156) + `/citations/styles` +
`/citations/render-document` (inc 107) + `/papers/export` (inc 70), all already audited + pytest-tested → **no new
endpoint/surface/migration/egress/dependency, no new audit gate**. **Verification reality (the user has no Word):**
the in-Word Office.js glue is exercised by NO ONE — best-effort-correct per the Office.js docs; the value is the
pure logic (`node --test` 11/11) + the proven contracts. **GOTCHA (carry to Docs):** insert at the selection END
(collapse-to-end) so a sentence-scoped Suggest doesn't overwrite the sentence; `cc.delete(true)` keeps content
(flatten). pytest **611** unchanged (adapter-only; `tests/test_word_addin.py` re-confirms the rewritten assets
serve + no AI host); surface **120/120 API + 599/599 FE, 0 uncovered**; `ruff` clean; no frontend rebuild (only
`adapters/word/` + help corpus). help corpus's "Citing in Microsoft Word" section now covers Suggest/style/flatten
(`HELP-DOCS-SYNCED` → 166). **NOT headed-verifiable** (the task pane needs Word; the SP1 headed Settings drive still
covers the unchanged Settings surface). Notes: `INCREMENT-166-NOTES.md`. **This completes the Word adapter (SP1 inc
164 + SP2 inc 165 + SP3 inc 166).** **NEXT:** **Google Docs** via the authenticated **clffwrkmn.net relay** (its own
design-led increment: a tunnel + auth + rate-limiting on callosum [Security baseline] + the add-on, opt-in egress) —
and/or beyond-library discovery to feed Suggest (#30 SP2). Carried: the **`40_app.jsx` 630/600 split** (rule #1).

Earlier — increment 165 (Microsoft Word add-in, Office.js — SP2: live cite-while-you-write):
upgrades the inc-164 SP1 static-text insert to the Zotero-style loop — **live citations + Refresh/renumber +
bibliography**. Each citation is a Word **Content Control** whose `.tag` carries the cluster's CSL-JSON (base64,
unicode-safe), `appearance:"Hidden"` (a live field, not a visible box). **Insert** = `POST /papers/export` csl-json
→ `Word.run` wrap a Content Control around the inserted range → **Refresh**. **Refresh** scans citation Content
Controls **in document order** (`body.contentControls`, filtered by the `CALLOSUM_CITATION ` tag prefix), POSTs them
to the inc-107 **`/citations/render-document`** (positional `citationID`s), writes each control's text back with
`cc.insertText(text,"Replace")` (Office.js preserves the control — no LibreOffice setString-destroys-the-mark trap),
and rebuilds a managed **References** Content Control (tag `CALLOSUM_BIBLIOGRAPHY`) at the body end. Chose **Content
Controls** over ADDIN fields (the more mature Office.js primitive). The style dropdown feeds Refresh (one-click
whole-doc style-switch + Flatten + Suggest = SP3). **All in `adapters/word/`** (`taskpane.js` rewrite + the SP2 pure
helpers in `taskpane_core.js` + a Refresh button in `taskpane.html`/`.css`); the SP1-only per-item helpers were
removed (rule #5). **No backend change** — reuses `/papers/export` (inc 70) + `/citations/render-document` (inc 107),
both already audited + pytest-tested → **no new endpoint/surface/migration/egress/dependency, no new audit gate**;
the inc-164 audit posture (same-origin loopback, zero egress, no traversal) is unchanged. **Verification reality —
the user has no Word, so the in-Word Office.js glue (`taskpane.js`) is exercised by NO ONE** (it ships
best-effort-correct per the Office.js docs); the value is the **pure logic** (`taskpane_core.js`: tag encode/decode
incl. a unicode round-trip + malformed→null-never-guess, the render-document request builder + response extractors)
**`node --test` 8/8** + the render-document contract it calls being **pytest-proven** (inc 107). **GOTCHA (carry to
Docs):** `cc.insertText(.., "Replace")` keeps the Content Control (unlike LibreOffice ReferenceMarks); content-control
iteration is in document order. pytest **611** unchanged (SP2 is frontend/adapter-only; `tests/test_word_addin.py`
re-confirms the rewritten assets serve with no AI host); `node --test "adapters/word/*.test.js"` **8/8**; surface
**120/120 API + 599/599 FE, 0 uncovered** (no surface change); `ruff` clean; no frontend rebuild (only `adapters/word/`
touched). help corpus's "Citing in Microsoft Word" section updated to live-fields + Refresh (`HELP-DOCS-SYNCED` →
165). **NOT headed-verifiable** (the task pane needs Word; the SP1 headed Settings drive still covers the Settings
surface, unchanged). Notes: `INCREMENT-165-NOTES.md`. **NEXT:** **SP3 (inc 166)** — Suggest (`/citations/suggest`,
relevance-from-the-sentence) + a one-click whole-doc style switch + Flatten (live→static). Then **Google Docs** via
the authenticated **clffwrkmn.net relay** (its own design-led increment). Carried: the **`40_app.jsx` 630/600 split**
(rule #1).

Earlier — increment 164 (Microsoft Word add-in, Office.js — SP1: HTTPS spine + search-and-insert
task pane): the second word-processor adapter (after LibreOffice). A Word add-in is a **web task pane**, and Office
requires it over **HTTPS** + **can't fetch `http://localhost`** (Word-on-the-web can't reach localhost at all) — so
the user chose **Architecture A** in plan mode: callosum serves the task pane over **local HTTPS, same-origin** with
its API (`https://localhost:8443`), so the add-in reaches the library with **no CORS change and no egress** (it's all
loopback); the one cost is a one-time local-cert trust. SP1 ships the spine that proves the platform end-to-end
(read + write in real Word): **search the library → insert a formatted citation as static text** at the cursor. New
**`adapters/word/`** (shipped client code) — `manifest.xml` (XML add-in-only; ribbon **Home → Callosum → Show
Citations**; SourceLocation `https://localhost:8443/…/taskpane.html`), `taskpane.html`/`taskpane.js` (thin Office.js
glue: `Office.onReady` → `fetch('/papers?q=')` → on pick `fetch('/citations/render')` → `Word.run` insert),
**`taskpane_core.js`** (pure logic, no Office.js → `node --test`-able: `formatSearchRows`/`buildRenderRequest`/
`inTextFromRender`), `taskpane.css`, `README.md`, `icon.png`. New **`routers/word.py`** (serve the task pane + manifest
via **explicit per-filename `FileResponse` routes** — no `{filename}` param → no traversal — + `POST …/install` opens
the add-in folder, graceful). **`tools/run_https.py`** (locate the `office-addin-dev-certs` cert + run uvicorn TLS on
:8443). `35_settings.jsx` **WordSettings** section (Download manifest + Open add-in folder + the 3-step setup note +
the desktop-only/HTTPS caveat). **Same-origin is the trick:** CORSMiddleware only applies cross-origin, so the
existing GET-only allowlist is untouched AND nothing leaves the machine. **GOTCHAS (carry to SP2/Docs):** office.js
**cannot take SRI** (MS updates it in place at the fixed URL — documented exception); **there is no headless Word**
→ the in-Word round-trip is the **user's MANUAL check** (the pure logic lives in `taskpane_core.js` precisely so most
of it IS testable). **No migration, no egress, no new dependency** (office.js CDN-loaded by Word; `office-addin-dev-certs`
via `npx`; `node --test` built-in). **Principles non-triggering** (packaging + a thin field-placer reusing the audited
citeproc render); audit `.claude/security-audits/2026-06-27_word-addin.md` PASS (no traversal; egress NONE; local-only
→ pre-hosted-deploy gate recorded). **Rule #10:** `route_35_settings.md` extended with `/integrations/word/*` + a Word
step + a local-only/no-egress standing assertion → surface **120/120 API + 599/599 FE, 0 uncovered**. help corpus
gained a "Citing in Microsoft Word (desktop)" section (`HELP-DOCS-SYNCED` → 164). pytest **611** (+7
`tests/test_word_addin.py`); `node --test "adapters/word/*.test.js"` 8/8; `ruff` clean; build + assembly green.
**Verified headed, no egress** (`.local/visual/drive_inc164_word.py`: the WordSettings section renders, the served
manifest's SourceLocation is `https://localhost:8443/…`, the task pane references office.js + **no** AI/library host,
Open-add-in-folder posts a result [OS opener stubbed]; 0 console/page/genai). **The in-Word round-trip is the user's
manual eyeball** (desktop Word only: `npx office-addin-dev-certs install` → `python tools/run_https.py` → sideload
`adapters/word/manifest.xml` → Word → Callosum → Show Citations → search + insert). Notes: `INCREMENT-164-NOTES.md`.
**NEXT:** **SP2 (inc 165)** — live cite-while-you-write (insert as Content Controls carrying CSL-JSON + a Refresh that
renumbers the whole doc + bibliography via `/citations/render-document`); then **SP3 (inc 166)** — Suggest / style
picker / Flatten. Word-on-the-web + **Google Docs** ride the future authenticated **clffwrkmn.net relay** (its own
design-led increment: a tunnel + auth + rate-limiting, opt-in egress). Carried: the **`40_app.jsx` 630/600 split**
(rule #1).

Earlier — increment 163 ("Coming soon" accordion placeholders — a visible roadmap): the user
asked to preemptively scaffold the planned THEORY/METHODS sections + subsection tabs into the GUI as placeholders,
"to keep me psyched about all of the stuff we're gonna build." Built **honestly** (not vaporware) — new chunk
`app/frontend/js/09_placeholders.jsx` (loads at 09, after the registry@05 + METHODS sections@06–08): a
`<ComingSoon title body builds/>` component (an `--accent-soft` badge + a "Backlog #…" line) registering **THEORY →
Discover** (`order 30`, with coming-soon **tabs** Beyond library / Feed / Search — #30 SP2 + #28) + **METHODS →
Mixed-model reporting** (`50`, #23) / **Bayesian statistics** (`60`, #24) / **Meta-analysis** (`70`, #37) /
**Citation equity** (`80`, #25), plus a **"More checks"** tab appended to the **shipped** `statcheck` section (#27)
via `registerPaneTab` find-or-create — **no edit to `06_methods_statcheck.jsx`** (it now shows a `[Statistics check |
More checks]` strip). Convention (DESIGN §5, new note): a stub must (1) name a real backlog item, (2) be placed by
the cognitive-task rubric, (3) **bake in its ship-time principle framing** (signal-not-verdict / "descriptive, never
an accusation" / "extracts, never pools"), (4) be **inert** ("silence is not a certificate" — no controls/data);
**remove each stub in the increment its real feature lands**. Deliberately NOT stubbed: where-to-submit (#40 — it's
authoring-support, not method-evaluation → breaks the placement rubric); the Word/Docs adapters (external, not
accordion sections). `.coming-soon*` CSS = tokens only (rule #8). **Frontend-only — no backend/migration/egress;
Principles non-triggering** (inert roadmap UI; the descriptions carry the charter framing so the roadmap can't
promise something misaligned); surface **113/113 API + 597/597 FE, 0 uncovered** (the stubs add no interactive
surface). pytest **601** unchanged; `ruff` clean; build + assembly green. **Verified headed, no egress**
(`.local/visual/drive_inc163_placeholders.py`: Discover's `[Beyond library | Feed | Search]` tabs + a METHODS stub
+ the statcheck `[Statistics check | More checks]` strip all render; the shipped statcheck intact; 0
console/page/genai). Notes: `INCREMENT-163-NOTES.md`. **NEXT (the user's roadmap):** the **Word add-in (Office.js)**
— reuses our `/citations/render-document` + `/papers/export` + `/citations/suggest` + `/papers?q=` contracts; new
Office.js shell + manifest + a CORS/origin change (its own plan-mode increment). Then **Google Docs via an
authenticated `clffwrkmn.net` relay** (the user's server tunnels to local callosum; needs **auth + rate-limiting on
callosum** [Security baseline] + the tunnel + the add-on — its own design-led increment, audit + Principles/A-A
gate, opt-in egress). Plus the carried **`40_app.jsx` 630/600 split** (rule #1) + any more placeholder sections the
user names.

Earlier — increment 162 (LibreOffice adapter v2 — a discoverable, installable cite flow): the
inc-108 adapter worked but the *routing* was unusable — macros buried in Tools → Macros → Organize Macros → Python,
and insert-by-numeric-paper-id. The user: "no end user is going to find this intuitive"; asked to research how the
ref managers do it. Research (Zotero/Mendeley/EndNote): a **toolbar/menu that appears after install** + an **"Add
Citation" search-as-you-type** box over the library (our **Suggest** = relevance-from-the-sentence is a novel
complement none of them have). **Built (3 phases): SP1** — a single **`.oxt`** (`adapters/libreoffice/oxt/`:
`Addons.xcu` = a top-level **Callosum** menu + toolbar; `META-INF/manifest.xml` registers `callosum_addon.py`, a UNO
**`XJobExecutor`** dispatcher whose menu URLs are `service:com.callosum.cite.Dispatcher?<action>` — **path-independent**
vs the fragile `vnd.sun.star.script:` package-path URIs). `callosum_cite.py` gained an **`_ACTIONS`/`dispatch`**
registry shared by the macro entry points (macro mode) + the dispatcher (component mode), **`_DISPATCH_CTX`** (bridges
the component context into the dialog helpers, which otherwise use the macro-only `XSCRIPTCONTEXT`), and a
**configurable server URL** (sidecar `~/.callosum/libreoffice.json`, pure I/O) + `CallosumSetServerUrl`. New
`tools/build_libreoffice_oxt.py::build_oxt` (stdlib `zipfile`; importable so the backend builds on demand). **SP2** —
**`add_citation_by_search`** (GET `/papers?q=` → a pick-list → `insert_citation`; the everyday cite action, no ids) +
`CallosumAddCitation`, wired as the top menu item; `_suggest_listbox` parameterized so the search picker reuses it.
**SP3** — install from callosum: `routers/libreoffice.py` `GET /integrations/libreoffice/plugin.oxt` (build+serve) +
`POST …/install` (build + open with the OS handler → LibreOffice's Extension Manager; graceful `{opened:false}` +
download fallback, never 500) + a `35_settings.jsx` **LibreOffice plugin** section (Install + Download .oxt). **No
migration, no egress, no new dependency.** Audit `.claude/security-audits/2026-06-27_libreoffice-install.md` PASS
(fixed-artifact path → no injection; local-only → flagged for the pre-hosted-deploy gate, like the folder-scan note);
Principles non-triggering (packaging/UX; Add-Citation reuses the library search + the inc-108 insert; credit-the-lineage
already satisfied for the Zotero `CSL_CITATION` field *pattern*). Rule #10: `route_35_settings.md` extended → surface
**113/113 API + 597/597 FE, 0 uncovered**; help corpus gained a "Citing in LibreOffice Writer" section + the adapter
README reworked to v2 (`HELP-DOCS-SYNCED` → 162). pytest **601** (+10 `test_libreoffice_oxt.py` + `test_libreoffice_install.py`;
the suite is slow ~16min with model loading — run offline `HF_HUB_OFFLINE=1`); `ruff` clean; build + assembly green.
**Verified through real LibreOffice** (`.local/lo_roundtrip/run_roundtrip.py`: builds the `.oxt`, **`unopkg add` rc=0**,
SELFTEST OK = IEEE→APA→flatten→**suggest-insert**→**search-to-cite**→**dispatcher resolves** [`com.callosum.cite.Dispatcher`
instantiates + exposes `trigger` ⟹ the menu URLs work]) + **headed Settings drive, no egress**
(`.local/visual/drive_inc162_settings.py`, OS opener stubbed: Download .oxt href + Install POST + result; 0
console/page/genai). **GOTCHAS for the Word/Docs adapters:** a Python UNO **component** must import siblings **lazily**
after `sys.path.insert(dirname(__file__))` (at `unopkg add` registration the ext dir isn't importable → the first
spike's `ModuleNotFoundError: callosum_cite`); the dialog/`_msgbox` helpers need `XSCRIPTCONTEXT` (macro-only) so a
component injects `_DISPATCH_CTX`; the round-trip harness leaked its uvicorn when `start_stack()` raised before its
try/finally (locked `roundtrip.sqlite` → next-run `PermissionError`) — now it tears down on any startup failure +
cleans the LO profile + clears `unopkg`'s bootstrap soffice. **For the user (GUI eyeball):** Settings → LibreOffice
plugin → Install → restart Writer → the **Callosum** menu/toolbar appear → **Add citation** searches + inserts;
**Suggest** works from a highlighted sentence (the Addons.xcu *rendering* is GUI-only; the dispatch + actions are
headless-verified). Notes: `INCREMENT-162-NOTES.md`. **NEXT:** the `40_app.jsx` 630/600 split (carried from inc 161);
then live search-as-you-type Add-Citation (user-deferred) / the Word (Office.js) + Google Docs adapters / #30 SP2
beyond-library discovery.

Earlier — increment 161 (non-destructive merge of duplicate papers): the user's real workflow —
a **preprint + its published copy**, *merge* not delete, **keep the preprint PDF + ensure the OSF link survives**,
and never risk losing info by mis-identifying which line item to delete. Scales the long-deferred library merge into
the dedup flow. New **`app/backend/metadata/paper_merge.py::merge_papers`**: re-points the merged copies' **source
data** onto a chosen survivor — `attachments`/`chunks`/`annotations`/`notes`/`paper_external_identifiers` via
`UPDATE paper_id` (no per-paper UNIQUE — verified; **chunk embeddings follow via the unchanged `chunk.id` → no
vector surgery**); unions `paper_tags`/`collection_papers`/manual `cluster_node_papers` idempotently; repoints
`profile.starred_paper_ids`/`research_domains` (`profile_repo.replace_paper_id`). It **frees each husk's UNIQUE id
columns first** (`doi`/`openalex_work_id`/… → NULL; `csl_json` keeps them for audit) so the survivor can adopt them
(soft-delete keeps the row, so the UNIQUE would otherwise block it) + auto-adopts the matching ids the survivor
lacks; composes the survivor's metadata from the user's per-field picks via `paper_edits.build_paper_update`; appends
a **"Merged from…" lineage note** to `csl_json["note"]` capturing every merged copy's identifiers (so a link can
never be silently lost); stamps `imported_source=MERGED_SOURCE` (kept OUT of the crossref-update allowlist like
`user-edited`); sets the chosen **primary** attachment (**both PDFs kept**); **soft-deletes** the husks (restorable
Trash; FK rows already moved). **`POST /papers/merge`** in `routers/duplicates.py` (registered before
`/papers/{paper_id}`; `MergeMetadata` typed + `extra="forbid"`; `MergeValidationError`→422, `MergeConflictError`→409
on a DOI clash with an **outside** paper; `conn.commit()` all-or-nothing). Frontend **`38_merge.jsx`**
(`MergePapersModal`: survivor pick + per-conflict-field radios + primary-PDF pick; reads each paper via
`GET /papers/{id}`; sends only fields differing from the survivor) wired into `19_duplicates.jsx` (per-group
**merge**), `10_pdf_layer.jsx` (bulk-bar **merge** at ≥2 selected), `40_app.jsx` (`mergeIds` state + `onMerged`
selects the survivor + refreshes lib/axes/tags). **No migration, no egress, no new dependency.** Derived
signals/findings recompute (not migrated); the husk retains its copies. Audit `2026-06-27_paper-merge.md` PASS;
Principles gate run (preserves provenance/inspectability — the aligned alternative to lossy delete; no A-A veto in
play). Rule #10: `route_24_duplicates.md` extended → surface **111/111 API + 595/595 FE, 0 uncovered**; help corpus
gained a "Merging duplicates (keeps everything)" subsection (`HELP-DOCS-SYNCED` → 161). pytest **591** (+10
`test_paper_merge.py`; the suite is slow ~16min with model loading — run offline `HF_HUB_OFFLINE=1` to avoid a HF
network stall); `ruff` clean; build + assembly green. **Verified headed, no egress**
(`.local/visual/drive_inc161_merge.py`: select a seeded preprint + published → bulk-bar **merge** → the dialog →
Merge → survivor keeps the DOI + the **OSF URL** + **both PDFs** + a "Merged from…" note; the preprint is in Trash;
0 console/page/genai). **WATCH (rule #1):** `app/frontend/js/40_app.jsx` is now **630/600** — it was already 609 at
HEAD (a prior slip; the App god-component accreted modal/bulk wiring since the inc-128 split). A behavior-preserving
split (extract the modal-render block or another `use*` hook, the inc-128 precedent) is the **immediate next chore**.
Notes: `INCREMENT-161-NOTES.md`. **NEXT:** the 40_app.jsx split; then back to **#30 — SP2 beyond-library discovery**
(design-led; its own plan-mode session).

Earlier — increment 160 (the library folder is watched by default): a user dropped a known-
retracted PDF into the library folder and it never appeared (even across restart + hard refresh), blocking the
Retraction Watch test. **Root cause (systematic-debugging):** the auto-rescan (launch/focus, inc 98/136) only
re-scans **registered** watched folders, and `watched_folders` was **empty** — the library papers were
harness-ingested (`pdf-scaffold`), never UI-"Scan folder"ed (which registers + sets `library-scan`), so the
library folder was never watched (confirmed: `library/Whitehouse…2019…Nature.pdf` on disk, absent from the DB).
**Fix (the user's design):** the **library folder is watched by default**. The canonical folder already existed —
`acquisition/fetch.py::library_dir()` (`CALLOSUM_LIBRARY_DIR` env, else project `library/`; where OA-acquired
PDFs land), now **public**. `routers/library.py`: the rescan **always scans `library_dir()` first** (even with no
rows), then user folders (deduped via `_path_key` resolve+casefold); `GET /library/watched` **pins it first** as
`id=0, is_default=True` (non-removable; a user folder equal to it folds in); `DELETE /library/watched/0` → **422**.
`27_scan.jsx`: the modal shows it as a pinned **"default · always watched"** row (accent border + a "default"
pill, no remove). `conftest.py` now isolates **`CALLOSUM_LIBRARY_DIR`** per-test (hermetic; also stops OA tests
writing the real `library/`). **No new endpoint** (`is_default` additive), no migration/egress/dependency, no
Principles trigger (a watched-folder default, not a claim/signal); the server-side library-folder read is the
same posture as existing watched folders (deployment-gate note extended). pytest **581** (+3 `test_watched_folders.py`);
`ruff` clean; build + assembly green; surface **110/110 API + 577/577 FE, 0 uncovered**; help corpus's
Watched-folders section leads with the default (`HELP-DOCS-SYNCED` → 160). **Verified headed, no egress**
(`.local/visual/drive_inc160_library_watched.py`: the pinned non-removable default row + a drop → Re-scan all →
"1 added"; 0 console/page/genai). **For the user: restart uvicorn** (autoScanWatched on, default) → the on-launch
rescan scans `callosum/library/` → **Whitehouse ingests + Crossref-enriches (DOI) + retraction-auto-checks**
(inc 134), unblocking the RW test (the RW *database* source also needs the Settings → Metadata access contact
email, inc 158). Notes: `INCREMENT-160-NOTES.md`. **NEXT:** back to **#30 — SP2 beyond-library discovery**
(design-led; its own plan-mode session).

Earlier — increment 159 (formatted "Cite as…" in the in-app Cite pane — #30 follow-on): the
deadline-writer persona's ask from the inc-156 experience pass — the Cite pane could only extract **BibTeX** (for
a reference manager), but a writer hand-citing in prose wants a **formatted** human citation. **Frontend-only**
(`app/frontend/js/37_cite.jsx` + `styles.css`): a pane-level **style picker** (`/citations/styles`, default apa) +
a per-card **`FormattedCiteButton`** ("Cite") that renders the paper in the chosen style via the inc-106
`POST /citations/render` (local citeproc) and copies the `reference_text`; the BibTeX copy stays as a secondary
action ("BibTeX"). Reuses tested endpoints (local, **no egress**) → **no backend/endpoint/migration/audit gate**;
**no new claim/signal** (formatting is mechanical — Principles non-triggering); surface unchanged (route_42 claims
`37_cite.jsx`): **110/110 API + 577/577 FE, 0 uncovered**. pytest **578** unchanged (frontend-only;
`test_frontend_assembly` confirms the build is in sync); `ruff` clean. **Verified headed, no egress**
(`.local/visual/drive_inc159_cite_format.py`: the Cite click fires a `/citations/render` 200 — the formatted-cite
path runs UI→engine; 0 console/page/genai). The clipboard write is the shipped Details "Cite as…"/BibTeX pattern —
headed Chromium blocks `clipboard.writeText` without OS focus, so the driver asserts the render call, not the
clipboard. Notes: `INCREMENT-159-NOTES.md`. **NEXT:** the bigger #30 continuation — **SP2 beyond-library
discovery** (OpenAlex/Semantic-Scholar, explainable reasons; design-led → its own plan-mode increment, trips the
audit + Principles gates) + Stage-4 section-scoping; the Word (Office.js) + Google Docs adapters remain the broader
word-processor track.

Earlier — increment 158 (contact email / polite-pool mailto in Settings): a UX fix the user
flagged — the Retraction Watch download (inc 132) hard-required the `CALLOSUM_CROSSREF_MAILTO` **env var**, while
everything else configurable now lives in Settings (the inc-146 BYOK pattern). Now **one Contact email** in
**Settings → Metadata access** supplies the polite-pool contact for **all** public metadata APIs (Crossref,
OpenAlex, Retraction Watch), overlaying both `CALLOSUM_CROSSREF_MAILTO` + `CALLOSUM_OPENALEX_MAILTO`. New
`app_settings.set_contact_email`/`stored_contact_email`/**`resolved_mailto(env_var)`** (= stored email or env);
the **4 metadata clients** (`CrossrefClient`/`RetractionWatchClient`/`OpenAlexClient`/`OpenAlexAuthorClient`)
resolve their mailto via `resolved_mailto(...)` (the unused `import os` was dropped from each). `routers/settings.py`:
`contact_email` + `contact_email_source` on `GET /settings`, `set_contact_email`/`contact_email` (max_length 254 →
422; non-empty must contain `@` → 422) on `PUT`. `35_settings.jsx`: a **Metadata access** section. The RW
fail-closed message now points to Settings. **Not a secret** — the email is sent to public metadata APIs as the
polite-pool contact (exactly as the env vars did), so it's file-stored (not the keychain) and **is** returned by
`GET /settings` (unlike the API key). **No new egress vector** (the email was already transmitted when the env var
was set), **no new endpoint/dependency/migration**. **Audit:** an **addendum** to `2026-06-26_byok-api-key.md` PASS.
**Rule #10:** `route_35_settings.md` + `route_40_retraction_watch.md` updated → surface **110/110 API + 573/573 FE,
0 uncovered**. help corpus's Settings + Retraction Watch sections point to Settings → Metadata access
(`HELP-DOCS-SYNCED` → 158). pytest **578** (+6 `test_settings.py`); `ruff` clean. **Verified headed, no egress**
(`.local/visual/drive_inc158_contact_email.py`, isolated `CALLOSUM_SETTINGS_PATH`): save → `GET /settings` returns
it (source `ui`) → persists across reload; 0 console/page/genai. (The real RW CSV download with the UI-set email is
the user's spot-check, as in inc 132.) Notes: `INCREMENT-158-NOTES.md`. **NEXT:** back to **#30** — a formatted
"Cite as… (style)" copy in the in-app Cite pane (the deadline-writer persona's ask, via the inc-106 engine), then
SP2 beyond-library discovery.

Earlier — increment 157 (highlight-to-suggest, SP1b — the LibreOffice "Suggest citations"
macro): surfaces the inc-156 `POST /citations/suggest` contract **inside LibreOffice**, where the writer already
inserts citations (the inc-108 cite-while-you-write adapter). The inc-107→108 pattern: SP1a was the contract,
SP1b is the adapter. **Client-side only** (`adapters/libreoffice/callosum_cite.py`) — talks only to 127.0.0.1,
reuses the SP1a endpoint + the inc-108 insert; **no server change, no new endpoint/egress/migration/dependency**
(stdlib `urllib`). The writer **selects (highlights)** a sentence → `CallosumSuggestCitations` POSTs it to
`/citations/suggest` (`current_query_text` = selection, else the paragraph) → a UNO **pick-list** (`_suggest_listbox`,
each row from the pure `build_suggest_rows`: `[stance] Author Year · match N.NN — "quote…"` — the quote is the
reason) → the chosen paper inserts as a live citation via the existing `insert_citation` (at the selection end).
UNO-free helpers (`fetch_suggestions`/`build_suggest_rows`) are pytest-covered; `SUGGEST_TIMEOUT=90s` (the first
call loads the embed+NLI models server-side; render/export keep 20s). **Honesty:** rows show stance+quote, the
user **picks** (nothing auto-inserts), inserting reuses citeproc (no formatting in the adapter) — non-triggering
beyond honoring the inc-156 posture. **Audit:** an **addendum** to `2026-06-21_libreoffice-adapter.md` PASS (same
local-only/plain-text/no-egress; the one new flow = the highlighted **document text** → the local server, the
feature's purpose, stays on 127.0.0.1). **No QA route** (a LO macro is outside the web-app surface map;
`/citations/suggest` is covered by route_42) + **no help-corpus change** (the macro's doc is its README). pytest
**572** (+4 `test_libreoffice_adapter.py`); `ruff` clean; no migration. **Verified — the headless UNO round-trip
(`python .local/lo_roundtrip/run_roundtrip.py`) → SELFTEST OK**: the harness now seeds+embeds a chunk per paper so
`/citations/suggest` returns results, and `selftest_uno.py` asserts the suggest→insert chain through **real
LibreOffice** (got `[(1,'support'),(2,'support')]` — both seeded papers, **stance from the real NLI** — top one
inserted). The interactive list-box dialog is the **user's manual eyeball** (it blocks on `execute()`; copy the
macro into `%APPDATA%\LibreOffice\4\user\Scripts\python\`, select a sentence, run **Tools → Macros →
CallosumSuggestCitations**). **Op gotchas (carry forward):** LibreOffice's Windows Python stdout is cp1252 — keep
selftest `print()` strings ASCII (a `→` raised `UnicodeEncodeError`); a crashed prior round-trip can leave a
**zombie TCP listener** (no owning process) on the port — the harness moved to :8100/:2003. **LibreOffice is
installed** here (`C:\Program Files\LibreOffice\program\`). Notes: `INCREMENT-157-NOTES.md`; design spec
`.claude/docs/specs/2026-06-27-highlight-suggest-design.md` (SP1a). **NEXT:** a formatted "Cite as… (style)" copy
in the in-app Cite pane (the deadline-writer persona's ask, via the inc-106 engine); then **SP2 beyond-library
discovery** (OpenAlex/Semantic-Scholar, explainable reasons — trips the audit + Principles gates) + Stage-4
section-scoping; the Word (Office.js) + Google Docs adapters remain the broader word-processor track.

Earlier — increment 156 (highlight-to-suggest / evaluate — Track C, SP1a): the first build of
the highest-value novel capability (#30), and the start of a new design-led arc (brainstorm → Principles gate →
plan → build). Given a draft sentence, **suggest** which library papers to cite (retrieval in reverse) and
**evaluate** whether each candidate *supports / contrasts / mentions* the claim — evidence shown. **User-scoped:**
SP1 = suggest+evaluate together; the real input is the sentence being written in the **LibreOffice document**
(inc-108 cite-while-you-write); sequence like **inc-107→108** — engine + endpoint contract first (SP1a, this
increment) with a thin in-app surface to verify it, then the LO macro (SP1b). **SP1a:** `app/backend/citations/
suggest.py::suggest_citations` (`search_similar(target_types=("chunk",))` → best chunk per paper → rank by score,
trashed excluded) + a **local NLI stance scorer** beside `NLISupportScorer` in `summarization/verification.py`
(the `cross-encoder/nli-MiniLM2-L6-H768` 3-way softmax: entailment→support, contradiction→contrast,
neutral→mention; `_label_index` generalizes `_entailment_index`; **any failure → None**, never a guessed verdict)
+ **`POST /citations/suggest`** (`routers/citations.py`; the adapter contract; whitespace→422, caps via Pydantic;
the heavy embed + NLI models cached on `app.state`, injected ones win via `create_app(stance_scorer=…)`) + an
in-app **Cite** pane (`js/37_cite.jsx`, THEORY accordion order 25): paste a sentence → cards (stance pill · match
· verbatim quote · **Open source region** · **Copy BibTeX**). **Fully local — no egress; no migration** (read-only
over chunks). **Honesty (Principles gate run):** suggestions carry their quote+page+match-score as the **reason**
(#8), are **candidates the author picks** — nothing auto-inserts (#3/#5); stance leads with the verbatim
quote+confidence, a labeled signal not a bare verdict (#1/#4), local-NLI-only; evidence is **region** precision,
never a fabricated exact rect (#2); `match_score` is one labeled similarity, **no opaque composite** (#7); ranked
by sentence-match not citation count (bias-amplification is an SP3 concern); accuses no one (A-A veto). **Audit
`.claude/security-audits/2026-06-27_citation-suggest.md` PASS** (local, bounded, bound-param, region-honest, no
new dependency, graceful NLI degradation). **Rule #10:** new `route_42_cite.md` (`/citations*` already globbed by
route_34) → surface **110/110 API + 569/569 FE, 0 uncovered**. help corpus gained a "Suggesting citations"
section (`HELP-DOCS-SYNCED` → 156). pytest **568** (+11 `test_citations_suggest.py`: ranking/one-per-paper,
region-not-exact, evaluate attaches/omits stance, trashed excluded, the NLI label-mapping + graceful + loader
path, endpoint shape/stance/evaluate-false/empty/whitespace/oversized→422; route-surface +1); `ruff` clean; build
+ assembly green. **Experience pass (rule #11)** — a deadline-writer persona found the *vet* half strong but a
pane named "Cite" that couldn't **extract** anything dead-ended → fixed in-increment (cheap): a **Copy BibTeX**
button per card (the in-app bridge for hand-citing; reuses inc-70 export), a **visible** "stance unavailable"
note, de-duped the per-card boilerplate. **Verified headed, no egress** (`.local/visual/drive_inc156_cite.py` —
paste → 2 cards (SUPPORT pill, MATCH 1.00, quote, Copy BibTeX), Open source region → real PDF at region; 0
console/page/genai). Notes: `INCREMENT-156-NOTES.md`; design spec `.claude/docs/specs/2026-06-27-highlight-suggest-design.md`.
**NEXT: SP1b** — the LibreOffice "Suggest citations" UNO macro (`adapters/libreoffice/callosum_cite.py`): grab the
current sentence → `/citations/suggest` → present + Insert via the inc-108 flow (headless UNO round-trip; no server
change). Deferred (backlog/SP1b+): a formatted "Cite as… (style)" copy via the inc-106 engine; SP2 beyond-library
discovery (OpenAlex/Semantic-Scholar); Stage-4 plugin section-scoping.

Earlier — increment 155 (scan done-summary surfaces which files couldn't be read — backlog #4):
the autonomous part of the Migrator experience-pass remainder. The folder scan already isolated per-file failures
(`scan_library_folder` → `errors:[{path,error}]` via savepoints) but reported only a count — now the done-summary
shows **which files failed + why**. `routers/library.py`: a `ScanError{path,error}` model; `ScanSummary.error_details`
(capped 25); `_scan_summary` maps the scan's errors; the watched-rescan agg collects them across folders. Frontend
(`27_scan.jsx`): a collapsible `<details className="scan-errors">` "N file(s) couldn't be read" → `<basename> —
<reason>` (+ "…and K more" when capped); one `.scan-errors` CSS recipe (tokens). **Scope (honest):** scan side only
— the import path's "skipped" records are dropped *at parse* (both parsers silently drop title-less/malformed entries
before the `failed` count), so surfacing those needs a **parser-level** change (deferred, noted on #4); ETA + cancel
also stay deferred (timing / cooperative-cancellation infra). No new endpoint (additive field), no migration.
**Principles non-triggering** (surfaces existing data). pytest **557** (+1 `test_library_scan.py`: a broken file →
`summary.errors>=1` + `error_details` with path + reason); `ruff` clean; build + assembly green; QA surface
**109/109 API + 561/561 FE, 0 uncovered**. **Verified headed, no egress** (`.local/visual/drive_inc155_scan_errors.py`
— a temp folder with a valid + a broken PDF → scan → "1 added · 1 error" + the collapsible lists "broken.pdf —
FileDataError…"; 0 console/page/genai). Notes: `INCREMENT-155-NOTES.md`. **This completes the autonomous-work pass
(inc 153 synthesis coverage · 154 statcheck deep-link · 155 scan error detail).** The remaining open backlog is all
design-gated / destructive-security / future-track / non-code — none autonomous-cheap.

Earlier — increment 154 (statcheck flagged-chip deep-link → the specific inconsistent test):
the remaining autonomous part of the statcheck experience-pass finding (d). **Frontend-only** (`06_methods_statcheck.jsx`):
when a per-paper statcheck run finishes, a `listRef` + a `state.status` effect scroll the **first inconsistent row
into view + flash it** (the row is marked `.flagged-row` when `consistency !== "consistent"`) — so the "⚠ N flagged"
chip path (inc 141) lands the deadline-citer on the specific result that doesn't recompute, not just the full list.
CSS: `@keyframes statcheckflash` (flag-amber) + `.statcheck-item.flash` (reuses the helpflash pattern; tokens only).
Coordinate honesty unchanged (rows still page-open at `precision:"region"`); **Principles non-triggering** (a
navigation affordance over the existing signal). pytest **556** unchanged (frontend-only; statcheck data path covered
by `test_statcheck`); `ruff` clean; build + assembly green; QA surface **109/109 API + 561/561 FE, 0 uncovered**; no
migration. **Verified headed, no egress** (`.local/visual/drive_inc154_statcheck_flash.py` — seed a flagged paper →
chip → Statistics check auto-runs → the inconsistent row is marked `.flagged-row` + flashes; 0 console/page/genai).
Notes: `INCREMENT-154-NOTES.md`. **Remaining statcheck (b)/(e) are [design] — left for Cliff.** **NEXT (this run):**
progress skipped/failed detail + filename (inc 155, the last cheap autonomous item).

Earlier — increment 153 (synthesis coverage readout + top_k + answerability — backlog #7):
the remaining autonomous part of the Skeptical-synthesizer follow-ups. **Frontend-only** (`20_synthesis.jsx`): a
new `scopeMeta` state `{total, topK}` captured on a papers-scope launch → on done, a **coverage line** "Drew from
**M** of N selected papers · top K chunks (· K contributed no cited passage)" computed from distinct `paper_id`
across the result's citations; an **answerability** note (`.synth-coverage-warn`) when claims exist but none clear
verification (`verifiedCount===0`); and a sharper 0-sentence empty state. `scopeMeta` clears on a query-scope run +
on loading a saved synthesis (N unknown). Display-only — doesn't touch generation/retrieval (so the "eyes on first
run" caveat, about LLM quality, doesn't apply); **Principles non-triggering** (makes coverage inspectable, no new
claim). One CSS recipe `.synth-coverage` (tokens only). pytest **556** unchanged (frontend-only; the data path —
citations carry `paper_id` — is covered by `test_summaries`); `ruff` clean; build + assembly green; QA surface
**109/109 API + 561/561 FE, 0 uncovered**; no migration. **Verified headed, no real egress**
(`.local/visual/drive_inc153_coverage.py` — a fake-generator app citing 1 of 2 selected papers → "Drew from 1 of 2
selected papers · top 8 chunks · 1 contributed no cited passage"; 0 console/page/genai). Notes:
`INCREMENT-153-NOTES.md`. **NEXT (this autonomous run):** statcheck (d) deep-link to the specific failing test (inc
154); progress skipped/failed detail + filename (inc 155).

Earlier — increment 152 (BYOK deferred item: OS-keychain key storage — optional `keyring`, file
fallback): per-provider BYOK keys can live in the **OS keychain** (Windows Credential Manager / macOS Keychain /
Linux Secret Service) instead of the gitignored file. `app_settings._keyring()` returns the `keyring` module iff
importable with a usable backend (else None → file); `get_provider_key` reads keychain→file (a pre-keychain key is
never lost), `set_provider_key` writes the vault + **removes any plaintext file copy** (migrate-on-save) when
available, and **every keyring call is `try/except` → graceful file fallback** (never crashes). `set_api_key`/
`stored_api_key` (inc-146 gemini entry points) route through the per-provider layer; `generator._resolve_key(provider)`
reads via `get_provider_key` + the per-provider env fallback; `settings._stored_key` likewise. `SettingsStatus`
gains **`key_storage`** ("keychain"|"file") + the UI shows where keys live. **`keyring` is OPTIONAL** (a commented
`requirements.txt` entry; `pip install keyring` to enable) — **no new hard dependency**, the ethos holds; absent (the
dev/CI default) → everything uses the file store exactly as before. Keys stay **write-only over the wire**. **Audit
`.claude/security-audits/2026-06-27_keychain-storage.md` PASS** (strictly-stronger at-rest store + safe fallback; no
key loss; no plaintext lingering post-migration; fail-closed; keys never logged/returned). pytest **556** (+4
`test_settings.py`: in-memory fake keyring → vault-not-file, migrate-on-resave, backend-error→file, status reports
`key_storage`); `ruff` clean; build + assembly green; QA surface **109/109 API + 561/561 FE, 0 uncovered** (no new
surface); help corpus + privacy note the keychain option (`HELP-DOCS-SYNCED` → 152). **Verified headed, no egress**
(`.local/visual/drive_inc152_keystorage.py` — the key-storage note renders [file branch; keyring not installed here],
key not in DOM, 0 console/page/genai); **the real OS-vault round-trip is the user's spot-check** (needs `keyring`
installed → writes the real Credential Manager). Notes: `INCREMENT-152-NOTES.md`. **This completes the BYOK deferred
items (inc 151 + 152); the whole BYOK arc — #10 (146) + Test-key (147) + nudge (148) + #39 engine/UI (149/150) +
disclaimer/help-toggle (151) + keychain (152) — is shipped.** **NEXT:** the open backlog is the user's pick.

Earlier — increment 151 (BYOK deferred items: validation-lock disclaimer + help-assistant toggle):
two small Settings → AI features additions. **(A)** A standing footer disclaimer (`.settings-ai-note`): *"Whichever
provider you choose, every summary sentence is still verified locally against your PDFs — your model choice affects
draft quality + coverage, never which citations are accepted."* — the validation-lock (local, provider-agnostic
verification, re-run every result since inc 61) made visible. **(B)** The AI help assistant (already per-provider
via the inc-149 `complete()` seam) is now a Settings **toggle** instead of env-only: `app_settings.
set_help_assistant_enabled` + `GeminiConfig.from_environment()` overlays the stored flag over
`CALLOSUM_HELP_ASSISTANT_ENABLED`; `SettingsStatus` gains `help_assistant_enabled` + `help_source`; `PUT /settings`
accepts it; `35_settings.jsx` shows an **AI help assistant** switch (its OWN gate — sends only the question + public
help docs, never library text — independent of egress). **No new audit** (the only schema change is a non-secret
bool toggle identical to the audited egress flag; no secret/fetch/migration); **Principles gate aligned/non-triggering**
(the disclaimer reinforces "verification is the substrate's job, not the model's"). pytest **552** (+2
`test_settings.py`); `ruff` clean; build + assembly green; QA surface **109/109 API + 561/561 FE, 0 uncovered**; help
corpus help-assistant section updated (`HELP-DOCS-SYNCED` → 151). **Verified headed, no egress**
(`.local/visual/drive_inc151_aisettings.py` — the help toggle flips + the disclaimer renders; 0 console/page/genai).
Notes: `INCREMENT-151-NOTES.md`. **NEXT:** inc 152 — OS-keychain key storage (optional `keyring` + file fallback;
the last deferred #39 item; audited).

Earlier — increment 150 (multi-provider Settings UI — #39 part 2; completes #39):
the Settings → AI features section became **provider-aware**. **`PUT /settings`** extended — `provider` (allowlisted
→ 422), per-provider `api_key` via `api_key_provider` (gemini stays the inc-146 `api_key` field), `local_base_url`
(**loopback-validated → 422**), `model`; `SettingsStatus` gained `provider`/`local_base_url`/`model`/
`provider_keys_set` (which cloud providers have a key — **never a value**). **`POST /settings/test-key` is now
provider-aware** (validates the active provider via `complete()`; cloud egress-gated, local runs regardless +
only hits the loopback endpoint; the gemini-only `_ping_gemini` was removed). Frontend (`35_settings.jsx`): a
**Model provider** dropdown (Gemini/OpenAI/Anthropic/Local) — cloud shows a key field + the egress toggle; **Local**
shows a loopback `base_url` field + a "nothing leaves your machine" note + **no egress toggle**; the Test button
reads "Test key" (cloud) / "Test connection" (local). The **local-no-egress** claim is enforced in **two** places
(the `PUT` write boundary + `complete()`), so a non-loopback "local" endpoint can never be stored. Per-provider keys
stay **write-only over the wire**. **Audit addendum** to `2026-06-26_multi-provider-llm.md` **PASS** (PUT schema
extension: provider allowlist, loopback-422, per-provider key isolation/write-only, provider-aware test-key). **Rule
#10:** `route_35_settings.md` extended (provider picker + the local-no-egress step + a "non-loopback local = Critical"
assertion) → surface **109/109 API + 559/559 FE, 0 uncovered**. help corpus AI/privacy sections rewritten for
multi-provider + local (`HELP-DOCS-SYNCED` → 150). pytest **550** (+4 net: `test_settings.py` provider set/422,
loopback-only, per-provider key isolation, local-test-without-egress; inc-147 test-key tests repointed to
`providers.complete`; redaction moved to `test_providers.py`); `ruff` clean; build + assembly green; **no migration**.
**Verified headed, no cloud egress** (`.local/visual/drive_inc150_provider_ui.py` — a fake loopback OpenAI-compatible
server; provider=Local + egress OFF → base_url shown, no key/no egress toggle, **Test connection works against the
loopback server with 0 cloud-host hits**; switch to OpenAI → key + egress toggle; 0 console/page errors). Notes:
`INCREMENT-150-NOTES.md`. **This completes #39 (multi-provider BYOK): engine inc 149 + UI inc 150.** **The BYOK
follow-on batch is done — inc 147 Test-key, 148 synthesis nudge, 149 engine, 150 UI.** **NEXT (deferred):**
OS-keychain key storage (hardening / desktop-shell); real OpenAI/Anthropic/Ollama round-trips (user's manual check).

Earlier — increment 149 (multi-provider LLM engine — #39 part 1):
one provider-neutral **`complete(config, prompt)`** seam (`app/backend/llm/providers.py`) routes all six LLM
generators to **Gemini / OpenAI / Anthropic / a local OpenAI-compatible endpoint** — hand-rolled via **httpx (no new
dependency)**. **The local provider is the flagship: summaries with zero egress.** `GeminiConfig` → **`LLMConfig`**
(back-compat alias kept; ~12 import sites unaffected) gains `provider` + `base_url` + per-provider key resolution
(`from_environment()` reads the stored provider/key/model/`local_base_url`; `DEFAULT_MODELS` per provider). The 6
generators (`generator`/`axis_terms`/`axis_cluster_labeler`/`research_summary`/`overview`/`help_assistant`) each
swapped their `genai.Client().generate_content()` block for `complete(self.config, …)` (uniform ×6; prompt-build +
parse unchanged). The `EgressGated*` wrappers gained a `provider` field + the gate is now
**`if requires_egress(provider) and not data_egress_enabled: raise`** — and the 6 router factories pass
`provider=config.provider`. `app_settings` gained `set_provider`/`set_model`/`set_local_base_url`/`set_provider_key`.
**Principles gate (rule #9) run — the local-no-egress decision:** the egress invariant protects *library text
leaving the machine*; a **loopback-restricted** local model keeps text on the machine, so `requires_egress("local")`
is False — not a loosening of the promise but the promise recognizing local ≠ egress. The misaligned easy path
(arbitrary `base_url` under a "no egress" label) is **declined** — `complete()` rejects a non-loopback local
base_url (`ProviderError`; inc 150 422s it at the write boundary). Cloud providers stay fully gated. **Audit
`.claude/security-audits/2026-06-26_multi-provider-llm.md` PASS** (SSRF: loopback-only local + constant cloud hosts;
per-provider key redaction; fail-closed httpx; no new dep). pytest **546** (+10 `test_providers.py`: per-provider
request/parse/usage via an injected fake client, loopback truth table + non-loopback rejection, the gate [local
skips / cloud blocks], per-provider key resolution, **the headline — a local summary generates with egress OFF**);
the 73 existing LLM tests confirm the gemini path is behavior-preserved through the seam. `ruff` clean; **no
migration, no new endpoint** (engine-only → route + QA surface unchanged); no frontend change. Notes:
`INCREMENT-149-NOTES.md`. **NEXT:** inc 150 — the Settings provider UI (provider dropdown + per-provider key /
local base_url + the egress toggle auto-satisfied for local; `PUT /settings` extension with a loopback-422) + help
corpus "choosing a provider". (Real OpenAI/Anthropic/Ollama round-trips are the user's manual check.)

Earlier — increment 148 (BYOK follow-on: synthesis pane "AI is off" nudge):
when AI is off, the Synthesis pane shows a clear **"AI summaries are off — Enable in Settings →"** nudge instead of
a dead-end raw `DataEgressDisabledError` string. **Frontend-only.** `40_app.jsx`: `paneCtx` gains
`onOpenSettings: () => setSettingsOpen(true)` + a **`settingsNonce`** bumped on the Settings modal's `onClose` (so
panes re-read egress state when Settings closes). `20_synthesis.jsx` (`SynthesisPane` + its `registerPaneSection`
render): a `GET /settings` read on mount + on `settingsNonce` change → `egressOff`; **proactive** `.synth-nudge`
banner above the run controls when off, and **reactive** — the `.errbox` renders the same nudge when `state.error`
contains `DataEgressDisabledError`. One CSS recipe `.synth-nudge` (amber `--flag` banner + a `.btn-link` door,
mirrors `.synth-scope-note`; tokens only, rule #8). Informational, not a block (local features stay usable); reuses
the inc-146 `GET /settings` (no new endpoint) + the inc-121 accordion `paneCtx`. **No Principles trigger** (a UX
affordance over an existing state; egress posture unchanged); **no new surface** (surface map unchanged). pytest
**536** unchanged (frontend-only; wiring headed-verified); `ruff` clean; build + assembly green; **no migration**.
help corpus synthesis section's egress-off line now describes the nudge (`HELP-DOCS-SYNCED` → 148). **Verified headed,
no egress** (`.local/visual/drive_inc148_nudge.py` — egress OFF → THEORY → Synthesis shows the nudge → **Enable in
Settings →** opens the Settings modal; 0 console/page/genai). Notes: `INCREMENT-148-NOTES.md`. **NEXT:** inc 149–150
multi-provider LLM (#39) — OpenAI/Anthropic/local via httpx; the local provider = summaries with zero egress
(Principles-gate + audit).

Earlier — increment 147 (BYOK follow-on: "Test this key" — egress-gated key validation):
a **Test key** button in Settings → AI features confirms a pasted Gemini key works before the user relies on it.
**`POST /settings/test-key`** (`routers/settings.py`) → `KeyTestResult{ok, detail}`: egress OFF → "Turn on Allow
AI features first…" + **no outbound call** (the toggle's promise stays ironclad — strongest reading of invariant #3,
no second egress path); no key → "No API key is set…"; else `_ping_gemini(model, key)` makes a minimal **non-library**
call (`generate_content(contents="Reply with the single word OK.")`). The key is **never logged**, and any provider
error is **redacted** (`str(exc).replace(key, "***")`) + length-capped before reaching `detail`. Frontend: a Test
key button + ✓/✗ result line (`35_settings.jsx`, shown when a key is available); one CSS block `.settings-keytest`
(`.ok`=green `--verified`, `.err`=amber `--flag-ink`). **Principles gate non-triggering** (no claim/signal; it
*strengthens* the egress posture). **Audit `.claude/security-audits/2026-06-26_test-key.md` PASS.** **Rule #10:**
`route_35_settings.md` extended (`/settings/test-key` + the egress-off-no-call step) → surface **109/109 API +
549/549 FE, 0 uncovered**. help corpus Settings AI bullet gained a Test-key line (`HELP-DOCS-SYNCED` → 147). pytest
**536** (+4 `test_settings.py`: egress-off→no-ping, egress-on+no-key, egress-on+key→ping, `_ping_gemini` redaction;
route-surface extended); `ruff` clean; build + assembly green; **no migration**. **Verified headed, no egress**
(`.local/visual/drive_inc147_testkey.py` — key saved + egress OFF → Test → "Turn on Allow AI features…", **0 genai**,
key not in DOM). Notes: `INCREMENT-147-NOTES.md`. **NEXT:** inc 148 (synthesis-pane egress-off nudge) → inc 149–150
(multi-provider LLM #39: OpenAI/Anthropic/local via httpx; the local provider = summaries with zero egress).

Earlier — increment 146 (BYOK — Gemini API key + egress consent from the Settings UI):
the user-prioritized feature after the slate. Set the Gemini **API key** and toggle **data egress** from
**Settings → AI features**, instead of editing env vars — so a GitHub user can enable AI summaries end-to-end
from the UI. New `app/backend/app_settings.py` (a tiny local store: read/write a JSON file at
**`~/.callosum/app-settings.json`**, override `CALLOSUM_SETTINGS_PATH` — *outside the repo + the synced Dropbox
folder*, so the secret never travels with a copy of the library `.sqlite`; atomic write, best-effort 0600,
fail-soft load). **`GeminiConfig.from_environment()` overlays** the stored key + egress over the env defaults
(lazy import; stored wins, env is the fallback) — so all ~12 AI call sites pick up BYOK with **zero call-site
changes**. New `routers/settings.py`: **`GET /settings`** returns **status only** (`api_key_set`,
`api_key_source`∈{ui,env,null}, `data_egress_enabled`, `egress_source`) — *never the key value*; **`PUT /settings`**
sets/clears the key + toggles egress (`set_api_key` guard so an egress-only PUT can't clear the key; `max_length`
512 → 422). Frontend: a Settings **AI features** section (`35_settings.jsx`) — a password-masked key input +
Save/Clear (+ a "Get a key →" link) and an **"Allow AI features (sends text to Google)"** toggle (default OFF);
one CSS class `.settings-keyrow`. **The egress invariant (#3) is unchanged** — egress stays default-OFF (stored
flag absent → env fallback, default off), the `EgressGated*` gate logic is byte-identical, and a present key does
**not** bypass the gate (test: stored egress OFF + key set → still raises `DataEgressDisabledError`). The UI
toggle is an explicit, labeled, default-off opt-in (consent surface moved from env var to UI control). **Key
storage was the user's call** (gitignored local file, over OS-keychain/DB/in-memory) — realized at `~/.callosum/`
to keep the secret out of the synced DB; OS-keychain is the documented hardening upgrade (ties to the
desktop-shell packaging). **Audit `.claude/security-audits/2026-06-26_byok-api-key.md` PASS** (key never
logged/returned/committed; length-capped; fixed/env settings path → no traversal; no new dependency; egress-off
still blocks). **Rule #10:** `route_35_settings.md` extended (BYOK steps + the key-secrecy + egress-default-off
assertions) → surface **108/108 API + 547/547 FE, 0 uncovered**. help corpus's Settings + privacy sections updated
(`HELP-DOCS-SYNCED` → 146). pytest **532** (+8 `test_settings.py`: store round-trip/clear, GET-never-returns-key,
PUT set/clear/toggle, oversized-key 422, env-source status, config overlay of stored key + egress, egress-off-
still-blocks; route-surface extended); `ruff` clean; build + assembly green; **no migration**. **Verified headed,
no egress** (`.local/visual/drive_inc146_byok.py` — egress toggle defaults OFF; paste a key → Save → `GET /settings`
has **no key value in the body or DOM**; toggle egress on→off, 0 genai; Clear → stored UI key removed, falls back
to env; 0 console/page/genai). Notes: `INCREMENT-146-NOTES.md`. **NEXT (deferred):** OS-keychain storage
(hardening / desktop-shell); a "test this key" egress-gated ping; an inline "AI is off — enable in Settings" nudge
in the synthesis pane when egress is off.

Earlier — increment 145 (discoverable multi-paper focus query — Skeptical synthesizer dogfood;
**completes the build-and-test slate, 4/4**): the last slate build. A dispatched **Skeptical synthesizer** persona
agent drove the select→summarize flow and found the trust machinery is strong (every claim carries quote+page+
confidence; verified-vs-flagged is clean) and **the focus query already worked** (a query in the Synthesis textarea
makes the selection summary query-ranked, inc 111) — **but it was invisible at the moment of action**: the focus
lived in a different accordion section, the selection bar's `summarize` gave no hint, and the help even *misframed*
selection-summarize as "without phrasing a question." Fix (frontend + a help edit): a **"Focus on… (optional)"** input
in the library selection bar (`10_pdf_layer.jsx`) → `bulkSummarizePapers(focus)` (`40_app.jsx`) → `pendingSummarize.focus`
→ the multi-paper synthesis (`20_synthesis.jsx`) **prefers it** (falls back to the textarea, inc-111), reflects it into
the textarea, and sets `body.query = focus` (query-ranked) + the "focused on …" scope-note. **Discoverability, not a
new capability** — the backend papers-scope already honored `query`; the verification spine + honesty contract are
unchanged (the focus *ranks* coverage, never fabricates). **Principles gate non-triggering** (no new claim type).
pytest **524** unchanged (frontend + help; wiring headed-verified); `ruff` clean; build + assembly green; surface
**106/106 API + 539/539 FE, 0 uncovered**. **Verified headed, no egress** (`.local/visual/drive_inc145_focus.py` —
select 2 papers → Focus input → summarize → the `POST /summarize` body carries `query=<focus>` + `scope_type:papers`,
the scope-note reads "focused on …", the textarea reflects it; 0 console/page/genai). Help corpus also brought current
for inc 143 (durable keyword deletion) + inc 144 (export highlights) → `HELP-DOCS-SYNCED` moved to 145. Remaining
synthesizer findings → backlog #7 (coverage readout "drew from M of N"; answerability note; show the top_k cap).
Notes: `INCREMENT-145-NOTES.md`. **The slate is done — 6 persona runs (incl. inc 141), 6 real gaps found + fixed,
validating the experience-pass gate + its persona-agent mechanism.** **NEXT: BYOK** (Gemini API key in Settings →
full bring-your-own-key) — user-prioritized to the top of the pile now that the slate is complete.

Earlier — increment 144 (export / copy a paper's highlights + notes — Close reader dogfood): the
4th build in the slate. A dispatched **Close reader** persona agent drove the read→highlight→note→navigate→return
flow and found the reading experience is genuinely good (page comfort, select→note in one gesture, a Notes panel
that lists + jumps + flashes, marks that persist + re-find) — but **no way to get the marks *out***: they're trapped
in the panel (no copy-all, no per-paper digest, no markdown export). Fix (frontend-only, `30_viewer.jsx`): **Copy** +
**Export .md** buttons in the Notes panel head (shown when ≥1 highlight) assemble a Markdown **digest** from the
already-loaded annotations (`# title`, `**p.N** — <highlighted text>`, the note as a `> blockquote`, page-ordered) —
`copyDigest` via `navigator.clipboard` + `exportDigest` via a blob `*-notes.md` download (the inc-70 pattern). No
backend endpoint / new data (the annotation list already carries quote+note+page; a reusable export endpoint is a
deferred follow-up). pytest **524** unchanged (frontend-only; the pure `buildAnnotationDigest` is **node-verified**,
the flow **headed-verified**); `ruff` clean; build + assembly green; surface **106/106 API + 536/536 FE, 0 uncovered**.
**Verified headed, no egress** (`.local/visual/drive_inc144_marks.py` — seeds a real 2-page PDF + 2 marks, opens the
viewer → Notes panel → Copy → the exact digest is read back off the clipboard; 0 console/page/genai). Remaining
close-reader findings filed to the backlog (keyboard zoom + next/prev-mark hotkeys; noted-only filter + note-text
search; fit-page + remembered scroll position; free-form note colors; a minimap highlight marker). Notes:
`INCREMENT-144-NOTES.md`. **NEXT (the slate, last):** inc 145 **Skeptical synthesizer ↔ multi-paper focus query (#7)**
(needs egress to test live). **Then BYOK** (user-prioritized after the slate).

Earlier — increment 143 (deleting an imported keyword tag is durable — Librarian experience pass +
backlog #3): the 3rd build in the slate. A dispatched **Librarian** persona agent drove the tag-curation + 🔎 re-resolve
flow and found: tags don't *duplicate* and imported-vs-typed is clear (those work), but **deleting an imported keyword
tag isn't durable** — `apply_crossref_subject_tags` re-adds *every* `subject`, so re-resolve (the cleanup button)
silently **resurrects** a keyword the librarian deliberately removed. Fix (backend-only, the tag analogue of the inc-49
user-edit guard): a per-paper **`suppressed_paper_tags`** table (migration **0020**, additive/guarded) keyed by
`(paper_id, tag_name)`; `remove_tag_from_paper` reads the removed tag's source *before* the orphan-prune and, if it's
an imported `keyword:*` tag, records a suppression; `add_tag_to_paper` **clears** it (re-adding = the user wants it);
`apply_crossref_subject_tags` filters `subject` by the suppressed set, so 🔎 re-resolve **and** `backfill_keyword_tags.py`
honor the deletion. Gated to keyword sources (removing a **user** tag never suppresses). No new endpoint/response/egress/
surface (rides the existing `DELETE /papers/{id}/tags/{tag_id}` + re-resolve). pytest **524** (+2: delete-keyword-not-
re-added round-trip; user-removal-doesn't-suppress); `ruff` clean; migration head **0020** (derived by `alembic_head()`,
no test edit); apply-callers unchanged. **Backend-only → unit-verified the exact librarian scenario** (import → delete →
re-resolve → stays gone → re-add → cleared); the UI (TagsRow ×, 🔎) is unchanged. Remaining librarian findings filed to
backlog #3/#9 (a re-resolve-overwrites-metadata confirm; an always-on source label; a diff toast; a tag-lock). Notes:
`INCREMENT-143-NOTES.md`. **NEXT (the slate):** inc 144 **Close reader ↔ dogfood the reading flow**; inc 145
**Skeptical synthesizer ↔ multi-paper focus query**. **Then BYOK** (user-prioritized after the slate).

Earlier — increment 142 (determinate import/scan progress — Migrator experience pass + backlog #4):
the 2nd build in the "build + persona-test 4 features" exercise (after inc 141). A dispatched **Migrator** persona
agent drove the import/scan onboarding flow and found the bar was an **indeterminate pulse** ("looks identical at item
3 and item 380") — for a few-hundred-item import the migrator's #1 anxiety ("stuck? how far?") went unanswered (the
backlog's "add a progress bar" was already partly met by the indeterminate bar — the pass found the *real* gap). Built
**determinate "X / N" progress**: `JobStore` gained `JobProgress{current,total,label}` + `mark_progress`;
`embed_papers`/`embed_chunks` (the slow phase) + `scan_library_folder` (per file) take an opt-in `on_progress(current,
total)` callback the scan/import jobs wire through ("Reading PDFs" → "Fetching metadata" → "Embedding papers"); the
`Scan`/`ImportJobResponse` expose `progress`; the modals render a real fill + "Embedding papers — X / N" (the
`.progress-fill-det` modifier kills the sweep) instead of the pulse. Plus a **"Review unsorted →"** door in the scan
done-summary (`added>0`) → the inc-80 Unsorted view. **Opt-in + additive** (other jobs stay indeterminate → zero
blast radius). pytest **522** (+3: `test_job_store` ×2, `embed_papers` per-paper progress); `ruff` clean; build +
assembly green; surface **106/106 API + 532/532 FE, 0 uncovered**; no new endpoint/migration/egress. **Verified
headed, no egress** (`.local/visual/drive_inc142_progress.py` — a slowed-fake-model server imports an 8-record .bib →
the bar shows "Embedding papers — 4 / 8" mid-run + finishes "8 imported"; 0 console/page/genai). Remaining migrator
findings filed to backlog #4 (a skipped/failed-detail list; per-item filename + ETA; a cancel button). Notes:
`INCREMENT-142-NOTES.md`. **NEXT (the slate):** inc 143 **Librarian ↔ protect imported/system tags from clobber (#3)**;
then inc 144 **Close reader ↔ dogfood the reading flow**; inc 145 **Skeptical synthesizer ↔ multi-paper focus query**.
**Then BYOK** (Gemini API key in Settings) — **user-prioritized to the top of the pile after the slate.**

Earlier — increment 141 (statcheck flagged→detail path — the experience-pass fix): the first fix
**produced by** the inc-140 end-user experience pass. The dogfood (deadline-citer persona vs statcheck) found that
"this paper is flagged" and "here is the specific result that doesn't recompute" were two good halves that **didn't
link** — the METHODS pane defaults to **Details**, and the "⚠ N flagged" chip→filter left you on Details with the
already-selected paper. Fix (frontend-only, `40_app.jsx` + `06_methods_statcheck.jsx`): the flagged chip now (1) opens
the METHODS **Statistics check** section (`setMethodsOpen("statcheck")`; `methodsOpen` added to `paneCtx`), (2)
**re-targets the top *flagged* paper** via a **`pendingSelectTopRef`** resolved in the `/papers` fetch callback (so it
selects the *filtered* list's top, not the stale pre-filter one — the bug behind the first failed headed run), and (3)
the per-paper `StatcheckPaper` **auto-runs** its check when its section is the open one (`active = ctx.methodsOpen ===
"statcheck"`; gated so the mount-but-hidden section never runs) — so the inconsistent rows (reported vs recomputed *p*
+ page link) show with **no manual "Check statistics" click**. Net: the citer clicks "⚠ N flagged" → the flagged
paper's specific result is right there (backlog sub-findings (a)+(c) shipped; (b)/(d)/(e) remain). **No Principles
trigger** (UX wiring; counts/rows unchanged — still a list-to-review, region page-open); **no new surface** (106/106 API
+ 530/530 FE, 0 uncovered); pytest **519** unchanged; `ruff` clean; build + assembly green. **Verified headed, no
egress** (`.local/visual/drive_inc141_statcheck_path.py` — chip → Statistics check opens → flagged paper auto-selected →
inconsistent row auto-shows `computed p = 0.0449` vs reported `.001`; 0 console/page/genai). Notes: `INCREMENT-141-NOTES.md`.
**NEXT (queued):** remaining statcheck sub-findings (b on-paper entry [design], d deep-link to the test, e flagged-vs-to-review
duality [design]); gap-finder followed-authors / similarity ranking; a cadence auto-refresh. **Watch (rule #1):**
`clustering/my_publications.py` at **594/600**.

Earlier — increment 140 (the end-user experience pass — a 4th gate — + its first dogfood): codifies
the standing orientation the user asked for — **before any user-facing change is "done," make a pass inhabiting the
end user of the thing you touched** (does it actually *serve* them?). New **`.claude/EXPERIENCE-PASS.md`** + **CLAUDE.md
rule #11**: two questions — (1) **reception** (discoverable / legible / is the next step obvious) and (2) **intended
use** (what does the user reach for next; does the built thing support it or dead-end), the latter **bounded by our
commitments** (a desire conflicting with the ethics — accusation, paywall circumvention, an opaque score — is *declined*
per #9 + A-A, not served). The user's key upgrade = the **mechanism**: *persona-grounded experience agents* — dispatch
a subagent **in character** as a concrete persona with a **goal in the moment** (the **deadline citer** vetting a paper's
stats before citing; the corpus builder; the skeptical synthesizer) to drive the feature and report what's left to be
desired — grounding turns "is the UX good?" into "can *this* person, doing *this*, get where they're going?" The 4th
gate beside DESIGN (#8 looks) / PRINCIPLES (#9 honest) / QA (#10 works+covered) → **EXPERIENCE (#11 serves the user)**;
reflective pause → a finding (fix-cheap or backlog). **Dogfooded immediately:** a deadline-citer agent drove the live
statcheck flow and found the per-paper drill-down (METHODS → Statistics check → "This paper" → per-test rows) is
**hidden** — the METHODS pane defaults to Details and the "⚠ N flagged" chip→filter lands on Details, ignoring the
flagged state, so "flagged" and "the specific result that doesn't recompute" never link. Filed **▲ BUILD FIRST** to
`INCREMENT-BACKLOG.md` (5 sub-findings, simplest-first; (a) open Statistics check from the flagged view = the cheap fix).
**Docs-only** — no app code / build / migration / surface change; pytest **519** unchanged. Notes: `INCREMENT-140-NOTES.md`.
**NEXT (queued):** the statcheck flagged→per-test fix [build-first (a)]; gap-finder followed-authors / similarity ranking;
a cadence auto-refresh. **Watch (rule #1):** `clustering/my_publications.py` at **594/600**.

Earlier — increment 139 (accordion tabs-within-a-section — Tags becomes a tab of AXES; METHODS
reordered): codifies the IA rule that **accordion sections are broad tool categories and TABS present like-with-like
submenus** (DESIGN.md §5). **`05_panes.jsx`** registry now supports tabs: `registerPaneTab({id,label,paneId,order},
{id,label,order,render})` adds a tab to a find-or-created host section; `registerPaneSection` is sugar for a one-tab
section (no strip). A section with ≥2 tabs renders a **segmented tab strip** (reuses the `.tags-srcfilter` chip recipe
— the user-approved style) + **mount-but-hides** the inactive tabs (`.pane-tab:not(.active){display:none}`, so an open
axis / running action survives a switch); the active tab persists (`callosum.panetab.<sectionId>`). **THEORY:** **Tags**
moves from its own section to the **second tab of AXES** (`[Axes | Tags]`, `15_axes.jsx` + `10_pdf_layer.jsx` →
`registerPaneTab`) — like-with-like (your labels beside your conceptual lenses); discoverability is preserved (the Tags
tab is always visible when AXES is open, the default). **METHODS reordered by cognitive task:** **Data consistency
(GRIM)** (`order: 20`) now precedes **Statistics check** (`order: 30`) — raw-data check before analysis check; future
stat checks become **tabs** within Statistics check, not new sections. **Frontend-only** — no backend/API/migration/egress;
no Principles trigger (IA, not a new claim/signal). **Rule #10:** route_00 + route_20_tags repointed to the Tags tab;
surface **106/106 API + 530/530 FE, 0 uncovered** (the new tab strip). help corpus's left-pane + Tags lines updated
(`HELP-DOCS-SYNCED` → 139). pytest **519** unchanged; `ruff` clean; build + assembly green. **Verified headed, no egress**
(`.local/visual/drive_inc139_panetabs.py` — THEORY = [AXES, SYNTHESIS] with [Axes|Tags] tabs + mount-but-hide switching;
METHODS GRIM-before-statcheck; 0 console/page/genai). Notes: `INCREMENT-139-NOTES.md`. **NEXT (queued):** gap-finder
followed-authors / similarity ranking; a cadence auto-refresh; the broader backlog. **Watch (rule #1):**
`clustering/my_publications.py` at **594/600** — split before the next backend addition there.

Earlier — increment 138 (auto-select the top library paper on load — Details populated): on app
load the **top library paper is auto-selected**, so the METHODS → DETAILS section starts **populated** (its editable
Details) instead of the empty "Select a paper …" hint — the right pane is useful without a first click. **Frontend-only**
(`40_app.jsx`): an effect sets `selected` to `listState.papers[0].id` when **nothing is selected** and the **(non-trash)**
list is ready with papers; it fires on first load + when a selection clears to null (e.g. the selected paper was trashed),
and **never overrides** a paper the user already picked (guarded `selected == null` → idempotent, no loop). Auto-selects
**Details only** (does not open a PDF tab — `openPdf` is separate). **No Principles trigger** (auto-triggers an existing
view-state), **no new surface** (surface map unchanged 106/106 API + 528/528 FE, 0 uncovered) — `route_00` step 5 reworded
(DETAILS starts populated; the hint shows only for an empty library). pytest **519** unchanged; `ruff` clean; build +
assembly green. **Verified headed, no egress** (`.local/visual/drive_inc138_autoselect.py` — on load the top paper's
title fills Details, no hint, clicking another paper updates it; 0 console/page/genai). Notes: `INCREMENT-138-NOTES.md`.
**NEXT (queued):** the accordion-tabs design rule (tabs-within-a-section for like-with-like — Axes+Tags tabs; order
Data-consistency before Statistics-check; codify in `DESIGN.md`); gap-finder followed-authors / similarity ranking; a
cadence auto-refresh. **Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend
addition there.

Earlier — increment 137 (gap-finder v2 — forward gap + axis-scoped + persistent cache): rounds
out the inc-135 backward gap-finder with the user-chosen scope. **Forward gap** (`compute_gaps(direction="forward")`):
works that **cite** ≥ N of your papers ("cites N of your papers") — newer work building on your collection — via new
OpenAlex `fetch_work_id` + `fetch_citing_works` (`?filter=cites:<W…>`, validated `^W\d+$`, cached `citing:<id>`,
capped `MAX_CITING=200`, fail-closed); **backward** (works your papers cite) is the unchanged other branch. **Axis-scoped**
(`axis_id`): `_scoped_paper_rows` restricts the scan to an axis's members (inc-63 subquery). **Persistent cache**
(`gap_candidates`, **migration 0019**; `persistence/gap_repo.py` replace-all-per-scope + read): **`GET /gaps
{direction,axis_id}`** reads the cache and **filters dismissed / now-in-library at read time** (Add/Dismiss take
effect with no recompute), **`POST`/`GET /gaps/refresh`** recomputes + replaces a scope (the inc-135 `/gaps/find*`
removed). Frontend `36_gaps.jsx` gains a **direction toggle** + an **axis dropdown** + a **Refresh** button (opening /
toggling reads the cache instantly; a "Last refreshed …" line). **Honesty/Principles unchanged** — "cited by / cites N
of *your* papers" is a library count, never a global importance/quality rank; coverage stated; candidates-not-verdicts;
Add metadata-only (no PDF → no paywall circumvention); forward adds no new judgment (declined a must-read leaderboard).
**Gotcha:** OpenAlex ids are `W`+**digits** — the backward path drops non-digit ids (`^W\d+$`), so seed/test data must
use real `W<digits>` ids. **Rule-#1 prerequisite:** split `schema.py` (611→**558**, over since inc 130/132) — the
findings/signals/retraction/gap tables moved to `persistence/schema_findings.py` on a shared `persistence/schema_base.py`
`metadata`, re-exported from `schema.py` (no circular import; zero blast-radius; `metadata.create_all` still includes
every table). Audit: **addendum** to `2026-06-26_gapfinder.md` (same OA-metadata posture; additive/guarded migration;
bound-param SQL; no new dependency; no Gemini egress) **PASS**. Rule #10: `route_41_gaps.md` updated → surface
**106/106 API + 528/528 FE, 0 uncovered**. pytest **519** (+5: `fetch_work_id`, `fetch_citing_works`, forward,
axis-scoped, `gap_repo`, + 2 endpoint tests replacing the find-endpoint tests); `ruff` clean; build + assembly green;
migration head **0019**. **Verified headed, no egress** (`.local/visual/drive_inc137_gaps.py` — free port + own-process
check; pre-seeded `external_api_cache` so the real client runs offline: Refresh backward → "cited by 3 of your papers"
+ coverage; toggle forward → Refresh → "cites 3 of your papers"; Dismiss drops the row; 0 console/page/genai). Notes:
`INCREMENT-137-NOTES.md`. **NEXT (queued):** auto-select the top library paper on load (Details populated); the
accordion-tabs design rule (tabs-within-a-section for like-with-like — Axes+Tags tabs; order Data-consistency before
Statistics-check; codify in `DESIGN.md`); gap-finder followed-authors / similarity ranking; a cadence auto-refresh.
**Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend addition there.

Earlier — increment 136 (watched folders rescan on window focus — live-ish pickup): a user
dropped a PDF into their library folder expecting it to appear (and be retraction-tagged); nothing happened.
Root cause (no code bug): the watched-folder auto-rescan only ran **on app launch** (`40_app.jsx`'s effect had
`[]` deps → mount-only), so a **mid-session** drop wasn't picked up until a restart / manual "Re-scan all". Fix
(**frontend-only**): the rescan now also fires **on window `focus`** (throttled 20s + an in-flight guard, gated by
the existing `callosum.autoScanWatched` toggle) — drop a PDF, switch back to Callosum, it appears. The rest of the
chain already worked: scan → `pdf-scaffold` → enrich (**`find_doi_in_pdf` reads the DOI from the PDF text**,
`enrichment.py:160` → Crossref → metadata) → the inc-134 `auto_check_retractions` tags it. Two prerequisites the
user owns: the folder must be **registered as watched** (a one-time "Scan folder" via the UI — can't be done
remotely), and a retraction check must have run / runs on-import. pytest **514** unchanged (frontend-only; the
rescan endpoint + chain are already tested); build + assembly + the e2e suite green; help corpus watched-folders
line updated (`HELP-DOCS-SYNCED` → 136). Notes: `INCREMENT-136-NOTES.md`. **NEXT (queued):** gap-finder v2
(forward gap + axis-scoped ranking + a persistent `gap_candidates` cache — user-chosen scope); auto-select the top
library paper on load; the accordion-tabs design rule (tabs-within-a-section for like-with-like, Axes+Tags tabs,
order Data-consistency before Statistics-check, codify in `DESIGN.md`); a true live OS file-watcher later if
focus-rescan isn't enough.

Earlier — increment 135 (literature gap-finder — backward citation gap): a new **discovery**
capability (a long-wanted future-track). Aggregate each library paper's OpenAlex **`referenced_works`** → surface
external works cited by **≥ N (default 3) of your papers** that the library doesn't have ("**cited by N of your
papers**") as **Add / Dismiss candidates** — the inverse of the inc-119 "who cites my work" feature. New OpenAlex
adapter methods `fetch_referenced_works` (cached DOI→work, bare `W…` ids, capped, fail-closed) + `fetch_work_meta`
(a candidate by `W…` id — **validated `^W\d+$` before any fetch**, cached); `clustering/gapfinder.compute_gaps`
(aggregate `ref_id → set(paper_id)`; keep ≥ min; **exclude** no-DOI / already-in-library / dismissed; rank by
count + a coverage dict); an **ephemeral async job** `POST`/`GET /gaps/find` (`app.state.gap_jobs` over
`app.state.openalex_client`); `POST /gaps/add` (reuses the inc-119 `import_citing_work` with a new `imported_source`
param → `"gap-import"` — **metadata-only, deduped, into the general library**; the PDF stays the OA-acquire lane →
no paywall circumvention); `POST /gaps/dismiss` (persisted in `profile.dismissed_gap_works`, **migration 0018**
additive; `dismiss_gap` inserts a minimal profile row if none — the gap-finder needs no My-Pubs profile). A **"Gaps"**
library-header button → `36_gaps.jsx` modal (Find gaps → candidate list + Add/Dismiss + the coverage caveat).
**Honesty/Principles:** "cited by N of *your* papers" is a count over the user's own library, **never a global
importance/quality rank**; coverage is **stated** ("scanned M of N papers; partial"); candidates-not-verdicts; no
PDF on Add. **Principles gate run** (declined a "must-read importance leaderboard"); **audit
`.claude/security-audits/2026-06-26_gapfinder.md` PASS**; **rule #10** `route_41_gaps.md` → surface **105/105 API +
522/522 FE, 0 uncovered**; help corpus gained a "Finding gaps in your library" section (`HELP-DOCS-SYNCED` → 135).
Egress = public **OpenAlex/Crossref metadata** (bounded, cached, fail-closed), **not** the Gemini gate. pytest
**514** (+8 `test_gapfinder.py`); `ruff` clean; build + assembly + the **e2e suite** green; migration head **0018**.
**Verified headed, no egress** (pre-seeded `external_api_cache` so the **real** code path ran offline — a "cited by
3" candidate, Add → in-library; 0 console/page/genai). **Op gotcha:** stray uvicorns from repeated headed-driver
runs can hold a port + serve a *stale* app — use a free port + assert your own process is alive (folded into
`route_41`). **Watch:** `my_publications.py` at **594/600** (the `import_citing_work` signature growth) — split
before the next addition there. Notes: `INCREMENT-135-NOTES.md`. **NEXT:** axis-scoped gaps ("gaps for [axis]"); a
persistent `gap_candidates` cache (v1 recomputes — cached OpenAlex makes the 2nd run fast); external-search
discovery beyond the library.

Earlier — increment 134 (retraction lifecycle — on-import auto-check + RW staleness nudge):
completes the producer's world-state lifecycle. The retraction producer checked only on demand (the batch /
per-paper), so a freshly imported retracted paper wouldn't flag until a manual re-run. Now: (1) **on-import
auto-check** — new `methods/retraction.py::auto_check_retractions(conn, paper_ids, *, checkers)` runs a **guarded
best-effort** detect+apply over a set of papers (each wrapped in `try/except` on top of `detect_retraction`'s
per-source guard, so a source error / missing row **never aborts the import**), hooked into the **scan** job
(`_process_scan_result` gained a `retraction_checkers` param, passed by scan + watched-rescan) and the
**citation-import** job over the *new* paper ids via `app.state.retraction_checkers` — a freshly imported
retracted paper flags immediately (Crossref reads the cache the enrich just populated; the RW mirror is offline;
OpenAlex is one cached lookup → marginal); (2) an **RW staleness nudge** — the Retraction Watch panel computes its
snapshot age from `retrieved_at` and past **30 days** appends "· N days old — refresh recommended" (amber; the
data isn't wrong, just old). **No new endpoint, migration, external-fetch type/host, or dependency** → reuses the
inc-131 audit (an **addendum** was added to `2026-06-26_retraction.md`) + the established Principles posture (no
new claim type); **no new end-user surface** (an internal auto-check + a text nudge in the already-QA-covered RW
panel) → no new QA route, surface map unchanged (**0 uncovered**). help corpus's retraction section gained the
on-import + staleness lines (`HELP-DOCS-SYNCED` → 134). pytest **506** (+2 `test_retraction.py`:
`auto_check_retractions` best-effort [flagged / clean / missing-id swallowed]; the citation-import job auto-checks
→ the imported paper carries the FACT); `ruff` clean; build + assembly + the **e2e suite** green locally; the
staleness endpoint + render confirmed live. `library.py` 284/600. Notes: `INCREMENT-134-NOTES.md`. **This
completes the retraction arc end-to-end (131 SP1 → 132 SP2 → 133 candidate-review → 134 lifecycle).** **NEXT:**
on-import for the Zotero / single-PDF paths; an automatic *cadence* refresh of the RW DB; the broader backlog
(discovery/gapfinder, a live OS file-watcher, the Word/Docs adapters, auth).

Earlier — increment 133 (activate the candidate-review half — statcheck candidates + a unified
"N to review" facet): the inc-130 Confirmed/Accepted/Noted candidate-review machinery was built but **unexercised**
(the only producer, retraction, writes *facts*). Now the **statcheck batch also emits a CANDIDATE finding** per
flagged paper (`source="statcheck"`, `desc` + counts + the flagged result's page; clean re-check → supersede; a
reviewed candidate's state is **preserved** across re-runs via `upsert_findings`' `content_key` idempotency) —
**coexisting** with the inc-97 **signal** (the candidate = the user's reviewable *work-state*; the signal = the
persistent *fact* about the paper — reviewing the candidate drops it from the review queue but **not** from the
"⚠ N flagged" statcheck filter). A unified **"📋 N to review"** library chip (count of papers with an unreviewed
candidate, derived from the `/findings/overview` already fetched into `findingsByPaper`) + filter view
(`GET /papers?finding=needs-review` → `repository.FINDING_FILTERS` allowlist → a bound subquery on
`paper_findings.review_state`, mirroring the inc-97 `SIGNAL_FILTERS`) reuses `librarySignalFilter` with the
sentinel `"needs-review"` (**zero new view-state**); the `/papers` fetch gained `findingsRefresh` as a dep so
reviewing a paper **re-narrows the queue live**. The Review-pane `FindingCard` + per-card badge already render
candidates (inc 130). **Principles** (run inline): a statcheck candidate is *a prompt to look, reviewable* (the
inc-95/97 framing) — signal-not-verdict, no score, non-accusatory; the facet is a work-state queue, not a rank;
retraction **facts** are correctly excluded (`review_state=None`). **No new endpoint, no migration, no external
fetch, no egress** → no audit gate. **Rule #10:** `route_38_findings.md` extended; surface **101/101 API +
510/510 FE, 0 uncovered** (the `finding` param rides the existing `/papers`). help corpus "Reviewing findings"
gained the review-queue lines (`HELP-DOCS-SYNCED` → 133). pytest **504** (+3 `test_findings_review.py`); `ruff`
clean; build + assembly + the **e2e suite (incl. reading mode)** green locally. **Verified headed, no egress**
(`.local/visual/drive_inc133_review.py` — chip → filter → the statcheck candidate card → Confirm → drops from the
queue live; 0 console/page/genai). `methods.py` at **492/600** (split watch). Notes: `INCREMENT-133-NOTES.md`.
**NEXT:** p-curve/GRIM are collection-level / per-value (not per-paper auto-scans → don't naturally emit
candidates, deferred); the retraction **on-import auto-check + a TTL/staleness nudge** remains open; a later
consolidation could fold the statcheck signal chip into the unified facet (coexist is the deliberate v1).

Earlier — increment 132 (Retraction Watch DB, SP2 — the bulk third retraction source):
completes the user's "all three sources" ask. The **Retraction Watch Database** (Crossref-hosted, CC0) joins
Crossref + OpenAlex (SP1) as the **third checker** — downloaded once into a local **`retraction_records`** mirror
(migration **0017**, additive/guarded) and matched against every library DOI **offline**; it's the **richest**
source (nature, date, **reason**, notice), **prepended** to `DEFAULT_CHECKERS` so its detail wins the merge (an
empty mirror → None, the SP1 sources still work). New `persistence/retraction_repo.py` (`replace_retraction_records`
[DELETE-all + bulk INSERT — authoritative, withdrawn records vanish] / `lookup_retraction_record` [most-severe] /
`retraction_db_status`); `integrations/retraction_watch/` (`RetractionWatchClient` — an injectable **size-capped**
https fetcher mirroring `acquisition/fetch.py`, mailto from `CALLOSUM_CROSSREF_MAILTO`, **absent →
`RetractionWatchUnavailable`** fail-closed; `parse_retraction_csv` — **stdlib `csv`, no new dependency**, tolerant
headers, **skips no-DOI + Reinstatement + unknown natures**; `download_retraction_database`). `RETRACTION_WATCH_CHECKER`
in `methods/retraction.py`; endpoints `GET /methods/retraction/database` + async `POST`/`GET
/methods/retraction/database/refresh` (`app.state.retraction_db_jobs` + `retraction_watch_client`, overridable);
a "Refresh database" UI + as-of line + the RW **reason** in the FactMark tooltip. **No new dependency.** Public
**bulk CC0 metadata** (manual-triggered, snapshot date shown) — **not** the Gemini gate; **reinstatements never
flagged** (an un-retraction is the opposite of a finding); `notice_url` derived-only (no SSRF). **Audit
`.claude/security-audits/2026-06-26_retraction-watch.md` PASS**; **rule #10** `route_40_retraction_watch.md` →
surface **101/101 API + 506/506 FE, 0 uncovered**; help corpus gained an RW-database paragraph (`HELP-DOCS-SYNCED`
→ 132). pytest **501** (+8 `test_retraction_watch.py`); `ruff` clean; build + assembly green; migration head 0017.
**Verified headed, no egress** (`.local/visual/drive_inc132_retraction_watch.py` — as-of line, FactMark + notice +
RW-reason tooltip; 0 console/page/genai). **The real CSV download is the user's manual check** (needs their
`CALLOSUM_CROSSREF_MAILTO` + a ~tens-of-MB fetch; verifies the live URL + CSV schema the hermetic tests assume).
`methods.py` at **463/600** — a `routers/retraction.py` split when it next grows. Notes: `INCREMENT-132-NOTES.md`.
**This completes the retraction arc (SP1 inc 131 + SP2 inc 132) — all three sources.** **NEXT:** an on-import
auto-check + TTL/cadence refresh; then statcheck/p-curve/GRIM can emit *candidates* into the findings store + a
unified library-wide "needs review" facet.

Earlier — increment 131 (retraction producer, SP1: Crossref + OpenAlex — the first findings
producer): the first real producer feeding the inc-130 findings contract. For each library paper's DOI, query
**multiple sources** (Crossref + OpenAlex in SP1), **merge**, and persist a **FACT** in `paper_findings` (the
Review-pane FactMark + a notice link + the ◆-fact card mark) plus an honest per-paper **check status** in
`open_science_signals` (`none` when checked-clean, `unchecked` when no DOI — **silence ≠ clean**) that also powers
a library **"Retracted" chip + filter**. The user asked for *all three* sources ("critical to know before
citing") → SP1 = the per-DOI two-source core via the existing audited adapters; **SP2 (inc 132) adds the
Retraction Watch DB** as a third checker (the merge layer already accepts it → additive). New
`app/backend/methods/retraction.py` (pure `RetractionSignal`/`merge_signals`/`detect_retraction`/`apply_retraction`;
checkers are injected `RetractionChecker`s → **hermetic**; no-DOI → `unchecked`, a source raising is skipped never
aborts, a now-clean paper supersedes its stale FACT); `CrossrefClient.lookup_retraction` parses the raw
`message.update-to`, `OpenAlexClient.lookup_retraction` reads `is_retracted` (the type→status map is **local to
each adapter** — no `methods`→`integrations` cycle); `signals_repo` store/count/get retraction status; endpoints
(`routers/methods.py`) `GET /papers/{id}/retraction` (read-only) + async `POST`/`GET /methods/retraction/run` +
`GET /methods/retraction/summary`; `app.state.retraction_jobs` + `retraction_checkers` (overridable in tests);
`SIGNAL_FILTERS["retraction-retracted"]` for the filter; the frontend FactMark/status-line/chip/filter/batch. **No
migration** (reuses `paper_findings` + `open_science_signals`). **Honesty/Principles:** a registry FACT relayed
verbatim (no LLM), evidence-carried (sources + notice), **no accusation** (the chip is a *filter* count, never an
author/reputation signal — A-A veto), and `notice_url` is **derived-only** (`https://doi.org/<doi>` → no SSRF).
Public DOI metadata egress — **not** the Gemini gate. **Principles gate run** (declined the author-reputation +
unchecked-as-clean easy paths); **audit `.claude/security-audits/2026-06-26_retraction.md` PASS**; **rule #10**
`route_39_retraction.md` → surface **98/98 API + 504/504 FE, 0 uncovered**; help corpus gained a "Checking for
retractions" section (`HELP-DOCS-SYNCED` → 131). pytest **493** (+15 `test_retraction.py`); `ruff` clean; build +
assembly green. **Verified headed, no egress** (`.local/visual/drive_inc131_retraction.py` — chip + filter,
FactMark + notice link, checked-none / unchecked status lines; 0 console/page errors, 0 genai hits). Notes:
`INCREMENT-131-NOTES.md`. **NEXT (queued):** SP2 (inc 132) — the **Retraction Watch DB** bulk source (a
`retraction_records` table + a download/index job + the third checker); then an on-import auto-check + TTL expiry;
then statcheck/p-curve/GRIM can optionally emit *candidates* into the same findings store + a unified
"needs review" facet.

Earlier — increment 130 (findings subsystem — the FACT-vs-CANDIDATE backbone, foundation only):
the architectural spine the METHODS "data-detective" features (statcheck, p-curve, GRIM, and the coming retraction
producer) plug into — a persistent, typed, per-paper **findings** store + a review surface. **v1 ships the contract +
UI only — no producer is wired yet** (retraction is the explicit next increment; user-chosen scope "foundation only").
New **`paper_findings`** table (migration **0016**, additive/guarded): `kind` (**fact** | **candidate**), nullable
`tier`, JSON `payload`, deterministic `content_key`, nullable `review_state`. New `persistence/findings_repo.py` — the
**producer contract** `upsert_findings(conn, paper_id, source, findings)` diffs by `content_key` (**supersede stale +
preserve the review_state of unchanged candidates** → idempotent re-runs), plus `get_paper_findings` /
`findings_overview` / `set_review_state` (allowlisted `confirmed`/`accepted`[needs reason]/`noted`; candidates only).
Endpoints (`routers/findings.py`): `GET /papers/{id}/findings`, `GET /findings/overview`, `POST /findings/{id}/review`
(404/422 on bad input). Frontend `08_methods_findings.jsx` self-registers the METHODS **"Review"** section (order 40):
**FACTs render as neutral marks**, **CANDIDATEs as reviewable cards** (region-precision page anchors — coordinate
honesty intact, no fabricated exact rect); the library card gets a `◆ fact` mark + an **"N to review"** work-state
badge from `/findings/overview` (refetched after a review). **Honesty encoded structurally** — `kind` IS the
FACT/CANDIDATE distinction; the badge counts the user's review work, never paper quality, and vanishes at zero;
nothing auto-acts or labels a paper/author (A-A no-accusation veto). **Principles gate run** (aligned with #2/#3/#5/#7/#8
+ the veto); **audit `.claude/security-audits/2026-06-26_findings.md` PASS** (local, bound-param SQL, validated/escaped,
no egress, no new dependency); **rule #10** new `route_38_findings.md` (+ `04_layout.jsx` folded into `route_00`, a
pre-existing inc-128 gap) → surface **94/94 API + 496/496 FE, 0 uncovered**; help corpus gained a "Reviewing findings"
section (`HELP-DOCS-SYNCED` → 130). pytest **478** (+6 `test_findings.py`; route-surface extended); `ruff` clean; build
+ assembly green. **Verified headed, no egress** (`.local/visual/drive_inc130_findings.py` — badge + FactMark render,
Confirmed reviews + drops the badge, persists across reload; 0 console/page errors, 0 genai hits). Notes:
`INCREMENT-130-NOTES.md`. **NEXT (queued):** the first real **producer** = **retraction** (Crossref / Retraction Watch
→ a **FACT** with a TTL) — its own increment, trips the audit gate (new external fetch) + the Principles gate; then
statcheck/p-curve/GRIM can optionally emit candidates into this store + a library-wide "needs review" facet.

Earlier — increment 129 (multi-item GRIMMER): completes the inc-127 GRIMMER — `grimmer_test`
now supports **multi-item scales** (`items > 1`), not just single-item. The multi-item math is the same analytic
check with an **`items²` factor** on the variance term and the total taken over all `N*items` item responses,
**with the same parity refinement** (`Σc_i² ≡ Σc_i = T (mod 2)`); `items=1` is the special case (the single-item
behavior is unchanged). **Derived from first principles + validated against the scrutiny reference** (mean 2.74,
SD 0.96, N 63, items 2 → consistent). The `items != 1 → supported=False` guard is gone (`supported` is now always
true); the dead frontend "unsupported" branch was removed (rule #5) and the help line updated. The simplified
analytic **errs toward leniency** (no per-item-range min-SS bound), so any miss is a *missed* inconsistency, never
a false "impossible" — the safe, non-accusatory direction. Backend math + tests + a 1-line frontend/help tidy;
**no API/surface change** (the GRIMMER verdict render path was headed-verified in inc 127 and is unchanged).
pytest **472** (+1 net: the "unsupported" test became two multi-item tests); `ruff` clean; build + assembly green.
Notes: `INCREMENT-129-NOTES.md`. **NEXT (user's pick):** the **findings subsystem** (the FACT-vs-CANDIDATE
backbone — the big architectural arc these METHODS features plug into); or other backlog.

Earlier — increment 128 (split 40_app.jsx — relieve the 600-line cap): a behavior-preserving
refactor clearing the rule-#1 risk flagged since inc 126/127 (`40_app.jsx` had crept to **590/600**). New early
chunk **`app/frontend/js/04_layout.jsx`** (107) holds, extracted verbatim: the module-scope layout helpers
(`_loadLayout`/`_saveLayout`/`_clampW`/`_beginDrag`, the `LEFT_*`/`RIGHT_*` width consts, the `Divider` component)
+ a new **`useUiPrefs()`** hook = the app's persisted UI state (theme; axis hide-uncertain + cutoff defaults;
auto-scan-watched; side-panel widths/open + their localStorage effects; THEORY/METHODS accordion-open; transient
Reading mode), lifted out of `App` unchanged. **`40_app.jsx` 590 → 514**: `App` now replaces ~50 lines of
pref/layout state with one `const { … } = useUiPrefs();` (only `settingsOpen`/`helpOpen` stay — modal toggles).
**Chunk-order-safe** (04 loads before its consumers; `30_viewer.jsx` already used `_loadLayout`/`_saveLayout` via
the IIFE function-hoist — now they're defined-before-use). No user-facing / API / surface change. pytest **471**
(unchanged); `ruff` clean; QA surface 91/484 0-uncovered. **Verified behavior-preserving headed**
(`.local/visual/drive_inc128_layout.py` — renders all 6 accordion sections; dark-mode toggles; left-panel collapse
works **and persists across reload**; Reading mode + Esc; 0 console/page errors). Notes: `INCREMENT-128-NOTES.md`.
**NEXT (user's pick):** multi-item GRIMMER; or the **findings subsystem** (the FACT-vs-CANDIDATE backbone — the big
architectural arc the methods plug into).

Earlier — increment 127 (GRIM + GRIMMER data-consistency calculator — the second GRIM/p-curve
"data-detective" METHODS feature): **GRIM** (Brown & Heathers, 2017) checks whether a reported **mean** of
integer-scale data is mathematically possible for the sample size; **GRIMMER** (Anaya 2016 / Allard 2018) extends
the check to the **SD**. Brainstorming chose an **assisted per-value calculator** (NOT an auto-scanner — pulling
mean+N+granularity from PDF prose is unreliable and would risk false, accusation-flavored flags): the user enters
a specific reported value to check, exactly how researchers use GRIM. **New `app/backend/methods/grim.py`** (pure
stdlib, no scipy/LLM/egress): `grim_test(mean, n, items=1)` (achievable means `K/(N*items)`; **nearest-possible**
values; a `no_power` flag when `N*items >= 10**decimals`) + `grimmer_test(mean, sd, n, items=1)` — **items=1**:
GRIM-check the mean, then test for an **integer sum-of-squares in the SD interval with the parity refinement
`SS ≡ T (mod 2)`** (the Allard correction over Anaya; **validated against the `scrutiny` reference** —
5.23/2.55/31→consistent, /35→inconsistent: for N=35 the only integer SS is even while the total is odd, so parity
correctly flips it). Rounding is **round-half-up via `Decimal`** (not banker's / float `==`). **`POST /methods/grim`**
(`routers/methods.py`) — sync, stateless, no DB/egress; `{mean, sd?, n, items}` → `{grim, grimmer?}`; bad inputs →
**422**. **Frontend `07_methods_grim.jsx`** — a **self-registering** METHODS section "Data consistency (GRIM)"
(order 30): a mean/SD/N/items form → GRIM (✓/✗ + nearest) + GRIMMER (✓/✗) + the no-power + integer-scale caveats +
a credit block with one-click **add to library**; tokens-only CSS; **no `40_app.jsx` change** (self-registered →
sidesteps the 590/600 cap there). **Assisted/per-value → inherently non-accusatory** (the user picks the value; it
never scans/ranks/labels a paper or author): **Principles gate #9 aligned** (declined an auto-scanner of
guessed-N flags; the A-A no-accusation veto held); **audit `.claude/security-audits/2026-06-25_grim.md` PASS**;
**rule #10** `route_37_methods_grim.md` + surface **91 API / 484 FE, 0 uncovered**; **credit-the-lineage** —
`THIRD-PARTY-NOTICES.md` (GRIM + GRIMMER + the `scrutiny` reference [Lukas Jung] + the Lakens catalog). **GRIMMER
is items=1 in v1** (multi-item deferred; GRIM supports items). pytest **471** (+12 `test_grim.py`: math + endpoint;
route-surface updated); `ruff` clean. **Verified headed, no egress** (`.local/visual/drive_inc127_grim.py` — 3.48/
N20 → impossible + nearest 3.45/3.50; 5.23/2.55/31 → GRIM+GRIMMER consistent; add-to-library; 0 console/page/genai).
Design/plan: `.claude/docs/specs/2026-06-25-grim-calculator-{design,plan}.md`; notes: `INCREMENT-127-NOTES.md`.
**NEXT (user's pick):** multi-item GRIMMER; the findings subsystem (FACT vs CANDIDATE); or the overdue
**`40_app.jsx` 590/600 split** (rule #1).

Earlier — increment 126 (p-curve — collection-level evidential-value check; the first GRIM/p-curve
"data-detective" METHODS feature): the user asked for GRIM/p-curve (surfaced via Daniël Lakens'
[automated-review catalog](https://lakens.github.io/automated_review_daily_build/)); we built **p-curve first**
(lower risk — it **reuses the proven statcheck p-value extractor**; GRIM's hard, low-coverage mean+N+granularity
extraction is the deliberate follow-up). Given a SET of significant focal NHST results across **user-selected**
papers, p-curve (Simonsohn, Nelson & Simmons, 2014) tests whether the p-value distribution is **right-skewed**
(→ evidential value) vs flat. **Collection-level only, never per-paper, never "p-hacked"** (the A-A no-accusation
veto); the interpretation is the user's. **New `app/backend/methods/pcurve.py`** (pure, no-DB/LLM/egress):
`compute_pcurve` (right-skew **Stouffer** `Z=ΣΦ⁻¹(p/.05)/√k` + a **binomial** check on share-of-p<.025 + the 5
observed bins) + `run_pcurve` (over per-paper `StatResult`s). **Async `POST/GET /methods/pcurve/run`**
(`routers/methods.py`, new `api.state.pcurve_jobs`) reuses `run_statcheck`+`get_chunks_for_paper` per **live**
selected paper; **ephemeral — no persistence, no migration**; selection de-duped+capped, empty→422. **Frontend:**
a **p-curve** library bulk-bar action (`10_pdf_layer.jsx`) + minimal `40_app.jsx` wiring → a new
**`29_pcurve.jsx`** modal: the collection-level/not-a-verdict framing, the coverage note, a hand-rolled **SVG
curve** (bars .01–.05 + a dashed 20% null), the right-skew + binomial statistics (descriptive), the
**included-tests** list (each opens its page at region precision), the coverage caveat, and a **credit** block
(Simonsohn et al. 2014 + a one-click **add to library** via the inc-93 `/library/import` with bundled CSL-JSON);
tokens-only CSS (rule #8). **Reuses statcheck's exact p-values** (`StatResult.computed_p`); since those are
rounded 4dp, results so significant p rounds to ≈0 are **conservatively dropped** (biases *against* over-claiming
— the safe direction; stated in the coverage note). **Principles gate #9 aligned** (declined a per-paper
"evidential value / p-hacking" badge/rank); **audit `.claude/security-audits/2026-06-25_pcurve.md` PASS**;
**rule #10** `route_36_methods_pcurve.md` + surface **90 API / 472 FE, 0 uncovered**; **credit-the-lineage** —
`THIRD-PARTY-NOTICES.md` gained a methods-lineage section (p-curve + `scrutiny` [Lukas Jung] + the Lakens catalog;
statcheck's credit backfilled). pytest **459** (+10 `test_pcurve.py`: math + endpoint; route-surface updated);
`ruff` clean. **Verified headed, no egress** (`.local/visual/drive_inc126_pcurve.py` — 12 papers → 76 significant
tests, **Z=−10.98, p<.0001** right-skewed; SVG curve + stats + included-tests + add-to-library; 0 console/page/genai).
**WATCH (rule #1): `40_app.jsx` is now 590/600 — a split is overdue; keep further wiring out of it.** Swept stray
`tests/*.tmp.*` + `app/frontend/js/*.tmp.*` atomic-write orphans (rule #5). Design/plan:
`.claude/plans/would-you-mind-reading-wise-peacock.md`; notes: `INCREMENT-126-NOTES.md`. **NEXT (user-queued):**
**GRIM** — the per-paper data-detective analogue (its own increment; harder extraction of mean+N+response
granularity → conservative v1 with heavy coverage caveats).

Earlier — increment 125 (strengthen the front-matter classifier — **live-validated** with real
Gemini): the user authorized spending tokens to eyeball the real synthesis output, and a **live** no-query
papers-scope run (`.local/visual/drive_inc124_live.py`, egress on) over the same papers that produced the broken
summary #7 showed inc-123's `is_front_matter_chunk` was **still too conservative** — paper **titles**, **author/
affiliation lines**, **journal running-headers**, and **funding lines** were leaking into the verified claims.
Strengthened `is_front_matter_chunk` (`app/backend/summarization/chunk_filtering.py`) to catch: name-attached
author superscripts (`Alves1`/`Uğurlar2`, `[A-Za-z][1-9](?![0-9])`, ≥2) + digit-prefix affiliations
(`1Department`, `(?:^|\s)\d[A-Z][a-z]`, ≥2); funding/acknowledgment lines (`grant`/`funding` + a grant-id
`[A-Z]{1,3}\s?\d{4,}`); and the **strong prose-safe title/header signal** — *no terminal sentence punctuation AND
≥60% of words capitalized* (body prose is mostly lowercase function words, so its caps-fraction is low even when
truncated → safe for content; titles/journal-headers are caught). The real leaked strings are now regression
tests (`tests/test_chunk_filtering.py`); the real body text that correctly stayed is asserted as CONTENT (guards
over-flagging). **Still fallback-only** (the inc-123 two-phase `_select_no_query` is unchanged — front matter is
deprioritized, never dropped), so a more-aggressive classifier is safe. **Re-ran live** → the verified claims are
now **all body text** (no front matter) and the **inc-124 Overview populated** with 3 real synthesis sentences,
each tracing to the verified claims it restates (e.g. *"For survival, continuously evaluating environmental risks
is crucial…"* → claims [2, 6]). The earlier **empty Overview** was confirmed **transient** — the 2nd (overview)
Gemini call hit repeated **503**s (model overloaded); the **fail-closed** path correctly omitted it and it
populated on retry over the cached summary. **Op note:** Gemini **key 1's prepay credits are depleted (429)** —
the live run fell back to `GOOGLE_API_KEY_2` (keys 1-4 live in `.env`). Backend-only — no `/summarize` contract
change, no migration, no egress, no new dependency; **Principles gate non-triggering** (retrieval quality, like
inc-66/123). pytest **449** (the FRONT_MATTER/CONTENT regression lists were extended; no new test functions);
`ruff` clean. Notes: `INCREMENT-125-NOTES.md`. **This live-validates the full synthesis-overview fix (inc 123 +
124 + 125): the original "synthesis gives no real summary, just sections" report is resolved end-to-end.**
**NEXT (user's pick):** the findings subsystem (FACT vs CANDIDATE) + adopting the THEORY/METHODS vocabulary; or
open backlog (discovery/gapfinder, GRIM/p-curve, file-watcher, emoji→SVG buttons, toasts, auth).

Earlier — increment 124 (synthesis evidence-traceable Overview — Part B of the synthesis-overview
fix; **completes** the "synthesis should provide a summary, too" request): after a synthesis is generated +
verified, a **second LLM pass narrativizes ONLY the verified claims** into a short **Overview** shown **above**
them, where **each Overview sentence links back to the verified claim(s) it restates** (per-sentence trace — click
a line → the claim(s) scroll into view + flash). Framed *"Overview — synthesized from the verified claims below"*
(traceable, NOT a free-floating "unverified" blob — the user's refinement): it restates only verified claims, its
trace refs are **inherited from verified claims, never LLM-invented** (`claim_indices` validated ⊆ the verified set
→ mapped to the verified sentences' **ordinals**; out-of-range dropped), and a line left with no valid refs is
dropped. New `app/backend/summarization/overview.py` (`OverviewGenerator` Protocol + `FakeOverviewGenerator` +
`OverviewSentence{text,claim_indices}`) + `integrations/gemini/overview.py` (`GeminiOverviewGenerator`, mirrors
`research_summary.py`; defensive `_parse_overview_response`; `OVERVIEW_PROMPT_VERSION`) + `EgressGatedOverviewGenerator`
(the inc-58 seam — library-derived text → **library egress gate**; egress-off → summary gen already raised, so the
pass is never reached → **no overview**, verified claims stand alone; any generator error caught → no overview,
never fails the synthesis). `summarize_scope(..., overview_generator=None)` + `_maybe_store_overview`; new
`summaries.overview_json` column (**migration 0015**, guarded/additive; head derived by tests, inc 99); `overview`
on the summary response (`OverviewItemResponse{text, claim_ordinals}`); `_overview_generator(api)` factory +
`create_app(overview_generator=…)` + `_summarization_app(..., overview_generator=…)` seams. Frontend
`20_synthesis.jsx`: `OverviewBlock` above the claims + `flashClaims` scrolling/flashing `#summary-claim-<ordinal>`;
tokens-only CSS (rule #8). **Principles gate #9 aligned** (traceable-to-evidence, restates only verified, secondary/
above the evidence, egress-gated, omitted when 0 verified — declined the authoritative-prose-eclipsing-evidence
path); **audit `.claude/security-audits/2026-06-25_synthesis-overview.md` PASS**; **rule #10** `route_55` extended;
**surface check 88 API / 462 FE, 0 uncovered**. pytest **449** (+9 `test_summary_overview.py`: column, Fake/egress/
parse, pipeline storage+map+out-of-range-drop+0-verified→none, e2e response); `ruff` clean; help corpus synthesis
section gained an Overview paragraph (`HELP-DOCS-SYNCED` → 124). Verified **headed, no egress**
(`.local/visual/drive_inc124_overview.py` — Overview above claims, label, trace-flash, 0 console/page/genai). The
**real Gemini prose-quality eyeball is deferred to the user** (needs egress + a key). Design (both parts):
`.claude/docs/specs/2026-06-25-synthesis-overview-design.md`; plan: `…-synthesis-overview-partB-plan.md`; notes:
`INCREMENT-124-NOTES.md`. **This completes the synthesis-overview fix (Part A inc 123 + Part B inc 124).**
**NEXT (user's pick):** the real-Gemini Overview eyeball (egress on); then the findings subsystem (FACT vs
CANDIDATE) + adopting the THEORY/METHODS vocabulary, or open backlog (discovery/gapfinder, GRIM/p-curve,
file-watcher, SVG buttons, toasts, auth).

Earlier — increment 123 (synthesis no-query scope prefers content over front matter — Part A of
the synthesis-overview fix): fixes **root cause #1** of the user's report that "synthesis doesn't provide a real
summary, just relevant sections." The no-query **papers** scope (the inc-62 select-papers→summarize path) was
ordering chunks by `chunks.c.id` (= import order → the *first* chunk of each paper is its **title page /
masthead**) and `_round_robin_by_paper(rows)[:top_k]` took the first chunk of each paper — so the LLM was fed
front matter and the "verified claims" came back as mastheads ("Original Manuscript", "© The Author(s) 2021 …
DOI:", journal volume lines, author lists — validation summary #7). Fix: a new conservative classifier
`app/backend/summarization/chunk_filtering.py::is_front_matter_chunk` (flags DOI/publisher/©-boilerplate; ≥2
author-affiliation superscripts; short + journal-volume run; short + no-terminal-punctuation + <10% function
words — **titles deliberately NOT caught**, errs toward "content") + a two-phase `_select_no_query` in
`pipeline.py` that round-robins **content** chunks across papers first, then front-matter chunks **as fallback**
(never dropped — a paper with only front matter still contributes), then slices `top_k`. **Query/cluster scopes
untouched** (query ranking already passes front matter). **Backend-only — no `/summarize` contract change, no new
endpoint, no migration, no egress, no new dependency** → no rule-#10 route change (surface check 0 uncovered, 88
API / 460 FE) and no audit-gate trigger; **Principles gate non-triggering** (a retrieval-quality change like
inc-66 trashed-paper exclusion; inspectability / provenance / egress posture all unchanged — every verified claim
still carries its quote/page/confidence). pytest **440** (+3: 2 classifier unit + the content-over-front-matter
selection assertion); `ruff` clean. Design (both parts): `.claude/docs/specs/2026-06-25-synthesis-overview-design.md`;
plan: `…-synthesis-frontmatter-fix-plan.md`; notes: `INCREMENT-123-NOTES.md`. **NEXT (user-queued):** **inc 124,
Part B — the evidence-traceable Overview**: a second LLM pass that narrativizes ONLY the verified claims into a
short prose Overview shown above them, where **each Overview sentence links back to the verified claim(s) it
restates** (per-sentence trace; citations inherited from verified claims, never LLM-invented; framed
"synthesized from the verified claims below", not "unverified"). Trips the audit + Principles gates; adds a
`summaries.overview_json` migration + the `EgressGatedOverviewGenerator` seam + `20_synthesis.jsx` rendering.

Earlier — increment 122 (statcheck relocated to a METHODS "Statistics check" section — the
first real METHODS module on the inc-121 pane registry): moved **both** statcheck surfaces — the **library-wide
batch** (was `StatcheckSettings` in ⚙ Settings) and the **per-paper check** (was `StatcheckRow` in the Details
pane) — into a new **METHODS accordion section** "Statistics check" (`app/frontend/js/06_methods_statcheck.jsx`,
self-registers `order: 20`, after DETAILS). The section has two parts under "Whole library" / "This paper"
eyebrows: `StatcheckLibrary` (the batch, verbatim) + `StatcheckPaper` (the per-paper check — since `paneCtx`
carries only `selectedPaper` (the id), it **self-fetches** `GET /papers/{id}` for title + chunk_count, then runs
`GET /papers/{id}/statcheck`). App wiring: `paneCtx` gains `onShowStatcheckFlagged` + `onStatcheckRan`, and the
inc-100 "⚠ N flagged" header-chip refresh moved from **settings-close-keyed** to **mount + `onStatcheckRan`**
(after a batch). statcheck was **removed from both Settings and Details**; the library chip + the
`?signal=statcheck-inconsistent` filter/banner are unchanged. This **relieves the pre-existing rule-#1 violation**
on `25_detail.jsx` (**625 → 579**). **Honesty posture preserved verbatim** → **Principles gate non-triggering**
(a relocation, not a new claim/signal): counts never a composite score (#7); "a prompt to look, not a verdict" +
non-accusatory (#2 + the A-A no-accusation boundary); inline-APA caveat (#6); per-test rows open the page at
`precision:"region"` (no fake exact rect). **Frontend-only — no backend/endpoint/migration/egress change**
(every statcheck endpoint already existed). **Rule #10:** `route_33` repointed `fe:` → `06_methods_statcheck.jsx`
+ steps via the METHODS accordion; `route_30` dropped the per-paper statcheck step + its coverage (now route_33's
alone); `route_32` clarified; **surface check 0 uncovered (88 API / 460 FE)**. Also swept stray
`app/frontend/js/*.jsx.tmp.*` atomic-write orphans (rule #5). pytest **437**; `ruff` clean; help corpus statcheck
section repointed (`HELP-DOCS-SYNCED` → 122). Spec/plan:
`.claude/docs/specs/2026-06-25-statcheck-methods-section-{design,plan}.md`; notes: `INCREMENT-122-NOTES.md`.
**NEXT (user-queued):** investigate **synthesis showing no text summary** (the papers-scope front-matter bug —
diagnosed + spec'd at `.claude/docs/specs/2026-06-25-synthesis-papers-scope-bug.md`); then the findings subsystem
(FACT vs CANDIDATE) + adopting the THEORY/METHODS vocabulary once more METHODS modules exist.

Earlier — increment 121 (THEORY/METHODS accordion side-panes on a module registry — the
"next major upgrade", UI-shell half): replaced the two fixed side-pane wrappers (left `Sidebar` = Axes+Tags;
right `RightPane` = the inc-57 Synthesis/Details drag-split) with **accordions** on an extensible **module
registry** — new chunk `05_panes.jsx` (`PANE_SECTIONS` + `registerPaneSection({id,label,paneId,order,render})` +
`<PaneAccordion paneId ctx openId onOpen/>`). **Left pane = THEORY accordion** (AXES · SYNTHESIS · TAGS, one open
at a time, AXES default); **right pane = METHODS accordion** (DETAILS, with a "select a paper" hint). Sections
**self-register from their own chunks** (15/20/10/—; load order 05<10<15<20<25 ⇒ the registry exists before the
register calls; `order` controls display position; adding a section is one call with **zero `PaneAccordion` edits**,
proven via a throwaway chunk). **Mount-but-hide** (inactive bodies `display:none`, never unmounted) keeps an
in-progress synthesis alive across a switch; the open section persists (`callosum.theoryOpen`/`methodsOpen`);
summarize-from-library opens the SYNTHESIS section. The inc-57 `RightPane`+`detailH`+`.divider-h` are **retired**;
the outer panel resize/collapse + reading mode + center tabs are untouched. **Soft labels** — section headers only,
no "THEORY"/"METHODS" umbrella text yet (the `paneId` is the internal architecture + the eventual rename, adopted
once the METHODS modules earn it). One intentional behavior change: **Tags always shows** (empty-state hint) instead
of vanishing when empty (the user reported never discovering Tags). **DESIGN.md §5** = the THEORY/METHODS placement
rubric (place by cognitive task) + the accordion/registry pattern + the AI-usage principle + a FACT-vs-CANDIDATE
forward-note. **esbuild DCE gotcha (documented):** the IIFE build dead-code-eliminates unreferenced top-level
functions, so a registered-but-unused component is stripped until used — the gate is raw-assembly inclusion +
a successful build (`test_frontend_assembly.py` checks the raw assembly), not a bundle grep; `node --check` doesn't
take `.html`. **Rule #1:** `25_detail.jsx` was already **625 (>600) pre-inc-121** → the DETAILS registration lives
in `05_panes.jsx` to avoid worsening it (back to exactly 625); a split is queued (the statcheck→METHODS move pulls
statcheck out of it). pytest **437** (frontend-only — unchanged); `ruff` clean; help corpus layout passages updated
(`HELP-DOCS-SYNCED` → 121); `route_00` recalibrated + surface map green (88/88). Frontend-only, no backend/migration;
Principles gate non-triggering. Verified headed on `:8097` (switch/persist/synthesis-survives/details-on-select,
0 console errors). Spec/plan: `.claude/docs/specs/2026-06-25-theory-methods-accordion-{design,plan}.md`; notes:
`INCREMENT-121-NOTES.md`. **NEXT (user-queued):** (1) **statcheck Settings → a METHODS accordion section** (the
first real METHODS module — relieves the 25_detail.jsx size debt); (2) **investigate synthesis showing no text
summary** (only retrieved sections — leading hypothesis: egress off → no generation; could be a render bug); then
the findings subsystem (FACT vs CANDIDATE) + adopting the THEORY/METHODS vocabulary once METHODS modules exist.

Earlier — increment 120 (QA mechanism — surface-coverage gate + Codex-exec supervisor +
watched inbox): installed the QA bundle delivered as `qa_routes.zip` (authored out-of-band) per its
`QA-BUILD-GUIDE.md`, and had **Codex author the full route suite** until the gate went green. New **rule #10**
(`.claude/QA-POLICY.md`) — read before changing any **end-user surface** — joins DESIGN.md (#8) + PRINCIPLES.md
(#9). Three parts: **`tools/qa/build_surface_map.py`** (pure-stdlib static extractor — AST of `@router.<m>("path")`
+ JSX element/handler scan — and a `check` that diffs the surfaces declared in `.claude/qa-routes/*.md` against the
real ones; **API hard-gate, FE checklist**), **`tools/qa/supervisor.py`** (dispatches each route to a headless
`codex exec`, waits for its deposit in `.claude/qa-inbox/<run-id>/`, writes a Critical/High-first `run-summary.md`;
Tier-0 gates the rest), and **`tools/qa/_qa_serve.py`** (the fixture contract — a freshly migrated + **seeded
throwaway** SQLite via `tests.api_helpers._seed_library` on a free port, **egress unset by default**, never the
real library). Routes assert the **honesty invariants** (egress gate, coordinate honesty, signal-not-verdict), not
just clicks. Coverage is a **computed property** (re-extracted each run): current tree **88 API / 460 FE**, and
after Codex authored the 13 missing routes (the 2 seeds + 13 = **15 routes**, tiered 00 / 15–40 T1 / 55–58 T2
hermetic) → **88/88 API + 460/460 FE → `check` exits 0**. CLAUDE.md gained rule #10 + kickoff step #10 (triage the
inbox); `.gitignore` covers `qa-inbox/` + `surface-map.json` + the zip; CI has a report-only `check` step. Repo-fit:
added `tools/qa/__init__.py`, ran `ruff --fix`/`format` on the bundle scripts. **Two Codex roles:** the *author*
(this increment — writes the spec files, never opens the app) vs. the *route-runner* the supervisor dispatches
(Phase 3 — an **adversarial end user** driving the seeded app in Playwright, instrumented to also verify the
invariants). pytest **436** (additive — no app/test code touched); ruff clean. **NOT run (the user's to trigger —
spends Codex credits):** **Phase 3**, `python tools/qa/supervisor.py --tier 0` (the real browser-driven QA pass),
then deeper tiers; the first deposit is triaged at the next kickoff. **NEXT:** kick off a Tier-0 QA run to validate
the pipeline end-to-end; otherwise the open backlog (discovery/gapfinder, GRIM/p-curve, file-watcher, SVG buttons,
toasts, auth) is the user's pick.

Earlier — increment 119 (My Publications overhaul, SP3 — citing articles & citation counts):
the **final** sub-project (TDL #14); **completes the overhaul = SP1 (inc 117) + SP2 (inc 118) + SP3 (inc 119) = TDL #1 +
#3–18**. Each own-pub card shows its **OpenAlex cited-by count** (shown verbatim + attributed, never a Callosum
composite or ranking verdict) + a **"Most cited"** sort; clicking the count opens a **citing-articles modal** — the
papers OpenAlex records as citing it (**discovery candidates**, coverage stated "not exhaustive") — with per-row
**Import** + a confirm-gated **Import all**, which add them **metadata-only + deduped** to the **general** library (NOT
My Pubs — they aren't your works; the PDF stays the separate OA-acquire lane → no paywall circumvention). **Backend
(additive, no migration):** `AuthorWork.openalex_work_id` (was fetched but discarded), `paper_citations` on the
dashboard, `OpenAlexAuthorClient.fetch_citing_works` (`filter=cites:<id>`, validated `^W\d+$`, **cached** under
`citing:<id>`, **capped 100**, fail-closed) + `GET /my-publications/citing/{work_id}` (in_library via dedup) +
`import_citing_work` + `POST /my-publications/citing/import`; **`resolve_my_publications` now `fetch_author_works(refresh=True)`**
so the "Refresh from OpenAlex" button repopulates fresh counts + the work ids the chips need (old caches lack them).
Egress = **public OpenAlex/Crossref metadata, bounded/cached/on-demand** — NOT the Gemini library-text gate.
**Principles gate run** (spec §2 — aligned: count=fact, citing=candidates, human-selected import, OA-only PDFs);
**audit `2026-06-24_mypubs-citing.md` PASS**. Frontend: an optional `PaperCard` cited-by chip (library omits it) +
`MyPubsPublications` Most-cited sort + new chunk `34_mypubs_citing.jsx` (the modal). pytest **436** (+5: work-id
capture, `paper_citations`, citing fetch/cache/endpoint/in_library, import-citing dedup/not-in-mypubs, route-surface);
`ruff format`/`check` clean; verified **headed** via Playwright on `:8097` (71 chips, Most-cited reorder, a real
`cites:` fetch → 9 candidates, import → in-library). **Watch:** `clustering/my_publications.py` is **587/600** — split
before the next backend addition lands there (extract the citing/import or dashboard-builder helpers). **NEXT:** the
My-Publications overhaul is done; open backlog — the discovery/gapfinder track, GRIM/p-curve, a live OS file-watcher,
emoji→SVG buttons, toasts, auth — is the user's pick.

Earlier — increment 118 (My Publications overhaul, SP2 — domain organization):
the second sub-project (TDL #9/#15/#16/#17/#18). Organizes the own-corpus by **research domain**. A **Group by domain**
toggle regroups the publications under per-domain headers (the dashboard list) and collapsible subheadings (the pinned
**sidebar** My-Pubs card), with an **"Other"** group for papers in no domain and **starred-first** ordering within each.
Domains can be **renamed** inline (the box pre-suggests the closest existing **axis** name by domain-term overlap), and
custom names **persist across Re-decompose** by best paper-overlap (Jaccard ≥ 0.5 — a `custom` flag in the existing
`research_domains` JSON + `_reapply_custom_labels`, so **no migration**). **#18:** selecting a domain locks the Overview
flip-chart to **Publications (domain-filtered)** and disables the **Citations** pill until cleared. **Backend additive
only:** `Domain.paper_ids` + `DashboardResponse.starred_ids` on the dashboard, a per-paper **`ClusterPaperResponse.domain`**
populated only for the my-pubs `/axes/{id}/clusters` (mirrors the inc-84 `starred` gating — so the sidebar groups with
**no new route and no second fetch**), and one new endpoint **`POST /my-publications/domains/rename`** (a local
profile-JSON write; audit `2026-06-24_mypubs-domain-rename.md` PASS). **No migration, no egress, no Principles trigger**
(organizational, not a new claim/signal). A shared `PaperCard` (from SP1) is reused; `MyPubsPublications`
(`33_mypubs_pubs.jsx`) does the dashboard grouping, `15_axes.jsx` the sidebar grouping. pytest **432** (+4:
`paper_ids`/`starred_ids`/`domain` shape, rename endpoint, `_reapply_custom_labels` overlap); `ruff format`/`check`
clean; verified **headed** via Playwright against the live `:8097` data. Spec/plan:
`.claude/docs/specs/2026-06-24-mypubs-sp2-{domains-design,plan}.md`; notes: `INCREMENT-118-NOTES.md`. **NEXT:** **SP3 —
citing articles & citation counts (#14)** — citation counts on the publication cards → click → a modal of the papers
that *cite* yours → import them; needs a **new OpenAlex "cited-by" fetch** → trips the security-audit gate AND the
Principles gate (a new discovery signal), so it's built last on its own. (The domains section sits below the
publications list transitionally; a later layout pass can move it if wanted.)

Earlier — increment 117 (My Publications overhaul, SP1 — dashboard restructure & publication cards):
the first sub-project of the My-Pubs overhaul (TDL line 1 + #1/#3–8/#10–13; decomposed into SP1/SP2/SP3). The dashboard
tab was restructured into author-priority order — **Overview** (collapsible: 2×2 metrics + one **Publications⇄Citations**
flip-chart, last 10 years `'NN`, replacing the two side-by-side charts) → **Research summary** (moved to r2; the
⭐-only toggle hides when no starred pubs, #8) → **Publications** (the user's in-library own-papers as library-style
cards via `GET /papers?axis_id=<my-pubs>` — search/sort + a checkbox bulk bar [summarize/export/bibliography/delete] +
copy + open; the **Decompose** button relocated into its controls row, #10) → Research domains → **OpenAlex footer card**
(provenance "as of …", the indexed/library/not-imported gap, 2-yr mean citedness + affiliation + an OpenAlex profile
link, a second **Refresh** [#11], and a **Review/Dismissed →** button opening the missing-works **modal**, #12). A shared
**`PaperCard`** was extracted from the 40-prop `PaperList` monolith (behavior-preserving for the library) so the list
reuses the library aesthetic + parity; new chunks `33_mypubs_pubs.jsx` (the list) + `32_mypubs_missing.jsx` (the modal).
**Backend additive only:** `ResolvedAuthor.two_year_mean_citedness` + `.affiliation` parsed from the already-cached
OpenAlex author object → an `openalex_extra` block + `starred_count` on the dashboard response — **no new endpoint,
migration, or egress** (OpenAlex figures stay verbatim + attributed, the inc-81 posture → no audit/Principles gate).
Two bugs caught + fixed: `/papers` 422 on `limit>200` (→ 200 + an honest truncation note); the "Review →" button was
unreachable when every missing work was dismissed (→ now "Dismissed (N) →"). pytest **428** (+`openalex_extra`/
`starred_count` assertions in `test_my_publications.py`); `ruff format`/`check` clean; verified **headed** via Playwright
against the live `:8099` data (`.local/visual/drive_mypubs.py` + `drive_t5{,b}.py`; the modal restore→re-dismiss
round-trip confirmed the `onChanged` refetch and left state clean). Spec/plan:
`.claude/docs/specs/2026-06-24-mypubs-sp1-{restructure-design,plan}.md`; notes: `INCREMENT-117-NOTES.md`.
**NEXT:** **SP2 — domain organization** (#9 group-by-domain toggle, #15 rename domains vs axes, #16 domains →
AXES-card subheadings, #17 starred-first sorting, #18 chart-filter-on-domain-select); then **SP3 — citing articles &
citation counts** (#14, a new OpenAlex cited-by fetch → trips the audit + Principles gates). The domains section sits
below the publications list transitionally; SP2 reworks it.

Increments 109–116 (frontend/UX TDL items: inc-109 brand-asset source move, inc-110 PDF page-view options, inc-111
editable Translators, inc-112 multi-paper focus query, inc-113/114/115 button canonicalization, inc-116 synthesis
✕-close + AXES ambient outlines) are journaled in `RECOVERY-LOG.md` rather than in this footer.

Earlier — increment 108 (LibreOffice (UNO) citation adapter — the first word-processor adapter):
the first piece that places citations **inside a word processor**, riding the inc-107 `POST /citations/render-document`
contract. A drop-in LibreOffice Writer **Python UNO macro** in a new top-level **`adapters/`** tree (client code
that ships into the user's LibreOffice — NOT the FastAPI app, NOT a server-side `integrations/` client). A **thin
field-placer**: place/track a live field, read the full ordered set, write back what the backend rendered — it
**never formats** (citeproc does). Live fields = **ReferenceMarks** whose name carries the cited work's CSL-JSON
(base64), the Zotero `CSL_CITATION` **pattern** (credited in `THIRD-PARTY-NOTICES.md`, not code). Four macros:
Insert (paper id → `/papers/export` csl-json → ReferenceMark), Refresh (full-document-order scan via
`XTextRangeCompare` → `render-document` → write back in-text + bibliography), SetStyle (validated vs
`/citations/styles`, persisted as doc user-properties), Flatten (live→static). **No server change** — no new
endpoint/migration/route/egress (127.0.0.1 only); stdlib `urllib` (LO's bundled Python has no pip). **Verified by a
headless UNO round-trip** (`.local/lo_roundtrip/run_roundtrip.py` drives a real LibreOffice → IEEE `[1]/[2]`, APA
`(Vaswani & Shazeer, 2017)` author-date, flatten preserves text — **SELFTEST OK**) + **5 pytest pure-logic tests**.
**Four UNO traps found+fixed** (carry forward to the next adapters): `loadComponentFromURL` needs `Hidden=True`;
clearing the bib invalidates its bookmark anchor (reuse the cursor); `setString` on a ReferenceMark anchor
**destroys the mark** (recreate around the new text); holding `ReferenceMarks` items across a mutation hangs on a
stale handle (capture names → re-fetch) + removing a mark deletes its text (flatten re-inserts it). pytest **424**
(+5 `test_libreoffice_adapter.py`); `ruff` clean; audit `.claude/security-audits/2026-06-21_libreoffice-adapter.md`
**PASS**; help corpus unchanged (no in-app surface). **NEXT (the track):** **Word (Office.js)** — one cross-platform
add-in over the same `render-document` engine (needs the CORS/origin change, content-controls/ADDIN fields, Win+Mac
parity); then **Google Docs** (named ranges, the fenced cloud opt-in, built last). Deferred for LibreOffice: `.oxt`
packaging + toolbar, a library-search picker, grouped cites/locators, note-style footnotes, Track-Changes handling.

Earlier — increment 107 (position-aware document-render layer — Phase 2 of word-processor
integration): the shared contract every word-processor adapter (LibreOffice → Word → Google Docs) will call.
The inc-106 engine renders each cite **in isolation** (`makeCitationCluster`) — right for a *selection*, **wrong
for a live document** (numeric must renumber `[1][2][3]` by order; author-date must disambiguate `2020a`/`2020b`
across the doc). Inc 107 adds the position-aware layer: the runner gains a **`mode:"document"`** branch using
citeproc's **`rebuildProcessorState`** (the inc-106 per-item path is the unchanged default); `render.py` refactors
the subprocess into **`_run(request)`** + adds **`render_document(citations,*,style,locale)`** (self-contained —
renders from the passed CSL-JSON, **no library lookup / no DB**; caps clusters/items/total; output `_safe_html`-
sanitized); **`POST /citations/render-document`** `{citations:[{citationID?,items:[CSL-JSON]}],style,locale}` is
*the adapter contract* (scan doc for citation fields → POST in document order → get back position-aware in-text per
field + the bibliography to write back; stateless per request; 503/422/502, never 500). **Backend-only — no
frontend change (no rebuild), no migration, no egress, no new dependency.** pytest **419** (+3 `test_citations.py`
document-render: IEEE `[1][2][3]`+renumber-on-reorder, APA `2020a`/`2020b` disambiguation, unknown-style 422;
route-surface +1); `ruff` clean; audit `.claude/security-audits/2026-06-21_citation-render-document.md` **PASS**;
help corpus unchanged (no user-facing surface). **NEXT (the track):** the **LibreOffice (UNO) adapter** — the
live-field loop (insert → render → update → flatten) riding this endpoint; then Word (Office.js, needs the
CORS/origin change); then Google Docs (opt-in). Deferred: note-style footnote management, locators/prefixes, a
shared subprocess timeout, Vancouver + more styles.

Earlier — increment 106 (citation & bibliography engine — Phase 1 of word-processor
integration): the foundation of the word-processor track + the close of the "no formatted citation styles" gap.
**citeproc-js** runs as a **Node sidecar** (invoked exactly like esbuild — `citations/render.py::_run_engine`
mirrors `frontend.py::_transpile_jsx`, request JSON on stdin / result on stdout, fail-closed → 503) over **bundled
CSL styles + locales** (`app/backend/citations/csl/`, committed verbatim, CC-BY-SA) to render `papers.csl_json`
into formatted in-text citations + bibliographies (APA/MLA/Chicago/IEEE/Nature/Harvard). One central render = the
**word-processor adapters will only place fields, never format** (LibreOffice → Word → Google Docs ride this
engine). citeproc HTML is **sanitized server-side** (`_safe_html`) before any in-app render. Endpoints
`GET /citations/styles` + `POST /citations/render`; in-app surface = Details **"Cite as …"** (style dropdown + live
preview + copy) + a bulk **"bibliography…"** `.html` download. `citeproc` pinned (`package.json`); **no egress**
(bundled styles). Credit in `THIRD-PARTY-NOTICES.md` (credit-the-lineage). pytest **416** (+5 `test_citations.py`;
route-surface +2); `ruff` clean; opt-in Playwright smoke (0 console errors); audit
`.claude/security-audits/2026-06-21_citation-engine.md` **PASS**; help corpus gained a formatted-citations note
(`HELP-DOCS-SYNCED` → 106). **NEXT (the track):** the **LibreOffice (UNO) adapter** — the live-field loop (insert →
render → update → flatten) on this engine; then Word (Office.js, needs the CORS/origin change); then Google Docs
(opt-in). Deferred: fetch-on-demand styles, Vancouver + more styles, rich-clipboard copy, CRediT builder,
highlight-to-suggest/evaluate.

Earlier — increment 105 (two chores: default axis cutoff in Settings + a tag source filter):
the "2 chores" half of a fresh patter (carrot = the **literature gap-finder** (backward gap), next, in its own
plan-mode increment). Both **frontend-only over existing data**. (1) A **`callosum.axisCutoffDefault`** localStorage
pref — a "Default axis cutoff" slider in **Settings → Axes** (clamped [0.2,0.6], default 0.35; mirrors the inc-77
hide-uncertain pattern) — threads App→Sidebar→AxesPanel→`AxisItem`, whose re-score cutoff flipper falls back to it
when `axis.scoring_gain == null` (a stored per-axis gain still wins; AxesPanel keys cards on the default so a change
re-inits unscored cards). Sets what the flipper *proposes*; no backend change. (2) The sidebar `TagsPanel` gained an
**All / Yours / Keywords** segmented control filtering by the inc-100 tag `source` (`tagIsImported`), shown only
when both kinds exist — purely client-side over the already-fetched `/tags`. `styles.css` `.settings-cutoff` +
`.tags-srcfilter` (tokens only, rule #8). pytest **411** unchanged; `ruff` clean; opt-in Playwright smoke (2 tests)
passed (0 console errors); `callosum-app.html` rebuilt; help corpus tags section noted the source filter
(`HELP-DOCS-SYNCED` → 105). **NEXT:** the carrot — **literature gap-finder (backward gap)**: surface papers cited
by ≥k of your library's papers but missing from it ("cited by N of your papers on [axis]"), axis-ranked,
add-or-dismiss; uses the OpenAlex adapter (`referenced_works`). Gets **plan-mode + the Principles gate + a security
audit** (new external fetch / discovery signal).

Earlier — increment 104 (panel min-widths + Spotify pull-to-collapse + sidebar-button
reposition): three small layout tweaks (frontend-only). The **left (AXES)** panel now has a **300px** min drag
width and the **right (Synthesis/Details)** panel **415px**; dragging a resizer ~80px past its min auto-collapses
that panel (no chevron needed) — `40_app.jsx` constants `LEFT_MIN/RIGHT_MIN` + `*_COLLAPSE_AT`, each divider's
drag collapses when the unclamped `proposed` width crosses the threshold (else clamps to `[MIN,MAX]`); the
persisted width init clamps up to the min. The panel sticks at its min then snaps shut (works via `_beginDrag`'s
document-level listeners); re-expand = the collapse chevron. The two sidebar-header buttons regrouped:
`.icon-help` → `top:19px;right:33px` (down 7 / left 4, then both nudged left 15px), `.icon-gear` →
`top:19px;right:60px` (same Y, 27px left of help — a right-aligned pair, top-left vacated), both with an always-on
`currentColor` outline (hover unchanged).
pytest **411** unchanged; `ruff` clean; opt-in Playwright smoke
(incl. the reading-mode panel test) passed (0 console errors); `callosum-app.html` rebuilt. Visual QA delegated.
**NEXT:** the user's call — more layout polish, another patter, or deferred backlog (a live OS file-watcher,
GRIM/p-curve, the discovery/gapfinder track, My Pubs Layer 3, tag-provenance grouping/protection).

Earlier — increment 103 (per-card "copy BibTeX" clipboard button): a small library-card
affordance the user requested. inc-98's `.paper { user-select:none }` (which fixed the double-click word-select)
removed card text-copy, so each card now carries a small **clipboard SVG button** just left of its checkbox that
copies the paper's **BibTeX** in one click (`PaperCopyButton` in `10_pdf_layer.jsx`, reusing the inc-70
`POST /papers/export {format:"bibtex"}` → `navigator.clipboard`; `stopPropagation` so it never selects/opens the
card; icon → green ✓ for ~1.5s). `.paper-copy` is absolutely positioned at `top:10px;right:36px` (the checkbox
stays at `right:14px`, untouched); `.paper-title` gained `padding-right:46px` to clear both controls; two inline
Feather SVGs. Shown only in `selecting` mode (the normal library view), matching "alongside the checkbox".
**Frontend-only — no backend/endpoint/migration/egress** (reuses a validated, tested local read-only endpoint).
pytest **411** unchanged; `ruff` clean; the opt-in Playwright smoke passed (0 console errors, confirming the SVG
JSX compiled under the inc-102 esbuild precompile); help corpus's "Exporting citations" section gained a line.
**NEXT:** the user's call — another patter, or deferred backlog (a live OS file-watcher, GRIM/p-curve, the
discovery/gapfinder track, My Pubs Layer 3, tag-provenance grouping/protection).

Earlier — increment 102 (precompile the JSX with esbuild; drop in-browser Babel): a console-
hygiene change the user requested. The served page transpiled `<script type="text/babel">` JSX **in the browser**
via `babel-standalone` (cdnjs) — emitting a "precompile for production" warning + a `babel.min.js.map` 404
source-map error, plus a ~500KB download. Now `frontend.py` **esbuild-precompiles** the concatenated chunks
(`assemble_jsx` → `_transpile_jsx`: `node node_modules/esbuild/bin/esbuild --loader=jsx --jsx=transform
--jsx-factory=React.createElement --jsx-fragment=React.Fragment --format=iife --target=esnext`, JSX via stdin, no
shell) into one plain `<script>`; the Babel CDN line is removed from `index.html`. esbuild is a **build-time** dep
(`package.json` pins 0.28.1; `npm install`; `node_modules/` gitignored); the **server stays Python-only** (serves
the prebuilt `callosum-app.html`; the live-assembly fallback degrades gracefully if esbuild is absent — `app.py`
try/except, no 500). The IIFE preserves the chunks' shared scope (identical runtime). `test_frontend_assembly.py`
updated (precompiled markers; `test_every_js_chunk_is_included` checks the raw `assemble_jsx()` so completeness
needs no toolchain); CI gained `setup-node` + `npm ci`. Verified: `node --check` on the output (153
`React.createElement`, 0 leftover JSX) **and the opt-in Playwright smoke passed with 0 console errors**. pytest
**411** unchanged; `ruff` clean; audit `.claude/security-audits/2026-06-21_precompile-esbuild.md` **PASS**. (The
third console line — `XrayWrapper … content-script.js` — is an external **browser extension**, not callosum;
nothing to fix in the repo.) **NEXT:** the user's call — another patter, or deferred backlog (a live OS
file-watcher, GRIM/p-curve, the discovery/gapfinder track, My Pubs Layer 3, the tag-provenance
grouping/protection).

Earlier — fix (post-inc-101): double-click on a library card no longer word-selects the title — `.paper` got
`user-select: none` (inc-98 `onDoubleClick` always opens; the browser's default word-select on double-click was
the residual highlight). Card text isn't drag-selectable now but stays copyable in the Details pane. Frontend-only;
pytest 411 unchanged.

Earlier — increment 101 (Reading mode — one-click distraction-free reader): the carrot of the
inc 100–101 patter. A **⛶ Read** toggle (right of the center tab bar) hides **both** side panels and their
dividers to maximize the open PDF; **⤢ Exit** or **Esc** returns. `readingMode` state in `40_app.jsx`
(`toggleReading` snapshots `leftOpen`/`rightOpen` → collapses both → restores the snapshot on exit, so an
asymmetric layout returns intact); `cols` zeroes the divider tracks + `.app.reading .divider{display:none}` so
only the center pane shows; Esc is guarded to defer to an open modal. **Transient** (a reload returns to normal —
never strands the user with hidden chrome). Frontend-only (`40_app.jsx`, `30_viewer.jsx` `LibraryFrame`,
`styles.css` `.frame-reading` — tokens only, rule #8); no backend/migration/egress. pytest **411** unchanged;
`ruff` clean; `callosum-app.html` rebuilt. Visual QA delegated (no Playwright MCP this session). **NEXT:** the
user's call — another patter, or deferred backlog (a live OS file-watcher, GRIM/p-curve, the discovery/gapfinder
track, My Pubs Layer 3, the remaining tag-provenance grouping/protection).

Earlier — increment 100 (statcheck "flagged" header chip + tag-source aesthetic
differentiation): a "2 chores" half-patter (carrot = Reading mode, inc 101). (1) A **⚠ N flagged**
chip in the Library header — when the inc-97 batch statcheck run flagged any papers — jumps to the flagged-papers
filter (a more prominent door to a Settings-only feature). `signals_repo.count_statcheck_flagged` + `GET
/methods/statcheck/summary` (cache-only count; the inc-97 batch stays the only persister) → a `statcheckFlagged`
state in `40_app.jsx` → the chip in `10_pdf_layer.jsx`. (2) Tags from different sources (imported
Crossref/OpenAlex/Zotero keywords vs the ones you typed) are differentiated **aesthetically** — a muted style +
a source tooltip, no on-screen label (user request, to declutter Details). The inc-73 `import_source` is exposed
on the tag responses (`PaperTagRef`/`TagRef`/`TagSummary.source`) and read by `tagIsImported`/`tagSourceLabel`
(`00_lib.jsx`) → `tag-chip-imported`/`tags-panel-item-imported` in `25_detail.jsx` + `10_pdf_layer.jsx`. Both are
read-only projections of persisted facts — **no migration, no egress, no LLM**; the `source` field is additive
(default null). Principles gate: chip = a path to a *filter* (no rank/verdict; no-accusation boundary holds); tag
styling = provenance made visible (inspectability). pytest **411** (+1 `test_tag_source_exposed_on_responses`;
statcheck-summary assertion folded into an existing test); `ruff` clean; help corpus tags + statcheck sections
updated (`HELP-DOCS-SYNCED` → 100). **NEXT:** the carrot — **Reading mode** (a one-click distraction-free reader:
collapse both side panels, maximize the open PDF, Esc to return; frontend-only, builds on the inc-42 collapsible
panels); or another patter / deferred backlog (a live OS file-watcher, GRIM/p-curve, the discovery/gapfinder
track, My Pubs Layer 3).

Earlier — increment 99 (tests derive the Alembic head, not a hardcoded revision): a small
dev-infra cleanup killing a recurring failure class — a migration bumps the head, but `test_health.py` +
`test_startup_migration.py` hardcoded the old revision string, so a missed edit only went red on the *full* suite
(it bit inc 91 + inc 98). New `tests/api_helpers.py::alembic_head()` (`ScriptDirectory…get_current_head()`); the
two files now use `HEAD = alembic_head()` instead of `"00NN_…"` literals — a new migration needs **zero** test
edits for the head, and `test_health`'s `db_revision == HEAD` (vs a migrated DB) is the wiring proof. Tests-only;
no app code/migration/behavior change. pytest **410** unchanged; `ruff` clean. **NEXT:** the user's call —
another patter, or deferred backlog (a live OS file-watcher, GRIM/p-curve, the discovery/gapfinder track, My Pubs
Layer 3, reading mode / page-view options).

Earlier — increment 98 (double-click-to-open fix + watched library folders): a user-reported
bug + a requested feature. **(A) Double-click bug:** the inc-82 `getSelection().isCollapsed` guard suppressed the
open when the **title** was double-clicked (browser auto-selects the word) — so `onDoubleClick` now **always
opens** (`10_pdf_layer.jsx`); titles stay copyable in Details. (Independent of the scan — the wiring was intact;
coincidental timing.) **(B) Watched folders (Zotero/Mendeley-style, minus a live OS watcher):** scanning a folder
now **registers** it (`watched_folders` table, migration **0014**, `persistence/watched_repo.py`), and watched
folders are **re-scanned automatically on launch** (default-on Settings toggle) + via "Re-scan all" — new PDFs
appear without re-adding. `GET/DELETE /library/watched` (un-watch keeps papers) + `POST/GET
/library/watched/rescan` (async, reuses the inc-87 scan body via a shared `_process_scan_result`); the "+ Add ▾"
menu item → **"Watched folders…"** with a managed list. Safe to re-scan the library folder (content-dedup by
`file_sha256` → no dupes), answering the user's "no need to re-add" concern. Server-side folder read is now
persisted + auto-read → the deployment-gate note extended. pytest **410** (+2 `test_watched_folders.py`;
migration head → 0014); `ruff` clean; audit `.claude/security-audits/2026-06-21_watched-folders.md` **PASS**; help
corpus's scanning section reworked → watched folders (`HELP-DOCS-SYNCED` → 98). **NEXT:** the user's call —
another patter, or deferred backlog (a live OS file-watcher, changed-file re-ingest, GRIM/p-curve, the
discovery/gapfinder track, My Pubs Layer 3, reading mode / page-view options).

Earlier — increment 97 (statcheck as a library-wide lens): the patter's **carrot** (chores =
inc 96). Turns the inc-95 per-paper statcheck into **library triage**: a batch "Check all papers" (⚙ Settings →
Statistics check) persists a per-paper summary into the pre-built `open_science_signals` table (new
`persistence/signals_repo.py`, OR-REPLACE upsert — no migration), and a library **filter**
(`GET /papers?signal=statcheck-inconsistent`, allowlisted → bound subquery) shows only papers with a reporting
inconsistency, reached via a **"Show flagged papers"** link + a non-accusatory banner. Async
`POST/GET /methods/statcheck/run` (`routers/methods.py`, `statcheck_jobs`); the batch is the **only** persister
(the inc-95 per-paper GET stays live/read-only). **Principles gate run:** the aggregate is a **FILTER, never a
rank/score (#7) or a "bad papers" verdict (#2 + the no-accusation veto)** — the declined easy path was a
reproducibility-score leaderboard. Reuses the inc-95 engine unchanged; **no migration, no egress, no LLM, no new
dependency.** pytest **408** (+3 `test_statcheck.py`); `ruff` clean; audit
`.claude/security-audits/2026-06-21_statcheck-library.md` **PASS**; help corpus's statcheck section gained the
library-wide check (`HELP-DOCS-SYNCED` → 97). **This completes the inc 96–97 patter.** **NEXT:** the user's call
— another patter, or deferred backlog (a permanent header entry for the filter, GRIM/p-curve, a unified findings
facet, the discovery/gapfinder track, My Pubs Layer 3, reading mode / page-view options).

Earlier — increment 96 (sidebar Tags browser + Details "More → + add field"): the two
**chores** of a fresh patter (carrot = statcheck-as-a-library-lens, next, in its own plan-mode increment). Both
**frontend-only**, reusing already-tested endpoints. (1) A **`TagsPanel`** in the left sidebar (below Axes,
`10_pdf_layer.jsx`) lists every tag + paper count → click to filter the library (reuses `GET /tags` + the inc-71
`filterToTag`); a `tagRefresh` nonce + an `onTagsChanged` callback (App→RightPane→DetailContent→TagsRow) keep it
live with per-paper tag edits. (2) The Details **"More"** section always renders now + has an **`AddFieldRow`** to
add an arbitrary CSL field by hand (reuses the inc-49 validated `csl` patch; letter-led `[A-Za-z0-9_-]` keys,
reserved/core 422). **No Python changed**; rebuilt `callosum-app.html`. pytest **405** unchanged; `ruff` clean;
help corpus updated (tags + Details sections; `HELP-DOCS-SYNCED` → 96). **NEXT:** the carrot — **statcheck as a
library-wide lens** (persist results to `open_science_signals` + a batch run + a "reporting inconsistencies"
library filter; plan-mode + Principles gate — keep it a *filter with counts*, never a rank/"bad papers" list).

Earlier — increment 95 (statcheck — an inspectable, deterministic statistics-reporting signal):
the patter's **carrot** (chores = inc 94) and Track A's v1. A **"Check statistics"** button in the Details
**Statistical reporting** section recomputes reported APA NHST p-values (t/F/r/χ²/z) from the paper's extracted
text and flags reported-vs-computed disagreements — **deterministic, local, no-LLM.** `methods/statcheck.py` (new
`methods/` package): anchored regexes → `recompute_p` via `scipy.stats` → classify **consistent / inconsistent /
decision-error** with **rounding + one-tailed tolerance** (so correct reporting isn't false-flagged); per-chunk so
each result carries its page. `GET /papers/{id}/statcheck` (`routers/methods.py`, sync read-only; no chunks →
`checked:0`). UI shows per-test rows (verbatim match + recomputed p + green/amber `.cite-status` pill) + **counts,
never a composite score** + a **non-accusatory** caveat (amber not red; inline-APA-only ⟹ absence ≠ clean), each
row routing to its page. **Principles gate (rule #9) run:** PRINCIPLES Example 3 / extends value A6; honors the
veto-level **no-accusation** boundary (#2/#7 — signal-not-verdict, no opaque score). `scipy` made explicit
(already transitive via scikit-learn; needed for the t/F/χ² CDFs). **No persistence v1** (the `open_science_signals`
table + a library-wide facet defer to the findings subsystem); **no migration, no egress.** pytest **405** (+10
`test_statcheck.py`); `ruff` clean; audit `.claude/security-audits/2026-06-21_statcheck.md` **PASS**; help corpus
gained a "Checking statistics (statcheck)" section (`HELP-DOCS-SYNCED` → 95). **This completes the inc 94–95
patter.** **NEXT:** the user's call — another patter, or deferred backlog (statcheck persistence + library-wide
facet, GRIM/p-curve, the discovery/gapfinder track, My Pubs Layer 3, reading mode / page-view options).

Earlier — increment 94 (library-header "+ Add ▾" menu + persistent/descending Sort): the two
**chores** of a fresh patter (carrot = statcheck, next, in its own plan-mode increment). (1) The library header's
two "bring papers in" actions (Scan folder + Import) folded into one **"+ Add ▾"** dropdown (`AddMenu` in
`10_pdf_layer.jsx`: a `.trash-toggle`-styled trigger + an outside-click-closing popup; token-based CSS) — 6
header actions → 5. (2) The **Sort** choice now **persists** (`localStorage["callosum.librarySort"]`, like the
theme/hide-uncertain prefs) and gained **Title (Z–A)** / **Author (Z–A)** (new `title_desc`/`author_desc` keys in
the `_paper_sort_order` allowlist; NULL author still last, `papers.id` tiebreak). Frontend-only bar the one
allowlist line; rebuilt `callosum-app.html`. pytest **395** unchanged (+2 assertions on the existing sort test);
`ruff` clean. **No migration, no egress.** **NEXT:** the carrot — **statcheck** (Track A: a local, inspectable
per-paper open-science signal that recomputes reported NHST p-values from the extracted text and flags
inconsistencies — never a verdict). Gets **plan-mode + the Principles gate** first (it produces a signal about
the literature).

Earlier — increment 93 (BibTeX / RIS / CSL-JSON import): the patter's **carrot** (chores were
inc 91 filter-by-type + inc 92 un-dismiss). The inverse of inc-70 export: **Import** a `.bib`/`.ris`/`.json`
(library header, next to Scan folder) → parse → dedup → create metadata-only papers → embed. New
`metadata/citation_import.py` **hand-rolls** all three parsers (**no new dependency** — project ethos, cf.
inc-75); each yields a CSL dict (inverting `citation_export`'s maps), `csl_record_to_paper_fields` → `create_paper`
kwargs (`csl_json` stored whole → lossless round-trip; `item_type` = CSL type → the inc-91 Type facet labels it);
`import_citations` dedups via `find_existing_paper_by_identity` in per-record savepoints (a bad entry is
skipped+counted, never fatal); caps bytes + record count. **Entirely local — NO egress** (the file is
authoritative; no Crossref/Gemini); the browser POSTs the file **text in the JSON body** (no multipart/upload
surface, no server-side path → no traversal surface). Async `POST/GET /library/import` (`routers/library.py`,
reusing the inc-87 scan scaffolding) + `28_import.jsx` (clones `ScanModal`, a file picker). `<fmt>-import` is
outside enrichment's update allowlist (won't clobber the imported metadata, like user-edits). pytest **395**
(+9 `test_citation_import.py`); `ruff` clean; audit `.claude/security-audits/2026-06-21_citation-import.md`
**PASS**; help corpus gained an "Importing a citation file" section (`HELP-DOCS-SYNCED` → 93). **No migration, no
egress, no new dependency.** **This completes the "2 chores + 1 carrot" patter (inc 91–93).** Deferred: PDF-attach
on import, optional enrich/My-Pubs hook, a hardened BibTeX parser. **NEXT:** the user's call — another patter, or
deferred backlog (statcheck, the discovery/gapfinder track, page-view options / reading mode, full `.btn-*`
normalization).

Earlier — increment 92 (un-dismiss for My-Publications missing works): chore 2 of the patter.
Completes inc-85's missing-works review queue with the **undo** inc-67 added for duplicate-dismissals — a
mistakenly-dismissed own-paper can be **Restored** to the queue. `profile_repo.undismiss_work` removes a
normalized DOI from `profile.dismissed_work_dois`; `build_dashboard` now also returns **`dismissed_works`**
(the author's cached works whose DOI is dismissed — titles from the cached OpenAlex works) beside `missing_works`,
sharing one dismissed-set computation; `DashboardResponse.dismissed_works` reuses `MissingWork`; new **`POST
/my-publications/works/undismiss`** (local, idempotent, 204) mirrors the dismiss endpoint; the dashboard
(`31_mypubs_dashboard.jsx`) gains a collapsible **"Previously dismissed (N)"** section with a **Restore** link.
Cache-only (no network call), **no migration, no egress** (pure profile-JSON edit). pytest **386** (+1:
`test_undismiss_returns_work_to_missing_queue`); `ruff` clean; backlog reconciled (the inc-85 deferred follow-on
marked done). **NEXT (this patter):** the carrot — **BibTeX/RIS/CSL-JSON import** (plan-mode + security-audit
first; new ingestion path, the complement to inc-70 export).

Earlier — increment 91 (filter the library by type + prerequisite module splits): chore 1
of a "2 chores + 1 carrot" patter. A **Type** dropdown in the library header filters to a single CSL item type
(article-journal / book / preprint / …): `list_papers(item_type=…)` adds a **bound** `WHERE item_type == :v`
(rule #3), and a new **`GET /papers/item-types`** facet endpoint (distinct **live** types + counts via
`list_item_types`, NULL excluded) drives the dropdown so it only offers types that exist — a `_typeLabel` map
prettifies them ("article-journal" → "Journal article (32)"). `.searchbar` gained `flex-wrap`. **Rule #1 forced
a split first:** adding this surfaced `repository.py` (625) + `routers/papers.py` (600) at/over the 600-line cap
(the CLAUDE "~577" note had silently drifted), so native-annotations data-access moved verbatim →
`persistence/annotations_repo.py` (repository.py→538) and PDF file-serving → `routers/paper_files.py`
(papers.py→539), both behavior-preserving (precedents: dedup_repo/tags_repo, duplicates.py). The PDF route kept
its path, so the only route-surface change is `/papers/item-types`. Frontend: `40_app.jsx` `libraryItemType` +
`itemTypes` state; `10_pdf_layer.jsx` Type `<select>`; rebuilt `callosum-app.html`. pytest **385** (+1:
`test_filter_by_item_type_and_item_types_endpoint`); `ruff` clean; backlog reconciled (Unsorted=inc 80,
re-score-wrap=inc 86, filter-by-type=inc 91 marked done; progress-indication partial). **No migration, no egress,
no audit gate.** **NEXT (this patter):** chore 2 — un-dismiss for My-Pubs missing works (mirror inc-67); then the
carrot — **BibTeX/RIS/CSL-JSON import** (plan-mode + security-audit; new ingestion path).

Earlier — increment 90 (sidebar header redesign: horizontal logo + larger wordmark):
a frontend-only brand-header reorg (user request, matched to a mockup + alignment guides). The sidebar brand
became a **horizontal lockup** — the brain logo on the left, a **36px** "Callosum" serif wordmark to its right
(was a 19px wordmark stacked *under* a centered logo) — with the `⚙` settings button in the **top-left** corner
and the `?` help button in the **top-right**. **CSS-only** (`app/frontend/styles.css`: `.brand` column→row +
center + `margin-top`; `.brand h1` 19→36px + nowrap; `.icon-gear` →top-left `left:14`; `.icon-help` →top-right
`right:14`): the JSX already supported it (the buttons are `position:absolute` so DOM order is irrelevant;
`.brand` is a flex container). The inc-47 connection-status logo (green-dot `.connected` swap, theme-matched) is
untouched; no new tokens/hexes (serif + `--ink`, existing `.icon-*` recipes). Rebuilt `callosum-app.html`. pytest
**384** unchanged (no Python touched); visual QA delegated to the user; **font-size 36px is the flagged tunable**.
_(Two same-day tweaks after first look: wordmark 40→36px; buttons split back into the two corners, settings left /
help right.)_
**NEXT:** the user has broader tweaks coming (likely My Pubs); or a fresh chore/carrot cluster (deferred:
BibTeX/RIS import, statcheck, the discovery/gapfinder track, scan watch/auto + changed-file re-ingest, full
button `.btn-*` normalization if the user wants it eyeballed).

Earlier — increment 89 (search across all fields + a search-scope dropdown): two related
search upgrades (user request). (1) **Fixed the all-authors bug** — search only looked at title +
`first_author_family_name`, so a co-author's surname found only first-authored papers (the user's name returned
6 of 40); it now searches the whole `csl_json` record (every author + journal + year + DOI + abstract + …). (2)
A **scope dropdown** beside the search box (All fields / Title / Author / Journal, default All) narrows it.
Backend: `repository._search_clause(field, pattern)` + a `search_field` query param on `GET /papers` (key from a
`SEARCH_FIELDS` allowlist — rule #3; pattern bound); composes with sort/deleted/axis/tag/pagination.
Frontend: a `librarySearchField` state + the scope `<select>` (`40_app.jsx`, `10_pdf_layer.jsx`). **No migration,
no new endpoint, no egress.** pytest **384** (+1: `test_search_covers_all_authors_and_scopes` — a 2nd author is
found under all/author, not title; journal matches venue); `ruff` clean; help corpus's "Browsing and searching"
search paragraph rewritten (`HELP-DOCS-SYNCED` → 89). Trade-off (v1): the `author` scope matches the whole
record + `all` includes the JATS abstract — a precise per-author `json_each` query is a deferred refinement.
**NEXT:** the user has broader tweaks coming (likely My Pubs); or a fresh chore/carrot cluster (deferred:
BibTeX/RIS import, statcheck, the discovery/gapfinder track, scan watch/auto + changed-file re-ingest, full
button `.btn-*` normalization if the user wants it eyeballed).

Earlier — increment 88 (search + sort on one row): a small library-pane tweak (user request) —
the **Sort** control moved inline to the right of the search box (into the `.searchbar` flex row; dropped the
`.lib-sort-row` wrapper), reclaiming a vertical row. Frontend-only (`10_pdf_layer.jsx` + `styles.css`); pytest
**383** unchanged.

Earlier — increment 87 (scan / refresh a library folder): the user's top-priority TDL item —
point Callosum at a folder of PDFs and reconcile **new / unchanged / removed** files into the library (the
Zotero-free way to keep it current). New `pdf_processing/library_scan.py::scan_library_folder` (reuses
`attach_pdf_to_paper` + `file_sha256` + the indexed `attachments.checksum`; **linked** in-place, nothing copied;
checksum-dedup; per-file savepoint isolates corrupt PDFs; removed → `availability="missing"`) + an async job
(`routers/library.py`, `POST/GET /library/scan`) that enriches new papers from Crossref (unresolved → the inc-80
Unsorted view) + embeds them. Frontend: a **Scan folder** button + `ScanModal` (`27_scan.jsx`). **No migration**
(reuses `attachments`); only egress is the Crossref DOI lookup (NOT the Gemini gate); the folder is read
server-side (fine on 127.0.0.1 — flagged in the deployment checklist to gate before any hosted deploy). pytest
**383** (+3); audit `.claude/security-audits/2026-06-21_library-scan.md` **PASS**; help corpus gained a "Scanning
a folder for PDFs" section (`HELP-DOCS-SYNCED` → 87). v1 = manual scan/refresh; **watch/auto** + a persisted
watched-folder + changed-file re-ingest are deferred. **NEXT:** the user has tweaks coming (likely My Pubs); or
a fresh chore/carrot cluster (deferred: BibTeX/RIS import, statcheck, the discovery/gapfinder track).

Earlier — increment 86 (axis re-score line-wrap fix + button-cleanup resolution): two
frontend-only UI-polish chores. (1) The axis **re-score row** no longer wraps badly — `flex-wrap: nowrap` + the
Cutoff slider made the shrinkable flex item (`.axis-cutoff-range flex:1; min-width:36px`), so label · slider ·
Re-score · 👁 stay on one line at any sidebar width. (2) **DESIGN §3 #5 resolved:** the remaining "divergent
buttons" (axis-sort, pdf-zoom, axis-new, source-jump, history-delete, hl-editor, axis-x, frame-tab-close) were
reviewed and found to be **intentional distinct compact/colored variants, not near-duplicates** — folding them
into the full `.btn-*` recipe would value-shift them (contra "no behavior change"), so they're **kept as
documented exceptions**; the only safe unification was tokenizing every `border-radius: 5px` → `var(--radius-sm)`
(zero visual change; advances §3 #6). pytest **380** unchanged (frontend-only); `ruff` clean; help corpus
unchanged. **NEXT (in progress):** the carrot — **scan/refresh a library folder** (plan-mode first; new
ingestion path → audit gate).

Earlier — increment 85 (My Publications — missing-works review + import): the dashboard's
indexed-vs-library gap ("79 indexed · 40 in library") becomes a **review queue** — the OpenAlex-attributed works
**not** in your library, each with **Import** (accept) or **Dismiss** (reject). `build_dashboard.missing_works`
= cached author works whose DOI ∉ live library ∉ `profile.dismissed_work_dois` (sorted by citations; cache-only).
**Import** (`import_missing_work`) is **guardrailed** (the DOI must be one of the author's cached works — no
arbitrary minting) + **metadata-only** (`create_paper` + Crossref enrich `force=True`; the OA-PDF path stays the
separate "Acquire OA copy") + adds a confirmed My-Pubs member directly; idempotent. **Dismiss** persists a
normalized DOI (migration **0013**). `POST /my-publications/works/{import,dismiss}`; only egress is the Crossref
DOI lookup (not the Gemini gate). pytest **380** (+3); audit
`.claude/security-audits/2026-06-21_my-pubs-missing-works.md` **PASS**; help corpus updated (`HELP-DOCS-SYNCED`
→ 85). **This completes the user's three My-Pubs follow-ups** (inc 84 starring + inc 85 missing-works review +
import). **NEXT:** Layer 3 (enriched per-paper cards) / Layer 4 (prospection) remain deferred; or a fresh
chore/carrot cluster.

Earlier — increment 84 (star key publications + scope the AI summary): a My-Publications
curation chore — ⭐ **star** key papers in the My Pubs sidebar card, and a **"⭐ only"** toggle on the dashboard
that scopes the inc-81 AI research-summary generation to the starred set. Storage is an isolated
`profile.starred_paper_ids` JSON list (migration **0012**; like `research_domains`); the star state surfaces on
the **my_publications axis clusters** response (`ClusterPaperResponse.starred`, gated to that axis); `POST
/my-publications/star`; the generate endpoint gained a `starred_only` body → `my_publication_documents(only_paper_ids=…)`
(empty starred + starred_only → 422). LLM-free plumbing (the summary path is the already-gated inc-81 egress
seam). pytest **377** (+2); help corpus updated (`HELP-DOCS-SYNCED` → 84); `ruff` clean. **NEXT:** inc 85 (the
carrot) — the missing-works review/import queue.

Earlier — increment 83 (My Publications Part 2 — domain decomposition, Layer 2): the
dashboard's **Research domains** section — cluster your CONFIRMED own-papers into research domains
(**impact-by-domain**: citation sums) and **click a domain to re-filter** the publications-by-year chart.
**LLM-free** local clustering (reuses the inc-52 axis-suggestion machinery); the only egress is the OpenAlex
works **refresh** that adds per-work `cited_by_count` (metadata, not the Gemini gate). Stored as an **isolated
`profile.research_domains` JSON** artifact (migration **0011**), NOT child `cluster_nodes` — because
`axis_score_state` counts members by `axis_id` across all nodes, so children would double-count the inc-78/79
card badge. New `decompose_domains` + `_dashboard_domains` (my_publications.py), `AuthorWork.cited_by_count` +
`fetch_author_works(refresh=…)`, `POST/GET /my-publications/domains`, `DashboardResponse.domains`; frontend
domains section (impact bars + select-to-refilter) in `31_mypubs_dashboard.jsx`. Impact = honest citation
**sums** (no composite score); domains show member papers + terms (inspectable); 0.25 candidates excluded.
pytest **375** (+5); audit `.claude/security-audits/2026-06-20_my-publications-domains.md` **PASS**; help corpus's
My Publications section extended (`HELP-DOCS-SYNCED` → inc 83). Layers 3–4 deferred. **Also captured to the
backlog (user, deferred):** star key pubs + scope the AI summary to starred; a review queue for OpenAlex works
**missing** from My Pubs (the 79-indexed vs 40-in-library gap → accept/reject); import the missing ones via the
acquisition lane. **NEXT:** those My-Pubs follow-ups, or Layer 3 (enriched per-paper cards), or another
chore/carrot cluster.

Earlier — increment 82 (library-card tidy + double-click/text-select fix): two small
library-card UX chores (frontend-only, `10_pdf_layer.jsx`). (1) Dropped the "N chunks" chip from cards —
chunk count is processing-internal, not bibliographic (cards keep title·authors·year·venue + tier/file/needs-DOI).
(2) A card's double-click now opens the PDF **only when it didn't select text** (`getSelection().isCollapsed`):
double-click a title word → it selects (copyable), no open; double-click empty card space → opens. pytest **370**
unchanged (frontend-only); no migration/endpoint/egress/CSS. **NEXT:** the chosen carrot — My Publications
**Part 2 Layer 2** (domain decomposition: cluster your own corpus into sub-axes + impact-by-domain, re-filter
the dashboard) — plan-mode first.

Earlier — increment 81 (My Publications Part 2 — the impact dashboard, Layer 1): an Overview
**dashboard tab** for the pinned My Publications axis (opened by a **📊** button on the card), turning the
user's own corpus into a first-class impact surface — headline OpenAlex metrics (citations / h-index / i10 /
indexed works), a hand-rolled **publications-by-year SVG chart** (+ citations-by-year), the **indexed-vs-library
gap** (an import nudge), and an **editable AI research summary**. The dashboard is a **cache-only, egress-free
read** (`build_dashboard` via `cached_author`, which never fetches; gated on `profile.openalex_author_id` ⟹ the
cache is warm) — the OpenAlex author object inc-78 already cached carries the stats, so headline metrics need
**no new API call**, are OpenAlex's authoritative figures shown **verbatim + attributed** (never a callosum
composite). The only egress is the research summary — LLM narration over the user's OWN titles/abstracts
(library text), **egress-gated at the inc-58 seam** (`EgressGatedResearchSummaryGenerator`; off → 503), a
non-load-bearing editable draft. New `integrations/gemini/research_summary.py`, `31_mypubs_dashboard.jsx`,
3 endpoints (`GET /my-publications/dashboard`, `POST /summary/generate`, `PUT /summary`), migration **0010**
(`profile.research_summary`). pytest **370** (+8); audit
`.claude/security-audits/2026-06-20_my-publications-dashboard.md` **PASS**; help corpus's My Publications
section extended (`HELP-DOCS-SYNCED` → inc 81). Layers 2–4 (domain decomposition / enriched cards / grounded
prospection) deferred. **NEXT:** open backlog — a separate **discovery** track the user floated (find papers
beyond the library / external search / a gapfinder) stays a parked future-track, plus the standing backlog
(library merge, etc.).

Earlier — increment 80 (the "Unsorted" library view — a needs-review filter): an **Unsorted**
toggle in the Library header (+ a clearable banner) that narrows the list to papers whose metadata still needs
review — raw PDF scaffolds, Crossref-unresolved imports, and papers with no recorded source — so they don't
silently disappear into the library. Backend: a `needs_review` query param on `GET /papers` →
`list_papers(needs_review=…)` filters `imported_source IN ("pdf-scaffold","crossref-unresolved") OR IS NULL`
(a local literal allowlist; bound-param). A **view** like Trash (clears axis/tag filters) but keeps
checkbox-select on, so you can select-all the unsorted papers and bulk re-resolve/export/delete. **No migration,
no new endpoint, no egress**; pytest **362** (+1: the three unsorted states returned, resolved/user-edited
excluded, trashed excluded); `ruff` clean; help corpus updated (the browsing section gained the Unsorted control;
`HELP-DOCS-SYNCED` → inc 80, also folding in the inc-77 hide-uncertain default + the inc-79 count-badge note).
**NEXT (task list):** My Publications Part 2 — the impact **dashboard tab** (the carrot; plan-mode first). A
separate **discovery** direction the user floated (find papers beyond the library / external search / a
gapfinder) stays a parked future-track, not part of My Pubs Part 2.

Earlier — increment 79 (count badge subtracts hidden uncertain papers): a follow-on to
inc-77's hide-uncertain-by-default — when an axis shows only assigned/manual papers (the inc-51 👁 toggle / the
inc-77 Settings default), its count badge now shows the **visible** count (total − uncertain) with a tooltip
noting how many are hidden, so the number matches the list. `axis_score_state(conn, id, *, cutoff=…)` returns a
new **`uncertain_count`** (scored `confidence < cutoff`, mirroring the read-time tiering); `AxisResponse.uncertain_count`
exposes it; `15_axes.jsx` subtracts it per the per-axis view-state (My Pubs card passes `hideUncertainDefault={false}`
→ full count). Additive read-only field on the existing `/axes` response — **no migration, no new endpoint, no
egress**; pytest **361** (assertions added to two existing axis tests, count unchanged); `ruff` clean; frontend
rebuilt. (Also this session, as small unnumbered chores: an indeterminate `ProgressBar` on the long async jobs;
the My Publications card moved below the filter/sort controls; inter-axis-card spacing 2→5px; CI actions bumped
to Node 24 — checkout@v5 / setup-python@v6.) **NEXT (task list):** the UNSORTED/needs-review library filter
(chore), then My Publications Part 2 — the impact **dashboard tab** (carrot, plan-mode first).

Earlier — increment 78 (My Publications — the auto-axis of your own papers, Part 1):
a pinned, **OpenAlex-resolved, LLM-free** axis of the researcher's own papers. Set a **profile** (name /
published-name variants / ORCID) in Settings → **Refresh** resolves the identity via OpenAlex (ORCID-first) →
ORCID/DOI matches are **confirmed members**, name-only matches are **candidates** you ✓ confirm / ✕ reject
(**persisted** in `my_publication_decisions` — a rejection never re-appears). Facts-vs-candidates +
confirm-and-learn; an **import hook** adds new matching papers incrementally (cache-based, zero extra egress);
the pinned 📄 card reuses `AxisItem` branched on the new `axes.kind`. New `integrations/openalex/author.py`,
`persistence/profile_repo.py`, `clustering/my_publications.py`, `routers/my_publications.py`, migration **0009**.
OpenAlex author lookup is **metadata egress, not the Gemini gate**; **no model tokens**; strictly additive (the
import hook is a guarded no-op when unused). pytest **361** (+14); audit
`.claude/security-audits/2026-06-20_my-publications.md` **PASS**; help corpus gained a "My Publications" section
(`HELP-DOCS-SYNCED` → inc 78). **NEXT:** Part 2 — the impact **dashboard tab** (charts / citation graph /
prospection), deferred. (Also this session: the backlog was split into open + `INCREMENT-BACKLOG-DONE.md`;
inc 77 hide-uncertain-by-default shipped.)

Earlier — increment 77 (hide uncertain axis papers by default): a backlog quick-win — the
inc-51 per-axis **👁 hide-uncertain** view can now be the **default** via a new **Settings → Axes** toggle
(persisted to `localStorage["callosum.hideUncertainDefault"]`, mirroring the theme pattern). Threaded App →
Sidebar → AxesPanel → AxisItem (initial `hideUncertain` reads the default; AxesPanel keys each card on it so a
toggle remounts them live). Frontend-only (`35_settings.jsx`, `40_app.jsx`, `10_pdf_layer.jsx`, `15_axes.jsx`,
`styles.css`; rebuilt `callosum-app.html`); pytest **347** unchanged; visual check delegated to the user. Also
this session: the **backlog was split** into `INCREMENT-BACKLOG.md` (open) + `INCREMENT-BACKLOG-DONE.md` (closed
archive). NEXT: the **My Publications** future-track (the chosen reward — plan-mode + Principles gate first), then
more backlog quick-wins / the deferred follow-ons.

Earlier — increment 76 (literature acquisition — the wanted list + OA re-check + coverage, C):
completes the acquisition arc's **track** loop. A persistent **wanted list** (`wanted_items`, migration **0008**)
that auto-includes PDF-less library papers (**Sync from library**) and accepts external adds (**Add by DOI**),
a manual async **Re-check OA** job that runs the same resolver cascade over the list and **auto-acquires** hits
(library wants fill the paper; external wants create a paper then import + enrich), and a **coverage readout**.
The OA-only bright line is **free + structural** — the re-check resolves only through the `ResolverRegistry` (so
no non-OA/arbitrary-URL path; test-pinned); external wants need a doi/pmid (title-only → skipped, never a fuzzy
mint); per-item errors never abort a run; a logged per-run cap bounds bulk fetching. New
`persistence/wanted_repo.py` + `acquisition/wanted.py` (the testable re-check service) + `routers/wanted.py`
(`/wanted` CRUD + sync-library + coverage + async recheck) + `26_wanted.jsx` (a **Wanted** modal in the lib-head).
**No new dependency, no new egress** (OA databases only, NOT the Gemini gate). pytest **347** (+13: repo +
run_recheck library/external/skip/miss/error-isolation/registry-only + endpoints); audit
`.claude/security-audits/2026-06-20_wanted-list.md` **PASS**; help corpus gained an acquisition/wanted section
(`HELP-DOCS-SYNCED` → inc 76). **This completes Acquisition A/B/C.** **Phase 8** (the future-tracks watched-inbox
session-kickoff rule — Session kickoff #9) is now done too, **closing the release-readiness arc, Phases 1–8.**
NEXT: deferred follow-ons in `INCREMENT-BACKLOG.md` (CI billing, collaborator/branch-protection, dev-infra
hardening, and the future tracks themselves); the legally-ambiguous lane stays counsel-gated (parked in the
gitignored inbox).

Earlier — increment 75 (literature acquisition — fan out the resolver cascade, B): the
inc-74 OA lane gains a **7-source cascade** (gold→green→preprint, first authorized copy wins) behind the
unchanged `OaLocation` seam — OpenAlex (primary) → **DOAJ** → **Europe PMC** → **Crossref-OA** → **CORE** →
**arXiv** → **bioRxiv/medRxiv** → **OSF/PsyArXiv**. Each is the OpenAlex-adapter shape (injectable fetcher,
`external_api_cache`, `lookup_oa → OaLocation|None`, fail-closed) + a thin resolver; the `resolve()` loop is
untouched (new sources only `register()` in `build_default_registry`). OA-ness stays each database's assertion
(no honest https PDF → None, never a guess); shared `integrations/api_cache.py`; **CORE** uses
`CALLOSUM_CORE_API_KEY` (Bearer; absent → silent no-op); **arXiv** parses the Atom id by regex not stdlib XML
(XXE surface, rule #4) → **no new dependency, no migration (head 0007), no new endpoint, no frontend change**.
pytest **334** (+31 hermetic per-source + cascade + structural); audit
`.claude/security-audits/2026-06-20_oa-acquisition-b.md` **PASS**; help corpus gained an "Acquiring an
open-access copy" section (`HELP-DOCS-SYNCED` → inc 75, clearing the inc-74 help debt). **NEXT:** Increment C
(wanted-list table + an OA-DB-only re-check job + a coverage readout). The legally-ambiguous lane stays
deferred/counsel-gated (its inbox spec is gitignored).

Earlier — increment 74 (literature acquisition — the legally-clear open-access lane, A):
resolve a PDF-less paper (DOI/PMID/title) → an OpenAlex-asserted **authorized open-access** PDF → download +
validate → import locally as a **`managed`** attachment named per the library convention
(`Authors - Year - Venue.pdf`) + labeled OA color/version/source (bronze flagged unstable). The bright lines
are enforced **structurally** by the `OaLocation` seam (required OA color, no "closed" member; the downloader
takes an `OaLocation`, never a bare URL → an arbitrary/non-OA fetch is inexpressible — same idea as the inc-58
egress gate). New `app/backend/acquisition/` (registry + fetch + resolvers), `integrations/openalex/`, migration
**0007** (OA-label columns on `attachments`), async `POST /papers/{id}/acquire-oa`, and a per-paper **"Acquire
OA copy"** button on PDF-less papers. pytest **303** (+24: structural OA-only, OpenAlex mapping/cache/fail-closed,
download validation, managed import+labeling, filename convention); audit
`.claude/security-audits/2026-06-20_oa-acquisition.md` **PASS**; e2e green; the spec is
`future-tracks/opus4.8_future-tracks_acquisitionclean.md`. **NEXT:** Increment B (resolver cascade —
DOAJ/CORE/arXiv·bioRxiv·PsyArXiv·PMC/Crossref) then C (wanted-list + OA-only re-check + coverage). The
legally-ambiguous lane stays deferred/counsel-gated. (The release-readiness arc Phases 1–7 shipped callosum to
**github.com/cliffworkman/callosum** — public, AGPL-3.0; follow-ons — CI billing, collaborator/branch-protection,
Phase 8 watched-inbox rule, dev-infra hardening roadmap — are tracked in `INCREMENT-BACKLOG.md`.)

Earlier — increment 73 (author/index keywords as first-order tags — Crossref `subject`):
a paper's **Crossref subject categories** import as first-order tags (`import_source="keyword:crossref"`) —
automatically on **🔎 re-resolve** / batch enrich, and across the existing library via
`python tools/backfill_keyword_tags.py` (full: cache-first, re-resolve the rest; **tag-only**, idempotent).
`adapter._crossref_message_to_csl` now keeps `subject` in `csl_json`; `enrichment.apply_crossref_subject_tags`
mirrors it to tags (additive, never clobbers metadata); `tags_repo.add_tag_to_paper(import_source=…)` sets
provenance on create only (a user tag is never relabeled) + `add_tags_to_paper`. DOI-only to public Crossref
(NOT the egress gate, per inc 49); **no migration, no new endpoint, no new dependency**. The inc-72 c-TF-IDF
suggester is the second-order gap-filler; Zotero tags already import (inc 71). Frontend bugfix: `TagsRow`
re-syncs on a detail refetch so 🔎-added chips appear without a paper switch (no other UI change — the inc-49
"More" section already hides the list-valued `subject` via `isScalarValue`). pytest **256** (+5: adapter
dedupe, re-resolve→tags + provenance preserved + filterable, backfill cache/fetch/idempotent/metadata-safe);
live E2E (`.local/keyword_tags_e2e/`, injected fake Crossref) — 🔎 → keyword chips → filter, 0 console errors;
audit `.claude/security-audits/2026-06-20_keyword-tags.md` PASS; help corpus tags section covers keyword tags
+ the backfill (`HELP-DOCS-SYNCED` → inc 73). NEXT (deferred): the **provenance UI** (surface tag `source`;
group "author keywords" vs "your tags" vs system facts; protect imported tags), **OpenAlex `concepts` /
PubMed MeSH** sources, and the **tags ↔ findings/system-facts** cross-cut (RETRACTED etc.) — all in
`INCREMENT-BACKLOG.md` "Tags & keywords"; plus sidebar Tags browser, formatted citation styles, library
**merge** (last).

Earlier — increment 72 (auto-suggest tags via local c-TF-IDF): a **✨ Suggest** button on
the Details Tags row proposes candidate tags mined from the paper's own text vs the library
(`clustering/tag_suggestion.py::suggest_tags_for_paper` — tf·idf, reuses `axis_suggestion._paper_tokens`,
excludes existing tags), which the user clicks to accept (added via the inc-71 path). The per-paper analogue
of inc-52's axis suggestion — **purely local: no embeddings, no clustering, no Gemini, no egress** (user's
explicit choice). `GET /papers/{id}/suggested-tags` (sync, read-only); no migration. pytest **251** (+3:
distinctive ranking, **idf demotes common terms**, exclude-existing, endpoint; route-surface +1); live E2E
(`.local/tag_suggest_e2e/`) — Suggest → accept a candidate, 0 console errors; audit
`.claude/security-audits/2026-06-20_tag-suggest.md` PASS; help corpus tags section now covers ✨ Suggest
(`HELP-DOCS-SYNCED` → inc 72). **FOLLOW-UP (user):** **author/expert keywords as first-order tags** (the
authors already did the concept work; c-TF-IDF is the second-order gap-filler) + a **tag-provenance** model
(user / imported-keyword / suggested / system-fact) + the **tags ↔ findings** cross-cut (a future RETRACTED
tag from the retraction producer) — recorded in `INCREMENT-BACKLOG.md` + "Tags hook" notes in the
future-tracks docs. NEXT: that author-keywords increment (Crossref `subject` / OpenAlex concepts / PubMed
MeSH; Zotero tags already imported), sidebar Tags browser, formatted citation styles, embedding-text JATS
cleanup, library **merge** (last).

Earlier — increment 71 (tags: per-paper labels + filter the library by tag): lightweight
free-form **tags** — view/add/remove on the Details pane, click a tag to **filter the library** to it. The
`tags`/`paper_tags` tables already existed (the Zotero importer populated them via `_upsert_tags`), so this
surfaces previously-**invisible** imported tags with **no migration**. New `persistence/tags_repo.py`
(get/list[+counts]/add[get-or-create + idempotent link]/remove[+orphan prune]) — split out because
`repository.py` was at 591 (mirrors inc-67's `dedup_repo.py`); new `routers/tags.py` (`GET /tags`,
`POST`/`DELETE /papers/{id}/tags*`); `PaperDetailResponse.tags` + a `tag_id` filter on `GET /papers` (IN
subquery, mirrors the inc-63 axis filter). Local, bound-param, non-destructive (manages links; prunes orphan
tags); names rendered as plain text. Frontend: Details `TagsRow` (chips name→filter / ×→remove + add-input
with a `/tags` datalist) + the axis-filter mirrored for tags (`libraryTagFilter`, mutually exclusive) + a
"Filtered to tag …" banner. pytest **248** (+4: dedupe/idempotent/orphan-prune/filter/endpoints; route-surface
+3); live E2E (`.local/tags_e2e/`) — add→filter→clear→remove, 0 console errors; audit
`.claude/security-audits/2026-06-20_tags.md` PASS; help corpus gained a "Tagging papers" section
(`HELP-DOCS-SYNCED` → inc 71). NEXT (chosen): **inc 72 — auto-suggest tags** per paper via **local c-TF-IDF
(no Gemini)**, reusing the inc-52 axis-suggestion machinery; candidate terms curated → added via this
increment's tag path. Other backlog: sidebar Tags browser, formatted citation styles (APA/MLA), embedding-text
JATS cleanup, purge-deletes-on-disk-PDF, library **merge** (last).

Earlier — increment 70 (citation export: BibTeX + RIS + CSL-JSON): the first way to get
citations **out** of the library — a **bulk file download** (select papers → `export…` picker → a
`.bib`/`.ris`/`.json`) and a **per-paper clipboard copy** (Details → **Cite** row). New
`app/backend/metadata/citation_export.py` (pure `to_bibtex`/`to_ris`/`to_csl_json` + `render_citations`
dispatch; reads `csl_json` with scalar fallback, abstract JATS-stripped via `abstract_plain_text`; **escapes
output**; BibTeX key = `citation_key` else deduped `{family}{year}`); `repository.get_papers_for_export`
(bound-param `IN`, **live papers only**); `POST /papers/export {paper_ids, format: Literal}` → `Response` with
the format media type + a **constant** download filename. **Read-only, local (no egress), no migration.**
Frontend: `apiPost` forces `.json()`, so a **raw fetch** does blob→`<a download>` (bulk) / text→clipboard
(per-paper; secure context on 127.0.0.1); the Cite links reuse the inc-68 `.btn-link`. pytest **244** (+8: 7
formatter unit + endpoint; route-surface +`/papers/export`); live E2E (`.local/citation_export_e2e/`) — bulk
`.bib` download + clipboard copy, 0 console errors; audit `.claude/security-audits/2026-06-20_citation-export.md`
PASS; help corpus gained an "Exporting citations" section (`HELP-DOCS-SYNCED` moved to inc 70). NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — formatted human citation styles (APA/MLA via a CSL processor, Track-B);
persist library sort; migrate divergent ghost/icon buttons to `.btn-*`; embedding-text JATS cleanup;
purge-deletes-on-disk-PDF; library **merge** (last, destructive).

Earlier — increment 69 (sort the library): added a **Sort** dropdown to the library
pane-head — order by date added (oldest/recent), title (A–Z), publication year (newest/oldest), or first
author (A–Z). Backend: a `sort` query param on `GET /papers` → `repository._paper_sort_order(sort)` maps the
key via an **allowlist** to ORDER BY constant column expressions (rule #3 — never interpolated); unknown →
default `added` (= prior `id ASC`); NULL year/author sort **last**; `papers.id` is the stable tiebreak.
**No new route, no migration, no egress**; composes with q/deleted/axis_id/pagination. Frontend: `librarySort`
state (resets to page 1; omitted from the URL when `added` so the default is unchanged) + `.lib-sort` control.
pytest **236** (+1: every sort order + NULL-last + unknown→default); live E2E (`.local/library_sort_e2e/`) —
list re-orders by title/year/recency, 0 console errors; no audit gate (read-only param); help corpus library
section updated (`HELP-DOCS-SYNCED` moved to inc 69). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — persist
the chosen sort + a direction toggle (deferred); migrate divergent ghost/icon buttons to `.btn-*` (+ §3 #6
radius scale); deferred token levers; embedding-text JATS cleanup; purge-deletes-on-disk-PDF; library
**merge** (last, destructive).

Earlier — increment 68 (canonical `.btn-*` button classes, DESIGN.md §3 #5): added
`.btn`/`.btn-primary`/`.btn-ghost`/`.btn-link`/`.btn-icon` + a `.danger` modifier as the single source of
truth for buttons, and folded the cleanly-identical ad-hoc button blocks into them by **grouping their
selectors** (primary: `.axis-btn`+`.synth-actions button`; ghost: `.pginate button`; link: `.axis-link`;
icon: `.axis-icon-btn`) — only where every grouped property is byte-identical, so it's **CSS-only with zero
visual change and no JSX touched**. Size-divergent ghost/icon buttons left as-is (value-shifting → deferred
to a per-button className migration). No Python changed → pytest unchanged at **235**; live E2E
(`.local/btn_dry_e2e/`) asserts each canonical class's **computed style** equals the intended recipe + the
real `.synth-actions button` keeps its sizing delta, 0 console errors; DESIGN.md §2 Buttons rewritten + §3 #5
→ PARTIAL. No audit gate (styling only); no help-corpus change. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md`
— migrate the divergent ghost/icon buttons to `.btn-*` (+ reconcile `.axis-link.axis-danger` amber→red) +
the §3 #6 radius scale; deferred token levers; embedding-text JATS cleanup; purge-deletes-on-disk-PDF;
library **merge** (last, destructive).

Earlier — increment 67 (un-dismiss / manage dismissals): completes inc-64's persistent
"not a duplicate" dismiss with an **in-app undo** — the Duplicates modal now has a **Previously dismissed**
section listing the dismissed pairs (with titles) and an **un-dismiss** control that lets the scan flag them
again. `GET /papers/duplicates/dismissed` (registered before `/papers/duplicates/{job_id}` so "dismissed"
isn't captured as a job id) + `POST /papers/duplicates/undismiss {paper_ids}` (non-destructive, idempotent,
local, bound-param). No migration (reuses the inc-64 table). **Forced module split (rule #1):** the two new
data-access fns pushed `repository.py` to 604 (>600), so the dedup-dismiss concern (4 fns) was **moved
verbatim** to new `persistence/dedup_repo.py` (63; repository.py→555); two importers repointed. pytest **235**
(+1: list → undismiss → re-flag, idempotent, 422); route-surface +2; live E2E (`.local/undismiss_e2e/`) —
dismiss → previously-dismissed → un-dismiss → re-flagged, 0 console errors; audit
`.claude/security-audits/2026-06-20_undismiss-duplicates.md` PASS; help corpus duplicates section updated
(`HELP-DOCS-SYNCED` moved to inc 67). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — deferred token levers
(cache extension + output caps); DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup; purge-deletes-on-disk-PDF;
library **merge** (last, destructive).

Earlier — increment 66 (exclude trashed papers from synthesis retrieval): closes the last
soft-delete leak (the inc-65 deferred item) — a paper in **Trash** (soft-deleted, not yet purged) is no
longer a retrieval candidate, so it can't be cited in a **new** synthesis. The real leak wasn't where inc-65
guessed: the pipeline doesn't use `search_similar` — `summarization/pipeline.py::_source_chunks_for_scope`
builds its own candidate SQL, and the **query** scope was `select(chunks)` with no paper filter (every paper).
Fixed with a **live-paper filter** there (covers query + hardens papers/cluster scopes); also hardened the
general `retrieval._candidate_embedding_ids` primitive (excludes trashed paper/chunk embeddings; used by the
validation harness). Backend-only — no migration/endpoint/egress/frontend; behavior-preserving when nothing
is trashed (harness unaffected). pytest **234** (+2: query-scope `_source_chunks_for_scope` + `search_similar`
both drop a trashed paper, keep the live one); no audit gate; help corpus trash gotcha updated
(`HELP-DOCS-SYNCED` moved to inc 66). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — deferred token levers
(cache extension + output caps); un-dismiss / "manage dismissals" UI; DESIGN.md `.btn-*` DRY; embedding-text
JATS cleanup; purge-deletes-on-disk-PDF; library **merge** (last, destructive).

Earlier — increment 65 (permanent delete: delete forever / empty Trash): completes
inc-54's soft-delete — a **trashed** paper can now be **permanently purged** (per-paper **Delete forever**
or **Empty Trash**), removing the paper, its dependent rows, AND its embeddings + sqlite-vec vectors. The
unsafe part inc-54 deferred was the orphan crash (`embeddings.target_id` has no FK + the store had no
delete → a leftover vector crashes `retrieval._resolve_hit`); fixed by a new `VectorStore.delete` +
`repository.purge_paper`/`purge_all_trashed` that delete the paper's embeddings + vectors **before** the
paper row (FK CASCADE handles the rest), in one transaction. **Trashed-only** (a live paper → 404, can't be
purged in one step); UI double-confirms; local-only; **no migration** (pure DML; head stays 0006).
`DELETE /papers/{id}/permanent` + `POST /papers/trash/empty`; frontend Delete-forever/Empty-Trash (danger,
`.danger` recipe). pytest **232** (+4: purge removes rows+vectors + no orphan-crash, live-paper refused,
trash-only endpoint, empty-trash-only-trashed); route-surface +2; live E2E
(`.local/permanent_delete_e2e/`) — delete-forever + empty-trash, live paper survives, 0 console errors;
audit `.claude/security-audits/2026-06-20_permanent-delete.md` PASS; help corpus trash section updated
(`HELP-DOCS-SYNCED` moved to inc 65). Deferred: doesn't delete the on-disk PDF; trashed-but-not-purged
papers still leak into new-synthesis retrieval (separate `deleted_at` filter). NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — that retrieval `deleted_at` filter; deferred token levers (cache
extension + output caps); un-dismiss / "manage dismissals" UI; DESIGN.md `.btn-*` DRY; embedding-text JATS
cleanup; library **merge** (last, destructive).

Earlier — increment 64 (persistent "not a duplicate" dismiss): marking a duplicate group
**not a duplicate** now **sticks** — the scan persists the group's pairs and respects them on every future
scan (finishes inc-56's deferred "persistent dedup-dismiss"). New `dismissed_duplicate_pairs` table
(migration **0006**, head; canonical `low<high`, FK CASCADE, unique) + `repository`
`get_dismissed_duplicate_pairs`/`dismiss_duplicate_pairs`; `find_duplicate_groups` drops dismissed pairs
**before** the union-find (so the group never re-forms); `POST /papers/duplicates/dismiss {paper_ids}`
(≥2 existing live papers → else 422; bound-param `INSERT OR IGNORE`; local, non-destructive); the frontend
dismiss button keeps the session-hide AND persists. **Forced module split (rule #1):** extending dedup pushed
`routers/papers.py` to **636** (>600), so the duplicates concern (models + `_DedupJobStore` + the 3 endpoints
+ `_run_dedup_job`) was **moved verbatim** to new **`routers/duplicates.py`** (157; papers.py→**497**),
included **before** `papers.router` so `/papers/duplicates*` still wins over `/papers/{paper_id}` — behavior
preserved. pytest **228** (+1; migration-head + route-surface asserts → `0006`); live E2E
(`.local/dedup_dismiss_e2e/`) — dismiss → reopen → "No likely duplicates found.", 0 console errors; audit
`.claude/security-audits/2026-06-20_dedup-dismiss.md` PASS; help corpus duplicates section corrected
(`HELP-DOCS-SYNCED` moved to inc 64). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — deferred token levers
(cache extension + output caps), un-dismiss / "manage dismissals" UI, DESIGN.md `.btn-*` DRY, embedding-text
JATS cleanup, permanent-delete/empty-trash; library **merge** (last, destructive).

Earlier — increment 63 (filter the library by axis): clicking an axis's **count badge**
(now a button, `15_axes.jsx`) narrows the main Library to that axis's papers, with a clearable "Filtered to
axis …" banner; pairs with inc-62 — **filter → select all → summarize** = a verified synthesis of a whole
topic cluster. Server-side: a new `axis_id` query param on `GET /papers` → `repository.py::list_papers` adds
a **bound-param `IN` subquery** over `cluster_node_papers`→`cluster_nodes` (composes with the existing
`deleted_at`/`q`/pagination; trashed stay excluded; rule #3). Frontend: `40_app.jsx` `libraryAxisFilter`
state + `filterToAxis`/`clearAxisFilter`/`selectAllLibrary` (the filter is a *view*, exclusive with
trash/focus but keeps checkbox-select on) threaded App→Sidebar→AxesPanel; a banner (reuses the inc-50
`.focus-card`) + a `.lib-select-all` link in `10_pdf_layer.jsx`. **No new endpoint/egress/ingestion/migration**;
read-only (security note in the increment notes, no separate audit). pytest **227** (+1); live E2E
(`.local/library_axis_filter_e2e/`) — filter narrows 2→1 + banner + select-all→summarize verified + clear
restores, 0 console errors; help corpus axis-review section updated (`HELP-DOCS-SYNCED` moved to inc 63).
NEXT: deferred token levers (cache extension + output caps), DESIGN.md `.btn-*` DRY, embedding-text JATS
cleanup, permanent-delete/empty-trash, persistent dedup-dismiss; library **merge** (last).

Earlier — increment 62 (summarize selected papers): the library checkbox multi-select
(inc 54) now wires to a **summarize** action — select papers → click **summarize** in the bulk bar → a
**verified, citation-grounded synthesis of just that subset** runs in the always-on Synthesis pane (with an
"N selected papers" scope-note badge), reusing the existing `/summarize` **papers** scope + local
verification + the inc-61 cache (no new endpoint/egress/ingestion/migration). Wiring:
`40_app.jsx` (`pendingSummarize` nonce + `bulkSummarizePapers`) → `RightPane` → `20_synthesis.jsx`
(`start()`'s POST+poll refactored into a shared `launch()`; a nonce-keyed `useEffect` runs the papers scope
with `top_k = min(max(8, n), 24)`). **Backend coverage fix:** `pipeline.py::_round_robin_by_paper`
interleaves chunks across the selected papers before the `top_k` slice (a plain `rows[:top_k]` is
chunk-id-ordered → would ignore higher-id papers); ≤1 paper → identity, query scope untouched. The
**critical-review supplement** is deferred behind the **Auditability standard** (recorded in the backlog).
pytest **226** (+3: round-robin interleave + a capturing-generator multi-paper coverage proof); live E2E
(`.local/summarize_selected_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-20_summarize-selected.md`
PASS; help corpus's synthesis section updated (`HELP-DOCS-SYNCED` moved to inc 62). NEXT: deferred token
levers (cache extension + output caps), DESIGN.md `.btn-*` DRY, embedding-text JATS cleanup,
permanent-delete/empty-trash, persistent dedup-dismiss; library **merge** (last).

Earlier — increment 61 (reduce LLM token spend: content-addressed summary cache +
usage logging): a **persistent content-addressed SQLite cache** on the token-expensive **summary
generation** step (a cache hit costs zero tokens — the dominant cost lever). `CachedSummaryGenerator`
(`app/backend/llm/cache.py`) keys on `sha256(canonical_json({cache_signature, chunk set, scope_ref}))`
(`cache_signature` = model + `SUMMARY_PROMPT_VERSION`), so any input change misses automatically (no
explicit invalidation; negative results cached free); stored in `llm_cache` (migration **0005**, head). It
is layered **inside** the egress gate (`EgressGated(Cached(real))`) so egress-off behaves byte-for-byte as
before, and uses the pipeline's existing `conn` (threaded into `generate()`; a 2nd SQLite connection
mid-transaction would lock); **local citation-verification re-runs on every result, cached or fresh** — a
hit replays cached *candidates* and re-verifies them, never serving a stale verdict. Plus token-usage
logging (`llm/usage.py`) at all 4 LLM call sites. Eagerness audit: no hover/preview/auto LLM calls (only
`/axes/suggest` fires on its modal open). The other levers (cache extension to help/labeler/suggester,
output caps + JSON mode, top_k right-sizing, Gemini provider prefix caching, Batch API, coalescing) are
**proposed with a measurement/verification plan and DEFERRED for review** — see `INCREMENT-61-NOTES.md` for
the ranked table + implemented-vs-deferred. pytest **223** (+6); audit
`.claude/security-audits/2026-06-20_llm-cache.md` PASS; no frontend change. NEXT: the deferred token levers
(cheapest: cache extension + output caps, gated on the usage measurements), then backlog — library merge,
terms-as-first-class, embedding-text JATS cleanup, permanent-delete/empty-trash, persistent dedup-dismiss.

Earlier — increment 60 (AI help assistant, separate gate): an AI help assistant in the
help modal — ask a question, get an answer + **reference chips** that scroll to and highlight the matching
help section (reusing inc-59's `flashHelpSection`), recapitulating the synthesis "probe → route to source"
workflow over the app's own help. `POST /help/ask` is gated by its **own** `CALLOSUM_HELP_ASSISTANT_ENABLED`
toggle (new `GeminiConfig.help_assistant_enabled`), **independent** of the library `CALLOSUM_ALLOW_DATA_EGRESS`
gate — it sends only the user's question + the **public** help corpus (never library text), so it works
with the library gate off (proven by a test + a library-egress-off live E2E). Provider-neutral
`HelpAssistant` Protocol (`app/backend/help/assistant.py`) + `GeminiHelpAssistant`
(`integrations/gemini/help_assistant.py`, **NO RAG** — whole corpus stuffed); enforced at the inc-58 seam
(`EgressGatedHelpAssistant` + `HelpAssistantDisabledError`). Multi-turn (stateless), defensive parse
(failure → answer, no refs, never 500), router drops hallucinated section ids. Additive — **no existing
path or API shape touched**. Added an `ai-help-assistant` help section (moving the `HELP-DOCS-SYNCED` marker
to inc 60). pytest **217** (+7: answer+refs, gate-independence, hole-closed 503, unknown-id drop, 422, parse
degradation, self-check); live E2E (`.local/help_assistant_e2e/`, library egress OFF) 0 console errors; audit
`.claude/security-audits/2026-06-20_help-assistant.md` PASS. NEXT: backlog — library **merge** (last,
destructive), terms-as-first-class; DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup;
permanent-delete/empty-trash; persistent dedup-dismiss.

Earlier — increment 59 (help corpus + navigable help modal): the in-app help became a
real surface — extensive end-user documentation served as a structured **corpus**
(`app/backend/help/help_content.md`, 22 sections with **stable anchor ids** via `<!-- section: <id> -->`
markers) by `GET /help/corpus` (stateless, no DB, **no egress**), rendered in a **navigable two-column
modal** (`18_help.jsx`: TOC + sections + a reusable `flashHelpSection(id)` scroll-to-flash) — retiring the
old single hard-coded tips block. `corpus.py` parses the markdown into sections + a small **allowlisted**
HTML render (no new dep); `dangerouslySetInnerHTML` is safe here (app-owned static, escaped/allowlisted —
audit PASS). The **first draft was generated by Codex** (token-saving) then reviewed against the real code
and shipped. Groundwork for the inc-60 AI help assistant (`help_corpus_prompt()` is defined; its references
will reuse `flashHelpSection`). New convention: a **`HELP-DOCS-SYNCED` marker** in `.claude/changes.md` +
a Session-kickoff check so future sessions can tell from the changelog whether the corpus needs updating.
pytest **210** (+7); live E2E (`.local/help_e2e/`) — 22 sections, TOC scroll+flash, 0 console errors; audit
`.claude/security-audits/2026-06-19_help-corpus.md` PASS. NEXT (after the user reviews the in-app docs):
**increment 60** — the AI help assistant (`POST /help/ask`, its own `CALLOSUM_HELP_ASSISTANT_ENABLED` gate
via the inc-58 seam pattern, references → `flashHelpSection`). Other backlog unchanged.

Earlier — increment 58 (provider-agnostic egress gate at the DI seam): moved
data-egress enforcement (invariant #3) from per-provider self-checks **by convention** to a
**provider-neutral gate applied at the dependency-injection seam**, closing the hole where a provider
injected via `create_app(...)` was returned **unchecked**. New `app/backend/llm/egress.py` is the
**canonical home** of `DataEgressDisabledError` (re-exported from `integrations/gemini/generator.py`, so
every existing import path resolves to the same class) + three wrappers
(`EgressGated{SummaryGenerator,AxisTermSuggester,AxisClusterLabeler}`) conforming to the existing
protocols; the three router factories (`_summary_generator`, `_axis_term_suggester`,
`_axis_cluster_labeler`) now resolve the inner provider (injected or default Gemini) and return it
**wrapped** with the `GeminiConfig.from_environment().data_egress_enabled` flag. Egress-on → delegate
unchanged (real Gemini path identical); egress-off → same `DataEgressDisabledError` (summaries job
`error`; suggest-terms 503 via the unchanged handler; labeler → `apply_labels` local fallback, never
503). Providers keep their internal checks as **defense-in-depth**. Tests model consent via an autouse
conftest fixture (`CALLOSUM_ALLOW_DATA_EGRESS=1` by default; egress-off tests `delenv`). No migration, no
new route, no API-shape change; backend-only (no frontend rebuild). pytest **203** (+4: hole-closed +
behavior-preserved across generator/suggester/labeler); audit
`.claude/security-audits/2026-06-19_egress-gate-seam.md` PASS. Also swept 25 stray `*.tmp.26380.*`
atomic-write orphans from a crashed earlier process. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` —
library **merge** (last, destructive — needs design forks), terms-as-first-class; DESIGN.md `.btn-*` DRY;
embedding-text JATS cleanup; permanent-delete/empty-trash; persistent dedup-dismiss. (`axes.py` is at 586
lines — a split watch candidate.)

Earlier — increment 57 (always-on Synthesis + contextual Details split, backlog F): the
right pane stopped being **tabbed** (Synthesis | Detail) and became a **vertical split** — Synthesis always
on top, and when a paper is selected its editable **Details** appear in a lower section with a **draggable
divider** between them (height persisted to `localStorage["callosum.detailH"]`). Reuses the inc-42 resizer
(`_beginDrag` now passes clientX **and** clientY; horizontal side callers use x, the vertical split uses y).
`RightPane` (`20_synthesis.jsx`) rewritten + dead `.pane-tabs` removed; `SynthesisPane`/`DetailContent`
unchanged; Details aren't mounted when nothing is selected (Synthesis fills the pane). Frontend-only; pytest
199 (unchanged); live E2E (`.local/synthesis_split_e2e/`) — no-paper→synth only, paper→both, drag resizes +
persists across reload, 0 console errors; no audit gate.

Earlier — increment 56 (duplicate detection, flag-only, backlog E): a **"Duplicates"**
scan (library head, next to Trash) surfaces likely-duplicate paper groups for review. New
`app/backend/clustering/duplicate_detection.py` `find_duplicate_groups`: **layered** signals — shared
`csl_json` PMID/arXiv (DOI can't collide, UNIQUE) → identical canonical title+author+year → embedding
cosine ≥0.92 (high, so not same-topic; reuses axis_suggestion's in-memory numpy) — merged by **union-find**
into groups with a confidence + reason. Async `POST /papers/duplicates` + `GET /papers/duplicates/{job_id}`
(mirror `/axes/suggest`; registered before `/papers/{paper_id}`); entirely **local** (no egress); **ephemeral**
+ **flag-only** (never auto-deletes/merges). The review modal (`19_duplicates.jsx`) resolves a group by
**deleting** the redundant copy (reuses the inc-54 soft-delete → Trash, reversible), open, or session-only
dismiss. pytest 199 (+9: 7 unit layers/union-find/trashed + 2 endpoint); live E2E
(`.local/duplicates_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-19_duplicate-detection.md`
PASS. **Deferred:** library **merge** (the real consolidation, last); **persistent "not a duplicate"**
dismiss. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — synthesis split (F), terms-as-first-class, library
merge (last); DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup; permanent-delete/empty-trash.

Earlier — increment 55 (fix: strip JATS from the editable abstract + suggest terms):
raw Crossref JATS XML (stored in `papers.abstract` per inc-33) was leaking as `<jats:p>` tags in the inc-49
editable abstract **textarea** and as the term **"jats"** in **suggest-optimal-axes** (the c-TF-IDF
tokenizer). One shared fix: new **`abstract_plain_text(raw)`** (`metadata/abstract_display.py`, a tag-free
sibling of `clean_abstract_for_display`) feeds both — a new `PaperDetailResponse.abstract_text` (the
textarea binds to it) and `axis_suggestion._paper_tokens` (strips JATS before counting terms). Display-only
(stored column untouched; editing the textarea writes the user's plain text). **Deferred:** the abstract's
JATS noise in the *embedding text* (`paper_embedding_text`) — cleaning it needs a `PAPER_TEXT_VERSION` bump
+ a full re-embed. pytest 190 (+7); live E2E (`.local/jats_fix_e2e/`) 0 console errors; no audit gate.
NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — dedup (E), synthesis split (F), library merge (last),
terms-as-first-class; DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup.

Earlier — increment 54 (library delete: soft + multi-select + Trash/Restore, backlog D):
the first way to delete a paper. Checkbox multi-select + a bulk-delete bar (mirrors the inc-43 axis pattern)
→ **soft-delete** (`papers.deleted_at`, migration 0004): hidden from the library/axes/clustering but kept,
with a **Trash ⇄ Library** toggle + per-row **Restore**. Soft because a **hard** delete is unsafe today —
`embeddings.target_id` has no FK + the vector store has no delete method, so it orphans the paper's
embeddings/sqlite-vec vectors and an orphaned paper-embedding crashes `retrieval._resolve_hit`; true
permanent-delete / empty-trash (with vector cleanup) is **deferred**. `DELETE /papers/{id}` (soft, 404 if
missing/already-trashed) + `POST /papers/{id}/restore` + `GET /papers?deleted=true`. `repository`:
`soft_delete_paper`/`restore_paper`, `list_papers(only_deleted=…)`, cluster-node + suggest exclude trashed;
`get_paper` unfiltered (Restore/detail resolve by id). Frontend `40_app.jsx` + `10_pdf_layer.jsx` (the three
row modes normal/focus/trash are mutually exclusive). pytest 183 (+4); live E2E
(`.local/library_delete_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-19_library-delete.md`
PASS. Deferred (noted): permanent-delete/empty-trash + excluding trashed papers from new synthesis retrieval.
NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — dedup (E), synthesis split (F), library merge (last),
terms-as-first-class; DESIGN.md `.btn-*` DRY.

Earlier — increment 53 (polish pass): four deferred quick wins, frontend-only. (1)
**SRI** — `integrity` sha384 + `crossorigin` on the React/ReactDOM/Babel CDN `<script>`s in `index.html`
(hashes from the immutable cdnjs files; the live E2E rendering under them is the proof they're correct;
pdf.js is loaded dynamically so left as-is). (2) **Radius scale** — `--radius-sm/-lg/-pill` tokens added
(DESIGN.md §3 #6); the clean pill (`999px`/`20px`) + modal (`12px`) values migrated; the messy middle
(4/5/6/8/9px) + the `.btn-*` class DRY left as §3 worklist items (too value-shifting to bundle mid-use).
(3) **In-app HELP viewer** — a **?** button in the sidebar header (top-left, mirroring ⚙) opens
`HelpModal` (`18_help.jsx`) with the axes/tiers tips from `.claude/HELP.md`. (4) **Favicon dark-swap** —
two `media="(prefers-color-scheme:…)"` favicon links (light `favicon.png` / dark `favicon_dm.png`) so the
tab icon follows the **OS** scheme with no JS (trade-off: OS, not the in-app toggle); `inline_brand_assets.py`
now maintains both. pytest 179 (unchanged); live E2E (`.local/polish_e2e/`) 0 console errors; no audit gate.
NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — library multi-select + bulk delete (D, destructive → needs a
soft-delete/undo decision + plan), dedup (E), synthesis split (F), library merge (last), terms-as-first-class;
DESIGN.md `.btn-*` DRY + full radius consolidation.

Earlier — increment 52 (suggest optimal axes): a **✨ Suggest** button mines the
library's own embeddings to propose a *diverse* set of candidate axes that **blanket the literature without
duplicating each other or the user's existing axes**, then the user curates (rename + toggle term chips,
selected-by-default) and creates the ones they like. New `app/backend/clustering/axis_suggestion.py`:
in-memory clustering (`AgglomerativeAbstractClusterer`) → **novelty filter** (drop clusters ≥0.6 cosine to an
existing axis) → **MMR-lite diversity** (skip ≥0.5-similar clusters) → **local c-TF-IDF labels**;
`apply_labels` adds optional **egress-gated Gemini polish** (`integrations/gemini/axis_cluster_labeler.py`,
sends only representative titles) that **falls back to local on any failure — so the endpoint never 503s**.
Async `POST /axes/suggest` + `GET /axes/suggest/{job_id}` (mirror the score job); frontend chunk
`17_axes_suggest.jsx`. Suggestions are ephemeral — creation goes through the existing `POST /axes`. **NO
migration, no new dependency** (numpy/sklearn already present). pytest 179 (+5: clusters/novelty/labeler/
egress-off-local/too-few); live E2E (`.local/suggest_axes_e2e/`, fake model, no network) 0 console errors;
audit `.claude/security-audits/2026-06-19_suggest-axes.md` PASS. NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — library multi-select + bulk delete (D, destructive → soft-delete/undo
decision + plan), dedup (E), synthesis split (F), library merge (last); favicon dark-swap; DESIGN.md
`.btn-*` DRY; HELP viewer; SRI.

Earlier — increment 51 (B′: eyeball toggle to hide/show UNCERTAIN papers): a small
follow-on to inc-50's axes UX. `AxisItem` gains a per-axis **👁** toggle (in the re-score row, shown only
when the axis has ≥1 uncertain paper) that filters the list to an **assigned/manual-only** view; a subtle
"N uncertain hidden — show" hint restores them. Pure display filter — frontend-only (`15_axes.jsx` 344,
`styles.css`), no backend/endpoint/migration. pytest 174 (unchanged); live E2E (`.local/eye_e2e/`) 0 console
errors; no audit gate. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — suggest-optimal-axes, library
multi-select/bulk-delete (D, destructive → needs a soft-delete/undo decision + plan), dedup (E), synthesis
split (F), library merge (last).

Earlier — increment 50 (axes manual-assignment cleanup + library focus-mode, backlog B + C):
the axes panel's manual-override UX. **B:** the redundant "ASSIGNED" tag is gone (assigned = no tag, just
the confidence; amber = uncertain; dashed = manual/human), and a **✓** on uncertain rows promotes a paper to
a manual override. **C:** the per-axis **＋** opens a **library focus-mode** — a reminder card above the
search bar + per-row **+add / ✓ in axis / ✓ staged / − staged** buttons — **staged and committed on Save**
(replacing the inc-38 in-card `AddPaperPicker`). Underpinned by two `axis_scoring.py` correctness fixes so
**`confidence IS NULL` (= manual) is authoritative + durable**: `add_manual_assignment` upserts a scored row
to NULL (the confirm), and `restore_manual_assignments` forces NULL even when present (survives re-score;
also fixed a latent revert-on-re-score bug). Frontend: `15_axes.jsx` (332, AddPaperPicker removed),
`10_pdf_layer.jsx`, `40_app.jsx` (focus state + `axisRefresh` nonce), `styles.css`. **NO new
endpoint/route/migration/egress** — ✓-confirm + focus Save reuse `POST`/`DELETE /axes/{id}/papers`. pytest
174 (+2); live E2E (`.local/axes_manual_e2e/`, fake model) 0 console errors; audit
`.claude/security-audits/2026-06-19_axes-manual-assignment.md` PASS. NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — B′ eyeball (hide UNCERTAIN), suggest-optimal-axes, library
multi-select/bulk-delete (D), dedup (E), synthesis split (F), library merge (last).

Earlier — increment 49 (editable Details pane + DOI correction / re-resolve, backlog G):
the Detail pane is now a Mendeley-style **always-editable** bibliographic editor (inline fields, "Add …"
placeholders, **auto-save on blur**, Literature Type dropdown, large editable title, collapsible
**Identifiers**, a **More** section that auto-surfaces extra DOI-populated scalar fields, a **Files** list,
honest provenance footer). A wrong/missing **DOI can be corrected and re-fetched from Crossref** (🔎). New:
`app/backend/metadata/paper_edits.py` (`build_paper_update` — safe partial csl_json merge + column
projection, the linchpin: edits a copy, writes only changed columns → never wipes the record); `PATCH
/papers/{id}` (DOI-UNIQUE clash → 409; empty title/no fields → 422) + `POST /papers/{id}/re-resolve`
(force past the user-edited guard; Crossref miss → graceful 200); `enrichment.USER_EDITED_SOURCE` (NOT in
the can-update allowlist → batch enrich won't clobber hand-edits) + a `force` flag; `create_app(crossref_client=…)`
injectable. Frontend chunk `25_detail.jsx` (DetailContent moved out of `20_synthesis.jsx`; `onOpenPaper=openPdf`
threaded for the Files list). **NO migration** — `csl_json` is the canonical record; scalar columns are
projections. pytest 172 (+22: `test_paper_edits.py` unit + PATCH/re-resolve integration + route surface);
live E2E (`.local/detail_edit_e2e/`, fake Crossref) 0 console errors; audit
`.claude/security-audits/2026-06-19_paper-edit-doi.md` PASS. Deferred (noted): per-attachment PDF serving
(Files opens the primary today — lands with duplicate-merge), multi-URL, Translator(s), a "More" add-field
menu. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — tier-tag ✓-confirm, B′ eyeball, library
multi-select/dedup/merge, suggest-optimal-axes.

Earlier — increment 48 (sidebar density + cutoff acts on displayed precision):
finished the **B″ density** pass — dropped the "local reference workbench" subtitle, added an axis
**filter** (`Filter axes…`, matches title or terms), turned "+ new" into a green **"+"** (`--verified`),
all on one no-wrap controls row (`Filter… · sort ▾ · +`) so more axes are visible. Also a **rounding fix**
(`_confidence_from_cosine_distance` now `round(…,2)`): confidences are stored/compared at the 2 decimals
the UI shows, so a paper displayed as "0.35" can't be tagged UNCERTAIN because its raw score was 0.349
(user-caught). Frontend-only density + a 1-line backend round; pytest 150; live E2E (`.local/density_e2e/`)
0 console errors. **B″ is now complete** (with inc 47's connection-in-logo). NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — favicon dark-swap, DESIGN.md `.btn-*` DRY + radius scale, HELP
viewer, terms-as-first-class, tier-tag ✓-confirm, B′ eyeball (hide UNCERTAIN), library focus-mode/
multi-select/dedup/merge, synthesis split + editable Details + DOI re-search, suggest-optimal-axes, SRI.

Earlier — increment 47 (connection status shown by the logo): retired the textual
`● connected · local-verifier-v1` line; the **brand logo now carries the signal** — a green dot in the
brain's cell-body when connected — using the user's `logo_on`/`logo_dm_on` assets. Implemented as a
**4-state CSS `background-image`** (theme × a `.connected` class): four `--logo-*` tokens in `styles.css`
`:root` hold the base64 (**kept in CSS, not the Babel script** — 4 logos there would blow its 500KB deopt
cap). `.brand-logo` is now a `<div>` (removed the inc-46 two-`<img>` toggle); `ConnStatus` + the `.conn`/
`.led` CSS removed; the "local reference workbench" subtitle kept (its removal is a separate B″ item).
Losslessly recompressed `logo_on`/`logo_dm_on` (423KB→57KB); `inline_brand_assets.py` repointed to the 4
CSS tokens. Frontend-only; pytest 149 (unchanged); live E2E (`.local/conn_logo_e2e/`) 0 console errors;
no audit gate. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — **B″ remaining** (drop the subtitle +
verifier text entirely, axis **filter** field, "+ new" → green "+", single no-wrap row); then favicon
dark-swap, DESIGN.md `.btn-*` DRY + radius scale, HELP viewer, terms-as-first-class, tier-tag ✓-confirm,
library focus-mode/multi-select/dedup/merge, synthesis split + editable Details + DOI re-search,
suggest-optimal-axes, SRI hardening.

Earlier — increment 46 (DESIGN.md token consolidation + dark mode + Settings modal):
finished DESIGN.md's color-token consolidation (scattered hex → tokens; split destructive color reconciled
to a new `--danger`) — the groundwork for a **warm-dark theme** via `:root[data-theme="dark"]` CSS-variable
overrides. `data-theme` is set on `<html>` by a **no-flash bootstrap** `<script>` in `index.html`'s head
(localStorage/`prefers-color-scheme`); toggled in a new **Settings modal** (`35_settings.jsx`) opened by a
**gear icon** in the sidebar. The **rendered PDF page stays light** in both themes (only chrome themes);
`--on-fill` flips so text stays legible on the now-light semantic fills; the brand logo CSS-swaps to
`logo_dm.png` (losslessly recompressed 427KB→57KB so the inline Babel script stays under its 500KB deopt
cap). **Any CSS change must read `.claude/DESIGN.md` (rule #8).** Frontend-only; pytest 149 (unchanged);
live E2E (`.local/dark_mode_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-19_dark-mode-settings.md`
PASS. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — DESIGN.md §3 worklist remaining (`.btn-*` DRY +
radius scale), favicon dark-swap, **B″ sidebar density** (+ connection-in-logo), HELP viewer,
terms-as-first-class, tier-tag ✓-confirm, library focus-mode/multi-select/dedup/merge, synthesis split +
editable Details + DOI re-search, suggest-optimal-axes; hardening: SRI on the CDN scripts.

Earlier — increment 45 (adjustable assignment cutoff + axis-card redesign): the
assigned/uncertain badge is now an **absolute cutoff** (default 0.35), **per-axis, persisted**
(`axes.scoring_gain`; migration 0003, additive + auto-applied on startup) and **user-adjustable** via a
"Cutoff" flipper on the Re-score row — superseding inc-39's relative natural-break, which assigned only
the top 2–6 papers (the largest gap sits near the top of real axes' smooth similarity declines). Axis
cards redesigned: ✎/＋/🗑 icon buttons (＋ auto-expands + opens the add-paper picker; ✎ does NOT expand) +
a circular **red count badge**; Re-score is the lone in-list control. The relative-tiers tip moved to
`.claude/HELP.md` (in-app help viewer deferred). `_axis_text` unchanged; existing axes re-tier at 0.35 on
read with NO re-score needed. pytest 149; live E2E (`.local/axis_gain_e2e/`) 0 console errors; audit
`.claude/security-audits/2026-06-19_axis-gain.md` PASS. `axis_scoring.py` 588, `axes.py` 466,
`15_axes.jsx` 378. NEXT: the running to-do list **`.claude/docs/INCREMENT-BACKLOG.md`** (guiding
principle: *reference manager first*) — queued: in-app HELP viewer, Settings (cutoff default +
light/dark), terms-as-first-class, **B′ eyeball toggle** (hide/show UNCERTAIN), tier-tag ✓-confirm (B),
library focus-mode (C), suggest-optimal-axes, library multi-select/dedup/merge, synthesis split + editable
Details + DOI re-search. Open proposals: undo/soft-delete, filter-library-by-axis.

Earlier — increment 44 (axis edit modal + title/term decoupling + click-to-open; backlog
A + A′): one **Edit Axis modal** (`14_axes_edit.jsx`) for create/edit/term-search — the **title is now a
cosmetic display name** and the *search vocabulary* is a curated terms list stored in the description's
`Related:` block (primary term first). `_axis_text` embeds the **description only** (label fallback; no
migration) so the title no longer pollutes the query; existing axes show stale → re-score once. Suggested
terms arrive **deselected** (selected sort to top — human-in-the-loop). "+ new" = a quick inline name →
prefilled modal. Removed the inline create/edit forms, the inc-41 terms modal, the standalone "suggest
terms" action, and the per-axis `.axis-desc` preview (terms live only in the modal). **A′:** clicking an
axis-listed article opens its PDF (`onOpenPaper` threaded App→Sidebar→AxesPanel). pytest 147 (+2: scoring
keys on description not label; label-only fallback); live E2E (`.local/axis_edit_e2e/`) 0 console errors;
audit `.claude/security-audits/2026-06-19_axis-edit-modal.md` PASS (no new endpoint/egress/ingestion).
`15_axes.jsx` 448→357, new `14_axes_edit.jsx` 102. NEXT: the running to-do list
**`.claude/docs/INCREMENT-BACKLOG.md`** (guiding principle: *reference manager first*) — A + A′ now done;
next is **B** (tier-tag cleanup: remove the ASSIGNED tag, ✓-confirm uncertain papers) + **C** (library
focus-mode manual add), then suggest-optimal-axes (now safe against the finalized axis model); then library
multi-select + bulk delete, AI dedup (after **G** = editable Details + DOI re-search), always-on synthesis +
contextual Details, settings + light/dark; library **merge** deferred to last (free-form). Open proposals:
undo/soft-delete, filter-library-by-axis.
Earlier — fix (2026-06-19, post-inc-44): an axis could show "re-score" forever after a merge —
`axis_score_state` judged freshness from the newest embedding row by id, but `_embed_axis` accrues one
row per scored text version (never pruned), so a merge/edit cycle revisiting a prior version left a stale
higher-id row above the matching one. Now fresh if ANY stored embedding matches the current text
(self-heals on read; no re-score needed). Also restored the 600-line cap (`_axis_text`'s inc-44 comment
had pushed `axis_scoring.py` to 603 → 598). pytest 148.
Earlier — increment 43 (axis management): sortable ordering (name / paper count / newest),
checkbox multi-select with a bulk-action bar (delete N, or merge ≥2), and a **merge** that folds axes into
one surviving axis via a comparison/curation view (`16_axes_merge.jsx`) — each folded axis's label carried
into the survivor's `Related:` terms so a re-score keeps its papers discoverable; manual assignments
unioned, survivor auto-re-scores. New `app/backend/clustering/axis_operations.py` (`merge_axes`); `POST
/axes/merge` + `created_at` on `AxisResponse` (no migration). pytest 145; audit
`.claude/security-audits/2026-06-19_axis-merge.md` PASS.
Earlier — increment 42 (resizable + collapsible side panels): the `.app` grid's side
columns are React state with drag-grip resizers + chevron collapse toggles (a `Divider` between each side
panel and the center); the center PDF/library area expands as a side collapses; layout persists to
localStorage. Frontend-only (`40_app.jsx` + `styles.css`, rebuilt `callosum-app.html`); removed the old
narrow-screen media query. pytest 143 (Python untouched).
Earlier — increment 41 (Gemini axis synonym suggester): optional AI assist to broaden
niche axes. New `integrations/gemini/axis_terms.py` (`GeminiAxisTermSuggester`, mirrors the summary
generator) + `POST /axes/suggest-terms` (sync, stateless, **egress-gated** — off → 503 before any genai
call; other failure → 502). The user curates suggested terms in a new modal (`15_axes.jsx`); chosen terms
fold into the axis description (re-score to apply) — no migration. Untrusted model output is
deduped/capped/echo-stripped; suggester injectable for hermetic tests. pytest 143 (+3); live E2E +
security audit PASS. NEXT (queued, per the user): resizable/collapsible panels → axis-management tree
(sort + multi-select + bulk delete/merge) → suggest-optimal-axes (unsupervised + coverage-with-diversity).
Earlier — increment 40 (axis punctuation normalization): axes differing only in
punctuation/spacing scored differently ("anomalous-is-bad" vs "anomalous is bad") because `normalize_text`
keeps punctuation and MiniLM tokenizes them differently. New `strip_punctuation` util
(`embeddings/models.py`) is applied to the axis text before embedding + text-versioning (`_embed_axis` +
`axis_score_state` in `axis_scoring.py`), so equivalent phrasings produce an identical axis embedding.
Axis-side only (no paper re-embed, no migration, no frontend). pytest 140 (+2). Users re-score punctuated
axes once (they show stale). NEXT: Gemini synonym-suggestion modal (egress-gated, user-curated) to raise
recall on niche axes.
Earlier — increment 39 (axis scoring calibration): inc-38's absolute thresholds
(assigned ≥0.7 / uncertain ≥0.5) assigned NOTHING on real data — `all-MiniLM-L6-v2` axis-vs-paper-metadata
cosine maxes ~0.37 (median 0.02), though the ranking is correct. Replaced with **natural-break relative
tiering**: new `assignment_mode="natural_break"` + `SUPERVISED_AXIS_CONFIG` (noise floor 0.2, minimum_gap
0.03) — assigned = the cluster above the largest gap in the axis's ranking, uncertain = the rest of the
eligible, never-empty fallback. Tiers recomputed on read from stored confidences (`natural_break_assigned_ids`)
→ no migration, read == score. The 0.2 floor is a documented MiniLM constant. pytest 138; real-data check +
live E2E green. Users must re-score axes scored under the old logic. `axis_scoring.py` 595 (<600).
Earlier — increment 38 (Axes increment 1: create/browse/score/correct user-defined
axes): exposed the existing `app/backend/clustering/axis_scoring.py` engine as write endpoints + an
AxesPanel UI (`app/frontend/js/15_axes.jsx`). New on the axes router: `POST /axes`, `PATCH`/`DELETE
/axes/{id}`, async `POST /axes/{id}/score` + `GET /axes/score/{job_id}` (mirrors the summarize job;
fully local, no egress), `POST`/`DELETE /axes/{id}/papers` (manual override). Scoring uses
`assignment_mode="absolute"` → assigned ≥0.7 / uncertain ≥0.5 / below-threshold (not stored). NO
migration: manual-vs-scored = `confidence IS NULL` vs float; staleness via the axis embedding's stored
`source_text_version` + `normalization`. Re-score preserves manual adds. Sidebar Axes panel is now
create/browse/correct (was read-only). pytest 136 (route-surface updated); hermetic fake-model tiers +
live browser E2E (create→score→tiers→manual-add, 0 console errors). Supervised single-lens only;
unsupervised/synthesis-scope/multi-pole deferred. Audit:
`.claude/security-audits/2026-06-17_axes-supervised.md`.
Earlier — increment 37 (modularize the monolith files): behavior-preserving split
of the oversized files to satisfy the 600-line rule and enable directed reviews. `app/backend/api/app.py`
1108→113 (thin factory + `routers/{health,papers,annotations,axes,summaries}.py` + `startup.py` +
`dependencies.py`; only logic change: `/summarize*` read the job store via `request.app.state`).
`pdf_processing/extraction.py` 662→555 (+`quote_matching.py`). `tests/test_api.py` → `conftest.py` +
`api_helpers.py` + per-resource `test_*.py`. `tools/validation_harness.py` 1298→898 (report
dataclasses + markdown renderer → `tools/validation/`; probes stay — exempt). `callosum-app.html`
2023 → modular `app/frontend/` assembled at serve time into one document at `/` (no build step, no new
file-serving surface; JSX concatenated into one `<script>` so shared scope is unchanged); old file
deleted. No file under `app/`/`integrations/` now exceeds 600 (largest `extraction.py` 555). pytest 129
(route-surface invariant green); inc-36 E2E green vs the assembled frontend (reload-drift 0.0px, 0
console errors). Audit: `.claude/security-audits/2026-06-17_frontend-assembly.md`.
Earlier — increment 36 (synthesis → annotation bridge, suite C): a verified,
exact-coordinate synthesis citation can be saved as a durable `source="synthesis"` annotation.
`POST /papers/{id}/annotations` now accepts an optional `source` (allowlist-validated against
`NATIVE_ANNOTATION_SOURCES`, forged → 422; defaults `"user"`) — no new route, no migration. A
"Save as highlight" control on each citation card is enabled only for exact+verified citations and
otherwise disabled-with-tooltip (honesty contract); saved synthesis highlights render with a distinct
dashed `.pdf-synthesis-outline` and appear live in an open viewer via an `annoRefresh` nonce (no
reload). pytest 129; headless E2E: gating proof + reload-drift 0.0px + 0 console errors. See
`.claude/security-audits/2026-06-17_synthesis-source.md` + `INCREMENT-36-NOTES.md`.
Earlier — increment 35 (multi-line highlight compositing): fixed the darker
interior band by flattening each annotation's per-line rects into an isolated per-annotation group
(opaque fills union without doubling) that composites once via multiply (opacity 0.7) — uniform on
every row, text-legible. No geometry change; reload-drift 0.0px; gap-row luminance spread ~2.4 across
the page. Frontend-only; pytest 126.
Earlier — increment 34 (PDF text-layer alignment): fixed progressive text-layer↔
canvas drift by single-sourcing the scale (exact un-floored CSS dims for canvas/text/overlays),
device-resolution canvas backing (DPR-aware), and removing responsive shrink; added a matchMedia
DPR-change re-render. Bottom-of-page drift −7.97px→−0.20px; highlight reload-drift 0.0px at
50/75/115/195% + dpr2. Frontend-only; pytest 126.
Earlier — startup auto-migration is now loud (INFO check / WARNING "auto-migrated
X→Y" / INFO "already at head" / ERROR-but-non-fatal on failure, on stdout via a `_loud()` helper that
survives Alembic's `fileConfig`), and `/health` is honest (`db_migrated` = at-head, plus
`db_revision`/`db_head_revision`). No schema change; env.py untouched. pytest 126.
Earlier — increment 33 (clean JATS abstracts): Crossref abstracts stored raw as
JATS XML now render structured in the Detail pane via a new allowlisted-HTML transform
(`clean_abstract_for_display`) exposed as a derived `abstract_display` field; raw `abstract` and the
stored column are untouched. App's first `dangerouslySetInnerHTML` (allowlisted output only; audited).
No schema change. pytest 122.
Earlier — fix: highlight-create 500'd on stale `.local` DBs missing the
`annotations` columns (never run through migration `0002`). The app now **auto-migrates the
configured DB to head on startup** (lifespan), the frontend **surfaces API errors** (toast +
console.warn) instead of swallowing them, and all existing `.local/**/validation.sqlite` were
migrated. No schema change (head stays `0002`). pytest 113.
Earlier — increment 32 (branding): brain `logo.png` shown before the "Callosum"
wordmark + `favicon.png` wired, both inlined as base64 `data:` URIs from `app/media/` (no new
file-serving surface). Pure frontend; pytest still 113.
Earlier same day — increment 31 (annotation notes + management panel): `note` now
writable via the project's first update endpoint `PATCH /annotations/{id}` (note/color only,
note capped 4000) + `note` on create; a collapsible in-viewer panel lists/edits/deletes/jumps-to
annotations; note indicator on commented highlights. No migration (the `note` column already
existed). See `.claude/security-audits/2026-06-16_annotation-notes.md` + the decision-log row.
Earlier same day — increment 30 (annotation highlights): first user-authored data +
first mutating endpoints. Extended the `annotations` table (now shared across imported/user/
synthesis via a `source` discriminator) and added `POST/GET /papers/{id}/annotations` +
`DELETE /annotations/{id}`; see the decision-log rows + `.claude/security-audits/2026-06-16_annotations.md`.
Earlier same day — initial authoring, adapted from the renovatr / rubberhead / clffwrkmn CLAUDE.md
house style and customized to callosum (local-first Python reference manager): dropped all
web-deploy machinery; added the citation/coordinate honesty invariants, the egress gate, the
increment workflow, and the zip-snapshot backup model.*
