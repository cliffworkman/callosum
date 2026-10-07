# PHASE 34 / I4-1 - pure assertion-source / assertion-kind classifier: results

Status: **pure, unwired**. The classifier has zero production authority. Nothing in mapping, engine, recovery, relation witness, direction,
effectiveness, ParentClaim, or AnswerPlan imports it. No version constant changed. No model, network, live search, or live end-to-end run.

- Starting HEAD: `70ca0d28` (I2-2), branch `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, worktree
  `.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Final HEAD: the commit that carries this increment (see the handback). The increment is one commit on top of `70ca0d28`.

## 1. Files changed

| File | Change |
|---|---|
| `experiments/ask_cli_revised/assertion_authority.py` | new: the pure classifier |
| `experiments/ask_cli_revised/test_assertion_authority.py` | new: 105-test gate (preregistered, invariants, purity, static guard) |
| `experiments/ask_cli_revised/assertion_authority_preregistered.json` | new: 80 frozen expectations (amended, see §6) |
| `experiments/ask_cli_revised/assertion_authority_holdout.json` | new: 24 frozen adversarial cases (run once) |
| `experiments/ask_cli_revised/PHASE34_I4_1_ASSERTION_AUTHORITY_RESULTS.md` | new: this report |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | appended: Phase 34 / I4-1 section |

Nothing else changed. No `app/`, `integrations/`, frontend, pin, frozen-contract, or version file was touched.

## 2. Pure API

```python
classify_assertion_authority(text, *, target_start, target_end, is_caption=False,
                             structural_context=None, locator=None) -> dict
classify_surface(text, surface, *, occurrence=None, is_caption=False,
                 structural_context=None, locator=None) -> {"ambiguity", "occurrence_count", "results"}
classify_all_occurrences(text, surface, *, ...) -> list[dict]   # every occurrence, never a preferred one
finding_authority(assertion_source, assertion_kind, is_caption=False) -> "authoritative" | "candidate"
durable_locator(paper_id, evidence_anchor_chunk_id, quote_text) -> dict
```

Explicit inputs only. No I/O, no model, no network, no current-version lookup. Stdlib imports only (`__future__`, `hashlib`, `re`,
`collections`), checked by an AST test. Output is JSON-safe and deterministic.

`structural_context` accepts only `{"owner_signal": "this_study" | "prior_work"}`, supplied by a caller that has already verified it.
It is applied only to an unowned governing assertion and is recorded in `structural_context_consumed`. Any other key or value raises.
Nothing in the classifier invents context.

## 3. Output schema (JSON-safe)

- `classifier`: `{id, ruleset, pure, unwired}`
- `input`: `{text_length, text_sha256, target:{start,end,surface}, is_caption, structural_context_supplied, locator}`
- `sentence`: the sentence containing the target
- `assertion`: `{span, text, predicate:{span,text,lemma}, head, subject:{span,text,source,rule,inherited}, object, content}`, or null
- `assertion_source`, `assertion_kind`, `is_caption`, `finding_authority`
- `framing_source` (`prior_work` or null), `framing` (span and text)
- `citation_marked`, `citation_spans`, `hedged`, `negated`, `negated_replication`
- `rule`, `rules_applied`, `ambiguity`, `fail_closed_reasons`, `assertions_considered`
- `structural_context_consumed`

No confidence score. Each axis fails closed on its own: an unowned subject yields `unknown` source, and an unknown predicate yields
`unknown` kind.

## 4. Extraction and attachment rules

1. **Tokenization.** Words, numbers, punctuation, and citation markers. A marker is digits attached to a word of three or more letters, to
   two letters plus `.`, `,` or `)`, or to a single letter plus `.` (so `Y.12` counts; `t11`, `3.26`, and `P < 0.001` do not).
2. **Sentences.** Split at `.`, `!`, `?` when a citation marker and whitespace precede a capital, an opening quote, or an opening
   parenthesis. Abbreviations (`al.`, `e.g.`, `i.e.`, `Fig.`, `vs.`, and others) never split.
