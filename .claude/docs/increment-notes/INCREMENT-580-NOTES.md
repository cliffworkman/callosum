# Increment 580 — H1b.2: source-envelope coherence and non-finite geometry

**Not H1c.** This increment closes exactly two source-substrate defects found by the independent
H1b.1 audit. It does not reconstruct evidence, alter retrieval, change embeddings, add a migration,
or make any source-substrate field load-bearing.

---

## Why this increment exists

H1b.1 made a source representation current only when its completeness record, attachment checksum,
derivation identity, page count, and component count all agreed. An independent audit found two
remaining fail-open cases:

1. A representation envelope and one or more persisted `source_pages` rows could disagree on
   `source_checksum`, `extraction_tool`, `extraction_version`, or `derivation_version`, yet the graph
   still read as current. Six adversarial identity-drift cases demonstrated the gap.
2. IEEE `NaN` passes none of the ordinary less-than/greater-than comparisons in the geometry
   classifier, so it fell through as `valid`. Python's SQLite binding then persisted that NaN as
   `NULL`, leaving a partial bbox whose materialized state falsely claimed validity.

The live validation corpus contained neither defect. They are substrate-integrity failures rather
than retrieval regressions, and both must fail closed before any later H1c association research can
safely depend on the substrate.

---

## Implemented

### Internal envelope/page identity coherence

`source_representation_repo._current_source_stmt()` retains every H1b.1 currentness clause and adds
one bounded anti-condition:

```text
current only if there exists no persisted source_page whose
    source_checksum
    extraction_tool
    extraction_version
    derivation_version
disagrees with its source_representations envelope
```

The check groups disagreements by attachment and scans `source_pages` (1,628 rows in the validation
corpus), not `source_components` (~1.09 million rows). One incoherent page invalidates the complete
multi-page representation. A coherent representation remains current.

This is deliberately **internal graph/envelope coherence**. It does not compare historical rows to
the currently installed PyMuPDF/runtime version and does not establish a global extractor-upgrade
invalidation policy.

### Explicit non-finite geometry rejection

`classify_geometry()` still handles absent/partial bboxes first, returning `unknown/missing`. Only
after that guard does it call `math.isfinite()` on all four present coordinates. Any NaN or infinity
now returns:

```text
geometry_state = invalid
reason = non_finite
```

Raw observations are not normalized, clamped, swapped, zeroed, or repaired. SQLite may still be
unable to represent a NaN coordinate and store it as `NULL`, but the independently materialized
judgment can no longer claim that row is valid.

Finite behavior is unchanged:

- inverted boxes remain `invalid/inverted`;
- boxes beyond the frozen 2.0-point page tolerance remain `invalid/out_of_page`;
- ordinary finite boxes remain valid;
- partial/missing boxes remain unknown;
- zero-area boxes remain outside H1b.2 semantics and are deferred to bounded H1c qualification.

---

## No migration

H1b.2 changes one query predicate and one pure classifier. Migration head remains
`0081_source_representations`; no schema or stored-data rewrite is required.

---

## Focused regression coverage

Identity-coherence tests cover:

- representation `extraction_tool` mismatch;
- representation `extraction_version` mismatch;
- page `source_checksum` mismatch;
- page `derivation_version` mismatch;
- page `extraction_tool` mismatch;
- page `extraction_version` mismatch;
- a coherent complete control;
- one incoherent page invalidating a multi-page graph;
- preservation of the pre-existing completeness/count checks.

Geometry tests cover NaN independently in x0/y0/x1/y1, positive and negative infinity, the real
SQLite NaN-to-NULL persistence seam, inverted and out-of-page finite boxes, ordinary finite boxes,
missing/partial boxes, the frozen tolerance, and unchanged zero-area behavior.

Focused source/component/migration suites: **111 passed**. Adjacent PDF extraction, H1a structure,
GROBID pipeline/TEI, and chunk-filtering suites: **81 passed**. Explicit non-coupling parameterization:
**9 passed**. Tach and the 593-file line-budget gate pass. Scoped Ruff check and format check pass.

Full offline suite: **2,950 passed, 4 skipped, 6 failed** in 10m53s. The six failures are the known
pre-existing Overview qualification freeze cascade: the frozen manifest rejects the unchanged
`app/backend/llm/providers.py` working-tree CRLF bytes. That file is outside this increment, and no
H1b.2 or adjacent source/PDF test failed. The unrelated baseline is recorded, not repaired here.

