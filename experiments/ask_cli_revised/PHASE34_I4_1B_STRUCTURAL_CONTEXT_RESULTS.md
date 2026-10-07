# PHASE 34 / I4-1b — run-in structure and target-span hardening (results)

**Status.** Pure and unwired. Starting HEAD `013364cf`. The I4-1b commit follows it on the same branch. No production module changed.
No sufficiency version bump (`sufficiency-semantics-v4` unchanged), no `PLAN_VERSION` bump (`answer-plan-step2-v4` unchanged).
The classifier's own ruleset string moved from `i4-1.0` to `i4-1b.0`, because its outputs changed. It is not a sufficiency or plan version.
No recovery, relation-witness, direction/effectiveness, AnswerPlan, sealing, frozen-pin, model, network, or live-search change. I2-3 not started. I4-2 not started.

---

## 1. Files changed

| File | Change |
|---|---|
| `experiments/ask_cli_revised/assertion_authority.py` | Repairs A, B, C and the narrow Results resolver (§3–§7). |
| `experiments/ask_cli_revised/test_assertion_authority.py` | Seven I4-1 expectations superseded by the region rule are strict-xfail, each with a reason (§8). Frozen I4-1 JSON not edited. |
| `experiments/ask_cli_revised/test_assertion_authority_i4_1b.py` | New. Runs the three frozen batteries, pins their hashes, checks the invariants. |
| `experiments/ask_cli_revised/assertion_authority_i4_1b_preregistered.json` | New, frozen. 80 cases. |
| `experiments/ask_cli_revised/assertion_authority_i4_1b_holdout.json` | New, frozen. 27 cases. |
| `experiments/ask_cli_revised/assertion_authority_i4_1b_twins.json` | New, frozen. 10 cases. |
| `experiments/ask_cli_revised/PHASE34_I4_1B_STRUCTURAL_CONTEXT_RESULTS.md` | This report. |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | Appended (prior entries unchanged). |

Not committed, by design: the 54-quote input file (sealed library excerpts, kept under the gitignored `.local/` area), and the battery generator. The generator's output filenames contain the module name, which the unwired static guard correctly flags. The committed batteries are pinned by hash in the test file, so the generator is not needed to verify them.

## 2. Freeze record (before the classifier change)

The three batteries and the generator were written while `git status` was clean at `013364cf`. The unchanged I4-1 module was then run over all 117 cases to record its observed outputs (`baseline_i4_1_observed.json`, kept in scratch). Only after that was `assertion_authority.py` edited.

| Artifact | sha256 |
|---|---|
| `assertion_authority_i4_1b_preregistered.json` | `0dd17d2afd56c9c6b4062851190c8fce96a949adcd7a95cd644e60167ce6e8cb` |
| `assertion_authority_i4_1b_holdout.json` | `b07a2d661f15c2f2d58ccc7a86dfb295313c9940d103578e104026ccf0715baf` |
| `assertion_authority_i4_1b_twins.json` | `c420db67d4e9111b4301d8527caf31f69402731e9fb2b67ac98de252ef6570ce` |
| `make_battery.py` (generator, local) | `42dd7c1cf6693b048f78d7cf1e84794cbc40628299b01b34d94f5406bf46c444` |
| `frozen_54_inputs.json` (local; 54 sealed verified quotes) | `8aa8b0e06b4dd750fc8c7c900a4ca6868ca6196e718d13267550f3e47f5cf8ac` |

**At commit time, the repository's `end-of-file-fixer` pre-commit hook added one trailing newline to each of the three battery
files** (no other byte changed; confirmed with `git diff`). The hashes above are the pre-fixer freeze record. The hashes actually
pinned in `test_assertion_authority_i4_1b.py`, matching the committed bytes, are: preregistered
`5b3519463050768c41ce0a1db378c40c4c86126afe794fc271cb3342b94ae216`, holdout
`23d02abf8000ea734ff6e97b77e286920fceec47ce3d67ab5965a2949664a032`, twins
`50dec8186d7165aff478a53f352d52f69aa0e99ac3a76946e6f0b7616832d834`. The expectations themselves are unchanged.

