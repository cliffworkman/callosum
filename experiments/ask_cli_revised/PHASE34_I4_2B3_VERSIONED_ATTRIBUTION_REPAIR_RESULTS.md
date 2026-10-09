# PHASE 34 / I4-2b3 — Versioned attribution repair and bounded context transport

## Scope and checkpoint

This increment implements attribution-only `sufficiency-semantics-v6`: collect exactly the v5 grounded,
role-instance-relevant candidates, then annotate their ownership under `i4-2b3.0`. It does not decide
whether evidence may satisfy a requirement. Guards remain prefilters; all ten real candidates retain
`admissible=None` and `inadmissibility_reason=None`.

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.

- Accepted production starting HEAD: `d2f3e1619a820b27479e7e00abb1e1e002fd1882`.
- Docs-only checkpoint and implementation starting HEAD: `645647044dd8cb032665283014c29bfce35bf69d`.
  Its four files are the accepted I4-2b0, I4-2b1 and I4-2b2 reports and experiment lineage.
  It passed its hooks, was pushed, and the worktree was verified clean before implementation.
- Final implementation HEAD is the single commit containing this report, directly after that checkpoint.
  Resolve its exact hash with `git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_2B3_VERSIONED_ATTRIBUTION_REPAIR_RESULTS.md`.
  The completion message records the resulting hash; a commit cannot contain its own content-derived hash.

The original six-exclusion support-policy projection remains preserved in I4-2b0 as the
**uncorrected-attribution counterfactual**. I4-2b1's revised interpretation is confirmed:
all six are recoverable attribution failures. Recommendation B remains explicit:
**fix attribution first; do not weaken the conservative support-policy default**.

## Version dispatch and legacy freeze

`ASSERTION_AUTHORITY_RULESET_I4_1F = "i4-1f.0"` and
`ASSERTION_AUTHORITY_RULESET_I4_2B3 = "i4-2b3.0"` are explicit selectors.
`RULESET_VERSION` remains a permanent alias for I4-1f. An omitted selector always selects legacy;
there is no mutable current selector or environment-driven classifier selection.

The six public APIs—classify_assertion_authority, classify_target_assertions,
locate_containing_assertion, classify_surface, classify_all_occurrences, and aggregation—accept
keyword-only ruleset_version and ownership_context. Invalid/non-string rulesets raise ValueError
before parsing. Legacy plus ownership_context is invalid. Corrected plus bare structural_context
is invalid. Legacy serializers return exactly their historical key sets, with no null proof additions.

Before production edits, `assertion_authority_legacy_freeze.json` recorded the checkpoint source
SHA-256 `593a5296177a6b022e6e8a518997f8c4418a0bb508ff7a3e63c299ca443a9762`
and the individual SHA-256 of `ast.dump(node, include_attributes=False)` for 119 legacy constants,
private functions, and unchanged public projection helpers. All 119 still match. Tokenization,
sentence splitting, assertion boundaries, labels, owners, kinds, aggregation, veto/caption handling,
and legacy _effective are unchanged. The six historical API implementations are retained as legacy
implementations behind the new wrappers.

Corrected ownership is post-parse. Explicit/previously resolved ownership wins. For unresolved
assertions, the resolver collects eligible R1/R2/R3 proposals. One unique relation is accepted;
zero stays unresolved; conflicting relations stay unresolved with inspectable conflict metadata.
R1 failure does not invalidate independently valid local R2/R3 evidence.

## Resident context transport and sidecar

`ownership_context.py` is a pure supplied-data module. It imports only stdlib copying, hashing,
JSON serialization and regular expressions. It performs no filesystem, database, network, model,
retrieval, classifier or support-policy calls.

At E2E boundaries, the already resident evidence packets and sealed propositions build the index.
The same corrected-path snapshot reaches the diagnostic mapper and post-recovery dry inventory.
The initial and final trace owners persist `17_ownership_context.initial.json` and
`17_ownership_context.json`, both with schema `ownership-context-v1`. Historical v5 ignores
even a supplied index; a spy proves it never reads context or enters corrected classification.
Old sealed artifacts are never rewritten.

The index binds physical paper/chunk/span identity and quote hash to a content-addressed entry.
Entries reference deduplicated source snapshots containing paper, attachment, chunk, source-attachment
checksum, extracted-text SHA-256, extraction tool/version, chunk version/type, and exact source bytes.
Entries record quote SHA-256, exact occurrence bounds, containing paragraph bounds, and boundary provenance.
The bundle has a separate manifest digest. Entry identities do not depend on unrelated recovery additions.

