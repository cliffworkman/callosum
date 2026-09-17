// Unit tests for background.js's pure logic, using Node's BUILT-IN test runner (node:test) --
// deliberately no new dependency for one extension's worth of tests. Run with:
//   node --test app/desktop-shell/extension
//
// Saved-fixture coverage for extraction (Highwire, JSON-LD, DOI-only, malformed/partial,
// unsupported generic page) and result-state rendering, per the increment's verification plan.
// No network, no real browser, no CI dependency on a live publisher page.

import assert from "node:assert/strict";
import { test } from "node:test";

// extractPageMetadata references the page's `document` global -- exactly as it must, since
// chrome.scripting.executeScript injects it into a real page. A minimal fake covers only the
// query shapes the function actually uses (single/multi meta[name=...], the JSON-LD script tag),
// so the REAL function is exercised verbatim rather than a re-implementation that could drift.
function fakeDocument({ metas = {}, jsonLdBlocks = [], title = "" } = {}) {
  const metaSelector = /^meta\[name="([^"]+)"\]$/;
  function valuesFor(name) {
    const raw = metas[name];
    if (raw === undefined) return [];
    return Array.isArray(raw) ? raw : [raw];
  }
  return {
    title,
    querySelector(selector) {
      const match = selector.match(metaSelector);
      if (!match) return null;
      const values = valuesFor(match[1]);
      return values.length ? { getAttribute: () => values[0] } : null;
    },
    querySelectorAll(selector) {
      const match = selector.match(metaSelector);
      if (match) return valuesFor(match[1]).map((value) => ({ getAttribute: () => value }));
      if (selector === 'script[type="application/ld+json"]') {
        return jsonLdBlocks.map((text) => ({ textContent: text }));
      }
      return [];
    },
  };
}

async function withFakeDocument(doc, fn) {
  const previous = globalThis.document;
  globalThis.document = doc;
  try {
    return await fn();
  } finally {
    if (previous === undefined) delete globalThis.document;
    else globalThis.document = previous;
  }
}

const mod = await import("./background.js");
const {
  validateBackendOrigin,
  looksLikePdfUrl,
  resultKeyFor,
  extractPageMetadata,
  buildDirectPdfEnvelope,
  filenameFromUrl,
  RESULT_DISPLAY,
} = mod;

// ── validateBackendOrigin (steering point 7) ────────────────────────────────────────────────────

test("validateBackendOrigin accepts a bare loopback origin and rebuilds it from parts", () => {
  assert.equal(validateBackendOrigin("http://127.0.0.1:54321"), "http://127.0.0.1:54321");
  assert.equal(validateBackendOrigin("http://127.0.0.1:54321/"), "http://127.0.0.1:54321");
});

test("validateBackendOrigin rejects everything a compromised or buggy host could try", () => {
  const rejected = [
    undefined,
    null,
    "",
    "https://127.0.0.1:1234", // wrong scheme
    "http://localhost:1234", // wrong host -- exact 127.0.0.1 only
    "http://evil.example:1234", // arbitrary hostname
    "http://user:pass@127.0.0.1:1234", // credentials
    "http://127.0.0.1:1234/capture/item", // host-supplied path -- paths are extension-owned constants
    "http://127.0.0.1:1234?x=1", // query
    "http://127.0.0.1:1234#frag", // fragment
    "http://127.0.0.1:0", // out-of-range port
    "http://127.0.0.1:70000", // out-of-range port
    "http://127.0.0.1", // no port at all
    "not a url",
  ];
  for (const candidate of rejected) {
    assert.equal(validateBackendOrigin(candidate), null, `expected rejection for ${JSON.stringify(candidate)}`);
  }
});

// ── looksLikePdfUrl ──────────────────────────────────────────────────────────────────────────────

test("looksLikePdfUrl matches only a .pdf path, case-insensitively, ignoring query/hash", () => {
  assert.equal(looksLikePdfUrl("https://example.org/paper.PDF"), true);
  assert.equal(looksLikePdfUrl("https://example.org/paper.pdf?download=1"), true);
  assert.equal(looksLikePdfUrl("https://example.org/paper.pdf#page=3"), true);
  assert.equal(looksLikePdfUrl("https://example.org/article/123"), false);
  assert.equal(looksLikePdfUrl("https://example.org/pdf-viewer"), false);
  assert.equal(looksLikePdfUrl("not a url"), false);
});

// ── resultKeyFor: the backend's status/pdf_reason vocabulary, exactly as admission.py emits it ──

test("resultKeyFor covers every real admission outcome", () => {
  const cases = [
    [{ status: "added", pdf_reason: "not_offered" }, false, "added"],
    [{ status: "added", pdf_reason: "ok" }, true, "added_pdf_attached"],
    [{ status: "already_present", pdf_reason: "not_offered" }, false, "already_present"],
    [{ status: "already_present", pdf_reason: "ok" }, true, "already_present_pdf_attached"],
    [{ status: "added", pdf_reason: "attachment_review_required" }, false, "attachment_review_required"],
    [{ status: "in_trash", pdf_reason: "not_offered" }, false, "in_trash"],
    [{ status: "unresolved_review_required", pdf_reason: "not_offered" }, false, "unresolved"],
    [{ status: "direct_pdf_identity_unresolved", pdf_reason: "not_offered" }, false, "direct_pdf_identity_unresolved"],
    [{ status: "invalid_capture", pdf_reason: "not_offered" }, false, "failed"],
    [{ status: "some_future_status", pdf_reason: "not_offered" }, false, "failed"], // unknown -> fail visibly, not silently
  ];
  for (const [outcome, pdfAttached, expected] of cases) {
    assert.equal(resultKeyFor(outcome, pdfAttached), expected, JSON.stringify(outcome));
  }
});

