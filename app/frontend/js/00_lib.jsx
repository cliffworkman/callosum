const { useState, useEffect, useCallback, useRef } = React;

// ─────────────────────────────────────────────────────────────
// CONFIG — defaults to the same-origin API served by FastAPI.
// Launch the backend with, e.g.:
//   $env:CALLOSUM_DB_URL = "sqlite:///C:/path/to/validation.sqlite"
//   uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
// Then open http://127.0.0.1:8080/. For separate frontend development,
// override with ?api=http://127.0.0.1:8080 or window.CALLOSUM_API_BASE.
// ─────────────────────────────────────────────────────────────
const API_BASE = (() => {
  const params = new URLSearchParams(window.location.search);
  const override = params.get("api") || window.CALLOSUM_API_BASE || "";
  return override.replace(/\/+$/, "");
})();
const API_LABEL = API_BASE || "same-origin API";

// Remote-access token (inc 168). When the user turns Remote access ON (Settings → for the Google Docs add-on via a
// tunnel), the backend gates every data call behind a bearer token — and the LOCAL browser needs it too (the app
// can't tell the local browser from the tunnel). We keep the token in localStorage (never injected into the served
// HTML, so there is no leak path) and inject it on SAME-ORIGIN requests from ONE place — a fetch shim — so the api*
// helpers AND every raw fetch (exports, PDF bytes) are covered uniformly. Harmless when remote access is off.
const ACCESS_TOKEN_KEY = "callosum.accessToken";
function getAccessToken() { try { return localStorage.getItem(ACCESS_TOKEN_KEY) || ""; } catch (e) { return ""; } }
function setAccessToken(token) {
  try { token ? localStorage.setItem(ACCESS_TOKEN_KEY, token) : localStorage.removeItem(ACCESS_TOKEN_KEY); } catch (e) { /* ignore */ }
}
(function _installAuthFetchShim() {
  const orig = window.fetch.bind(window);
  const sameOrigin = (url) => {
    if (typeof url !== "string") return false;
    return API_BASE ? url.startsWith(API_BASE) : (url.startsWith("/") || url.startsWith(window.location.origin));
  };
  window.fetch = function (input, init) {
    const token = getAccessToken();
    const url = typeof input === "string" ? input : (input && input.url);
    if (token && sameOrigin(url)) {
      const next = Object.assign({}, init);
      const h = new Headers((next.headers) || (typeof input !== "string" && input && input.headers) || {});
      if (!h.has("Authorization")) h.set("Authorization", "Bearer " + token);
      next.headers = h;
      return orig(input, next);
    }
    return orig(input, init);
  };
})();

// inc 254: remote-access LOCKOUT recovery. When Remote access is on but this browser holds no valid token, every
// data call 401s (including GET /settings) — a dead-end the old "start the backend" error box wrongly blamed on a
// dead server. The api* helpers below flag a 401 as `authRequired` and notify ONE registered handler, so the App
// raises a single honest recovery overlay (AccessLockOverlay) instead of N panes each erroring. Recovery is either:
// paste the token (client-side), or the local-possession reset (POST /access/recover — disable-only).
let _authRequiredHandler = null;
function onAuthRequired(fn) { _authRequiredHandler = fn; }
function _notifyAuthRequired() { try { if (_authRequiredHandler) _authRequiredHandler(); } catch (e) { /* ignore */ } }
function clearAccessToken() { setAccessToken(""); }
async function startAccessRecovery() { return apiPost("/access/recover", {}); }        // phase 1 → writes the code to a local file
async function submitAccessRecovery(code) { return apiPost("/access/recover", { code }); }  // phase 2 → verify → disable remote access

// inc-100: tag provenance. A tag carries an import_source; imported author/index keywords are styled distinctly
// from tags you added (aesthetic only — no extra labels), with the specific source shown in the tooltip.
function tagIsImported(source) { return !!source && source !== "user"; }
function tagSourceLabel(source) {
  if (!source || source === "user") return "Added by you";
  if (source === "keyword:crossref") return "Imported keyword — from Crossref subjects";
  if (source === "keyword:openalex") return "Imported keyword — from OpenAlex";
  if (source === "keyword:pubmed") return "Imported keyword — from PubMed (MeSH)";
  if (source === "zotero") return "Imported from Zotero";
  return "Imported keyword (" + source + ")";
}
const PAGE_SIZE = 50;