A usable anchor must be in recorded context_read and have an undiscarded matching resident packet.
Disagreeing copies, missing source identity, unsupported paragraph provenance, nonunique exact quote
occurrences without an explicit verified occurrence locator, cross-paragraph quotes, or invalid hashes/spans
fail closed. No fuzzy or first-match lookup is available. Context views are defensive copies, and supplied
occurrence spans are copied into snapshots.

Unit transport associates context with every supporting proposition/physical anchor. It never selects the
first pooled proposition as semantic authority. Distinct pooled R1 contexts must all resolve and agree;
missing/conflicting sources leave ownership unresolved without deleting or narrowing candidate IDs.
Duplicate uses of the same physical proof are deduplicated. Seeded packets without chunks are supported:
R1 is unavailable while R2/R3 can still operate on the supplied quote.

## Three bounded rules

### R1 — owner.local_antecedent.v1

**R1 v1 is a bounded discourse resolver, not a general coreference/anaphora engine, synonym matcher,
or semantic discourse parser. Widening requires new preregistration and versioned behavior.**

The anchored quote must use the preregistered “Across these levels…” anaphor. Its containing preserved
paragraph must have exactly one explicitly owned method_or_description study-act introduction with
the supported enumerated list grammar, followed by one matching “At [the] level [of] ITEM” header per
opaque item, in order. Case/whitespace and leading articles are mechanical normalization; parenthetical
list material is masked. There is no stemming, synonym expansion, ontology, or domain vocabulary.

Ownership is the introduction's owner, including attributed_external for a prior-owned introduction.
Missing/duplicate headers, competing introductions, citation conflict, owner/discourse/paragraph reset,
unsupported grammar or bad identity/span proof refuse resolution. Explicit target ownership remains authoritative.
The mapper supplies legacy-classified owner records; the context helper itself never imports a classifier.

R1 provenance records the source identity, stable context entry, quote hash and occurrence, paragraph,
owner assertion, header and anaphor spans, list items, resolver version, rule ID and proposed relation.
Validation bytes are transport-only; candidate proofs do not copy arbitrary source paragraphs.

### R2 — owner.adjacent_cited_continuation.v1

An unresolved result may inherit attributed_external from the immediately preceding sentence's
final assertion only when that predecessor is explicitly parsed prior_work/result, both assertions
have the same nonempty recognized citation set, and both are in the same paragraph without a
discourse/ownership reset. Unparsed intervening text is not skipped. R2 never recursively seeds itself.

Normalization operates only on legacy-recognized citation tokens: reordered lists and ascending
recognized ranges can express the same set. Missing/different/partially overlapping sets, descending
ranges, statistics, bare numbers, unsupported bracket syntax, paragraph boundaries, current-owned
predecessors and resets do not establish external ownership. Citation presence alone is insufficient.

The proof records exact quote/target identity, predecessor and owner spans, sentence/paragraph bounds,
citation spans and normalized citation set. No reference-list or library lookup occurs at runtime.

### R3 — owner.results_coordination.v1

Only an initial explicit Results run-in label can resolve a parallel second result clause joined by
comma + while/whereas in the first sentence. The first clause must be current-document/result under
legacy parsing. The target must be unresolved/result and meet the existing narrow Results safeguards,
plus a full target-region hedge check. The latter catches subject-position “probably” without changing
legacy hedge metadata or parser behavior.

Target citation, prior framing/object, replication, hedge/modal, negation, ref/refs/cf/et-al marker,
caption, owner/reset conflict, semicolon, later sentence and later-clause chaining refuse this rule.
Separate assertion identities remain separate. General Results label scope is not widened.

The proof records the quote/target identity, Results label, first-assertion span, connector and its span,
and first-sentence span.

## Candidate schema and annotation boundary

The corrected mapper calls the preserved v5 collector first, including unchanged guard, dependency,
localization, deduplication and target-relevance behavior. It then annotates only those candidates.
Runtime assertions and replay tests check the same attachment, assertion text/span, kind, aggregation,
authority_veto, IDs/order, predicate/content spans, caption flag and every other frozen candidate field.
The legacy representative binding is retained.

Allowed differences are assertion_relation, its derived support_label, and optional corrected-only
`attribution`:

