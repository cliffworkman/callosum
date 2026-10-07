# PHASE 34 / I4-1c — negated-result / absence-of-evidence authority hardening (results)

**Status.** Pure and unwired. Starting HEAD `1c62c102`. The I4-1c commit follows it on the same branch. No production module
changed. No sufficiency version bump (`sufficiency-semantics-v4` unchanged), no `PLAN_VERSION` bump
(`answer-plan-step2-v4` unchanged). The classifier's own ruleset string moved from `i4-1b.0` to `i4-1c.0`, because its
outputs changed; it is not a sufficiency or plan version. No achieved-outcome span work, no I4-2, no wiring, no I2-3.

---

## 1. The defect this closes

Two pre-existing unsafe classifications, confirmed in the I4-1b report and reproducing unchanged at `HEAD`:

- `"We did not find that scores increased."` → `this_study / result / authoritative`
- `"We found no evidence that scores increased."` → `this_study / result / authoritative`

Both report a genuine this-study result act, but neither authoritatively establishes the embedded positive target
(`scores increased`). I4-1c does **not** change who reported it or what kind of assertion it is — it adds a narrow,
deterministic gate on whether that assertion **authoritatively establishes the target proposition**.

## 2. Files changed

| File | Change |
|---|---|
| `experiments/ask_cli_revised/assertion_authority.py` | The authority-veto gate (§3). |
| `experiments/ask_cli_revised/test_assertion_authority.py` | Two more I4-1 expectations (P21, P59) are superseded by the veto and marked strict-xfail with reasons, alongside the seven already superseded by I4-1b. Frozen I4-1 JSON not edited. |
| `experiments/ask_cli_revised/test_assertion_authority_i4_1b.py` | `test_versions_are_unchanged_for_sufficiency_and_plan` no longer pins the exact `RULESET_VERSION` string (the directive explicitly allows it to move per increment); it checks the frozen sufficiency/plan versions and that the ruleset is still an `i4-1` family value. |
| `experiments/ask_cli_revised/test_assertion_authority_i4_1c.py` | New. Runs the three frozen batteries, pins their hashes, checks the invariants. |
| `experiments/ask_cli_revised/assertion_authority_i4_1c_preregistered.json` | New, frozen. 37 cases. |
| `experiments/ask_cli_revised/assertion_authority_i4_1c_holdout.json` | New, frozen. 21 cases. |
| `experiments/ask_cli_revised/assertion_authority_i4_1c_twins.json` | New, frozen. 18 cases. |
| `experiments/ask_cli_revised/PHASE34_I4_1C_NEGATED_AUTHORITY_RESULTS.md` | This report. |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | Appended (prior entries unchanged). |

Not committed, by the same rationale as I4-1b: the battery generator's output filenames contain the module name,
which the unwired static guard correctly flags. The three battery files are pinned by hash in the test file instead.

## 3. The authority-veto schema

One new optional input to the one central authority function, and one new output field, per assertion:

```
finding_authority(assertion_source, assertion_kind, is_caption=False, authority_veto=None)
```

`authority_veto` ∈ `{None, "negated_result_predicate", "absence_of_evidence"}`. It can only **prevent**
`AUTHORITATIVE`; it never promotes. It is computed once, in `_build()`, as a property of the assertion's own
structure — independent of how its source was resolved (ordinary parsing, the Results-label resolver, or a supplied
owner signal) — and is gated to `kind == result` only, so `method_or_description` / `aim_or_hypothesis` /
`interpretation` / caption candidates are never touched (they were already `candidate`).

**`negated_result_predicate`** fires when either:
- the governing predicate's own head-to-pred negation is set (the existing `neg` flag — `"did not find"`, `"never
  observed"`, `"failed to find"`, all already detected by the pre-existing `_NEG`/`_HEAD_SKIP` machinery); or
- the object **content** itself reads as a clause whose own result/replication verb is negated (new:
  `_content_negated`) — `"We found that X did not increase"`, where the outer predicate (`found`) is not negated but
  the embedded one (`increase`) is.

