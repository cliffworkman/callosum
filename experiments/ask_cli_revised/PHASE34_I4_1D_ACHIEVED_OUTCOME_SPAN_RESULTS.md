# PHASE 34 / I4-1d — achieved-outcome assertion-span attachment (results)

**Status.** Pure and unwired. Starting HEAD `0a5420a3`. The I4-1d commit follows it on the same branch. No
production module changed. No sufficiency version bump, no `PLAN_VERSION` bump. A local matcher/schema version
(`i4-1d.0`) exists only on the new module; it is not a sufficiency or plan identity. No achieved-outcome span is
consumed anywhere yet. No `finding_authority` is used to accept or reject anything here.

**Architectural posture, stated once and held throughout.** This increment is about **attachment**, not authority.
It never asks whether an assertion is direct, prior-work, review-style, descriptive, or `candidate` under the I4-1
classifier — only *which* local assertion a result-predicate match belongs to. `candidate` is not treated as
unsatisfying; `prior_work` is not treated as unusable. Those remain open questions for a future evidence-directness
increment, explicitly not decided here (see §9).

---

## 1. The problem

`sufficiency_mapping._match_achieved_outcome(text)` reuses `attribution.has_result_predicate` to answer only
**whether** a passage contains a result predicate, then returns the **whole passage** as the binding's `exact_text`
— regardless of how many local assertions that passage actually contains. Reading the real call site
(`_bind_role_candidates`, `sufficiency_mapping.py` lines ~354–377) confirms exactly how thin this is: the detector
receives only `unit["passage"]` — no separate target value, no requirement-specific content to match against — and
the bound `proposition_id` is simply `unit["proposition_ids"][0]`, the first of (possibly several) proposition ids
that happen to share that passage's exact text, not necessarily the one that produced the match. The first
admissible **unit** (not predicate) in list order wins; there is no ranking across units by source authority either
— the existing acceptance mechanism is already source-neutral in that sense, just not sub-passage-aware.

## 2. The API / schema

One pure function, `find_achieved_outcome_matches(text) -> AchievedOutcomeMatchSet`:

```
AchievedOutcomeMatchSet(old_match_is_not_none, matches, has_ambiguity)

AchievedOutcomeMatch(
    predicate_span,              # (start, end) of this match's own anchoring result-predicate word
    predicate_surface,           # text[predicate_span]
    secondary_predicate_spans,   # other result-predicate hits merged in as embedded content ('that'-clauses)
    sentence_span, clause_span,  # context
    assertion_span,              # clause_span, narrowed on an edge when split from a neighbour
    content_span,                # (predicate_start, assertion_span end) -- the tightest predicate-anchored view
    matched_text,                # text[content_span]
    rule,                        # single_or_last_in_clause | merged_embedded_content | split_at_coordination | ambiguous_boundary
    ambiguous_with,               # None, or the neighbouring predicate_span(s) this one could not be bounded against
)
```

`old_match_is_not_none` is the exact historical boolean (`attribution.has_result_predicate(text)`), carried
alongside for self-contained parity verification: by construction, it is always true iff `matches` is non-empty.

**Predicate lexicon: reused, not duplicated.** `attribution._RESULT_PREDICATE`/`has_result_predicate` are called
directly, unmodified — zero risk of the regex silently drifting out of sync with the real mapper.

**Boundary logic: duplicated, not imported.** The sentence/clause splitter is a direct reimplementation of the I4-1
classifier's own boundary rules (`;` and `, but/although/whereas/while/however/yet/though` for clauses; the same
abbreviation-aware sentence splitter). This is deliberate: importing the I4-1 classifier module would trip its own
unwired static guard, which forbids any non-test reference to it by name. Cross-validation against that classifier
happens only in this module's own test file (§8), never inside the module itself.

## 3. The attachment algorithm

Within each clause, every raw `_RESULT_PREDICATE` hit is walked left to right. For each consecutive pair, the
**last** occurrence of `that`/`and`/`or`/`but` between them decides the relationship:

- **`that` last** → the second hit is embedded content of the first (`We found that X increased` — `increased` is
  content `found` reports, not a second assertion). Recorded in `secondary_predicate_spans`, rule `merged_
  embedded_content`.
- **`and`/`or`/`but` last** → the second hit is a coordinated sibling assertion. The first is closed right at the
  coordinating word (rule `split_at_coordination`); the second starts right after it.
- **Neither found** → genuinely undecidable. Both are reported as their own matches, each carrying the other's
  `predicate_span` in `ambiguous_with` — **on both sides**, never only one (a real asymmetry bug was caught and
  fixed during a manual trace before any battery was run: the first pass only flagged the earlier match, leaving
  the later one looking falsely resolved).

