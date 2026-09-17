# Claude expanded-envelope retry — mechanical contract failure

2026-09-11 local / 2026-09-12 UTC. **PRE-FREEZE-A HARDENING BLOCKED.**

The user authorized continuation following the service-limit stop and reported
replenished Claude usage credits. This retry was recorded separately from the
original quota-blocked attempt. The frozen v2 adapter, v1 adapter and expanded
packet were verified unchanged before the retry. The perfect expected response
still passed v2. Prior validation remains 138 passing synthetic tests; no
response-contingent adapter changes were made.

In a fresh conversation, Opus 4.8 was explicitly selected and the control
confirmed **Opus 4.8 High**. Claude restored two prior unsent draft attachments;
they were removed before sending. The final gate verified exactly one complete
attachment matching the frozen packet and the exact fixed wrapper, totaling
**20,434 UTF-8 bytes**. Provenance and the input gate were preserved before
submission. There was **one Send message invocation in this retry**, no nudge,
regeneration, model switch, or second attempt.

The response completed without a service error and was captured privately from
`.font-claude-response .prose`, after Stop response disappeared and Copy controls
appeared. Capture size: **2,559 UTF-8 bytes**. Capture SHA256:
`9c599d9b897bfd7aa360c019612e8eb6264a1d5f6b225c8de9b0769753d5e330`.

## Exact mechanical finding

- Strict receipt-only check: `FAIL_ROWS`.
- Frozen v2 narrow adapter: `FAIL_AMBIGUOUS_RECEIPT`.
- Both complete expected rows appear exactly once, in required order, at
  zero-based lines 5 and 6.
- An additional nonqualifying line at zero-based index 8 (589 UTF-8 bytes)
  matches v2's existing receipt-marker guard. It contains no pipe, expected
  candidate ID, or matching 16-character receipt fragment. The marker guard
  alone is sufficient to reject it under the frozen contract.

No response text is reproduced here. This is not missingness or mutation of the
two required rows. It is failure of the frozen rule forbidding ambiguous
receipt-like material outside them. The guard's match does not establish that
the surrounding prose semantically contradicts the rows; it is a conservative
syntactic exclusion. It cannot be relaxed after this answer to declare a pass.
The 1,216-byte expected receipt contract excludes surrounding prose; the larger
raw capture is preserved without truncation.

## Preservation and stop

Private hash-linked store:
`C:/Users/cliff/AppData/Local/Temp/callosum-adjudication-synthetic-uba_hyc4`.
It links the prior quota failure and preserves the unchanged code/packet,
retry amendment, model/input gates, submission intent, completed raw response,
completion metadata, strict/v2 scores, content-free diagnostics and stop status.
Relay: `callosum-claude-retry-relay-itYxyc` under the same Temp root.

The earlier smaller-envelope qualification, original strict failure, v1/v2
tests and quota failure remain unchanged. **Claude has not qualified at the
expanded envelope.** No configuration was silently excluded and no role was
reassigned. The eight-rater assignment remains a proposal, not a freeze.

Operational blinding followed the standing dedicated minimized Chrome / no
investigator inspection arrangement, with direct private DOM capture and no
clipboard or response echo. Minimization is an operational condition, not a
browser-API guarantee. No exposure was reported.

Stop without another call or adapter change. No real q_AIB records, Arm-1/Arm-2
outputs or sealed mapping were accessed. No frontier semantic screening,
Freeze A, human queue, production edits, staging or commits occurred.
