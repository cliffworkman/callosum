# Security audit — in-app feedback relay and Slack publisher, inc 439

**Date:** 2026-08-02
**Trigger:** new explicit client egress, local API endpoint, public hosted ingress, and Slack integration.

## Surface and trust boundaries reviewed

- `app/frontend/js/18b_feedback.jsx`: user-authored report, exact JSON preview, explicit submit/copy/retry.
- `app/backend/feedback/` + local `/feedback/*`: shared strict schema, body cap, fixed hosted destination, bounded HTTP.
- `feedback_relay/`: public ingress, optional existing OIDC validation, source-IP/account limiting, publisher protocol.
- `feedback_relay/slack.py`: server-only webhook configuration and plain-text Slack formatting.
- Tauri staging/config, environment examples, frontend artifact, logging, test mocks, CI/static security activation.

The client is not trusted. A token embedded in a distributed app would not authenticate it, so none was added. A
valid existing OIDC access token, when the hosted verifier is configured, improves the rate-limit key only;
anonymous submissions remain possible and IP-limited. The Slack publisher, webhook, channel, and formatter are a
separate hosted trust boundary.

## Findings and controls

| Concern | Assessment/control |
|---|---|
| Webhook in source/client/frontend/Tauri | No real webhook exists. The only client setting is the fixed relay URL. Slack configuration/imports live only under `feedback_relay/`, which Tauri staging does not copy. Example/test URLs are conspicuously fake. |
| Secret/error leakage | Neither API returns provider bodies, exception text, headers, configuration, workspace/channel, or webhook. Slack errors are mapped to safe categories. Logging uses report ID/schema/type/outcome/timing only and deliberately omits exception traceback at this boundary. |
| Raw body/request logging | Application code never logs the decoded/raw body. Tests attach directly to both loggers and assert description/contact sentinels are absent. Operations docs require proxy/APM body capture to be disabled for this route. |
| Schema smuggling | Both boundaries stream-cap at 32 KiB before JSON decode, require `application/json`, require schema 1, use a discriminated strict Pydantic union with `extra=forbid`, bounded strings/lists, strict enums/ID/time, and no arbitrary nested fields. |
| Slack mention/format injection | User text goes only into Block Kit `plain_text`. `@channel`, `@here`, and `@everyone` gain a zero-width separator; Slack user/group/special/link constructs use visible non-executable angle punctuation. The client cannot supply blocks. |
| Arbitrary channel/webhook/API invocation | Publisher and webhook are server-constructed. Schema rejects channel, webhook, blocks, and unknown fields. Webhook config accepts only HTTPS `hooks.slack.com`/`hooks.slack-gov.com` `/services/…`; redirects are off. |
| SSRF/relay substitution | Desktop relay URL comes only from local process configuration, never the report/UI. It requires HTTPS except loopback test/dev, rejects credentials/fragments, and uses redirects-off HTTP. |
| Resource exhaustion | 32 KiB body; per-field/list limits; five-per-ten-minute default account/IP sliding window; 8 s desktop-relay and 5 s Slack timeouts; at most 50 Slack blocks; no attachments/storage/background retry. |
| Rate-limit bypass assumptions | OIDC is optional, not claimed as mandatory auth. IP limits are per process; multi-worker deployments must provide a shared edge limiter. Proxy headers are ignored unless explicitly trusted behind an overwriting proxy. NAT sharing/multi-IP spam remain documented residual risks. |
| Contact retention | Contact is optional and invalid without explicit permission. No local/hosted feedback database or outbox exists; failed text remains only in the mounted dialog and disappears when it closes. Slack receives contact only when permitted. |
| Scholarly/local diagnostic disclosure | Payload has no PDF, extracted text, citation/reference, library/WIP title, folder/path, DB row, key/token/env, clipboard/history, prompt/response, log/stack, attachment, or machine-ID field. UI states exclusions before submit; tests assert no such automatic keys. |
| Report identity/tracking | UUID4-based random ID is per report, non-sequential, and shown in preview. No installation/device identifier is read or reused. |
| Retry/duplicate publication | Submit disables while in flight. No automatic/durable retry exists. A transport ambiguity can still mean Slack accepted just before a timeout; the stable report ID makes a user retry recognizable but Slack webhooks provide no idempotency key. |
| Cross-site/browser access | Browser calls same-origin local API; it never calls the hosted relay or Slack. Existing local API access-control middleware still applies. Hosted relay exposes only health and one report POST. |

## Static security activation

The staged Bandit trigger fired. Bandit 1.9.4 now runs in CI and pre-commit against all Python runtime/service code.
The activation baseline records 73 pre-existing findings: 57 low, 16 medium, zero high. They are existing deliberate
subprocess wrappers, bounded XML readers, allowlisted/parameterized dynamic SQL, hardcoded non-secret sentinels, and
best-effort exception paths. The new feedback/local-relay/hosted-relay code has zero findings. The committed baseline
makes any new finding fail the ratchet; it does not claim the baseline items were fixed.

## Negative-path evidence

- Valid bug/feature, malformed/unknown/unsupported/oversized/wrong-content-type, contact consent, Unicode/newlines,
  random ID, timeout/rejection/exception, rate-limit/account/IP, and no-body-log tests use only fake publishers.
- Slack mock-transport tests inspect outbound JSON and prove mass/entity/group/link control syntax is absent while
  ordinary punctuation/Unicode survives; Slack response bodies never enter exceptions/responses.
- The in-process vertical test runs local API → fixed HTTP client → hosted relay → fake publisher.
- Chromium holds the first request pending to prove duplicate-submit prevention, returns 503 to prove preservation and
  explicit retry, compares both request bodies exactly, submits feature mode, tests disabled state, Escape, and focus.
- Bandit ratchet passes after baseline creation. Focused feedback/security tests are 42/42; all 1830 root tests pass
  in bounded filename partitions after monolithic Windows runs exceeded their process limits; all 10 Chromium routes
  pass. Strict QA coverage is 354/354 API and 1573/1573 frontend. Runtime dependency audit reports no vulnerabilities;
  the dev-only accepted pytest advisory remains documented.
- `git diff --check` passes. Targeted scans found webhook URL syntax only in the fake server example/mock fixtures;
  a 9-test static boundary suite scans the assembled frontend, frontend sources, Tauri Rust/config, staging manifest,
  and runtime imports and proves no Slack webhook setting or URL prefix enters distributed client inputs.

## Residual risks

Anonymous distributed clients imply unavoidable spam risk; IP limiting is bypassable with multiple IPs and can
over-limit users behind NAT. The in-memory limiter requires one worker or a shared ingress limiter. Webhook delivery
has no idempotency primitive, so retry after an ambiguous timeout may duplicate a Slack report. Hosted reverse
proxy/APM configuration remains operationally responsible for not capturing request bodies or auth headers.

## Verdict

**PASS.** The feature adds one explicit, inspectable, bounded egress path; Slack authority remains server-only; both
boundaries validate; publication is rate-limited and fail-closed; no scholarly diagnostics are collected; and the
remaining abuse/delivery risks are bounded and documented without claiming client authentication.
