# Increment 366 — Local custom CSL installation

## Context

Increment 365 made the seven bundled CSL styles searchable and shared the catalog/default/preview model with
Writer. P1 item #9 still required users to bring their own CSL styles without editing the source tree or trusting
unvalidated XML.

## Implemented

- **Settings → Citation styles → Install .csl** reads one local file in the browser and sends its text to the
  loopback API. Valid styles appear immediately as **Personal style** rows in Installed/search/detail/preview.
- The browser uses a non-mutating validation preflight before the install call. Expected validation failures and
  update detection therefore remain normal UI states with no failed network request or console error.
- Validation is layered: request/file/XML complexity bounds, DTD/entity rejection, CSL namespace/version/class,
  required canonical id/title, installed-parent enforcement for dependent styles, required citation layout for
  independent styles, then real citeproc instantiation/rendering before persistence.
- Personal styles live in `citation-styles/` beside the overridable `app-settings.json`, outside the repository.
  Their runtime ids are server-generated `custom-*` slugs; upload names and canonical URLs never become paths.
- Exact re-imports report `already_installed` without rewriting. Changed content with the same canonical CSL id
  returns `update_available` from a non-mutating validation preflight; the UI asks before an atomic in-place update.
  Expected validation failures also use the successful preflight response, so normal user correction creates no
  browser-console error; direct invalid install calls remain strict 422/409. Bundled canonical ids are immutable.
- The Python renderer resolves bundled/personal ids and supplies XML directly to the fixed Node sidecar. Both
  single-paper and ordered-document rendering therefore support personal styles without expanding the sidecar's
  filesystem authority.
- Dependent personal styles resolve their exact canonical parent from the installed catalog, inherit its
  note/in-text family and citation format, and fail clearly if the parent is absent or the chain is circular/deep.
- Favorites, Recent, locale, and application-default preferences accept installed personal style ids. Settings,
  the Cite pane, and LibreOffice consume the same dynamic catalog without adapter-specific changes.
- LibreOffice's native fixture installs, searches, previews, inherits, embeds, and applies a personal style.
- Extension version bumped 0.15.0 → 0.16.0.

## Boundaries

This increment installs or explicitly updates a local `.csl` file. CSL repository search/install, URL import,
personal-style removal/export, validation against the full upstream CSL schema, and visual/source editing remain
later P1 #9 slices. Existing Writer documents still depend on the installed style id; style embedding/portability
is separate roadmap work.

## Verification

- Focused API/frontend/LibreOffice suite: **209 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** against the installed 0.16.0 OXT, including
  personal-style install/search/preview, application-default inheritance without premature embedding, and
  document application, plus the complete legacy Writer fixture.
- Playwright at desktop and `375x812`: valid install, search/detail/preview, exact duplicate, explicit update,
  actionable invalid-file preflight, hidden native file input, zero horizontal overflow, and zero console/page
  errors.
- Full project suite: **1524 passed, 1 skipped**.

## Gates

- **Principles / governance:** non-triggering. This is deterministic local formatting/tool configuration; it
  creates no claim, signal, ranking, recommendation, judgment, or egress.
- **Security:** `2026-07-24_custom-csl-install.md` is **PASS**.
- **QA:** routes 34 and 35 cover install/render persistence, exact duplicate/update behavior, dependent parents,
  bundled immutability, adversarial XML, no egress, and mobile layout.

## Experience pass

A deadline writer can download a journal's `.csl`, install it from Settings, inspect a real preview, and select it
in Writer without learning a CSL id or restarting either app. A malformed file names the failed requirement; a
changed re-import asks before replacing working formatting. The project no-delegation instruction prevented a
persona subagent, so this walkthrough was performed locally against the deadline-citer workflow.

## Manual verification debt

Install 0.16.0 and run **Callosum → Citation style…** in Writer after installing a personal `.csl` in Settings.
Confirm the native dialog labels it descriptively, previews it, applies it, and lists it in Recent. The modal
`dialog.execute()` path cannot be clicked by the headless UNO fixture.

## Next

Add removal/export with document-safety warnings and a portable provenance record, then CSL repository search and
URL import behind an explicit egress action.