test("every resultKeyFor output and every connector runtime_state has a RESULT_DISPLAY entry", () => {
  const resultKeys = ["added", "added_pdf_attached", "already_present", "already_present_pdf_attached",
    "attachment_review_required", "in_trash", "unresolved", "direct_pdf_identity_unresolved", "failed"];
  const connectorRuntimeStates = ["callosum_closed", "callosum_starting", "version_incompatible",
    "not_eligible_instance", "pairing_unavailable", "host_unavailable"];
  for (const key of [...resultKeys, ...connectorRuntimeStates, "capturing", "direct_pdf_unsupported"]) {
    assert.ok(RESULT_DISPLAY[key], `missing RESULT_DISPLAY entry for ${key}`);
    assert.ok(RESULT_DISPLAY[key].title.length > 0);
  }
});

// ── extractPageMetadata: saved fixtures (Highwire, JSON-LD, DOI-only, malformed, unsupported) ──

test("extraction: Highwire citation_* tags are preferred and fully attributed", async () => {
  const doc = fakeDocument({
    metas: {
      citation_doi: "10.1000/example",
      citation_title: "A Highwire-Tagged Paper",
      citation_author: ["Ada Lovelace", "Charles Babbage"],
      citation_journal_title: "Journal of Testing",
      citation_publication_date: "2024/03/01",
    },
  });
  const result = await withFakeDocument(doc, async () => extractPageMetadata());
  assert.equal(result.doi, "10.1000/example");
  assert.equal(result.title, "A Highwire-Tagged Paper");
  assert.deepEqual(result.authors, ["Ada Lovelace", "Charles Babbage"]);
  assert.equal(result.container_title, "Journal of Testing");
  assert.equal(result.year, "2024/03/01");
  assert.equal(result.field_provenance.doi, "citation_doi");
  assert.equal(result.field_provenance.creators, "citation_author");
});

test("extraction: JSON-LD ScholarlyArticle is used only when Highwire tags are absent", async () => {
  const doc = fakeDocument({
    jsonLdBlocks: [
      JSON.stringify({ "@type": "ScholarlyArticle", headline: "A JSON-LD Paper", identifier: "doi:10.2000/ld" }),
    ],
  });
  const result = await withFakeDocument(doc, async () => extractPageMetadata());
  assert.equal(result.doi, "10.2000/ld");
  assert.equal(result.title, "A JSON-LD Paper");
  assert.equal(result.field_provenance.doi, "json-ld");
  assert.equal(result.field_provenance.title, "json-ld");
});

test("extraction: a bare DOI with no title still resolves, generic page falls back to document.title", async () => {
  const doc = fakeDocument({ metas: { citation_doi: "10.3000/bare" }, title: "Fallback Page Title" });
  const result = await withFakeDocument(doc, async () => extractPageMetadata());
  assert.equal(result.doi, "10.3000/bare");
  assert.equal(result.title, "Fallback Page Title");
  assert.equal(result.field_provenance.title, undefined); // never falsely attributed to a tag it didn't come from
});

test("extraction: malformed JSON-LD is skipped without throwing, never crashes the extractor", async () => {
  const doc = fakeDocument({ jsonLdBlocks: ["{not valid json", '{"@type": "ScholarlyArticle", "headline": "Recovered"}'] });
  const result = await withFakeDocument(doc, async () => extractPageMetadata());
  assert.equal(result.title, "Recovered");
});

test("extraction: an unsupported generic page with no signals at all yields an honest empty result", async () => {
  const doc = fakeDocument({ title: "Just A Blog Post" });
  const result = await withFakeDocument(doc, async () => extractPageMetadata());
  assert.equal(result.doi, null);
  assert.equal(result.title, "Just A Blog Post");
  assert.deepEqual(result.authors, []);
  assert.deepEqual(result.field_provenance, {});
});

// ── direct-PDF envelope shape ────────────────────────────────────────────────────────────────────

test("buildDirectPdfEnvelope marks pdf_bytes_from_active_tab and derives a filename title", () => {
  const envelope = buildDirectPdfEnvelope({ url: "https://example.org/papers/final%20draft.pdf" });
  assert.equal(envelope.producer_kind, "direct-pdf");
  assert.equal(envelope.pdf_bytes_from_active_tab, true);
  assert.equal(envelope.title, "final draft.pdf");
  assert.equal(envelope.envelope_version, 1);
});

test("filenameFromUrl handles a bare host with no path", () => {
  assert.equal(filenameFromUrl("https://example.org/"), null);
  assert.equal(filenameFromUrl("not a url"), null);
});
