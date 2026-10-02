# Browser Capture paper-index correction — local verification, 2026-10-02

## Anchors and preserved evidence

Accepted candidate: `2a80b7348df0377ced4aa06d35df67e6bbad965c`, clean
`fix/browser-pdf-capture-responsive`. New local branch: `fix/capture-admission-paper-index`.
Remote `browser-capture-research` and open draft PR #103 both remained at
`fcaabb7a76ec48620a5404c04e974f2a98e9f9a9` when rechecked. The only two commits between remote
and accepted candidate are `f241f9aa` (Windows native-host paths) and `2a80b734` (PDF recognition/
responsive capture). None changes provisional confirmation, PDF ingest or the shared admission hook.
Canonical main remains `4bce1a77c8ffa774789a62d97c22f22ea75ee307`, with pre-existing untracked
`.claude/docs/legacy_engine/` and `experiments/`, left untouched.

The original accepted worktree is not advanced. No source beyond its accepted head was silently
included. No QA process was stopped, no accepted database was opened for writes, and no installed
app, runtime, extension or native-host registration was changed.

Preserved Windows evidence is under
`C:\Users\cliff\Callosum-Windows-QA-0516-20260930\candidate-2a80b734` and
`private-backups\completed-2a80b734-20261002-083836` beneath that QA root.

| Artifact | SHA-256 |
|---|---|
| Installer `Callosum_0.5.15_x64-setup.exe` | `8588cfd3923f25d9a72e66584d7b9c4ed2c228b2c0d8469873f57988b117f008` |
| Completed `callosum.sqlite` snapshot | `6f3d63e47a4b738f6abb347fbdde0c735964dd36fff5813f5e028e4060b18a65` |
| Completed backend log | `d4629b60fde0f0fd9a352fbee66097a73fb0c821ba2faac4df902d041699ec7c` |
| Original Ioannidis PDF | `ffc1005680cb620eec4c913437dfabbf311b535cfe16cbaeb2faec1f92afc362` |

The local, untracked `.claude/paper-index-evidence/` contains an anchor receipt and a 28-file
before/after evidence-hash manifest, including the original collector/analysis receipts. These records
do not overwrite the historical acceptance report. Parked user state and frozen research worktrees
remain outside the fix. No paired credential/session token was read or printed.

## Established cause and scope

1. Capture stores provisional bytes; the real fixture's page-1 body DOI remains observed/unverified.
2. `preview_doi` performs lookup without canonical creation/indexing.
3. The actual `/library/import-queue/{id}/confirm` route invokes `confirm_identity`, persists the
   human action, then commits `_resolve_and_admit_doi` / shared `add_paper_by_doi`.
4. `attempt_attach_to_paper` stages the PDF, invokes `attach_pdf_to_paper`, commits chunk extraction
   and `embed_chunks`, then finishes promotion and preserves the human action.
5. That orchestration never invoked `ensure_paper_indexed` or `embed_papers`. A fully chunked paper
   therefore had no metadata embedding. The collector was correct: the preserved Windows snapshot
   has 122 actual current chunk vectors for paper 6, zero paper vectors for it, and five metadata
   vectors for the earlier failed-capture records (127 total).

The omission also affects `_attempt_promotion` (automatic admission) and `retry_promotion`, which
share `attempt_attach_to_paper`. It predates both Windows fixes. Ordinary Add-by-DOI calls the
existing shared post-commit helper, Discovery and Zotero likewise use it, while ordinary Library
scan/import job orchestration explicitly calls `embed_papers` in addition to chunk indexing.
Attachment ingest alone deliberately does not own canonical admission. No unrelated call sites
were refactored.

The existing `ADMISSION_FRONT_ENDS` matrix only contained DOI, Discovery and Zotero. Existing generic
capture coverage exercised metadata-envelope admission, not provisional PDF confirmation. The matrix
now includes confirmation and automatic PDF admission so this omission is enforced at real routes.