- schema_version = ownership-attribution-v1; classifier_id; ruleset_version;
- assertion_relation; source_resolution; ordered rule_ids;
- target quote_sha256, span_proposition_id, assertion_span and supporting_proposition_ids;
- bounded rule-specific proofs; context_status and context_failure.

Legacy candidate rows have **no attribution key**. The engine validates the optional schema as data;
it does not call classification or policy. Neither a support label nor an ownership proof becomes
scientific support text.

## Explicit version-routing audit

| Routing site | v6 selection |
|---|---|
| sufficiency_engine identity/readability | v6 current; v5 explicitly historical/readable; unknown versions still rejected |
| category goal gate and recomputation | Explicit v4/v5/v6 membership; same category semantics |
| achieved-outcome mapping | v6 wrapper annotates v5 collection; v5 explicitly selects i4-1f.0 |
| cardinality mapper | Explicit v4/v5/v6 membership; same observations and satisfaction |
| direction mapping / direction_target table | Explicit v6 entry uses the same target-aware behavior |
| relation_witness containment table | Explicit v6 entry uses the same case-insensitive containment rule |
| recovery targets and searched-target terminal behavior | Explicit v4/v5/v6 membership; no query or stop-search change |
| E2E final obligation inventory | Explicit v6 membership; same raw-final-target rule |
| effectiveness / parent propagation / AnswerPlan | Existing machinery unchanged; versioned inputs explicitly supported through audited delegates |

No numeric/floating inheritance was introduced. PLAN_VERSION remains `answer-plan-step2-v4`.
No same_local_assertion registration, ParentClaims/AnswerPlan implementation edit, support-policy
evaluation, guard retain-and-flag, authority-veto gate, or claim-goal authoring was added.

## Real preserved replay

The replay boundary verifies the three existing ledger/map hashes and packet SHA-256
`1949dc56e4abcbb58f7ebf512387c3c6041bdf0a2176facd64aaf44bea1e83f6`.
It holds recorded model nominations fixed and runs the real deterministic mapper and downstream
machinery. This is an offline replay, not live E2E or a fresh model decision.

| Child/use | Coordinate anchor | Assertion span in quote | v5 relation | v6 relation | Proof |
|---|---|---|---|---|---|
| c1 | p2; supporting p2,p11 | [37,264) | unresolved | current_document | R1, chunk 34974 |
| c4 first instance | p11; supporting p11,p2 | [37,264) | unresolved | current_document | Same physical R1 proof |
| c4 second instance | p40 | [147,273) | unresolved | attributed_external | R2, shared citation set {6} |
| c8 anger | p41 | [208,372) | unresolved | current_document | R3 |
| c8 dominance | p41 | [208,372) | unresolved | current_document | R3 |
| c8 threateningness | p41 | [208,372) | unresolved | current_document | R3 |

Exactly six relation uses change. The two p41 assertion-1 uses retain current_document and [43,200).
c2/p47 and c3/p7 retain their original relations. There is no seventh correction.

| Gate | v5 | Attribution-only v6 |
|---|---:|---:|
| Candidate supports | 10 | 10 |
| Evaluated policy decisions | 0 | 0 |
| Filled / missing achieved-outcome evidence roles | 10 / 16 | 10 / 16 |
| Evidence-role state changes | — | 0 of 26 |
| Requirement-state changes | — | 0 of 13 |
| Recovery targets | 48 | 48, identical |
| ParentClaims | 17 | 17, identical |
| AnswerPlan nodes | 9 | 9, identical semantic content/statuses |
| Downstream invariants | 33 passing | 33 passing |
| Test-only conservative empirical predicate | Not applied | 10 of 10 pass |

The five guard-excluded candidates from the earlier retain-and-flag counterfactual are **not collected**.
c10 and c12 gain no candidates. c8 retains open-list semantics. c5/c6 inheritance, c9 pairing,
witnesses, relations, direction/effectiveness, recovery and rendered Layer 1 are unchanged.

The whole combined replay compares equal after restoring the six allowed relation/label corrections,
removing only the new candidate attribution objects, normalizing v6 identity to v5, and excluding
the derived plan hash. Existing AnswerPlan attribution fields are retained in this comparison.
The plan hash changes because its containment/direction semantic identities change, not because
its semantic content or renderer changed. Full v6 byte identity to v5 is neither claimed nor expected.

## Frozen replay baselines