The expectations are rule-derived predictions of the repaired contract. Each case's `note` says why. They were not derived from running the repaired code. Two places diverge from the directive's sketch, and both are recorded before any run:

- **mp_F** ("Results: These findings suggest…"). The sketch says `this_study`. Under the authorised rules, "These findings" is not an owner cue, and the resolver needs kind `result`, so the frozen source is `unknown`. Finding authority is `candidate` either way, so nothing authority-relevant differs.
- **p30** (§9). The directive's expectation is conditional on a delimiter-free heading being recognised. It is not, so the frozen expectation is unchanged.

## 3. Run-in label grammar (repairs A and B)

- **Position.** Only at the start of the classifier input, after optional spaces or tabs. Nothing mid-text, and nothing from section state.
- **Shape.** One to eight words, each beginning with a letter and allowing hyphens or apostrophes, then `:`, then whitespace, then more text. At most 80 characters. Digits, citation markers and other punctuation do not match.
- **Rejected as labels.** Any word that is a predicate, negation, modal, hedge, contrast word, copula, or `that`. A prior-source phrase (`Previous studies:`, `Smith et al:`), because removing it would lose the prior owner. An owner phrase (`We:`, `This study:`).
- **Retained for audit.** `run_in_label_surface`, `run_in_label_normalized` (lower-cased, whitespace-collapsed), and `run_in_label_span` (character span of the label, excluding the colon).
- **Grants no ownership.** After removal, the remainder is parsed normally.
- **Not a label.** An undelimited heading. This is deliberate and is why p30 is unchanged.

## 4. Results resolver and vetoes (narrow)

Applies only when all of the following hold: the normalised label is exactly `results`; the assertion is in label scope (§6); the source is still `unknown` after ordinary parsing; kind is `result`; the input is not a caption; and the caller supplied no owner signal. It then sets `assertion_source = this_study`, `source_resolution = structural_results_label`, and `finding_authority` through the one central function.

The resolver is never reached when a source was already parsed, so explicit owners are never overridden. Each veto is recorded as a rule `resolver.vetoed.<reason>`:

`label_not_results` · `kind_not_result` (covers modal, interpretation, hypothesis and method kinds) · `prior_framing_or_object` · `replication_act` · `negated` · `hedged_or_modal` · `citation_in_assertion` · `citation_like_marker` (`ref`, `refs`, `cf`, `et al` inside the span) · `citation_like_parenthetical` (a parenthesised year 1800–2099) · `caption` · `owner_signal_supplied`

## 5. Label-leak repair (required order)

The implemented order is: detect the label → remove it from tokenisation → parse the remainder (owners, prior noun phrases, framing) → kind → only if the source is still unknown, the structural resolver.

Examples:
- `Results: Previous studies found that scores increased.` → `prior_work / result / candidate` (mp_B). Under I4-1 this was `unknown`, because the label blocked the prior owner.
- `Results: Earlier work reported that scores increased.` → `prior_work / result / candidate` (ll_1).
- `Results: We found that scores increased.` → `this_study / result / authoritative`, with `source_resolution = parsed`. The resolver is not the reason (mp_D).

## 6. Label scope (bounded)

The label governs only:
- the first clause of the sentence that begins the input (clauses split at `;` and at `, but/although/whereas/while/however/yet/though`); and
- within that clause, the first assertion plus assertions coordinated on that same inherited subject (`Results: Scores increased and decreased.` governs both predicates).

It does not reach later sentences, semicolon-separated clauses, contrast-linked clauses with their own subject, or a second `Label:` later in the text. There is no section state, no evidence-packet section label, and no library lookup.

## 7. Target-span representation (repair C)

- **Region includes the subject.** An assertion's region is now its own subject (when not inherited) through its object end. Previously it started at the predicate head, so any target beginning at a subject word failed closed as `target_crosses_assertion_boundary`. This is the root of the whole-passage failure.
- **Coverage ignores terminal punctuation.** Leading whitespace and trailing `.;!?` are excluded from the coverage check. The raw target is still reported, with the content span beside it.
- **Singular call unchanged in principle.** `classify_assertion_authority` still fails closed on any target that crosses, overlaps, or is covered inconsistently by more than one assertion.
- **New multi-assertion API.** `classify_target_assertions` returns `target_scope` ∈ {`within_assertion`, `partial_assertion`, `multi_assertion`, `no_governing_assertion`}, every intersecting assertion with its own classification and `covers_target`, and `aggregate_authority = None` always. No single authority is ever computed for a broad target.
- **Repeated surfaces.** `classify_all_occurrences` classifies each occurrence separately. `classify_surface` still reports `repeated_target_occurrence` when no occurrence is given.