**`absence_of_evidence`** fires when either the governing **subject** is exactly `no` + a closed head noun
(`"No evidence showed that X increased"`), or the **object content** starts with the same pattern
(`"We found no evidence that X increased"`) — new: `_absence_of_evidence`. The head-noun set is deliberately small
and closed: `evidence`, `support`, `indication`, `proof`. No null-result ontology is built; a sentence that merely
contains the word "evidence" without a leading `no` never matches (`"We found strong evidence that X increased"` is
untouched).

One lexicon addition was required for a directive-mandated test case: `provided` / `provide` / `provides` joined the
existing closed `_RESULT_VERBS` set, so `"The analysis provided no evidence that X increased"` has a governing
predicate at all (`"the analysis"` was already an owner phrase via the pre-existing `_STUDY_NOUN` match on
`analysis`).

**One structural hardening found while implementing, not requested but necessary for soundness:** the existing
"do these covering assertions agree" check (used when a target is covered by more than one assertion, e.g. a
coordinated/inherited subject) compared only `(source, kind)`. Two covering assertions could in principle agree on
those while disagreeing on `authority_veto`, and silently picking the first would risk exactly the kind of unsafe
promotion this increment exists to close. The signature now also includes `authority_veto`, so such a case fails
closed (`multiple_assertions_disagree`) instead of picking an answer. No preregistered case needed this — it is a
latent-path closure, reported for completeness, not a discovered live defect.

## 4. Source/kind parity

For both defect classes, `assertion_source` and `assertion_kind` are **unchanged** by this gate — the authors are
still reported as having made a this-study result act. Only `finding_authority` moves from `authoritative` to
`candidate`, and `authority_veto` records why. Verified directly:

```
"We did not find that scores increased."       → this_study / result / candidate   (veto: negated_result_predicate)
"We found no evidence that scores increased."  → this_study / result / candidate   (veto: absence_of_evidence)
```

The one place source/kind changes for a reason **unrelated** to the veto, as flagged in the pre-registration itself:
`"We cannot conclude that scores increased."` — `conclude` is not a governing predicate in the lexicon at all, so the
only recognised assertion binds `scores` as its own unowned subject; this already yields `unknown/result/candidate`
through `source = unknown`, not through the new veto, before I4-1c ever runs. This matches the directive's own
required outcome (`-> candidate`) without needing `conclude` added anywhere.

## 5. Preregistered battery (37 cases)

Covers: positive minimal pairs A–F (§7 of the directive), negation-scope minimal pairs 1–7 (§8), four generic
negated-result-predicate variants (§5), five generic absence-of-evidence variants (§6), target-specificity across
mixed two-assertion sentences (§9), Results-label interaction (§12), prior-work interaction (§13), and
method/interpretation/caption parity spot-checks (§14).

**Result: 37 / 37.** One frozen expectation was corrected before the implementation run reached it — see §6.

Noteworthy confirmations against the directive's own named traps:
- `"We did find that scores increased."` → authoritative. `did` alone is not in the negation set; only `"did not"`
  sits in the head-skip zone.
- `"We found that scores increased, not revenue."` → authoritative. The trailing `not revenue` sits after the
  predicate's own head-to-pred window and outside the object content's embedded-clause scan, so it never reaches
  either detector.
- `"We found that scores increased but not significantly."` → authoritative, unchanged. No new significance
  ontology was built; the hedge is inert to both detectors.
- `"Notably, we found that scores increased."` → authoritative. `Notably` is comma-framed discourse, already
  excluded from the subject by the pre-existing framing mechanism.
- `"We found not only that scores increased, but also that revenue decreased."`, target `scores increased` →
  authoritative. `not only` never reaches the negation window around `found`.
- `"We cannot conclude that scores increased."` → `unknown/result/candidate` (§4, no lexicon change needed).
- `"We failed to find evidence that scores increased."` → candidate, veto `negated_result_predicate`. `failed` was
  already in the pre-existing `_NEG` set and sits in `find`'s head-skip zone — the exact same mechanism as `"did not
  find"`, needing no new code.

