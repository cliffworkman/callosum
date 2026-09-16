"use strict";

// Must match connector/identity.json's "native_host_name" exactly -- kept in sync by
// tests/test_connector_identity.py rather than a build step, since this extension ships unbundled
// (a raw folder to the stores, or "Load unpacked" for local testing).
const NATIVE_HOST_NAME = "org.callosum.connector";
const PROTOCOL_VERSION = 1;

// Literal, extension-owned request paths. NEVER built from anything the connector host returns
// (steering point 7) -- the host only ever supplies an origin (scheme+host+port) to validate and
// reuse; every actual request path below is one of these two constants.
const CAPTURE_ITEM_PATH = "/capture/item";
const capturePdfPath = (captureId) => `/capture/item/${encodeURIComponent(captureId)}/pdf`;
const CAPTURE_ACTION_HEADER = "x-callosum-capture";
const CAPTURE_ACTION_VALUE = "browser-capture-v1";

// One entry per state the extension ever renders (Part 4). Every branch below resolves to exactly
// one of these keys -- nothing is rendered ad hoc, so this table is the complete UI vocabulary.
export const RESULT_DISPLAY = {
  capturing: { badge: "…", color: "#5b6169", title: "Capturing…" },
  added: { badge: "OK", color: "#1a7f37", title: "Added to your Callosum library." },
  added_pdf_attached: { badge: "OK", color: "#1a7f37", title: "Added to your Callosum library, with the PDF attached." },
  already_present: { badge: "=", color: "#0969da", title: "Already in your Callosum library." },
  already_present_pdf_attached: {
    badge: "=",
    color: "#0969da",
    title: "Already in your Callosum library. The PDF is now attached.",
  },
  attachment_review_required: {
    badge: "!",
    color: "#b35900",
    title: "Added, but the PDF was withheld for review (an existing attachment or annotation).",
  },
  in_trash: { badge: "TR", color: "#57606a", title: "This paper is in your Callosum Trash. Not modified." },
  unresolved: { badge: "?", color: "#b35900", title: "Callosum couldn't resolve this page's identity for review." },
  direct_pdf_unsupported: {
    badge: "!",
    color: "#b35900",
    title: "Callosum couldn't read this PDF directly from the tab. Try it from a page listing instead.",
  },
  callosum_starting: { badge: "…", color: "#5b6169", title: "Callosum is still starting up. Try again shortly." },
  callosum_closed: { badge: "OFF", color: "#57606a", title: "Callosum isn't running. Open Callosum, then try again." },
  host_unavailable: {
    badge: "OFF",
    color: "#57606a",
    title: "Callosum's browser connector isn't responding. Make sure Callosum is installed.",
  },
  version_incompatible: {
    badge: "v?",
    color: "#b35900",
    title: "This extension and your installed Callosum are out of sync. Update one of them.",
  },
  not_eligible_instance: {
    badge: "OFF",
    color: "#57606a",
    title: "Browser capture isn't available on this Callosum instance.",
  },
  pairing_unavailable: {
    badge: "!",
    color: "#b35900",
    title: "Callosum couldn't authorize capture. Try restarting Callosum.",
  },
  failed: { badge: "ERR", color: "#cf222e", title: "Capture failed. Try again." },
};

// Guarded so this module can be imported under plain Node (tests/js/background.test.mjs) without a
// `chrome` global -- registration is a real no-op there, never exercised outside an actual browser.
if (typeof chrome !== "undefined" && chrome.action) {
  chrome.action.onClicked.addListener((tab) => {
    handleCapture(tab).catch(() => render("failed"));
  });
}

async function handleCapture(tab) {
  render("capturing");
  if (!tab || !tab.id || !tab.url) {
    render("failed");
    return;
  }

  const connector = await resolveConnector();
  if (connector.resultKey !== "available") {
    render(connector.resultKey);
    return;
  }

  const { origin, sessionToken } = connector;
  let envelope;
  let pdfBuffer = null;

  if (looksLikePdfUrl(tab.url)) {
    pdfBuffer = await fetchDirectPdfBytes(tab.url);
    if (!pdfBuffer) {
      render("direct_pdf_unsupported");
      return;
    }
    envelope = buildDirectPdfEnvelope(tab);
  } else {
    let extracted;
    try {
      const [injection] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractPageMetadata,
      });
      extracted = injection && injection.result ? injection.result : {};
    } catch {
      extracted = {};
    }
    envelope = buildGenericEnvelope(tab, extracted);
  }

  const outcome = await postCaptureItem(origin, sessionToken, envelope);
  if (!outcome) {
    render("failed");
    return;
  }

  let pdfAttached = false;
  if (pdfBuffer && outcome.pdf_accepted && outcome.capture_id) {
    pdfAttached = await postCapturePdf(origin, sessionToken, outcome.capture_id, pdfBuffer);
  }

  render(resultKeyFor(outcome, pdfAttached));
}

