# Increment 605 — refresh the mirror after restoring confirmation history

## Implemented

Only `app/backend/capture/provisional_review.py` changes production behavior: pass the existing
Library root through the four `_reattach_user_actions` calls, then invoke the existing sidecar
refresh after `run_write` commits. Production diff: 9 additions / 5 deletions in one file.

## Key technical detail

`attempt_attach_to_paper` serializes `_Evidence`, which has no user-actions field, and refreshes
the sidecar. Its review caller then restored actions only to the database. The mirror remained
stale while marked `ok`. The same restoration helper covers unresolved confirmation, successful
or blocked admission, and retry before/after attachment. Refresh belongs after its committed
merge, not in fixture-specific code. The existing writer retains atomic replacement and nonfatal
OSError handling; the DB stays authoritative. Automatic promotion already refreshes its final
evidence without this restoration helper and is unchanged.

## Verification / targeted replay

Before the production edit, the extended confirmation/review suite produced **7 failed, 50 passed**,
all seven at full sidecar/DB evidence equality. They cover manual/candidate actions, ambiguous
identities, unresolved lookup, attachment conflict and retry. Green: **90 focused + 180 broader
passed, 2 POSIX-only Windows skips**. No acceptance claim derives from fake-model local tests.

Use a NEW isolated replay directory, exact committed source archive, unchanged actual Windows
managed interpreter and real installed MiniLM model. Preserve the original acceptance and failed
run. Require provisional/preview zero canonical state; one paper/one intact Ioannidis PDF;
122 current chunk vectors + one metadata vector (finite/nonzero/readable, 384D); complete matching
DB/sidecar evidence; idempotency without recomputation; and a separate backend-process reopen.
Scripted production-route confirmation is explicitly synthetic, never a new human/Chrome click.
The new external QA receipt is the authority for real-runtime PASS/FAIL.

## Experience, principles, latency and lineage

Backend-only consistency repair; no new control, API contract, candidate policy or UX flow.
The curator's durable confirmation remains inspectable in both stores. Principles 1/3/5/8 and
the human-owned resolution in Example 2 apply: deriving a mirror from the committed DB is aligned;
inventing history or suppressing the failed provenance check would be the misaligned shortcut.
No inference, provider, polling or worker ownership changes. One existing local refresh follows
each action restoration. Report actual backend request-to-response time separately from UI latency.

Cliff supplied physical evidence, executed the failed replay, and authorized this repair. Lucien
scoped the minimal shared repair and fresh acceptance. Cody/ChatGPT traced the stale mirror and
implemented its regression coverage. Prior FAIL/PARTIAL receipts remain historical evidence.
