// Funding Discovery display helpers. Pure functions only; React components live in 08k_funding_discovery.jsx.

function fundingProviderDisplayName(id) {
  const names = {
    "local-funding-history": "Local funding history",
    "openalex-funding": "OpenAlex funding lineage",
    "crossref-funding": "Crossref funding metadata",
    "grants-gov": "Grants.gov opportunities",
    "configured-llm": "LLM triage",
  };
  return names[id] || id || "Funding source";
}

function fundingProviderStatusLabel(status) {
  return (status || "unknown").replaceAll("_", " ");
}

function fundingCoverageMeaning(status) {
  const id = status.provider_id || "";
  const state = status.status || "unknown";
  if (id === "openalex-funding") {
    return state === "success"
      ? "Scholarly funding lineage was searched. OpenAlex funding metadata is useful but incomplete by source design."
      : "OpenAlex lineage evidence may be missing from this run; historical and opportunity evidence from other sources is retained.";
  }
  if (id === "crossref-funding") {
    return state === "success"
      ? "Crossref grant metadata was searched. Coverage depends on publisher and deposited funder metadata."
      : "Crossref grant metadata may be missing from this run; this is not evidence that no grant lineage exists.";
  }
  if (id === "grants-gov") {
    return state === "success"
      ? "Current federal opportunities were searched. This covers supported federal records, not private or society mechanisms."
      : "Current federal opportunities may be incomplete or unavailable; prospects and recurring schemes from other evidence remain reviewable.";
  }
  if (id === "local-funding-history") {
    return "Local historical-award evidence was searched. Long-tail private foundation evidence is limited to indexed filings and fixtures.";
  }
  return state === "not_searched" || state === "not_configured"
    ? "This source was not searched. Absence here is not evidence that no funding mechanism exists."
    : "This source contributed structured coverage status for interpreting the result pool.";
}

function fundingCoverageLimits(statuses) {
  const ids = new Set((statuses || []).map(s => s.provider_id));
  const notes = [
    "Commercial or licensed philanthropic databases are not part of the open-data path unless configured.",
    "Funder website pages, newsletters, and society-specific calls are not exhaustively crawled.",
  ];
  if (!ids.has("grants-gov")) notes.push("Current federal opportunity coverage was not searched in this run.");
  if (!ids.has("local-funding-history")) notes.push("Local EO-BMF / 990-PF historical coverage was not searched in this run.");
  if (!ids.has("openalex-funding")) notes.push("OpenAlex scholarly funding lineage was not searched in this run.");
  if (!ids.has("crossref-funding")) notes.push("Crossref grant metadata was not searched in this run.");
  return notes;
}

function fundingSignalLabel(value) {
  return (value || "signal").replaceAll("_", " ");
}

function fundingSignalBoundary(type) {
  if (type === "scheme_recurrence") {
    return "Observed prior cycles are not a forecast and do not verify a current application window.";
  }
  if (type === "scholarly_lineage") {
    return "Related scholarly works were linked to this funder; this is not evidence of a current program or policy.";
  }
  if (type === "application_surface") {
    return "Application-route evidence is separate from substantive research fit.";
  }
  if (type === "recipient_similarity" || type === "cofunding_proximity") {
    return "Neighborhood evidence can surface a prospect, but it does not establish funder intent.";
  }
  return "This is a funding-fit signal, not a recommendation or chance estimate.";
}

function fundingSignalSourceSummary(evidence) {
  if (!evidence || !evidence.length) return "No historical award rows attached.";
  const sources = [...new Set(evidence.map(e => e.source_kind || "source").filter(Boolean))];
  const years = [...new Set(evidence.map(e => e.tax_year).filter(Boolean))].sort();
  const sourceText = sources.slice(0, 3).join(", ");
  return years.length ? `${sourceText} · observed years ${years.join(", ")}` : sourceText;
}

function fundingEvidenceClassLabel(kind) {
  if (kind === "opportunity") return "Open Opportunity - current provider-backed application evidence.";
  if (kind === "scheme") return "Recurring Scheme - prior-cycle evidence without a verified current window.";
  return "Funding Prospect - historical or lineage evidence without a verified current application surface.";
}

function fundingSignalFacetSummary(signal) {
  const facets = signal.matched_profile_facets || [];
  if (!facets.length) return "";
  return facets.slice(0, 3).map(f => `${f.facet}: ${f.value}`).join("; ");
}

