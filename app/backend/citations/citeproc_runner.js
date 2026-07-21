// citeproc-js sidecar (inc 106; document mode inc 107) — invoked by app/backend/citations/render.py exactly like
// the esbuild sidecar (a fixed-arg `node <this>` subprocess; request JSON on stdin, result JSON on stdout). It
// renders formatted citations + a bibliography from CSL-JSON items using the bundled CSL styles + locales. No
// network, no shell.
//
//  Per-item mode (default, inc 106) — isolated rendering for the in-app "Cite as …" / bulk bibliography:
//    stdin  : { "items": [ <CSL-JSON item with `id`>, ... ], "style": "apa", "locale": "en-US", "order": [id,...] }
//    stdout : { "items": [ { "id", "inText", "reference" }, ... ], "bibliography": [ "<entry>", ... ] }
//
//  Document mode (inc 107; per-occurrence cite properties inc TBD/P0-phase-3) — POSITION-AWARE rendering of a
//  document's ordered citation clusters (numeric renumbering, author-date disambiguation) via citeproc's
//  rebuildProcessorState; the word-processor adapter spine:
//    stdin  : { "mode": "document", "style", "locale",
//               "citations": [ { "citationID", "items": [ <CSL-JSON item with `id`, plus optional
//                 locator/label/prefix/suffix/"suppress-author"/"author-only">, ... ] }, ... ] }   // doc order
//    stdout : { "citations": [ { "citationID", "html" }, ... ], "bibliography": [ "<entry>", ... ] }
//
//  On failure either mode writes { "error": "<message>" } to stdout and exits non-zero.

"use strict";
const fs = require("fs");
const path = require("path");

function fail(msg) {
  process.stdout.write(JSON.stringify({ error: String(msg) }));
  process.exit(1);
}

let CSL;
try {
  CSL = require("citeproc");
} catch (e) {
  fail("citeproc not installed — run `npm install` at the project root.");
}

const STYLES_DIR = path.join(__dirname, "csl", "styles");
const LOCALES_DIR = path.join(__dirname, "csl", "locales");

// P0 phase 3 (backlog #33/#34): forward an item's per-occurrence citeproc-cite properties — locator/label/
// prefix/suffix/suppress-author/author-only — onto its citationItems entry, alongside `id`. These are real
// citeproc-js citationItems properties (confirmed in the engine source), separate from the CSL-JSON bibliographic
// record itself (registered separately via retrieveItem/itemsById above). Keys are copied only when actually set
// (`!= null`) rather than assigned `undefined` — a JS object literal with an `undefined`-valued key is still an
// enumerable own property, which could confuse citeproc's own presence checks on these fields.
function buildCitationItem(it) {
  const out = { id: String(it.id) };
  ["locator", "label", "prefix", "suffix"].forEach(function (k) {
    if (it[k] != null) out[k] = it[k];
  });
  if (it["suppress-author"]) out["suppress-author"] = true;
  if (it["author-only"]) out["author-only"] = true;
  return out;
}

function main() {
  let req;
  try {
    req = JSON.parse(fs.readFileSync(0, "utf8"));  // fd 0 = stdin
  } catch (e) {
    fail("invalid request JSON: " + e.message);
  }

  const locale = typeof req.locale === "string" && req.locale ? req.locale : "en-US";
  const style = String(req.style || "");
  if (!/^[a-z0-9-]+$/.test(style)) fail("invalid style id");
  const stylePath = path.join(STYLES_DIR, style + ".csl");
  if (!fs.existsSync(stylePath)) fail("unknown style: " + style);
  const styleXml = fs.readFileSync(stylePath, "utf8");

  const isDocument = req.mode === "document";

  // Item definitions: document mode flattens each cluster's embedded payload; per-item mode uses req.items.
  const itemsById = {};
  if (isDocument) {
    for (const c of Array.isArray(req.citations) ? req.citations : []) {
      for (const it of Array.isArray(c.items) ? c.items : []) {
        if (it && it.id != null) itemsById[String(it.id)] = it;
      }
    }
  } else {
    for (const it of Array.isArray(req.items) ? req.items : []) {
      if (it && it.id != null) itemsById[String(it.id)] = it;
    }
  }

  const sys = {
    retrieveLocale: function (lang) {
      const candidates = ["locales-" + lang + ".xml", "locales-" + locale + ".xml", "locales-en-US.xml"];
      for (const c of candidates) {
        const p = path.join(LOCALES_DIR, c);
        if (fs.existsSync(p)) return fs.readFileSync(p, "utf8");
      }
      return false;  // citeproc tolerates a missing secondary locale
    },
    retrieveItem: function (id) {
      return itemsById[String(id)];
    },
  };

  let engine;
  try {
    engine = new CSL.Engine(sys, styleXml, locale);
  } catch (e) {
    fail("citeproc engine error: " + e.message);
  }

  if (isDocument) {
    // Render the document's ordered clusters as a coherent whole (renumber numeric, disambiguate author-date).
    const clusters = (Array.isArray(req.citations) ? req.citations : []).map(function (c, i) {
      return {
        citationID: String(c.citationID || "c" + i),
        citationItems: (Array.isArray(c.items) ? c.items : []).map(buildCitationItem),
        properties: { noteIndex: 0 },
      };
    });
    let rebuilt;
    try {
      rebuilt = engine.rebuildProcessorState(clusters, "html");
    } catch (e) {
      fail("citeproc rebuild error: " + e.message);
    }
    const byId = {};
    (rebuilt || []).forEach(function (r) { byId[r[0]] = r[2]; });  // [citationID, noteIndex, renderedString]
    const outCitations = clusters.map(function (c) { return { citationID: c.citationID, html: byId[c.citationID] || "" }; });
    let bibliography = [];
    try {
      const bib = engine.makeBibliography();
      bibliography = bib && bib[1] ? bib[1].map(function (s) { return String(s).trim(); }) : [];
    } catch (e) {
      bibliography = [];  // some styles have no bibliography layout
    }
    process.stdout.write(JSON.stringify({ citations: outCitations, bibliography: bibliography }));
    return;
  }

  // Per-item (inc 106): isolated rendering — a per-paper bibliography entry + a single-cluster in-text cite.
  const ids = (Array.isArray(req.order) && req.order.length ? req.order : Object.keys(itemsById)).map(String);
  try {
    engine.updateItems(ids);
  } catch (e) {
    fail("citeproc engine error: " + e.message);
  }
  const refById = {};
  try {
    const bib = engine.makeBibliography();
    if (bib && bib[0] && Array.isArray(bib[0].entry_ids)) {
      bib[0].entry_ids.forEach(function (arr, i) {
        refById[String(arr[0])] = String((bib[1] || [])[i] || "").trim();
      });
    }
  } catch (e) {
    fail("bibliography error: " + e.message);
  }
  const out = ids.map(function (id) {
    let inText = "";
    try {
      inText = engine.makeCitationCluster([{ id: id }]);
    } catch (e) {
      inText = "";
    }
    return { id: id, inText: inText, reference: refById[id] || "" };
  });
  const bibliography = ids.map(function (id) { return refById[id]; }).filter(Boolean);
  process.stdout.write(JSON.stringify({ items: out, bibliography: bibliography }));
}

main();
