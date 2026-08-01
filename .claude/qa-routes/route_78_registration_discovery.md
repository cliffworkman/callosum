<!-- qa-coverage
api: GET /papers/{paper_id}/registration-discovery/preview, POST /papers/{paper_id}/registration-discovery, GET /registration-discovery/{job_id}, GET /papers/{paper_id}/registration-links, POST /papers/{paper_id}/registration-links/{link_id}/confirm, POST /papers/{paper_id}/registration-links/{link_id}/reject
fe: 08h_methods_transparency.jsx
-->

# ROUTE 78 — Registration discovery and candidate confirmation

**Tier:** 2 local-stateful + explicit public-metadata egress
**Goal:** Exercise candidate discovery without converting a metadata hit into an automatic or epistemic verdict.

## Environment

Use a paper with a printed OSF registration link, a paper DOI whose DataCite record has a typed relation to an OSF
StudyRegistration, and a false candidate with overlapping title/authors. Keep a browser network log. Use hermetic
fixtures for CI; live OSF/DataCite checks are an optional provider-health spot check, not a test dependency.

## Standing assertions

- Opening **Checklists → Transparency signals** or **Synthesize → Meta-Preregistration** performs no OSF/DataCite request.
- **Find registration** first shows exactly what will be sent and what remains local. Cancel sends nothing.
- No abstract, chunk, PDF/registration text, notes, annotations, or synthesis appears in outbound payloads.
- Every candidate shows provider, identifier/DOI, status/date/contributors where returned, and specific match evidence.
- Wording is “Explicitly linked,” “Probable match, confirm,” or “Possible match, inspect”—never correct/verified,
  compliant/noncompliant, risk, integrity, or an author judgment.
- A candidate creates no attachment. Confirming it creates no attachment and downloads no artifact.
- “No candidate located” includes the non-absence caveat.
- Provider errors are visible; one provider's failure does not remove another's candidate.
- Console/page error budget is zero; ordinary article synthesis/search still excludes preregistration chunks.

## Steps

1. Open a selected paper's Transparency panel. Confirm no registry request, inspect any local printed reference, then
   use **Open Meta-Preregistration** and verify the dedicated Synthesize tab opens after Critique.
2. In Meta-Preregistration click **Find registration**; verify the disclosure, then Cancel and confirm no off-machine request.
3. Repeat and choose **Search OSF and DataCite**. Confirm the Status popover shows Registration discovery while active.
4. Inspect direct-link, typed-related-identifier, and contextual candidates. Compare the visible evidence to fixture
   metadata; verify no score and no auto-selection.
5. Open a candidate externally. Confirm the app records no link/attachment merely from navigation.
6. Confirm one candidate. Reload: it remains “Registration linked, not acquired,” with no registration attachment.
7. Dismiss another candidate. Search again normally: it stays hidden. Request the explicit fresh search: it returns.
8. Simulate OSF failure with a DataCite/direct result. Confirm the error and surviving candidate are both visible.
9. Use a withdrawn candidate and confirm its status is visible and confirmation disabled.
10. Use a paper with no returned candidates. Confirm the UI says the searched routes found none, not that no
    registration exists, and offers manual reference/local PDF fallback.

## Pass criteria

Discovery is opt-in and metadata-only; every result is inspectable evidence, never an adjudication; confirmation and
acquisition remain separate; dismissal persists; failures are isolated; and document scope remains intact.
