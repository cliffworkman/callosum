# Future track — Citation & bibliography engine (the reference-manager core)

**Disposition for CC:** Capture + `.claude/docs/future-tracks/`. The reference-manager spine — scope carefully and
**do not hand-roll citation formatting.** Security audit fires (new JS-runtime surface + per-target injection +
cloud egress for the Google Docs target). One open build decision remains: how to host the JS runtime (see
Processor).

## Why this one is different
Everything else in METHODS is an add-on. This is the spine of the "reference manager" claim: insert in-text
citations while writing, generate and maintain the reference list, and reformat both to any journal's or style's
requirements. If this isn't excellent, Callosum is not a reference manager.

## Architecture — CSL + citeproc + the CSL style repository (settled; never reinvent)
- **CSL (Citation Style Language)** + the **official style repository** (10,000+ styles: APA, MLA, Chicago,
  Vancouver, IEEE, plus thousands of journal-specific styles — "format to each journal's requirements," already
  encoded).
- **A citeproc processor** renders (item CSL-JSON + style + locale) → citations + bibliography, handling
  disambiguation, et-al, numeric renumbering, name-particle/title-case, ibid., subsequent-author substitution.
- **CSL-JSON** is the interchange schema; Callosum's metadata maps to it, and metadata quality bounds output
  quality (surface what's missing).

## Processor — RESOLVED: citeproc-js, backend-side, under its AGPL arm
The research closed this. **citeproc-js** is the only actively maintained, spec-complete processor (1,300+ tests,
CSL 1.0.1 + CSL-M, still Zotero's default). The alternatives are out:
- **citeproc-rs** (Rust) is effectively dormant (no release since v0.2.0 Dec 2021, no Python bindings, incomplete
  test pass) — not viable.
- **citeproc-py** passes only ~60% of the CSL suite and **lacks disambiguation, year-suffix, and cite
  collapsing** — i.e., exactly the live-field behaviors that justify this whole feature. Not viable as primary.
- License: citeproc-js is dual **CPAL-1.0 OR AGPL-3.0** → use the **AGPL arm**, which combines cleanly with
  Callosum's AGPL-3.0.

**New hard dependency (v1 missed this):** citeproc-js is JavaScript, so the Python core must **host a JS runtime**
to run it — either a **Node sidecar process** or an **embedded engine (e.g., QuickJS)**. This is a real packaging
+ security-surface dependency. Fallback only if a JS runtime proves unacceptable: **citeproc-lua** (better
correctness than citeproc-py, needs a Lua runtime) ahead of citeproc-py.

## Render location — RESOLVED: backend-side, adapters thin
Render **in the Python core**, not in each document environment. Because only one good processor exists, hosting
it separately in each runtime would fragment correctness (citations rendering differently per word processor). One
central citeproc-js instance = single source of truth + byte-identical output across all targets. This is exactly
how Zotero operates (central engine; thin word-processor plugins).
- **Consequence:** each adapter becomes a thin, uniform **field-placer** with only three jobs — place/track a
  field, read back the full ordered citation set, write back rendered cites + bibliography.
- **Accepted cost:** every restyle/renumber round-trips through the backend. Worth it for correctness uniformity.

## The live-field model — confirmed, with the payload format resolved
Citations are **live tracked fields** (item keys + CSL-JSON), never pasted static text — the line between a
reference manager and a toy. Clarification from the research: this is a **document-storage** property, not a
render-location one (the backend reads the ordered set out of the document, renders, writes back). Live fields are
what enable restyle, renumber, and bibliography-sync.
- **Field payload format — RESOLVED:** adopt the **Zotero `ADDIN … CSL_CITATION` embedded-CSL-JSON** convention
  (the field stores the `citationItems` CSL-JSON + a schema URL; visible text is the rendered citation). It's
  documented, interoperable, and **Mendeley-compatible**, so Callosum documents round-trip with the dominant
  tools. Reuse as a *pattern*, not code.

## New architectural primitives to design in from target #1 (v1 missed these)
1. **A target-agnostic field abstraction:** `{itemKeys, cslJsonPayload, renderedText, orderIndex}` that maps onto
   all three containers (ReferenceMarks / Office.js content-controls-or-field-codes / Docs named-ranges-or-links).
2. **Document-order extraction that tolerates a full-document scan.** Google Docs cannot cheaply enumerate fields,
   so the "retrieve the full ordered citation set" contract must not assume a fast field iterator — design for the
   weakest target from the start so it isn't blocked later.
3. **A flatten / unlink mode** (convert live fields → static text) for publication hand-off. Required across all
   targets; v1 omitted it.

## The four targets → three adapters
Word for Windows + Word for Mac unify under **Office.js** (one adapter), so the four targets are **three
integration architectures**:
- **UNO (LibreOffice)** — Python-scriptable via the UNO bridge; **ReferenceMarks** as the live-field primitive
  (Bookmarks optionally, for Word interop); bibliography via a dedicated paragraph style. ReferenceMarks survive
  only in ODF and can be corrupted by Track Changes — handle both.
- **Office.js (Word Win + Mac + web)** — one cross-platform web add-in; live field via **content controls** or the
  legacy **ADDIN field code** embedding CSL-JSON. Parity is strong but imperfect: **test Win and Mac, gate
  features with `requirements.isSetSupported()`, target the JS-API lowest common denominator.**
- **Apps Script / Docs API (Google Docs)** — see the fenced opt-in below.

## Build sequence — RESOLVED: LibreOffice → Word → Google Docs
- **LibreOffice/UNO first.** Python-native (no second runtime to fight), richest field model (ReferenceMarks),
  fully local (no cloud/values tension), open-source (Zotero's `.oxt` readable as a pattern). The friendliest
  place to prove the full render→place→read-back→write-back loop and the field abstraction.
- **Word (Office.js) second** — the popular target, once the architecture is proven; Win+Mac in one adapter.
- **Google Docs last** — the weakest field model + the values tension.
- **Cross-cutting constraints to bake in at target #1** (so later targets aren't blocked): the target-agnostic
  field abstraction; the full-scan extraction contract; backend-renders/adapter-places (never let an adapter
  format); CSL-JSON-in-field payload; the flatten mode.

## Google Docs — fenced as an explicit cloud opt-in (not a peer target)
It demands broad permissions ("see, edit, create, delete **all** your Google Docs"), has **no native field
concept** (prefer **named ranges** over the link-sentinel hack; named ranges auto-track indices but are visible to
collaborators and can split), and **slows at scale** (~10s to update 100+ citations → ship a **delayed/manual
update mode**). It is the one target that genuinely strains local-first, so it is **opt-in, clearly labeled**
("this target sends document content to Google's cloud and requires broad Docs permissions"), **never a default**,
and built last.

## Style & locale selection + bundle-vs-fetch — RESOLVED
- **Style picker backed by the CSL repo** — search by journal → its CSL style; plus named styles
  (APA/MLA/Chicago/Vancouver/IEEE); map "journal says use APA" → the named style. **Locale** selection
  (en-US/en-GB/…).
- **Bundle a curated core style set + all locale files** (locales are small and required) for offline/local-first
  operation; **fetch the long tail on demand, consent-gated.** Cache aggressively; fetch individual raw files
  (don't clone); treat the repo as a courtesy resource.
- **PUBLISHERS synergy:** once a target journal is chosen there, preselect its CSL style here.

## Numeric vs author-date — confirmed (both must work)
Numeric (Vancouver/IEEE/Nature): order by appearance or alphabetically; renumber on edit. Author-date
(APA/Chicago author-date): disambiguate (2020a/2020b), et-al rules. citeproc-js handles both *given the ordered
set* — another reason for live-fields + backend render.

## Credit-the-lineage + licensing — RESOLVED
This feature stands on major open-source infrastructure (CSL — D'Arcus, Bennett, Zelle et al.; citeproc-js; the
style repo), so it's a flagship case for the credit-the-lineage principle + dependency-NOTICE.
- **CC-BY-SA / AGPL compatibility:** CSL styles + locales are CC-BY-SA (mostly 3.0 Unported, some 4.0). They
  coexist with AGPL as an **aggregate** — they're *data the program operates on*, not a derivative of your code —
  so bundling forces **no relicensing in either direction.**
- **Obligations:** preserve each style's embedded `<rights>` element and author/contributor listings **verbatim**;
  keep styles/locales **under CC-BY-SA** (modified styles stay CC-BY-SA + note the change); use citeproc-js under
  its AGPL arm.
- **Six-element NOTICE / acknowledgments file:** (1) clear mention of the **CSL project** + link to
  citationstyles.org; (2) statement that bundled styles+locales are **CC-BY-SA** (with version + license link),
  remaining CC-BY-SA not AGPL; (3) preserved `<rights>` + author metadata; (4) **citeproc-js** attribution
  (© Frank Bennett & contributors), used under **AGPL-3.0**, with source link; (5) any style modifications noted +
  confirmed still CC-BY-SA; (6) the standard AGPL corresponding-source offer for the app.

## Scope discipline (it's THE feature — resist gold-plating)
- **v1 build = LibreOffice target:** pick a style (named + journal-specific), insert live ReferenceMark fields,
  generate/update the reference list, restyle/renumber/regenerate, both style families, flatten mode, core-bundle
  + consent-fetch.
- **Defer per the sequence:** Word (Office.js) → Google Docs (opt-in); in-app custom-style editing; citation
  prefixes/suffixes/locators beyond the basics.

## Gates
- **Security audit:** fires on three new surfaces — the **JS runtime** hosting citeproc-js (sidecar/embedded:
  packaging + sandboxing), the **per-target field-injection** path into live documents (must not become an
  injection vector), and **cloud egress** for the Google Docs adapter (consent-gated, clearly disclosed). Validate
  fetched styles.
- **Principles gate:** clears (core utility; credit/NOTICE handled; Google Docs egress is opt-in + disclosed).

## Tests / acceptance criteria
- In-text citations insert as **live fields** (keys + CSL-JSON) in the v1 (LibreOffice) target; the **field
  abstraction** maps cleanly and the **full-scan extraction** returns the ordered set.
- **Backend-side render** produces identical output regardless of target; adapters never format.
- **Restyle / renumber / regenerate** the bibliography in sync; both numeric and author-date families correct
  (disambiguation, et-al).
- Format to a **named style** and a **journal-specific CSL style** from the repo.
- **Flatten mode** converts live fields → static text faithfully.
- Metadata→CSL-JSON correct; degrades gracefully + surfaces gaps on incomplete metadata.
- The **JS runtime** is sandboxed and packaged; the **NOTICE** is present with all six elements; bundled
  styles/locales retain `<rights>` + authors.

## Watch items / caveats
- **citeproc-js is a single-track dependency** (maintenance now community-led — Wiernik/Lee — active as of early
  2025); monitor it. Revisit a Rust engine only if citeproc-rs revives with Python bindings + a full suite pass.
- **Office.js Win/Mac parity** is good, not perfect (e.g., `getHtml()` differs) — verify per platform.
- **Named-range vs link-sentinel** for Google Docs should be prototyped (named ranges cleaner but collaborator-
  visible and splittable).
- **CC-BY-SA 3.0 vs 4.0** mixing — NOTICE should reference both.

## OUTPUT
The reference-manager core, research-resolved: a citation & bibliography engine on CSL + **citeproc-js run
backend-side** (under its AGPL arm) in the Python core via a hosted JS runtime, with **three thin, uniform
adapters** (UNO, Office.js spanning Word Win+Mac, Apps Script) that only place/track fields, read back the full
ordered set, and write rendered output; in-text citations stored as **live fields** in the Zotero
`CSL_CITATION` CSL-JSON payload; a **target-agnostic field abstraction**, a **full-scan-tolerant extraction
contract**, and a **flatten mode** designed in from target #1; **build sequence LibreOffice → Word → Google Docs**,
with Google Docs fenced as a clearly-labeled cloud opt-in; a style picker over named + journal-specific styles
with a curated-bundle-plus-consent-fetch strategy; correct numeric and author-date handling; and full
credit-the-lineage with a six-element CC-BY-SA/AGPL-correct NOTICE.
