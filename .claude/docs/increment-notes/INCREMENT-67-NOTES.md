# Increment 67 Notes — Un-dismiss / manage dismissals (duplicate detection)

Completes inc-64's persistent "not a duplicate" dismiss with an **in-app undo**. Before this, a dismiss was
permanent and invisible — no way to see what you'd dismissed or to flag a pair again. Now the Duplicates
modal has a **Previously dismissed** section listing each dismissed pair with an **un-dismiss** control.

## Implemented
- **`persistence/dedup_repo.py`** (new) — `list_dismissed_duplicate_pairs(conn)` (the dismissed pairs joined
  to `papers` twice for each title) + `undismiss_duplicate_pair(conn, low, high)` (delete the canonical pair;
  False if it wasn't dismissed). Also now the home of the inc-64 `get_dismissed_duplicate_pairs` /
  `dismiss_duplicate_pairs` (see module split below).
- **`api/routers/duplicates.py`** — `GET /papers/duplicates/dismissed` (`{pairs: [{low:{id,title},
  high:{id,title}}]}`), registered **before** `GET /papers/duplicates/{job_id}` so the literal "dismissed"
  isn't captured as a job id; `POST /papers/duplicates/undismiss {paper_ids}` (≥2; removes the canonical
  pairs among them; idempotent no-op if not dismissed; non-destructive — drops a preference, not a paper).
- **Frontend** (`19_duplicates.jsx`, `styles.css`) — a collapsible **Previously dismissed (N)** section at
  the bottom of the modal; each row shows the two titles + an **un-dismiss** button. Dismissing a group now
  also refreshes the list so it appears immediately. New `.dup-dismissed*` CSS (token-based, matches the
  `.dup-*` recipe). Rebuilt `callosum-app.html`.

**No migration** (reuses the inc-64 `dismissed_duplicate_pairs` table). **No egress** (entirely local). No new
dependency.

## Module split (rule #1, behavior-preserving)
Adding the two data-access functions pushed `persistence/repository.py` to **604** (>600). The cohesive
dedup-dismiss concern (all four functions operate solely on `dismissed_duplicate_pairs`) was **moved verbatim**
to new **`persistence/dedup_repo.py`** (63), bringing `repository.py` to **555**. The two importers
(`clustering/duplicate_detection.py`, `api/routers/duplicates.py`) were repointed to the new module. No
behavior change (full suite green).

## Verification
- **pytest 235** (+1): `test_dismissed_pair_can_be_listed_and_undismissed` — dismiss → `GET .../dismissed`
  lists the canonical pair with titles → `POST .../undismiss` (any order) → list empty → re-scan re-flags;
  idempotent no-op; <2 ids → 422. Route-surface invariant +2 routes (GET read + POST mutation). Full suite
  green through the module split.
- **Live E2E** (`.local/undismiss_e2e/`): scan flags 1 group → dismiss → "Previously dismissed (1)" → expand
  → un-dismiss → section gone → reopen modal → **flagged again**, 0 console errors; screenshot.
- Audit `.claude/security-audits/2026-06-20_undismiss-duplicates.md` — **PASS**.

## Manual verification script
1. Library with ≥2 papers that scan as a duplicate group. Click **Duplicates** → see the group.
2. Click **dismiss** → the group hides; **Previously dismissed (1)** appears at the bottom. Expand it.
3. Click **un-dismiss** → the row disappears. Close and reopen **Duplicates** → the pair is flagged again.

## Deferred (noted)
- Per-pair vs whole-group is now moot for *un*-dismiss (the list is per pair); dismiss still stores the whole
  group's pairs.
- Library **merge** (the real consolidation) remains the last, destructive dedup increment.
