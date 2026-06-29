# Design — callosum accounts: local-first + an optional, opt-in identity (backlog #15)

**Date:** 2026-06-29
**Status:** DESIGN — pending maintainer review. **No code until this spec is approved.**
**Backlog:** #15 (Account creation / login + publishing name). Supersedes the "post-V1, deferred" framing with a
concrete, invariant-preserving shape.

---

## How we got here (the decisions already made)

A short brainstorm settled the load-bearing forks before any design:

1. **What's driving OAuth?** → the maintainer wants **callosum accounts**, created **several ways** (email +
   "Sign in with ORCID" + likely "Sign in with Google"), where ORCID-login both *authenticates* and **populates
   what it can** (My Publications). So ORCID/Google are **login methods (OIDC)**, not data-connectors — this is
   callosum-as-**identity-provider**, not callosum-as-OAuth-client-to-a-service.
2. **How far toward hosted?** → **Local-first + an optional account** (the Zotero model), explicitly **not** full
   hosted multi-tenant and **not** identity-only-forever. The app stays fully local & offline with **no account**;
   signing in is **opt-in** and **additive**.
3. **Build vs. buy the auth core?** → **use a proven auth platform** (self-hostable preferred); **do not hand-roll**
   the OAuth-provider / password / session / social-connector security surface.
4. **First slice?** → **SP1 = "Sign in with ORCID" → verified My Publications, identity-only (no sync).**

This spec captures the **whole vision** + the architecture, then details **SP1** enough to plan from. Sync (SP3) and
sharing (SP4) are scoped at the section level only; each gets its own design pass when it's next.

---

## The invariant this touches — and the aligned framing

**Core invariant #3 is *local-first, egress-off by default*; the project's stated promise is "your data stays on
your machine."** Accounts unavoidably introduce a service off-127.0.0.1 that holds **PII** (emails, ORCID/Google
ids, tokens). That is an **emergent value** in A-A terms — *adopt it deliberately, don't drift into it.*

The aligned design that keeps the promise intact:

- **No account is the default.** With no account, callosum is byte-for-byte today's app: local, offline, no egress.
  The account is a capability you *add*, never a gate on the core.
- **Data minimization is structural, not a policy.** The identity service holds **identity only** — never library
  text, PDFs, notes, or axes — through SP1/SP2. Library data leaving the machine is a **separate, later, explicitly
  consented** step (SP3 sync), with its own design + Principles/A-A pass.
- **Every egress is labeled + opt-in**, consistent with the BYOK/egress-toggle posture (inc 146/168): signing in is
  an explicit action; what (if anything) syncs is a per-user choice; the README/help promise is rewritten to say
  *"local-first; account + sync are opt-in"* (honest, not silently weakened).

If any phase can't be built to honor this, that's a finding about the phase, not a reason to relax the invariant.

---

## Architecture

Two halves. Only the first lives in this repo's app; the second is a service the maintainer stands up.

### A. The local app (in-repo, what we build)
- A **client** of the identity service via standard **OIDC / OAuth2 authorization-code + PKCE**, with a **loopback
  redirect** (`http://127.0.0.1:<port>/oauth/callback`). Loopback *fits* local-first — the callback lands on the
  user's own running app; no public callback server, no inbound port.
- **Tokens stored like the BYOK keys** (`app_settings.py` keychain-or-file, inc 152): write-only over the wire,
  never logged, never returned by `GET /settings`. A new `account`/`session` block in the local settings.
- A **Settings → Account** surface: signed-out by default; "Sign in with ORCID / Google / email"; shows the signed-in
  identity + a sign-out; explains exactly what an account does and does not send.
- **My Publications integration (the SP1 payoff):** a signed-in ORCID identity makes the My-Pubs author resolution
  *authoritative* (a verified ORCID) instead of the current unauthenticated OpenAlex ORCID *guess* — and can
  pre-populate the profile (name variants, ORCID) the user otherwise types by hand (`profile_repo.py`, inc 78).

