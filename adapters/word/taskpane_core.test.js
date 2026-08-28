/*
 * Pure-logic unit tests for the Word add-in (run: `node --test "adapters/word/*.test.js"`).
 * Uses Node's built-in test runner — no new dependency, no browser, no Office host. This is the primary
 * automated check for the add-in, since there is no headless Word to exercise the Office.js glue.
 */
const test = require("node:test");
const assert = require("node:assert");
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

// ---- live-citation tag round-trip (SP2) ----
test("encode/decodeCitationTag: round-trips CSL items, including unicode", () => {
  const items = [{ id: "callosum-1", title: "Über Ästhetik", author: [{ family: "Uğurlar" }] }];
  const tag = core.encodeCitationTag(items);
  assert.ok(core.isCitationTag(tag));
  assert.deepStrictEqual(core.decodeCitationTag(tag), items);
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
