<!-- qa-coverage
fe: 04b_workspaces.jsx, 18b_feedback.jsx, 40_app.jsx
api: GET /feedback/capability, POST /feedback/reports
-->

# ROUTE 84 — Explicit in-app feedback to hosted relay

**Tier:** 3 external egress with fake relay/publisher; never use a real Slack workspace in QA
**Goal:** Verify the complete bug/feature workflow, exact preview, privacy boundary, failure recovery, and abuse guards.

## Environment

Use a packaged Tauri build and browser/source build. Run the local backend first without
`CALLOSUM_FEEDBACK_RELAY_URL`, then against the in-process/fake relay and fake publisher. Use synthetic text only.
Capture frontend requests, local/relay logs, console/page errors, and the fake publisher payload. Exercise desktop
and 375px mobile widths, keyboard-only navigation, an optional signed-in account, and anonymous mode.

## Steps

1. Locate **Feedback** beside Help/Settings/Status (and beside the mobile Workspace selector). Open it by keyboard;
   verify dialog labeling, initial title focus, focus containment, Escape/backdrop close, and focus restoration.
2. Inspect the privacy notice before entering data. Verify it names the exact preview and explicitly excludes PDFs,
   library/WIP/citation data, paths, logs, prompts, clipboard data, and machine identifiers.
3. Complete a bug report. Edit app version, OS, package type, component, all shared/bug fields, impact, and
   reproducibility. Verify the preview changes immediately and contains one random `fb_` ID and timestamp.
4. Enter contact text before/after toggling follow-up permission. Verify it is absent/null from the preview unless
   permission is checked; unchecking removes it from transmission without requiring contact.
5. Submit against a delayed fake relay. Verify duplicate submit is disabled, Status shows **Submitting feedback…**,
   its row returns to the still-open dialog, and no success appears before the fake publisher confirms.
6. Return a safe 503/timeout. Verify the dialog states submission was not confirmed, preserves every field, and offers
   explicit retry/copy. Verify no automatic second request and no feedback data in local storage, SQLite, or logs.
7. Retry with success. Verify the exact same preview reaches the fake publisher once, success shows only after 201,
   and the displayed report ID matches. Inspect local/relay logs for metadata only, never body/contact/token/URL.
8. Switch to Feature request. Verify bug-only fields leave the payload and capability/problem/workaround/importance
   fields appear. Exercise client required validation, then submit a valid feature report.
9. With feedback configuration absent, verify drafting/preview/copy remain usable, submit is disabled, and unrelated
   app workflows continue normally. With relay webhook absent, verify truthful unavailable failure and no fallback.
10. Send malformed JSON, wrong content type, unknown fields, bad enums/ID/schema/time, 32 KiB overflow, 13 steps,
    contact-without-permission, raw Slack blocks, channel, and webhook fields directly to local and relay APIs. Verify
    bounded stable errors and no publisher call.
11. Submit `@channel`, `@here`, `@everyone`, `<@U…>`, `<!subteam^…>`, and `<https://…|…>` in every user field. Inspect
    fake Slack JSON: all user content is `plain_text`, control forms are neutralized, ordinary Unicode remains legible,
    and the client cannot select channel/webhook/blocks.
12. Exhaust anonymous IP and verified-account buckets independently. Verify 429 + `Retry-After`; test forged proxy
    headers with trust off, and only test trusted forwarded IP after configuring an overwriting proxy.
13. Repeat at 375px and with long-but-valid Unicode/newline-heavy content. Verify no overflow, the preview is
    inspectable, controls remain reachable, and copying is an explicit user action.

## Pass criteria

Bug and feature reports are discoverable, editable, exactly previewed, explicitly submitted, truthfully confirmed,
and recoverable after failure. No scholarly/local diagnostic content is collected automatically; no report is
persisted; Slack credentials/destination never reach the desktop or response/log surface. Both API boundaries reject
malformed/oversized/control payloads, Slack formatting cannot trigger mentions or links, rate limits are real but not
misrepresented as authentication, and the fake publisher is the only destination exercised.
