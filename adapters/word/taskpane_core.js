/*
 * Callosum Word add-in — PURE logic (no Office.js, no DOM).
 *
 * Kept separate from taskpane.js so it is unit-testable with `node --test` (no browser, no Office host).
 * The thin Office.js glue (taskpane.js) imports these as `CallosumCore.*` in the browser; the test file
 * `require()`s them in Node. Mirrors the LibreOffice adapter's pure helpers (build_search_rows, etc.).
 */
(function (root) {
  // A library paper's display author label for a search row. `authors` is a list of "Family, Given" strings
  // (the /papers list shape); we show the first author's family name + "et al." when there are more.
  function authorLabel(authors) {
    if (!Array.isArray(authors) || authors.length === 0) return "Unknown";
    var first = String(authors[0] || "").split(",")[0].trim() || "Unknown";
    return authors.length > 1 ? first + " et al." : first;
  }

  // Turn /papers?q= results (a bare list) into pick-list rows: {id, label}. label = "Author (Year) — Title".
  function formatSearchRows(papers) {
    if (!Array.isArray(papers)) return [];
    return papers.map(function (p) {
      var year = p && p.year ? " (" + p.year + ")" : "";
      var title = (p && p.title) ? String(p.title) : "Untitled";
      return { id: p && p.id, label: authorLabel(p && p.authors) + year + " — " + title };
    }).filter(function (r) { return r.id != null; });
  }

  // The POST /citations/render body to format ONE paper in a style (SP1 inserts the in-text citation as text).
  function buildRenderRequest(paperId, style, locale) {
    return { paper_ids: [paperId], style: style || "apa", locale: locale || "en-US" };
  }

  // Extract the formatted in-text citation from a /citations/render response ({items:[{in_text,...}]}).
  function inTextFromRender(data) {
    if (!data || !Array.isArray(data.items) || data.items.length === 0) return "";
    return String(data.items[0].in_text || "");
  }

  var api = { authorLabel: authorLabel, formatSearchRows: formatSearchRows, buildRenderRequest: buildRenderRequest, inTextFromRender: inTextFromRender };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CallosumCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
