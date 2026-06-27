/*
 * Callosum Word add-in — the thin Office.js glue (inc 164 SP1).
 *
 * Architecture A: this page is served by callosum over HTTPS (https://localhost:8443), so every fetch below is a
 * SAME-ORIGIN call to the local API — nothing leaves the machine. The page is a thin field-placer: it reads the
 * library (/papers?q=) and the formatted citation (/citations/render), and writes it into the doc via Word.run.
 * All formatting happens in callosum's citeproc engine (this never formats).
 *
 * Pure logic lives in taskpane_core.js (CallosumCore.*) so it can be unit-tested without Office/DOM.
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
      var styles = (data && data.styles) || [];
      sel.innerHTML = styles.map(function (s) {
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

  async function onPick(ev) {
    var btn = ev.target.closest("button.row[data-id]");
    if (!btn) return;
    var id = Number(btn.getAttribute("data-id"));
    setStatus("Inserting…");
    try {
      var r = await fetch("/citations/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(CallosumCore.buildRenderRequest(id, currentStyle(), "en-US")),
      });
      if (!r.ok) throw new Error("render failed (" + r.status + ")");
      var inText = CallosumCore.inTextFromRender(await r.json());
      if (!inText) throw new Error("no citation text returned");
      await Word.run(async function (ctx) {
        ctx.document.getSelection().insertText(inText, Word.InsertLocation.replace);
        await ctx.sync();
      });
      setStatus("Inserted: " + inText);
    } catch (e) {
      setStatus("Couldn't insert: " + ((e && e.message) || e), true);
    }
  }

  function wire() {
    $("q").addEventListener("input", debounce(search, 250));
    $("results").addEventListener("click", onPick);
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
