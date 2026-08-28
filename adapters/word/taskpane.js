/*
 * Callosum Word add-in — the thin Office.js glue (inc 166, SP3: parity — suggest / style-switch / flatten;
 * SP4: Word-on-the-web relay; inc 509: grouped-citation composer with locators/edit/delete; inc 516: Citations
 * in this document panel; inc 517: accessibility pass -- icon-button aria-labels, Enter-to-add, Escape-to-cancel).
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
 *   • Insert/Update — wraps the assembly's items in a Content Control whose .tag carries them (a NEW citation
 *               at the END of the selection, so Suggest inserts AFTER the sentence) or retags an existing one
 *               (Edit mode), then Refresh.
 *   • Suggest — read the sentence (selection, else the paragraph), POST /citations/suggest → ranked candidates
 *               with stance + quote (the reason); pick one to add to the assembly.
 *   • Edit/Delete at cursor — reads the citation Content Control the cursor is inside
 *               (Range.parentContentControlOrNullObject) to repopulate the composer or remove it outright.
 *   • Refresh — scan every citation Content Control IN DOCUMENT ORDER → /citations/render-document → write back
 *               the position-aware in-text + a managed bibliography block.
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
  function renderRows(ulId, rows, emptyMsg) {
    $(ulId).innerHTML = rows.length
      ? rows.map(function (row) {
          return '<li><button class="row" data-id="' + row.id + '">' + escapeHtml(row.label) + "</button></li>";
        }).join("")
      : '<li class="empty">' + escapeHtml(emptyMsg) + "</li>";
  }

  async function loadStyles() {
    try {
      var r = await callosumFetch("/citations/styles");
      if (!r.ok) return;
      var data = await r.json();
      var sel = $("style");
      sel.innerHTML = ((data && data.styles) || []).map(function (s) {
        return '<option value="' + escapeHtml(s.id) + '">' + escapeHtml(s.title || s.id) + "</option>";
      }).join("");
      if (data && data.default_style) sel.value = data.default_style;
    } catch (e) { /* styles are optional polish; the default 'apa' still works */ }
    // A persisted per-document style choice wins (set programmatically → does not fire 'change').
    try {
      var saved = Office.context.document.settings.get("callosumStyle");
      if (saved) $("style").value = saved;
    } catch (e) { /* settings unavailable → keep the default */ }
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
      var rows = CallosumCore.formatSuggestRows((data && data.suggestions) || []);
      renderRows("suggestions", rows, "No relevant papers in your library.");
      setStatus(rows.length ? "Pick a paper to add — ranked by relevance; the quote is the reason." : "");
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
      assembly.push({ csl: csl, row: CallosumCore.cslRecordRow(csl) });
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
          cc.tag = CallosumCore.encodeCitationTag(items);
          await ctx.sync();
        });
      } else {
        await Word.run(async function (ctx) {
          var end = ctx.document.getSelection().getRange(Word.RangeLocation.end);
          var inserted = end.insertText("…", Word.InsertLocation.replace);
          var newCc = inserted.insertContentControl();
          newCc.tag = CallosumCore.encodeCitationTag(items);
          newCc.title = "Callosum citation";
          newCc.appearance = Word.ContentControlAppearance.hidden; // a live field, not a visible box
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
        cc.load("tag,isNullObject");
        await ctx.sync();
        if (cc.isNullObject || !CallosumCore.isCitationTag(cc.tag)) return;
        var items = CallosumCore.decodeCitationTag(cc.tag);
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
        cc.delete(false);
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
    lines.push("Bibliography: " + report.bibliography + ".");
    if (truncated) lines.push("(Only the first " + MAX_EXISTENCE_CHECK_IDS + " distinct cited papers were checked against the library.)");
    $("diagnostics").textContent = lines.join(" ");
  }
  async function runDiagnostics() {
    setStatus("Scanning the document…");
    $("diagnostics").textContent = "";
    try {
      var tags = [];
      await Word.run(async function (ctx) {
        var ccs = ctx.document.body.contentControls;
        ccs.load("items/tag");
        await ctx.sync();
        tags = ccs.items.map(function (cc) { return cc.tag; });
      });

      var idSet = {};
      tags.forEach(function (tag) {
        if (!CallosumCore.isCitationTag(tag)) return;
        var items = CallosumCore.decodeCitationTag(tag);
        if (!items) return;
        items.forEach(function (item) {
          var pid = CallosumCore.extractPaperId(item && item.id);
          if (pid != null) idSet[pid] = true;
        });
      });
      var existence = await checkPaperExistence(Object.keys(idSet));
      renderDiagnosticsReport(
        CallosumCore.summarizeDiagnostics(tags, existence.missingIds, existence.checked),
        existence.truncated,
      );
      setStatus("Diagnostics complete.");
    } catch (e) {
      setStatus("Couldn't run diagnostics: " + ((e && e.message) || e), true);
    }
  }

  // Citations-in-this-document panel (inc 516): every unique cited work, occurrence count, orphan/retraction
  // badges, click-to-navigate to its first occurrence, and client-side search -- explicit on-demand trigger,
  // matching Document diagnostics' own UX pattern (no auto-refresh, no background work on load).
  var citationsPanelEntries = []; // last-computed entries, re-filtered client-side on every search keystroke
  function renderCitationsPanelBadges(entry) {
    var badges = [];
    if (entry.orphaned) badges.push('<span class="badge-warn">not in library</span>');
    if (entry.retraction) badges.push('<span class="badge-warn">' + escapeHtml(entry.retraction.status) + "</span>");
    return badges.join(" ");
  }
  function renderCitationsPanelList() {
    var filterText = ($("citationsSearch").value || "").trim().toLowerCase();
    var visible = filterText
      ? citationsPanelEntries.filter(function (e) { return e.row.toLowerCase().indexOf(filterText) !== -1; })
      : citationsPanelEntries;
    $("citationsPanel").innerHTML = visible.length
      ? visible.map(function (e) {
          return '<li><button class="row" data-position="' + e.positions[0] + '">' +
            escapeHtml(e.row) + " · " + e.occurrenceCount + "×  " + renderCitationsPanelBadges(e) +
            "</button></li>";
        }).join("")
      : '<li class="empty">' + escapeHtml(citationsPanelEntries.length ? "No matches." : "No citations in this document yet.") + "</li>";
  }
  async function runCitationsPanel() {
    setStatus("Scanning the document…");
    $("citationsPanel").innerHTML = "";
    $("citationsSearch").style.display = "block"; // revealed on first use, like the tunnel token section
    try {
      var tags = [];
      await Word.run(async function (ctx) {
        var ccs = ctx.document.body.contentControls;
        ccs.load("items/tag");
        await ctx.sync();
        tags = ccs.items.map(function (cc) { return cc.tag; });
      });
      var entries = CallosumCore.buildCitationsPanelEntries(tags);
      var ids = entries.map(function (e) { return e.paperId; }).filter(function (id) { return id != null; });
      var existence = await checkPaperExistence(ids);
      citationsPanelEntries = CallosumCore.mergePanelEntryStatus(entries, existence.missingIds, existence.checked);
      renderCitationsPanelList();
      setStatus(
        entries.length + " unique work(s) cited" + (existence.truncated ? " (only the first " + MAX_EXISTENCE_CHECK_IDS + " checked against the library)" : "") + ".",
      );
    } catch (e) {
      setStatus("Couldn't build the citations panel: " + ((e && e.message) || e), true);
    }
  }
  function onCitationsPanelClick(ev) {
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
        var ccs = ctx.document.body.contentControls;
        ccs.load("items/tag");
        await ctx.sync();
        var citationCCs = ccs.items.filter(function (cc) { return CallosumCore.isCitationTag(cc.tag); });
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

  // Re-render every Callosum citation in document order + rebuild the bibliography (the Zotero-style loop).
  async function refreshDocument() {
    setStatus("Refreshing…");
    try {
      await Word.run(async function (ctx) {
        var body = ctx.document.body;
        var ccs = body.contentControls;
        ccs.load("items/tag");
        await ctx.sync();

        var citationCCs = [], itemsList = [], bibCC = null;
        ccs.items.forEach(function (cc) {
          if (CallosumCore.isCitationTag(cc.tag)) {
            var items = CallosumCore.decodeCitationTag(cc.tag);
            if (items) { citationCCs.push(cc); itemsList.push(items); }
          } else if (cc.tag === CallosumCore.BIB_TAG) {
            bibCC = cc;
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
        bibCC.insertText(CallosumCore.bibliographyText(data), Word.InsertLocation.replace);

        await ctx.sync();
        setStatus("Updated " + itemsList.length + " citation(s) + the bibliography.");
      });
    } catch (e) {
      setStatus("Couldn't refresh: " + ((e && e.message) || e), true);
    }
  }

  // One-click whole-document style switch: persist the choice (per document) + re-render.
  async function onStyleChange() {
    try {
      Office.context.document.settings.set("callosumStyle", currentStyle());
      Office.context.document.settings.saveAsync(function () {});
    } catch (e) { /* settings unavailable → still re-render below */ }
    await refreshDocument();
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
        var ccs = ctx.document.body.contentControls;
        ccs.load("items/tag");
        await ctx.sync();
        ccs.items.forEach(function (cc) {
          if (CallosumCore.isCitationTag(cc.tag)) citationCount += 1;
          else if (cc.tag === CallosumCore.BIB_TAG) hasBib = true;
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
        var ccs = ctx.document.body.contentControls;
        ccs.load("items/tag");
        await ctx.sync();
        ccs.items.forEach(function (cc) {
          if (CallosumCore.isCitationTag(cc.tag) || cc.tag === CallosumCore.BIB_TAG) {
            cc.delete(true); // keep the rendered text, drop the live field
            n++;
          }
        });
        await ctx.sync();
        // Post-flatten integrity check: re-scan rather than trust the delete calls above all landed.
        var after = ctx.document.body.contentControls;
        after.load("items/tag");
        await ctx.sync();
        after.items.forEach(function (cc) {
          if (CallosumCore.isCitationTag(cc.tag) || cc.tag === CallosumCore.BIB_TAG) remaining += 1;
        });
      });
      if ($("flattenClearStyle").checked) {
        try {
          Office.context.document.settings.remove("callosumStyle");
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
    if (ev.key === "Escape" && assembly.length) resetAssembly();
  }
  function wire() {
    $("q").addEventListener("input", debounce(search, 250));
    $("q").addEventListener("keydown", onSearchKeydown);
    document.addEventListener("keydown", onGlobalKeydown);
    $("results").addEventListener("click", onPick);
    $("suggestions").addEventListener("click", onPick);
    $("suggest").addEventListener("click", suggestSentence);
    $("assembly").addEventListener("click", onAssemblyClick);
    $("assembly").addEventListener("input", onAssemblyChange);
    $("assembly").addEventListener("change", onAssemblyChange);
    $("insertCitation").addEventListener("click", insertOrUpdateCitation);
    $("cancelAssembly").addEventListener("click", resetAssembly);
    $("editAtCursor").addEventListener("click", editCitationAtCursor);
    $("deleteAtCursor").addEventListener("click", deleteCitationAtCursor);
    $("diagnosticsRun").addEventListener("click", runDiagnostics);
    $("citationsPanelRun").addEventListener("click", runCitationsPanel);
    $("citationsPanel").addEventListener("click", onCitationsPanelClick);
    $("citationsSearch").addEventListener("input", debounce(renderCitationsPanelList, 150));
    $("refresh").addEventListener("click", function () { refreshDocument(); });
    $("flatten").addEventListener("click", onFlatten);
    $("style").addEventListener("change", onStyleChange);
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
