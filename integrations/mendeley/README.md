# Mendeley Integration Scope

## Supported paths

Mendeley support is deliberately a migration handoff, not a direct database reader:

1. **Fuller library bridge:** in current Zotero Desktop, use **File → Import → Mendeley Reference Manager
   (online import)**. After Zotero finishes, point Callosum's native Zotero importer at that ordinary Zotero data
   directory. Zotero documents that its bridge imports the personal library's data, files, and folder structure.
2. **Metadata-only:** export BibTeX/RIS from Mendeley and use Callosum's generic citation-file importer.

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
