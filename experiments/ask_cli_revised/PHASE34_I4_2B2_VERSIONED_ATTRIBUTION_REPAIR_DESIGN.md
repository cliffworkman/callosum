# Phase 34 / I4-2b2 — Versioned attribution repair design audit

**Planning/docs only. No attribution, policy, guard, or version implementation.**
**Recommendation:** version the classifier explicitly; introduce attribution-only sufficiency v6 in a
separately authorized implementation; reserve the later policy/guard behavior change for a subsequent
semantic version (expected v7). **READY for the bounded attribution implementation described here;
NOT READY to implement support policy as part of it.**

Date: 2026-10-08. Design audit: Cody/Codex. Scope and prior decisions: Cliff Workman.
Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
HEAD: `d2f3e1619a820b27479e7e00abb1e1e002fd1882`.

## 1. Scope and audit baseline

[I4-2a](PHASE34_I4_2A_LOCAL_GROUNDING_INTEGRATION_RESULTS.md) is accepted.
[I4-2b0](PHASE34_I4_2B0_SUPPORT_POLICY_GUARD_AUDIT.md) and
[I4-2b1](PHASE34_I4_2B1_OWNERSHIP_UNCERTAINTY_AUDIT.md) are accepted planning. Their reports and two
lineage entries were already uncommitted at this turn's start; they are preserved, not overwritten or
mistaken for this increment's changes. This increment adds only this report and one experiment-lineage entry.

The accepted repair targets are three generic ownership failure families: local antecedent context
(p2/p11), adjacent cited prior-work continuation (p40), and bounded Results coordination (p41 assertion 2).
The six role-instance uses are recoverable; support policy must not compensate for an attribution defect.
The conservative empirical default remains provisionally accepted.

The hard historical gate is exact explicit `sufficiency-semantics-v5` combined replay:

```text
109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77
```

The unchanged offline harness was rerun during this audit. It matched both the saved decoded replay
and this byte hash, using the accepted Windows-newline serialization. Its input ledger/map hashes
were checked by `test_i4_2a_replay.inputs()`. No new corrected classifier or semantics version was
installed, and no proposed-rule implementation was run.

## 2. A1 — Current architecture: identity is not dispatch

| Surface inspected | Current fact | Compatibility consequence |
|---|---|---|
| `assertion_authority.RULESET_VERSION` | Global string `i4-1f.0` | Describes one global implementation; no version registry/dispatch |
| `classify_assertion_authority` | text + target offsets, is_caption, structural_context, locator | No version parameter |
| `classify_target_assertions` | Same optional inputs; returns separate assertion records | No version parameter |
| `locate_containing_assertion` | Thin single-governing-assertion join over multi API | No version parameter |
| `classify_surface`, `classify_all_occurrences`, `aggregation` | Delegate into the same global classifier | Also no version parameter |
| `_classifier_public()` | Emits id, global ruleset, pure, unwired | Identity is in top-level classifier output, not an executable freeze |
| `structural_context` | Optional bare owner_signal: this_study or prior_work | No bounded source proof, context hash, or target identity |
| `_effective` | Parsed owner, then supplied owner signal, then narrow Results resolver | Supplied signal can affect otherwise-unowned records; not a verified R1 resolver |
| Mapper `_bind_achieved_outcome_v5` | Calls `aa.locate_containing_assertion(passage, start, end)` | No explicit ruleset, locator, or ownership context |
| Mapper candidate construction | Stores relation, kind, aggregation, veto, spans, plural IDs, label | Discards classifier/ruleset, source_resolution, rule trace, and context proof |
| Legacy binding provenance | deterministic_mapping / achieved_outcome_predicate / model=None / plural IDs | Does not identify classifier ruleset |
| v1–v4 mapping | Historical whole-passage predicate path | Does not use the new local assertion ownership path |
| v5 mapping | Exact version branch selects local grounding, which calls the global classifier | A global classifier edit would change historical v5 despite its map stamp |

Code anchors: [assertion_authority.py](assertion_authority.py) (RULESET_VERSION; public signatures;
_all_assertions; _effective; _classifier_public),
[sufficiency_mapping.py](sufficiency_mapping.py) (_bind_achieved_outcome_v5 and _bind_role_candidates),
[sufficiency_engine.py](sufficiency_engine.py) (version invariant and new_candidate_support),
[sufficiency_diagnostic.py](sufficiency_diagnostic.py) (units_by_child and orchestration), and
[sufficiency_identity.py](sufficiency_identity.py) (explicit stamping and historical reading).

The classifier's old `unwired` metadata/docstrings are historical wording; the tests now authorize
exactly the mapper as a production consumer. Do not confuse that flag with an enforced absence of a caller.

### Tests and static guards

- I4-1b/c tests assert that RULESET_VERSION starts with `i4-1`, and pin frozen battery file hashes.
- `test_i4_1j_local_grounding.test_ruleset_version_deliberately_unchanged` pins **exactly**
  `i4-1f.0`. Tests do not only pin behavior.
- I4-1, I4-1b/c/f, and I4-1j batteries pin historical outputs, including unresolved p41 assertion 2.
- `test_assertion_authority` and `test_assertion_authority_i4_1f` scan production trees for the
  classifier name with one exact mapper exception. I4-1j similarly restricts local-grounding primitives.
- Purity guards restrict classifier imports to __future__, hashlib, re, collections and prohibit I/O.
  Other guards forbid participant/population noun cues and q_aib vocabulary.
- Tests also pin current sufficiency/PLAN_VERSION separately. None selects an old classifier at runtime.
  Current static consumer guards assume one entry family but do not freeze its global implementation.

**Finding:** a sufficiency-version bump alone is insufficient. Historical dispatch must select a
preserved classifier contract, including parser behavior and output shape.

## 3. A2/A8 — Compatibility architecture comparison and choice

