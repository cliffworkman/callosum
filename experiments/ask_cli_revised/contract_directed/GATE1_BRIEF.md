# Gate 1 brief: contract-directed pilot (c5, c6, c9, c10, c11)

Prepared 2026-09-26. **Nothing live has run.** No Qwen was launched, the shared Ollama was never contacted (the offline
suite and the deterministic dry-run ran with every socket refused), the frozen baseline and library are unchanged (hash-verified
before and after), no parent synthesis exists, and no GitHub issue was touched. Receipts: `callosum-data/contract-directed-slice/runs/pilot-prep-003/`.

## 1. What actually runs, and what differs from the baseline

**Software.** `experiments/ask_cli_revised/contract_directed/` (this branch, off tag `e2e-substrate-v4`). **Model.** Qwen3.5:9b,
thinking OFF, on the isolated Ollama :11435 (digest `6488c96f…`, version 0.34.3), ctx 12288 / temp 0 / seed 42 / num_predict 4096:
the same settings as the baseline child-answer diagnostics. No cloud, no Gemini, no other model.

**Inputs frozen.** The approved contract (question `6e037bab…`, hierarchy `c45630b8…`, model-facing `c1f3be3b…`), a
disposable copy of the frozen library (`4f2e98a5…`), and the baseline `child_evidence_diag` answers.

**What differs from the baseline** (this is the experiment): (1) retrieval uses each child's approved wording only, not the
parent question; (2) papers are read section- and obligation-directed, including each paper's own abstract page, not top-8
chunks; (3) evidence is exact-source packets built by code from model-chosen sentence ids, not machine-written claims judged by
NLI; (4) every packet is checked against every child's obligation units, not only the child whose retrieval found it; (5) one
bounded recovery pass revisits capped neighborhoods, wider context, other sections and other attachments. **What does not
differ:** the child prompt instruction text is byte-identical to the baseline (verified by reproducing all 11 recorded baseline
prompts), same model, same options. The evidence block adds source metadata only (paper, section, page, attachment role,
link/fragment notes); that is a disclosed confound.

## 2. What it can and cannot establish

**Can:** whether the failure cases traced in the baseline (evidence never reaching the neural-relationship children, the scales
child, the cross-cultural children) are repaired by inspecting the right parts of already-nominated papers; whether cross-child
assignment with slot-level, single-finding justification delivers evidence the route-exclusive baseline withheld; whether
attribution and seam rules stop background recitals, speculation and truncated clauses from closing a finding; and how many
calls each stage actually needs.
**Cannot:** anything about generality (one question, one library, one run per arm, no variance estimate); which pipeline
component is responsible (route attribution is descriptive provenance of one union run, not evidence of how a route-exclusive run
would perform); whether an answer is scientifically correct (a human reads it); completeness (always `not_certified`). The
slot judgments are model-made; the mitigations are ids-only output, mechanical status derivation and negative controls.

## 3. Budgets (explicit, computed by code, enforced at run time)

Per child: T=25 triage papers, I=6 inspected papers, **N=18** neighborhoods (= I x (1 abstract page + at most 2 content units)),
R=6 recovery, B=3 bridge (only if triggered), 9,000 chars per neighborhood (max 243,000 chars inspected per child).
**Change from my plan:** N was 12; a paper-major rule with N=18 is what lets each inspected paper contribute its abstract page and
its best neighborhood for each of the child's units without cross-paper score competition. Ceilings were widened accordingly.

| Worst case (model calls) | Pilot (5 children) | Full (11 children) |
|---|---|---|
| S2 triage (children x 25) | 125 | 275 |
| S4 localization (children x (18+6+3)) | 135 | 297 |
| S6 eligibility (unique-packet cap x children; cap 40 / 60) | 200 | 660 |
| S9 answers | 5 | 11 |
| **Worst-case total** | **465** | **1,243** |
| Hard ceilings in the authorization file | 500 calls / 120 min | 1,300 calls / 300 min |

