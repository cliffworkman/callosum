# Phase -1 qualification review

Review date: 2026-09-11. Scope: synthetic capability evidence only.
**NO real semantic observation has been consumed.** No sealed mapping, real
queue, scientific frontier prompt, Freeze A, revised-0.6 integration or R_0_6
work was accessed, generated or executed. Previous failed and partial attempts
remain intact. This review made no new model calls.

## Decision

Seven surfaces have bounded transport evidence, including Microsoft Copilot
with an empty-line-only layout adapter. None has completed blinding
qualification through the present shared interactive workflow. Do not admit
these surfaces to semantic execution yet.

The current common packet is `copy2-2a920803899346f9305eca4d`: two fabricated
records, including one long record, 20,541 input bytes and 406 expected response
bytes. It is sufficient to support a decision about copying and ingestion at
this bounded envelope. It does not establish global context limits, fidelity,
complete field-wise parsing, or adequate output capacity for longer answers.
Later packet admission must check actual byte/count constraints without splitting
or truncating a scientific unit. Oversize material requires an adapter amendment.
File acceptance alone is not ingestion evidence. Earlier larger-packet Gemini
missing-end-marker and incomplete-output evidence remains a limitation.

## Per-surface outcome

All exact passes below refer to the common packet, not semantic competence.
Recorded timestamps are UTC; complete URLs, hashes and timestamps are in the
private machine-readable report. Account labels are descriptive, not credentials.

| Surface / observed configuration | Account/plan evidence | Transport result | Final status |
| --- | --- | --- | --- |
| ChatGPT / 5.6 Sol response-menu label | Alternate account, Plus observed | Exact pass; automatic paste attachment; 15:43:28 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| Gemini / Pro mode, exact backend unknown | Signed in; plan unknown | Exact pass; bounded text; 15:43:41 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| Grok / Fast mode, exact backend unknown | Signed in; plan unknown | Exact pass; rich-text paste; 15:43:42 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| Kimi / Instant mode, exact backend unknown | Signed in; tier unknown, K3 previously blocked | Exact pass; automatic TXT; 15:44:27 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| DeepSeek / exact backend unknown | Signed in; plan unknown | Exact pass; Paste original text; 15:44:27 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| Z.ai / GLM-5.3-Flash model control | Signed in; plan unknown | Exact pass; bounded text; 15:45:39 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| Microsoft Copilot / Smart mode, backend unknown | Microsoft 365 Family displayed | Exact rows with empty-line adapter; strict layout failure preserved; 15:43:28 | PROVISIONAL_PASS_PENDING_BLINDING_QUALIFICATION |
| GitHub Copilot / Auto, Haiku 4.5 response label | Copilot Free | Required identifiers and receipt lines absent; 15:41:30 | TECHNICALLY_UNAVAILABLE for this protocol |
| Claude / Opus 5 High | Regular Pro account observed | Repeated reasoning_extraction service error, no answer | TECHNICALLY_UNAVAILABLE |
| Claude / Opus 4.8, user reported | Attribution pending | No independently verified attributable answer located | UNRESOLVED |

Backend model labels are UI observations, not independently verified provider
implementations. Mode names are not silently promoted into backend-model claims.
Auto is not a stable backend guarantee. Separate surfaces do not imply IID errors.

## Manual Claude check

The user-directed open conversation was
`https://claude.ai/chat/2e6514fa-4024-4f7e-8cf3-39de5f2cf350`.
It has the expected synthetic attachment filename and a completed answer. Its
current selector reads **Sonnet 4.6 High**; no response-specific model label was
exposed on the inspected article. A current selector does not establish the
generation model. The user was asked whether it changed after generation or
whether an Opus 4.8 answer exists in another conversation.

The preserved response is 2,410 bytes and contains neither expected candidate
identifier nor either full receipt line. It therefore fails the mechanical
contract, regardless of the unresolved generation-model attribution. A completed
answer is not equivalent to a copying pass. Keep this answer distinct from both
Opus 5 failures and the user-reported Opus 4.8 success. No causal conclusion about
browser automation, vendor intent or the service error follows.

