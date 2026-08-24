# Security Audit — Calibrated Status Timing

## Scope

This feature adds controlled job-stage metadata to the existing local Status response and stores bounded timing
receipts in browser-local storage. It adds no endpoint, provider call, model call, dependency, authentication rule,
or server-side file-write path.

## Threat review

- **Input validation / resource caps:** stage keys, labels, and timing identities originate only in server-owned call
  sites. The Status schema types all numeric fields. Browser receipt validation bounds identifiers, durations (24
  hours), per-shape history (24), and total history (200); malformed or wrong-version history is ignored.
- **Output encoding / injection:** React renders labels and timing wording as text. No receipt value becomes HTML,
  a URL, a selector, a command, or SQL.
- **Privacy / data egress:** receipts contain only a random job receipt id, controlled timing identity/stage key,
  coarse numeric workload bucket, duration, and a provider-variability boolean. Paper text, prompts, claims,
  citations, titles, authors, paths, endpoints, API keys, and credentials are not accepted or serialized. Receipts
  stay in same-origin `localStorage`; no telemetry or network transmission was added.
- **Secrets:** timing identity is built from workflow, provider family, model/wire label, execution target, and local
  model/device labels. Raw base URLs and credential identity are deliberately excluded. Recognizable private fixture
  fields are absent from serialized receipt tests.
- **SSRF / external calls / egress gate:** no URL is accepted and no provider/model/network call is made for timing.
  Existing provider egress gates and routes are unchanged.
- **File/path safety:** no server-side path is accepted or written. Browser storage access is exception-safe and the
  feature falls back to elapsed-only display if unavailable.
- **Availability / contention:** stage updates are in-memory constant-size data. UI-only stage changes deliberately
  do not wake completion long polls. The display timer runs once per second only while the Status popover is open and
  a job is running. No database write or unbounded poll was added.
- **Supply chain:** no dependency was added.

## Negative-path checks

- malformed JSON, wrong schema, and invalid receipt records fall back to empty history;
- 260 injected receipts are capped to 24 per comparable shape and 200 globally;
- sparse/configuration-mismatched history yields no estimate;
- negative display input is clamped, remaining-time wording never emits zero/negative values, and elapsed-over-range
  state becomes “Taking longer than recent runs”;
- a job carrying recognizable private title/prompt fixture fields serializes neither field into timing history;
- a UI stage transition leaves a registered completion long-poll held until terminal state.

## Residual risk

Timing duration and coarse workload shape are local behavioral metadata. They are intentionally bounded and never
egress, but a person with access to the same browser profile can inspect them, as with other local preferences.

**Security Audit: PASS**
