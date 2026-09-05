# Focused independent H1b.1 hardening audit

## 1. Provenance / independence boundary

This audit was performed in a dedicated worktree and branch rooted at the exact H1b.1 production
commit. The protocol was frozen before measurement in commit
`88ba2e0c0ce282f210d6bfcc8d3df1c544961e96`. Before this independent findings freeze I did **not**
read Claude's H1b.1 increment notes, implementation appendix, final summary, H1b.1 narrative in
`.claude/changes.md`, or parallel H1b.1 scratch artifacts.

Permitted inputs were production code at the target, tracked tests/fixtures, the earlier frozen
Codex H1b audit, pre-H1b/H1b research, the design-only evidence contract, and copied validation
data. No production database, source code, retrieval behavior, prompt, model, provider, embedding,
threshold, or verifier was changed. No model/provider was called. The main worktree's six unrelated
deleted handoff documents were untouched.

The ignored H1b database snapshot had SHA-256
`3be4c7a62779eed8e802f46b7c1dcf51f4abd95a94a78a49eee1addda267e0fc`, migration
`0080_source_components`, 114 live PDFs, one trashed PDF, 1,628 source pages, and 1,089,546 source
components. All experiments used copies.

## 2. Exact commit audited

- H1b.1 commit: `1f65f8e90c92263d80c0991601a5b805dca568e2`
- Tree: `ce2dbf03d4d318e9eb1bad7e593426fa3d13e1eb`
- Parent: `b2efbaf1a1585a7c676905a9987a2fd5d58fcccd`
- H1b baseline: `a41266ba4850a17ce04af3480b7237197416574f`
- Migration head: `0081_source_representations`

Selected SHA-256 identities:

| Artifact | SHA-256 |
|---|---|
| 0081 migration | `f8b1b4b8866f5df0a9f6c1b88275930e99859b9acaeb9cae1d32edcaed58fd44` |
| source-component schema | `529a778e87cfafcdf5699d7451d527e884ebb43128298b0efce60decba8b7c40` |
| source-component repository | `4d078e07c92f67cd7eb67ad8c9c9e8128fe6886d31172bc85909a344e8db1a8f` |
| source-representation repository | `dff79e0c2d7af20c1924bcc0f5409524f0044840857a5cc2ee2f0627632650c2` |
| source-component builder | `6a6cc631f11d77a2e59ce605df8281143ce21ed13c142db9809a5fd3fbf0eda3` |
| ingest seam | `42c494c146e379f6af76d0c1b4936922c523e2b4d004674c63b720971aa9d8aa` |
| backfill tool | `74f542989f4bafa556fef6631d5ecad9c7d0f69a799d735e16108078df630667` |
| evidence-unit provenance specification | `6c16b7d848e2d900dd1e76abd8f3d344acb546c6c1c450fdc2aa4f74d4f343ff` |
| prior H1b research harness | `c20c600cbe6279f0bf03abed9ac2b361cb161bc664d31e4f53c69c01431d3847` |
| independent H1b.1 harness | `cd11924583b9922efb910a5a66bba6663c06be615633511d2f417c306e55da9d` |

## 3. Currentness contract

Most of the contract is correctly enforced. Independent one-field mutations showed the following
were excluded from the current set: `truncated`, `incomplete`, `failed`, absent status, live checksum
mismatch, requested derivation mismatch, missing page, missing component, written-page mismatch,
written-component mismatch, and `skipped_pages > 0`.

However, `_current_source_stmt()` does not compare `source_representations.extraction_tool` or
`extraction_version` with the persisted graph, nor does it ensure each persisted page's checksum,
derivation, or extraction identity agrees with the representation. Each of these six deliberately
incoherent graphs still returned **current**:

- representation extraction-tool mismatch;
- representation extraction-version mismatch;
- page checksum mismatch;
- page derivation mismatch;
- page extraction-tool mismatch;
- page extraction-version mismatch.

This is not merely a hypothetical “current installed PyMuPDF” policy question. Even internal
representation-to-page disagreement is accepted. The status/count envelope can therefore describe
one source identity while the persisted graph carries another. That fails the preregistered minimum
currentness invariant.

`expected_pages` is correctly interpreted only as persistence completeness relative to deterministic
extractor output. A seed-20260905 five-PDF direct check found PDF page count = `extract_pdf()` source
page count = representation `expected_pages` for all five cases (9, 10, 13, 11, and 17 pages). This
small check does not turn `expected_pages` itself into independent PDF-page proof.

