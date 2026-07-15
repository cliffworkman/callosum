# Funding Discovery

Funding Discovery is a Theory-pane tool for discovering plausible funding prospects from observed funding behavior and
scholarly funding lineage, then separately resolving whether an actionable application surface currently exists.

```text
ResearchFundingProfile
    ->
prospect candidate generation
    ->
LatentFundingFitEngine
    ->
FundingProspect
    ->
OpportunityResolver
    ->
Open Opportunity / Recurring Scheme / Funding Prospect
```

## Domain Semantics

- `HistoricalAward` is observed funding behavior. It is not an opportunity.
- `FundingProspect` is latent-fit evidence. It is not a recommendation and has no user-visible chance estimate.
- `FundingScheme` names a funding mechanism. It is not necessarily open.
- `FundingOpportunity` requires current provider-backed opportunity evidence.
- `ApplicationSurface` records how an applicant might approach a funder or scheme. It is separate from substantive
  alignment.
- Recurrence is detected from prior cycles. It is not a forecast.

## Provider Capabilities

Providers declare the evidence class they supply:

- `organization_identity`
- `award_history`
- `grantmaking_transaction`
- `opportunity_index`
- `application_surface`
- `taxonomy`
- `news_signal`

Future providers should implement narrow capability adapters. An international award-history source should not pretend
to know current application status; a professional-society opportunity source should not pretend to know historical
grantmaking transactions.

Licensed providers should attach source-specific policy constraints for raw-payload persistence, normalized-field
persistence, semantic indexing, model input, source-text display, and export. Those restrictions belong at the provider
boundary, not in global matching logic.

Current open-data adapters:

- ROR `organization_identity`: cached organization query resolution with aliases, geography, and Crossref/FundRef
  crosswalk where supplied.
- OpenAlex `award_history`: cached works search restricted to records with funder metadata; selected-paper runs also
  reuse the existing OpenAlex DOI lookup and related-work fetch to normalize grants on related scholarly work as
  `HistoricalAward` lineage evidence.
- Crossref `award_history`: cached works search restricted to records with funder metadata; funder/award metadata is
  normalized as `HistoricalAward` evidence.
- Grants.gov `opportunity_index`: cached official opportunity search for open/forecasted federal opportunities.
- Local funding history `award_history` / `grantmaking_transaction`: bounded fixture and ETL feed point for IRS/990-PF
  parsed evidence.

## Identity Resolution

Callosum uses an internal organization id as canonical identity. External ids such as ROR, EIN, OpenAlex, Crossref
funder ids, and platform ids are identifiers on the organization record, not universal primary keys.

Resolution is deterministic first:

- exact EIN
- exact ROR
- exact normalized name
- alias/acronym
- multiple plausible candidates retained
- unresolved remains unresolved

The implementation keeps ambiguous organizations representable. It does not force a winner to simplify matching.

## Provenance

Every meaningful normalized or inferred fact should carry provenance:

- `provider_native`: provider explicitly supplied the field.
- `deterministic_parse`: Callosum parsed or normalized it without semantic inference.
- `taxonomy_mapping`: Callosum mapped source text into a controlled label.
- `semantic_inference`: Callosum inferred a facet from evidence.
- `manual`: user-supplied.

UI language must distinguish provider-stated facts from inferred portfolio behavior. Do not turn historical overlap into
an explicit funder policy.

## Privacy

Research inputs are minimized before provider queries. The selected-paper path uses local title, abstract, keywords, and
deterministic concept rules; full PDFs, notes, annotations, unpublished claims, and project contents are not sent by
default.

Applicant-sensitive facts such as citizenship, immigration status, disability, race, ethnicity, sex, gender, veteran
status, career stage, PI eligibility, and years since terminal degree are never inferred from manuscript text.

IRS 990-PF records may include individual recipient names and addresses. Default Funding Discovery UI suppresses
individual donee names and never displays home addresses.

## Ranking And Diversification

`LatentFundingFitEngine` emits inspectable categorical signals:

