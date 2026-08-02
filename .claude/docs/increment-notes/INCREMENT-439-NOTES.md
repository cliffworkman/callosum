# Increment 439 — explicit in-app feedback through a hosted Slack relay

## Outcome

Callosum now has a discoverable **Feedback** dialog for bug reports and feature requests. The user edits low-risk
metadata and report fields, sees the exact versioned JSON that will leave the device, and submits only by explicit
action. The desktop sends to a fixed Callosum-controlled relay, never Slack. The separately deployed relay validates,
rate-limits, neutralizes Slack controls, and publishes readable plain-text blocks through a generic publisher seam.

## Architecture and trust boundary

- `app/backend/feedback/domain.py` is the one strict schema shared by local proxy and hosted ingress.
- The local `/feedback/capability` exposes only enabled/schema/report ID/version/OS/package metadata; local
  `/feedback/reports` validates and uses a configured fixed-destination client with an 8-second timeout.
- `feedback_relay.app` repeats streaming size/schema validation, keys a conservative in-memory limiter by verified
  existing account or peer IP, and injects `FeedbackPublisher`.
- `SlackWebhookPublisher` is server-only, fixed to configured Slack webhook hosts, redirects off, 5-second timeout,
  safe failures, and Block Kit `plain_text`. GitHub and Slack-bot publishers are deliberately deferred.
- There is no migration, report database, successful-submission retention, durable outbox, attachment, automatic log
  bundle, or silent retry. Failure text remains only in the open dialog for user retry/copy.

## Privacy and UX

The dialog includes both requested modes/fields, editable app/OS/packaging/component metadata, optional consented
contact, a random per-report ID/timestamp, a persistent exact JSON preview, service-disabled state, duplicate-submit
guard, progress/Status navigation, confirmed success ID, and recoverable error/copy actions. It names what never gets
collected: PDF/extracted/citation/reference/library/WIP/path/database/secret/env/clipboard/history/prompt/log/stack or
machine identifier data. Accessible dialog semantics, focus trap/return, Escape/backdrop, labels, and mobile layout
follow the existing modal/form/button vocabulary.

## Abuse and Slack safety

Both ingress boundaries require JSON, stream-cap at 32 KiB, reject unknown fields and unsupported versions, normalize
whitespace, enforce string/list/enum/ID/time/contact-consent limits, and never accept Slack structures or destination
controls. Hosted limits default to five reports/ten minutes per verified account or anonymous IP; trusted proxy
headers are opt-in. Slack mass mentions receive a zero-width separator and entity/group/link markup is neutralized,
in addition to all user content being plain text.

## Tests and QA

Added domain, local API, hosted relay, Slack mock-transport, frontend structural, in-process vertical, and real Chromium
coverage. Route 84 specifies manual packaged/browser/mobile, privacy, abuse, malicious formatting, retry, log, and
accessibility checks. Exact final command results are appended after the full verification pass.

### Verification results

- `pytest` focused feedback/domain/local/relay/frontend/security suites: **42 passed** (serial 62.33 s; repeated with
  four-worker xdist: 42 passed in 28.92 s).
- The monolithic `pytest -n auto -q` exceeded a 10-minute process bound with no result, and `pytest -n 4 -q` exceeded
  15 minutes with no result. Neither is claimed as passed. The same complete root collection (**1830 tests**) was
  therefore run in deterministic filename partitions with four workers: A–C **398 passed**, D–F **251 passed**, G–M
  **441 passed**, N–S **585 passed**, T–Z **155 passed** — **1830/1830 passed** in total.
- `CALLOSUM_RUN_E2E=1 pytest tests/e2e -q`: **10 passed in 157.66 s**. The focused feedback browser workflow also
  passed independently in 29.09 s.
- Ruff check/format: **626 files clean**. Three cache-write warnings reported access denied under `.ruff_cache`; they
  did not affect the successful checks.
- Line budget: **465 application source files** within the 600-line cap (`40_app.jsx` is exactly 600).
- Strict QA surface map: **354/354 API** and **1573/1573 frontend** surfaces covered.
- `uv lock --check`: **161 packages resolved, lock current**. Runtime `pip-audit --strict`: **no known
  vulnerabilities**. Dev audit: the one already accepted `pytest 8.4.2 / PYSEC-2026-1845` finding (fixed by pytest
  9.0.3) remains; project policy defers that major-version toolchain migration.
- Bandit activation scan created a 73-finding reviewed baseline (57 low, 16 medium, 0 high); the baseline-ratcheted
  full runtime scan exits **0**, and the new feedback paths have **zero findings**.
- Frontend rebuilt successfully at **20,207 lines / 2,065,066 bytes**; SHA-256 was unchanged by the final rebuild,
  proving the committed generated artifact was already fresh.
- `git diff --check` passed. Targeted secret scans found Slack webhook-shaped URLs only in the conspicuously fake
  relay example and mock tests; the client/Tauri/bundle security suite (**9 passed**) proves the hosted webhook
  setting and Slack URL prefix are absent from distributed sources. Unrelated pre-existing untracked handoff/video
  files were left untouched and unstaged.

## Security/harness activation

The hosted ingress fired the staged Bandit trigger. Bandit is now a locked dev dependency and CI/pre-commit ratchet.
The reviewed activation baseline contains 73 existing findings (57 low, 16 medium, zero high); new feedback code has
zero. See `2026-08-02_feedback-relay.md` for the complete checklist, accepted baseline categories, and residual risks.

## Experience pass

- **Busy professor / first-time reporter:** “Feedback” is visible in desktop and mobile utility chrome; the two modes,
  required-field error, exact preview, truthful success ID, and retry/copy path require no deployment knowledge.
- **Research librarian / privacy-sensitive scholar:** the pre-submit notice and preview make the complete egress set
  inspectable; contact is optional/consented; there is no scholarly auto-collection, device ID, or hidden retention.
- **Methodologist / skeptical reader:** impact is explicitly reporter-assessed rather than an inferred severity,
  reproducibility stays descriptive, and no compliance/integrity/risk score is created.
- **Maintainer / relay operator:** fixed destination, safe errors/log metadata, documented rotation/disable procedure,
  mock-only tests, explicit single-worker/shared-limiter caveat, and publisher injection make operation and extension
  legible. No blocking experience issue remained after the browser and 375px QA contract review.

## Documentation

Updated the user help/layout/privacy corpus, root configuration/privacy/security guidance, environment example,
architecture/data contracts, ops index, dedicated relay setup/rotation/disable/threat-model guide, QA route, security
audit, changes log, and project briefing. GitHub issue creation and future consented diagnostic attachments are stated
as deferred.

## Rollback

Remove the Feedback launcher/dialog/styles/built artifact; local feedback router/client/schema; hosted relay package;
config/docs/tests; and Bandit activation/baseline/dependency changes, then rebuild the frontend and lockfile. There is
no schema or user-data rollback.