## 8. Results against the frozen batteries

| Battery | Result | Notes |
|---|---|---|
| Preregistered (80) | **80 / 80** | One harness bug was found and fixed on the first run: the occurrence checker omitted `source_resolution`. The expectation was not edited. |
| Holdout (27) | **27 / 27**, first and only run | Pre-registered, but written by the same author with rule-derived predictions. It is a frozen check, not an independent validation. |
| Cross-domain twins (10) | **10 / 10** | Architecture (2), clinical (2), language learning (2), neutral labels with `we found/observed` (4). |

The required minimal pairs A–J all pass. F matches the frozen rule-derived expectation, which differs from the sketch as noted in §2.

**Existing I4-1 battery.** 98 pass. Seven cases are superseded by the subject-inclusive region and are strict-xfail with reasons: P07, P42, P52, T06, T09, T17, P62. Each one's source is still `unknown` and its authority still `candidate`. What changed is that the target now lies inside its own subject noun phrase, so the assertion's real kind is reported (for example `method_or_description` for "The Implicit Association Test was used"), or a fail-closed ambiguity is cleared. The frozen I4-1 JSON is unchanged.

## 9. p41 positive control and p30 check

**p41.** The label `Results:` is inside the sealed quote, and the classifier received only that quote. The sealed text reads `attrac- tiveness` (a line-wrap artifact), so the surface uses that exact form.
- Assertion 1, `revealed greater proportionality was associated with attrac- tiveness …`: `unknown / result / candidate` → **`this_study / result / authoritative`**, rule `resolver.structural_results_label`. This is the expected positive control.
- Assertion 2, `associated with impressions of anger …`: stays `unknown / result / candidate`. It is a contrast-linked clause with its own unowned subject, outside label scope.
- The whole quote stays fail-closed, because it contains two assertions. The multi-assertion API keeps both records.

**p30.** Remains `unknown / result / candidate`. The sealed heading `Specificity and generalization of intervention effects We also observed …` has no delimiter, so the authorised label rule does not fire. The directive's conditional expectation, `this_study / result / authoritative`, is therefore **not met**. I did not add a delimiter-free owner rule. That would be an unauthorised broadening, and fitting p30 would be tuning. The colon variant `…effects: We also observed …` does resolve (ph_1, pre-registered).

## 10. Preserved 54-quote before/after

Before and after were computed by the same enumeration code, once on the unchanged module and once on the repaired one. The table records only proposition IDs and short fragments, not full quotes.

| Measure | Before (I4-1) | After (I4-1b) |
|---|---|---|
| Assertions | 64 | 64 |
| Authoritative assertions | 21 | 22 |
| Propositions with any authoritative assertion | 11 | 12 |
| Assertion classification changes (source, kind or authority) | — | **1** |
| Assertion span-only changes (subject-inclusive region) | — | 49 |
| Whole-quote singular changes | — | 14 |

**The one classification change.**

| Prop | Assertion (fragment) | Old | New | Rule | Expected before implementation |
|---|---|---|---|---|---|
| p41 | `revealed greater proportionality was associated with attrac- tiveness …` | unknown / result / candidate | this_study / result / authoritative | `resolver.structural_results_label` | **Yes** (pre-registered positive control) |

**Span-only changes (49).** Every assertion whose region now starts at its own subject. This was pre-registered as expected. No classification changed.

**Whole-quote singular changes (14).** Each moved from fail-closed `target_crosses_assertion_boundary` to a resolved, covered assertion. None became authoritative. The exact membership was not pre-registered. The cause is the same subject-inclusive region and terminal trim, so the rule explains it, and each was inspected.

