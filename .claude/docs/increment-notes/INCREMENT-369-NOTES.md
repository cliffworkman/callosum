# Increment 369 — CSL schema, provenance, update checks, and duplication

## Implemented

- Imported CSL now passes the official CSL 1.0.2 RELAX NG schema and Schematron macro rules locally before the
  existing citeproc execution check. The generated schema assets retain their upstream MIT license.
- A bounded atomic sidecar records local-file, repository, URL, or duplicate provenance plus install/update/check
  timestamps. Catalog detail exposes that provenance and links remote sources; malformed metadata fails soft.
- Remote styles expose an explicit **Check for updates** action. It refreshes installed custom parents as well as
  the selected style, never runs in the background, and installs the exact preflighted chain after confirmation.
- Every selected style exposes **Duplicate**. Bundled, independent, and dependent sources become a new standalone
  personal style with a new canonical identity, preserved source lineage, and no mutation of the original.
- The guarded network fetcher and prepared-token cache were split by concern so application modules retain ample
  room under the 600-line cap.

## Key technical detail

A dependent copy cannot merely copy its small alias XML: that would still rely on its parent. Duplication instead
uses the resolved parent's complete formatting tree, replaces its `<info>` with the selected style's descriptive
metadata, removes `independent-parent`, creates new self/template lineage links and a UUID canonical id, then runs
the same full schema and citeproc validators as an imported file.

## Boundaries

Update status is a timestamped source check, not a certificate. There is no background egress, automatic update,
general URL proxy, source-file path retention, library-text flow, database migration, or style editor in this
increment. Visual/source editing remains the final open P1 item #9 slice.

## Gates

- **Principles:** principles 8 and 10 apply: origin and check time stay inspectable, while remote work is explicit
  and bounded. The closest worked contrast is Example 2's reviewable deterministic signal. The misaligned shortcut
  would silently refresh styles and present “current” without naming source/time; this implementation declines it.
- **Design:** reuses the existing detail metadata, secondary buttons, link, and wrapping action-row recipes.
- **Security:** `2026-07-24_csl-schema-provenance-lifecycle.md` — **PASS**.
- **QA/experience:** route 35 covers source/check/copy states and route 34 covers independent rendering. The
  deadline citer's next step is visible after install without turning a format check into background activity.

## Verification

- Changed-surface citation, repository, frontend-assembly, and help tests: **129 passed**.
- Frontend build, Ruff format/check, line budget, `git diff --check`, and offline lock verification: clean.
- QA surface map: **306/306 API**; the 21 frontend gaps are the same pre-existing tag/My Publications entries.
- Playwright: desktop and 375px mobile duplication; independent copy provenance/actions/preview; live guarded URL
  import and explicit current-source check; no horizontal overflow, console errors, or warnings.
- Real LibreOffice Writer passed the shared searchable-catalog/install/default/preview contract after its fixture
  was brought onto the official schema and made repeatable. The full extended adapter harness continued through
  phase 6 before hitting its existing eight-minute ceiling.
- Full project suite: **1548 passed, 1 skipped**.
- `pip-audit -r requirements.txt` was attempted but did not return within two minutes in the current package-host
  network environment. The generated lock remains SHA256-pinned and `uv lock --check --offline` passed.

## Next

Finish P1 item #9 with the visual/source CSL editor built on the independent-copy and schema-validation boundary.
