# Security audit — global AI/progress Status navigation, inc 436

**Date:** 2026-08-01  
**Trigger:** broadened cross-feature status metadata and client tracking around egress-capable operations.

## Surface reviewed

The existing `/status/jobs*` API now supplies server-owned destinations and compute-kind labels for every backend job
family. A frontend-only registry records synchronous provider/local-AI requests and unowned progress indicators. No
new endpoint, network request, provider invocation, persistence table, file access, credential path, or dependency was
added.

## Findings

| Concern | Assessment |
|---|---|
| Result/content disclosure | `StatusJob` still has no `result` field. The client tracker receives only method/path to match an allowlisted route and never stores the request body or response. Prompts, passages, notes, provider output, and document content do not enter either status channel. |
| Navigation as an exfiltration channel | Backend destinations come from `JOB_NAV_DEFAULTS`. `_bounded_nav` accepts only positive integer `paper_id`/`summary_id` and a capped positive-integer `paper_ids` list from a job; it discards URLs, paths, free text, secrets, booleans, and attempts to override workspace/tab/modal tokens. The client uses fixed route descriptors and a central dispatcher, never arbitrary URLs or callbacks. |
| Egress posture | Tracking wraps existing calls but initiates none. Provider operations retain their existing consent gate; installed/loopback AI retains its no-egress behavior. `compute_kind` is display metadata only. |
| Cross-user/auth exposure | Backend routes retain the existing access-control middleware. Client-only rows exist solely in the current renderer's memory and expire/dismiss locally. |
| Resource exhaustion | Backend aggregation remains bounded by in-memory jobs. Finished client receipts expire lazily after one hour; listeners are removed on unmount. `paper_ids` serialization is capped at 500. |
| Injection | Navigation values are never rendered as HTML and never interpreted as URLs. The dispatcher compares bounded tokens and invokes existing state transitions only. No SQL, shell, or filesystem sink was added. |
| Duplicate/misleading state | `managedBy` establishes one owner for an operation. Determinate progress requires real totals; unknown progress remains indeterminate and explicitly withholds completion/ETA. |

## Negative paths and evidence

- A job attempts to publish `workspace=settings`, `file:///secret`, and private free text: Status retains the
  server-owned Synthesize destination and the valid paper id only.
- Every application `JobStore` must be a subset of `JOB_NAV_DEFAULTS`; a new unregistered store fails the structural
  test rather than shipping a dead navigation row.
- The browser test holds `/help/ask` open after leaving Help. Its Status receipt exposes only the label,
  `Provider AI`, running state, and fixed Help destination; no request text or response is surfaced.
- Existing dismiss/clear authorization and `job.result` exclusion tests remain in force.

## Verdict

**PASS.** Inc 436 broadens visibility without broadening egress or content exposure, and tightens the formerly
convention-only navigation dictionary into a bounded serialization contract.