| Prop | Old | New |
|---|---|---|
| p9 | fail-closed | this_study / interpretation / candidate (`We suggest …`) |
| p20 | fail-closed | this_study / interpretation / candidate |
| p10, p16, p19, p27, p39, p42, p48, p49 | fail-closed | unknown / result / candidate |
| p21, p22, p54 | fail-closed | unknown / interpretation / candidate |
| p44 | fail-closed | unknown / method_or_description / candidate |

Consumers must read `finding_authority`, not the absence of `ambiguity`, for these records. All 14 are `candidate`.

**Required unchanged (assertion level, no classification change).**

| Prop | Status | Evidence |
|---|---|---|
| p36 | unknown / result / candidate | Locked non-recovery. The `Participants` subject is not a cue (D-D). |
| p11 | unknown / result / candidate | Locked non-recovery. No replayable ownership structure. |
| p52 | unknown / interpretation / candidate | Locked non-recovery. Headless quote; modal scope; no outside context used. |
| p17 | this_study / result / authoritative | Source authority unchanged. Repeated-term polarity is a separate axis and was not touched. |
| p40 | prior_work / result / candidate | Unchanged. Prior-work cited finding stays candidate. |
| p43 | unknown / aim_or_hypothesis / candidate | `Objective:` is a non-Results label and grants nothing. Unchanged. |
| p30 | unknown / result / candidate | See §9. |

## 11. Achieved-outcome integration question (I4-2 seam)

**Answer: no. I4-2 is blocked** until a separate pure mapping-span increment exists.

- `sufficiency_mapping._match_achieved_outcome(text)` returns the **whole passage** as a string, or `None` (lines 81–84).
- `attribution.has_result_predicate(text)` returns a **boolean** from a regex search (`attribution.py` lines 174–177).

So the matcher cannot return the matched predicate span, the clause or assertion span, or any deterministic local identifier of the assertion that produced the binding. The mapper's text is the unit passage, which is the proposition quote. Attaching an authoritative binding from that output would require classifying the whole passage, which is the overbinding the directive forbids ("some authoritative result somewhere").

The new `classify_target_assertions` records do carry spans and per-assertion authority, so they are the natural seam. A future I4-2 should key each role binding to the assertion span those records return. That wiring is I4-2's work, not this increment's. Also note that the matcher uses its own regex lexicon (`_RESULT_PREDICATE`), separate from the classifier's verb lexicon, so the two can disagree.

## 12. Unsafe authority promotions found (pre-existing; not fixed here)

Both reproduce at `HEAD` (I4-1), so they are not caused by I4-1b. They are outside this increment's scope ("do not broaden beyond these"). They are reported, not patched:

- **`We did not find that scores increased.`** → `this_study / result / authoritative`. The `negated` flag is set, but negation never changes authority.
- **`We found no evidence that scores increased.`** → `this_study / result / authoritative`. The negation lies outside the checked span.

Both are reachable through `classify_target_assertions` and would matter for any future authority-gated role. Recommended fix, as a separate increment: a negated own result, and an absence-of-evidence statement, resolve to `candidate`, with their own frozen battery written before the change.

## 13. Conservative unknowns (by design)

Each returns `unknown` with `candidate` authority rather than promoting: undelimited neutral headings (the p30 structure); "These findings suggest …" (kind is interpretation, so no resolver); a citation alone (`Results: Scores increased.12`); a prior object or prior framing inside the labelled sentence; labels that are not exactly `results` (`Results section`, `Results of prior trials`, `Results-based`, `Results and discussion`, `Results Of The Trial`, `Findings`, `Discussion`); a second `Results:` later in the text.

## 14. Runtime parity (zero-runtime-change gate)

