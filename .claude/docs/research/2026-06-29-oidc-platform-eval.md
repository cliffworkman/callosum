# OIDC auth-platform evaluation — callosum accounts SP1 (sub-step 0)

**Date:** 2026-06-29
**For:** the accounts/identity arc (backlog #15; design spec `…/specs/2026-06-29-accounts-optional-identity-design.md`;
plan `~/.claude/plans/would-you-mind-reading-wise-peacock.md`).
**Question:** which **self-hostable** auth platform should be the "callosum account" service that brokers ORCID
(and later Google/email) as login methods, for **SP1 = identity-only**?

## The architecture this has to satisfy

callosum (the local app) is **one OIDC client** of **the callosum account platform**. The platform adds **ORCID as a
connector** and must pass the **verified ORCID iD through as a claim** the app can read → write into the My-Pubs
profile. So the must-haves are: (1) add a **generic OIDC/OAuth source** (ORCID), (2) **map an external claim**
(the ORCID iD) into the platform's own id-token/userinfo, (3) reasonable **self-host** weight, (4) allow a
**loopback redirect** (`http://127.0.0.1:<port>/oauth/callback`) for the callosum client.

## Confirmed facts (web-verified, 2026-06-29)

- **ORCID = a conformant OIDC provider.** `iss: https://orcid.org`; request the `openid` scope on the auth-code flow →
  an `id_token` whose **`sub` is the ORCID iD** (e.g. `0000-0002-2601-8132`). This is the **free public** path —
  authentication + the iD need no member API. *(Reading a user's works still uses OpenAlex/public ORCID, unchanged.)*
- **Authentik** — first-class **OAuth/OIDC Sources** + **property/scope mappings** (Customization → Property Mappings;
  expression-based, e.g. map `info.get(...)` → a claim). Adding ORCID as a generic OAuth/OIDC source + a mapping to
  carry the ORCID iD is its standard pattern. Python/Django.
- **Zitadel** — **Generic OIDC Identity Provider** config + **Actions/flows** ("External Authentication → Post
  Authentication") to prefill/append external claims. ORCID-as-generic-OIDC works; carrying the ORCID iD as a custom
  claim is via an Action (a bit more assembly than Authentik's mappings). Go single-binary; self-host or SaaS.

## Recommendation

| Platform | Stack / self-host weight | ORCID-claim path | Verdict |
|---|---|---|---|
| **Authentik** ⭐ | Python/Django (callosum's stack); container/compose; moderate | OAuth/OIDC **Source** + **property mapping** → cleanest | **Pick for SP1** — stack familiarity + the simplest ORCID-iD-as-claim path + sane self-host weight |
| **Zitadel** | Go **single binary**; very easy to deploy | Generic OIDC IdP + an **Action** (slightly more setup) | **Close runner-up** — choose if you'd rather run one Go binary than a Django stack |
| **Supabase (self-host)** | Heavy (Auth+Postgres+Studio+…) | Custom-OIDC SSO is **less first-class** than the above | **Only if SP3 sync is imminent** — its Postgres+RLS *doubles as the sync store*; otherwise overkill for identity-only |
| Keycloak | Java; heaviest; most battle-tested | Identity-provider + mappers (very capable) | Not recommended — overkill for a single-user tool's optional account |
| Ory (Kratos+Hydra) | Go; API-first; most assembly | Capable but you build more glue | Not recommended — more than SP1 needs |

**My pick: Authentik for SP1** — same language as callosum (easiest for the maintainer to reason about + self-host),
the cleanest "ORCID iD → claim" path (property mappings), and light enough for a small VPS/container. **Zitadel** is
the equal-quality fallback if you prefer a single Go binary. **Reconsider Supabase only if you want to commit now to
it as the eventual SP3 sync backend** (one stack for auth + sync) — at the cost of a heavier identity-only footprint
and a fiddlier ORCID-as-custom-OIDC setup.

## Verify at standup (whichever is chosen)

1. Add **ORCID** as a generic OAuth/OIDC source (ORCID's authorize/token/userinfo + a registered ORCID API client).
2. **Map the ORCID iD (`sub`) into a claim** the platform issues to callosum (e.g. an `orcid` claim) — the SP1 payoff
   depends on this reaching the app.
3. Register the **callosum OIDC client** with the **loopback redirect** `http://127.0.0.1:<port>/oauth/callback`
   (allow the loopback port pattern; RFC 8252).
4. A **privacy policy** URL (the service holds identity PII).

*Platform-agnostic note:* the in-repo OIDC client code (the SP1 plan) is written against the standard OIDC contract,
so none of the above blocks building it — it only blocks the **live** ORCID round-trip.
