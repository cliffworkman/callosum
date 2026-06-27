/*
 * Callosum Word add-in — the thin Office.js glue (inc 166, SP3: parity — suggest / style-switch / flatten).
 *
 * Architecture A: this page is served by callosum over HTTPS (https://localhost:8443), so every fetch is a
 * SAME-ORIGIN call to the local API — nothing leaves the machine. The add-in is a thin field-placer:
 *   • Insert  — fetch the picked paper's CSL-JSON (/papers/export), wrap a Content Control whose .tag carries it,
 *               at the END of the selection (so Suggest inserts AFTER the sentence), then Refresh.
 *   • Suggest — read the sentence (selection, else the paragraph), POST /citations/suggest → ranked candidates
 *               with stance + quote (the reason); pick one to insert.
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

  function $(id) { return document.getElementById(id); }
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
      var r = await fetch("/citations/styles");
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
      var r = await fetch("/papers?q=" + encodeURIComponent(q) + "&limit=20");
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
      var r = await fetch("/citations/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(CallosumCore.buildSuggestRequest(queryText, 8)),
      });
      if (!r.ok) throw new Error("suggest failed (" + r.status + ")");
      var data = await r.json();
      var rows = CallosumCore.formatSuggestRows((data && data.suggestions) || []);
      renderRows("suggestions", rows, "No relevant papers in your library.");
      setStatus(rows.length ? "Pick a paper to cite — ranked by relevance; the quote is the reason." : "");
    } catch (e) {
      setStatus("Couldn't suggest: " + ((e && e.message) || e), true);
    }
  }

  // Insert a LIVE citation at the END of the selection (so Suggest inserts after the sentence, never replacing it).
  async function insertCitation(paperId) {
    setStatus("Inserting…");
    try {
      var r = await fetch("/papers/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format: "csl-json" }),
      });
      if (!r.ok) throw new Error("export failed (" + r.status + ")");
      var csl = CallosumCore.firstCslRecord(await r.json());
      if (!csl) throw new Error("no CSL-JSON returned");
      await Word.run(async function (ctx) {
        var end = ctx.document.getSelection().getRange(Word.RangeLocation.end);
        var inserted = end.insertText("…", Word.InsertLocation.replace);
        var cc = inserted.insertContentControl();
        cc.tag = CallosumCore.encodeCitationTag([csl]);
        cc.title = "Callosum citation";
        cc.appearance = Word.ContentControlAppearance.hidden; // a live field, not a visible box
        await ctx.sync();
      });
      await refreshDocument(); // render the new citation + renumber the rest + rebuild the bibliography
    } catch (e) {
      setStatus("Couldn't insert: " + ((e && e.message) || e), true);
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

        var resp = await fetch("/citations/render-document", {
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

  function onPick(ev) {
    var btn = ev.target.closest("button.row[data-id]");
    if (btn) insertCitation(Number(btn.getAttribute("data-id")));
  }

  function wire() {
    $("q").addEventListener("input", debounce(search, 250));
    $("results").addEventListener("click", onPick);
    $("suggestions").addEventListener("click", onPick);
    $("suggest").addEventListener("click", suggestSentence);
    $("refresh").addEventListener("click", function () { refreshDocument(); });
    $("flatten").addEventListener("click", onFlatten);
    $("style").addEventListener("change", onStyleChange);
  }

  Office.onReady(function (info) {
    if (info.host === Office.HostType.Word) {
      $("app").style.display = "block";
      wire();
      loadStyles();
    } else {
      $("status").textContent = "Open this add-in in Microsoft Word (desktop).";
    }
  });
})();
