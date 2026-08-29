/*
 * Callosum Word add-in — PURE logic (no Office.js, no DOM).
 *
 * Kept separate from taskpane.js so it is unit-testable with `node --test` (no browser, no Office host) — which
 * matters especially because there is no headless Word to exercise the Office.js glue. The browser uses these as
 * `CallosumCore.*`; the test file `require()`s them in Node. Mirrors the LibreOffice adapter's pure helpers.
 *
 * SP2 (inc 165): each citation is a Word **Content Control**. Legacy controls carry base64 CSL-JSON directly in
 * `.tag`; current controls carry only a short Custom XML Part reference, keeping unbounded scholarly metadata
 * out of Word's tag property. A Refresh resolves those controls in document order, POSTs them to
 * /citations/render-document, and writes back the position-aware in-text + bibliography.
 *
 * SP4: Word-on-the-web relay. Desktop Word loads this page same-origin from callosum (no token needed); Word
 * Online instead loads it through the existing cloudflared cite-only tunnel (a different origin), which is
 * gated by callosum's Remote-access bearer token. `isLocalOrigin`/`authHeaders` decide, from `location.hostname`
 * alone, whether a fetch needs that header -- desktop behavior is unchanged either way.
 */
(function (root) {
  var CITATION_PREFIX = "CALLOSUM_CITATION"; // content-control tag prefix for a citation cluster
  var CITATION_REFERENCE_MARKER = "xml:";
  var MAX_CITATION_REFERENCE_LENGTH = 256;
  var CITATION_XML_NAMESPACE = "https://callosum.app/schemas/word-citation/1";
  var BIB_TAG = "CALLOSUM_BIBLIOGRAPHY"; // content-control tag for the managed bibliography block

  // UTF-8-safe base64 (CSL-JSON has unicode author names). btoa/atob + TextEncoder/TextDecoder are global in both
  // modern browsers and Node 16+ (the add-in runs in Word's webview; tests run in Node).
  function b64encode(str) {
    var bytes = new TextEncoder().encode(str);
    var bin = "";
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }
  function b64decode(b64) {
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  // ---- search (SP1, unchanged) ----
  function authorLabel(authors) {
    if (!Array.isArray(authors) || authors.length === 0) return "Unknown";
    var first = String(authors[0] || "").split(",")[0].trim() || "Unknown";
    return authors.length > 1 ? first + " et al." : first;
  }
  function formatSearchRows(papers) {
    if (!Array.isArray(papers)) return [];
    return papers.map(function (p) {
      var year = p && p.year ? " (" + p.year + ")" : "";
      var title = (p && p.title) ? String(p.title) : "Untitled";
      return { id: p && p.id, label: authorLabel(p && p.authors) + year + " — " + title };
    }).filter(function (r) { return r.id != null; });
  }

  // The CSL-JSON record for an inserted paper, from a /papers/export (csl-json) response (a JSON array).
  function firstCslRecord(arr) {
    return (Array.isArray(arr) && arr.length) ? arr[0] : null;
  }

  // ---- live-citation storage (SP2; short-reference redesign) ----
  // Legacy tag = "CALLOSUM_CITATION <base64 of {items:[csl, ...]}>". Kept readable so existing documents can
  // be migrated without losing citations; no new citation is written in this format.
  function encodeCitationTag(items) {
    return CITATION_PREFIX + " " + b64encode(JSON.stringify({ items: items || [] }));
  }
  function isCitationTag(tag) {
    return typeof tag === "string" && tag.indexOf(CITATION_PREFIX + " ") === 0;
  }
  function decodeCitationTag(tag) {
    if (!isCitationTag(tag) || citationReferenceId(tag) != null) return null;
    try {
      var payload = JSON.parse(b64decode(tag.slice((CITATION_PREFIX + " ").length)));
      var items = payload && Array.isArray(payload.items) ? payload.items : [];
      return items.length ? items : null;
    } catch (e) {
      return null; // malformed → never guess; the caller skips it
    }
  }

  // Current tag = "CALLOSUM_CITATION xml:<encoded CustomXmlPart.id>". The reference is deliberately bounded;
  // CSL-JSON lives in the corresponding Custom XML Part, never in the tag. `encodeURIComponent` handles the
  // braced GUID form Word commonly returns without constraining Word's documented opaque ID representation.
  function encodeCitationReferenceTag(partId) {
    var id = String(partId || "").trim();
    var encodedId = encodeURIComponent(id);
    if (!id || encodedId.length > MAX_CITATION_REFERENCE_LENGTH) throw new Error("invalid citation XML part id");
    return CITATION_PREFIX + " " + CITATION_REFERENCE_MARKER + encodedId;
  }
  function citationReferenceId(tag) {
    var prefix = CITATION_PREFIX + " " + CITATION_REFERENCE_MARKER;
    if (typeof tag !== "string" || tag.indexOf(prefix) !== 0) return null;
    try {
      var encodedId = tag.slice(prefix.length);
      if (encodedId.length > MAX_CITATION_REFERENCE_LENGTH) return null;
      var id = decodeURIComponent(encodedId).trim();
      return id || null;
    } catch (e) {
      return null;
    }
  }
  function isLegacyCitationTag(tag) {
    return isCitationTag(tag) && tag.indexOf(CITATION_PREFIX + " " + CITATION_REFERENCE_MARKER) !== 0;
  }

  // The XML body is intentionally tiny and deterministic. Base64 keeps arbitrary CSL-JSON text out of XML
  // syntax while retaining exact UTF-8 round trips. Only this exact namespace/schema is accepted; malformed or
  // foreign parts fail closed rather than being guessed into a citation.
  function encodeCitationXml(items) {
    if (!Array.isArray(items) || items.length === 0) throw new Error("citation items are required");
    return '<?xml version="1.0" encoding="UTF-8"?>' +
      '<callosumCitation xmlns="' + CITATION_XML_NAMESPACE + '" version="1">' +
      '<payload encoding="base64">' + b64encode(JSON.stringify({ items: items })) + "</payload>" +
      "</callosumCitation>";
  }
  function decodeCitationXml(xml) {
    if (typeof xml !== "string") return null;
    var rootMatch = xml.match(/<callosumCitation\b([^>]*)>([\s\S]*?)<\/callosumCitation>\s*$/);
    if (!rootMatch) return null;
    var attrs = rootMatch[1];
    if (attrs.indexOf('xmlns="' + CITATION_XML_NAMESPACE + '"') === -1 ||
        !/\bversion="1"/.test(attrs)) return null;
    var payloadMatch = rootMatch[2].match(/^\s*<payload\s+encoding="base64">([A-Za-z0-9+/=]+)<\/payload>\s*$/);
    if (!payloadMatch) return null;
    try {
      var payload = JSON.parse(b64decode(payloadMatch[1]));
      return payload && Array.isArray(payload.items) && payload.items.length ? payload.items : null;
    } catch (e) {
      return null;
    }
  }

  // Office.js resolves current tags asynchronously, then passes `{tag, items}` records to the pure diagnostic
  // and panel helpers. Tests and legacy callers may still pass raw tags; this compatibility seam keeps document
  // analysis pure while making missing/malformed Custom XML Parts explicit (`items: null`).
  function citationItems(recordOrTag) {
    if (typeof recordOrTag === "string") return decodeCitationTag(recordOrTag);
    if (!recordOrTag || !isCitationTag(recordOrTag.tag)) return null;
    if (Array.isArray(recordOrTag.items) && recordOrTag.items.length) return recordOrTag.items;
    return isLegacyCitationTag(recordOrTag.tag) ? decodeCitationTag(recordOrTag.tag) : null;
  }

  // ---- reliable paper-id tracking (inc 512) ----
  // /papers/export returns the STORED, un-normalized csl_json.id verbatim (confirmed by reading
  // citation_export.py's to_csl_json) -- NOT guaranteed to equal the paper's real numeric database id (it
  // depends on how the paper was originally imported: a Zotero key, a DOI-based id, etc. could end up there).
  // Rendering doesn't care (render_document is self-contained -- each cluster carries its own full record, so
  // `id` is only an internal citeproc correlation key within one request) but anything that needs to know
  // WHICH library paper a citation references does. Mirrors callosum_cite.py:307's own `_build_records`
  // convention exactly, rather than inventing a different one: stamp a known-reliable id at insert time.
  var CALLOSUM_ID_PREFIX = "callosum-";
  function stampCallosumId(csl, paperId) {
    return Object.assign({}, csl, { id: CALLOSUM_ID_PREFIX + paperId });
  }
  // The inverse: strip the prefix, or null if it's absent (a citation inserted before this convention existed,
  // or a foreign one) -- never guess at a paper id that wasn't actually stamped.
  function extractPaperId(cslId) {
    var s = String(cslId || "");
    return s.indexOf(CALLOSUM_ID_PREFIX) === 0 ? s.slice(CALLOSUM_ID_PREFIX.length) : null;
  }

  // ---- the document render-document contract (SP2) ----
  // itemsList is the per-cluster CSL-JSON item arrays in DOCUMENT ORDER (one per citation content control).
  function buildDocumentRequest(itemsList, style, locale) {
    return {
      citations: (itemsList || []).map(function (items, i) {
        return { citationID: "c" + i, items: items };
      }),
      style: style || "apa",
      locale: locale || "en-US",
    };
  }
  // The rendered in-text strings, in order, from a /citations/render-document response ({citations:[{text}]}).
  function inTextResults(data) {
    if (!data || !Array.isArray(data.citations)) return [];
    return data.citations.map(function (c) { return String((c && c.text) || ""); });
  }
  function bibliographyText(data) {
    return (data && data.bibliography_text) || "";
  }

  // ---- suggest-from-the-sentence (SP3) ----
  // The query text for /citations/suggest: the highlighted selection, else the paragraph the cursor sits in.
  function pickQueryText(selectionText, paragraphText) {
    var sel = (selectionText || "").trim();
    return sel || (paragraphText || "").trim();
  }
  // POST /citations/suggest body (text capped at the endpoint's 4000-char limit; evaluate → stance per candidate).
  function buildSuggestRequest(text, topK) {
    return { text: String(text || "").slice(0, 4000), top_k: topK || 8, evaluate: true };
  }
  function _stanceTag(stance) {
    return stance && stance.label ? "[" + stance.label + "]" : "[?]";
  }
  // Suggestion pick-rows: "[stance] Author Year · match N.NN — "quote…"" — the quote IS the reason (signal not verdict).
  function formatSuggestRows(suggestions) {
    if (!Array.isArray(suggestions)) return [];
    return suggestions.map(function (s) {
      var author = (s && s.author) ? s.author : "Unknown";
      var year = (s && s.year) ? " " + s.year : "";
      var match = (s && typeof s.match_score === "number") ? " · match " + s.match_score.toFixed(2) : "";
      var quote = (s && s.quote) ? ' — "' + String(s.quote).slice(0, 80).trim() + '…"' : "";
      return { id: s && s.paper_id, label: _stanceTag(s && s.stance) + " " + author + year + match + quote };
    }).filter(function (r) { return r.id != null; });
  }

  // ---- citation composer (inc 509, backlog #33/#34 P0 items 1-5): grouped citations + per-occurrence
  // locator/label/prefix/suffix/suppress-author/author-only. Mirrors adapters/libreoffice/composer.py's
  // `_item_overrides`/`_format_assembly_row`/`_assembly_item_from_decoded` exactly, so the same mental model
  // (an ordered "assembly" of {csl, ...overrides} rows, built by search/suggest then inserted as ONE cluster)
  // applies to both adapters even though the UI shells are unrelated.
  var LOCATOR_LABELS = [
    "book", "chapter", "column", "figure", "folio", "issue", "line", "note", "opus", "page",
    "paragraph", "part", "scene", "section", "sub-verbo", "supplement", "table", "verse", "volume",
  ]; // MUST match CSL_LOCATOR_LABELS in callosum_cite.py / app/backend/api/routers/citations.py exactly.
  var ASSEMBLY_OVERRIDE_KEYS = ["locator", "label", "prefix", "suffix", "suppress-author", "author-only"];

  // The per-occurrence override fields on one assembly row, ready to merge into its CSL record -- strips
  // default/empty/false values so a citation that overrides nothing renders an ordinary bare item (mirrors
  // composer.py's `_item_overrides`).
  function itemOverrides(row) {
    var out = {};
    ASSEMBLY_OVERRIDE_KEYS.forEach(function (k) {
      var v = row && row[k];
      if (v !== null && v !== undefined && v !== "" && v !== false) out[k] = v;
    });
    return out;
  }
  // Merge every assembly row's CSL record with its own overrides into the final `items` array a citation
  // cluster's tag carries -- encodeCitationTag already accepts arbitrary per-item keys unchanged.
  function buildClusterItems(assembly) {
    return (assembly || []).map(function (row) {
      return Object.assign({}, row && row.csl, itemOverrides(row));
    });
  }
  // A compact "Author (Year) — Title" row label built from a raw CSL-JSON record (not the /papers search
  // response shape formatSearchRows expects -- CSL authors are {family, given} objects, not "Last, First").
  function cslRecordRow(item) {
    var authors = (item && Array.isArray(item.author)) ? item.author : [];
    var first = (authors[0] && (authors[0].family || authors[0].literal)) || "Unknown";
    var authorLbl = authors.length > 1 ? first + " et al." : first;
    var dateParts = item && item.issued && Array.isArray(item.issued["date-parts"]) ? item.issued["date-parts"][0] : null;
    var year = (dateParts && dateParts[0]) ? " (" + dateParts[0] + ")" : "";
    var title = (item && item.title) ? String(item.title) : "Untitled";
    return authorLbl + year + " — " + title;
  }
  // The assembly-list display row: the base label plus a compact "[...]" summary of any active override, so
  // the user sees at a glance which assembled items carry one without opening its own options (mirrors
  // composer.py's `_format_assembly_row`).
  function formatAssemblyRow(row) {
    var tags = [];
    if (row.locator) tags.push((row.label || "loc.") + " " + row.locator);
    if (row.prefix) tags.push('prefix "' + row.prefix + '"');
    if (row.suffix) tags.push('suffix "' + row.suffix + '"');
    if (row["suppress-author"]) tags.push("no author");
    if (row["author-only"]) tags.push("author only");
    return tags.length ? row.row + "  [" + tags.join(", ") + "]" : row.row;
  }
  // Rebuild an assembly row from an EXISTING citation's already-decoded item (Edit Citation) -- separates the
  // per-occurrence override keys back out from the bare CSL record, so an edited citation's assembly rows have
  // the identical shape a fresh search-and-add produces (mirrors composer.py's `_assembly_item_from_decoded`).
  function assemblyRowFromDecodedItem(item) {
    var bareCsl = Object.assign({}, item);
    ASSEMBLY_OVERRIDE_KEYS.forEach(function (k) { delete bareCsl[k]; });
    var row = { csl: bareCsl, row: cslRecordRow(bareCsl) };
    ASSEMBLY_OVERRIDE_KEYS.forEach(function (k) {
      if (item && item[k] != null && item[k] !== false) row[k] = item[k];
    });
    return row;
  }

  // ---- Document diagnostics (inc 512, backlog #33/#34 P0 remainder) ----
  // Mirrors adapters/libreoffice/callosum_cite.py's `diagnose_document`/`citation_integrity_preflight` (inc
  // 459), narrowed to what Word's simpler tag model can actually check: Word has no embedded schema-version
  // field and no LibreOffice-style random mark identity distinct from Word's own (always-unique, Word-managed)
  // content-control id, so "unsupported schema version" and "duplicate mark identity" have no Word equivalent
  // and are deliberately not checked here -- narrower on purpose, not silently.
  //
  // `tags`: every content control's raw .tag string in the document (citations, the bibliography tag, and any
  // unrelated ones, which are ignored). `missingPaperIds`: real ids confirmed NOT to resolve via a per-id
  // /papers/export existence check (presence/count only -- never the response record's own .id VALUE, which
  // isn't guaranteed to match the requested id, the same problem this increment already fixed for citation
  // tags). NOT sourced from /methods/retraction/check-selected's own `not_found` -- that endpoint's internal
  // get_paper() lookup has no deleted_at filter, so a paper moved to TRASH still resolves as "found" there,
  // silently missing exactly the orphan case a user is most likely to test (confirmed live, not assumed: a
  // trashed paper's citation was reported clean until this was fixed). `retractionChecked`: the `checked` array
  // from that same endpoint, called only for ids already confirmed to exist.
  function summarizeDiagnostics(tags, missingPaperIds, retractionChecked) {
    var notFoundSet = {};
    (missingPaperIds || []).forEach(function (id) { notFoundSet[String(id)] = true; });
    var flaggedByPaperId = {};
    (retractionChecked || []).forEach(function (row) {
      var status = row && row.status;
      if (status && status !== "none" && status !== "unchecked") flaggedByPaperId[String(row.paper_id)] = row;
    });

    var citationCount = 0, malformedCount = 0, unresolvableItemCount = 0;
    var resolvedIds = {}, hasBibliography = false;
    (tags || []).forEach(function (recordOrTag) {
      var tag = typeof recordOrTag === "string" ? recordOrTag : recordOrTag && recordOrTag.tag;
      if (tag === BIB_TAG) { hasBibliography = true; return; }
      if (!isCitationTag(tag)) return;
      citationCount += 1;
      var items = citationItems(recordOrTag);
      if (!items) { malformedCount += 1; return; }
      items.forEach(function (item) {
        var pid = extractPaperId(item && item.id);
        if (pid == null) unresolvableItemCount += 1;
        else resolvedIds[pid] = true;
      });
    });

    var distinctPaperIds = Object.keys(resolvedIds);
    var orphanedPaperIds = distinctPaperIds.filter(function (id) { return notFoundSet[id]; });
    var retractionFlagged = distinctPaperIds
      .filter(function (id) { return flaggedByPaperId[id]; })
      .map(function (id) { return flaggedByPaperId[id]; });

    return {
      citationCount: citationCount,
      malformedCount: malformedCount,
      unresolvableItemCount: unresolvableItemCount,
      distinctPaperIds: distinctPaperIds,
      orphanedPaperIds: orphanedPaperIds,
      bibliography: citationCount === 0 ? "n/a" : (hasBibliography ? "ok" : "missing"),
      retractionFlagged: retractionFlagged,
    };
  }

  // ---- Citations-in-this-document panel (inc 516, backlog #33/#34 P1) ----
  // Groups repeated citations of the SAME library paper into one entry with an occurrence count + every
  // occurrence's position (an index into the document-order list of citation-tagged controls -- the same
  // "index into document order" concept refreshDocument/runDiagnostics already rely on). An item with no
  // resolvable paper id (extractPaperId returned null -- a pre-inc-512 legacy citation) gets its OWN singleton
  // entry rather than being guessed into an existing group.
  function buildCitationsPanelEntries(tags) {
    var entriesByKey = {};
    var order = [];
    var citationIndex = -1;
    (tags || []).forEach(function (recordOrTag) {
      var tag = typeof recordOrTag === "string" ? recordOrTag : recordOrTag && recordOrTag.tag;
      if (!isCitationTag(tag)) return;
      citationIndex += 1;
      var items = citationItems(recordOrTag);
      if (!items) return; // malformed -- Document diagnostics reports this separately; the panel just skips it
      items.forEach(function (item, i) {
        var pid = extractPaperId(item && item.id);
        var key = pid != null ? "id:" + pid : "unresolved:" + citationIndex + ":" + i;
        var entry = entriesByKey[key];
        if (!entry) {
          entry = { key: key, paperId: pid, row: cslRecordRow(item), occurrenceCount: 0, positions: [] };
          entriesByKey[key] = entry;
          order.push(key);
        }
        entry.occurrenceCount += 1;
        entry.positions.push(citationIndex);
      });
    });
    return order.map(function (key) { return entriesByKey[key]; });
  }
  // Pure augmentation: mark each entry orphaned/retraction-flagged from the same shaped inputs
  // summarizeDiagnostics already consumes (a "missing ids" list + a retraction check-selected `checked` array).
  function mergePanelEntryStatus(entries, missingPaperIds, retractionChecked) {
    var missingSet = {};
    (missingPaperIds || []).forEach(function (id) { missingSet[String(id)] = true; });
    var flaggedByPaperId = {};
    (retractionChecked || []).forEach(function (row) {
      var status = row && row.status;
      if (status && status !== "none" && status !== "unchecked") flaggedByPaperId[String(row.paper_id)] = row;
    });
    return (entries || []).map(function (entry) {
      var out = Object.assign({}, entry);
      out.orphaned = entry.paperId != null && !!missingSet[String(entry.paperId)];
      out.retraction = entry.paperId != null ? flaggedByPaperId[String(entry.paperId)] || null : null;
      return out;
    });
  }

  // ---- Word-on-the-web relay (SP4) ----
  // The task pane is served same-origin from callosum on desktop (localhost/127.0.0.1) -- no token needed, the
  // browser/webview never leaves the machine. Word-on-the-web loads the SAME task pane through the cloudflared
  // relay instead (a different origin entirely), which callosum's existing Remote-access bearer token gates.
  function isLocalOrigin(hostname) {
    return hostname === "localhost" || hostname === "127.0.0.1";
  }
  // Merges an Authorization: Bearer header into `headers` only when `token` is truthy -- never mutates the
  // input object (the caller may reuse it), and passes non-tunnel (local, no token) calls through unchanged.
  function authHeaders(headers, token) {
    var h = Object.assign({}, headers || {});
    if (token) h.Authorization = "Bearer " + token;
    return h;
  }

  var api = {
    CITATION_PREFIX: CITATION_PREFIX,
    CITATION_XML_NAMESPACE: CITATION_XML_NAMESPACE,
    BIB_TAG: BIB_TAG,
    authorLabel: authorLabel,
    formatSearchRows: formatSearchRows,
    firstCslRecord: firstCslRecord,
    encodeCitationTag: encodeCitationTag,
    encodeCitationReferenceTag: encodeCitationReferenceTag,
    citationReferenceId: citationReferenceId,
    isLegacyCitationTag: isLegacyCitationTag,
    encodeCitationXml: encodeCitationXml,
    decodeCitationXml: decodeCitationXml,
    citationItems: citationItems,
    isCitationTag: isCitationTag,
    decodeCitationTag: decodeCitationTag,
    buildDocumentRequest: buildDocumentRequest,
    inTextResults: inTextResults,
    bibliographyText: bibliographyText,
    pickQueryText: pickQueryText,
    buildSuggestRequest: buildSuggestRequest,
    formatSuggestRows: formatSuggestRows,
    isLocalOrigin: isLocalOrigin,
    authHeaders: authHeaders,
    LOCATOR_LABELS: LOCATOR_LABELS,
    itemOverrides: itemOverrides,
    buildClusterItems: buildClusterItems,
    cslRecordRow: cslRecordRow,
    formatAssemblyRow: formatAssemblyRow,
    assemblyRowFromDecodedItem: assemblyRowFromDecodedItem,
    stampCallosumId: stampCallosumId,
    extractPaperId: extractPaperId,
    summarizeDiagnostics: summarizeDiagnostics,
    buildCitationsPanelEntries: buildCitationsPanelEntries,
    mergePanelEntryStatus: mergePanelEntryStatus,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CallosumCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
