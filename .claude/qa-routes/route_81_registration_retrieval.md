<!-- qa-coverage
api: POST /papers/{paper_id}/registration-evidence/retrieve
-->

# ROUTE 81 — Section- and study-aware publication evidence retrieval

**Tier:** 1 local deterministic + local embeddings
**Goal:** Verify bounded, inspectable passage retrieval before any comparison classification.

## Steps

1. Use a paper with Introduction, Participants, Procedure, Analysis, Results, Discussion, and supplement chunks plus
   a separate registration attachment. Extract commitments for hypothesis, sample size, exclusions, outcome, model,
   and subgroup analysis.
2. Retrieve with supplements off. Verify each field starts in its documented compatible section families and every
   hit names attachment/chunk/page/bbox, section family, phase, and neighboring context.
3. Put the only model-family passage in Discussion. Verify the result records whole-article expansion; verify text
   saying “analysis” inside Discussion does not relabel that section.
4. Verify no registration/protocol/other attachment chunk can appear, even when it is a perfect semantic match.
5. Repeat with supplements on. Verify supplement hits and `supplements_searched=true`; turn it off and verify they
   disappear.
6. Use Study 1/Study 2. Verify a Study 1 commitment retrieves only Study 1 candidates. Remove or mismatch the label
   and verify `ambiguous` is visible rather than a silent cross-study match.
7. Use a commitment with no relevant passage. Inspect sections/expansion/supplement scope and the explicit
   non-detection-is-not-proof note. Confirm no comparison status or verdict is emitted.

## Pass criteria

Retrieval is local, field-bounded first, explicit about expansion/supplements/study ambiguity, source-anchored, and
structurally unable to read registration chunks as publication evidence.

