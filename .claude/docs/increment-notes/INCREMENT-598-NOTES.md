# Increment 598 — Reader reference lookup → acquire OA + Critique (GitHub #79)

A follow-on to inc 595's "Find referenced paper…". After confirming a cited reference, the reader flow now
attempts OA acquisition and — **only once the paper has usable full text** — offers a one-click **Critique this
paper**, so a reader of paper A can interrogate the evidence of a cornerstone citation B without leaving A.
**Frontend-only; zero backend change.**

## Scope correction honored (no durable queue)
Per the maintainer's correction, this does **NOT** build a `pending_critiques` table, critique-intent
endpoints, an acquisition completion hook, a background watcher, or any cross-job state machine. The "queue"
begins only **after** successful acquisition + fulltext readiness — it is a synchronous "critique now that full
text is ready", not "remember and monitor until evidence appears." The whole feature lives in
`30h_reference_finder.jsx`, composing existing endpoints.

## Flow (`30h_reference_finder.jsx`)
1. Confirm candidate → `POST /discovery/save` (add/dedup) — existing.
2. `_fulltextReady(paperId)` = `GET /papers/{id}.chunk_count > 0`. If already chunked (existing paper / re-run)
   → Critique available immediately (no re-acquire).
3. Else `POST /papers/{id}/acquire-oa`, poll `GET /papers/acquire-oa/{job_id}` (via the shared
   `observeJobUntilTerminal`), then **re-check `chunk_count`** — a downloaded-but-unparsed PDF
   (`attachment_count>0, chunk_count==0`) is NOT usable.
4. **Full text ready** → **Critique this paper** → the canonical single-paper `POST /papers/{id}/critical-read`
   (polled via `/critical-read/{job_id}`) — the ONLY Critique implementation; the run persists and is reviewable
   in that paper's Synthesize → Critique. Modal shows running → ready + an Open-paper action; the user can close
   and keep reading.
5. **No usable full text** (no OA / acquire error / downloaded-but-no-chunks) → an honest "Critique needs the
   full paper" message with the specific reason. **Nothing is queued or retained.**

Poll cancel-fns (`acqPollRef`/`critPollRef`) + a `mountedRef` guard cancel on unmount and prevent
post-unmount state writes (keeps the e2e zero-console-error property).

## Key technical detail — the fulltext gate is LOAD-BEARING for the epistemic boundary
`methods.critical_review.extract_claim_sentences` extracts claims from the paper's **abstract first**, falling
back to chunks only when there is no abstract. So the canonical Critical Read *would* critique a metadata-only
paper from its abstract — exactly what #79 forbids ("metadata/title/abstract/snippets are never sufficient").
The boundary is therefore enforced by the **reader flow's `chunk_count > 0` gate**, which never POSTs
`critical-read` for a chunkless paper — not by the backend extractor (deliberately unchanged; altering shared
Critique extraction is out of this thin slice's scope, and would change the existing Synthesize → Critique
behavior). Documented so this is not mistaken for defense-in-depth.

## Reading-edge provenance
Not recorded — there is no existing principled field for "B was encountered while reading A", and the scope
correction forbids inventing one (no Crossref overload, no anchored highlights, no citation graph / #23). The
critique run itself is durable provenance that B was critiqued.

## Testing
- `tests/test_reader_critique_boundary.py` (2): the `chunk_count` signal distinguishes metadata-only (0) from
  full-text (>0) — the signal the reader gate reads; and `extract_claim_sentences` returns non-empty for a
  chunkless-but-abstracted paper — proving the gate cannot be left to the backend (locks in *why* the gate
  exists).
- `tests/test_frontend_assembly.py` (87) — the modified chunk assembles.
- **Manual (honest):** the interactive confirm → acquire → fulltext-gate → Critique flow needs a real run
  (the modal opens from a PDF text selection, which headless Playwright can't reliably drive — same reason inc
  595's modal has no e2e test). Acceptance cases to verify by hand: full text already present → Critique runs;
  OA success + chunked → Critique enabled; OA failure / no OA / downloaded-but-no-chunks → honest no-access,
  nothing queued, paper kept; Critique never offered on a metadata-only paper; later manual PDF attach → Critique
  from Synthesize → Critique.

## Gates / scope
Reuses `/discovery/save`, `/papers/{id}/acquire-oa`, `/papers/acquire-oa/{job_id}`, `/papers/{id}`,
`/papers/{id}/critical-read`, `/critical-read/{job_id}`, `observeJobUntilTerminal`, `onOpenPaper` — **no new
backend endpoint/table/hook**, so the security-audit gate is not triggered (no new external surface). QA route
94 updated; help corpus updated. No `experiments/**` / `summarization/**` change. Line budget: `30h` 220 ≤600.
Frozen 0.6/0.7 Ask experiment untouched.

**Next up:** #77 (inc 599) — Discover Search: expose search-capable providers (arXiv / Europe PMC / PsyArXiv).