// thin fetch helper — returns {ok, data, error}
async function api(path) {
  try {
    const res = await fetch(API_BASE + path, { headers: { "Accept": "application/json" } });
    if (!res.ok) {
      if (res.status === 401) { _notifyAuthRequired(); return { ok: false, status: 401, authRequired: true, error: `HTTP 401 on ${path}` }; }
      return { ok: false, error: `HTTP ${res.status} on ${path}` };
    }
    return { ok: true, data: await res.json() };
  } catch (e) {
    return { ok: false, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
  }
}

async function apiPost(path, body) {
  try {
    const res = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status} on ${path}`;
      if (res.status === 401) { _notifyAuthRequired(); return { ok: false, status: 401, authRequired: true, error: detail }; }
      console.warn("[callosum] request failed:", path, detail);
      return { ok: false, error: detail };
    }
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
  }
}

async function apiDelete(path) {
  try {
    const res = await fetch(API_BASE + path, { method: "DELETE", headers: { "Accept": "application/json" } });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      const detail = data && data.detail ? data.detail : `HTTP ${res.status} on ${path}`;
      if (res.status === 401) { _notifyAuthRequired(); return { ok: false, status: 401, authRequired: true, error: detail }; }
      console.warn("[callosum] request failed:", path, detail);
      return { ok: false, error: detail };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
  }
}

async function apiPatch(path, body) {
  try {
    const res = await fetch(API_BASE + path, {
      method: "PATCH",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status} on ${path}`;
      if (res.status === 401) { _notifyAuthRequired(); return { ok: false, status: 401, authRequired: true, error: detail }; }
      console.warn("[callosum] request failed:", path, detail);
      return { ok: false, error: detail };
    }
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
  }
}