| Option | How it could preserve v5 | Cost / risk | Decision |
|---|---|---|---|
| A: version assertion_authority itself | All public wrappers accept an explicit ruleset; v5 requests legacy; corrected path requests new | Small dispatch surface; must freeze common parser and old serialization, not just _effective | **Recommend** |
| B: version only mapper seam | Mapper selects old/new ownership helpers | If helpers still share mutable global classification, old behavior drifts; also moves attribution logic into mapping or creates a hidden second classifier API | Reject as the sole architecture; mapping still selects A's version |
| C: preserved old entry + new corrected entry / snapshot | Old entry and helpers are truly frozen; new entry separately selected | A wrapper alone does not freeze shared helpers. A full copied snapshot duplicates a large parser and complicates guards/maintenance | Valid fallback if parser divergence becomes necessary; unnecessary now |

For each option the conceptual contract is identical: v5 yields unresolved for all three target
assertions; the explicitly corrected path yields current_document / attributed_external /
current_document. Only A with real legacy dispatch or C with a real preserved implementation provides
that guarantee directly. B becomes equivalent to A/C once its helper paths are adequately frozen.

### Selected API and frozen default

Proposed names, **not added by this audit**:

```text
ASSERTION_AUTHORITY_RULESET_I4_1F = "i4-1f.0"
ASSERTION_AUTHORITY_RULESET_I4_2B3 = "i4-2b3.0"
RULESET_VERSION = ASSERTION_AUTHORITY_RULESET_I4_1F  # permanent legacy compatibility alias

classify_assertion_authority(...,
    ruleset_version=ASSERTION_AUTHORITY_RULESET_I4_1F, ownership_context=None)
classify_target_assertions(...,
    ruleset_version=ASSERTION_AUTHORITY_RULESET_I4_1F, ownership_context=None)
locate_containing_assertion(...,
    ruleset_version=ASSERTION_AUTHORITY_RULESET_I4_1F, ownership_context=None)
```

Thread the same keyword-only selection through classify_surface, classify_all_occurrences, and
aggregation. Omission **always means legacy**, not “latest/current.” Unknown/non-string rulesets raise
ValueError before classification. No mutable module-global selector, environment flag, or caller monkeypatch
selects production behavior.

For the legacy ruleset, return the **exact old key set and values**, including classifier metadata.
Do not add null proof fields to old outputs. Retain the legacy structural_context contract unchanged.
Passing the new ownership_context to a legacy classifier call is an invalid API combination; fail loudly.
At the diagnostic v5 boundary, the new optional transport is ignored and never passed to the classifier.

For the corrected ruleset, reject an unverified bare structural_context owner_signal as a substitute for
ownership proof. Accept only the typed target-scoped context contract below. Normal no-context calls
still support R2/R3 on supplied quote text.

Keep the existing tokenizer, sentence splitting, assertion builder, regions, source/kind/veto/aggregation
calculations, and legacy _effective behavior frozen. Add a new post-parse ownership resolver over those
records. The new resolver may inspect raw local delimiters; it must not change tokenization or splitting
for either ruleset. If a later repair requires a parser change, put it behind an explicit new parser
path/version; never silently improve a shared legacy helper.

Preserve existing parsed owners and existing legitimate resolved ownership. For an otherwise unresolved
record, collect eligible R1/R2/R3 proposals; accept only a unique proposed relation. Conflicting proposals
leave it unresolved with an inspectable conflict reason. Explicit current/external ownership is not
overridden by contextual proposals. This conflict rule concerns competing ownership proofs, not
attachment/guard/policy aggregation.

### Mapper selection and invariant-preserving annotation

| Sufficiency semantics | Classifier choice | Candidate behavior |
|---|---|---|
| v1–v4 | Existing historical mapping | Unchanged |
| v5 | Explicit i4-1f.0 | Exact accepted original output |
| Proposed v6 | i4-2b3.0, after legacy grounding/relevance | Correct ownership + proof, policy still unevaluated |

Future v5's join must name the legacy constant explicitly even though the default is frozen.
The proposed v6 binder first uses the preserved v5 collector for **the same guards, localization,
dependency resolution, deduplication, relevance, ordering, and legacy representative**. It then annotates
the resulting candidates through the selected corrected classifier, asserting that each assertion span
and exact_text is unchanged. Recompute only relation, its derived display label, and new attribution
metadata. A mismatch in boundaries is an implementation error, not permission to rebind evidence.

This wrapper/annotation shape minimizes risk and ensures context never broadens candidate collection.
Do not use corrected source/authority as a filter, select a different representative, or add candidates.

## 4. A3/A6 — R1 local antecedent proof and context transport

### Production transport facts

`sufficiency_diagnostic.units_by_child` has sealed quotes, proposition IDs, physical anchors, and
proposition_passages. It **does not have full source chunk text**. `stages.seal` receives evidence
packets but emits evidence_spans from candidate_spans, not full packet chunks. Recorded
`provenance.context_read` IDs locate context but do not reproduce its bytes.

`e2e.Sink.evidence_packets` already holds packet chunks before U1 and U2. The initial and final
diagnostic calls, plus the post-recovery dry request inventory, are the narrow transport seams.
The seeded-ledger path can construct packets with candidate_spans but **no chunks**, so missing context
is a real supported case, not an exceptional excuse to query the library.

The preserved run has enough data in its existing 08_evidence_packets.jsonl. Stable source identity is
chunk ID + paper/attachment identity + source attachment checksum + exact extracted-text SHA-256 +
extraction/chunk provenance. Chunk ID or attachment checksum alone is insufficient: extraction can change
without changing PDF bytes.

### Selected transport, no hidden lookup

Introduce one pure, generic module, proposed `ownership_context.py`, with two responsibilities:
build/validate a bounded context index from already supplied sealed rows and packet dictionaries;
resolve R1 over a supplied paragraph and supplied legacy owner records. It imports no classifier and
performs no filesystem, database, network, model, or retrieval I/O.

