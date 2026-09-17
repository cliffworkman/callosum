// #61 provisional ingestion — human review increment: the PURE, side-effect-free seam behind the
// Import Queue review UI. No JSX syntax, no React hooks, no `api`/`apiPost`/`apiDelete` calls — every
// function here returns data (copy strings, action-token lists, request shapes), never performs
// network I/O. This is deliberate: R1-R4 real-Edge acceptance cannot drive clicks inside Callosum's
// own Tauri window, so the state→copy/actions mapping and the action→HTTP contract are pinned by a
// Node test (`tests/frontend/test_import_queue_logic.test.mjs`) that loads this exact file via
// `vm.runInContext` — no transpilation needed since nothing here is JSX, and no new test framework
// (Node's built-in `vm`, same tier as `node:test`/`node:assert` already used for the extension).
// `10l_import_queue.jsx`'s actual React components call these functions, then perform the real
// `api()`/`apiPost()`/`apiDelete()` call using the shapes returned here.

const IMPORT_QUEUE_STATE_COPY = {
  "unresolved:pending_review": "Saved — needs review",
  "resolved:attachment_conflict": "Identified — attachment needs review",
  "resolved:processing_failed": "Saved — processing could not finish",
  "resolved:indexing_unavailable": "Saved — processing could not finish",
};

function importQueueStateHeadline(identityState, promotionState) {
  return IMPORT_QUEUE_STATE_COPY[`${identityState}:${promotionState}`] || "Saved — needs review";
}

function importQueueStateActions(identityState, promotionState, hasBestCandidate) {
  if (promotionState === "attachment_conflict") return ["open_existing_paper", "delete"];
  if (promotionState === "processing_failed" || promotionState === "indexing_unavailable") return ["retry", "delete"];
  return hasBestCandidate ? ["confirm_candidate", "enter_doi", "delete"] : ["enter_doi", "delete"];
}

function importQueueAttachmentConflictExplanation() {
  return "This paper is already in your Library and Callosum cannot safely attach this captured PDF automatically.";
}

function importQueueProcessingFailedExplanation() {
  return "Your PDF is safe — Callosum just couldn't finish processing it yet.";
}

function importQueueDeleteConfirmMessage() {
  return "Delete this capture? This permanently removes the saved PDF and its capture history from Callosum — this can't be undone.";
}

function buildPreviewDoiRequest(artifactId, doi) {
  return { method: "POST", path: `/library/import-queue/${encodeURIComponent(artifactId)}/preview-doi`, body: { doi } };
}

function buildConfirmRequest(artifactId, doi, source) {
  return { method: "POST", path: `/library/import-queue/${encodeURIComponent(artifactId)}/confirm`, body: { doi, source } };
}

function buildRetryRequest(artifactId) {
  return { method: "POST", path: `/library/import-queue/${encodeURIComponent(artifactId)}/retry`, body: null };
}

function buildDeleteRequest(artifactId) {
  return { method: "DELETE", path: `/library/import-queue/${encodeURIComponent(artifactId)}`, body: null };
}

function buildPdfPreviewRequest(artifactId) {
  return { method: "GET", path: `/library/import-queue/${encodeURIComponent(artifactId)}/pdf`, body: null };
}

function buildListRequest() {
  return { method: "GET", path: "/library/import-queue", body: null };
}

function openExistingPaperArgs(item) {
  return { id: item.resolved_paper_id, title: item.resolved_paper_title || null };
}

// Which review actions mutate server state and therefore must refresh the persistent header count
// (`onChanged()`) on success. Read-only preview/list/pdf-fetch actions never do.
function importQueueActionRequiresOnChanged(action) {
  return action === "confirm_candidate" || action === "enter_doi_confirm" || action === "retry" || action === "delete";
}
