# Mendeley → Zotero → Callosum feasibility spike — 2026-08-21

## Verdict

**The bridge is real, current, and documented.** It is the preferred full-library Mendeley migration path within
Callosum's hard boundary against reading/decrypting another tool's protected store. No Callosum backend work is
needed: Zotero performs the Mendeley-specific network/authentication import, materializes an ordinary local Zotero
library, and Callosum's shipped native Zotero importer reads a copy of that local result.

## Verified flow

1. In Mendeley, ensure the personal library's data and files are synced to Mendeley/Elsevier's servers.
2. Run the latest Zotero Desktop and choose **File → Import → Mendeley Reference Manager (online import)**.
3. Authenticate with Mendeley inside Zotero. Zotero states that it never sees or stores the Mendeley password.
4. Let Zotero finish. It documents direct import of “all data, including the full folder structure,” from the
   online Mendeley library.
5. In Callosum, choose **+ Add → Read Zotero library…** and point at the resulting Zotero data directory. From
   this point the existing copy-then-read Zotero importer applies; Callosum never receives Mendeley credentials
   and does not call the Mendeley API.

Primary source: [Zotero — How do I import a Mendeley library into Zotero?](https://www.zotero.org/support/kb/mendeley_import)
(page last updated 2025-08-25; reviewed 2026-08-21). Zotero's team announcement independently describes the
online importer and the absence of a usable current local database:
[Zotero Forums — Online Mendeley importer](https://forums.zotero.org/discussion/89393/available-for-beta-testing-online-mendeley-importer).

## Boundaries that must travel with the recommendation

- **This is an upstream egress step.** Mendeley data/files must already be online, and Zotero contacts Mendeley
  after an explicit user login. It is not Callosum's local/no-egress importer reaching outward.
- **Personal library only.** Zotero cannot directly import Mendeley group libraries. Its documented workaround is
  to copy group items into a collection in the personal Mendeley library before importing.
- **Institutional login caveat.** An institution-only/Shibboleth account may need a separate personal Mendeley
  account connected to it for Zotero login.
- **Field normalization.** Mendeley permits fields Zotero does not permit on a given item type; Zotero places
  invalid fields in `Extra`. Callosum's native Zotero adapter reads all raw item fields but maps only its canonical
  metadata subset, so this bridge is not a promise that every arbitrary/custom Mendeley field becomes a first-
  class Callosum column.
- **No direct group/document bridge.** Zotero can relink citations made by legacy Mendeley Desktop after library
  import, but explicitly says citations created by **Mendeley Cite** are not readable by Zotero. Phase 3 concerns
  the library, not live Word fields; Phase 5 researches those separately.
- **No protected-store workaround.** Zotero documents that Mendeley Desktop 1.19+ encrypted its local database
  and current Mendeley Reference Manager has no real local database. Callosum will not adopt the old-version/
  decryption workaround; that is a hard `APPROACH-AVOIDANCE.md` boundary.

## Alternatives and fidelity

- A direct Mendeley BibTeX/RIS export can go straight into Callosum's generic importer with fewer installed-app
  steps, but it is metadata-only in Callosum and standardized exports omit Mendeley folders, some metadata, and
  PDF annotations. Use it when the user wants references rather than a fuller library migration.
- The Zotero bridge adds an application hop but is the documented way to preserve substantially more library
  structure and files without Callosum handling Mendeley credentials or depending on Elsevier's API.
- The resulting local store is Zotero's normal database/attachment layout, so Phase 1's metadata, collections,
  tags, notes, local PDFs, and Phase 4's supported Zotero annotation-position handling apply to whatever the
  bridge actually materializes. This statement deliberately does not assert that every Mendeley annotation is
  converted; the Zotero page does not make that field-level guarantee.

## Product decision

Ship guidance, not another importer: surface the exact bridge action in onboarding, the Zotero import modal,
Help, and the + Add tooltip; retain the existing Zotero action as the only Callosum entry point. This is fewer
Callosum concepts, keeps credentials outside Callosum, and makes the unavoidable external handoff inspectable.
