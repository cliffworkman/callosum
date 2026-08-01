# Registration workflow completion audit

**Date:** 2026-07-31
**Acceptance result:** PASS. Final repository-wide receipt: **1778 passed, 1 skipped**.

This matrix audits the requested workflow against repository evidence. It is a requirements trace, not a paper,
author, integrity, risk, or compliance assessment.

| Acceptance area | Implementation evidence | Hermetic acceptance evidence |
|---|---|---|
| Document-scope invariant first | controlled roles and explicit attachment/role retrieval in `document_roles.py` and `repository.py`; ordinary consumers migrated; unrestricted read visibly named | `test_document_scope.py`, structural ambiguous-call guard, single-primary legacy cases |
| Local reference extraction | OSF URL/DOI, AsPredicted, NCT, PROSPERO, contextual generic links/DOIs, and PDF annotations in `registration_references.py`; evidence/page/attachment retained | `test_registration_references.py`, including hidden “here,” duplicate identity, language-only, multiple and manual cases |
| Manual fallback | paste identifier, upload local PDF, or re-role an existing attachment; local PDF is separately chunked/versioned | reference/attachment API tests and role-change lifecycle test |
| Explicit discovery and consent | preview discloses fields; click sends DOI/title/detected IDs only; OSF, DataCite typed relations, direct known-reference seam; no document text | `test_registration_discovery.py` provider/consent/egress/error/fresh-search cases |
| Candidate uncertainty and multiplicity | explicit/contextual/similarity classes, no auto-attachment, persistent rejection, contradictory-date downgrade; paper-link schema permits many papers and many registrations | multiple-candidate, one-registration/multiple-paper, false-overlap, confirm/reject tests |
| Versioned acquisition | confirmed-only OSF structured or direct AsPredicted acquisition, manual-local seam, hash versions, deterministic rendering, original snapshots, bounded file manifest | `test_registration_acquisition.py` pagination, status, type, redirect, same/changed hash, restoration and no-egress cases |
| Canonical commitments | deterministic structured OSF/numbered AsPredicted mapping and cautious local-PDF mapping with verbatim evidence, locator, method/confidence, hash/version | `test_registration_commitments.py`, including amendment, existing-data timing and exact attachment scope |
| Section/study retrieval | compatible section families first, local semantic ranking, nearby context, optional expansion/supplements, study labels/ambiguity | `test_registration_retrieval.py` bounded, expanded, supplement, multi-study and source-receipt cases |
| Evidence-bound comparison | bounded statuses and deterministic numeric/outcome/exclusion/model/stopping/covariate/timing checks; unresolved semantics stay not-comparable | `test_registration_comparisons.py`, including empty extraction and one-sided evidence |
| Evidence completeness | paired evidence/locators where available; one-sided rows carry search scope, exact chunk/source receipt and non-detection warning | comparison persistence and frontend assembly tests |
| Timing language | prospective support, unclear/insufficient, after collection began/ended/analysis; existing-data and amendment timing; no registry-name shortcut to “preregistration” | timing comparator and UI wording tests |
| Inspectable UI | explicit state machine, version/config controls, paired responsive columns, raw/open-source actions, review/dismiss/note, incorrect-match recovery | `test_frontend_assembly.py`, QA route 83 |
| Persistence and staleness | hashes/checksums/pipeline versions/config/search scope/review state persisted; link, role, registration/article/supplement and pipeline changes stale prior runs | comparison API/staleness/role-change tests |
| Egress/security | local detection/comparison; fixed-origin, bounded, credential-free provider traffic only after the relevant user action; transactional status rechecks | registration security audits and provider negative-path tests |
| Evaluation | 18 curated cases mapped to separate dimensions and executable tests; no combined score | `test_registration_evaluation_manifest.py` and `.claude/evaluations/registration-workflow.md` |

## Deliberate boundaries

- OSF reverse lookup is not simulated when no documented relation is exposed. Exact paper references, OSF `papers`
  resources, registration identifiers, and DataCite typed relations are retained as distinct evidence routes.
- AsPredicted supports direct known identifiers/URLs, not undocumented reverse discovery.
- OSF file-provider and nested file metadata are preserved in a bounded manifest; only the deterministic structured
  registration artifact is imported automatically after confirmation. Related file bytes require a separate reader
  selection or local attachment so an arbitrary data/code directory is not silently downloaded.
- Comparison is local and deterministic. No external model sees article or registration content; future semantic
  mapping must use Callosum's existing explicit AI/egress gate.
- No clean crosswalk is a positive certificate, and no review-queue state is an author-level finding.