## 4. Original truncation-bug reproduction

The original failure class is repaired.

- With the research-only cap reduced to zero, the two-page representation was marked `truncated`,
  wrote 0/2 pages, and was non-current.
- Ordinary backfill did not skip it; it reprocessed one attachment into a complete/current graph
  with two pages and nine components.
- In the last-page variant, page 1 fit and page 2 crossed the cap. The receipt remained
  `truncated` with 1/2 pages and was non-current even though this is the arithmetic edge case that
  previously could masquerade as complete.
- A normal rerun repaired the last-page case to current.

Partial graph persistence is therefore honest and repairable rather than silently current.

## 5. Interruption / failure semantics

Independent fault injection covered interruption before the first page write, after partial graph
persistence, immediately before the final marker, and during component SQL persistence. Every case:

- raised as injected;
- was non-current before repair;
- became current after an ordinary rerun;
- converged to the exact same canonical logical-tree hash as the uninterrupted control.

For the subtle rollback case, a previously complete/current graph survived a failing forced rebuild
inside a savepoint. Its logical tree remained exact, currentness remained true, and
`record_source_failure()` correctly declined to overwrite the restored valid status with `failed`.

The four states remain meaningfully distinct: only `complete` can be current; `truncated` records a
cap; `incomplete` records an unrepresentable/no-page/page-gap result; `failed` records a derivation or
persistence exception where no valid graph survived. All three non-complete states were repairable.

## 6. Migration / backfill behavior

Migration from the coherent H1b database was conservative:

| Stage | Complete | Truncated | Incomplete | Failed | Absent/current |
|---|---:|---:|---:|---:|---:|
| Before 0081 | n/a | n/a | n/a | n/a | 114 absent |
| Immediately after 0081 | 0 | 0 | 0 | 0 | 114 absent / 0 current |
| First ordinary backfill | 114 | 0 | 0 | 0 | 0 absent / 114 current |
| Second ordinary backfill | 114 | 0 | 0 | 0 | 0 absent / 114 current |

Immediately after migration, all 1,089,546 old rows had null `component_path` and `geometry_state`,
and no source-representation row existed. Thus old H1b graphs were not promoted optimistically.

The first backfill wrote exactly 1,628 pages and 1,089,546 components for 114 live PDFs, with zero
missing files, checksum mismatches, no-structure cases, truncations, incompletes, or failures. The
single trashed PDF remained outside live coverage. The second run skipped all 114 current
attachments, processed zero, wrote zero, and completed in 1.416 seconds.

## 7. Stable locator validation

The durable reference is correctly modeled as attachment-instance context plus a content-level
`SourceLocator`. The locator contains checksum, extraction tool/version, derivation version, page,
and inspectable component path; it contains no source-page/component surrogate ID.

An unchanged destructive rebuild changed every sampled component surrogate ID while preserving the
exact logical tree and every locator. The pre-rebuild locator resolved to the same component path
after rebuild. Altered checksum, extraction version, and derivation version locators all failed
closed.

Independently deriving paths from persisted parent links, component kinds, `sorted_order`, and
`child_order`—without calling the production path helper—produced:

- rows compared: **1,089,546**;
- exact matches: **1,089,546**;
- mismatches: **0**;
- duplicate independently derived paths within a page/source namespace: **0**.

The materialized paths are therefore exact across the complete live corpus.

## 8. Duplicate-source versus true-collision analysis

The preregistered canonical payload included page identity/dimensions/rotation/coordinate system,
component and parent paths, kind, exact text, bbox, native/sorted/child ordering, font/size/flags,
line direction, and writing mode; it excluded surrogate IDs.

The full live scan found one checksum shared by two attachment instances:

- byte-identical source groups: **1**;
- attachment instances in that group: **2**;
- component rows across both attachments: **6,684**;
- same locator key + same canonical payload duplicates: **3,342**;
- same locator key + different canonical payload: **0**.

This is duplicate content identity, not a collision. The separate `attachment_id` argument to
resolution distinguishes the two Callosum attachment instances. No true locator collision was
observed.

## 9. Surrogate-ID reuse result