---

## Corpus validation

Validation used two private copies of the coherent H1b.1 database snapshot. The untouched baseline
SHA-256 is:

```text
faaf8a28e7cc985caeffe65e90ec465cf905c5d14550051cb01d3ead6ac7af3a
```

The target was force-rebuilt from the original PDFs under H1b.2 in three disjoint validation shards,
then run once through the ordinary non-force backfill path.

| Measure | Result |
|---|---:|
| Live PDF attachments | 114 |
| Complete/current | **114 / 114** |
| Truncated / incomplete / failed | **0 / 0 / 0** |
| Ordinary rerun skipped as current | **114 / 114** |
| Soft-deleted PDF attachments | 1 (accounted separately) |
| Persisted pages | 1,628 |
| Persisted components | 1,089,546 |
| Page/envelope checksum mismatches | **0** |
| Page/envelope extraction-tool mismatches | **0** |
| Page/envelope extraction-version mismatches | **0** |
| Page/envelope derivation-version mismatches | **0** |

Independent geometry recomputation over all live components found:

| Geometry observation | Count |
|---|---:|
| Non-finite | **0** |
| Missing/partial marked valid | **0** |
| Inverted finite | 363 |
| Out-of-page finite (> frozen 2.0 pt tolerance) | 1,113 |
| Zero-area (reported, not reclassified) | 3 images |

The canonical logical raw-coordinate hash (attachment/source/page/component path/kind/coordinates,
excluding replaceable surrogate IDs and timestamps) is identical before and after:

```text
6cdff2f465f581b4c4a61083887d4829d94b44b2353d5ef4220e43415e25f67a
```

---

## Raw-data and retrieval invariants

| Data | Rows | SHA-256 before = after |
|---|---:|---|
| `chunks` complete rows/text | 23,875 | `c0b4d848a5b0178ad868a6d8d96ca8002a61c3d23bc9d31a30157f41d0fa6e97` |
| `embeddings` metadata | 24,134 | `f91de983ec3dc4afa11231be4ae18f79b986265a128af367471d46bd552e7d01` |
| `attachments` identities/checksums | 115 | `6ee7c19275e3007989493682dfa672b954d58b5049bb835e842c564acbedef84` |
| sqlite-vec row-ID map | 24,032 | `d9ef326667658fc474b388a5a02de054ea96f49700ef8363ba89fe1f3955c3b9` |
| sqlite-vec vector blobs | 26 | `ab474f0468b434dc518fd77ad1648ea05f33c369fd560fcf590878b1fcdd35db` |

The same ten stored vectors were used as query vectors against the untouched baseline and rebuilt
target. Ordered top-20 IDs and hexadecimal distances were exactly equal. Both canonical receipts:

```text
884470634b09f8bbb8938a08788107c7a064e920290f9e8667e05ab4eb426025
```

The older `5cb20a94...` value is not treated as a magic acceptance hash: its producing wrapper is
not present in this worktree, so the serialization difference cannot be reconstructed here. This
run deliberately uses the frozen Codex receipt serialization on both sides; under that one identical
probe and serialization, baseline equals H1b.2 exactly.

Nine retrieval/generation modules remain explicitly guarded against references to
`source_representations`, `source_representation_repo`, `component_path`, `geometry_state`, or
`SourceLocator`. The source substrate remains non-load-bearing.

---

## Currentness cost

On the complete target corpus (114 attachments, 1,628 pages, 1,089,546 components), 12 warm-query
measurements of H1b.2 currentness were:

```text
min 163.30 ms / median 177.37 ms / max 272.67 ms
```

To isolate the new coherence predicate from machine/load variance, the pre-H1b.2 and H1b.2 statements
were also interleaved on the untouched baseline in one process. Median changed from 168.83 ms to
169.92 ms (**+1.10 ms, about 0.65%**). The added page-level scan is bounded and not a material
regression.

---

## Explicitly unchanged / deferred

- No H1c reconstruction or association probe.
- No evidence-unit persistence.
- No retrieval, embedding, prompt, provider, verifier, or threshold change.
- No adjustment to the 2.0-point geometry tolerance.
- No zero-area policy.
- No global installed-extractor invalidation policy.
- No repair of unrelated pre-existing Ruff/CRLF failures.

H1b.2 implementation satisfies the two known blockers locally. Whether the bounded H1c research gate
opens is reserved for a separate independent audit.