### B. The hosted identity service (NOT in-repo; the maintainer operates it)
- **This is the heaviest ~40% and it is operational, not an in-repo increment.** An always-on service off-127.0.0.1
  holding accounts + identity PII → a deploy, a domain, TLS, a small DB, and real security/legal weight. Like the
  cloudflared tunnel (inc 169): the **deploy/account is the maintainer's**; what *I* build is the app-side
  integration + the contracts + the docs.
- **Deploy-target constraint (known from inc 169):** the existing **HostGator shared hosting cannot host this** —
  jailshell reaps long-running processes, no Node, no container runtime. The identity service needs a **VPS /
  container host** (Fly.io, Railway, a small Linux VPS, etc.) **or a managed auth provider**. This must be chosen
  before SP1 can go live (it does not block writing the app-side code against the OIDC contract, which is standard).
- **Build-vs-buy = use a proven platform, self-hostable preferred.** ORCID + Google are turnkey OIDC connectors in
  every real platform; ORCID exposes OAuth2 + an OpenID-Connect endpoint, brokered as a generic OIDC/social
  connector. Candidate shortlist (final pick = an open decision below; verify ORCID OIDC discovery for the chosen
  one):
  - **Self-hostable (PII stays under the maintainer's control — fits the ethos):** Authentik (Python/Django — same
    stack as callosum), Zitadel (Go, modern DX), Ory Kratos+Hydra (API-first, more assembly), Keycloak (battle-tested
    but heavy/Java), **Supabase self-host** (Auth + Postgres + row-level security in one stack — attractive *if* SP3
    sync is likely, since it doubles as the sync backend).
  - **Managed (faster, but a third party holds identity records):** Clerk, Auth0, WorkOS, Supabase-hosted.
  - **Recommendation:** a **lightweight self-hostable** platform for SP1 (identity-only) — Authentik or Zitadel as
    front-runners; **Supabase** worth weighing if sync (SP3) is on the near horizon (one stack for auth + sync).
    *Do not hand-roll.*

---

## Sequencing (value-first, invariant-protecting)

The order is deliberate: deliver real value and prove the spine **before** anything touches the data-locality
promise. The invariant stays fully intact through SP2; SP3 is where it becomes an explicit consented opt-in.

| Phase | What | Touches data-locality? | Gate weight |
|---|---|---|---|
| **SP1** | Hosted identity spine + **Sign in with ORCID** → **verified My Publications** (identity-only, no library data on the server) | **No** | Security audit + Principles/A-A (emergent-value adoption) + README/help privacy rewrite |
| **SP2** | More login methods: **email/password**, **Google** | No | Security audit (each method) |
| **SP3** | **Opt-in, consented sync** (library/metadata across devices) | **Yes — the invariant inversion** | Heaviest Principles + A-A pass; metadata-first or **E2E-encrypted**; never silent; its own full design |
| **SP4** | **Sharing / collaboration** (share a collection) | Yes | Its own design; depends on SP3 |

SP3/SP4 are section-level scope only here; each gets a dedicated design when it's next.

---

## SP1 detail — Sign in with ORCID → verified My Publications (identity-only)

**Goal:** prove the entire architecture (a hosted identity service exists; OIDC social-login works; the local app
authenticates via the loopback flow; tokens are stored safely; the signed-in ORCID identity flows into a feature)
with **a real, shippable payoff** — and **zero library data on the server**.

### In-repo (the app side I build)
- **An OIDC client seam** (`app/backend/...` — likely `app/backend/api/auth/` + a settings block): start-auth
  (build the authorization URL + PKCE challenge), the **loopback callback handler** (`/oauth/callback`), token
  exchange, token storage (keychain/file, the inc-152 pattern), refresh, sign-out. Provider config is a **registry**
  (the proven `register()`-one-provider pattern from SourceProvider / acquisition-resolver / FeedSource) so SP2's
  Google/email are additive.