Add optional `ownership_context_index=None` to compute_diagnostic_sufficiency_map and its internal unit
transport. E2E constructs it from the already resident packets, supplies it only on the corrected path,
and supplies the same snapshot to the U2 dry inventory and actual remap. Existing offline replay explicitly
loads the preserved packets at the harness boundary. No locator lookup occurs inside classification.

The index is keyed by each proposition's physical anchor and quote digest, not by a role name, question,
paper allow-list, or first pooled proposition alone. Attach context **per proposition/physical anchor**
as a separate unit field; never concatenate it into unit.passage, exact_text, candidate rows sent to a
model, target_relevance inputs, or recovery queries. Legacy versions do not inspect this field.

Persist a versioned ownership-context sidecar through the existing trace owner for future runs.
Deduplicate paragraph/chunk text there; candidate proofs carry references, not copied arbitrary prose.
Use canonical content hashes for individual entries and a bundle manifest hash for replay integrity.
Proofs reference stable entry hashes so adding recovery entries does not rewrite earlier proof identities.
Do not alter old sealed files or retroactively fill legacy maps. The current audit creates no sidecar.

For a frozen replay, reconstruct the same sidecar in memory from hash-verified saved packets. Require
the evidence-anchor chunk to be present in that proposition's recorded context_read and an undiscarded
matching source packet. Reject disagreeing copies for the same physical source. A saved quote must have
a unique exact occurrence in the supplied chunk (or an already verified exact occurrence locator);
normalization, fuzzy matching, and choosing the first repeated occurrence are forbidden.

Only the paragraph containing that verified occurrence is available to R1. Use preserved block/paragraph
structure or explicit blank-line boundaries. For the actual p2/p11 source this is the single preserved
body-prose block 34974. Never merge neighboring chunks, treat an arbitrary body_prose document as one
paragraph, or invent missing boundaries. Unknown paragraph provenance fails R1 closed.

For pooled byte-identical quotes from different physical anchors, validate each distinct anchor and require
one compatible owner result for all of them before annotating the pooled candidate through R1.
Missing or conflicting source proof leaves R1 unresolved; do not narrow or reorder supporting IDs.
p2 and p11 share one physical source, so one proof serves both child views with their original ID order.

### Bounded generic R1 resolver

The mapper remains the only production classifier consumer. On the corrected path it obtains **legacy**
owner records for the supplied bounded paragraph, then hands those records and the paragraph to
ownership_context's deterministic R1 resolver. Full-paragraph classification by itself is not a repair:
the existing classifier still leaves the target unresolved.

The first implementation is deliberately a closed structural grammar:

1. Target assertion is otherwise unresolved. Its containing sentence begins with
   “Across these levels”, optionally followed by an `of ...` noun phrase, then a comma. The anaphor
   may precede the assertion region; preserve its separate span.
2. Exactly one preceding, explicitly owned study-act assertion in that paragraph introduces the
   corresponding list. Owner comes from legacy parsed owner language, never the asserted subject matter.
   Require method_or_description kind for this introduction. Supported list forms are
   “at levels A and B” and “in A, B, and C”, with at least two items.
3. Split the list at top-level commas/conjunction, respecting parentheses; compare opaque item token
   sequences to subsequent “At [the] level [of] ITEM,” headers. For this comparison only, casefold and
   remove a leading article; do not use synonyms, stemming, scientific categories, or paper-specific words.
4. Require one matching header per listed item in order, before the target, with no duplicate/missing
   items or second possible owner/list introduction. Neutral A/B examples and the real three-item
   source satisfy the same grammar. Unknown internal body assertions do not acquire ownership or become
   extra supports; only the anchored target receives the final proof.
5. Refuse on a paragraph/section/discourse reset, competing explicit owner, citation conflict in the
   introduction-to-target chain, conflicting target owner, or unresolved antecedent linkage. A current
   replication mentioning earlier findings is not itself a new external owner. The real intermediate
   “we replicated…” record is unresolved under the old effective-source rule; it must not be falsely
   required to be a parsed current result, nor treated as an external owner.
6. Resolve to the unique introduction owner's relation, including attributed_external for a prior-owned
   antecedent. Preserve kind, aggregation, veto, caption, assertion boundaries, and evidence text.

“Across these levels” and “At the level” are generic discourse scaffolding. List item values are captured
opaque text, never executable topic vocabulary. Other anaphors or list grammars remain unresolved in this
bounded increment; widening them would require new preregistration and versioned behavior.

### Real R1 coordinate proof to preserve

| Item | Verified coordinate/value |
|---|---|
| Physical source | paper 67, attachment 67, chunk 34974 |
| Extracted chunk length | 1420 characters |
| Exact quote occurrence in chunk | [978,1243), unique |
| Target assertion in quote | [37,264) |
| Target assertion in chunk | [1015,1242) |
| Owner-bearing “We examined…” assertion in chunk | [298,430) |
| Chunk text SHA-256 | 8c1518e74a71dae10538a595a81f74b12ed3cb6a903c67f6b2f74a8a10e5ebdf |
| Source attachment checksum | e69488571a95103bc028347349faafb2fa03a4722c303c3f4973d7bdaeed6283 |

These values are fixture evidence only. Executable logic must contain none of these IDs, hashes, topic
terms, or preassigned relations. Quote/paragraph/header/anaphor proof spans are derived from the supplied
bytes. Missing snapshot/proof leaves the original target unresolved; it does not delete the grounded
candidate or fall back to a mutable library lookup.

## 5. A4 — R2 adjacent cited continuation

The current internal representation contains sentence spans, ordered assertion records, raw token spans,
explicit owner/source, kind, framing, and recognized citation tokens. That plus the supplied quote text
is sufficient for this repair; no outside reference lookup is required. However, the **public assertion
record alone is not sufficient**: it lacks a paragraph ID, normalized citation set, and explicit adjacency/
separator metadata. Add a corrected-path local view over raw input and old parse records; do not change
legacy records or sentence boundaries.

Require all of the following:

