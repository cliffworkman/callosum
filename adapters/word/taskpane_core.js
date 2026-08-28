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
 *
 * SP4: Word-on-the-web relay. Desktop Word loads this page same-origin from callosum (no token needed); Word
 * Online instead loads it through the existing cloudflared cite-only tunnel (a different origin), which is
 * gated by callosum's Remote-access bearer token. `isLocalOrigin`/`authHeaders` decide, from `location.hostname`
 * alone, whether a fetch needs that header -- desktop behavior is unchanged either way.
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
    isLocalOrigin: isLocalOrigin,
    authHeaders: authHeaders,
    LOCATOR_LABELS: LOCATOR_LABELS,
    itemOverrides: itemOverrides,
    buildClusterItems: buildClusterItems,
    cslRecordRow: cslRecordRow,
    formatAssemblyRow: formatAssemblyRow,
    assemblyRowFromDecodedItem: assemblyRowFromDecodedItem,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CallosumCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
