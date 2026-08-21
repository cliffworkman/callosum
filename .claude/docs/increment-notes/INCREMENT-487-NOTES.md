# Increment 487 — Mendeley-via-Zotero bridge confirmed (backlog #57 Phase 3)

## Implemented

- `.claude/docs/research/2026-08-21_mendeley_via_zotero_bridge.md` verifies the current first-party path:
  Zotero Desktop's **File → Import → Mendeley Reference Manager (online import)**, followed by Callosum's shipped
  **Read Zotero library…** action. Zotero performs Mendeley auth/network work and materializes the ordinary local
  Zotero library; Callosum receives neither credentials nor a Mendeley API integration.
- `app/frontend/js/04e_onboarding.jsx` names the bridge at the migration decision point rather than assuming a
  Mendeley user will interpret a Zotero-labeled button. Inc 489's combined experience pass promotes that identity
  into both visible action labels—**Read Zotero / migrated Mendeley library…** in onboarding and **Read Zotero
  library… (Mendeley bridge)** in + Add—while `27b_zotero_import.jsx` states the exact upstream action/online/auth
  boundary next to the Zotero directory field.
- Served Help provides the three-step handoff and keeps upstream limitations attached: personal-library only
  unless group items are copied first, Mendeley data/files must be online, Mendeley Cite document fields are not
  converted, and Callosum does not read/decrypt the protected local store.
- `integrations/mendeley/README.md` moves from speculative “planned” language to the supported bridge plus generic
  metadata-only alternative, with a primary source and explicit declined path. Route 93 and assembled-frontend
  coverage travel with the copy change; `callosum-app.html` was rebuilt.

## Key technical detail

**No second importer is the design.** Zotero's bridge owns the unstable Mendeley API/login contract and writes
into the same open local model Callosum already understands. Adding a Callosum Mendeley endpoint would duplicate
that work, create a new secret/egress surface, and depend directly on Elsevier while still not solving Mendeley's
encrypted/no-real-local-database boundary. The composed flow has one extra application hop but a much smaller
trust surface: Mendeley → user-authorized Zotero import → local Zotero database → Callosum copy-then-read.

## Experience pass

**Mendeley migrator, code/help-grounded walkthrough:** at onboarding I no longer have to guess whether a Zotero
action is irrelevant to me—the button itself names a migrated Mendeley library, and the copy names the online-
import bridge. The established-library + Add menu keeps the bridge visible without a hover. The modal repeats the
exact Zotero menu command, prerequisite, and credential boundary at the
moment I need them. After the external Zotero import completes, Callosum's existing single directory field and
job receipt take over. The unavoidable friction is installing/running Zotero and syncing Mendeley online; the
product cannot safely remove that hop, so it explains it rather than dead-ending or offering a fake direct path.

## Manual verification script

1. With a throwaway personal Mendeley library whose data/files are fully synced, run current Zotero Desktop's
   **File → Import → Mendeley Reference Manager (online import)** and authenticate in Zotero.
2. Confirm the Zotero result contains representative metadata, folder hierarchy, and locally available PDFs.
   Record any normalization to Extra; test group-library items only after copying them to a personal collection.
3. In Callosum onboarding, confirm the bridge is discoverable before choosing **Read Zotero / migrated Mendeley
   library…**; in an established library, confirm the visible + Add label and Zotero modal convey the same path.
4. Point Callosum at the resulting Zotero data directory. Confirm metadata, collections, tags/notes, PDFs, and
   honest attachment errors against what Zotero actually materialized—do not compare against an unsupported
   promise of every original Mendeley field/annotation.
5. Confirm no Mendeley credential or API request reaches Callosum and that Help discloses the group-library and
   Mendeley Cite document boundaries.

## Verification

- `pytest tests/test_frontend_assembly.py -q` → **68 passed**.
- `pytest tests/test_help.py -q` → **14 passed**.
- `ruff format --check .` → **784 files already formatted**; `ruff check .` → **All checks passed**.
- `python -m tach check` → **All modules validated**; line-budget, QA surface map, and reviewed website coverage
  checks pass (553 source files within cap; 428/428 API + 1767/1767 frontend surfaces; 70 public routes mapped).
- Final whole-branch suite: `pytest -n auto -q` → **2338 passed, 3 skipped in 1315.42s (0:21:55)**.

## Primary source

- <https://www.zotero.org/support/kb/mendeley_import> (last updated 2025-08-25; reviewed 2026-08-21).