## GitHub Copilot diagnosis

The saved reduced-packet answer has 19 lines, neither expected identifier, no
COPY_OK token and neither expected receipt line anywhere in it. The composer
exactly matched the packet bytes before submission. This is nonconforming task
output, not harmless whitespace or Markdown layout. A deterministic adapter
cannot recover the absent rows without inventing content.

There is no evidence that Auto switching caused the failure: inspected trials
identified Haiku 4.5, while Auto's future selection remains unpinned. Complete
backend ingestion cannot be proven solely from the composer. Bound the result
as NOT QUALIFIED FOR THIS BOUNDED ENVELOPE; retain Haiku as an honestly identified
candidate for a separately justified future mechanical amendment. No retry was
needed to establish this diagnosis. Semantic competence was not evaluated.

## Microsoft Copilot adapter

Retain the original strict-layout failure. The separate comparison normalizes
CRLF and deletes only zero-length separator lines. It never applies strip() to
nonempty lines or edits, reorders, deduplicates or fills rows. Synthetic checks
passed for exact output, empty separators and CRLF, and rejected missing,
duplicated, reordered or altered rows, space-only and tab-only separators,
leading whitespace and commentary. No adapter broadening is permitted.

## Blinding qualification

| Path | Evidence and limitation |
| --- | --- |
| Viewport | Dedicated minimized Chrome is user-controlled; hidden-tab capability was unavailable. It is not enforced concealment. |
| Notifications | No dedicated synthetic notification test evidence; user exposure question pending. |
| Previews | Browser DOM contains titles and response previews. Selective output filtering is not a universal redaction boundary. |
| Clipboard history | Current DOM-to-file route bypasses clipboard; first compact Claude used it and historical retention is unknown. |
| Terminal/sink | Synthetic CLI success/error non-echo tests pass. Ad hoc scripts are not a sealed operator interface. |
| Exceptions | CLI tests do not qualify browser/extension errors, locator payloads or tool-trace output. |
| Storage | Outside Dropbox with immutable hashes; still accessible through Cliff's local account, not access-separated storage. |

The 16 existing storage/CLI boundary tests were rerun successfully, including
synthetic non-echo exceptions and immutable capture checks. This is evidence
for those components only. No notifications, OS privacy settings or browser
permissions were altered during this review.

**The present shared workflow is technically unavailable for blinded semantic
execution until a stronger capture/visibility boundary is qualified.** This
does not overturn its transport passes or assert intrinsic surface failure.
The smallest global amendment must specify a separate operator/capture boundary
or a demonstrably redacted UI, notification, preview and exception route, then
test it with synthetic canaries. An agreement to avoid looking alone is not
enough to claim completed qualification.

## Role readiness and stop

Seven transport survivors could cover eight roles with at least three raters
and at most three roles each; numerical capacity is adequate without either
Claude or GitHub Copilot. However, zero raters are fully qualified for the
blinded phase through the current workflow. No actual role assignment or freeze
was created. Preserve all eight predeclared roles and revisit assignments once
the blinded roster is established.

Private review run: `callosum-adjudication-synthetic-9u8o6o20` under the user's
local temporary directory. It contains the manual capture, model-attribution
record, GitHub diagnosis, adapter validation, visibility review and per-surface
qualification JSON, with links to the prior immutable runs. The raw manual
relay is `callosum-final-audit-relay-z8IryK`. Raw answers are not printed here.
No production changes, staging or commits occurred.

**PHASE -1 BLOCKED — AMENDMENT REQUIRED**

Smallest global blocker: qualify the blinded capture/visibility boundary.
Additional Claude-specific blocker: locate and verify an attributable Opus 4.8
answer if that configuration is to be retained. GitHub Copilot may remain
technically unavailable without preventing sufficient role coverage.