3. **Clauses.** Split at `;` and at `, but|although|whereas|while|however|yet`.
4. **Predicates.** A closed verb lexicon (result, replication, method, aim, test, interpretation). Noun uses such as "reports" are not
   predicates, so `earlier reports that X` is not an assertion.
5. **Assertion starts.** The first predicate of a clause starts an assertion. A later predicate starts one only if it is coordinated
   (immediately after `,`, `and`, or `or`, allowing `then`/`also`) or its own subject is an exact owner or a leading external-source noun phrase
   (`and we found`, `and previous studies reported`). A predicate inside a complement is not an assertion.
6. **Subject.** The segment before the head, after the last comma or `that`. Owner means exact: `we`, `our` plus up to two nouns, or
   `this|the|present|current` plus a study noun, with no verb. Prior means a leading external-source noun phrase (`previous|prior|earlier|recent|…`
   plus `study|studies|work|reports|findings|…`, or `Name et al.` or `Name (YEAR)`), with a trailing modifier allowed. Anything else is unowned.
7. **Framing.** Text before the subject's comma. A prior noun phrase there is recorded as `framing_source: prior_work`. Discourse words
   (`Nevertheless`, `Although`) are stripped and never own anything.
8. **Object.** From the predicate to the next separator. A prior construction followed by `that` (`earlier reports that X`) shifts the
   content to X and is recorded as framing. A comparison phrase (`consistent with …`, `contrary to …`) with a prior source after it is framing,
   and the content ends before the comma.
9. **Target attachment.** The target must lie inside one assertion's governed region (predicate through object). A target inside the
   subject, outside any predicate's scope, or crossing the subject and predicate boundary fails closed:
   `target_outside_predicate_scope`, `no_governing_predicate`, or `target_crosses_assertion_boundary`. If several assertions cover a
   whole-passage target and they disagree, the result is `multiple_assertions_disagree` (unknown).
10. **Repeated occurrences.** `classify_surface` without an explicit occurrence returns `repeated_target_occurrence` with the count and no
    result. `classify_all_occurrences` returns each occurrence separately.

## 5. Owner, prior, confirmation, citation, and kind rules

- **Owner (D-A, D-D).** Only the explicit forms above. No participant, patient, student, observer, user, subject, or respondent noun
  appears anywhere in the module (a test scans the constants). An unmarked result stays `unknown`.
- **Prior ownership.** A leading external-source noun phrase (`Previous studies found X`, `Smith et al. found X`, `Smith et al.12 found X`,
  `Previous studies12 found X`). Prior nouns elsewhere in the sentence do not transfer ownership.
- **Confirmation and replication (D-B).** `This study confirmed earlier reports that X`: the act is this study's result, and X is this
  study's result with `framing_source: prior_work`. `We replicated the previous finding that X`: the same. A replication with no prior
  construction in its object has unmarked content, so it is `unknown` (conservative).
- **Failed replication.** `We failed to replicate the previous finding that X` makes X `prior_work` / `result` / candidate, with
  `negated_replication: true`. The content is not confirmed, so it cannot become a positive this-study result.
- **Citations (D-C).** The marker is audit evidence (`citation_marked`). It establishes prior ownership only when it governs a leading
  external-source subject. A marker after an own result (`We found X.12`), a method object (`completed the Beck Depression Inventory.12`), or
  a comparison (`We found X, consistent with Smith et al.12`) changes no owner.
- **Kind.** Aim (`hypothesized`, `tested whether`, `predicted that … would`), method (`measured`, `used`, `completed`, and negated test or
  method forms become `unknown`), interpretation (`suggest`, `propose`, `believe`, and a result predicate under a modal), and result (the
  remaining result verbs). Kind is lexical and does not depend on the owner.
- **Hedging.** `hedged` is audit metadata from a closed hedge set. It does not change kind by itself.
- **Captions.** `is_caption` is a structural flag. It never sets the source, and it forces `finding_authority` to candidate.

## 6. Preregistration, amendments, and the frozen holdout

Both expectation files were written before `assertion_authority.py` existed. The hashes are recorded below.

