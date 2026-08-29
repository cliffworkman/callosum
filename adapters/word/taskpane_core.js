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
  var SECTION_BIB_SCOPE_PREFIX = "CALLOSUM_SECTION_BIBLIOGRAPHY_SCOPE ";
  var SECTION_BIB_BLOCK_PREFIX = "CALLOSUM_SECTION_BIBLIOGRAPHY_BLOCK ";
  var MAX_SECTION_BIBLIOGRAPHIES = 50;
  var BIBLIOGRAPHY_UNCATEGORIZED = "Other references";
  var BIBLIOGRAPHY_CATEGORY_MAX = 80;
  var MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS = 1000;
  var MAX_BIBLIOGRAPHY_CATEGORIES = 50;
  var MAX_BIBLIOGRAPHY_CATEGORY_METADATA = 131072;
  var MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA = 8192;
  var MAX_BIBLIOGRAPHY_LINKS_PER_ENTRY = 20;
  var MAX_BIBLIOGRAPHY_EXTERNAL_URL = 2048;
  var SUGGEST_RETRIEVAL_THRESHOLD = 0.7;
  var SUGGEST_SUPPORT_THRESHOLD = 0.55;
  var EVIDENCE_SNIPPET_MAX = 150;
  var EVIDENCE_QUOTE_MAX = 20000;
  var EVIDENCE_NOTE_MAX = 4000;
  var EVIDENCE_STANCE_TEXT_MAX = 4000;
  var EVIDENCE_LOCATOR_MAX = 80;
  var EVIDENCE_FORMATS = [
    { value: "quote_only", label: "Quote only (no citation)" },
    { value: "quote_cite", label: "Quote + citation" },
    { value: "paraphrase_cite", label: "Your saved note + citation" },
    { value: "card", label: "Structured card (quote + note + citation)" },
  ];
  var MAX_STATEMENT_LENGTH = 4000;
  // Keep these author-chosen starting phrases aligned with the web workspace's `38b_statements.jsx`. They are
  // deterministic prose aids, not claims inferred or verified by Callosum.
  var STATEMENT_TYPES = [
    { kind: "data_availability", label: "Data availability", phrases: [
      { label: "Available on request", text: "The data that support the findings of this study are available from the corresponding author upon reasonable request." },
      { label: "Openly available", text: "The data that support the findings of this study are openly available in [repository name] at [URL/DOI]." },
      { label: "Restricted (third-party)", text: "The data used in this study are third-party data, and restrictions apply to their availability." },
      { label: "No new data", text: "No new data were generated in this study." },
    ] },
    { kind: "code_availability", label: "Code availability", phrases: [
      { label: "Openly available", text: "The code that supports the findings of this study is available at [repository URL]." },
      { label: "Available on request", text: "The code used in this study is available from the corresponding author upon reasonable request." },
      { label: "No custom code", text: "No custom code was used in this study." },
    ] },
    { kind: "preregistration", label: "Preregistration", phrases: [
      { label: "Preregistered", text: "The study design and analysis plan were preregistered at [registry/URL] prior to data collection." },
      { label: "Not preregistered", text: "This study was not preregistered." },
      { label: "Some exploratory analyses", text: "Some analyses reported here were not specified in the preregistration and should be considered exploratory." },
    ] },
    { kind: "funding", label: "Funding", phrases: [
      { label: "Funded", text: "This work was supported by [Funder name] under Grant No. [XXX]." },
      { label: "No specific funding", text: "This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors." },
    ] },
    { kind: "conflict_of_interest", label: "Conflict of interest", phrases: [
      { label: "None declared", text: "The authors declare no competing interests." },
      { label: "Declared", text: "The authors declare the following competing interests: [describe]." },
    ] },
    { kind: "ethics", label: "Ethics", phrases: [
      { label: "IRB approved", text: "This study was approved by [IRB/Ethics Committee name], protocol #[XXX]." },
      { label: "Not required", text: "This study did not require ethical approval because [reason]." },
      { label: "Informed consent", text: "All participants provided informed consent prior to participation." },
    ] },
    { kind: "ai_use", label: "AI use", phrases: [
      { label: "AI used", text: "Generative AI tools were used for [specific purpose]; all AI-assisted content was reviewed and edited by the authors, who take full responsibility for the final manuscript." },
      { label: "No AI used", text: "No generative AI tools were used in the preparation of this manuscript." },
    ] },
  ];

  function statementType(kind) {
    return STATEMENT_TYPES.find(function (type) { return type.kind === String(kind || ""); }) || null;
  }
  function normalizeStatementText(text) {
    return String(text == null ? "" : text).trim().slice(0, MAX_STATEMENT_LENGTH);
  }
  function normalizeStagedStatements(value) {
    var source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    var normalized = {};
    STATEMENT_TYPES.forEach(function (type) {
      var text = typeof source[type.kind] === "string" ? normalizeStatementText(source[type.kind]) : "";
      if (text) normalized[type.kind] = text;
    });
    return normalized;
  }
  function buildStatementStageRequest(kind, text) {
    if (!statementType(kind)) return null;
    return { kind: String(kind), text: normalizeStatementText(text) };
  }

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

  // ---- heading-scoped bibliography identity (inc 524) ----
  // Word has no stable production bookmark-creation API, so each block is a strict pair of Content Controls:
  // one hidden control wrapping the owning heading and one bounded generated-text control. The shared random
  // id survives save/reopen; paragraph uniqueLocalId is used only within one Office.js batch to calculate the
  // current outline subtree and is never persisted.
  function sectionBibliographyIdFromBytes(bytes) {
    if (!bytes || bytes.length !== 16) throw new Error("Section bibliography ids require 16 random bytes.");
    return Array.prototype.map.call(bytes, function (value) {
      if (!Number.isInteger(value) || value < 0 || value > 255) {
        throw new Error("Section bibliography id bytes must be integers from 0 through 255.");
      }
      return value.toString(16).padStart(2, "0");
    }).join("");
  }
  function encodeSectionBibliographyTag(kind, identifier) {
    var id = String(identifier || "");
    if (!/^[0-9a-f]{32}$/.test(id)) {
      throw new Error("Section bibliography ids must be 32 lowercase hexadecimal characters.");
    }
    if (kind === "scope") return SECTION_BIB_SCOPE_PREFIX + id;
    if (kind === "block") return SECTION_BIB_BLOCK_PREFIX + id;
    throw new Error("Section bibliography tag kind must be scope or block.");
  }
  function decodeSectionBibliographyTag(tag) {
    if (typeof tag !== "string") return null;
    var kind = null, value = "";
    if (tag.indexOf(SECTION_BIB_SCOPE_PREFIX) === 0) {
      kind = "scope"; value = tag.slice(SECTION_BIB_SCOPE_PREFIX.length);
    } else if (tag.indexOf(SECTION_BIB_BLOCK_PREFIX) === 0) {
      kind = "block"; value = tag.slice(SECTION_BIB_BLOCK_PREFIX.length);
    } else {
      return null;
    }
    return /^[0-9a-f]{32}$/.test(value) ? { id: value, kind: kind } : null;
  }
  function isSectionBibliographyTag(tag) {
    return typeof tag === "string" &&
      (tag.indexOf(SECTION_BIB_SCOPE_PREFIX) === 0 || tag.indexOf(SECTION_BIB_BLOCK_PREFIX) === 0);
  }
  function sectionBibliographyInventory(records) {
    var grouped = {}, malformed = [];
    (records || []).forEach(function (recordOrTag, index) {
      var tag = typeof recordOrTag === "string" ? recordOrTag : recordOrTag && recordOrTag.tag;
      if (!isSectionBibliographyTag(tag)) return;
      var decoded = decodeSectionBibliographyTag(tag);
      if (!decoded) { malformed.push("malformed-" + index); return; }
      var group = grouped[decoded.id] || (grouped[decoded.id] = { id: decoded.id, scope: [], block: [] });
      group[decoded.kind].push(recordOrTag);
    });
    var ids = Object.keys(grouped).sort();
    if (ids.length > MAX_SECTION_BIBLIOGRAPHIES) {
      throw new Error("A Word document can contain at most " + MAX_SECTION_BIBLIOGRAPHIES +
        " section bibliographies.");
    }
    var complete = [], damaged = malformed.slice();
    ids.forEach(function (id) {
      var group = grouped[id];
      if (group.scope.length === 1 && group.block.length === 1) {
        complete.push({ id: id, scope: group.scope[0], block: group.block[0] });
      } else {
        damaged.push(id);
      }
    });
    return { complete: complete, damaged: damaged };
  }

  function isHeadingOutlineLevel(value) {
    return Number.isInteger(value) && value >= 1 && value <= 9;
  }
  // `anchorParagraphId` may be any paragraph in the section (insertion/removal) or the scope heading itself
  // (refresh). The semantic section is the nearest preceding heading plus all lower-ranked headings until the
  // next peer/ancestor, exactly matching Writer's established contract.
  function sectionParagraphBounds(paragraphs, anchorParagraphId) {
    var rows = paragraphs || [], anchor = -1;
    for (var i = 0; i < rows.length; i++) {
      if (String(rows[i] && rows[i].id) === String(anchorParagraphId)) { anchor = i; break; }
    }
    if (anchor < 0) return null;
    var start = anchor;
    while (start >= 0 && !isHeadingOutlineLevel(rows[start] && rows[start].outlineLevel)) start -= 1;
    if (start < 0) return null;
    var level = rows[start].outlineLevel, end = rows.length;
    for (var j = start + 1; j < rows.length; j++) {
      var candidate = rows[j] && rows[j].outlineLevel;
      if (isHeadingOutlineLevel(candidate) && candidate <= level) { end = j; break; }
    }
    return { start: start, end: end, headingId: String(rows[start].id), outlineLevel: level };
  }
  function sectionCitationItemIds(paragraphs, headingParagraphId, citations) {
    var bounds = sectionParagraphBounds(paragraphs, headingParagraphId);
    if (!bounds || bounds.headingId !== String(headingParagraphId)) {
      throw new Error("A section bibliography scope no longer wraps a heading.");
    }
    var indexById = {};
    (paragraphs || []).forEach(function (row, index) { indexById[String(row && row.id)] = index; });
    var allowed = {};
    (citations || []).forEach(function (citation) {
      var index = indexById[String(citation && citation.paragraphId)];
      if (!Number.isInteger(index) || index < bounds.start || index >= bounds.end) return;
      (citation.items || []).forEach(function (item) {
        var id = String(item && item.id || "");
        if (id.indexOf(CALLOSUM_ID_PREFIX) === 0) allowed[id] = true;
      });
    });
    return Object.keys(allowed);
  }

  function projectBibliographyData(data, allowedItemIds) {
    var original = bibliographyText(data);
    if (!original) return { bibliography_text: "", bibliography_entry_ids: [], bibliography_links: [] };
    var entries = original.split("\n").map(function (entry) { return entry.replace(/\r$/, ""); });
    var entryIds = data && data.bibliography_entry_ids;
    if (!Array.isArray(entryIds) || entryIds.length !== entries.length) {
      throw new Error("Bibliography entry identity is unavailable; a section bibliography was not updated.");
    }
    var rawLinks = data && data.bibliography_links;
    if (!Array.isArray(rawLinks) || rawLinks.length !== entries.length) {
      rawLinks = entries.map(function () { return []; });
    }
    var allowed = {};
    (allowedItemIds || []).forEach(function (id) { allowed[String(id)] = true; });
    var keptEntries = [], keptIds = [], keptLinks = [];
    entryIds.forEach(function (ids, index) {
      var normalizedIds = Array.isArray(ids) ? ids.map(String) : [];
      if (!normalizedIds.some(function (id) { return allowed[id]; })) return;
      keptEntries.push(entries[index]); keptIds.push(normalizedIds); keptLinks.push(rawLinks[index]);
    });
    return {
      bibliography_text: keptEntries.join("\n"),
      bibliography_entry_ids: keptIds,
      bibliography_links: keptLinks,
    };
  }
  function sectionBibliographyText(data, allowedItemIds, assignments, configuredOrder) {
    return sectionBibliographyPlan(data, allowedItemIds, assignments, configuredOrder).text;
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
  // `clusters` is either the legacy per-cluster item arrays or `{items, noteIndex}` records in document/note
  // order. Positive one-based note indexes let citeproc compute first/subsequent/ibid behavior for note styles.
  function buildDocumentRequest(clusters, style, locale) {
    return {
      citations: (clusters || []).map(function (cluster, i) {
        var record = Array.isArray(cluster) ? { items: cluster } : cluster || { items: [] };
        var citation = { citationID: "c" + i, items: record.items || [] };
        if (record.noteIndex != null) citation.noteIndex = record.noteIndex;
        return citation;
      }),
      style: style || "apa",
      locale: locale || "en-US",
    };
  }

  function isNoteStyle(citationFormat) {
    return String(citationFormat || "").toLowerCase() === "note";
  }
  function normalizeNotePreference(value) {
    return String(value || "").toLowerCase() === "endnote" ? "endnote" : "footnote";
  }
  function bodyTypeLocation(value) {
    var bodyType = String(value || "").toLowerCase();
    if (bodyType === "maindoc") return "inline";
    if (bodyType === "footnote") return "footnote";
    if (bodyType === "endnote") return "endnote";
    return null;
  }
  // A note style must contain only native notes of one configured kind; an in-text style must remain in the main
  // story. Mixing stories has no honest global ordering for numeric/in-text citeproc state, so fail closed instead
  // of silently emitting plausible-but-wrong numbering or note position behavior.
  function placementIssue(citations, citationFormat, notePreference) {
    var locations = (citations || []).map(function (c) { return c && c.location; }).filter(Boolean);
    if (!locations.length) return null;
    if (!isNoteStyle(citationFormat)) {
      return locations.some(function (location) { return location !== "inline"; })
        ? "This in-text citation style has Callosum citations inside notes. Move them to the main document before refreshing."
        : null;
    }
    if (locations.some(function (location) { return location === "inline"; })) {
      return "This note citation style has inline Callosum citations. Reinsert them as native notes before refreshing.";
    }
    var expected = normalizeNotePreference(notePreference);
    var actual = {};
    locations.forEach(function (location) { actual[location] = true; });
    if (Object.keys(actual).length > 1) {
      return "Callosum citations are split between footnotes and endnotes. Use one native note type per document.";
    }
    if (!actual[expected]) {
      return "This document's Callosum citations use " + Object.keys(actual)[0] +
        "s, but new note citations are set to " + expected + "s.";
    }
    return null;
  }
  // The rendered in-text strings, in order, from a /citations/render-document response ({citations:[{text}]}).
  function inTextResults(data) {
    if (!data || !Array.isArray(data.citations)) return [];
    return data.citations.map(function (c) { return String((c && c.text) || ""); });
  }
  function bibliographyText(data) {
    return (data && data.bibliography_text) || "";
  }

  // ---- document-local bibliography categories (inc 521; Writer parity inc 377) ----
  function normalizeBibliographyCategory(value) {
    var raw = String(value == null ? "" : value);
    var category = raw.trim();
    if (!category) return null;
    if (category.length > BIBLIOGRAPHY_CATEGORY_MAX) {
      throw new Error("Bibliography categories must be " + BIBLIOGRAPHY_CATEGORY_MAX + " characters or fewer.");
    }
    if (/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/.test(raw)) {
      throw new Error("Bibliography categories must be a single line without control characters.");
    }
    if (category.toLowerCase() === BIBLIOGRAPHY_UNCATEGORIZED.toLowerCase()) {
      throw new Error("\"" + BIBLIOGRAPHY_UNCATEGORIZED + "\" is reserved for entries without a category.");
    }
    return category;
  }

  function normalizeBibliographyCategories(value) {
    var decoded = value;
    if (typeof value === "string") {
      if (value.length > MAX_BIBLIOGRAPHY_CATEGORY_METADATA) return {};
      try { decoded = JSON.parse(value); } catch (e) { return {}; }
    }
    if (!decoded || typeof decoded !== "object" || Array.isArray(decoded)) return {};
    var ids = Object.keys(decoded);
    if (ids.length > MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS) return {};
    var normalized = {}, canonical = {};
    for (var i = 0; i < ids.length; i++) {
      var paperId = ids[i];
      if (!/^\d{1,20}$/.test(paperId)) continue;
      var category;
      try { category = normalizeBibliographyCategory(decoded[paperId]); } catch (e) { continue; }
      if (!category) continue;
      var folded = category.toLowerCase();
      if (!canonical[folded]) {
        if (Object.keys(canonical).length >= MAX_BIBLIOGRAPHY_CATEGORIES) return {};
        canonical[folded] = category;
      }
      normalized[paperId] = canonical[folded];
    }
    return normalized;
  }

  function serializeBibliographyCategories(assignments) {
    var normalized = normalizeBibliographyCategories(assignments);
    var sorted = {};
    Object.keys(normalized).sort().forEach(function (paperId) { sorted[paperId] = normalized[paperId]; });
    var encoded = JSON.stringify(sorted);
    if (encoded.length > MAX_BIBLIOGRAPHY_CATEGORY_METADATA) {
      throw new Error("Bibliography category metadata is too large for one Word document.");
    }
    return encoded;
  }

  function updateBibliographyCategories(assignments, paperIds, value) {
    var ids = [];
    (paperIds || []).forEach(function (paperId) {
      var id = String(paperId == null ? "" : paperId);
      if (!/^\d{1,20}$/.test(id)) {
        throw new Error("Bibliography category assignments require numeric Callosum paper ids.");
      }
      if (ids.indexOf(id) === -1) ids.push(id);
    });
    if (ids.length > MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS) {
      throw new Error("A category can be assigned to at most " +
        MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS + " works at once.");
    }
    if (!ids.length) return Object.assign({}, normalizeBibliographyCategories(assignments));
    var updated = Object.assign({}, normalizeBibliographyCategories(assignments));
    var category = normalizeBibliographyCategory(value);
    var existing = category == null ? null : Object.keys(updated).map(function (key) { return updated[key]; })
      .find(function (label) { return label.toLowerCase() === category.toLowerCase(); });
    ids.forEach(function (id) {
      if (category == null) delete updated[id];
      else updated[id] = existing || category;
    });
    if (Object.keys(updated).length > MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS) {
      throw new Error("A document can categorize at most " + MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS + " works.");
    }
    var categories = {};
    Object.keys(updated).forEach(function (key) { categories[updated[key].toLowerCase()] = true; });
    if (Object.keys(categories).length > MAX_BIBLIOGRAPHY_CATEGORIES) {
      throw new Error("A document can use at most " + MAX_BIBLIOGRAPHY_CATEGORIES + " bibliography categories.");
    }
    serializeBibliographyCategories(updated); // final bounded-metadata assertion
    return updated;
  }

  function updateBibliographyCategory(assignments, paperId, value) {
    var id = String(paperId == null ? "" : paperId);
    if (!/^\d{1,20}$/.test(id)) {
      throw new Error("Bibliography category assignments require a numeric Callosum paper id.");
    }
    return updateBibliographyCategories(assignments, [id], value);
  }

  function normalizeBibliographyCategoryOrder(value) {
    var decoded = value;
    if (typeof value === "string") {
      if (value.length > MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA) return [];
      try { decoded = JSON.parse(value); } catch (e) { return []; }
    }
    if (!Array.isArray(decoded) || decoded.length > MAX_BIBLIOGRAPHY_CATEGORIES) return [];
    var order = [], seen = {};
    for (var i = 0; i < decoded.length; i++) {
      if (typeof decoded[i] !== "string") return [];
      var category;
      try { category = normalizeBibliographyCategory(decoded[i]); } catch (e) { return []; }
      if (category == null || seen[category.toLowerCase()]) return [];
      seen[category.toLowerCase()] = true;
      order.push(category);
    }
    return order;
  }

  function serializeBibliographyCategoryOrder(categories) {
    if (!Array.isArray(categories)) throw new Error("Bibliography category order must be a list.");
    if (categories.length > MAX_BIBLIOGRAPHY_CATEGORIES) {
      throw new Error("A document can order at most " + MAX_BIBLIOGRAPHY_CATEGORIES + " bibliography categories.");
    }
    var order = [], seen = {};
    categories.forEach(function (rawCategory) {
      if (typeof rawCategory !== "string") throw new Error("Bibliography category order labels must be text.");
      var category = normalizeBibliographyCategory(rawCategory);
      if (category == null) throw new Error("Bibliography category order cannot contain a blank label.");
      var folded = category.toLowerCase();
      if (seen[folded]) throw new Error("Bibliography category order cannot contain duplicate labels.");
      seen[folded] = true;
      order.push(category);
    });
    var encoded = JSON.stringify(order);
    if (encoded.length > MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA) {
      throw new Error("Bibliography category order metadata is too large for one Word document.");
    }
    return encoded;
  }

  function orderedBibliographyCategories(categories, configuredOrder) {
    var rank = {};
    normalizeBibliographyCategoryOrder(configuredOrder).forEach(function (category, index) {
      rank[category.toLowerCase()] = index;
    });
    return (categories || []).slice().sort(function (left, right) {
      var leftFolded = left.toLowerCase(), rightFolded = right.toLowerCase();
      var fallback = Object.keys(rank).length;
      var leftRank = Object.prototype.hasOwnProperty.call(rank, leftFolded) ? rank[leftFolded] : fallback;
      var rightRank = Object.prototype.hasOwnProperty.call(rank, rightFolded) ? rank[rightFolded] : fallback;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return leftFolded < rightFolded ? -1 : leftFolded > rightFolded ? 1 : (left < right ? -1 : left > right ? 1 : 0);
    });
  }

  function bibliographyCategoryForIds(itemIds, assignments) {
    var categories = (itemIds || []).map(function (itemId) {
      var paperId = extractPaperId(itemId);
      return assignments[paperId || ""] || null;
    });
    if (!categories.length || categories[0] == null) return null;
    return categories.every(function (category) { return category === categories[0]; }) ? categories[0] : null;
  }

  // `/citations/render-document` link offsets are Python Unicode-code-point offsets, not JavaScript UTF-16
  // indexes. Convert through Array.from so an astral character before a title/DOI cannot move a link onto the
  // wrong visible text. Malformed metadata is additive and therefore degrades to plain text, never a failed
  // bibliography refresh.
  function validatedBibliographyExternalUrl(value) {
    if (typeof value !== "string" || !value || value.length > MAX_BIBLIOGRAPHY_EXTERNAL_URL ||
        /[\s\u0000-\u001f\u007f]/.test(value)) return null;
    try {
      var parsed = new URL(value);
      if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || !parsed.hostname ||
          parsed.username || parsed.password) return null;
    } catch (e) { return null; }
    return value;
  }

  function normalizeBibliographyLinks(entries, rawLinks) {
    var plain = (entries || []).map(function () { return []; });
    if (!Array.isArray(rawLinks) || rawLinks.length !== plain.length) return plain;
    return plain.map(function (_unused, entryIndex) {
      var entry = String(entries[entryIndex] || "");
      var codePoints = Array.from(entry);
      var links = rawLinks[entryIndex];
      if (!Array.isArray(links)) return [];
      var accepted = [], previousEnd = 0;
      links.slice(0, MAX_BIBLIOGRAPHY_LINKS_PER_ENTRY).forEach(function (link) {
        if (!link || typeof link !== "object") return;
        var start = link.start, length = link.length;
        var url = validatedBibliographyExternalUrl(link.url);
        if (!Number.isInteger(start) || !Number.isInteger(length) || start < previousEnd || length <= 0 ||
            start + length > codePoints.length || !url) return;
        var text = codePoints.slice(start, start + length).join("");
        if (!text) return;
        accepted.push({ start: start, length: length, text: text, url: url });
        previousEnd = start + length;
      });
      return accepted;
    });
  }

  function bibliographyEntryRecords(data, requireIdentity) {
    var original = bibliographyText(data);
    if (!original) return [];
    var entries = original.split("\n").map(function (entry) { return entry.replace(/\r$/, ""); });
    var entryIds = data && data.bibliography_entry_ids;
    if (requireIdentity && (!Array.isArray(entryIds) || entryIds.length !== entries.length)) {
      throw new Error("Bibliography entry identity is unavailable; categories were not applied.");
    }
    var normalizedLinks = normalizeBibliographyLinks(entries, data && data.bibliography_links);
    return entries.map(function (entry, index) {
      return {
        text: entry,
        itemIds: Array.isArray(entryIds) && Array.isArray(entryIds[index]) ? entryIds[index].map(String) : [],
        links: normalizedLinks[index],
      };
    });
  }

  // Reorders citeproc's already-rendered entries only between user-authored groups. Within each group, the
  // original citeproc order is untouched. Each plan also retains exact per-entry link spans and paragraph
  // indexes after category headings/blank separators are inserted.
  function bibliographyRenderPlan(data, assignments, configuredOrder) {
    var normalized = normalizeBibliographyCategories(assignments);
    var records = bibliographyEntryRecords(data, Object.keys(normalized).length > 0);
    if (!records.length) return { text: "", entries: [] };
    var lines = [], plannedEntries = [];
    function appendEntry(record) {
      plannedEntries.push({ paragraphIndex: lines.length, text: record.text, links: record.links });
      lines.push(record.text);
    }
    if (!Object.keys(normalized).length) {
      records.forEach(appendEntry);
      return { text: lines.join("\n"), entries: plannedEntries };
    }
    var aligned = records.map(function (record) {
      return bibliographyCategoryForIds(record.itemIds, normalized);
    });
    var categoryNames = [];
    aligned.forEach(function (category) {
      if (category && categoryNames.indexOf(category) === -1) categoryNames.push(category);
    });
    if (!categoryNames.length) { // only stale/non-visible assignments exist
      records.forEach(appendEntry);
      return { text: lines.join("\n"), entries: plannedEntries };
    }
    categoryNames = orderedBibliographyCategories(categoryNames, configuredOrder);
    var groups = categoryNames.concat([null]);
    groups.forEach(function (category) {
      var groupEntries = records.filter(function (_entry, index) { return aligned[index] === category; });
      if (groupEntries.length) {
        if (lines.length) lines.push("");
        lines.push(category || BIBLIOGRAPHY_UNCATEGORIZED);
        groupEntries.forEach(appendEntry);
      }
    });
    return { text: lines.join("\n"), entries: plannedEntries };
  }

  function sectionBibliographyPlan(data, allowedItemIds, assignments, configuredOrder) {
    var projected = projectBibliographyData(data, allowedItemIds);
    var plan = bibliographyRenderPlan(projected, assignments, configuredOrder);
    return {
      text: "References" + (plan.text ? "\n" + plan.text : ""),
      entries: plan.entries.map(function (entry) {
        return Object.assign({}, entry, { paragraphIndex: entry.paragraphIndex + 1 });
      }),
    };
  }

  function categorizedBibliographyText(data, assignments, configuredOrder) {
    return bibliographyRenderPlan(data, assignments, configuredOrder).text;
  }

  function applyBibliographyCategories(entries, assignments) {
    var normalized = normalizeBibliographyCategories(assignments);
    return (entries || []).map(function (entry) {
      var out = Object.assign({}, entry);
      out.category = entry.paperId == null ? null : normalized[String(entry.paperId)] || null;
      return out;
    });
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

  function _boundedProbability(value) {
    var number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
  }
  function stanceBreakdownText(stance) {
    if (!stance || typeof stance !== "object") return "No stance signal for this passage.";
    var probs = stance.probs && typeof stance.probs === "object" ? stance.probs : {};
    function percent(key) { return Math.round(_boundedProbability(probs[key]) * 100); }
    return "Stance signal: " + percent("support") + "% support · " + percent("mention") +
      "% mention · " + percent("contrast") + "% contrast";
  }
  function suggestionIsWeakEvidence(item) {
    var match = _boundedProbability(item && item.match_score);
    var probs = item && item.stance && item.stance.probs;
    var support = _boundedProbability(probs && probs.support);
    return !(match >= SUGGEST_RETRIEVAL_THRESHOLD || support >= SUGGEST_SUPPORT_THRESHOLD);
  }
  function suggestionAutoLocator(item) {
    var start = item && item.page_start;
    var end = item && item.page_end;
    if (!Number.isInteger(start) || start <= 0) return "";
    return Number.isInteger(end) && end > start ? start + "-" + end : String(start);
  }
  function suggestionEvidenceFields(item) {
    var quote = String(item && item.quote || "").replace(/\s+/g, " ").trim();
    if (!quote) return {};
    var snippet = quote.length > EVIDENCE_SNIPPET_MAX
      ? quote.slice(0, EVIDENCE_SNIPPET_MAX).trimEnd() + "…"
      : quote;
    var out = { evidence_snippet: snippet };
    if (Number.isInteger(item.chunk_id) && item.chunk_id > 0) out.evidence_chunk_id = item.chunk_id;
    if (Number.isInteger(item.page_start) && item.page_start > 0) {
      out.evidence_page_start = item.page_start;
      if (Number.isInteger(item.page_end) && item.page_end >= item.page_start) {
        out.evidence_page_end = item.page_end;
      }
    }
    return out;
  }
  function suggestionAssemblyFields(item, locatorOverride, hasLocatorOverride) {
    var locator = hasLocatorOverride ? String(locatorOverride || "").slice(0, 80).trim() : suggestionAutoLocator(item);
    var out = suggestionEvidenceFields(item);
    if (locator) { out.locator = locator; out.label = "page"; }
    return out;
  }
  function suggestionDetail(item, locatorOverride, hasLocatorOverride) {
    var match = Math.round(_boundedProbability(item && item.match_score) * 100);
    var start = item && item.page_start, end = item && item.page_end;
    var page = Number.isInteger(start) && start > 0
      ? (Number.isInteger(end) && end > start ? "Pages " + start + "–" + end : "Page " + start)
      : "Page unknown";
    return {
      quote: String(item && item.quote || ""),
      page: page,
      stance: stanceBreakdownText(item && item.stance),
      reason: "Retrieved by local semantic similarity — approximately " + match + "% match to your selected text.",
      weak: suggestionIsWeakEvidence(item),
      locator: hasLocatorOverride ? String(locatorOverride || "").slice(0, 80) : suggestionAutoLocator(item),
      canOpenPdf: Number.isInteger(item && item.paper_id) && item.paper_id > 0 &&
        Number.isInteger(item && item.attachment_id) && item.attachment_id > 0,
    };
  }
  function suggestionOpenPdfPath(item) {
    if (!Number.isInteger(item && item.paper_id) || item.paper_id <= 0 ||
        !Number.isInteger(item && item.attachment_id) || item.attachment_id <= 0) return null;
    var path = "/?open_paper=" + encodeURIComponent(String(item.paper_id));
    if (Number.isInteger(item.page_start) && item.page_start > 0) {
      path += "&page=" + encodeURIComponent(String(item.page_start)) + "&precision=region";
    }
    return path;
  }

  // ---- Insert saved evidence (inc 529, backlog #33/#34 P2 #20) ----
  // These helpers keep saved-highlight normalization, four author-chosen formats, stance-request bounds, and
  // compact citation provenance out of Office.js. Nothing here decides whether evidence supports a claim.
  function _evidenceText(value) {
    return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
  }
  function normalizeEvidenceAnnotations(value) {
    if (!Array.isArray(value)) return [];
    return value.filter(function (item) {
      return item && Number.isInteger(item.id) && item.id > 0 && !!_evidenceText(item.anchor_text);
    }).map(function (item) {
      var page = Number(item.page);
      return {
        id: item.id,
        quote: _evidenceText(item.anchor_text),
        note: _evidenceText(item.note),
        page: Number.isInteger(page) && page > 0 ? page : null,
      };
    });
  }
  function evidenceAnnotationRows(annotations) {
    return (annotations || []).map(function (annotation, index) {
      var quote = annotation.quote.length > 70 ? annotation.quote.slice(0, 70).trimEnd() + "…" : annotation.quote;
      var note = annotation.note.length > 40 ? annotation.note.slice(0, 40).trimEnd() + "…" : annotation.note;
      return {
        index: index,
        label: "p." + (annotation.page || "?") + ' — “' + quote + '”' + (note ? "  [note: " + note + "]" : ""),
      };
    });
  }
  function evidenceAnnotationDetail(annotation) {
    var quote = _evidenceText(annotation && annotation.quote);
    var note = _evidenceText(annotation && annotation.note);
    var reason = "";
    if (!quote) reason = "This saved highlight has no quoted text.";
    else if (quote.length > EVIDENCE_QUOTE_MAX) {
      reason = "This saved highlight exceeds the " + EVIDENCE_QUOTE_MAX + "-character insertion limit.";
    } else if (note.length > EVIDENCE_NOTE_MAX) {
      reason = "This saved note exceeds the " + EVIDENCE_NOTE_MAX + "-character insertion limit.";
    }
    return { quote: quote, note: note, page: annotation && annotation.page || null, valid: !reason, reason: reason };
  }
  function evidenceBodyText(annotation, format) {
    var detail = evidenceAnnotationDetail(annotation);
    if (!detail.valid) throw new Error(detail.reason);
    var quoted = "“" + detail.quote + "”";
    if (format === "quote_only" || format === "quote_cite") return quoted;
    if (format === "paraphrase_cite") return detail.note || quoted;
    if (format === "card") return detail.note ? quoted + " — " + detail.note : quoted;
    throw new Error("Unknown evidence insertion format.");
  }
  function buildEvidenceStanceRequest(claim, annotation) {
    var sentence = _evidenceText(claim);
    var passage = _evidenceText(annotation && annotation.quote);
    if (!sentence || !passage) return null;
    if (sentence.length > EVIDENCE_STANCE_TEXT_MAX || passage.length > EVIDENCE_STANCE_TEXT_MAX) {
      throw new Error("Claim and highlighted passage must each be at most " +
        EVIDENCE_STANCE_TEXT_MAX + " characters for stance checking.");
    }
    return { sentence: sentence, passage: passage };
  }
  function evidenceAssemblyFields(annotation, locator) {
    var detail = evidenceAnnotationDetail(annotation);
    if (!detail.valid) throw new Error(detail.reason);
    var out = { evidence_annotation_id: annotation.id };
    if (detail.page) {
      out.evidence_page_start = detail.page;
      out.evidence_page_end = detail.page;
    }
    out.evidence_snippet = detail.quote.length > EVIDENCE_SNIPPET_MAX
      ? detail.quote.slice(0, EVIDENCE_SNIPPET_MAX).trimEnd() + "…" : detail.quote;
    var boundedLocator = _evidenceText(locator).slice(0, EVIDENCE_LOCATOR_MAX);
    if (boundedLocator) { out.locator = boundedLocator; out.label = "page"; }
    return out;
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
  var ASSEMBLY_EVIDENCE_KEYS = [
    "evidence_chunk_id", "evidence_annotation_id", "evidence_page_start", "evidence_page_end", "evidence_snippet",
  ];

  function assemblyEvidenceFields(row) {
    var out = {};
    if (Number.isInteger(row && row.evidence_chunk_id) && row.evidence_chunk_id > 0) {
      out.evidence_chunk_id = row.evidence_chunk_id;
    }
    if (Number.isInteger(row && row.evidence_annotation_id) && row.evidence_annotation_id > 0) {
      out.evidence_annotation_id = row.evidence_annotation_id;
    }
    if (Number.isInteger(row && row.evidence_page_start) && row.evidence_page_start > 0) {
      out.evidence_page_start = row.evidence_page_start;
      if (Number.isInteger(row.evidence_page_end) && row.evidence_page_end >= row.evidence_page_start) {
        out.evidence_page_end = row.evidence_page_end;
      }
    }
    var snippet = String(row && row.evidence_snippet || "").replace(/\s+/g, " ").trim();
    if (snippet) {
      out.evidence_snippet = snippet.length > EVIDENCE_SNIPPET_MAX
        ? snippet.slice(0, EVIDENCE_SNIPPET_MAX).trimEnd() + "…"
        : snippet;
    }
    return out;
  }

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
      return Object.assign({}, row && row.csl, itemOverrides(row), assemblyEvidenceFields(row));
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
    ASSEMBLY_EVIDENCE_KEYS.forEach(function (k) { delete bareCsl[k]; });
    var row = { csl: bareCsl, row: cslRecordRow(bareCsl) };
    ASSEMBLY_OVERRIDE_KEYS.concat(ASSEMBLY_EVIDENCE_KEYS).forEach(function (k) {
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

    var sectionInventory = sectionBibliographyInventory(tags);
    return {
      citationCount: citationCount,
      malformedCount: malformedCount,
      unresolvableItemCount: unresolvableItemCount,
      distinctPaperIds: distinctPaperIds,
      orphanedPaperIds: orphanedPaperIds,
      bibliography: citationCount === 0 ? "n/a" : (hasBibliography ? "ok" : "missing"),
      sectionBibliographyCount: sectionInventory.complete.length,
      damagedSectionBibliographyCount: sectionInventory.damaged.length,
      retractionFlagged: retractionFlagged,
    };
  }

  // ---- Citation-coverage audit (inc 528, backlog #33/#34 P2) ----
  // Pure structural signal only: three or more consecutive substantive main-story paragraphs without a
  // Callosum citation anchor. This deliberately does not infer claims, support, or whether a citation is
  // required. Headings, short transitions, table prose, and Callosum-managed bibliography blocks break a run.
  var UNCITED_STRETCH_MIN_PARAGRAPHS = 3;
  var UNCITED_STRETCH_MIN_WORDS = 15;
  var UNCITED_STRETCH_PREVIEW_MAX = 150;
  var MAX_COVERAGE_STRETCHES = 20;

  function coverageParagraphText(row) {
    return String(row && row.text || "").trim().replace(/\s+/g, " ");
  }
  function summarizeCitationCoverage(paragraphs) {
    var rows = paragraphs || [], stretches = [], stretchCount = 0, run = [];
    var substantiveParagraphCount = 0, citationAnchoredParagraphCount = 0;

    function flush() {
      if (run.length >= UNCITED_STRETCH_MIN_PARAGRAPHS) {
        stretchCount += 1;
        if (stretches.length < MAX_COVERAGE_STRETCHES) {
          var preview = run[0].text;
          if (preview.length > UNCITED_STRETCH_PREVIEW_MAX) {
            preview = preview.slice(0, UNCITED_STRETCH_PREVIEW_MAX).trimEnd() + "…";
          }
          stretches.push({
            startParagraph: run[0].paragraphNumber,
            endParagraph: run[run.length - 1].paragraphNumber,
            paragraphCount: run.length,
            preview: preview,
          });
        }
      }
      run = [];
    }

    rows.forEach(function (row, index) {
      var text = coverageParagraphText(row);
      var substantive = text ? text.split(/\s+/).length >= UNCITED_STRETCH_MIN_WORDS : false;
      var eligible = substantive && !isHeadingOutlineLevel(row && row.outlineLevel) &&
        !(row && row.excluded) && !(row && Number(row.tableNestingLevel) > 0);
      if (eligible) substantiveParagraphCount += 1;
      if (row && row.hasCitation) citationAnchoredParagraphCount += 1;
      if (eligible && !(row && row.hasCitation)) {
        run.push({ paragraphNumber: Number(row.paragraphNumber) || index + 1, text: text });
      } else {
        flush();
      }
    });
    flush();
    return {
      paragraphCount: rows.length,
      substantiveParagraphCount: substantiveParagraphCount,
      citationAnchoredParagraphCount: citationAnchoredParagraphCount,
      stretchCount: stretchCount,
      stretches: stretches,
      stretchesTruncated: stretchCount > stretches.length,
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
          entry = {
            key: key,
            paperId: pid,
            row: cslRecordRow(item),
            occurrenceCount: 0,
            positions: [],
            evidence: citationEvidenceFromItem(item),
          };
          entriesByKey[key] = entry;
          order.push(key);
        }
        entry.occurrenceCount += 1;
        entry.positions.push(citationIndex);
      });
    });
    return order.map(function (key) { return entriesByKey[key]; });
  }
  function citationEvidenceFromItem(item) {
    var snippet = String(item && item.evidence_snippet || "").trim();
    if (!snippet) return null;
    var start = item && item.evidence_page_start, end = item && item.evidence_page_end;
    var page = Number.isInteger(start) && start > 0
      ? (Number.isInteger(end) && end > start ? String(start) + "–" + end : String(start))
      : null;
    return { page: page, snippet: assemblyEvidenceFields({ evidence_snippet: snippet }).evidence_snippet };
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
    SECTION_BIB_SCOPE_PREFIX: SECTION_BIB_SCOPE_PREFIX,
    SECTION_BIB_BLOCK_PREFIX: SECTION_BIB_BLOCK_PREFIX,
    MAX_SECTION_BIBLIOGRAPHIES: MAX_SECTION_BIBLIOGRAPHIES,
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
    sectionBibliographyIdFromBytes: sectionBibliographyIdFromBytes,
    encodeSectionBibliographyTag: encodeSectionBibliographyTag,
    decodeSectionBibliographyTag: decodeSectionBibliographyTag,
    isSectionBibliographyTag: isSectionBibliographyTag,
    sectionBibliographyInventory: sectionBibliographyInventory,
    sectionParagraphBounds: sectionParagraphBounds,
    sectionCitationItemIds: sectionCitationItemIds,
    projectBibliographyData: projectBibliographyData,
    sectionBibliographyText: sectionBibliographyText,
    isCitationTag: isCitationTag,
    decodeCitationTag: decodeCitationTag,
    buildDocumentRequest: buildDocumentRequest,
    isNoteStyle: isNoteStyle,
    normalizeNotePreference: normalizeNotePreference,
    bodyTypeLocation: bodyTypeLocation,
    placementIssue: placementIssue,
    inTextResults: inTextResults,
    bibliographyText: bibliographyText,
    BIBLIOGRAPHY_UNCATEGORIZED: BIBLIOGRAPHY_UNCATEGORIZED,
    BIBLIOGRAPHY_CATEGORY_MAX: BIBLIOGRAPHY_CATEGORY_MAX,
    MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS: MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS,
    normalizeBibliographyCategory: normalizeBibliographyCategory,
    normalizeBibliographyCategories: normalizeBibliographyCategories,
    serializeBibliographyCategories: serializeBibliographyCategories,
    updateBibliographyCategories: updateBibliographyCategories,
    updateBibliographyCategory: updateBibliographyCategory,
    normalizeBibliographyCategoryOrder: normalizeBibliographyCategoryOrder,
    serializeBibliographyCategoryOrder: serializeBibliographyCategoryOrder,
    orderedBibliographyCategories: orderedBibliographyCategories,
    validatedBibliographyExternalUrl: validatedBibliographyExternalUrl,
    normalizeBibliographyLinks: normalizeBibliographyLinks,
    bibliographyRenderPlan: bibliographyRenderPlan,
    sectionBibliographyPlan: sectionBibliographyPlan,
    categorizedBibliographyText: categorizedBibliographyText,
    applyBibliographyCategories: applyBibliographyCategories,
    pickQueryText: pickQueryText,
    buildSuggestRequest: buildSuggestRequest,
    formatSuggestRows: formatSuggestRows,
    stanceBreakdownText: stanceBreakdownText,
    suggestionIsWeakEvidence: suggestionIsWeakEvidence,
    suggestionAutoLocator: suggestionAutoLocator,
    suggestionEvidenceFields: suggestionEvidenceFields,
    suggestionAssemblyFields: suggestionAssemblyFields,
    suggestionDetail: suggestionDetail,
    suggestionOpenPdfPath: suggestionOpenPdfPath,
    EVIDENCE_FORMATS: EVIDENCE_FORMATS,
    EVIDENCE_QUOTE_MAX: EVIDENCE_QUOTE_MAX,
    EVIDENCE_STANCE_TEXT_MAX: EVIDENCE_STANCE_TEXT_MAX,
    normalizeEvidenceAnnotations: normalizeEvidenceAnnotations,
    evidenceAnnotationRows: evidenceAnnotationRows,
    evidenceAnnotationDetail: evidenceAnnotationDetail,
    evidenceBodyText: evidenceBodyText,
    buildEvidenceStanceRequest: buildEvidenceStanceRequest,
    evidenceAssemblyFields: evidenceAssemblyFields,
    MAX_STATEMENT_LENGTH: MAX_STATEMENT_LENGTH,
    STATEMENT_TYPES: STATEMENT_TYPES,
    statementType: statementType,
    normalizeStatementText: normalizeStatementText,
    normalizeStagedStatements: normalizeStagedStatements,
    buildStatementStageRequest: buildStatementStageRequest,
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
    UNCITED_STRETCH_MIN_PARAGRAPHS: UNCITED_STRETCH_MIN_PARAGRAPHS,
    UNCITED_STRETCH_MIN_WORDS: UNCITED_STRETCH_MIN_WORDS,
    MAX_COVERAGE_STRETCHES: MAX_COVERAGE_STRETCHES,
    summarizeCitationCoverage: summarizeCitationCoverage,
    buildCitationsPanelEntries: buildCitationsPanelEntries,
    citationEvidenceFromItem: citationEvidenceFromItem,
    mergePanelEntryStatus: mergePanelEntryStatus,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CallosumCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