Canonical replay bytes are sorted JSON, indent 2, ensure_ascii=False, UTF-8, CRLF, one terminal newline,
matching the accepted Windows baseline serialization.

| Version | Combined replay SHA-256 |
|---|---|
| Historical v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| Historical v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| Corrected attribution-only v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |

The v6 context manifest is
`3e3a72f4cd9be783e7932024f004b72d8177cae7788398d42ac3413567218d02`
(11 source snapshots, 14 context entries for the supplied sealed corpus).
`attribution_i4_2b3_replay_baseline.json` freezes these values. Future v7 must preserve explicit v6
replay exactly as well as the older baselines.

## Matrix, isolation and verification

`attribution_i4_2b3_preregistered.json` was materialized before implementation from the accepted
32-case I4-2b1 battery and every E01–E40 I4-2b2 row. No historical expected ownership label,
including pp_p41_a2, was changed.

The new tests cover every initial case and expanded E-row variants: real three contexts; absent,
malformed, mismatched and repeated context; current/prior/absent/competing antecedents; duplicate/missing
headers; explicit owner precedence; citation normalization and nonadjacency; both connectors with
hedge/modal/negation; caption and citation-like vetoes; unsupported versions; conflicting proposals;
pooled agreement/conflict/missing proof both at helper and mapper boundaries; append-stable entry IDs;
seed packets without chunks; whole-input attachment; arbitrary neutral list items; and candidate ordering.

384 historical text fixtures additionally compare complete omitted/explicit legacy results across public
APIs. An opt-in paired-call pytest plugin runs the actual historical battery calls both ways using their
original arguments/occurrences, including matching ValueError behavior. Original frozen fixture hashes
and expected outputs remain intact.

Model-facing equality tests compare the real corpus's candidate rows, category descriptions, request
fingerprints and nomination prompt text across v5/v6 unit transport. Recovery records/queries are exactly
equal. Retrieval/search/ranking code is untouched. Context never enters target_relevance input text.

Static guards keep sufficiency_mapping.py as the sole production classifier consumer. The exact context
transport allowlist is ownership_context.py, sufficiency_mapping.py, sufficiency_diagnostic.py and e2e.py;
tests/replay are separate. Negative fixtures prove an unauthorized consumer fails. No directory-wide
production exemption was added. assertion_authority.py gains only stdlib JSON for content-hash validation;
the old purity import allowlist is updated for that one import. The mapper API allowlist adds only the two
explicit ruleset constants and classify_target_assertions, needed to supply legacy owner records.

| Gate | Final observed result |
|---|---|
| New attribution/context/preregistered/replay tests | 558 passed |
| Actual historical batteries with every API call paired omitted/explicit legacy | 443 passed, 9 existing xfailed |
| Full declared-environment offline experiments suite, four workers | 4334 passed, 5 independently known failures, 12 skipped, 9 xfailed, 276 subtests passed; no collection errors; 183.67 seconds |
| Optional psutil-dependent offline module, existing Anaconda | 7 passed |
| Combined full experiments coverage across environments | **4341 passed; five known failures; zero unexplained new failures** |
| Ruff lint / format | Passed for all 23 changed/new Python files |
| Bandit / Tach | Passed |
| Legacy AST freeze / exact v4 and v5 / frozen v6 / 33 invariants | Passed |

Final staged-file pre-commit checks pass for whitespace, EOF, merge conflicts, large files, Ruff,
Bandit and Tach. The sole remaining hook failure is the pre-existing 615-line
app/frontend/js/20_synthesis.jsx limit. The frontend is byte-unchanged relative to the docs checkpoint.
The user-authorized --no-verify exception applies only to this known line-budget failure; no semantic,
replay, parser-freeze, static-boundary or regression gate is bypassed. The first hook invocation selected
system Python without Bandit/Tach; rerunning with the project's .venv/Scripts on PATH passed both.
The EOF fixer removed one extra report newline; frozen data files were unchanged.

### Independently reconfirmed baseline/environment failures

The same five tests fail against saved, hash-recorded checkpoint production modules and current modules,
under the same network-denial plugin. They are not marked xfail or repaired in this increment.

