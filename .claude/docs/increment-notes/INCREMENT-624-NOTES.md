# Increment 624: website coverage, claims and screenshot review

Self-review by the implementing session. No app, model, Help or demo-source file changed. Full matrices:
`.claude/docs/research/2026-10-31_release-060-audit/WEBSITE_REVIEW_INC624.md`.

## Implemented
- **Claims corrected** in `www/index.html`, `www/showcase.html`, `www/how-it-works.html`: test count, signing and notarization, missing
  Intel Mac download, search sources, "every network action", download disclosures, MCP write tools, overclaims about what the
  verification layer decides, a stale `bge-base` claim, "model versions" for 0.5.16, three caption claims.
- **0.6.0 kept separate.** One note on How It Works, labelled "Planned for 0.6.0, not yet released", covers Arctic S, MiniLM, DeBERTa, MiniLM2,
  Qwen2.5, modernization and older syntheses. Both model names appear nowhere else on the site, and a test enforces that.
- **Six screenshots recaptured** from real rendered views: `wip_workspace`, `reader`, `feed`, `publishers`, `usage`, `mobile`. Three more
  relabelled: `synthesis`, `status`, `statements`. Twelve retained after inspection.
- **Broken deep links fixed.** Six compact showcase images no longer lazy-load.
- **Demo disclosure on the website:** every page describing the demo now says its results came from an earlier version.
- **Registry:** captured dates and sources for recaptures, truthful `route_97` exclusion, then the review block by the gate's own `--refresh`.

## Key technical detail
- The website gate checks hashes, dimensions and counts. It can pass over a wrong sentence or a stale image: the
  retired-tab screenshots were all marked reviewed at inc 603. A refreshed receipt here means this review happened; it doesn't make the gate smarter.
- `--refresh` keeps `captured_at`, so recaptured figures need their date set by hand first. It stamps every figure reviewed, which is true here
  because all 21 were opened.
- Recaptures use the demo's snapshot data rendered by the current frontend. Between v0.5.16 and this head those views have no material
  difference, so they stand truthfully for 0.5.16. Captions name the saved demo.
- `synthesis_current.png` is honest as a 0.5.x image, and no real 0.6.0 image can be made here: the demo has `model_provenance: null`, and a real run needs
  separately authorized inference.

## Manual verification script
1. `python tools/demo/build_demo.py` from PowerShell, then `python .local\validation-624\site_acceptance.py check`.
2. Or by hand: serve a copy of `www/` at `/callosum/` with a demo built for `/callosum/demo/`, open `showcase.html#fig-wip` in a new tab, and confirm it
   lands on the figure and shows two synthetic drafts.
3. On the home page, confirm four download buttons and that the Technical details on How It Works show the unreleased note.

## Findings not fixed
- **Find covers the text it found** in the reader (shared frontend, also in 0.5.16). Stacking context from `.pdf-find-layer` isolates the blend. Measured
  and confirmed, see the review. Needs one CSS line in a stabilization increment, and it stales both gates.
- Find has no Help entry. Low. Same reason.
- `synthesis_current.png` has no 0.6.0 equivalent yet.
- `my_publications_current.png` identifies the maintainer through public records. Retained, flagged.

## Pytest and checks
All on the corrections, with `CALLOSUM_DB_URL` overridden to a new disposable file under `.local\validation-624\`, checked by `preflight_db.py`.

| Check | Result |
|---|---|
| `test_website_how_it_works`, `test_check_website_coverage`, `test_help`, `test_demo_experience_coverage`, `test_demo_snapshot`, `test_frontend_assembly` | 145 passed, 1 skipped (curated source DB absent), before the mobile recapture; re-run in the receipt commit below |
| `CALLOSUM_RUN_E2E=1 tests/e2e/test_demo_static.py` | 2 passed |
| Three inc-623 historical tests | Included above, passed |
| Demo gate | Pass, unchanged at 120 capabilities. Receipt not touched |
| QA surface map, tach, line budget, what's-new, scoped ruff | Pass |
| Rendered acceptance, `site_acceptance.py final` | **147 passed, 0 failed**, 0 console errors, 0 page errors, 0 blocked requests. 1440x900 and 375x812 |
| External links, shell only | All reachable (see review). Not visited by the browser test |

Coverage of the rendered run: all pages and direct reload, primary navigation, tabs, unreleased note, capability search, 53 hotspots, 12 fresh direct
links, homepage deep link, download labels, website-to-demo and back, demo reload, demo base path, internal link crawl, anchors, image load and size, captions, overflow.

**Final-code full suite: not run, still owed.** Plain terminal or CI, per the instruction. No targeted result here implies it.

## Not run
Real static hosting, other browsers, a real phone, packaged-app behaviour, the macOS and Linux install path. Screenshots were not pixel-diffed.

## Security
No endpoint, fetch, ingestion path, auth or dependency changed, so the audit gate does not trigger. The website text now discloses more network activity,
not less. Independent security review of incs 616-623 is still owed; this increment does not discharge it.

## Protected state
See the final report. No access to the research master or desktop database other than file-size and timestamp stats. JUNO and deployed sites untouched.
