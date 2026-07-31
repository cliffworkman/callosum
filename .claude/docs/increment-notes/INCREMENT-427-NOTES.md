# Increment 427 — explicit registration discovery and candidate matching

**Date:** 2026-07-31
**Status:** implemented

## Outcome

Readers can explicitly search public OSF and DataCite metadata for a selected paper, inspect why each registration
candidate surfaced, confirm a link, or dismiss it. Discovery never runs when the Methods panel opens, never sends
document text, never auto-attaches a candidate, and never treats a search miss as evidence that no registration
exists. Confirmation records a relationship only; acquisition is Increment 428.

## Architecture and decisions

- `registration_discovery` is a small provider registry with isolated reports. One provider exception becomes a
  visible error report and cannot discard another provider's candidates or mutate existing records.
- The explicit per-run consent preview names the outbound fields. Current providers send paper DOI/title and detected
  registration identifiers. Author names/publication year are used only for local comparison of returned metadata.
- `DirectReferenceProvider` converts already-known AsPredicted, ClinicalTrials.gov, PROSPERO, URL, and other manual
  references into explicit-linkage candidates without any network request.
- `OsfRegistrationProvider` resolves a known registration GUID or the documented registrations relationship on a
  known OSF node. It reads contributors, DOI identifiers, status, schema name, and paper resources. Empirical checks
  on 2026-07-31 found no working documented OSF reverse lookup from publication DOI; unsupported filters returned 400
  and were not simulated.
- `DataCiteRegistrationProvider` resolves a printed registration DOI, queries typed related identifiers for the paper
  DOI, and performs a bounded StudyRegistration title query. Reported relation types are retained verbatim; even an
  exact related DOI is shown as linkage evidence, not a correctness verdict.
- Linkage classes are `explicit-linkage`, `strong-contextual-match`, and `similarity-candidate`, rendered as
  “Explicitly linked,” “Probable match, confirm,” and “Possible match, inspect.” No opaque confidence score exists.
- `paper_registration_links` is a dedicated additive table. Uniqueness is per paper/provider/external identifier,
  allowing one registration to link to multiple papers and a paper to retain multiple candidates. It stores metadata,
  evidence, source snapshot, link status, and future attachment/hash fields without forcing one-to-one cardinality.
- Rejected candidates stay hidden on ordinary repeat searches and reappear only when the user requests a fresh search.
  Confirmed candidates are not acquired or assigned an attachment in this increment.
- Local uploaded/reclassified preregistration attachments create a confirmed `manual-local` link so manual and
  discovered sources converge on the same downstream seam.

## Epistemic boundary

- Candidate means “inspect this possible relationship,” not “correct registration.”
- Registry status is reported as public, embargoed, withdrawn, unavailable, or provider-specific metadata; it does
  not establish prospective timing. The UI uses “registration” until later timing comparison supports otherwise.
- No compliance/integrity/risk score, author judgment, paper verdict, or positive certificate is produced.
- An empty result says only that the searched metadata routes did not locate a candidate.

## Security and privacy

Audit: `.claude/security-audits/2026-07-31_registration-discovery.md` — **PASS**.

Provider URLs are constructed from fixed HTTPS API origins and normalized identifiers, redirects are disabled,
responses are capped at 5 MiB, requests time out after 20 seconds, and no credentials/cookies are sent. Provider
fixtures are hermetic. No arbitrary URL is fetched, including pasted manual URLs and AsPredicted links.

## Rollback

Revert Increment 427's code/tests/docs commit. Migration 0060 is additive and deliberately has a no-op downgrade to
avoid deleting user confirmations/rejections. Leaving the orphaned table is harmless. Before manually dropping
`paper_registration_links`, export user decisions and attachment associations. Keep Increments 425–426 while any
registration attachment/reference remains in use.

## Verification

- Provider/API/manual-link focused suite: 18 passed.
- Frontend/discovery/reference/health/migration/status regression gate: 106 passed.
- Full suite: **1740 passed, 1 skipped** in **862.03s** (`pytest -n auto -q`).
