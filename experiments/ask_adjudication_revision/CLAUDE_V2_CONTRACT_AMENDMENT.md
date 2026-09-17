# Claude synthetic receipt contract v2 — before submission

2026-09-11. Explicitly authorized syntax-only correction. The mismatch was found
by testing the perfect expected output before any Claude call at the expanded
envelope. Zero submissions occurred under the incompatible contract. No semantic
result informed this amendment, and no real corpus or sealed mapping was accessed.

## Preserved v1

`receipt_adapter.py` and its existing tests remain byte-for-byte unchanged.
It continues to recognize 26-character synthetic IDs and COPY_OK rows, with
all previous exactness/rejection behavior. Previous small-envelope qualification
and strict-output failure evidence remain unchanged.

V1 source SHA256:
`d29cca948e992412ed2178050982d82b7a7beec442f4f47e550d507a0aaf3789`.

## New version, syntax only

`receipt_adapter_v2.exact_receipts_in_prose_v2` recognizes exactly 80-character
synthetic IDs (`s-` plus 78 lowercase hexadecimal characters), the literal
UNCERTAIN label, and a nonempty reason of at most 512 UTF-8 bytes. Expected rows
come from the verified unchanged ReasonEnvelope fixture and stored manifest,
never from a response. This is a known-answer copying check, not a semantic parser.

Beyond the ID/label recognition and reason-byte bound, the v1 algorithm is
preserved: UTF-8 decode, CRLF-to-LF only, full-line exact matches, all expected
rows exactly once in order, and rejection of competing receipt markers, IDs,
literal fragments, duplicate/partial/changed rows. The same narrow treatment of
surrounding prose/fences applies. No repair, inference, fuzzy match, trimming,
or substantive normalization was added.

The unchanged packet remains `reason3-409179459b78cabf944aa98a`:
20,352 packet bytes plus the 82-byte wrapper, at most 20,480 total; two whole
synthetic objects; 1,216 expected output bytes; 512 bytes per reason. Object
bounds, roster and proposed roles are unchanged.

## Validation before any submission

The perfect expanded expected output passes v2 and still fails the incompatible
v1 contract. All existing v1 tests remain. **45 v2 tests pass; 138 total synthetic
tests pass; Ruff passes.** Tests include 79/80/81-character IDs, altered IDs,
wrong labels, changed/over-budget reasons, UTF-8 byte boundaries, missing and
duplicate rows, conflicting duplicates, reorderings, partial and extra rows,
misleading embedded rows/fragments, fences/prose, LF/CRLF and invalid contracts.

Before submission, a private hash-linked record must preserve this amendment,
v1/v2 and test-source hashes, unchanged packet/expected bytes and hashes, passing
validation, and the one-submission stop rule. V2 and its dependency snapshots
remain frozen after response generation regardless of outcome.

## Authorized execution and stopping

Exactly one submission in a fresh Claude conversation with Opus 4.8 High
explicitly selected and recorded beforehand. Preserve surface, account alias,
exposed model label, transport/input gate, timestamps and URL. Maintain the
standing dedicated-minimized-Chrome/no-investigator-inspection procedure;
minimization is user-reported operational blinding, not a technical guarantee.
Capture final DOM text privately, without clipboard or response echo.

Use the frozen v2 adapter. Preserve strict scoring separately. On a mechanical
failure, preserve and stop without retry or roster redesign. On service/transport
failure, preserve and stop for authorization. No Opus 5 test. Only a pass permits
expanded-envelope qualification and hardening completion; proposed roles still
do not constitute Freeze A. Real-corpus access and semantic execution remain
separately unauthorized.
