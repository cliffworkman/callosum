/**
 * Callosum — Google Docs cite-while-you-write add-on (inc 170, Google Docs SP2).
 *
 * A sidebar that cites from your LOCAL callosum library: it reaches callosum over the cloudflared bridge
 * (https://callosum.clffwrkmn.net) with your access token (Settings → Remote access). Citations follow the Zotero
 * pattern — each is a Google Docs NamedRange (name = a uuid) whose cited work's CSL-JSON lives in
 * DocumentProperties; Refresh renders the whole ordered set via /citations/render-document and writes each
 * NamedRange's text back, then rebuilds a managed "References" block. The add-on never formats citations itself
 * (citeproc does, server-side) — it only places fields, so output matches the in-app "Cite as…".
 *
 * VERIFICATION REALITY: this glue runs only in Google's cloud — there is no way to exercise it from the repo. It
 * ships best-effort-correct per the Apps Script docs; the bug-prone request/response mapping lives in
 * gdocs_core.js (loaded here as `CallosumCore`, unit-tested with `node --test`). Add BOTH files to the project.
 *
 * Scope (SP2): Settings (URL + token) · Search → Insert · Refresh (in-text + bibliography) · Style switch.
 * Deferred (SP3): Suggest-from-the-selection (/citations/suggest) · Flatten (live → static).
 */

function onOpen() {
  DocumentApp.getUi().createAddonMenu().addItem("Open Callosum", "showSidebar").addToUi();
}

function onInstall(e) {
  onOpen(e);
}

function showSidebar() {
  var html = HtmlService.createHtmlOutputFromFile("sidebar").setTitle("Callosum");
  DocumentApp.getUi().showSidebar(html);
}

// ── Settings (UserProperties: per-user bridge URL + token; the token is NEVER returned to the sidebar) ────────
function getSettings() {
  var up = PropertiesService.getUserProperties();
  var dp = PropertiesService.getDocumentProperties();
  return {
    baseUrl: up.getProperty("CALLOSUM_BASE_URL") || "https://callosum.clffwrkmn.net",
    hasToken: !!up.getProperty("CALLOSUM_TOKEN"),
    style: dp.getProperty(CallosumCore.STYLE_KEY) || "apa",
  };
}

function saveSettings(baseUrl, token) {
  var up = PropertiesService.getUserProperties();
  if (baseUrl != null) up.setProperty("CALLOSUM_BASE_URL", String(baseUrl).replace(/\/+$/, ""));
  if (token) up.setProperty("CALLOSUM_TOKEN", String(token)); // only overwrite when a new token is provided
  return getSettings();
}

// ── HTTP through the bridge ───────────────────────────────────────────────────────────────────────────────
function _fetch(method, path, body) {
  var up = PropertiesService.getUserProperties();
  var base = up.getProperty("CALLOSUM_BASE_URL");
  var token = up.getProperty("CALLOSUM_TOKEN");
  if (!base) throw new Error("Set your Callosum URL + token in the sidebar first.");
  var opts = { method: method, muteHttpExceptions: true, headers: {} };
  if (token) opts.headers["Authorization"] = "Bearer " + token;
  if (body != null) {
    opts.contentType = "application/json";
    opts.payload = JSON.stringify(body);
  }
  var resp = UrlFetchApp.fetch(base + path, opts);
  var code = resp.getResponseCode();
  if (code === 401) throw new Error("Unauthorized — check your access token (Settings → Remote access).");
  if (code === 404)
    throw new Error("Not reachable through the bridge (cite-only). Is the tunnel + callosum running?");
  if (code >= 400) throw new Error("Callosum error " + code + ": " + resp.getContentText().slice(0, 200));
  return resp.getContentText();
}

// ── Sidebar-callable (google.script.run) ─────────────────────────────────────────────────────────────────
function searchPapers(query) {
  var q = String(query || "").trim();
  if (!q) return [];
  var arr = JSON.parse(_fetch("get", "/papers?q=" + encodeURIComponent(q) + "&limit=20"));
  return CallosumCore.formatSearchRows(arr);
}

function listStyles() {
  var data = JSON.parse(_fetch("get", "/citations/styles"));
  return { styles: data.styles || [], current: getSettings().style };
}

function setStyle(style) {
  PropertiesService.getDocumentProperties().setProperty(CallosumCore.STYLE_KEY, String(style || "apa"));
  return refreshDocument();
}

