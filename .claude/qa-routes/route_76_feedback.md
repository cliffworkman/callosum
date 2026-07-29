<!-- qa-coverage
api: /feedback*
fe: 18b_feedback.jsx
-->

# ROUTE 76 — In-app feedback (bug report / feature request)

**Tier:** 1 local-stateful
**Goal:** Exhaust the **Feedback** reporter — both report kinds, the screenshot attach paths, the diagnostics
preview + opt-out, the destination address (blank by default, settable in the modal and in Settings), and
the saved-bundle result state — while proving the feature adds **no egress**: the app writes files and
composes a `mailto:` URL, and never transmits the report itself.

## Environment (every route is self-contained — assume a cold agent)

You are a meticulous QA tester for **callosum**, a local-first, single-user, AI-assisted reference
manager for scholarly PDFs. Stand up a clean instance and drive it in a real browser:

1. From the repo root, create a throwaway DB and seed it (mirror `tests/e2e/test_smoke.py`):
   - `python -m alembic upgrade head` against a temp `sqlite:///` set in `CALLOSUM_DB_URL`, then seed
     via `tests.api_helpers._seed_library`. (`tools/qa/_qa_serve.py` does spin-up + seed + free-port +
     teardown; call it if present.)
   - **Keep `CALLOSUM_ALLOW_DATA_EGRESS` UNSET** — this route is not a Tier-2 egress route.
   - **Set `CALLOSUM_SETTINGS_PATH`** to a throwaway path. Reports are written to
     `<settings dir>/feedback/`, so this keeps the run out of the real `~/.callosum/`.
2. Start `uvicorn app.backend.api.app:app` on a free `127.0.0.1` port; wait for `/health` 200.
3. Open `/` in headless Chromium via Playwright. Register listeners BEFORE navigating:
   - `page.on("console", …)` — collect every `type=="error"`.
   - `page.on("pageerror", …)` — collect every uncaught error.
   - `page.on("request", …)` — collect every outbound URL (for the egress assertion).

## Seed contract (what `_seed_library` actually contains — do not assume more)

Match your expectations to the seed; over-assuming its contents produces false-positive findings.

- **3 papers**: **Facial Anomaly Perception** (4 attachment rows whose files are **NOT on disk**, so its
  `/pdf` honestly 404s — the correct coordinate-honesty `null` case, not a bug); **Signal Detection
  Theory** (metadata-only); and **Renderable Seed Paper** (the one paper backed by a real 2-page PDF).
- **1 axis**, **1 tag**. **No** summaries, wanted items, watched folders, or feedback reports.
- The feedback folder does **not** exist until the first report is saved.

## Reporting format (every issue)

1. **Severity:** Critical / High / Medium / Low / Visual (see `.claude/QA-POLICY.md` rubric)
2. **Location:** exact route surface id + URL/component
3. **Steps to reproduce:** numbered, replayable
4. **Expected vs Actual:** include exact error text / console errors / what the screenshot shows
5. **Evidence:** screenshot filename under `screenshots/`

## Standing assertions (apply to EVERY step)

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed through the UI is a bug.
- **Egress gate.** Any outbound request to a non-loopback host is **Critical** — the reporter must not
  transmit anything. (A `mailto:` navigation is a client hand-off, not a request; it must never appear
  as an HTTP request.)
- **Signal not verdict / inspectability.** The diagnostics shown in the form must be **byte-identical**
  to what lands in `report.md`. A report that attaches something the form didn't show is **Critical**.

## Route-specific assertions (this feature's honesty contract)

- **Nothing is sent by callosum.** `POST /feedback` writes files and returns a URL. Assert the process
  opened no socket to a mail/HTTP service, and that the response contains no "sent" claim.
- **The destination is the user's.** With no address configured, `GET /feedback/config` returns
  `destination_email: ""` and a submit returns `mailto_url: null` — and the report is **still saved**.
  A report that is silently discarded when unaddressed is **High**.
