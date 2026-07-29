# Increment 413 — friendly classification for real provider HTTP errors (401/403/429/5xx)

## Implemented

A direct follow-up question after inc 411 (the missing-API-key pre-check): are there other places an end user
could hit the same *kind* of raw-provider-error dump, and is it worth the same fix? Investigation found one:
inc 411's pre-check in `complete()` only catches a **missing** key — it can't help a **wrong or expired** key,
a rate limit, or a provider outage, since those all require the network call to actually happen before the
provider tells you something's wrong. All of them funnel through `_post()`'s single `httpx.HTTPStatusError`
handler, which previously wrapped *any* status code the same way: `f"HTTP {status}: {body}"` — the same raw
JSON dump Bella's original report showed, just for a different trigger. Confirmed two live call sites that
would have shown this verbatim: `workbench.py`'s extraction-assist endpoint and `settings.py`'s `test-key`.

Fix, in the same "fix once at the shared seam" spirit as inc 411: a new `_friendly_status_prefix(status)` in
`app/backend/llm/providers.py` classifies exactly three well-understood cases — **401/403** → "Authentication
failed for this provider — check the saved API key in Settings."; **429** → "Rate limited by the provider —
wait a moment and try again."; **5xx** → "The provider is temporarily unavailable — try again shortly." Every
other status keeps today's plain `HTTP {code}: {body}` format unchanged — we only guess a friendly
interpretation for codes we're confident about, never for an arbitrary custom provider's unknown error shape
(a deliberate limit, not an oversight: overclaiming an interpretation for an unclassified error would be its
own dishonesty).

The raw detail is never hidden, only reordered: the friendly text leads, followed by `(HTTP {code}: {body})`
appended after it — so a user gets an actionable first line, and anyone who wants the underlying provider
response (a self-hoster debugging a custom endpoint, for instance) still has it. This matches invariant #4
(evidence always shown) — the fix is about ordering/legibility, not suppression.

## Key technical detail

The classification lives entirely inside `_post()`'s existing `except httpx.HTTPStatusError` branch — no new
call sites, no router changes, no new exception type. Every wire format (`messages`/`chat_completions`/
`responses`) routes through this one function, so a wrong key on ANY provider (builtin or custom) gets the
same friendly lead-in automatically.

## Manual verification

- New tests in `tests/test_providers.py` use a small `_FakeErrorResp`/`_FakeErrorClient` pair whose
  `raise_for_status()` raises a real `httpx.HTTPStatusError` (the existing `_FakeResp`/`_FakeClient` always
  succeed, so a new fake was needed to actually exercise this branch) — one per classified status (401, 429,
  503) plus one asserting an unclassified status (400) is left in its original plain format, unchanged.
- `pytest tests/test_providers.py -q` → **19 passed** (4 new).
- Full suite: `pytest -n auto -q` — see `changes.md`'s entry for this date for the confirmed count.

## Pytest

`tests/test_providers.py`: 19 passed.
