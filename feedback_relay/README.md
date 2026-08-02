# Callosum feedback relay

This separately deployed service backs Callosum's **Feedback** dialog. The desktop sends a versioned report to this
relay; the relay validates it again, rate-limits the caller, and publishes through a generic `FeedbackPublisher`.
This increment provides only the Slack incoming-webhook publisher. GitHub issues, Slack bots, interactive messages,
message mutation, and bidirectional sync are not built.

The `feedback_relay/` package is not copied into the Tauri sidecar staging tree. The Slack webhook is a hosted-service
secret and must never be set in a desktop environment, `.env`, Tauri config, frontend build, installer, log, or API
response.

## Configure and run

1. In Slack, create or select a Slack app, enable **Incoming Webhooks**, and add a webhook to the intended private
   channel. Slack's setup guide is <https://api.slack.com/messaging/webhooks>.
2. On the hosted relay only, set `CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL` to that generated URL. Restrict access to the
   service account/environment that runs the relay.
3. Install `feedback_relay/requirements.txt` and run one relay process behind an HTTPS reverse proxy:

   ```bash
   python -m pip install -r feedback_relay/requirements.txt
   CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL='set-in-secret-manager' \
     uvicorn feedback_relay.app:app --host 127.0.0.1 --port 8090
   ```

4. Configure the desktop/local backend with only the public HTTPS endpoint:

   ```text
   CALLOSUM_FEEDBACK_RELAY_URL=https://feedback.example.org/feedback/reports
   ```

`GET /health` returns only `configured: true|false`; it never returns a webhook, workspace, or channel. With no
webhook, publication fails closed with a safe `503`. To disable reporting completely, remove
`CALLOSUM_FEEDBACK_RELAY_URL` from the local installation; the dialog remains available for drafting/copying but its
submit action explains that publication is unavailable. To disable only publication at the service, remove the
webhook from the relay and restart it.

Use one relay worker with the built-in in-memory rate limiter. A multi-worker or multi-instance deployment must add a
shared limiter at the trusted ingress before scaling out; otherwise each process has an independent bucket. Default
limits are five reports per ten minutes per verified account or, for anonymous clients, source IP:

```text
CALLOSUM_FEEDBACK_RATE_LIMIT=5
CALLOSUM_FEEDBACK_RATE_WINDOW_SECONDS=600
```

If the existing Callosum OIDC service is configured with `CALLOSUM_FEEDBACK_OIDC_ISSUER` and
`CALLOSUM_FEEDBACK_OIDC_AUDIENCE`, a valid desktop account token gets an account-scoped bucket. Anonymous reports are
still accepted and IP-limited. No embedded desktop token is considered authentication. Enable
`CALLOSUM_FEEDBACK_TRUST_PROXY_HEADERS=1` only when a trusted reverse proxy overwrites (rather than appends untrusted
values to) `X-Forwarded-For`; otherwise the relay uses the socket peer.

## Privacy and observability

The user sees and can edit the complete JSON report before the one explicit submit action. Its only generated fields
are a random per-report ID and timestamp. The initial schema can contain the report type and user-entered report
fields, component, Callosum version, OS family/version, packaging type, and optional consented contact information.
It has no arbitrary object, attachment, log, diagnostic, Slack block, URL-destination, channel, webhook, or device-ID
field.

Callosum never automatically attaches PDF content, extracted text, citations, reference metadata, manuscript or
library titles, watched-folder names, local paths, usernames, database rows, keys/tokens, environment variables,
clipboard data, search history, prompts/responses, logs, or stack traces. There is no feedback database or durable
outbox. A failed report remains only in the open dialog for explicit retry or copy.

Default application logs include only report ID, schema, type, publication result category, provider name, status,
and timing. They do not include request bodies, descriptions, steps, contact information, headers, webhook URLs, or
Slack response bodies. Configure the reverse proxy and any APM/request-capture product not to record bodies or
authorization headers on `/feedback/reports`.

## Validation, formatting, and failure behavior

Both the local proxy and relay enforce `application/json`, a 32 KiB streaming body cap, schema version 1, strict
enums, per-field/list limits, timezone-bearing timestamps, report-ID format, contact consent, and `extra=forbid`.
The relay controls the publisher and destination. Errors use stable categories such as `invalid_report`,
`report_too_large`, `rate_limited`, `feedback_service_unavailable`, and `submission_failed`; raw provider exceptions
and Slack bodies are never returned.

Slack formatting is isolated in `feedback_relay/slack.py`. User text is placed only in Block Kit `plain_text`
objects. Mass mentions gain a zero-width separator, while Slack entity/group/link markup is changed to visible,
non-executable angle punctuation. The client cannot submit Slack blocks.

The desktop waits for the relay's confirmed `201` before showing success. A timeout, relay failure, or Slack failure
leaves all entered text in the open dialog and offers explicit retry/copy; it never silently retries.

## Webhook rotation and incident response

Create a replacement webhook for the intended private channel, update the hosted secret atomically, restart the
relay, submit a synthetic test report, then revoke the old webhook in Slack. If exposure is suspected, revoke first,
leave publication disabled until the replacement is installed, and inspect metadata-only relay access logs. Never
paste a webhook into an issue, feedback report, shell transcript, or client config.

## Testing and publisher extension

```bash
uv run pytest tests/test_feedback_domain.py tests/test_feedback_relay.py tests/test_feedback_api.py -q
CALLOSUM_RUN_E2E=1 uv run pytest tests/e2e/test_smoke.py::test_feedback_dialog_end_to_end_states -q
uv run bandit -q -c pyproject.toml -b .bandit-baseline.json -r app/backend integrations sync_server feedback_relay
```

All external Slack calls are mocked. To add a later destination, implement `FeedbackPublisher.publish(report)` and
inject it into `feedback_relay.app.create_app`; validation, rate limiting, local API behavior, UI, and error contracts
do not change. A future diagnostic attachment feature would need a separate consent step and exact-content preview;
it is deliberately not implemented here.

## Residual abuse risk

Distributed clients cannot hold a meaningful shared secret, so anonymous spam cannot be eliminated. Strict size and
schema limits, per-IP/account buckets, bounded HTTP timeouts, a fixed publisher, and a fixed Slack webhook limit its
impact. Operators should additionally use reverse-proxy request/concurrency limits and service-level monitoring.
NATs can cause unrelated users to share an IP bucket; attackers with many IPs can bypass a single-process IP limit.
