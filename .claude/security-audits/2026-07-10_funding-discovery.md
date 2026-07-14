# Security Audit - Funding Discovery

**Date:** 2026-07-10
**Feature:** Theory-pane Funding Discovery for latent funding prospects, recurring schemes, and open opportunities.
**Triggers:** new API endpoints, new persistence tables, funding metadata egress, IRS 990-PF privacy-sensitive source
handling, new frontend section.

## Scope

New API surfaces:

- `POST /funding-discovery/run`
- `GET /funding-discovery/run/{job_id}`
- `POST /funding-discovery/save`
- `GET /funding-discovery/saved`
- `POST /funding-discovery/saved/refresh`
- `PATCH /funding-discovery/saved/{saved_item_id}`
- `DELETE /funding-discovery/saved/{saved_item_id}`
- `GET /funding-discovery/runs/{run_id}/export.csv`

New persistence surfaces include normalized funding organizations, schemes, historical awards, prospects,
opportunities, application surfaces, research funding profiles, search runs, saved items, and source batches.

## Threat Review

| Vector | Assessment |
|---|---|
| Data egress | Provider queries use minimized structured profile facets. The implementation does not send full PDFs, notes, private annotations, or protected applicant facts by default. ROR receives organization-name queries; OpenAlex/Crossref receive bounded facet keyword queries for funding metadata; selected-paper OpenAlex lineage sends the selected paper DOI and bounded related-work IDs through the existing OpenAlex client; Grants.gov receives bounded facet keyword queries for opportunities, exact opportunity IDs for saved-opportunity detail refresh, and bounded organization/scheme terms for saved prospect/scheme application-surface refresh. |
| Sensitive applicant facts | No citizenship, immigration status, disability, race/ethnicity, sex/gender, veteran status, career stage, PI status, or years-since-degree is inferred from manuscript text. |
| IRS PII | 990-PF individual recipient names are suppressed in UI-facing evidence; home addresses are not extracted for default display. |
| Licensed sources | Extension boundary exists for provider data policy. No commercial provider is scraped or required. |
| Injection / SQL | Persistence uses SQLAlchemy Core bound values and fixed schema. No user text is interpolated into SQL. |
| Output encoding | Frontend renders through React text nodes and does not use `dangerouslySetInnerHTML`. |
| Network scope | Current opportunity resolution uses bounded provider adapters; no unrestricted crawler or broad scraping system is introduced. |
| Verdict leakage | UI/API avoid recommendation, chance-estimate, reopening-forecast, funder-intent, and hidden composite confidence language. |
| Resource use | 990-PF support is a bounded parser/ETL feed point, not a global historical backfill on the request path. |
| Read-only mode | Theory section is hidden in read-only UI; endpoints remain behind existing access-control middleware. |

## Negative-Path Checks

- Empty or conflicting input modes return 422.
- Unknown selected paper returns 404.
- Provider failure is represented as structured provider status and does not destroy local prospect results.
- Selected-paper OpenAlex related-work grant metadata is lineage evidence only, not current opportunity evidence.
- Grants.gov search misses are not turned into "no grants exist."
- OpenAlex/Crossref funding records with missing funder names are skipped rather than force-normalized.
- Recipient-neighborhood signals use exact non-individual recipient organization names; individual recipient rows are excluded.
- Co-funding proximity uses exact non-individual recipient organization overlap and is presented as proximity evidence, not alignment proof.
- Application-surface posture is displayed as route evidence and does not suppress prospects or become an eligibility verdict.
- Saved funding rows expose only lightweight canonical metadata plus last-known status/deadline snapshots.
- Saved refresh re-queries saved Grants.gov opportunities by exact provider opportunity id where supported, then re-snapshots saved rows and reports status/deadline changes. Saved prospects/schemes use bounded organization/scheme terms against supported provider indexes and require conservative provider title/organization matches before creating a linked opportunity. It is a bounded manual action, not a daemon or whole-web recrawl.
- Saved refresh events persist only per-saved-item outcome labels, status/deadline change summaries, linked opportunity id where applicable, provider status, and checked timestamp. They do not store research text, PDFs, notes, annotations, or provider raw payloads.
- Saved-item updates are limited to allowlisted workflow state values and a bounded note field.
- Unsaving deletes only the saved workflow marker by saved row id; canonical funding records and search-run evidence remain intact.
- CSV export summarizes safe run-level evidence and does not export nested recipient rows or hidden scoring fields.
- Recurrence does not create an open opportunity.
- Individual 990-PF recipient evidence is withheld in UI-safe records.

