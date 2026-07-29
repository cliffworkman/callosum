# Security audit — in-app feedback reporter (`/feedback*`), inc 413

**Date:** 2026-07-29
**Author:** Claude (session)
**Trigger:** New API endpoints (audit-gate criterion #1) + a new file-write path (#3) + a net-new feature
spanning 3+ files / ~300+ LOC (#5). No new dependency (#6) and no new external fetch (#2) — see below.

## What shipped

An in-app **bug report / feature request** reporter, reached from **Feedback** in the menu bar, beside Help / Settings / Status.
The user picks a kind, writes a title/description (+ steps for a bug), optionally attaches a screenshot
(browser `getDisplayMedia`, or paste/drag-drop), reviews the diagnostics that would be attached, and saves.

- **Backend:** `app/backend/feedback/` (`bundle.py` — render + write + `mailto:`; `diagnostics.py` — the
  attached facts + client-half sanitizer; `destination.py` — the address store) and
  `app/backend/api/routers/feedback.py` (`GET`/`PUT /feedback/config`, `POST /feedback`), mounted in `app.py`.
- **Frontend:** `app/frontend/js/18b_feedback.jsx` (`FeedbackModal`, `FeedbackDestinationRow`,
  `FeedbackSettings`), the `FeedbackMenuItem` rendered by `MenuBar`
  (`04b_workspaces.jsx`), a Feedback card in `35_settings.jsx`, styles in `styles.css`.

`POST /feedback` writes `<settings dir>/feedback/<UTC stamp>_<kind>_<slug>/report.md` (+ `screenshot.png|jpg`)
and returns the paths, the full report text, and a **prefilled `mailto:` URL**. **The server transmits
nothing.** Sending is the user's own mail client, from a draft the user reads first.

## Threat review

| Concern | Assessment |
|---|---|
| **Data egress (invariant #3)** | **No new egress channel.** The feature adds no outbound socket of any kind — no SMTP, no HTTP POST to a collector, no telemetry beacon. `mailto:` is a URL handed to the browser, not a request the app makes; the report reaches a human only when the user presses send in their own client. Verified in the browser pass: across the whole flow the only non-loopback requests were the pre-existing React/pdf.js CDN loads — zero from `/feedback*`. The Gemini library-text gate is a separate channel, untouched. |
| **What leaves the machine, and does the user see it?** | The report body is authored by the user; the one part they didn't type is the diagnostics block, so it is (a) fetchable *before* submitting via `GET /feedback/config`, (b) rendered in the form behind "Show what's attached", (c) written verbatim into `report.md`, and (d) opt-out. Browser pass confirmed the previewed table is identical to the written one. There is exactly **one** rendering of the report — no hidden second payload. |
| **Secret handling** | The diagnostics carry **no secret**: no API key (only `key_storage: keychain\|file` and `ai_provider: <id>`), no access token, no OIDC session, no provider base URL. `test_config_diagnostics_are_previewable_and_carry_no_secrets` asserts this. The destination address is a preference, not a secret — stored in the plaintext settings file like `contact_email`, and freely returned by `GET`. |
| **Privacy of the library** | No paper title, annotation, summary, tag, or DOI can reach the report except by the user typing it. The diagnostics deliberately exclude the **DB URL/path** and the **library folder** (both carry the user's name/directory layout) — only the Alembic revision goes in. |
| **File-path safety (rule #4)** | The bundle folder name is built **server-side**: `strftime("%Y%m%d-%H%M%S")` + `bug\|feature` + `slugify(title)`, where `slugify` collapses everything outside `[a-z0-9]` to `-` and truncates to 48 chars. A client-supplied path can therefore never contribute a separator or a `..`. Every write target additionally passes `_contained(root, path)`, which resolves and asserts the result sits inside the feedback root. `test_a_hostile_title_cannot_escape_the_feedback_folder` submits `../../../../etc/passwd` and asserts the folder's parent is still the feedback root. Collisions within one second get a numeric suffix; `mkdir(exist_ok=False)` means an existing directory is never written into. |
| **Untrusted image handling (rule #4)** | The screenshot is decoded with `base64.b64decode(..., validate=True)` (a malformed payload raises → 422, never a partial write), capped at **5 MB decoded** with the encoded cap declared on the pydantic field so an oversized body is rejected at the boundary, and accepted only if its **magic bytes** are PNG or JPEG. The written filename and extension are **ours**, chosen from the magic-byte check — a client filename is never used. The bytes are written verbatim and never decoded, parsed, or rendered server-side, so there is no image-parser attack surface. Covered by `test_submit_rejects_a_screenshot_that_is_not_an_image` (3 cases), `test_submit_rejects_an_oversized_screenshot`, `test_a_jpeg_screenshot_keeps_its_own_extension`. |
| **Output encoding / injection into the report** | The report is Markdown, not HTML, and is never rendered as HTML by the app. Client diagnostic values are whitespace-collapsed (so a newline can't forge a table row) and pipe-escaped (so a `\|` can't forge a column) — `test_diagnostic_values_cannot_forge_the_report_table`. Keys are capped at 24 × 40 chars, values at 300 (`test_client_diagnostics_are_bounded`). |
| **Resource exhaustion** | Every text field is bounded by a pydantic `max_length` (title 200, body 20 000, steps 8 000, reply-to 254, screenshot ~6.7 MB encoded), so an oversized request is rejected before any work. A report bundle is therefore ≤ ~5 MB. Unbounded *accumulation* over time is a real but low-severity property (see Residual risk). |
| **SQL injection (rule #3)** | The feature writes no SQL. Its one DB touch is read-only: `MigrationContext.get_current_revision()` for the diagnostics. |
| **SSRF / external calls** | None. `mailto:` is validated only as "contains `@`" and is **not** fetched by the server; it is URL-encoded via `urllib.parse.quote` into the returned string, which the browser hands to the OS mail handler. A hostile address could at worst pre-address the user's own draft — visible to the user before they send. |
| **Auth / access control** | Both `/feedback` routes sit behind the existing `AccessControlMiddleware`: with Remote access on they require the bearer token like every other endpoint (they were **not** added to `_EXEMPT_PATHS` or `_RECOVERY_PATHS`). Under `CALLOSUM_READ_ONLY=1` the `PUT`/`POST` are 403'd by the method gate — accepted (the read-only companion is a reader, and the desktop instance is where reports are filed). |
| **Supply chain** | **No new dependency.** Backend: stdlib only (`base64`, `binascii`, `re`, `dataclasses`, `datetime`, `pathlib`, `urllib.parse`, `platform`, `sys`, `os`) plus FastAPI/pydantic/SQLAlchemy already present. Frontend: no library — screen capture is the browser's own `getDisplayMedia`, and downscaling/encoding is `<canvas>`. A DOM-to-image CDN library was explicitly declined for this reason (and because it misrenders the pdf.js canvas). |
| **Screen-capture consent** | Capture is never automatic: it requires a click, and the browser then shows its own surface picker — consent is the platform's, not ours. Tracks are stopped in a `finally`, so the capture indicator is always released. The modal hides itself during capture (visual only). |

## Negative-path checks (concrete results)

`python -m pytest tests/test_feedback.py -q` → **18 passed**.

- `../../../../etc/passwd` as the title → **201**, folder is `…/feedback/<stamp>_bug_etc-passwd`, parent is the
  feedback root, no `..` in the name; nothing written outside.
- Base64 of `b"not a png at all"` behind an `image/png` data-URL prefix → **422** (magic-byte check), no file.
- A `text/html` data URL → **422**. Non-base64 garbage → **422**.
- 5 MB + 1 byte screenshot → **422**, nothing written.
- 60 client-diagnostic keys × 500 chars → **201**, exactly 24 rows kept, each ≤ 300 chars.
- `kind: "nonsense"` → **422** (`Literal["bug","feature"]`). Whitespace-only title or empty body → **422**.
- Destination `"nope"` (no `@`) → **422**; `""` → cleared.
- Diagnostic value `"a | b\n| forged | row |"` → the forged row does not appear; the pipes are escaped.
- No destination set → **201**, `mailto_url: null`, `report.md` still on disk (a report is never discarded
  because it had nowhere to go).
- Browser pass (headless Chromium, egress unset): 0 console errors, 0 page errors, 0 non-loopback requests
  attributable to the feature, previewed diagnostics == written diagnostics, no mobile horizontal overflow.

## Residual risk

1. **Unbounded accumulation.** Bundles are never pruned; a user who files hundreds of reports with screenshots
   accumulates disk under `~/.callosum/feedback/`. Bounded per report (≤ ~5 MB), visible (the folder path is
   shown in the UI and in Settings), and user-deletable. **Accepted** for a local single-user app; a retention
   sweep belongs with the `.local/`/backup lifecycle if it ever matters.
2. **The user can type anything into their own report.** Free-text fields can contain whatever the user
   chooses, including something sensitive. Mitigated by the flow itself: the report is written locally, shown
   in full ("What was written"), and opened as an editable draft before it is ever sent. **Accepted** — this is
   the user's own composition, and the design keeps them the last party to see it.

## Verdict

**Security Audit: PASS**
