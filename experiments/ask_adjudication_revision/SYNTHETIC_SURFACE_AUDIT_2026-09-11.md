# Synthetic surface audit, 2026-09-11

This is an actual consumer-interface audit using only generated mechanical
fixtures. It is not Study 1, Freeze A, semantic screening, or human adjudication.
No real observations, sealed mapping, or archived semantic results were read.
The user authorized both Microsoft Copilot and GitHub Copilot as separate
surfaces, and authorized testing in a dedicated minimized Chrome session.

## Observations

| Surface | Compact: 2 KB / 2 cases | Intended: 23 KB / 8 cases | Single long case: 17.5 KB |
| --- | --- | --- | --- |
| Claude | Exact response passed | Attachment upload failed; no final answer captured | Not run |
| Alternate ChatGPT | Exact response passed | Exact response passed | Padding length failed |
| Gemini | Exact response passed | Exact response passed | Padding length failed |
| Grok | Exact response passed | Padding length failed | Not run |
| Microsoft Copilot | Exact response passed | Padding length failed | Not run |
| GitHub Copilot | Required response format failed | Not run | Not run |
| DeepSeek | Exact response passed | Padding length failed | Not run |
| Z.ai | Exact response passed | Padding length failed | Not run |
| Kimi | K3/High required a higher account tier; no response | Not run | Not run |

Exact checks normalize only CRLF and a final newline. Failures and raw response
captures are preserved; none were silently repaired or converted into passes.
The sizes are synthetic design envelopes, not measurements of real candidates.
Untested profiles do not establish a surface's upper capacity.

## Interpretation and next qualification step

The strict fixture asks for exactly 160 repeated padding characters. Several
surfaces returned the requested rows but miscounted that padding. This conflates
character-counting ability with transport and response capture. It is evidence
about this fixture, not evidence of semantic failure or inability to execute a
future fidelity screen. No surface is fully qualified by this pass.

Preserve this run and explicitly amend the synthetic fixture before spending
more calls on exact padding counts. A replacement should supply literal output
tokens to copy, test identifier completeness and boundaries, and separately
measure response size. Record new packet identities and qualify the revised
mechanical contract independently; do not relabel historical failures.

No general quota exhaustion was observed. Kimi showed an account-tier block;
the user was asked about a qualified alternate account or available mode. Any
account/mode replacement requires distinct provenance and synthetic qualification.

## Transport and capture

- Compact tests used bounded pasted UTF-8 text. DeepSeek automatically turned
  the paste into an attachment; its Paste original control restored text.
- Chrome's extension could not guarantee hidden tabs. After a reconnect,
  fresh agent tabs recovered page control. Minimization is an operator-based
  precaution, not enforced concealment.
- The user enabled extension file-URL access. Claude's file chooser then
  accepted a TXT path, but the application subsequently reported Upload failed.
  An earlier paste had also become a pasted-text attachment. This intended
  trial is an imperfect transport attempt, not a clean text-capacity test.
- Claude's first response used the response Copy button and a private file;
  clipboard history was not verified. Subsequent captures read response-only
  rendered DOM into private files, excluding UI controls and separate thought
  panels. No real study content was involved.
- Blinding across notifications, previews, and exceptions remains unverified.
  These records do not authorize semantic execution.

## Provenance and preservation

The private run is `callosum-adjudication-synthetic-haagd234` under the user's
local temporary directory, outside Dropbox. It contains generated packets,
append-only amendments, individual captures, provenance, and a hash-linked
journal. Raw relay files are in the separate temporary directory
`callosum-capability-relay-Fpng4x`. Raw responses are not embedded in this report.

Displayed model labels are recorded as observed, not inferred from the planned
roster: Claude Opus 5 High; Gemini Pro without a visible version; Microsoft
Copilot Smart; GitHub Copilot Auto with claude-haiku-4.5 shown in its response
retry control; Kimi K3 High. ChatGPT's final trial showed 5.6 Sol in its retry
menu. Grok and DeepSeek exact model identities remain unverified; Z.ai's page
title mentioned GLM-5.3-Flash but selected-model identity remains unverified.
No role assignment or scientific roster freeze occurred.

The GitHub Copilot roster addition has synthetic test coverage. The package's
61 tests and Ruff checks pass. The first test invocation encountered an existing
pytest temporary-directory permission issue; a fresh task-specific directory
resolved it. No production changes, staging, or commits were performed.
