<!-- qa-coverage
api: GET /reading-queue
api: POST /reading-queue
api: PUT /reading-queue/order
api: DELETE /reading-queue/{paper_id}
fe: 16_queue.jsx
fe: 25_detail.jsx
-->

# ROUTE 49 - Reading queue (the to-read Queue tab)

**Tier:** 1 local-stateful
**Goal:** Exercise the reading-queue surface — add (drag a library card onto the Queue + the Details "+ Reading
queue" button), drag-to-reorder, remove (× and ✓ Done), and the honesty/safety boundaries (a queue is a plain
user-authored ordered list — no score/claim; local-only, no egress; idempotent; trashed papers hidden; reorder is
all-or-nothing). The Queue is the third tab of the left-pane AXES section ([Axes | Tags | Queue], `16_queue.jsx`);
the Details add button lives in `25_detail.jsx`.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** — the queue is entirely local (no external
fetch), so it runs with egress unset; register console/pageerror/request listeners on any opened page.

## Standing assertions

- **A queue is a user-authored ordered list — never a claim/score.** It records *what the user chose to read*, in
  *the order they chose*. There is no AI scoring, ranking, or judgment anywhere in it (the inc-211 curated-axis /
  inc-208 saved-search class). A surfaced "score"/"recommendation" would be **wrong** for this feature.
- **Local-only, no egress.** The 4 `/reading-queue/*` endpoints touch only the local DB; no request goes to any
  external/genai host. Any egress is **Critical**.
- **Add is idempotent.** `POST /reading-queue {paper_id}` returns `{added:true}` the first time, `{added:false}`
  thereafter — never a duplicate row. A nonexistent paper → **404**.
- **Trashed papers are hidden.** A paper that is soft-deleted (Trash) but still has a queue row must **not** appear
  in `GET /reading-queue`; a purged paper's queue row is CASCADE-dropped.
- **Reorder is all-or-nothing.** `PUT /reading-queue/order {paper_ids}` requires the list to be **exactly** the
  current members; a partial/foreign id set → **422** (no partial write).
- **Remove is idempotent + non-destructive to the paper.** `DELETE /reading-queue/{paper_id}` → 204 whether or not
  it was queued; it removes only the *queue membership*, never the paper (both × and ✓ Done call it).
- **Priority strata are the user's own label, not a score (inc 294).** `GET /reading-queue` carries each row's
  `priority` (`high`/`normal`/`low`/null); the Queue tab groups rows into **High / Normal / Low / Unprioritized**
  (null → Unprioritized). This is the user's hand-set triage label re-displayed — **never** an AI ranking. Dragging a
  row **across** groups reuses `POST /papers/{id}/priority` (dropping into Unprioritized sends `priority:null` to
  clear), then the existing all-or-nothing reorder — no new endpoint, no egress.

## Steps

1. `GET /reading-queue` on a clean instance → `[]`.
2. `POST /reading-queue {paper_id:A}` → `{added:true}`; again → `{added:false}`; `{paper_id:<nonexistent>}` → 404.
3. `POST` a second paper B; `GET /reading-queue` → `[A, B]` with `title`/`authors`/`year` shaped for display.
4. `PUT /reading-queue/order {paper_ids:[B,A]}` → 204; `GET` → `[B, A]`. `PUT {paper_ids:[A]}` → **422**.
5. Soft-delete A (Trash) → `GET /reading-queue` no longer lists A.
6. `DELETE /reading-queue/B` → 204; again → 204; `GET` → `[]`.
7. (UI) Open the **Queue** tab (empty state) → drag a library card onto the panel → it appears; open a paper's
   Details → **+ Reading queue** → it appears (the tab reloads); drag the ⠿ grip to reorder; **✓ Done** / **×**
   each remove a row; clicking a row opens the paper.
8. (priority strata) `GET /reading-queue` → each item has a `priority` field. Set A's priority via `POST
   /papers/{A}/priority {priority:"high"}` → `GET /reading-queue` shows A `priority:"high"`. `POST {priority:null}`
   → clears it (null). (UI) Queue shows **High / Normal / Low / Unprioritized** headers; dragging a row from one
   group onto another moves it there **and** the Library priority filter / paper-card control reflect the new label;
   an empty group still accepts a drop; the read-only companion shows the groups but no drag handles.

## Pass criteria

- All 4 endpoints behave (idempotent add + 404; ordered list excluding trashed; reorder 422 on a foreign set;
  idempotent remove); the UI add (drag + button) / reorder / remove / open all work.
- 0 console/page errors and 0 external/genai-host requests across any opened page.
