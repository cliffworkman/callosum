# Security Audit - Meta Reference List

**Date:** 2026-07-10
**Feature:** A Theory-pane "Meta Reference List" that inspects a selected paper's reference list and stores
per-citation review state for three negative signals: could not verify with available sources, known retraction
signal, and previously flagged in the user's library.
**Triggers:** audit-gate #1 (new API endpoints), #4 (new persisted user review state), #5 (net-new feature spanning
backend methods, router, persistence, migration, and frontend). No new dependency, no new file-ingestion path.

## Scope

New public API surfaces:

- `GET /papers/{paper_id}/reference-integrity`
- `POST /papers/{paper_id}/reference-integrity/run`
- `GET /reference-integrity/run/{job_id}`
- `GET /reference-integrity/overview`
- `POST /reference-integrity/instances/{instance_id}/review`

The run endpoint fetches linked references for a paper DOI via the existing Semantic Scholar adapter, falling back
to OpenAlex `referenced_works` when Semantic Scholar has no linked reference list. It reuses Crossref/OpenAlex
metadata resolution, reuses the existing retraction checker list, and reuses the local citation context classifier
for advisory hints. It persists reference entities, citation instances, detector signals, and per-instance review rows.

## Threat Review

| Vector | Assessment |
|---|---|
| **Data egress** | Public metadata only. The selected paper DOI is sent to Semantic Scholar and, if needed, OpenAlex to fetch linked references; cited reference DOI/title may be sent to Crossref/OpenAlex; retraction checks use the existing Crossref/OpenAlex/Retraction Watch paths. No PDF text or library notes are sent. No LLM path is introduced. |
| **Signal-not-verdict** | The detector emits only explicit negative signals. UI/API copy avoids positive verification and forbidden verdict labels. Clearing all signals only clears the reference-derived active count. No composite score or hidden confidence field is added. |
| **Review scope** | Review state is keyed to the citation instance and current signal-set fingerprint. There is no global whitelist. A dismissal in one paper cannot suppress the same entity in another paper. |
| **Stale review invalidation** | The current warning state is derived from active signals plus the review row matching the current deterministic signal-set fingerprint. A materially new signal set, such as a later retraction signal, creates a new unreviewed fingerprint and marks the item reopened. |
| **Input validation** | Review mutation accepts only `dismissed` or `confirmed_problem` via Pydantic `Literal`. Unknown paper/job/instance ids return 404. Papers without DOI return 422 for the run path because linked reference retrieval is unavailable. |
| **Injection / SQL** | Persistence uses SQLAlchemy Core bound parameters and fixed table/column definitions. User/library metadata is stored as values, not interpolated into SQL or file paths. |
| **Output encoding** | Reference titles, raw citation text, evidence, and context sentences render through React text nodes; no `dangerouslySetInnerHTML` is used. |
| **Secrets** | No secrets are read or written. Existing metadata contact-email behavior remains unchanged. |
| **Resource** | Runs are job-store background tasks, matching existing async patterns. The implementation processes one selected paper's linked reference list per run and stores bounded JSON evidence per signal. |
| **Remote/read-only exposure** | Endpoints sit behind existing access control. The Theory section is hidden in read-only UI; mutating POSTs are covered by the existing method gate on read-only instances. |
| **Supply chain** | No new package dependency. |

## Negative-Path Checks

- Unknown paper id, job id, and citation-instance id return 404. Passed in `tests/test_reference_integrity.py`.
- Paper without DOI returns 422 for a run, rather than attempting unsupported reference retrieval. Passed.
- Search miss emits **Could not verify with available sources** and not a verdict label. Passed.
- Semantic Scholar miss can fall back to OpenAlex `referenced_works`; an OpenAlex work record counts as source evidence rather than a weaker search miss. Passed.
- New retraction signal after an older dismissal reopens the instance as unreviewed. Passed.
- Same unchanged signal set preserves a user's dismissal across restart. Passed.
- Context hints do not mutate review state or suppress detector signals. Passed.

## Verification

`pytest tests/test_reference_integrity.py` - 8 passed before final integration run. Route surface and frontend
assembly tests are updated for the new endpoints and Theory section.

## Result

**Security Audit: PASS.** The feature stores local review state and makes public metadata lookups through existing
adapters. It introduces no LLM adjudication, no file-write path, no secrets, no global whitelist, and no hidden paper
confidence score. Review invalidation is tied to deterministic signal-set fingerprints.
