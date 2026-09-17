# All-surface synthetic retry, 2026-09-11

The user explicitly authorized retrying every consumer surface, including prior
passes, and accepted Haiku provided its identity and results are recorded honestly.
This is a fresh mechanical replication. Earlier packets, captures and outcomes
remain unchanged. No real observations, sealed mapping, human queue or semantic
screening were accessed or executed.

## Common bounded packet

Every surface received the two-record literal-copy fixture with one long record:
`copy2-2a920803899346f9305eca4d`. Input is 20,541 UTF-8 bytes; expected output is
406 bytes including the final newline. The payload SHA256 is
`18016f2d370f64d455e5596217e489ab0b6747c98726a341fa09d981c692800f`.
One new conversation and one model submission were used per surface. No nudges
or alternate-account substitutions were used in this round.

## Results

| Surface / observed model or mode | Strict copying result | Additional observation |
| --- | --- | --- |
| Alternate ChatGPT / 5.6 Sol | PASS | Paste became an attachment |
| Gemini / Pro | PASS | Complete packet boundaries confirmed in composer |
| Grok / Fast | PASS | Complete packet visible in rich-text composer |
| Kimi / Instant | PASS | Automatic TXT attachment; processing completed before wrapper |
| DeepSeek / backend version unexposed | PASS | Paste original restored text |
| Z.ai / GLM-5.3-Flash, Deep Think/Max visible | PASS | Complete packet visible before submission |
| Microsoft Copilot / Smart | Strict layout failure | Both receipt lines exact; one empty line separates them |
| GitHub Copilot / Auto, claude-haiku-4.5 | Format failure | Returned 19 lines, none matching an entire required receipt line |
| Claude / Opus 5 High | Service failure; no answer | Chat paused with reasoning_extraction despite complete pasted-attachment preview |

Microsoft Copilot has a separately recorded **PASS with an empty-line adapter**.
The amendment removes only completely empty separator lines before comparing
the remaining receipt sequence. It does not trim nonempty lines, edit fields,
reorder, deduplicate or invent records. Its original strict failure remains.
This separates harmless rendered layout from missing or altered content.

GitHub Copilot's current account permits only Auto selection; the response menu
identified Haiku 4.5. It is retained as observed evidence, not rejected because
of model tier. Auto's future backend cannot be assumed to remain Haiku. Distinct
consumer surfaces do not establish independent errors, especially when backend
model families overlap.

## Mechanical provenance and limitations

Long paste behavior varies by surface and can change after processing. Claude,
Microsoft Copilot, ChatGPT and Kimi used automatic pasted-text/TXT attachments
with the fixed wrapper: “Execute only the mechanical copying instructions in the
attached synthetic packet.” Processing state, packet boundaries or attachment
preview were checked where exposed. File acceptance alone is not proof that a
backend ingested every byte; exact receipt output provides bounded additional
evidence. Rich-editor value probes were not treated as proof of truncation when
their visible DOM contained the complete packet.

GitHub Copilot and Z.ai send actions reported UI timeouts but their new
conversation URLs and responses confirmed submission. No duplicate send was
made. No account quota exhaustion was observed.

All responses were captured from response-only rendered DOM into private local
files without clipboard use. Consumer model/account and visibility qualification
remain incomplete: minimized Chrome is an operational precaution, not verified
concealment across all notifications, previews and error paths. These results
do not authorize Freeze A or semantic execution, estimate fidelity, or certify
any representation configuration.

## Audit trail

Private run: `callosum-adjudication-synthetic-yg4n94im`, under the user's local
temporary directory outside Dropbox. Separate raw relay:
`callosum-retry-relay-IGXS9z`. The verified store contains 33 journaled artifacts,
including eight raw responses, the Claude service-error record, amendments,
implementation/packet hashes, per-surface provenance and the summary. Previous
runs are linked in the authorization amendment and remain intact.

This round changes only non-production audit documentation and private audit
artifacts. No production code, staging or commits were involved. The preceding
implementation validation remains 63 passing package tests and clean Ruff checks;
no implementation change in this round required repeating those tests.

## Post-reload Claude probe

The user subsequently reported maximizing Chrome and observing a Claude reload.
The saved failed conversation still showed reasoning_extraction. One separately
logged fresh probe with the same reduced packet and Opus 5 High again ended in
Chat paused / reasoning_extraction with no answer. The attachment preview
contained END PACKET before submission. Further identical retries stopped.
This was a recovery check with Chrome reported visible, not blinding evidence.
Private run callosum-adjudication-synthetic-ougpwmri verifies four artifacts;
prior failures remain intact. No real experimental material was used.