- Target's legacy source is unresolved and kind is result.
- Its predecessor is the final assertion in the immediately preceding sentence, is a result, and has
  explicitly parsed prior_work ownership. Neither contextual R1/R2 inheritance nor merely inferred
  Results ownership seeds a chain. Do not recursively propagate R2.
- The two sentences are contiguous within the same supplied paragraph, with no intervening sentence,
  unparsed textual sentence, heading, paragraph boundary, or owner/discourse reset.
- Both own assertion regions contain the same **nonempty** recognized citation-marker set.
- Target has no conflicting prior framing/object/comparison construction, explicit target owner, or reset.

Normalize only existing cite-token forms: comma-separated numeric markers and ascending hyphen/en-dash
ranges into sorted, deduplicated positive integer sets. Preserve raw markers and their exact spans.
Reject malformed/descending ranges and unsupported notation for this rule. Statistics, bare unrelated
numbers, and parenthetical years are not newly converted to citation markers. No citation parser expansion
is authorized. Different, partial-overlap, missing, or ambiguous sets do not qualify.

For resets, reject a target sentence introduced by the existing contrast family (but/although/whereas/
while/however/yet/though), or “by contrast”, “in contrast”, “in this study”, “in the present study”,
“here”, or a new run-in heading. A parsed current/external target owner is preserved independently;
it is never replaced by R2. An intervening owner-bearing sentence prevents adjacency even if the same
citation number appears again later. Repeated numbers in nonadjacent sentences cannot establish ownership.

Paragraph boundaries must be retained in the supplied input/local block contract. Never infer continuity
across known removed source boundaries or concatenated snippets. When continuity is unavailable, R2
does not fire. For p40 the existing quote contains the contiguous same-block sentences and their markers;
R1 remains the only real audited context requiring additional text.

Result: attributed_external, with predecessor span, explicit-owner span, both citation spans and normalized
set, paragraph/sentence spans, and rule ID. Citation → external is explicitly forbidden.

Real p40: target [147,273), predecessor [0,146), cite spans [145,146) and [272,273), set {6}.
The locally inspected reference list supports the audit judgment but is not a production classifier
dependency. Scientific correctness of the cited finding is outside this rule.

## 6. A5 — R3 bounded Results coordination

Use the existing leading-label detector and the existing first sentence/record regions. The corrected
local view retains the comma-plus-connector token span discarded by current clause assembly.
Do not teach the historical parser broader label scope.

Eligibility:

1. A valid explicit leading Results run-in label at the start of the classifier input.
2. The target is the otherwise-unowned result assertion in the second clause of that first sentence,
   immediately linked to the first clause by comma + `while` or `whereas`.
3. The first clause's eligible assertion has current-document ownership under legacy parsing/resolution.
   An explicitly prior-owned first clause does not qualify. No recursive chaining to later clauses.
4. The target passes the existing narrow Results safeguards when assessed with this bounded label scope:
   result kind; no caption, prior framing/object, replication act, negation, modal/hedge, citation token,
   ref/refs/cf or et-al marker, or citation-like parenthetical.
5. No additional intervening label, semicolon, sentence boundary, or owner/reset conflict.

“Parallel” here means the two adjacent clause-level result records under this one label and allowed
connector, each retaining its own subject/predicate. It does not mean topic similarity or shared
scientific interpretation. No claim is made that the first statistical predicate grammatically governs
the second; the relation is structural label scope.

An explicit second-clause owner always retains its parsed value, including external ownership.
A current-document interpretation remains interpretation; this rule does not convert it to a result.
A hedge or negation on an otherwise-unowned target blocks this **ownership resolver** under the accepted
narrow safeguards, not under a new global support-policy gate.

Record the leading label span, first/target assertion spans, connector text/span, sentence/paragraph
scope, and rule ID. Preserve two separate assertion records. For p41 retain [43,200) and [208,372);
the correction applies to only the second assertion's three uses.

## 7. A7 — Ownership context and candidate provenance contract

Ownership evidence and scientific support text are distinct objects. Do not overload support_label,
change exact_text, or attach the whole paragraph as scientific evidence.

### Transport entry (data, never semantic authority by itself)

A versioned `ownership-context-v1` entry contains:

| Field group | Required meaning |
|---|---|
| Physical identity | paper_id, attachment_id, chunk_id, source_attachment_checksum |
| Text identity | chunk_text_sha256; extraction_tool/version and chunk_version when available |
| Bounded material | exact paragraph text, paragraph span in chunk, preserved block/boundary provenance |
| Quote attachment | proposition IDs/physical anchor, quote_sha256, exact quote span in chunk, occurrence proof |
| Replay identity | content-derived entry ID/hash, originating saved-packet/sidecar reference |

The sidecar owns the text once. A chunk/source checksum plus offsets can **reference** proof material,
but cannot replace its availability: a bare locator is not replayable without immutable bytes supplied
at the boundary. The classifier never dereferences a path or queries a database.

### Target-scoped verified R1 context

The resolver returns `verified-local-owner-v1`, or a structured failure:

- context entry ID and source identities/hashes;
- target quote hash and exact target assertion span;
- explicit owner-bearing assertion span and parsed owner;
- enumeration introduction/list-item spans and matching header spans;
- anaphor span, paragraph scope, and quote-to-chunk offset mapping;
- result relation; resolver ID/version `local-antecedent-v1`;
- proof rule ID `owner.local_antecedent.v1`.

Only the internal mapper may supply this verified object to corrected classification, after the pure
resolver validates the supplied bytes and legacy parse observations. The classifier validates schema,
hash/target binding, span bounds, relation vocabulary, and explicit-owner consistency. It consumes the
bounded proof; it does not search the library or arbitrarily enlarge the paragraph.

This is an internal provenance contract, not a signature or a security guarantee that any caller-provided
JSON is truthful. Do not accept user/model-generated “verified” objects or a bare owner_signal as this
proof. The authorized mapper must construct it through the tested resolver, not mark arbitrary inputs
verified. Invalid/mismatched proof contributes no ownership proposal and records a failure; it must not
override independently parsed ownership or a valid local R2/R3 result.

