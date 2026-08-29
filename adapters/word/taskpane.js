/*
 * Callosum Word add-in — the thin Office.js glue (inc 166, SP3: parity — suggest / style-switch / flatten;
 * SP4: Word-on-the-web relay; inc 509: grouped-citation composer with locators/edit/delete; inc 516: Citations
 * in this document panel; inc 517: accessibility; inc 519: Custom-XML storage; inc 520: native notes;
 * inc 521: document-local bibliography categories; inc 522: bounded batch assignment; inc 523: category order;
 * inc 524: heading-scoped bibliography blocks; inc 525: opt-in bibliography title/DOI links;
 * inc 526: evidence-aware Suggest details and audit records; inc 527: open-science statement insertion).
 *
 * Architecture A (desktop): this page is served by callosum over HTTPS (https://localhost:8443), so every fetch
 * is a SAME-ORIGIN call to the local API — nothing leaves the machine, and (inc 511) desktop genuinely never
 * needs a token, EVEN if Remote Access happens to be on for a tunnel elsewhere: tools/run_https.py deliberately
 * exempts its own dedicated :8443 process from the token gate, since cloudflared's ingress can only ever target
 * the plain HTTP dev port (never :8443 — see cloudflared-config.yml's own warning). If a fetch ever DOES come
 * back 401 anyway (e.g. this page wasn't served via run_https.py, or the tunnel was misconfigured), the token
 * section reveals itself reactively as a fallback (inc 510) — that's a signal something's off, not the normal
 * flow, but it keeps desktop workable rather than silently broken in that edge case.
 * Architecture B (Word-on-the-web, SP4): Word Online can't reach localhost at all, so this same page is instead
 * loaded through callosum's existing cloudflared cite-only tunnel (adapters/googledocs/cloudflared-config.yml,
 * extended to also relay these task-pane files) at a public hostname. Every fetch is still same-origin (relative
 * paths — no separate "server URL" setting, unlike the Google Docs add-on, which runs in a genuinely different
 * origin) but now needs the Remote-access Bearer token, since the tunnel forwards to callosum with that gate on.
 * `authToken()` reads any saved token regardless of origin; the tunnel section is always shown up front here.
 * Every fetch below is wrapped with `CallosumCore.authHeaders(...)`.
 *
 * The add-in is a thin field-placer:
 *   • Add     — a search/suggest row click fetches the paper's CSL-JSON (/papers/export) and adds it to the
 *               "assembly" being built (inc 509) — never inserts immediately, so several works can be combined
 *               into ONE grouped citation, each with its own locator/label/prefix/suffix/suppress-author.
 *   • Insert/Update — stores the assembly's items in a Custom XML Part and puts only that part's opaque ID in
 *               the Content Control tag (a NEW citation at the END of the selection, so Suggest inserts AFTER
 *               the sentence), or updates the existing part in Edit mode, then Refresh.
 *   • Suggest — read the sentence (selection, else the paragraph), POST /citations/suggest → ranked candidates
 *               with stance + quote (the reason); pick one to add to the assembly.
 *   • Edit/Delete at cursor — reads the citation Content Control the cursor is inside
 *               (Range.parentContentControlOrNullObject) to repopulate the composer or remove it outright.
 *   • Refresh — scan main + native note-body citation controls; note styles carry Word's native one-based
 *               noteIndex → /citations/render-document → write back citations + a managed bibliography block.
 *   • Style   — changing the dropdown re-renders the whole document (one-click) + persists in the doc settings.
 *   • Flatten — convert the live citation + bibliography controls to plain text (one-way).
 * All formatting happens in callosum's citeproc engine (this never formats).
 *
 * Pure logic lives in taskpane_core.js (CallosumCore.*) and is unit-tested with `node --test` — important because
 * there is no headless Word to exercise the Office.js parts below.
 */
