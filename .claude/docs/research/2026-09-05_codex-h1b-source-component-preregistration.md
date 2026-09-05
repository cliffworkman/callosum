# H1b Source-Component Audit Preregistration

**Frozen before database migration, backfill, corpus measurement, PDF reread, or inspection of
parallel-agent H1b notes/results.**

## Identity and independence

- H1b commit: `a41266ba4850a17ce04af3480b7237197416574f`
- H1b tree: `1fa67760adce3476aaf2ec99ae5b075171d82752`
- Migration target: `0080_source_components`
- Starting database: coherent pre-H1b snapshot SHA-256
  `fc402464bfb9eb26b02f4b7bd12a844bbdc828413dcfc751b3cbf8252da93f70`
- Deterministic seed: `20260905`
- Worktree branch: `codex/h1b-source-component-audit-20260905`
- Detailed data, article text, PDF paths, and raw adjudication remain ignored under
  `.local/h1b-source-component-audit/`.

Before the independent findings freeze, the investigator will not read increment 578 notes,
the H1b implementation appendix/final summary, H1b portions of the change diary, or any
parallel-agent H1b scratch artifact. Production code, schema, tests, the design-only
`evidence_form` contract, pre-H1b studies, and the investigator's own prior replication are
permitted.

## Questions and hypotheses

1. H1b is additive and non-load-bearing: it does not change chunks, embeddings, vectors,
   retrieval, prompts, providers, verifiers, or thresholds.
2. The component graph round-trips Callosum's extraction observations faithfully.
3. An independent raw-PyMuPDF reread will reproduce the persisted source fields; this comparison
   is separate from the shared-code Callosum round trip.
4. MuPDF block number (`native_order`) and geometric-list position (`sorted_order`) remain
   distinct and neither is treated as semantic reading order.
5. Pure headings and raster bounds are retained as structural observations without becoming
   retrieval evidence or scientific claims.
6. GROBID figure/description/grid persistence remains structural and non-retrieval-facing, but
   may remain incomplete for coordinates, footnotes, multi-page regions, or source-version
   provenance.
7. Stable logical source locators, not replaceable database surrogate keys, are required for
   future multi-region evidence provenance.
8. H1b may be sufficient for a bounded H1c study only if it contains no harmful structural
   misrepresentation in the adversarial safety set.

## Corpus and coverage

The logical live universe is every PDF attachment joined to a paper where
`papers.deleted_at IS NULL`. Soft-deleted papers and their physically retained chunks are counted
separately and are not live coverage defects. Each target is classified as available and
checksum-matching, missing/unavailable, checksum-mismatched, current, stale, absent, or incomplete.
Current means every persisted page row agrees with the attachment checksum and
`source-components-v1`; this audit will separately test whether that predicate can mistakenly
accept an incomplete/truncated graph.

The audit will explicitly reproduce the reported 93-row discrepancy and test whether all such
rows belong to soft-deleted paper 2 using direct `chunks`/`papers`/H1a structure joins.

## Before/after invariants

Canonical, order-stable SHA-256 digests will be computed before migration, after migration, after
the first backfill, and after the second backfill for:

- complete existing chunk row identities and content, including `text`;
- current/live chunk counts;
- embedding metadata identities and content;
- sqlite-vec row identities and vector blobs;
- attachment identities, roles, checksums, and source paths represented only by a private hash.

Any difference outside the three new H1b tables is a stop-level non-load-bearing failure. A fixed
set of existing vector rows will also serve as query vectors for a bounded before/after retrieval
identity check; ordered IDs and scores must be exactly equal.

## Field comparison semantics

These semantics are frozen before outcomes:

- Exact: page/component logical identity, attachment/checksum, page number, rotation, coordinate
  system, extraction/derivation identity, component kind, parent/child hierarchy, text, font,
  flags, writing mode, native order, sorted order, and child order.
- Coordinates, page dimensions, and font sizes: report both byte/float-exact equality and equality
  within absolute tolerance `0.0001` PDF points.
- Direction cosines: report exact equality and absolute tolerance `0.000001`.
- `None` versus a numeric/text value is always an exact mismatch and cannot pass by tolerance.
- Rates are reported separately for Callosum extraction round-trip and independent raw-PyMuPDF
  source fidelity. Tolerances will not be changed after outcomes are inspected.

Surrogate page/component primary keys may change during replace-per-attachment backfill without
being labeled a defect. The audit instead requires a stable logical locator derived from source
identity, page, hierarchy, and deterministic component positions. Surrogate instability is a
defect only if production exposes it as provenance identity, no stable logical locator can be
formed, or logical-source mappings change.

## Sampling and independent reread

- Callosum round-trip comparison: every available, checksum-matching live PDF.
- Order analysis: every comparable page, plus deterministic human-confirmed samples of 40
  one-column and 40 two-column pages where available.
- Independent raw-PyMuPDF reread: at least 30 deterministic adversarial pages spanning the
  required fixture classes. It will call PyMuPDF directly and independently reconstruct expected
  block/line/span observations rather than calling Callosum's component builder.
- GROBID: the tracked TEI fixture plus any already-local inspectable TEI evidence; no provider or
  network call.
- Adversarial manifest: opaque references for one-column prose, two-column prose, order
  disagreement, cross-column and cross-page adjacency, pure heading, related/unrelated captions,
  ruled and false tables, multi-page table, orphan value, raster image, GROBID figure, and retained
  chunks from a soft-deleted paper.

The investigator will not use a model to select, adjudicate, or reconstruct fixtures.

## Idempotence and failure experiments

Run normal backfill twice and compare counts/content. Force-rebuild a bounded attachment set twice
and compare canonical logical component trees. Simulate an interruption only on a copied database,
then rerun and compare against an uninterrupted control. Test stale-checksum and derivation-version
detection. Lower the component cap by research-only monkeypatch to determine whether a truncated
graph can be mistaken for current; do not modify production constants.

## H1c readiness and optional probe gate

Each substrate is classified `READY`, `READY WITH BOUNDED FIX`, `INSUFFICIENT`, or `NOT TESTED`.
The optional nonpersistent H1c feasibility probe may run only if:

1. existing chunks/embeddings/vectors and bounded retrieval are identical;
2. there are no unexplained source-fidelity mismatches;
3. stale, absent, or truncated structures cannot masquerade as current;
4. a stable logical component locator exists independently of surrogate IDs; and
5. the H1b adversarial safety set contains no harmful structural misrepresentation.

If the probe runs, harmful false-association rate is its primary safety outcome and is reported
before recovery. The probe may inspect known same-column prose or caption/table geometry only; it
will not persist evidence units or change production retrieval.

## Stop and interpretation rules

- Stop the optional probe, but complete the audit, on any H1b invariant, fidelity, completeness,
  locator, or structural-safety failure.
- Missing local PDFs reduce the fidelity denominator and are reported; they are not silently
  treated as H1b mismatches.
- Agreement with production tests is not sufficient evidence of raw-source fidelity.
- Improved coverage is never allowed to excuse a harmful association.
- Table detection and table reconstruction remain distinct.
- This study cannot authorize H1c, a model/representation experiment, retrieval changes, or any
  production fix.

## Outputs and freeze

The tracked outputs are this preregistration, a research-only harness, an opaque/privacy-safe
fixture manifest if useful, and
`.claude/docs/research/2026-09-05_codex-h1b-source-component-audit.md`. Independent observations,
interpretation, and recommendation will be committed before any prohibited H1b narrative or
parallel scratch material is read. A later comparison, if possible, will be appended in a separate
commit without editing the frozen sections.