// ---------------------------------------------------------------------------------------------
// Connector resolution
// ---------------------------------------------------------------------------------------------

function sendNativeMessage(message) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendNativeMessage(NATIVE_HOST_NAME, message, (response) => {
        // chrome.runtime.lastError (host missing, manifest not registered, host crashed before
        // replying) and "no response" are exactly the host_unavailable case the connector host's
        // own comments describe as CLIENT-inferred -- it can never emit that state itself, because
        // a host that can't be reached never gets the chance to say so.
        if (chrome.runtime.lastError || !response) {
          resolve(null);
          return;
        }
        resolve(response);
      });
    } catch {
      resolve(null);
    }
  });
}

async function resolveConnector() {
  const response = await sendNativeMessage({ id: crypto.randomUUID(), protocol_version: PROTOCOL_VERSION });
  if (!response) {
    return { resultKey: "host_unavailable" };
  }
  const state = typeof response.runtime_state === "string" ? response.runtime_state : "host_unavailable";
  if (state !== "available") {
    return { resultKey: state in RESULT_DISPLAY ? state : "failed" };
  }
  const origin = validateBackendOrigin(response.backend_base_url);
  const sessionToken = typeof response.session_token === "string" ? response.session_token : "";
  if (!origin || !sessionToken) {
    return { resultKey: "failed" };
  }
  return { resultKey: "available", origin, sessionToken };
}

/// Steering point 7: the connector host necessarily runs on a dynamic port the extension has
/// broad `http://127.0.0.1/*` permission for, so its reply is never trusted blindly. Every field
/// is checked; the returned origin is REBUILT from validated parts only, never the raw string, so
/// nothing the host supplied beyond a bare scheme+host+port can ever reach a fetch() call.
export function validateBackendOrigin(raw) {
  if (typeof raw !== "string" || raw.length === 0) return null;
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }
  if (parsed.protocol !== "http:") return null;
  if (parsed.hostname !== "127.0.0.1") return null;
  if (parsed.username || parsed.password) return null;
  if (parsed.pathname !== "/" && parsed.pathname !== "") return null;
  if (parsed.search || parsed.hash) return null;
  const port = Number(parsed.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return null;
  return `http://127.0.0.1:${port}`;
}

// ---------------------------------------------------------------------------------------------
// Direct-PDF path (Part 3): the fetch happens INSIDE the click handler's async chain, still within
// the activeTab grant issued by this exact gesture -- never deferred to a later wake-up.
// ---------------------------------------------------------------------------------------------

export function looksLikePdfUrl(url) {
  try {
    return new URL(url).pathname.toLowerCase().endsWith(".pdf");
  } catch {
    return false;
  }
}

async function fetchDirectPdfBytes(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const buffer = await response.arrayBuffer();
    const head = new Uint8Array(buffer.slice(0, 5));
    if (head.length < 5 || String.fromCharCode(...head) !== "%PDF-") return null;
    return buffer;
  } catch {
    return null;
  }
}

export function buildDirectPdfEnvelope(tab) {
  return {
    envelope_version: 1,
    source_url: String(tab.url).slice(0, 2000),
    captured_at: new Date().toISOString(),
    producer_kind: "direct-pdf",
    producer_label: "callosum-browser-extension",
    title: filenameFromUrl(tab.url),
    pdf_bytes_from_active_tab: true,
  };
}

