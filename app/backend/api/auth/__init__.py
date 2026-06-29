"""Optional-account auth (SP1): "Sign in with ORCID" via OIDC.

The callosum app is one OIDC client of the callosum account platform (Authentik), which brokers ORCID and returns
the verified ORCID iD as a claim. Identity-only — no library data is sent. See the design spec
``.claude/docs/specs/2026-06-29-accounts-optional-identity-design.md``.
"""
