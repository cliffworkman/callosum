# Future Freeze-A execution checklist — NOT EXECUTED

Prepared 2026-09-11 from directory names and experiment writer code only. No
candidate records, source inventory, archived output files, or sealed mapping
were opened to prepare this checklist. Do not run the old experiment scripts:
their helpers read more material than this task requires and may write artifacts.

## Authorization and restricted inputs

Obtain explicit authorization for the following private corpus preparation and
Freeze A. Semantic screening needs its own authorization; a hashed freeze does
not dispatch any calls. Resolve Claude's expanded-envelope gap first if it is
to remain in the proposed roster.

Define these exact roots:

- O: `C:/Users/cliff/AppData/Local/Temp/callosum-claim-representation-isolation-resume-20260909-190527`
- B: `C:/Users/cliff/AppData/Local/Temp/callosum-claim-representation-isolation-20260909-184828`

Only these three content artifacts are needed:

| Artifact | Fields retained privately | Decision enabled |
| --- | --- | --- |
| `B/experimental_units.json` | `unit_id`, `qid`; for `qid == "q_aib"` only: `quote`, `paper_id`, `span`, `grown_context`, `source_unit_context` | Establish membership and original source/context boundaries |
| `O/arm1_outputs.jsonl` | `unit_id`, `arm`; for eligible units only: `raw_text`, `produced_representation`, `provider_ok`, `failure_reason`, `finish_reason`, `truncated`, `whole_response_parse_success`, `schema_valid`, `malformed_response`, `mechanically_complete`, `empty_response`, `explicit_null_claim`, `wrapper_fallback`, `prompt_sha256` | Bind the original observation and effective carrier, retain technical missingness without model-based exclusion |
| `O/arm2_outputs.jsonl` | Same projection as Arm 1 | Bind the second tested configuration without decoding the old blinded packet |

Metadata-only supporting reads:

- `O/artifact_hashes.json`: project only the entries for the two output files
  and the execution freeze manifest. Do not follow every listed path.
- `O/execution_freeze_manifest.v2.json` and its `.sha256` sidecar: verify the
  manifest, then retain only the `files` entry identifying
  `B/experimental_units.json`. Do not recursively verify unrelated artifacts.

Hash the three allowed files as bytes and compare the applicable recorded
hashes. Full-file hashing necessarily streams all bytes; projection must not
display, analyze, or retain non-q_AIB semantic fields. The inventory also carries
historical lineage: discard that field, never inspect its nested raw outputs.
Use a bounded field-projecting reader with content-free errors. If its structure
cannot be processed without widening retained access, stop for an amendment.
Do not describe file-level access as though only eligible bytes were read.

## Corpus identity and source binding

1. Confirm unique inventory unit IDs and exactly one row per eligible unit in
   each selected arm. Treat the methods-code expectation of 39 q_AIB units / 78
   observations as a check to verify later, not a count measured in this task.
   A mismatch stops preparation; do not silently change membership.
2. Preserve mechanical failures in the corpus manifest. Missing/unusable output
   is technical evidence, not a fabricated semantic label. Freeze its handling
   explicitly; do not silently drop a case from the denominator.
3. Bind each observation to `(original archive identity, unit_id, arm)` in a
   **new private manifest**. Create new opaque candidate IDs using a recorded
   domain-separated digest and collision checks, at most 80 ASCII bytes. Do not
   reuse or reconstruct the old blinded candidate IDs or their sealed key.
   Public packets omit arm, selection rationale and identity mapping. Intrinsic
   representation form can still reveal configuration; do not promise perfect
   arm blinding. The new private configuration manifest is necessary for later
   configuration-level decisions and remains inaccessible to Cliff.
4. Record file SHA256, original record-byte SHA256, projected canonical-record
   SHA256, and each source/scientific-object SHA256. Preserve raw source strings
   and spans exactly; never normalize or reconstruct scientific content.
5. Bind `quote` as the exact excerpt, `grown_context` as reference-only context,
   and `source_unit_context` as source-unit/obligation context. Retain paper ID
   and span. Bind `produced_representation` as the effective carrier. Keep its
   annotations and status fields; canonical quotation cannot excuse erroneous
   interpretation. `raw_text` cannot repair the effective representation.
6. For Arm 2 check canonical quote, paper ID and span against the inventory by
   exact structural comparison. A mismatch stops preparation; never repair it.
   Do not read `parsed` or re-run production parsing to reconstruct a carrier.

## Actual size gates before any semantic submission

1. Render complete objects with the exact shared prompt, assigned attention
   text, output instructions, framing and wrapper. Count UTF-8 bytes of the
   actual transmitted form, including escapes and any inserted blank lines.
2. Proposed route: at most 2 candidates, at most 20,480 input bytes including
   wrapper, at most 80 ASCII ID bytes, and 1,216 expected response bytes. Reserve
   512 UTF-8 bytes for each FLAG/UNCERTAIN reason **as serialized**, including
   escape expansion; NO_FLAG has an empty reason. The 2,048-byte prompt reserve
   is an engineering allocation, not permission to shorten the scientific task.
3. Pack in fixed order using whole objects. If two do not fit, use one; record
   surface/batch context as an interpretation limitation. If one complete object
   plus instructions does not fit, stop that route for a synthetic transport
   amendment. Never truncate source, carrier, annotations, or meaningful reasons.
   Also gate serialized objects at 14,698 bytes individually and 16,413 combined,
   the demonstrated structural allocation; larger objects need an amendment even
   if total input bytes would fit.
4. Full input budget is a provisional constraint, not an estimate of actual
   corpus sizes. Synthetic copying does not establish semantic competence, a
   token ceiling, or reliability at every smaller size/format. Check provider
   token constraints when exposed; otherwise retain UNKNOWN.
5. Before semantic execution, settle lossless delimiter/newline escaping and
   test the semantic row parser with synthetic FLAG/UNCERTAIN/NO_FLAG fixtures.
   The new Claude COPY_OK adapter is deliberately **not** a semantic row parser;
   future reasons have no known expected answer. Do not match or repair them
   using expected-receipt logic. Preserve over-budget/unparseable raw answers as
   mechanical exceptions, never truncate, infer a label, or convert to NO_FLAG.

## Required freezes and amendment triggers

Freeze A records hashes of: projected corpus and private identity manifest;
source bindings; eligibility/technical-missingness rules; criterion/labels;
each exact prompt and roster/role assignment; account/model provenance and
qualification evidence; canonical scientific objects and each transmitted
packet; batching order/parameters; renderer/parser versions; retry rules;
operational blinding, capture boundaries and access permissions; preservation
rules and complete-Study-1 closure rules. Create a content-addressed manifest
and timestamped approval receipt privately. No fabricated real hashes now.

Append an amendment for any format/batch/parser/capture/scheduling/account/model
change. Record what, why, timestamp, semantic visibility, Cliff's blinding,
affected hashes and interpretation consequences. New model or account needs
appropriate synthetic qualification. Missing coverage pauses the roster; never
silently reassign roles after semantic results. Any scientific-task change
requires an explicit scientific amendment, not a transport relabeling.

The sealed directory, old blinded packet, old randomization manifest,
Arm-0 outputs, wire logs, treatment inputs, database, historical lineage and
other questions' semantic records remain outside this preparation's retained
access. The original 492 observations/exhaustive protocol stay immutable.

Freeze B still follows private completed Study 1 and its logged interstudy
design amendment. Nothing here fixes the real human queue or changes the human
budget, severe-failure rule, attention safeguard, or later acceptance boundary.