function fundingTriageReasons(item, kind, surfaces) {
  const signals = item.signals || [];
  const reasons = signals.slice(0, 3).map(signal => {
    const strength = signal.strength || "unresolved";
    const facets = fundingSignalFacetSummary(signal);
    const suffix = facets ? ` Facets: ${facets}.` : "";
    return `${fundingSignalLabel(signal.signal_type)} (${strength}). ${signal.explanation || fundingSignalBoundary(signal.signal_type)}${suffix}`;
  });
  if (!reasons.length && kind === "opportunity") reasons.push("Provider returned a current or forecasted opportunity record.");
  if (!reasons.length && kind === "scheme") reasons.push("Prior-cycle evidence surfaced this scheme; current actionability is checked separately.");
  if (!reasons.length) reasons.push("This record was included in the run output, but no detailed match signal was attached.");
  if (kind !== "opportunity" && fundingSurfacesFor(item, surfaces).length) {
    reasons.push("Application-route evidence is attached separately from substantive funding-fit evidence.");
  }
  return reasons;
}

function fundingTriageReviewNotes(item, kind, surfaces) {
  const notes = [];
  const signals = item.signals || [];
  const strengths = fundingSignalStrengths(item);
  const eligibility = item.eligibility && item.eligibility.label;
  if (!signals.length) notes.push("No detailed funding-fit signal is attached; inspect the source record directly.");
  if (strengths.length && strengths.every(s => ["weak", "unresolved"].includes(s))) {
    notes.push("All attached signals are weak or unresolved.");
  }
  if (kind === "scheme") notes.push("Recurring evidence is not a forecast and does not verify a current funding window.");
  if (kind === "prospect" && !fundingSurfacesFor(item, surfaces).length) {
    notes.push("No current application surface was verified in this run.");
  }
  if (eligibility) notes.push(`Eligibility evidence: ${eligibility}.`);
  else notes.push("Eligibility evidence was not assessed.");
  if (item.identity_resolution_quality && item.identity_resolution_quality !== "high") {
    notes.push(`Organization identity resolution is ${item.identity_resolution_quality}; confirm aliases and source records.`);
  }
  if (item.llm_evaluation && item.llm_evaluation.status === "stale") {
    notes.push("AI-fit label is stale because the underlying funding evidence changed.");
  }
  return notes;
}