| File | SHA-256 | Status |
|---|---|---|
| `assertion_authority_preregistered.json` (as first frozen) | `06e3ecd1…b1d834` | scratch copy, kept for the diff |
| `assertion_authority_preregistered.json` (amended, committed) | `5ed2dfcd…3cbd95` | 80 cases |
| `assertion_authority_holdout.json` | `e4fc4ec3…1b42` | unchanged since it was frozen |

**First preregistered run: 74 of 79.** The five failures:

| Case | Failure | Classification | Action |
|---|---|---|---|
| P26 `We found that X predicted Y.12` | `citation_marked` false | **classifier defect**: a marker after a single letter and period was not recognised (`Y.12`) | fixed (one lookbehind alternative: single letter plus `.`) |
| P48 `Figure 2. X predicted Y.` (caption) | target `X predicted Y` crossed the subject and predicate boundary; result was fail-closed unknown | **test-design error** (the target spanned subject and predicate) | target changed to `predicted Y`; expectation unchanged |
| T05 (caption, architecture) | same | **test-design error** | target changed to `predicted occupant satisfaction` |
| T16 (caption, language) | same | **test-design error** | target changed to `predicted vocabulary gains` |
| T09 `Beck Depression Inventory was completed.12` (target in subject) | `citation_marked` expected true | **expectation error**: with no governing assertion for a subject-only target, there is no citation flag | expectation changed to false, with the reason in the note |

One case was added after the first run: **P62**, which records the fail-closed behaviour for a target that crosses the subject and predicate.
All changes are listed here and in the amended file's `note` fields.

**Amended run: 80 of 80.**

**Holdout (24 cases, run once).** Result: **24 of 24 within the frozen acceptable sets; 0 must-not-authoritative violations.** The run was
not repeated and no case was tuned after seeing it. Per-case outcomes:

| ID | Got (source / kind / authority) | Note |
|---|---|---|
| H01 | this_study / result / authoritative | "Our sample showed …" |
| H02 | unknown / result / candidate | "The authors reported …": no owner (conservative) |
| H03 | unknown / result / candidate | framing prior, unowned subject |
| H04 | this_study / result / authoritative | accepted set includes unknown |
| H05 | this_study / result / authoritative | "found no evidence that": negative finding, polarity separate |
| H06 | this_study / result / authoritative | ", but we found": clause split |
| H07 | unknown / result / candidate | negated replication, no prior construction |
| H08 | unknown / unknown / candidate | target in subject |
| H09 | this_study / method / candidate | "reaction times that Smith et al. reported" stays method |
| H10 | unknown / method / candidate | "rated" coordinated, unowned subject |
| H11 | this_study / result / candidate | caption makes it candidate |
| H12 | unknown / result / candidate | "Figure 4 shows that", caption |
| H13 | unknown / unknown / candidate | target in subject |
| H14 | unknown / result / candidate | "replicate prior work on X" has no owner |
| H15 | this_study / result / authoritative | "hypothesized and then found": coordinated finding owns the claim |
| H16 | unknown / result / candidate | "The team measured X and found Y" |
| H17 | prior_work / result / candidate | "We found that Smith et al.12 predicted X": complement subject owns its claim |
| H18 | this_study / result / authoritative | "Previous studies found X, and we found Y" |
| H19 | prior_work / result / candidate | "did not replicate the Smith et al.12 finding that X" |
| H20 | this_study / result / authoritative | "We found X …, but Smith et al. found no effect" |
| H21 | unknown / unknown / candidate | "This study reports": `reports` is not a predicate (false negative, safe) |
| H22 | unknown / method / candidate | "Participants who were assessed showed …" (false negative, safe) |
| H23 | unknown / unknown / candidate | "Our data were consistent with …": no predicate |
| H24 | unknown / result / candidate | "we replicated the effect" with no prior construction |

## 7. Cross-domain results

The preregistered set includes eighteen twins (T01–T18) across architecture, clinical, and language learning. Each was written from its
prototype and frozen before implementation: current result, prior work, prior-framed result, hypothesis, caption, proper-noun trap,
method, prior replication, and interpretation. **All eighteen pass unchanged**, so no domain-specific branch is needed. The shared
`Association` trap (T06, T17) stays `unknown`.

