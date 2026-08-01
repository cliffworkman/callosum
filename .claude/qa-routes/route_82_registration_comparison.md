<!-- qa-coverage
api: POST /papers/{paper_id}/registration-comparisons, GET /registration-comparisons/jobs/{job_id}, GET /papers/{paper_id}/registration-comparisons, GET /papers/{paper_id}/registration-comparisons/{run_id}, POST /registration-comparison-rows/{row_id}/review
-->

# ROUTE 82 — Evidence-bound registration comparison and staleness

**Tier:** 2 local-stateful + background local embeddings
**Goal:** Verify the persisted crosswalk is evidence, not an adjudication.

## Steps

1. Compare the curated fixtures: exact alignment; different sample size; either/both exclusion threshold; changed
   primary outcome; planned outcome not located; newly reported primary outcome; disclosed deviation; underspecified
   registration/publication; directional/nondirectional hypothesis; and an unresolved semantic pair.
2. Verify each row shows registration field/value/evidence/source and publication value/evidence/source whenever that
   side is available, plus status, explanation, uncertainty, search scope, registration hash/version, article checksum,
   and pipeline versions.
3. Verify unresolved semantic pairs are `not comparable`, not changed. Verify “not located” rows list sections,
   whole-article expansion, supplement state, and the non-detection-is-not-proof statement.
4. Exercise prospective, unclear, after-collection-began/ended, and after-analysis timing fixtures. Verify cautious
   “supported”/“appears” language and that OSF alone does not cause the UI to say preregistration.
5. Mark one row reviewed, dismiss another, and add a note. Reload and verify state persists without changing evidence.
6. Change the registration hash, article attachment/chunk/extraction version, included supplement, and pipeline version
   in turn. Verify stale reason(s) appear, prior evidence/reviews remain, and no stale run appears current.
7. Verify Status shows the background comparison job. Simulate failure and verify no partial run/rows are stored.
8. Inspect response/schema/UI for forbidden aggregate fields/wording: no compliance/integrity/risk/deviation score,
   no author judgment, no positive certificate when no flags surface.

## Pass criteria

The crosswalk is versioned, paired-evidence-first, reviewable, and stale-aware; bounded statuses stay cautious; no
document content leaves the machine; and there is no paper/author verdict or overall score.

