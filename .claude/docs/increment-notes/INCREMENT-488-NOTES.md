# Increment 488 — foreign Word citation conversion research gate (backlog #57 Phase 5)

## Implemented

- Researched current first-party Mendeley Cite, EndNote 2025, and Zotero documentation before touching a parser.
- `.claude/docs/research/2026-08-21_word_citation_migration_formats.md` records the verified container mechanisms,
  missing schema evidence, primary sources, and concrete evidence required to reopen implementation.
- `adapters/word/README.md` now makes the ownership boundary explicit: Callosum live citations are supported, while
  existing Mendeley Cite/EndNote fields must remain with their originating tool until a stable conversion contract
  exists.
- No parser, endpoint, file-ingestion path, dependency, or interactive control was added.

## Key technical detail

The vendors document the **container**, not a complete conversion contract. Mendeley confirms Word content
controls; EndNote confirms Word fields, `ADDIN EN.CITE`, and the Traveling Library. Neither publishes the complete,
versioned payload grammar needed to preserve grouped citations and per-item options. Conflicting third-party
reverse engineering is not a safe basis for rewriting a scholarly manuscript. The parser therefore fails closed
at the design boundary: it does not exist yet.

## Experience pass

Withholding an attractive but ungrounded converter is the user-facing result. A researcher can migrate their
library and create new Callosum citations, but the product will not silently reinterpret or damage live citation
fields in an existing manuscript. The adapter documentation points existing fields back to their owning tool and
does not confuse flattening with editable citation migration.

## Manual verification script

1. Read the research note and follow every primary-source link; confirm each supports only the claim attached to
   it and that no exact payload schema is asserted.
2. Open `adapters/word/README.md`; confirm the limitation distinguishes Callosum-created fields from foreign live
   fields and identifies vendor-owned flattening as static output, not migration.
3. Confirm no production parser, endpoint, dependency, QA route, or security-audit surface was introduced by this
   increment.
4. If a future vendor contract or approved fixture corpus becomes available, execute the evidence and safety
   checklist in the research note before changing this phase's implementation status.

## Verification

- Documentation-only slice; final repository gates and full suite recorded in the session handoff.

## Honest completion boundary

**The research gate is complete; converter implementation remains open and blocked on primary evidence.** This is
the intended useful result of the handoff's research-only fallback, not a claim that Mendeley Cite or EndNote Word
documents can now be converted.
