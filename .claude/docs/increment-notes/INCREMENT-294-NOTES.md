# Increment 294 — Reading Queue stratified by priority (drag within + across groups)

The Reading Queue (left pane AXES → Queue) was one flat, manually ordered list. It now shows papers **grouped by the
priority the user already set in the Library** — **High / Normal / Low / Unprioritized** — and papers stay movable:
reorder within a group, or **drag a paper across groups to re-prioritise** (e.g. Low → High when plans change).

## Implemented

- **Backend (surface the label, no new endpoint):**
  - `persistence/reading_queue_repo.py` — `list_reading_queue` now selects `papers.priority`.
  - `api/routers/reading_queue.py` — `ReadingQueueItem` gains `priority: str | None`, populated in the GET.
  - Cross-group moves reuse the existing `POST /papers/{id}/priority` (validates `PRIORITY_LEVELS`, accepts `null`
    to clear); reorders reuse `PUT /reading-queue/order` (the all-or-nothing full-id-list contract). No schema
    change, no migration, no new endpoint.
- **Frontend (`app/frontend/js/16_queue.jsx`):** the fetched items are grouped into the four ordered buckets
  (`queueGroupOf` maps `null` → Unprioritized); each bucket renders as a labelled section that is itself a drop
  target. A unified `moveTo(draggedId, targetGroup, targetId?)` handles both cases — a same-group drop is a plain
  reorder; a cross-group drop first `POST`s the new priority (Unprioritized → `null`), then splices the global order
  (next to the target row, or to the end of the target group when dropped on the group), then `PUT`s the full order.
  `onQueueChanged()` refreshes the Library list + the paper-card `ReadPriorityControl` so the new label shows there
  too. All drag handlers stay `readOnly`-guarded.
- **Styling (`styles.css`):** `.queue-group` + `.queue-group.drop` reuse the existing `.queue-pane.queue-drop`
  accent-soft/dashed drop recipe; the four headers reuse the muted priority colours (`pr-high` stronger via `--ink`,
  others `--ink-2`). No new tokens or colour semantics — priority stays a neutral triage label, never a status colour.
- **Cross-pane sync (cards ↔ Queue, one source of truth):** `papers.priority` now feeds *two* views, so a change in
  either must re-read in the other. `ReadPriorityControl` (`16b_readmark.jsx`) — previously self-contained ("no
  cross-pane refresh wiring") — gains an `onChanged` callback threaded `40_app → PaperList (10_pdf_layer) → PaperCard
  (10d) → ReadPriorityControl`; it fires **after a successful priority write** and bumps `queueRefresh` (the card is
  already optimistic, so no library reload needed). The reverse: `onQueueChanged` (40_app) now bumps **`setLibRefresh`
  too**, so a cross-group drag reloads the cards. Reuses the codebase's existing bump-counter pattern (no event bus).

## Key technical detail

Priority is a **display grouping layered on the single global manual order**, not a second stored order. `moveTo`
keeps the queue's `position` list intact (it always PUTs the complete member set), and re-derives the groups from
`priority` on each load — so the two existing contracts (priority-set + all-or-nothing reorder) compose without a new
concept. Dropping into **Unprioritized** sends `priority: null`, which the priority endpoint already accepts as
"clear".

## Principles (rule #9)

Priority is the user's **hand-set triage label, never an AI score** (the inc-220 contract). Grouping the user's own
labels produces no claim, signal, or ranking about the literature — it is the user's data, organised the way they
asked (aligned with "defaults/labels are the user's"). No egress, no provenance/fact-vs-candidate change.

## Manual verification script

App on :8888 → left pane **AXES → Queue** with papers of mixed priority. Confirm four sections **High / Normal / Low
/ Unprioritized**; a paper with no priority set sits under Unprioritized. Drag a Low paper onto the **High** group →
it moves there, and the Library priority filter + that paper's card priority now read **High**. Drag a paper onto
**Unprioritized** → its priority clears (Library shows "Priority ▾"). Reorder within a group and reload → the order
persists. An empty group still accepts a drop. On a read-only companion the groups show but there are no drag grips.
**Sync check:** set a **card's** priority to High → the paper jumps to the Queue's High group live (no reload); drag
it to Low in the Queue → the card now reads Low. (A running instance must be restarted / auto-reloaded to serve the
new `/reading-queue` `priority` field, else every row reads Unprioritized until then.)

## Pytest

`tests/test_reading_queue.py` +2 (priority surfaced in the list; priority settable/clearable and reflected in the
queue GET — the contract the cross-group drag reuses); `tests/test_frontend_assembly.py` +2 (the four strata +
`queueGroupOf` + the cross-group `moveTo`/priority wiring + the CSS; and the cards↔queue sync wiring). Full suite:
**1251 passed, 1 skipped**.
