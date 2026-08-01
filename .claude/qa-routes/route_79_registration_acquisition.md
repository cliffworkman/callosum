<!-- qa-coverage
api: POST /papers/{paper_id}/registration-links/{link_id}/acquire, GET /registration-acquisition/{job_id}, GET /papers/{paper_id}/registration-versions, GET /papers/{paper_id}/registration-versions/{version_id}
fe: 08h_methods_transparency.jsx
-->

# ROUTE 79 — Confirmed registration acquisition and version preservation

**Tier:** 2 local-stateful + explicit selected-artifact download
**Goal:** Verify that acquisition is a separate, bounded action and preserves exactly what later comparison will use.

## Environment

Use hermetic fixtures for an OSF structured registration, a modern AsPredicted PDF, a legacy AsPredicted verification
page, a local PDF, and OSF/AsPredicted error cases. Keep a browser network log.

## Steps

1. Open Transparency on a paper with a confirmed link. Verify “Registration linked, not acquired” and no provider
   request on open/reload.
2. Click **Acquire registration**. Verify only the selected provider is contacted and Status shows acquisition.
3. For OSF, inspect the managed Markdown attachment and version detail: question IDs/labels/order, schema version,
   responses, amendment metadata, contributors/resources/files metadata, retrieval time, and hash are preserved.
4. For AsPredicted, verify a valid PDF is stored and numbered questions are exposed where readable. Exercise the
   legacy page and verify only its same-origin PDF is followed.
5. Verify the panel reads “Registration attached, not compared,” exposes the hash/date, and makes no claim about
   prospective timing, adherence, compliance, or integrity.
6. Click **Check for an updated version** with identical bytes: no duplicate attachment/version appears. Change the
   fixture bytes and repeat: a second immutable version appears and the first remains inspectable.
7. Attach a local preregistration PDF. Verify a `manual-local` version exists and no network request occurs.
8. Exercise invalid MIME/PDF, oversize, timeout, redirect-to-another-origin, withdrawn, unavailable, and embargoed
   cases. Confirm a visible error and unchanged prior data.
9. Run the document-scope structural tests: ordinary paper chunks/synthesis exclude all registration versions, while
   exact attachment retrieval returns the selected registration only.

## Pass criteria

Acquisition is explicit and fixed-provider; content is bounded, validated, hashed, and versioned; failure cannot
corrupt prior state; panel load has no egress; and acquisition is never presented as a comparison or verdict.