/* global Office, Word, CallosumCore */
(function () {
  "use strict";

  var TOKEN_KEY = "callosum.accessToken"; // same key name the main app's fetch shim uses (00_lib.jsx) — a
  // different key per browser origin regardless (localStorage is origin-scoped), so no collision risk; kept
  // for naming consistency only.
  var isTunneled = !CallosumCore.isLocalOrigin(window.location.hostname);

  // ---- citation composer state (inc 509) ----
  // `assembly`: the ordered list of {csl, locator, label, prefix, suffix, "suppress-author", "author-only"}
  // rows being built into ONE citation cluster (mirrors adapters/libreoffice/composer.py's own `assembly`).
  // `editingCC`: null when building a NEW citation; a tracked Word.ContentControl (see the correlated-objects
  // pattern -- .track()/.untrack() -- since a proxy object can't otherwise survive between separate Word.run
  // calls) when editing an EXISTING one at the cursor.
  var assembly = [];
  var editingCC = null;
  var openOptionsIdx = -1; // which assembly row's Options panel is expanded, or -1
  var suggestionItems = Object.create(null);
  var suggestionLocators = Object.create(null);
  var suggestionRows = [];
  var openSuggestionId = null;
  var styleFormats = Object.create(null); // style id -> CSL citation-format from the shared catalog
  var BIBLIOGRAPHY_CATEGORY_SETTING = "callosumBibliographyCategories";
  var BIBLIOGRAPHY_CATEGORY_ORDER_SETTING = "callosumBibliographyCategoryOrder";
  var BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING = "callosumBibliographyExternalLinks";
  var stagedStatements = Object.create(null);
  var statementDrafts = Object.create(null);
  var statementInFlight = false;

  // ---- live-citation storage ----
  // Current citations keep CSL-JSON in a Word Custom XML Part (WordApi 1.4) and only an opaque reference in the
  // Content Control tag. Legacy base64-in-tag citations remain readable and migrate on the next Refresh/Edit.
  // This is deliberately Office.js-only glue; serialization/classification stays in the Node-tested core.
  function requireCustomXmlSupport() {
    if (!Office.context.requirements || !Office.context.requirements.isSetSupported("WordApi", "1.4")) {
      throw new Error("this Word version does not support Callosum's live-citation storage (WordApi 1.4 required)");
    }
  }

  async function createCitationPart(ctx, items) {
    requireCustomXmlSupport();
    var part = ctx.document.customXmlParts.add(CallosumCore.encodeCitationXml(items));
    part.load("id");
    await ctx.sync();
    return part;
  }

  // Resolve all current short-reference tags in two bounded syncs: first determine which requested XML parts
  // exist, then fetch XML only for real parts. Legacy records decode locally and do not require WordApi 1.4.
  async function resolveControlRecords(ctx, controls) {
    var records = (controls || []).map(function (cc) {
      return { cc: cc, tag: cc.tag, items: null, partId: null, part: null, xmlResult: null };
    });
    var referenced = records.filter(function (record) {
      record.partId = CallosumCore.citationReferenceId(record.tag);
      if (!record.partId && CallosumCore.isLegacyCitationTag(record.tag)) {
        record.items = CallosumCore.decodeCitationTag(record.tag);
      }
      return !!record.partId;
    });
    if (!referenced.length) return records;

    requireCustomXmlSupport();
    var partsById = Object.create(null);
    referenced.forEach(function (record) {
      if (partsById[record.partId]) return;
      var part = ctx.document.customXmlParts.getItemOrNullObject(record.partId);
      part.load("id");
      partsById[record.partId] = part;
    });
    await ctx.sync();
    referenced.forEach(function (record) {
      var part = partsById[record.partId];
      if (!part.isNullObject) {
        record.part = part;
        record.xmlResult = part.getXml();
      }
    });
    await ctx.sync();
    referenced.forEach(function (record) {
      if (record.xmlResult) record.items = CallosumCore.decodeCitationXml(record.xmlResult.value);
    });
    return records;
  }

  function notesSupported() {
    return !!(Office.context.requirements && Office.context.requirements.isSetSupported("WordApi", "1.5"));
  }
  function requireNotesSupport() {
    if (!notesSupported()) throw new Error("this Word version does not support native note citations (WordApi 1.5 required)");
  }

  function sectionBibliographiesSupported() {
    return !!(Office.context.requirements && Office.context.requirements.isSetSupported("WordApi", "1.6"));
  }
  function requireSectionBibliographiesSupport() {
    if (!sectionBibliographiesSupported()) {
      throw new Error("heading-scoped bibliographies require WordApi 1.6 on this Word version");
    }
  }
  function requireParagraphIdentitySupport() {
    if (!sectionBibliographiesSupported()) {
      throw new Error("citation coverage requires WordApi 1.6 on this Word version");
    }
  }
  function newSectionBibliographyId() {
    var bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return CallosumCore.sectionBibliographyIdFromBytes(bytes);
  }

  // Collect main-story controls plus every footnote/endnote body's controls. Native collection position—not
  // citation count—is the one-based noteIndex: ordinary non-Callosum notes intentionally leave gaps, and two
  // citation clusters in the same note intentionally share an index.
  async function loadDocumentControlRecords(ctx) {
    var bodyControls = ctx.document.body.contentControls;
    bodyControls.load("items/tag,id,text");
    var footnotes = null, endnotes = null;
    var footnoteStories = [], endnoteStories = [];
    if (notesSupported()) {
      footnotes = ctx.document.body.footnotes;
      endnotes = ctx.document.body.endnotes;
      footnotes.load("items");
      endnotes.load("items");
    }
    await ctx.sync();

    if (footnotes) {
      footnotes.items.forEach(function (note) {
        var noteBody = note.body;
        var controls = noteBody.contentControls;
        noteBody.load("text");
        controls.load("items/tag,id,text");
        footnoteStories.push({ note: note, body: noteBody, controls: controls });
      });
      endnotes.items.forEach(function (note) {
        var noteBody = note.body;
        var controls = noteBody.contentControls;
        noteBody.load("text");
        controls.load("items/tag,id,text");
        endnoteStories.push({ note: note, body: noteBody, controls: controls });
      });
      await ctx.sync();
    }

    var entries = bodyControls.items.map(function (cc) {
      return { cc: cc, location: "inline", noteIndex: 0 };
    });
    if (footnotes) {
      footnoteStories.forEach(function (story, index) {
        story.controls.items.forEach(function (cc) {
          entries.push({ cc: cc, location: "footnote", noteIndex: index + 1, note: story.note,
            noteText: story.body.text, noteControlCount: story.controls.items.length });
        });
      });
      endnoteStories.forEach(function (story, index) {
        story.controls.items.forEach(function (cc) {
          entries.push({ cc: cc, location: "endnote", noteIndex: index + 1, note: story.note,
            noteText: story.body.text, noteControlCount: story.controls.items.length });
        });
      });
    }
    var records = await resolveControlRecords(ctx, entries.map(function (entry) { return entry.cc; }));
    records.forEach(function (record, index) {
      record.location = entries[index].location;
      record.noteIndex = entries[index].noteIndex;
      record.note = entries[index].note || null;
      record.noteText = entries[index].noteText || "";
      record.noteControlCount = entries[index].noteControlCount || 0;
    });
    return records;
  }

  // Paragraph ids are session-local by design: they correlate the main-story controls with Word's current
  // outline only inside this Word.run batch. Persistent identity lives solely in the strict paired tags.
  async function loadSectionParagraphContext(ctx, records, selection) {
    requireSectionBibliographiesSupport();
    var paragraphs = ctx.document.body.paragraphs;
    paragraphs.load("items/uniqueLocalId,items/outlineLevel");
    var relevant = (records || []).filter(function (record) {
      return record.location === "inline" &&
        (CallosumCore.isCitationTag(record.tag) || CallosumCore.isSectionBibliographyTag(record.tag));
    });
    relevant.forEach(function (record) {
      record.sectionParagraph = record.cc.paragraphs.getFirst();
      record.sectionParagraph.load("uniqueLocalId,outlineLevel");
    });
    var selectionParagraph = null;
    if (selection) {
      selectionParagraph = selection.paragraphs.getFirst();
      selectionParagraph.load("uniqueLocalId,outlineLevel");
    }
    await ctx.sync();
    relevant.forEach(function (record) { record.sectionParagraphId = record.sectionParagraph.uniqueLocalId; });
    return {
      paragraphs: paragraphs.items.map(function (paragraph) {
        return { id: paragraph.uniqueLocalId, outlineLevel: paragraph.outlineLevel };
      }),
      selectionParagraphId: selectionParagraph ? selectionParagraph.uniqueLocalId : null,
    };
  }

  function requireHealthySectionBibliographies(records) {
    var inventory = CallosumCore.sectionBibliographyInventory(records);
    if (inventory.damaged.length) {
      throw new Error("Document diagnostics found damaged section bibliography controls. " +
        "Remove or repair them before continuing.");
    }
    return inventory;
  }

  function citationRecords(records) {
    return (records || []).filter(function (record) { return CallosumCore.isCitationTag(record.tag); });
  }
  function assertPlacementCompatible(records) {
    var issue = CallosumCore.placementIssue(citationRecords(records), currentCitationFormat(), currentNotePreference());
    if (issue) throw new Error(issue);
  }

  // Refresh is already a document-mutating operation, so it is the safe migration boundary: valid legacy
  // citations get a new part, and duplicate references produced by copy/paste are cloned so later edits remain
  // citation-local. Missing/malformed parts stay untouched and fail closed for Document diagnostics to report.
  async function normalizeCitationStorage(ctx, records) {
    var seenPartIds = Object.create(null);
    var additions = [];
    (records || []).forEach(function (record) {
      if (!record.items) return;
      var needsPart = CallosumCore.isLegacyCitationTag(record.tag) ||
        (record.partId && seenPartIds[record.partId]);
      if (record.partId) seenPartIds[record.partId] = true;
      if (!needsPart) return;
      requireCustomXmlSupport();
      var part = ctx.document.customXmlParts.add(CallosumCore.encodeCitationXml(record.items));
      part.load("id");
      additions.push({ record: record, part: part });
    });
    if (!additions.length) return records;
    await ctx.sync();
    additions.forEach(function (entry) {
      entry.record.cc.tag = CallosumCore.encodeCitationReferenceTag(entry.part.id);
      entry.record.tag = entry.record.cc.tag;
      entry.record.partId = entry.part.id;
      entry.record.part = entry.part;
    });
    await ctx.sync();
    return records;
  }

  async function writeCitationItems(ctx, cc, items) {
    var partId = CallosumCore.citationReferenceId(cc.tag);
    if (partId) {
      requireCustomXmlSupport();
      var part = ctx.document.customXmlParts.getItemOrNullObject(partId);
      part.load("id");
      await ctx.sync();
      if (part.isNullObject) throw new Error("the citation's Custom XML data is missing");
      part.setXml(CallosumCore.encodeCitationXml(items));
      await ctx.sync();
      return;
    }
    if (!CallosumCore.isLegacyCitationTag(cc.tag)) throw new Error("the citation storage reference is malformed");
    var migratedPart = await createCitationPart(ctx, items);
    cc.tag = CallosumCore.encodeCitationReferenceTag(migratedPart.id);
    await ctx.sync();
  }

  function configureCitationControl(cc, partId) {
    cc.tag = CallosumCore.encodeCitationReferenceTag(partId);
    cc.title = "Callosum citation";
    cc.appearance = Word.ContentControlAppearance.hidden;
  }

  function $(id) { return document.getElementById(id); }
  // Read any saved token regardless of origin (inc 510) -- empty when none is saved, which is a no-op exactly
  // like before for the common desktop-with-Remote-Access-off case.
  function authToken() {
    return window.localStorage.getItem(TOKEN_KEY) || "";
  }
  // Reveal the (usually-hidden, on desktop) token section with an explanatory message -- called reactively the
  // moment a fetch actually needs a token this session hasn't got, rather than guessing origin alone.
  function revealTokenSection(message) {
    $("tunnel").style.display = "block";
    setStatus(message, true);
  }
  // Wraps `fetch` with the Bearer header (attached only when a token is actually saved -- see authHeaders).
  // A 401 means this callosum instance needs a token this session doesn't have (or it's stale) -- reveal the
  // token field instead of leaving whichever caller's own generic error message as the only explanation.
  function callosumFetch(url, opts) {
    var o = opts || {};
    return fetch(url, Object.assign({}, o, { headers: CallosumCore.authHeaders(o.headers, authToken()) }))
      .then(function (r) {
        if (r.status === 401) {
          revealTokenSection("This callosum instance requires an access token (Settings → Remote access) — paste it below and try again.");
        }
        return r;
      });
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function setStatus(msg, isErr) {
    var el = $("status");
    el.textContent = msg || "";
    el.className = "status" + (isErr ? " err" : "");
  }
  function debounce(fn, ms) {
    var t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }
  function currentStyle() {
    var sel = $("style");
    return (sel && sel.value) || "apa";
  }
  function currentCitationFormat() {
    return styleFormats[currentStyle()] || "in-text";
  }
  function currentNotePreference() {
    return CallosumCore.normalizeNotePreference($("notePlacement").value);
  }
  function currentBibliographyCategories() {
    try {
      return CallosumCore.normalizeBibliographyCategories(
        Office.context.document.settings.get(BIBLIOGRAPHY_CATEGORY_SETTING),
      );
    } catch (e) { return {}; }
  }
  function currentBibliographyCategoryOrder() {
    try {
      return CallosumCore.normalizeBibliographyCategoryOrder(
        Office.context.document.settings.get(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING),
      );
    } catch (e) { return []; }
  }
  function currentBibliographyExternalLinks() {
    try {
      return Office.context.document.settings.get(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING) === "1";
    } catch (e) { return false; }
  }
  function saveDocumentSettings() {
    return new Promise(function (resolve, reject) {
      Office.context.document.settings.saveAsync(function (result) {
        if (result && result.status === Office.AsyncResultStatus.Failed) {
          reject(new Error((result.error && result.error.message) || "Word could not save the document setting"));
        } else resolve();
      });
    });
  }
  async function persistBibliographyCategories(assignments) {
    var encoded = CallosumCore.serializeBibliographyCategories(assignments);
    if (encoded === "{}") Office.context.document.settings.remove(BIBLIOGRAPHY_CATEGORY_SETTING);
    else Office.context.document.settings.set(BIBLIOGRAPHY_CATEGORY_SETTING, encoded);
    await saveDocumentSettings();
  }
  async function persistBibliographyCategoryOrder(order) {
    var encoded = CallosumCore.serializeBibliographyCategoryOrder(order);
    if (encoded === "[]") Office.context.document.settings.remove(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING);
    else Office.context.document.settings.set(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING, encoded);
    await saveDocumentSettings();
  }
  async function restoreBibliographyCategoryOrder(rawValue) {
    if (rawValue == null) Office.context.document.settings.remove(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING);
    else Office.context.document.settings.set(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING, rawValue);
    await saveDocumentSettings();
  }
  async function persistBibliographyExternalLinks(enabled) {
    if (enabled) Office.context.document.settings.set(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING, "1");
    else Office.context.document.settings.remove(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING);
    await saveDocumentSettings();
  }
  async function restoreBibliographyExternalLinks(rawValue) {
    if (rawValue == null) Office.context.document.settings.remove(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING);
    else Office.context.document.settings.set(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING, rawValue);
    await saveDocumentSettings();
  }
  function updateNotePlacementVisibility() {
    $("notePlacementField").style.display = CallosumCore.isNoteStyle(currentCitationFormat()) ? "block" : "none";
  }
  function renderRows(ulId, rows, emptyMsg) {
    $(ulId).innerHTML = rows.length
      ? rows.map(function (row) {
          return '<li><button class="row" data-id="' + row.id + '">' + escapeHtml(row.label) + "</button></li>";
        }).join("")
      : '<li class="empty">' + escapeHtml(emptyMsg) + "</li>";
  }

  function suggestionHasLocatorOverride(paperId) {
    return Object.prototype.hasOwnProperty.call(suggestionLocators, String(paperId));
  }
  function renderSuggestionRows(rows, emptyMsg) {
    $("suggestions").innerHTML = rows.length ? rows.map(function (row) {
      var id = String(row.id), item = suggestionItems[id];
      var expanded = openSuggestionId === id;
      var detail = CallosumCore.suggestionDetail(
        item, suggestionLocators[id], suggestionHasLocatorOverride(id),
      );
      var detailId = "suggestion-detail-" + id;
      var detailHtml = expanded ? (
        '<div class="suggestion-details" id="' + detailId + '">' +
          '<blockquote class="suggestion-quote">' + escapeHtml(detail.quote || "No matched passage available.") + "</blockquote>" +
          '<p class="suggestion-meta">' + escapeHtml(detail.page) + "</p>" +
          '<p class="suggestion-meta">' + escapeHtml(detail.stance) + "</p>" +
          '<p class="suggestion-meta">' + escapeHtml(detail.reason) + "</p>" +
          (detail.weak ? '<p class="suggestion-warning">⚠ Weak evidence — neither the match nor the support signal clears Callosum’s verification thresholds. Verify before citing.</p>' : "") +
          '<p class="suggestion-meta">If you insert this work, Callosum stores a short matched-passage snippet inside this Word document for later audit.</p>' +
          '<label class="field-inline">Page locator<input type="text" maxlength="80" data-suggestion-locator="' +
            escapeHtml(id) + '" value="' + escapeHtml(detail.locator) + '"/></label>' +
          '<div class="actions"><button type="button" class="secondary" data-suggestion-open-pdf="' +
            escapeHtml(id) + '"' + (detail.canOpenPdf ? "" : " disabled") + ">Open in PDF</button></div>" +
        "</div>"
      ) : "";
      return '<li><div class="suggestion-row-main">' +
        '<button class="row" data-id="' + escapeHtml(id) + '">' + escapeHtml(row.label) + "</button>" +
        '<button type="button" class="secondary" data-suggestion-details="' + escapeHtml(id) +
          '" aria-expanded="' + expanded + '" aria-controls="' + detailId + '">Details…</button>' +
        "</div>" + detailHtml + "</li>";
    }).join("") : '<li class="empty">' + escapeHtml(emptyMsg) + "</li>";
  }

  async function loadStyles() {
    try {
      var r = await callosumFetch("/citations/styles");
      if (!r.ok) return;
      var data = await r.json();
      var sel = $("style");
      styleFormats = Object.create(null);
      ((data && data.styles) || []).forEach(function (s) { styleFormats[s.id] = s.citation_format || s.family; });
      sel.innerHTML = ((data && data.styles) || []).map(function (s) {
        return '<option value="' + escapeHtml(s.id) + '">' + escapeHtml(s.title || s.id) + "</option>";
      }).join("");
      if (data && data.default_style) sel.value = data.default_style;
    } catch (e) { /* styles are optional polish; the default 'apa' still works */ }
    // A persisted per-document style choice wins (set programmatically → does not fire 'change').
    try {
      var saved = Office.context.document.settings.get("callosumStyle");
      if (saved) $("style").value = saved;
      var savedNotePlacement = Office.context.document.settings.get("callosumNotePlacement");
      if (savedNotePlacement) $("notePlacement").value = CallosumCore.normalizeNotePreference(savedNotePlacement);
    } catch (e) { /* settings unavailable → keep the default */ }
    $("bibliographyExternalLinks").checked = currentBibliographyExternalLinks();
    updateNotePlacementVisibility();
  }

  async function search() {
    var q = $("q").value.trim();
    if (!q) { $("results").innerHTML = ""; return; }
    try {
      var r = await callosumFetch("/papers?q=" + encodeURIComponent(q) + "&limit=20");
      if (!r.ok) throw new Error("search failed (" + r.status + ")");
      renderRows("results", CallosumCore.formatSearchRows(await r.json()), "No matches in your library.");
    } catch (e) {
      $("results").innerHTML = '<li class="err">' + escapeHtml(String((e && e.message) || e)) + "</li>";
    }
  }

  // Suggest papers from the sentence being written (the selection, else the cursor's paragraph).
  async function suggestSentence() {
    setStatus("Finding relevant papers… (the first run loads the local models)");
    $("suggestions").innerHTML = "";
    suggestionItems = Object.create(null);
    suggestionLocators = Object.create(null);
    suggestionRows = [];
    openSuggestionId = null;
    try {
      var queryText = "";
      await Word.run(async function (ctx) {
        var sel = ctx.document.getSelection();
        sel.load("text");
        var para = sel.paragraphs.getFirst();
        para.load("text");
        await ctx.sync();
        queryText = CallosumCore.pickQueryText(sel.text, para.text);
      });
      if (!queryText) { setStatus("Place your cursor in a sentence first.", true); return; }
      var r = await callosumFetch("/citations/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(CallosumCore.buildSuggestRequest(queryText, 8)),
      });
      if (!r.ok) throw new Error("suggest failed (" + r.status + ")");
      var data = await r.json();
      var suggestions = (data && data.suggestions) || [];
      suggestions.forEach(function (item) {
        if (item && item.paper_id != null) suggestionItems[String(item.paper_id)] = item;
      });
      suggestionRows = CallosumCore.formatSuggestRows(suggestions);
      renderSuggestionRows(suggestionRows, "No relevant papers in your library.");
      setStatus(suggestionRows.length ? "Pick a paper to add — ranked by relevance; the quote is the reason." : "");
    } catch (e) {
      setStatus("Couldn't suggest: " + ((e && e.message) || e), true);
    }
  }

  // ---- citation composer (inc 509): add works to an assembly, set per-item locator/prefix/suffix, then
  // insert (or update an existing citation) as ONE cluster. Mirrors composer.py's own assembly model.

  // A search/suggest row was clicked: fetch its CSL-JSON and add it to the assembly being built (never
  // inserts immediately — that's what the Insert/Update button is for, so several works can be combined).
  async function onPick(ev) {
    var btn = ev.target.closest("button.row[data-id]");
    if (!btn) return;
    var paperId = Number(btn.getAttribute("data-id"));
    var suggestion = btn.closest("#suggestions") ? suggestionItems[String(paperId)] : null;
    setStatus("Adding…");
    try {
      var r = await callosumFetch("/papers/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format: "csl-json" }),
      });
      if (!r.ok) throw new Error("export failed (" + r.status + ")");
      var exported = CallosumCore.firstCslRecord(await r.json());
      if (!exported) throw new Error("no CSL-JSON returned");
      // The stored csl_json.id isn't guaranteed to be the real paper id (inc 512) -- stamp a reliable one
      // (matching callosum_cite.py's own convention) so Document diagnostics can later identify this citation.
      var csl = CallosumCore.stampCallosumId(exported, paperId);
      var row = { csl: csl, row: CallosumCore.cslRecordRow(csl) };
      if (suggestion) {
        Object.assign(row, CallosumCore.suggestionAssemblyFields(
          suggestion,
          suggestionLocators[String(paperId)],
          suggestionHasLocatorOverride(paperId),
        ));
      }
      assembly.push(row);
      openOptionsIdx = -1;
      renderAssembly();
      setStatus(assembly.length + " work(s) in this citation — add more, set a locator, or Insert.");
    } catch (e) {
      setStatus("Couldn't add: " + ((e && e.message) || e), true);
    }
  }

  function assemblyRowLabel(row) {
    return CallosumCore.formatAssemblyRow(Object.assign({}, row, { row: row.row || CallosumCore.cslRecordRow(row.csl) }));
  }

  function renderOptionsPanel(row) {
    var labelOptions = ['<option value="">(none)</option>'].concat(
      CallosumCore.LOCATOR_LABELS.map(function (l) {
        return '<option value="' + l + '"' + (row.label === l ? " selected" : "") + ">" + l + "</option>";
      }),
    ).join("");
    return (
      '<div class="assembly-row-options">' +
        '<label class="field-inline">Locator label<select data-field="label">' + labelOptions + "</select></label>" +
        '<label class="field-inline">Locator (e.g. a page number)<input type="text" data-field="locator" value="' +
          escapeHtml(row.locator || "") + '"/></label>' +
        '<label class="field-inline">Prefix<input type="text" data-field="prefix" value="' +
          escapeHtml(row.prefix || "") + '"/></label>' +
        '<label class="field-inline">Suffix<input type="text" data-field="suffix" value="' +
          escapeHtml(row.suffix || "") + '"/></label>' +
        "<div>" +
          '<label class="checkbox-inline"><input type="checkbox" data-field="suppress-author"' +
            (row["suppress-author"] ? " checked" : "") + "/> Suppress author</label>" +
          '<label class="checkbox-inline"><input type="checkbox" data-field="author-only"' +
            (row["author-only"] ? " checked" : "") + "/> Author only</label>" +
        "</div>" +
      "</div>"
    );
  }

  function renderAssembly() {
    var section = $("assemblySection");
    if (!assembly.length) {
      section.style.display = "none";
      $("assembly").innerHTML = "";
      return;
    }
    section.style.display = "block";
    $("assembly").innerHTML = assembly.map(function (row, i) {
      var optionsOpen = i === openOptionsIdx;
      return (
        '<li class="assembly-row" data-idx="' + i + '">' +
          '<div class="assembly-row-main">' +
            '<span class="assembly-row-label">' + escapeHtml(assemblyRowLabel(row)) + "</span>" +
            '<div class="assembly-row-btns">' +
              '<button type="button" class="icon-btn" data-act="up" title="Move up" aria-label="Move up">↑</button>' +
              '<button type="button" class="icon-btn" data-act="down" title="Move down" aria-label="Move down">↓</button>' +
              '<button type="button" class="icon-btn" data-act="opts" aria-pressed="' + optionsOpen +
                '" title="Locator, prefix, suffix…" aria-label="Locator, prefix, suffix options">⋯</button>' +
              '<button type="button" class="icon-btn" data-act="remove" title="Remove" aria-label="Remove from citation">✕</button>' +
            "</div>" +
          "</div>" +
          (optionsOpen ? renderOptionsPanel(row) : "") +
        "</li>"
      );
    }).join("");
    $("insertCitation").textContent = editingCC ? "Update citation" : "Insert citation";
  }

  function onAssemblyClick(ev) {
    var btn = ev.target.closest("button.icon-btn[data-act]");
    if (!btn) return;
    var idx = Number(btn.closest(".assembly-row").getAttribute("data-idx"));
    var act = btn.getAttribute("data-act");
    if (act === "remove") {
      assembly.splice(idx, 1);
      if (openOptionsIdx === idx) openOptionsIdx = -1;
      else if (openOptionsIdx > idx) openOptionsIdx -= 1;
    } else if (act === "up" && idx > 0) {
      var a = assembly[idx - 1]; assembly[idx - 1] = assembly[idx]; assembly[idx] = a;
      if (openOptionsIdx === idx) openOptionsIdx = idx - 1;
      else if (openOptionsIdx === idx - 1) openOptionsIdx = idx;
    } else if (act === "down" && idx < assembly.length - 1) {
      var b = assembly[idx + 1]; assembly[idx + 1] = assembly[idx]; assembly[idx] = b;
      if (openOptionsIdx === idx) openOptionsIdx = idx + 1;
      else if (openOptionsIdx === idx + 1) openOptionsIdx = idx;
    } else if (act === "opts") {
      openOptionsIdx = openOptionsIdx === idx ? -1 : idx;
    }
    renderAssembly();
  }

  // Field edits inside an open Options panel. Locator/prefix/suffix/label just patch the row's label text in
  // place (no full re-render) so typing doesn't lose focus; the mutually-exclusive checkboxes need a full
  // re-render since the OTHER checkbox's checked state may also have changed.
  function onAssemblyChange(ev) {
    var field = ev.target.getAttribute("data-field");
    var li = ev.target.closest(".assembly-row");
    if (!field || !li) return;
    var row = assembly[Number(li.getAttribute("data-idx"))];
    if (!row) return;
    if (ev.target.type === "checkbox") {
      row[field] = ev.target.checked;
      if (field === "suppress-author" && ev.target.checked) row["author-only"] = false;
      if (field === "author-only" && ev.target.checked) row["suppress-author"] = false;
      renderAssembly();
      return;
    }
    row[field] = ev.target.value;
    var labelEl = li.querySelector(".assembly-row-label");
    if (labelEl) labelEl.textContent = assemblyRowLabel(row);
    $("insertCitation").textContent = editingCC ? "Update citation" : "Insert citation";
  }

  function resetAssembly() {
    if (editingCC) { try { editingCC.untrack(); } catch (e) { /* already released */ } }
    editingCC = null;
    assembly = [];
    openOptionsIdx = -1;
    renderAssembly();
  }

  // Insert the assembly as a NEW citation at the end of the selection (so Suggest inserts after the sentence,
  // never replacing it), or — when editing an existing one — just retag it; refreshDocument() re-renders every
  // citation's text from its tag regardless, so an update needs no direct text manipulation of its own.
  async function insertOrUpdateCitation() {
    if (!assembly.length) { setStatus("Add at least one work first.", true); return; }
    var wasEditing = !!editingCC;
    setStatus(wasEditing ? "Updating…" : "Inserting…");
    try {
      var items = CallosumCore.buildClusterItems(assembly);
      if (wasEditing) {
        var cc = editingCC;
        await Word.run(cc, async function (ctx) {
          cc.load("tag");
          await ctx.sync();
          await writeCitationItems(ctx, cc, items);
        });
      } else {
        await Word.run(async function (ctx) {
          var selection = ctx.document.getSelection();
          var parentBody = selection.parentBody;
          parentBody.load("type");
          var existingRecords = await loadDocumentControlRecords(ctx);
          assertPlacementCompatible(existingRecords);
          await ctx.sync();

          var location = CallosumCore.bodyTypeLocation(parentBody.type);
          var noteStyle = CallosumCore.isNoteStyle(currentCitationFormat());
          if (!location) throw new Error("place the cursor in the main document, a footnote, or an endnote");
          if (!noteStyle && location !== "inline") {
            throw new Error("this in-text citation style inserts citations in the main document, not inside a note");
          }
          if (noteStyle) {
            requireNotesSupport();
            var expectedLocation = currentNotePreference();
            if (location !== "inline" && location !== expectedLocation) {
              throw new Error("new note citations are set to " + expectedLocation + "s; move the cursor there or change the setting");
            }
          }

          var part = await createCitationPart(ctx, items);
          var insertionRange;
          if (noteStyle && location === "inline") {
            var referenceRange = selection.getRange(Word.RangeLocation.end);
            var note = currentNotePreference() === "endnote"
              ? referenceRange.insertEndnote()
              : referenceRange.insertFootnote();
            insertionRange = note.body.getRange(Word.RangeLocation.start);
          } else {
            insertionRange = selection.getRange(Word.RangeLocation.end);
          }
          var inserted = insertionRange.insertText("…", Word.InsertLocation.replace);
          var newCc = inserted.insertContentControl();
          configureCitationControl(newCc, part.id);
          await ctx.sync();
        });
      }
      resetAssembly();
      await refreshDocument(); // render the citation(s) + renumber the rest + rebuild the bibliography
    } catch (e) {
      setStatus("Couldn't " + (wasEditing ? "update" : "insert") + ": " + ((e && e.message) || e), true);
    }
  }

  // Populate the composer from the Callosum citation the cursor is currently inside, in Update mode.
  async function editCitationAtCursor() {
    setStatus("Looking for a citation at the cursor…");
    try {
      var outcome = "none"; // "none" | "malformed" | "found"
      await Word.run(async function (ctx) {
        var cc = ctx.document.getSelection().getRange().parentContentControlOrNullObject;
        cc.load("tag,id,text,isNullObject");
        await ctx.sync();
        if (cc.isNullObject || !CallosumCore.isCitationTag(cc.tag)) return;
        var records = await resolveControlRecords(ctx, [cc]);
        var items = CallosumCore.citationItems(records[0]);
        if (!items) { outcome = "malformed"; return; }
        if (editingCC) { try { editingCC.untrack(); } catch (e) { /* already released */ } }
        cc.track();
        await ctx.sync();
        editingCC = cc;
        assembly = items.map(CallosumCore.assemblyRowFromDecodedItem);
        openOptionsIdx = -1;
        outcome = "found";
      });
      if (outcome === "found") {
        renderAssembly();
        setStatus("Editing the citation at the cursor — add/remove works or set a locator, then Update.");
      } else if (outcome === "malformed") {
        setStatus("This citation looks malformed and can't be edited.", true);
      } else {
        setStatus("Place the cursor inside a Callosum citation first.", true);
      }
    } catch (e) {
      setStatus("Couldn't find a citation: " + ((e && e.message) || e), true);
    }
  }

  // Fully remove the Callosum citation the cursor is currently inside (unlike Flatten's delete(true), which
  // keeps the rendered text — this drops it entirely).
  async function deleteCitationAtCursor() {
    setStatus("Looking for a citation at the cursor…");
    try {
      var found = false;
      await Word.run(async function (ctx) {
        var cc = ctx.document.getSelection().getRange().parentContentControlOrNullObject;
        cc.load("tag,isNullObject");
        await ctx.sync();
        if (cc.isNullObject || !CallosumCore.isCitationTag(cc.tag)) return;
        var allRecords = await loadDocumentControlRecords(ctx);
        var partId = CallosumCore.citationReferenceId(cc.tag);
        if (partId) {
          var references = allRecords.filter(function (other) {
            return CallosumCore.citationReferenceId(other.tag) === partId;
          }).length;
          if (references === 1) {
            requireCustomXmlSupport();
            var part = ctx.document.customXmlParts.getItemOrNullObject(partId);
            part.load("id");
            await ctx.sync();
            if (!part.isNullObject) part.delete();
          }
        }
        var currentRecord = allRecords.find(function (record) { return record.cc.id === cc.id; });
        var noteContainsOnlyCitation = currentRecord && currentRecord.note && currentRecord.noteControlCount === 1 &&
          String(currentRecord.noteText || "").trim() === String(cc.text || "").trim();
        if (noteContainsOnlyCitation) currentRecord.note.delete();
        else cc.delete(false);
        await ctx.sync();
        found = true;
      });
      if (!found) { setStatus("Place the cursor inside a Callosum citation first.", true); return; }
      await refreshDocument();
      setStatus("Citation deleted.");
    } catch (e) {
      setStatus("Couldn't delete: " + ((e && e.message) || e), true);
    }
  }

  // Shared by Document diagnostics (inc 512-513) and the Citations panel (inc 516): given a list of resolved
  // paper ids, determine which are still real library papers and their retraction status, in one orchestration
  // both features reuse identically -- factored out so the inc-513 trash-aware existence fix can't drift
  // between two copies. Caps at MAX_EXISTENCE_CHECK_IDS, matching /methods/retraction/check-selected's own cap.
  var MAX_EXISTENCE_CHECK_IDS = 100; // matches methods_retraction.py's own MAX_CHECK_SELECTED request cap
  async function checkPaperExistence(ids) {
    var truncated = ids.length > MAX_EXISTENCE_CHECK_IDS;
    var checkedIds = truncated ? ids.slice(0, MAX_EXISTENCE_CHECK_IDS) : ids;

    // Existence (and orphan) detection: /methods/retraction/check-selected's own "not found" only means the
    // paper ROW is gone -- its internal get_paper() lookup has no deleted_at filter, so a TRASHED paper still
    // resolves as "found." /papers/export DOES exclude trash (get_papers_for_export filters deleted_at IS
    // NULL), but its response .id can't be trusted to correlate back to which requested id it answers (the
    // same stored-id problem inc 512 already fixed for citation tags) -- so check ONE id at a time and key off
    // presence/count, never off the returned record's own id value.
    var missingIds = [];
    await Promise.all(checkedIds.map(async function (id) {
      var r = await callosumFetch("/papers/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [Number(id)], format: "csl-json" }),
      });
      var exists = false;
      if (r.ok) { var rows = await r.json(); exists = Array.isArray(rows) && rows.length > 0; }
      if (!exists) missingIds.push(Number(id));
    }));
    var existingIds = checkedIds.filter(function (id) { return missingIds.indexOf(Number(id)) === -1; });

    var checked = [];
    if (existingIds.length) {
      var r2 = await callosumFetch("/methods/retraction/check-selected", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: existingIds.map(Number) }),
      });
      if (!r2.ok) throw new Error("retraction check failed (" + r2.status + ")");
      var data = await r2.json();
      checked = (data && data.checked) || [];
    }
    return { missingIds: missingIds, checked: checked, truncated: truncated };
  }

  // Document diagnostics (inc 512): a read-only scan -- malformed/unresolvable citations, orphaned or
  // retracted cited works, and bibliography health. Mirrors composer.py's diagnose_document narrowed to what
  // Word's tag model can actually check (see taskpane_core.js's summarizeDiagnostics comment).
  function renderDiagnosticsReport(report, truncated) {
    var lines = [];
    lines.push(report.citationCount + " citation(s) found.");
    if (report.malformedCount) lines.push("⚠ " + report.malformedCount + " malformed (can't be read).");
    if (report.unresolvableItemCount) {
      lines.push("⚠ " + report.unresolvableItemCount + " item(s) with no identifiable library paper (likely inserted before this check existed).");
    }
    if (report.orphanedPaperIds.length) {
      lines.push("⚠ " + report.orphanedPaperIds.length + " cited paper(s) no longer in your library.");
    }
    if (report.retractionFlagged.length) {
      lines.push("⚠ " + report.retractionFlagged.length + " cited paper(s) flagged (retraction/correction) — see Methods for detail.");
    }
    if (report.placementIssue) lines.push("⚠ " + report.placementIssue);
    lines.push("Bibliography: " + report.bibliography + ".");
    lines.push("Section bibliographies: " + report.sectionBibliographyCount + ".");
    if (report.damagedSectionBibliographyCount) {
      lines.push("⚠ " + report.damagedSectionBibliographyCount + " damaged section bibliography block(s).");
    }
    if (truncated) lines.push("(Only the first " + MAX_EXISTENCE_CHECK_IDS + " distinct cited papers were checked against the library.)");
    $("diagnostics").textContent = lines.join(" ");
  }
  async function runDiagnostics() {
    setStatus("Scanning the document…");
    $("diagnostics").textContent = "";
    try {
      var records = [];
      await Word.run(async function (ctx) {
        records = await loadDocumentControlRecords(ctx);
      });

      var idSet = {};
      records.forEach(function (record) {
        if (!CallosumCore.isCitationTag(record.tag)) return;
        var items = CallosumCore.citationItems(record);
        if (!items) return;
        items.forEach(function (item) {
          var pid = CallosumCore.extractPaperId(item && item.id);
          if (pid != null) idSet[pid] = true;
        });
      });
      var existence = await checkPaperExistence(Object.keys(idSet));
      var report = CallosumCore.summarizeDiagnostics(records, existence.missingIds, existence.checked);
      report.placementIssue = CallosumCore.placementIssue(
        citationRecords(records), currentCitationFormat(), currentNotePreference(),
      );
      renderDiagnosticsReport(
        report,
        existence.truncated,
      );
      setStatus("Diagnostics complete.");
    } catch (e) {
      setStatus("Couldn't run diagnostics: " + ((e && e.message) || e), true);
    }
  }

  // Citation coverage (inc 528): one local, read-only structural scan. WordApi 1.6's session-local paragraph
  // identity lets us correlate inline controls and WordApi 1.5 note references without quadratic range
  // comparisons. Managed bibliography paragraphs and tables are excluded; no text leaves Word and no model or
  // backend endpoint is called. The pure helper owns the neutral 15-word / 3-paragraph rule.
  async function loadCitationCoverageRows(ctx, records) {
    requireParagraphIdentitySupport();
    var paragraphs = ctx.document.body.paragraphs;
    paragraphs.load("items/uniqueLocalId,items/text,items/outlineLevel,items/tableNestingLevel");
    var anchors = [], exclusions = [];
    (records || []).forEach(function (record) {
      var collection = null;
      if (CallosumCore.isCitationTag(record.tag)) {
        collection = record.location === "inline"
          ? record.cc.paragraphs
          : record.note && record.note.reference.paragraphs;
        if (collection) anchors.push(collection);
      } else if (record.tag === CallosumCore.BIB_TAG ||
        String(record.tag || "").indexOf(CallosumCore.SECTION_BIB_BLOCK_PREFIX) === 0) {
        collection = record.cc.paragraphs;
        exclusions.push(collection);
      }
      if (collection) collection.load("items/uniqueLocalId");
    });
    await ctx.sync();

    var citedIds = {}, excludedIds = {};
    anchors.forEach(function (collection) {
      collection.items.forEach(function (paragraph) { citedIds[paragraph.uniqueLocalId] = true; });
    });
    exclusions.forEach(function (collection) {
      collection.items.forEach(function (paragraph) { excludedIds[paragraph.uniqueLocalId] = true; });
    });
    return paragraphs.items.map(function (paragraph, index) {
      return {
        paragraphNumber: index + 1,
        text: paragraph.text,
        outlineLevel: paragraph.outlineLevel,
        tableNestingLevel: paragraph.tableNestingLevel,
        hasCitation: !!citedIds[paragraph.uniqueLocalId],
        excluded: !!excludedIds[paragraph.uniqueLocalId],
      };
    });
  }

  function renderCitationCoverageReport(report) {
    var lines = [
      "Scanned " + report.paragraphCount + " main-document paragraph(s); " +
        report.substantiveParagraphCount + " counted as substantive prose.",
    ];
    if (!report.stretchCount) {
      lines.push("No stretch of " + CallosumCore.UNCITED_STRETCH_MIN_PARAGRAPHS +
        "+ consecutive substantive paragraphs without a Callosum citation anchor was found.");
    } else {
      lines.push("Review " + report.stretchCount + " structural citation-free stretch(es):");
      report.stretches.forEach(function (stretch) {
        lines.push("Paragraphs " + stretch.startParagraph + "–" + stretch.endParagraph + " (" +
          stretch.paragraphCount + "): “" + stretch.preview + "”");
      });
      if (report.stretchesTruncated) {
        lines.push("Only the first " + CallosumCore.MAX_COVERAGE_STRETCHES + " stretches are shown.");
      }
    }
    lines.push("This is a structural review prompt, not a finding that a citation is required or that prose is unsupported.");
    $("diagnostics").textContent = lines.join("\n");
  }

  async function runCitationCoverageAudit() {
    setStatus("Scanning citation coverage…");
    $("diagnostics").textContent = "";
    try {
      var rows = [];
      await Word.run(async function (ctx) {
        var records = await loadDocumentControlRecords(ctx);
        rows = await loadCitationCoverageRows(ctx, records);
      });
      renderCitationCoverageReport(CallosumCore.summarizeCitationCoverage(rows));
      setStatus("Citation coverage audit complete.");
    } catch (e) {
      setStatus("Couldn't audit citation coverage: " + ((e && e.message) || e), true);
    }
  }

  // Citations-in-this-document panel (inc 516): every unique cited work, occurrence count, orphan/retraction
  // badges, click-to-navigate to its first occurrence, and client-side search -- explicit on-demand trigger,
  // matching Document diagnostics' own UX pattern (no auto-refresh, no background work on load).
  var citationsPanelEntries = []; // last-computed entries, re-filtered client-side on every search keystroke
  var categoryEditingPaperIds = [];
  var categoryEditFromBatch = false;
  var categoryEditHasMixedCategories = false;
  var selectedCategoryPaperIds = Object.create(null);
  var categoryEditInFlight = false;
  var categoryOrderDraft = [];
  var categoryOrderAlphabetical = [];
  var categoryOrderInFlight = false;
  function renderCitationsPanelBadges(entry) {
    var badges = [];
    if (entry.category) badges.push('<span class="category-badge">' + escapeHtml(entry.category) + "</span>");
    if (entry.orphaned) badges.push('<span class="badge-warn">not in library</span>');
    if (entry.retraction) badges.push('<span class="badge-warn">' + escapeHtml(entry.retraction.status) + "</span>");
    if (entry.evidence) badges.push('<span class="category-badge">evidence</span>');
    return badges.join(" ");
  }
  function visibleCitationsPanelEntries() {
    var filterText = ($("citationsSearch").value || "").trim().toLowerCase();
    return filterText
      ? citationsPanelEntries.filter(function (e) {
          return (e.row + " " + (e.category || "")).toLowerCase().indexOf(filterText) !== -1;
        })
      : citationsPanelEntries;
  }
  function selectedCategoryIds() { return Object.keys(selectedCategoryPaperIds); }
  function activeBibliographyCategories() {
    var labels = {};
    citationsPanelEntries.forEach(function (entry) {
      if (entry.category) labels[entry.category.toLowerCase()] = entry.category;
    });
    return CallosumCore.orderedBibliographyCategories(Object.keys(labels).map(function (key) { return labels[key]; }), []);
  }
  function renderBatchControls(visible) {
    var selectable = (visible || []).filter(function (entry) { return entry.paperId != null; });
    var selectedCount = selectedCategoryIds().length;
    $("citationsBatchBar").style.display = citationsPanelEntries.length ? "flex" : "none";
    $("citationsBatchCount").textContent = selectedCount + " selected";
    var busy = categoryEditInFlight || categoryOrderInFlight;
    $("citationsBatchCategory").disabled = selectedCount === 0 || busy;
    $("citationsClearSelection").disabled = selectedCount === 0 || busy;
    $("citationsSelectVisible").disabled = selectable.length === 0 || busy;
    $("bibliographyCategoryOrderOpen").disabled = activeBibliographyCategories().length < 2 || busy;
  }
  function renderCitationsPanelList() {
    var visible = visibleCitationsPanelEntries();
    $("citationsPanel").innerHTML = visible.length
      ? visible.map(function (e) {
          var selection = e.paperId == null ? '<span></span>' :
            '<input class="citation-select" type="checkbox" data-batch-paper-id="' + e.paperId +
              '" aria-label="Select ' + escapeHtml(e.row) + ' for batch category assignment"' +
              (selectedCategoryPaperIds[String(e.paperId)] ? " checked" : "") + "/>";
          var categoryAction = e.paperId == null ? "" :
            '<button class="secondary category-action" data-category-paper-id="' + e.paperId +
              '" aria-label="Set bibliography category for ' + escapeHtml(e.row) + '">' +
              (e.category ? "Change category…" : "Set category…") + "</button>";
          var evidenceAction = e.evidence ? '<button class="secondary category-action" data-evidence-position="' +
            e.positions[0] + '" aria-label="View recorded suggestion evidence for ' + escapeHtml(e.row) +
            '">View evidence…</button>' : "";
          var actions = categoryAction || evidenceAction
            ? '<div class="citation-panel-actions">' + categoryAction + evidenceAction + "</div>"
            : "";
          return '<li class="citation-panel-item">' + selection +
            '<button class="row" data-position="' + e.positions[0] + '">' +
            escapeHtml(e.row) + " · " + e.occurrenceCount + "×  " + renderCitationsPanelBadges(e) +
            "</button>" + actions + "</li>";
        }).join("")
      : '<li class="empty">' + escapeHtml(citationsPanelEntries.length ? "No matches." : "No citations in this document yet.") + "</li>";
    renderBatchControls(visible);
  }
  function closeCategoryEditor() {
    categoryEditingPaperIds = [];
    categoryEditFromBatch = false;
    categoryEditHasMixedCategories = false;
    $("bibliographyCategoryEditor").style.display = "none";
    $("bibliographyCategory").value = "";
  }
  function closeCategoryOrderEditor() {
    categoryOrderDraft = [];
    categoryOrderAlphabetical = [];
    $("bibliographyCategoryOrderEditor").style.display = "none";
  }
  function renderCategoryOrderEditor() {
    $("bibliographyCategoryOrderList").innerHTML = categoryOrderDraft.map(function (label, index) {
      return '<li class="category-order-item"><span class="category-order-label">' + escapeHtml(label) +
        '</span><button type="button" class="secondary" data-order-index="' + index + '" data-order-delta="-1"' +
        (index === 0 || categoryOrderInFlight ? " disabled" : "") + ' aria-label="Move ' + escapeHtml(label) +
        ' up">↑</button><button type="button" class="secondary" data-order-index="' + index +
        '" data-order-delta="1"' + (index === categoryOrderDraft.length - 1 || categoryOrderInFlight ? " disabled" : "") +
        ' aria-label="Move ' + escapeHtml(label) + ' down">↓</button></li>';
    }).join("");
    $("bibliographyCategoryOrderReset").disabled = categoryOrderInFlight;
    $("bibliographyCategoryOrderSave").disabled = categoryOrderInFlight;
    $("bibliographyCategoryOrderCancel").disabled = categoryOrderInFlight;
  }
  function openCategoryOrderEditor() {
    if (categoryEditInFlight || categoryOrderInFlight) return;
    var alphabetical = activeBibliographyCategories();
    if (alphabetical.length < 2) {
      setStatus("Create at least two bibliography categories before setting a custom order.", true);
      return;
    }
    closeCategoryEditor();
    categoryOrderAlphabetical = alphabetical;
    categoryOrderDraft = CallosumCore.orderedBibliographyCategories(alphabetical, currentBibliographyCategoryOrder());
    $("bibliographyCategoryOrderEditor").style.display = "block";
    renderCategoryOrderEditor();
  }
  function moveCategoryOrder(index, delta) {
    if (categoryOrderInFlight || index < 0 || index >= categoryOrderDraft.length) return;
    var destination = index + delta;
    if (destination < 0 || destination >= categoryOrderDraft.length) return;
    var moved = categoryOrderDraft[index];
    categoryOrderDraft[index] = categoryOrderDraft[destination];
    categoryOrderDraft[destination] = moved;
    renderCategoryOrderEditor();
  }
  async function saveCategoryOrder() {
    if (categoryOrderInFlight || categoryOrderDraft.length < 2) return;
    categoryOrderInFlight = true;
    renderCategoryOrderEditor();
    renderBatchControls(visibleCitationsPanelEntries());
    var previousRaw = Office.context.document.settings.get(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING);
    var alphabetical = categoryOrderDraft.every(function (label, index) {
      return label === categoryOrderAlphabetical[index];
    });
    var savedOrder = alphabetical ? [] : categoryOrderDraft.slice();
    try {
      setStatus(alphabetical ? "Restoring alphabetical category order…" : "Saving category order…");
      await persistBibliographyCategoryOrder(savedOrder);
      await refreshDocument({ throwOnError: true });
      closeCategoryOrderEditor();
      setStatus(alphabetical ? "Alphabetical category order restored." : "Bibliography category order saved.");
    } catch (e) {
      try { await restoreBibliographyCategoryOrder(previousRaw); } catch (rollbackError) {
        setStatus("Couldn't update the category order or restore its setting: " +
          ((rollbackError && rollbackError.message) || rollbackError), true);
        return;
      }
      setStatus("Couldn't update the bibliography category order: " + ((e && e.message) || e), true);
    } finally {
      categoryOrderInFlight = false;
      if (categoryOrderDraft.length) renderCategoryOrderEditor();
      renderBatchControls(visibleCitationsPanelEntries());
    }
  }
  function updateCategorySaveState() {
    var missingMixedChoice = categoryEditHasMixedCategories && !$("bibliographyCategory").value.trim();
    $("bibliographyCategorySave").disabled = categoryEditInFlight || missingMixedChoice;
  }
  function openCategoryEditor(paperIds, fromBatch) {
    if (categoryEditInFlight || categoryOrderInFlight) return;
    closeCategoryOrderEditor();
    var requested = Array.isArray(paperIds) ? paperIds : [paperIds];
    var ids = [], selected = [];
    requested.forEach(function (paperId) {
      var entry = citationsPanelEntries.find(function (candidate) {
        return String(candidate.paperId) === String(paperId);
      });
      if (entry && entry.paperId != null && ids.indexOf(String(entry.paperId)) === -1) {
        ids.push(String(entry.paperId)); selected.push(entry);
      }
    });
    if (!selected.length) {
      setStatus("This legacy citation has no reliable Callosum paper id, so it cannot be categorized.", true);
      return;
    }
    categoryEditingPaperIds = ids;
    categoryEditFromBatch = Boolean(fromBatch);
    $("bibliographyCategoryTarget").textContent = selected.length === 1 ? selected[0].row :
      selected.length + " selected works";
    var firstCategory = selected[0].category || "";
    categoryEditHasMixedCategories = !selected.every(function (entry) {
      return (entry.category || "") === firstCategory;
    });
    $("bibliographyCategory").value = categoryEditHasMixedCategories ? "" : firstCategory;
    $("bibliographyCategory").placeholder = categoryEditHasMixedCategories ? "Choose a category" : "";
    var labels = {}, assignments = currentBibliographyCategories();
    Object.keys(assignments).forEach(function (id) { labels[assignments[id]] = true; });
    $("bibliographyCategoryOptions").innerHTML = Object.keys(labels).sort().map(function (label) {
      return '<option value="' + escapeHtml(label) + '"></option>';
    }).join("");
    $("bibliographyCategoryEditor").style.display = "block";
    updateCategorySaveState();
    $("bibliographyCategory").focus();
  }
  async function applyCategoryEdit(value, explicitRemove) {
    if (!categoryEditingPaperIds.length || categoryEditInFlight || categoryOrderInFlight) return;
    if (categoryEditHasMixedCategories && !String(value || "").trim() && !explicitRemove) {
      setStatus("Choose a category for the mixed selection, or use Remove category.", true);
      return;
    }
    categoryEditInFlight = true;
    $("bibliographyCategorySave").disabled = true;
    $("bibliographyCategoryRemove").disabled = true;
    renderBatchControls(visibleCitationsPanelEntries());
    var paperIds = categoryEditingPaperIds.slice();
    var wasBatch = categoryEditFromBatch;
    var previous = currentBibliographyCategories();
    var updated;
    try {
      updated = CallosumCore.updateBibliographyCategories(previous, paperIds, value);
      setStatus("Updating " + paperIds.length + " bibliography categor" + (paperIds.length === 1 ? "y" : "ies") + "…");
      await persistBibliographyCategories(updated);
      await refreshDocument({ throwOnError: true });
      citationsPanelEntries = CallosumCore.applyBibliographyCategories(citationsPanelEntries, updated);
      if (wasBatch) selectedCategoryPaperIds = Object.create(null);
      renderCitationsPanelList();
      closeCategoryEditor();
      setStatus(updated[paperIds[0]] ?
        "Bibliography category saved for " + paperIds.length + " work(s)." :
        "Bibliography category removed from " + paperIds.length + " work(s).");
    } catch (e) {
      try { await persistBibliographyCategories(previous); } catch (rollbackError) {
        setStatus("Couldn't update the category or restore its setting: " +
          ((rollbackError && rollbackError.message) || rollbackError), true);
        return;
      }
      setStatus("Couldn't update the bibliography category: " + ((e && e.message) || e), true);
    } finally {
      categoryEditInFlight = false;
      $("bibliographyCategoryRemove").disabled = false;
      updateCategorySaveState();
      renderBatchControls(visibleCitationsPanelEntries());
    }
  }
  async function runCitationsPanel() {
    if (categoryEditInFlight || categoryOrderInFlight) return;
    setStatus("Scanning the document…");
    closeCategoryEditor();
    closeCategoryOrderEditor();
    selectedCategoryPaperIds = Object.create(null);
    citationsPanelEntries = [];
    $("citationsPanel").innerHTML = "";
    $("citationEvidence").textContent = "";
    $("citationsBatchBar").style.display = "none";
    $("citationsSearch").style.display = "block"; // revealed on first use, like the tunnel token section
    try {
      var records = [];
      await Word.run(async function (ctx) {
        records = await loadDocumentControlRecords(ctx);
      });
      var entries = CallosumCore.buildCitationsPanelEntries(records);
      var ids = entries.map(function (e) { return e.paperId; }).filter(function (id) { return id != null; });
      var existence = await checkPaperExistence(ids);
      citationsPanelEntries = CallosumCore.applyBibliographyCategories(
        CallosumCore.mergePanelEntryStatus(entries, existence.missingIds, existence.checked),
        currentBibliographyCategories(),
      );
      renderCitationsPanelList();
      setStatus(
        entries.length + " unique work(s) cited" + (existence.truncated ? " (only the first " + MAX_EXISTENCE_CHECK_IDS + " checked against the library)" : "") + ".",
      );
    } catch (e) {
      setStatus("Couldn't build the citations panel: " + ((e && e.message) || e), true);
    }
  }
  function onCitationsPanelClick(ev) {
    var selection = ev.target.closest("input[data-batch-paper-id]");
    if (selection) {
      if (categoryEditInFlight || categoryOrderInFlight) return;
      var selectionId = selection.getAttribute("data-batch-paper-id");
      if (selection.checked && selectedCategoryIds().length >= CallosumCore.MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS) {
        selection.checked = false;
        setStatus("A batch can contain at most " + CallosumCore.MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS + " works.", true);
        return;
      }
      if (selection.checked) selectedCategoryPaperIds[selectionId] = true;
      else delete selectedCategoryPaperIds[selectionId];
      if (categoryEditFromBatch) closeCategoryEditor();
      renderBatchControls(visibleCitationsPanelEntries());
      return;
    }
    var categoryBtn = ev.target.closest("button[data-category-paper-id]");
    if (categoryBtn) { openCategoryEditor(categoryBtn.getAttribute("data-category-paper-id"), false); return; }
    var evidenceBtn = ev.target.closest("button[data-evidence-position]");
    if (evidenceBtn) {
      var evidencePosition = Number(evidenceBtn.getAttribute("data-evidence-position"));
      var evidenceEntry = citationsPanelEntries.find(function (entry) {
        return entry.positions[0] === evidencePosition;
      });
      $("citationEvidence").textContent = evidenceEntry && evidenceEntry.evidence
        ? "Evidence recorded when suggested" + (evidenceEntry.evidence.page ? " · page " + evidenceEntry.evidence.page : "") +
          ": “" + evidenceEntry.evidence.snippet + "”"
        : "No recorded suggestion evidence is available for this citation.";
      return;
    }
    var btn = ev.target.closest("button.row[data-position]");
    if (btn) navigateToCitation(Number(btn.getAttribute("data-position")));
  }
  // Re-scans fresh rather than holding stale Content Control references from when the panel was built --
  // the document may have changed since then (matches the composer's own .track()/.untrack() caution, just
  // solved here by not caching cross-click state at all instead).
  async function navigateToCitation(position) {
    try {
      var found = false;
      await Word.run(async function (ctx) {
        var records = await loadDocumentControlRecords(ctx);
        var citationCCs = citationRecords(records).map(function (record) { return record.cc; });
        if (position < 0 || position >= citationCCs.length) return;
        citationCCs[position].select();
        await ctx.sync();
        found = true;
      });
      if (!found) setStatus("Couldn't locate that citation — the document may have changed. Try again.", true);
    } catch (e) {
      setStatus("Couldn't navigate: " + ((e && e.message) || e), true);
    }
  }

  // Insert exact plain bibliography text first, then add only backend-approved web links whose generated entry
  // paragraph and anchor resolve unambiguously in Word. Range.hyperlink is production WordApi 1.3; paragraph-
  // local search avoids picking the wrong repeated DOI/title elsewhere in a full or section bibliography.
  function queueBibliographyWrite(cc, plan, linksEnabled) {
    cc.insertText(plan.text, Word.InsertLocation.replace);
    if (!linksEnabled || !plan.entries.some(function (entry) { return entry.links.length > 0; })) return null;
    var paragraphs = cc.paragraphs;
    paragraphs.load("items/text");
    return { plan: plan, paragraphs: paragraphs };
  }
  function plainWordParagraphText(value) {
    return String(value == null ? "" : value).replace(/\r$/, "");
  }
  async function applyQueuedBibliographyWrites(ctx, writes) {
    await ctx.sync(); // materialize every plain-text write before resolving paragraph-local anchors
    var searches = [];
    (writes || []).filter(Boolean).forEach(function (write) {
      write.plan.entries.forEach(function (entry) {
        var paragraph = write.paragraphs.items[entry.paragraphIndex];
        if (!paragraph || plainWordParagraphText(paragraph.text) !== entry.text) return;
        entry.links.forEach(function (link) {
          var ranges = paragraph.search(link.text, {
            matchCase: true, matchWholeWord: false, matchWildcards: false,
          });
          ranges.load("items/text");
          searches.push({ ranges: ranges, text: link.text, url: link.url });
        });
      });
    });
    if (!searches.length) return;
    await ctx.sync();
    var applied = false;
    searches.forEach(function (search) {
      // Zero or multiple matches stay plain. This is stricter than guessing from offsets Word cannot slice.
      if (search.ranges.items.length !== 1 || search.ranges.items[0].text !== search.text) return;
      search.ranges.items[0].hyperlink = search.url;
      applied = true;
    });
    if (applied) await ctx.sync();
  }

  // Re-render every Callosum citation in document order + rebuild the bibliography (the Zotero-style loop).
  async function refreshDocument(options) {
    setStatus("Refreshing…");
    try {
      var bibliographyCategories = currentBibliographyCategories();
      var bibliographyCategoryOrder = currentBibliographyCategoryOrder();
      var bibliographyExternalLinks = currentBibliographyExternalLinks();
      await Word.run(async function (ctx) {
        var body = ctx.document.body;
        var citationCCs = [], itemsList = [], bibCC = null;
        var records = await loadDocumentControlRecords(ctx);
        assertPlacementCompatible(records);
        var sectionInventory = requireHealthySectionBibliographies(records);
        if (sectionInventory.complete.length && CallosumCore.isNoteStyle(currentCitationFormat())) {
          throw new Error("Heading-scoped bibliographies currently require an in-text citation style; " +
            "native note-to-heading membership is not yet supported.");
        }
        var sectionContext = sectionInventory.complete.length
          ? await loadSectionParagraphContext(ctx, records, null)
          : null;
        await normalizeCitationStorage(ctx, records);
        records.forEach(function (record) {
          if (CallosumCore.isCitationTag(record.tag)) {
            var items = CallosumCore.citationItems(record);
            if (items) {
              citationCCs.push(record.cc);
              itemsList.push({ items: items, noteIndex: CallosumCore.isNoteStyle(currentCitationFormat()) ? record.noteIndex : 0 });
            }
          } else if (record.tag === CallosumCore.BIB_TAG) {
            bibCC = record.cc;
          }
        });
        if (itemsList.length === 0) { setStatus("No Callosum citations in this document yet."); return; }

        var resp = await callosumFetch("/citations/render-document", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(CallosumCore.buildDocumentRequest(itemsList, currentStyle(), "en-US")),
        });
        if (!resp.ok) throw new Error("render failed (" + resp.status + ")");
        var data = await resp.json();

        var texts = CallosumCore.inTextResults(data);
        citationCCs.forEach(function (cc, i) {
          if (i < texts.length) cc.insertText(texts[i], Word.InsertLocation.replace);
        });

        if (!bibCC) {
          body.insertParagraph("References", Word.InsertLocation.end);
          var bibPara = body.insertParagraph("", Word.InsertLocation.end);
          bibCC = bibPara.getRange().insertContentControl();
          bibCC.tag = CallosumCore.BIB_TAG;
          bibCC.title = "Callosum bibliography";
        }
        var bibliographyWrites = [queueBibliographyWrite(
          bibCC,
          CallosumCore.bibliographyRenderPlan(data, bibliographyCategories, bibliographyCategoryOrder),
          bibliographyExternalLinks,
        )];

        var sectionCitations = citationRecords(records).filter(function (record) {
          return record.location === "inline" && record.items && record.sectionParagraphId;
        }).map(function (record) {
          return { paragraphId: record.sectionParagraphId, items: CallosumCore.citationItems(record) || [] };
        });
        sectionInventory.complete.forEach(function (section) {
          if (section.scope.location !== "inline" || section.block.location !== "inline") {
            throw new Error("Section bibliography controls must remain in the main document.");
          }
          var allowedIds = CallosumCore.sectionCitationItemIds(
            sectionContext.paragraphs, section.scope.sectionParagraphId, sectionCitations,
          );
          bibliographyWrites.push(queueBibliographyWrite(
            section.block.cc,
            CallosumCore.sectionBibliographyPlan(
              data, allowedIds, bibliographyCategories, bibliographyCategoryOrder,
            ),
            bibliographyExternalLinks,
          ));
        });

        await applyQueuedBibliographyWrites(ctx, bibliographyWrites);
        setStatus("Updated " + itemsList.length + " citation(s) + the bibliography" +
          (sectionInventory.complete.length ? " + " + sectionInventory.complete.length + " section block(s)." : "."));
      });
      return true;
    } catch (e) {
      setStatus("Couldn't refresh: " + ((e && e.message) || e), true);
      if (options && options.throwOnError) throw e;
      return false;
    }
  }

  async function insertSectionBibliography() {
    setStatus("Inserting the current-section bibliography…");
    var insertedId = null;
    try {
      requireSectionBibliographiesSupport();
      if (CallosumCore.isNoteStyle(currentCitationFormat())) {
        throw new Error("Heading-scoped bibliographies currently require an in-text citation style.");
      }
      await Word.run(async function (ctx) {
        var selection = ctx.document.getSelection();
        var parentBody = selection.parentBody;
        parentBody.load("type");
        var records = await loadDocumentControlRecords(ctx);
        await ctx.sync();
        if (CallosumCore.bodyTypeLocation(parentBody.type) !== "inline") {
          throw new Error("Section bibliographies must be inserted in the main document, not inside a note.");
        }
        assertPlacementCompatible(records);
        var inventory = requireHealthySectionBibliographies(records);
        if (inventory.complete.length >= CallosumCore.MAX_SECTION_BIBLIOGRAPHIES) {
          throw new Error("A Word document can contain at most " +
            CallosumCore.MAX_SECTION_BIBLIOGRAPHIES + " section bibliographies.");
        }
        var context = await loadSectionParagraphContext(ctx, records, selection);
        var bounds = CallosumCore.sectionParagraphBounds(context.paragraphs, context.selectionParagraphId);
        if (!bounds) throw new Error("Callosum could not find a preceding heading for the current section.");
        if (inventory.complete.some(function (section) {
          return section.scope.sectionParagraphId === bounds.headingId;
        })) {
          throw new Error("This heading-defined section already has a Callosum bibliography.");
        }
        var sectionCitations = citationRecords(records).filter(function (record) {
          return record.location === "inline" && record.items && record.sectionParagraphId;
        }).map(function (record) {
          return { paragraphId: record.sectionParagraphId, items: CallosumCore.citationItems(record) || [] };
        });
        var allowedIds = CallosumCore.sectionCitationItemIds(
          context.paragraphs, bounds.headingId, sectionCitations,
        );
        if (!allowedIds.length) {
          throw new Error("No live Callosum citations were found in this heading-defined section.");
        }
        var itemsList = citationRecords(records).filter(function (record) { return record.items; }).map(function (record) {
          return { items: CallosumCore.citationItems(record), noteIndex: 0 };
        });
        var resp = await callosumFetch("/citations/render-document", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(CallosumCore.buildDocumentRequest(itemsList, currentStyle(), "en-US")),
        });
        if (!resp.ok) throw new Error("render failed (" + resp.status + ")");
        var data = await resp.json();
        var plan = CallosumCore.sectionBibliographyPlan(
          data, allowedIds, currentBibliographyCategories(), currentBibliographyCategoryOrder(),
        );

        insertedId = newSectionBibliographyId();
        var heading = ctx.document.body.paragraphs.items[bounds.start];
        var scopeCC = heading.insertContentControl();
        scopeCC.tag = CallosumCore.encodeSectionBibliographyTag("scope", insertedId);
        scopeCC.title = "Callosum section scope";
        scopeCC.appearance = "Hidden";
        var blockParagraph = selection.insertParagraph("", Word.InsertLocation.after);
        blockParagraph.styleBuiltIn = "Normal"; // never let insertion inside a heading create a false outline boundary
        var blockCC = blockParagraph.insertContentControl();
        blockCC.tag = CallosumCore.encodeSectionBibliographyTag("block", insertedId);
        blockCC.title = "Callosum section bibliography";
        var write = queueBibliographyWrite(blockCC, plan, currentBibliographyExternalLinks());
        await applyQueuedBibliographyWrites(ctx, [write]);
      });
      setStatus("Inserted a live bibliography for the current heading-defined section.");
    } catch (e) {
      if (insertedId) {
        try {
          await Word.run(async function (ctx) {
            var records = await loadDocumentControlRecords(ctx);
            records.forEach(function (record) {
              var decoded = CallosumCore.decodeSectionBibliographyTag(record.tag);
              if (decoded && decoded.id === insertedId) record.cc.delete(decoded.kind === "scope");
            });
            await ctx.sync();
          });
        } catch (cleanupError) {
          setStatus("Section bibliography insertion failed and cleanup could not be verified. " +
            "Close without saving and reopen the document.", true);
          return;
        }
      }
      setStatus("Couldn't insert the section bibliography: " + ((e && e.message) || e), true);
    }
  }

  async function removeSectionBibliography() {
    setStatus("Removing the current-section bibliography…");
    try {
      requireSectionBibliographiesSupport();
      var removed = false;
      await Word.run(async function (ctx) {
        var selection = ctx.document.getSelection();
        var parentBody = selection.parentBody;
        parentBody.load("type");
        var records = await loadDocumentControlRecords(ctx);
        await ctx.sync();
        if (CallosumCore.bodyTypeLocation(parentBody.type) !== "inline") {
          throw new Error("Place the cursor in the main document section whose bibliography should be removed.");
        }
        var inventory = requireHealthySectionBibliographies(records);
        var context = await loadSectionParagraphContext(ctx, records, selection);
        var bounds = CallosumCore.sectionParagraphBounds(context.paragraphs, context.selectionParagraphId);
        if (!bounds) throw new Error("Callosum could not find a preceding heading for the current section.");
        var target = inventory.complete.find(function (section) {
          return section.scope.sectionParagraphId === bounds.headingId;
        });
        if (!target) throw new Error("This heading-defined section has no Callosum bibliography.");
        target.block.cc.delete(false);
        target.scope.cc.delete(true);
        await ctx.sync();
        removed = true;
      });
      if (removed) setStatus("Removed the bibliography for the current section; citations were unchanged.");
    } catch (e) {
      setStatus("Couldn't remove the section bibliography: " + ((e && e.message) || e), true);
    }
  }

  // One-click whole-document style switch: persist the choice (per document) + re-render.
  async function onStyleChange() {
    updateNotePlacementVisibility();
    try {
      Office.context.document.settings.set("callosumStyle", currentStyle());
      Office.context.document.settings.saveAsync(function () {});
    } catch (e) { /* settings unavailable → still re-render below */ }
    await refreshDocument();
  }
  function onNotePlacementChange() {
    var preference = currentNotePreference();
    try {
      Office.context.document.settings.set("callosumNotePlacement", preference);
      Office.context.document.settings.saveAsync(function () {});
    } catch (e) { /* insertion still uses the visible choice for this session */ }
    setStatus("New note citations will use " + preference + "s. Existing notes are not converted.");
  }
  async function onBibliographyExternalLinksChange() {
    var checkbox = $("bibliographyExternalLinks");
    var enabled = checkbox.checked;
    var previousRaw = null;
    try {
      previousRaw = Office.context.document.settings.get(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING);
    } catch (e) {
      checkbox.checked = !enabled;
      setStatus("Word could not read this document's bibliography-link setting.", true);
      return;
    }
    checkbox.disabled = true;
    try {
      await persistBibliographyExternalLinks(enabled);
      await refreshDocument({ throwOnError: true });
      setStatus("Bibliography title/DOI links " + (enabled ? "enabled." : "disabled."));
    } catch (e) {
      try { await restoreBibliographyExternalLinks(previousRaw); } catch (restoreError) { /* preserve first error */ }
      checkbox.checked = previousRaw === "1";
      setStatus("Couldn't change bibliography links: " + ((e && e.message) || e), true);
    } finally {
      checkbox.disabled = false;
    }
  }

  // Flatten = convert citation + bibliography Content Controls to plain text (one-way). Two-click confirm — no
  // dialog. Office.js has no saveAs (confirmed by research, not assumed) -- an add-in cannot save a copy on
  // the user's behalf, so the honest move is telling them to do it themselves before confirming, not silently
  // omitting that safety net the way a bare "click again" would.
  var flattenArmed = false;
  async function onFlatten() {
    if (!flattenArmed) {
      var citationCount = 0, hasBib = false;
      await Word.run(async function (ctx) {
        var records = await loadDocumentControlRecords(ctx);
        records.forEach(function (record) {
          if (CallosumCore.isCitationTag(record.tag)) citationCount += 1;
          else if (record.tag === CallosumCore.BIB_TAG || CallosumCore.isSectionBibliographyTag(record.tag)) hasBib = true;
        });
      });
      flattenArmed = true;
      $("flatten").textContent = "Click again to flatten (one-way)";
      setStatus(
        "This will flatten " + citationCount + " citation(s)" + (hasBib ? " + the bibliography" : "") +
          " to plain text. Callosum can't undo this or save a copy for you — consider File → Save As " +
          "first (Word's own Ctrl+Z should still work). Click again to confirm.",
        true,
      );
      setTimeout(function () {
        flattenArmed = false;
        $("flatten").textContent = "Flatten to static text";
      }, 8000);
      return;
    }
    flattenArmed = false;
    $("flatten").textContent = "Flatten to static text";
    doFlatten();
  }
  async function doFlatten() {
    setStatus("Flattening…");
    try {
      var n = 0, remaining = 0;
      await Word.run(async function (ctx) {
        var records = await loadDocumentControlRecords(ctx);
        var deletedPartIds = Object.create(null);
        records.forEach(function (record) {
          if (CallosumCore.isCitationTag(record.tag) || record.tag === CallosumCore.BIB_TAG ||
              CallosumCore.isSectionBibliographyTag(record.tag)) {
            record.cc.delete(true); // keep the rendered text, drop the live field
            n++;
          }
          if (record.part && !deletedPartIds[record.partId]) {
            record.part.delete();
            deletedPartIds[record.partId] = true;
          }
        });
        await ctx.sync();
        // Post-flatten integrity check: re-scan rather than trust the delete calls above all landed.
        var after = await loadDocumentControlRecords(ctx);
        after.forEach(function (record) {
          if (CallosumCore.isCitationTag(record.tag) || record.tag === CallosumCore.BIB_TAG ||
              CallosumCore.isSectionBibliographyTag(record.tag)) remaining += 1;
        });
      });
      if ($("flattenClearStyle").checked) {
        try {
          Office.context.document.settings.remove("callosumStyle");
          Office.context.document.settings.remove("callosumNotePlacement");
          Office.context.document.settings.remove(BIBLIOGRAPHY_CATEGORY_SETTING);
          Office.context.document.settings.remove(BIBLIOGRAPHY_CATEGORY_ORDER_SETTING);
          Office.context.document.settings.remove(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING);
          Office.context.document.settings.saveAsync(function () {});
        } catch (e) { /* settings unavailable -- flatten itself already succeeded, not worth failing over */ }
      }
      setStatus(
        remaining === 0
          ? "Flattened " + n + " field(s) to static text — verified none remain live."
          : "Flattened " + n + " field(s), but " + remaining + " still show as live — Refresh and check manually.",
        remaining !== 0,
      );
    } catch (e) {
      setStatus("Couldn't flatten: " + ((e && e.message) || e), true);
    }
  }

  // Pre-fill the token field from any prior save on THIS origin (localStorage is origin-scoped, so desktop and
  // the tunnel each remember their own saved token independently — pasting it once per surface is expected).
  // Word-on-the-web always shows the section up front (it needs a token far more often); desktop only shows it
  // once a fetch actually 401s (inc 510: Remote Access can be on for the tunnel while desktop is also in use).
  function initTunnelSection() {
    $("tunnelToken").value = authToken();
    if (isTunneled) $("tunnel").style.display = "block";
  }
  function saveToken() {
    var val = $("tunnelToken").value.trim();
    window.localStorage.setItem(TOKEN_KEY, val);
    setStatus(val ? "Access token saved." : "Access token cleared.");
    // loadStyles() already ran once at Office.onReady, before any token existed to save -- on a first-ever
    // visit that first call 401s (silently, since styles are treated as optional polish) and nothing else
    // ever re-triggers it, leaving the dropdown permanently empty even after the token is saved. Re-fetch now
    // that a real token exists so the dropdown actually populates without requiring a reload.
    if (val) loadStyles();
  }

  // inc 527 (P2 #21): author-controlled disclosure prose. The shared endpoint is local/transient staging only;
  // Word inserts the exact bounded draft as plain text, never as a citation Content Control or generated fact.
  function renderStatementKinds() {
    $("statementKind").innerHTML = CallosumCore.STATEMENT_TYPES.map(function (type) {
      return '<option value="' + escapeHtml(type.kind) + '">' + escapeHtml(type.label) + "</option>";
    }).join("");
  }
  function renderStatementPhrases() {
    var type = CallosumCore.statementType($("statementKind").value);
    var phrases = type ? type.phrases : [];
    $("statementPhrase").innerHTML = '<option value="">Choose a starting phrase…</option>' +
      phrases.map(function (phrase, index) {
        return '<option value="' + index + '">' + escapeHtml(phrase.label) + "</option>";
      }).join("");
    $("statementText").value = statementDrafts[$("statementKind").value] || "";
    updateStatementState();
  }
  function updateStatementState() {
    var kind = $("statementKind").value;
    var draft = CallosumCore.normalizeStatementText($("statementText").value);
    var staged = stagedStatements[kind] || "";
    $("statementInsert").disabled = statementInFlight || !draft;
    $("statementStage").disabled = statementInFlight || !draft || draft === staged;
    $("statementClear").disabled = statementInFlight || !staged;
    $("statementCancel").disabled = statementInFlight;
    $("statementStageState").textContent = staged ?
      (draft === staged ? "This exact draft is staged for LibreOffice or another Word session." :
        "A different draft is staged; stage again to share these edits.") :
      "Nothing is staged for this statement type.";
  }
  function setStatementBusy(busy) {
    statementInFlight = busy;
    updateStatementState();
  }
  async function openStatementEditor() {
    $("statementEditor").style.display = "block";
    setStatementBusy(true);
    setStatus("Loading staged open-science statements…");
    try {
      var response = await callosumFetch("/statements/pending");
      if (!response.ok) throw new Error("server returned " + response.status);
      var previousStaged = stagedStatements;
      var fetched = CallosumCore.normalizeStagedStatements(await response.json());
      CallosumCore.STATEMENT_TYPES.forEach(function (type) {
        var kind = type.kind;
        if (!Object.prototype.hasOwnProperty.call(statementDrafts, kind) ||
            statementDrafts[kind] === (previousStaged[kind] || "")) {
          statementDrafts[kind] = fetched[kind] || "";
        }
      });
      stagedStatements = fetched;
      renderStatementPhrases();
      setStatus("Choose a statement type and review every word before inserting.");
      $("statementText").focus();
    } catch (e) {
      setStatus("Couldn't load staged statements: " + ((e && e.message) || e), true);
    } finally {
      setStatementBusy(false);
    }
  }
  function closeStatementEditor() {
    if (statementInFlight) return;
    $("statementEditor").style.display = "none";
    $("statementPhrase").value = "";
  }
  function chooseStatementPhrase() {
    var type = CallosumCore.statementType($("statementKind").value);
    var selected = $("statementPhrase").value;
    if (selected === "") return;
    var index = Number(selected);
    if (!type || !Number.isInteger(index) || !type.phrases[index]) return;
    var next = type.phrases[index].text;
    var current = $("statementText").value.trim();
    if (current && current !== next && !window.confirm("Replace the current text with the selected phrase?")) {
      $("statementPhrase").value = "";
      return;
    }
    $("statementText").value = next;
    statementDrafts[$("statementKind").value] = next;
    updateStatementState();
  }
  function updateStatementDraft() {
    statementDrafts[$("statementKind").value] = $("statementText").value;
    updateStatementState();
  }
  async function stageStatement(clear) {
    var request = CallosumCore.buildStatementStageRequest(
      $("statementKind").value,
      clear ? "" : $("statementText").value,
    );
    if (!request || (!clear && !request.text)) {
      setStatus("Write a statement before staging it.", true);
      return;
    }
    setStatementBusy(true);
    setStatus(clear ? "Clearing staged statement…" : "Staging statement locally…");
    try {
      var response = await callosumFetch("/statements/pending", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      if (!response.ok) throw new Error("server returned " + response.status);
      stagedStatements = CallosumCore.normalizeStagedStatements(await response.json());
      updateStatementState();
      setStatus(clear ? "Cleared the staged statement; document text was unchanged." :
        "Staged locally for LibreOffice or another Word session.");
    } catch (e) {
      setStatus("Couldn't update the staged statement: " + ((e && e.message) || e), true);
    } finally {
      setStatementBusy(false);
    }
  }
  async function insertStatementAtCursor() {
    var text = CallosumCore.normalizeStatementText($("statementText").value);
    if (!text) {
      setStatus("Write a statement before inserting it.", true);
      return;
    }
    setStatementBusy(true);
    setStatus("Inserting the author-reviewed statement…");
    try {
      await Word.run(async function (ctx) {
        var insertionPoint = ctx.document.getSelection().getRange(Word.RangeLocation.end);
        insertionPoint.insertText(text, Word.InsertLocation.replace);
        await ctx.sync();
      });
      setStatus("Inserted ordinary editable text at the cursor; no live citation field was created.");
    } catch (e) {
      setStatus("Couldn't insert the statement: " + ((e && e.message) || e), true);
    } finally {
      setStatementBusy(false);
    }
  }

  // inc 517 (accessibility, backlog #33/#34 P1): Enter in the search box adds the top result (Zotero's own
  // shortcut, cited precedent from the LibreOffice adapter's own accessibility increment 474) -- reuses the
  // existing click handling verbatim via a real .click() rather than duplicating onPick's logic.
  function onSearchKeydown(ev) {
    if (ev.key !== "Enter") return;
    var first = $("results").querySelector("button.row");
    if (first) first.click();
  }
  // Escape clears an in-progress citation assembly -- a pure UI-state reset, never a document mutation either
  // way, so there's nothing unsafe about firing it broadly rather than scoping it to one element's focus.
  function onGlobalKeydown(ev) {
    if (ev.key === "Escape" && $("statementEditor").style.display !== "none" && !statementInFlight) {
      closeStatementEditor(); return;
    }
    if (ev.key === "Escape" && categoryOrderDraft.length && !categoryOrderInFlight) {
      closeCategoryOrderEditor(); return;
    }
    if (ev.key === "Escape" && categoryEditingPaperIds.length && !categoryEditInFlight) {
      closeCategoryEditor(); return;
    }
    if (ev.key === "Escape" && assembly.length) resetAssembly();
  }
  function wire() {
    renderStatementKinds();
    $("q").addEventListener("input", debounce(search, 250));
    $("q").addEventListener("keydown", onSearchKeydown);
    document.addEventListener("keydown", onGlobalKeydown);
    $("results").addEventListener("click", onPick);
    $("suggestions").addEventListener("click", function (ev) {
      var details = ev.target.closest("button[data-suggestion-details]");
      if (details) {
        var detailsId = details.getAttribute("data-suggestion-details");
        openSuggestionId = openSuggestionId === detailsId ? null : detailsId;
        renderSuggestionRows(suggestionRows, "No relevant papers in your library.");
        return;
      }
      var openPdf = ev.target.closest("button[data-suggestion-open-pdf]");
      if (openPdf) {
        var path = CallosumCore.suggestionOpenPdfPath(suggestionItems[openPdf.getAttribute("data-suggestion-open-pdf")]);
        if (path) window.open(path, "_blank", "noopener,noreferrer");
        return;
      }
      onPick(ev);
    });
    $("suggestions").addEventListener("input", function (ev) {
      var id = ev.target.getAttribute("data-suggestion-locator");
      if (id != null) suggestionLocators[id] = ev.target.value;
    });
    $("suggest").addEventListener("click", suggestSentence);
    $("assembly").addEventListener("click", onAssemblyClick);
    $("assembly").addEventListener("input", onAssemblyChange);
    $("assembly").addEventListener("change", onAssemblyChange);
    $("insertCitation").addEventListener("click", insertOrUpdateCitation);
    $("cancelAssembly").addEventListener("click", resetAssembly);
    $("editAtCursor").addEventListener("click", editCitationAtCursor);
    $("deleteAtCursor").addEventListener("click", deleteCitationAtCursor);
    $("diagnosticsRun").addEventListener("click", runDiagnostics);
    $("citationCoverageRun").addEventListener("click", runCitationCoverageAudit);
    $("citationsPanelRun").addEventListener("click", runCitationsPanel);
    $("citationsPanel").addEventListener("click", onCitationsPanelClick);
    $("citationsSearch").addEventListener("input", debounce(renderCitationsPanelList, 150));
    $("citationsSelectVisible").addEventListener("click", function () {
      if (categoryEditInFlight || categoryOrderInFlight) return;
      var ids = visibleCitationsPanelEntries().map(function (entry) { return entry.paperId; })
        .filter(function (paperId) { return paperId != null; });
      var combined = selectedCategoryIds().slice();
      ids.forEach(function (paperId) {
        var id = String(paperId);
        if (combined.indexOf(id) === -1) combined.push(id);
      });
      if (combined.length > CallosumCore.MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS) {
        setStatus("A batch can contain at most " + CallosumCore.MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS + " works.", true);
        return;
      }
      combined.forEach(function (paperId) { selectedCategoryPaperIds[paperId] = true; });
      if (categoryEditFromBatch) closeCategoryEditor();
      renderCitationsPanelList();
    });
    $("citationsClearSelection").addEventListener("click", function () {
      if (categoryEditInFlight || categoryOrderInFlight) return;
      selectedCategoryPaperIds = Object.create(null);
      if (categoryEditFromBatch) closeCategoryEditor();
      renderCitationsPanelList();
    });
    $("citationsBatchCategory").addEventListener("click", function () {
      openCategoryEditor(selectedCategoryIds(), true);
    });
    $("bibliographyCategoryOrderOpen").addEventListener("click", openCategoryOrderEditor);
    $("bibliographyCategoryOrderList").addEventListener("click", function (ev) {
      var button = ev.target.closest("button[data-order-index]");
      if (button) moveCategoryOrder(Number(button.getAttribute("data-order-index")), Number(button.getAttribute("data-order-delta")));
    });
    $("bibliographyCategoryOrderReset").addEventListener("click", function () {
      if (categoryOrderInFlight) return;
      categoryOrderDraft = categoryOrderAlphabetical.slice();
      renderCategoryOrderEditor();
    });
    $("bibliographyCategoryOrderSave").addEventListener("click", saveCategoryOrder);
    $("bibliographyCategoryOrderCancel").addEventListener("click", function () {
      if (!categoryOrderInFlight) closeCategoryOrderEditor();
    });
    $("bibliographyCategorySave").addEventListener("click", function () {
      applyCategoryEdit($("bibliographyCategory").value);
    });
    $("bibliographyCategoryRemove").addEventListener("click", function () { applyCategoryEdit("", true); });
    $("bibliographyCategoryCancel").addEventListener("click", function () {
      if (!categoryEditInFlight) closeCategoryEditor();
    });
    $("bibliographyCategory").addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); applyCategoryEdit($("bibliographyCategory").value); }
    });
    $("bibliographyCategory").addEventListener("input", updateCategorySaveState);
    $("refresh").addEventListener("click", function () { refreshDocument(); });
    $("sectionBibliographyInsert").addEventListener("click", insertSectionBibliography);
    $("sectionBibliographyRemove").addEventListener("click", removeSectionBibliography);
    $("bibliographyExternalLinks").addEventListener("change", onBibliographyExternalLinksChange);
    $("flatten").addEventListener("click", onFlatten);
    $("style").addEventListener("change", onStyleChange);
    $("notePlacement").addEventListener("change", onNotePlacementChange);
    $("statementOpen").addEventListener("click", openStatementEditor);
    $("statementKind").addEventListener("change", renderStatementPhrases);
    $("statementPhrase").addEventListener("change", chooseStatementPhrase);
    $("statementText").addEventListener("input", updateStatementDraft);
    $("statementInsert").addEventListener("click", insertStatementAtCursor);
    $("statementStage").addEventListener("click", function () { stageStatement(false); });
    $("statementClear").addEventListener("click", function () { stageStatement(true); });
    $("statementCancel").addEventListener("click", closeStatementEditor);
    // Unconditional (inc 510): desktop can also need this, once a fetch reveals the section on a 401.
    $("tunnelSave").addEventListener("click", saveToken);
  }

  Office.onReady(function (info) {
    if (info.host === Office.HostType.Word) {
      $("app").style.display = "block";
      wire();
      initTunnelSection();
      loadStyles();
    } else {
      $("status").textContent = "Open this add-in in Microsoft Word (desktop or Word on the web).";
    }
  });
})();
