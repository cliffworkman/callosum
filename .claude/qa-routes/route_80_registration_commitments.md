<!-- qa-coverage
api: POST /papers/{paper_id}/registration-versions/{version_id}/commitments/extract, GET /papers/{paper_id}/registration-versions/{version_id}/commitments
-->

# ROUTE 80 — Canonical registration commitment extraction

**Tier:** 1 local deterministic
**Goal:** Verify that a registration becomes inspectable field-level evidence without a verdict or hidden egress.

## Steps

1. Acquire an OSF fixture containing hypotheses, outcomes, sample size, exclusions, model, and amendment metadata.
2. Run commitment extraction. Verify every row names a canonical field, verbatim evidence, question/section, method,
   confidence, registration hash, version, and attachment locator; numeric sample size is structured where explicit.
3. Repeat with AsPredicted and verify numbered questions map deterministically without one general document prompt.
4. Attach a local PDF with headed exclusions/outcomes plus unrelated prose. Verify only explicit mappable passages
   surface, local mappings carry uncertainty, and no provider/network request occurs.
5. Put contradictory tempting text in the article attachment. Verify registration extraction reads only the exact
   registration attachment.
6. Re-run the same extractor version and verify no duplicate rows. Verify another paper cannot address the version.
7. Inspect an unmappable/underspecified registration. Confirm the UI/API does not invent a commitment or positive
   completeness statement.

## Pass criteria

Commitments remain local, versioned, source-anchored extraction proposals; unknown text stays unknown; no score,
adherence claim, author judgment, paper text, or registration content leaves the machine.