## 6. One frozen expectation corrected before the implementation run reached it

`ns_5b` (`"We found not only that scores increased, but also that revenue decreased."`, target `revenue decreased`)
was originally frozen as `this_study/result/authoritative`, on the assumption that the correlative `not only … but
also …` construction shares the one subject (`We`) across both halves. It does not, under the classifier's own
clause-splitting architecture (established in I4-1/I4-1b, the same principle that already governs `spec_2c` in this
battery, §9): the sentence splits into two clauses at `, but`, and clause 2 (`"also that revenue decreased"`) starts
with no subject token in it at all, so its `revenue` stays unowned under the pre-existing no-cross-clause-ownership
rule. The corrected, rule-derived expectation — `unknown/result/candidate` — is what the frozen battery now asserts,
with the reasoning recorded in the case's own `note`. This is a test-design correction, not a classifier change: the
directive's own requirement for pair 5 (that `not only` must not veto solely from the token `not`) is fully
demonstrated by the sibling case `ns_5` (clause 1, `scores increased`, authoritative) without needing clause 2 to be
authoritative too. Adding correlative-conjunction subject-sharing would be a new grammar rule, not this increment's
narrow authority veto, and was not made.

A second case (`ho_07`, holdout) surfaced a bug in the **test harness**, not the classifier: the harness collapsed
any result carrying a non-null `ambiguity` down to `{"ambiguity": ..., "fail_closed": ...}`, discarding
`assertion_source`/`assertion_kind`/`finding_authority` even when the expectation needed to check them. Direct
inspection confirmed the classifier already returned the correct `unknown/unknown/candidate` with
`ambiguity=target_outside_predicate_scope`; the harness was fixed to report the full field set alongside `ambiguity`,
and no expectation changed.

## 7. Holdout (21 cases, first and only run)

Stress: `not only`, `did not`, `never`, `no evidence`, `no support`, `no indication`, `no proof`, `failed to find`,
`cannot conclude`, negation in a sibling clause with no predicate of its own, target in a positive sibling assertion,
multiple target occurrences, Results label (plain and absence-of-evidence-on-subject), prior-work owner, and a
headless fragment with no subject at all.

**Result: 21 / 21, after the one harness fix in §6.** No expectation in the holdout itself was edited.

## 8. Cross-domain twins (18 cases)

Architecture, clinical, and language-learning domains, each with: a positive baseline, a negated-result-predicate
case, an absence-of-evidence case, a mixed two-assertion sentence (target the unvetoed sibling), a Results-label
case, and a prior-work-plus-absence-of-evidence case. **Result: 18 / 18.**

## 9. Target-specificity

Verified directly, matching the directive's own examples:

```
"We did not find that scores increased, but we found that revenue decreased."
    target "scores increased"  → candidate  (veto: negated_result_predicate)
    target "revenue decreased" → authoritative
```

The veto is computed per-assertion in `_build()` and never applied to a sibling clause's own record — there is no
sentence-level or whole-text veto anywhere in the implementation.

## 10. Preserved 54-quote evaluation

**Zero change.** Authoritative-assertion count: 22 before, 22 after (identical to the I4-1b end state). Zero of the
54 sealed quotes' 64 assertions have `authority_veto` set after I4-1c; zero assertion-level classification changes;
zero whole-quote changes. None of the preserved quotes happen to contain a negated-result-predicate or
absence-of-evidence construction. Per the directive's own §17, this is an explicitly acceptable outcome — the
synthetic battery's purpose is to close the semantic hole before wiring, not to demonstrate recall on this one
sealed corpus. Confirmed unchanged at the assertion level, as required: p41, p17, p36, p11, p52, p40, p30 (all
identical to their I4-1b values — see `PHASE34_I4_1B_STRUCTURAL_CONTEXT_RESULTS.md` §10 for those values).

## 11. Unsafe promotions remaining