## 8. Preserved-case evaluation (read-only, Attempt2 sealed quotes)

Evaluated against the sealed ledger and the bounded p52 context. Nothing was wired into a map. The I4-0 expectations are compared as
written, and each disagreement is explained. **No classifier change was made in response to these results.**

| Case | Target | Got | I4-0 expectation | Agreement and reason |
|---|---|---|---|---|
| p8 c3 | `explicit` | this_study / result / authoritative | same | agrees |
| p4 c2 | `a behavioral manifestation` | this_study / result / authoritative | same | agrees (described = own predicate) |
| p1 operand X | `negative personality characteristics` | this_study / result, framing prior | same (D-B) | agrees |
| p17 c6 occ1 | `explicit` | this_study / result / authoritative | same | agrees (polarity unknown is separate) |
| p17 occ2 (instrument name) | `Explicit` | this_study / result / authoritative | same | agrees (same owned object) |
| p36 c3 | `explicit` | unknown / result / candidate | candidate | agrees with D-A and D-D |
| p36 c3 | `implicit` | unknown / unknown / candidate | candidate | agrees (no governing predicate) |
| p52 headless quote | `explicit` | unknown / unknown / candidate | candidate | agrees (fail closed) |
| p52 bounded context (not sealed) | `explicit` | unknown / interpretation / candidate; citation true | candidate | agrees on authority; the lexical kind is interpretation (`believe`) |
| p40 c4 prior finding | `certain neuroanatomic structures` | prior_work / result / candidate; citation true | prior candidate | agrees. I4-0's target `implicit` sat in the subject, so the target was corrected. |
| p40 object | `increased amygdala` | unknown / result / candidate; citation true | unknown candidate | agrees (object-end citation is not ownership) |
| p11 c4 | `correlated with` | unknown / result / candidate | unknown candidate | agrees (D-A) |
| p41 c8 | `revealed greater proportionality` | unknown / result / candidate | I4-0 said authoritative via statistics | **disagrees, and the disagreement is the decision.** Reported statistics are not an ownership signal under D-A, so p41 is a candidate. The I4-0 inventory's c8 entry must be corrected. |
| p30 c12 | `produced a clear reduction in implicit bias` | unknown / result / candidate | this_study authoritative | **false negative, from an extraction artifact.** The sentence begins with a run-in heading ("Specificity and generalization of intervention effects We also observed …"), so "We" is not an exact owner. Fail-closed is correct; the heading is not stripped here. |
| p31 c12 | `can help reduce negative implicit biases` | unknown / interpretation / candidate | interpretation candidate | agrees on authority. The source differs from I4-0: the hedged assertion's subject is the exposure, not "our data", so unknown is the faithful answer. |
| p20 c8 | `underpinned by a suite of negative attitudes` | this_study / interpretation / candidate | this_study interpretation | agrees |

## 9. Conservative unknowns (intentional)

- Unmarked results with no owner, including p11 and p36 explicit (D-A, D-D). p36's explicit positive loses authority. c3 explicit still
  holds through p8, so no completion changes.
- Headless fragments (p52 quote). Their authority falls to candidate. The sealed quote carries no citation marker, and the classifier does
  not repair completeness (D6).
- Reported statistics without an owner (p41). This is the largest recall cost in the preserved set, and it is accepted under D-A.
- Verbs outside the lexicon, such as `reports`, `shows` in some forms, and `presented`-type phrasing: false negatives that stay safe.
- Run-in headings before an owner (p30): false negative from an extraction artifact.

## 10. False-positive-looking and false-negative-looking cases (for review)

**Authoritative and worth a second look:**

- P59 and H05: negative findings ("did not find", "found no evidence") are authoritative this-study results. Polarity must carry the
  negation. Authority only says the study made the claim.