The surrogate hazard is real. In a controlled destructive rebuild whose logical content changed,
one old `source_component.id` was reused for a different canonical payload. Conversely, with a
co-resident attachment forcing allocation movement, every ID changed across an unchanged rebuild.
Therefore a surrogate can be unstable or, worse, stably resolve to different content. Neither the
implemented locator nor the revised design contract treats it as durable provenance.

## 10. Geometry-validity audit

Independent row-by-row classification used persisted raw coordinates and page dimensions, did not
call the production helper, did not normalize coordinates, and retained the frozen 2.0-point
tolerance.

| Result | Count |
|---|---:|
| Compared | 1,089,546 |
| Exact production/independent state agreement | 1,089,546 |
| Disagreements | 0 |
| Valid | 1,088,070 |
| Invalid | 1,476 |
| Unknown | 0 |
| Inverted | 363 |
| Out of page beyond 2.0 points | 1,113 |
| Degenerate zero-area | 3 |

All three zero-area observations were image components. They are stored `valid` by the committed
contract. This is **not** manufactured into an H1b.1 failure. H1c spatial association should exclude
or separately qualify zero-area regions until their usefulness is demonstrated; they cannot support
area-overlap reasoning as ordinary rectangles.

The committed classifier correctly preserved/marked ordinary, inverted, missing/partial,
out-of-page, and infinity cases. It has one fail-closed defect: `NaN` passes both comparison clauses
and is classified `valid`. SQLite then persists that NaN coordinate as NULL while leaving
`geometry_state='valid'`. A malformed observation can therefore become a partial stored bbox that
explicitly claims validity. Non-finite geometry was preregistered as clearly invalid, so this fails
the H1c geometry gate even though no non-finite value was found in the current corpus.

Raw finite inverted/out-of-page/zero-area coordinates remained unmodified. Missing/partial input
became all-null with `unknown`; infinity remained present and `invalid`.

## 11. Currentness-query cost

On 114 representations and 1,089,546 components, after one warm-up, ten executions of
`attachments_with_current_source()` returned 114 IDs:

- minimum: 162.66 ms;
- median: 169.72 ms;
- maximum: 192.42 ms.

This is bounded and acceptable for backfill/currentness use. No optimization is justified by this
audit.

## 12. Raw chunk / embedding / vector invariants

Canonical ordered hashes before migration, after migration, and after full backfill were identical:

| Data | Rows | SHA-256 |
|---|---:|---|
| chunks | 23,875 | `c0b4d848a5b0178ad868a6d8d96ca8002a61c3d23bc9d31a30157f41d0fa6e97` |
| embedding metadata | 24,134 | `f91de983ec3dc4afa11231be4ae18f79b986265a128af367471d46bd552e7d01` |
| attachments/checksums | 115 | `6ee7c19275e3007989493682dfa672b954d58b5049bb835e842c564acbedef84` |
| sqlite-vec row-ID map | 24,032 | `d9ef326667658fc474b388a5a02de054ea96f49700ef8363ba89fe1f3955c3b9` |
| sqlite-vec vector blobs | 26 chunks | `ab474f0468b434dc518fd77ad1648ea05f33c369fd560fcf590878b1fcdd35db` |

No authoritative retrieval data changed.

## 13. Retrieval non-coupling

The ten-query frozen vector probe was byte-for-byte identical before and after H1b.1:

- ordered results and distances identical: **yes**;
- before/after receipt hash:
  `884470634b09f8bbb8938a08788107c7a064e920290f9e8667e05ab4eb426025`.

Static reference inspection found H1b.1 fields only in the structural builder, schema, persistence
repositories, ingest seam, and backfill/provenance surfaces. No Ask, retrieval, generation, prompt,
provider, or verifier path reads them. The tracked AST non-coupling tests also passed. The H1b.1
substrate remains non-load-bearing.

## 14. Evidence-form contract review

The revised design-only contract correctly requires future assembled evidence to carry:

- attachment-instance identity;
- source checksum;
- extraction tool/version;
- derivation version;
- page and component path;
- per-component role and assembly order;
- assembly strategy/version.

It explicitly rejects `source_component_id` as durable identity. Character offsets remain honestly
deferred. `evidence_form=assembled` is still unimplemented; `canonical_text_contains`, production
verification, prompts, providers, and thresholds are unchanged. No assembled string can currently
masquerade as a contiguous verbatim quote.

## 15. H1c gate decision