**None newly introduced.** The two promotions this increment targeted are closed (§1, §4). No other unsafe
promotion was found while building or testing this gate. The I4-1b report's other finding — I4-2 is blocked because
the achieved-outcome mapper returns only the whole passage, never a predicate or assertion span — is **unchanged
and out of scope here** (the directive explicitly excludes achieved-outcome span work from I4-1c).

## 12. Conservative false negatives (by design)

Kept deliberately narrow per the directive ("keep the vocabulary SMALL... do not build a general null-result
ontology"): a magnitude hedge (`"but not significantly"`, `"but not dramatically"`) is never treated as a negation
of the underlying claim; `"some evidence"` / `"strong evidence"` (without a leading `no`) never trigger the
absence-of-evidence veto; `"cannot conclude"` is handled only because `conclude` has no governing-predicate binding
at all, not through a new epistemic-hedge rule. None of these under-classify in a way the directive asked to be
fixed; all were explicit required outcomes.

## 13. Proof the classifier stays unwired

- `test_classifier_is_unwired_static_guard` (unchanged, in `test_assertion_authority.py`) passes: no non-test module
  under `app/`, `integrations/`, `experiments/`, `tools/`, `tests/`, `mcp_server/`, `tui/`, or `sync_server/`
  references `assertion_authority`.
- `git diff --stat HEAD -- app integrations tools mcp_server tui sync_server tests` is empty.

## 14. Runtime parity (zero-runtime-change gate)

- **Change set against `HEAD` (`1c62c102`).** Only `experiments/ask_cli_revised/` files changed.
- **Attempt2 AnswerPlan replay**, re-run against the same scratch stamped-run baseline used for I4-1b: all 7 output
  files byte-identical (sha256 lists equal); `plan_sha256 f7ce7d3c618745872ad66bfa1cbb9e4f60376c932e9f147c7033c4c802f2c09a`
  identical.
- **The same 16 parity-surface test files from I4-1b** (replay, relation witnesses, direction and effectiveness,
  recovery targets, empty-result terminality, parent synthesis, AnswerPlan, witness alignment): **444 passed, 18
  subtests passed** — exactly the I4-1b totals, confirmed file-by-file.
- **Full offline experiments suite (159 files, socket-blocking launcher).** **Totals: 3365 passed, 7 failed, 12
  skipped, 276 subtests passed**, plus the one documented `psutil`-import skip (pre-existing). All seven failures
  are the **exact same seven files** reported in the I4-1b parity gate, with the same causes: `test_e2e_run.py`,
  `test_hierarchy_contract.py` (the already-known pin drift), and `test_hierarchy_e2e.py` are pre-existing and
  unrelated to this change; `experiments/ask_070/tests/test_corpus_and_referents.py` and `test_schema_validation.py`
  are missing-fixture `FileNotFoundError`s in an unrelated experiment subtree this checkout does not have; and
  `experiments/ask_070/tests/test_offline_boundaries.py` and `experiments/ask_adjudication_revision/tests/
  test_storage_cli_boundaries.py` are the same scratch-launcher double-guard artifact described there. **Zero new
  failures.**

## 15. Lint

`ruff format` (applied) and `ruff check` pass on all four touched Python files: `assertion_authority.py`,
`test_assertion_authority.py`, `test_assertion_authority_i4_1b.py`, `test_assertion_authority_i4_1c.py`.

## 16. Recommendation: next step

I4-1c closes the two unsafe promotions it was scoped to close, with zero runtime change and zero collateral change
to the preserved corpus. **I4-2 remains blocked** on the same achieved-outcome mapping-span seam identified in
I4-1b (§11) — that work is explicitly out of scope here and was not started. The classifier's test battery now
numbers 76 (I4-1c) + 117 (I4-1b, minus 2 now superseded) + 80 (I4-1, minus 9 now superseded) cases plus the
preserved-corpus evaluation; before any wiring, I4-2 should still define how a mapping-time role binding keys to a
single assertion's span (not just its authority), since that is what makes a single-assertion binding *attachable*
in the first place, independent of the authority value it carries.
