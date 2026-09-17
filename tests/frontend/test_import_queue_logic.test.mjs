// Unit tests for app/frontend/js/10l_import_queue_logic.jsx's pure functions -- the seam behind the
// Import Queue review UI, tested because R1-R4 real-Edge acceptance cannot drive clicks inside
// Callosum's own Tauri window (see that file's header comment). Uses Node's BUILT-IN `vm` module to
// run the file's source directly: it contains zero JSX syntax, so no transpilation is needed, and no
// new test framework is introduced (same tier as node:test/node:assert, already used by the browser
// extension's own background.test.mjs). This is the first Node test for app/frontend/js/*.
//
// Run with: node --test tests/frontend

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, "..", "..", "app", "frontend", "js", "10l_import_queue_logic.jsx");

function loadLogic() {
  // `runInThisContext` (NOT `runInContext` with a fresh sandbox) deliberately: it executes the file's
  // top-level `function` declarations against the REAL global object, in THIS SAME realm -- a fresh
  // `vm.createContext({})` sandbox has its own separate `Object`/`Array` prototypes, which makes every
  // object/array the loaded code returns fail `assert.deepEqual` from `node:assert/strict` (structurally
  // identical but not reference-equal across realms). Safe here because this file defines nothing that
  // collides with an existing global.
  const source = readFileSync(SOURCE_PATH, "utf8");
  vm.runInThisContext(source, { filename: SOURCE_PATH });
  return globalThis;
}

const logic = loadLogic();
const {
  importQueueStateHeadline,
  importQueueStateActions,
  importQueueAttachmentConflictExplanation,
  importQueueProcessingFailedExplanation,
  importQueueDeleteConfirmMessage,
  buildPreviewDoiRequest,
  buildConfirmRequest,
  buildRetryRequest,
  buildDeleteRequest,
  buildPdfPreviewRequest,
  buildListRequest,
  openExistingPaperArgs,
  importQueueActionRequiresOnChanged,
} = logic;

// ── state → headline ────────────────────────────────────────────────────────────────────────────

test("importQueueStateHeadline covers every real backend state pair", () => {
  const cases = [
    ["unresolved", "pending_review", "Saved — needs review"],
    ["resolved", "attachment_conflict", "Identified — attachment needs review"],
    ["resolved", "processing_failed", "Saved — processing could not finish"],
    ["resolved", "indexing_unavailable", "Saved — processing could not finish"],
  ];
  for (const [identity, promotion, expected] of cases) {
    assert.equal(importQueueStateHeadline(identity, promotion), expected, `${identity}:${promotion}`);
  }
});

test("importQueueStateHeadline falls back honestly for an unrecognized pair, never a raw enum", () => {
  const result = importQueueStateHeadline("resolved", "some_future_state");
  assert.equal(result, "Saved — needs review");
  assert.ok(!result.includes("some_future_state"));
});

// ── state → actions ─────────────────────────────────────────────────────────────────────────────

test("importQueueStateActions: attachment_conflict offers Open existing Paper + Delete only", () => {
  assert.deepEqual(importQueueStateActions("resolved", "attachment_conflict", true), [
    "open_existing_paper",
    "delete",
  ]);
  // A best_candidate flag never changes this branch -- attachment_conflict already has a resolved
  // identity; there is nothing left to "confirm".
  assert.deepEqual(importQueueStateActions("resolved", "attachment_conflict", false), [
    "open_existing_paper",
    "delete",
  ]);
});

test("importQueueStateActions: processing_failed / indexing_unavailable offer Retry + Delete", () => {
  assert.deepEqual(importQueueStateActions("resolved", "processing_failed", false), ["retry", "delete"]);
  assert.deepEqual(importQueueStateActions("resolved", "indexing_unavailable", false), ["retry", "delete"]);
});

test("importQueueStateActions: pending_review with a candidate offers Confirm + Enter DOI + Delete", () => {
  assert.deepEqual(importQueueStateActions("unresolved", "pending_review", true), [
    "confirm_candidate",
    "enter_doi",
    "delete",
  ]);
});

test("importQueueStateActions: pending_review with NO candidate omits Confirm (nothing to confirm)", () => {
  assert.deepEqual(importQueueStateActions("unresolved", "pending_review", false), ["enter_doi", "delete"]);
});

// ── explanatory copy: exact, non-alarming, never a raw enum ────────────────────────────────────────