| Test | Unchanged cause |
|---|---|
| ask_070/test_corpus_and_referents::test_dev_eval_separation | Missing frozen/dev_inputs_v0.json |
| ask_070/test_schema_validation::test_real_frozen_nonsemantic_artifact_schemas | Missing frozen/corpus_presence_v0.json |
| test_e2e_run::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored | Existing Ollama /api/tags probe precedes mocked runtime; connection denied offline |
| test_hierarchy_contract::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts | Existing hierarchy_contract.py code-input pin drift |
| test_hierarchy_e2e::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects | Same pin rejection returns 3 instead of 0 |

The psutil-dependent contract_directed/tools/test_run_gate_integration_live.py is an offline scripted module
despite its name. It is excluded only from the declared-environment collection and separately passes all
seven tests in the existing dependency-complete Anaconda environment. No dependency installation occurred.

Initial gate triage also found the two expected test adaptations for explicit legacy dispatch/new mapper API
references, and an incorrectly specified optional-module exclusion path. These were corrected before the final
gate; none is treated as a passing test or hidden regression.

No external search, live retrieval, model invocation or live E2E occurred. The offline plugin denies socket
connections, except where a test subtree already installs and tests its own stricter offline boundary.
The known Ollama probe is denied rather than allowed.

## Exact changed files

- `CONTRIBUTION-LINEAGE.md`
- `PHASE34_I4_2B3_VERSIONED_ATTRIBUTION_REPAIR_RESULTS.md`
- `assertion_authority.py`
- `assertion_authority_legacy_freeze.json`
- `attribution_i4_2b3_preregistered.json`
- `attribution_i4_2b3_replay_baseline.json`
- `direction_target.py`
- `e2e.py`
- `ownership_context.py`
- `relation_witness.py`
- `sufficiency_diagnostic.py`
- `sufficiency_engine.py`
- `sufficiency_mapping.py`
- `sufficiency_recovery_targets.py`
- `test_achieved_outcome_span.py`
- `test_assertion_authority.py`
- `test_assertion_authority_i4_1b.py`
- `test_assertion_authority_i4_1c.py`
- `test_assertion_authority_i4_1f.py`
- `test_i4_1j_local_grounding.py`
- `test_i4_2a_local_grounding.py`
- `test_i4_2a_replay.py`
- `test_i4_2b3_attribution.py`
- `test_i4_2b3_legacy_parity_plugin.py`
- `test_i4_2b3_replay.py`
- `test_sufficiency_semantics_version.py`
- `test_sufficiency_support_schema.py`
- `test_sufficiency_v4_category_satisfaction.py`

All paths above are under experiments/ask_cli_revised. Accepted planning documents, sealed source artifacts,
frozen old batteries, authored sufficiency contracts, PLAN_VERSION, app/frontend, ParentClaims and
AnswerPlan implementation files are untouched.

## Reproduction

From the canonical worktree, run the new test files with pytest; the replay gates require the preserved
Attempt2 run named in test_i4_2a_replay.py. The optional module uses the existing Anaconda environment.
The paired historical invocation is:

```text
python -m pytest experiments/ask_cli_revised/test_assertion_authority.py experiments/ask_cli_revised/test_assertion_authority_i4_1b.py experiments/ask_cli_revised/test_assertion_authority_i4_1c.py experiments/ask_cli_revised/test_assertion_authority_i4_1f.py -p experiments.ask_cli_revised.test_i4_2b3_legacy_parity_plugin
```

Local evidence logs and full replay/context artifacts are under .local/i4-2b3:
new-tests-final.log, historical-paired.log, full-final.log/xml, known-head.log, known-current.log,
optional.log, baseline-module-hashes.json, v6.json and ownership-context.json. The committed manifest
and tests provide the durable replay gate; local logs are not new production inputs.

## Readiness and stop

**READY for separately authorized v7 support-policy planning.** The bounded attribution repair is
implemented and validated, and its attribution-only v6 baseline is frozen. This is not authorization
or a readiness claim for immediate policy/guard implementation: that increment must preserve v6,
apply the accepted orthogonal aggregation contract, and undergo its own scoped gates.

R1 remains limited to the preregistered grammar. Missing source bytes, unsupported discourse structures,
ambiguous contexts and conflicting ownership remain unresolved; no fallback library lookup is available.
The preserved corpus still does not supply real synthesis or caption candidate examples. Attribution repair
does not validate a future policy layer, general anaphora, or future rendering changes.

Stop after I4-2b3. No v7 policy/guard integration, same_local_assertion registration, I4-3 implementation,
ParentClaims/AnswerPlan semantic change, or I2-3 is included.
