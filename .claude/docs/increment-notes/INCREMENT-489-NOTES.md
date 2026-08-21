# Increment 489 — backlog #57 hardening + cross-phase coherence pass

## Implemented

- **One combined migration surface:** reread `EXPERIENCE-PASS.md` and `DESIGN.md`, then inspected onboarding,
  + Add, both receiving modals, Help, and the PDF viewer as one flow. Existing component recipes and hierarchy
  remain: the fullest-fidelity Zotero/composed-Mendeley route is the sole primary onboarding action; metadata-
  only citation import and Callosum bundle restore remain ghost actions; + Add remains a uniform menu. No CSS,
  token, spacing, radius, or component pattern changed.
- **Manager-visible choices:** onboarding now says **Read Zotero / migrated Mendeley library…** and **Import
  EndNote RIS / citations file…**; + Add says **Read Zotero library… (Mendeley bridge)** and **Import citations
  file… (EndNote RIS)**. Help and QA use the same names. This fixes discoverability without pretending Callosum
  directly reads Mendeley or EndNote databases.
- **Exact annotation identity:** an already-exact Zotero row is immutable to later attachment relinks. Before this
  fix, re-import could move it to a replacement PDF when the old rectangle happened to remain page-valid. Raw-
  only rows still retain the intended one-way upgrade when their first provable PDF appears.
- **Native “highlight + note” identity:** the viewer's second creation path now sends the active attachment id,
  matching ordinary highlight creation. Previously those marks became legacy-unscoped despite being created
  after attachment scoping shipped.
- **Phase 4 coverage:** adds two annotated sibling PDFs on one paper, an importer-level rotated-page/raw-only
  case, a bounds-valid but semantically different replacement-PDF relink, and a structural assertion for the
  note-create payload.
- **CI repair:** inspected [GitHub Actions run 32488894048](https://github.com/cliffworkman/callosum/actions/runs/32488894048).
  `main` was failing before this branch at Bandit's B405/B314 findings in the GROBID TEI parser. That parser
  already strictly decodes UTF-8 and rejects NUL/DOCTYPE before stdlib parsing, with adversarial regression tests;
  narrow, rule-specific `nosec` annotations now record that reviewed guard so the ratcheted Bandit step can pass.
  No parser behavior or dependency changed.

## Key technical detail

**Page validity is not document identity.** A rectangle that fits PDF B says nothing about whether a mark proven
against PDF A belongs there. The Zotero annotation key is stable across a relink, so treating every re-import as
permission to overwrite `attachment_id` silently converted a valid rectangle into a false exact claim. Existing
exact `{attachment_id, page, bboxes, coordinate_system}` now stays as one proven unit; only a row without exact
geometry accepts location backfill. This follows inc 485's own principle that attachment identity is part of
coordinate truth.

## Experience pass

**Established EndNote migrator:** I open + Add with a RefMan RIS export ready. Previously the only candidate was
“Import file…”, alongside watched folders, Zotero, bundles, sharing, and export; without hovering or already
knowing that RIS was supported, I had to inspect multiple actions or leave for Help. Now **Import citations
file… (EndNote RIS)** is self-identifying, and its modal immediately confirms metadata-only scope and `.txt`
acceptance. I am not misled into expecting PDFs.

**Day-one Mendeley migrator:** onboarding names my source manager in both the short explanation and the leading
action. I learn that Zotero owns the online import/login step, then return to **Read Zotero / migrated Mendeley
library…**. Later, + Add retains **(Mendeley bridge)** visibly instead of hiding the relationship in a desktop-
only tooltip. The unavoidable Zotero hop remains friction, but it is the documented bridge rather than a dead end.

**Hierarchy/design finding:** keeping one primary action is still correct: Zotero direct and the composed Mendeley
bridge preserve PDFs/organization, while RIS/BibTeX/CSL-JSON and bundles have narrower disclosed contracts. Making
all three primary would create visual competition and erase that distinction. The existing vertical action stack
and plain menu rows match `DESIGN.md`; no redesign or new style was warranted.

## Documentation consistency

- Inc 485 now records exact-row relink immutability and both native creation paths.
- Inc 486/487 use the visible EndNote/Mendeley labels rather than stale “Import file”/tooltip language.
- Inc 488 explicitly routes library migration back through inc 486/487 before restating the intentionally gated
  live-Word-field boundary.
- `CLAUDE.md`, backlog #57, the Phase 4 PASS audit, Routes 00/27/77/93, the QA template, Help, the Mendeley
  integration scope, and the assembled frontend carry the same contracts.

## Verification

- Initial red proof: combined importer/frontend run → **2 failed, 75 passed**; failures were the relink identity
  drift and missing note-create attachment id described above.
- After fixes: `pytest tests/test_zotero_importer.py tests/test_annotations.py tests/test_papers.py
  tests/test_frontend_assembly.py tests/test_grobid_tei_parse.py -q` → **170 passed**.
- Per-file confirmation: Zotero importer **9 passed**; frontend assembly **68 passed**; GROBID TEI parser
  **11 passed**.
- `uv run python tools/run_bandit.py` → exit **0** with no findings (the exact previously-failing CI command).
- `ruff check .` → **All checks passed**; `python -m tach check` → **All modules validated**; line budget → all
  **553** application-source files ≤ 600 (`30_viewer.jsx` is 582).
- Final `pytest -n auto -q` → **2341 passed, 3 skipped in 932.07s (0:15:32)**.
- Final surface map → **428/428 API** and **1767/1767 frontend** surfaces covered; website coverage → **70 QA
  routes (1 excluded), 6 external surfaces, 20 current figures**; demo coverage → all **121** surfaces categorized.
- Final Help check → **14 passed**. Format/lint, Tach, Bandit, line budget, website, demo, and surface-map gates
  all passed in the same worktree.

## Honest completion boundary

No real EndNote-created export or live Mendeley/Zotero account flow became available; Phases 2 and 3 retain their
existing manual-verification boundaries. Phase 5 remains gated exactly as inc 488 left it. This increment changes
findability and hardens already-shipped attachment truth; it does not broaden any migration-format promise.
