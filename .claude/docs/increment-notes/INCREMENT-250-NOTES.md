# Increment 250 — Transparency-signals auditor (backlog #44 increment 1, the Lakens track)

## Implemented

A METHODS **"Transparency signals"** panel — the direct sibling of the statcheck / LMM / meta-analysis auditors —
that reads a paper's extracted text and detects whether it **discloses** 7 open-science artifacts, each `present` /
`not-found` / `not-applicable`. **FLAG-not-ADJUDICATE: it never scores, ranks, or accuses; "not detected" never means
"absent".** Fully local — rule-based (ODDPub/rtransparent-derived), no AI, no egress, no migration, no new dependency.

- **`app/backend/methods/transparency.py`** (NEW pure) — `TransparencySignal`/`TransparencyReport` (the exact
  `MetaCheck` shape: key/label/status/evidence/page/note/explainer/basis) + `detect_transparency(chunks)`. **NO gate**
  (unlike statcheck/LMM/meta): it always returns the 7 checks; the only "off" state is a paper with no chunks (the
  frontend gates the "process a PDF first" message). Self-contained regex helpers (`_rx`/`_chunk_rows`/`_snippet`/
  `_first`/`_has`) + a `_present_or_absent(patterns…)` matcher. No I/O, no LLM.
- **`app/backend/api/routers/transparency.py`** (NEW) — `GET /papers/{paper_id}/transparency` (sync, read-only;
  mirrors `/meta-analysis`; 404 unknown; no chunks → 200 with 7 all-not-detected checks). Wired in `app.py` (import
  after `tags`, `include_router` after the meta-analysis include).
- **`app/frontend/js/08h_methods_transparency.jsx`** (NEW) — `TransparencySection`/`TransparencyPaper`/
  `TransparencyChecklist`/`TransparencyCredit`; `registerPaneSection` id `"transparency"`, order **36** (after
  Meta-analysis reporting, before Review), `hideInReadOnly`; auto-runs when its section is open (the statcheck
  pattern). Reuses `.bayes-check-*` / `.method-credit` / `.lmm-*` — **no new CSS**.

**The 7 detectors:** (1) data availability (statement and/or a repository link — OSF/Zenodo/Dryad/figshare); (2) code
/ software availability (statement and/or GitHub/GitLab/Code Ocean); (3) conflict-of-interest statement; (4) funding
statement; (5) protocol/trial registration — **precondition-scoped** to `n/a` unless a trial/registration cue is
present; (6) preregistration; (7) `"Available upon request"` — a weak-signal qualifier, **present** only when the
phrase appears, else `n/a` (never "not found").

## Key technical detail

- **The no-accusation boundary (load-bearing, A-A veto):** an absence of a disclosure must NEVER read as "this paper
  hides its data / has an undisclosed conflict / did no open science". Enforced **structurally** (no score, no rank,
  no verdict field) + **test-pinned** (`test_no_accusatory_language`: no `concealed`/`failed to`/`hiding`/`no open
  data`/`not shared` in any emitted note/explainer; the not-found note carries "not detected in the extracted text").
- **No gate (the difference from the siblings):** transparency has no `is_transparency` gate — every paper gets the 7
  checks; the endpoint response is just `{checks}`. A non-open paper is a legitimate result (all not-detected), not an
  "off" state.
- **Precondition-scoping:** registration → `n/a` unless a trial/registration cue is present (a registration flag on
  every paper is the failure mode); upon-request → `n/a` when the phrase is absent (its absence is the norm, not a gap).
- **FLAG-not-ADJUDICATE:** statuses are only `present`/`not-found`/`not-applicable`; no `score`/`grade` (test); the
  panel tally is a factual status count, explicitly "not a score"; "not found" = "not detected in the extracted text —
  check the paper", never "missing"/"absent" (silence≠certificate).

## Manual verification script

