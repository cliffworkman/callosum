(function () {
  "use strict";

  var networkFetch = window.fetch.bind(window);
  var base = new URL(document.baseURI);
  var demoConfig = window.CALLOSUM_DEMO;
  if (!demoConfig) throw new Error("Demo configuration was not generated before the static provider loaded");
  var snapshotUrl = new URL("snapshot-v1.json", base);
  var snapshotPromise = networkFetch(snapshotUrl, { cache: "no-store", credentials: "omit" }).then(function (response) {
    if (!response.ok) throw new Error("Demo snapshot failed to load (HTTP " + response.status + ")");
    return response.json();
  });

  function blocked(message, path) {
    window.dispatchEvent(new CustomEvent("callosum:demo-blocked", { detail: { message: message, path: path } }));
  }

  function jsonResponse(value, status) {
    return new Response(JSON.stringify(value), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }
    });
  }

  function textResponse(value, contentType, status) {
    return new Response(value, {
      status: status || 200,
      headers: { "Content-Type": contentType, "Cache-Control": "no-store" }
    });
  }

  var FEED_STATE_KEY = "callosum.demo.feedState.v1";

  function initialFeedState(snapshot) {
    var sample = snapshot.api.extended.feed.items.find(function (item) { return !item.in_library; });
    var state = { version: 1, initialized: true, all_read: false, read: {}, starred: {} };
    if (sample) state.starred[String(sample.id)] = true;
    return state;
  }

  function loadFeedState(snapshot) {
    try {
      var raw = window.localStorage.getItem(FEED_STATE_KEY);
      if (!raw) {
        var seeded = initialFeedState(snapshot);
        window.localStorage.setItem(FEED_STATE_KEY, JSON.stringify(seeded));
        return seeded;
      }
      var parsed = JSON.parse(raw);
      if (parsed && parsed.version === 1 && parsed.initialized === true) return parsed;
    } catch (_error) {
      // Browser-local practice state is optional; the reviewed fixture remains the fallback.
    }
    return { version: 1, initialized: true, all_read: false, read: {}, starred: {} };
  }

  function saveFeedState(state) {
    try { window.localStorage.setItem(FEED_STATE_KEY, JSON.stringify(state)); } catch (_error) { /* optional */ }
  }

  function feedItemsWithLocalState(snapshot) {
    var state = loadFeedState(snapshot);
    return snapshot.api.extended.feed.items.map(function (item) {
      var key = String(item.id);
      var read = state.all_read ? true : Object.prototype.hasOwnProperty.call(state.read || {}, key)
        ? !!state.read[key] : !!item.is_read;
      var starred = Object.prototype.hasOwnProperty.call(state.starred || {}, key)
        ? !!state.starred[key] : !!item.is_starred;
      return Object.assign({}, item, { is_read: read, is_starred: starred });
    });
  }

  function requestBody(init) {
    if (!init || init.body == null) return {};
    if (typeof init.body === "string") {
      try { return JSON.parse(init.body); } catch (_error) { return {}; }
    }
    return {};
  }

  function mutationBlockedMessage(path) {
    if (/^\/settings(?:\/|$)/.test(path)) return "Settings changes are unavailable because this public snapshot has no writable configuration or secret store. The controls remain visible so you can inspect Callosum's local-first boundaries.";
    if (/^\/sync(?:\/|$)/.test(path)) return "Sync is unavailable because the static demo has no account, encrypted vault, or sync server. In the installed app it is optional, end-to-end encrypted, and off by default.";
    if (/^\/integrations\/libreoffice/.test(path)) return "LibreOffice installation runs on the user's computer and cannot start from a static website. The integration's real controls and setup boundary remain described in Settings and Help.";
    if (/^\/integrations\/word/.test(path)) return "The Word add-in is installed into desktop Word and needs the local Callosum app. Its real setup boundary remains described in Settings and Help.";
    if (/^\/citations\/styles\//.test(path)) return "Installing, editing, duplicating, or setting preferences for citation styles writes to persistent local configuration and is unavailable in this immutable demo.";
    if (path === "/methods/pcurve/run" || /^\/methods\/pcurve\/run\//.test(path)) return "p-curve reruns the statcheck extractor and its own EM estimator over whatever papers you select. That local computation needs the Callosum backend and is unavailable in the static browser demo.";
    if (path === "/methods/zcurve/run" || /^\/methods\/zcurve\/run\//.test(path)) return "Z-curve's EDR/ERR mixture-model estimator runs locally over whatever papers you select. That local computation needs the Callosum backend and is unavailable in the static browser demo.";
    if (path === "/methods/effect-size") return "The effect-size converter needs Callosum's local calculator. Its inputs remain visible for you to inspect the intended workflow, but no computation runs in the static browser demo.";
    if (path === "/critical-read/set" || /^\/critical-read\/set\//.test(path)) return "Running a fresh multi-paper critical read against your library needs the Callosum backend, local embeddings, and NLI models. This saved per-paper Critique example remains inspectable.";
    if (/^\/feedback/.test(path)) return "Feedback submission is disabled in the public demo because it would send data outside the static site. You can still compose, inspect, and copy the exact JSON report locally.";
    if (path === "/help/ask") return "AI Help answers require an explicitly enabled model provider. The complete bundled Help corpus below remains searchable and inspectable without any network request.";
    if (/^\/usage/.test(path)) return "Changing the usage log requires a writable local database. The public demo exposes only a saved, zero-egress usage summary.";
    if (/^\/annotations\//.test(path) || /^\/papers\/\d+\/annotations$/.test(path)) return "The saved demo annotations are inspectable but immutable. Creating, editing, or deleting highlights and notes requires your persistent local Callosum library.";
    if (/^\/papers\/\d+\/(read|priority)$/.test(path)) return "Read state and priority are personal library markers. Their saved demo values remain visible, but changing them requires your persistent local Callosum library.";
    if (path === "/library/scan" || path === "/papers/import") return "Import and watched-folder scanning read local files and create persistent library records. The static browser demo has no filesystem or database.";
    if (/^\/library\/bundle/.test(path)) return "Portable library bundle import or export is produced from persistent local records, tags, axes, and annotations and is unavailable in the immutable public snapshot.";
    if (/^\/saved-searches/.test(path)) return "The curated saved searches can be recalled in the demo, but saving or deleting them requires persistent local library state.";
    if (/^\/papers\/(duplicates|merge)/.test(path)) return "Duplicate review and merge require persistent local library records. The curated five-paper demo has no duplicate candidate to fabricate.";
    if (/^\/papers\/(trash|\d+\/(restore|permanent))/.test(path)) return "Trash, restore, and permanent deletion require persistent local library state; the curated demo contains no deleted paper.";
    if (/^\/papers\/\d+$/.test(path)) return "Editing paper details writes to persistent local library state. The saved demo metadata for this paper remains visible and inspectable.";
    if (/^\/papers\/text-health/.test(path) || /^\/papers\/\d+\/ocr/.test(path)) return "Text-health repair and OCR operate on local files through the backend. All four bundled demo PDFs already have extracted text.";
    if (/^\/agent/.test(path)) return "MCP writes require the installed local server, an explicit write gate, and a reversible activity log. The static demo has none of those mutation endpoints.";
    if (path === "/feed/refresh") return "Feed refresh is unavailable online because it polls external journal and search providers. The reviewed cached Feed remains inspectable.";
    if (path === "/feed/subscriptions" || /^\/feed\/subscriptions\//.test(path)) return "Following and unfollowing sources changes the persistent library and is unavailable in this immutable demo.";
    if (/^\/followed-authors/.test(path)) return "Following, refreshing, adding, or dismissing author results needs the local backend and OpenAlex access. The saved author results remain inspectable.";
    if (/^\/funding-discovery/.test(path)) return "New funding discovery, AI triage, saving, and refresh require the local backend or external providers. This saved, evidence-bearing run remains inspectable.";
    if (/^\/(gaps|overlooked|wanted)/.test(path)) return "Refreshing or changing this discovery queue requires the local backend and, where applicable, external providers. The demo can only show saved results.";
    if (/^\/citations\/beyond-library/.test(path)) return "Changing the saved-for-later queue requires persistent local library state and is unavailable in this immutable demo.";
    if (path === "/discovery/save") return "Saving metadata would change the library, so it is unavailable in this immutable demo.";
    if (/^\/wip\//.test(path)) return "Manuscript edits, reruns, and local file actions require Callosum on your computer. This synthetic manuscript's saved structure, evidence, checks, and provenance remain inspectable.";
    if (/^\/workbench\//.test(path)) return "Changing or recomputing this extraction project requires the local backend. The saved values, source anchors, converted effects, and production exports remain inspectable.";
    if (/^\/(credit|statements)\//.test(path)) return "Persistent manuscript handoff requires local Callosum and its editor integration. Browser-local drafting and copying remain available here.";
    return "That operation is unavailable in the online demo. This snapshot is immutable and has no backend.";
  }

  function csvCell(value) {
    var text = value == null ? "" : String(value);
    return /[\",\r\n]/.test(text) ? "\"" + text.replace(/\"/g, "\"\"") + "\"" : text;
  }

  function fundingCsv(report) {
    var headings = [
      "item_kind", "canonical_item_id", "title", "organization_name", "status", "next_deadline",
      "eligibility", "identity_resolution_quality", "source_provider", "source_url", "top_signals",
      "matched_facets", "interpretation_boundary", "llm_triage_label", "llm_triage_show_in_triage",
      "llm_triage_rationale", "llm_triage_prompt_version"
    ];
    var rows = [];
    (report.open_opportunities || []).forEach(function (item) {
      var evaluation = item.llm_evaluation || {};
      rows.push({
        item_kind: "open_opportunity", canonical_item_id: item.id, title: item.title,
        organization_name: item.organization_name, status: item.status,
        next_deadline: item.deadlines && item.deadlines[0] ? item.deadlines[0].date : "",
        eligibility: item.eligibility && item.eligibility.label, source_provider: item.provider_id,
        source_url: item.source_url,
        interpretation_boundary: "Current opportunity status was provider-backed at run time; eligibility still requires review.",
        llm_triage_label: evaluation.label, llm_triage_show_in_triage: !!evaluation.show_in_triage,
        llm_triage_rationale: evaluation.rationale, llm_triage_prompt_version: evaluation.prompt_version
      });
    });
    [
      ["recurring_scheme", report.recurring_schemes || []],
      ["funding_prospect", report.funding_prospects || []]
    ].forEach(function (group) {
      group[1].forEach(function (item) {
        var evaluation = item.llm_evaluation || {};
        var signals = item.signals || [];
        rows.push({
          item_kind: group[0], canonical_item_id: item.id,
          title: item.scheme_name || item.organization_name, organization_name: item.organization_name,
          status: group[0] === "recurring_scheme" ? "current window not verified" : "prospect only",
          eligibility: "Not assessed", identity_resolution_quality: item.identity_resolution_quality,
          source_provider: Array.from(new Set(signals.flatMap(function (signal) {
            return (signal.matched_evidence || []).map(function (evidence) { return evidence.source_kind || evidence.provider_id; });
          }).filter(Boolean))).join("; "),
          top_signals: signals.slice(0, 5).map(function (signal) {
            return String(signal.signal_type || "signal").replace(/_/g, " ") + (signal.explanation ? ": " + signal.explanation : "");
          }).join("; "),
          matched_facets: signals.flatMap(function (signal) { return signal.matched_profile_facets || []; })
            .map(function (facet) { return facet.facet + ": " + facet.value; }).slice(0, 12).join("; "),
          interpretation_boundary: group[0] === "recurring_scheme"
            ? "Repetition was detected from prior cycles; a current funding window was not verified."
            : "Portfolio alignment is inferred from observed records; this is not an explicit funder policy.",
          llm_triage_label: evaluation.label, llm_triage_show_in_triage: !!evaluation.show_in_triage,
          llm_triage_rationale: evaluation.rationale, llm_triage_prompt_version: evaluation.prompt_version
        });
      });
    });
    return [headings.join(",")].concat(rows.map(function (row) {
      return headings.map(function (heading) { return csvCell(row[heading]); }).join(",");
    })).join("\r\n") + "\r\n";
  }

  function requestParts(input, init) {
    var raw = typeof input === "string" ? input : input.url;
    var method = String((init && init.method) || (typeof input !== "string" && input.method) || "GET").toUpperCase();
    var parsed = new URL(raw, window.location.origin);
    return { method: method, path: parsed.pathname, search: parsed.searchParams };
  }

  function demoPath(parts) {
    var basePath = base.pathname.replace(/\/$/, "");
    var path = parts.path;
    if (basePath && path.indexOf(basePath + "/") === 0) path = path.slice(basePath.length);
    return path || "/";
  }

  function paperById(snapshot, id) {
    return snapshot.api.papers.find(function (paper) { return Number(paper.list_item.id) === Number(id); });
  }

  function wipById(snapshot, id) {
    return snapshot.api.wip.by_id[String(id)] || null;
  }

  function filteredWip(snapshot, search) {
    var items = snapshot.api.wip.manuscripts.slice();
    var query = String(search.get("query") || "").trim().toLowerCase();
    if (query) items = items.filter(function (item) {
      return [item.display_title, item.manuscript_type, item.target_journal, item.notes]
        .join(" ").toLowerCase().indexOf(query) >= 0;
    });
    ["state", "stage"].forEach(function (key) {
      var value = String(search.get(key) || "");
      if (value) items = items.filter(function (item) { return item[key] === value; });
    });
    if (search.get("has_open_tasks") === "true") items = items.filter(function (item) { return item.open_task_count > 0; });
    if (search.get("has_unresolved_findings") === "true") items = items.filter(function (item) { return item.unresolved_finding_count > 0; });
    return items;
  }

  function filteredPapers(snapshot, search) {
    var items = snapshot.api.papers.map(function (paper) { return paper.list_item; });
    var query = String(search.get("q") || "").trim().toLowerCase();
    if (query) {
      items = items.filter(function (paper) {
        return [paper.title, paper.venue].concat(paper.authors || []).join(" ").toLowerCase().indexOf(query) >= 0;
      });
    }
    var tagId = Number(search.get("tag_id") || 0);
    if (tagId) {
      items = items.filter(function (item) {
        var paper = paperById(snapshot, item.id);
        return paper && (paper.detail.tags || []).some(function (tag) { return Number(tag.id) === tagId; });
      });
    }
    var axisId = String(search.get("axis_id") || "");
    if (axisId) {
      var axisPaperIds = new Set((snapshot.api.axis_clusters[axisId] || []).flatMap(function (node) {
        return (node.papers || []).map(function (paper) { return Number(paper.id); });
      }));
      items = items.filter(function (item) { return axisPaperIds.has(Number(item.id)); });
    }
    var priority = String(search.get("priority") || "");
    if (priority) items = items.filter(function (item) { return item.priority === priority; });
    var offset = Math.max(0, Number(search.get("offset") || 0));
    var limit = Math.max(1, Number(search.get("limit") || 50));
    return items.slice(offset, offset + limit);
  }

  var EMPTY_ARRAY_PATHS = [
    "/collections", "/saved-searches", "/findings/overview",
    "/reference-integrity/overview", "/jobs/active"
  ];

  window.CALLOSUM_DATA_PROVIDER = {
    mode: "static-demo",
    fetch: async function (input, init) {
      var snapshot = await snapshotPromise;
      if (snapshot.manifest.snapshot_schema_version !== demoConfig.snapshot_schema_version) {
        throw new Error("Incompatible demo snapshot. Regenerate it with the current Callosum exporter.");
      }
      var parts = requestParts(input, init || {});
      var path = demoPath(parts);
      var feedStateMatch = path.match(/^\/feed\/items\/(\d+)\/state$/);
      if (parts.method === "POST" && feedStateMatch) {
        var feedState = loadFeedState(snapshot);
        var feedBody = requestBody(init || {});
        var feedKey = feedStateMatch[1];
        if (typeof feedBody.is_read === "boolean") feedState.read[feedKey] = feedBody.is_read;
        if (typeof feedBody.is_starred === "boolean") feedState.starred[feedKey] = feedBody.is_starred;
        saveFeedState(feedState);
        return jsonResponse({ id: Number(feedKey), changed: true });
      }
      if (parts.method === "POST" && path === "/feed/mark-read") {
        var allReadState = loadFeedState(snapshot);
        allReadState.all_read = true;
        allReadState.read = {};
        saveFeedState(allReadState);
        return jsonResponse({ marked: snapshot.api.extended.feed.items.length });
      }
      if (parts.method === "POST" && path === "/demo/feed-state/reset") {
        saveFeedState({ version: 1, initialized: true, all_read: false, read: {}, starred: {} });
        return jsonResponse({ reset: true });
      }
      if (parts.method === "POST" && path === "/citations/render") {
        var renderBody = requestBody(init || {});
        var renderIds = renderBody.paper_ids || [];
        var savedRendering = renderIds.length === 1 && renderBody.style === "apa"
          ? snapshot.api.extended.work.citation_renderings[String(renderIds[0])] : null;
        if (savedRendering) return jsonResponse(savedRendering);
        var renderMessage = "Only the saved APA citations are available online. Rendering another paper or style requires Callosum's local citation engine.";
        blocked(renderMessage, path);
        return jsonResponse({ detail: renderMessage }, 405);
      }
      if (parts.method === "POST" && path === "/papers/export") {
        var exportBody = requestBody(init || {});
        var exportIds = exportBody.paper_ids || [];
        var savedBibtex = exportIds.length === 1 && exportBody.format === "bibtex"
          ? snapshot.api.extended.work.citation_bibtex[String(exportIds[0])] : null;
        if (savedBibtex) return textResponse(savedBibtex, "application/x-bibtex; charset=utf-8");
        var exportMessage = "Only the saved Cite suggestions' BibTeX entries are available online. Other exports require the local library.";
        blocked(exportMessage, path);
        return jsonResponse({ detail: exportMessage }, 405);
      }
      if (parts.method !== "GET") {
        var mutationMessage = mutationBlockedMessage(path);
        blocked(mutationMessage, path);
        return jsonResponse({ detail: mutationMessage }, 405);
      }
      if (path === "/health") return jsonResponse(snapshot.api.health);
      if (path === "/help/corpus") return jsonResponse(snapshot.api.help_corpus);
      if (path === "/settings") return jsonResponse(snapshot.api.settings);
      if (path === "/settings/providers") return jsonResponse({
        active_provider: "local", active_model: "",
        wire_formats: ["messages", "chat_completions", "responses"],
        providers: [
          { id: "gemini", name: "Gemini", wire_format: "messages", base_url: null, models: [], builtin: true, key_set: false, active: false },
          { id: "openai", name: "OpenAI", wire_format: "responses", base_url: null, models: [], builtin: true, key_set: false, active: false },
          { id: "anthropic", name: "Anthropic", wire_format: "messages", base_url: null, models: [], builtin: true, key_set: false, active: false },
          { id: "local", name: "Local / loopback", wire_format: "chat_completions", base_url: "", models: [], builtin: true, key_set: false, active: true }
        ]
      });
      if (path === "/sync/status") return jsonResponse({ enabled: false, configured: false, signed_in: false, server_url: null, last_cursor: 0 });
      if (path === "/sync/conflicts") return jsonResponse([]);
      if (path === "/agent/writes") return jsonResponse([]);
      if (path === "/usage/summary") return jsonResponse({ enabled: true, types: [
        { event_type: "citation_exported", label: "Citations exported", all_time: 0, last_30_days: 0 },
        { event_type: "duplicate_resolved", label: "Duplicates resolved", all_time: 0, last_30_days: 0 },
        { event_type: "metadata_reresolved", label: "Metadata records re-resolved", all_time: 0, last_30_days: 0 },
        { event_type: "quote_located", label: "Evidence quotes located", all_time: 0, last_30_days: 0 },
        { event_type: "reference_reviewed", label: "Reference signals reviewed", all_time: 0, last_30_days: 0 }
      ] });
      if (path === "/feedback/capability") return jsonResponse({
        enabled: false, schema_version: "callosum-feedback/1", report_id: "demo-report-preview",
        app_version: snapshot.manifest.callosum_version, operating_system: "Static online demo", installation_type: "browser"
      });
      if (path === "/my-publications/dashboard") return jsonResponse(snapshot.api.my_publications_dashboard);
      if (path === "/my-publications/profile") return jsonResponse(snapshot.api.my_publications_profile);
      if (path === "/my-publications/citation-gaps") return jsonResponse(snapshot.api.extended.discover.citation_gaps);
      if (path === "/my-publications/emerging-citing-topics") return jsonResponse(snapshot.api.extended.discover.emerging_topics);
      if (path === "/my-publications/citing-authors") return jsonResponse(snapshot.api.extended.discover.citing_authors);
      var citingMatch = path.match(/^\/my-publications\/citing\/(W\d+)$/);
      if (citingMatch) {
        var citing = snapshot.api.my_publications_citing[citingMatch[1]];
        return citing ? jsonResponse(citing) : jsonResponse({ detail: "Saved cited-by result not found" }, 404);
      }
      if (path === "/axes") return jsonResponse(snapshot.api.axes);
      var axisMatch = path.match(/^\/axes\/(\d+)\/clusters$/);
      if (axisMatch) return jsonResponse(snapshot.api.axis_clusters[axisMatch[1]] || []);
      if (path === "/tags") return jsonResponse(snapshot.api.tags);
      if (path === "/tags/colors") return jsonResponse(snapshot.api.tag_colors);
      if (path === "/reading-queue") return jsonResponse(snapshot.api.reading_queue);
      if (path === "/citations/styles") {
        return jsonResponse({
          default_style: "apa", default_locale: "en-US", favorite_style_ids: [], recent_style_ids: [],
          locales: ["en-US", "en-GB"],
          styles: [{
            id: "apa", title: "APA", full_title: "American Psychological Association 7th edition",
            short_title: "APA", summary: "Bundled author-date style.", family: "author-date",
            citation_format: "author-date", fields: [], independent: true, parent_style: null,
            custom: false, favorite: false, recent_rank: null, application_default: true
          }]
        });
      }
      if (path === "/discovery/sources") return jsonResponse({ sources: snapshot.api.extended.discover.search.sources });
      if (path === "/discovery/search") {
        if (String(parts.search.get("q") || "") !== snapshot.api.extended.discover.search.query ||
            String(parts.search.get("source") || "") !== snapshot.api.extended.discover.search.source) {
          var searchMessage = "New literature searches are unavailable in the online demo. This saved result remains inspectable.";
          blocked(searchMessage, path);
          return jsonResponse({ detail: searchMessage }, 405);
        }
        return jsonResponse({ items: snapshot.api.extended.discover.search.items });
      }
      if (path === "/feed/subscriptions") return jsonResponse({
        subscriptions: snapshot.api.extended.feed.subscriptions,
        source_types: snapshot.api.extended.feed.kinds,
        source_meta: snapshot.api.extended.feed.source_meta
      });
      if (path === "/feed") {
        var allFeedItems = feedItemsWithLocalState(snapshot);
        var feedItems = allFeedItems.slice();
        if (parts.search.get("unread") === "true") feedItems = feedItems.filter(function (item) { return !item.is_read; });
        if (parts.search.get("starred") === "true") feedItems = feedItems.filter(function (item) { return item.is_starred; });
        var subscriptionId = Number(parts.search.get("subscription_id") || 0);
        if (subscriptionId) feedItems = feedItems.filter(function (item) { return Number(item.subscription_id) === subscriptionId; });
        var feedLimit = Math.min(500, Math.max(1, Number(parts.search.get("limit") || 200)));
        return jsonResponse({
          items: feedItems.slice(0, feedLimit),
          unread_count: allFeedItems.filter(function (item) { return !item.is_read; }).length
        });
      }
      if (path === "/feed/library-journals") return jsonResponse({ journals: snapshot.api.extended.feed.library_journals });
      if (path === "/followed-authors") return jsonResponse(snapshot.api.extended.discover.followed_authors);
      if (path === "/feed/suggest-authors") return jsonResponse({ authors: snapshot.api.extended.discover.suggested_authors });
      if (path === "/funding-discovery/saved") return jsonResponse({ items: snapshot.api.extended.discover.saved_funding });
      if (path === "/funding-discovery/runs") return jsonResponse({ runs: snapshot.api.extended.discover.funding_runs });
      var fundingRunMatch = path.match(/^\/funding-discovery\/runs\/(\d+)$/);
      if (fundingRunMatch) {
        var fundingReport = snapshot.api.extended.discover.funding_reports[fundingRunMatch[1]];
        return fundingReport ? jsonResponse({ report: fundingReport }) : jsonResponse({ detail: "Saved funding run not found" }, 404);
      }
      var fundingCsvMatch = path.match(/^\/funding-discovery\/runs\/(\d+)\/export\.csv$/);
      if (fundingCsvMatch) {
        var fundingCsvReport = snapshot.api.extended.discover.funding_reports[fundingCsvMatch[1]];
        return fundingCsvReport
          ? textResponse(fundingCsv(fundingCsvReport), "text/csv; charset=utf-8")
          : jsonResponse({ detail: "Saved funding run not found" }, 404);
      }
      if (path === "/wanted") return jsonResponse(snapshot.api.extended.discover.wanted || { items: [] });
      if (path === "/wanted/coverage") return jsonResponse(snapshot.api.extended.discover.wanted_coverage || {
        library_total: snapshot.api.papers.length, with_pdf: snapshot.api.papers.length,
        acquired_oa: { gold: 0, green: 0, bronze: 0 }, wanted_open: 0
      });
      if (path === "/gaps") return jsonResponse(snapshot.api.extended.discover.literature_gaps || { candidates: [], computed_at: null });
      if (path === "/overlooked") {
        var savedOverlooked = snapshot.api.extended.discover.overlooked_by_axis[String(parts.search.get("axis_id") || "")];
        return jsonResponse(savedOverlooked || { candidates: [], computed_at: null });
      }
      if (path === "/citations/beyond-library/saved") return jsonResponse(snapshot.api.extended.discover.beyond_library_saved || { items: [] });
      if (path === "/workbench/projects") return jsonResponse(snapshot.api.extended.work.workbench_projects);
      var workbenchMatch = path.match(/^\/workbench\/projects\/(\d+)$/);
      if (workbenchMatch) {
        var workbench = snapshot.api.extended.work.workbench_details[workbenchMatch[1]];
        return workbench ? jsonResponse(workbench) : jsonResponse({ detail: "Saved workbench project not found" }, 404);
      }
      var workbenchExportMatch = path.match(/^\/workbench\/projects\/(\d+)\/export$/);
      if (workbenchExportMatch) {
        var exportFormat = String(parts.search.get("format") || "csv");
        var projectExports = snapshot.api.extended.work.workbench_exports[workbenchExportMatch[1]] || {};
        var savedProjectExport = projectExports[exportFormat];
        if (!savedProjectExport) return jsonResponse({ detail: "Saved workbench export not found" }, 404);
        return textResponse(savedProjectExport, exportFormat === "audit" ? "application/json" : "text/csv; charset=utf-8");
      }
      if (path === "/credit/pending") return jsonResponse(snapshot.api.extended.work.credit_pending);
      if (path === "/statements/pending") return jsonResponse(snapshot.api.extended.work.statements_pending);
      if (path === "/saved-searches") return jsonResponse(snapshot.api.extended.library.saved_searches);
      if (path === "/reference-integrity/overview") return jsonResponse(snapshot.api.extended.work.reference_overview);
      if (path === "/demo/saved-artifacts/search") return jsonResponse(snapshot.api.extended.discover.search);
      if (path === "/demo/saved-artifacts/journals") return jsonResponse(snapshot.api.extended.discover.journals);
      if (path === "/demo/saved-artifacts/cite") return jsonResponse({ claim: snapshot.api.extended.work.cite_claim, result: snapshot.api.extended.work.cite });
      if (path === "/demo/saved-artifacts/credit") return jsonResponse({ authors: snapshot.api.extended.work.credit_authors, result: snapshot.api.extended.work.credit_result });
      if (path === "/demo/saved-artifacts/statements") return jsonResponse(snapshot.api.extended.work.statement_drafts);
      if (path === "/wip/watch-roots") return jsonResponse([]);
      if (path === "/wip/manuscripts") return jsonResponse(filteredWip(snapshot, parts.search));
      var wipMatch = path.match(/^\/wip\/manuscripts\/(\d+)\/(files|activity|sections|tasks|references|snapshots|checks|funding-runs|journal-runs|reference-integrity)$/);
      if (wipMatch) {
        var wip = wipById(snapshot, wipMatch[1]);
        if (!wip) return jsonResponse({ detail: "WIP manuscript not found" }, 404);
        var wipKey = wipMatch[2].replace(/-/g, "_");
        if (wipKey === "funding_runs" || wipKey === "journal_runs") return jsonResponse({ runs: wip[wipKey] || [] });
        return jsonResponse(wip[wipKey]);
      }
      if (path === "/status/jobs") return jsonResponse(snapshot.api.status);
      if (path === "/summaries") return jsonResponse(snapshot.api.summary_index);
      var summaryMatch = path.match(/^\/summaries\/(\d+)$/);
      if (summaryMatch) {
        var summary = snapshot.api.summaries[summaryMatch[1]];
        return summary ? jsonResponse(summary) : jsonResponse({ detail: "Summary not found" }, 404);
      }
      if (path === "/papers") return jsonResponse(filteredPapers(snapshot, parts.search));
      if (path === "/papers/item-types") {
        var counts = {};
        snapshot.api.papers.forEach(function (paper) {
          var kind = paper.detail.item_type || "article-journal";
          counts[kind] = (counts[kind] || 0) + 1;
        });
        return jsonResponse(Object.keys(counts).sort().map(function (kind) { return { item_type: kind, count: counts[kind] }; }));
      }
      var positionMatch = path.match(/^\/papers\/(\d+)\/position$/);
      if (positionMatch) {
        var filtered = filteredPapers(snapshot, parts.search);
        var index = filtered.findIndex(function (paper) { return Number(paper.id) === Number(positionMatch[1]); });
        return index >= 0 ? jsonResponse({ index: index }) : jsonResponse({ detail: "Paper not found" }, 404);
      }
      var annotationsMatch = path.match(/^\/papers\/(\d+)\/annotations$/);
      if (annotationsMatch) return jsonResponse(snapshot.api.extended.library.annotations[annotationsMatch[1]] || []);
      var referenceMatch = path.match(/^\/papers\/(\d+)\/reference-integrity$/);
      if (referenceMatch) {
        var referenceReport = snapshot.api.extended.work.reference_integrity[referenceMatch[1]];
        return referenceReport ? jsonResponse(referenceReport) : jsonResponse({ detail: "Saved reference report not found" }, 404);
      }
      var equityMatch = path.match(/^\/demo\/saved-artifacts\/citation-equity\/(\d+)$/);
      if (equityMatch) return jsonResponse(snapshot.api.extended.work.citation_equity[equityMatch[1]] || null);
      var overlookedMatch = path.match(/^\/demo\/saved-artifacts\/overlooked-work\/(\d+)$/);
      if (overlookedMatch) return jsonResponse(snapshot.api.extended.work.overlooked_work[overlookedMatch[1]] || null);
      var contextMatch = path.match(/^\/demo\/saved-artifacts\/citation-context\/(\d+)\/(incoming|outgoing)$/);
      if (contextMatch) {
        var contextMap = contextMatch[2] === "incoming"
          ? snapshot.api.extended.work.citation_context_incoming
          : snapshot.api.extended.work.citation_context_outgoing;
        return jsonResponse(contextMap[contextMatch[1]] || null);
      }
      var savedCheckMatch = path.match(/^\/papers\/(\d+)\/(grim-checks|debit-checks|duplicate-value-checks)$/);
      if (savedCheckMatch) {
        var checkMap = {
          "grim-checks": snapshot.api.extended.library.grim_checks,
          "debit-checks": snapshot.api.extended.library.debit_checks,
          "duplicate-value-checks": snapshot.api.extended.library.duplicate_value_checks
        }[savedCheckMatch[2]];
        return jsonResponse({ checks: checkMap[savedCheckMatch[1]] || [] });
      }
      var suggestedTagsMatch = path.match(/^\/papers\/(\d+)\/suggested-tags$/);
      if (suggestedTagsMatch) {
        var suggestions = snapshot.api.suggested_tags[suggestedTagsMatch[1]];
        return suggestions ? jsonResponse(suggestions) : jsonResponse({ detail: "Paper not found" }, 404);
      }
      var savedCriticalMatch = path.match(/^\/papers\/(\d+)\/critical-read\/saved$/);
      if (savedCriticalMatch) {
        var critical = snapshot.api.synthesis.critical_reads[savedCriticalMatch[1]];
        return critical ? jsonResponse(critical) : jsonResponse({ detail: "Saved critical read not found" }, 404);
      }
      var criticalCandidatesMatch = path.match(/^\/papers\/(\d+)\/critical-read\/candidates$/);
      if (criticalCandidatesMatch) {
        return jsonResponse(snapshot.api.synthesis.critical_candidates[criticalCandidatesMatch[1]] || { candidates: [] });
      }
      var findingsMatch = path.match(/^\/papers\/(\d+)\/findings$/);
      if (findingsMatch) return jsonResponse({ facts: [], candidates: [] });
      var registrationLinksMatch = path.match(/^\/papers\/(\d+)\/registration-links$/);
      if (registrationLinksMatch) {
        return jsonResponse(snapshot.api.synthesis.registration_links[registrationLinksMatch[1]] || []);
      }
      var registrationVersionsMatch = path.match(/^\/papers\/(\d+)\/registration-versions$/);
      if (registrationVersionsMatch) {
        return jsonResponse(snapshot.api.synthesis.registration_versions[registrationVersionsMatch[1]] || []);
      }
      var registrationRunsMatch = path.match(/^\/papers\/(\d+)\/registration-comparisons$/);
      if (registrationRunsMatch) {
        return jsonResponse(snapshot.api.synthesis.registration_comparison_runs[registrationRunsMatch[1]] || []);
      }
      var registrationDetailMatch = path.match(/^\/papers\/(\d+)\/registration-comparisons\/(\d+)$/);
      if (registrationDetailMatch) {
        var comparison = snapshot.api.synthesis.registration_comparison_details[registrationDetailMatch[2]];
        return comparison && Number(comparison.paper_id) === Number(registrationDetailMatch[1])
          ? jsonResponse(comparison) : jsonResponse({ detail: "Saved comparison not found" }, 404);
      }
      var pdfMatch = path.match(/^\/papers\/(\d+)\/pdf$/);
      if (pdfMatch) {
        var pdfPaper = paperById(snapshot, pdfMatch[1]);
        if (!pdfPaper || !pdfPaper.document.asset_path) return jsonResponse({ detail: "Document unavailable" }, 404);
        var requestedAttachmentId = parts.search.get("attachment_id");
        if (requestedAttachmentId != null) {
          var knownAttachmentIds = (pdfPaper.detail.attachments || []).map(function (attachment) { return String(attachment.id); });
          if (knownAttachmentIds.indexOf(String(requestedAttachmentId)) < 0) {
            return jsonResponse({ detail: "This locator points at a document the public snapshot has no redistribution right to bundle (for example, an unlicensed registration record). Only this paper's own licensed PDF is available in the online demo." }, 404);
          }
        }
        var assetUrl = new URL(pdfPaper.document.asset_path, base);
        if (assetUrl.origin !== window.location.origin || assetUrl.pathname.indexOf(base.pathname) !== 0) {
          throw new Error("Demo document escaped the static base path");
        }
        return networkFetch(assetUrl, { credentials: "omit", cache: "force-cache" });
      }
      var methodMatch = path.match(/^\/papers\/(\d+)\/(statcheck\/cached|transparency|lmm|bayes|meta-analysis)$/);
      if (methodMatch) {
        var methodPaper = paperById(snapshot, methodMatch[1]);
        if (!methodPaper) return jsonResponse({ detail: "Paper not found" }, 404);
        var methodKey = {
          "statcheck/cached": "statcheck", "transparency": "transparency", "lmm": "lmm",
          "bayes": "bayes", "meta-analysis": "meta_analysis"
        }[methodMatch[2]];
        return jsonResponse(methodPaper.methods[methodKey]);
      }
      var detailMatch = path.match(/^\/papers\/(\d+)$/);
      if (detailMatch) {
        var detailPaper = paperById(snapshot, detailMatch[1]);
        return detailPaper ? jsonResponse(detailPaper.detail) : jsonResponse({ detail: "Paper not found" }, 404);
      }
      var methodSummaryMatch = path.match(/^\/methods\/(statcheck|transparency|lmm|meta-analysis|bayes)\/summary$/);
      if (methodSummaryMatch) {
        var summaryKey = methodSummaryMatch[1].replace("meta-analysis", "meta_analysis");
        return jsonResponse(snapshot.api.method_summaries[summaryKey]);
      }
      if (path === "/methods/retraction/summary") return jsonResponse({ retracted: 0 });
      if (EMPTY_ARRAY_PATHS.indexOf(path) >= 0) return jsonResponse([]);
      var missingReadMessage = /^\/integrations\/libreoffice/.test(path)
        ? "The LibreOffice extension is installed on the user's computer and is not bundled as a web-demo download. Its real workflow and setup instructions remain inspectable here."
        : /^\/integrations\/word/.test(path)
          ? "The Word manifest belongs to an installed local Callosum instance and is not bundled as a web-demo download. Its real setup boundary remains inspectable here."
          : /^\/citations\/styles\//.test(path)
            ? "Browsing the remote CSL style repository, exporting, checking for updates, or previewing another installed style requires Callosum's local citeproc engine. Only the one saved default style is available in this demo."
            : "This read-only surface is not included in the current demo snapshot. No network request was made. Install Callosum for live local data, or inspect the saved surfaces available in this demo.";
      blocked(missingReadMessage, path);
      return jsonResponse({ detail: missingReadMessage }, 404);
    }
  };

  // Development safeguard: only the snapshot and its same-base static assets may use the browser network.
  // Callosum API traffic never reaches this shim because CALLOSUM_DATA_PROVIDER resolves it in memory.
  window.fetch = function (input, init) {
    var url = new URL(typeof input === "string" ? input : input.url, window.location.href);
    var allowed = url.origin === window.location.origin && url.pathname.indexOf(base.pathname) === 0;
    if (!allowed) {
      var message = "Unexpected network request blocked by the static demo: " + url.href;
      blocked(message, url.pathname);
      return Promise.reject(new Error(message));
    }
    return networkFetch(input, init);
  };
})();
