# Increment 368 — CSL repository search/install and guarded URL import

## Context

The shared style manager could search bundled/personal styles and manage the full local lifecycle, but reaching
the CSL project's public catalog still required leaving Callosum. P1 item #9 also called for import by URL. Both
are network operations, unlike the preceding local slices, and therefore needed explicit action boundaries,
bounded fetching, dependency resolution, and a separate security audit.

## Implemented

- Settings adds a **Repository** view. Search runs only on submit, fetches the fixed public Zotero/CSL index, and
  locally matches title/journal, acronym, citation format, and discipline. The bounded index is cached in memory
  for six hours; query text is never sent to the repository.
- Repository rows expose install state and one **Install** action. The server accepts only a constrained style id
  and constructs the Zotero URL itself rather than trusting a client/catalog URL.
- The install bar now pairs local **Install .csl** with **Import URL**. URL import is an explicit HTTPS-only,
  port-443 fetch with URL/DNS/connected-peer/redirect/stream-size guards.
- Dependent styles recursively fetch their canonical parent up to a bounded depth. Every candidate in the chain
  passes existing structural and real citeproc validation before any write; parents install before the requested
  style. Official dependent styles may correctly omit `class`, as CSL 1.0.2 permits.
- Remote preflight retains the exact validated chain briefly behind a bounded opaque token; the confirmed install
  consumes those bytes without refetching, eliminating both expected browser-console errors and a content race.
- Remote imports reuse exact duplicate detection, immutable bundled styles, deterministic personal ids, update
  conflict/confirmation, catalog refresh, preview, preferences, export/removal, and all adapter rendering paths.
- The UI attributes repository styles to the Citation Style Language project and remains responsive on mobile.

## Boundaries

No repository background refresh, search-as-you-type request, library/manuscript/PDF payload, credential, or AI
toggle is involved. This slice does not yet add full upstream-schema/update provenance, style duplication, or a
visual/source editor; those remain the open P1 item #9 work.

## Gates

- **Principles/governance:** non-triggering. Public formatting configuration creates no literature claim,
  evidence, score, or decision. The only egress is the exact explicit public-catalog/style action.
- **Design:** extends the existing manager list, segmented view, inputs, buttons, and mobile breakpoints without
  nested cards or new visual tokens.
- **Security:** `2026-07-24_csl-repository-url-import.md` is **PASS**.
- **QA:** route 35 covers fixed-host/local-query repository behavior, URL SSRF/redirect/size bounds, dependency
  preflight, duplicate/update semantics, browser errors, and responsive layout.

## Verification

- Repository/URL unit and API coverage: **15 passed**; citation/frontend/help synchronization suite:
  **78 passed**.
- A live isolated catalog search returned the expected discipline-tagged Journal of Experimental Psychology
  styles. A live repository install resolved the selected dependent style through bundled APA; browser repository
  and URL installs both reached the same Personal-style preview/detail lifecycle.
- Playwright at `1440x900` and `375x812` covered repository search/install, URL install, private/local URL
  refusal, fixed-height import controls, responsive search/tabs/list/detail, and zero console/page errors.
- `python adapters/libreoffice/run_roundtrip.py`: installed 0.16.0 OXT completed the shared personal-style path and
  full native Writer fixture with **SELFTEST OK**.
- QA surface map: **304/304 API covered, 0 uncovered**. Ruff check/format, generated-frontend synchronization,
  diff checks, and the 600-line source budget pass.
- Full project suite: **1543 passed, 1 skipped**.

## Experience pass

The deadline citer can now name a journal rather than find and download XML manually. Repository installation and
URL import converge immediately on the familiar personal-style detail/preview/default workflow; duplicate and
update language remains identical across all three import sources. No persona subagent was used because the
active collaboration instruction prohibits delegation unless the user explicitly requests it.

## Next

Finish P1 item #9 with full upstream-schema/update provenance and safe style duplication before beginning the
visual/source editor.
