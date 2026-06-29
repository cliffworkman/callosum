# Standing up the callosum account platform (Authentik) — "Sign in with ORCID"

This is the **maintainer's** runbook to make the optional account (SP1, inc 194) work *live*. The in-repo code is
done + tested; it just needs an OIDC provider to point at. Until you do this, **Settings → Account** honestly shows
"Sign-in isn't set up on this Callosum yet" and nothing changes — callosum stays fully local.

**The shape (decided in the design spec `.claude/docs/specs/2026-06-29-accounts-optional-identity-design.md`):**
callosum is **one OIDC client of the callosum account platform** (Authentik), *not* of ORCID directly. Authentik
brokers ORCID (and, later, Google/email — SP2, no app change) and hands callosum a token whose claims include the
**verified ORCID iD**. callosum reads that iD and pre-fills *My Publications*. **Identity only — no library data ever
reaches the account platform.**

> Exact menu labels vary by Authentik version; the **live sign-in at step 7 is the real proof**. The platform eval
> (`.claude/docs/research/2026-06-29-oidc-platform-eval.md`) picked Authentik; Zitadel works the same way if you
> prefer a single Go binary.

---

## 0. Prerequisites

- A host that can run an **always-on** service behind **TLS** with a stable hostname (e.g. `https://auth.example.com`).
  **Not** the HostGator shared hosting — it reaps long-running processes and has no container runtime (see inc 169). A
  small VPS, a container host, or a PaaS (Fly.io / Railway) is fine. *This service holds identity PII — you operate it.*
- Docker + docker-compose on that host.
- An **ORCID account** (yours) to test the round-trip.

## 1. Run Authentik

Follow Authentik's official docker-compose quickstart (<https://docs.goauthentik.io/docs/install-config/>). Put it
behind your TLS reverse proxy at, say, `https://auth.example.com`. Finish the initial admin setup (`akadmin`).

## 2. Register an ORCID API client

At <https://orcid.org/developer-tools> create a **public API** client (sign-in only needs the public API — no member
API). You get a **client ID** + **secret**. Set its **redirect URI** to Authentik's source callback, which Authentik
shows when you create the source in step 3 (typically `https://auth.example.com/source/oauth/callback/orcid/`).

## 3. Add ORCID as a source in Authentik

Admin → **Directory → Federation & Social login → Create → OAuth Source** (generic **OpenID Connect / OAuth**):
- **Name / slug:** `orcid`
- **Consumer key / secret:** the ORCID client ID / secret from step 2
- **OIDC well-known / discovery URL:** `https://orcid.org/.well-known/openid-configuration` (Authentik fills the
  authorize / token / JWKS / userinfo endpoints from it)
- **Scopes:** `openid`
- The user's **ORCID iD arrives as the `sub` claim** (e.g. `0000-0002-2206-0325`), issuer `https://orcid.org`.

## 4. Surface the ORCID iD as an `orcid` claim — the crucial step

callosum reads the ORCID iD from a claim named by `CALLOSUM_OIDC_CLAIM_ORCID` (**default `orcid`**). So Authentik must
*emit* an `orcid` claim to callosum:
- Customization → **Property Mappings → Create → Scope Mapping**: scope name `orcid`, expression returns the iD from
  the user's ORCID source connection — e.g.
  ```python
  return {"orcid": request.user.attributes.get("orcid")}
  ```
  (Map the ORCID source's `sub` into the user's `attributes["orcid"]` on enrollment, then return it here. Authentik's
  exact attribute path depends on your source-enrollment flow; the goal is simply: **the token callosum receives
  contains `orcid: <the verified iD>`**.)
- Add that `orcid` scope mapping to the callosum provider in step 5.

If you can't easily emit a custom claim, an alternative is to set `CALLOSUM_OIDC_CLAIM_ORCID` to a claim Authentik
*does* emit that carries the ORCID iD (e.g. `preferred_username` if you map it to the iD). The point is just: callosum
reads the verified iD from that one claim.

## 5. Create the callosum OIDC application + provider

