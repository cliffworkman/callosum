# Ioannidis DOI-review investigation — local proposal

Base: `c7a7c10b16e01e587c5b69e0d3212987bae106ad`.
Local branch: `fix/ioannidis-doi-review`; isolated worktree; no push or deployment.

## Established cause

The exact 255629-byte, six-page acceptance PDF has SHA-256
`ffc1005680cb620eec4c913437dfabbf311b535cfe16cbaeb2faec1f92afc362`.
It was copied read-only from the existing iMac QA fixture, not downloaded again.
The unchanged installed c7a7c10b source and managed Intel runtime (PyMuPDF 1.28.0)
reproduced the failure over SSH with `python -B`. Local PyMuPDF 1.27.2.3 reproduced
the same candidates, title, zero resolution attempts and incorrect explanation.

`get_text("dict", sort=True)` walks PDF blocks, not semantic publication regions.
Page 1 is a three-column layout. The Mac's zero-based sorted block sequence is:

| Block | Text / region | Section after observation |
| --- | --- | --- |
| 0 | Open access, freely available online | none |
| 1 | Essay | none |
| 2 | Why Most Published Research Findings / Are False (25 pt, two lines) | none |
| 3 | John P. A. Ioannidis | none |
| 4 | Middle-column paragraph continuation | none |
| 5 | Summary (11 pt) | abstract |
| 6–13 | Mixed-column text, modeling heading, pull quote and body | abstract |
| 14 | Citation: Ioannidis JPA (2005) ... | abstract |
| 15–20 | Copyright, abbreviation, body, affiliations, competing interests, Essay note | abstract |
| 21 | DOI: 10.1371/journal.pmed.0020124 | abstract |
| 22–24 | Body and publication footers | abstract |

`SectionTracker.observe_block` recognizes Summary as abstract and retains that state
across subsequent blocks/columns/pages. `_extract_candidates` observes the block
**before** calling `_classify_position`. The right-column DOI, bbox approximately
(393.00, 719.26, 499.34, 726.26), is therefore `body`: page <= 2 alone is insufficient;
front matter additionally requires no recognized section. Its publication-information
location is lost by the page-wide section heuristic. Local PyMuPDF partitions two
blocks differently: DOI block 19 locally versus 21 on the Mac; Summary is block 5 in both.
This is not a missing OCR/text/DOI-regex match or a provider outage.

The five original observations were:

| DOI suffix after `10.1371/journal.pmed.0020124` | Page | Mac sorted block | Original class |
| --- | --- | --- | --- |
| (article DOI itself) | 1 | 21 | body |
| .t001 | 2 | 4 | body |
| .t002 | 2 | 21 | body |
| .g001 | 3 | 4 | body |
| .t003 | 3 | 13 | body |

The latter four are table/figure component identifiers, not competing article identities.
`_resolve_and_score` retains all five observations but resolves only front-matter DOIs,
so its resolver was called **zero times** and it returned no automatic candidate.
`best_candidate` considered only strong/insufficient resolved records, yielding None.
`explain_evidence` handled front matter and reference-only observations but had no body
branch, falling through to the false claim that no DOI-shaped text was found.

The internal PDF title is `PLME0208_696-701.indd`. The old extractor accepted any internal
title longer than eight characters, then skipped first-page title extraction entirely.
Even simply removing that metadata would let the old first-line fallback pick the
"Open access, freely available online" banner. The useful evidence is the two-line,
25-point article title at bbox (45.00, 66.70, 482.81, 121.70). Title corroboration was a
second defect, not the reason the resolver was skipped in this acceptance.

## Proposed local behavior

- Any recorded DOI observation (including body, reference, figure/table, unknown position
  or resolution-only historical evidence) prevents a "No DOI-shaped text" explanation.
- Keep the article DOI's body classification and the front-matter automatic-resolution
  gate. Do not globally reset SectionTracker or declare publication footers canonical.
- Offer a unique non-reference, non-component observed DOI as `observed_unverified`,
  with page and position, no asserted resolved title. Opening the queue does not resolve it.
  This read-time fallback also handles the unchanged original schema-1 evidence.
- Exclude explicitly captioned figure/table blocks and the narrowly recognized PLOS
  `.tNNN`/`.gNNN` component DOI form from article selection. Never derive a parent DOI
  by stripping a suffix; the article DOI itself must have been observed.