### New candidate metadata, corrected path only

Proposed optional `attribution` object, emitted for every corrected-path candidate and absent from v5:

```text
schema_version: ownership-attribution-v1
classifier_id: i4-1-assertion-authority
ruleset_version: i4-2b3.0
assertion_relation: current_document | attributed_external | unresolved
source_resolution: parsed | structural_results_label | corrected_context | unresolved
rule_ids: ordered rule identifiers
target:
    quote_sha256
    span_proposition_id
    assertion_span
    supporting_proposition_ids  # original discovery order
proofs: bounded rule-specific proof records
context_status: not_needed | applied | unavailable | invalid | ambiguous | conflicting
context_failure: null or specific reason
```

R2 proof ID: `owner.adjacent_cited_continuation.v1`; fields include physical quote locator, predecessor/
owner/target/paragraph/sentence spans, both raw citation spans and the normalized citation set.
R3 proof ID: `owner.results_coordination.v1`; fields include physical quote locator, label, connector,
first/target assertion and sentence spans. R1 uses the sidecar-backed proof above. Existing parsed
owners need no new contextual proof; retain their existing rule trace with an empty new-proof list.

Candidate construction validates optional metadata but does not infer ownership. Legacy calls omit
the key entirely; default builders must not emit `attribution=None` into historical records.
Record the selected ruleset for unchanged as well as corrected candidates so mixed-version outputs are
detectable. Maintain source/proof identity when passing candidates through existing maps. ParentClaims
and AnswerPlan do not become proof consumers in this increment.

### Failure behavior

Missing snapshot, absent anchor, nonunique quote occurrence, ambiguous antecedent, paragraph uncertainty,
conflicting pooled source ownership, malformed spans, mismatched hashes, or incompatible proof version
leave R1 unresolved with a specific context failure. They do not mark policy inadmissibility, delete a
candidate, change guard flags, or produce an attachment-ambiguous role. Bad API ruleset selection raises
ValueError; unavailable evidence is a recorded fail-closed ownership result.

## 8. A9/A12/A14 — Version boundary and next increment

| Version option | Assessment |
|---|---|
| A: change ruleset while keeping corrected production maps stamped v5 | Reject: contradicts exact historical candidate/replay identity |
| B: attribution repair begins sufficiency v6 | **Recommend**: separately replayable corrected attribution with policy unevaluated |
| C: new classifier ruleset standalone now, defer mapper integration to policy v6 | Technically safe only while entirely unwired; then bundles two meaningful map changes or needs another identity anyway; unnecessary extra increment |

Ownership relation is already a serialized candidate-level semantic distinction even though admissibility
is None. The engine's invariant requires a bump for mapping derivation changes. Choose **attribution-only
sufficiency-semantics-v6**, with the explicit classifier ruleset **i4-2b3.0**. Later support-policy gating
and accepted retain-and-flag behavior require a subsequent bump, expected **v7**, with exact explicit
v6 replay preserved as well. This supersedes the earlier provisional “policy probably v6” numbering
recommendation; it does not change the conservative policy or any accepted guard decision.

Proposed next increment:

**PHASE 34 / I4-2b3 — VERSIONED ATTRIBUTION REPAIR + BOUNDED CONTEXT TRANSPORT
(ATTRIBUTION-ONLY SUFFICIENCY V6).**

Recommend **one bounded implementation** for version dispatch, R1 transport/proof, R2/R3, candidate
provenance, and offline gates. Internal work can be staged and tested, but do not publish a partially
corrected sufficiency-v6 behavior that later changes under the same identity. R1's transport is necessary
to test the full six-use result; splitting a ruleset-only release from transport adds another incomplete
state without a compatibility benefit.

In that future implementation, guards stay prefilters exactly as v5. The original **ten** candidates
remain ten, all with admissible=None and inadmissibility_reason=None. There are no five newly retained
guard-excluded candidates: those belong to the later policy/guard increment. The conservative predicate
is applied only in an audit assertion demonstrating 10/10, not in production state derivation.

Future version plumbing must explicitly preserve existing category, direction, witness, inheritance,
recovery, and stop-search rules. Current explicit v4/v5 checks exist in sufficiency_engine,
sufficiency_mapping, sufficiency_recovery_targets, and e2e; direction_target and relation_witness use
version tables. Add deliberate v6 → existing-behavior entries and tests. Do not fall through to old
pre-category behavior, use numeric >= dispatch, or float to current semantics.

No authored contract change, PLAN_VERSION change, relationship registration, ParentClaims/AnswerPlan
semantic change, model-prompt change, live retrieval, or I2-3 is in that proposed increment.
Version-reader/stamping tests and historical authorization paths must recognize v5 as historical after
a future current-v6 bump. This audit changes none of those surfaces.

## 9. A10 — Static-guard and authorized-module plan

| Module / layer | Future authorization | Explicit prohibition |
|---|---|---|
| ownership_context.py (new pure helper) | Snapshot validation; bounded R1 resolution from supplied text and supplied legacy owner records | No classifier import/call; no I/O; no domain/ID literals; no support-policy logic |
| sufficiency_mapping.py | Sole production classifier consumer; select ruleset, obtain owner records, call R1 resolver, attach candidate proof | No library/packet-file lookup, extra retrieval, policy gating, or relevance broadening |
| assertion_authority.py | Version dispatch, frozen legacy parsing, R2/R3, consume bounded verified R1 proof | No arbitrary context search, question parsing, sufficiency imports, I/O, or global-current selector |
| sufficiency_diagnostic.py | Validate/thread per-proposition context index to units | No classifier call, new relevance decision, or model-payload expansion |
| e2e.py | Build supplied snapshot from resident packets, thread U1/U2/dry paths, persist sidecar through trace | No semantic ownership inference or additional source retrieval |
| sufficiency_engine.py | Optional provenance shape validation and future version identity | No classifier/context resolver import |
| offline replay/tests | Load explicit saved context, assert full compatibility and proposed behavior | No live model calls or fixture relation overrides masquerading as classifier output |
| ParentClaims / AnswerPlan / target_relevance / achieved_outcome_span | Existing behavior only | No new proof/classifier consumption |

