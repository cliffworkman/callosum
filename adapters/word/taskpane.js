/*
 * Callosum Word add-in — the thin Office.js glue (inc 166, SP3: parity — suggest / style-switch / flatten;
 * SP4: Word-on-the-web relay; inc 509: grouped-citation composer with locators/edit/delete).
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
      var csl = CallosumCore.firstCslRecord(await r.json());
      if (!csl) throw new Error("no CSL-JSON returned");
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
              '<button type="button" class="icon-btn" data-act="up" title="Move up">↑</button>' +
              '<button type="button" class="icon-btn" data-act="down" title="Move down">↓</button>' +
              '<button type="button" class="icon-btn" data-act="opts" aria-pressed="' + optionsOpen +
                '" title="Locator, prefix, suffix…">⋯</button>' +
              '<button type="button" class="icon-btn" data-act="remove" title="Remove">✕</button>' +
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

  // Flatten = convert citation + bibliography Content Controls to plain text (one-way). Two-click confirm — no dialog.
  var flattenArmed = false;
  function onFlatten() {
    if (!flattenArmed) {
      flattenArmed = true;
      $("flatten").textContent = "Click again to flatten (one-way)";
      setStatus("Flatten makes every citation + the bibliography plain text — click again to confirm.");
      setTimeout(function () {
        flattenArmed = false;
        $("flatten").textContent = "Flatten to static text";
      }, 4000);
      return;
    }
    flattenArmed = false;
    $("flatten").textContent = "Flatten to static text";
    doFlatten();
  }
  async function doFlatten() {
    setStatus("Flattening…");
    try {
      var n = 0;
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
      });
      setStatus("Flattened " + n + " field(s) to static text — live updating is off for them now.");
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

  function wire() {
    $("q").addEventListener("input", debounce(search, 250));
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
