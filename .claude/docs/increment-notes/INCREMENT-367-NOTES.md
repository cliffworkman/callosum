# Increment 367 — Personal CSL export, portability, and guarded removal

## Context

Increment 366 installed personal and dependent CSL styles, but users had no in-app backup/removal lifecycle and
an existing unsuffixed local id could not be reconstructed reliably on another device. Existing word-processor
documents refer to that local style id, so portability is an identity problem, not merely a file download.

## Implemented

- A selected **Personal style** now exposes **Download .csl** and **Remove** in Settings.
- Export returns valid CSL XML with a constrained prolog marker containing the exact Callosum `custom-*` id.
  Re-import strips the marker before validation/storage and uses the id only when it is valid and free.
- New unmarked imports derive an install-order-independent canonical URL slug plus SHA-256 prefix. Existing
  pre-increment unsuffixed ids remain valid and become portable through the export marker.
- Exported-marker content is normalized before exact-duplicate/update comparison, so downloading and immediately
  re-importing reports `already_installed`, not a false update.
- Removal refuses bundled styles, the application default, unknown ids, and parents of installed dependent
  styles. A successful removal deletes the exact local file and cleans Favorites/Recent preferences.
- The UI disables removal for the application default and explains the required next step. Its confirmation warns
  that existing documents will not render until the same style is reinstalled, recommends exporting first, and
  states that removal cannot be undone.

## Boundaries

This slice does not enumerate or mutate external word-processor documents and cannot prove whether one uses a
style. It preserves their recovery path instead: export first, reinstall the same marked CSL later, recover the
same id. Repository search/install, explicit URL import, full upstream-schema/update provenance, duplication, and
visual/source editing remain later P1 item #9 slices.

## Verification

- Focused changed-surface citation/frontend tests: **55 passed**; frontend/help synchronization suite:
  **63 passed**.
- Playwright covered marked download, default-removal guard, warning cancel/confirm, removal feedback/fallback
  selection, marked-file re-import, hidden native input, and mobile `375x812` layout with zero horizontal
  overflow and zero console/page errors.
- `python adapters/libreoffice/run_roundtrip.py`: installed 0.16.0 OXT completed the shared personal-style
  install/search/preview/default path and the full Writer fixture with **SELFTEST OK**.
- QA surface map: **299/299 API covered, 0 uncovered**.
- Ruff format/check and the 600-line source budget pass.
- Full project suite: **1528 passed, 1 skipped**.

## Gates

- **Principles/governance:** non-triggering. This manages deterministic local formatting configuration and creates
  no literature claim, signal, ranking, judgment, or egress.
- **Design:** existing `.btn`, `.btn-ghost danger`, Settings spacing, and token recipes only.
- **Security:** `2026-07-24_custom-csl-portability-removal.md` is **PASS**.
- **QA:** routes 34 and 35 cover portability, default/dependency guards, destructive warning/cancel/confirm,
  preference cleanup, adversarial markers, no egress, and mobile layout.

## Experience pass

Locally walked the **deadline citer** through backing up a journal style before moving machines and through
cleaning up an obsolete style without breaking a manuscript silently. Download is visible only where relevant;
removal is adjacent, reversible only by the clearly recommended backup, and blocked with an actionable default
instruction. No cheap follow-up remained. A persona subagent was not used because the active collaboration
instruction prohibits delegation unless the user explicitly requests it.

## Next

Add CSL repository search/install and explicit URL import as a separately audited, explicitly initiated egress
slice.
