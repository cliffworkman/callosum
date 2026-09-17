# Pre–Freeze-A hardening — 2026-09-11

**BLOCKED only on expanded-envelope evidence for the proposed Claude route.**
No Freeze A, real-corpus access, sealed mapping access, semantic screening, or
human queue occurred. Production and ask_070 files were not edited; nothing was
staged or committed. Earlier audit reports and all original observations remain
unchanged. This report supplements the accepted Phase -1 closure.

## Claude adapter and tests

`receipt_adapter.exact_receipts_in_prose` is a synthetic COPY_OK adapter only.
It accepts UTF-8, normalizes CRLF to LF, and collects only full-line byte-exact
expected receipts. Every expected identifier must occur once in the correct
order. Missing, altered, duplicate, reordered or extra rows fail. There is no
trimming, fuzzy match, repair, deduplication, ID inference or model normalization.

Nonmatching lines containing pipes, receipt/status markers, candidate-like IDs,
long hexadecimal strings, or 16-character literal receipt fragments fail closed.
Other prose, blank lines and Markdown fences may surround exact rows. Inline,
quoted or list-prefixed rows do not qualify. Ordinary short words alone cannot
be identified as receipt fragments; the adapter checks syntax, not the meaning
or sincerity of surrounding prose. It does not declare such prose trustworthy.
Conservative false negatives are acceptable; never add a rescue rule based on
semantic-study responses.

**28 adapter tests pass**: missing/changed/partial rows, changed IDs, exact and
conflicting duplicates, reversed order, embedded misleading rows, fake rows,
orphaned/embedded suffix fragments, whitespace changes, fences, prose, encoding,
contract validity and LF/CRLF. Two new envelope tests also pass. The whole
synthetic suite passes **93 tests**, with Ruff clean.

The preserved clean Opus 4.8 High final body passes the adapter. Its original
strict-output failure remains intact. Classification:

`QUALIFIED_WITH_NARROW_ADAPTER_UNDER_OPERATIONAL_BLINDING`

This classification applies to the previously audited **20,541-byte / two-record
/ 406-byte response** envelope. No new Claude call was made. The ambiguous older
Claude answer was not reinterpreted. Opus 5 remains retired. The original raw
response is in the closure store; its SHA256 is
`ce38ed7ba625816add64baa6dfb4d91b8a46c1a267e0b7126f4d030d1d76fd66`.

## Conservative intended envelope

`reason_envelope.ReasonEnvelope` generates only fabricated complete objects.
It cannot accept a file, arbitrary candidate content, or external observations.
Source excerpt, grown context, source/task context, raw output and effective
representation stay structurally separate, including nested annotations.

| Allocation | Provisional bound |
| --- | --- |
| Candidates per batch | 2 maximum; reduce to 1 when necessary |
| Entire transmitted input, including wrapper | 20,480 UTF-8 bytes |
| Generated test packet | 20,352 bytes |
| Wrapper | 82 bytes, within a reserved 128 bytes |
| Shared prompt reservation | 2,048 bytes; existing all-role prompt is 1,301 bytes |
| Candidate identifier | At most 80 ASCII bytes |
| FLAG/UNCERTAIN reason | At most 512 UTF-8 bytes in its serialized form |
| Expected response | At most 1,216 UTF-8 bytes for two maximal UNCERTAIN rows |
| Demonstrated serialized objects | 14,698 and 1,715 bytes; 16,413 combined |
| Provider-specific token ceiling | Unknown; not inferred from byte budgets |

Both test labels and reasons are predetermined literal strings. The test never
asks a model to judge fidelity. UNCERTAIN is the longest of the unchanged three
labels, so two maximal UNCERTAIN rows bound the expected output. Reasons include
fabricated source anchors and literal length padding; this establishes copying
capacity, not reasoning quality or actual corpus dimensions. FLAG and NO_FLAG
remain unchanged; the fixture supplies no semantic labels.

The eventual actual-size check must also keep each serialized scientific object
within the demonstrated 14,698-byte object envelope and the combined objects
within 16,413 bytes, or obtain a synthetic amendment. These conservative object
limits prevent substituting a much larger single object merely because the
total input still fits. No theoretical maximum was sought. Neither input size
nor one successful trial establishes general reliability.

Semantic reasons that do not fit are preserved as mechanical exceptions; never
truncate or weaken their scientific content. The exact output escaping and
semantic-parser contract must be frozen and synthetically validated before
semantic execution. This work does not repurpose known-answer receipt matching
as a semantic normalizer.

## Surface results at this envelope

Each final answer is preserved privately before deterministic scoring. No model
response text is included in this report. LF/CRLF and final-newline handling are
the existing strict convention.

| Surface/configuration | Expanded-envelope result | Relevant qualification |
| --- | --- | --- |
| Alternate ChatGPT / 5.6 Sol, High | Strict PASS | Response menu identifies 5.6 Sol |
| Gemini / explicitly selected 3.1 Pro | Strict PASS | Pro selected and recorded before submission |
| Grok / Fast | Strict PASS | Backend version not exposed |
| Microsoft Copilot / Smart | Strict layout FAIL; existing empty-line adapter PASS | Adapter removes only wholly empty lines |
| DeepSeek / version not exposed | Strict PASS | Original-text route |
| Kimi / Instant | Strict PASS on final answer | Tool/thinking output kept separate; Python tool use observed |
| Z.ai / GLM-5.3-Flash | Strict PASS | Pasted-text route |
| Claude / Opus 4.8 High | UNTESTED at expanded envelope | Narrow adapter qualifies only previous envelope |
| GitHub Copilot / Auto | Not retested | Prior technical failure remains; no rescue |

