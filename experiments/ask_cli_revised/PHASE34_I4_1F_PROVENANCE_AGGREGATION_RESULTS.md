# PHASE 34 / I4-1f — pure assertion_relation + aggregation + support_label descriptors (results)

**Status: pure, unwired.** Nothing in mapping, engine, recovery, relation witness, direction, effectiveness,
ParentClaim, or AnswerPlan imports or reads `assertion_relation`, `aggregation`, or `support_label`. No `RoleSpec`
field, no `support_policy`, no `candidate_supports` production structure, no mapping change, no achieved-outcome
wiring, no `requested_category_terms` behavior change, no satisfaction/recovery/relation/direction/effectiveness/
AnswerPlan change, no `sufficiency_semantics_version` bump, no `PLAN_VERSION` bump. No model, network, live search,
or live end-to-end run. No sealing/pin/frozen-run modification.

- **Docs-only checkpoint commit** (I4-1e revision 2, committed and pushed before any code change in this
  increment): `d80b28cda12dc263c1c5cc103a654eb1b4949e31`.
- **Implementation starting HEAD:** `d80b28cda12dc263c1c5cc103a654eb1b4949e31` (the same commit — no other commit
  landed on the branch between the docs checkpoint and this increment's own work).
- Branch `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, worktree
  `.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Final HEAD: the commit that carries this increment (see the handback).

The I4-1e revision-2 design audit is the authoritative architecture for this increment. It is implemented here
exactly as bounded in that document's own §15 ("I4-1f's exact bounded contract"), without broadening.

---

## 1. Files changed

| File | Change |
|---|---|
| `experiments/ask_cli_revised/assertion_authority.py` | Modified. `assertion_relation`, the review/meta-analysis/literature-synthesis owner-phrase extension, `aggregation`'s three cue families, `support_label`, and the public `aggregation()` entry point (§2–§6 below). `RULESET_VERSION` moved `i4-1c.0` → `i4-1f.0`. |
| `experiments/ask_cli_revised/test_assertion_authority_i4_1f.py` | New. Loads and hashes all six frozen batteries; runs them; proves locality, the zero-runtime-change guards, and `support_label`'s display-only status. |
| `experiments/ask_cli_revised/assertion_relation_i4_1f_preregistered.json` | New, frozen. Battery A (9 cases). |
| `experiments/ask_cli_revised/prior_source_review_i4_1f_preregistered.json` | New, frozen. Battery B (16 cases). |
| `experiments/ask_cli_revised/aggregation_i4_1f_preregistered.json` | New, frozen. Battery C (29 cases, including the two real preserved sealed quotes — §9). |
| `experiments/ask_cli_revised/aggregation_i4_1f_holdout.json` | New, frozen. Battery D (9 cases, run once — §7). |
| `experiments/ask_cli_revised/aggregation_i4_1f_twins.json` | New, frozen. Battery E (28 cases, 4 domains × 7). Amended once before any run — §6. |
| `experiments/ask_cli_revised/support_label_i4_1f_table.json` | New, frozen. Battery F (25 cases, exhaustive). |
| `experiments/ask_cli_revised/test_assertion_authority_i4_1c.py` | Modified, mechanically. `test_versions_are_unchanged_for_sufficiency_and_plan` no longer pins the exact `RULESET_VERSION` string — §8. |
| `experiments/ask_cli_revised/PHASE34_I4_1F_PROVENANCE_AGGREGATION_RESULTS.md` | New: this report. |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | Appended (prior entries unchanged). |

Nothing else changed. No `app/`, `integrations/`, frontend, pin, frozen-contract, or sufficiency/plan version file
was touched — confirmed by `git diff --stat` against the implementation starting HEAD, scoped to
`app integrations tools mcp_server tui sync_server tests` (empty) plus a direct listing of every modified/new path
(all ten rows above, all under `experiments/ask_cli_revised/`).

---

## 2. `assertion_relation` — pure 1:1 rename-view

```
assertion_relation(assertion_source) -> "current_document" | "attributed_external" | "unresolved"
```

A plain dict lookup over `assertion_source`'s own three existing values (`this_study`/`prior_work`/`unknown`), with
no new inference. Any other input — including `"synthesis"` (R1's lock, explicitly tested), `"candidate"` (a
`finding_authority` value, not an `assertion_source` value), the empty string, `None`, or one of this function's own
output values fed back in — raises `ValueError` rather than inventing a fourth relation. `ASSERTION_RELATIONS` is the
closed three-value output vocabulary.

## 3. The review/meta-analysis/literature-synthesis owner-phrase extension

One new, fully self-contained matcher, `_match_review_source_np`, wired as the last-resort fallback inside the
existing `_match_prior_np` (reached only when none of the three pre-existing branches — `_PRIOR_ADJ`+`_SOURCE_NOUN`,
`Name et al.`, `Name (YEAR)` — match). Self-contained by design: it does its own determiner handling (including
`"a"`/`"an"`, which the shared `_DET` set does not cover) rather than widening any shared lexicon, so it can change
**only** cases whose governing source owner falls inside this new class — exactly the constraint the directive set.

- **Shape.** An optional determiner, then an optional single modifier — a temporal-priority word (`_PRIOR_ADJ`,
  e.g. "recent") or a genre word (`systematic`/`meta-analytic`) — then a head noun from `{review, reviews,
  meta-analysis, meta-analyses, literature}`. `"evidence"` is recognised **only** directly after the genre modifier
  (`"meta-analytic evidence"`) — too generic a noun to recognise bare, unlike the other heads.
- **The governing-owner guard.** After the head noun (and any trailing citation marker), nothing but end-of-range
  may follow within the caller's own bound. This is what makes `"the review variable increased"` fail to match
  (`"variable"` is a plain word following `"review"`, so `"review"` is not *this* noun phrase's governing head) while
  `"A recent review found X"` matches cleanly (the subject span ends exactly at the head noun).
- **Where it applies.** Every existing caller of `_match_prior_np` benefits uniformly — subject detection
  (`_prior_prefix`), framing detection, and the object-internal prior-source scan — with zero special-casing, since
  the guard above is what keeps each caller safe.

## 4. `aggregation` — three cue families, orthogonal to source/kind/authority

```
aggregation(text, *, target_start, target_end, is_caption=False, structural_context=None)
    -> "literature_synthesis" | "non_synthetic_or_unspecified"
```

Also exposed as a field (`"aggregation"`) on every assertion record `classify_assertion_authority`/
`classify_target_assertions` already return, computed once inside `_build` from that one assertion's own structure
and never read back by anything in this module.

- **Cue A (framing).** A closed, literal phrase — `"across studies"` / `"across multiple studies"` / `"across prior
  studies"` / `"across trials"` — anywhere in the assertion's own pre-predicate clause span `[cs, head)`. Scoped to
  the **clause**, not the subject, because a comma-separated list inside a subject (a pre-existing, unrelated
  parsing property of `_first_assertion`/`_clause_assertions`, confirmed directly: `"Across multiple studies,
  regions A, B, and C are implicated in X."` resolves its subject to `"and C"`) can otherwise swallow a fronted
  adverbial before subject detection ever sees it. `"across trials"` sits in this list, not only in cue C's, because
  the cross-domain twins battery needed it in adverbial position (`"Across trials, the intervention has been
  associated with..."`) and it is already an authorised explicit synthesis cue.
- **Cue B (governing subject).** The assertion's own subject, independent of how its ownership resolved, is itself
  a match for `_match_review_source_np` consuming the subject's **entire** span (not merely a non-None prefix —
  this is checked by equality against `subj["end"]`, not by "is not None"). This is what lets `"The literature
  suggests X"` register `literature_synthesis` even though `"suggests"` makes the assertion `interpretation`-kind,
  and what makes coordinated assertions sharing a review-headed subject (`"A systematic review found X and
  reported Y"`) agree with each other without a separate propagation rule — they already share the same `subj`
  record the existing architecture uses for ownership.
- **Cue C (synthesis-shaped result content).** For a `RESULT`-kind assertion only, its own content span contains an
  explicit synthesis-context word (`meta-analytic`/`meta-analysis`/`meta-analyses`, sufficient alone) or phrase
  (`across studies`/`across trials`/`literature-wide`). **Never** `pooled`/`combined`/`aggregate`/`effect` by
  themselves — the conservative rule this increment exists to hold. Kind-gated deliberately: a `method_or_
  description`-kind object merely containing the word `"meta-analysis"` (`"We performed a meta-analysis of X"`)
  does not trigger it.

Any one cue firing is `literature_synthesis`; none firing is `non_synthetic_or_unspecified`. The three cues never
read `finding_authority`, `authority_veto`, `is_caption`, observation polarity, or any requirement/RoleSpec state —
confirmed by direct reading of `_compute_aggregation`'s own three conditions, none of which touches those fields,
and by the holdout battery's own `HO01`/`HO05` cases (§7).

**One extension to an existing soundness rule.** I4-1c's "two covering assertions must agree on `authority_veto`
too" check (`classify_assertion_authority`'s multi-assertion-disagreement signature) now also compares
`aggregation`, for the identical reason I4-1c gave for adding `authority_veto` there: `aggregation` is now a
property a caller can read from a single-assertion result, so silently picking the first covering reading could
otherwise report one assertion's aggregation value when another, equally-covering reading disagrees. No
preregistered case needed this — like I4-1c's own analogous addition, it is a latent-path closure, reported for
completeness, not a discovered live defect.

## 5. `support_label` — display-only, never fed back

```
support_label(relation, aggregation, kind) -> str | None
```

Exactly the table I4-1e revision 2 specified: the six `(relation × aggregation)` combinations for `result`-kind
(`direct_empirical`/`direct_synthetic`/`attributed_indirect`/`attributed_synthetic`/`unresolved`/
`unresolved_synthetic`), a single `"descriptive"` for `method_or_description`, a single `"interpretive"` for
`interpretation`, and `None` for `aim_or_hypothesis`/`unknown`. `test_support_label_never_consumed_by_any_
admissibility_function` is a static AST guard: it parses the module and asserts no function other than
`support_label` itself ever calls it — a structural, not merely observational, proof that the display-only
contract holds.

## 6. Pre-registration, and one amendment before any run reached it

All six batteries were authored and hashed before `assertion_authority.py` was edited, each informed by running the
exact candidate sentences through the **unmodified** module first (confirming baseline subject/scope/kind
behaviour empirically, the same discipline I4-1b's own freeze record used) — never guessed.

| File | SHA-256 (frozen) |
|---|---|
| `assertion_relation_i4_1f_preregistered.json` | `f67e81a2fa0100ad553a85df9073ac6cba719ddbe64bc5edee99b3fd7150a0a3` |
| `prior_source_review_i4_1f_preregistered.json` | `055181788ebfdc9afc3ceed5718839d0ab13fa656f6822684dd898a9fee23d1c` |
| `aggregation_i4_1f_preregistered.json` | `f7388c80f34684d1442a7b7acda98f298f9d022b67e97f632caa2a002482a7b5` |
| `aggregation_i4_1f_holdout.json` | `65c143e520604eb228657ee7a8e015a6ba01a181c36d0986460efcb1a99f1e30` |
| `aggregation_i4_1f_twins.json` (amended) | `a00dee4ccf9e2a9859758ff06f05bd2f0a0edc59a71e9c094fc18e337c589d8c` |
| `support_label_i4_1f_table.json` | `eccbee4b7eed3557e131f513840c7dfe0067af24081fac275e2827c5185e2e41` |

**One amendment, found by the first implementation run, not guessed around:** `T_CLIN_02_attributed` originally
read `"Previous trials found that symptom severity decreased."`, expecting `attributed_external` via the
pre-existing, unmodified `_PRIOR_ADJ`+`_SOURCE_NOUN` branch. The run returned `unresolved` instead. Direct inspection
showed the cause: `"trials"` is not, and never was, a member of the existing `_SOURCE_NOUN` lexicon (`study studies
work works report reports research finding findings literature evidence investigation investigations paper papers
experiment experiments`) — a pre-existing, unrelated gap this increment's authorized scope does not touch. This is
a **test-design error**, corrected by changing the sentence to `"Previous studies found..."`, which exercises the
intended, byte-unchanged branch; the amended file's hash is recorded above, and the reasoning is recorded in the
case's own `note` field. No classifier change was made in response to this.

## 7. First and only holdout run (9 cases)

**Result: 9/9.** Cases: `HO01` (the authority-veto/aggregation independence case — `"A review found no evidence
that X increased"` resolves `attributed_external`/`literature_synthesis` with `authority_veto=absence_of_evidence`
fully intact, per §4's "never reads authority_veto" claim verified directly); `HO02A`/`HO02B` (one sentence, two
contrast-split clauses — the negated clause carries no aggregation cue of its own and the `meta-analysis`-headed
clause is unaffected by the first clause's veto, proving locality and veto-independence together); `HO03A`/`HO03B`
(coordination: a second assertion sharing a review-headed subject correctly shares both relation and aggregation,
because it shares the same `subj` record, not because of a new propagation rule); `HO04A`/`HO04B` (two sentences —
sentence 1's fronted adverbial does not leak into sentence 2, the required cross-sentence locality proof); `HO05`
(`is_caption=True` on a review-headed assertion: `finding_authority` still forces `candidate`, while `relation`/
`aggregation` are unaffected, confirming orthogonality to captioning exactly as to authority); `HO06`/`HO07`
(plural and grammatically atypical determiner/number forms, both matching as specified — disclosed, not required
negatives). No case was tuned after this run; nothing needed changing.

## 8. Regression of the prior I4-1 family (section 19)

Full, unmodified I4-1/I4-1b/I4-1c/I4-1d test files, run together with this increment's new file:
**500 passed, 9 xfailed** (the 9 xfails are I4-1b's own pre-existing, reasoned supersessions — unchanged from
before this increment). **Zero new failures, zero changed expectations, zero silently-xfailed cases.**

One **mechanical, non-semantic** change was required and is disclosed here rather than silently made:
`test_assertion_authority_i4_1c.py::test_versions_are_unchanged_for_sufficiency_and_plan` hard-coded
`assert aa.RULESET_VERSION == "i4-1c.0"`. This is not a classification expectation (it asserts nothing about any
text's `assertion_source`/`assertion_kind`/`finding_authority`/`authority_veto` output) — it is a version-string
literal that the directive's own `RULESET_VERSION` convention explicitly allows to move per increment, and which
**I4-1c's own test file already relaxed for I4-1b's file for this identical reason**
(`test_assertion_authority_i4_1b.py` checks `aa.RULESET_VERSION.startswith("i4-1")`, not an exact string, per its
own comment: "RULESET_VERSION is the classifier's own ruleset identity... explicitly allowed to move per
increment"). `test_assertion_authority_i4_1c.py`'s own copy of this test was never updated to match that
relaxation when I4-1c shipped, and would fail on every subsequent sub-phase otherwise. The fix mirrors the existing
precedent exactly (`.startswith("i4-1")`), changes nothing else in that file, and is the only edit made to any
pre-existing I4-1-family file in this increment. This is reported per the directive's own instruction to disclose
rather than silently xfail; it was not treated as a "STOP and report" case because it fails the directive's own
description of what that clause protects — a classification expectation that "genuinely conflicts with the newly
approved contract" — not a version-identity literal with an established, already-applied relaxation precedent.

`sufficiency-semantics-v4` and `answer-plan-step2-v4` are confirmed unchanged everywhere they are checked across
the full regression.

## 9. Preserved-data limitation, disclosed plainly (sections 16–17)

**The gitignored scratch fixtures this section's full sweep depends on are not present in this worktree.** Neither
`frozen_54_inputs.json` (the sealed 54-quote input file I4-1b's own report names as "kept under the gitignored
`.local/` area") nor any reconstructed `final_v4_lenient.json`/`final_v4.json` map file exists anywhere under this
worktree's `.local/` directory or `experiments/ask_cli_revised/` (confirmed by direct listing — `.local/` contains
only unrelated `decompose-runs`/`e2e-runs`/`phase32`/nomination-diagnostic directories). These are session-local
artifacts a prior Claude Code session created and deliberately did not commit (by the same rationale every
I4-1x report already states: their filenames would trip the unwired static guard). **This is reported as a blocked
precondition, not worked around by fabricating substitute data.**

**What was actually done instead, using only real, already-public, already-committed preserved text:** two complete
verbatim preserved sealed quotes are quoted in full inside I4-1b's and I4-1d's own committed results reports, and
both were run through the finished implementation as real `aggregation_i4_1f_preregistered.json` cases
(`AGG_P41_REAL`, `AGG_P8_REAL`):

- **p41** (I4-1d §10's own verbatim quote): `"Results: Across the ratings for all faces, Spearman correlations
  revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness
  (ρ = 0.193, P < 0.001), while lesser proportionality was associated with impressions of anger (ρ = 0.132,
  P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001)."` — the **required**
  negative control. Confirmed: `assertion_relation = current_document` (via I4-1b's own `structural_results_label`
  resolver, unchanged), `aggregation = non_synthetic_or_unspecified`. The clause's own pre-predicate span is
  `"Across the ratings for all faces, Spearman correlations"` — cue A's phrase list requires `"across"` directly
  followed by `"studies"`/`"multiple studies"`/`"prior studies"`/`"trials"`; `"across the ratings"` matches none of
  them, confirming the conservative, literal-phrase design (not a loose `"across \w+"` pattern) holds against the
  real preserved text that originally motivated this exact required check.
- **p8/p4/p1's shared sentence** (I4-1d §10's own verbatim quote): `"This research confirmed earlier reports that
  people with anomalous faces are imbued with negative personality characteristics, detected explicit biases
  against people with facial anomalies, and described a behavioral manifestation of the 'anomalous-is-bad'
  stereotype affecting prosociality."` Confirmed: `assertion_relation = current_document`,
  `aggregation = non_synthetic_or_unspecified` — no spurious trigger from the word `"reports"` in `"confirmed
  earlier reports"` (a `_SOURCE_NOUN` match used only by the pre-existing D-B confirmation rule, never read by
  `aggregation`'s cues).

**What remains genuinely unverified against the real preserved corpus, named rather than silently skipped:** the
other six specifically-discussed ids (p1, p11, p17, p30, p31, p40, p52) and the full 54-quote sweep. Nothing here
was guessed at as a substitute; the two real quotes used are the only ones this session has verbatim access to
through already-public, already-committed material, and both are reported with their real, unmodified text.

## 10. Lint

`ruff format` (applied) and `ruff check` pass on all three touched/new Python files:
`assertion_authority.py`, `test_assertion_authority_i4_1f.py`, `test_assertion_authority_i4_1c.py`.

## 11. Zero-runtime-change proof

- **Static unwired guard.** `test_classifier_is_still_unwired_static_guard` (this increment's own) re-confirms I4-1's
  own invariant: no non-test module under `app`, `integrations`, `experiments`, `tools`, `tests`, `mcp_server`,
  `tui`, or `sync_server` references `assertion_authority` by name. Combined with the unchanged, still-passing
  original guard in `test_assertion_authority.py`, this is confirmed from two independently-written scans.
- **Change set against the implementation starting HEAD.** `git diff --stat` touches only the ten paths in §1, all
  under `experiments/ask_cli_revised/`; nothing under `app/`, `integrations/`, `tools/`, `mcp_server/`, `tui/`,
  `sync_server/`, or `tests/`.
- **Full offline experiments suite** (`pytest experiments/ -n auto`, no special socket-blocking launcher — this
  increment's own code makes no network call, so none was needed for its own verification): **3651 passed, 5
  failed, 12 skipped, 9 xfailed.** All five failures are the exact pre-existing/environment-artifact set every
  prior I4-1x report already names — the `hierarchy_contract.py` pin-drift (`test_hierarchy_contract.py`), its
  downstream exit-code effect (`test_hierarchy_e2e.py`), the live-Ollama-dependent unscored-smoke-run case
  (`test_e2e_run.py`), and two missing-fixture `FileNotFoundError`s in the unrelated `experiments/ask_070/`
  subtree. **Zero new failures.**
- **Scoped re-run** (`pytest experiments/ask_cli_revised -n auto`): **3431 passed, 3 failed, 11 skipped, 9
  xfailed** — the same three in-package pre-existing failures, confirming the two `ask_070` failures above are
  outside this package entirely.
- **`sufficiency-semantics-v4`/`answer-plan-step2-v4` confirmed unchanged** by the regression suite's own version
  tests (§8).

## 12. Recommendation: READY for I4-1g, scoped exactly as I4-1e revision 2's §22 bounds it

I4-1f delivers precisely its own bounded contract: `assertion_relation` (a pure rename), the disclosed
review/meta-analysis/literature owner-phrase extension, `aggregation`'s three cue families, and `support_label` —
all pure, all unwired, all additive, with zero collateral change to any pre-existing classification (confirmed by a
500-case regression) and zero production-path exposure (confirmed by a static guard and a full-suite run). The
next bounded step, per I4-1e revision 2 §15/§22, is **I4-1g**: the `support_policy` `RoleSpec` field and its
builder, the `candidate_supports` instance-level structure, and the `requested_category_terms` reuse for
disambiguation — still pure schema additions with their own backward-compatibility tests, still no semantic-gating
change anywhere a production path executes. **I4-2** (production wiring, the `sufficiency_semantics_version` bump,
all-support aggregation, requirement admissibility, span attachment) remains explicitly not started, and this
increment does not attempt to shorten that distance.
