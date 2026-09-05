# H1b.1 focused independent hardening audit — preregistration

**Frozen:** 2026-09-05, before outcome measurement  
**Target commit:** `1f65f8e90c92263d80c0991601a5b805dca568e2`  
**Target tree:** `ce2dbf03d4d318e9eb1bad7e593426fa3d13e1eb`  
**Target parent:** `b2efbaf1a1585a7c676905a9987a2fd5d58fcccd`  
**H1b baseline:** `a41266ba4850a17ce04af3480b7237197416574f`  
**Database snapshot:** `.local/h1b1-hardening-audit/h1b-baseline.sqlite` (ignored), SHA-256 `3be4c7a62779eed8e802f46b7c1dcf51f4abd95a94a78a49eee1addda267e0fc`, migration `0080_source_components`  
**Deterministic seed:** `20260905`

## Independence boundary

Before the independent findings commit, the audit will not read Claude's H1b.1 increment notes,
implementation appendix, final summary, H1b.1 narrative in `.claude/changes.md`, or parallel H1b.1
scratch artifacts. Permitted inputs are production code at the target commit, tracked tests and
fixtures, the frozen Codex H1b audit and earlier evidence-unit research, the design-only provenance
contract, and validation PDFs/database. The target and hypotheses will not change after measurement.

## Primary hypothesis and decision

H1b.1 opens the bounded H1c research gate only if all thirteen gate conditions in the task hold:
non-complete/interrupted graphs are non-current and repairable; rollback preserves a prior valid
graph; durable logical provenance survives rebuild without true content collisions; duplicate-byte
attachment instances remain distinguishable; malformed geometry fails closed without rewriting raw
coordinates; chunks, embeddings, vectors, retrieval and verification remain unchanged; and no H1b.1
field is load-bearing. Any failed condition yields `H1c GATE = BLOCKED` with the smallest blocker.

## Currentness invariant

A source graph is current only when all applicable facts agree:

1. the representation exists and has `state == complete`;
2. its non-empty source checksum equals the live attachment checksum;
3. its requested derivation identity equals the current derivation identity;
4. its extraction tool/version agrees with the persisted graph identity (and any separately defined
   committed current-extractor identity, if production defines one);
5. `expected_pages > 0`, `written_pages == expected_pages`, and `skipped_pages == 0`;
6. actual persisted page count equals `written_pages`;
7. actual persisted component count equals `written_components`.

`expected_pages` means pages emitted by deterministic extraction. It proves persistence completeness
relative to that output, not independent completeness relative to the PDF. A small direct PyMuPDF
check may confirm the distinction; the full H1b fidelity study will not be rerun.

Each predicate will be challenged in an isolated synthetic database. Tests include truncated,
incomplete, failed and absent states; checksum, derivation and extraction-identity drift; missing
page/component rows; count mismatches; skipped pages; original and last-page cap truncation; four
interruption/failure boundaries; ordinary repair; and rollback restoration of an existing valid graph.

## Durable locator identity and collision payload

Durable Callosum provenance is the pair `(attachment_id, source_locator)`. `attachment_id` identifies
the Callosum attachment instance; the inspectable content-level locator contains source checksum,
extraction tool/version, derivation version, page number and `component_path`. Surrogate page/component
IDs are excluded.

For equal content-level locator keys, the canonical component payload is the canonical JSON object:

```text
{
  page_number,
  page_width, page_height, page_rotation, coordinate_system,
  component_path, parent_component_path,
  kind, native_order, sorted_order, child_order,
  text,
  bbox: [x0, y0, x1, y1],
  font, font_size, flags, dir_x, dir_y, wmode
}
```

Keys are sorted, JSON separators are compact, Unicode is preserved, and numeric values use SQLite's
retrieved finite floating-point values without rounding or normalization. Null remains null. Page
identity within the source and all observational fields that could distinguish stored components are
therefore inspectable. Report separately: duplicate source identities from byte-identical PDFs;
same key/same payload; and same key/different payload. Only the last is a true collision defect.

Across the complete migrated live corpus, independently reconstruct each `component_path` without
calling production helpers: top-level path is `b{sorted_order}`; line path appends
`/l{child_order}`; span path appends `/s{child_order}`. Parent links and kind constrain permitted
hierarchy. Report compared rows, exact matches, mismatches and duplicate expected paths within each
attachment/page/source namespace. Any unexplained mismatch is a provenance defect.

## Geometry comparison semantics

The fixed page-bound tolerance is exactly 2.0 PDF points. Independent classification will not call
the production classifier and will never alter coordinates:

- `unknown`: any bbox coordinate is absent/unparseable according to stored representation;
- `invalid/inverted`: `x1 < x0` or `y1 < y0`;
- `invalid/out_of_page`: any edge exceeds its page boundary by more than 2.0 points;
- `invalid/non_finite`: any coordinate or required page dimension is NaN or infinite;
- `degenerate`: `x1 == x0` or `y1 == y0`, measured separately and not prejudged as an H1b.1 failure;
- otherwise `valid`.

Because production's committed vocabulary is `valid | invalid | unknown`, corpus agreement is
reported both (a) against that committed state and (b) with degenerate observations split out by
component kind for an H1c safety judgment. A zero-area observation alone cannot fail H1b.1 unless it
violates the committed contract; if unsafe for bounded spatial association, it becomes an H1c
qualification or smallest follow-up. Raw coordinates must match before/after exactly by Python value
and canonical serialization; no swap, clamp, or normalization is permitted.

## Corpus, migration, invariants and timing

The coherent H1b snapshot has 114 live PDF attachments, one trashed PDF, 1,628 source pages and
1,089,546 source components. Migration to `0081_source_representations` must leave old graphs
non-current. Ordinary backfill should produce 114 complete/current live representations; a second
run must write none. The trashed attachment is reported separately.

Before migration, after migration, and after backfill, canonical ordered hashes will cover complete
chunk rows/text, embedding metadata, sqlite-vec row IDs and vector blobs, and attachment
identity/checksums. A frozen fixed-vector retrieval probe must return identical ordered IDs and exact
distances. Static references and SQL tracing must show no retrieval/generation read of H1b.1 fields.

Currentness-query cost will use one warm-up plus ten `perf_counter` measurements on the migrated full
corpus and report minimum, median and maximum with corpus counts. This is descriptive, not an
optimization threshold.

## Failure and stop rules

Stop-level defects are: any truncated/incomplete/failed/interrupted graph classified current; failed
ordinary repair; rollback poisoning a valid graph; logical locator drift for unchanged source;
same-key/different-payload collision; duplicate-byte attachment provenance not disambiguated by
attachment context; raw-geometry rewrite; required malformed geometry accepted contrary to the
committed contract; any chunk/embedding/vector/retrieval change; or any production retrieval/
generation coupling. Unrelated pre-existing Ruff/CRLF failures will be independently baselined but
are not H1c gate failures unless H1b.1 introduced or worsened them.

No production code, prompts, models, providers, retrieval, embeddings, thresholds or verifier will
be changed. No model/provider will be called. No H1c association or reconstruction probe will run.