- **Change set against `HEAD`.** Only `experiments/ask_cli_revised/` files changed. Nothing under `app/`, `integrations/`, `tools/`, `tests/`, `mcp_server/`, `tui/` or `sync_server/`.
- **Unwired static guard.** `test_classifier_is_unwired_static_guard` passes. No non-test module references `assertion_authority`.
- **Attempt2 AnswerPlan replay.** Re-run against the scratch stamped run baseline. All **7** output files are byte-identical to the baseline (sha256 lists equal). `plan_sha256 f7ce7d3c618745872ad66bfa1cbb9e4f60376c932e9f147c7033c4c802f2c09a` is identical. The replay's `parent_claim_ledger_rebuilds_identically` check is pre-existing and identical in the baseline.
- **Parity-surface test files.** Sixteen files covering replay, relation witnesses, direction and effectiveness, recovery targets, empty-result terminality, parent synthesis, AnswerPlan and witness alignment all pass. Six of them have earlier per-file records, and their counts are identical: `test_answer_plan_replay` 10, `test_relation_witness` 33, `test_direction_target` 19, `test_sufficiency_mapping` 98, `test_sufficiency_semantics_version` 18, `test_parent_synthesis_replay` 20. The other ten pass with no earlier record to compare against.
- **Map captures, recovery, terminality, stop-search, ParentClaims.** These are covered by the parity files above and by the full offline run in §15. They were not separately re-captured.

## 15. Full offline experiments suite

Full per-file run, socket-blocking launcher, 159 files under `experiments/`. **Totals: 3363 passed, 7 failed, 12 skipped, 276 subtests passed**, plus the one documented `psutil`-import skip (pre-existing, commit `80467e06`).

All seven failures are pre-existing or environment artifacts, not caused by this change:

- **Three match the earlier per-file baseline exactly** (identical failed/passed/subtest counts): `test_e2e_run.py`, `test_hierarchy_contract.py` (the already-known pin drift), `test_hierarchy_e2e.py`.
- **Two are missing-fixture `FileNotFoundError`s** in an unrelated experiment subtree (`experiments/ask_070/tests/test_corpus_and_referents.py`, `test_schema_validation.py`), for frozen input files under `experiments/ask_070/frozen/` that this checkout does not have. Nothing here imports or is reachable from `assertion_authority`.
- **Two are harness double-guards**, not regressions: `experiments/ask_070/tests/test_offline_boundaries.py` and `experiments/ask_adjudication_revision/tests/test_storage_cli_boundaries.py` each assert that *their own* network/subprocess guard raises a specific blocked error; this run's scratch socket-blocking launcher (used to keep the whole suite offline) installs its own guard first, so the assertion sees the launcher's exception instead of the test's own. Running either file without the extra launcher would not reproduce this.

None of the seven touches `assertion_authority.py` or anything that imports it.

## 16. Lint

`ruff format` (applied) and `ruff check` pass on the three touched Python files: `assertion_authority.py`, `test_assertion_authority.py` and `test_assertion_authority_i4_1b.py`. Scoped to those files only.

## 17. Recommendation: **NOT READY for I4-2**

1. **Achieved-outcome seam is missing.** The matcher returns the whole passage, so no single-assertion binding exists yet (§11). This needs a separate pure mapping-span increment first.
2. **Pre-existing negation promotions** are unresolved (§12). They must be closed before any authority-gated role.
3. **Whole-quote singular outputs changed** for 14 quotes (§10). All are `candidate`, but the consumer contract (read `finding_authority`, not `ambiguity`) needs review.
4. **p30 is unchanged.** The directive's conditional expectation is not met (§9), and no delimiter-free rule was added.
5. **An earlier audit claim is not reproduced.** The I4-1a audit said the `Results:` label would recover "p41 and the five c8 instances". In the 54-quote ledger, p41 is the only quote that contains a `Results:` label, so the c8 claim is unverified here.

**Decisions for review.**
- (a) Approve a negation rule (own negated result, and absence-of-evidence statements → `candidate`) as its own increment with a frozen battery.
- (b) Confirm mp_F: frozen as `unknown` source under the authorised rules, against the sketch's `this_study`. Authority is identical.
- (c) Accept the whole-quote fail-closed → resolved change (§10), or ask for it to stay fail-closed.
- (d) Whether a delimiter-free owner rule for p30-style headings should be considered at all. It was not authorised here.

## 18. Versioning

No sufficiency or plan version changed. `RULESET_VERSION` (the classifier's own) moved to `i4-1b.0`. The I4-1 test file still asserts the unchanged sufficiency and plan versions, and the I4-1b test file asserts both as well.