`HF_HUB_OFFLINE=1 python .local/visual/drive_inc250_transparency.py` → "PASS":
- Seeds a paper with an **open footer** (data@OSF / code@GitHub / a COI statement / funding), **no preregistration**,
  and a **non-trial** lab-experiment design. Open METHODS → **Transparency signals** → the section auto-runs → a
  **7-row checklist**: **Data availability / Code / COI / Funding ✓ detected** (basis ODDPub on the data row),
  **Preregistration "not detected"** (note "not detected in the extracted text — check the paper", no banned/accusatory
  strings), **registration + "available upon request" "n/a"** (precondition scoping). The tally reads "4 disclosed · 1
  not detected · 2 not applicable · 7 checks"; a present row's evidence opens its page; the credit ＋add renders.
  **0 console/page errors, 0 genai-host requests.**

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_transparency-signals.md` **PASS** (local read-only over the
  paper in hand; no external fetch/egress/LLM/migration/dependency; anchored regexes, no backtracking; the
  flag-not-adjudicate / silence-≠-certificate / precondition-scoped controls uphold the A-A no-accusation boundary,
  test-pinned by `test_no_accusatory_language`).
- **Principles + A-A gate (rule #9) — aligned** (PRINCIPLES Example 3 / the statcheck-LMM-meta class; the A-A veto-level
  no-accusation boundary is the load-bearing constraint; the misaligned "transparency score / this paper hides its
  data / no open science" verdict declined, along with persisting a "NO open data" fact from an absence).
- **QA (rule #10):** new `route_63_methods_transparency.md` (`api: /papers/{paper_id}/transparency` +
  `fe: 08h_methods_transparency.jsx`) + the honesty assertions; surface **179/179 API + 808/808 FE, 0 uncovered**.
- **Experience pass (rule #11, open-science-vetter persona):** run inline (a near-exact clone of the inc-247/249
  auditors, whose persona-agent passes already surfaced this reception/intended-use and whose in-increment fixes this
  panel inherits — the factual tally + the `lmm-na` de-emphasis of n/a rows). The vetter's need to *rely on a paper* is
  served once the section is reached: the 7-row checklist + tally give the at-a-glance disclosure picture, and each row
  self-explains (in-context basis + explainer). The desire to be declined per #9 + A-A — a "transparency score" to rank
  papers, or to flag authors who "hide data" — is refused structurally. **Filed cross-method to #44 / the shared #23
  chip item:** (F1) an on-paper **"open-science report card" chip** (the panel is buried behind a METHODS section — the
  vetter has to know to open it; the statcheck-inc-141 pattern); (F4) persisting the audit as a findings **candidate**
  (inc 130) so an "open data not detected" review queue / library-wide filter becomes possible; (F2) suppressing the
  methods-credit footer on the metadata-only / not-applicable state (uniform across the LMM/meta/statcheck/bayes/
  transparency siblings).
- **Rule #1:** all new files well under cap (`methods/transparency.py` ~262, `routers/transparency.py` ~53,
  `08h_methods_transparency.jsx` ~186). No migration, no new dependency, no egress, no LLM.

## Pytest

**963 passed, 1 skipped** (+13 hermetic `tests/test_transparency.py`: the full open footer [all present]; exactly-7
checks + order; a bare repo link trips data availability; each detector not-found + the silence-≠-certificate wording;
registration precondition scoping [non-trial → n/a; registered trial → present; unregistered trial → not-found];
upon-request present + n/a; no-verdict/no-score; the no-accusatory-language contract; evidence/basis on a present row;
the endpoint 404 + no-chunks 7-all-not-detected honest-empty). `ruff check` + `ruff format --check` clean; frontend
rebuilt (`test_frontend_assembly` 5/5).

## Notes

`THIRD-PARTY-NOTICES.md` credits the ODDPub / rtransparent / Nosek-preregistration manifest; help corpus gained
"Auditing transparency signals" (`HELP-DOCS-SYNCED` → 250). **The live spot-check on real papers is the maintainer's**
(the regex detection + contracts + a seeded round-trip are proven; per-detector precision/recall on real footers is the
first live read). **This is increment 1 of the Lakens track (#44).** **NEXT within #44:** increment 1b — persist the
detected-present disclosures as **findings-FACTs** (inc 130) + `system:transparency:*` **tags** (the tags↔system-facts
cross-cut, #19) + a library-wide "open data not detected" filter; then increments 2–5 (a `DocumentTextProvider` for
JATS/DOCX/HTML full text so the detectors see the whole paper; a registration-consistency check; a CRediT parser; a
reported-vs-registered consistency registry).
