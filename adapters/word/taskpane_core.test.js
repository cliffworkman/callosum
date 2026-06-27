/*
 * Pure-logic unit tests for the Word add-in (run: `node --test adapters/word/`).
 * Uses Node's built-in test runner — no new dependency, no browser, no Office host.
 */
const test = require("node:test");
const assert = require("node:assert");
const core = require("./taskpane_core.js");

test("authorLabel: single author shows the family name", () => {
  assert.strictEqual(core.authorLabel(["Lovelace, Ada"]), "Lovelace");
});

test("authorLabel: multiple authors → et al.", () => {
  assert.strictEqual(core.authorLabel(["Lovelace, Ada", "Babbage, Charles"]), "Lovelace et al.");
});

test("authorLabel: empty/invalid → Unknown", () => {
  assert.strictEqual(core.authorLabel([]), "Unknown");
  assert.strictEqual(core.authorLabel(null), "Unknown");
});

test("formatSearchRows: builds 'Author (Year) — Title' rows keyed by id", () => {
  const rows = core.formatSearchRows([
    { id: 7, title: "Notes on the Analytical Engine", authors: ["Lovelace, Ada"], year: 1843 },
    { id: 9, title: "On Computable Numbers", authors: ["Turing, Alan", "Church, Alonzo"], year: 1936 },
  ]);
  assert.deepStrictEqual(rows, [
    { id: 7, label: "Lovelace (1843) — Notes on the Analytical Engine" },
    { id: 9, label: "Turing et al. (1936) — On Computable Numbers" },
  ]);
});

test("formatSearchRows: missing year/title degrade gracefully; rows without id are dropped", () => {
  const rows = core.formatSearchRows([
    { id: 3, authors: ["Doe, Jane"] },
    { title: "No id here", authors: ["X, Y"], year: 2020 },
  ]);
  assert.deepStrictEqual(rows, [{ id: 3, label: "Doe — Untitled" }]);
});

test("formatSearchRows: non-array input → []", () => {
  assert.deepStrictEqual(core.formatSearchRows(null), []);
});

test("buildRenderRequest: wraps the id + style/locale; defaults to apa/en-US", () => {
  assert.deepStrictEqual(core.buildRenderRequest(42, "ieee", "en-GB"), {
    paper_ids: [42], style: "ieee", locale: "en-GB",
  });
  assert.deepStrictEqual(core.buildRenderRequest(42), { paper_ids: [42], style: "apa", locale: "en-US" });
});

test("inTextFromRender: pulls items[0].in_text; empty when absent", () => {
  assert.strictEqual(core.inTextFromRender({ items: [{ in_text: "(Lovelace, 1843)" }] }), "(Lovelace, 1843)");
  assert.strictEqual(core.inTextFromRender({ items: [] }), "");
  assert.strictEqual(core.inTextFromRender(null), "");
});