## Verification

- `pytest -q tests/test_funding_discovery.py` - 21 passed.
- Addendum 2026-07-11: `pytest -q tests/test_funding_discovery.py` - 22 passed after adding saved-item unsave.
- Addendum 2026-07-11: `pytest -q tests/test_funding_discovery.py` - 22 passed after adding saved-item workflow/notes updates.
- Addendum 2026-07-11: `pytest -q tests/test_funding_discovery.py` - 22 passed after adding saved snapshot refresh.
- Addendum 2026-07-11: `pytest -q tests/test_funding_discovery.py` - 22 passed after adding Grants.gov exact-opportunity detail refresh.
- Addendum 2026-07-11: `pytest -q tests/test_funding_discovery.py` - 24 passed after adding saved prospect/scheme application-surface refresh.
- Addendum 2026-07-11: `pytest -q tests/test_funding_discovery.py` - 24 passed after adding saved refresh event history.
- `pytest -q tests/test_funding_discovery.py tests/test_openalex_adapter.py tests/test_publishers.py tests/test_reference_integrity.py tests/test_health.py tests/test_frontend_assembly.py tests/test_startup_migration.py` - 69 passed.
- `ruff check .` - passed.
- `python tools/check_line_budget.py --list` with `PYTHONIOENCODING=utf-8` - passed.

## Result

**Security Audit: PASS for the implemented vertical slice.** The feature introduces no new dependency, no unrestricted
crawler, no LLM adjudication path, no commercial-provider dependency, no hidden funding confidence score, and no
positive eligibility verdict.

---

## Addendum - Optional LLM triage over surfaced results

**Date:** 2026-07-10
**Change:** Added an opt-in Funding Discovery run toggle that sends the bounded research abstract/description plus
compact already-surfaced funding item summaries to the configured LLM for apparent-fit triage.

### Additional Threat Review

| Vector | Assessment |
|---|---|
| Data egress | Default remains off. The LLM triage path runs only when the user checks the Funding Discovery AI-triage box. Cloud providers require the existing AI-features/data-egress consent and configured key; loopback providers use the existing provider endpoint rules. |
| Private text scope | The payload is limited to title/abstract or the pasted research description/field plus compact surfaced-card summaries. Full PDFs, notes, annotations, and applicant-sensitive facts are not sent. |
| Authority / verdict leakage | The model returns review annotations (`closer_apparent_fit`, `possible_fit`, `uncertain`, `lower_apparent_fit`) and a `show_in_triage` flag. The full deterministic pool remains available via "All surfaced"; model output does not create, delete, verify, save, or suppress funding records. |
| Prompt injection | Provider/opportunity text is treated as untrusted input inside a JSON payload. The prompt instructs JSON-only output and forbids invented deadlines, eligibility, application routes, funder priorities, recommendations, and funding probabilities. Parser accepts only known labels and known item keys. |
| Failure behavior | LLM triage failure is non-destructive. The deterministic funding report still completes and carries an `llm_triage_status` warning. |
| Persistence | LLM annotations live in the run response only; canonical funding entities and saved items remain deterministic records. |

### Additional Negative-Path Checks

- Malformed/irrelevant LLM labels are ignored unless they reference a known surfaced item key.
- A low apparent-fit label does not remove an item from the full pool.
- AI triage unavailable/off does not contact a provider and does not fail deterministic discovery.
- UI text avoids recommendation and funding-probability language.

### Additional Verification

- `pytest -q tests/test_funding_discovery.py tests/test_frontend_assembly.py` - 28 passed.
- `ruff check .` - passed.
- `ruff format --check app/backend/api/routers/funding.py app/backend/funding/llm_triage.py app/backend/api/app.py tests/test_funding_discovery.py` - passed.
- `python -m compileall -q app/backend/api/routers/funding.py app/backend/funding/llm_triage.py app/backend/api/app.py` - passed.
- `python tools/build_frontend.py` - passed.
- `python tools/check_line_budget.py --list` with `PYTHONIOENCODING=utf-8` - passed.

**Security Audit: PASS for optional LLM triage.** It is opt-in, egress-gated, non-authoritative, failure-isolated,
and does not persist model output as canonical funding evidence.