A fresh Gemini conversation initially defaulted to **3.6 Flash**, which also
passed. That capture remains a separate configuration result and is not counted
as Pro evidence or an additional rater. A logged amendment authorized one
unchanged synthetic trial with 3.1 Pro selected before send. No semantic results
informed that correction.

Kimi's first capture accidentally targeted its still-growing tool/thinking
container. The premature completion claim is explicitly retracted in a capture
correction; both that artifact and the later complete final answer remain.
Only the final `.markdown-container:not(.toolcall-content-text) > .markdown`
answer was scored. There was one Kimi submission, no nudge or regeneration.

ChatGPT, Gemini and Grok's rich-text composers inserted blank paragraph
separators: every nonempty input line was verified exact before submission,
with observed input 20,369 bytes, below the total budget. DeepSeek and Z.ai
retained exact original text. Copilot and Kimi used automatic TXT attachments
from the generated packet plus the fixed wrapper. Their tested route exposes
upload/name indicators but not an independent full-file preview: record that
limitation, rather than claiming every attachment byte was independently read
back. Exact first/last receipts and final complete output support bounded
transport execution, not proof that a model attended to all source content.

No quota exhaustion blocked these completed trials. Backend identities, quota
ceilings and attachment maxima remain unknown where the interface does not
expose them. Account aliases/tiers and prior failures remain in the closure
provenance; no alternate accounts were substituted. Payment confers no weight.

## Updated proposed assignments — NOT FROZEN

Apply ROSTER order, excluding GitHub Copilot, then assign ROLES round-robin.
Claude's inclusion follows its narrow qualification, not a quality preference.
Expanded-envelope eligibility is a separate unresolved gate for Claude.

| Configuration | Proposed role |
| --- | --- |
| Claude / Opus 4.8 High | Literal fidelity |
| Gemini / 3.1 Pro | Subject/population preservation |
| Grok / Fast | Relationships, endpoints and direction |
| Microsoft Copilot / Smart | Null/mixed/uncertain evidence |
| DeepSeek | Unsupported additions / neighboring import |
| Kimi / Instant | Qualifiers/modality |
| Z.ai / GLM-5.3-Flash | Proposition reconstructability |
| Alternate ChatGPT / 5.6 Sol | Broad skeptical review |

These eight separately generated raters do not have IID errors, and consensus
does not establish truth. Codex is methods/infrastructure engineering only.
If the roster changes, recompute by the same rule before semantic execution;
do not silently remove an attentional role or substitute a mode/account.

## Readiness, audit trail and remaining blocker

[FREEZE_A_LEAST_ACCESS_CHECKLIST.md](FREEZE_A_LEAST_ACCESS_CHECKLIST.md) gives the
exact future three-file content allowlist, metadata projections, field-level
retention, new private identities, source binding, byte gates, hashes and
amendment triggers. No existing sealed key is necessary. No real identities or
hashes were fabricated, and no real-corpus preparation was executed.

The current private hash-linked store is:
`C:/Users/cliff/AppData/Local/Temp/callosum-adjudication-synthetic-i1zf3y9c`.
It preserves generated packet/expected output, model/input gates, captured raw
answers, corrections, deterministic results, proposed roles, implementation
snapshots and this readiness package. The original Claude response remains in
`callosum-adjudication-synthetic-0uafiism`, linked by path and hash. Raw browser
relay files are retained separately under `callosum-reason-relay-Njptxk`.

Packet identity: `reason3-409179459b78cabf944aa98a`.
Payload SHA256: `409179459b78cabf944aa98a4cb3bafa77eb177cab86888de76f26fbe2f41cc2`.
Expected-output SHA256: `b10f3d07afccbc463c2c2a3325c5d5c96d9b78b06a65b42f2002dcc393a74ef0`.

**Remaining blocker:** Claude has no direct expanded-envelope evidence. Its
surrounding prose length in the old answer cannot substitute for correct
reason-sized rows. The current instruction prohibits another Claude call and
no ambiguity in the narrow adapter required one. Therefore the eight-rater
proposal cannot yet be declared ready for the new common envelope. Resolving
this requires an explicit next authorization for that synthetic gap, or a
reviewed roster amendment; neither is inferred here.

Operational blinding remains a dedicated minimized browser, no investigator
inspection, private DOM capture, no clipboard and no response echo. It is not a
technical guarantee against incidental exposure. Preserve affected records and
log HUMAN_BLINDING_COMPROMISED if exposure occurs. No exposure was reported in
this task. Retain the two-freeze architecture, private content-informed
interstudy design, and human capability to overturn the frontier screen.
Human gates/budgets, severe-failure rule, archived fallback, integration and
end-to-end acceptance boundaries remain unchanged. No R_0_6 nomination or 0.7
semantic execution is authorized by this component work.
