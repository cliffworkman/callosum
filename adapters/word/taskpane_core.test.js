/*
 * Pure-logic unit tests for the Word add-in (run: `node --test "adapters/word/*.test.js"`).
 * Uses Node's built-in test runner — no new dependency, no browser, no Office host. This is the primary
 * automated check for the add-in, since there is no headless Word to exercise the Office.js glue.
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const core = require("./taskpane_core.js");

// ---- search rows (SP1) ----
test("authorLabel: single / multiple / empty", () => {
  assert.strictEqual(core.authorLabel(["Lovelace, Ada"]), "Lovelace");
  assert.strictEqual(core.authorLabel(["Lovelace, Ada", "Babbage, Charles"]), "Lovelace et al.");
  assert.strictEqual(core.authorLabel([]), "Unknown");
  assert.strictEqual(core.authorLabel(null), "Unknown");
});

test("formatSearchRows: 'Author (Year) — Title' keyed by id; drops id-less; non-array → []", () => {
  assert.deepStrictEqual(
    core.formatSearchRows([
      { id: 7, title: "Notes on the Analytical Engine", authors: ["Lovelace, Ada"], year: 1843 },
      { id: 9, title: "On Computable Numbers", authors: ["Turing, Alan", "Church, Alonzo"], year: 1936 },
      { title: "No id", authors: ["X, Y"], year: 2020 },
    ]),
    [
      { id: 7, label: "Lovelace (1843) — Notes on the Analytical Engine" },
      { id: 9, label: "Turing et al. (1936) — On Computable Numbers" },
    ],
  );
  assert.deepStrictEqual(core.formatSearchRows(null), []);
});

test("suggestion details expose bounded evidence, honest stance/reason, and editable auto locator", () => {
  const item = {
    paper_id: 9,
    attachment_id: 4,
    chunk_id: 12,
    quote: `  ${"evidence ".repeat(30)}  `,
    page_start: 7,
    page_end: 9,
    match_score: 0.68,
    stance: { probs: { support: 0.6, mention: 0.3, contrast: 0.1 } },
  };
  assert.strictEqual(core.stanceBreakdownText(item.stance), "Stance signal: 60% support · 30% mention · 10% contrast");
  assert.strictEqual(core.suggestionIsWeakEvidence(item), false);
  assert.strictEqual(core.suggestionAutoLocator(item), "7-9");
  assert.deepStrictEqual(core.suggestionDetail(item, undefined, false), {
    quote: item.quote,
    page: "Pages 7–9",
    stance: "Stance signal: 60% support · 30% mention · 10% contrast",
    reason: "Retrieved by local semantic similarity — approximately 68% match to your selected text.",
    weak: false,
    locator: "7-9",
    canOpenPdf: true,
  });
  const evidence = core.suggestionEvidenceFields(item);
  assert.strictEqual(evidence.evidence_chunk_id, 12);
  assert.strictEqual(evidence.evidence_page_start, 7);
  assert.strictEqual(evidence.evidence_page_end, 9);
  assert.ok(evidence.evidence_snippet.endsWith("…"));
  assert.ok(evidence.evidence_snippet.length <= 151);
  assert.deepStrictEqual(core.suggestionAssemblyFields(item, "42", true), {
    ...evidence, locator: "42", label: "page",
  });
  assert.deepStrictEqual(core.suggestionAssemblyFields(item, "", true), evidence);
  assert.strictEqual(core.suggestionAssemblyFields(item, "x".repeat(100), true).locator.length, 80);
});

test("suggestion details fail soft on missing signals and build only bounded same-origin PDF deep links", () => {
  const weak = { paper_id: 2, attachment_id: 3, page_start: 5, match_score: 0.2 };
  assert.strictEqual(core.stanceBreakdownText(null), "No stance signal for this passage.");
  assert.strictEqual(core.suggestionIsWeakEvidence(weak), true);
  assert.strictEqual(core.suggestionOpenPdfPath(weak), "/?open_paper=2&page=5&precision=region");
  assert.strictEqual(core.suggestionOpenPdfPath({ paper_id: 2 }), null);
  assert.strictEqual(core.suggestionOpenPdfPath({ paper_id: "2", attachment_id: 3 }), null);
  assert.deepStrictEqual(core.suggestionEvidenceFields({ quote: "   " }), {});
  assert.strictEqual(core.suggestionAutoLocator({ page_start: 9, page_end: 4 }), "9");
  assert.deepStrictEqual(core.suggestionEvidenceFields({ quote: "x", page_start: 9, page_end: 4 }), {
    evidence_snippet: "x", evidence_page_start: 9,
  });
});

test("saved evidence normalization accepts only identified highlights and preserves display facts", () => {
  const rows = core.normalizeEvidenceAnnotations([
    { id: 7, anchor_text: "  Exact\nquoted   passage ", note: " My note ", page: 4, attachment_id: 9 },
    { id: 0, anchor_text: "bad id" }, { id: 8, anchor_text: "   " }, null,
  ]);
  assert.deepStrictEqual(rows, [{
    id: 7, quote: "Exact quoted passage", note: "My note", page: 4,
  }]);
  assert.match(core.evidenceAnnotationRows(rows)[0].label, /^p\.4 — “Exact quoted passage”  \[note: My note\]$/);
  assert.deepStrictEqual(core.normalizeEvidenceAnnotations({}), []);
});

test("saved evidence formats keep quote-only uncited and use the author's note only when requested", () => {
  const annotation = { id: 7, quote: "Exact passage", note: "Author paraphrase", page: 4 };
  assert.strictEqual(core.evidenceBodyText(annotation, "quote_only"), "“Exact passage”");
  assert.strictEqual(core.evidenceBodyText(annotation, "quote_cite"), "“Exact passage”");
  assert.strictEqual(core.evidenceBodyText(annotation, "paraphrase_cite"), "Author paraphrase");
  assert.strictEqual(core.evidenceBodyText(annotation, "card"), "“Exact passage” — Author paraphrase");
  assert.strictEqual(
    core.evidenceBodyText({ id: 8, quote: "Fallback quote", note: "" }, "paraphrase_cite"),
    "“Fallback quote”",
  );
  assert.throws(() => core.evidenceBodyText(annotation, "mystery"), /Unknown evidence insertion format/);
});

test("saved evidence fails explicitly instead of silently truncating insertion content", () => {
  const tooLong = { id: 7, quote: "x".repeat(core.EVIDENCE_QUOTE_MAX + 1), note: "" };
  const detail = core.evidenceAnnotationDetail(tooLong);
  assert.strictEqual(detail.valid, false);
  assert.match(detail.reason, /exceeds the 20000-character/);
  assert.throws(() => core.evidenceBodyText(tooLong, "quote_only"), /exceeds/);
});

test("saved evidence stance checks are explicit, exact, and bounded", () => {
  const annotation = { quote: "Observed passage." };
  assert.deepStrictEqual(core.buildEvidenceStanceRequest("  Draft claim. ", annotation), {
    sentence: "Draft claim.", passage: "Observed passage.",
  });
  assert.strictEqual(core.buildEvidenceStanceRequest("", annotation), null);
  assert.strictEqual(core.buildEvidenceStanceRequest("Claim", { quote: "" }), null);
  assert.throws(
    () => core.buildEvidenceStanceRequest("x".repeat(core.EVIDENCE_STANCE_TEXT_MAX + 1), annotation),
    /at most 4000/,
  );
});

test("saved evidence citation fields retain annotation/page provenance and bound locator/snippet", () => {
  const fields = core.evidenceAssemblyFields({
    id: 7, page: 4, quote: "word ".repeat(50).trim(), note: "",
  }, " 12 ");
  assert.strictEqual(fields.evidence_annotation_id, 7);
  assert.strictEqual(fields.evidence_page_start, 4);
  assert.strictEqual(fields.evidence_page_end, 4);
  assert.ok(fields.evidence_snippet.endsWith("…"));
  assert.ok(fields.evidence_snippet.length <= 151);
  assert.strictEqual(fields.locator, "12");
  assert.strictEqual(fields.label, "page");
  const item = core.buildClusterItems([{ csl: { id: "callosum-1" }, ...fields }])[0];
  assert.strictEqual(item.evidence_annotation_id, 7);
  assert.strictEqual(core.assemblyRowFromDecodedItem(item).evidence_annotation_id, 7);
});

test("firstCslRecord: first element of the export array, else null", () => {
  assert.deepStrictEqual(core.firstCslRecord([{ id: "callosum-1" }, { id: "callosum-2" }]), { id: "callosum-1" });
  assert.strictEqual(core.firstCslRecord([]), null);
  assert.strictEqual(core.firstCslRecord(null), null);
});

// ---- live-citation storage round-trip (SP2; short-reference redesign) ----
test("legacy encode/decodeCitationTag: remains readable for migration, including unicode", () => {
  const items = [{ id: "callosum-1", title: "Über Ästhetik", author: [{ family: "Uğurlar" }] }];
  const tag = core.encodeCitationTag(items);
  assert.ok(core.isCitationTag(tag));
  assert.deepStrictEqual(core.decodeCitationTag(tag), items);
});

test("current citation tag contains only a bounded opaque Custom XML Part reference", () => {
  const id = "{01234567-89AB-CDEF-0123-456789ABCDEF}";
  const tag = core.encodeCitationReferenceTag(id);
  assert.strictEqual(core.isCitationTag(tag), true);
  assert.strictEqual(core.isLegacyCitationTag(tag), false);
  assert.strictEqual(core.citationReferenceId(tag), id);
  assert.ok(tag.length < 100);
  assert.strictEqual(tag.includes("A very long scholarly title"), false);
  assert.throws(() => core.encodeCitationReferenceTag(""), /invalid citation XML part id/);
  assert.throws(() => core.encodeCitationReferenceTag("x".repeat(257)), /invalid citation XML part id/);
  assert.strictEqual(core.citationReferenceId(core.CITATION_PREFIX + " xml:%"), null);
});

test("Custom XML citation payload round-trips exact unicode CSL-JSON without putting it in the tag", () => {
  const items = [{ id: "callosum-1", title: "Über Ästhetik", author: [{ family: "Uğurlar" }] }];
  const xml = core.encodeCitationXml(items);
  const tag = core.encodeCitationReferenceTag("part-1");
  assert.deepStrictEqual(core.decodeCitationXml(xml), items);
  assert.strictEqual(tag.includes(items[0].title), false);
  assert.deepStrictEqual(core.citationItems({ tag, items }), items);
});

test("Custom XML citation decoder fails closed on foreign schema, malformed payload, and empty items", () => {
  const valid = core.encodeCitationXml([{ id: "callosum-1" }]);
  assert.strictEqual(core.decodeCitationXml(valid.replace(core.CITATION_XML_NAMESPACE, "https://foreign.test")), null);
  assert.strictEqual(core.decodeCitationXml(valid.replace('version="1"', 'version="2"')), null);
  assert.strictEqual(core.decodeCitationXml(valid.replace(/<payload[^>]*>.*<\/payload>/, '<payload encoding="base64">!</payload>')), null);
  assert.throws(() => core.encodeCitationXml([]), /citation items are required/);
});

test("isCitationTag: only the prefix; bibliography + arbitrary tags are not citations", () => {
  assert.ok(core.isCitationTag(core.encodeCitationTag([{ id: "x" }])));
  assert.strictEqual(core.isCitationTag(core.BIB_TAG), false);
  assert.strictEqual(core.isCitationTag("Heading 1"), false);
  assert.strictEqual(core.isCitationTag(null), false);
});

test("decodeCitationTag: non-citation / malformed / empty-items → null (never guesses)", () => {
  assert.strictEqual(core.decodeCitationTag("Heading 1"), null);
  assert.strictEqual(core.decodeCitationTag(core.CITATION_PREFIX + " not-base64!!"), null);
  assert.strictEqual(core.decodeCitationTag(core.encodeCitationTag([])), null);
  assert.strictEqual(core.decodeCitationTag(core.encodeCitationReferenceTag("part-1")), null);
});

// ---- reliable paper-id tracking (inc 512) ----
test("stampCallosumId: overwrites .id to 'callosum-<paperId>'; never mutates the input record", () => {
  const csl = { id: "some-zotero-key", title: "Notes" };
  const stamped = core.stampCallosumId(csl, 7);
  assert.deepStrictEqual(stamped, { id: "callosum-7", title: "Notes" });
  assert.strictEqual(csl.id, "some-zotero-key"); // input untouched
});

test("extractPaperId: strips the prefix; absent prefix (pre-fix/foreign id) → null, never guesses", () => {
  assert.strictEqual(core.extractPaperId("callosum-7"), "7");
  assert.strictEqual(core.extractPaperId("some-zotero-key"), null);
  assert.strictEqual(core.extractPaperId(null), null);
  assert.strictEqual(core.extractPaperId(undefined), null);
});

// ---- render-document request + response (SP2) ----
test("buildDocumentRequest: positional citationIDs in document order + style/locale", () => {
  assert.deepStrictEqual(
    core.buildDocumentRequest([[{ id: "callosum-1" }], [{ id: "callosum-2" }]], "ieee", "en-GB"),
    {
      citations: [
        { citationID: "c0", items: [{ id: "callosum-1" }] },
        { citationID: "c1", items: [{ id: "callosum-2" }] },
      ],
      style: "ieee",
      locale: "en-GB",
    },
  );
  assert.deepStrictEqual(core.buildDocumentRequest([], undefined, undefined), {
    citations: [], style: "apa", locale: "en-US",
  });
});

test("buildDocumentRequest: native note clusters preserve one-based noteIndex, including equal indexes", () => {
  assert.deepStrictEqual(
    core.buildDocumentRequest([
      { items: [{ id: "callosum-1" }], noteIndex: 1 },
      { items: [{ id: "callosum-2" }], noteIndex: 1 },
      { items: [{ id: "callosum-1" }], noteIndex: 3 },
    ], "chicago-notes-bibliography", "en-US").citations,
    [
      { citationID: "c0", items: [{ id: "callosum-1" }], noteIndex: 1 },
      { citationID: "c1", items: [{ id: "callosum-2" }], noteIndex: 1 },
      { citationID: "c2", items: [{ id: "callosum-1" }], noteIndex: 3 },
    ],
  );
});

test("placementIssue: note and in-text styles fail closed on incompatible native placement", () => {
  assert.strictEqual(core.placementIssue([{ location: "inline" }], "author-date", "footnote"), null);
  assert.match(core.placementIssue([{ location: "footnote" }], "author-date", "footnote"), /in-text citation style/);
  assert.strictEqual(core.placementIssue([
    { location: "footnote" }, { location: "footnote" },
  ], "note", "footnote"), null);
  assert.match(core.placementIssue([{ location: "inline" }], "note", "footnote"), /inline Callosum citations/);
  assert.match(core.placementIssue([
    { location: "footnote" }, { location: "endnote" },
  ], "note", "footnote"), /split between footnotes and endnotes/);
  assert.match(core.placementIssue([{ location: "endnote" }], "note", "footnote"), /set to footnotes/);
  assert.strictEqual(core.normalizeNotePreference("ENDNOTE"), "endnote");
  assert.strictEqual(core.normalizeNotePreference("anything"), "footnote");
  assert.strictEqual(core.bodyTypeLocation("MainDoc"), "inline");
  assert.strictEqual(core.bodyTypeLocation("Footnote"), "footnote");
  assert.strictEqual(core.bodyTypeLocation("Endnote"), "endnote");
  assert.strictEqual(core.bodyTypeLocation("Header"), null);
});

test("inTextResults: the in-text strings in order; bibliographyText: the joined block", () => {
  const resp = {
    citations: [{ citationID: "c0", text: "[1]" }, { citationID: "c1", text: "[2]" }],
    bibliography_text: "Lovelace, A. (1843)…\nTuring, A. (1936)…",
  };
  assert.deepStrictEqual(core.inTextResults(resp), ["[1]", "[2]"]);
  assert.strictEqual(core.bibliographyText(resp), "Lovelace, A. (1843)…\nTuring, A. (1936)…");
  assert.deepStrictEqual(core.inTextResults(null), []);
  assert.strictEqual(core.bibliographyText({}), "");
});

// ---- suggest-from-the-sentence (SP3) ----
test("pickQueryText: selection wins, else the paragraph, else empty", () => {
  assert.strictEqual(core.pickQueryText("  the selected sentence  ", "the whole para"), "the selected sentence");
  assert.strictEqual(core.pickQueryText("   ", "the whole para"), "the whole para");
  assert.strictEqual(core.pickQueryText("", ""), "");
  assert.strictEqual(core.pickQueryText(null, null), "");
});

test("buildSuggestRequest: caps text at 4000, default top_k 8, evaluate true", () => {
  const big = "x".repeat(5000);
  const req = core.buildSuggestRequest(big, undefined);
  assert.strictEqual(req.text.length, 4000);
  assert.strictEqual(req.top_k, 8);
  assert.strictEqual(req.evaluate, true);
  assert.strictEqual(core.buildSuggestRequest("claim", 5).top_k, 5);
});

test("formatSuggestRows: '[stance] Author Year · match — quote' keyed by paper_id; missing stance → [?]; drops id-less", () => {
  const rows = core.formatSuggestRows([
    { paper_id: 7, author: "Lovelace", year: 1843, match_score: 0.8234, quote: "the engine can be made to act",
      stance: { label: "support", confidence: 0.9 } },
    { paper_id: 9, author: "Turing", year: 1936, match_score: 0.5, quote: "a number is computable", stance: null },
    { author: "NoId", year: 2020, match_score: 0.4 },
  ]);
  assert.deepStrictEqual(rows, [
    { id: 7, label: '[support] Lovelace 1843 · match 0.82 — "the engine can be made to act…"' },
    { id: 9, label: '[?] Turing 1936 · match 0.50 — "a number is computable…"' },
  ]);
  assert.deepStrictEqual(core.formatSuggestRows(null), []);
});

// ---- citation composer (inc 509): grouped citations + locators/prefix/suffix/suppress-author/author-only ----
test("LOCATOR_LABELS: the 19-value CSL vocabulary, matching callosum_cite.py's CSL_LOCATOR_LABELS", () => {
  assert.strictEqual(core.LOCATOR_LABELS.length, 19);
  assert.ok(core.LOCATOR_LABELS.includes("page"));
  assert.ok(core.LOCATOR_LABELS.includes("volume"));
});

test("itemOverrides: strips default/empty/false values; never emits a falsy key", () => {
  assert.deepStrictEqual(core.itemOverrides({ csl: {}, row: "x" }), {});
  assert.deepStrictEqual(
    core.itemOverrides({ locator: "5", label: "page", "suppress-author": false, "author-only": true }),
    { locator: "5", label: "page", "author-only": true },
  );
  assert.deepStrictEqual(core.itemOverrides(null), {});
});

test("buildClusterItems: merges overrides and bounded evidence fields into each CSL record, in order", () => {
  const assembly = [
    {
      csl: { id: "callosum-1", title: "A" }, locator: "5", label: "page",
      evidence_chunk_id: 7, evidence_snippet: "Matched evidence",
    },
    { csl: { id: "callosum-2", title: "B" } },
  ];
  assert.deepStrictEqual(core.buildClusterItems(assembly), [
    {
      id: "callosum-1", title: "A", locator: "5", label: "page",
      evidence_chunk_id: 7, evidence_snippet: "Matched evidence",
    },
    { id: "callosum-2", title: "B" },
  ]);
  assert.deepStrictEqual(core.buildClusterItems([]), []);
  assert.deepStrictEqual(core.buildClusterItems(null), []);
});

test("buildClusterItems: tampered evidence metadata is bounded and invalid identities are dropped", () => {
  const [item] = core.buildClusterItems([{
    csl: { id: "callosum-1" },
    evidence_chunk_id: -1,
    evidence_page_start: "2",
    evidence_snippet: `  ${"word ".repeat(80)}  `,
    evidence_unrecognized: "not copied",
  }]);
  assert.deepStrictEqual(Object.keys(item).sort(), ["evidence_snippet", "id"]);
  assert.ok(item.evidence_snippet.endsWith("…"));
  assert.ok(item.evidence_snippet.length <= 151);
});

test("cslRecordRow: 'Author (Year) — Title' from a raw CSL-JSON record; multi-author → et al.; missing → Unknown/Untitled", () => {
  assert.strictEqual(
    core.cslRecordRow({ author: [{ family: "Lovelace" }], issued: { "date-parts": [[1843]] }, title: "Notes" }),
    "Lovelace (1843) — Notes",
  );
  assert.strictEqual(
    core.cslRecordRow({ author: [{ family: "Turing" }, { family: "Church" }], title: "On Computable Numbers" }),
    "Turing et al. — On Computable Numbers",
  );
  assert.strictEqual(core.cslRecordRow({}), "Unknown — Untitled");
});

test("formatAssemblyRow: appends a compact '[...]' override summary; no overrides → the bare row", () => {
  assert.strictEqual(core.formatAssemblyRow({ row: "Lovelace (1843) — Notes" }), "Lovelace (1843) — Notes");
  assert.strictEqual(
    core.formatAssemblyRow({ row: "Lovelace (1843) — Notes", locator: "5", label: "page", suffix: "emphasis mine" }),
    'Lovelace (1843) — Notes  [page 5, suffix "emphasis mine"]',
  );
  assert.strictEqual(
    core.formatAssemblyRow({ row: "X", locator: "3", "suppress-author": true }),
    "X  [loc. 3, no author]",
  );
});

test("assemblyRowFromDecodedItem: round-trips buildClusterItems' output back into an assembly row", () => {
  const decoded = {
    id: "callosum-1", title: "Notes", author: [{ family: "Lovelace" }], locator: "5", label: "page",
    evidence_page_start: 5, evidence_snippet: "Matched evidence",
  };
  const row = core.assemblyRowFromDecodedItem(decoded);
  assert.deepStrictEqual(row.csl, { id: "callosum-1", title: "Notes", author: [{ family: "Lovelace" }] });
  assert.strictEqual(row.locator, "5");
  assert.strictEqual(row.label, "page");
  assert.strictEqual(row.evidence_page_start, 5);
  assert.strictEqual(row.evidence_snippet, "Matched evidence");
  assert.strictEqual(row.row, "Lovelace — Notes");
  // Round-trip: building cluster items from the reconstructed row reproduces the original decoded item.
  assert.deepStrictEqual(core.buildClusterItems([row]), [decoded]);
});

// ---- Document diagnostics (inc 512) ----
test("summarizeDiagnostics: a clean document — citations resolve, bibliography present, nothing flagged", () => {
  const tags = [
    core.encodeCitationTag([{ id: "callosum-1", title: "A" }]),
    core.encodeCitationTag([{ id: "callosum-2", title: "B" }, { id: "callosum-3", title: "C" }]),
    core.BIB_TAG,
  ];
  const report = core.summarizeDiagnostics(tags, [], []); // nothing missing -- every cited paper resolved
  assert.deepStrictEqual(report, {
    citationCount: 2,
    malformedCount: 0,
    unresolvableItemCount: 0,
    distinctPaperIds: ["1", "2", "3"],
    orphanedPaperIds: [],
    bibliography: "ok",
    sectionBibliographyCount: 0,
    damagedSectionBibliographyCount: 0,
    retractionFlagged: [],
  });
});

test("summarizeDiagnostics: malformed tags counted separately; unrelated (non-Callosum) tags ignored entirely", () => {
  const tags = [core.CITATION_PREFIX + " not-base64!!", "Heading 1", "SomeOtherAddin_Field"];
  const report = core.summarizeDiagnostics(tags, [], []);
  assert.strictEqual(report.citationCount, 1); // the malformed one IS a citation tag, just undecodable
  assert.strictEqual(report.malformedCount, 1);
  assert.strictEqual(report.bibliography, "missing"); // citations exist, no bibliography tag
});

test("summarizeDiagnostics: resolved current records work; missing Custom XML data is malformed", () => {
  const goodTag = core.encodeCitationReferenceTag("part-good");
  const missingTag = core.encodeCitationReferenceTag("part-missing");
  const report = core.summarizeDiagnostics([
    { tag: goodTag, items: [{ id: "callosum-7", title: "Current" }] },
    { tag: missingTag, items: null },
    { tag: core.BIB_TAG, items: null },
  ], [], []);
  assert.strictEqual(report.citationCount, 2);
  assert.strictEqual(report.malformedCount, 1);
  assert.deepStrictEqual(report.distinctPaperIds, ["7"]);
  assert.strictEqual(report.bibliography, "ok");
});

test("summarizeDiagnostics: no citations at all → bibliography is n/a, not 'missing'", () => {
  assert.strictEqual(core.summarizeDiagnostics([], [], []).bibliography, "n/a");
  assert.strictEqual(core.summarizeDiagnostics(["Heading 1"], [], []).bibliography, "n/a");
});

test("summarizeDiagnostics: a pre-fix/foreign id (no callosum- prefix) counts as unresolvable, not orphaned", () => {
  const tags = [core.encodeCitationTag([{ id: "some-zotero-key", title: "Old" }])];
  const report = core.summarizeDiagnostics(tags, [], []);
  assert.strictEqual(report.unresolvableItemCount, 1);
  assert.deepStrictEqual(report.distinctPaperIds, []); // never guessed a paper id for it
  assert.deepStrictEqual(report.orphanedPaperIds, []);
});

test("summarizeDiagnostics: a resolvable id confirmed missing (deleted OR trashed) is orphaned", () => {
  const tags = [core.encodeCitationTag([{ id: "callosum-99", title: "Deleted or trashed paper" }])];
  const report = core.summarizeDiagnostics(tags, [99], []); // 99 came back missing from the per-id existence check
  assert.deepStrictEqual(report.orphanedPaperIds, ["99"]);
});

test("summarizeDiagnostics: retraction-flagged papers surface by distinct id; 'none'/'unchecked' don't flag", () => {
  const tags = [
    core.encodeCitationTag([{ id: "callosum-1", title: "A" }]),
    core.encodeCitationTag([{ id: "callosum-2", title: "B" }]),
  ];
  const checked = [
    { paper_id: 1, status: "retracted", nature: "Retraction", date: "2020-01-01", notice_url: null, sources: [] },
    { paper_id: 2, status: "none" },
  ];
  const report = core.summarizeDiagnostics(tags, [], checked); // both papers exist -- nothing missing
  assert.deepStrictEqual(report.retractionFlagged, [checked[0]]);
});

// ---- Citation-coverage audit (inc 528) ----
const coverageProse = (label, words = 15) => Array.from({ length: words }, (_value, i) => `${label}${i}`).join(" ");

test("summarizeCitationCoverage: flags exactly three consecutive substantive uncited paragraphs", () => {
  const report = core.summarizeCitationCoverage([
    { text: coverageProse("a"), outlineLevel: 10 },
    { text: coverageProse("b"), outlineLevel: 10 },
    { text: coverageProse("c"), outlineLevel: 10 },
  ]);
  assert.strictEqual(report.paragraphCount, 3);
  assert.strictEqual(report.substantiveParagraphCount, 3);
  assert.strictEqual(report.stretchCount, 1);
  assert.deepStrictEqual(report.stretches[0], {
    startParagraph: 1, endParagraph: 3, paragraphCount: 3, preview: coverageProse("a"),
  });
});

test("summarizeCitationCoverage: citation anchors and short transitions break a run", () => {
  const report = core.summarizeCitationCoverage([
    { text: coverageProse("a") }, { text: coverageProse("b") },
    { text: coverageProse("c"), hasCitation: true },
    { text: coverageProse("d") }, { text: "Short transition." }, { text: coverageProse("e") },
  ]);
  assert.strictEqual(report.citationAnchoredParagraphCount, 1);
  assert.strictEqual(report.stretchCount, 0);
});

test("summarizeCitationCoverage: headings, tables, and managed bibliography rows never count as prose", () => {
  const report = core.summarizeCitationCoverage([
    { text: coverageProse("heading"), outlineLevel: 1 },
    { text: coverageProse("table"), outlineLevel: 10, tableNestingLevel: 1 },
    { text: coverageProse("bib"), outlineLevel: 10, excluded: true },
    { text: coverageProse("a"), outlineLevel: 10 },
    { text: coverageProse("b"), outlineLevel: 10 },
  ]);
  assert.strictEqual(report.substantiveParagraphCount, 2);
  assert.strictEqual(report.stretchCount, 0);
});

test("summarizeCitationCoverage: reports document paragraph numbers and bounds stored previews/results", () => {
  const rows = [];
  for (let run = 0; run < 22; run += 1) {
    const long = `${coverageProse(`run${run}`, 20)} ${"x".repeat(200)}`;
    rows.push({ paragraphNumber: run * 4 + 2, text: long });
    rows.push({ paragraphNumber: run * 4 + 3, text: coverageProse("b") });
    rows.push({ paragraphNumber: run * 4 + 4, text: coverageProse("c") });
    rows.push({ paragraphNumber: run * 4 + 5, text: "Break." });
  }
  const report = core.summarizeCitationCoverage(rows);
  assert.strictEqual(report.stretchCount, 22);
  assert.strictEqual(report.stretches.length, core.MAX_COVERAGE_STRETCHES);
  assert.strictEqual(report.stretchesTruncated, true);
  assert.deepStrictEqual(
    [report.stretches[0].startParagraph, report.stretches[0].endParagraph], [2, 4],
  );
  assert.ok(report.stretches[0].preview.length <= 151);
});

// ---- Citations-in-this-document panel (inc 516) ----
test("buildCitationsPanelEntries: the same paper cited solo, then again inside a grouped citation, is one entry", () => {
  const tags = [
    core.encodeCitationTag([{ id: "callosum-1", title: "Notes", author: [{ family: "Lovelace" }] }]), // index 0
    core.encodeCitationTag([{ id: "callosum-2", title: "B" }, { id: "callosum-1", title: "Notes", author: [{ family: "Lovelace" }] }]), // index 1
  ];
  const entries = core.buildCitationsPanelEntries(tags);
  assert.strictEqual(entries.length, 2);
  const lovelace = entries.find((e) => e.paperId === "1");
  assert.strictEqual(lovelace.occurrenceCount, 2);
  assert.deepStrictEqual(lovelace.positions, [0, 1]);
  assert.strictEqual(lovelace.row, "Lovelace — Notes");
});

test("buildCitationsPanelEntries: first occurrence retains compact Suggest evidence for later audit", () => {
  const tags = [core.encodeCitationTag([{
    id: "callosum-7", title: "Evidence",
    evidence_page_start: 4, evidence_page_end: 5, evidence_snippet: "Matched passage",
  }])];
  const entries = core.buildCitationsPanelEntries(tags);
  assert.deepStrictEqual(entries[0].evidence, { page: "4–5", snippet: "Matched passage" });
  assert.strictEqual(core.citationEvidenceFromItem({ evidence_snippet: "" }), null);
});

test("buildCitationsPanelEntries: resolved current storage records group like legacy tags", () => {
  const entries = core.buildCitationsPanelEntries([
    { tag: core.encodeCitationReferenceTag("part-1"), items: [{ id: "callosum-1", title: "A" }] },
    { tag: core.encodeCitationReferenceTag("part-2"), items: [{ id: "callosum-1", title: "A" }] },
  ]);
  assert.strictEqual(entries.length, 1);
  assert.strictEqual(entries[0].occurrenceCount, 2);
  assert.deepStrictEqual(entries[0].positions, [0, 1]);
});

test("buildCitationsPanelEntries: unresolvable (pre-fix) items each get their own singleton entry, never grouped", () => {
  const tags = [
    core.encodeCitationTag([{ id: "some-zotero-key", title: "Old" }]),
    core.encodeCitationTag([{ id: "some-zotero-key", title: "Old" }]), // identical CSL, still NOT merged
  ];
  const entries = core.buildCitationsPanelEntries(tags);
  assert.strictEqual(entries.length, 2);
  assert.ok(entries.every((e) => e.paperId === null && e.occurrenceCount === 1));
});

test("buildCitationsPanelEntries: malformed citation tags are skipped but still consume a position slot", () => {
  const tags = [
    core.CITATION_PREFIX + " not-base64!!", // malformed, index 0 -- consumes a slot
    core.encodeCitationTag([{ id: "callosum-1", title: "A" }]), // index 1
  ];
  const entries = core.buildCitationsPanelEntries(tags);
  assert.strictEqual(entries.length, 1);
  assert.deepStrictEqual(entries[0].positions, [1]); // NOT [0] -- the malformed one still occupied index 0
});

test("buildCitationsPanelEntries: non-citation tags (bibliography, arbitrary) are ignored entirely", () => {
  const tags = ["Heading 1", core.BIB_TAG, core.encodeCitationTag([{ id: "callosum-1", title: "A" }])];
  const entries = core.buildCitationsPanelEntries(tags);
  assert.strictEqual(entries.length, 1);
  assert.deepStrictEqual(entries[0].positions, [0]); // the citation is the first (and only) CITATION-tagged control
});

test("buildCitationsPanelEntries: entries are ordered by first occurrence", () => {
  const tags = [
    core.encodeCitationTag([{ id: "callosum-2", title: "B" }]),
    core.encodeCitationTag([{ id: "callosum-1", title: "A" }]),
    core.encodeCitationTag([{ id: "callosum-2", title: "B" }]),
  ];
  const entries = core.buildCitationsPanelEntries(tags);
  assert.deepStrictEqual(entries.map((e) => e.paperId), ["2", "1"]);
});

test("mergePanelEntryStatus: flags orphaned + retraction-flagged entries by resolved paper id; unresolved untouched", () => {
  const entries = [
    { key: "id:1", paperId: "1", row: "A", occurrenceCount: 1, positions: [0] },
    { key: "id:2", paperId: "2", row: "B", occurrenceCount: 1, positions: [1] },
    { key: "unresolved:2:0", paperId: null, row: "C", occurrenceCount: 1, positions: [2] },
  ];
  const checked = [{ paper_id: 2, status: "retracted", nature: "Retraction", date: null, notice_url: null, sources: [] }];
  const merged = core.mergePanelEntryStatus(entries, [1], checked);
  assert.strictEqual(merged[0].orphaned, true);
  assert.strictEqual(merged[0].retraction, null);
  assert.strictEqual(merged[1].orphaned, false);
  assert.deepStrictEqual(merged[1].retraction, checked[0]);
  assert.strictEqual(merged[2].orphaned, false);
  assert.strictEqual(merged[2].retraction, null);
  // never mutates the input array's own objects
  assert.strictEqual(entries[0].orphaned, undefined);
});

// ---- document-local categorized bibliographies (inc 521) ----
test("normalizeBibliographyCategory: trims valid labels and rejects reserved, multiline, and oversized labels", () => {
  assert.strictEqual(core.normalizeBibliographyCategory("  Methods  "), "Methods");
  assert.strictEqual(core.normalizeBibliographyCategory(""), null);
  assert.throws(() => core.normalizeBibliographyCategory("Other references"), /reserved/);
  assert.throws(() => core.normalizeBibliographyCategory("Methods\nTheory"), /single line/);
  assert.throws(() => core.normalizeBibliographyCategory("Methods\u2028Theory"), /single line/);
  assert.throws(() => core.normalizeBibliographyCategory("x".repeat(81)), /80 characters/);
});

test("bibliography category metadata: reads fail-soft, canonicalizes case, updates immutably, and removes blank", () => {
  assert.deepStrictEqual(core.normalizeBibliographyCategories("not json"), {});
  assert.deepStrictEqual(core.normalizeBibliographyCategories({ nope: "Methods", 1: "Methods" }), { 1: "Methods" });
  const original = { 1: "Methods" };
  const added = core.updateBibliographyCategory(original, 2, "methods");
  assert.deepStrictEqual(original, { 1: "Methods" });
  assert.deepStrictEqual(added, { 1: "Methods", 2: "Methods" });
  assert.deepStrictEqual(core.updateBibliographyCategory(added, 1, ""), { 2: "Methods" });
  assert.strictEqual(core.serializeBibliographyCategories({ 2: "Theory", 1: "Methods" }), '{"1":"Methods","2":"Theory"}');
  assert.throws(() => core.updateBibliographyCategory({}, "foreign-id", "Methods"), /numeric Callosum paper id/);
});

test("bibliography category metadata: enforces bounded assignment and category growth", () => {
  const assignments = {};
  for (let id = 1; id <= 1000; id += 1) assignments[id] = "Methods";
  assert.throws(
    () => core.updateBibliographyCategory(assignments, 1001, "Methods"),
    /at most 1000 works/,
  );

  const categories = {};
  for (let id = 1; id <= 50; id += 1) categories[id] = `Category ${id}`;
  assert.throws(
    () => core.updateBibliographyCategory(categories, 51, "Category 51"),
    /at most 50 bibliography categories/,
  );
});

test("updateBibliographyCategories: applies one category atomically to a deduplicated bounded work batch", () => {
  const original = { 1: "Methods", 2: "Theory", 4: "methods" };
  assert.deepStrictEqual(
    core.updateBibliographyCategories(original, [2, "3", 3], "METHODS"),
    { 1: "Methods", 2: "Methods", 3: "Methods", 4: "Methods" },
  );
  assert.deepStrictEqual(original, { 1: "Methods", 2: "Theory", 4: "methods" });
  assert.deepStrictEqual(
    core.updateBibliographyCategories(original, [1, 2], ""),
    { 4: "Methods" },
  );
  assert.deepStrictEqual(core.updateBibliographyCategories(original, [], "Methods"), {
    1: "Methods", 2: "Theory", 4: "Methods",
  });
  assert.throws(
    () => core.updateBibliographyCategories({}, Array.from({ length: 1001 }, (_value, index) => index + 1), "Methods"),
    /at most 1000 works at once/,
  );
  assert.throws(
    () => core.updateBibliographyCategories({}, [1, "foreign-id"], "Methods"),
    /numeric Callosum paper ids/,
  );
});

test("bibliography category order: bounded read is fail-soft and strict serialization rejects invalid drafts", () => {
  assert.deepStrictEqual(core.normalizeBibliographyCategoryOrder('["Theory","Methods"]'), ["Theory", "Methods"]);
  ["not json", '{"Theory":1}', '["Theory","theory"]', '["Other references"]', '[1]']
    .forEach((value) => assert.deepStrictEqual(core.normalizeBibliographyCategoryOrder(value), []));
  assert.strictEqual(core.serializeBibliographyCategoryOrder(["Theory", "Methods"]), '["Theory","Methods"]');
  assert.throws(() => core.serializeBibliographyCategoryOrder(["Theory", "theory"]), /duplicate/);
  assert.throws(() => core.serializeBibliographyCategoryOrder(["Other references"]), /reserved/);
  assert.throws(
    () => core.serializeBibliographyCategoryOrder(Array.from({ length: 51 }, (_value, index) => `Category ${index}`)),
    /at most 50 bibliography categories/,
  );
});

test("orderedBibliographyCategories: configured active labels lead and stale/new labels fall back alphabetically", () => {
  assert.deepStrictEqual(
    core.orderedBibliographyCategories(["New", "Methods", "Theory", "Background"], ["Theory", "Stale", "Methods"]),
    ["Theory", "Methods", "Background", "New"],
  );
  assert.deepStrictEqual(core.orderedBibliographyCategories(["Theory", "Methods"], []), ["Methods", "Theory"]);
});

test("categorizedBibliographyText: alphabetizes groups, preserves citeproc order, and leaves Other last", () => {
  const data = {
    bibliography_text: "Entry 2\nEntry 1\nEntry 3\nEntry 4",
    bibliography_entry_ids: [["callosum-2"], ["callosum-1"], ["callosum-3"], ["callosum-4"]],
  };
  assert.strictEqual(
    core.categorizedBibliographyText(data, { 1: "Theory", 2: "Methods", 3: "Methods" }),
    "Methods\nEntry 2\nEntry 3\n\nTheory\nEntry 1\n\nOther references\nEntry 4",
  );
  // No visible assignment restores the exact ordinary citeproc text rather than adding an empty group.
  assert.strictEqual(core.categorizedBibliographyText(data, { 99: "Methods" }), data.bibliography_text);
  assert.strictEqual(
    core.categorizedBibliographyText(data, { 1: "Theory", 2: "Methods", 3: "Methods" }, ["Theory", "Methods"]),
    "Theory\nEntry 1\n\nMethods\nEntry 2\nEntry 3\n\nOther references\nEntry 4",
  );
});

test("categorizedBibliographyText: multi-id entries group only when every source shares one category", () => {
  const data = {
    bibliography_text: "Shared entry\nMixed entry",
    bibliography_entry_ids: [["callosum-1", "callosum-2"], ["callosum-2", "callosum-3"]],
  };
  assert.strictEqual(
    core.categorizedBibliographyText(data, { 1: "Methods", 2: "Methods", 3: "Theory" }),
    "Methods\nShared entry\n\nOther references\nMixed entry",
  );
  assert.throws(
    () => core.categorizedBibliographyText({ bibliography_text: "Entry", bibliography_entry_ids: [] }, { 1: "Methods" }),
    /identity is unavailable/,
  );
});

test("bibliography links: validates safe web URLs and converts Python code-point spans across astral text", () => {
  const entries = ["😀 Author. Linked title. https://doi.org/10.1/test"];
  const start = Array.from(entries[0]).indexOf("L");
  const links = core.normalizeBibliographyLinks(entries, [[
    { start, length: Array.from("Linked title").length, url: "https://doi.org/10.1/test" },
  ]]);
  assert.deepStrictEqual(links, [[{
    start,
    length: 12,
    text: "Linked title",
    url: "https://doi.org/10.1/test",
  }]]);
  assert.strictEqual(core.validatedBibliographyExternalUrl("https://example.org/a?q=1"), "https://example.org/a?q=1");
  ["javascript:alert(1)", "file:///tmp/x", "https://user:pass@example.org/x", "https://exa mple.org/x", ""]
    .forEach((url) => assert.strictEqual(core.validatedBibliographyExternalUrl(url), null));
});

test("bibliography links: malformed, overlapping, excessive, and misaligned metadata degrades to plain text", () => {
  const entries = ["0123456789"];
  const raw = [[
    { start: 1, length: 3, url: "https://example.org/one" },
    { start: 2, length: 2, url: "https://example.org/overlap" },
    { start: 9, length: 2, url: "https://example.org/out" },
    { start: 5, length: 1, url: "mailto:test@example.org" },
  ]].concat([]);
  assert.deepStrictEqual(core.normalizeBibliographyLinks(entries, raw), [[{
    start: 1, length: 3, text: "123", url: "https://example.org/one",
  }]]);
  assert.deepStrictEqual(core.normalizeBibliographyLinks(entries, []), [[]]);
  assert.deepStrictEqual(
    core.normalizeBibliographyLinks(entries, [[
      ...Array.from({ length: 20 }, (_value, index) => ({
        start: index % 10, length: 1, url: `https://example.org/${index}`,
      })),
      { start: 9, length: 1, url: "https://example.org/ignored-21st" },
    ]])[0].length,
    10,
  );
});

test("bibliographyRenderPlan: categories retain entry links at their exact generated paragraph indexes", () => {
  const data = {
    bibliography_text: "Entry 2 DOI\nEntry 1 title\nEntry 3",
    bibliography_entry_ids: [["callosum-2"], ["callosum-1"], ["callosum-3"]],
    bibliography_links: [
      [{ start: 8, length: 3, url: "https://doi.org/10.2/x" }],
      [{ start: 8, length: 5, url: "https://doi.org/10.1/x" }],
      [],
    ],
  };
  const plan = core.bibliographyRenderPlan(data, { 1: "Theory", 2: "Methods" }, ["Theory", "Methods"]);
  assert.strictEqual(
    plan.text,
    "Theory\nEntry 1 title\n\nMethods\nEntry 2 DOI\n\nOther references\nEntry 3",
  );
  assert.deepStrictEqual(plan.entries.map((entry) => [entry.paragraphIndex, entry.text]), [
    [1, "Entry 1 title"], [4, "Entry 2 DOI"], [7, "Entry 3"],
  ]);
  assert.deepStrictEqual(plan.entries[0].links[0], {
    start: 8, length: 5, text: "title", url: "https://doi.org/10.1/x",
  });
});

test("applyBibliographyCategories: annotates only resolvable document works without mutating panel entries", () => {
  const entries = [{ paperId: "1", row: "A" }, { paperId: null, row: "Legacy" }, { paperId: "2", row: "B" }];
  const applied = core.applyBibliographyCategories(entries, { 1: "Methods" });
  assert.deepStrictEqual(applied.map((entry) => entry.category), ["Methods", null, null]);
  assert.strictEqual(entries[0].category, undefined);
});

// ---- heading-scoped bibliographies (inc 524) ----
test("section bibliography identity: 16 bytes become a strict deterministic pair of 32-hex tags", () => {
  const id = core.sectionBibliographyIdFromBytes(Uint8Array.from([
    0, 1, 2, 3, 4, 5, 6, 7, 248, 249, 250, 251, 252, 253, 254, 255,
  ]));
  assert.strictEqual(id, "0001020304050607f8f9fafbfcfdfeff");
  const scope = core.encodeSectionBibliographyTag("scope", id);
  const block = core.encodeSectionBibliographyTag("block", id);
  assert.deepStrictEqual(core.decodeSectionBibliographyTag(scope), { id, kind: "scope" });
  assert.deepStrictEqual(core.decodeSectionBibliographyTag(block), { id, kind: "block" });
  assert.strictEqual(core.decodeSectionBibliographyTag(`${core.SECTION_BIB_SCOPE_PREFIX}${id.toUpperCase()}`), null);
  assert.throws(() => core.sectionBibliographyIdFromBytes(new Uint8Array(15)), /16 random bytes/);
  assert.throws(() => core.encodeSectionBibliographyTag("scope", "abc"), /32 lowercase/);
  assert.throws(() => core.encodeSectionBibliographyTag("other", id), /scope or block/);
});

test("sectionBibliographyInventory: complete pairs survive order; missing, duplicate, and malformed controls fail closed", () => {
  const a = "a".repeat(32), b = "b".repeat(32), c = "c".repeat(32);
  const records = [
    { tag: core.encodeSectionBibliographyTag("block", a), marker: "a-block" },
    { tag: core.encodeSectionBibliographyTag("scope", b), marker: "b-scope" },
    { tag: core.encodeSectionBibliographyTag("scope", a), marker: "a-scope" },
    { tag: core.encodeSectionBibliographyTag("scope", b), marker: "duplicate-b-scope" },
    { tag: `${core.SECTION_BIB_BLOCK_PREFIX}not-an-id` },
    { tag: core.encodeSectionBibliographyTag("block", c), marker: "c-block-only" },
  ];
  const inventory = core.sectionBibliographyInventory(records);
  assert.deepStrictEqual(inventory.complete.map((row) => row.id), [a]);
  assert.strictEqual(inventory.complete[0].scope.marker, "a-scope");
  assert.strictEqual(inventory.complete[0].block.marker, "a-block");
  assert.deepStrictEqual(inventory.damaged, ["malformed-4", b, c]);
});

test("sectionBibliographyInventory: more than 50 distinct ids is rejected", () => {
  const records = Array.from({ length: 51 }, (_value, index) => ({
    tag: core.encodeSectionBibliographyTag("scope", index.toString(16).padStart(32, "0")),
  }));
  assert.throws(() => core.sectionBibliographyInventory(records), /at most 50/);
});

test("sectionParagraphBounds: nearest heading owns nested headings through the next peer or ancestor", () => {
  const paragraphs = [
    { id: "preamble", outlineLevel: 10 },
    { id: "methods", outlineLevel: 1 },
    { id: "m1", outlineLevel: 10 },
    { id: "sub", outlineLevel: 2 },
    { id: "m2", outlineLevel: 10 },
    { id: "results", outlineLevel: 1 },
    { id: "r1", outlineLevel: 10 },
  ];
  assert.deepStrictEqual(core.sectionParagraphBounds(paragraphs, "m2"), {
    start: 3, end: 5, headingId: "sub", outlineLevel: 2,
  });
  assert.deepStrictEqual(core.sectionParagraphBounds(paragraphs, "methods"), {
    start: 1, end: 5, headingId: "methods", outlineLevel: 1,
  });
  assert.strictEqual(core.sectionParagraphBounds(paragraphs, "preamble"), null);
  assert.strictEqual(core.sectionParagraphBounds(paragraphs, "missing"), null);
});

test("sectionCitationItemIds: exact heading subtree includes nested citations and deduplicates grouped works", () => {
  const paragraphs = [
    { id: "h1", outlineLevel: 1 }, { id: "a", outlineLevel: 10 },
    { id: "h2", outlineLevel: 2 }, { id: "b", outlineLevel: 10 },
    { id: "peer", outlineLevel: 1 }, { id: "c", outlineLevel: 10 },
  ];
  const citations = [
    { paragraphId: "a", items: [{ id: "callosum-1" }, { id: "callosum-2" }] },
    { paragraphId: "b", items: [{ id: "callosum-2" }, { id: "foreign" }] },
    { paragraphId: "c", items: [{ id: "callosum-3" }] },
  ];
  assert.deepStrictEqual(core.sectionCitationItemIds(paragraphs, "h1", citations), ["callosum-1", "callosum-2"]);
  assert.deepStrictEqual(core.sectionCitationItemIds(paragraphs, "h2", citations), ["callosum-2"]);
  assert.throws(() => core.sectionCitationItemIds(paragraphs, "a", citations), /no longer wraps a heading/);
});

test("sectionBibliographyText: projects full citeproc order before applying document categories", () => {
  const data = {
    bibliography_text: "Entry 3\nEntry 1\nEntry 2\nEntry 4",
    bibliography_entry_ids: [["callosum-3"], ["callosum-1"], ["callosum-2"], ["callosum-4"]],
    bibliography_links: [[], [{ start: 0, length: 5, url: "https://example.org/1" }], [], []],
  };
  assert.strictEqual(
    core.sectionBibliographyText(data, ["callosum-1", "callosum-2"], { 1: "Theory", 2: "Methods" }, ["Theory", "Methods"]),
    "References\nTheory\nEntry 1\n\nMethods\nEntry 2",
  );
  assert.strictEqual(core.sectionBibliographyText(data, [], {}, []), "References");
  const plan = core.sectionBibliographyPlan(data, ["callosum-1"], {}, []);
  assert.strictEqual(plan.text, "References\nEntry 1");
  assert.deepStrictEqual(plan.entries, [{
    paragraphIndex: 1,
    text: "Entry 1",
    links: [{ start: 0, length: 5, text: "Entry", url: "https://example.org/1" }],
  }]);
  assert.throws(
    () => core.sectionBibliographyText({ bibliography_text: "Entry", bibliography_entry_ids: [] }, ["callosum-1"], {}, []),
    /identity is unavailable/,
  );
});

test("diagnostics count complete and damaged section bibliography controls separately", () => {
  const good = "1".repeat(32), bad = "2".repeat(32);
  const report = core.summarizeDiagnostics([
    core.encodeCitationTag([{ id: "callosum-1" }]), core.BIB_TAG,
    core.encodeSectionBibliographyTag("scope", good), core.encodeSectionBibliographyTag("block", good),
    core.encodeSectionBibliographyTag("scope", bad),
  ], [], []);
  assert.strictEqual(report.sectionBibliographyCount, 1);
  assert.strictEqual(report.damagedSectionBibliographyCount, 1);
});

test("bibliography category controls are present and wire single/batch edits through one categorized render path", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  [
    "bibliographyCategoryEditor", "bibliographyCategory", "bibliographyCategorySave", "bibliographyCategoryRemove",
    "citationsBatchBar", "citationsSelectVisible", "citationsClearSelection", "citationsBatchCategory",
    "bibliographyCategoryOrderOpen", "bibliographyCategoryOrderEditor", "bibliographyCategoryOrderList",
    "bibliographyCategoryOrderReset", "bibliographyCategoryOrderSave", "bibliographyCategoryOrderCancel",
  ]
    .forEach((id) => assert.match(html, new RegExp(`id=["']${id}["']`)));
  assert.match(js, /bibliographyRenderPlan\(data, bibliographyCategories, bibliographyCategoryOrder\)/);
  assert.match(js, /persistBibliographyCategories\(updated\)/);
  assert.match(js, /updateBibliographyCategories\(previous, paperIds, value\)/);
  assert.match(js, /openCategoryEditor\(selectedCategoryIds\(\), true\)/);
  assert.match(js, /Choose a category for the mixed selection, or use Remove category/);
  assert.match(js, /applyCategoryEdit\("", true\)/);
  assert.match(js, /persistBibliographyCategoryOrder\(savedOrder\)/);
  assert.match(js, /restoreBibliographyCategoryOrder\(previousRaw\)/);
  assert.match(js, /refreshDocument\(\{ throwOnError: true \}\)/);
});

test("heading-scoped bibliography controls use paired identity, refresh projection, diagnostics, and flatten", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  ["sectionBibliographyInsert", "sectionBibliographyRemove"]
    .forEach((id) => assert.match(html, new RegExp(`id=["']${id}["']`)));
  assert.match(js, /isSetSupported\("WordApi", "1\.6"\)/);
  assert.match(js, /scopeCC\.appearance = "Hidden"/);
  assert.match(js, /blockParagraph\.styleBuiltIn = "Normal"/);
  assert.match(js, /sectionBibliographyPlan\(/);
  assert.match(js, /requireHealthySectionBibliographies\(records\)/);
  assert.match(js, /isSectionBibliographyTag\(record\.tag\)/);
  assert.match(js, /native note-to-heading membership is not yet supported/);
});

test("bibliography web-link opt-in persists and applies only unambiguous paragraph-local ranges", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  assert.match(html, /id=["']bibliographyExternalLinks["']/);
  assert.match(js, /BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING/);
  assert.match(js, /queueBibliographyWrite\(/);
  assert.match(js, /paragraph\.search\(link\.text/);
  assert.match(js, /search\.ranges\.items\.length !== 1/);
  assert.match(js, /search\.ranges\.items\[0\]\.hyperlink = search\.url/);
  assert.match(js, /restoreBibliographyExternalLinks\(previousRaw\)/);
  assert.match(js, /remove\(BIBLIOGRAPHY_EXTERNAL_LINKS_SETTING\)/);
});

test("citation coverage UI maps inline and native-note citations to main-story paragraphs without a backend call", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  assert.match(html, /id=["']citationCoverageRun["']/);
  assert.match(js, /isSetSupported\("WordApi", "1\.6"\)/);
  assert.match(js, /record\.note && record\.note\.reference\.paragraphs/);
  assert.match(js, /record\.cc\.paragraphs/);
  assert.match(js, /CallosumCore\.summarizeCitationCoverage\(rows\)/);
  assert.doesNotMatch(js, /citationCoverage[\s\S]{0,500}callosumFetch/);
});

test("evidence-aware Suggest exposes detail, editable locator, PDF deep link, and later audit UI", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  assert.match(html, /id=["']citationEvidence["']/);
  assert.match(js, /renderSuggestionRows\(/);
  assert.match(js, /data-suggestion-details/);
  assert.match(js, /data-suggestion-locator/);
  assert.match(js, /suggestionAssemblyFields\(/);
  assert.match(js, /suggestionOpenPdfPath\(/);
  assert.match(js, /window\.open\(path, "_blank", "noopener,noreferrer"\)/);
  assert.match(js, /data-evidence-position/);
  assert.match(js, /Evidence recorded when suggested/);
});

test("Word saved-evidence UI keeps selection, stance, format, and citation semantics author-controlled", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  [
    "evidenceOpen", "evidenceEditor", "evidencePaperQuery", "evidencePaperResults",
    "evidenceAnnotationResults", "evidenceQuote", "evidenceNote", "evidenceClaim",
    "evidenceCheckStance", "evidenceFormat", "evidenceLocator", "evidenceInsert", "evidenceCancel",
  ].forEach((id) => assert.match(html, new RegExp(`id=["']${id}["']`)));
  assert.match(html, /Callosum never chooses evidence or a stance for you/);
  assert.match(js, /\/integrations\/word\/evidence\/" \+ encodeURIComponent\(String\(paperId\)\)/);
  assert.match(js, /callosumFetch\("\/citations\/classify-stance"/);
  assert.match(js, /This is a model signal, not a verdict/);
  assert.match(js, /if \(format === "quote_only"\)/);
  assert.match(js, /saved evidence must be inserted from the main document/);
  assert.match(js, /insertNewCitation\(ctx, selection, parentBody, existingRecords, items, body, true\)/);
  assert.match(js, /evidenceAssemblyFields\(selectedEvidenceAnnotation/);
  assert.match(js, /await refreshDocument\(\)/);
});

test("open-science statements expose the seven bounded author-controlled kinds", () => {
  assert.deepStrictEqual(core.STATEMENT_TYPES.map((type) => type.kind), [
    "data_availability", "code_availability", "preregistration", "funding",
    "conflict_of_interest", "ethics", "ai_use",
  ]);
  assert.ok(core.STATEMENT_TYPES.every((type) => type.label && type.phrases.length >= 2));
  assert.strictEqual(core.statementType("funding").phrases[0].text,
    "This work was supported by [Funder name] under Grant No. [XXX].");
  assert.strictEqual(core.statementType("unknown"), null);
});

// ---- Zotero Word-field conversion (inc 530) ----
function zoteroCode(items, extra) {
  return " ADDIN ZOTERO_ITEM CSL_CITATION " + JSON.stringify(Object.assign({ citationItems: items }, extra || {})) + " ";
}

test("Zotero field decoder accepts the current exact ADDIN contract and preserves grouped overrides", () => {
  const code = zoteroCode([
    { id: 1, uris: ["http://zotero.org/users/7/items/A"], itemData: { id: "A", title: "Alpha" }, locator: "9", label: "page" },
    { id: 2, itemData: { id: "B", title: "Beta" }, prefix: "see", "suppress-author": true },
  ], { citationID: "cluster-1" });
  const decoded = core.decodeZoteroCitationFieldCode(code);
  assert.strictEqual(decoded.citationID, "cluster-1");
  assert.strictEqual(decoded.citationItems.length, 2);
  assert.strictEqual(decoded.citationItems[0].locator, "9");
  assert.strictEqual(decoded.citationItems[1]["suppress-author"], true);
});

test("Zotero field decoder fails closed on foreign, malformed, oversized, and incomplete fields", () => {
  assert.strictEqual(core.decodeZoteroCitationFieldCode("ADDIN EN.CITE {}"), null);
  assert.strictEqual(core.decodeZoteroCitationFieldCode("ADDIN ZOTERO_ITEM CSL_CITATION nope"), null);
  assert.strictEqual(core.decodeZoteroCitationFieldCode(zoteroCode([])), null);
  assert.strictEqual(core.decodeZoteroCitationFieldCode(zoteroCode([{ id: 1 }])), null);
  assert.strictEqual(core.decodeZoteroCitationFieldCode("x".repeat(1024 * 1024 + 1)), null);
});

test("Zotero bibliography decoder requires the exact current BIBL wrapper", () => {
  assert.deepStrictEqual(
    core.decodeZoteroBibliographyFieldCode(' ADDIN ZOTERO_BIBL {"uncited":[]} CSL_BIBLIOGRAPHY '),
    { uncited: [] },
  );
  assert.strictEqual(core.decodeZoteroBibliographyFieldCode("ADDIN ZOTERO_BIBL {}"), null);
  assert.strictEqual(core.decodeZoteroBibliographyFieldCode("ADDIN ZOTERO_BIBL [] CSL_BIBLIOGRAPHY"), null);
});

test("Zotero conversion scan separates inline, note, bookmark, bibliography, and malformed material", () => {
  const good = zoteroCode([{ itemData: { title: "Good" } }]);
  const scan = core.zoteroConversionScan([
    { type: "Addin", code: good, location: "inline" },
    { type: "Addin", code: good, location: "footnote" },
    { type: "Addin", code: "ADDIN ZOTERO_ITEM CSL_CITATION nope", location: "inline" },
    { type: "Citation", code: good, location: "inline" },
    { type: "Addin", code: 'ADDIN ZOTERO_BIBL {"uncited":[]} CSL_BIBLIOGRAPHY', location: "inline" },
    { type: "Addin", code: "ADDIN EN.CITE {}", location: "inline" },
  ], ["ZOTERO_BREF_abc", "USER_MARK"]);
  assert.strictEqual(scan.convertible.length, 1);
  assert.strictEqual(scan.noteStyleCount, 1);
  assert.strictEqual(scan.bookmarkCount, 1);
  assert.strictEqual(scan.malformedCount, 2);
  assert.strictEqual(scan.bibliographies.length, 1);
  assert.match(scan.snapshot, /ZOTERO_BREF_abc/);
});

test("Zotero conversion snapshot is deterministic but detects a changed Zotero field", () => {
  const a = { type: "Addin", code: zoteroCode([{ itemData: { title: "A" } }]), location: "inline" };
  const first = core.zoteroConversionScan([a], ["ZOTERO_BREF_z", "ZOTERO_BREF_a"]);
  const same = core.zoteroConversionScan([a], ["ZOTERO_BREF_a", "ZOTERO_BREF_z"]);
  const changed = core.zoteroConversionScan([
    { type: "Addin", code: zoteroCode([{ itemData: { title: "B" } }]), location: "inline" },
  ], ["ZOTERO_BREF_a", "ZOTERO_BREF_z"]);
  assert.strictEqual(first.snapshot, same.snapshot);
  assert.notStrictEqual(first.snapshot, changed.snapshot);
});

test("Zotero resolution plan deduplicates metadata canonically and restores grouped Callosum identity", () => {
  const one = { id: "z1", title: "One", author: [{ family: "A" }] };
  const sameDifferentOrder = { author: [{ family: "A" }], title: "One", id: "z1" };
  const two = { id: "z2", title: "Two" };
  const plan = core.buildZoteroResolutionPlan([
    { citationItems: [{ itemData: one, uris: ["u1"], locator: "4", label: "page" }, { itemData: two }] },
    { citationItems: [{ itemData: sameDifferentOrder, suffix: ", appendix" }] },
  ]);
  assert.strictEqual(plan.items.length, 2);
  assert.deepStrictEqual(plan.items[0], { item_data: one, uris: ["u1"] });
  const clusters = core.resolveZoteroConversionClusters(plan, [{ paper_id: 8 }, { paper_id: 9 }]);
  assert.deepStrictEqual(clusters[0].map((item) => item.id), ["callosum-8", "callosum-9"]);
  assert.deepStrictEqual({ locator: clusters[0][0].locator, label: clusters[0][0].label }, { locator: "4", label: "page" });
  assert.strictEqual(clusters[1][0].id, "callosum-8");
  assert.strictEqual(clusters[1][0].suffix, ", appendix");
});

test("Zotero resolution plan rejects caps and incomplete or invalid resolver results", () => {
  assert.throws(() => core.buildZoteroResolutionPlan([]), /No Zotero/);
  const fields = Array.from({ length: core.MAX_ZOTERO_CONVERT_FIELDS + 1 }, (_v, i) => ({
    citationItems: [{ itemData: { title: `T${i}` } }],
  }));
  assert.throws(() => core.buildZoteroResolutionPlan(fields), /at most 500/);
  const plan = core.buildZoteroResolutionPlan([{ citationItems: [{ itemData: { title: "One" } }] }]);
  assert.throws(() => core.resolveZoteroConversionClusters(plan, []), /incomplete/);
  assert.throws(() => core.resolveZoteroConversionClusters(plan, [{ paper_id: 0 }]), /invalid paper id/);
});

test("Word Zotero conversion UI is preflighted, snapshot-checked, field-based, and refreshes existing semantics", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  assert.match(html, /id=["']convertZotero["']/);
  assert.match(js, /isSetSupported\("WordApi", "1\.5"\)/);
  assert.match(js, /body\.fields/);
  assert.match(js, /note\.body\.fields/);
  assert.match(js, /getBookmarks\(true, true\)/);
  assert.match(js, /\/citations\/zotero\/resolve/);
  assert.match(js, /fresh\.scan\.snapshot !== initial\.scan\.snapshot/);
  assert.match(js, /field\.result\.insertText\("…", Word\.InsertLocation\.after\)/);
  assert.match(js, /field\.delete\(\)/);
  assert.match(js, /customXmlParts\.add\(CallosumCore\.encodeCitationXml\(items\)\)/);
  assert.match(js, /Word Undo does not remove those library records/);
  assert.match(js, /await refreshDocument\(\{ throwOnError: true \}\)/);
  assert.doesNotMatch(js, /convertZotero[\s\S]{0,2500}(gemini|openai|anthropic)/i);
});

test("statement staging normalizes only allowlisted bounded text without mutating input", () => {
  const raw = {
    funding: "  Funded by an author-confirmed grant.  ",
    ethics: "x".repeat(core.MAX_STATEMENT_LENGTH + 25),
    unknown: "must not cross the adapter boundary",
    ai_use: 42,
  };
  const normalized = core.normalizeStagedStatements(raw);
  assert.deepStrictEqual(normalized, {
    funding: "Funded by an author-confirmed grant.",
    ethics: "x".repeat(core.MAX_STATEMENT_LENGTH),
  });
  assert.strictEqual(raw.funding, "  Funded by an author-confirmed grant.  ");
  assert.deepStrictEqual(core.normalizeStagedStatements(null), {});
  assert.deepStrictEqual(core.normalizeStagedStatements([]), {});
});

test("statement stage requests preserve clear semantics and reject unknown kinds", () => {
  assert.deepStrictEqual(core.buildStatementStageRequest("ethics", "  IRB approved.  "), {
    kind: "ethics", text: "IRB approved.",
  });
  assert.deepStrictEqual(core.buildStatementStageRequest("ethics", "   "), { kind: "ethics", text: "" });
  assert.strictEqual(core.buildStatementStageRequest("other", "text"), null);
});

test("Word statement UI stages locally and inserts exact plain text without a Content Control", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  [
    "statementOpen", "statementEditor", "statementKind", "statementPhrase", "statementText",
    "statementStageState", "statementInsert", "statementStage", "statementClear", "statementCancel",
  ].forEach((id) => assert.match(html, new RegExp(`id=["']${id}["']`)));
  assert.match(html, /maxlength=["']4000["']/);
  assert.match(html, /Callosum does not infer or verify facts about your study/);
  assert.match(js, /callosumFetch\("\/statements\/pending"\)/);
  assert.match(js, /method: "POST"/);
  assert.match(js, /window\.confirm\("Replace the current text/);
  assert.match(js, /if \(selected === ""\) return/);
  assert.match(js, /statementDrafts\[\$\("statementKind"\)\.value\]/);
  assert.match(js, /getSelection\(\)\.getRange\(Word\.RangeLocation\.end\)/);
  assert.match(js, /insertionPoint\.insertText\(text, Word\.InsertLocation\.replace\)/);
  const insertBody = js.slice(js.indexOf("async function insertStatementAtCursor"), js.indexOf("// inc 517"));
  assert.doesNotMatch(insertBody, /insertContentControl|createCitationPart|callosumFetch/);
});

// ---- Word-on-the-web relay (SP4): local vs. tunneled origin + the Bearer token header ----
test("isLocalOrigin: localhost/127.0.0.1 are local; a tunnel hostname is not", () => {
  assert.strictEqual(core.isLocalOrigin("localhost"), true);
  assert.strictEqual(core.isLocalOrigin("127.0.0.1"), true);
  assert.strictEqual(core.isLocalOrigin("callosum-tunnel.clffwrkmn.net"), false);
  assert.strictEqual(core.isLocalOrigin(""), false);
  assert.strictEqual(core.isLocalOrigin(null), false);
});

test("authHeaders: attaches Bearer only when a token is given; never mutates the input; existing headers survive", () => {
  const base = { "Content-Type": "application/json" };
  const withToken = core.authHeaders(base, "secret123");
  assert.deepStrictEqual(withToken, { "Content-Type": "application/json", Authorization: "Bearer secret123" });
  assert.deepStrictEqual(base, { "Content-Type": "application/json" }); // input untouched

  assert.deepStrictEqual(core.authHeaders(base, null), { "Content-Type": "application/json" });
  assert.deepStrictEqual(core.authHeaders(base, ""), { "Content-Type": "application/json" });
  assert.deepStrictEqual(core.authHeaders(undefined, "tok"), { Authorization: "Bearer tok" });
});