Admin → **Applications → Create with provider → OAuth2/OpenID Provider**:
- **Client type:** **Public** (so it uses **PKCE**, no client secret — callosum is a native/local app, RFC 8252).
- **Redirect URIs:** `http://127.0.0.1:8080/oauth/callback` — add a line per port you run callosum on (8888, etc.), or
  use Authentik's **regex** mode for `http://127\.0\.0\.1:\d+/oauth/callback` and `http://localhost:\d+/oauth/callback`.
- **Scopes:** `openid`, `profile`, and the **`orcid`** scope from step 4.
- Note the provider's **OpenID Configuration Issuer** (e.g. `https://auth.example.com/application/o/callosum/`) and the
  **Client ID**.

## 6. Point callosum at it

Set these in callosum's gitignored **`.env`** (or the process environment), then **restart** callosum:

```
CALLOSUM_OIDC_ISSUER=https://auth.example.com/application/o/callosum/
CALLOSUM_OIDC_CLIENT_ID=<the client id from step 5>
CALLOSUM_OIDC_SCOPES=openid profile orcid
CALLOSUM_OIDC_CLAIM_ORCID=orcid
```

(Install the verification dep once: `pip install "PyJWT[crypto]"` — already in `requirements.txt`.) `Settings →
Account` now offers **Sign in with ORCID** instead of the "not set up" note.

## 7. Verify (the live round-trip — your manual check)

1. Open callosum → **Settings → Account → Sign in with ORCID**. You're sent to Authentik → ORCID → consent.
2. You land back at callosum signed in. **Settings → Account** shows your name + ORCID; **My Publications** is now
   pre-filled with your verified ORCID (run *Refresh my papers* if needed).
3. Sanity: `GET /settings` → `account.signed_in: true`, `account.orcid` set, and **no token value anywhere** in the
   body. **Sign out** clears the session (your library + profile are untouched).

If sign-in fails, the callback redirects to `/?signin=error` (never a crash); check Authentik's event log + that the
redirect URI (step 5) exactly matches callosum's loopback origin + `/oauth/callback`.

---

## Adding more login methods — Google + email/password (SP2)

Because callosum is one OIDC client of Authentik, **more login methods are pure Authentik config — no callosum
change**. They appear on Authentik's own sign-in page; callosum's single **"Sign in"** entry sends the user there, and
gets a token back whichever method they used. (Only an **ORCID** login carries the `orcid` claim → only it pre-fills
My Publications; a Google/email login just sets your account identity, shown as your name or email.)

- **Google:** in Google Cloud Console → APIs & Services → **OAuth consent screen** + **Credentials → OAuth client ID
  (Web application)**; set the authorized redirect URI to Authentik's Google-source callback (Authentik shows it).
  Then in Authentik → **Directory → Federation & Social login → Create → Google source**, paste the Google client
  ID/secret.
- **Email/password:** use Authentik's built-in identity — either create users in **Directory → Users**, or enable a
  self-service **enrollment/registration flow** (Flows & Stages) so people can register with an email + password.
- **Make sure Authentik emits the identity claims** callosum displays: the callosum provider (step 5) should include
  the `profile` + `email` scopes so the token carries `name` / `email` (callosum shows "Signed in as <name or
  email>"). The `orcid` claim mapping from step 4 stays as-is — it's only populated when the user chose ORCID.

No callosum change is required for these; the single "Sign in" button + the OIDC flow already handle whatever method
Authentik offers.

## Security notes (recap)

- **PKCE public client** — no client secret embedded in callosum.
- **Loopback redirect** — callosum validates the redirect target is `127.0.0.1`/`localhost` only (no open-redirect);
  the `/oauth/callback` navigation is the only endpoint exempt from the Remote-access bearer gate (it carries only an
  opaque code+state validated against the stored PKCE verifier).
- **Tokens are write-only** in callosum (OS keychain or the gitignored `~/.callosum/` file); `GET /settings` reports
  only the verified identity, never a token.
- **Identity only** — the ORCID handshake sends no library text. The egress gate for AI summaries is unaffected.
- The **account platform holds PII** (emails / ORCID iDs / tokens) — that's the service *you* run; keep it patched +
  behind TLS. Cross-device **sync** (the only step that would move library data off your machine) is a separate,
  future, explicitly-consented feature (SP3) — it does not exist yet.