Keep the exact mapper allow-list in I4-1 and I4-1f guards; no second classifier consumer is necessary.
I4-1j primitive guards must stay exact: avoid mentioning/calling classifier primitives in the transport
helper or broadening exemptions to a directory. Add analogous helper-consumer guards with only mapper,
diagnostic, and E2E as authorized context consumers.

Keep RULESET_VERSION's legacy alias so old exact/prefix tests remain true. Parameterize new tests over
explicit old/new selections; preserve frozen battery files and old expectations. Add corrected-rule
expectations separately rather than editing pp_p41_a2 or relaxing a failing historical test. Tests that
pin the current sufficiency constant to v5 will need the narrowly justified current-v6 identity update;
retain separate explicit-v5 behavior and hash assertions. PLAN_VERSION pins remain unchanged.

Extend static checks to require explicit mapper ruleset selection; forbid se.SUFFICIENCY_SEMANTICS_VERSION
or an environment-driven default inside classifier/context helpers; verify no candidate policy fields
are read/written by ownership logic; forbid imports from database/network/model modules and all I/O.
Freeze the AST digest of legacy tokenization/sentence/label/owner/assertion-building helpers, _all_assertions,
_effective, and their grammar constants before implementation; a wrapper may not hide a shared-helper
modification. New dispatch and corrected resolver functions are outside that frozen set. Preserve the
old assertion-field serializer and add new proof fields only in the corrected-result wrapper.

Scan executable constants for q_aib, target paper/proposition IDs, fixture hashes, scientific topic nouns,
and population-based owner cues. Allow generic grammatical owner/discourse vocabulary and dynamically
captured opaque list items. Use negative tests with an unauthorized consumer and injected topic/ID
constant to demonstrate the guards detect violations. Keep library excerpts in fixtures/docs only.

## 10. A11 — Preregistered test matrix

All expectations below are design commitments. No corrected classifier was implemented to obtain them.
The accepted I4-2b1 battery is the initial preregistration source, reproduced below without changing its
texts or manual ownership judgments. Legacy observations remain the v5 expectations.

R1 positive tests must build the proof through the actual proposed resolver/transport, not hand-author
the desired owner into JSON. R2/R3 tests use quote-only inputs. All tests assert unchanged assertion
spans/text/kind/aggregation/veto as well as ownership; parsed owners and interpretation kinds are preserved.

### Initial 32 cases from I4-2b1

For R1 cases the whole supplied paragraph is context and the indicated assertion is the grounded target.
The proposed proof-construction path supplies the valid context where available. Literal backslash-n
sequences in this transcript represent paragraph breaks in the original test input.

1. **context_same_owner**

   Text: We examined responses at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `current_document`.

2. **context_prior_owner**

   Text: Previous studies examined responses at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `attributed_external`.

3. **context_no_owner**

   Text: Responses were examined at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

4. **context_omitted**

   Text: Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

5. **context_switch**

   Text: We examined responses at levels A and B. Previous studies examined responses at levels C and D. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

6. **context_paragraph_boundary**

   Text: We examined responses at levels A and B.\n\nAcross these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

7. **context_target_citation**

   Text: We examined responses at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.6

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

8. **context_explicit_target**

   Text: We examined responses at levels A and B. Across these levels, previous studies found that scores correlated with ratings.

   Target: scores correlated

   Observed: `attributed_external` / `result`. Proposed ownership: `attributed_external`.

9. **citation_shared**

   Text: Recent work found that scores increased.6 Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `attributed_external`.

10. **citation_different**

   Text: Recent work found that scores increased.6 Participants demonstrated higher ratings.7

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

11. **citation_alone**

   Text: Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

12. **citation_explicit_current**

   Text: Recent work found that scores increased.6 We found higher ratings.6

   Target: higher ratings

   Observed: `current_document` / `result`. Proposed ownership: `current_document`.

13. **citation_no_prior_marker**

   Text: Recent work found that scores increased. Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

14. **citation_paragraph_boundary**

   Text: Recent work found that scores increased.6\n\nParticipants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

15. **citation_preceding_current**

   Text: We found that scores increased.6 Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

16. **citation_missing_target**

   Text: Recent work found that scores increased.6 Participants demonstrated higher ratings.

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

17. **label_parallel**

   Text: Results: Scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `current_document`.

18. **label_prior_override**

   Text: Results: Scores increased, while previous studies found that ratings decreased.

   Target: ratings decreased

   Observed: `attributed_external` / `result`. Proposed ownership: `attributed_external`.

19. **label_citation**

   Text: Results: Scores increased, while ratings decreased.6

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

20. **label_prior_first**

   Text: Results: Previous studies found that scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

21. **label_wrong_label**

   Text: Discussion: Scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

22. **label_semicolon**

   Text: Results: Scores increased; ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

23. **label_new_sentence**

   Text: Results: Scores increased. Ratings decreased.

   Target: Ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

24. **label_absent**

   Text: Scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

25. **label_explicit_current**

   Text: Results: Scores increased, while we found that ratings decreased.6

   Target: ratings decreased

   Observed: `current_document` / `result`. Proposed ownership: `current_document`.

26. **label_interpretation**

   Text: Results: Scores increased, while we suggest that ratings decreased.

   Target: ratings decreased

   Observed: `current_document` / `interpretation`. Proposed ownership: `current_document`.

27. **label_hedged**

   Text: Results: Scores increased, while ratings probably decreased.

   Target: ratings probably decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

28. **label_modal**

   Text: Results: Scores increased, while ratings could decrease.

   Target: ratings could decrease

   Observed: `unresolved` / `interpretation`. Proposed ownership: `unresolved`.

