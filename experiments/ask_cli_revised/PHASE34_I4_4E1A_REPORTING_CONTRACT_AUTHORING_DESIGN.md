# Phase 34 / I4-4E1A — fresh reporting-contract authoring design

**READY for one bounded I4-4E1B implementation of the reviewed-authored fresh path.**
Add a small, explicitly authored reporting object to the existing pre-retrieval request /
scientific-contract review boundary, then carry it into the E1 handoff. No additional model
pass is necessary. Execution children do not automatically become visible reporting nodes.

This readiness is for a request supplied with reviewed scientific and reporting authoring,
as in the requested shipping sequence. It is not a claim that arbitrary raw question text
already becomes a reviewed scientific contract automatically. That capability is explicitly
absent in `sufficiency_authoring.py:1–18`; this design neither supplies it nor hides its
absence behind a test fixture. No promotion or product-readiness claim follows from this audit.

## Checkpoint, authorization and method

The accepted E1 STOP report and its lineage append were the only outstanding changes on
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z` at
`35b800473bc5c756d6950eb680c2ff27dd2ef7fa`. Per the E1A brief, they were committed and pushed
as the documentation-only checkpoint:

`13680c71954c7f75964e096ceb48339eb1faf618` — `docs: record I4-4E1 reporting contract prerequisite stop`.

Normal applicable hooks passed; code-only hooks skipped. No `--no-verify` was used. The
server accepted the push and reported its protected-ref/status-check bypass notices;
remote CI completion is not asserted. Clean status was confirmed before beginning E1A.
The E1 report's final-HEAD statement describes the earlier stopped increment; it has not
been retroactively rewritten to describe this later checkpoint.

E1A is source inspection and design only. Ten targeted AST/source assertions passed without
importing or executing any production module. The A–J cases below are conceptual design
exercises, not an implemented test suite. No full suite, model, retrieval, NLI or live E2E
was run. No production, test, baseline, version, overlay or registry file changed.

## R1–R2: exact consumer needs and current authoring sources

| Consumer / field | Actual use | Fresh design disposition |
|---|---|---|
| `plan_v5.build_plan`, `overlay.nodes` sequence | Visits visible nodes in authored order. | Keep ordered nodes; no separate sort key. |
| Node `owning_child_ids` | Selects ALL facets whose scientific child is owned by this node. | Required explicit authored ownership; never derived from evidence or execution parentage. |
| Node `literal_text` | Copied to plan and printed verbatim as the question-facing heading. | Required reviewed wording. |
| Node `label` | Copied to plan/render and printed before the heading. Also serves as the historical parent reference. | A stable `node_id` can supply this value. No second label field is necessary. |
| Node `parent` | Copied to plan; `render_v5` does not read it or aggregate descendant states. | Retain an explicit `parent_id` for structure. Do not introduce semantic roll-up. |
| `parent_synthesis_v2` | Reads typed claims, projection, receipts, finalized displays and relation units. | No reporting-tree fields required; reporting cannot authorize new claim content. |
| `layerc_presentation.finalize_display`, `requested_construct_terms` | Sends these terms to `classify.evaluate_sentence` and `text.construct_direct`. | Preserve an explicit authored list, including an intentional empty list; never silently default a missing field to empty. |
| `layerc_presentation`, `facet_phrases` | Transported in `Ctx`; `evaluate_sentence` does not use the phrases. A separate legacy classifier function does. | Not required in the fresh reporting schema. Preserve on the unchanged qualification path. |
| Overlay `role_phrases`, `category_phrases`, `obligation_phrases`, `human_review_obligations`, `nesting` | Not read by these v2 consumers to compute/render reporting nodes. Some belong to legacy overlay validation/consumers. | Do not copy into fresh reporting v1. |
| Overlay confirmation names, Phase-28 run ID, replay status, postdating flag | Historical authorization/material provenance. | Replay-only; no fresh equivalents in the reporting body. |
| `layerc_projection._profile`, `layerc_consumer`, `profile_b` | Bind/hash the authored requirements and whole historical overlay, then the projection/plan/output. | Fresh provenance must bind the new reporting object explicitly. Leave the historical binding intact. |

Source anchors: `answer_plan/plan_v5.py:44–174`, `answer_plan/render_v5.py:6–71`,
`parent_synthesis_v2.py:9–93`, `layerc_presentation.py:9–87`,
`answer_plan/classify.py:63–97`, `answer_plan/text.py:143–151`,
`layerc_projection.py:74–110`, `layerc_consumer.py:21–81` and `profile_b.py`.

`requested_construct_terms` is a request-authored display restriction, not a scientific
category list. In current code, an empty list disables that particular check; a nonempty
list requires a term in the quote or the paper's sealed text. Dropping it would change
display behavior. Keep the current request-wide behavior in this bounded increment; do
not invent per-node scientific rules or derive terms from retrieved evidence.

| Existing pre-retrieval source | Already explicit | Deterministic transport available | Genuinely missing decision |
|---|---|---|---|
| `request_contract.build_request_contract` | Original text, question hash, literal unit text/offsets and order. | Copy original text; resolve exact existing unit/obligation identities. | Visible grouping, hidden helpers, scientific ownership and scoped construct terms. Segmentation alone is not semantic authoring. |
| `request_subquestions` flat path | `sN` retrieval identity, `sN-o1` obligation identity, original sentence/list context. | Enumerate identities before retrieval. | Which reviewed scientific contracts belong to them; whether multiple units share a visible node. |
| Hierarchy contract | Approved child wording, execution parents, scope carriers, qualifications, obligation ownership and folded records. | Copy already approved wording/context if explicitly selected; reference existing children/parents. | Which nodes are visible, visible parent relations and node-to-scientific-child ownership. |
| Reviewed sufficiency contract | Child IDs, requirement IDs, role/completion/quantifier declarations, source wording. | Enumerate requirements under their existing child. | Visible labels/wording/grouping; these must not be reconstructed from the mapped output. |
| Product query planner | `QueryPlan(scope, facets)`; each `Facet(label, query)` is a retrieval subquery. | Can transport existing label/query text, but only with its retrieval meaning. | No scientific-child IDs, reporting ownership, parent structure or reviewed scientific contract. |
| Calibration decomposition | Source-unit IDs/text and authored rephrasing items; model schema returns `rewrite` or `rewrites`. | Exact item/source links and sequence. | No reporting ownership, sufficiency authoring or production integration with this fresh caller. |

The product planner is `app/backend/summarization/query_planner.py`; its docstring and
`Facet`/`QueryPlan` definitions explicitly describe retrieval. It is used by `/summarize`,
not by experimental `e2e.execute`. `calibration/decomposition.py` is an experiment, not an
already active reporting author. Neither is silently upgraded into reporting authority.

## R3, R9–R10, R12–R14: authoring and review boundary

Choose the point **after execution obligations/scientific child IDs have been assigned and
the scientific requirements proposed, but before the joint authoring review is accepted
and before retrieval starts**. This is the earliest point where ownership can be named
truthfully. Add reporting to that same authoring output, as a sibling of the request and
scientific contract. Author/review the three together; keep their schemas and meanings
distinct. A tiny deterministic adapter validates and binds an explicit decision; it does
not decide the visible tree on the author's behalf.

The minimum new authored decisions are node wording/ownership, visible parent relationships,
and any scientific-only exclusions. Technical node IDs and serialization can be generated
deterministically before review. Copying wording is deterministic only after the author
selects the exact source wording and its intended scope. A child with anaphoric wording or
scope qualifications needs reviewed question-facing wording retaining that context; the
validator does not synthesize an unapproved paraphrase.

**R9: NO additional model call is required.** Existing researcher/request authoring can
provide this small object. Outcome A (already sufficient decomposition output) is false
for general current requests, and true only for the explicitly approved trivial case below.
The smallest extension is B-shaped: add a `reporting` sibling to the existing authored
request/scientific-input submission. This is a structured authoring-field addition, not a
claim that a production model planner already generates it. If an existing authoring
proposal later comes from a model, it can propose that same sibling in the same pass,
subject to the same review; no separate C pass is justified here. **R10: no new model
output/prompt is needed for the bounded implementation.** Do not alter the product planner.

Review remains the existing request/scientific-authoring lifecycle. The review must bind
the exact request, scientific frozen definitions and reporting body together. A hash proves
integrity, not review: code must not manufacture `reviewed_by`, approval or a trusted
invocation merely because supplied JSON hashes correctly. Existing genuine review records
or the actual trusted authoring/review caller provide authority. Tests explicitly mark
their test authoring provenance; it is not a production approval record. No D1 registry,
signature, new trust service or runtime self-enrollment is needed for authored inputs.

There is an existing useful generic seam: `sufficiency_freeze.load_verified` accepts explicit
`frozen_path` and `review_path` and checks their matching question key, reviewed hash and
per-child hashes. Its default files and the current `sufficiency_authoring.freeze` wrapper
are fixture-specific. The fresh route must require explicit invocation-owned inputs and
bind their request identity; it must not call the default q_aib loader or reuse that
wrapper's fixed question key/supersessions as general authoring.

## R4: minimal reporting-contract-v1

Proposed exact body (illustrative values; not an artifact produced by this audit):

```json
{
  "schema": "reporting-contract-v1",
  "request_ref": "request-contract:sha256:<canonical-request-body-digest>",
  "nodes": [
    {
      "node_id": "1",
      "literal_text": "What was found about alpha?",
      "parent_id": null,
      "owning_child_ids": ["s1-o1"]
    }
  ],
  "scientific_only_child_ids": [],
  "requested_construct_terms": ["alpha"]
}
```

All shown keys are required and the schema is closed. No evidence IDs, results, scientific
role definitions, category inventories, state, citations, recovery state or answer prose.
`scientific_only_child_ids` is necessary to distinguish an intentional hidden helper from
an accidentally omitted answer obligation. `requested_construct_terms` is necessary to
preserve the existing display restriction; it is not implied by the node heading.

Use node sequence as the authored display order. No `order`, `visible`, separate `label`,
root record, layout type or rendering template is required. Every listed node is visible;
node IDs serve the current label function. Technical IDs can be minted in authored sequence
before review, but changing them later changes reporting identity. `parent_id: null`
denotes a root; a forest is sufficient. Original request context stays in the bound request.

`request_ref` binds the full canonical request body, not merely the question string. Keep
reporting outside that body to avoid a reference cycle. Use the repository's canonical JSON
and SHA-256 convention; bind schema and complete body. A reporting content reference can
be `reporting-contract-v1:sha256:<digest>`, computed outside the body. The joint review and
fresh invocation also bind the scientific-contract digest, so matching raw question text
cannot substitute a different decomposition or requirement set.

## R5–R8, R11: precise structural rules

1. Establish the invocation's scientific child inventory from reviewed scientific contracts
   and the request's real obligation identities, before evidence exists. Unknown children
   fail. Scientific contract keys and embedded child IDs must agree.
2. The owned-child sets and `scientific_only_child_ids` form an exact partition of that
   scientific inventory. Every child is explicitly accounted for. Duplicate ownership,
   even identical ownership repeated at another node, fails in v1. Duplicate entries within
   a list fail. Shared scientific evidence remains legal; sharing evidence is not duplicate
   ownership of an answer obligation. An arbitrary reporting DAG is deferred.
3. Each node owns at least one scientific child with authored requirements. A node may own
   several children; all their requirements remain separate facets with current plan-v5
   aggregation. Do not split or duplicate a child's requirements among nodes in v1.
4. Node IDs and nonblank literal strings are required; IDs are unique. No missing-literal
   fallback in validation. Authoring may copy an explicitly selected approved literal before
   review, but validation cannot invent it.
5. Parent IDs resolve within the reporting nodes, are not self-links, and form an acyclic
   forest. Require parent-before-descendant, contiguous depth-first authored sequence;
   reject conflicting order rather than silently rearrange it. No second ordering field.
6. A reporting parent means question organization, not scientific dependency. It neither
   inherits child facts nor unions descendant states. Current plan-v5 computes each node's
   state from its directly owned facets; keep that unchanged. Scientific inheritance still
   uses the reviewed scientific/execution parent map and existing proof machinery.
7. A parent that asks an independent overarching question owns its own scientific child;
   its visible children own other children. A purely decorative heading without an answer
   obligation is not a status-bearing node in v1. Use the original request context and
   root nodes for that case; do not falsely mark an empty heading `not_established` or add
   a new roll-up/status algorithm. Current renderer remains sequential; tree-aware layouts
   are not required by current rendering semantics.
8. Hidden helpers remain in the scientific map, proofs and diagnostics, and can supply
   properly proved inherited context. They gain no visible node and no independent rendered
   claim through omission. Hiding a requested answer obligation requires an explicit
   reviewed scope decision, not merely passing this structural validator.
9. Folded historical/decomposition IDs that are absent from the active scientific inventory
   are not new scientific children. Their scope remains attached to their reviewed owner.
   If a folded helper is an active scientific child, the author must explicitly own it or
   list it scientific-only. Never infer this decision from an execution `folded` flag.
10. `requested_construct_terms` is a required list of unique nonblank strings; `[]` is an
    explicit authored decision to configure no request-wide term restriction. Do not derive
    terms from scientific categories or evidence, or fill missing terms with `[]`.
11. Reject unsupported extra fields and mismatched request/review digests before retrieval.
    Require globally unique requirement IDs across the invocation for the current v2
    consumers: plan facets are keyed by requirement ID and rendering matches those IDs.
    Do not silently rename collisions or expand this increment into identifier redesign.
12. Optional/conditional scope is fixed by reviewed authoring, not by evidence-dependent
    removal of a node. A requested conditional question can retain its literal condition
    and node; establishedness still follows its existing scientific contract. If authoring
    excludes optional scope before execution, record that scope choice in the request and
    account for any remaining helper scientific child explicitly. No new condition evaluator
    or claim of condition satisfaction is introduced.

**Simple/flat Ask:** `request_contract.py:88–99` already creates obligation IDs such as
`s1-o1`. `stages.py:119` maps retrieval IDs to those obligation IDs; sealed responsiveness
and `overview_evidence.py:279–289` retain them. `sufficiency_diagnostic.units_by_child`
uses those actual attached IDs. Therefore the reviewed scientific contract can use the
same existing obligation ID as its child key. Do not use `s1` or a fabricated `root` key
and later relabel evidence to match it.

For one authored question with reviewed requirements under that existing identity, the
explicit single-node authoring operation copies the original question, assigns node `1`,
sets its parent to null and names the scientific child. Multiple scientific requirements
under that child need no hierarchy. If segmentation gives multiple obligations, a reviewed
one-node choice may own all their scientific children; this is an explicit grouping choice,
not an automatic conclusion from sentence count. Missing scientific authoring remains a
fail-closed precondition; reporting cannot generate evidence requirements from raw text.

## R15–R17: qualification compatibility and identity

The Phase-30 overlay remains replay-only historical material. A **qualification-only**
adapter may project its confirmed nodes as follows:

| Historical source | Reporting view |
|---|---|
| `label` | `node_id`, copied exactly (preserves historical labels). |
| `literal_text` | Copied exactly. |
| `parent` | `parent_id`, preserving null and exact source references. |
| `owning_child_ids` | Copied exactly; no evidence-driven remapping. |
| Source node sequence | Same sequence. |
| `requested_construct_terms` | Copied exactly. |
| Explicit folded/excluded records | Only active scientific IDs explicitly excluded from visible ownership become scientific-only; unresolved omissions fail. |

The adapter requires the original request and already authenticated scientific authoring as
inputs. Do not invent `request_ref` from the output map. Keep adapter provenance outside
the reporting body: the source overlay digest and actual confirmed replay authorization
identify this as a derived **replay** view. Source-only folded IDs absent from the active
scientific contract are retained in source history, not added to the reporting child set.
Never claim the original live execution possessed reporting-contract-v1.

Preserve exact D2/profile-A output paths. Do not replace the overlay in the historical
projection envelope or insert a reporting ref into the old serialized plan/manifest:
both would change accepted hashes. The adapter's reporting view can supply the same node
access for qualification while original authored bytes and serializer remain authoritative;
prove field/order equivalence. Additional view identity, if recorded, belongs in a separate
inspection artifact outside the frozen output hash, not in a rewritten D2 baseline. Leave
legacy phrase maps and every original overlay byte intact.

Fresh consumers receive reporting v1 natively. A narrow input-normalization seam can expose
node ID/literal/parent/ownership to the existing plan builder without duplicating facet,
proof, value or status logic. Map node ID to its existing label slot and pass the explicit
construct-term list to the same display checker. This compatibility view is not a Phase-30
replay overlay and carries none of its authority or event metadata. Fresh provenance binds
the native reporting body's ref, not a fixture-shaped synthetic receipt.

The fresh invocation provenance must bind the actual request, reviewed scientific frozen
definitions, reporting ref, explicit semantic version, sealed evidence, ownership context,
final map and recovery/search inputs. Create the trusted fresh provenance only from active
execution after scientific production; loading a persisted map cannot construct it.
The shared `validate_layerc_inputs` scientific checks remain mandatory.

Fresh plan/output provenance carries the reporting ref and typed
`trusted_fresh_invocation` upstream reference. Persisted profile B retains its exact
`VerifiedProducerAuthorization` and original overlay binding. A reporting hash does not
authenticate persisted scientific output; D1 remains required for that path. No fake D1
receipt, enrollment or wildcard profile follows from accepting a reporting object.

E1's recorded-disposition repair remains necessary and unchanged in scope. Recorded
noncurrent/v8 must be verified against its enrolled event/profile and known semantic version,
independently of today's current classification. Fresh execution uses actual runtime/explicit
version routing and cannot claim historical disposition just because it supplies old bytes.
Reporting identity is another authored-input binding, not a sufficiency semantics change.
No v9, current-default flip or replacement qualification receipt is proposed here.

## R18: domain-neutral conceptual A–J exercise

These cases are manually evaluated against the proposed contract, not executed production
tests. Every named child below is presumed to exist in that case's reviewed scientific
inventory, with requirements already authored independently of reporting.

| Case | Explicit authoring and expected result | Negative control |
|---|---|---|
| A. Atomic question | One root copies the authored alpha question and owns its existing obligation/scientific child. Valid; no hierarchy or new model pass. | Missing scientific contract fails; literal text alone cannot invent a requirement. |
| B. Independent subquestions | Two roots, authored sequence, disjoint ownership and explicit literals. Valid. | Segmented units are not automatically two visible nodes. |
| C. Parent question with two children | A parent answer obligation owns child `overview`; nodes for `measure` and `effect` reference the parent's node ID and own those distinct scientific children. Valid; parent state remains its own facets. | An empty decorative parent cannot acquire an answer state from its children. |
| D. Hidden helper | A visible node owns `outcome`; `context_helper` is explicitly scientific-only. Valid; helper science remains available under existing proof rules. | Unlisted helper fails the inventory partition check. |
| E. Many children, one visible node | A root explicitly owns `measure` and `effect`; plan-v5 evaluates their separate facets together. Valid. | Another node owning either child fails duplicate ownership. |
| F. Nested visible nodes | A depth-first ordered chain/tree with disjoint own obligations and valid parent links. Valid; no new descendant-state roll-up. | Cycle, unknown parent or conflicting authored ordering fails. |
| G. Optional/conditional child | Reviewed request fixes scope before retrieval; a requested conditional literal remains visible, or excluded scope is recorded before execution with helper disposition explicit. Valid within existing scientific declarations. | Hiding a node after an empty search, or inferring a satisfied condition from reporting, is prohibited. |
| H. Flat nonhierarchical question | Root owns reviewed scientific requirements keyed by actual flat obligation IDs, with scientific parent map empty. Valid; no fabricated hierarchy. | Binding `s1` when sealed responsiveness uses `s1-o1` fails before execution. |
| I. Category/list question | One authored node owns the existing list/category requirement's scientific child. Valid; reporting duplicates no requested-category inventory. | Turning open-list into exhaustive coverage or altering category polarity is prohibited. |
| J. Relational question | A node owns the child containing its reviewed relation requirement; existing proof/value machinery decides reportability. Valid. | Owning two atomic children does not manufacture a joint relation or citation witness. |

These establish schema applicability to arbitrary subject matter and the existing supported
scientific types. They do not establish automatic semantic authoring from arbitrary natural
language, or support for decorative layouts, dynamic conditions or arbitrary presentation DAGs.

## R19–R21: one bounded implementation and acceptance

**R19: zero q_aib semantic/runtime dependency in the new authored fresh route.** Qualification
adapters retain their fixture bindings, separately. The legacy experimental command may
keep its existing fixture-specific choices; the new route cannot use those choices as its
authoring source. No product `/summarize` changes.

**R20: recommend one I4-4E1B atomic implementation; no split is necessary.** The review/input
addition, fresh execution routing and historical identity repair form one testable boundary:

1. Implement the reporting body, pure structural validator and deterministic single-question
   authoring operation. Accept explicit multi-node authoring alongside existing reviewed
   scientific inputs. Bind joint review before retrieval; never implement a new automatic
   scientific decomposition or a separate model pass.
2. Add an explicit public authored-request route to the experimental runner/CLI that takes
   invocation-owned request, scientific and reporting inputs. Reuse existing runtime setup
   and `e2e.execute`; no separate scientific execution implementation. Do not leave this as
   a private constructor or an injected test overlay. Do not fall back to the old question
   table, hierarchy loader or frozen sufficiency defaults when input is missing.
3. Thread explicit v8 selection through the new route and execute the existing U1/U2
   orchestration. Replace hierarchy-only eligibility **only for this explicitly selected,
   reviewed-input route** with validated scientific obligation coverage. Preserve legacy
   route behavior. `e2e.py:524, 723–726, 953` currently gate U1/U2/parent output on hierarchy;
   a post-U2 adapter alone cannot qualify the flat public case. Use existing obligation IDs,
   reviewed scientific parent links, and the same mapper/ownership/recovery machinery.
4. Carry immutable pre-retrieval authored input snapshots to the actual post-U2 handoff;
   produce trusted invocation provenance there, pass the shared scientific validator and
   v2 consumers, and select their plan-v5 answer for this route. Do not merely emit additive
   artifacts while leaving the selected answer on legacy rendering.
5. Add the replay-only reporting view adapter with exact historical serialization, and
   separate recorded disposition verification from fresh routing as already required by
   E1. Preserve source pins/receipts and exact historical qualification; no baseline updates
   may mask drift. No registry generalization or science edits.

This makes the requested sequence possible for a genuinely reviewed non-q_aib request
using the existing scientific builders/mapper. The reviewer authors scientific intent;
the small reporting addition authors its presentation ownership. It does not require a
new architecture. A goal of unattended raw-text-to-scientific-contract authoring would
require additional scope and is **not** silently included in E1B or claimed ready here.

The implementation's decisive control must start at that public authored-request route
with a new non-q_aib flat question, its independently reviewed scientific requirements and
native reporting object. Offline retrieval/model substitutes may supply deterministic
evidence at existing stage boundaries; they must not prebuild the final map, fake trusted
fresh provenance, inject a historical overlay, or call only `_build_components`. Actual
U1/U2 orchestration, handoff, shared validation, claim-v2, plan-v5 and selected rendering
must run. Include a relational control where applicable and mutation-before-retrieval
rejection of request/science/reporting mismatches.

Require the E1 gates in the same implementation: generic A–J, no receipt needed fresh,
persisted input cannot masquerade as fresh, recorded noncurrent/v8 survives a hypothetical
current-v8 flip while fresh v8 reads current, scientific before/after equality, D1/D2
authentication, exact v4–v8/profile-A/profile-B hashes, static fixture-dependency guards,
then full offline qualification and established optional tests. These are future gates;
none is represented as already passed by this planning audit.

**R21: READY for that bounded reviewed-authored implementation; not ready for promotion.**
The E1 STOP was correct for the old caller. This proposal supplies the missing authored
input before retrieval and specifies the necessary caller transport, rather than assuming
the old caller already had it. Failure to supply/review scientific or reporting authoring
must stop the fresh route; no fixture fallback or invented authority is permitted.

## Verification, files and stop

Ten source/static assertions checked: plan node-field reads; render label/literal reads;
render's lack of parent-state handling; synthesis's lack of reporting-field dependency;
active construct-term transport; projection overlay hashing; absence of reporting arguments
at current fresh boundaries; absence of the product planner import in `e2e`; literal-request
non-certification; and explicit frozen/review path parameters. All ten passed. Additional
source inspection traced flat obligation IDs through sealing and scientific attachment.
No prototype reporting implementation or new tests were written.

E1A changes exactly this report and the appended experiment lineage. Final HEAD remains
the clean-start checkpoint `13680c71954c7f75964e096ceb48339eb1faf618`; these new audit docs
are left uncommitted because this brief authorizes commit/push of the prior E1 checkpoint,
not a new E1A commit. Documentation whitespace/EOF and exact change scope are checked.

Explicit backlog: extensible layouts, custom templates, arbitrary presentation DAGs,
signatures/enrollment, schema plugins, cross-query entity normalization, unknown role
types, automatic general scientific authoring, UI integration and I2-3 wording. No such
subsystem is introduced to solve this reporting boundary.

Stop after E1A. No reporting implementation, E1 resumption, promotion, I2-3, application
endpoint rewiring or automatic next increment.
