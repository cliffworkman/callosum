# Security and privacy audit — Meta-Preregistration workspace relocation

**Date:** 2026-08-01
**Increment:** 434
**Result:** PASS

## Scope

Relocate the existing registration discovery, acquisition, manual-source, and comparison controls from Transparency
to **Synthesize → Meta-Preregistration**, and align their presentation with Settings. This increment changes frontend
composition/navigation/styles only; it adds no endpoint, provider, payload, dependency, storage field, or network
capability.

## Findings

- Opening Transparency now mounts less registration workflow code and continues to run only the local transparency
  detector. Its handoff performs workspace/tab state changes only.
- Opening Meta-Preregistration reads the selected paper plus already-persisted candidate/version/comparison state from
  Callosum's local API. It does not invoke discovery, acquisition, or comparison POST endpoints.
- Registry discovery still requires the existing metadata preview and explicit **Search OSF and DataCite** action.
  Acquisition still requires a confirmed link and explicit action. Comparison remains a separate explicit action.
- Manual URL/DOI saving, local PDF attachment, and attachment-role changes retain their existing local-only behavior.
- No paper/registration content is newly exposed off machine. No credentials, cookies, arbitrary fetch URL, redirect,
  download limit, timeout, content-type, filename, or checksum behavior changed.
- Selected-paper scope is inherited from the workspace context; WIP mode provides no stale Library paper id.
- Error, stale, unavailable, and incorrect-match states remain visible and no action auto-attaches a candidate.

## Regression pins

Frontend assembly tests prove the rich workflow is absent from `TransparencyPaper`, present only in the dedicated
workspace, ordered after Critique, and still keeps acquisition/comparison POSTs outside mount effects. Existing
backend/provider security and hermetic registration suites remain applicable without modification.

## Rollback

Revert Increment 434 and rebuild the frontend. The operation is UI-only and requires no data or schema rollback.
