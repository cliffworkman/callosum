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