export function filenameFromUrl(url) {
  try {
    const path = new URL(url).pathname;
    const last = path.substring(path.lastIndexOf("/") + 1);
    return decodeURIComponent(last) || null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------------------------
// Generic extraction (Part 3): DOI, Highwire citation_*, JSON-LD/schema.org. Runs INSIDE the page
// via chrome.scripting.executeScript -- this function is serialized and injected, so it must be
// fully self-contained (no closures over background.js's own scope).
// ---------------------------------------------------------------------------------------------

export function extractPageMetadata() {
  function metaContent(name) {
    const el = document.querySelector(`meta[name="${name}"]`);
    const value = el ? el.getAttribute("content") : null;
    return value && value.trim() ? value.trim() : null;
  }
  function metaContentAll(name) {
    return Array.from(document.querySelectorAll(`meta[name="${name}"]`))
      .map((el) => el.getAttribute("content"))
      .map((v) => (v ? v.trim() : ""))
      .filter(Boolean);
  }

  const doi = metaContent("citation_doi");
  const title = metaContent("citation_title");
  const authors = metaContentAll("citation_author");
  const containerTitle = metaContent("citation_journal_title") || metaContent("citation_conference_title");
  const year = metaContent("citation_publication_date") || metaContent("citation_date") || metaContent("citation_year");
  const provenance = {};
  if (doi) provenance.doi = "citation_doi";
  if (title) provenance.title = "citation_title";
  if (authors.length) provenance.creators = "citation_author";
  if (containerTitle) provenance.container_title = "citation_journal_title";

  let jsonLd = null;
  let jsonLdUsedFor = [];
  if (!doi || !title) {
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      let parsed;
      try {
        parsed = JSON.parse(script.textContent);
      } catch {
        continue; // malformed JSON-LD is common on the open web; not this extractor's job to fix
      }
      const candidates = Array.isArray(parsed) ? parsed : [parsed];
      const candidate = candidates.find(
        (item) => item && (item["@type"] === "ScholarlyArticle" || item["@type"] === "Article")
      );
      if (candidate) {
        jsonLd = candidate;
        break;
      }
    }
  }
  const ldDoi = jsonLd && typeof jsonLd.identifier === "string" && jsonLd.identifier.startsWith("doi:") ? jsonLd.identifier.slice(4) : null;
  const ldTitle = jsonLd && (jsonLd.headline || jsonLd.name) ? String(jsonLd.headline || jsonLd.name) : null;
  if (!doi && ldDoi) jsonLdUsedFor.push("doi");
  if (!title && ldTitle) jsonLdUsedFor.push("title");
  for (const field of jsonLdUsedFor) provenance[field] = "json-ld";

  return {
    doi: doi || ldDoi || null,
    title: title || ldTitle || document.title || null,
    authors,
    container_title: containerTitle,
    year,
    field_provenance: provenance,
  };
}

export function parseYear(value) {
  if (!value) return null;
  const match = String(value).match(/(1[0-9]{3}|2[0-9]{3})/);
  return match ? Number(match[1]) : null;
}

export function buildGenericEnvelope(tab, extracted) {
  const creators = (extracted.authors || []).slice(0, 500).map((literal) => ({ literal }));
  return {
    envelope_version: 1,
    source_url: String(tab.url).slice(0, 2000),
    captured_at: new Date().toISOString(),
    producer_kind: "generic",
    producer_label: "callosum-browser-extension",
    title: extracted.title || tab.title || null,
    creators,
    container_title: extracted.container_title || null,
    year: parseYear(extracted.year),
    identifiers: extracted.doi ? { doi: extracted.doi } : {},
    field_provenance: extracted.field_provenance || {},
    pdf_bytes_from_active_tab: false,
  };
}

// ---------------------------------------------------------------------------------------------
// Talking to /capture/* directly (the connector host never proxies these -- Part 1: it may
// authorize, never parse or admit). Every URL below is `origin` (validated) + a literal path
// constant; no host- or page-supplied string is ever used as a fetch target.
// ---------------------------------------------------------------------------------------------

async function postCaptureItem(origin, sessionToken, envelope) {
  try {
    const response = await fetch(`${origin}${CAPTURE_ITEM_PATH}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${sessionToken}`,
        [CAPTURE_ACTION_HEADER]: CAPTURE_ACTION_VALUE,
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify(envelope),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function postCapturePdf(origin, sessionToken, captureId, buffer) {
  try {
    const response = await fetch(`${origin}${capturePdfPath(captureId)}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        Authorization: `Bearer ${sessionToken}`,
        [CAPTURE_ACTION_HEADER]: CAPTURE_ACTION_VALUE,
      },
      body: buffer,
    });
    if (!response.ok) return false;
    const result = await response.json();
    return result && result.pdf_accepted === true;
  } catch {
    return false;
  }
}

export function resultKeyFor(outcome, pdfAttached) {
  const status = outcome.status;
  const pdfReason = outcome.pdf_reason;
  if (pdfReason === "attachment_review_required") return "attachment_review_required";
  if (status === "in_trash") return "in_trash";
  if (status === "unresolved_review_required") return "unresolved";
  if (status === "added") return pdfAttached ? "added_pdf_attached" : "added";
  if (status === "already_present") return pdfAttached ? "already_present_pdf_attached" : "already_present";
  return "failed"; // covers "invalid_capture" and any status this extension doesn't yet know
}

// ---------------------------------------------------------------------------------------------
// Rendering: badge + tooltip only (Part 4). No default_popup, no notifications permission -- both
// deliberately unrequested (see README.md's permission table).
// ---------------------------------------------------------------------------------------------

function render(resultKey) {
  const display = RESULT_DISPLAY[resultKey] || RESULT_DISPLAY.failed;
  chrome.action.setBadgeText({ text: display.badge });
  chrome.action.setBadgeBackgroundColor({ color: display.color });
  chrome.action.setTitle({ title: display.title });
}
