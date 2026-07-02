<!-- qa-coverage
api: POST /papers/{paper_id}/read
api: POST /papers/{paper_id}/priority
fe: 16b_readmark.jsx
-->

# ROUTE 50 - Reading markers (read/unread toggle + priority)

**Tier:** 1 local-stateful
**Goal:** Exercise the per-paper reading markers (inc 220) — a manual **read/unread** toggle and a user-set
**priority** (high/normal/low) on each library card (`16b_readmark.jsx`'s `ReadPriorityControl`, rendered in
PaperCard's foot) — plus their honesty/safety boundaries (both are user labels, never an AI score/judgment;
local-only, no egress; the priority allowlist is enforced server-side).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** — entirely local (no external fetch);
register console/pageerror/request listeners on any opened page.

## Standing assertions

- **Read & priority are USER labels, never an AI signal.** Nothing computes or suggests them; the user sets them
  by hand. A "read" marker is workflow state; "priority" is the user's triage order — neither is a quality/rank
  verdict about the paper (the inc-207 declined-ratings logic: a hand label, not a composite score).
- **Local-only, no library-text egress.** `POST /papers/{id}/read` + `POST /papers/{id}/priority` touch only the
  local DB. The egress invariant (#3) is about *library text leaving to a remote LLM* — ANY request to a
  Gemini / `generativelanguage` / genai host with egress unset is **Critical**. (The app loads React/ReactDOM +
  pdf.js from the cdnjs CDN by design — a framework CDN fetch is expected, NOT an egress violation; do not flag it.)
- **Priority is allowlist-validated.** `priority` must be `"high"`/`"normal"`/`"low"` or `null` (clear); any other
  value → **422** (the stored value is unchanged). A nonexistent paper → **404** for both endpoints.
- **Read is a timestamp, idempotent-safe.** `{read:true}` stamps `read_at`; `{read:false}` clears it. Marking an
  already-read paper read again is harmless.
- **`read_at`/`priority` are projected, not bibliographic.** They appear on the paper list item + detail, but are
  workflow state on `papers` (like `deleted_at`), never part of the CSL record.

## Steps

1. `GET /papers/{id}` → `read_at` is null, `priority` is null on a fresh paper.
2. `POST /papers/{id}/read {read:true}` → 200; the detail shows a non-null `read_at`. `GET /papers?read_status=read`
   includes it; `?read_status=unread` excludes it. `{read:false}` → `read_at` null again.
3. `POST /papers/{id}/priority {priority:"high"}` → 200, `priority=="high"`. `GET /papers?priority=high` includes it.
   `{priority:"urgent"}` → **422** (stored priority unchanged). `{priority:null}` → clears it.
4. `GET /papers?sort=priority` → high → normal → low → unset (NULL last); an explicit user-chosen order.
5. `POST /papers/999999/read` and `…/priority` → **404**.
6. (UI) On a library card, the read toggle (○ unread / ✓ read) flips on click; the **Priority ▾** badge opens a
   popover (High/Normal/Low/Clear) that sets the level. Clicking the markers never selects/opens the card.
7. (UI, inc 221) The library header has a **Read** filter (all/unread/read) + a **Priority** filter (all/high/
   normal/low) — both user facets (no score), live-library only. Filtering to Unread excludes read papers; to High
   shows only high-priority. These compose with the other filters (the inc-221 useLibrary subsystem).

## Pass criteria

- Both endpoints behave (read set/clear + filters; priority set/clear/filter + 422 off-allowlist + 404; the
  By-priority sort); the card toggle + priority popover work and don't trigger card select/open.
- 0 console/page errors and 0 Gemini/`generativelanguage`/genai-host requests across any opened page (a cdnjs
  React/pdf.js CDN fetch is the app's by-design framework load, not an egress violation).
