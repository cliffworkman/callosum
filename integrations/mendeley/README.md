# Mendeley Integration Scope

## Native API status (increment 537)

Callosum now has a **dormant, transport-only** client for Mendeley's official personal-library API in
`client.py`. It pins v1 media types, keeps bearer tokens in headers, bounds pages/items/body sizes, rejects
pagination that leaves the exact API resource, and validates the documented `downloads.mendeley.com` file
redirect without following it. It also models the official authorization-code request/token exchange shape.

This is not user-facing and does not publish an OAuth callback. Current official Mendeley documentation still
requires a confidential client secret for authorization-code exchange, documents no PKCE support, and requires
an exact registered redirect URI. A distributed desktop binary cannot make an embedded shared secret
confidential, while Callosum's backend port may move when occupied. Live app-registration capability and a safe
redirect/secret ownership design must be proven before the native path can activate. Until then, the supported
paths below remain the product behavior.

## Supported paths

Mendeley support is deliberately a migration handoff, not a direct database reader:

1. **Fuller library bridge:** in current Zotero Desktop, use **File → Import → Mendeley Reference Manager
   (online import)**. After Zotero finishes, point Callosum's native Zotero importer at that ordinary Zotero data
   directory through **+ Add → Read Zotero library… (Mendeley bridge)**. Zotero documents that its bridge imports
   the personal library's data, files, and folder structure.
2. **Metadata-only:** export BibTeX/RIS from Mendeley and use **+ Add → Import citations file… (EndNote RIS)**.

The bridge requires the Mendeley library and files to be synced to Mendeley/Elsevier's servers and asks the user
to authenticate inside Zotero; Callosum never sees those credentials. Zotero cannot directly import Mendeley
group libraries (copy their items into a personal-library collection first), and Mendeley Cite document citations
are not readable by Zotero. These are upstream boundaries, not capabilities Callosum claims to erase.

## Declined path

Callosum does not read or decrypt Mendeley's protected local store. Zotero documents that Mendeley Desktop 1.19+
encrypted its database and that current Mendeley Reference Manager has no real local database. Circumventing that
boundary conflicts with `.claude/APPROACH-AVOIDANCE.md`; the documented Zotero bridge or supported interchange
exports are the only intended routes.

Scope / backlog:

- No major future *track* depends on direct Mendeley integration — it is **import coverage**, not track
  infrastructure. Tracked under **"Import coverage — additional sources"** (Theme 2) in
  `.claude/docs/INCREMENT-BACKLOG.md`, alongside generic BibTeX/RIS/CSL-JSON import.
- Relevant to reference-manager parity for users whose libraries originate in Mendeley.

Primary source: <https://www.zotero.org/support/kb/mendeley_import> (last updated 2025-08-25 when reviewed on
2026-08-21).