`content_span` always starts at its own predicate's own position, never a neighbour's — so for `"We hypothesized X
and found Y."` (`hypothesized` is not even in the mapper's lexicon, so there is only one raw hit), the result
attaches to `found Y`, never the hypothesis, by construction rather than by a special case.

## 4. Ambiguity is never silently resolved

`"found X previous studies found Y"` (no punctuation at all — a genuine headless fragment) has no `that`/`and`/
`or`/`but` between its two `found` hits. Both are returned, each flagged `ambiguous_with` the other's span, with
`has_ambiguity=True` on the overall result. No source-authority tie-break is ever consulted to resolve this, per
the directive's explicit instruction. Consecutive matches that are **not** mutually ambiguous never overlap in
`content_span` — verified as an explicit invariant over the full frozen battery, the 54 preserved quotes, and every
prose string literal in the production mapping test file (237 texts total, §6).

## 5. Multiple result assertions

`"Previous studies found X. We found Y."` → two sentences, trivially two independent local assertions, never
collapsed to one and never ranked by source. `"We found X and detected Y."` (one clause, coordinated) → split into
two local assertions at `and`. Neither case lets whichever assertion "looks strongest" absorb the other.

## 6. Parity with the historical matcher (section 9)

**Exact parity confirmed, zero mismatches, across 237 independent texts:**

| Corpus | Texts | Mismatches |
|---|---|---|
| Frozen I4-1d battery (preregistered + holdout + twins) | 42 | 0 |
| The 54 preserved Attempt2 sealed quotes | 54 | 0 |
| Every prose string literal in `test_sufficiency_mapping.py` (the production mapping test file) | 141 | 0 |

For every one, `attribution.has_result_predicate(text) == result.old_match_is_not_none == (len(result.matches) >
0)`, with no documented pre-existing bug needed to explain an exception, because there was none to explain.

**One real expectation bug was found and corrected before any battery was frozen for a final time** (disclosed, not
silently fixed): `_RESULT_PREDICATE` lists only the past-tense `found`, never the base form `find` that correct
do-support negation grammar requires (`"did not find"`, never `"did not found"`). Four cases using `"did not
find"` were frozen expecting a `found` match that the regex never actually produces; the corrected expectation —
a single match on `increased` alone — is itself a concrete, real demonstration of exactly the lexicon-divergence
flagged in the I4-1b report: this mapper-level regex is a **different, narrower** lexicon than the I4-1 classifier's
own `_RESULT_VERBS` (which lists `found`/`find`/`finds` all three). The two can and do disagree.

## 7. Direct/indirect contrasts (section 8 minimal pairs)

| Case | Text | Result |
|---|---|---|
| A | `We found that scores increased.` | 1 match, `found` (merges `increased`) |
| B | `Previous studies found that scores increased.` | 1 match, `found` — **not suppressed** for being prior-work |
| C | `Previous studies found X. We found Y.` | 2 distinct local assertions |
| D | `A review concluded that X is associated with Y.` | 1 match, `associated` — `concluded` is not in the lexicon at all; preserved, admissibility undecided |
| E | `We hypothesized X and found Y.` | 1 match, `found` — attaches to the result, never the hypothesis |
| F | `We found no evidence that scores increased.` | 1 match, `found` — remains representable, not deleted |

All six pass exactly as pre-registered. None required tuning.

## 8. `assertion_authority` interop — validation only (section 7)

Every non-ambiguous frozen match's `content_span` was fed into the I4-1 classifier's `classify_target_assertions`
as a target, over all 42 battery cases (37 checks). In every case the target scope came back `within_assertion` or
`partial_assertion` — never `multi_assertion` or `no_governing_assertion` — confirming the span maps cleanly onto
exactly one of that classifier's own assertions. This is read-only, report-only: nothing here feeds the classified
`finding_authority` or `authority_veto` back into which matches this module keeps. For `"We found no evidence that
scores increased."`, the cross-check does surface `authority_veto = absence_of_evidence` in the validation
metadata — visible for inspection, never consulted by the matcher itself, and the match is never deleted.

## 9. Target-aware seam (section 6)

**No** — the existing mapper does not currently have enough information to associate a specific role/requirement
value with one achieved-outcome assertion inside a multi-assertion passage. Concretely:

- `_deterministic_text_for_role(role_spec, passage)` → `_match_achieved_outcome(text)` receives only the raw unit
  passage. There is no separate "target value" parameter for this strategy at all (contrast with
  `explicit_category_terms`, whose detector *does* take `requested_category_terms` — an asymmetry worth noting:
  that role already has a target-aware signature; this one never did).
- The bound `exact_text` is the **whole passage**, and the bound `proposition_id` is `unit["proposition_ids"][0]`
  — the first of however many proposition rows happen to share that exact passage text, which (as the real audit
  in §10 shows) can be an artifact of ledger insertion order, not of which proposition actually produced the match.

**What is needed before a safe single-assertion attachment is possible:** (1) this module's span output — now
delivered; (2) the mapper's call site would need to be changed to store a span (not the whole passage) in the
binding's provenance — a **production change**, explicitly out of scope here; and (3) an explicit policy for what
to do when one unit's passage contains more than one independently-valid local assertion (bind the first? require
model disambiguation? mark the binding ambiguous?) — a **policy decision**, not an attachment mechanism, and
therefore deferred, not decided, by this increment.