| Gate condition | Result |
|---|---|
| 1. Truncated cannot be current | PASS |
| 2. Incomplete cannot be current | PASS |
| 3. Failed cannot be current | PASS |
| 4. Interrupted cannot be current | PASS |
| 5. Ordinary rerun repairs incomplete states | PASS |
| 6. Complete live representations become current | PASS — 114/114 |
| 7. Failed rebuild preserves rollback-restored valid graph | PASS |
| 8. Durable locator survives destructive rebuild | PASS |
| 9. No same-key/different-content collisions | PASS — 0 |
| 10. Duplicate-byte attachments retain attachment provenance | PASS |
| 11. Invalid geometry unusable; raw geometry intact | **FAIL — NaN becomes NULL + `valid`** |
| 12. Chunks/embeddings/vectors/retrieval unchanged | PASS |
| 13. No H1b.1 field is load-bearing | PASS |
| Mandatory minimum currentness identity contract | **FAIL — six identity-drift cases remain current** |

**H1c GATE = BLOCKED.**

Exact blockers:

1. currentness verifies counts but not representation-to-page source/extraction/derivation identity;
2. non-finite NaN geometry is accepted as valid and becomes a partial NULL bbox at persistence.

The original truncation blocker is fixed. These are narrower hardening defects discovered by the
independent negative tests; neither invalidates H1b's high corpus fidelity.

## 16. Unresolved risks

- The live corpus contains no non-finite geometry, so the NaN defect is adversarial rather than a
  present-data corruption finding. It still violates fail-closed behavior needed before H1c.
- Three zero-area image regions are not H1b.1 failures, but H1c should not use them as ordinary
  area-bearing rectangles without a bounded safety rule.
- `expected_pages` is extractor-relative. The five-file direct check passed, while complete
  independent PDF/extractor fidelity remains established by the prior H1b audit rather than rerun.
- The currentness function validates the requested derivation string but has no explicit policy for
  deciding which extraction runtime version should be considered globally current. At minimum it
  must reject internal representation/page disagreement; any runtime-upgrade invalidation policy is
  a separate explicit design choice.
- The currentness count query is acceptable for backfill but should not be placed on a request-hot
  path without separate measurement.
- Repository-wide Ruff remains red with the same 20 findings in `tools/evidence_hygiene/*.py` at the
  H1b baseline, target parent, and H1b.1 target. Ruff formatting also remains red: 11 pre-existing
  evidence-hygiene files at H1b; 12 files at the parent/target because the merged prior Codex H1b
  research harness is also unformatted. H1b.1 introduced no new check or format failure relative to
  its parent. These unrelated baselines are not part of the H1c decision.

## 17. Smallest justified next step

Make one narrow H1b.1 hardening follow-up, subject to maintainer approval:

1. strengthen currentness so the representation envelope and every persisted page agree on source
   checksum, extraction tool/version, and derivation version, while preserving the existing live
   checksum, status, and count checks;
2. classify all non-finite coordinates as invalid before persistence, without normalizing or
   rewriting the raw finite observations;
3. add the exact adversarial regressions from this audit and rerun this focused gate only.

For H1c, separately require `geometry_state=valid` **and** non-zero area for any algorithm that needs
rectangle overlap; treat that as an H1c qualification, not a retroactive H1b.1 failure.

Do not begin reconstruction, evidence-unit persistence, retrieval coupling, or model/provider work
until the two blockers pass a focused rerun.

Validation completed before freeze:

- focused source-representation/source-component/migration suite: **94 passed**;
- full corpus migration/backfill/idempotence: passed as reported above;
- independent adversarial and corpus harness: passed execution, with the two reported negative
  findings;
- research harness Ruff check and format check: passed;
- target-vs-parent `git diff --check`: passed;
- ignored receipt manifest SHA-256:
  `cf50d58d49bd46ea7f964acf043e2af9c4b17c796ffca87e2a457d5da4c3a2b3`;
- principal ignored receipts: adversarial
  `d660a538fdce86dfd8a41524a77e967e48ba946f5241dc209d82f86bb55b4a6c`, corpus
  `69fdcd401a46ac27f2876150d61484be22c92727986b764e0083a638f2deeb00`, retrieval
  `8b8ac6b474cc40865935be99f7939e938421290fd16a2d032ee4539341926e07`.

## 18. Post-hoc Claude comparison

Not performed before the independent findings freeze. This section will be appended only after the
independent report and harness are committed.
