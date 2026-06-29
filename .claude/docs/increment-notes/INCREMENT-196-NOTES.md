# Increment 196 — accounts SP2: more login methods (email/password + Google), method-agnostic

Adds **email/password + Google** sign-in to the optional account (after SP1 inc 194 + the superuser/runbook inc 195).
Because callosum is **one OIDC client of the account platform (Authentik)**, the login *methods* are **Authentik
connectors** — so the functional part is platform config (the runbook), and callosum needs only a small refinement: a
**method-agnostic** sign-in entry + graceful handling of a **non-ORCID** login.

## Implemented

### A — runbook (the functional part)
- **`ops/accounts-authentik-setup.md`** gained an **"Adding more login methods (SP2)"** section: add **Google** as a
  social source in Authentik (Google Cloud OAuth client → Authentik Google source) + enable **email/password**
  (Authentik's built-in identity + an enrollment flow); ensure the callosum provider includes the `profile`+`email`
  scopes so the token carries `name`/`email`. These appear on **Authentik's** login page — **no callosum change**;
  callosum's single "Sign in" entry handles whatever method is used.

### B — callosum refinement (small; on the SP1 seam)
- **`app/backend/api/auth/oidc.py`** — `Identity.email` (default None) + `_claims_to_identity` reads `claims["email"]`.
- **`app/backend/api/auth/router.py`** — store `email` in the session; **populate My-Pubs only when `identity.orcid`
  is present** (was `if identity.orcid or identity.display_name:` → `if identity.orcid:`) — a Google/email login sets
  the account identity but must not overwrite the My-Pubs profile from a non-authoritative display name.
- **`app/backend/app_settings.py`** — `oauth_account_status()` adds `email`.
- **`app/backend/api/routers/settings.py`** — `AccountStatus.email: str | None`.
- **`app/frontend/js/35_settings.jsx`** — the button is now **"Sign in"** (was "Sign in with ORCID"); method-agnostic
  copy ("ORCID, Google, or email — chosen on the next page; ORCID also pre-fills My Publications"); the signed-in line
  shows `display_name` **or** `email`.
- help corpus account section updated to "ORCID, Google, or email."

## Key technical detail

The login *method* is chosen on **Authentik's** page, not callosum's — the clean OIDC-client model (per-method
buttons in callosum were rejected: they'd couple callosum to Authentik connector slugs). callosum gets a token back
whichever method was used: an **ORCID** login carries the `orcid` claim → it alone pre-fills My-Pubs; a **Google/email**
login carries `name`/`email` → the account shows the identity, My-Pubs is untouched, and (no ORCID) the superuser flag
is False. `email` is the signed-in user's own identity shown locally — additive, non-secret, never a token.

## Manual verification script

The live Google/email round-trip is the maintainer's check (per `ops/accounts-authentik-setup.md` §SP2: add the
Google source / email enrollment in Authentik). The non-ORCID flow is hermetically tested; the unconfigured UI was
headed-re-verified (no regression).

## Gates

- **pytest 670 passed, 1 skipped** (+1 `tests/test_auth_oidc.py` — a non-ORCID login signs in, `orcid` None, `email`
  shown, `is_superuser` False, **My-Pubs profile untouched**; the file is now 15 tests). `ruff` clean.
- **QA (rule #10):** the button relabel is text in the already-claimed `35_settings.jsx`; `account.email` is an
  additive field → **no new route**; surface **132/132 API + 661/661 FE, 0 uncovered**.
- **Audit:** an **addendum** to `…/security-audits/2026-06-29_orcid-account.md` PASS (still identity-only — `email` is
  the user's own identity shown locally, not a token/library; platform-config login methods; no new endpoint/egress).
- **Principles → non-triggering** (more login methods, same opt-in/identity-only posture). Frontend rebuilt; no
  migration. Headed driver re-verified (unconfigured render unchanged).

## NEXT

The maintainer's live Google/email standup (Authentik connectors, runbook). Then **SP3 opt-in sync** — the only step
that moves library data off-machine — its own design + a heavy Principles/A-A pass. **SP4 sharing** later. Superuser
*capabilities* remain parked (backlog).