Overflow is recorded, never dropped: `capped_out` (nomination), `budget_capped` (neighborhoods, the first thing recovery
revisits), `not_checked_budget` (packets beyond the eligibility cap, in a fixed priority order), `not_run_budget` (after a ceiling).
Time: my estimate is 45-60 minutes typical, up to about 85 minutes if every cap is hit. Cost: zero cloud credits.
**Stop conditions:** any stage whose NO ANSWER rate exceeds 10% over at least 20 calls; the call or wall ceiling; a library, baseline,
digest or version mismatch. No retries, no fallbacks. Mechanical failure (`no_answer`: capped, unparseable, schema-invalid, failed,
prompt too large) is counted apart from a valid "nothing relevant" (`none_established`) at every stage.

## 4. Pilot inputs

| Child | Frozen contract (approved wording) | Failure case it tests |
|---|---|---|
| c5 | brain areas relate to behaviors, and which kinds | neural-relationship evidence and direction never reached it |
| c6 | brain areas relate to attitudes, and which kinds | same, plus the left-amygdala span |
| c9 | which scales measure the traits (carries the c8 pair requirement) | received no evidence; the named scales exist in Methods |
| c10 | is there any cross-cultural evidence | truncated clause; abstract unused |
| c11 | which cultures, and how measured (carries c10's wording as approved scope) | culture-measure pairing; the exposure qualifier |

Eligibility is checked among these five only, so the parents c4, c8 and the umbrella children c1-c3 are not examined in the pilot.
c11's contract legitimately contains c10's wording as its approved scope, exactly as in the baseline.

## 5. Implemented receipts (all offline, all reproducible)

Per run: `00_run_manifest.json` (code sha, frozen identities, caps, budgets, model, stop conditions, integrity before and after),
`budget.json`, `expectations.json` (pre-registered), `authorization_template.json`, `prepare_summary.json`, and the deterministic
dry-run receipts `01_nominations.jsonl` (every route, rank and score), `04_anchors.jsonl`, `05_neighborhoods.jsonl` (`read` or
`budget_capped`), `05b_seam_states.jsonl`. Live adds `02` triage, `06` localization, `07` packets (exact pieces, locators, per-span
attribution, verified links, attachment identity), `08` eligibility (slot-level, per unit), `09` coverage, `10` recovery, `11` bridge,
`12_answers/` (raw first, diagnostics after), `13` assignment matrix and span overlap, `14` ledger, `15` expectation results,
`16` route attribution, `17` review sheet, `trace_cN.md` (contract to raw answer for one child).

**Offline gates.** 173 tests pass (171 with every socket refused; the 2 deselected are guard-mechanics tests needing a real
socket layer). `ruff format` and `ruff check` clean on the new files. Baseline-prompt fidelity: 11 of 11 recorded prompts reproduce byte
for byte. Library-wide distribution over all 55,287 chunks: 0 invariant failures across 144,993 sentence pieces; of 10,483 candidate
seams, 75.7% verify (95% in line-chunked papers, 74.5% in paragraph-chunked); 4.7% of pieces remain unresolved fragments.
End-to-end sequencing on the real library with a scripted fake model: receipts, cross-child pairing, ceilings, raw-answer
preservation and no parent or sibling leakage all check out.

**Deterministic dry-run on the pilot (before any model).** Every regression-target chunk lies in a neighborhood that round one *reads*:
chunk 34974 (abstract: amygdala response and less prosociality) and 35111 (Discussion: left amygdala) for c5 and c6; chunk 35019
(Methods: Just World Beliefs Scale, Interpersonal Reactivity Index, Three-Domain Disgust scale) for c9; paper 68's abstract page and
its unit-probe neighborhoods for c10 and c11, all from its primary attachment. Unresolved fragments in the read neighborhoods are
17-23 per child (about 4-5%). **Caveat:** c9's chunk was checked during development, so that check is development-informed, not blind.

## 6. Pre-registered expectations (version `gate1-v2-2026-09-26`, frozen before any inference)

Edited at Gate 1 authorization, recorded before inference, never to be changed in response to pilot results (the record, its edit log
and its sha256 are written to every run directory and carried in the manifest).

E1 c5 and c6 receive the two neural spans with closing or partial status, or a receipt names the upstream stage that lost them.
E2 c5's answer states no direction its cited passages lack.
**E3 (edited)** c9 receives the Methods sentence naming the scales (chunk 35019), and BOTH its evidence and its answer carry the
correct **instrument-to-construct pairings**, not merely the names: Just World Beliefs Scale with beliefs about interpersonal
fairness; Interpersonal Reactivity Index with cognitive/affective empathy (perspective taking, empathic concern); Three-Domain Disgust
scale with pathogen-related disgust sensitivity. A scale paired with another scale's construct fails; names without pairings are a
review item, never a pass. Constructs separated from named measures is a human item; no acronym expansion absent from the passages.
The chunk-level part is development-informed, not blind.
E4 c10 and c11 receive complete or explicitly unresolved sentences from paper 68 with the Hadza design and exposure qualifier, primary
attachment preferred, no truncated-clause span eligible.
N1 unattributed statements never close a unit, and the Introduction recital (chunk 34984) never closes a finding.
**N2 (restored)** a suggestion, proposal or speculation about an intervention cannot establish effectiveness. Tested OFFLINE against the
real speculative sentence (U5) and an own-reported outcome; c12 is not in this pilot, so it is **not** reported as a live
intervention-answer result.
N3 every assignment has a slot-level receipt.
**N4 (edited)** no obligation is closed by combining unrelated passages or by independently mentioning its component concepts. A finding
supported across Methods, Results or other sections is permitted only when the **source itself establishes the link** (a definition
acronym, a named measure present verbatim in both spans, an explicit table or study reference), with each exact span, its locator, its
attribution and the linking rationale preserved. Being in the same paper never establishes a relationship. Audited on every closure
(one packet only; every span located and verbatim; core spans own-attributed; every linked span backed by a verified link and used only
in a descriptive slot) plus offline controls.
Integrity (voids the run): hashes, verbatim pieces, unchanged library and baseline, no leakage, raw answers preserved, NO ANSWER rates
reported. A miss is a finding with its upstream cause, not something to patch.

## 7. Decisions and blockers I need from you

1. **Commit authorization.** The package is staged but uncommitted. The pre-commit `line-budget` hook fails on
   `app/frontend/js/20_synthesis.jsx` (615 lines), a file in the frozen base checkpoint that I did not touch. An earlier session used
   `SKIP=line-budget` with your authorization for commit 71114551; I will not reuse that without your word. A live run refuses a dirty
   tree, so this must be resolved (narrow `SKIP=line-budget`, or your alternative) before Gate 1 runs.
2. **Abstract-only evidence (decide before the full run; irrelevant to this pilot).** 11 of 43 nominated papers have no readable
   text. They include two direct intervention studies (papers 83 and 100) that c12 would need, plus unreadable duplicates of
   readable papers (229 of 68; 88 and 230 of 61). Default: evidence must be chunk-anchored, so abstract-only leads are reported in the
   receipts, not cited. The alternative is citable metadata abstracts with a null locator, at a coordinate-honesty cost.
3. **Column-switch continuations are disabled.** A spot-check found about 4 of 12 verified joins wrong; geometry cannot prove them, so
   those seams stay honest fragments. Say so if you would rather accept the risk.
4. **Budget revision** (N 12 to 18, ceilings 500 / 1,300 calls) as tabled above.
5. **Authorization file.** Fill `authorization_template.json` (experiment `pilot-live`) yourself, or tell me to record your
   confirmation of this specific brief; `brief_confirmed` stays false until you do.

## 8. Not done, by design

No live call, no Gate 2, no parent synthesis, no route-exclusive answer comparison (optional add-on, 11 calls, separate approval), no
GitHub issue comments (drafts follow the results, append-only, with contribution-level lineage), nothing pushed.
