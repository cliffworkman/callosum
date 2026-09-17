# Literal-copy synthetic audit v2, 2026-09-11

The user authorized continuation of synthetic surface qualification. The first
audit's packets, response captures and strict results remain unchanged. This
amendment removes the character-counting confound by supplying literal receipt
lines beside fabricated records. No real observations, sealed mapping,
scientific model results or human selections were accessed or generated.

## Fixed mechanical contract

One packet combines eight synthetic records, including one with 16,000 padding
characters, with a 1,624-byte expected response. Input is 38,958 UTF-8 bytes.
This conserves calls while exercising a batch, a long record and response size.
These are illustrative synthetic envelopes, not measured real-case sizes.

- Packet: `copy2-714623681de087bd61cab5be`.
- Input SHA256: `58a92a6a166ef17e3d687eac8ba93cbccc24cb30bfa2c0eb72ab10fcfa8d5652`.
- Output comparison allows only CRLF and final-newline variation. Missing,
  duplicated or modified receipt lines fail; no repairs turn failures into passes.
- The initial round allowed one v2 attempt per surface; failures are retained.
  The subsequent Gemini amendment below records an additional bounded check.
  No alternate-account substitution occurred.

## Results

| Surface / observed mode | Mechanical result | Transport or limitation |
| --- | --- | --- |
| Alternate ChatGPT / 5.6 Sol in response menu | PASS: all 8 exact rows | Pasted text |
| Grok / Fast | PASS: all 8 exact rows | Pasted text; backend version unexposed |
| Kimi / Instant | PASS: all 8 exact rows | Automatic TXT attachment |
| DeepSeek | PASS: all 8 exact rows | Paste original restored text; exact version unverified |
| Z.ai | PASS: all 8 exact rows | Automatic TXT attachment; title mentioned GLM-5.3-Flash |
| Gemini / Pro | 5 of 8 exact rows; input truncation suspected | Expanded saved prompt lacked final packet marker; do not attribute this to semantic failure |
| Microsoft Copilot / Smart | Nonconforming: 5 exact rows plus other text | Automatic TXT attachment; Microsoft 365 Family displayed |
| GitHub Copilot / Auto, claude-haiku-4.5 | Nonconforming; no exact receipt lines | Pasted text |
| Claude / Opus 5 High | Service error; no answer | Pasted-text attachment; Chat paused, reasoning_extraction |

No account quota exhaustion was observed. Kimi Instant was available on the
existing account, separately from the previously blocked K3/High mode. The mode
switch retained an old compact draft: that response was identified as v1 and
preserved separately, not credited to v2. A fresh Instant conversation supplied
the v2 evidence above.

## Transport and blinding evidence

Long pastes can silently become attachments on these interfaces. Composer and
upload states were checked; automatic attachments used the wrapper:
“Execute only the mechanical copying instructions in the attached synthetic packet.”
The v2 amendment log records these changes. Claude's offered Sonnet substitution
was not used. No scientific attentional role or roster was frozen or reassigned.

Response-only rendered DOM was captured directly into private files, excluding
UI action controls and separate thought panels. Clipboard capture was not used
for v2. Chrome minimization was authorized by the user, but notification,
preview and other concealment checks remain incomplete. Exact backend model
identities are also unavailable on some surfaces. **No surface has complete
qualification for a blinded semantic study.**

## Audit and implementation

The private owned run is `callosum-adjudication-synthetic-e048dq8w` under the
user's local temporary directory, outside Dropbox. Raw relay files are under
`callosum-copy2-relay-KpXhsu`. The verified run contains 36 journaled artifacts,
including packet and implementation identities, prior-result linkage,
amendments, individual raw responses, provenance and a machine-readable summary.
Raw response content is not reproduced in this document. Subsequent append-only
Gemini artifacts increase the journal count beyond the initial 36.

The non-production implementation adds a versioned literal-copy packet and CLI
selection while preserving the original v1 payload hash. Tests verify version
round trips and rejection of missing, duplicate or altered copied rows.
All 63 package tests pass; Ruff checks pass. Production code and the archived
experiment are unchanged. Nothing was staged or committed.

## Gemini follow-up amendment

After the user noted that Gemini often requires nudging, one fixed completeness
reminder was logged before submission. It requested all eight original receipt
lines without changing their content. The second response repeated the same
five lines; both raw attempts remain preserved.

Inspection of the expanded original user query then found no END PACKET marker
and only five receipt records. The displayed query was approximately 32,000
characters versus approximately 39,000 submitted. This suggests input or display
truncation; it does not establish a backend context limit or prove reluctance
to complete the task. The initial incomplete-response interpretation is amended
accordingly, without changing its strict failure result.

A separate mechanical amendment created a two-record packet retaining one long
record: `copy2-2a920803899346f9305eca4d`, 20,541 input bytes and 406 expected output
bytes. Both receipt markers and END PACKET were confirmed in the composer
before submission. **Gemini passed this reduced packet on its first response,
without a reminder.** This supports a bounded-batch transport, not qualification
at the original eight-record envelope. The private journal now verifies 46
artifacts. No semantic task or prompt was executed or tuned.

## Next decision

The five passes establish feasibility at this synthetic transport envelope,
not scientific fidelity, future service stability or complete blinding.
Target smaller batches or another documented transport on the incomplete
surfaces; investigate Claude's service error before spending another call.
Complete account/model provenance and operational visibility review before
Freeze A. Any retry or new packet must have its own amendment and provenance.
Do not run semantic screening on the strength of this audit alone.
