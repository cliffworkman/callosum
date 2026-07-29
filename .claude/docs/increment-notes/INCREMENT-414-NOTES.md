# Increment 414 — three OA-acquisition bug fixes (temp-dir crash, WAF-blocked downloads, bulk-error detail)

## Implemented

A fourth real bug report from the same external adopter (Isabella Bobrow): "Acquire OA copy" repeatedly failed,
and a bulk "Wanted" re-check run showed many rows failing the same way with no useful detail. Investigation
(an Explore agent + direct file reads, all confirmed against the actual current source before any fix was
written) found three independent, distinct root causes, all inside `app/backend/acquisition/`:

**1. A hard crash on the packaged macOS app (`OSError: [Errno 30] Read-only file system`), every attempt, not
occasional.** `download_oa_pdf`'s temp-staging directory was `PROJECT_ROOT / ".local" / "acquire-tmp"`, where
`PROJECT_ROOT = Path(__file__).resolve().parents[3]`. When Tauri packages the app, the whole Python source
tree ships as a bundled resource — so `PROJECT_ROOT` resolves to `Contents/Resources/callosum-src/`, read-only
once code-signed. This raised a bare, unwrapped `OSError`, violating the function's own documented promise
("any failure raises `OaFetchError`... leaves no temp file behind"). Fixed with a new `_acquire_temp_dir()`:
`CALLOSUM_OA_TEMP_DIR` env override, else `Path(tempfile.gettempdir()) / "callosum-acquire-tmp"` — mirroring
`app_settings.settings_path()`'s stronger pattern (never `__file__`-relative), not `library_dir()`'s more
fragile env-var-with-PROJECT_ROOT-fallback shape (which only works today because `backend.rs` happens to set
`CALLOSUM_LIBRARY_DIR`). Confirmed no Rust changes are needed: `backend.rs`'s spawned Python child inherits the
full parent environment (no `.env_clear()`), so `tempfile.gettempdir()` resolves correctly without any wiring.
The `mkdir`/`write_bytes` pair is now wrapped in `try/except OSError` → re-raised as `OaFetchError` — defense in
depth beyond the root-cause fix, closing the docstring's promise for any *future* write failure too.

**2. Downloads from nature.com (and likely other WAF-protected publishers) failing with "downloaded bytes are
not a PDF" or "HTTP 403".** `_httpx_pdf_fetcher` — the one step that streams the actual PDF bytes — sent no
headers at all, unlike every other external fetcher in this codebase (the Crossref/OpenAlex adapters both
identify with `"Callosum/0.1 (local-first reference manager)[; mailto:...]"`). A publisher WAF that tolerates
an identified client but blocks httpx's bare default UA would produce exactly the reported symptoms: an HTML
interstitial (200, not `%PDF-`) or an outright 403. Fixed with a new `_pdf_fetch_headers()` sending the same
honest identity via a new `CALLOSUM_OA_MAILTO` env var (kept separate from the Crossref/OpenAlex mailto vars
since this fetch hits arbitrary publisher/repository hosts, not those APIs) — **identifying politely, never
browser-UA spoofing or paywall circumvention.** This reduces, not eliminates, such failures; some publishers
will still legitimately decline automated fetches, and that limitation is now stated in the help docs rather
than implied away.

**3. The bulk Wanted list showing uniform `"error: OaFetchError"` for what could be several different
underlying causes.** `wanted.py`'s exception handler discarded the message, keeping only the class name —
every one of `OaFetchError`'s 8 differently-worded raise sites (oversize / not-a-PDF / corrupt / zero-page /
bad-redirect / any HTTP-non-200 / redirect-loop) collapsed to the same indistinguishable string, even though
the single-paper acquire endpoint already preserved the full message. Fixed: `f"error: {type(exc).__name__}:
{exc}"[:100]` — capped to `wanted_items.last_result`'s declared column width (confirmed via the schema:
`String(100)`, not DB-enforced by SQLite but the column's own stated contract; confirmed via the frontend,
`app/frontend/js/26_wanted.jsx`'s `.wanted-row-meta` has no truncation styling, so a longer message displays
safely with no frontend change needed).

Also added, in the same conversation: a Help-doc bullet under Acquire OA copy's "Outcomes" naming the
previously-unstated third outcome (a download can fail, not just succeed or find nothing), and a
`CALLOSUM_OA_MAILTO`/`CALLOSUM_OA_TEMP_DIR` pair added to `.env.example`.

## Key technical detail

Every fix was verified against the actual current file contents (via Explore + direct reads) before being
written, not assumed from a plausible-sounding description — e.g., `resolved_mailto`'s exact signature
(`stored_contact_email() or os.environ.get(env_var)`) and `backend.rs`'s actual spawn call (no `.env_clear()`)
were both confirmed by reading the real source before the plan finalized on "pure Python fix, no Rust change."

`_httpx_pdf_fetcher` gained an optional keyword-only `client: httpx.Client | None = None` param (mirroring the
existing injectable-client precedent in `app/backend/citations/style_fetch.py`) purely for test injection via
`httpx.MockTransport` — the `PdfFetcher` Protocol and `download_oa_pdf`'s call site are unaffected, so every
existing injected-lambda test in `test_acquisition.py` needed zero changes.

## Manual verification

- `pytest tests/test_acquisition.py tests/test_wanted.py -q` → **37 passed** (8 new: 3 temp-dir tests, 3
  header tests, 2 wanted-message-preservation tests — all following each file's existing injection patterns).
- Full suite: `pytest -n auto -q` → **1695 passed, 1 skipped** (up from 1687 post-inc-413; +8 new here).
- `ruff format` + `ruff check` on all four touched files: clean.
- Manual, can't be fully scripted: a real acquire attempt against a live nature.com-hosted OA-asserted DOI
  (confirms the header fix actually changes real-world publisher behavior) is still owed — the hermetic suite
  proves the header is sent and the logic is otherwise unchanged, not that any specific publisher's WAF now
  admits the request. Bug 1 (the packaged-app crash) similarly can only be *fully* confirmed by a real macOS
  desktop-shell build; the new temp-dir regression test is the strongest available proof without one.
- Security audit: no new stub — a dated addendum was appended to the existing
  `.claude/security-audits/2026-06-20_oa-acquisition.md` (still PASS; this is the same download path already
  covered there, no new endpoint/destination/dependency).

## Pytest

`tests/test_acquisition.py` + `tests/test_wanted.py`: 37 passed.
