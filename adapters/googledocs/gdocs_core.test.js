/* node --test "adapters/googledocs/*.test.js" — the pure logic the Apps Script add-on shares (gdocs_core.js). */
const test = require("node:test");
const assert = require("node:assert");
const C = require("./gdocs_core.js");

test("authorLabel: empty / single / multiple", () => {
  assert.equal(C.authorLabel([]), "Unknown");
  assert.equal(C.authorLabel(["Vaswani, Ashish"]), "Vaswani");
  assert.equal(C.authorLabel(["Vaswani, Ashish", "Shazeer, Noam"]), "Vaswani et al.");
});

test("formatSearchRows: builds labels + drops rows with no id", () => {
  const rows = C.formatSearchRows([
    { id: 1, title: "Attention", year: 2017, authors: ["Vaswani, Ashish", "Shazeer, Noam"] },
    { id: null, title: "ignored" },
    { title: "also ignored" },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, 1);
  assert.equal(rows[0].label, "Vaswani et al. (2017) — Attention");
});

test("firstCslRecord: first of array, else null", () => {
  assert.deepEqual(C.firstCslRecord([{ id: "a" }, { id: "b" }]), { id: "a" });
  assert.equal(C.firstCslRecord([]), null);
  assert.equal(C.firstCslRecord(null), null);
});

test("buildDocumentRequest: positional citationIDs + style/locale", () => {
  const req = C.buildDocumentRequest([[{ id: "a" }], [{ id: "b" }]], "ieee", "en-GB");
  assert.deepEqual(req.citations, [
    { citationID: "c0", items: [{ id: "a" }] },
    { citationID: "c1", items: [{ id: "b" }] },
  ]);
  assert.equal(req.style, "ieee");
  assert.equal(req.locale, "en-GB");
  // defaults
  const d = C.buildDocumentRequest([]);
  assert.equal(d.style, "apa");
  assert.equal(d.locale, "en-US");
  assert.deepEqual(d.citations, []);
});

test("inTextResults: maps .text in order, tolerates gaps", () => {
  const data = { citations: [{ citationID: "c0", text: "[1]" }, { citationID: "c1" }] };
  assert.deepEqual(C.inTextResults(data), ["[1]", ""]);
  assert.deepEqual(C.inTextResults(null), []);
  assert.deepEqual(C.inTextResults({}), []);
});

test("bibliographyEntries: split bibliography_text, trim, drop blanks", () => {
  const data = { bibliography_text: "Entry one.\n\n  Entry two.  \n" };
  assert.deepEqual(C.bibliographyEntries(data), ["Entry one.", "Entry two."]);
  assert.deepEqual(C.bibliographyEntries({}), []);
  assert.deepEqual(C.bibliographyEntries(null), []);
});

test("parseOrder: valid array of strings / malformed / non-array / non-strings", () => {
  assert.deepEqual(C.parseOrder('["a","b"]'), ["a", "b"]);
  assert.deepEqual(C.parseOrder("not json"), []);
  assert.deepEqual(C.parseOrder("null"), []);
  assert.deepEqual(C.parseOrder('{"x":1}'), []);
  assert.deepEqual(C.parseOrder('["a",2,"b"]'), ["a", "b"]);
  assert.deepEqual(C.parseOrder(undefined), []);
});

test("serializeOrder / appendOrder: round-trip + dedupe", () => {
  assert.equal(C.serializeOrder(["a", "b"]), '["a","b"]');
  assert.deepEqual(C.appendOrder('["a"]', "b"), ["a", "b"]);
  assert.deepEqual(C.appendOrder('["a"]', "a"), ["a"]); // no dup
  assert.deepEqual(C.appendOrder(null, "a"), ["a"]);
});

test("parseItems / serializeItems: round-trip + malformed → []", () => {
  assert.deepEqual(C.parseItems('{"items":[{"id":"a"}]}'), [{ id: "a" }]);
  assert.deepEqual(C.parseItems("garbage"), []);
  assert.deepEqual(C.parseItems('{"items":"x"}'), []);
  assert.equal(C.serializeItems([{ id: "a" }]), '{"items":[{"id":"a"}]}');
  assert.equal(C.serializeItems(null), '{"items":[]}');
});

test("rangeName: prefixes the id", () => {
  assert.equal(C.rangeName("xyz"), "CALLOSUM_CITATION_xyz");
});

test("pickQueryText: selection wins, else paragraph", () => {
  assert.equal(C.pickQueryText("  sel text ", "para"), "sel text");
  assert.equal(C.pickQueryText("   ", "para text"), "para text");
  assert.equal(C.pickQueryText("", ""), "");
});

test("buildSuggestRequest: caps text at 4000, defaults top_k + evaluate", () => {
  const r = C.buildSuggestRequest("hello", 5);
  assert.deepEqual(r, { text: "hello", top_k: 5, evaluate: true });
  assert.equal(C.buildSuggestRequest("x".repeat(5000)).text.length, 4000);
  assert.equal(C.buildSuggestRequest("x").top_k, 8); // default
});

test("formatSuggestRows: stance + author + match + quote; drops rows with no paper_id", () => {
  const rows = C.formatSuggestRows([
    {
      paper_id: 7,
      author: "Vaswani",
      year: 2017,
      match_score: 0.83,
      quote: "Attention is all you need.",
      stance: { label: "support" },
    },
    { paper_id: null, author: "X" },
    { paper_id: 9, author: "Doe" }, // no stance/score/quote → still rendered
  ]);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].id, 7);
  assert.equal(rows[0].label, '[support] Vaswani 2017 · match 0.83 — "Attention is all you need.…"');
  assert.equal(rows[1].id, 9);
  assert.equal(rows[1].label, "[?] Doe");
  assert.deepEqual(C.formatSuggestRows(null), []);
});