function fundingNormalizeKey(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function fundingGroupKey(kind, item) {
  if (!item) return "";
  if (kind === "opportunity") {
    if (item.provider_id && item.provider_opportunity_id) {
      return `opportunity:${fundingNormalizeKey(item.provider_id)}:${fundingNormalizeKey(item.provider_opportunity_id)}`;
    }
    return `opportunity:${item.id || fundingNormalizeKey(item.source_url || item.title || "")}`;
  }
  const org = fundingNormalizeKey(item.organization_name);
  const scheme = fundingNormalizeKey(item.scheme_name);
  return `${kind}:${org}:${scheme || "organization"}`;
}

function fundingSignalKey(signal) {
  return `${signal.signal_type || "signal"}:${signal.explanation || ""}`;
}

function fundingGroupedItems(items, kind) {
  const groups = [];
  const byKey = new Map();
  (items || []).forEach(item => {
    const key = fundingGroupKey(kind, item);
    if (!byKey.has(key)) {
      const group = { key, items: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    byKey.get(key).items.push(item);
  });
  return groups.map(group => {
    if (group.items.length === 1) return group.items[0];
    const primary = group.items[0];
    const signals = [];
    const seen = new Set();
    group.items.forEach(item => (item.signals || []).forEach(signal => {
      const key = fundingSignalKey(signal);
      if (!seen.has(key)) {
        seen.add(key);
        signals.push(signal);
      }
    }));
    const signalTypes = [...new Set(signals.map(s => s.signal_type).filter(Boolean))];
    return {
      ...primary,
      signals,
      _fundingGroup: {
        count: group.items.length,
        evidencePaths: signalTypes.length || signals.length,
        records: group.items.map(item => ({
          id: item.id,
          kind,
          title: item.title || item.scheme_name || item.organization_name || "Funding record",
          signals: [...new Set((item.signals || []).map(s => fundingSignalLabel(s.signal_type)))],
        })),
      },
    };
  });
}

function fundingAmountText(amount) {
  if (!amount || amount.value == null) return "";
  const currency = amount.currency || "USD";
  return `${currency} ${Number(amount.value).toLocaleString()}`;
}

function fundingSurfacesFor(item, surfaces) {
  return (surfaces || []).filter(s => {
    if (s.organization_name !== item.organization_name) return false;
    if (item.scheme_name && s.scheme_name && item.scheme_name !== s.scheme_name) return false;
    return true;
  });
}

function fundingTriageItems(items, triageOnly) {
  if (!triageOnly) return items || [];
  return (items || []).filter(item => item.llm_evaluation && item.llm_evaluation.show_in_triage);
}

function fundingIsLowerSignalProspect(item, surfaces) {
  if (fundingSurfacesFor(item, surfaces).length) return false;
  const signals = item.signals || [];
  return !signals.length || signals.every(s => ["weak", "unresolved"].includes(s.strength || "unresolved"));
}

const FUNDING_RESULT_FILTERS = [
  { key: "all", label: "All" },
  { key: "current_opportunity", label: "Current opportunity" },
  { key: "recurring_only", label: "Recurring only" },
  { key: "prospect_only", label: "Prospect only" },
  { key: "eligibility_review", label: "Eligibility review" },
  { key: "no_current_surface", label: "No current surface" },
  { key: "identity_uncertain", label: "Identity uncertain" },
  { key: "stale_ai_fit", label: "Stale AI-fit" },
  { key: "strong_moderate", label: "Strong / moderate" },
  { key: "weak_unresolved", label: "Weak / unresolved" },
  { key: "scholarly_lineage", label: "Scholarly lineage" },
  { key: "historical_grantmaking", label: "Historical grantmaking" },
  { key: "federal", label: "Federal" },
  { key: "application_route", label: "Application route" },
  { key: "saved", label: "Saved" },
  { key: "unsaved", label: "Unsaved" },
  { key: "llm_triaged", label: "LLM triaged" },
];

const FUNDING_RESULT_SORTS = [
  { key: "default", label: "Default evidence order" },
  { key: "application_route", label: "Application route first" },
  { key: "saved_first", label: "Saved first" },
  { key: "upcoming_deadlines", label: "Upcoming deadlines" },
  { key: "strong_signals", label: "Strong signals first" },
  { key: "recently_surfaced", label: "Recently surfaced" },
];

function fundingOptionLabel(options, key) {
  const option = (options || []).find(item => item.key === key);
  return option ? option.label : key || "Default";
}

function fundingTagItem(item, kind, order) {
  return { ...item, _fundingKind: kind, _fundingOrder: order || 0 };
}

function fundingSavedKey(kind, id) {
  return `${kind || "item"}:${id || ""}`;
}

function fundingSavedKeySet(savedItems) {
  return new Set((savedItems || []).map(item =>
    fundingSavedKey(item.item_kind || item.itemKind, item.canonical_item_id || item.canonicalItemId)
  ));
}

function fundingItemIsSaved(item, savedKeys) {
  return savedKeys.has(fundingSavedKey(item._fundingKind, item.id));
}

function fundingSavedItemFor(kind, id, savedItems) {
  const key = fundingSavedKey(kind, id);
  return (savedItems || []).find(item =>
    fundingSavedKey(item.item_kind || item.itemKind, item.canonical_item_id || item.canonicalItemId) === key
  ) || null;
}

function fundingSignalStrengths(item) {
  return (item.signals || []).map(s => s.strength || "unresolved");
}

function fundingHasSignal(item, type) {
  return (item.signals || []).some(s => s.signal_type === type);
}

function fundingHasHistoricalEvidence(item) {
  return (item.signals || []).some(signal => (signal.matched_evidence || []).some(e =>
    ["irs_990_pf", "openalex_award", "crossref_grant"].includes(e.source_kind)
      || ["local-funding-history", "openalex-funding", "crossref-funding"].includes(e.provider_id)
  ));
}

function fundingHasFederalEvidence(item, surfaces) {
  if (item.provider_id === "grants-gov") return true;
  return fundingSurfacesFor(item, surfaces).some(s => s.provider_id === "grants-gov");
}

function fundingNeedsEligibilityReview(item) {
  const eligibility = item.eligibility || {};
  const assessment = fundingNormalizeKey(eligibility.assessment);
  const label = fundingNormalizeKey(eligibility.label);
  if (!assessment && !label) return true;
  if (assessment === "apparently_eligible" || label === "no checked conflict found") return false;
  return assessment === "not_assessed"
    || assessment === "uncertain"
    || assessment === "apparently_ineligible"
    || label.includes("review")
    || label.includes("not assessed")
    || label.includes("conflict")
    || label.includes("uncertain");
}

function fundingHasNoCurrentSurface(item, surfaces) {
  return item._fundingKind !== "opportunity" && fundingSurfacesFor(item, surfaces).length === 0;
}

function fundingIdentityIsUncertain(item) {
  const quality = fundingNormalizeKey(item.identity_resolution_quality);
  return Boolean(quality && quality !== "high");
}

function fundingHasStaleAiFit(item) {
  return item.llm_evaluation && item.llm_evaluation.status === "stale";
}

function fundingResultMatchesFilter(item, filter, surfaces, savedKeys) {
  const strengths = fundingSignalStrengths(item);
  if (filter === "all") return true;
  if (filter === "current_opportunity") return item._fundingKind === "opportunity";
  if (filter === "recurring_only") return item._fundingKind === "scheme";
  if (filter === "prospect_only") return item._fundingKind === "prospect";
  if (filter === "eligibility_review") return fundingNeedsEligibilityReview(item);
  if (filter === "no_current_surface") return fundingHasNoCurrentSurface(item, surfaces);
  if (filter === "identity_uncertain") return fundingIdentityIsUncertain(item);
  if (filter === "stale_ai_fit") return fundingHasStaleAiFit(item);
  if (filter === "strong_moderate") return strengths.some(s => ["strong", "moderate"].includes(s));
  if (filter === "weak_unresolved") return !strengths.length || strengths.every(s => ["weak", "unresolved"].includes(s));
  if (filter === "scholarly_lineage") return fundingHasSignal(item, "scholarly_lineage");
  if (filter === "historical_grantmaking") return fundingHasHistoricalEvidence(item);
  if (filter === "federal") return fundingHasFederalEvidence(item, surfaces);
  if (filter === "application_route") return item._fundingKind === "opportunity" || fundingSurfacesFor(item, surfaces).length > 0;
  if (filter === "saved") return fundingItemIsSaved(item, savedKeys);
  if (filter === "unsaved") return !fundingItemIsSaved(item, savedKeys);
  if (filter === "llm_triaged") return item.llm_evaluation && item.llm_evaluation.show_in_triage;
  return true;
}

function fundingResultFilterCounts(items, surfaces, savedItems) {
  const savedKeys = fundingSavedKeySet(savedItems);
  const counts = Object.fromEntries(FUNDING_RESULT_FILTERS.map(f => [f.key, 0]));
  (items || []).forEach(item => {
    FUNDING_RESULT_FILTERS.forEach(f => {
      if (fundingResultMatchesFilter(item, f.key, surfaces, savedKeys)) counts[f.key] += 1;
    });
  });
  return counts;
}

function fundingFilterResults(items, filter, surfaces, savedItems) {
  const savedKeys = fundingSavedKeySet(savedItems);
  return (items || []).filter(item => fundingResultMatchesFilter(item, filter, surfaces, savedKeys));
}

function fundingStrengthRank(item) {
  const ranks = { strong: 3, moderate: 2, weak: 1, unresolved: 0 };
  return Math.max(0, ...fundingSignalStrengths(item).map(s => ranks[s] == null ? 0 : ranks[s]));
}

function fundingDeadlineTime(item) {
  const times = (item.deadlines || []).map(d => Date.parse(d.date || d.deadline || d.due_date || "")).filter(Number.isFinite);
  return times.length ? Math.min(...times) : Number.POSITIVE_INFINITY;
}

function fundingRecencyTime(item) {
  const direct = Date.parse(item.surfaced_at || item.fetched_at || item.source_updated_at || item.detected_at || item.created_at || "");
  if (Number.isFinite(direct)) return direct;
  const signalTimes = (item.signals || []).map(s => Date.parse(s.detected_at || s.created_at || "")).filter(Number.isFinite);
  if (signalTimes.length) return Math.max(...signalTimes);
  const years = (item.signals || []).flatMap(s => s.matched_evidence || []).map(e => e.tax_year).filter(Boolean);
  return years.length ? Date.parse(`${Math.max(...years)}-12-31`) : Number.NEGATIVE_INFINITY;
}

function fundingOriginalOrder(a, b) {
  return (a._fundingOrder || 0) - (b._fundingOrder || 0);
}

function fundingSortResults(items, sort, surfaces, savedItems) {
  if (sort === "default") return items || [];
  const savedKeys = fundingSavedKeySet(savedItems);
  return [...(items || [])].sort((a, b) => {
    if (sort === "application_route") {
      const routeA = a._fundingKind === "opportunity" || fundingSurfacesFor(a, surfaces).length ? 1 : 0;
      const routeB = b._fundingKind === "opportunity" || fundingSurfacesFor(b, surfaces).length ? 1 : 0;
      return routeB - routeA || fundingOriginalOrder(a, b);
    }
    if (sort === "saved_first") {
      return Number(fundingItemIsSaved(b, savedKeys)) - Number(fundingItemIsSaved(a, savedKeys)) || fundingOriginalOrder(a, b);
    }
    if (sort === "upcoming_deadlines") {
      return fundingDeadlineTime(a) - fundingDeadlineTime(b) || fundingOriginalOrder(a, b);
    }
    if (sort === "strong_signals") {
      return fundingStrengthRank(b) - fundingStrengthRank(a) || fundingOriginalOrder(a, b);
    }
    if (sort === "recently_surfaced") {
      return fundingRecencyTime(b) - fundingRecencyTime(a) || fundingOriginalOrder(a, b);
    }
    return fundingOriginalOrder(a, b);
  });
}