async function apiPut(path, body) {
  try {
    const res = await fetch(API_BASE + path, {
      method: "PUT",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status} on ${path}`;
      if (res.status === 401) { _notifyAuthRequired(); return { ok: false, status: 401, authRequired: true, error: detail }; }
      console.warn("[callosum] request failed:", path, detail);
      return { ok: false, error: detail };
    }
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
  }
}

// ─────────────────────────────────────────────────────────────
// Client-side file downloads (citation export + formatted bibliography). Extracted from App (inc 167) so the
// god-component stays under the 600-line cap; these are pure UI utilities over the existing export/render endpoints.
// ─────────────────────────────────────────────────────────────
function _downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// inc-70: download the given papers' citations as a file (BibTeX/RIS/CSL-JSON). Raw fetch — apiPost forces .json().
async function downloadCitationExport(ids, format) {
  if (!ids || !ids.length) return;
  const ext = format === "ris" ? "ris" : format === "csl-json" ? "json" : "bib";
  try {
    const res = await fetch(API_BASE + "/papers/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paper_ids: ids, format }),
    });
    if (!res.ok) { console.warn("[callosum] export failed:", res.status); return; }
    _downloadBlob(await res.blob(), `callosum-citations.${ext}`);
  } catch (e) { console.warn("[callosum] export error:", e); }
}

// inc-106: download a FORMATTED bibliography (citeproc engine → sanitized HTML → .html file).
async function downloadBibliography(ids, style) {
  if (!ids || !ids.length) return;
  const r = await apiPost("/citations/render", { paper_ids: ids, style });
  if (!r.ok) { console.warn("[callosum] bibliography failed:", r.error); return; }
  const entries = (r.data && r.data.bibliography_html) || [];
  if (!entries.length) return;
  const body = entries.map(e => `<p style="text-indent:-2em;padding-left:2em;margin:0 0 .6em">${e}</p>`).join("");
  const html = `<!doctype html><meta charset="utf-8"><title>Bibliography (${style})</title>` +
    `<body style="font-family:Georgia,'Times New Roman',serif;font-size:12pt;line-height:1.5;max-width:46em;margin:2em auto">${body}</body>`;
  _downloadBlob(new Blob([html], { type: "text/html" }), `callosum-bibliography-${style}.html`);
}

// inc-172: download a server asset (the LibreOffice .oxt / Word manifest) via a GET that goes through the auth
// shim, so it carries the access token under Remote access — a plain <a download> navigation would NOT, and 401s.
async function downloadAsset(path, filename) {
  try {
    const res = await fetch(API_BASE + path);
    if (!res.ok) { console.warn("[callosum] download failed:", path, res.status); return; }
    _downloadBlob(await res.blob(), filename);
  } catch (e) { console.warn("[callosum] download error:", path, e); }
}

// inc-144 (Close-reader): assemble a paper's highlights + notes into a copy/printable Markdown digest — pure,
// from the already-loaded annotations ({page, anchor_text, note}), page-ordered like the panel. (Relocated from
// 30_viewer.jsx in inc 175 for the rule-#1 cap; it's a pure util, the viewer's home for it.)
// B2 SP1: download a portable library bundle (metadata + tags + annotations + axis defs, NO PDFs). Raw POST — a
// tokened fetch through the auth shim (so it carries the Remote-access token) since apiPost forces .json().
async function downloadBundle(scope, paperIds) {
  try {
    const res = await fetch(API_BASE + "/library/bundle/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, paper_ids: paperIds || [] }),
    });
    if (!res.ok) { console.warn("[callosum] bundle export failed:", res.status); return; }
    _downloadBlob(await res.blob(), "callosum-library-bundle.json");
  } catch (e) { console.warn("[callosum] bundle export error:", e); }
}

function buildAnnotationDigest(title, annotations) {
  const lines = [`# ${title || "Highlights & notes"}`, "", `_${annotations.length} highlight${annotations.length === 1 ? "" : "s"}_`, ""];
  for (const a of annotations) {
    const quote = (a.anchor_text || "").trim();
    lines.push(`**p.${a.page}**${quote ? " — " + quote : ""}`);
    if (a.note && a.note.trim()) lines.push(`> ${a.note.trim()}`);
    lines.push("");
  }
  return lines.join("\n").trim() + "\n";
}

// ─────────────────────────────────────────────────────────────
// PDF.js — loaded lazily from cdnjs, exactly once, the first time a
// PDF tab is opened. UMD build (3.x) so it works with no build step.
// ─────────────────────────────────────────────────────────────
const PDFJS_VERSION = "3.11.174";
let pdfLibPromise = null;
function loadPdfJs() {
  if (pdfLibPromise) return pdfLibPromise;
  pdfLibPromise = new Promise((resolve, reject) => {
    if (window.pdfjsLib) { resolve(window.pdfjsLib); return; }
    const script = document.createElement("script");
    script.src = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/pdf.min.js`;
    script.onload = () => {
      if (!window.pdfjsLib) { reject(new Error("PDF.js failed to initialize")); return; }
      window.pdfjsLib.GlobalWorkerOptions.workerSrc =
        `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/pdf.worker.min.js`;
      resolve(window.pdfjsLib);
    };
    script.onerror = () => reject(new Error("Could not load PDF.js from the CDN"));
    document.head.appendChild(script);
  });
  return pdfLibPromise;
}

function tierClass(t) {
  if (!t) return "tier-unknown";
  return "tier-" + t.toLowerCase().replace(/[^a-z]+/g, "-");
}
function tierLabel(t) { return t ? t.replace(/[-_]/g, " ") : "unknown"; }

// A paper is "metadata-unresolved" if it has no real metadata yet.
// Honest signal: authors empty AND no year — the raw-PDF stub state.
function needsMetadata(p) {
  return (!p.authors || p.authors.length === 0) && !p.year;
}

function fmtAuthors(authors, max = 3) {
  if (!authors || authors.length === 0) return null;
  if (authors.length <= max) return authors.join(", ");
  return authors.slice(0, max).join(", ") + ` +${authors.length - max} more`;
}

function fmtScore(value) {
  return typeof value === "number" ? value.toFixed(3) : "—";
}

const SECTION_LABELS = {
  abstract: "Abstract",
  introduction: "Introduction",
  methods: "Methods",
  results: "Results",
  discussion: "Discussion",
  data_availability: "Data availability",
  code_availability: "Code availability",
  funding: "Funding",
  conflict_of_interest: "Conflict of interest",
  ethics: "Ethics",
  references: "References",
  supplementary_material: "Supplementary material",
};

function sectionLabel(section) {
  const raw = String(section || "").trim();
  if (!raw) return "";
  return SECTION_LABELS[raw] || raw.replace(/[_-]+/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function pageLabel(citation) {
  const section = sectionLabel(citation && citation.section);
  if (!citation || citation.page_start == null) return section || "No page located";
  const page = citation.page_end && citation.page_end !== citation.page_start
    ? `pp. ${citation.page_start}-${citation.page_end}`
    : `p. ${citation.page_start}`;
  return section ? `${section} · ${page}` : page;
}

function precisionText(precision) {
  if (precision === "exact") return "exact quote coordinates";
  if (precision === "region") return "region-level · exact passage not located";
  return "no coordinate claim";
}

function evidencePrecisionText(precision, hasSourcePage) {
  if (precision === "exact") return "exact highlight";
  if (precision === "region") return "region";
  if (hasSourcePage) return "page only";
  return "no source page";
}

function evidencePrecisionClass(precision, hasSourcePage) {
  if (precision === "exact") return "exact";
  if (precision === "region") return "region";
  if (hasSourcePage) return "page";
  return "none";
}

function boundedEvidenceText(text, maxChars = 420) {
  const raw = String(text || "").replace(/\s+/g, " ").trim();
  if (raw.length <= maxChars) return { text: raw, clipped: false };
  return { text: raw.slice(0, Math.max(0, maxChars - 1)).trimEnd() + "…", clipped: true };
}

function EvidenceQuote({
  text,
  match,
  label = "Evidence",
  section,
  precision,
  hasSourcePage,
  onOpen,
  openLabel,
  maxChars = 420,
  className = "",
}) {
  const bounded = boundedEvidenceText(text, maxChars);
  if (!bounded.text) return null;
  const needle = String(match || "").trim().toLowerCase();
  const hay = bounded.text.toLowerCase();
  const idx = needle ? hay.indexOf(needle) : -1;
  const body = idx < 0
    ? bounded.text
    : <React.Fragment>
        {bounded.text.slice(0, idx)}
        <mark className="evidence-mark">{bounded.text.slice(idx, idx + needle.length)}</mark>
        {bounded.text.slice(idx + needle.length)}
      </React.Fragment>;
  const classes = `evidence-quote ${onOpen ? "is-clickable" : ""} ${className}`.trim();
  const title = onOpen ? (openLabel || "Open source evidence") : (bounded.clipped ? String(text || "") : undefined);
  const showPrecision = precision !== undefined || hasSourcePage !== undefined;
  const precisionClass = evidencePrecisionClass(precision, !!hasSourcePage);
  const precisionLabel = evidencePrecisionText(precision, !!hasSourcePage);
  const sectionText = sectionLabel(section);
  const head = (
    <span className="evidence-head">
      <span className="evidence-label">{label}</span>
      {sectionText && <span className="coord evidence-section">{sectionText}</span>}
      {showPrecision && <span className={"coord evidence-precision " + precisionClass}>{precisionLabel}</span>}
    </span>
  );
  if (onOpen) {
    return (
      <button type="button" className={classes} title={title} aria-label={openLabel || label} onClick={onOpen}>
        {head}
        <span className="evidence-text">“{body}”</span>
      </button>
    );
  }
  return (
    <span className={classes} title={title}>
      {head}
      <span className="evidence-text">“{body}”</span>
    </span>
  );
}

function EvidenceTrail({ detector, matched, precision, hasSourcePage, page, section, caveat, reason }) {
  const source = evidencePrecisionText(precision, !!hasSourcePage);
  const sectionText = sectionLabel(section);
  const why = reason || (
    precision === "exact"
      ? "Callosum located this evidence text in the PDF on the expected page."
      : hasSourcePage
        ? "Callosum has a source page, but no exact PDF text box is available for this evidence."
        : "No source page is available for this evidence item."
  );
  return (
    <details className="evidence-trail">
      <summary>Evidence trail</summary>
      <div className="evidence-trail-grid">
        {detector && <span><b>Detector</b>{detector}</span>}
        <span><b>Source precision</b>{source}</span>
        {sectionText && <span><b>Section</b>{sectionText}</span>}
        <span><b>Page</b>{hasSourcePage ? "p. " + page : "not located"}</span>
        {matched && <span><b>Matched text</b>{boundedEvidenceText(matched, 180).text}</span>}
        <span><b>Anchor note</b>{why}</span>
        {caveat && <span><b>Boundary</b>{caveat}</span>}
      </div>
    </details>
  );
}

function citationTarget(citation) {
  if (!citation || citation.paper_id == null) return null;
  return {
    id: `${citation.mapping_id || citation.evidence_quote_id || Date.now()}:${citation.coordinate_precision || "none"}`,
    paperId: citation.paper_id,
    paperTitle: citation.paper_title || `Paper ${citation.paper_id}`,
    page: citation.page_start || citation.page_end || null,
    pageEnd: citation.page_end || citation.page_start || null,
    section: citation.section || null,
    precision: citation.coordinate_precision || null,
    bboxJson: citation.bbox_json || null,
    status: citation.status,
    quote: citation.quote || "",
  };
}

function methodEvidenceTarget(paperId, paperTitle, evidence, key) {
  if (paperId == null || !evidence || evidence.page == null) return null;
  return {
    id: key || `methods:${paperId}:${evidence.key || evidence.raw || evidence.page}:${evidence.coordinate_precision || "region"}`,
    paperId,
    paperTitle: paperTitle || `Paper ${paperId}`,
    page: evidence.page,
    pageEnd: evidence.page_end || evidence.page,
    section: evidence.section || null,
    precision: evidence.coordinate_precision || "region",
    bboxJson: evidence.bbox_json || null,
    status: evidence.status || evidence.consistency || "",
    quote: evidence.evidence || evidence.raw || "",
  };
}

function normalizeBboxes(bboxJson) {
  if (!bboxJson) return [];
  let raw = bboxJson;
  if (typeof raw === "string") {
    try { raw = JSON.parse(raw); } catch (e) { return []; }
  }
  const list = Array.isArray(raw) ? raw : [raw];
  return list.map(rect => ({
    page: rect && rect.page != null ? Number(rect.page) : null,
    x0: rect && Number(rect.x0),
    y0: rect && Number(rect.y0),
    x1: rect && Number(rect.x1),
    y1: rect && Number(rect.y1),
  })).filter(rect =>
    Number.isFinite(rect.x0) && Number.isFinite(rect.y0) &&
    Number.isFinite(rect.x1) && Number.isFinite(rect.y1) &&
    rect.x1 > rect.x0 && rect.y1 > rect.y0
  );
}

function clearPdfOverlays(host) {
  if (!host) return;
  host.querySelectorAll(".pdf-highlight, .pdf-region-note").forEach(node => node.remove());
}

function addRegionNote(layer, text) {
  const note = document.createElement("div");
  note.className = "pdf-region-note";
  note.textContent = text;
  layer.appendChild(note);
}

function applyPdfCitationTarget(scroller, host, target) {
  clearPdfOverlays(host);
  if (!scroller || !host || !target || !target.page) return;
  const pageEl = host.querySelector(`[data-page="${target.page}"]`);
  if (!pageEl) return;
  const layer = pageEl.querySelector(".pdf-highlight-layer");
  if (!layer) return;

  if (target.precision === "exact") {
    const sourceWidth = Number(pageEl.dataset.sourceWidth);
    const sourceHeight = Number(pageEl.dataset.sourceHeight);
    const rotation = Number(pageEl.dataset.rotation || 0);
    const rects = normalizeBboxes(target.bboxJson)
      .filter(rect => rect.page == null || rect.page === Number(target.page));

    if (rotation !== 0) {
      addRegionNote(layer, "Citation page opened. Exact overlay is disabled for rotated pages.");
    } else if (sourceWidth > 0 && sourceHeight > 0 && rects.length > 0) {
      rects.forEach(rect => {
        const highlight = document.createElement("div");
        highlight.className = "pdf-highlight";
        highlight.title = target.quote ? `Exact citation: ${target.quote}` : "Exact citation highlight";
        highlight.style.left = `${Math.max(0, Math.min(100, (rect.x0 / sourceWidth) * 100))}%`;
        highlight.style.top = `${Math.max(0, Math.min(100, (rect.y0 / sourceHeight) * 100))}%`;
        highlight.style.width = `${Math.max(0, Math.min(100, ((rect.x1 - rect.x0) / sourceWidth) * 100))}%`;
        highlight.style.height = `${Math.max(0, Math.min(100, ((rect.y1 - rect.y0) / sourceHeight) * 100))}%`;
        layer.appendChild(highlight);
      });
    } else {
      addRegionNote(layer, "Citation page opened. Exact coordinates were not usable for this rendered page.");
    }
  } else if (target.precision === "region") {
    addRegionNote(layer, "Region-level citation. The exact passage couldn't be located in this PDF, so its page is shown.");
  }

  pageEl.scrollIntoView({ block: "center", behavior: "smooth" });
}

// Preset highlight colors offered in the picker. MUST stay in sync with the
// server-side ANNOTATION_COLORS allowlist in app/backend/api/app.py.
const HIGHLIGHT_COLORS = ["#ffd54a", "#7bc67e", "#6aa9ff", "#f48fb1", "#ff8a65"];

function hexToRgba(hex, alpha) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
  if (!m) return `rgba(255, 213, 74, ${alpha})`;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