## Minimal repair and preserved behavior

One production file gains six lines: import the existing `ensure_paper_indexed` and call it at the
shared post-admission attach seam. Every caller has already committed or loaded the canonical paper.
The call applies whether the paper is newly created or reused, and whether attachment is allowed.
The helper owns normal model/version idempotency, metadata text, vector-store writes and nonfatal
logging. No independent Browser Capture embedding algorithm, model or indexing policy is introduced.

The resolver/DOI rules, human-confirmation event, artifact ownership, PDF copy/cleanup, chunking,
queue states, preview identity, transport and update notifications are unchanged. Model failures can
still leave metadata unindexed, as the existing helper contract requires; they are logged rather
than causing admission failure. This change is not a global historical backfill and does not repair
the accepted QA paper in place.

## Verification chronology and results

Before the production edit, the added real-fixture confirmation matrix case reached successful
promotion with an intact PDF and a vector for every extracted chunk, then failed `0 == 1` for the
paper embedding. Receipt: `red-invariant.log`. Early test-draft mistakes (attachment column name and
assuming the packaged extraction count in a different development runtime) were corrected before
this decisive regression; their logs are retained separately and are not defect evidence.

The local development extractor produces 92 chunks for this PDF, versus 122 on the accepted packaged
runtime. Tests assert every locally extracted chunk is indexed, not an invented 122 result. This is
why final packaged-runtime acceptance still requires its established 122-vector count.

Final local results (Windows, Anaconda Python 3.12.7 / PyMuPDF 1.27.2.3):

- Focused: `test_admission_indexing`, `test_import_queue`, `test_provisional_doi_review`,
  `test_embeddings`: **88 passed in 88.16 seconds**. The expanded admission file contains 18 tests
  (12 added), including a real sqlite-vec reopen/search check with an explicitly fake 3D model.
- Broader: `test_capture`, `test_capture_responsiveness`, `test_capture_updates`,
  `test_capture_trust_boundaries`, `test_queue_filesystem_authority`, `test_provisional_module_seams`,
  `test_doi_add`, `test_acquisition`, `test_sqlite_retry`, `test_library_scan`:
  **180 passed, 2 skipped in 151.26 seconds**. The two Windows skips are POSIX permission-bit tests.
- Total: **268 passed, 2 skipped**, without counting earlier overlapping development runs.
  All runs used `python -B -m pytest -p no:tach ... -q --show-capture=no`; Tach ran separately.
- Ruff format/check, diff whitespace check, all applicable pre-commit hooks (including Bandit,
  600-line budget and Tach), and the API QA-surface coverage gate passed.
- Website gate initially caught the prior preview-marketing deferral expiring at increment 603.
  The existing explicit decline was extended to 604 with truthful current acceptance limits;
  the tool reports OK **with acknowledged drift**, not a newly reviewed marketing/screenshot pass.
  No published visual/copy changed. The prior review/decline remains available in git history.

An initial broader command named nonexistent `test_library.py` and ran no tests; the corrected
command used the actual `test_library_scan.py` listed above. The full unrelated root suite, fresh
remote CI, a packaged build and a real-model performance benchmark were not run under this scoped
authorization. All automated confirmation actions above are synthetic test requests, not human
acceptance clicks.

Exact changed files:

- `app/backend/capture/provisional.py` — the six-line production correction.
- `tests/test_admission_indexing.py` — expanded shared admission regressions.
- `.claude/CLAUDE.md` — shared-seam convention and scoped increment counter.
- `.claude/changes.md` — chronological change/lineage entry.
- `.claude/docs/worktree-topology.md` — new isolated branch and preservation boundary.
- `.claude/qa-routes/route_27_scan_import.md` — distinct paper/chunk indexing assertions.
- `.claude/docs/increment-notes/INCREMENT-604-NOTES.md` — increment record.
- `.claude/docs/research/2026-10-02_capture-paper-index.md` — this separate follow-up receipt.
- `www/showcase-coverage.json` — continuation of the existing explicit marketing deferral only.