29. **label_negated**

   Text: Results: Scores increased, while ratings did not increase.

   Target: ratings did not increase

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

30. **label_unowned_interpretation**

   Text: Results: Scores increased, while this suggests that ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `interpretation`. Proposed ownership: `unresolved`.

31. **citation_discourse_reset**

   Text: Recent work found that scores increased.6 By contrast, ratings decreased.6

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

32. **citation_current_override**

   Text: Recent work found that scores increased.6 We found ratings decreased.6

   Target: ratings decreased

   Observed: `current_document` / `result`. Proposed ownership: `current_document`.

### Additional preregistered cases

C = current_document; E = attributed_external; U = unresolved. Expected relation is the corrected
target result, not an admissibility decision. All cases retain the legacy expectation separately.

| ID | Fixture / variation | Corrected expectation and required proof/gate |
|---|---|---|
| E01 | Real p2 and p11 from preserved sealed rows + chunk 34974 | C for two uses; same physical proof, original plural order/quote spans |
| E02 | Real p40 full sealed quote | E for second assertion; exact shared {6}, no reference lookup |
| E03 | Real p41 full sealed quote, both assertions and all five uses | C for both; only three formerly U uses change; two assertion identities retained |
| E04 | “Recent work found X.6 Scores increased.7 Ratings decreased.6” target Ratings | U; nonadjacent repetition is not continuation |
| E05 | “Recent work found X.6 We examined Y. Scores increased.6” target Scores | U; intervening sentence/owner reset |
| E06 | “Recent work found X.6” + paragraph break + “Scores increased.6” | U; no paragraph crossing |
| E07 | R1 positive paragraph, omit context index/proof | U; candidate retained, context unavailable |
| E08 | R1 positive, quote/chunk hash mismatch, out-of-bounds span, wrong target hash, wrong source identity (separate rows) | U; invalid proof; no fallback lookup |
| E09 | R1 positive, exact target quote appears twice without an occurrence locator | U; ambiguous attachment to context, not a new role state |
| E10 | R1 positive with prior-owned introduction | E; prove prior owner, never default C |
| E11 | R1 positive with two owner/list introductions or duplicate/missing level header (separate rows) | U; nonunique or incomplete antecedent proof |
| E12 | Proposed prior context + explicit “We found…” target | C retained; contextual proof cannot override |
| E13 | Proposed current context + explicit “Previous studies found…” target | E retained |
| E14 | “Results: Scores increased. Ratings decreased.” | U for later sentence |
| E15 | “Results: Scores increased; ratings decreased.” | U for semicolon |
| E16 | “Results: Scores increased, whereas ratings decreased.” | C; same bounded coordination as while |
| E17 | “Results: Scores increased, whereas previous studies found that ratings decreased.” | E retained |
| E18 | “Results: Scores increased, while previous studies found that ratings decreased.” | E retained |
| E19 | “Results: Scores increased, whereas ratings decreased.6” | U; target citation veto |
| E20 | Results second clause with probably / could / did not (separate rows, both connectors) | U under narrow resolver; hedge/modal/negation metadata preserved |
| E21 | “Results: Scores increased, whereas we suggest that ratings decreased.” | C/interpretation retained; no kind promotion |
| E22 | “Background: X changed. Results: Scores increased, while ratings decreased.” | U target; no mid-input Results section inference |
| E23 | “Results: Previous studies found X, whereas ratings decreased.” | U; prior first clause cannot seed current ownership |
| E24 | “Recent work found X.6 By contrast, scores increased.6” | U; explicit discourse reset |
| E25 | “Recent work found X.6,7 Scores increased.7,6” | E; audited legacy tokens recognize both markers, normalized set {6,7} |
| E26 | “Recent work found X.6–8 Scores increased.6,7,8” | E; audited legacy tokens recognize both markers, normalized set {6,7,8} |
| E27 | Same citation set represented by statistics, bare numbers, unsupported brackets, descending range (separate rows) | U for R2; do not expand recognition to make a positive |
| E28 | Same markers on nonadjacent unrelated sentences with an unparsed intervening sentence | U; do not skip unparsed text to invent adjacency |
| E29 | Positive R1 with paragraph text unavailable but locator/checksum supplied | U; hashes cannot substitute for source bytes |
| E30 | Pooled identical quotes from two physical anchors with conflicting/missing R1 proofs | U; no first-anchor ownership shortcut or ID narrowing |
| E31 | R1 proof schema/resolver version unknown or relation invalid | U + invalid context failure; unsupported classifier ruleset itself raises ValueError |
| E32 | Valid R2/R3 local ownership with malformed unrelated R1 proof | Local result preserved; R1 failure recorded, no blanket invalidation |
| E33 | Same R1 source snapshot with recovery-only entries appended | Identical old proof entry IDs and ownership outputs |
| E34 | Seeded packets contain candidate_spans but no source chunks | R1 unavailable; R2/R3 still evaluated from supplied quotes |
| E35 | New context supplied to explicit v5 diagnostic call | Exact old replay; no context read/classification side effect |
| E36 | Omitted classifier ruleset vs explicit i4-1f.0 across all old batteries | Exact complete result equality, no new keys |
| E37 | Unsupported ruleset and incompatible legacy ownership_context argument | ValueError, never floating to current |
| E38 | Corrected call requests whole multi-assertion quote | Same attachment scope and separate records; singular API still fails closed |
| E39 | Change list-item words to arbitrary neutral strings while preserving scaffolding | Same R1 decision; no topic/identity dependence |
| E40 | Reorder input candidate list / swap target domain nouns while holding structural scope | Per-candidate ownership follows its proof, never a representative or domain ranking |

E25/E26 were checked against the unchanged tokenizer during this audit: it recognizes both own citation
markers in each exact string. Freeze those token spans in their future fixtures. A bracketed [6] alone
is not recognized as a cite token; the legacy tokenizer does recognize a descending 8–6 token, which the
new set validator must reject. No tokenizer change is needed or authorized for these matrix rows.