- **No secrets, no library content, no paths in diagnostics.** The diagnostics table must not contain an
  API key, the DB URL/path, the library folder, or any paper title. Any leak is **Critical**.
- **The screenshot is the user's choice.** No capture may start without an explicit click (the
  `getDisplayMedia` picker is the browser's own consent surface); "Remove" must actually drop it from
  the submitted payload.

## Adversarial checklist (the curious, motivated end user)

- paste ~50KB into Title / What happened / Steps; submit empty and whitespace-only (expect a blocked
  submit, not a 500)
- `POST /feedback` directly with: `screenshot` = a base64 HTML document; `screenshot` = a >5 MB blob;
  `title` = `../../../../etc/passwd`; `client_diagnostics` = 100 keys of 5 KB each; `kind` = `"exploit"`
  → every one must be a clean 422 (or a sanitized 201 for the title), never a write outside
  `<settings dir>/feedback/`
- double-click **Save report**; close the modal mid-submit; submit two identical reports in one second
  (expect two distinct folders)
- set the destination to `nope` (no `@`) → 422 with a legible message; set it to blank → cleared
- resize to `375x812`, hard refresh — no horizontal overflow; the ✉ must not collide with ⚙/?

## Steps

1. Baseline screenshot of the library. Confirm the menu bar's right-aligned utilities read
   **Help · Settings · Status · Feedback**, and that **Feedback** opens a MODAL over the current workspace
   rather than navigating to a new one (the reported screen must stay visible behind it).
2. Open the reporter. Assert the modal traps Escape (closes) and that **Something's broken** is selected
   by default with **Steps to reproduce** visible; switch to **I'd like a feature** and assert the Steps
   field disappears and the body label changes.
3. Diagnostics: click **Show what's attached**; screenshot the table. Record it verbatim — you will diff
   it against `report.md` in step 6.
4. Screenshot panel: paste an image from the clipboard (`page.evaluate` a synthetic paste of a small PNG)
   → assert a preview renders; click **Remove** → assert the preview goes and the submitted payload has
   `screenshot: null`. (Headless Chromium cannot drive the `getDisplayMedia` picker; assert only that
   **Take screenshot** is enabled and that dismissing capture surfaces a legible message rather than a
   console error.)
5. Submit with no destination set: fill Title + What happened, **Save report**. Assert the result state
   shows the report path, **Open email draft** is ABSENT, the inline destination row is offered, and
   `report.md` exists on disk.
6. Read `report.md` from the feedback folder. Diff its Diagnostics table against what step 3 displayed —
   they must match. Assert no key/DB path/paper title appears.
7. Set the destination inline (`maintainer@example.org`), submit a second report **with** diagnostics
   opted OUT. Assert: `mailto_url` is present, starts with `mailto:maintainer%40example.org`, and the
   new `report.md` has **no** `## Diagnostics` section.
8. Open **Settings → Feedback**. Assert the address shows the value set in step 7 (one source of truth),
   that the reports folder path is displayed, and that clearing it there empties it in the modal too.
9. Run the adversarial checklist against `POST /feedback` and the form.
10. Mobile viewport pass. On a phone width the menu bar collapses to the workspace `<select>`; confirm
   **Feedback** is still reachable and the modal fits without horizontal overflow.

## Pass criteria

- Every declared surface exercised and reachable.
- 0 console errors / 0 page errors.
- No unexpected 4xx/5xx; every malformed payload is a clean 422.
- **Zero outbound requests to any non-loopback host across the whole route.**
- Diagnostics shown == diagnostics written; nothing sensitive in either.
- No report is ever lost because no destination was set.
- Mobile viewport: no horizontal overflow.

## Deposit (REQUIRED — this is how the supervisor knows you finished)

Write your consolidated, severity-ordered report to:

    .claude/qa-inbox/<RUN_ID>/route_76_feedback.md

and put all screenshots under:

    .claude/qa-inbox/<RUN_ID>/screenshots/

`<RUN_ID>` is provided in the dispatch prompt. Lead the report with Critical/High; collapse the rest.