- **Settings → Account** UI (`app/frontend/js/35_settings.jsx` or a new chunk): signed-out by default; "Sign in with
  ORCID"; signed-in identity + sign-out; a clear "what this does / does not send" note.
- **My-Pubs wiring:** on sign-in, populate the inc-78 profile (verified ORCID + name) and mark authorship resolved
  via the **verified** ORCID rather than the unauthenticated OpenAlex lookup. Everything My-Pubs already does stays
  local; the account only makes the *identity* authoritative + pre-fills the profile.
- **Local posture preserved:** no account → My-Pubs + everything else behaves exactly as today (the existing
  manual-profile path stays). The account is strictly additive.

### Operational (the maintainer stands up — gated before go-live)
- Stand up the chosen auth platform on a VPS/container host (or managed), behind a domain + TLS.
- Register callosum as an OIDC client (loopback redirect `http://127.0.0.1:<port>/oauth/callback`).
- Add **ORCID** as the first social connector (verify ORCID's OIDC discovery for the chosen platform).
- A **privacy policy** URL (the service holds PII).

> **Runbook (shipped inc 195):** `ops/accounts-authentik-setup.md` — the concrete step-by-step for Authentik (the
> chosen platform): host it behind TLS → register an ORCID API client → add ORCID as an OIDC source → **emit the
> ORCID iD as an `orcid` claim** → create the callosum public/PKCE provider with the loopback redirect → set
> `CALLOSUM_OIDC_*` env → live-verify the sign-in.

### Verification (SP1)
- Hermetic app-side tests against the **OIDC contract** with an injected fake provider (the inc-149/183 injectable
  pattern) — PKCE built right, callback exchanges the code, token stored write-only, refresh, sign-out, signed-out
  default unchanged. No live service needed for the suite.
- The **live ORCID round-trip** is the maintainer's manual check (needs the real service + an ORCID account) — same
  reality as the cloudflared tunnel / Word add-in.
- QA route (rule #10) for the new Account surface + endpoints; honesty-invariant assertions (no library egress on
  sign-in; signed-out default).

---

## Gates this whole effort trips

- **Security audit (every phase):** auth/session logic, secret/token handling, OIDC redirect + state/PKCE, SSRF on
  the discovery/token endpoints, PII handling, the new external service, supply-chain (the auth platform). The
  Security baseline mandates auth + rate-limiting before exposure — the inc-168 `AccessControlMiddleware` +
  RateLimiter foundation is reused/extended, not re-rolled.
- **Principles + A-A values pass:** accounts/sync are an **emergent value** — adopt deliberately. Default-off,
  opt-in, labeled egress (the A-A consent value); data-minimization structural through SP2; SP3 sync gets the
  heaviest pass (the invariant inversion).
- **README / help / PRINCIPLES privacy promise:** rewritten honestly to *"local-first; account + sync are opt-in"* —
  surfaced, never silently weakened.

---

## Open decisions for spec review (the maintainer's calls)

1. **Auth platform.** Self-hostable front-runners: **Authentik** (Python, same stack) or **Zitadel** (modern) for
   identity-only SP1; **Supabase** if SP3 sync is near (auth + sync in one stack). Want a focused research increment
   to compare, or a direct pick?
2. **Deploy host for the identity service.** Not HostGator (can't run it). A small VPS? Fly.io/Railway? A managed
   provider (skips self-hosting entirely)? This is the operational commitment behind "optional account."
3. **SP1 scope confirmation.** ORCID-only login + verified My-Pubs + identity-only, no sync — good as the first
   shippable increment?

---

## Out of scope / explicitly deferred

- **Full hosted multi-tenant callosum** (server holds everyone's library) — **rejected**; reverses local-first.
- **Sync (SP3)** and **sharing (SP4)** — section-level only here; each its own design when next.
- **Billing** — not contemplated.