## 10. Preserved Attempt2 audit (section 10, real data, read-only)

Every `achieved_outcome_predicate`-strategy `filled` binding in the reconstructed v4 map (`final_v4_lenient.json`)
was read directly — **15 bindings, 8 distinct proposition ids** (p1, p4, p8, p11, p24, p30, p31, p41). The map was
not changed.

| child / requirement | role | proposition_id | old whole-passage match | local matches | unique? | ambiguous? |
|---|---|---|---|---|---|---|
| c1 / neural-manifestation | neural_manifestation_evidence | p1 | yes | 1 | yes | no |
| c2 / behavioral-manifestation (×3 instances) | behavioral_manifestation_evidence | p4 | yes | 1 | yes | no |
| c3 / attitude-manifestation | attitude_manifestation_evidence | p8 | yes | 1 | yes | no |
| c4 / specific-region (×2 instances) | region_bears_on_bias_evidence | p11 | yes | 1 | yes | no |
| c12 / intervention-effectiveness, instance 0 | observed_effect_or_outcome | p24 | yes | 1 | yes | no |
| c12 / intervention-effectiveness, instance 2 | observed_effect_or_outcome | p30 | yes | 1 | yes | no |
| c12 / intervention-effectiveness, instance 3 | observed_effect_or_outcome | p31 | yes | 1 | yes | no |
| c8 / trait-construct (×5 instances) | relationship_to_bias_manifestation | p41 | yes | **3** | **no** | **yes** |

**A real, concrete illustration of the §1 problem, found in the sealed data itself:** p1, p4, p8, and p24 are
**four different proposition ids bound to the exact same 292-character quote text** (`"This research confirmed
earlier reports that people with anomalous faces are imbued with negative personality characteristics, detected
explicit biases against people with facial anomalies, and described a behavioral manifestation of the
'anomalous-is-bad' stereotype affecting prosociality."`) — the same sentence satisfies four unrelated children's
(c1, c2, c3, c12) achieved-outcome roles, each receiving `unit["proposition_ids"][0]`, i.e. whichever proposition
row happened to appear first in the sealed ledger for that exact (paper, passage) pair. That value is an artifact
of ledger insertion order, not of which proposition actually produced the match.

**p41 is genuinely ambiguous, and that is the honest result, not a defect to fix.** Its sealed text is: `"Results:
Across the ratings for all faces, Spearman correlations revealed greater proportionality was associated with
attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001), while lesser proportionality
was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and
threateningness (ρ = 0.234, P < 0.001)."` Clause-splitting correctly separates the `, while` contrast into two
clauses. The first clause contains two raw hits, `revealed` and `associated`; the gap between them —
`"greater proportionality was "` — contains **no** `that`/`and`/`or`/`but` at all. This is **elliptical
`that`-omission**, extremely common in scientific writing (`"revealed [that] X was associated with Y"` with the
`that` silently dropped), which this module's simple boundary-word scan cannot distinguish from "these two
predicates are unrelated" without guessing. The result: `revealed` and the first `associated` are mutually
flagged ambiguous; the second `associated` (in the second, `while`-separated clause) stands alone, unambiguous.
**This was not tuned.** Resolving it would require real subject/complement grammar (detecting that a bare
post-verbal `was`-clause without `that` is still the reported content), which is outside this increment's
deterministic-local-boundary-word design and would risk exactly the kind of grammar-expansion the I4-1b/c
increments were careful to keep narrow. It is reported here as a genuine, disclosed limitation (§12), as instructed
— p41 was not tuned to, in either direction.

**p36, p40, and p52 — named in the directive's "pay special attention to" list — are not achieved-outcome bindings
at all in this map, and that is reported plainly rather than guessed around:** `p36` and `p52` are
`explicit_category_terms` (`category_evidence` role); `p40` is `model_nomination_only` (`named_brain_region_or_
network` role). Neither uses `_match_achieved_outcome`, so neither has anything for this increment's audit to
attach to. This is stated directly, not silently omitted.

## 11. Cross-domain generalisation (section 11)

24 twins across architecture, clinical, and language-learning domains, each with: a direct result, a prior-work
result (not suppressed), a review-style result (`concluded` absent from the lexicon, `associated` or similar
carries the match), a hypothesis-plus-result sentence (attaches only to the result), an interpretation-plus-result
sentence, a multiple-result-assertion sentence, a negated result (mechanically identical to the unnegated case —
this module has no concept of negation), and an absence-of-evidence sentence (match remains representable). **24 /
24 pass**, no domain-specific rule anywhere in the implementation.

