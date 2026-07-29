# Increment 413 — in-app feedback reporter (bug report / feature request)

## Implemented

A **Feedback** item in the menu bar's right-aligned utilities (beside Help / Settings / Status) opens a
reporter: pick a kind, write it up, attach a screenshot, review the diagnostics, save. The report is
assembled **locally** into a bundle and handed to the user's own mail client as a prefilled draft.

**Backend (new subsystem `app/backend/feedback/`)**

- `bundle.py` (209) — `render_report` (one Markdown rendering, reused as the file, the API response, and the
  mail body), `write_bundle` (timestamped folder under the feedback root), `decode_screenshot` (strict base64
  + 5 MB cap + PNG/JPEG magic-byte check), `build_mailto_url`, `slugify`, `_contained`.
- `diagnostics.py` (88) — `server_diagnostics` (versions/posture only) + `clean_client_diagnostics` (bounds
  the browser-supplied half).
- `destination.py` (50) — the destination address, **blank by default**, stored in the settings file via
  `app_settings.load_settings`/`save_settings` with a `CALLOSUM_FEEDBACK_EMAIL` env fallback.
- `app/backend/api/routers/feedback.py` (147) — `GET`/`PUT /feedback/config`, `POST /feedback`; mounted in
  `app.py` beside `help.router`.

**Frontend**

- `app/frontend/js/18b_feedback.jsx` (NEW, 345) — `FeedbackMenuItem` (the entry point), `FeedbackModal`,
  `FeedbackDestinationRow` (rendered in **both** the modal and Settings, so the two can't drift),
  `FeedbackSettings`, `captureFeedbackScreenshot`, `readFeedbackImageFile`, `feedbackClientDiagnostics`.
- `04b_workspaces.jsx` — `<FeedbackMenuItem/>` in **both** MenuBar branches; `35_settings.jsx` — a "Feedback"
  `SettingsCard`; `styles.css` — the `.fb-*` block + two mobile-menubar rules.

**Docs/QA:** `.claude/qa-routes/route_76_feedback.md`, the
`.claude/security-audits/2026-07-29_feedback-reporter.md` audit (**PASS**), a `reporting-a-bug` help-corpus
section, `tests/test_feedback.py` (18 tests).

## Key technical detail

**The feature adds no egress, and that is the whole design.** `POST /feedback` writes files and returns a
`mailto:` URL; the *browser* hands that to the OS mail handler. There is no SMTP client, no collector, no
beacon. The consequence the user feels: the report is composed where they can read it and sent by them, not
by us — which is why the destination ships **blank** (nobody is pre-addressed) and why an unset address still
saves the report instead of discarding it.

The diagnostics block is the one part of a report the user didn't type, so it is held to the inspectability
commitment: `GET /feedback/config` returns **exactly** what a submit would attach, the form shows it behind
"Show what's attached", it is written verbatim into `report.md`, and it is opt-out. There is a single
`render_report` call — no second, hidden payload can exist.

**Why a modal and not a utility workspace.** Help and Settings became workspaces in inc 280; Feedback
deliberately did not. A bug report is *about the screen you are looking at* — navigating to a Feedback
workspace would replace that screen, discarding the context being reported and putting the reporter itself
into any screenshot taken afterwards. So it rides the same MenuBar exception `StatusMenu` does (inc 406) and
overlays instead. It is rendered in **both** MenuBar branches: the mobile branch drops the utility buttons
(Help/Settings survive there only because they're registered workspaces in the `<select>`), which would have
left the reporter unreachable at phone width — the one width where "something is broken and I can't get on
with it" is most likely.

Two boundary details worth remembering:

- **The bundle path is entirely server-built** — `%Y%m%d-%H%M%S` + `bug|feature` + `slugify(title)` (everything
  outside `[a-z0-9]` collapses to `-`), then `_contained()` re-asserts the resolved path is under the feedback
  root. A title of `../../../../etc/passwd` yields `…/feedback/<stamp>_bug_etc-passwd`.
- **The screenshot's extension is ours, from our magic-byte check** — never a client filename. The bytes are
  written verbatim and never parsed server-side, so there is no image-decoder surface.

**Screen capture:** `getDisplayMedia({preferCurrentTab: true})` → `<video>` → `<canvas>` (downscaled to 1600px,
PNG, falling back to JPEG only if it would exceed the 5 MB cap). Chosen over a DOM-to-image CDN library because
it adds no dependency **and** because it captures the pdf.js `<canvas>` correctly — a DOM renderer would show a
blank page for the exact bug a user is most likely to report. The modal hides itself during capture. Paste and
drag-drop route through the same encoder.

**Line budget:** the destination accessors deliberately live in `feedback/destination.py` rather than
`app_settings.py` (552 lines) — the feature stays self-contained and that file stays clear of the cap.

## Open question for the maintainer (desktop shell)

The shell (Tauri v2) has no `mailto:` handling that I could find, and its capability set is `core:default`
with no opener plugin. In a plain browser the draft opens correctly (verified); **inside the packaged desktop
app the "Open email draft" button may do nothing**. The feature degrades honestly either way — the report is
already on disk, and *Copy report* / *Copy folder path* are always offered — but if the shell needs an
opener permission or an `on_navigation` hook for `mailto:`, that's a one-line follow-up I couldn't verify
without building the shell. Flagged rather than assumed.

## Manual verification script

Reproduced headlessly (Playwright, Chromium, egress unset, `CALLOSUM_SETTINGS_PATH` at a temp dir); the same
steps work by hand.

1. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`, open `/`.
2. The menu bar's utilities read **Help · Settings · Status · Feedback**. Click **Feedback** → the reporter
   opens **over** the current workspace (the reported screen stays visible behind it), on *Something's broken*
   with a Steps field; switch to *I'd like a feature* → Steps goes and the body label changes.
3. **Show what's attached** → the diagnostics table renders. Note it.
4. Paste an image (⌘V) → a preview appears; **Remove** drops it.
5. Fill Title + What happened → **Save report**. With no destination set: the result shows the report path,
   **no** "Open email draft", and an inline destination row. `report.md` exists; its Diagnostics table matches
   step 3 exactly; `screenshot.png` sits beside it.
6. Set the address inline → submit a second report with diagnostics **unticked** → **Open email draft** now
   appears (`mailto:maintainer%40example.org?subject=%5Bcallosum%5D%20%5BFeature%20request%5D…`) and the new
   `report.md` has no Diagnostics section.
7. **Settings → Feedback** shows the same address and the reports folder.
8. 375×812: the mobile menu bar shows the workspace `<select>` **and** Feedback; the modal fits, no
   horizontal overflow.

**Result:** 0 console errors, 0 page errors; the only non-loopback requests in the whole run were the
pre-existing React CDN loads — **none** from `/feedback*`.

*(Harness note, not a product finding: `text=`-style selectors in the driver intermittently clicked through to
a reload. An isolating probe drove every real sequence — open/close, submit, set-destination-then-close — and
recorded **zero** navigations and zero page errors, so the reporter itself never reloads the page. Cost
~an hour; recorded so the next person doesn't re-chase it.)*

## Pytest

`pytest --ignore=tests/test_mcp_server.py` → **1689 passed, 1 skipped** (18 new).
Line budget clean (423 files ≤ 600); ruff (pinned 0.9.6) clean; QA surface map: `/feedback*` covered by route
76. (The check still reports 7 uncovered API surfaces — `/status/jobs*`, `/papers/{id}/grim-checks`,
`/manuscripts/{id}/funding-runs|journal-runs` — all pre-existing on `main`, none of them this increment's.)
