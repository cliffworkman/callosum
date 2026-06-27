/*
 * Callosum Word add-in — PURE logic (no Office.js, no DOM).
 *
 * Kept separate from taskpane.js so it is unit-testable with `node --test` (no browser, no Office host) — which
 * matters especially because there is no headless Word to exercise the Office.js glue. The browser uses these as
 * `CallosumCore.*`; the test file `require()`s them in Node. Mirrors the LibreOffice adapter's pure helpers.
 *
 * SP2 (inc 165): each citation is a Word **Content Control** whose `.tag` carries the cited cluster's CSL-JSON
 * (base64), like the Zotero/LibreOffice embedded-CSL-JSON pattern. A Refresh scans those controls in document
 * order, POSTs them to /citations/render-document, and writes back the position-aware in-text + bibliography.
 */
(function (root) {
  var CITATION_PREFIX = "CALLOSUM_CITATION"; // content-control tag prefix for a citation cluster
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

  // ---- the live-citation tag (SP2) ----
  // tag = "CALLOSUM_CITATION <base64 of {items:[csl, ...]}>"  (a cluster = one or more CSL-JSON works).
  function encodeCitationTag(items) {
    return CITATION_PREFIX + " " + b64encode(JSON.stringify({ items: items || [] }));
  }
  function isCitationTag(tag) {
    return typeof tag === "string" && tag.indexOf(CITATION_PREFIX + " ") === 0;
  }
  function decodeCitationTag(tag) {
    if (!isCitationTag(tag)) return null;
    try {
      var payload = JSON.parse(b64decode(tag.slice((CITATION_PREFIX + " ").length)));
      var items = payload && Array.isArray(payload.items) ? payload.items : [];
      return items.length ? items : null;
    } catch (e) {
      return null; // malformed → never guess; the caller skips it
    }
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

  var api = {
    CITATION_PREFIX: CITATION_PREFIX,
    BIB_TAG: BIB_TAG,
    authorLabel: authorLabel,
    formatSearchRows: formatSearchRows,
    firstCslRecord: firstCslRecord,
    encodeCitationTag: encodeCitationTag,
    isCitationTag: isCitationTag,
    decodeCitationTag: decodeCitationTag,
    buildDocumentRequest: buildDocumentRequest,
    inTextResults: inTextResults,
    bibliographyText: bibliographyText,
    pickQueryText: pickQueryText,
    buildSuggestRequest: buildSuggestRequest,
    formatSuggestRows: formatSuggestRows,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CallosumCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
