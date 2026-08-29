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

test("buildClusterItems: merges each row's CSL record with its own overrides, in order", () => {
  const assembly = [
    { csl: { id: "callosum-1", title: "A" }, locator: "5", label: "page" },
    { csl: { id: "callosum-2", title: "B" } },
  ];
  assert.deepStrictEqual(core.buildClusterItems(assembly), [
    { id: "callosum-1", title: "A", locator: "5", label: "page" },
    { id: "callosum-2", title: "B" },
  ]);
  assert.deepStrictEqual(core.buildClusterItems([]), []);
  assert.deepStrictEqual(core.buildClusterItems(null), []);
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
  const decoded = { id: "callosum-1", title: "Notes", author: [{ family: "Lovelace" }], locator: "5", label: "page" };
  const row = core.assemblyRowFromDecodedItem(decoded);
  assert.deepStrictEqual(row.csl, { id: "callosum-1", title: "Notes", author: [{ family: "Lovelace" }] });
  assert.strictEqual(row.locator, "5");
  assert.strictEqual(row.label, "page");
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

test("applyBibliographyCategories: annotates only resolvable document works without mutating panel entries", () => {
  const entries = [{ paperId: "1", row: "A" }, { paperId: null, row: "Legacy" }, { paperId: "2", row: "B" }];
  const applied = core.applyBibliographyCategories(entries, { 1: "Methods" });
  assert.deepStrictEqual(applied.map((entry) => entry.category), ["Methods", null, null]);
  assert.strictEqual(entries[0].category, undefined);
});

test("bibliography category controls are present and wire single/batch edits through one categorized render path", () => {
  const html = fs.readFileSync(path.join(__dirname, "taskpane.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "taskpane.js"), "utf8");
  [
    "bibliographyCategoryEditor", "bibliographyCategory", "bibliographyCategorySave", "bibliographyCategoryRemove",
    "citationsBatchBar", "citationsSelectVisible", "citationsClearSelection", "citationsBatchCategory",
  ]
    .forEach((id) => assert.match(html, new RegExp(`id=["']${id}["']`)));
  assert.match(js, /categorizedBibliographyText\(data, bibliographyCategories\)/);
  assert.match(js, /persistBibliographyCategories\(updated\)/);
  assert.match(js, /updateBibliographyCategories\(previous, paperIds, value\)/);
  assert.match(js, /openCategoryEditor\(selectedCategoryIds\(\), true\)/);
  assert.match(js, /Choose a category for the mixed selection, or use Remove category/);
  assert.match(js, /applyCategoryEdit\("", true\)/);
  assert.match(js, /refreshDocument\(\{ throwOnError: true \}\)/);
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