- P03 and the p1 operand X: "This research confirmed earlier reports that X" makes X authoritative with framing. This is D-B by decision.
- The p8 and p4 sentence is authoritative for every operand that the coordinated `detected` and `described` predicates own. Whether a
  given binding is directly about its target is a directness question, and it is not decided here.

**Candidate and worth a second look:**

- p41 (statistics only), H21 (`reports` not in the lexicon), H22, and p30 (run-in heading): discussed in §8 and §9.

## 11. Changes after the first run, and why

1. The citation lookbehind now accepts a single letter plus `.` (P26). This was a classifier defect, not an expectation change.
2. Expectations P48, T05, T16, T09 and the addition of P62 (§6). These were test-design errors, corrected transparently.
3. Formatting by `ruff format` and removal of an unused local (`content`). No semantic change. The unused local was found by lint.

No change was made in response to the holdout or the preserved-case evaluation.

## 12. Zero-runtime-change proof

- **Static guard.** `test_classifier_is_unwired_static_guard` scans `app`, `integrations`, `experiments`, `tools`, `tests`, `mcp_server`,
  `tui`, and `sync_server` for any non-test module that mentions `assertion_authority`. The list is empty. The scan is relative to the repo
  root, so it is not vacuous.
- **AnswerPlan replay (Attempt2, current-v4 map).** Seven output files, byte-identical before and after (`answer_plan.json`,
  `answer_plan_audit.json`, `comparison_against_phase29_hand_audit.md`, `deterministic_layer1/2/3.md`,
  `replay_decomposition_authorization.json`). Hashes are in the scratch record.
- **Sufficiency maps (current v4).** `initial_v4` and `final_v4` (lenient, with the known c1 gap), plus the two v3 reconstructions:
  byte-identical before and after. These carry the mapping, the relation witness fields, direction and effectiveness summaries, and
  requirement states, which together cover the mapping, relation, direction, and ParentClaim surfaces that depend on the map.
- **Recovery targets, stop-search, terminality.** Not separately hashed in this increment. They are covered by the experiments suite
  (§13), and they consume only the map, which is byte-identical.
- **Version constants.** `SUFFICIENCY_SEMANTICS_VERSION = sufficiency-semantics-v4` and `PLAN_VERSION = answer-plan-step2-v4`, asserted by a test.

## 13. Test counts and pre-existing failures

- I4-1 gate (`test_assertion_authority.py`): **105 passed**. Includes the 80 preregistered cases.
- Experiments suite, offline (all outbound sockets refused by a scratch launcher; no model or network), run file by file over 140 test
  files: **3029 passed, 11 skipped, 3 failed.** None of the three failures is caused by this increment:
  - `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`: "pin drift:
    `hierarchy_contract.py` changed since the pins were generated". `hierarchy_contract.py` has zero diff against `70ca0d28`, so the stale
    pin predates this increment.
  - `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`:
    exit code 3 is `HierarchyRejected` from the same pin drift (`e2e.py` returns 3 only on `HierarchyRejected` or `AuthorizationRefused`).
  - `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`: it expects the
    runtime build to reach a live Ollama endpoint, and the offline launcher refuses that connection. It is environment-dependent.
  - Excluded: `contract_directed/tools/test_run_gate_integration_live.py` imports `psutil`, which is not a declared dependency. This file
    predates this increment (commit `80467e06`).
- Root `tests/`: not run for this increment. It touches no code under `app/` or `integrations/`, and the static guard covers its import
  surface.

## 14. Lint

`ruff format --check` and `ruff check` pass on both new Python files. The line-budget hook covers only `app/` and `integrations/`. The
pre-commit hook suite runs on this commit; see the handback.

## 15. Recommendation

**READY for I4-2 review, not for implementation.** The classifier is pure, reproducible, and prereg-clean. The holdout passes. The remaining
decisions for I4-2 are the ones §10 and §9 name: the unmarked-result recall cost (c4 region and the c8 statistics case), whether the run-in
heading should be handled upstream, and the R-1 consequence for `c6` explicit that Cliff approved. I4-2 must not start until those are
decided and the offline v4 diff in the I4-0 closure has been reproduced against this classifier.