- Multiple equally eligible candidates stay unselected. Existing resolved candidates
  retain their precedence; ambiguity is not resolved by picking the first record.
- **Review DOI** prefills the observed value. **Look up** uses the existing read-only
  preview endpoint. Unresolved lookup offers no confirmation; resolved preview shows
  metadata for inspection, then explicit confirmation uses existing canonical admission.
  Unedited suggestions record `user_confirmed_candidate`; edited values record
  `user_entered_doi`. Original candidates/resolutions remain alongside these actions.
- Prefer an unambiguous prominent first-page heading (top 35%, all spans >=14 pt,
  4+ words, 21–300 characters), joining wrapped lines. Conflicting internal metadata
  cannot corroborate another work when that heading is available. Reject common internal
  filename titles. This bounded heuristic is not a general PDF title/reading-order solver.

No database migration, new provider, endpoint, dependency, browser-capture notification
change, runtime change or automatic body/reference promotion is introduced.

## Evidence and provenance

Original acceptance artifact: `385d21d3095f46c4a126cf973216ee34`.
Original evidence: five body observations, title `PLME0208_696-701.indd`, no resolutions.
Cliff subsequently entered the DOI manually; the recorded action is `user_entered_doi`,
`pending_admission`, at `2026-09-24T22:54:36.707717+00:00`. The artifact was promoted
by that user-confirmation path, not by automatic discovery. The original evidence and
that action are preserved verbatim as data in `tests/fixtures/capture/ioannidis-acceptance.json`.
The original acceptance outputs, movie, parked user data, installed app/runtime and
active QA session are not rewritten. The new tests mutate only throwaway local databases.
The browser-capture no-refresh acceptance remains Cliff's independently reported success;
this investigation does not reclassify it as a capture failure.

## Regression and experience review

Tests cover the exact original PDF, schema-1 historical evidence, reference-only,
figure/table-only (including non-PLOS caption DOIs), body-only, ambiguous, unresolved,
misleading internal metadata, and a legitimate front-matter/title match. Endpoint tests
exercise preview without mutation, unresolved confirmation rejection, explicit admission
and append-only user actions. Assembled Chromium tests exercise the visible review flow,
no confirmation before successful lookup, and candidate/manual provenance after editing.

Experience review is grounded in Cliff's actual task: recovering the DOI should not
require typing one already found in the PDF. The candidate now supplies that value and
its location, with an explicit verification step. The PDF thumbnail and resolved preview
support inspection. Remaining limitation: complex title layouts and arbitrary publisher
component identifiers are not universally recognized; ambiguous captures still require
manual selection. This is a primary-agent walkthrough plus browser tests, not an
independent persona-agent review or renewed real-Mac acceptance.

## Validation receipt and exact local changes

- Focused backend suite: **146 passed, 2 skipped** (Windows skips for POSIX permission bits).
  `tests/test_provisional_doi_review.py`, `tests/test_import_queue.py`, `tests/test_capture.py`,
  `tests/test_provisional_module_seams.py`, `tests/test_capture_trust_boundaries.py`,
  `tests/test_section_scope.py`. The 19 new real/synthetic/provenance tests are included.
- Assembled frontend and genuine local Chromium review flow: **90 passed** (88 assembly
  tests and 2 browser scenarios: unchanged suggested DOI / edited DOI). Three dependency
  warnings; no page errors in either browser scenario. Injected resolver, disposable DBs.
- Existing Import Queue Node tests: **20 passed**.
- Frontend build, Ruff lint/format, Tach module boundaries, Bandit baseline security gate,
  600-line budget, QA surface coverage, website review receipt and staged whitespace check pass.
- Development checks caught a Windows text-encoding edit and a missing parent directory
  for the test scratch path; both corrected before the passing build/browser receipt.
  No product workaround or additional dependency was needed.
- Preservation check: all **53 original acceptance output files** and **95 original untracked
  files** retain their hashes. Original browser-capture worktree tracked status is clean and
  its HEAD remains c7a7c10b. All Mac operations in this investigation were read-only SSH.

Exact changes on the local `fix/ioannidis-doi-review` branch, based on c7a7c10b:

| File | Change |
| --- | --- |
| `app/backend/capture/provisional_evidence.py` | Visible title selection, filename rejection and bounded figure/table exclusion; automatic body/reference gate retained. |
| `app/backend/capture/provisional_review.py` | Truthful observed-DOI explanation; unique unverified candidate fallback; no arbitrary ambiguity winner. |
| `app/backend/api/routers/import_queue.py` | Optional candidate page and position fields. |
| `app/frontend/js/10l_import_queue.jsx` | Unverified label/location, prefilled Review DOI flow, lookup-before-confirmation and candidate/manual provenance. |
| `callosum-app.html` | Regenerated from frontend source. |
| `tests/test_provisional_doi_review.py` | 19 real-PDF, adversarial and provenance regressions. |
| `tests/e2e/test_doi_review.py` | 2 assembled Chromium review/provenance scenarios. |
| `tests/test_import_queue.py` | Updated ambiguity expectations and unresolved-explanation fixture. |
| `tests/fixtures/capture/ioannidis-pmed.0020124.pdf` | Exact unchanged, credited CC-BY publisher fixture. |
| `tests/fixtures/capture/ioannidis-acceptance.json` | Original evidence and manual user-confirmation provenance. |
| `tests/fixtures/capture/README.md` | Source, credit, hash and provenance. |
| `.gitignore` | Exception for this exact regression PDF. |
| `.claude/CLAUDE.md` | Review/canonical identity invariant briefing. |
| `.claude/changes.md` | Local change record. |
| `.claude/qa-routes/route_27_scan_import.md` | DOI review and adversarial acceptance steps. |
| `.claude/docs/research/2026-09-24_ioannidis-doi-review.md` | This investigation. |
| `.claude/security-audits/2026-09-24_doi-review.md` | Ingestion/review boundary audit. |
| `www/showcase-coverage.json` | Local review fingerprint; no website publication. |

Principles gate: evidence-carried claims (1), reviewable signals (2), candidate/fact
separation (3), and human judgment (5). The existing worked pattern is a detected
identifier offered for review rather than silently made canonical; automatically
promoting every observed DOI would violate that boundary. The correction makes the
actual observation inspectable while preserving shared canonical admission.

Status: **prepared and staged locally, uncommitted**. No push, merge, PR-ready change,
release, runtime publication, browser-store submission or Mac installation. This is
not a new Intel-Mac acceptance run. Stop here for review of the local proposal.


## Finalization addendum — Lucien's review

The proposal and prior receipts above describe the original staged investigation and
remain historical. Finalization adds only the extraction/lookup-failure explanation and
four focused regressions; no new evidence field, schema change, automatic-promotion rule,
or runtime change is needed. The fixed `decision_reason` dispositions already emitted by
`_run_identity_pipeline` distinguish an extraction exception from a completed scan with
no DOI and from a metadata lookup exception. UI copy is a fixed safe message, never raw
exception text. Generic empty schema-1 evidence does not imply extraction failure.

The endpoint regressions inject extraction and resolver exceptions containing a private
path/token sentinel: it never appears in review output, saved bytes remain intact, and no
canonical paper is created. A genuinely inspected DOI-free PDF retains its distinct
no-DOI explanation. Existing schema-1 failure evidence is understood without migration.

Contribution lineage (chronological):
- Cliff Workman — empirical evidence and product direction: real Intel-Mac capture,
  manual DOI-entry friction, and the requirement that observed evidence remain reviewable.
- Codex (Cody) — investigation and implementation: exact-PDF/runtime reproduction,
  block-order and title trace, bounded review proposal and regression fixtures.
- Lucien — critique: preserve the review/canonical boundary and distinguish inability
  to inspect a PDF from a successful scan with no DOI; supplied the safe wording.
- Codex (Cody) — finalization: applied that critique using existing dispositions,
  reviewed source/evidence/fixture provenance, and ran the final validation before local commit.

Fixture audit: the PDF's page-1 notice permits reuse under Creative Commons Attribution;
README credits Ioannidis and the original article. The unchanged 255629-byte PDF retains
its recorded SHA-256. The small acceptance JSON contains only source/artifact hashes and
IDs, public DOI observations, the original internal title, dispositions and the necessary
user-action timestamp. It contains no credentials, tokens, local paths, settings or unrelated
personal data, and its evidence exactly matches the original saved acceptance record.

The local commit and QA-preparation receipts are separate from the previous proposal's
receipts. Nothing here authorizes a push, publication, normal-app replacement or unattended
human confirmation. A future Intel test must use a fresh disposable Library and record the
provisional state before Cliff confirms. The existing repaired runtime is not pristine-runtime
acceptance; runtime publication and support-floor decisions remain separate.
