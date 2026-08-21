# Increment 486 — EndNote through generic citation import, partial (backlog #57 Phase 2)

## Implemented

- Primary-source research confirms the supported low-effort route is **EndNote → File/Export → RefMan (RIS)
  Export → Callosum + Add/Import file**. EndNote's manual lists both RIS and BibTeX transfer styles and recommends
  RefMan RIS when the destination is uncertain; the export is text-only. EndNote Online may produce RIS with a
  `.txt` extension, which Callosum already accepts and auto-detects.
- `app/backend/metadata/citation_import.py` — fills a narrow gap against Clarivate's current RIS acceptance
  vocabulary: `CPAPER` maps to `paper-conference`; `A4` is accepted as an author; `BT/CT/T3/TT/ST`, `J1`, and
  `Y2` join the already-supported title/journal/year aliases. Resource caps, local-only parsing, record isolation,
  dedup, and source provenance are unchanged.
- `tests/test_citation_import.py` — adds a synthetic Clarivate-contract fixture covering those aliases. Its source
  comment and test name intentionally do not call it an EndNote export sample.
- Served Help gives the exact desktop path, says `.txt` needs no rename, and repeats the honest metadata-only/no-
  PDF boundary. Route 27 now exercises actual citation files rather than incorrectly calling `/library/import` a
  PDF importer, and names the real-file verification gap.
- `.claude/docs/research/2026-08-21_endnote_generic_import.md` records sources, parser comparison, and the decision
  not to add parenthesis-delimited BibTeX support without current primary-source evidence that EndNote emits it.

## Key technical detail

**The format recommendation is part of compatibility.** EndNote output styles are customizable, so “accept every
file EndNote can be configured to emit” is not a bounded contract. Its own current manual names RefMan (RIS)
Export as the general transfer choice, and Clarivate publishes the aliases it accepts in that RIS family. Callosum
therefore hardens the standard, documented route and tells the user exactly which style to choose; it does not
reverse-engineer proprietary `.enl/.enlx` stores, promise attachments from a text export, or broaden a hand-rolled
BibTeX parser around an unverified rumor.

## Experience pass

**EndNote migrator, code/help-grounded walkthrough:** I select All References in EndNote, export once with the
named RefMan (RIS) style, then choose that file under Callosum's existing + Add → Import file action. If EndNote
named it `.txt`, the picker accepts it without a rename. The completion receipt tells me imported/duplicate/
failed/skipped counts and the Help text makes clear that this moved metadata, not PDFs, so I am not surprised by
missing attachments. The remaining trust gap is unavoidable in this repository: nobody has run the path with an
actual EndNote-created file. That is called out at the backlog and handoff level rather than hidden behind the
synthetic contract test.

## Manual verification script

1. In current EndNote Desktop, select a small representative set (journal article, conference paper, book,
   non-ASCII author/title), then **File → Export**, plain text, **RefMan (RIS) Export**.
2. Preserve the original file unchanged as a non-secret test fixture after checking it contains no private notes
   or identifiers. Record the EndNote version/platform and export-style name/date.
3. In Callosum, choose **+ Add → Import file…**, select the `.ris`/`.txt`, and confirm the job receipt plus title,
   creators, year, type, venue, DOI, and Unicode values against EndNote.
4. Re-import the same file and confirm every record reports duplicate rather than creating copies.
5. Add the redacted genuine fixture and assertions to `tests/test_citation_import.py`; only then mark Phase 2
   shipped in the backlog.

## Verification

- `pytest tests/test_citation_import.py -q` → **13 passed**.
- Final whole-branch suite: `pytest -n auto -q` → **2338 passed, 3 skipped in 1315.42s (0:21:55)**.
- Final gates: `ruff format --check .` → **784 files already formatted**; `ruff check .` → **All checks
  passed**; `python -m tach check` → **All modules validated**. Line budget, QA surface map, reviewed website
  coverage, and demo-experience coverage all pass.

## Honest completion boundary

**Phase 2 is partial, not done.** No genuine EndNote-created export exists in the repository or was available in
this session. The synthetic test proves the documented Clarivate RIS alias contract, not EndNote's actual current
file output. The backlog's explicit real-sample criterion remains open.