function insertCitation(paperId) {
  var doc = DocumentApp.getActiveDocument();
  var cursor = doc.getCursor();
  if (!cursor) throw new Error("Place your cursor in the body text where the citation should go.");

  // 1. the canonical CSL-JSON record for this paper
  var arr = JSON.parse(_fetch("post", "/papers/export", { paper_ids: [Number(paperId)], format: "csl-json" }));
  var csl = CallosumCore.firstCslRecord(arr);
  if (!csl) throw new Error("Could not load that reference.");

  // 2. a placeholder at the cursor, wrapped in a NamedRange; CSL-JSON → DocumentProperties; id → the order list
  var id = Utilities.getUuid();
  var dp = PropertiesService.getDocumentProperties();
  dp.setProperty("cite:" + id, CallosumCore.serializeItems([csl]));
  var start = cursor.getSurroundingTextOffset();
  if (start < 0) start = 0;
  var el = cursor.insertText("[…]"); // "[…]" — Refresh replaces it with the rendered in-text
  if (!el) throw new Error("Cannot insert here — place the cursor in the body text.");
  _wrapNamedRange(doc, CallosumCore.rangeName(id), el, start, start + 2); // "[…]" is 3 chars → [start, start+2]
  dp.setProperty(CallosumCore.ORDER_KEY, CallosumCore.serializeOrder(CallosumCore.appendOrder(dp.getProperty(CallosumCore.ORDER_KEY), id)));

  return refreshDocument();
}

function refreshDocument() {
  var doc = DocumentApp.getActiveDocument();
  var dp = PropertiesService.getDocumentProperties();
  var order = CallosumCore.parseOrder(dp.getProperty(CallosumCore.ORDER_KEY));

  // collect the live citations in insertion order; prune ids whose NamedRange or props are gone
  var ids = [];
  var itemsList = [];
  for (var i = 0; i < order.length; i++) {
    var id = order[i];
    var nrs = doc.getNamedRanges(CallosumCore.rangeName(id));
    var prop = dp.getProperty("cite:" + id);
    if (!nrs.length || !prop) {
      dp.deleteProperty("cite:" + id);
      continue;
    }
    ids.push(id);
    itemsList.push(CallosumCore.parseItems(prop));
  }
  dp.setProperty(CallosumCore.ORDER_KEY, CallosumCore.serializeOrder(ids));

  if (!ids.length) {
    _rebuildBibliography(doc, []);
    return { count: 0 };
  }

  var style = dp.getProperty(CallosumCore.STYLE_KEY) || "apa";
  var data = JSON.parse(_fetch("post", "/citations/render-document", CallosumCore.buildDocumentRequest(itemsList, style, "en-US")));
  var texts = CallosumCore.inTextResults(data);
  for (var j = 0; j < ids.length; j++) {
    _setRangeText(doc, CallosumCore.rangeName(ids[j]), texts[j] != null ? texts[j] : "[?]");
  }
  _rebuildBibliography(doc, CallosumCore.bibliographyEntries(data));
  return { count: ids.length };
}

// ── DOM helpers (Apps Script DocumentApp; untestable outside Google's cloud) ─────────────────────────────────
function _wrapNamedRange(doc, name, textEl, start, end) {
  var rb = doc.newRange();
  rb.addElement(textEl, start, end);
  doc.addNamedRange(name, rb.build());
}

// Replace a citation NamedRange's text with newText, then recreate the range (editing the text invalidates it —
// the same "setString destroys the mark" trap as the LibreOffice ReferenceMark adapter).
function _setRangeText(doc, name, newText) {
  var nrs = doc.getNamedRanges(name);
  if (!nrs.length) return false;
  var nr = nrs[0];
  var elems = nr.getRange().getRangeElements();
  if (!elems.length) {
    nr.remove();
    return false;
  }
  var re = elems[0];
  var el = re.getElement().editAsText();
  var start = re.isPartial() ? re.getStartOffset() : 0;
  var end = re.isPartial() ? re.getEndOffsetInclusive() : el.getText().length - 1;
  if (end >= start && start >= 0) el.deleteText(start, end);
  el.insertText(start, newText);
  nr.remove();
  var rb = doc.newRange();
  rb.addElement(el, start, start + newText.length - 1);
  doc.addNamedRange(name, rb.build());
  return true;
}

// Remove the old managed References block (heading + entries) and append a fresh one at the document end.
function _rebuildBibliography(doc, entries) {
  var body = doc.getBody();
  var nrs = doc.getNamedRanges(CallosumCore.BIB_NAME);
  for (var i = 0; i < nrs.length; i++) {
    var els = nrs[i].getRange().getRangeElements();
    for (var j = els.length - 1; j >= 0; j--) {
      try {
        body.removeChild(els[j].getElement()); // bib elements are whole paragraphs → removable top-level children
      } catch (err) {
        // a partial / non-removable element — skip it
      }
    }
    nrs[i].remove();
  }
  if (!entries.length) return;
  var rb = doc.newRange();
  var heading = body.appendParagraph("References");
  heading.setHeading(DocumentApp.ParagraphHeading.HEADING2);
  rb.addElement(heading);
  for (var k = 0; k < entries.length; k++) {
    rb.addElement(body.appendParagraph(entries[k]));
  }
  doc.addNamedRange(CallosumCore.BIB_NAME, rb.build());
}