The additional rows with variants are a matrix specification; expand each stated variant into a named,
hash-pinned fixture before implementation. Do not claim “72 passing tests”: 32 initial cases plus 40
matrix rows include multiple subcases and currently specify unimplemented behavior.

## 11. A13 — Readiness and counterfactual replay acceptance plan

**READY for the bounded I4-2b3 attribution-only implementation specified here**, subject to user
authorization and the following preregistered acceptance gates. This is design readiness, not a claim
that new rules have passed tests. Support-policy integration remains out of scope.

### Historical compatibility gate

1. Freeze existing accepted fixture files and legacy parser behavior; do not rewrite the frozen old
   batteries to make new behavior appear historical.
2. Explicit v5 selects legacy rules even when current production eventually becomes v6.
3. Run the preserved offline harness with original frozen model nominations and no ownership sidecar
   consumption in v5.
4. Require exact combined v5 hash
   `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77`,
   including candidates, diagnostics, map, recovery, claims, AnswerPlan, rendering, and invariants.
   Explicit v4 must retain `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a`.
5. Run old classifier batteries both by omitted version and explicit legacy version. Exact output shape,
   source_resolution, rules, locator metadata, kind, aggregation, and veto remain pinned.
6. Show the legacy branch cannot call corrected resolver helpers (a fail-on-call spy), and prove context
   presence/absence does not alter old replay. No version stripping is allowed for the historical hash.

### Corrected attribution-only gate

1. Build immutable context from the preserved packets with the actual generic code, not manually injected
   p2/p11 owners or a six-entry output rewrite. Enforce no filesystem/database/network access inside
   mapper/classifier/resolver.
2. Preserve exactly ten original candidates; guard ordering is still v5. Check each full original
   grounding signature: IDs/order, anchor, exact text, assertion/predicate/content spans, relevance,
   attachment, kind, aggregation, veto, caption, and representative.
3. Exactly six relation uses change: p2/p11 twice → C; p40 once → E; p41 assertion 2 three times → C.
   Other relations unchanged. New provenance is expected; derived support_label changes consistently
   for the six corrected uses and remains display-only.
4. All ten retain admissible=None and inadmissibility_reason=None. Apply the unchanged conservative
   predicate **only in the test/audit projection** and require 10/10. Do not call new_support_policy()
   to manufacture that default.
5. Role/requirement/instance/recovery/witness/relation/direction/effectiveness behavior must match v5;
   no guard-retained extra five candidates and no newly changed c8 missing reasons in this increment.
6. Compare downstream semantic payloads and rendering, allowing only explicitly enumerated version
   identity stamps and new attribution metadata. Unlike the earlier v5-dispatch counterfactual, real
   v6 identity necessarily differs; do not describe the whole v6 artifact as byte-identical to v5.
   Historical v5 itself still must be exact. PLAN_VERSION and answer semantics stay unchanged.
7. Run all 32 initial cases, expanded additional matrix, real source cases, static/purity/domain guards,
   candidate schema compatibility, and the 33 downstream invariant checks. Freeze the resulting corrected
   replay hash as a separately replayable **policy-unevaluated** baseline for later support-policy work.
8. Require old context/source proof identities to remain stable through append-only recovery, and verify
   model-facing nomination rows/fingerprints are unchanged by context transport.

Any unexpected seventh relation change, altered grounding, new candidate, changed gate/state, lookup,
or old replay drift is a stop condition. Diagnose it; do not expand the increment to support policy,
guard implementation, question-specific exceptions, or AnswerPlan fixes.

## 12. Required decision register

| Decision | Result |
|---|---|
| A1 | One global i4-1f.0 implementation; public identity but no runtime ruleset selection; candidate provenance insufficient |
| A2 | Architecture A: explicit versioned classifier dispatch with permanently frozen legacy default |
| A3 | R1 consumes a bounded verified local-list/anaphor proof; generic resolver and exact guards in §4 |
| A4 | R2 is a pure corrected ruleset layer over supplied quote/old parse plus raw delimiter/citation metadata |
| A5 | R3 scopes only first-sentence while/whereas coordination under leading Results and existing safeguards |
| A6 | Caller-supplied immutable context index through diagnostic units; source packets at E2E/replay boundary; no hidden lookup |
| A7 | Target-scoped ownership proof and per-candidate attribution metadata, separate from support text/label |
| A8 | v5 explicitly selects i4-1f.0; no new fields or context effects in historical output |
| A9 | Attribution-only sufficiency v6 + i4-2b3.0; later policy/guard change requires subsequent version, expected v7 |
| A10 | Preserve sole classifier consumer; authorize pure context transport/resolution separately; strengthen explicit-version/purity/domain guards |
| A11 | Initial 32 cases preserved + additional matrix in §10, real examples and exact historical replay |
| A12 | One bounded attribution implementation including necessary transport, internally staged; no partial published v6 |
| A13 | READY for that attribution-only implementation; not implemented, and not ready to bundle support policy |
| A14 | I4-2b3 — Versioned attribution repair + bounded context transport (attribution-only sufficiency v6) |

## 13. Verification and stop

This audit inspected the actual public signatures, parser records, mapper call site and candidate
construction, diagnostic/sealing/E2E transport, semantic version tables, identity code, frozen tests,
and static guards. It verified real quote occurrence coordinates and reran exact unchanged v5 replay.
The 32-case source is the accepted I4-2b1 report; new-rule expectations remain preregistration, not
observed implementation results. No external search, retrieval, model calls, or live E2E occurred.

Only this Markdown file and a new lineage entry are written in this increment. The prior I4-2b0/I4-2b1
files remain byte-identical; existing lineage content is retained. No attribution implementation,
support-policy implementation, guard change, version bump, same_local_assertion registration,
ParentClaims/AnswerPlan change, or I2-3.

**STOP after I4-2b2.**
