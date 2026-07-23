# Security audit — LibreOffice refresh progress and cancellation (2026-07-23)

## Scope

Increment 360 adds Writer status-bar progress, a temporary Escape-key listener, cooperative cancellation
checkpoints, and a render-input consistency check to the existing LibreOffice citation refresh. It adds no API
endpoint, dependency, network host, secret, persistence schema, or file path.

## Threat review

- **Egress / SSRF:** the same configured loopback Callosum render endpoint is used. Progress and cancellation
  make no request and introduce no retry, background request, or external host.
- **Input / parsing:** progress values derive from bounded recognized citation counts. Status labels are fixed
  application text. The consistency signature reads existing recognized ReferenceMark names/ids/anchor strings;
  it does not parse or execute their visible text.
- **Mutation authority:** cancellation cannot add a mutation path. It raises through the existing transaction's
  exception branch, which closes the UndoManager group, undoes it, and verifies the pre-mutation mark snapshot.
- **Concurrency / stale data:** yielding to Writer may admit document events. The complete ordered render-input
  signature is therefore re-read after the HTTP render and compared before mutation. A mismatch aborts instead
  of applying stale output.
- **Keyboard scope:** the Toolkit key handler exists only for a visible large refresh, consumes only the
  published Escape key code, and is removed in `finally` on success, cancellation, or failure.
- **Resource use:** progress is O(1) state. Existing document scans and bounded render limits remain unchanged.
  There is no thread, timer, polling loop, queue, or retained document content.
- **Secrets / filesystem / supply chain:** no secret or filesystem access is added. No dependency or package
  entry changes; the extension version changes only.

## Negative-path proof

- A small refresh touches no UNO progress service and preserves the prior path.
- An injected Escape cancellation after three real Writer field rewrites restores every field exactly and leaves
  both pre-existing pending flags set.
- A simulated citation edit during the real render is retained; the stale response raises before write-back.
- Progress cleanup removes the key handler and ends the indicator after normal, cancelled, and failing paths.
- Failure to acquire native status/toolkit services degrades to no visible progress, not a failed refresh.

## Result

**Security Audit: PASS**
