# Increment 587 — three fixes from live 0.5.9 testing (DB-lock, explicit delete, OA self-fetch link), shipped in 0.5.10

Alongside inc 586's cache-bust, live 0.5.9 use surfaced three more items, all folded into the same 0.5.10 patch.

## 1. `database is locked` on a duplicate same-paper OA acquisition (the bug)

**Report:** imported a DOI (eLife) → its backend-orchestrated auto-OA started fetching → user left the modal and,
while it was still searching, clicked **"Acquire OA copy"** in Details for the same paper → a long
`OperationalError: (sqlite3.OperationalError) database is locked [SQL: INSERT INTO attachments …]` (paper 82).

**Root cause:** two acquire jobs for the *same paper* ran concurrently (the auto-OA background task + the manual
button's), and both reach `import_oa_pdf` inside `engine.begin()`. SQLite has a single writer, so the second
`INSERT INTO attachments` collided. Background tasks aren't covered by the request-path
`SqliteWriteRetryMiddleware`, so it surfaced raw.

**Fix (root cause, `app/backend/api/job_store.py` + `routers/acquisition.py`):** a new
`JobStore.create_or_get_active_matching(nav, match_keys)` atomically **reuses a pending/running job whose nav
matches on the given keys, else creates one** (the boolean tells the sole creator to schedule the worker) — the
scoped sibling of `create_or_get_active`. Both acquire entry points (`acquire_oa_start` and the by-DOI import's
auto-OA) now dedup on `("paper_id",)`, so a paper can have at most **one in-flight acquisition**. The manual
button now simply returns the already-running job to poll. A *finished* (done/error) job never matches, so a
retry after a miss still starts fresh. This removes the concurrent same-paper writer entirely (the reported
collision) rather than papering over it with a retry. Resolver priority, the OA bright line, and the cascade
(inc 585) are untouched.

**Tests:** `tests/test_job_store.py` — per-target dedup (same paper reuses, different papers independent), a
fresh job after the prior one is terminal, and atomicity under 8 concurrent same-paper calls. (Endpoint-level
dedup isn't observable via `TestClient`, whose background tasks run synchronously — the first job finishes
before the second request — so the store is the correct test level.)

## 2. Per-card delete is now an explicit "Delete" button, not a hidden ⋯ menu (#57 revision)

**Report (from the same reporter whose #57 prompted the affordance):** hiding delete behind a `⋯` overflow menu
recreates the exact discoverability problem #57 set out to fix — she still couldn't tell how to delete a paper.

**Fix (`app/frontend/js/10d_papercard.jsx` + `styles.css`):** replaced `PaperCardMenu` (the ⋯ dropdown) with an
always-visible, plainly-labelled **`Delete`** button (`PaperTrashButton`) in the card foot. It routes through
the **same** shared `onTrash`/`trashPapers` primitive, which always confirms (`window.confirm`) and only
soft-deletes to Trash (restorable) — so surfacing it plainly carries no accidental-deletion risk. New
`.paper-trash` recipe mirrors the `.paper-priority` pill footprint; neutral at rest, **red on hover**
(`--danger`, DESIGN §4 destructive); `aria-label`/`title` spell out "moves to Trash, restorable." Removed the
now-dead dropdown (rule #5). No backend change — still `DELETE /papers/{id}` (soft delete).

## 3. A universal "get it yourself" link when OA download is blocked (both surfaces)

**Report:** 0.5.9's 403 presentation is much nicer, but many downloads 403 because publishers block automated
fetches (following the DOI in a browser hit a CAPTCHA) — and a scraping block shouldn't stop a user from getting
a paper *themselves*. Give them a link to the article both in the **Wanted** modal and next to **"Acquire OA
copy"** in Details.

**Fix (frontend-only — the DOI was already on both surfaces):**
- **Details** (`25a_detail_actions.jsx`, `25_detail.jsx`): `AcquireOaRow` takes the paper's `doi`; on a miss
  (no candidate *or* all candidates blocked) it now offers **"Open article page ↗"** (opens `https://doi.org/<doi>`
  in the user's browser) beside the existing "Get via my library →" resolver hand-off.
- **Wanted modal** (`26_wanted.jsx`): every not-yet-fulfilled row with a DOI gets an **"Open article ↗"** link.

**Values note (APPROACH-AVOIDANCE):** this is the *free-and-legal hand-off*, not paywall circumvention (a
veto-level boundary). callosum does not fetch or scrape anything here — it opens the publisher's own page so the
user obtains the paper through their own access, exactly like the pre-existing OpenURL "Get via my library"
hand-off, but always available with no setup.

## Gates

Backend: `tests/test_job_store.py`/`test_acquisition*.py`/`test_doi_add.py`/`test_wanted.py`/`test_retraction.py`
green. Frontend rebuilt (`callosum-app.html`); `test_frontend_assembly.py` green; line budget OK; ruff clean.
DESIGN §4 honored (new `.paper-trash` uses `--danger` for destructive). No new endpoint or external fetch → no
new security-audit trigger (the DOI link is a browser navigation, not a server fetch). Ships in **Desktop 0.5.10**
with inc 586.
