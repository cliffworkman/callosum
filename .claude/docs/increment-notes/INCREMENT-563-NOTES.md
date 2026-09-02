# Increment 563 Notes — OpenAlex transport, cache, and snapshot hardening

## Implemented

- All production OpenAlex HTTP paths now share bounded response reads, a current Callosum user agent, optional
  environment-only API-key support, and narrow retry handling for rate limits, transient server responses, and
  transport failures. Secrets are never written into cache request receipts.
- OpenAlex cache reads use a 24-hour freshness bound and honor explicit expiry. Refreshing a row now refreshes its
  timestamp; transient error rows are retried instead of replayed indefinitely. Cache identities now include
  output-affecting sample/cap parameters.
- Citation-count refresh explicitly bypasses the cached work record and performs provider I/O outside the SQLite
  writer transaction. Citation-equity, overlooked-work, and Feed refreshes likewise avoid holding writer locks
  while polling external services.
- Gap Finder, My Publications citation gaps, and the overlooked-work lens use strict provider reads. A timeout,
  malformed response, or partial scan aborts replacement and preserves the last known-good snapshot.
- Failed Feed polls no longer advance `last_polled_at`. Editing the My Publications identity invalidates the
  cached OpenAlex author id instead of silently retaining a match made for the previous identity.
- Title-only work resolution verifies the returned title before attaching OpenAlex metadata. Collection parsing
  and abstract reconstruction are type-checked and bounded, and partial citing-work pagination is not cached as a
  complete response.
- User-facing Citation concentration privacy copy now accurately names the public identifiers sent to OpenAlex.

## Scientific and product boundary

An empty result is publishable only after a complete bounded provider interaction. An unavailable or malformed
response is operational failure, not negative scientific evidence. No change turns OpenAlex coverage, citation
counts, gaps, or feed silence into a certificate of absence or quality.

## Manual verification script

1. Refresh a populated gap/overlooked snapshot while offline; confirm the job reports an error and the old cards
   remain.
2. Refresh a Feed subscription while offline; confirm its prior items and last-successful-poll time remain.
3. Change the saved My Publications name or ORCID; confirm Callosum requires a fresh OpenAlex resolution.
4. Refresh Citation counts twice after changing an injected/provider count; confirm the second refresh is fresh.

## Validation during development

- OpenAlex-focused regression matrix: **298 passed, 1 new-test assertion corrected** (the implementation reached
  the stricter character cap before the word cap).
- Corrected affected rerun: **66 passed**.
- Destructive snapshot/profile regressions: **119 passed** across the two focused runs.
- Ruff check/format and the line-budget gate passed for touched code. Full validation is recorded in the final
  hand-off after the residual call-site sweep.