## 12. Unresolved attachment failures (disclosed, not fixed)

- **Elliptical `that`-omission after a reporting verb** (`"revealed X was associated with Y"` with no `that`) is
  reported as ambiguous rather than resolved. Real example: p41 (§10). Fixing this would require subject/
  complement grammar beyond this increment's deterministic boundary-word design.
- **The target-aware seam gap** (§9): no production call site currently supplies a value to disambiguate which
  local assertion, among several in one passage, a specific role/requirement is actually asking about. This
  module supplies spans; it does not supply that missing value.
- **Duplicate-proposition-id artifacts** (§10): when several proposition rows share one exact passage, which one's
  id is "the" bound id is currently an artifact of ledger order, not of content. This module's span output does
  not change which proposition_id a production binding would carry — only a future production change could.

## 13. Zero-runtime-change proof

- **Static guards, both directions.** No non-test module anywhere in the repository (`app`, `integrations`,
  `experiments`, `tools`, `tests`, `mcp_server`, `tui`, `sync_server`) references `achieved_outcome_span` by name
  (new guard, this increment). This module's own source never contains the literal substring naming the I4-1
  classifier module (confirmed directly), so it cannot itself have tripped that classifier's own pre-existing
  unwired guard.
- **Change set against `HEAD` (`0a5420a3`).** Only `experiments/ask_cli_revised/` files changed; `git diff --stat`
  against `app`/`integrations`/`tools`/`mcp_server`/`tui`/`sync_server`/`tests` is empty.
- **Attempt2 AnswerPlan replay**, re-run against the same scratch stamped-run baseline used for I4-1b/c: all 7
  output files byte-identical; `plan_sha256 f7ce7d3c618745872ad66bfa1cbb9e4f60376c932e9f147c7033c4c802f2c09a`
  identical.
- **The same 16 I4-1b parity-surface test files**: **444 passed, 18 subtests passed** — the exact I4-1b/c totals,
  confirmed file-by-file.
- **Full offline experiments suite (161 files, 4 parallel workers).** **3512 passed, 7 failed, 12 skipped, 276
  subtests passed.** The 7 failures are in exactly the same 7 files as the I4-1b/c baseline
  (`test_corpus_and_referents.py`, `test_offline_boundaries.py`, `test_schema_validation.py`,
  `test_storage_cli_boundaries.py`, `test_e2e_run.py`, `test_hierarchy_contract.py`, `test_hierarchy_e2e.py`),
  each failing exactly 1 test — the identical pre-existing/environment-artifact set, zero new failures. The passed
  count is higher than I4-1c's recorded 3365 because this run includes the two new I4-1d test files themselves
  (57 passing cases) plus whatever incidental test growth occurred elsewhere on this branch since that count was
  taken; the failing-file set is what was cross-checked, and it is unchanged.

## 14. Lint

`ruff format` (applied) and `ruff check` pass on both new Python files: `achieved_outcome_span.py` and
`test_achieved_outcome_span.py`.

## 15. Recommendation: NOT a direct transition to the old I4-2 semantics

I4-1d delivers attachment — it does not, and must not be read to, resolve the question the earlier I4-2 sketch
assumed was already settled: that a role binding can simply inherit whatever single assertion in a passage "wins."
The real preserved-data audit (§10) shows that even with exact spans in hand, **7 of 8** distinct achieved-outcome
proposition ids resolve to one unambiguous local assertion, but **p41 does not**, and the duplicate-proposition-id
pattern (p1/p4/p8/p24) shows that *which* proposition id a binding carries is already decoupled from *which*
assertion actually produced the match.

The next architecture step must not treat this as "now wire assertion spans into the mapper and gate on
`finding_authority`." That would silently reintroduce exactly the conflation this track exists to avoid —
**evidence provenance/directness determines HOW evidence counts, not automatically WHETHER it counts.** A sound
next step needs, at minimum: (a) a production-side decision for what a binding does when its passage contains more
than one valid local assertion (bind the first deterministically, as today, but now *disclosed* as a choice rather
than invisible; require a model to disambiguate; or mark the binding structurally ambiguous) — a policy decision,
not an attachment mechanism; (b) a separate, explicit directness/admissibility design for *how* a `prior_work` or
`candidate`-authority assertion should count toward a requirement, never a blanket exclusion; and (c) the
target-aware seam gap (§9) closed first, since without it even a perfect span cannot tell a binding which of
several local assertions its own requirement actually meant.

**I4-2, as previously scoped, remains blocked** — not because spans are unavailable (they now are), but because
the acceptance *policy* for indirect/ambiguous evidence has not yet been designed, and this increment was
deliberately kept neutral on it.
