/*
 * Callosum Word add-in — the thin Office.js glue (inc 165, SP2: live cite-while-you-write).
 *
 * Architecture A: this page is served by callosum over HTTPS (https://localhost:8443), so every fetch is a
 * SAME-ORIGIN call to the local API — nothing leaves the machine. The add-in is a thin field-placer:
 *   • Insert  — fetch the picked paper's CSL-JSON (/papers/export), wrap a Content Control whose .tag carries it,
 *               then Refresh (so the new citation renders + the whole doc renumbers).
 *   • Refresh — scan every citation Content Control IN DOCUMENT ORDER, POST them to /citations/render-document,
 *               and write back the position-aware in-text + a managed bibliography block.
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
  }

  async function search() {
    var q = $("q").value.trim();
    var res = $("results");
    if (!q) { res.innerHTML = ""; return; }
    try {
      var r = await fetch("/papers?q=" + encodeURIComponent(q) + "&limit=20");
      if (!r.ok) throw new Error("search failed (" + r.status + ")");
      var rows = CallosumCore.formatSearchRows(await r.json());
      res.innerHTML = rows.length
        ? rows.map(function (row) {
            return '<li><button class="row" data-id="' + row.id + '">' + escapeHtml(row.label) + "</button></li>";
          }).join("")
        : '<li class="empty">No matches in your library.</li>';
    } catch (e) {
      res.innerHTML = '<li class="err">' + escapeHtml(String((e && e.message) || e)) + "</li>";
    }
  }

  // Insert a LIVE citation: fetch its CSL-JSON, wrap a Content Control carrying it, then refresh the document.
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
        var inserted = ctx.document.getSelection().insertText("…", Word.InsertLocation.replace);
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

  function onPick(ev) {
    var btn = ev.target.closest("button.row[data-id]");
    if (btn) insertCitation(Number(btn.getAttribute("data-id")));
  }

  function wire() {
    $("q").addEventListener("input", debounce(search, 250));
    $("results").addEventListener("click", onPick);
    $("refresh").addEventListener("click", function () { refreshDocument(); });
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
