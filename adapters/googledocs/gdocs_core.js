/*
 * Callosum Google Docs add-on — PURE logic (no Apps Script: no DocumentApp / UrlFetchApp / PropertiesService).
 *
 * This same file is BOTH unit-tested with `node --test` AND loaded by the Apps Script project (V8): in Node it
 * `module.exports`; in Apps Script `module` is undefined so the IIFE assigns `globalThis.CallosumCore`, which
 * Code.gs calls. So the bug-prone request/response mapping is covered by tests even though the in-Docs glue runs
 * only in Google's cloud (there is no way to exercise it from this repo). Same discipline as the Word adapter's
 * taskpane_core.js and the LibreOffice adapter's pure helpers.
 *
 * Citation model (the Zotero pattern): each citation is a Google Docs **NamedRange** named `CITATION_PREFIX + id`,
 * with its cited work's CSL-JSON kept in **DocumentProperties** (key `cite:<id>`); an insertion-order list lives in
 * DocumentProperties (`ORDER_KEY`). Refresh renders the whole ordered set via /citations/render-document and writes
 * each NamedRange's text back. Credits the Zotero CSL_CITATION embedded-CSL-JSON pattern (see THIRD-PARTY-NOTICES).
 */
(function (root) {
  var CITATION_PREFIX = "CALLOSUM_CITATION_"; // NamedRange name per citation = prefix + a uuid
  var BIB_NAME = "CALLOSUM_BIBLIOGRAPHY"; // NamedRange name for the managed References block
  var ORDER_KEY = "CALLOSUM_ORDER"; // DocumentProperties: JSON array of citation ids, insertion order
  var STYLE_KEY = "CALLOSUM_STYLE"; // DocumentProperties: the chosen CSL style id

  function rangeName(id) {
    return CITATION_PREFIX + id;
  }

  // ---- library search rows (GET /papers?q= returns a bare JSON array of {id,title,year,authors}) ----
  function authorLabel(authors) {
    if (!Array.isArray(authors) || authors.length === 0) return "Unknown";
    var first = String(authors[0] || "").split(",")[0].trim() || "Unknown";
    return authors.length > 1 ? first + " et al." : first;
  }
  function formatSearchRows(papers) {
    if (!Array.isArray(papers)) return [];
    return papers
      .map(function (p) {
        var year = p && p.year ? " (" + p.year + ")" : "";
        var title = p && p.title ? String(p.title) : "Untitled";
        return { id: p && p.id, label: authorLabel(p && p.authors) + year + " — " + title };
      })
      .filter(function (r) {
        return r.id != null;
      });
  }

  // The CSL-JSON record for an inserted paper, from a /papers/export (csl-json) response (a JSON array).
  function firstCslRecord(arr) {
    return Array.isArray(arr) && arr.length ? arr[0] : null;
  }

  // ---- the /citations/render-document contract ----
  // itemsList = per-cluster CSL-JSON item arrays in DOCUMENT (insertion) ORDER, one per citation NamedRange.
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
    return data.citations.map(function (c) {
      return String((c && c.text) || "");
    });
  }
  // The bibliography as one entry per line (the endpoint returns bibliography_text = entries joined by "\n").
  function bibliographyEntries(data) {
    var txt = (data && data.bibliography_text) || "";
    return String(txt)
      .split("\n")
      .map(function (s) {
        return s.trim();
      })
      .filter(function (s) {
        return s.length > 0;
      });
  }

  // ---- the DocumentProperties side-store ----
  function parseOrder(json) {
    try {
      var a = JSON.parse(json || "[]");
      return Array.isArray(a)
        ? a.filter(function (x) {
            return typeof x === "string";
          })
        : [];
    } catch (e) {
      return [];
    }
  }
  function serializeOrder(ids) {
    return JSON.stringify(Array.isArray(ids) ? ids : []);
  }
  function appendOrder(json, id) {
    var a = parseOrder(json);
    if (a.indexOf(id) === -1) a.push(id);
    return a;
  }
  // each citation's DocumentProperties value is {items:[csl,...]}; malformed → [] (never guess).
  function parseItems(json) {
    try {
      var p = JSON.parse(json);
      return p && Array.isArray(p.items) ? p.items : [];
    } catch (e) {
      return [];
    }
  }
  function serializeItems(items) {
    return JSON.stringify({ items: items || [] });
  }

  // ---- Suggest-from-the-selection (SP3, the /citations/suggest contract — inc 156) ----
  // The query text: the highlighted selection, else the paragraph the cursor sits in.
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
  // Suggestion rows: '[stance] Author Year · match N.NN — "quote…"' — the quote IS the reason (signal not verdict).
  function formatSuggestRows(suggestions) {
    if (!Array.isArray(suggestions)) return [];
    return suggestions
      .map(function (s) {
        var author = s && s.author ? s.author : "Unknown";
        var year = s && s.year ? " " + s.year : "";
        var match = s && typeof s.match_score === "number" ? " · match " + s.match_score.toFixed(2) : "";
        var quote = s && s.quote ? ' — "' + String(s.quote).slice(0, 80).trim() + '…"' : "";
        return { id: s && s.paper_id, label: _stanceTag(s && s.stance) + " " + author + year + match + quote };
      })
      .filter(function (r) {
        return r.id != null;
      });
  }

  var api = {
    CITATION_PREFIX: CITATION_PREFIX,
    BIB_NAME: BIB_NAME,
    ORDER_KEY: ORDER_KEY,
    STYLE_KEY: STYLE_KEY,
    rangeName: rangeName,
    authorLabel: authorLabel,
    formatSearchRows: formatSearchRows,
    firstCslRecord: firstCslRecord,
    buildDocumentRequest: buildDocumentRequest,
    inTextResults: inTextResults,
    bibliographyEntries: bibliographyEntries,
    parseOrder: parseOrder,
    serializeOrder: serializeOrder,
    appendOrder: appendOrder,
    parseItems: parseItems,
    serializeItems: serializeItems,
    pickQueryText: pickQueryText,
    buildSuggestRequest: buildSuggestRequest,
    formatSuggestRows: formatSuggestRows,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CallosumCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