## Minimum remaining indexing acceptance

The prior genuine Windows 11/Chrome extension identity, native-host handshake, capture, provisional
review, DOI lookup, explicit confirmation, automatic queue/Library refresh, exact PDF, chunk vectors,
PDF opening and restart persistence remain valid evidence of `2a80b734`. They are not relabeled as a
pass for a later build. The original overall report remains PARTIAL for the missing metadata index;
independent clean-profile/pristine-cache or other-platform release gates are not waived.

After approval, perform one targeted isolated confirmation/indexing replay using the corrected exact
source and the same unmodified Windows managed runtime. Use a fresh database, settings and Library
with the checksum-verified original fixture. Do not reuse or alter the accepted QA database/Library.
Stage one provisional artifact through the existing route (a disclosed test stimulus, not a genuine
Chrome click), record its zero canonical papers/indexes, preview, then confirm through the actual
confirmation endpoint. Require:

Record a scripted confirmation as a synthetic acceptance stimulus even though it exercises the
route's `user_confirmed_candidate` schema; it is not evidence of a new human confirmation click.

- one canonical paper with the expected DOI and retained `user_confirmed_candidate` provenance;
- one intact 255,629-byte PDF with the original SHA-256;
- 122 current chunk embeddings and one current metadata embedding, each with a readable finite,
  nonzero 384-dimensional vector under the actual installed model;
- empty pending queue, no duplicate paper/attachment/index rows on content replay, unchanged original
  observations and human-confirmation record, and persistence after database/backend reopen;
- record confirmation-to-index completion duration separately; do not infer a UI latency or a new
  browser acceptance pass from a scripted backend check.

That targeted result can close the downstream indexing gate in a new receipt. A full Chrome run is
not required by this six-line hook change. A later packaged release still must show it contains the
tested source and complete the existing release CI/support-matrix gates. No installer build, replay,
push, PR mutation, merge, bump, tag, runtime publication, updater release or store submission occurred.

## Review, documentation drift and lineage

Security: no new endpoint, input, path, fetch, dependency, authorization or file-write mechanism;
existing shared local vector storage is reused after canonical admission. Negative tests cover
nonfatal metadata failure, retained queued bytes after failed attachment, and attachment conflict.
Principles: no candidate is promoted merely to index it; observed evidence and human authority stay
separate. Experience: backend-only invariant repair; the corpus builder's confirmed paper participates
in the same metadata retrieval as other admissions without another user action. Help/UI copy unchanged.

Latency: one missing metadata input through the already injected/app-owned model; a current index is
a no-inference check. No model construction, batching rewrite, detached task, event-loop blocking or
polling change. Confirmation remains in its existing synchronous worker; automatic capture remains in
its awaited worker. Additional real-model inference cost is not benchmarked by fake-model tests and
is part of the targeted follow-up, rather than an unsupported performance claim.

The inherited CLAUDE overview still cites increment 580 and an old suite receipt, while numbered
history reaches 603; the increment-workflow counter was even older (575). This scoped follow-up is
604. The old release paragraph calling the updater unbuilt conflicts with later documented shipped
updater increments and existing Rust/workflows. Those historical claims are not release authority;
the established bump tool, annotated-tag/GitHub Release/updater workflow remains unchanged.

2026-10-02 | Evidence/authorization | Cliff — performed physical Windows acceptance and authorized follow-up.
2026-10-02 | Diagnosis/implementation/tests | Cody (Codex) — isolated the absent metadata index, reproduced the
source defect, reused the shared hook and preserved empirical evidence.
2026-10-02 | Scope/reframing | Lucien — required a shared admission-invariant repair and a targeted follow-up,
without erasing the valid browser acceptance or inventing capture-specific embedding behavior.
