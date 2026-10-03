# Capture visibility: real-Mac finding and local correction

## Observed acceptance result

Cliff performed a real Chrome capture against the packaged Intel Mac `b0d98e63` app.
The Import Queue was still absent until he reloaded after approximately **5–30 seconds**.
This is a user-reported interval, not a measured 30-second timeout. After identity confirmation,
the paper appeared in Library without another reload. Backend evidence records one promoted
paper, one canonical attachment, 96 chunks and 96 embeddings; the PDF checksum is preserved
and the queue copy is gone. The captured DOI is `10.1371/journal.pone.0000308`.

The extension directory recovery inspection found the original directory already populated
and matching the tested source. It did not establish deletion. The real capture occurred after
that inspection; the earlier no-click checkpoint is not a capture result. Development identity
remains `joepcflpilfcdllmbfihgcihaloahcdd`; no native-host or manifest changes accompany this fix.

The app used the locally repaired Intel managed runtime with cryptography 48.0.1. This capture
does not prove a pristine published runtime works. Runtime portability preparation remains a
separate local commit and a separate publication gate.

## Cause and correction

The queue chip was fetched on mount and after in-app queue actions, with no capture-completion
invalidation reaching an already-open app. Merely rechecking on focus would miss the case where
the user returns before upload completes. Cliff requires quick feedback so users do not assume
capture failed.

Capture commits now advance an opaque app-scoped revision. A bounded async request wakes on
change; the frontend retrieves authoritative queue state and increments the existing Library
refresh counter. Unchanged 20-second timeouts renew the subscription without fetching queue
state. A transient error retries after 1.2 seconds; focus reconnects a suspended subscription.
The server caps observers at 64 and holds no database connection while waiting. State stays
authoritative in the existing database, not in the notification. No fixed completion polling
interval, new trust boundary, identity rule, or admission rule is introduced.

## Local validation and limits

- Focused capture, queue, observer and frontend assembly suite: 177 passed before adding the
  two explicit auth-gate cases. Final observer plus access-control suite: 19 passed (overlaps
  the earlier observer tests; these counts must not be summed as unique tests).
- Frontend notification and queue tests: 26 passed.
- Full assembled frontend in headless Chromium against a fresh isolated backend: one test,
  three distinct synthetic capture uploads, no focus/reload, no page errors.
- Upload-response-to-visible queue: **395.0, 340.9, 230.6 ms**.
- Upload-start-to-visible queue: **1107.8, 568.8, 406.8 ms**, measured separately.
- Ruff, line budget, Bandit, Tach, website coverage and all 452 API surface mappings passed.

These are local Windows/Chromium measurements using synthetic PDFs, a fake metadata resolver,
and fake embeddings. They do not establish real extension latency or packaged macOS acceptance.
An earlier test-authoring attempt used a nonexistent selector; correcting it produced the passing
receipt without a corresponding product change. QA route 27 requires the actual user path on the
next build, including returning before upload completes. Reusing the promoted PDF requires
accounting for deduplication; do not erase the current session to manufacture a fresh result.

## Experience and documentation review

Grounded in Cliff's actual corpus-building task: after Capture reports success, he needs a visible
place to review the paper immediately, and should not have to discover a reload workaround.
The fix addresses that finding and preserves explicit identity confirmation. Screenshot inspection
shows the existing Import Queue control and count; no visual redesign or automatic confirmation.
This is the primary agent's review plus direct user evidence, not an independent persona-agent pass.
Website `cap-import` still describes Zotero/folder/citation-file import; this internal notification
change requires no new public capability claim. Help has no browser-capture section to revise;
public packaged-capture documentation remains gated on completed acceptance.

## Lineage and disposition

Cliff supplied the real capture observations, timing range, and quick-feedback requirement.
Earlier Claude/ChatGPT work and review remain credited in the existing chronological record.
Codex implemented and tested this narrow completion-notification correction. This local receipt
does not claim fresh GitHub CI, a new Mac build, or a second real-Chrome run. No runtime publication,
release, tag, merge, ready-for-review transition, or source push is authorized by this record.
