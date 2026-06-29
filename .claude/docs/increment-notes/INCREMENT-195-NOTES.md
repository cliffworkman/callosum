# Increment 195 — superuser role (verified-ORCID flag) + the Authentik standup runbook

Two approved follow-ons to accounts SP1 (inc 194), in sequence: (A) the maintainer runbook to stand up the account
platform so live sign-in works, and (B) the superuser role the maintainer asked for ("register my ORCID as a
superuser — build out what that means later").

## Implemented

### A — Authentik standup runbook (docs only)
- **`ops/accounts-authentik-setup.md`** — the concrete, step-by-step maintainer runbook: host Authentik behind TLS
  (not HostGator shared hosting, inc 169) → register an ORCID API client → add ORCID as a generic OIDC source →
  **emit the ORCID iD as an `orcid` claim** (the crucial step — callosum reads `CALLOSUM_OIDC_CLAIM_ORCID`) → create
  the callosum **public/PKCE** provider with the loopback redirect → set `CALLOSUM_OIDC_*` in `.env` → live-verify the
  sign-in. Referenced from the README security note + the design spec's operational section.

### B — superuser role (verified-ORCID allowlist)
- **`app/backend/app_settings.py`** — `_normalize_orcid` (bare iD from a `https://orcid.org/…` URL; uppercases the
  checksum X), `superuser_orcids()` (parse `CALLOSUM_SUPERUSER_ORCIDS`, comma/semicolon-split → normalized set),
  `is_superuser_orcid(orcid)`. `oauth_account_status()` now derives **`is_superuser`** (signed-in AND verified orcid
  ∈ allowlist; else False).
- **`routers/settings.py`** — `AccountStatus.is_superuser: bool = False` (on the `account` block).
- **`app/frontend/js/35_settings.jsx`** — the signed-in identity line appends "· superuser" when `acct.is_superuser`.
- **`.env`** (gitignored) — `CALLOSUM_SUPERUSER_ORCIDS=0000-0002-2206-0325` (the maintainer's ORCID).

## Key technical detail

The superuser flag is **verified, not self-asserted**: it keys off the **verified `orcid` id-token claim** on the
signed-in session (not request data → a caller can't claim it via the API), matched against the env allowlist. The
allowlist is **env config** in the gitignored `.env` — the personal ORCID is **never hardcoded** in the public repo
(the code only reads `CALLOSUM_SUPERUSER_ORCIDS`). Matching is normalization-insensitive (URL vs bare; X case). **What
being a superuser gates is deferred** — for now it's just an honest flag (backlog: the *capabilities* are a later
decision).

## Manual verification script

The signed-in "· superuser" display needs the live platform (the maintainer's check per `ops/accounts-authentik-
setup.md`): with `CALLOSUM_SUPERUSER_ORCIDS` containing your ORCID, sign in → Account shows "· superuser",
`GET /settings` `account.is_superuser:true`. The flag logic is hermetically tested; the unconfigured UI was headed-
re-verified (no regression, `.local/visual/drive_inc194_account.py`).

## Gates

- **pytest 669 passed, 1 skipped** (+3 superuser tests in `tests/test_auth_oidc.py`, now 13: allowlisted→true,
  non-allowlisted→false, `_normalize_orcid`/unset-env). `ruff check .` + `ruff format --check .` clean.
- **QA (rule #10):** an additive `account.is_superuser` field + one FE text span in the already-claimed
  `35_settings.jsx` → **no new route**; surface **132/132 API + 661/661 FE, 0 uncovered**.
- **Audit:** an **addendum** to `…/security-audits/2026-06-29_orcid-account.md` PASS (verified-identity-keyed,
  env-config, not self-asserted, no new surface/egress/migration).
- **Principles → A-A:** an authorization flag derived from a verified identity — non-accusatory, no opaque score; the
  capabilities are deferred (the flag gates nothing yet).
- Frontend rebuilt; no migration. (Also corrected inc-194's "+12" test-count references to the actual **+10**.)

## NEXT

Superuser **capabilities** (what the flag gates) — a decision when a concrete superuser-only need arises. The
maintainer's live sign-in via the runbook (stand up Authentik) unblocks the end-to-end ORCID round-trip. Then SP2
(email/Google = platform-config) → SP3 opt-in **sync** (the library-egress step — its own design + heavy A-A pass) →
SP4 sharing.
