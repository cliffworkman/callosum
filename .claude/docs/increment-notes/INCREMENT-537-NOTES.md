# Increment 537 — bounded Mendeley API transport scaffold

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6A safe work before app registration. Adds reusable official-API transport and
records the newly proven packaged-desktop OAuth constraint. No user-facing native Mendeley feature activates.

## Evidence-driven design

Current official Mendeley documentation was re-read before code. It specifies authorization code as a
confidential-client flow: `/oauth/token` uses HTTP Basic client-id/client-secret authentication; no PKCE/public
authorization-code option is documented. Implicit flow avoids the secret but provides one-hour tokens without a
refresh protocol. Registration pins an exact redirect URI.

That means “obtain a client ID/secret” is necessary but not sufficient for Callosum. A shared secret embedded in
a distributed desktop app is not confidential, and the ordinary backend port may move if occupied. This
increment fails closed at that boundary: OAuth URL/exchange shapes are modeled and tested, but no callback,
token persistence, Settings control, or importer is published.

## Retained scaffold

`integrations/mendeley/client.py` provides:

- official fixed HTTPS authorize/token/API origins and version-1 media types;
- validated exact loopback redirect configuration and cryptographic state generation;
- bounded/sanitized authorization-code and refresh exchanges for a future defensible confidential owner;
- read-only personal `/documents?view=all`, `/folders`, `/folders/{id}/documents`, and `/files` calls;
- 500-item pages, hard page/item/body/URL/token/code caps, pagination-cycle detection, and exact resource/origin
  validation for provider-supplied next links;
- manual (never automatic) `/files/{id}` 303 handling, allowlisted to the documented
  `downloads.mendeley.com` signed-download host;
- injectable HTTP clients so every request/redirect/error contract is tested without egress.

No PDF bytes are downloaded yet. Future download must still stream into a bounded temporary file, revalidate
redirect/DNS/MIME/PDF signature/size/hash, then reuse Callosum's existing PDF ingest path.

## Verification

- Focused client/adversarial suite: **16 passed** (included in the combined run below).
- Combined client, HTTP-bounds, acquisition, and credential-store affected suite: **80 passed** in 66.07s.
- Full collection: **2616 tests** in 15.60s.
- Ruff format/check on the client and tests: passed.
- Bandit, Tach, 575-file line budget, `git diff --check`, added-line secret/private-path scan, and personal-fixture
  gitignore verification: passed.
- Final staged pre-commit passed every applicable hook: whitespace/EOF, merge markers, added-file size, Ruff
  format/check, line budget, Bandit, and Tach. Commit and remote CI follow this receipt.
- No live Mendeley request or OAuth handshake was attempted; no registered application credentials exist.

## Exact unblocker

Inspect/register the app in Mendeley's My Applications UI and obtain authoritative confirmation of a
desktop-safe public-client/PKCE option or approve a separately secured broker that owns the confidential secret.
Choose/register an exact redirect endpoint whose port Callosum can reliably own. Only then add token persistence
and an OAuth callback, run the live flow, and proceed to import mapping/PDF ingestion.

## Revert

Revert this increment. It has no schema or production behavior effect.