- `portfolio_topic_overlap`
- `population_alignment`
- `method_modality_overlap`
- `intervention_alignment`
- `support_strategy_fit`
- `activity_type_fit`
- `recipient_similarity`
- `cofunding_proximity`
- `geography_signal`
- `scholarly_lineage`
- `scheme_recurrence`

Internal ordering is deterministic and code-visible. It is not displayed as a percentage. The initial algorithm caps
quantity effects, rewards distinct facet breadth and support-strategy specificity, and penalizes broad one-facet volume
so large indexed funders do not dominate solely because they have more records.

Deadline proximity and award size do not increase mission fit. Eligibility remains separate from topical or latent fit.

For selected-paper runs, scholarly lineage currently means: resolve the selected paper by DOI through the existing
OpenAlex client, read OpenAlex `related_works`, fetch a bounded related-work set, and normalize any returned grant
metadata. It does not infer that the funder has a current program in the area.

Recipient neighborhood currently means: exact normalized organization-recipient overlap between profile-matched
historical awards and other historical awards. Individual recipient rows are excluded from this signal.

Co-funding proximity currently means: funders sharing exact non-individual recipient organizations with funders that
have direct profile-matched historical evidence. It is graph-neighborhood evidence, not proof of mission alignment.

Application posture is displayed from `ApplicationSurface` records when present. A prospect-only surface such as
"unsolicited applications are not accepted" remains route evidence; it does not suppress latent-fit signals or become an
eligibility verdict.

## Persistence

Search runs persist the profile, provider statuses, normalized organizations, historical awards, opportunities,
prospects, schemes, and application surfaces needed to reconstruct evidence from a run.

Saved funding items are intentionally lightweight. A saved opportunity, scheme, or prospect stores the canonical item
identity, workflow state, optional note, and a last-known snapshot: checked time, status class, and next deadline where
the canonical item has one. The saved row editor updates only the workflow state and note on this marker. The manual
saved refresh re-queries saved Grants.gov opportunities by exact provider opportunity id through Grants.gov
`fetchOpportunity`, updates the canonical opportunity record when provider-backed status/deadline evidence changed,
then re-snapshots saved rows. For saved prospects and recurring schemes, refresh uses bounded organization/scheme terms
against supported provider indexes and accepts only conservative provider title/organization matches. If current
opportunity evidence is found, Callosum creates or updates a separate `FundingOpportunity` and `ApplicationSurface` and
links the saved row's snapshot to that evidence; the prospect or scheme remains a prospect or scheme. This is not a
background daemon or unrestricted provider recrawl. The refresh summary uses explicit outcome labels for current
opportunity found, status changed, deadline changed, no current application window verified, and provider unavailable.
Each manual refresh writes a `saved_funding_refresh_events` row per saved item; the saved-row detail shows the most
recent events so transient provider failures remain distinguishable from checks where no current application window was
verified. Saved-list filters count and show all items, needs review, current opportunity found, provider issue, no
current window, applying/planning, and archived items; they are local review-list views and do not modify the underlying
evidence. Unsaving deletes only the saved marker and its refresh-event history, not the canonical
opportunity, scheme, prospect, or search-run evidence. The Theory-pane saved view is a review list, not a grant CRM.

Run-level CSV export is available from persisted search runs. The export is an evidence table, not a recommendation
sheet: it keeps open opportunities, recurring schemes, and funding prospects distinct; includes source/status,
deadline, application-route, summarized signal, and matched-facet columns; and omits hidden scores or chance-estimate
fields. Nested historical evidence is summarized so individual 990-PF recipient details are not exported by default.

## Adding A Provider

To add a provider:

1. Implement only the capability interfaces the source actually supports.
2. Normalize records into the funding domain without collapsing prospects, schemes, opportunities, and surfaces.
3. Attach provenance and provider status.
4. Attach provider data policy if the source is licensed.
5. Feed normalized evidence into candidate generation or opportunity resolution as appropriate.
6. Add negative-path tests for empty results, malformed records, non-200 responses, timeouts, rate limits, pagination,
   partial data, and structured provider status.