test("importQueueAttachmentConflictExplanation is the exact required sentence", () => {
  assert.equal(
    importQueueAttachmentConflictExplanation(),
    "This paper is already in your Library and Callosum cannot safely attach this captured PDF automatically."
  );
});

test("importQueueProcessingFailedExplanation reassures rather than alarms", () => {
  const text = importQueueProcessingFailedExplanation();
  assert.ok(text.toLowerCase().includes("safe"));
  assert.ok(!text.toLowerCase().includes("failed"));
});

test("importQueueDeleteConfirmMessage states artifact-scoped deletion explicitly", () => {
  const text = importQueueDeleteConfirmMessage();
  assert.ok(text.includes("capture history"));
  assert.ok(text.includes("can't be undone"));
});

// ── action → HTTP contract ──────────────────────────────────────────────────────────────────────

test("buildListRequest", () => {
  assert.deepEqual(buildListRequest(), { method: "GET", path: "/library/import-queue", body: null });
});

test("buildPreviewDoiRequest", () => {
  assert.deepEqual(buildPreviewDoiRequest("abc-123", "10.1234/x"), {
    method: "POST",
    path: "/library/import-queue/abc-123/preview-doi",
    body: { doi: "10.1234/x" },
  });
});

test("buildConfirmRequest carries both doi and source", () => {
  assert.deepEqual(buildConfirmRequest("abc-123", "10.1234/x", "candidate"), {
    method: "POST",
    path: "/library/import-queue/abc-123/confirm",
    body: { doi: "10.1234/x", source: "candidate" },
  });
  assert.deepEqual(buildConfirmRequest("abc-123", "10.1234/x", "manual"), {
    method: "POST",
    path: "/library/import-queue/abc-123/confirm",
    body: { doi: "10.1234/x", source: "manual" },
  });
});

test("buildRetryRequest", () => {
  assert.deepEqual(buildRetryRequest("abc-123"), {
    method: "POST",
    path: "/library/import-queue/abc-123/retry",
    body: null,
  });
});

test("buildDeleteRequest", () => {
  assert.deepEqual(buildDeleteRequest("abc-123"), {
    method: "DELETE",
    path: "/library/import-queue/abc-123",
    body: null,
  });
});

test("buildPdfPreviewRequest", () => {
  assert.deepEqual(buildPdfPreviewRequest("abc-123"), {
    method: "GET",
    path: "/library/import-queue/abc-123/pdf",
    body: null,
  });
});

test("every request builder URI-encodes the artifact id", () => {
  const dangerous = "abc/../../etc?x=1";
  const encoded = encodeURIComponent(dangerous);
  assert.equal(buildRetryRequest(dangerous).path, `/library/import-queue/${encoded}/retry`);
  assert.equal(buildDeleteRequest(dangerous).path, `/library/import-queue/${encoded}`);
  assert.equal(buildPdfPreviewRequest(dangerous).path, `/library/import-queue/${encoded}/pdf`);
  assert.equal(buildConfirmRequest(dangerous, "10.1/x", "manual").path, `/library/import-queue/${encoded}/confirm`);
  assert.equal(buildPreviewDoiRequest(dangerous, "10.1/x").path, `/library/import-queue/${encoded}/preview-doi`);
});

// ── "Open existing Paper" args ──────────────────────────────────────────────────────────────────

test("openExistingPaperArgs maps resolved_paper_id/title to the onOpenPaper contract", () => {
  assert.deepEqual(openExistingPaperArgs({ resolved_paper_id: 42, resolved_paper_title: "A Captured Paper" }), {
    id: 42,
    title: "A Captured Paper",
  });
});

test("openExistingPaperArgs tolerates a missing title", () => {
  assert.deepEqual(openExistingPaperArgs({ resolved_paper_id: 42, resolved_paper_title: null }), {
    id: 42,
    title: null,
  });
});

// ── onChanged expectation ───────────────────────────────────────────────────────────────────────

test("importQueueActionRequiresOnChanged is true for every mutating action", () => {
  for (const action of ["confirm_candidate", "enter_doi_confirm", "retry", "delete"]) {
    assert.equal(importQueueActionRequiresOnChanged(action), true, action);
  }
});

test("importQueueActionRequiresOnChanged is false for read-only actions", () => {
  for (const action of ["preview_doi", "list", "pdf_preview", "open_existing_paper", "enter_doi"]) {
    assert.equal(importQueueActionRequiresOnChanged(action), false, action);
  }
});
