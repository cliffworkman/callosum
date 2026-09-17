# Frozen frontier execution — procedural pause 004

Mechanical metadata only. This report contains no semantic labels, reasons,
candidate identities, configuration comparisons, agreement counts, rankings,
or selection implications. Study 1 remains open; no interstudy analysis occurred.

199 of 273 packets have recorded dispositions, covering 398 of 546 planned
rater-observations. These include 50 technical missing observations. Another
148 observations remain unclosed. Recorded coverage includes technical failures;
it is not a claim that every recorded packet contains a model judgment.

| Surface | Recorded packets | Recorded cells | Execution state |
| --- | ---: | ---: | --- |
| Gemini | 24/39 | 48/78 | Pro quota limit before packet 25 |
| Grok | 28/39 | 56/78 | Rate limit; capture failures on packets 26–28 |
| Microsoft Copilot | 9/39 | 18/78 | Unqualified direct-text route for packet 10 |
| DeepSeek | 39/39 | 78/78 | Complete, including any technical dispositions |
| Kimi | 21/39 | 42/78 | Packet 22 submission unconfirmed |
| Z.ai | 39/39 | 78/78 | Complete, including any technical dispositions |
| Alternate ChatGPT | 39/39 | 78/78 | Complete, including any technical dispositions |

The four remaining blockers are separate:

- **Copilot:** The authorized 9,761-byte synthetic direct-text test passed strict
  matching and the existing empty-line adapter on one submission. Its expanded
  bound was logged before resuming packet 9. Packet 10 then remained direct text
  at 10,189 bytes, above that bound. It was never submitted. Another transport
  qualification/amendment is required before sending it; the original automatic
  TXT attachment route did not activate for this packet.
- **Kimi:** Packet 22's Enter invocation returned, but subsequent reconciliation
  found no conversation or final body. The frozen wrapper and attachment remain
  in the composer. Its intent and UI evidence are preserved. No second send was
  attempted. An explicit retry amendment and fresh reconciliation are required
  before another Send/Enter action.
- **Gemini:** Before packet 25, the model menu displayed a Pro limit with reset
  text “Sep 12, 11:11 AM.” The UI timezone was not independently confirmed.
  The automatically selected fallback was not used for an experimental packet.
  Resume requires availability and exact-model verification on the qualified
  account. No alternate model or account was substituted.
- **Grok:** A rate-limit notice was confirmed in non-message UI on packet 28.
  Read-only reconciliation showed the stored text for packets 26–28 came from
  user-message containers, with no assistant final body present. These six cells
  already had zero accepted semantic rows. An append-only correction classifies
  them as terminal technical capture/service failures, retaining original raw
  captures and invalid-normalization records. The precise service onset for
  packets 26–27 is not independently established. Remaining packets were paused;
  none of the affected packets was regenerated.

Two capture infrastructure corrections are documented privately:

- Grok packet 11 was initially captured while its final container was empty.
  Its later nonempty final body was captured from the same conversation without
  another model call. Original empty bytes and completion metadata remain intact.
  Ingestion accepts that appended recovery only when original hashes match, the
  original is empty, packet/conversation/send count match, final-boundary flags
  hold, and recovered byte count/hash match. Synthetic validation accepted the
  intended recovery and rejected nine adversarial conditions. The frozen parser
  was not changed. Future empty DOM containers remain pending.
- The Grok 26–28 boundary defect is a capture failure, not evidence about
  representation fidelity or rater semantic competence. The broad DOM selector
  must distinguish assistant final content from user bubbles and recognize
  service-limit UI before any authorized Grok resumption. No content repair or
  retrospective selection of favorable answers is permitted.

One additional model Send attempt was used in the entire recorded execution:
the explicitly authorized Gemini packet-4 retry. Its prior failure, reconciliation,
amendment, second intent, and response remain preserved. No automatic model retry,
regeneration, semantic nudge, account replacement, or role reassignment occurred.
Mechanical paste restoration and read-only conversation recovery did not create
additional model submissions.

Verification at this pause:

- All 308 bound artifacts and all 273 frozen packet bindings: PASS.
- Raw-response hashes, unique packet coverage, and journal chain: PASS.
- Frozen normalization reproduced for every one of the 199 recorded packets.
- Empty-capture recovery and Grok technical-correction evidence: verified.
- One unresolved submission remains: Kimi packet 22. No other response is in flight.
- A private hash receipt binds 2,493 execution, journal, response, qualification,
  amendment, correction, and exposure artifacts.
- Corpus SHA256: `6c40112f2253248f000c045325f267993992a673004ff7b4344844855d19e021`.
- Freeze A SHA256: `1836253a4c8632e36cabdab5f3c4c17168a33af4cfb1a0ca529a4d6b1a425437`.
- Pause artifact receipt SHA256: `5a9d6e7a2b20bcc846dc39ed31365a8683b3e8bc70508a4081c70a59a8e962f2`.

The earlier potential conversation-title exposure remains marked
HUMAN_BLINDING_COMPROMISED; actual reading is unknown. No additional semantic
response content was echoed during this continuation. Browser minimization is
an operational, user-reported safeguard, not guaranteed technical concealment.

Original observations, sealed mapping, archival adjudication materials, Freeze A,
scientific prompts, roles, parser, and reason limits remain unchanged. Changes
were limited to non-production capture infrastructure and procedural records.
No Study 2 design, human queue, Freeze B, production change, staging, or commit
occurred. This component study has not nominated or frozen R_0_6.

FRONTIER STUDY PAUSED — Copilot transport qualification, Kimi retry authorization,
and Gemini/Grok availability and capture checks remain necessary.
