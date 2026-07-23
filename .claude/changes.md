# Changes

Running human-readable log of non-trivial changes (newest first). The increment notes
are the design diary; this is the chronological "what & why" record.

> **Help-doc sync markers:** a `<!-- HELP-DOCS-SYNCED … -->` line marks where the served help corpus
> (`app/backend/help/help_content.md`) was last brought current. Because this log is newest-first, **every
> entry _above_ the topmost marker is a change made since the last help sync** — the set to review when
> deciding whether the help docs need updating (see CLAUDE.md Session kickoff). When an increment updates
> the corpus, it moves the marker forward to the top of its entry (replacing the prior one).

## 2026-07-23 — LibreOffice adapter: bibliography editing — include uncited / exclude cited (P1 item #11)

- **Files:** `app/backend/citations/citeproc_runner.js`, `app/backend/citations/render.py`,
  `app/backend/api/routers/citations.py`, `adapters/libreoffice/callosum_cite.py`,
  `adapters/libreoffice/citations_panel.py`, `adapters/libreoffice/selftest_uno.py`, `tests/test_citations.py`,
  `tests/test_libreoffice_adapter.py`, `.claude/security-audits/2026-06-21_citation-render-document.md`
  (addendum), `adapters/libreoffice/oxt/description.xml` (0.2.0 → 0.3.0).
- **What:** wired two real, pre-existing-but-unused citeproc-js mechanisms (`updateUncitedItems`,
  `makeBibliography`'s field-filter `exclude`) through `POST /citations/render-document` (two new additive
  request fields) and the LibreOffice adapter: "Add uncited work(s)…" (reuses the composer dialog verbatim)
  and "Toggle bibliography exclude", both now live in the "Citations in this document" panel, which moves from
  read-only to read-write. Along the way, found and fixed a real, previously-latent bug in
  `_write_bibliography`: `cursor.setString("")` on the bookmark-bounded range doesn't reliably remove the
  bookmark *objects* themselves, so a second-and-later rebuild could collide on name with survivors and
  silently accumulate an orphaned stack of old bibliography blocks — fixed via explicit
  `text.removeTextContent()`, the same pattern already used for ReferenceMarks.
- **Why:** next pick after the citations panel (P1 item #12); Cliff chose bibliography editing (roadmap item
  #11) as the next LibreOffice P1 slice.
- **Revert:** `git revert` this commit; rebuild the `.oxt` via `python tools/build_libreoffice_oxt.py`.

## 2026-07-23 — LibreOffice adapter: "Citations in this document" panel (P1 item #12)

- **Files:** `adapters/libreoffice/citations_panel.py` (new), `adapters/libreoffice/callosum_cite.py`,
  `adapters/libreoffice/selftest_uno.py`, `adapters/libreoffice/oxt/{Addons.xcu,description.xml}`,
  `adapters/libreoffice/README.md`, `tools/build_libreoffice_oxt.py`, `tests/test_libreoffice_adapter.py`,
  `tests/test_libreoffice_oxt.py`.
- **What:** a read-only panel listing every unique cited work in the document — occurrence count,
  missing/orphaned status, retraction status, a live filter, and click-to-navigate — modeled on RefWorks' "My
  Citations" view. Deliberately a **modal snapshot**, not a true always-open/live-refreshing panel: no dialog
  in this codebase has ever been non-modal, and building one would need new, unproven UNO lifecycle plumbing
  (an `XModifyListener`, a way to keep the window from being garbage-collected between the `.oxt` dispatcher's
  stateless per-click invocations) — deferred explicitly, not silently dropped. Extension version 0.1.1 → 0.2.0.
- **Why:** next pick after Cliff hand-verified the composer live in Writer ("a great start!") and asked what to
  build next. Surfaced along the way: the `INCREMENT-BACKLOG.md` #33/#34 entry was stale, describing an
  already-shipped P0 batch (incs 320–328) as still "active now" — corrected by reading the actual code rather
  than trusting the backlog's own prose.
- **Revert:** `git revert` this commit; `.oxt` rebuild via `python tools/build_libreoffice_oxt.py`.

## 2026-07-23 — Backlog #21: Tauri desktop-shell feasibility research + spike

- **Files:** `.claude/docs/future-tracks/desktop-packaging-tauri.md` (new), `.claude/docs/future-tracks/README.md`.
- **What:** a feasibility research doc (the OS-keychain half of #21 is already mostly done via inc 152; the
  real open question is bundling the Python/FastAPI backend + its ML stack — torch alone measured at 1.19 GB —
  into a Tauri sidecar, with an ONNX Runtime embedding-backend swap flagged as worth evaluating first to shrink
  that footprint) plus a hands-on spike: installed Rust via winget, scaffolded a minimal Tauri v2 app, pointed
  its window at the already-running callosum backend. **Confirmed working** — Cliff watched the real callosum
  UI render in a native window. The spike project itself is intentionally not committed (throwaway, per
  Cliff's chosen scope); it lives outside the repo at `C:\tauri-spike\`.
- **Why:** last item in Cliff's 12-item decision queue; #21 was always exploratory, and he chose "research doc
  + a small spike" over a full scaffold build when asked how far to take it.
- **Revert:** `git revert` (docs-only; nothing else in-repo changed).

## 2026-07-22 — Backlog #20: branch protection (required status checks)

- **Files:** none in-repo — a GitHub repository-settings change via the API (`.claude/docs/increment-notes/
  INCREMENT-342-NOTES.md` records it).
- **What:** added a `required_status_checks` rule (`lint-and-test` + `e2e-smoke`,
  `strict_required_status_checks_policy: true`) to the pre-existing "Callosum Rules" ruleset
  (`PUT /repos/cliffworkman/callosum/rulesets/18586133` — note `PUT`, not `PATCH`, which 404s). Presented
  Cliff three options (status-checks-only / that plus a required PR / hold off); he chose status-checks-only.
- **Why:** closes the last open piece of backlog #20 now that all three CI gates are green. Cliff's admin
  role already bypasses every rule on this ruleset "always", so his own direct-push-to-main workflow is
  completely unaffected — this only binds a future non-admin contributor or a low-privilege token to green CI
  before their commit can land.
- **Revert:** `PUT` the ruleset back to its prior `rules` array (recorded in the increment notes and in this
  session's `gh api` output) to remove the `required_status_checks` entry.

## 2026-07-22 — Backlog #20 remainder: uv, pre-commit framework, CI gates one at a time, staged-harnesses registry

- **Files:** `pyproject.toml`, `uv.lock` (new), `.gitignore`, `requirements-dev.txt`, `.pre-commit-config.yaml`
  (new, replaces `tools/git-hooks/pre-commit`, deleted), `.github/workflows/ci.yml`,
  `.github/workflows/libreoffice-adapter.yml` (setup-node bump only), `.github/dependabot.yml` (new),
  `alembic.ini`, `alembic/env.py`, `tests/test_migrations.py` (new),
  `.claude/security-audits/2026-06-20_pre-github-fullsweep.md` (addendum),
  `.claude/staged-harnesses/` (new, 8 files), `.claude/CLAUDE.md`, `CONTRIBUTING.md`.
- **What:** four commits, each pushed and confirmed green on GitHub Actions before the next landed — (1) uv
  adoption (`pyproject.toml` normalized + `[dependency-groups].dev` + committed `uv.lock`; CI installs via
  `uv sync --locked`) + migrated the hand-rolled git hook to the standard pre-commit framework (ruff +
  600-line budget + whitespace/EOF/large-file hygiene), including a one-time whitespace/EOF sweep across 31
  files; (2) a new CI gate — `alembic upgrade head` + `alembic check` against a fresh temp DB, catching both
  broken migrations and model/migration drift (required excluding the FTS5 `chunks_fts*` tables from the
  drift check — they have no SQLAlchemy `Table` equivalent by design); (3) a new CI gate — `pip-audit` blocking
  on `requirements.txt` (clean), report-only on `requirements-dev.txt` (one accepted dev-only finding: pytest
  8.4.2/PYSEC-2026-1845) — plus Dependabot enabled for uv/npm/github-actions; (4) the `.claude/staged-harnesses/`
  registry — 7 dormant fitness-function drafts (Pyright, tach, coverage gate, Hypothesis, embedding-drift,
  performance monitoring, bandit) each with an explicit activation trigger, per the harness-hardening plan's
  two-bucket split.
- **Why:** next in Cliff's 12-item backlog decision queue; executes
  `.claude/docs/future-tracks/opus4.8_future-tracks_harnesshardening.md` (backlog #20) Phases 1-4. Branch
  protection (that plan's Phase 5) is deliberately NOT applied yet — the exact ruleset gets shown to Cliff for
  sign-off first (a repo-wide, security-relevant GitHub setting, not a local file change).
- **Revert:** `git revert` the six commits `f0182af`→`703a407` (`f0182af` uv/pre-commit, `fa6fa77` a
  setup-uv version-pin fix, `6d00a12` the alembic gate, `57041be` a YAML-quoting fix, `2e5f09f` pip-audit +
  Dependabot, `703a407` the staged-harnesses registry); each was independently verified green in sequence.

## 2026-07-22 — Backlog #15: sync_server hardening (rate limiting, retention, backup runbook)

- **Files:** `sync_server/rate_limit.py` (new), `sync_server/schema.py`, `sync_server/store.py`,
  `sync_server/app.py`, `sync_server/prune_tombstones.py` (new), `sync_server/OPERATIONS.md` (new),
  `sync_server/README.md`, `tests/test_sync_server.py`,
  `.claude/security-audits/2026-06-29_sync-server.md` (addendum).
- **What:** per-user (OIDC `sub`-keyed) rate limiting on both `/sync/records` routes; a 90-day tombstone
  retention policy via a standalone CLI script for cron, not an in-process scheduler; a backup/restore runbook
  that's explicit about what a sync-server backup does and doesn't protect (opaque sync state, never a user's
  plaintext library). A per-user storage quota and a general migration tool stay explicitly out of scope.
- **Why:** Cliff's choice from the 12-item decision queue ("build the hardening code"); closes 3 of the 4
  pre-public-deploy follow-ons the original 2026-06-29 sync-server audit recorded. The live juno deploy stays
  entirely his own infra — untouched by this change.
- **Revert:** `git revert` this commit.

<!-- HELP-DOCS-SYNCED 2026-07-22 inc 340 — permanent-delete help now states that Callosum-managed attachment
files are removed while externally linked files remain on disk. Nothing above this line has an un-synced corpus
change. -->
## 2026-07-22 — Backlog #14: permanent delete removes Callosum-managed files

- **Files:** `app/backend/paper_purge.py`, `app/backend/persistence/paper_lifecycle_repo.py`,
  `app/backend/persistence/repository.py`, `app/backend/api/routers/papers.py`, `app/frontend/js/03_library.jsx`,
  `callosum-app.html`, `app/backend/help/help_content.md`, `tests/test_papers.py`,
  `tests/test_short_write_sweep.py`, `.claude/qa-routes/route_40_papers_crud_trash.md`, and the increment-340
  notes/security audit.
- **What:** Delete forever and Empty Trash now remove root-contained `managed` attachment files, with reversible
  staging around the database/vector transaction. Linked, URL, out-of-root, shared, missing, directory, and symlink
  paths remain untouched; file-lock failures leave the paper in Trash and are shown to the user.
- **Why:** close backlog #14 without treating external file pointers as files Callosum owns.
- **Revert:** `git revert` this commit. The pre-change snapshot is
  `.claude/backups/callosum_inc340_pre_managed_file_purge.zip`.

<!-- HELP-DOCS-SYNCED 2026-07-22 inc 339 — reviewed the entries below back to the prior (inc 338) marker.
Added role-bundle + "and"-toggle bullets to "Building a CRediT contribution statement", and a one-line mention
of the new jump-link to "Where to submit" (backlog #26). The LibreOffice .oxt fix entry below is a packaging
bug fix with no user-facing behavior change to document (composer already worked once installed correctly).
Nothing above this line has an un-synced corpus change. -->
## 2026-07-22 — Backlog #26: CRediT builder — role presets + "and" formatting + discoverability jump-link

- **Files:** `app/backend/methods/credit.py`, `app/backend/api/routers/credit.py`,
  `app/frontend/js/38_credit.jsx`, `app/frontend/js/40_app.jsx`, `app/frontend/js/08e_methods_publishers.jsx`,
  `app/frontend/styles.css`, `tests/test_credit.py`, `.claude/qa-routes/route_66_credit.md`,
  `app/backend/help/help_content.md`.
- **What:** three inc-261 experience-pass follow-ups, all closed: per-author role-bundle buttons (First author
  / PI / Collaborator — a pure client-side toggle shortcut, same `roles` state as manual clicks); an opt-in
  "and" before the last by-role contributor name (`use_and`, default off); a jump-link from Discover → Journals
  to Work → CRediT.
- **Why:** Cliff's choice from the 12-item decision queue ("build presets anyway, skip the discussion" for
  the presets specifically).
- **Revert:** `git revert` this commit.

## 2026-07-22 — fix: LibreOffice .oxt missing composer.py ("No module named 'composer'")

- **Files:** `tools/build_libreoffice_oxt.py`, `adapters/libreoffice/oxt/description.xml`,
  `tests/test_libreoffice_oxt.py`.
- **What:** `composer.py` (the Phase 5a citation composer, added earlier this session) was never added to the
  `.oxt` build script's `ENTRIES` list, so every packaged install was missing it — `import composer` 404ed with
  "No module named 'composer'" the moment **Add citation** or **Edit citation** actually opened the composer
  dialog. Fixed the list, bumped the extension version `0.1.0` → `0.1.1` (so LibreOffice's Extension Manager
  recognizes it as an update), and added a regression test (`test_every_local_sibling_import_is_packaged`) that
  scans `callosum_cite.py` for local sibling imports and asserts each is actually bundled — this class of bug
  can't recur silently now, regardless of which new adapter module gets added next.
- **Why:** Cliff hit this live while actually using the LibreOffice adapter to add citations — a real,
  blocking regression from earlier in the session, caught by dogfooding rather than any existing test (the
  existing `test_build_oxt_has_expected_entries` had a stale hardcoded entry list that just matched the bug).
- **Revert:** `git revert` this commit — but there's no reason to; this is a straightforward correctness fix.

## 2026-07-22 — Backlog #23 (3/3, CLOSED): Bayesian auditor — F1 chip + F4 persistence + F2 footer fix

- **Files:** `app/backend/persistence/signals_repo.py`, `app/backend/methods/bayes.py`,
  `app/backend/api/routers/methods.py`, `app/backend/api/routers/methods_bayes.py` (new),
  `app/backend/persistence/paper_query_repo.py`, `app/backend/api/app.py`, `app/frontend/js/03_library.jsx`,
  `app/frontend/js/40_app.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/08d_methods_bayes.jsx`,
  `app/frontend/styles.css`, `tests/test_bayes.py`,
  `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md`,
  `.claude/qa-routes/route_59_methods_bayes.md`, `app/backend/help/help_content.md`.
- **What:** the Bayesian auditor gets the same F1/F4/F2 build as LMM/meta-analysis, combining its two
  independent signals (a BF-reproduction mismatch + a reporting-completeness gap) into one `flagged` status.
  `GET /papers/{id}/bayes` moved out of `methods.py` into its own `methods_bayes.py` router (the file was out
  of headroom for the new batch endpoints). **Backlog #23 is now fully closed** — full suite: 1380 passed,
  1 skipped.
- **Why:** third and last of three checkers in backlog #23's full-scope build (Cliff's choice).
- **Revert:** `git revert` this commit.

## 2026-07-22 — Backlog #23 (2/3): meta-analysis auditor — F1 chip + F4 persistence + F2 footer fix

- **Files:** `app/backend/persistence/signals_repo.py`, `app/backend/methods/metaanalysis.py`,
  `app/backend/api/routers/metaanalysis.py`, `app/backend/persistence/paper_query_repo.py`,
  `app/backend/api/app.py`, `app/frontend/js/03_library.jsx`, `app/frontend/js/40_app.jsx`,
  `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/08g_methods_metaanalysis.jsx`, `app/frontend/styles.css`,
  `tests/test_metaanalysis.py`, `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md`,
  `.claude/qa-routes/route_62_methods_metaanalysis.md`, `app/backend/help/help_content.md`.
- **What:** same F1/F2/F4 build as LMM (inc 336), now for the meta-analysis reporting auditor — mechanical
  repetition of a proven pattern, no new design decisions.
- **Why:** second of three checkers in backlog #23's full-scope build.
- **Revert:** `git revert` this commit.

## 2026-07-22 — Backlog #23 (1/3): LMM auditor — F1 chip + F4 persistence + F2 footer fix

- **Files:** `app/backend/persistence/signals_repo.py`, `app/backend/methods/lmm.py`,
  `app/backend/api/routers/lmm.py`, `app/backend/persistence/paper_query_repo.py`, `app/backend/api/app.py`,
  `app/frontend/js/03_library.jsx`, `app/frontend/js/40_app.jsx`, `app/frontend/js/10_pdf_layer.jsx`,
  `app/frontend/js/08f_methods_lmm.jsx`, `app/frontend/styles.css`, `tests/test_lmm.py`,
  `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md`,
  `.claude/qa-routes/route_61_methods_lmm.md`, `app/backend/help/help_content.md`.
- **What:** the LMM auditor gets a library-wide batch + header chip (F1), persists a candidate finding as a side
  effect of the existing ad-hoc per-paper view (F4), and no longer shows its credit footer before confirming
  the paper is actually a mixed-model paper (F2).
- **Why:** Cliff's choice to build backlog #23 in full, one checker at a time; LMM first to prove the pattern
  before repeating it for meta-analysis and Bayesian.
- **Revert:** `git revert` this commit.

## 2026-07-22 — Backlog #19: tags ↔ findings/system-facts (retraction-surfacing)

- **Files:** `app/backend/methods/retraction.py`, `app/backend/persistence/tags_repo.py`,
  `app/backend/api/routers/tags.py`, `app/frontend/js/00_lib.jsx`, `app/frontend/js/25b_tags.jsx`,
  `app/frontend/js/10e_tagspanel.jsx`, `tests/test_retraction.py`, `tests/test_tags.py`,
  `tests/test_frontend_assembly.py`, `app/backend/help/help_content.md`, `.claude/docs/data-contracts.md`,
  `.claude/docs/glossary.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/docs/INCREMENT-BACKLOG-DONE.md`.
- **What:** `apply_retraction()` now links/unlinks a real, non-editable `system:retraction:retracted` tag in
  lockstep with the existing FACT/signal — an additive discovery path through the generic tag/tag-filter
  mechanism, alongside the pre-existing (unchanged) `signal=retraction-retracted` chip/filter.
- **Why:** Cliff's choice from the 12-item decision queue ("build a filter for this"); #9 had already reserved
  and sketched the naming-only approach, so this closes #19 with no schema change.
- **Revert:** `git revert` this commit.

## 2026-07-22 — Backlog #9: tag provenance vocabulary formalization

- **Files:** `app/backend/persistence/tags_repo.py`, `app/backend/importers/zotero.py`,
  `app/backend/metadata/enrichment.py`, `app/backend/api/routers/agent.py`,
  `alembic/versions/0047_tag_source_vocabulary.py`, `app/frontend/js/00_lib.jsx`,
  `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/10e_tagspanel.jsx` (new), `app/frontend/styles.css`,
  `tests/test_tags.py`, `tests/test_agent_writes.py`, `tests/test_zotero_importer.py`,
  `app/backend/help/help_content.md`, `.claude/docs/data-contracts.md`, `.claude/docs/glossary.md`,
  `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/docs/INCREMENT-BACKLOG-DONE.md`.
- **What:** formalized `tags.import_source` as a `{namespace}:{origin}` contract (`user` sentinel +
  `import`/`keyword`/`agent`/`system`-reserved namespaces), renamed the two non-conformant producers
  (`zotero`→`import:zotero`, `ai-agent`→`agent:mcp`, tag-column only, via a data migration), and grouped the
  sidebar Tags browser by exact source.
- **Why:** Cliff's own choice from the 12-item decision queue ("formalize the vocabulary too"), and the
  formal reservation of `system:{fact}` un-blocks #19 (tags ↔ retraction findings), next in the queue.
- **Revert:** `git revert` this commit; the alembic migration is additive-only (data rename, no down-migration
  by project convention — re-running `_RENAMES` in reverse would restore the bare values if ever needed).

## 2026-07-22 — Backlog #20: repo furniture (SECURITY.md, CITATION.cff, .env.example)
- **Files:** `SECURITY.md` (new), `CITATION.cff` (new), `.env.example` (new), `CONTRIBUTING.md`.
- **What:** three static, non-code additions, the first of #20's now-greenlit scope. `.env.example` documents
  every `CALLOSUM_*` and provider-key environment variable actually read by the codebase (grepped for
  `os.environ`/`os.getenv` calls, not just the README's user-facing subset — includes the remote-access/OIDC/
  superuser/OCR/HTTPS-port variables too), organized by concern. `SECURITY.md` is honest about there being no
  dedicated private-reporting channel yet (a `TODO(maintainer)` marker, not an invented email) and names the
  project's actual internal audit-gate discipline. `CITATION.cff` has no ORCID (flagged for Cliff to add, not
  guessed). `CONTRIBUTING.md` gained a one-line pointer to `SECURITY.md`.
- **Why:** backlog #20 (harness hardening) — Cliff greenlit the full scope; this is the safe, non-workflow-
  changing slice, done first.
- **Revert:** `git log` this commit.

## 2026-07-22 — README voice pass (backlog #11)
- **Files:** `README.md`.
- **What:** a style/voice rewrite of the opening (a first-person "why this exists" sentence before the thesis
  statement), the Status callout, a few section asides, and the "Built with AI assistance" closer — all drafted
  to a scratch file first, reviewed, and approved before applying. Also fixed one accuracy gap riding along:
  "Cite from your word processor" now mentions the composer's search-as-you-type/locators/Edit-Citation
  capabilities, which the old copy predated. Feature lists/Quickstart/config tables left structurally alone —
  already dense/scannable in a way prose would only hurt.
- **Why:** backlog #11 — explicitly Cliff's own voice/style call; he asked for a draft to react to instead of
  writing it himself, reviewed it, and approved as-is.
- **Revert:** `git log` this commit.

## 2026-07-22 — Relocate the working library DB out of the Dropbox-synced folder
- **Files:** `run-callosum.ps1`; the persisted `CALLOSUM_DB_URL` User environment variable (not repo state).
- **What:** the machine's real, 209-paper working library (`.local/validation-summarize/validation.sqlite`,
  378MB) lived inside the Dropbox-synced project tree — exactly the setup the README warns against (a real
  `database is locked` risk). Confirmed a live uvicorn (port 8888) had it open; Cliff stopped it, then the WAL
  was checkpointed into the main file, copied to `C:\Users\cliff\callosum-data\library.sqlite` (integrity
  checked, paper counts confirmed identical), and `CALLOSUM_DB_URL` repointed there. Verified end-to-end with a
  live smoke-test server on a scratch port before touching the persisted launcher script. The old copy is left
  in place, untouched, as a backup.
- **Why:** flagged in the pre-presentation readiness review as a real risk; Cliff's own call on the target path.
- **Revert:** the old file at its original path is untouched; re-point `CALLOSUM_DB_URL` back if ever needed.

## 2026-07-22 — Help docs: rewrite "Citing in LibreOffice Writer" (closes the flagged staleness)
- **Files:** `app/backend/help/help_content.md`.
- **What:** the served help corpus's LibreOffice section predated the entire Phase 0-10 + 5a/5b/5c rework — it
  still described the old one-shot search+single-select "Add citation…" flow and never mentioned Edit
  Citation, delete/merge/split/open-in-callosum, the bibliography controls, document diagnostics, or Prepare
  submission copy. Rewritten in full to describe the actual current menu: the composer (live search, Options
  incl. locator/prefix/suffix/suppress-author, Move ↑/↓ reorder, the beyond-library checkbox), Edit citation…,
  every existing-citation action, both bibliography controls, Document diagnostics…, and Prepare submission
  copy vs. Flatten.
- **Why:** flagged during backlog #27 (the statcheck fix) as a real, un-actioned gap; the user asked for it to
  be addressed as its own pass rather than folded into the smaller statcheck fix.
- **Revert:** `git log` this commit.

## 2026-07-22 — Backlog #27: statcheck reads test statistics reported as a bound, not just "="
- **Files:** `app/backend/methods/statcheck.py`, `tests/test_statcheck.py`, `app/backend/help/help_content.md`.
- **What:** the test-statistic comparator is no longer required to be "=" — statcheck now also reads APA
  reports like `F(1, 44) < 1, p > .05` (a common way to report a clearly-null result without an exact F). A
  new `_classify_stat_bound` handles the inequality case: the reported bound implies a p-value INTERVAL (p is
  monotonically decreasing in |stat|), and consistency reuses the existing `_p_consistent` "does at least one
  valid true value exist" check — never a false "inconsistent" flag on an ambiguous case, and never a
  "decision-error" classification (that needs a point estimate this input doesn't have). Verified against
  exact scipy-computed reference p-values, not guessed. Help corpus updated with a short, honest description of
  the new coverage + its ambiguous-case handling. "Results reported in tables" (the other half of backlog #27)
  remains out of scope — a structurally different problem (table-aware extraction, not a regex extension).
- **Why:** backlog #27, "more statcheck test forms" — picked up as a small, self-contained item while working
  through the backlog generally.
- **Revert:** `git log` this commit. **Note, not synced this pass:** the help corpus's "Citing in LibreOffice
  Writer" section is now substantially stale relative to this session's LibreOffice adapter work (the
  composer, beyond-library suggest, Edit Citation, diagnostics — none of it reflected there yet) — flagged as
  its own follow-up rather than folded into this narrower fix; the `HELP-DOCS-SYNCED` marker is deliberately
  NOT moved forward, since that section is still genuinely un-synced below it.

## 2026-07-22 — Backlog #45: Settings name-example placeholder, Ada Lovelace → Karen Spärck Jones
- **Files:** `app/frontend/js/35a_mypubs.jsx`, `callosum-app.html` (rebuilt).
- **What:** the My Publications "Your name" / "Other published names" input placeholders now read "e.g. Karen
  Spärck Jones" / "e.g. K. Spärck Jones" instead of "e.g. Ada Lovelace" / "e.g. A. Lovelace".
- **Why:** Cliff's request — a real non-ASCII ("ä") test case for these fields, and a credit-the-lineage nod:
  Spärck Jones's TF-IDF work underlies the term-weighting/retrieval methods callosum's search leans on. (The
  many unrelated "Ada Lovelace" test fixtures used as a generic stand-in author name across the test suite were
  left untouched — out of scope; the ask was specifically the Settings UI example.)
- **Revert:** `git log` this commit.

## 2026-07-22 — Increment 332: backlog #30 — LibreOffice beyond-library suggest + doc-drift fixes
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno,README}.py/.md`, `tests/test_libreoffice_adapter.py`,
  `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/docs/increment-notes/INCREMENT-332-NOTES.md`,
  `.claude/qa-routes/route_42_cite.md`, `integrations/README.md`, `integrations/semantic-scholar/` (removed).
- **What:** research before writing any code found backlog #30's framing ("the highest-value unbuilt
  capability") was itself stale — `beyond_library.py`'s OpenAlex-graph + public-metadata suggest engine already
  shipped inc 271/272, audited PASS, just never folded back into the backlog doc since it landed as one large
  uncredited commit with no increment notes. Wired the ALREADY-shipped engine into the LibreOffice adapter's
  Suggest macro (an opt-in checkbox, default off, matching the audited web consent model exactly; picking a
  beyond-library result saves it via the same `/discovery/save` path the web "Add to library" button uses,
  then cites it). Fixed the doc drift this surfaced: `INCREMENT-BACKLOG.md`'s #30 entry, a badly-stale
  `integrations/README.md` (listed real adapters as "planned"), a dead duplicate `integrations/semantic-scholar/`
  stub, and a QA route (`route_42_cite.md`) whose steps never actually exercised the beyond-library UI despite
  the mechanical coverage gate already passing.
- **Why:** the user chose to tackle #30, and the honest next step once its real state was understood was
  closing the one genuine gap (LibreOffice wiring) plus the documentation debt, not building a duplicate feature.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-332-NOTES.md`. A real empirical
  finding recorded there: a programmatic checkbox `setState()` does not fire `XItemListener.itemStateChanged`
  in this LibreOffice version (standard UNO/AWT behavior, not a bug) — applies retroactively to the Phase
  5b/5c Options dialog's mutex checkboxes too, folded into the standing composer manual-verification debt.

## 2026-07-22 — Increment 331: LibreOffice adapter rework, Phase 5c (Edit Citation) — closes backlog #33/#34
- **Files:** `adapters/libreoffice/{callosum_cite,composer,selftest_uno,README}.py/.md`,
  `adapters/libreoffice/oxt/Addons.xcu`, `tests/test_libreoffice_composer.py` (new),
  `tests/test_libreoffice_adapter.py`, `.claude/docs/increment-notes/INCREMENT-331-NOTES.md`.
- **What:** "Edit citation…" reopens the composer pre-populated from an existing citation (via `mark_at_cursor`),
  supporting add/remove/reorder (new Move ↑/↓ buttons) and per-item options, then saves back to the SAME
  citation identity (never mints a new rnd). Investigated and deliberately declined building a "restore
  style-defined sort" action — CSL/citeproc-js has no per-request override for a style's own sort behavior, so
  such a button would be a no-op for 4 of the 7 bundled styles; a control implying capability the tool doesn't
  have would itself be a transparency regression. Also added real pytest coverage for `composer.py`'s pure
  helpers (a gap from Phase 5a/5b — the module loads fine under plain pytest; only its dialog-building
  functions need real UNO).
- **Why:** the last piece of the original Phase 5 (composer) scope — and with it, the entire P0 LibreOffice-
  adapter rework (backlog #33/#34, phases 0-10 + 5a-5c) is now shipped.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-331-NOTES.md`. Note: the
  composer (Insert and Edit) still hasn't been driven by a real human in real Writer — flagged across three
  increments now, not assumed away.

## 2026-07-22 — Increment 330: LibreOffice adapter rework, Phase 5b (per-item locator/prefix/suffix)
- **Files:** `adapters/libreoffice/{callosum_cite,composer,selftest_uno,README}.py/.md`,
  `.claude/docs/increment-notes/INCREMENT-330-NOTES.md`.
- **What:** the composer's assembled items can now carry a per-occurrence locator (the exact 19-value CSL
  label vocabulary), prefix, suffix, suppress-author, or author-only — via a new "Options…" sub-dialog, with
  suppress-author/author-only kept mutually exclusive in the UI. `insert_citation_items`'s signature changed
  from bare paper ids to item dicts to carry these. A real-UNO spike confirmed all five overrides reach actual
  citeproc-js output correctly (e.g. suppress-author → `'(2017)'`, author-only → `'Vaswani & Shazeer'`).
- **Why:** the backend/schema have supported all of this since Phases 1/3; this was purely wiring the composer
  UI to what already existed server-side — the next slice of the deferred Phase 5 composer work.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-330-NOTES.md`. Note: like
  Phase 5a, the composer + its new Options dialog haven't been driven by a real human in real Writer yet.

## 2026-07-22 — Increment 329: LibreOffice adapter rework, Phase 5a (the composer)
- **Files:** `adapters/libreoffice/composer.py` (new), `adapters/libreoffice/{callosum_cite,selftest_uno,README}.py/.md`,
  `.claude/docs/increment-notes/INCREMENT-329-NOTES.md`.
- **What:** a live-search, multi-item citation composer replacing the old one-shot search+single-select "Add
  citation…" flow — search-as-you-type, an assembly list, a real rendered preview (never simulated), Insert.
  New backend `insert_citation_items` generalizes `insert_citation` to wrap multiple papers in one mark. A
  real-UNO spike (this codebase's first UNO event-listener beyond the .oxt dispatcher itself) confirmed a
  programmatic `setText()` reliably fires `XTextListener.textChanged` and a synchronous local search-refresh
  has no reentrancy issue (~26-37ms round-trip) — simple enough that no debounce timer was needed.
- **Why:** Phase 5 was the last major deferred piece of the P0 rework; scoped into 5a/5b/5c the same way every
  other phase in this rework got scoped, rather than attempting the whole original spec in one pass.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-329-NOTES.md`. Note: the
  composer itself has NOT been driven by a real human in real Writer yet — flagged as an open manual-verification
  gap, not assumed away.

## 2026-07-21 — Increment 328: LibreOffice adapter rework, Phase 10 (test-hardening, closes #33/#34's P0 batch)
- **Files:** `adapters/libreoffice/run_roundtrip.py` (new, promoted from gitignored `.local/`),
  `.github/workflows/libreoffice-adapter.yml` (new), `adapters/libreoffice/{selftest_uno,README}.py/.md`,
  `tests/test_libreoffice_{install,oxt}.py`, `.claude/docs/increment-notes/INCREMENT-328-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** promoted the manual, gitignored real-UNO test orchestrator into a committed, cross-platform script
  (Windows for local dev, Linux for CI) + a new path-scoped, non-blocking GitHub Actions workflow — closing a
  real structural gap (the adapters sat entirely outside the QA surface-map gate, zero CI enforcement). Also
  fixed a stale 180s selftest timeout (no longer had headroom after Phase 8/9) and cleared a month-stale,
  gitignored `ci.yml.tmp.*` artifact found in passing.
- **Why:** the user asked for this as an explicit final phase after Phase 9, prompted directly by a structural
  blind spot named in this session's earlier strategic readiness review.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-328-NOTES.md`. Note: the new
  CI workflow's Linux path is reasoned-through but unverified on a real GitHub Actions runner (no way to execute
  one from this environment) — flagged explicitly in the increment notes, not silently assumed correct.

## 2026-07-21 — Increment 327: LibreOffice adapter rework, Phase 9 (document diagnostics)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno,README}.md/.py`,
  `adapters/libreoffice/oxt/Addons.xcu`, `tests/test_libreoffice_adapter.py`,
  `.claude/docs/increment-notes/INCREMENT-327-NOTES.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/CLAUDE.md`.
- **What:** a read-only "Document diagnostics…" action — reports malformed citation marks, citations from an
  unsupported future schema version, citation-id collisions, citations whose source paper is no longer in the
  library, and whether the bibliography bookmark pair is damaged or just not built yet. Never mutates the
  document. Along the way, found and fixed a real pre-existing bug: `fetch_csl` assumed a missing paper makes
  `/papers/export` return 200 + an empty list, but the endpoint actually 422s — the orphan-detection spike
  caught this on its first real-UNO run (no pytest mock would have). Also queued backlog #45 (swap the "Ada
  Lovelace" Settings placeholder for "Karen Spärck Jones") per Cliff's request — cheap, whenever convenient.
- **Why:** the last of the smaller phases in the P0 LibreOffice-adapter rework (backlog #33/#34), closing states
  the adapter could already describe or safely fix internally but never surfaced to the user.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-327-NOTES.md`.

## 2026-07-21 — README: real screenshot + fixed stale sync claim, ahead of a presentation
- **Files:** `README.md`, `www/` (newly committed — `index.html`, `showcase.html`, `shots/*.png`).
- **What:** a pre-presentation readiness pass surfaced that a finished marketing site (a landing page +
  a 51-screenshot tour) already existed on disk but was uncommitted and unlinked. Committed it, replaced the
  README's long-standing `<!-- TODO(maintainer): add a screenshot -->` placeholder with the real
  `synthesis.png` shot + links to the tour/project page, and corrected the Security note's claim that
  cross-device sync "does not exist yet" — it shipped (incs 197-202, UI 310-311) and has been live in
  production since inc 312.
- **Why:** a strategic release-readiness review (not a coding increment) ahead of the maintainer presenting
  callosum at a meeting; both were cheap, concrete, high-leverage fixes identified by that review.
- **Revert:** `git log` this commit.

## 2026-07-21 — Increment 326: LibreOffice adapter rework, Phase 8 (safe flatten)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno,README}.md/.py`,
  `adapters/libreoffice/oxt/Addons.xcu`, `.claude/docs/increment-notes/INCREMENT-326-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** a new "Prepare submission copy…" action — the safe alternative to a bare, immediate flatten. Saves
  a separate copy with citations converted to static text (verified byte-identical text + zero remaining marks
  before saving), then always undoes the flatten in the open document, so it is never actually left mutated.
  The existing "Flatten to static text" stays available as the advanced, in-place option. Known v1 limitation:
  always saves ODF, regardless of the original document's format.
- **Why:** the next slice of backlog #33/#34's P0 rework — the roadmap's own "a second deliberate choice"
  framing, but made even safer by defaulting to copy-always rather than a checkbox that could be unchecked.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-326-NOTES.md`, including a
  real XML bug caught by the well-formedness check (a bare `--` inside an XML comment) before it shipped.

## 2026-07-21 — Increment 325: LibreOffice adapter rework, Phase 7 (bounded bibliography)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno,README}.md/.py`,
  `adapters/libreoffice/oxt/Addons.xcu`, `.claude/docs/increment-notes/INCREMENT-325-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** replaces the single start-only bibliography bookmark with a **bookmark pair** (start + end) — a
  rebuild now clears + rewrites exactly `[start, end]`, never `text.getEnd()`, closing the ORIGINAL verified
  data-loss finding that started this whole rework. Also adds "Insert bibliography here" (move it to the
  cursor) and a toggle to pause automatic bibliography rebuilding while citations keep updating normally.
- **Why:** this is the actual fix for the bug that was verified against shipped code at the start of backlog
  #33/#34 — everything before this phase was infrastructure (schema, transactional refresh, backend passthrough,
  cursor resolution) needed to build it safely.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-325-NOTES.md`, including a
  real-UNO spike reproducing the original bug live and then confirming it's fixed.

## 2026-07-21 — Increment 324: LibreOffice adapter rework, Phase 6 (delete / merge / split / open-in-callosum)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno,README}.md/.py`,
  `adapters/libreoffice/oxt/Addons.xcu`, `app/frontend/js/40_app.jsx`, `tests/test_frontend_assembly.py`,
  `.claude/security-audits/2026-06-21_libreoffice-adapter.md`,
  `.claude/docs/increment-notes/INCREMENT-324-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** the first real user-facing actions built on `mark_at_cursor` (Phase 4): **Delete citation** (removes
  both the field and its rendered text), **Merge with next/previous citation** + **Split citation** (the
  buildable-without-a-composer slice of "true grouped citations"), and **Open in callosum** (a new
  `?open_paper=<id>` browser deep link, read by a new frontend mount effect riding the existing `openPdf`
  chokepoint). All four degrade honestly with a message box when the cursor isn't on a recognized citation.
  Verified with real-UNO fault-injection-style spikes, all passing on the first run.
- **Why:** the next slice of backlog #33/#34's P0 rework — Edit Citation itself and "revert manual overrides"
  both need the composer (Phase 5) to mean anything, so this phase scoped to what's buildable without one.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-324-NOTES.md` and the new
  security-audit addendum covering the cumulative P0 phases 1-6 surface.

## 2026-07-21 — Increment 323: LibreOffice adapter rework, Phase 4 (find the mark at the cursor)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno}.py`,
  `.claude/docs/increment-notes/INCREMENT-323-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** a new `mark_at_cursor(doc)` — the shared primitive Edit Citation, Delete Citation, and merge/split
  will all need to resolve "which EXISTING citation is the user pointing at." Every prior action either inserted
  new or operated over all marks; this reuses `scan_citations_in_order`'s decode/filter logic and adds a
  cursor-containment check via `compareRegionStarts`. Verified with a new real-UNO spike (not pytest-fakeable —
  it touches the view cursor + region comparison directly): moving the cursor into citation #2 of 3 correctly
  resolves to citation #2, and a cursor in plain body text correctly resolves to `None`.
- **Why:** the next slice of backlog #33/#34's P0 rework — a small, self-contained lookup that Phases 5/6 both
  depend on, built once rather than duplicated per-action.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-323-NOTES.md`.

## 2026-07-21 — Increment 322: LibreOffice adapter rework, Phase 3 (backend cite-property passthrough)
- **Files:** `app/backend/citations/citeproc_runner.js`, `app/backend/api/routers/citations.py`,
  `tests/test_citations.py`, `.claude/docs/increment-notes/INCREMENT-322-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** locator/label/prefix/suffix/suppress-author/author-only — already carried by every mark's payload
  since Phase 1, but previously discarded at the exact chokepoint where `citeproc_runner.js` built a
  `citationItems` entry as bare `{ id }` — now actually reach citeproc-js. A new typed `CitationItem` Pydantic
  model replaces the bare-dict `CitationCluster.items`, with length-capped locator/prefix/suffix and `label`
  validated against CSL's real, fixed locator vocabulary (422 on garbage rather than a silent no-op).
- **Why:** the next slice of backlog #33/#34's P0 rework — the payload had these fields since Phase 1, but they
  were inert until the backend actually forwarded them.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-322-NOTES.md`, including two
  rendering-behavior assumptions (prefix/suffix wrap inside the cite's own parens; `author-only` is a bare name,
  not a full narrative form) corrected against real citeproc-js output while writing the tests.

## 2026-07-21 — Increment 321: LibreOffice adapter rework, Phase 2 (transactional refresh)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno}.py`, `tests/test_libreoffice_adapter.py`,
  `.claude/docs/increment-notes/INCREMENT-321-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** `refresh()`'s write-back (the per-mark text replace + bibliography rebuild) now runs inside an
  `XUndoManager`-grouped transaction. On success, a refresh is one undoable step for the user; on any failure
  partway through, the whole group is reverted in one call and checked against a pre-mutation snapshot, so a
  partial UNO failure never leaves the document with some citations updated and others (or the bibliography)
  stale. Proved with a real fault-injection spike against headless LibreOffice, not just asserted: a monkeypatch
  forces a failure on the 2nd of 3 write-backs mid-restyle, and the whole document — including the one mark that
  had already been rewritten — rolls back to its exact pre-refresh state.
- **Why:** the next slice of backlog #33/#34's P0 rework, building directly on Phase 0's confirmation that
  `XUndoManager` behaves as needed in this LibreOffice version — this is the first real exercise of it under an
  actual partial failure, not just the simple happy path.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-321-NOTES.md`.

## 2026-07-21 — Increment 320: LibreOffice adapter rework, Phase 0 (spike) + Phase 1 (versioned schema)
- **Files:** `adapters/libreoffice/{callosum_cite,selftest_uno}.py`, `tests/test_libreoffice_adapter.py`,
  `.claude/docs/increment-notes/INCREMENT-320-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** the first two slices of the P0 rework of the shipped LibreOffice citation adapter (backlog #33/#34,
  per the newly-filed `chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md`). Phase 1: a versioned
  ReferenceMark payload schema (`SCHEMA_VERSION = 2`) with backward-compatible decode of every mark written
  before this increment, and an explicit inert-but-present handling of any future unsupported version — no user
  action ever needed. Phase 0: four empirical spikes against a real headless LibreOffice (mark-size/scale +
  save/reopen fidelity: PASS; `XUndoManager` grouping/revert: CONFIRMED WORKING; within-document copy/paste of a
  citation mark: Writer refuses the name collision; a `TextSection`-bounded bibliography prototype: FAILED,
  redirecting Phase 7 toward a `Bookmark`-pair approach instead).
- **Why:** the roadmap graduated from a quick fix to a real multi-increment program once the bibliography
  data-loss claim was verified against shipped code; these two phases are the foundational, bounded, verifiable
  first slices every later phase depends on.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-320-NOTES.md` for the full
  design, including the live reproduction of the bibliography bug via an ordinary "cite, cite again" sequence
  during the spike itself (not a contrived edge case).

## 2026-07-21 — Increment 319: scroll-to-reveal the selected paper in the library list
- **Files:** `app/backend/api/routers/{papers,paper_models}.py`, `app/backend/persistence/{repository,
  paper_query_repo}.py`, `app/frontend/js/{03_library,10d_papercard,40_app,04b_workspaces}.jsx`,
  `app/frontend/styles.css`, `tests/{test_papers,test_frontend_assembly}.py`, `callosum-app.html`,
  `.claude/qa-routes/{route_40_papers_crud_trash,route_67_critical_review,route_73_workspaces}.md`,
  `.claude/security-audits/2026-07-21_paper-position.md`, `.claude/DESIGN.md`, `.claude/CLAUDE.md`,
  `.claude/docs/increment-notes/INCREMENT-319-NOTES.md`.
- **What:** three linked fixes so the library's `selected` paper always corresponds to what the user is actually
  looking at: (1) the selected/open-paper cue now renders on every workspace tab, not a 4-tab whitelist; (2) a
  single `activeTab`-keyed effect keeps `selected` in sync with whichever PDF tab is focused, however it was
  opened; (3) a new `GET /papers/{paper_id}/position` endpoint + a library effect that jumps to the selected
  paper's page and scrolls/flashes its card into view — but only when it matches the currently active filter; a
  non-match is a silent no-op, never a filter override. `list_papers`'s filter-building was extracted into a
  shared `_paper_filter_clauses` helper (reused by the new rank query) and the whole listing/filter/sort/rank
  cluster moved from `repository.py` (back at the 600-line cap) into the existing `paper_query_repo.py`.
- **Why:** opening a paper from a citation, the Files list, or an axis panel previously left the Details pane and
  library row highlight showing a stale paper, with no way to find the newly-selected one in a long or filtered
  list — a real navigation gap the user surfaced through iterative use.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-319-NOTES.md` for the full design
  (incl. the v1 scope decision to exclude the two local-only Text-Health/Reference filters from the cross-page
  jump) and `.claude/security-audits/2026-07-21_paper-position.md` for the new endpoint's threat review.

## 2026-07-21 — Increment 318: automatic cadence refresh for the Retraction Watch DB mirror (backlog #31)
- **Files:** `app/frontend/js/{03_library,30e_feed,35_settings}.jsx`, `app/frontend/styles.css`,
  `app/backend/help/help_content.md`, `tests/test_frontend_assembly.py`, `callosum-app.html`,
  `.claude/qa-routes/route_74_retraction_watch.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/CLAUDE.md`,
  `.claude/docs/increment-notes/INCREMENT-318-NOTES.md`.
- **What:** an opt-in, staleness-gated automatic refresh of the Retraction Watch mirror — default-off checkbox
  in Settings → Local Maintenance; when on, fires the same full re-check batch the existing "Retractions ↻"
  library-header button uses, on launch/focus, only once the mirror is >30 days old or never downloaded.
  Follows the same client-driven pull pattern already established for the Literature Feed's own auto-refresh
  (no backend scheduler exists, and none was introduced). Live verification against a QA fixture with no
  contact email configured surfaced a real gap — a mirror that can never become fresh would otherwise re-run the
  batch on every window focus indefinitely — fixed with a 1-hour attempt throttle as a safety net alongside the
  30-day staleness gate. Renamed Feed's `.feed-autorefresh` CSS class to the shared `.auto-refresh-toggle` now
  that a second feature uses the same recipe.
- **Why:** backlog #31's remaining slice — the 30-day staleness nudge (v1) was passive text nobody would act on
  unless they happened to have Settings open; this makes staying current the default behavior for anyone who
  opts in.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-318-NOTES.md` for the full
  design rationale (including the Principles-gate framing for why this is opt-in, not a silent timer) and the
  live Playwright verification of the full trigger/throttle/persistence behavior.

## 2026-07-21 — Increment 317: QA re-triage batch (routes 24/27/30/32)
- **Files:** `app/frontend/js/{19_duplicates,27_scan}.jsx`, `tests/test_frontend_assembly.py`, `callosum-app.html`,
  `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/CLAUDE.md`, `.claude/docs/increment-notes/INCREMENT-317-NOTES.md`.
- **What:** re-verified every Critical/High/Medium/Low finding from the 2026-07-03 QA run (routes 24/27/30/32)
  live against a fresh fixture instead of assuming staleness. Route 30's Critical (500s on PATCH/tag/cite
  endpoints) + its downstream Highs/Mediums were confirmed already fixed (the SQLite write-lock arc, incs
  272–281). Three "console-error budget" Mediums across routes 24/27/30 were confirmed to be Chromium's own
  network-layer logging for intentionally-triggered 4xx/5xx during adversarial checks, not app bugs. Two
  findings were confirmed by-design/already-tracked (route 27's PDF-import scope, its outside-path scan
  tradeoff) and one a QA-fixture limitation (route 32's unreachable exact-precision citation). Found and fixed
  two real, still-open bugs: `DuplicatesModal`'s un-dismiss never re-triggered the duplicate scan (only a full
  modal close/reopen recovered the pair); `ScanModal` lost mid-scan progress visibility across a modal
  close/reopen (the job always completed correctly server-side — no data loss, just no UI feedback).
- **Why:** this item sat in the backlog specifically because several 2026-07-03 findings were suspected to be
  downstream of the (now-closed) write-lock saga — the backlog explicitly asked for re-confirmation before
  treating any of them as fresh, actionable bugs.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-317-NOTES.md` for the full
  finding-by-finding disposition + the live Playwright verification of both fixes.

<!-- HELP-DOCS-SYNCED 2026-07-21 inc 316 — updated the "Editing paper details" section's Files-area description:
clicking a file now opens THAT specific PDF (was generically "the paper's PDF"), with a pointer to Duplicates &
merge for why a paper can have more than one. Nothing above this line has an un-synced corpus change. -->
## 2026-07-21 — Increment 316: per-attachment PDF serving (backlog #5 complete)
- **Files:** `app/backend/api/routers/{paper_files,summaries}.py`, `app/frontend/js/{00_lib,25_detail,
  30_viewer}.jsx`, `app/backend/help/help_content.md`, `tests/{api_helpers,test_papers,test_paper_merge,
  test_summaries}.py`, `callosum-app.html`, `.claude/qa-routes/route_{24_duplicates,32_viewer_annotations}.md`,
  `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/CLAUDE.md`, `.claude/docs/increment-notes/INCREMENT-316-NOTES.md`.
- **What:** `GET /papers/{paper_id}/pdf` gained an optional `?attachment_id=` so a caller can open a *specific*
  attachment instead of always the paper's primary — the case that matters is a merge survivor (#17) left with
  2+ PDFs. The Details pane's "Files" list (which already rendered one button per attachment) now wires each
  click to its own file. Found and fixed a related coordinate-honesty gap in the same pass: a citation's evidence
  always traces to a specific attachment (`chunks.attachment_id`, non-nullable) but that was never surfaced to
  the frontend, so a citation from a *non-primary* attachment always opened the *primary* one — risking an exact
  bbox highlight landing on the wrong document (two PDF renderings of "the same paper" don't share page geometry).
  Fixed by threading `attachment_id` through `SummaryCitationResponse`, gated so it's only ever populated for a
  real PDF attachment (a citation from a non-PDF "supplementary-text" attachment — DOCX/HTML/JATS-XML — still
  degrades to today's honest primary-PDF fallback, not a false "no local PDF" 404).
- **Why:** backlog item #5's remainder — Files always opened the primary PDF regardless of which button was
  clicked; the citation-attachment gap was surfaced by investigating this exact plumbing, not a separate ask.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-316-NOTES.md` for the full
  before/after + the live Playwright verification (a real merge survivor with 2 distinguishable local PDFs,
  each Files button confirmed via the network log to fetch its own attachment).

## 2026-07-21 — Increment 315: METHODS pane regroup — Details / Data / Statistics / Checklists
- **Files:** `app/frontend/js/{05_panes,06_methods_statcheck,07_methods_grim,08d_methods_bayes,
  08f_methods_lmm,08g_methods_metaanalysis,08h_methods_transparency,09_placeholders}.jsx`,
  `app/frontend/styles.css`, `app/backend/help/help_content.md`, `tests/test_frontend_assembly.py`,
  `callosum-app.html`, `.claude/qa-routes/route_{00_smoke_readonly,33_methods_statcheck,37_methods_grim,
  59_methods_bayes,61_methods_lmm,62_methods_metaanalysis,63_methods_transparency,
  70_tool_pane_visual_drift,73_workspaces}.md`, `.claude/DESIGN.md`, `.claude/CLAUDE.md`,
  `.claude/docs/increment-notes/INCREMENT-315-NOTES.md`.
- **What:** collapsed the METHODS accordion from 7 top-level sections to 4: Details (unchanged), Data (renamed
  from "Data consistency (GRIM)"), Statistics (renamed from "Statistics check"), and a new Checklists section
  folding the 4 reporting-completeness auditors (Transparency, Mixed-model, Bayesian, Meta-analysis) into one
  2×2 tab grid. Caught and fixed, before writing code, a real bug the merge would have introduced: each of the
  4 auditors gated its own auto-run on `ctx.methodsOpen === "<own-id>"`, which would permanently read
  `"checklists"` once merged — fixed by extending `PaneAccordion` to thread a real `render(ctx, isVisible)`
  bool (mirroring `WorkspacePane`'s existing contract) instead of each tool re-deriving visibility itself.
  Also caught live via Playwright (not a static read): the new grid CSS was silently overridden by
  `.tags-srcfilter`'s `display:flex` (equal specificity, later in source order) until raised to a compound
  selector.
- **Why:** the user asked for the METHODS panel reorganized this way — Details/Data/Statistics unchanged in
  place, and the 4 reporting checklists grouped as a 2×2 grid rather than 4 separate top-level sections.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-315-NOTES.md` for the full
  before/after + the Playwright verification (desktop 2×2 grid, mobile 1-column collapse, per-tab auto-run).

<!-- HELP-DOCS-SYNCED 2026-07-20 inc 314 — rewrote the "Reviewing findings" + "Checking for retractions" sections
(and the Metadata-access cross-reference) for the retired Review accordion: findings now live in Synthesize →
Critique ("What the checks surfaced" facts + a "Needs your review" candidate queue), and the Retraction Watch
database admin view moved to Settings → Local maintenance. Nothing above this line has an un-synced corpus change. -->
## 2026-07-20 — Increment 314: retire the left-pane "Review" accordion into Synthesize → Critique
- **Files:** `app/frontend/js/08x_methods_critical.jsx`, `35_settings.jsx`, `40_app.jsx` (deleted:
  `08_methods_findings.jsx`), `app/backend/methods/critical_review.py`,
  `app/backend/api/routers/critical_review.py`, `app/frontend/styles.css`, `app/backend/help/help_content.md`,
  `tests/{test_critical_review,test_frontend_assembly}.py`, `callosum-app.html`,
  `.claude/qa-routes/route_67_critical_review.md` (rewritten), `route_39_retraction.md`,
  `route_74_retraction_watch.md`, `route_73_workspaces.md` (deleted: `route_38_findings.md`),
  `.claude/DESIGN.md`, `.claude/CLAUDE.md`,
  `.claude/docs/increment-notes/INCREMENT-314-NOTES.md`.
- **What:** verified (not assumed) that the left-pane "Review" accordion was almost fully redundant with
  Synthesize → Critique before touching anything — its library-wide retraction batch duplicated the Library
  header's own button, and its FACT display was already a subset of Critique's Tier-1 backbone. Moved the one
  real gap (the reviewable CANDIDATE queue — statcheck-flagged issues etc., Confirmed/Accepted/Noted) into
  Critique as a new "Needs your review" block. Caught and fixed a real regression while writing the QA route:
  Critique's generic signal rendering was dropping the retraction fact's clickable notice-URL evidence link —
  fixed with a small, justified backend addition (`notice_url` threaded through `_stored_method_signals`) rather
  than accepted as a silent loss. Relocated the Retraction Watch DB admin panel to Settings → Local maintenance
  (no equivalent existed elsewhere). Deleted the accordion file, its dead-only CSS, and the QA route that
  described it (folded into route 67); updated DESIGN.md's navigation map and the help corpus.
- **Why:** the user asked whether Review could move into Critique and go away entirely; the honest answer needed
  verification, not a guess, and surfaced one real functional gap (the candidate queue) and one real regression
  risk (the notice link) that a same-day retirement would otherwise have shipped broken.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-314-NOTES.md` for the full
  before/after + the Playwright verification against the real testing DB (a real retracted paper's notice link,
  a real statcheck candidate's review-and-persist round-trip).

<!-- HELP-DOCS-SYNCED 2026-07-20 inc 313 — rewrote every stale "Extract"/"Work → Cite → …"/"CRediT statement"
reference across the corpus (menu bar description, mobile Workspace dropdown, meta-analysis auditor location,
effect-size converter location, the extraction-workspace section header, citation-concentration/how-it's-cited/
meta-reference-list locations, the CRediT tab name, the citation-suggestion tab name) to match the Work/Extract
reorg + the Meta-Analysis→METHODS move below. Nothing above this line has an un-synced corpus change. -->
## 2026-07-20 — Increment 313: the Work/Extract reorg, Meta-Analysis returns to METHODS, sub-tab-bar CSS fixes
- **Files:** `app/frontend/js/04b_workspaces.jsx`, `37_cite.jsx`, `37b_meta_reference.jsx` (new),
  `08j_reference_integrity.jsx`, `08b_methods_citation_equity.jsx`, `08c_methods_citation_context.jsx`,
  `38_credit.jsx`, `45_workbench.jsx`, `08i_methods_effectsize.jsx`, `08g_methods_metaanalysis.jsx`,
  `30c_frame.jsx`, `40_app.jsx`, `35_settings.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`,
  `tests/test_frontend_assembly.py`, `callosum-app.html`, `.claude/qa-routes/route_{00,42,51,53,62,65,66,68,73}_*.md`,
  `.claude/docs/increment-notes/INCREMENT-313-NOTES.md`, `.claude/CLAUDE.md`.
- **What:** folded the "Extract" workspace into "Work" (now Cite / Meta-Reference / CRediT / Meta-Analyze — Cite
  drops its inner nested-tab strip, Meta-Reference stacks 3 previously-nested tools as subsections, CRediT is
  renamed, Meta-Analyze is the relocated Workbench with Effect-Size folded in as a subsection). Fixed 2 real
  navigation regressions the sweep caught (a stale `selectWorkspace("extract")` in the Workbench capture round-trip,
  and the ref-signal-badge handler still targeting the deleted nested-Cite-tab system) plus a stray "Extract" in a
  banner string. Mid-session, moved the Meta-Analysis reporting auditor (left intentionally staged/unregistered by
  the reorg) into the METHODS accordion alongside its statcheck/GRIM/Bayes/LMM/transparency siblings, closing out
  the follow-up the user asked to finish in the same session rather than leave for later. Fixed the sub-tab-bar CSS
  (workspace buttons vertically centered + uniform height; the Discover selected-paper/open-PDF cue keeps Library's
  exact flush-bottom tab treatment; a fixed 40px bar height everywhere) after a multi-round diagnosis. Also this
  session: fixed `AccountSettings` copy to clarify ORCID is required, and made the Help modal's TOC sidebar
  independently scrollable. Brought the help corpus's Work/Extract references fully current (see the sync marker
  above).
- **Why:** two workspaces had drifted into an unclear split, with citation-integrity tools buried three levels deep
  as nested tabs-within-a-tab; the user wanted one coherent "producing science" workspace and asked to finish the
  Meta-Analysis relocation in the same pass once its absence surfaced mid-verification.
- **Revert:** `git log` this commit; see `.claude/docs/increment-notes/INCREMENT-313-NOTES.md` for the full
  before/after structure and the Playwright verification script.

## 2026-07-20 — Settings workspace visual hierarchy
- **Files:** `app/frontend/js/03_library.jsx`, `app/frontend/js/04_layout.jsx`, `app/frontend/js/35_settings.jsx`,
  `app/frontend/js/35a_mypubs.jsx`, `app/frontend/js/35b_providers.jsx`, `app/frontend/js/35c_sync.jsx`,
  `app/frontend/js/40_app.jsx`, `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, `callosum-app.html`,
  `.claude/DESIGN.md`.
- **What:** replaced the flat Settings scroll with four canonical panel/card groups (Account & sync, AI features,
  Library behavior, Integrations), using unframed responsive subsection grids inside related groups. My Publications
  now fills the account column, followed by Metadata access; Cross-device sync sits above Appearance in the opposite
  column; and AI agent access sits inside AI features.
  The four built-in AI providers are always open in an equal-size 2×2 desktop grid and a natural-height mobile stack.
  The AI egress, help-assistant, and agent-access controls share one three-column desktop row; the ORCID input and
  its Save/Refresh actions share one line; and the signed-in identity sits opposite Sign out on one account row.
  Published-name variants use an add field plus wrapping removable tag chips; add/remove persists immediately.
  Removed the stale "More settings will live here" placeholder, normalized the sync-step field hierarchy, and paired
  the provider verification note with a right-aligned Add provider action. Custom provider cards continue in
  natural-height two-column rows below the fixed 2×2 built-ins. Enable sync now precedes the unnumbered Sync server
  URL field. Removed the misleading watched-folder auto-scan preference: launch/focus rescans are now part of the
  standard library behavior, still protected by the existing read-only, health, in-flight, and throttle guards.
  The two remaining Axes defaults share one full-width row. The OpenURL lineage citation now uses the same DOI-aware
  add/check/completed-state control as method citations elsewhere in Callosum. Library access precedes Local
  maintenance on one row, while Discover: Journals spans the card with its weighting and breadth controls in columns.
  Metadata access moved below the ORCID form with concise Retraction Watch copy; the redundant sync introduction was
  removed; the two Axes setting names now use the same section-heading treatment as Library access and Local
  maintenance; account sign-in copy now uses "(Optional.)"; and the Google Docs integration heading now reads
  "Google Docs (Remote access)." Provider descriptions now use the full card width, active-provider model and test
  controls share one row (including custom providers), every provider shows its actual destination endpoint, and the
  synthesis-cache repair action sits opposite its label. AI permission names now use the feature-eyebrow treatment;
  journal preference controls share a baseline; Sync fields use consistent spacing; and the OpenURL label/input/save
  share one row. Integration columns now place full-width actions directly under their headings, keep download links
  inline in the explanatory text, and align the Google Docs label/toggle using the standard field-label recipe in a
  row matching the other integration actions' height.
- **Why:** make the mature settings surface scannable, use the full center workspace, present the provider roster as
  one deliberate set, and avoid controls whose apparent behavior diverges from the application's actual behavior.
- **Revert:** restore `.claude/backups/20260720_settings_redesign_pre.zip`, then rebuild the frontend.

## 2026-07-20 — Increment 312: the account platform goes live (Authentik + sync_server on juno) + three real bugs fixed
- **Files:** `app/backend/api/auth/oidc.py`, `sync_server/auth.py`, `app/backend/sync/transport.py`,
  `app/backend/sync/engine.py`, `app/backend/api/routers/sync.py`, `tests/test_sync_endpoints.py`
- **What:** Stood up Authentik + sync_server on the maintainer's own Debian box (juno), exposed via a Cloudflare
  Tunnel — no hosting cost. Getting a real ORCID sign-in + a real sync run working surfaced and fixed three bugs:
  (1) zero-leeway JWT timestamp checks too strict for any cross-machine deployment (`leeway=60` added in both
  `oidc.py` and `sync_server/auth.py`); (2) `sync_server`'s `JwksVerifier` compared a slash-stripped issuer against
  the JWT's real (trailing-slash) `iss` claim, failing every check; (3) `/sync/run` never refreshed a stale access
  token via the stored `refresh_token`, so any sync more than a few minutes after sign-in failed. Also: chunked
  `run_sync`'s push into batches of 500 (a first-ever sync can easily exceed a server's per-push cap), and
  `transport.py` now surfaces the actual response body on a non-200 instead of just the status code.
- **Why:** backlog #15's last open item was making Authentik/sync_server actually reachable; the bugs above would
  have silently blocked every real user of "Sign in with ORCID" or cross-device sync, not just this deployment.
- **Revert:** `git log` this commit; the juno-side infra (docker-compose, cloudflared config, systemd units) has no
  git history — see `.claude/docs/increment-notes/INCREMENT-312-NOTES.md` for the full setup.

<!-- HELP-DOCS-SYNCED 2026-07-20 inc 311 — added "Cross-device sync" (setup steps, what syncs/doesn't, conflict
review) and corrected the now-stale "sync doesn't exist yet" note under Account. Nothing above this line has an
un-synced corpus change. -->
## 2026-07-20 — Increment 311: Sync UI (SP3c) Increment B — the Settings → Sync UI + conflict review (frontend)
- **Files:** `app/frontend/js/35c_sync.jsx` (new), `app/frontend/js/35_settings.jsx`, `callosum-app.html`,
  `app/backend/api/routers/sync.py`, `tests/{test_sync_endpoints,test_frontend_assembly}.py`,
  `app/backend/help/help_content.md`, `.claude/qa-routes/route_46_sync.md`,
  `.claude/security-audits/2026-06-29_sync-server.md` (addendum),
  `.claude/docs/increment-notes/INCREMENT-311-NOTES.md`.
- **What:** built the frontend half of the approved Sync UI plan — a new `SyncSettings` section (split into its
  own chunk; `35_settings.jsx` was already at the 600-line cap) covering setup (passphrase + confirm, a one-time
  recovery-code reveal), a sequential enable gate (setup → sign-in → server URL → enable, matching the backend's
  own gate order), "Run sync now" (re-entering the passphrase every time, no session-remember), and a
  conflict-review panel (a collapsible card per conflict, a generic field-diff table reusing the `cr-matrix`
  recipe, Keep-mine/Keep-theirs actions). Manually browser-verified the whole flow with Playwright against an
  isolated scratch instance (`CALLOSUM_SETTINGS_PATH` + `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`, so
  the check never touched a real stored keyring/passphrase) — which surfaced two real backend bugs, fixed in the
  same increment: (1) `/sync/run`'s wrong-passphrase case used **401**, which the frontend's `api*` helpers treat
  as "the remote-access bearer token is invalid," firing the unrelated app-wide lockout-recovery overlay — changed
  to **422**, matching `sync_setup`'s own equivalent handling; (2) an unhandled `sqlite3.OperationalError` ("database
  is locked," e.g. colliding with a concurrent watched-folder rescan) surfaced as a raw 500 — now a clean **503**
  ("try again"), deliberately not auto-retried (retrying a mixed local+egress run risks a duplicate push).
- **Why:** the first real UI caller of `/sync/run` is what exposed both bugs — they were latent since inc 202 but
  invisible with no frontend exercising the endpoint.
- **Verify:** `test_sync_endpoints.py` 12 passed (2 status-code assertions updated); `test_frontend_assembly.py` 36
  passed (+1 new); full suite `pytest -n auto -q` unchanged-count baseline + these; `ruff check`/`ruff format --check`/
  line-budget clean; QA surface map 250/250 API + 1188/1188 FE, 0 uncovered (route_46 extended with FE steps 9-13).
- **Revert:** `git checkout main -- app/frontend/js/35_settings.jsx app/backend/api/routers/sync.py tests/test_sync_endpoints.py tests/test_frontend_assembly.py app/backend/help/help_content.md` + `rm app/frontend/js/35c_sync.jsx` + `python tools/build_frontend.py`.

## 2026-07-19 — Increment 310: Sync UI (SP3c) Increment A — list + resolve conflicts (backend)
- **Files:** `app/backend/sync/engine.py`, `app/backend/persistence/sync_conflicts_repo.py` (new),
  `app/backend/api/routers/sync.py`, `tests/test_sync_endpoints.py`, `.claude/qa-routes/route_46_sync.md`,
  `.claude/security-audits/2026-07-19_sync-conflict-resolution.md`,
  `.claude/docs/increment-notes/INCREMENT-310-NOTES.md`.
- **What:** planned + built Increment A of the approved Sync UI (SP3c) plan — the backend gap a UI needs before it
  can be built: `GET /sync/conflicts` (list unresolved rows, paired with the live domain value for a diff) and
  `POST /sync/conflicts/{id}/resolve {side: "mine"|"theirs"}`. "Mine" reuses the exact remote-apply write path
  (`_apply_record`/`_apply_link`) rather than a new ad-hoc writer, and deliberately doesn't touch `sync_state` —
  the next ordinary sync run's hash-diff naturally picks up and pushes the restored value. The resolve endpoint's
  request body can only choose between two already-server-held values, never supply data to write.
- **Why:** backlog #15's last open slice (Settings → Sync UI + conflict review) turned out to need backend work
  first — `sync_conflicts` was written by the engine but nothing read or resolved it. Planned with 3 parallel
  research passes (API surface, Settings UI conventions, the full 194–202 increment/spec history) before building.
- **Verify:** `tests/test_sync_endpoints.py` 13 passed (7 existing + 5 new); full suite `pytest -n auto -q` 1288
  passed, 1 skipped (was 1283); `ruff check` + `ruff format --check` + line-budget clean; QA surface map 250/250
  API, 0 uncovered. Caught and fixed a real gate along the way: the first draft used a raw `conn.commit()`, which
  inc 281's `test_short_write_sweep.py` correctly flagged — converted to `run_write` (see increment notes).
- **Revert:** `git checkout main -- app/backend/sync/engine.py app/backend/api/routers/sync.py tests/test_sync_endpoints.py` + `rm app/backend/persistence/sync_conflicts_repo.py`.

## 2026-07-19 — Increment 309: backlog §1 close-out (mobile CSS batch, real PDF-404 fix, route_00 rewrite, httpx2)
- **Files:** `app/frontend/js/{30_viewer,30c_frame,40_app}.jsx`, `app/frontend/styles.css`, `callosum-app.html`,
  `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_00_smoke_readonly.md`, `requirements-dev.txt`,
  `pyproject.toml`, `.claude/security-audits/2026-07-19_httpx2-testclient-migration.md`,
  `.claude/docs/increment-notes/INCREMENT-309-NOTES.md`.
- **What:** cleared the reorganized backlog's entire §1 "Near-term" batch in one Playwright-equipped session.
  (1) Fixed all 4 mobile-CSS QA findings (Feed filter-button wrapping, the whatsnew notice's height, Settings
  provider-badge/Use collision, Work's edge-hugging provenance line) — each reproduced and re-verified visually
  before/after, not guessed from source. (2) Actually **fixed** the metadata-only-paper PDF 404 (previously just
  documented as an "expected" console error): `openPdf` now threads the library card's already-known
  `attachment_count` through to `PdfViewer`, which skips the doomed fetch entirely instead of relying on a 404
  to fall back gracefully. (3) Rewrote `route_00_smoke_readonly.md` steps 4–5 to the actual current pane
  structure (confirmed live, not assumed) and fixed its now-inverted "404 is expected" pass criteria. (4) Migrated
  the `httpx→httpx2` TestClient deprecation — turned out to need zero source changes (starlette auto-prefers
  `httpx2` once installed) but surfaced that this dev environment's fastapi/starlette were never actually
  upgraded per inc 305's pin bump, so synced that too.
- **Why:** the user asked to "blow through" the backlog's near-term items now that Playwright made them
  genuinely checkable, rather than leaving them as filed-but-unverified findings.
- **Verify:** `test_frontend_assembly.py` 35 passed (+1 new regression guard); full suite `pytest -n auto -q`
  1283 passed, 1 skipped (unchanged count); `ruff check .` + `ruff format --check .` + `check_line_budget.py`
  clean. Manually re-verified every fix in a real browser (see `INCREMENT-309-NOTES.md`).
- **Revert:** `git checkout main -- app/frontend/js/{30_viewer,30c_frame,40_app}.jsx app/frontend/styles.css tests/test_frontend_assembly.py requirements-dev.txt pyproject.toml` + `python tools/build_frontend.py`.

## 2026-07-19 — INCREMENT-BACKLOG.md: full audit + reorg (autonomous/Cliff cut retired)
- **Files:** `.claude/docs/INCREMENT-BACKLOG.md`.
- **What:** at Cliff's request, dropped the legacy "autonomous vs ⛔ NEEDS CLIFF" cut-line organization (935→343
  lines) in favor of grouping by what an item actually is (near-term / needs-a-decision / gated / future-track),
  keeping the same why-it-needs-a-human labels. Before rewriting, audited every open item against all 308
  increment-notes titles (not just this file's own claims) and found real drift: **#12** (critical-review,
  single- *and* multi-paper) was listed as gated/unbuilt but shipped inc 266 + inc 271; **B1 SP2** (gated MCP
  agent writes) was called "the one genuinely-new architectural item" still to build but shipped inc 216; the
  **workspaces-nav "what moved" hint** was listed open but shipped inc 285; **#5**'s multi-URL field had shipped
  inc 214 (only per-attachment PDF serving remained); the ~60-line SQLite `database is locked` saga was already
  fully closed (inc 272–281) but read as open due to its own verbose history; and the entire Competitive-benchmark
  A1–A10 + B1–B5 list is now closed. Verified directly (not just by doc claims) that `SECURITY.md`/`CITATION.cff`/
  `.env.example`/`uv.lock`/`.pre-commit-config.yaml` don't exist, confirming #20 stays genuinely open.
- **Why:** the doc had drifted — some items marked "still needs building" had already shipped, which risks
  wasted re-planning or a wrong answer to "what's left." Cliff asked for a review that "reflects exactly what's
  left," not a reformat.
- **Verify:** manual read-through; numbering kept stable (cross-referenced from CLAUDE.md/session handoffs/
  increment-notes) — nothing renumbered, only regrouped or moved to the Shipped breadcrumbs with its number kept.
- **Revert:** `git checkout main -- .claude/docs/INCREMENT-BACKLOG.md`.

<!-- HELP-DOCS-SYNCED 2026-07-19 — corpus current through inc 308 (incl. its Playwright follow-up fix below); behavior/CSS only, no new user-facing feature — no help change. -->
## 2026-07-19 — Increment 308 follow-up: Playwright browser-verification + Discover Clear × real fix
- **Files:** `app/frontend/js/30d_discover.jsx`, `callosum-app.html`, `.claude/docs/increment-notes/INCREMENT-308-NOTES.md`.
- **What:** installed a session-local Playwright MCP server and browser-verified all 4 of inc 308's manual-verification
  steps directly (bypassing the Codex QA loop). Read-only credit gating, read-write credit affordance, and mobile
  Help all passed as shipped. Discover `Clear ×` **did not actually work** as inc 308 claimed: clicking it was
  immediately undone by an unrelated existing effect (inc 301's "resume last search when idle+empty") that shares
  the exact state shape `clearActiveSearch` produces, so every Clear click silently re-ran the just-cleared search
  (confirmed via the network log — a fresh `/discovery/search` + `/discovery/relevance` pair fired right after each
  click). Fixed by having that resume effect track a `wasActiveRef` and only fire on a genuine tab (re)entry
  (`active` false→true), not on every idle+empty state change while already active.
- **Why:** the session handoff flagged inc 308's frontend fixes as visually unverified; direct browser verification
  is more reliable and faster here than a Codex QA re-run for a small, already-scoped set of checks.
- **Verify:** `test_frontend_assembly` 34 passed (unchanged); manually re-verified in-browser: Clear × now stays
  cleared with no repopulation, and switching away from and back to Discover → Search still correctly resumes the
  last search (the original inc-301 behavior is intact). No backend change → full count unchanged (1283).
- **Revert:** `git checkout main -- app/frontend/js/30d_discover.jsx` + `python tools/build_frontend.py`.

## 2026-07-19 — Increment 308: QA-pass fixes (Codex 2026-07-19) — read-only credit + mobile Help + Clear ×
- **Files:** `app/frontend/js/{00_lib,05_method_credit,38_credit,40_app,30d_discover}.jsx`, `app/frontend/styles.css`, `callosum-app.html`, `tests/test_frontend_assembly.py`, `.claude/docs/{increment-notes/INCREMENT-308-NOTES.md,INCREMENT-BACKLOG.md}`, `.claude/CLAUDE.md`, `.claude/changes.md`.
- **What:** fixed the 3 highest-confidence Medium QA findings. (1) **Read-only credit 403s:** new app-wide tri-state `AppReadOnly` context; `MethodCreditButton` + `CreditSection` fire `/library/credit/status` + `/credit/statement` only when `readOnly === false` (a read-only companion no longer issues doomed write-method POSTs). (2) **Mobile Help** collapses the 2-column grid to 1 column at phone width. (3) **Discover `Clear ×`** gains a fetch-generation guard so it cancels an in-flight/stuck search and a late response can't repopulate.
- **Why:** QA-POLICY triage — real UX/console-error findings from the Codex pass. Filed the remaining subjective mobile-CSS + an ambiguous PDF-404 for a browser pass.
- **Verify:** ⚠️ **frontend changes NOT browser-verified this session (no Playwright)** — they build clean + `test_frontend_assembly` **34 passed**; logic reviewed; flagged for the next Codex QA re-run. No backend change → full count unchanged (1283). ruff clean.
- **Revert:** `git checkout main -- app/frontend/js/{00_lib,05_method_credit,38_credit,40_app,30d_discover}.jsx app/frontend/styles.css tests/test_frontend_assembly.py` + `python tools/build_frontend.py`.

## 2026-07-19 — QA inbox triage (Codex pass) — no increment (housekeeping + filing)
- **Files:** `.claude/qa-routes/{route_00_smoke_readonly.md,route_74_retraction_watch.md (renamed from route_40_retraction_watch.md)}`, `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/qa-inbox/_processed/*` (4 runs moved in), `.claude/changes.md`.
- **What:** triaged a Codex QA + manual-visual pass (routes 00/70/73 + Playwright). **No Critical/High.** Verified 4 Medium + 4 Low against the code — all frontend/visual — and **filed them** to `INCREMENT-BACKLOG.md` ("QA 2026-07-19" batch) for a browser-equipped fix pass (I don't ship blind UI changes without Playwright). Fixed the dev-hygiene in-session: deleted an orphan `route_38_findings.md.tmp…`; resolved the route_40 filename-number collision (retraction_watch → route_74); corrected the Wanted-in-header stale bit + flagged the pre-inc-280 accordion steps in `route_00`; moved all 4 runs to `_processed/`.
- **Why:** QA-POLICY triage loop (fix Critical/High, file Medium/Low, process the inbox). The findings are real UX polish (read-only credit 403s, mobile CSS, a metadata-only-paper PDF 404) but need a browser to fix + verify.
- **Verify:** `build_surface_map check` → 248/1157, 0 uncovered (route edits didn't break coverage); inbox empty bar `_processed`. No app code changed → no pytest/rebuild.
- **Revert:** restore the listed docs from git; `git mv` route_74 back to route_40 if desired.

## 2026-07-19 — Increment 307: keyword tags everywhere (Feed/Search-save + 🔎 re-resolve)
- **Files:** `app/backend/metadata/{enrichment.py,__init__.py}`, `app/backend/api/routers/{paper_enrich.py,discovery.py}`, `app/backend/discovery/search.py`, `app/frontend/js/{30d_discover,30e_feed}.jsx`, `callosum-app.html`, `tests/{test_discovery,test_metadata_multi_enrich,test_papers}.py`, `.claude/{security-audits/2026-07-19_keyword-tags-everywhere.md,qa-routes/route_43_discovery.md,qa-routes/route_48_metadata_enrich.md,docs/increment-notes/INCREMENT-307-NOTES.md,docs/INCREMENT-BACKLOG.md,CLAUDE.md,changes.md}`.
- **What:** extracted the inc-306 keyword loop → reusable `import_registry_keyword_tags`, and wired it into the two paths that skipped enrichment: **🔎 re-resolve** now imports OpenAlex/PubMed keywords (not just Crossref subjects), and **Feed/Search save** now runs the multi-pass enrich in a **FastAPI background task** so a saved paper arrives with keyword tags + gap-fills (save returns instantly). `SaveRequest`/`save_item` gain a digit-validated `pmid` (drives MeSH); both frontend save payloads send it.
- **Why:** make keyword-tag population consistent across every ingest/refresh path, "as part of the enrichment process." (Also diagnosed the user's "no tags" report as a stale-server issue — inc 306's extraction verified correct against live OpenAlex.)
- **Verify:** security audit **PASS**; 3 new tests + updated save-route hermeticity green; full `pytest -n auto` **<PENDING — CI authoritative>**; ruff check+format + line-budget clean; QA surface map **248/1157, 0 uncovered**. Hermetic by construction (registry-gated; bg task rides `app.state.enrich_registry`). Provenance note: bg enrich relabels a saved paper `discovery-import → crossref` (accepted). Needs a **server restart** to take effect.
- **Revert:** `git checkout main -- app/backend/metadata/enrichment.py app/backend/metadata/__init__.py app/backend/api/routers/paper_enrich.py app/backend/api/routers/discovery.py app/backend/discovery/search.py app/frontend/js/30d_discover.jsx app/frontend/js/30e_feed.jsx` + `python tools/build_frontend.py`.

## 2026-07-19 — Increment 306: richer keyword tags (OpenAlex topics + PubMed MeSH → keyword:*)
- **Files:** `integrations/openalex/{work_keywords.py (new),adapter.py}`, `app/backend/discovery/pubmed_provider.py`, `app/backend/metadata/{enrich_sources.py,enrichment.py}`, `tests/{test_openalex_work_keywords.py (new),test_pubmed_provider.py,test_metadata_multi_enrich.py}`, `.claude/{security-audits/2026-07-19_richer-keyword-tags.md,qa-routes/route_20_tags.md,docs/increment-notes/INCREMENT-306-NOTES.md,docs/INCREMENT-BACKLOG.md,CLAUDE.md,changes.md}`.
- **What:** the multi-pass metadata enrich now imports OpenAlex curated **topics** (`keyword:openalex`) + PubMed **MeSH** (`keyword:pubmed`) as additive/deletable/suppressible tags, joining `keyword:crossref`. Driven off the enrich **registry** (a source advertising `keyword_source` + `keywords()` contributes tags) → hermetic by construction. Backend-only — the frontend `tagSourceLabel` already renders both provenances.
- **Why:** richer, source-labeled library facets (backlog "richer keyword tags"). Facts from a named index (not AI guesses); OpenAlex scores filter noise server-side but are never surfaced (no opaque score).
- **Verify:** security audit **PASS**; new+existing tags/enrich tests green (16 delta tests + a prior full **1279-green** `-n auto` run pre-refinement; the isolated `_parse_mesh` refinement verified separately — expected total **1280/1**; local harness killed the consolidated run 3× on resource pressure, so **CI is the authoritative full-suite gate**); ruff check+format + line-budget clean (note: `adapter.py` now 599/600 — split before its next edit); QA surface map **248/1157, 0 uncovered**. OpenAlex = zero extra egress (cached work); PubMed = one bounded efetch/biomedical paper.
- **Revert:** `git checkout main -- integrations/openalex/adapter.py app/backend/discovery/pubmed_provider.py app/backend/metadata/enrich_sources.py app/backend/metadata/enrichment.py` + delete `integrations/openalex/work_keywords.py`.

## 2026-07-19 — Increment 305: web-stack CVE migration (FastAPI 0.115→0.139, Starlette 0.45→1.3.1)
- **Files:** `requirements.txt`, `tests/test_health.py`, `app/backend/api/routers/my_publications.py`, `.claude/security-audits/2026-07-19_web-stack-cve-migration.md`, `.claude/docs/increment-notes/INCREMENT-305-NOTES.md`, `.claude/{CLAUDE.md,changes.md}`.
- **What:** bumped the pinned web stack (`fastapi==0.139.2`, `starlette==1.3.1`) to clear all **14 open Dependabot advisories** (6 high / 6 moderate / 2 low), every one on starlette (a high covers `>=0.4.1,<1.3.1`, so 1.3.1 is the floor; fastapi 0.115 caps starlette `<0.46`, so both move together). Two code changes: (1) fastapi 0.139 defers `include_router` behind a lazy `_IncludedRouter`, so the mutation-surface lockdown test grew a recursive `_iter_api_routes` walker (descends `original_router.routes`) — the write-route allowlist is unchanged, proving the bump added no mutation surface; (2) `my_publications.py` renamed the deprecated `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT` (same value 422).
- **Why:** the starlette CVEs aren't exploitable in the current localhost-only single-user shape, but the project enforces the web-stack discipline now rather than retrofitting before a public deployment.
- **Verify:** security audit **PASS** (`2026-07-19_web-stack-cve-migration.md`); `pytest tests/test_health.py` 6 passed; full `pytest -n auto -q` **1265 passed / 1 skipped**; ruff check + format + line-budget clean; QA surface map **248 API / 1157 FE, 0 uncovered**. New transitive dep `annotated-doc 0.0.4` (fastapi 0.139). Non-blocking follow-up: TestClient httpx→httpx2 deprecation (dev-only).
- **Revert:** `git checkout main -- requirements.txt tests/test_health.py` then `pip install -r requirements-dev.txt` to restore fastapi 0.115.8 + starlette 0.45.3.

## 2026-07-18 — Increment 304: per-item titles in import/embed progress labels (backlog #4)
- **Files:** `app/backend/persistence/{paper_query_repo,repository}.py`, `app/backend/api/routers/library.py`, `tests/test_papers.py`, `.claude/docs/increment-notes/INCREMENT-304-NOTES.md`.
- **What:** the two long import jobs' determinate progress bar now reads **"Embedding <paper title> — k / N"** instead of the static "Embedding papers". New read helper `titles_for_ids(conn, paper_ids)` (leaf `paper_query_repo.py`, re-exported from `repository`) is fetched **once per job** and both embed loops read the per-item title from it.
- **Why:** backlog #4 — a user importing many PDFs had no idea which paper was in flight; the title closes that legibility gap. Backend-only (rides the inc-142 `ProgressBar` + `/jobs/{id}` poll); no frontend rebuild.
- **Verify:** `pytest tests/test_papers.py::test_titles_for_ids` + `tests/test_citation_import.py` green; full `pytest -n auto -q` **1265 passed / 1 skipped** (9m35s); ruff check + format + line-budget clean; no QA surface change (existing `progress.label` field, content-only).
- **Revert:** restore the four listed files from git. No frontend rebuild required.

## 2026-07-18 — Increment 303: Navigation rubric rewrite + backlog reconciliation
- **Files:** `.claude/DESIGN.md`, `.claude/docs/{INCREMENT-BACKLOG.md,INCREMENT-BACKLOG-DONE.md,increment-notes/INCREMENT-303-NOTES.md}`, `.claude/{CLAUDE.md,CODEX-HANDOFF.md,changes.md}`.
- **What:** rewrote `DESIGN.md §5` into the canonical mode-vs-lens placement rule: center workspaces are broad modes of work; side panes are selected-paper lenses; THEORY/METHODS remain internal pane ids, not a product taxonomy. Reconciled stale open backlog bullets by marking A8 closed-as-covered (inc 205) and A5 color tags done (inc 207).
- **Why:** the inc-280 workspace migration and inc-302 mobile follow-up were shipped, but the design guide and open backlog still carried transitional language that could steer future tools back into the side accordions.
- **Verify:** docs-only; no frontend rebuild required; ruff + format + line-budget gates clean; QA surface map **248 API / 1157 FE, 0 uncovered**; full suite **1264 passed / 1 skipped**.
- **Revert:** restore the listed docs from git. No frontend rebuild required.

## 2026-07-18 — Increment 302: Mobile workspace switcher
- **Files:** `app/frontend/js/{04b_workspaces,40_app}.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/{DESIGN.md,qa-routes/route_00_smoke_readonly.md,qa-routes/route_73_workspaces.md,security-audits/2026-07-18_mobile-workspace-switcher.md}`, `.claude/docs/{INCREMENT-BACKLOG.md,INCREMENT-BACKLOG-DONE.md,increment-notes/INCREMENT-302-NOTES.md}`, `tests/{test_frontend_assembly.py,e2e/test_smoke.py}`, `callosum-app.html`.
- **What:** at phone width, the center workspace menu now renders as a compact **Workspace** dropdown grouped into Workspaces and Utilities, while the bottom mobile nav remains the region switcher (**Library / Panels / Details**). Desktop keeps the horizontal menu bar.
- **Why:** the inc-280 workspace menu was reachable on phones but still behaved like a desktop tab strip. The compact switcher makes moved workspaces reachable without side-scrolling or confusing them with the bottom region nav.
- **Verify:** frontend rebuilt; focused `tests/test_frontend_assembly.py tests/test_help.py` **48 passed**; opt-in browser smoke `CALLOSUM_RUN_E2E=1 pytest tests/e2e/test_smoke.py -q` **3 passed**; QA surface map **248 API / 1157 FE, 0 uncovered**; full suite **1264 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 301: six misc UX fixes (Trash search · read-mode menu bar · Discover recall · duplicate card · invert sort · Missing-PDF filter)
- **Files:** `app/frontend/js/{40_app,03_library,10_pdf_layer,30d_discover,19_duplicates}.jsx`, `app/frontend/styles.css`, `app/backend/api/routers/papers.py`, `app/backend/persistence/{repository,paper_query_repo}.py` (new leaf), `app/backend/help/help_content.md`, `tests/{test_papers,test_frontend_assembly}.py`, `callosum-app.html`, increment notes.
- **What:** (1) Trash gets the read/priority/Missing-PDF filters (un-gated `!trashView`; backend already applied them); (2) the menu bar hides in read mode; (3) Discover → Search reloads your last search on access; (4) merging a duplicate removes its card; (5) a **▲/▼** sort direction toggle (fields dropdown, mapped to the existing backend sort keys — no backend change); (6) a **◫ Missing PDF** filter — new `GET /papers?missing_pdf=` (NOT EXISTS a local PDF, mirrors Text-Health no_local_pdf). `repository.py` was at the 600-cap, so two leaf helpers moved to `paper_query_repo.py` (re-exported).
- **Why:** small quality-of-life gaps in daily library work; none touches an honesty invariant (search/sort/filter/view-state; "Missing PDF" is a factual attribute, not a judgment).
- **Verify:** `tests/test_papers.py` +2 (missing_pdf filter + trash priority filter), `tests/test_frontend_assembly.py` +1 (all six UI features); QA surface **248 API / 1155 FE, 0 uncovered**; frontend rebuilt; ruff (both) + line-budget clean; full `pytest -n auto` green (count below). **User step:** restart the backend to serve `?missing_pdf=`.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 300: Fast pytest — targeted dev runs + xdist parallelism + testmon
- **Files:** `requirements-dev.txt`, `.github/workflows/ci.yml`, `.gitignore`, `.claude/CLAUDE.md`, increment notes. (No application code.)
- **What:** added `pytest-xdist` (parallel `pytest -n auto`, ~3-4× faster) + `pytest-testmon` (`pytest --testmon` runs only tests whose covered code changed). CI's offline suite → `pytest -n auto -q`. CLAUDE.md Verification protocol now prescribes **targeted dev runs** (`pytest tests/test_<area>.py`) as the default, with the full parallel run only before merge (or lean on CI).
- **Why:** the full serial suite is ~45 min; running everything for a localized change was wasted wall-clock. Tests are hermetic (per-test `tmp_path` DB + isolated settings), so parallelism is safe and coverage is unchanged.
- **Verify:** `pytest -n auto -q` matches the serial count (1261 passed / 1 skipped) with no new failures; targeted single-file runs finish in seconds; ruff + line-budget clean. **User step:** `pip install -r requirements-dev.txt` to get the new plugins.
- **Revert:** restore the listed files from git; `pip uninstall pytest-xdist pytest-testmon`.

## 2026-07-18 — Increment 299: Discover Search/Journals recent-query recall
- **Files:** `app/frontend/js/{30d_discover,08e_methods_publishers}.jsx`, `app/backend/help/help_content.md`, `.claude/{DESIGN.md,qa-routes/route_43_discovery.md,qa-routes/route_60_publishers.md,qa-routes/route_73_workspaces.md}`, `tests/test_frontend_assembly.py`, `callosum-app.html`, increment notes.
- **What:** added browser-local recent-query history for **Discover → Search** and **Discover → Journals**. Recall re-runs stored inputs for fresh results; Search stores query+source and Journals stores selected-paper or pasted abstract+subject run shapes. Search also gains **Clear ×** for the active query/results and both surfaces gain **Clear history** for their local recall list.
- **Why:** repeated discovery work should be easy to resume without treating prior result snapshots as current evidence. Re-running preserves the existing complete-list and signal-not-verdict contracts.
- **Verify:** frontend rebuilt; focused `tests/test_discovery.py tests/test_publishers.py tests/test_frontend_assembly.py tests/test_help.py` **80 passed**; QA surface map **248 API / 1151 FE, 0 uncovered**; full suite **1261 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 298: Synthesize Ask/Critique split
- **Files:** `app/frontend/js/{03_library,04b_workspaces,08x_methods_critical,08y_critical_set,20_synthesis,30c_frame,40_app}.jsx`, `app/backend/help/help_content.md`, `.claude/{DESIGN.md,qa-routes/route_55_synthesis_verification.md,qa-routes/route_67_critical_review.md,qa-routes/route_71_critical_review_set.md,qa-routes/route_73_workspaces.md}`, `tests/test_frontend_assembly.py`, `callosum-app.html`, increment notes.
- **What:** renamed the center workspace label to **Synthesize**, split it into **Ask** and **Critique**, moved single-paper Critical Read out of METHODS into **Synthesize → Critique**, and made selection summarize request **Ask**.
- **Why:** synthesis and critique are wide center-pane workflows over evidence. METHODS remains for compact paper-method lenses, while Critique gets the room it needs without changing the signal-not-verdict contract.
- **Verify:** frontend rebuilt; focused `tests/test_frontend_assembly.py tests/test_help.py tests/test_critical_review.py tests/test_critical_review_set.py` **73 passed**; QA surface map **248 API / 1141 FE, 0 uncovered**; full suite **1260 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 297: Discover Feed restored as its own sub-tab
- **Files:** `app/frontend/js/{04b_workspaces,09_placeholders,30d_discover}.jsx`, `app/backend/help/help_content.md`, `.claude/{DESIGN.md,qa-routes/route_44_feed.md,qa-routes/route_73_workspaces.md}`, `tests/test_frontend_assembly.py`, `callosum-app.html`, increment notes.
- **What:** re-separated Feed from Search inside the Discover workspace. Discover now presents **Feed · Search · Journals · Funding**; Feed renders standalone as the first Discover sub-tab, while Search no longer embeds Feed beneath its results. Wanted/Gaps/Overlooked remain Search launchers.
- **Why:** Feed is a recurring triage mode, not a one-off query result section. Restoring it as a sibling tab keeps Search focused on explicit provider-scoped searches while leaving followed-source monitoring quickly reachable.
- **Verify:** frontend rebuilt; focused `tests/test_frontend_assembly.py tests/test_help.py tests/test_feed.py` **57 passed**; QA surface map **248 API / 1141 FE, 0 uncovered**; full suite **1259 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 296: Discover Search selectable sources
- **Files:** `app/backend/discovery/{providers,search,crossref_provider,pubmed_provider}.py`, `app/backend/api/routers/discovery.py`, `app/frontend/js/30d_discover.jsx`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_43_discovery.md`, `.claude/security-audits/2026-07-18_discovery-search-source-picker.md`, `tests/{test_discovery,test_frontend_assembly}.py`, `callosum-app.html`, increment notes.
- **What:** Discover → Search now has a source dropdown using the existing `.lib-sort` recipe. **All sources** preserves the prior Crossref+PubMed fan-out and dedup; choosing **Crossref** or **PubMed** sends `source=<kind>` to `/discovery/search` so only that registered provider is queried. Added read-only `GET /discovery/sources` so the picker is registry-driven, and unknown source kinds fail closed with 422.
- **Why:** users sometimes need to deliberately scope discovery to a provider without implying AI has filtered the result list. The complete returned list is still shown, source pills remain visible, and axis relevance stays a hint only.
- **Verify:** security audit PASS; frontend rebuilt; focused `tests/test_discovery.py tests/test_frontend_assembly.py tests/test_help.py` **65 passed**; QA surface map **248 API / 1141 FE, 0 uncovered**; full suite **1259 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 295: Feed — follow journals by title + Suggest-from-library + typeahead
- **Files:** `app/backend/discovery/journal_title_source.py` (new; `journal_issn_source.py` removed), `app/backend/discovery/feed.py`, `app/backend/api/routers/feed.py`, `app/backend/persistence/{feed_repo,schema_feed}.py`, `app/frontend/js/30e_feed.jsx`, `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_44_feed.md`, `.claude/security-audits/2026-07-18_feed-journal-title-and-library-journals.md`, `tests/{test_feed,test_frontend_assembly}.py`, increment notes.
- **What:** the Feed now follows journals **by title** (the new default source; ISSN dropped) — resolve title→ISSN via the audited Crossref host then its recent works. New read-only local `GET /feed/library-journals` (`papers.venue` + counts) powers a **Suggest** modal of the journals already in your library (one-click Follow) and **journal-title typeahead** as you type. No new dependency; egress only on Refresh (the feed's existing opt-in channel).
- **Why:** users know journal titles, not ISSNs; seeding the feed from the library you already have makes it useful immediately. The suggestions are a transparent tally of your own library, not an AI ranking (signal-not-verdict).
- **Verify:** security audit PASS; `tests/test_feed.py` (title source exact+fallback+blank; library-journals endpoint; registry default), `tests/test_frontend_assembly.py` +1; QA surface **247 API / 1139 FE, 0 uncovered**; frontend rebuilt; ruff (both) + line-budget clean; full suite green (count in inc-295 notes). **User step:** restart the backend to serve the new `/feed/library-journals` + journal source.
- **Revert:** restore the listed files (+ restore `journal_issn_source.py` from git) and rebuild `callosum-app.html`.

## 2026-07-18 — Increment 294: Reading Queue stratified by priority (drag within + across groups)
- **Files:** `app/backend/api/routers/reading_queue.py`, `app/backend/persistence/reading_queue_repo.py`, `app/frontend/js/{16_queue,16b_readmark,10d_papercard,10_pdf_layer,40_app}.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_49_reading_queue.md`, `tests/{test_reading_queue,test_frontend_assembly}.py`, `callosum-app.html`, increment notes.
- **What:** the Reading Queue now groups papers by the priority set in the Library — **High / Normal / Low / Unprioritized** (null → Unprioritized). Rows stay draggable: reorder within a group, or drag across groups to re-prioritise. Cross-group moves reuse `POST /papers/{id}/priority` (Unprioritized → `null` clears) then the existing all-or-nothing reorder; `GET /reading-queue` now carries each row's `priority`. No new endpoint or schema change. **Cards ↔ Queue stay in sync** (one source of truth, `papers.priority`): a card priority change reloads the Queue and a Queue drag reloads the cards, via the existing bump-counter wiring (`ReadPriorityControl` gains an `onChanged`; `onQueueChanged` now also bumps `setLibRefresh`).
- **Why:** turn the flat to-read list into a triage board keyed on the user's existing hand-set priority, without inventing a new concept or any AI scoring (priority stays the user's own label).
- **Verify:** frontend rebuilt; `tests/test_reading_queue.py` +2, `tests/test_frontend_assembly.py` +1; QA surface **0 uncovered**; full suite green (count in the inc-294 notes); ruff (both) + line-budget clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 293: Credit-the-lineage add-missing states
- **Files:** `app/backend/api/routers/library.py`, `app/frontend/js/{05_method_credit,06_methods_statcheck,07_methods_grim,08b_methods_citation_equity,08c_methods_citation_context,08d_methods_bayes,08f_methods_lmm,08g_methods_metaanalysis,08h_methods_transparency,08i_methods_effectsize,29_pcurve,36b_overlooked,38_credit}.jsx`, `app/backend/help/help_content.md`, `.claude/{DESIGN.md,qa-routes/route_73_workspaces.md}`, `tests/{test_citation_import,test_frontend_assembly}.py`, `callosum-app.html`, increment notes.
- **What:** replaced the duplicated lineage import buttons with a shared `MethodCreditButton`. The button now checks DOI-backed credited sources via read-only `POST /library/credit/status`, says **＋ add missing to library** while anything is absent, imports only missing CSL items through `/library/import`, and says **✓ added to library** when all credited DOI-backed sources are already present or after a successful import. Multi-source credits such as CRediT now avoid blind re-imports.
- **Why:** method-credit affordances should not imply work remains when the cited method sources are already in the library, and partial multi-source credits should add only the genuinely missing lineage.
- **Verify:** frontend rebuilt; focused `tests/test_citation_import.py tests/test_frontend_assembly.py tests/test_help.py` **52 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; full suite **1247 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 292: Library retractions refresh + badges
- **Files:** `app/backend/api/routers/methods_retraction.py`, `app/backend/api/routers/{papers,paper_models}.py`, `app/backend/persistence/repository.py`, `app/frontend/js/{03_library,08_methods_findings,10_pdf_layer,10b_libmenus,10d_papercard,25_detail}.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, `tests/{test_retraction,test_frontend_assembly}.py`, `callosum-app.html`, increment notes.
- **What:** the library-wide retraction batch now attempts a Retraction Watch mirror refresh before checking papers, but treats refresh failure as a visible fallback rather than a hard failure. `/papers` and `/papers/{id}` now include stored `retraction_status`, enabling a red **RETRACTED** badge on paper cards and Details. Added a **Retractions ↻** Library-header button before **Text Health**, with last-run/fallback detail in the tooltip; the Review pane also reports mirror refresh counts/fallback detail.
- **Why:** Retraction Watch is the richest registry source, but its availability should not block Crossref/OpenAlex checks or the existing local mirror. Retraction remains an evidence-bearing registry signal to inspect before citing, not an accusation or score.
- **Verify:** frontend rebuilt; focused `tests/test_retraction.py tests/test_retraction_watch.py tests/test_frontend_assembly.py` **55 passed**; `tests/test_help.py` **14 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; throwaway-server Playwright smoke confirmed **Retractions ↻** before **Text Health** with `.trash-toggle`, registry tooltip, and 0 console/page errors; full suite **1245 passed / 1 skipped**; ruff + format + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 291: Discover selected-paper cue for Journals/Funding
- **Files:** `app/frontend/js/{04b_workspaces,40_app}.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, `tests/test_frontend_assembly.py`, `callosum-app.html`, increment notes.
- **What:** added a selected/open-paper cue before the Discover sub-tabs when **Journals** or **Funding** is active. It reuses the Library tab vocabulary: dashed selected-paper styling when the paper is selected but unopened, and normal open-PDF tab styling when that selected paper is already open.
- **Why:** Journals and Funding operate on the selected paper; the cue makes that context visible at the top of those tools and provides a direct click path to open or return to the reader.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py tests/test_help.py` **39 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; mocked static-bundle browser smoke confirmed Journals/Funding selected/open cues and Search absence; full suite **1243 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 290: Library selected-paper tab + PDF tab reorder
- **Files:** `app/frontend/js/{30c_frame,40_app}.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, `tests/test_frontend_assembly.py`, `callosum-app.html`, increment notes.
- **What:** added a pinned selected-paper tab immediately after **Library** whenever the current selection is not already open in the reader; clicking it opens the PDF via the existing `openPdf` path. Open PDF tabs are now draggable to reorder, while the selected-paper tab remains pinned and non-draggable.
- **Why:** keeps the selected paper visible in the Library tab strip without pretending it is already open, and lets users keep multiple reader tabs in their own working order.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py tests/test_help.py` **38 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; mocked static-bundle browser smoke confirmed the selected-paper tab and PDF tab drag reorder; full suite **1242 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 289: Workspace scroll + My Publications workspace polish
- **Files:** `app/frontend/js/{04b_workspaces,08g_methods_metaanalysis,08i_methods_effectsize,15_axes,15b_axis_card,30c_frame,31_mypubs_dashboard,40_app}.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, `tests/test_frontend_assembly.py`, `callosum-app.html`, increment notes.
- **What:** made registered workspace bodies vertically scroll within the bounded center pane; renamed menu-bar **Profile** to **My Publications**; renamed Extract tabs **Effect-Size** and **Meta-Analysis**; made the My Publications dashboard resolve its own axis and refetch on `axisRefresh`; removed the redundant My Publications axis-card dashboard button.
- **Why:** long Discover/Extract tools should not disappear below the viewport, and the My Publications workspace should populate from the menu bar after refresh without requiring an axis-card interaction.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py tests/test_help.py tests/test_my_publications.py` **78 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; static-bundle browser smoke confirmed labels/internal scroll/narrow overflow (expected API console errors without backend); full suite **1241 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 288: Library header polish + positive Open Data signal
- **Files:** `app/frontend/js/{03_library,10b_libmenus,10_pdf_layer,19_synthesis_failures,26b_text_health}.jsx`, `app/frontend/styles.css`, `app/backend/{api/routers/transparency,persistence/signals_repo,persistence/repository}.py`, `app/backend/help/help_content.md`, `tests/{test_frontend_assembly,test_transparency_findings}.py`, `callosum-app.html`, increment notes.
- **What:** shortened Library header controls to stable labels: **Metadata ↻**, **Citations ↻**, **Text Health**, **⚠ Flagged · N**, **⚠ Retracted · N**, **📋 Review · N**, and **🔎 Open Data · N**. Metadata/citation/text-health dynamic details now live in tooltips. Inverted the old open-data-not-detected chip into a positive `transparency-data-detected` signal and exposed `data_detected` from the transparency summary while preserving `data_not_detected` review queues.
- **Why:** keeps the Library header from shifting under the user after refreshes and makes the open-data chip a checkable positive signal instead of a negative-sounding absence queue.
- **Principles:** read `.claude/PRINCIPLES.md`; Open Data remains signal-not-verdict, evidence-bearing, and non-scoring. No claim is made that papers without the chip lack data.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py tests/test_help.py tests/test_transparency_findings.py` **44 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; full suite **1240 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 287: Synthesis + Work workspace split
- **Files:** `app/frontend/js/{03_library,04b_workspaces,08b_methods_citation_equity,08c_methods_citation_context,08j_reference_integrity,20_synthesis,30c_frame,37_cite,38_credit,40_app}.jsx`, `app/frontend/styles.css`, `callosum-app.html`, `tests/test_frontend_assembly.py`, help/design/QA/docs.
- **What:** added **Synthesis** as a center menu-bar workspace after Library, and added **Work** after Discover. Moved **Cite** out of the THEORY pane into Work, with nested tabs **Suggest → Meta Reference List → Citation concentration → How it's cited**; moved **CRediT statement** into Work. Paper-card ref-signal jumps now route directly to Work → Cite → Meta Reference List, and Library selection summarize opens Synthesis.
- **Why:** separates broad corpus synthesis and writing/citation authoring from the compact selected-paper THEORY accordion while preserving the existing modals/components and keeping open PDFs under Library.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py tests/test_help.py` **35 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; Playwright desktop/narrow smoke passed with menu overflow contained by horizontal scrolling; full suite **1237 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 286: Discover Search owns discovery launchers + Feed
- **Files:** `app/frontend/js/{04b_workspaces,30d_discover,30e_feed,10_pdf_layer,40_app}.jsx`, `app/frontend/js/{09_placeholders,30c_frame}.jsx`, `app/frontend/styles.css`, `callosum-app.html`, `tests/test_frontend_assembly.py`, help/design/QA/docs.
- **What:** moved **Wanted**, **Gaps**, and **Overlooked** out of the Library header and into **Discover → Search** as primary buttons immediately after Search, preserving their existing modal flows. Removed the standalone Discover **Feed** sub-tab and embedded Feed beneath the Search contents/results.
- **Why:** keeps outward-facing literature discovery tools together under Discover while reducing Library header sprawl and making Feed part of the Search surface instead of a sibling mode.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py tests/test_help.py` **35 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; Playwright desktop + narrow checks passed; full suite **1237 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore the listed files from git and rebuild `callosum-app.html`.

## 2026-07-17 — Increment 285: one-time workspace "what moved" hint
- **Files:** `app/frontend/js/30c_frame.jsx`, `app/frontend/styles.css`, `callosum-app.html`, `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_73_workspaces.md`, docs.
- **What:** added a dismissible one-time neutral Library banner for returning users: "Where to submit" + Funding now live under Discover; Effect-size + Meta-analysis under Extract; Help + Settings are on the menu bar. Dismissal persists via `callosum.workspaces-whatsnew=1`; the banner is hidden on read-only companions.
- **Why:** closes the inc-280 UX follow-up for users re-finding relocated tools after the workspace navigation change.
- **Verify:** frontend rebuilt; `tests/test_frontend_assembly.py` **21 passed**; QA surface map **0 uncovered API / 0 uncovered FE**; full suite **1237 passed / 1 skipped**; ruff + line-budget gates clean. Visual placement is **unverified** in-browser.
- **Revert:** restore the listed files from git.

## 2026-07-17 — Increment 284: DESIGN §5 workspace/lens rewrite
- **Files:** `.claude/DESIGN.md`, `.claude/docs/increment-notes/INCREMENT-284-NOTES.md`.
- **What:** rewrote DESIGN §5 as a coherent two-navigation-dimension model: workspaces/menu bar are center-pane modes of work; THEORY/METHODS side accordions are per-paper lenses. Preserved the shipped registry mechanics and token recipes for `.menubar`, `.workspace-tabs`, `.pane-tabs`, `.tags-srcfilter`, and mount-but-hide bodies.
- **Why:** closes the inc-280 follow-up by replacing the interim workspace note bolted onto the older accordion rubric with the actual placement rule: mode vs. lens, chosen by the user's cognitive task.
- **Verify:** static read against `04b_workspaces.jsx` + `05_panes.jsx`; full suite **1237 passed / 1 skipped**; ruff + line-budget gates clean.
- **Revert:** restore `.claude/DESIGN.md` and remove `.claude/docs/increment-notes/INCREMENT-284-NOTES.md` from git.

## 2026-07-17 — Increment 283: PDF text-health — fix "missing section labels" (per-line detection + honest staleness)
- **Files:** `app/backend/pdf_processing/sections.py`, `app/backend/pdf_processing/extraction.py`, `tests/test_pdf_processing.py`, increment notes.
- **What:** Text Health flagged 101/102 papers as *missing section labels* with a misleading *0 stale extraction*. Root cause: the whole library was extracted **before** section detection landed (commit `91ed1ae`), so 100% of chunks had `section = NULL` — and because that commit never bumped `DEFAULT_CHUNKING_STRATEGY`, the stale check saw those chunks as current. Fix: (A) `SectionTracker.observe_block` scans blocks **per line** so headings PyMuPDF merged with body text are caught (`observe`/`detect_section_heading` unchanged); (B) bumped the strategy to `pymupdf-block-v2` so pre-section chunks honestly read as `stale_chunk_version`. The existing **Reprocess missing section labels** job then backfills (re-extract + re-embed).
- **Why:** section labels feed section-scoped summarization, statcheck section context, and citation metadata — all silently degraded by a 100%-NULL library. Measured: papers with zero sections **13/108 (12%) → 0/107**; 82.4% mean chunk coverage, 5.0 sections/paper.
- **Verify:** `tests/test_pdf_processing.py` 22 passed (2 new; fixed one that used `v2` as its arbitrary alternate → `pymupdf-block-alt`); full suite green; ruff (both gates) + line-budget + QA-surface (0 uncovered) clean. Help corpus already accurate (no edit). **User step:** click Reprocess in Text Health to backfill the existing library.
- **Revert:** restore the 3 files from git (branch `feature/pdf-section-labels`).

## 2026-07-17 — Increment 282: credit-the-lineage backfill — the overlooked-work lens (#8 complete)
- **Files:** `app/frontend/js/36b_overlooked.jsx`, `callosum-app.html`, `tests/test_frontend_assembly.py`, docs.
- **What:** the overlooked-work lens (#37) operationalizes the Matthew effect (Merton 1968) but credited it only in prose; added the shared `.method-credit` affordance — source paper in-context + one-click **add to library** (`/library/import`), matching statcheck/GRIM/p-curve/etc.
- **Why:** closes the one Lane-A gap #8 had left (the lens post-dates the inc-180 credit pass). The other credit-less method surfaces are data-source-driven/compositional → NOTICES-level (excluded per the backlog rationale). **#8 now complete** — every method-implementing tool with an identifiable method-paper lineage credits it in-tool + offers it to the library.
- **Verify:** the overlooked assembly guard extended (OverlookedCredit + .method-credit + Merton CSL/DOI); build clean; line budget; full suite **1237** (unchanged — an existing guard extended).
- **Revert:** restore the listed files from git (branch `feature/credit-lineage-backfill`).

## 2026-07-17 — Increment 281: short-write run_write sweep — the "database is locked" residual edge CLOSED
- **Files:** `app/backend/api/dependencies.py` (+`get_engine`), 17 routers converted (`findings, saved_searches, paper_urls, annotations, feed, wanted, papers, axes, duplicates, critical_review, summaries, gaps, discovery, agent, settings, my_publications, workbench`), `tests/test_short_write_sweep.py` (new guard), notes + backlog.
- **What:** route the short SELECT-then-write API handlers through **`run_write`** (transaction-level retry, inc 272) so a snapshot-upgrade `SQLITE_BUSY` (which `busy_timeout` can't break) is retried instead of 500ing. Each handler wraps its read+write unit in `run_write(engine, _do)`; GET handlers keep `get_connection`. Idempotent I/O-mixed imports (gaps_add, my-pubs import*, discovery_save) wrap whole (dedupe + cached fetch).
- **Left raw (guard-test allowlist):** heavy/egress ops (reprocess-pdf, purge, empty-trash, summary-reverify, cr-generate, propose_row) + I/O that must not re-fire on retry (paper_enrich force-refetch, agent_save_reference Crossref, sync setup). No engine `BEGIN IMMEDIATE` (would re-starve the inc 273–278 fetch phases).
- **Why:** the last open piece of the `database is locked` arc (both halves now shipped). The middleware stays as the belt-and-suspenders backstop.
- **Invariant:** `test_short_write_sweep.py` fails on any NEW unaccounted raw `conn.commit()` in `routers/**` — machine-enforced.
- **Verify:** per-router suites green; the guard test green; full suite **1237 passed / 1 skipped**; ruff + line budget clean.
- **Revert:** `git revert` the sweep commits on `feature/short-write-sweep`, or restore from git.


## 2026-07-17 — Increment 280: workspaces — two-level center navigation (menu bar)
- **Files:** `app/frontend/js/04b_workspaces.jsx` (new — registry + `MenuBar` + `WorkspacePane`), `30c_frame.jsx` (Library workspace body), `40_app.jsx` (menu bar + workspace state + Help/Settings center slots), `10_pdf_layer.jsx` (Sidebar drops `?`/`⚙`), `08e`/`08k` (→ Discover: Journals/Funding), `08i`/`08g` (→ Extract: Effect-size/Meta-analysis), `18_help.jsx`/`35_settings.jsx` (Modal → View), `styles.css`, `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/{DESIGN.md, qa-routes/route_73_workspaces.md, docs/increment-notes/INCREMENT-280-NOTES.md}`, `tests/{test_frontend_assembly, test_funding_discovery}.py`.
- **What:** a two-level center nav — a **menu bar of workspaces** (Profile·Library·Discover·Extract + Help·Settings) **inside the center (Library) pane**, above per-workspace sub-tabs. Open PDFs nest under Library; My-Pubs → **Profile**; Journals/Funding relocate THEORY → **Discover**; Effect-size/Meta-analysis METHODS → **Extract**; Help/Settings modals → wide center views. The THEORY/METHODS side accordions **persist** — a second nav dimension (workspaces = *what you're doing*; accordions = *lenses on the paper*).
- **Why:** the flat center strip mixed modes-of-work with open documents, and outward/wide-output tools were stuck in narrow rails. Extends the placement rubric with a workspace axis (DESIGN §5).
- **Design note (feedback):** the menu bar lives **inside** the center pane, not app-wide — the three panes stay separate + full height.
- **Verify:** build clean; `test_frontend_assembly.py` workspace guard + updated funding/publishers tests; full suite **1236 passed / 1 skipped**; QA **route 73** (0 uncovered); line budget. Experience pass (returning-user persona) + a UX follow-up backlogged. **Manual UI check owed** (user verifying hands-on across stages).
- **Revert:** `git revert` the stage commits on `feature/workspaces-nav`, or restore from git.

## 2026-07-16 — Increment 279: overlooked-work lens (backlog #37) — per-axis discovery
- **Files:** `integrations/openalex/sources.py` (`fetch_topic_works` + `TopicWork` + inverted-index helper + opt-in `cache_engine`/`with_cache_engine`), `app/backend/methods/overlooked.py` (new — `compute_overlooked`), `app/backend/persistence/{schema_findings,schema,overlooked_repo}.py` + `alembic/versions/0046_overlooked_candidates.py` (new table + repo), `app/backend/api/routers/overlooked.py` (new — `POST/GET /overlooked/refresh` + `GET /overlooked`), `app/backend/api/app.py` (mount + `overlooked_lens_jobs`), `app/frontend/js/36b_overlooked.jsx` (new — `OverlookedLensModal`) + `40_app.jsx`/`10_pdf_layer.jsx` (header **Overlooked** button), `callosum-app.html` (rebuilt), `tests/{test_overlooked,test_frontend_assembly}.py`, docs (help + THIRD-PARTY-NOTICES + QA route 72 + security audit + INCREMENT-279-NOTES).
- **What:** a per-axis discovery lens ("the Matthew effect, inverted") that surfaces external works highly relevant to an axis but under-cited for their vintage. Pipeline: axis label → OpenAlex topic → topic works → drop in-library → **local** relevance (on-device abstract embedding, cosine to the axis vector) + **local** citation percentile among same-`publication_year` peers → keep the low-percentile candidates, rank by relevance, cap. Cached per axis; Refresh runs its fetch phase **fetch-outside-lock** (inc D). Add/Dismiss reuse the gap flow.
- **Why:** backlog #37 (equity/integrity signals) — make the literature's attention machinery inspectable so citation counts don't silently do the user's thinking.
- **Honesty (rule #9):** signal-not-verdict; **two separable visible inputs (relevance + citations-vs-same-vintage percentile), never fused into a composite score**; **identity-agnostic** (no author/identity field in the engine, table, or response); silence-not-a-certificate (null percentile when too few same-year peers → withheld, not guessed); pull-not-push; augment-never-filter. Credit-the-lineage: Merton (1968) credited in-panel + in NOTICES.
- **Security:** `2026-07-16_overlooked-work-lens.md` **PASS** — topic/work ids validated (`^T\d+$`/`^W\d+$`); only the axis label + topic id egress (public-metadata channel, NOT the Gemini gate; no library text — abstracts embedded on-device); bound-param SQL; bounded/cached/fail-closed. QA **route 72** added (0 uncovered API surfaces).
- **Naming note:** distinct from the pre-existing citation-equity per-paper "overlooked-work remediation" (#25 SP2, `/methods/citation-equity/overlooked`, `methods/overlooked_work.py`) — this is the library-level per-axis lens (`methods/overlooked.py`, `/overlooked/*`, `overlooked_lens_jobs`).
- **Verify:** `tests/test_overlooked.py` (9) + `test_frontend_assembly.py` overlooked guard green; full suite green; ruff + budget clean; frontend rebuilt. **Manual UI check owed** (no browser automation in-session — INCREMENT-279-NOTES).
- **Revert:** restore the listed files from git (branch `feature/overlooked-work-lens`); the additive migration 0046 has no down-migration (drop `overlooked_candidates` manually if needed).

## 2026-07-16 — Increment 278: long-job incremental commits — D (read-heavy) — the long-job half COMPLETE
- **Files:** `app/backend/api/routers/{duplicates,gaps,my_publications}.py`, `integrations/api_cache.py` (+`put_cached_committing`), `integrations/openalex/{adapter,author}.py` (opt-in `cache_engine`), `app/backend/clustering/my_publications.py` (resolve fetch/persist split), `app/backend/clustering/my_publications_domains.py` (new — decompose extracted), `tests/{test_api_cache,test_openalex_adapter,test_my_publications}.py`.
- **What:** the read-heavy jobs (not per-paper loops). Dedup → a read connection (a read-only scan mustn't open a write txn). Gap-finder + my-pubs refresh/decompose → **fetch-outside-lock**: their reads + external OpenAlex fetches run on a read connection with the client caching self-committingly (new opt-in `cache_engine` + `put_cached_committing`), then the single final persist is a short `run_write` (a fresh snapshot, dodging a snapshot-upgrade BUSY). My-pubs' resolve/decompose split into fetch/persist behind unchanged all-in-one wrappers (no caller/test blast radius); domain decomposition extracted to a sibling module for the 600-line cap.
- **Why:** the last group of the long-job half. **With D, every long job releases the write lock during its slow work** — a background job no longer starves foreground writes.
- **Safety:** the self-committing cache is **opt-in** (the per-item B/C callers keep conn-based caching — a universal change would deadlock a caller that fetches inside a held per-paper lock; guard tests `test_citation_counts`/`test_metadata_multi_enrich`).
- **Verify:** api_cache/duplicate_detection/gapfinder/openalex_adapter/my_publications/health suites green; full suite green; ruff + budget clean. **Manual scan/refresh-while-toggling check still owed** (INCREMENT-278-NOTES).
- **Revert:** restore the listed files from git (branch `feature/readheavy-fetch-outside-lock`).

## 2026-07-16 — Increment 277: long-job incremental commits — C (method batches)
- **Files:** `app/backend/api/routers/{methods,methods_retraction,transparency,citation_counts}.py`, `tests/test_statcheck.py`.
- **What:** per-item commits for the four method-batch jobs (statcheck / retraction / transparency / citation-counts). Each now reads its paper list first (read connection), then processes every paper in its own `run_write` transaction (was one `engine.begin()` over the whole loop) — so the write lock is released between papers, and the per-paper external calls (retraction DOI lookups, OpenAlex citation fetches) no longer hold a batch-wide lock. One bad paper is skipped, never aborting the batch.
- **Why:** the long-job half's method-batch group — user-initiated, same starvation risk during a library-wide run.
- **Behavior change (intended):** atomicity per-paper; a mid-run failure leaves earlier papers' signals committed and the job completes (every batch is a re-runnable overwrite).
- **Scope:** method batches done. Deferred: D (dedup, gap-finder, my-publications refresh/decompose) — the last group.
- **Verify:** the batch-covering suites green (74) + new `test_statcheck_batch_commits_per_paper_partial_progress`; full suite green; ruff + budget clean. **Manual batch-while-toggling check still owed** (INCREMENT-277-NOTES).
- **Revert:** restore the listed files from git (branch `feature/method-batch-per-item-commits`).
- **Note (numbering):** this is sequential increment 277 per CLAUDE.md's counter; a stale Codex backlog reference also says "inc 277" for the earlier `retry_sqlite_locked` helper — part of the 271-277-real vs 277-297-phantom drift flagged for reconciliation.

## 2026-07-16 — Increment 276: long-job incremental commits — B (ingest family)
- **Files:** `app/backend/api/routers/library.py` (`_run_import_job`, `_run_bundle_import_job`), `app/backend/api/routers/library_enrich.py` (`_run_metadata_enrich_job`), `tests/test_citation_import.py`, `tests/test_metadata_multi_enrich.py`.
- **What:** per-item commits for the three ingest jobs. Citation import + bundle import: parse+create commits as its own unit (`run_write`), then each new paper is embedded (import: + retraction-checked) in its own committed transaction (`commit_each`). Metadata enrich-batch: each paper's external fetch + write now runs in its own `run_write` transaction (was one big txn over the whole loop). So the write lock is released between papers.
- **Why:** the long-job half's ingest group — user-initiated, so lower urgency than the auto-running A/A2/A3 offenders, but the same starvation risk during a large import/enrich.
- **Behavior change (intended, consistent with A):** atomicity per-paper; a mid-run failure leaves earlier papers imported/embedded/enriched and the job completes (skip-on-error) rather than rolling back the whole run.
- **Scope:** ingest family done. Deferred: C (method batches + citation-counts), D (dedup/gap-finder/my-pubs).
- **Verify:** the 3 ingest suites green (41, incl. 2 new per-paper partial-progress tests); full suite green; ruff + budget clean. **Manual import/enrich-while-toggling check still owed** (INCREMENT-276-NOTES).
- **Revert:** restore the listed files from git (branch `feature/ingest-per-item-commits`).

## 2026-07-16 — Increment 275: long-job incremental commits — A3 (axis-score embed-phase hoist)
- **Files:** `app/backend/clustering/axis_scoring.py` (+`ensure_candidate_embeddings_committing`), `app/backend/api/routers/axes.py` (`_run_axis_score_job` rewired), `tests/test_axis_scoring.py`.
- **What:** the axis-score job wrapped its whole run — including embedding every candidate paper — in one `engine.begin()`. `ensure_candidate_embeddings_committing(engine, …)` now pre-embeds the pending candidate papers **one committed transaction per paper** (via `commit_each`), and the job runs the scoring (embeddings now present → `score_axis`'s `ensure_embeddings` is a no-op) in one short `run_write` transaction. So the slow embedding phase releases the write lock between papers.
- **Why:** finishes the **auto-running offenders** (scan + rescan + axis-score) of the long-job half; the axis-score job was one of the QA-flagged lock-holders.
- **Design note:** rather than thread `engine`/per-paper commits through the clustering internals, A3 pre-embeds at the job boundary and relies on `embed_papers`'s existing idempotency (skips already-embedded) — so `score_axis` keeps its single-`conn` contract and the existing scoring suite is untouched. The assignment *replace* stays atomic (one txn, as required); only the *embedding* became per-item.
- **Scope:** auto-running offenders now all per-item. Deferred: B (ingest family), C (method batches + citation-counts), D (dedup/gap-finder/my-pubs).
- **Verify:** `test_axis_scoring.py` (incl. 2 new per-paper commit tests) + `test_axes.py` green (41); full suite green; ruff + budget clean. **Manual score-while-toggling check still owed** (INCREMENT-275-NOTES).
- **Revert:** restore the listed files from git (branch `feature/axis-score-embed-hoist`).

## 2026-07-16 — Increment 274: long-job incremental commits — A2 (scan per-file extraction commits)
- **Files:** `app/backend/pdf_processing/library_scan.py` (`scan_library_folder` conn→engine, per-file commits), `app/backend/api/routers/library.py` (both scan jobs call it directly), `tests/test_library_scan.py`.
- **What:** finishes the scan half. `scan_library_folder` now takes `engine` and ingests **each new file in its own `run_write` transaction** (replacing the per-file `begin_nested` savepoint, which never released the lock), so the write lock is released between files during the slow extract+chunk phase. Upfront dedup reads run on a read connection; removed-detection is a final short write.
- **Why:** inc-273 (A) made the enrich+embed phase per-paper but the extraction phase still held the lock across the whole file loop (savepoints isolate but don't commit). Per-file commits release it between files.
- **Behavior change (intended, consistent with A):** atomicity is per-file; a corrupt PDF rolls back just its file (isolation preserved) and the scan continues; content-hash dedup keeps the scan idempotent. Signature `conn→engine` (the two scan jobs + 5 test call sites updated).
- **Scope:** finishes the scan. Deferred: A3 (axis-score embed-hoist), B–D.
- **Verify:** `test_library_scan.py` (14, incl. new per-file self-commit test) + `test_watched_folders.py` green; full suite green; ruff + budget clean (library_scan.py 144, library.py 522). **Manual scan-while-toggling check still owed** (INCREMENT-274-NOTES).
- **Revert:** restore the listed files from git (branch `feature/scan-per-file-commits`).

## 2026-07-16 — Increment 273: long-job incremental commits — A (commit_each + scan/rescan)
- **Files:** `app/backend/persistence/sqlite_retry.py` (+`commit_each`), `app/backend/api/routers/library.py` (`_process_scan_result` conn→engine per-paper; `_run_scan_job` + `_run_watched_rescan_job` rewired), `tests/test_sqlite_retry.py` + `tests/test_library_scan.py`.
- **What:** the second half of the `database is locked` item (first half = inc-272 foreground retry). `commit_each(engine, items, process, on_item_error="skip")` runs each item in its own short transaction via `run_write`, releasing the write lock between items. The scan / watched-rescan jobs now commit the `scan_library_folder` insert phase as its own unit, then enrich+embed **per paper** — so a long scan no longer holds the write lock for its whole multi-minute run; foreground writes (retrying via inc-272) slip in between papers.
- **Why:** inc-272's foreground retry can't outlast a lock held for *minutes* by a job that wraps its whole run in one `engine.begin()`. Releasing the lock between papers is the complementary fix.
- **Behavior change (intended):** atomicity moves from per-job to per-item — a mid-run failure leaves earlier papers committed (partial progress is usable + the scan is idempotent via content-hash dedup; also fixes a latent poisoned-transaction bug). Recorded in INCREMENT-273-NOTES.
- **Scope:** the scan/rescan family (auto-running offenders). Deferred: A2 (`scan_library_folder` per-file extraction commits), A3 (axis-score embed-hoist), B–D (per the spec).
- **Verify:** `test_sqlite_retry.py` (12) + `test_library_scan.py` (incl. new per-paper partial-progress test) + `test_watched_folders.py` green; full suite green; ruff + line-budget clean (library.py 528). **Manual scan-while-toggling check still owed** (INCREMENT-273-NOTES). No help-doc change (no user-facing surface).
- **Revert:** restore the listed files from git (branch `feature/long-job-incremental-commits`).

## 2026-07-15 — Increment 272: SQLite write-retry hardening (the "database is locked" short-write item)
- **Files:** `app/backend/persistence/sqlite_retry.py` (+`run_write`), `app/backend/api/sqlite_retry_middleware.py` (new), `app/backend/api/app.py` (wire the middleware), `app/backend/api/routers/{papers,tags,reading_queue,axes}.py` (convert hot short writes), `tests/test_sqlite_retry.py` + `tests/test_sqlite_retry_middleware.py`.
- **What:** two-layer defense against short request-path writes 500ing on a transient `sqlite3.OperationalError: database is locked`. **Layer 1** `run_write(engine, fn)` — transaction-level retry (fresh connection per attempt → run closure → commit → retry the whole unit on a lock with backoff); wired into read/priority, tag color/add/lock/remove, reading-queue add/reorder/remove, axis create (response reads still ride the `Depends` connection). **Layer 2** `SqliteWriteRetryMiddleware` — a backstop that re-runs any *replay-safe* mutating request that raises an uncaught lock error before sending a response; a `REPLAY_UNSAFE_PREFIXES`/`_SUBSTRINGS` denylist excludes job-spawning / external-fetch / secret-writing families so a replay can't double-execute a side effect.
- **Why:** the inc-277 `_write` retry is at the wrong granularity (retries a single `conn.execute` on the *same* still-open transaction, which keeps its stale snapshot → can't clear a snapshot-upgrade BUSY). Clearing a lock needs re-running the whole unit of work on a fresh connection. Backlog's "highest-value pre-public concurrency item", ▲elevated by the QA runs (route_15 axes, route_50 read-marker 500s).
- **Scope:** the SHORT-write half only. The long-job half (splitting `_run_scan_job`/embed/enrich/axis-score `engine.begin()` into incremental commits so they don't hold the write lock for minutes) stays open as its own increment.
- **Verify:** `tests/test_sqlite_retry*.py` (9+7) pass; papers/tags/reading_queue/annotations/findings/saved_searches/axes suites green *through the wired middleware* (119); full suite green; ruff + line-budget clean. No audit-gate trigger (no new endpoint/external fetch/ingestion/auth; the middleware only re-runs existing handlers, adds no data path). **Manual concurrency check (scan-while-toggling) still owed** — recorded in INCREMENT-272-NOTES.
- **Revert:** restore the listed files from git (branch `feature/sqlite-write-retry`).

## 2026-07-15 — Increment 271: set (multi-paper) critical review (backlog #12)
<!-- HELP-DOCS-SYNCED 2026-07-15 inc 271 — help corpus gains "Critically reviewing a set of papers together"; the intervening cosmetic UI entries above the prior 2026-07-13 marker (statcheck-e chip grouping, enrich per-item titles, region-precision copy, inc-270 locator) were reviewed as not needing a corpus change. Nothing above this line has an un-synced corpus change. -->
- **Files:** `alembic/versions/0045_cr_candidate_related_papers.py`, `app/backend/persistence/{schema_critical_review,critical_review_repo}.py`, `app/backend/methods/critical_review_set.py` (new), `integrations/gemini/critical_review_set.py` (new), `app/backend/api/routers/critical_review.py`, `app/backend/api/app.py`, `app/frontend/js/08y_critical_set.jsx` (new), `app/frontend/js/{03_library,10_pdf_layer,20_synthesis,40_app}.jsx`, `app/frontend/styles.css`, rebuilt `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/security-audits/2026-07-15_multi-paper-critical-review.md`, `.claude/qa-routes/route_71_critical_review_set.md`, `tests/test_critical_review_set.py`, `tests/test_frontend_assembly.py`.
- **What:** extends the single-paper "Critical read" (inc 266) to a **chosen set of papers reviewed together**. Tier 1 (local): a **fact-matrix** of each set paper's stored method signals (no score) + the claims papers *in the set* contest in one another (the inc-266 contradiction detector scoped to the set). Tier 2 (opt-in, egress-gated): the LLM proposes **cross-paper** critique candidates through the #13 verbatim bar; the anchor paper is chosen deterministically by which set paper contains the quote; `related_paper_ids` (new guarded `related_paper_ids_json` column, migration 0045) is the model's framing, not a verified link. New endpoints `POST/GET /critical-read/set` (2–12 ids). New modal `08y_critical_set.jsx` launched from a shown synthesis ("Critically review these sources") or the library bulk bar ("critical read").
- **Why:** backlog #12 — when citing several papers *together*, review them as a set: cross-paper contradictions + a per-paper fact-matrix, so a skeptical synthesizer can weigh the sources before trusting a synthesis. A signal, never a verdict.
- **Honesty (#9 / #13 / A-A):** no composite score / ranking (guard tests assert the banned key set absent); facts vs. amber candidates distinct; only the anchor quote is #13-verified; egress default-off (egress-off ⇒ honest `unavailable`, Tier-1 still completes); critique of claims + methods, never the authors. Security audit PASS; QA route 71 → 0 uncovered API/FE.
- **Verify:** `pytest tests/test_critical_review_set.py` 11 passed; full suite green; `build_surface_map.py check` 0 uncovered; ruff + line-budget clean. **Manual/visual click-through of the modal still owed** (no browser automation in repo; script in INCREMENT-271-NOTES).
- **Revert:** restore the listed files from git (branch `feature/multi-paper-critical-review`); migration 0045 is additive (a stale `related_paper_ids_json` column is harmless).

## 2026-07-15 — statcheck (e): group header chips by KIND — signals vs your review queue
- **Files:** `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/styles.css`, `.claude/DESIGN.md`, rebuilt `callosum-app.html`.
- **What:** the library-header filter chips now render in two divided `.lib-chip-group` clusters: **check signals** (amber/red — statcheck `⚠ flagged`, retraction `⚠ retracted`) vs **your review queue** (indigo — findings `📋 to review`, transparency `🔎 open data not detected`), separated by a thin `--line` rule. Also fixed the copy overload: the statcheck `flagged` tooltip no longer calls itself *"a list to review"* (it's *"a signal to inspect… distinct from your review queue"*), and `to review` is labeled *"your review queue, separate from the check signals."*
- **Why:** backlog #45-adjacent statcheck **(e)** — the "⚠ flagged" (signal) vs "📋 to review" (work-state) duality confused the "what's wrong with these numbers" citer, worsened by the flagged tooltip literally saying "a list to review." Clarify-not-collapse (honors inc-133's deliberate coexistence). The colors already carried the distinction; grouping makes it read at a glance.
- **Honesty (#9 / A-A):** `open data not detected` stays in the **queue** group (a go-look work-state), never "signals" — grouping it as a detection would drift toward a "hides data" verdict (the no-accusation boundary). DESIGN.md updated with the grouping convention.
- **Verify:** frontend assembly + design-drift tests green; grouping + new copy present in the built HTML, old conflating copy gone. **Manual/visual check of the grouped chips still owed** (rule #3 follow-up).

## 2026-07-15 — Enrich job shows per-item titles in its progress label (backlog #4)
- **Files:** `app/backend/api/routers/library_enrich.py` (NEW — `_enrich_progress_label` + `_run_metadata_enrich_job` + the two `/library/enrich/refresh` endpoints + models), `app/backend/api/routers/library.py`, `app/backend/api/app.py`, `tests/test_metadata_multi_enrich.py`.
- **Rule #1 split:** the #4 addition pushed `library.py` to 617 (over the 600 cap — caught by the CI line-budget gate, not the `--no-verify` local commits). Extracted the whole self-contained metadata-enrich cluster → new sibling router `library_enrich.py` (111), mounted beside `library.router` in `app.py` — the inc-226 `paper_enrich.py` pattern; `library.py` back to **528**. `library_enrich` reuses `library`'s `JobProgressOut`/`_progress_out` via a one-way import (no cycle).
- **What:** the library-wide metadata-enrich job's progress label now names the paper being enriched (`"Enriching {title}"`, bounded to 60 chars) instead of a generic *"Enriching metadata"* — like the scan job already shows each filename. Falls back to the generic label for a title-less scaffold.
- **Why:** backlog **#4** remaining ("a per-item title in the import/embed/enrich progress label"). The enrich job is the clearest per-item win (it loops live papers with real titles); the embed phases only get `(i, n)` and are fast, so they keep counts. Unit-tested pure label helper.

## 2026-07-15 — Honest region-precision copy (precise-highlighting follow-up)
- **Files:** `app/frontend/js/00_lib.jsx` (`precisionText` badge + the `applyPdfCitationTarget` region note), rebuilt `callosum-app.html`.
- **What:** reworded the region-precision copy from *"precise highlight pending"* → *"exact passage not located"* (badge) and *"Precise passage highlight is pending."* → *"The exact passage couldn't be located in this PDF, so its page is shown."* (on-PDF note).
- **Why:** inc-270 lifted the exact-highlight hit-rate to ~95%, so "pending" now mis-implies a missing feature. `region` means the exact passage genuinely couldn't be located (garbled/ambiguous source) — the copy now says that truthfully.

## 2026-07-14 — Increment 270: precise-highlighting locator — reading-order word reconstruction
- **Files:** `app/backend/pdf_processing/quote_matching.py` (`_word_tokens_for_pdf`), `tests/test_pdf_processing.py` (new two-column regression test).
- **What:** `locate_quote` reconstructs each PDF page from `page.get_text("words")` ordered by **reading order `(block, line, word)`** instead of PyMuPDF's geometric `sort=True`. Geometric sort orders words purely top-to-bottom / left-to-right, so it splices other-column or floating text into the middle of a passage (e.g. an extra "creative" wedged into a sentence), making a quote that is verbatim in its chunk fail to locate → the citation fell back to `region` ("precise highlight pending"). Reading order matches how chunk text is extracted, so the quote stays a contiguous substring.
- **Impact (measured on the real library, 167 stored citations with local PDFs):** exact-highlight hit-rate **53% → ~95%** (locate-found 89 → 159); the residual ~5% are garbled source text (a mis-decoded en-dash `253�258`, a spaced URL, a spaced-hyphen title) that honestly stay `region`. **Zero** off-page/false matches introduced. Coordinates unchanged (rectangles come from each token's own bbox; ordering only affects the matching string).
- **Honesty (#2):** a blanket "strip to alphanumerics" match was prototyped for the last ~5% and **rejected** — it broke three existing honesty tests that deliberately keep significant hyphens (`5-HT` ≠ `5HT`, `anti-inflammatory` ≠ `antiinflammatory`). Region is the truthful answer when the source text can't be confidently located. Measured with a read-only scratch probe (`.claude/highlight_diag.py`) that re-runs `locate` over stored evidence quotes.
- **Why:** Cliff's "precise highlighting" ask. The machinery was already built end-to-end (and Codex extended exact anchoring across the Methods pane in PR #5); the gap was the locator's hit-rate. This locator fix lifts summary citations now and every Methods evidence surface.
- **Follow-ups:** the frontend region label still reads "precise highlight pending" — now that precise highlighting works ~95%, reword to "exact passage not located" (small `00_lib.jsx` copy change + rebuild). Optionally promote the scratch probe into `tools/validation_harness.py` as a standing precision-rate metric.
- **Revert:** restore the single `words = page.get_text("words", sort=True)` line in `_word_tokens_for_pdf`.

## 2026-07-14 — Codex review round 2: text-health reprocess now re-embeds its chunks
- **Files:** `app/backend/pdf_processing/ingest.py`, `app/backend/api/routers/text_health.py`, `app/backend/api/routers/papers.py`, `tests/test_text_health.py`, `.claude/security-audits/2026-07-13_reprocess-pdf-text.md`.
- **What:** deep-reviewed the remaining spot-checked Codex surfaces before merge. **beyond-library citation suggest** and the **`StatResult.context`** evidence surface reviewed **CLEAN** (opt-in + egress-disclosed + abstract-level-stance-labeled-weaker; and a bounded, honestly-labeled "Context" snippet respectively). Found one **MEDIUM** bug in **text-health reprocess**: `reprocess_pdf_attachment` deleted the old chunks' vector embeddings and wrote new chunks but never **re-embedded** them, so a reprocessed paper silently dropped out of vector-search retrieval (find-related, gap-finder, axis scoring, library-wide citation suggest) until re-embedded. Fixed by threading the embedding model through both callers and calling `embed_chunks` on the new chunk ids (idempotent). Behavioral test asserts every reprocessed chunk gets an embedding row; reprocess audit corrected.
- **Why:** Codex's blob quality was uneven (funding shipped fabricated data); the reprocess maintenance action must not degrade a paper it is meant to improve.
- **Revert:** drop the `embed_chunks` call + `embedding_model` param in `reprocess_pdf_attachment` and the two accessors.

## 2026-07-14 — Trust-but-verify review of Codex's funding + reference-integrity work
- **Files:** `app/backend/funding/providers.py`, `app/backend/api/routers/funding.py`, `app/backend/metadata/paper_merge.py`, `app/backend/funding/triage_repo.py`, `tests/test_funding_discovery.py`, `tests/test_pcurve.py`, `.claude/security-audits/2026-07-14_text-document-ingest.md`.
- **What:** reviewed the uncommitted Codex feature blob (funding discovery, meta reference list, + adjacent, incs 267–269+) and fixed the defects it shipped: (1) **CRITICAL honesty** — Funding Discovery's production award fallback was `FixtureAwardHistoryProvider()`, which surfaced six hardcoded fake foundations as real `irs_990_pf` prospects; replaced with a `NullAwardHistoryProvider` (zero awards) and deleted `default_awards()`, added a no-seam regression test. (2) **un-merge reversibility regression** — the inc-269 duplicate-DOI change dropped `"doi"` from `_UNIQUE_ID_COLS`, and since `_SURVIVOR_SNAPSHOT_COLS` splats that tuple, un-merge silently stopped restoring the survivor's adopted DOI; `"doi"` is now listed explicitly. (3) **p-curve** — Codex's new required `StatResult.context` field wasn't threaded into `test_pcurve.py`. (4) CI: a `B023` late-binding closure in `triage_repo.py`, a `papers.py` import sort, and 16 files failing `ruff format --check` — all cleaned. Added the missing security-audit stub for the non-PDF text-document ingest path.
- **Why:** Codex's own audits claimed PASS/green, but the blob shipped a fabricated-data default and was not green (3 failing tests) nor CI-clean (ruff). Real, honesty-invariant-breaking bugs a green *subset* hid.
- **Verify:** full `pytest` **1187 passed, 1 skipped**; `ruff check .` + `ruff format --check .` clean; line-budget gate clean. Committed on branch `review/codex-funding-reference-integrity` as commit 2 (Codex's blob is commit 1).
- **Revert:** restore the six files from commit 1's versions; re-add `default_awards()`.

## 2026-07-13 — Per-paper tag locks and Details split

- **Files:** `app/frontend/js/25_detail.jsx`, `app/frontend/js/25a_detail_actions.jsx`, `app/frontend/js/25b_tags.jsx`, `app/frontend/styles.css`, `app/backend/persistence/schema.py`, `app/backend/persistence/tags_repo.py`, `app/backend/api/routers/paper_models.py`, `app/backend/api/routers/papers.py`, `app/backend/api/routers/tags.py`, `alembic/versions/0044_paper_tag_locks.py`, `tests/test_tags.py`, `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_20_tags.md`, `.claude/docs/INCREMENT-BACKLOG.md`, rebuilt frontend, and change log.
- **What:** split self-contained Details action widgets into `25a_detail_actions.jsx`, then added per-paper tag locks. A locked tag hides the remove control until unlocked, and deletion is rejected server-side if the link is locked.
- **Why:** Details needed headroom before adding more tag UI, and the remaining tag-provenance follow-up needed a scoped way to protect a tag on one paper without creating a global whitelist.
- **Boundaries:** locks are scoped to the paper-tag link. No global tag identity, imported-keyword suppression rule, provider import behavior, tag color semantics, ratings, axes, or paper metadata changed.
- **Help:** no served-help corpus change.
- **Verify:** tag tests, frontend assembly/design checks, startup migration check, line-budget gate, QA surface-map gate, and diff check pass.

## 2026-07-13 — Re-resolve metadata change notice

- **Files:** `app/frontend/js/25_detail.jsx`, `tests/test_frontend_assembly.py`, `.claude/docs/INCREMENT-BACKLOG.md`, rebuilt frontend, and change log.
- **What:** the Details-pane re-resolve action now compares the visible paper detail before and after the provider response and reports changed displayed fields plus newly added keyword tags in the existing inline note.
- **Why:** force re-resolve can overwrite bibliographic fields and import keyword tags; users should see what changed instead of inferring it from the refreshed form.
- **Boundaries:** frontend feedback only. No provider query, metadata merge rule, tag suppression, persistence schema, retraction check, or positive verification state changed.
- **Help:** no served-help corpus change.
- **Verify:** frontend assembly/design checks, paper route tests, line-budget gate, QA surface-map gate, and diff check pass.

## 2026-07-13 — Library header mobile action wrap

- **Files:** `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, `.claude/docs/INCREMENT-BACKLOG.md`, rebuilt frontend, and change log.
- **What:** hardened the Library header action row so Add, saved-search, warning, and utility controls wrap within narrow panes instead of overflowing horizontally.
- **Why:** the Library header can accumulate many action chips; mobile/read-only-width surfaces need every control reachable without horizontal scroll.
- **Boundaries:** CSS/layout only. No Library filtering, citation-count refresh, saved-search, warning-chip, provider, or persistence behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** frontend assembly/design checks, line-budget gate, QA surface-map gate, and diff check pass.

## 2026-07-13 — Saved funding visible-row bulk actions

- **Files:** `app/frontend/js/08l_funding_saved.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend, and change log.
- **What:** added display-scoped bulk workflow controls for the currently visible saved funding rows: mark visible reviewing and archive visible, with an explicit visible-item count.
- **Why:** saved funding filters and sorts create bounded work queues; users need a compact way to move the visible subset through lightweight workflow states.
- **Boundaries:** saved marker workflow state only. No canonical funding records, provider refreshes, evidence, exports, recommendations, opportunity status, or eligibility behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Funding Discovery saved-filter visual polish

- **Files:** `app/frontend/styles.css`, rebuilt frontend, `.claude/funding-ui-pass-desktop.png`, `.claude/funding-ui-pass-saved-queue.png`, `.claude/funding-ui-pass-narrow.png`, and change log.
- **What:** live Funding Discovery UI pass found saved-funding filter chips wrapping one letter per line in the narrow Theory pane; added a Funding-specific chip flex override so saved and result filter chips wrap at natural compact widths.
- **Why:** the saved funding queue should remain scannable after adding filters, sort controls, and row summaries.
- **Boundaries:** CSS/layout only. No filtering semantics, sorting semantics, provider calls, saved records, workflow states, exports, or funding evidence changed.
- **Help:** no served-help corpus change.
- **Verify:** live Chromium pass on validation DB showed no horizontal overflow or console errors; temporary saved markers were created for inspection and removed afterward. Funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Saved funding sort controls

- **Files:** `app/frontend/js/08l_funding_saved.jsx`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend, and change log.
- **What:** added display-only sort controls to the **Saved funding** queue: recently saved, deadline soon, changed-since-saved first, workflow state, open/current first, and archived last.
- **Why:** saved funding now has filters and queue cues; sorting lets the saved list function as a lightweight work queue without changing saved records.
- **Boundaries:** frontend display ordering only. No saved-item schema, workflow state, refresh logic, provider calls, exports, or canonical funding records changed.
- **Help:** no served-help corpus change.
- **Verify:** funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Saved funding row queue summaries

- **Files:** `app/frontend/js/08l_funding_saved.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend, and change log.
- **What:** saved funding rows now show compact queue cues before expansion: current/opportunity/prospect status, workflow state, next deadline or linked opportunity, and refresh-change cues.
- **Why:** the saved funding queue should be scannable without forcing users to expand every saved item.
- **Boundaries:** display-only frontend summary. No saved-item schema, refresh logic, workflow semantics, provider queries, exports, canonical funding records, or eligibility behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Saved funding queue filters

- **Files:** `app/frontend/js/08l_funding_saved.jsx`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend, and change log.
- **What:** updated the **Saved funding** queue with display-only filters for **Open / current**, **Prospects**, **Needs review**, **Changed since saved**, **Provider issue**, **No current window**, **Applying / planning**, and **Archived**.
- **Why:** saved funding items need quick workflow and refresh-state slices so the review queue stays usable without becoming a full grant CRM.
- **Boundaries:** frontend filtering only. No saved-item persistence schema, refresh logic, provider queries, canonical funding records, exports, or workflow-state semantics changed.
- **Help:** no served-help corpus change.
- **Verify:** funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Funding Discovery review-oriented filters

- **Files:** `app/frontend/js/08jz_funding_helpers.jsx`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend, and change log.
- **What:** added display filters for **Eligibility review**, **No current surface**, **Identity uncertain**, and **Stale AI-fit** to the Funding Discovery result pool.
- **Why:** the fit-triage panels surface review concerns; users need quick slices for those concerns without changing ranking, exports, saved state, or opportunity/prospect/scheme semantics.
- **Boundaries:** frontend filtering only. No provider queries, persistence, ranking, eligibility assessment, LLM triage, CSV export fields, or saved funding behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Funding Discovery fit triage panels

- **Files:** `app/frontend/js/08jz_funding_helpers.jsx`, `app/frontend/js/08m_funding_results.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend, and change log.
- **What:** Funding Discovery result cards now include a display-only triage panel that separates **Why this surfaced** from **What may need review**, including evidence class, existing signal strength/facets, eligibility evidence, identity uncertainty, missing current application surfaces, and stale AI-fit labels when present.
- **Why:** users need a faster way to distinguish plausible latent fit from review concerns without collapsing Funding Discovery into a recommendation score.
- **Boundaries:** frontend evidence summary only. It does not change provider queries, persistence, ranking, eligibility assessment, saved state, CSV exports, opportunity status, or LLM triage behavior.
- **Help:** no served-help corpus change.
- **Verify:** funding tests, frontend assembly/design checks, line-budget gate, QA surface-map gate, diff check, and verdict-language scan pass.

## 2026-07-13 — Inline Synthesis source-text diagnostics

- **Files:** `app/frontend/js/19_synthesis_failures.jsx`, `app/frontend/js/20_synthesis.jsx`, `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_55_synthesis_verification.md`, rebuilt frontend, and change log.
- **What:** Synthesis now shows a compact source-text diagnostic when a run fails from missing/retrieval source chunks or finishes with zero source chunks. Selected-paper runs summarize scoped Text Health signals such as no local PDF, no extracted text, stale extraction, missing section labels, and tiny text; query runs explain that no source chunks matched the query or active section filter.
- **Why:** users can see the likely retrieval/text-extraction cause before opening the full Text Health evidence queue.
- **Boundaries:** diagnostic UI only. It reuses the existing Text Health overview endpoint; no retrieval logic, extraction/OCR behavior, verifier thresholds, summary persistence, egress behavior, or backend schema changed.
- **Help:** no served-help corpus change.
- **Verify:** frontend assembly/design checks, line-budget gate, and QA surface-map gate pass.

## 2026-07-13 — Scoped Text Health reprocess for Synthesis

- **Files:** `app/frontend/js/26b_text_health.jsx`, `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_55_synthesis_verification.md`, rebuilt frontend, and change log.
- **What:** Text Health now shows **Reprocess scoped papers** when opened from Synthesis, limited to the synthesis-source papers that have missing section labels or stale extraction.
- **Why:** the recovery path can now fix only the papers relevant to the failed synthesis before offering **Retry synthesis**.
- **Boundaries:** frontend orchestration only. It reuses the existing selected-paper text reprocess endpoint; no OCR, metadata mutation, network call, extraction semantics, verifier behavior, or persistence schema changed.
- **Help:** no served-help corpus change.
- **Verify:** frontend assembly/design checks, line-budget gate, and QA surface-map gate pass.

## 2026-07-13 — Scoped Text Health handoff from Synthesis

- **Files:** `app/frontend/js/20_synthesis.jsx`, `app/frontend/js/26b_text_health.jsx`, `app/frontend/js/40_app.jsx`, `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_55_synthesis_verification.md`, rebuilt frontend, and change log.
- **What:** when Synthesis routes the user to Text Health, the modal now carries the synthesis context: selected-paper syntheses open Text Health scoped to those source papers, can toggle back to the full text-health queue, and offer **Retry synthesis** after reprocessing completes.
- **Why:** a missing-source-text synthesis failure should lead directly to the relevant local maintenance queue and then back to the same synthesis request.
- **Boundaries:** frontend handoff only. No extraction/OCR behavior, backend API, verifier thresholds, generation prompt, persistence, or egress behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** frontend assembly/design checks, line-budget gate, and QA surface-map gate pass.

## 2026-07-13 — Actionable synthesis failure recovery

- **Files:** `app/frontend/js/19_synthesis_failures.jsx`, `app/frontend/js/20_synthesis.jsx`, `app/frontend/js/40_app.jsx`, `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_55_synthesis_verification.md`, rebuilt frontend, and change log.
- **What:** replaced the generic synthesis error box with classified recovery states for AI/egress setup, provider failures, malformed cached citation ids, and missing source-text cases. Recovery actions can open Settings, repair the synthesis cache and retry the same request, open Text Health, or retry.
- **Why:** synthesis failures should point to the next bounded action instead of leaving the user with a raw exception.
- **Boundaries:** frontend recovery/routing only. No verifier thresholds, source retrieval, summary persistence, evidence semantics, egress gate, or provider behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** frontend assembly/design checks, line-budget gate, and QA surface-map gate pass.

## 2026-07-13 — Explicit synthesis-cache repair action

- **Files:** `app/backend/llm/cache.py`, `app/backend/api/routers/settings.py`, `app/frontend/js/35_settings.jsx`, `tests/test_llm_cache.py`, `.claude/qa-routes/route_35_settings.md`, rebuilt frontend, and change log.
- **What:** added a Settings → Local maintenance action that scans cached synthesis-generation rows and deletes only malformed summary-cache payloads, reporting scanned/removed counts.
- **Why:** the automatic malformed-cache recovery fixes the active generation path; this gives the user an explicit local repair action for stale bad cache rows already sitting in SQLite.
- **Boundaries:** summary-generation cache only. No saved syntheses, verified citations, evidence quotes, chunks, verifier thresholds, egress behavior, or paper/library records are changed.
- **Help:** no served-help corpus change.
- **Verify:** cache tests, frontend assembly/design checks, line-budget gate, and QA surface-map gate pass.

## 2026-07-13 — Synthesis cache malformed citation-id recovery

- **Files:** `app/backend/llm/cache.py`, `tests/test_llm_cache.py`, and change log.
- **What:** malformed cached synthesis generation payloads with non-numeric citation chunk ids, such as `chunk_1`, are now treated as cache misses. The bad row is deleted and generation is retried instead of surfacing a raw `ValueError`.
- **Why:** cached model output is not authoritative evidence; local verification still needs real chunk ids, and a bad cached candidate should not block synthesis.
- **Boundaries:** generation cache behavior only. No verifier thresholds, citation evidence semantics, prompt construction, egress gate, or UI behavior changed.
- **Help:** no served-help corpus change.
- **Verify:** `py_compile` on `app/backend/llm/cache.py`, `pytest -q tests/test_llm_cache.py tests/test_summaries.py`, line-budget gate, and `git diff --check` pass.

<!-- HELP-DOCS-SYNCED 2026-07-13 — help corpus updated for stale Funding Discovery AI-fit label handling. Nothing above this line has an un-synced corpus change. -->
## 2026-07-13 — Stale Funding Discovery AI-fit labels

- **Files:** `app/backend/funding/triage_repo.py`, `app/backend/funding/export.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08m_funding_results.jsx`, `app/backend/help/help_content.md`, `tests/test_funding_discovery.py`, and change log.
- **What:** AI-fit annotations now compare their persisted evidence fingerprint with the current reloaded/exported item evidence and mark the annotation `stale` when the evidence changed.
- **Why:** model labels should remain inspectable, but users need to know when a label was based on earlier opportunity/prospect evidence.
- **Boundaries:** stale labels do not hide items, rerank results, rerun models, mutate saved items, refresh providers, or create recommendations/probabilities.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** `py_compile` on changed backend modules, `pytest -q tests/test_funding_discovery.py tests/test_help.py tests/test_frontend_assembly.py tests/test_design_drift.py`, frontend rebuild, line-budget gate, QA surface-map gate, and `git diff --check` pass.

## 2026-07-13 — Funding Discovery result chunk split

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/js/08m_funding_results.jsx`, `tests/test_funding_discovery.py`, `.claude/qa-routes/route_69_funding_discovery.md`, rebuilt frontend artifact, and change log.
- **What:** moved Funding Discovery result-card, evidence-detail, filter/sort, and result-summary rendering helpers out of the stateful panel chunk into a new adjacent result-rendering chunk.
- **Why:** `08k_funding_discovery.jsx` was at 598/600 lines after the Recent runs UI; this split preserves behavior while restoring room for future Funding Discovery work.
- **Boundaries:** refactor only. No provider, persistence, matching, save, export, LLM triage, eligibility, warning, or UI behavior change intended.
- **Help:** no served-help corpus change.
- **Verify:** `pytest -q tests/test_funding_discovery.py tests/test_frontend_assembly.py tests/test_design_drift.py`, frontend rebuild, line-budget gate, QA surface-map gate, and `git diff --check` pass.

## 2026-07-13 — Funding Discovery Recent runs reload UI

- **Files:** `app/backend/funding/run_report.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/js/08l_funding_saved.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_69_funding_discovery.md`, `tests/test_funding_discovery.py`, and change log.
- **What:** added a bounded recent-run summary endpoint and a Theory-pane **Recent runs** disclosure that reloads a completed Funding Discovery run into the normal result lanes, preserving persisted source coverage, saved markers, CSV export, and AI-fit labels.
- **Why:** the previous persistence work made run reload possible; the UI now exposes it so users can return after refresh/restart without re-running discovery.
- **Boundaries:** reload is read-only and per-run; it does not refresh providers, mutate saved items, create recommendations, or convert prospects/schemes into opportunities.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** `py_compile` on changed backend modules, `pytest -q tests/test_funding_discovery.py tests/test_help.py tests/test_frontend_assembly.py tests/test_design_drift.py`, frontend rebuild, line-budget gate, QA surface-map gate, and `git diff --check` pass.

## 2026-07-13 — Persisted Funding Discovery AI-fit labels

- **Files:** `app/backend/persistence/schema_funding.py`, `alembic/versions/0043_funding_llm_triage_annotations.py`, `app/backend/funding/triage_repo.py`, `app/backend/funding/run_report.py`, `app/backend/funding/export.py`, `app/backend/api/routers/funding.py`, `app/backend/help/help_content.md`, `tests/test_funding_discovery.py`, and change log.
- **What:** persisted Funding Discovery AI-fit annotations per search-run item, added a completed-run reload endpoint, and included the persisted label/rationale/prompt version in CSV export.
- **Why:** AI triage should survive reloads and be exportable without turning a transient browser annotation into a global recommendation or hidden score.
- **Boundaries:** labels remain scoped to the run and item instance; no opportunity/prospect conversion, saved-item mutation, eligibility verdict, funding probability, or recommendation language.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** `py_compile` on changed backend modules, `pytest -q tests/test_funding_discovery.py tests/test_startup_migration.py tests/test_help.py`, line-budget gate, QA surface-map gate, and `git diff --check` pass.

## 2026-07-13 — Post-run Funding Discovery AI fit triage

- **Files:** `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `tests/test_funding_discovery.py`, rebuilt frontend artifact, and change log.
- **What:** added a post-run **Evaluate apparent fit with AI** action for Funding Discovery results, backed by a bounded `/funding-discovery/llm-triage` endpoint that annotates the current surfaced pool without rerunning deterministic discovery. The existing optional pre-run checkbox remains, but model calls now run outside the Funding Discovery database write transaction.
- **Why:** users can first inspect the broad latent-fit pool, then ask the configured model to add advisory fit labels and toggle to the LLM-triaged view without losing the full result set.
- **Boundaries:** no funding probabilities, recommendations, eligibility verdicts, hidden scoring, item deletion, saved-item mutation, schema change, or new provider dependency.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** funding discovery tests, frontend assembly/design checks, line-budget gate, and surface-map gate pass.

## 2026-07-13 — Reference check cache-lock hardening

- **Files:** `app/backend/api/routers/reference_integrity.py` and change log.
- **What:** split Meta Reference List runs into short provider/detector transactions and a separate final persistence transaction, so external metadata cache writes no longer share the long reference-signal write window.
- **Why:** a reference check could fail when an opportunistic `external_api_cache` write hit SQLite writer contention during a run.
- **Boundaries:** no detector semantics, review-state model, warning derivation, UI, schema, or provider behavior changed.
- **Verify:** reference-integrity, API-cache, SQLite-retry, opt-in tool-pane visual drift, and line-budget checks pass.

## 2026-07-13 — Synthesis section filters wrap in the Theory pane

- **Files:** `app/frontend/js/20_synthesis.jsx`, `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, rebuilt frontend artifact, and change log.
- **What:** gave the synthesis section filter strip its own class and made segmented filter controls wrap within the available pane width; synthesis section buttons now use compact wrapping chips so long labels stay visible.
- **Why:** narrow Theory panes could hide later section buttons such as Data availability, Funding, and Ethics off the right edge.
- **Boundaries:** layout-only frontend polish; no synthesis retrieval, verification, saved-summary, or API behavior changed.
- **Verify:** frontend assembly regression and design-drift checks pass.

## 2026-07-13 — Paper router model split

- **Files:** `app/backend/api/routers/paper_models.py`, `app/backend/api/routers/papers.py`, `app/backend/api/routers/paper_urls.py`, `app/backend/api/routers/paper_enrich.py`, and change log.
- **What:** moved paper-route Pydantic request/response models out of `papers.py` into `paper_models.py`, and updated sibling routers to import shared paper models from that module.
- **Why:** `papers.py` was exactly at the 600-line cap after first-class URL rows; this restores headroom for the next Details/file-serving increment.
- **Boundaries:** behavior-preserving refactor only; no schema, route, frontend, help, or migration change.
- **Verify:** targeted paper/health/startup checks and line-budget gate pass.

## 2026-07-13 — First-class extra URLs in Details

- **Files:** `app/backend/persistence/schema_paper_urls.py`, `alembic/versions/0042_paper_urls.py`, `app/backend/persistence/paper_urls_repo.py`, `app/backend/api/routers/paper_urls.py`, `app/backend/api/routers/papers.py`, `app/backend/api/app.py`, `app/backend/api/routers/paper_edit_input.py`, `app/frontend/js/25c_urls.jsx`, `app/frontend/js/25_detail.jsx`, `app/frontend/styles.css`, `tests/test_papers.py`, `tests/test_frontend_assembly.py`, `tests/test_health.py`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_30_detail_pane.md`, rebuilt frontend, and change log.
- **What:** promoted additional paper URLs from a CSL-only textarea into first-class per-paper URL rows with optional labels, add/remove endpoints, Details-pane row UI, and a compatibility mirror into `csl_json.extra_urls` / `extra_urls`.
- **Why:** real reference records often need more than one link: publisher page, preprint, OSF, data, code, project page, or alternate landing page.
- **Boundaries:** DOI remains the identifier field; primary CSL `URL` remains separate. No network fetch, scraping, metadata overwrite, scoring, or paper-status change.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** targeted paper/url/frontend/help/health checks pass; frontend rebuilt.

## 2026-07-13 — Watched-rescan single-flight and content dedup

- **Files:** `app/backend/api/app.py`, `app/backend/api/routers/library.py`, `app/backend/pdf_processing/library_scan.py`, `tests/test_library_scan.py`, `tests/test_watched_folders.py`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_27_scan_import.md`, and change log.
- **What:** added an app-level single-flight guard shared by manual folder scans and watched-folder rescans, so a second scan-family request reuses the pending/running job instead of spawning another SQLite writer. Strengthened scan unchanged records to expose checksum-based matches across import sources/provenance.
- **Why:** concurrent rescans and foreign-provenance duplicate PDFs were the two fragile spots behind recent lock/duplicate-library reports.
- **Boundaries:** no schema migration, no background daemon, no PDF copying, no egress change, and no change to import/enrichment semantics beyond avoiding duplicate scan-family writers.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** targeted scan/watched-folder/help/health checks pass.

## 2026-07-13 — Paper-card Meta Reference List jump

- **Files:** `app/frontend/js/10d_papercard.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/40_app.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_68_reference_integrity.md`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** made each paper-card **ref signal** badge an accessible jump control that selects the paper and opens the Theory pane directly to **Meta Reference List**; on mobile it switches to the Theory region.
- **Why:** bulk reference review now filters the Library to active reference-signal papers, so the badge should take the reviewer directly to the evidence and review controls.
- **Boundaries:** frontend routing only; no detector, persistence, warning semantics, schema, background job, or paper-quality verdict language changed.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** frontend assembly/help/design/reference smoke checks pass; frontend rebuilt.

## 2026-07-13 — Bulk reference-review Library filter

- **Files:** `app/frontend/js/03_library.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/10b_libmenus.jsx`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_68_reference_integrity.md`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** after a selected-paper **check refs** bulk run, the Library now switches to a clearable **Reference checks** view containing papers with active Meta Reference List signals.
- **Why:** completes the triage loop: select papers, run checks, immediately review affected papers instead of hunting for refreshed badges.
- **Boundaries:** frontend-only filter over existing `/reference-integrity/overview`; no backend query path, detector change, schema migration, auto-run, or positive verification state.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** frontend/help/design checks pass; frontend rebuilt.

## 2026-07-13 — Bulk Meta Reference List checks

- **Files:** `app/backend/api/routers/reference_integrity.py`, `app/frontend/js/03_library.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/10b_libmenus.jsx`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_68_reference_integrity.md`, `tests/test_reference_integrity.py`, `tests/test_frontend_assembly.py`, `tests/test_health.py`, rebuilt frontend, and change log.
- **What:** added a selected-paper bulk action, **check refs**, that starts `POST /reference-integrity/run-selected`, skips selected no-DOI papers visibly, runs the existing per-paper Meta Reference List checker for DOI-backed papers, and refreshes paper-card reference warning badges when complete.
- **Why:** reference integrity is useful at library-triage scale, especially after imports, but should remain explicit and bounded.
- **Boundaries:** no new detector path, no auto-run on import, no daemon, no schema migration, no positive verification state, and no global reference whitelist.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** reference-integrity/health/frontend/help/design checks pass; frontend rebuilt.

## 2026-07-13 — Meta Reference List run visibility

- **Files:** `app/backend/api/routers/reference_integrity.py`, `app/backend/persistence/reference_integrity_repo.py`, `app/frontend/js/08j_reference_integrity.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `tests/test_reference_integrity.py`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** made reference-integrity runs more inspectable: poll responses now include determinate progress, completed reports expose source coverage and last-checked time, provider failures are reported as partial coverage where fallback can continue, and the UI shows coverage plus a retry control for failed/partial runs.
- **Why:** “Check references” should not feel like a silent black box when Semantic Scholar/OpenAlex/retraction data are slow, empty, or partially unavailable.
- **Boundaries:** no detector verdict semantics changed, no schema migration, no background daemon, no positive reference-quality state, and no composite score.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** targeted reference-integrity/frontend/help checks pass; frontend rebuilt.

## 2026-07-13 — Text Health Library filter

- **Files:** `app/frontend/js/03_library.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/26b_text_health.jsx`, `app/frontend/js/40_app.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_30_detail_pane.md`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** added **Show in Library** for each Text Health modal group. The Library narrows to that paper set with a clearable **Text health:** banner and keeps the filter local to the frontend.
- **Why:** text-health diagnosis should flow into normal library triage without adding a backend query path or mixing it with saved searches.
- **Boundaries:** no schema, OCR, extraction, metadata, or network behavior changed. The filter is ephemeral and clears like axis/tag/signal review views.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** frontend assembly/help/design checks pass; frontend rebuilt.

## 2026-07-13 — Text Health stale extraction group

- **Files:** `app/frontend/js/26b_text_health.jsx`, `app/backend/help/help_content.md`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** exposed the existing `stale_chunk_version` detector as a first-class **Stale extraction version** group in the Text Health modal, including coverage count and per-row reprocess action.
- **Why:** stale extraction provenance is a distinct maintenance signal and should be inspectable separately from missing section labels.
- **Boundaries:** UI/docs only. Backend detection and batch semantics are unchanged; stale rows are reprocessed only when the user explicitly clicks their row action or selects papers in the bulk bar.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** frontend assembly/help/design checks pass; frontend rebuilt.

## 2026-07-13 — Text Health routes OCR candidates to Details

- **Files:** `app/frontend/js/26b_text_health.jsx`, `app/frontend/js/40_app.jsx`, `app/backend/help/help_content.md`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** added a **details for OCR** row action for Text Health papers with no extracted text. It selects the paper and opens the right-pane Details section so the existing explicit **OCR this paper (scanned)** control is visible.
- **Why:** Text Health should make likely OCR candidates actionable without automatically OCRing or creating a searchable copy.
- **Boundaries:** navigation/UI only. No OCR execution, extraction, metadata, provider, persistence, or batch-reprocess semantics changed.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** frontend assembly/design/help checks pass; frontend rebuilt.

## 2026-07-13 — PDF text-health drill-down

- **Files:** `app/frontend/js/26b_text_health.jsx` (new), `app/frontend/js/10b_libmenus.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/js/40_app.jsx`, `app/frontend/styles.css`, `app/backend/help/help_content.md`, `tests/test_frontend_assembly.py`, rebuilt frontend, and change log.
- **What:** changed the Library **Text health** button from a direct batch action into an inspectable modal queue grouped by missing section labels, no extracted text, very little text, and no local PDF. Rows show title, chunk count, extracted character count, section-labeled count, and open/reprocess actions where appropriate.
- **Why:** make maintenance signals inspectable before acting; the user should see what Callosum measured rather than trust an opaque batch button.
- **Boundaries:** UI/control-flow only. The existing text-health API, extraction, batch semantics, OCR boundaries, metadata preservation, and no-egress behavior are unchanged.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** frontend assembly/design tests pass; frontend rebuilt.

## 2026-07-13 — PDF text health and batch reprocess

- **Files:** `app/backend/api/routers/text_health.py` (new), `app/backend/api/app.py`, `app/backend/pdf_processing/ingest.py`, `app/backend/api/routers/papers.py`, `app/frontend/js/10b_libmenus.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `app/backend/help/help_content.md`, `tests/test_text_health.py`, `tests/test_frontend_assembly.py`, QA route, security audit, rebuilt frontend, and change log.
- **What:** added deterministic PDF text-health counts and async reprocessing jobs. The Library header now shows **Text health** and can reprocess local PDFs whose chunks are missing section labels; the selected-paper bulk bar adds **reprocess text** for an explicit checked set.
- **Why:** make the new section-aware extraction useful across existing libraries without forcing one-paper-at-a-time cleanup.
- **Boundaries:** no schema change, OCR, metadata overwrite, attachment replacement, provider call, LLM call, hidden scoring, or paper-status mutation. No-chunk/scanned candidates are counted but not silently OCR'd. Existing chunks are preserved if a reprocess attempt would replace them with an empty extraction.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** targeted text-health tests pass; frontend/help/design and health-route tests pass; frontend rebuilt; ruff, line-budget, and QA surface-map checks pass.

## 2026-07-13 — Details-pane PDF text reprocessing

- **Files:** `app/backend/persistence/paper_lifecycle_repo.py`, `app/backend/pdf_processing/ingest.py`, `app/backend/api/routers/papers.py`, `app/frontend/js/25_detail.jsx`, `app/backend/help/help_content.md`, `tests/test_pdf_processing.py`, security audit, and change log.
- **What:** added a per-paper **Reprocess PDF text** action for local PDFs that already have extracted chunks. It re-runs the existing PyMuPDF extraction/chunking path, including section labels, and replaces only chunks for the selected primary PDF attachment.
- **Why:** older PDF imports can now pick up newer extraction metadata without re-importing or disturbing bibliographic metadata, files, tags, highlights, notes, or annotations.
- **Boundaries:** no schema change, no PDF upload/egress, no OCR, no metadata overwrite, no attachment replacement, no hidden scoring, and no changes to synthesis/statcheck/reference/funding semantics. Stale chunk embeddings and vectors for the replaced attachment are removed before new chunks are written.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** targeted PDF processing and paper-route tests pass; frontend rebuilt; frontend/help/design tests, ruff,
  line-budget, and QA surface-map checks pass.

## 2026-07-13 — Section-filtered synthesis retrieval

- **Files:** `app/backend/summarization/generators.py`, `app/backend/summarization/pipeline.py`, `app/backend/api/routers/summaries.py`, `app/frontend/js/20_synthesis.jsx`, `app/backend/help/help_content.md`, `tests/test_summaries.py`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and change log.
- **What:** added optional section filters to Synthesis retrieval. Users can leave the filter at All or narrow retrieval to section-aware chunks such as Methods, Results, Discussion, Data availability, Funding, or Ethics. Completed summaries report the active section filter and retrieved source-chunk count.
- **Why:** let users steer synthesis toward the kind of evidence they want to inspect without changing verification thresholds or implying stronger support.
- **Boundaries:** no schema, extraction, embeddings, vector scoring, NLI, quote-location, confidence thresholds, summary status semantics, funding, reference-integrity, or methods-QA behavior changed. The filter narrows eligible source chunks only.
- **Help:** served help corpus updated and sync marker moved.
- **Verify:** targeted summary/frontend/help tests pass; adjacent summarization/cache/reverify tests pass; frontend rebuilt; ruff, design-drift, line-budget, and QA surface-map checks pass.

## 2026-07-13 — Section labels on evidence locations

- **Files:** `app/backend/methods/statcheck.py`, `app/backend/api/routers/methods.py`, `app/backend/api/routers/summaries.py`, `app/frontend/js/00_lib.jsx`, `app/frontend/js/06_methods_statcheck.jsx`, `app/frontend/js/20_synthesis.jsx`, `tests/test_statcheck.py`, `tests/test_summarize_selected.py`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and change log.
- **What:** propagated existing chunk `section` metadata into statcheck and synthesis evidence payloads and rendered section-aware location labels such as `Methods · p. 4` while preserving page-only fallbacks.
- **Why:** make bounded evidence and highlights easier to interpret by exposing deterministic document context without altering verification status, confidence, ranking, or warning behavior.
- **Boundaries:** no schema, extraction, quote-location, NLI, confidence thresholds, paper status, funding, reference-integrity, or methods detector semantics changed. Section labels are provenance/context only.
- **Help:** reviewed; no served help update needed because the workflow is unchanged and the visible addition is contextual metadata in existing evidence cards.
- **Verify:** targeted statcheck/synthesis/frontend tests pass; adjacent summarization/overview/annotation/PDF tests pass; frontend rebuilt; ruff, design-drift, line-budget, and QA surface-map checks pass.

## 2026-07-13 — Section-aware PDF chunks

- **Files:** `app/backend/pdf_processing/sections.py`, `app/backend/pdf_processing/extraction.py`, `tests/test_pdf_processing.py`, and change log.
- **What:** added conservative deterministic section-heading detection during PDF chunk drafting and now persists recognized section labels through the existing chunk `section` field.
- **Why:** give downstream evidence/highlight workflows bounded section context without changing the PyMuPDF extraction backend or adding a parallel document model.
- **Boundaries:** no schema, API, frontend, egress, OCR, quote-location, funding, reference-integrity, methods-QA, or Journal Search behavior changed. Heading detection is exact-alias based and intentionally conservative.
- **Help:** reviewed; no served help update needed because this is extraction metadata, not a new user workflow or visible control.
- **Verify:** `pytest -q tests/test_pdf_processing.py`; adjacent transparency/document/OCR tests pass; `ruff check`; line-budget and QA surface-map checks pass.

## 2026-07-12 — Increment 299: Close frontend QA surface-map gaps

- **Files:** `.claude/qa-routes/route_00_smoke_readonly.md`, `.claude/qa-routes/route_33_methods_statcheck.md`, and change log.
- **What:** closed the remaining frontend checklist gaps by assigning existing exercised surfaces to the right QA routes: route 00 now claims and explicitly walks `10d_papercard.jsx`; route 33 now claims the shared `00_lib.jsx` evidence-quote primitive used by statcheck source/context evidence.
- **Why:** after the runtime visual-drift route, the only uncovered frontend surfaces were paper-card interactions and the shared evidence quote button. The route map now reflects the actual QA responsibilities.
- **Boundaries:** QA documentation only. No product behavior, styling, API, provider, persistence, funding, reference-integrity, methods detector, or Journal Search behavior changed.
- **Help:** reviewed; no served help update needed because user-visible behavior is unchanged.
- **Verify:** `python tools/qa/build_surface_map.py check` reports 228/228 API surfaces and 1043/1043 frontend surfaces covered, 0 uncovered.

## 2026-07-12 — Increment 298: Runtime tool-pane visual drift route

- **Files:** `tests/e2e/test_smoke.py`, `.claude/qa-routes/route_70_tool_pane_visual_drift.md` (new), `app/frontend/styles.css`, `callosum-app.html`, and change log.
- **What:** added an opt-in Playwright visual-drift pass that walks visible THEORY and METHODS accordion sections at desktop and mobile widths, checking document/pane horizontal overflow, accordion-header visibility, and console/page errors. Added QA route 70 so the supervisor has the same visual-drift contract with screenshot deposit instructions.
- **Why:** complement the static DESIGN.md drift tests with runtime coverage that catches rendered breakage.
- **Fix:** the new test caught a real mobile Details overflow: the item-type/action row did not wrap at phone width. `.detail-type-row` now wraps controls instead of forcing a horizontal scroll.
- **QA:** route coverage remains complete for API surfaces and the new route claims the saved-funding pane controls, reducing frontend checklist gaps from 27 to 11.
- **Boundaries:** no product behavior, data model, API, provider, persistence, funding ranking, reference-integrity, methods-QA detector, or Journal Search behavior changed.
- **Help:** reviewed; no served help update needed because behavior and visible wording are unchanged.
- **Verify:** static design/frontend tests pass; full opt-in e2e smoke including the new visual pass passes; line-budget and surface-map checks pass.

## 2026-07-12 — Increment 297: Design drift regression tests

- **Files:** `tests/test_design_drift.py` (new), `app/frontend/styles.css`, `callosum-app.html`, and change log.
- **What:** added a deterministic aesthetic-drift test suite keyed to `.claude/DESIGN.md`: the design dictionary must name the enforced rules, normal app chrome cannot introduce raw hex colors outside documented exceptions, inline styles cannot add raw hex chrome colors, and Funding Discovery card type accents must use semantic design tokens.
- **Why:** catch design drift early without brittle screenshot goldens; the first pass caught Funding Discovery's raw purple/green card accents.
- **Fix:** changed Funding Discovery scheme/prospect card accents from raw hexes to `var(--accent)` and `var(--verified)`.
- **Boundaries:** no layout, behavior, provider, persistence, API, funding ranking, reference-integrity, methods-QA, or Journal Search behavior changed. PDF/page overlay raw-color exceptions remain documented and allowed.
- **Help:** reviewed; no served help update needed because behavior and visible wording are unchanged.
- **Verify:** targeted design/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 296: Backlog cleanup for Discover placeholder and QA seed item type

- **Files:** `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/changes.md`, `tests/test_frontend_assembly.py`, and `tests/test_api_helpers.py`.
- **What:** closed two stale backlog items with regression coverage: the THEORY accordion no longer registers the old Discover placeholder, and the shared QA seed helper now produces non-empty `/papers/item-types` data.
- **Why:** both fixes were already present in the code, but the backlog still listed them as pending and the seed fixture lacked direct route coverage.
- **Boundaries:** no product behavior, schema, API contract, styling, persistence, funding, reference-integrity, methods-QA, or Journal Search behavior changed.
- **Help:** reviewed; no served help update needed because user-visible behavior is unchanged.
- **Verify:** targeted frontend/API-helper tests pass; line-budget check passes.

## 2026-07-12 — Increment 295: Funding Discovery helper chunk split

- **Files:** `app/frontend/js/08jz_funding_helpers.jsx` (new), `app/frontend/js/08k_funding_discovery.jsx`, `tests/test_funding_discovery.py`, `callosum-app.html`, and change log.
- **What:** moved pure Funding Discovery display helpers into a preceding helper chunk, including provider coverage labels, signal formatting, grouping helpers, amount formatting, surface matching, triage filtering, and lower-signal prospect detection.
- **Why:** keep `08k_funding_discovery.jsx` well below the 600-line budget so future Funding Discovery work can proceed without brittle edits.
- **Boundaries:** refactor only. No UI behavior, styling, provider, matching, ranking, persistence, save, export, LLM triage, eligibility, or opportunity-resolution behavior changed.
- **Help:** reviewed; no served help update needed because behavior and visible wording are unchanged.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 294: Funding Discovery lower-signal prospect display filter

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and help corpus.
- **What:** the Funding Prospects lane now hides lower-signal prospects by default when every signal is weak/unresolved and no application surface was found. A compact **Show lower-signal prospects** toggle reveals them and reports the count affected by the display-only filter.
- **Why:** reduce review noise in broad Funding Discovery runs without deleting evidence or implying that hidden prospects are irrelevant.
- **Boundaries:** frontend display filter only. Open opportunities and recurring schemes are unaffected; no provider, matching, ranking, persistence, save, export, LLM triage, eligibility, or opportunity-resolution behavior changed.
- **Design:** read `.claude/DESIGN.md`; toggle uses compact token-based form styling.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 293: Funding Discovery grouping drill-down

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and help corpus.
- **What:** grouped Funding Discovery cards now include a **Why grouped?** disclosure listing grouped record IDs, item kind, display title, and signal types, plus the exact-key grouping boundary.
- **Why:** display de-duplication should be inspectable so it never feels like Callosum silently merged evidence.
- **Boundaries:** frontend display disclosure only. No provider, matching, ranking, persistence, save, export, LLM triage, eligibility, or opportunity-resolution behavior changed.
- **Design:** read `.claude/DESIGN.md`; the disclosure uses compact token-based evidence metadata styling.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 292: Funding Discovery display grouping

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and help corpus.
- **What:** Funding Discovery result lanes now group exact duplicate surfaces for display: opportunities group only by provider opportunity ID, recurring schemes by funder+scheme, and prospects by funder/scheme identity. Grouped cards show how many evidence paths/records contributed while keeping run/export records separate.
- **Why:** reduce review noise from the same funder or scheme surfacing through multiple evidence paths without collapsing distinct epistemic classes or application routes.
- **Boundaries:** frontend display grouping only. No provider, matching, ranking, persistence, export, save, LLM triage, eligibility, or opportunity-resolution behavior changed.
- **Design:** read `.claude/DESIGN.md`; grouping note uses existing provenance-token styling.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 291: Funding Discovery source coverage interpretation

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and help corpus.
- **What:** the Source coverage panel now explains what each provider status means for interpretation and includes a **What was not covered** disclosure for major open-data gaps such as licensed philanthropic databases and non-exhaustive funder website/newsletter coverage.
- **Why:** provider success/failure should calibrate the user's interpretation of the result pool without implying that absent results mean absent funding mechanisms.
- **Boundaries:** frontend interpretation only. No provider, search, matching, ranking, persistence, LLM, or export behavior changed.
- **Design:** read `.claude/DESIGN.md`; new coverage labels use existing token-based pill/status recipes.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 290: Funding Discovery evidence drill-downs and saved-refresh polish

- **Files:** `app/backend/funding/irs.py`, `app/frontend/js/{08k_funding_discovery,08l_funding_saved}.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and help corpus.
- **What:** historical funding evidence rows now show UI-safe source metadata, record IDs, award numbers, amount, scheme cues, extraction basis, and source-record links where provenance provides them. Saved funding refresh summaries/history now include compact text status labels for current opportunities, changed items, provider issues, and unresolved current windows.
- **Why:** funding evidence should be inspectable at the source, and saved refresh outcomes should be scannable without relying on color alone.
- **Boundaries:** no matching, ranking, provider, persistence schema, LLM triage, or eligibility behavior changed. Individual 990-PF recipient details remain withheld in the default UI.
- **Design:** read `.claude/DESIGN.md`; new styling uses existing token recipes, provenance/uncertain color semantics, and compact dense rows.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 289: Funding Discovery signal trails

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and help corpus.
- **What:** Funding Discovery signals now include a compact **Signal trail** disclosure showing signal type, categorical strength, matched profile facets, attached evidence row count/source summary, observed years when available, and the signal-specific interpretation boundary.
- **Why:** surfaced opportunities, recurring schemes, and prospects need clearer inspectable evidence without turning latent-fit signals into recommendations or probabilities.
- **Boundaries:** UI disclosure only. No provider, matching, ranking, persistence, LLM triage, eligibility, save workflow, or external-data behavior changed.
- **Verify:** targeted Funding Discovery/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 288: Methods evidence trail disclosures

- **Files:** `app/frontend/js/{00_lib,06_methods_statcheck,08d_methods_bayes,08f_methods_lmm,08g_methods_metaanalysis,08h_methods_transparency}.jsx`, `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** added a shared **Evidence trail** disclosure for Methods evidence. Statcheck, Bayes recompute/checklist/advisory evidence, LMM, meta-analysis reporting, and transparency evidence now expose detector name, matched text, source precision, page, anchor note, and detector boundary/caveat next to the evidence.
- **Why:** source jumps should be inspectable before the user leaves the Methods pane, without turning a signal into a verdict.
- **Boundaries:** UI disclosure only. No detector, source anchoring, scoring, warning-state, persistence, LLM, or egress behavior changed.
- **Verify:** targeted frontend/Methods tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 287: Evidence precision is visible before source jumps

- **Files:** `app/frontend/js/{00_lib,06_methods_statcheck,08d_methods_bayes,08f_methods_lmm,08g_methods_metaanalysis,08h_methods_transparency,20_synthesis}.jsx`, `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** the shared `EvidenceQuote` block now displays a compact precision chip: **exact highlight**, **region**, **page only**, or **no source page**. Synthesis, statcheck, Bayes, LMM, meta-analysis reporting, and transparency pass their source precision into that shared block.
- **Why:** users should know before clicking whether an evidence snippet will draw an exact PDF highlight or only navigate to a region/page.
- **Boundaries:** UI provenance only. No detector, verifier, scoring, warning-state, persistence, LLM, or egress behavior changed.
- **Verify:** targeted frontend/Methods tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-12 — Increment 286: Methods evidence snippets use exact anchors when locatable

- **Files:** `app/backend/methods/evidence_anchors.py`, `app/backend/api/routers/{methods,lmm,metaanalysis,transparency}.py`, `app/frontend/js/{00_lib,08d_methods_bayes,08f_methods_lmm,08g_methods_metaanalysis,08h_methods_transparency}.jsx`, `tests/test_methods_evidence_anchors.py`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** Bayes-factor rows, Bayesian checklist/advisory evidence, mixed-model reporting evidence, meta-analysis reporting evidence, and transparency evidence now carry optional `coordinate_precision` + `bbox_json` from the existing local PDF quote locator. The frontend routes those evidence snippets through the same PDF overlay path as synthesis/statcheck.
- **Why:** Methods evidence should be inspectable at the source with the best locally available anchor while preserving the exact/region distinction.
- **Boundaries:** detectors remain text/page signal producers; endpoint enrichment is interactive-response only. No new detector, score, verdict, persistence migration, LLM, egress, or batch-job coordinate work.
- **Verify:** targeted Methods/frontend tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-11 — Increment 285: Statcheck exact source anchors when locatable

- **Files:** `app/backend/methods/statcheck.py`, `app/backend/api/routers/methods.py`, `app/frontend/js/06_methods_statcheck.jsx`, `tests/test_statcheck.py`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** `/papers/{paper_id}/statcheck` now enriches interactive statcheck rows with `coordinate_precision` and `bbox_json` using the existing local PDF quote locator. Exact highlights are returned only when the matched statistic is found on the page reported by the extracted chunk; otherwise the row remains region/page-level evidence.
- **Why:** make statcheck evidence as easy to inspect as synthesis evidence while preserving the coordinate-honesty contract.
- **Boundaries:** `run_statcheck` remains a pure text detector/recompute engine for batch jobs and p-curve. No new detector, score, verdict, persistence migration, LLM, or egress path.
- **Verify:** targeted statcheck and frontend assembly tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-11 — Increment 284: Evidence quotes route to highlights

- **Files:** `app/frontend/js/00_lib.jsx`, `app/frontend/js/06_methods_statcheck.jsx`, `app/frontend/js/20_synthesis.jsx`, `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** added a shared bounded evidence-quote renderer. Synthesis evidence quotes are clickable and route through the existing source opener, drawing exact PDF highlights only when the verifier supplied exact coordinates. Statcheck context now highlights the matched reported statistic inside the bounded surrounding text while keeping the row's source jump page/region-only.
- **Why:** evidence should be faster to inspect without weakening the coordinate-honesty contract: exact synthesis citations can highlight; statcheck has text context and page location, not exact boxes.
- **Verify:** targeted frontend/statcheck tests pass; frontend rebuilt; line-budget check passes.

## 2026-07-11 — Increment 283: Statcheck rows show source context inline

- **Files:** `app/backend/methods/statcheck.py`, `app/backend/api/routers/methods.py`, `app/frontend/js/06_methods_statcheck.jsx`, `app/frontend/styles.css`, `tests/test_statcheck.py`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** each per-test statcheck result now carries a bounded extracted-text context snippet, returns it from `/papers/{paper_id}/statcheck`, and renders it inline under the matched statistic in the METHODS Statistics check row.
- **Why:** a reporting signal should expose the evidence neighborhood, not make the user infer context from a terse matched string and a page tooltip.
- **Boundaries:** no new detector, no change to p-value recomputation, no exact-coordinate claim, no score/verdict/rank, no persistence migration, no LLM, and no egress. Rows still open the page at region precision.
- **Verify:** targeted statcheck and frontend assembly tests pass; frontend rebuilt; line-budget check passes.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 282 — help corpus updated for inline tag validation feedback. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 282: Inline tag validation feedback

- **Files:** `app/frontend/js/25b_tags.jsx`, `app/frontend/styles.css`, `tests/test_frontend_assembly.py`, `callosum-app.html`, and help corpus.
- **What:** rejected tag add/remove/color operations now surface the existing API error message inline in the paper Details tag row, with `role="alert"`, `aria-invalid`, and `aria-describedby` on the tag input.
- **Why:** invalid tag names or rejected tag changes should not fail silently; the user should see the local validation reason where they are working.
- **Boundaries:** frontend feedback only. No tag validation rule, persistence behavior, provenance behavior, tag scoring, or egress path changed.
- **Verify:** targeted tag/frontend tests pass; frontend rebuilt; line-budget check passes.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 281 — help corpus updated for saved funding filters. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 281: Saved funding filters and counts

- **Files:** `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/js/08l_funding_saved.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and Funding Discovery help/developer docs.
- **What:** split the saved-funding review UI into its own frontend chunk and added compact saved-list filters with counts for all items, needs review, current opportunity found, provider issue, no current window, applying/planning, and archived.
- **Why:** saved prospects, schemes, and opportunities need a small review-queue triage surface once refresh history and workflow states exist.
- **Boundaries:** filters affect only the local saved list view. They do not re-rank funding evidence, create recommendations, change canonical prospect/scheme/opportunity records, run provider refreshes, or add grant-CRM workflow.
- **Verify:** targeted Funding Discovery and frontend assembly tests pass; frontend rebuilt; line-budget check passes.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 280 — help corpus updated for saved funding refresh history. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 280: Saved funding refresh history

- **Files:** `app/backend/persistence/schema_funding.py`, `alembic/versions/0041_saved_funding_refresh_events.py`, `app/backend/funding/saved_repo.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, help/developer docs, and Funding Discovery security audit.
- **What:** added `saved_funding_refresh_events`, wrote one event per saved item during manual saved-funding refresh, returned recent events with saved rows, and showed a compact **Refresh history** in each expanded saved funding item.
- **Why:** saved funding review should distinguish transient provider failures from repeated checks where no current application window was verified.
- **Boundaries:** this is an audit trail for manual refreshes only. It does not add background polling, notifications, watch semantics, provider raw-payload persistence, or a grant CRM.
- **Verify:** `pytest -q tests/test_funding_discovery.py` passed; frontend build and compileall passed.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 279 — help corpus updated for richer saved-funding refresh outcomes. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 279: Saved funding refresh outcome details

- **Files:** `app/backend/funding/saved_repo.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, and Funding Discovery help/developer docs.
- **What:** saved funding refresh now preserves provider outcome labels and the Theory-pane summary distinguishes current opportunity found, status changed, deadline changed, no current application window verified, and provider unavailable. Linked opportunity title, deadline, and source are shown directly in the refresh summary where available.
- **Why:** saved funding refresh should be reviewable evidence, not a terse counter.
- **Boundaries:** the UI remains signal-only: no recommendation language, no reopening forecast, no funding probability, and no hidden score.
- **Verify:** `pytest -q tests/test_funding_discovery.py tests/test_frontend_assembly.py` passed; Ruff and frontend build passed.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 278 — help corpus updated for saved prospect/scheme application-surface refresh. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 278: Saved funding prospects can refresh application-surface evidence

- **Files:** `app/backend/funding/saved_repo.py`, `app/backend/funding/repo.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `tests/test_funding_discovery.py`, help/developer docs, and Funding Discovery security audit.
- **What:** split saved Funding Discovery persistence into `saved_repo.py` and extended **Refresh saved funding** so saved prospects and recurring schemes can run a bounded provider-backed application-surface check using organization/scheme terms. Conservative matches create or update a separate linked `FundingOpportunity` and `ApplicationSurface`; the saved item remains a prospect or scheme.
- **Why:** saved latent prospects should be able to surface newly actionable application evidence without becoming broad web searches or collapsing prospects into opportunities.
- **Boundaries:** no full research text, PDFs, notes, annotations, applicant-sensitive context, unrestricted crawler, or commercial source is used. Matching ignores Callosum's query-echo summary text and accepts only provider title/organization matches.
- **Verify:** `pytest -q tests/test_funding_discovery.py` passed; frontend build passed.

## 2026-07-11 — Increment 277: Bounded SQLite lock retries for short writes

- **Files:** `app/backend/persistence/sqlite_retry.py`, `integrations/api_cache.py`, `app/backend/persistence/paper_lifecycle_repo.py`, `app/backend/persistence/reference_integrity_repo.py`, `app/backend/funding/repo.py`, `tests/test_sqlite_retry.py`, and `tests/test_api_cache.py`.
- **What:** added a small retry helper for transient SQLite `database is locked` errors and applied it to short external-cache writes, paper metadata/state writes, Meta Reference List persistence, and Funding Discovery persistence/saved-item updates.
- **Why:** provider-backed reference/funding/metadata operations should not fail just because a foreground write briefly collides with another SQLite writer.
- **Boundaries:** this does not use global `BEGIN IMMEDIATE`, does not make long background jobs grab write locks up front, and does not turn cache writes into required state. Broad request-transaction retries and long-job transaction splitting remain separate infrastructure work.
- **Verify:** `pytest -q tests/test_sqlite_retry.py tests/test_api_cache.py tests/test_reference_integrity.py tests/test_funding_discovery.py tests/test_metadata_multi_enrich.py` passed; Ruff passed for the touched files.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 276 — help corpus updated for Grants.gov saved-opportunity detail refresh. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 276: Saved funding refresh re-checks Grants.gov opportunities

- **Files:** `app/backend/funding/grants_gov.py`, `app/backend/funding/providers.py`, `app/backend/funding/repo.py`, `app/backend/api/routers/funding.py`, `tests/test_funding_discovery.py`, help/developer docs, and Funding Discovery security audit.
- **What:** saved funding refresh now re-queries saved Grants.gov opportunities by exact `provider_opportunity_id` using Grants.gov `fetchOpportunity`, updates the canonical opportunity when provider-backed status/deadline evidence changed, and then updates the saved marker snapshot.
- **Why:** saved opportunities should notice deadline/status changes without a broad search, web crawler, or background monitoring process.
- **Boundaries:** only saved `opportunity` rows from the supported provider are detail-refreshed; saved `prospect` and `scheme` rows remain snapshot-only until a bounded application-surface refresh adapter exists. Egress is the exact provider opportunity ID, not research text or PDFs.
- **Verify:** `pytest -q tests/test_funding_discovery.py` passed; Ruff, compileall, and frontend build passed.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 275 — help corpus updated for saved-funding refresh. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 275: Funding Discovery saved snapshot refresh

- **Files:** `app/backend/funding/repo.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, help/developer docs, and Funding Discovery security audit.
- **What:** added `POST /funding-discovery/saved/refresh` and a **Refresh saved funding** button. The action re-snapshots saved items from Callosum's current canonical funding records and reports status/deadline changes.
- **Why:** saved funding should be able to notice that a canonical opportunity's status or deadline changed without adding a background daemon or grant-CRM machinery.
- **Boundaries:** this is a bounded manual snapshot refresh, not continuous monitoring and not an unrestricted provider recrawl. It updates only saved marker snapshot fields (`last_checked_at`, `last_known_status`, `last_known_deadline`) and leaves canonical evidence untouched.
- **Verify:** `pytest -q tests/test_funding_discovery.py` passed; compileall and frontend build passed.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 274 — help corpus updated for saved-funding review queue controls. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 274: Funding Discovery saved review queue

- **Files:** `app/backend/funding/repo.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, help/developer docs, and Funding Discovery security audit.
- **What:** saved funding rows are now expandable review items. A saved row shows status/deadline/source snapshots and lets the user edit an allowlisted workflow state plus notes through `PATCH /funding-discovery/saved/{saved_item_id}`.
- **Why:** saved opportunities/schemes/prospects should be useful as a lightweight review queue without becoming a grant CRM.
- **Behavior:** updates affect only the saved marker row. They do not alter canonical opportunity/prospect/scheme evidence, provider statuses, search runs, or application-surface evidence.
- **Verify:** `pytest -q tests/test_funding_discovery.py` passed; Ruff, compileall, and frontend build passed.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 273 — help corpus updated for saved-funding unsave. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 273: Funding Discovery saved-item unsave

- **Files:** `app/backend/funding/repo.py`, `app/backend/api/routers/funding.py`, `app/frontend/js/08k_funding_discovery.jsx`, `tests/test_funding_discovery.py`, `callosum-app.html`, help/developer docs, and Funding Discovery security audit.
- **What:** added `DELETE /funding-discovery/saved/{saved_item_id}` and an **Unsave** button in the Theory-pane **Saved funding** list.
- **Why:** saved funding items are lightweight workflow markers; users need a way to remove a marker when an opportunity/scheme/prospect no longer belongs on their review list.
- **Behavior:** unsaving deletes only the saved marker row. It does not delete the underlying opportunity, recurring scheme, funding prospect, search run, or evidence.
- **Verify:** `pytest -q tests/test_funding_discovery.py` passed; frontend rebuilt.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 272 — help corpus updated for Cite graph-neighborhood expansion. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 272: Cite suggestions use local-match graph neighborhoods

- **Files:** `app/backend/citations/beyond_library.py`, `app/backend/api/routers/citations.py`, `app/frontend/js/37_cite.jsx`, `app/frontend/styles.css`, `tests/test_citations_suggest.py`, `callosum-app.html`, help corpus, and the beyond-library Cite security audit.
- **What:** the opt-in outside-library Cite search now uses the top local library matches as OpenAlex anchors. In addition to direct public metadata search, it gathers bounded reference, cited-by, and related-work neighborhoods and labels outside-library candidates as **Cited by a locally relevant paper**, **Cites a locally relevant paper**, or **Related to a locally relevant paper in OpenAlex**.
- **Why:** deterministic scholarly-neighborhood evidence should surface better candidates than text search alone when the right citation is not already in the library.
- **Boundaries:** graph expansion sends only DOI identifiers for top local matches to OpenAlex; it reuses the existing cached OpenAlex client; graph relationships are evidence labels, not citation recommendations or correctness claims.
- **Verify:** `pytest -q tests/test_citations_suggest.py` passed; Ruff, compileall, and frontend build passed.

<!-- HELP-DOCS-SYNCED 2026-07-11 inc 271 — help corpus updated for opt-in beyond-library Cite suggestions. Nothing above this line has an un-synced corpus change. -->
## 2026-07-11 — Increment 271: Cite suggestions beyond the local library

- **Files:** `app/backend/citations/beyond_library.py`, `app/backend/api/routers/citations.py`, `app/backend/api/app.py`, `app/frontend/js/37_cite.jsx`, `app/frontend/styles.css`, `tests/test_citations_suggest.py`, `callosum-app.html`, help corpus, and security audit.
- **What:** added an opt-in **Also search beyond my library** mode to the Cite pane. The existing `/citations/suggest` endpoint still returns local library suggestions by default, and now can also return separate outside-library candidates from public metadata providers, with provider coverage and abstract/metadata evidence. Outside-library cards can be added to the library through the existing discovery save path.
- **Why:** backlog #30 SP2: when the right citation is not already in the library, Callosum should surface reviewable public-metadata candidates without pretending abstracts are full-text evidence or automatically choosing a citation.
- **Boundaries:** default remains local/no-egress; opt-in public search sends only the pasted sentence/description to metadata providers; no full PDFs, notes, annotations, or manuscript bodies; outside-library stance is labeled abstract-level; no auto-insert, recommendation verdict, hidden score, or "verified good" language.
- **Verify:** `pytest -q tests/test_citations_suggest.py` passed; Ruff, compileall, and frontend build passed.

<!-- HELP-DOCS-SYNCED 2026-07-10 inc 270 — help corpus updated for optional Funding Discovery LLM triage. Nothing above this line has an un-synced corpus change. -->
## 2026-07-10 — Increment 270: Funding Discovery optional LLM triage

- **Files:** `app/backend/funding/llm_triage.py`, `app/backend/api/routers/funding.py`, `app/backend/api/app.py`, `app/frontend/js/08k_funding_discovery.jsx`, `app/frontend/styles.css`, `tests/test_funding_discovery.py`, `callosum-app.html`, help and audit notes.
- **What:** added an opt-in **Ask AI to triage apparent fit after discovery** control for Funding Discovery. When requested, Callosum sends the bounded research abstract/description plus compact summaries of already-surfaced funding items to the configured model, annotates cards with reviewable apparent-fit labels, and lets the user switch between **All surfaced** and **LLM-triaged** views.
- **Why:** the deterministic discovery pool can be intentionally broad, especially for latent funding fit. LLM triage helps reduce review noise without deleting evidence or turning the model into a funding-verdict engine.
- **Boundaries:** default off; uses the existing AI-features/data-egress gate; no full PDFs/notes/private annotations; no funding probability, recommendation column, eligibility verdict, or hidden composite score; deterministic results remain visible and canonical.
- **Verify:** `pytest -q tests/test_funding_discovery.py tests/test_frontend_assembly.py` passed; Ruff, compileall, frontend build, and line-budget guard passed.

<!-- HELP-DOCS-SYNCED 2026-07-10 inc 269 — help corpus updated for duplicate DOI merge workflow. Nothing above this line has an un-synced corpus change. -->
## 2026-07-10 — Increment 269: Duplicate DOI allowed for PDF/metadata merge cleanup

- **Files:** `app/backend/persistence/schema.py`, `alembic/versions/0040_allow_duplicate_paper_dois.py`, `app/backend/metadata/enrichment.py`, `app/backend/metadata/paper_merge.py`, `app/backend/api/routers/papers.py`, `tests/test_papers.py`, `tests/test_paper_merge.py`, `tests/test_metadata_multi_enrich.py`, help and audit/QA notes.
- **What:** removed the uniqueness block on `papers.doi`. A raw PDF record can now accept or recover the same DOI as an existing metadata-only record, giving duplicate detection and merge workflows the identifier they need.
- **Why:** DOI is a strong duplicate signal, but it should not be the barrier that prevents a user from identifying and merging duplicate records. OpenAlex/Semantic Scholar/Zotero identifiers remain unique.
- **Behavior:** duplicate DOI edits and fill-metadata DOI recovery now succeed; merge no longer rejects a DOI already present on another live paper. Merge still frees non-DOI unique identifiers on husks before adopting them.

<!-- HELP-DOCS-SYNCED 2026-07-10 inc 268 — help corpus gained "Funding Discovery" for the Theory-pane prospect/scheme/opportunity flow, source coverage, evidence boundaries, CSV export, saved funding view, and save workflow. Nothing above this line has an un-synced corpus change. -->
## 2026-07-10 — Increment 268: Funding Discovery — latent prospects, recurring schemes, and open opportunities

- **Files:** `app/backend/funding/*` (NEW domain/profile/providers/identity/IRS parser/engine/resolver/repo), `app/backend/api/routers/funding.py` (NEW `/funding-discovery/*` async run + save endpoints), `app/backend/api/app.py` (router/job seams), `app/backend/persistence/schema_funding.py` + `alembic/versions/0039_funding_discovery.py` (NEW normalized funding tables), `app/frontend/js/08k_funding_discovery.jsx` + `app/frontend/styles.css` + `callosum-app.html`, `tests/test_funding_discovery.py` (NEW), `.claude/docs/funding-discovery.md`, `.claude/qa-routes/route_69_funding_discovery.md`, `.claude/security-audits/2026-07-10_funding-discovery.md`, and help corpus.
- **What:** added **Funding Discovery** under **Where to submit** in the Theory pane. It builds a local multi-facet `ResearchFundingProfile`, gathers bounded historical funding evidence, produces inspectable latent-fit signals, resolves current Grants.gov opportunities separately, keeps recurring schemes distinct from open opportunities, shows source coverage, and lets users save opportunities/schemes/prospects.
- **Why:** funding fit often appears in historical portfolios, support strategies, recurrence, and scholarly funding lineage before a current opportunity uses the same vocabulary. The feature is calibrated as signal, not verdict: no chance-estimate field, no recommendation label, no positive eligibility verdict, no recurrence forecast, and no historical award presented as open.
- **Verify:** feature tests cover profile facets, provider minimization, identity ambiguity, Grants.gov normalization/failure, EO-BMF parsing, 990-PF grant/application parsing with individual-recipient suppression, recurrence, long-tail ranking protection, endpoint persistence/save, selected-paper mode, source coverage, and forbidden UI language. Frontend rebuilt.
- **Follow-up:** upgraded the initial provider seams into cached ROR, OpenAlex funding, and Crossref funding adapters with fixture-pinned extraction/failure tests; OpenAlex/Crossref funding records now contribute `HistoricalAward` evidence when those sources return funder/grant metadata.
- **Follow-up 2:** selected-paper runs now reuse the existing OpenAlex DOI and related-work fetch path to surface grants on related scholarly work as `scholarly_lineage`/historical-award evidence, without treating those grants as current opportunities.
- **Follow-up 3:** added `recipient_similarity` candidate generation from exact non-individual recipient-organization overlap: funders of organizations that also appear in profile-matched historical funding evidence can surface as prospects, while individual recipient rows are excluded.
- **Follow-up 4:** added `cofunding_proximity` graph-neighborhood evidence from exact non-individual recipient overlap between profile-matched funders and other funders; the signal is phrased as proximity, not mission alignment.
- **Follow-up 5:** surfaced `ApplicationSurface` posture on Funding Discovery cards. 990-PF/application posture such as unsolicited-application language now appears as **Application route** evidence, while official opportunity surfaces remain separate current-opportunity evidence.
- **Follow-up 6:** added a lightweight **Saved funding** read view. Saving an opportunity/scheme/prospect now snapshots last-known status and deadline where available, and the Theory pane lists saved items without adding grant-CRM workflow controls.
- **Follow-up 7:** added persisted-run CSV export for Funding Discovery. The export keeps open opportunities, recurring schemes, and prospects distinct and includes source/status, deadline, application-route, signal, and matched-facet summaries without adding recommendation/chance-estimate fields or recipient-level 990-PF details.

## 2026-07-10 — Increment 267: Meta Reference List — per-citation reference integrity signals
- **Files:** `app/backend/methods/reference_integrity.py`, `app/backend/persistence/schema_reference_integrity.py` + `reference_integrity_repo.py` + migration `0038_reference_integrity.py`, `app/backend/api/routers/reference_integrity.py`, `app/backend/api/app.py`, `app/frontend/js/08j_reference_integrity.jsx`, `03_library.jsx`, `10_pdf_layer.jsx`, `10d_papercard.jsx`, `40_app.jsx`, `styles.css`, `tests/test_reference_integrity.py`, plus route/security/help docs.
- **What:** added the **Meta Reference List** Theory accordion section above **Where to submit**. It fetches linked references through Semantic Scholar, falls back to OpenAlex `referenced_works` when Semantic Scholar has no linked reference list, reuses Crossref/OpenAlex resolution, existing retraction checkers, local citation-context hints, and paper-card warning counts to surface only three inspectable signals: **Could not verify**, **Known retraction signal**, and **Previously flagged in your library**.
- **Why:** a pre-flight reference gate before deeper literature search/synthesis, while preserving Callosum's signal-not-verdict rule. Search misses are cautious evidence, retractions are visually/textually distinct, local propagation is scoped to the reference entity, and human review stays scoped to the citation instance.
- **State model:** review rows are keyed by citation instance + deterministic active signal-set fingerprint. `dismissed` clears the active reference-warning contribution; `confirmed_problem` and `unreviewed` keep it active. A materially new signal set reopens a prior dismissal as unreviewed; there is no global whitelist and no positive paper state.
- **Follow-up hardening:** propagation rows now expose a local "open source paper" control through the existing `onOpenPaper` path; feature-specific Chromium check confirmed desktop rendering/order with 0 console/page errors. The existing opt-in reading-mode smoke has an unrelated reload timeout still to investigate.
- **Gates:** migration `0038`; security audit `2026-07-10_reference-integrity.md`; QA route `route_68_reference_integrity.md`; help "Checking reference signals" added.

## 2026-07-08 — Increment 266: critical-review supplement (#12) — a single-paper scrutiny surface
- **Files:** `app/backend/persistence/schema_critical_review.py` + `critical_review_repo.py` + migration `0037_critical_review_candidates.py` (rebased off `0036`), `app/backend/methods/critical_review.py` (Tier-1 contradiction detector + backbone + `paper_full_text`), `integrations/gemini/critical_review.py` (NEW — Tier-2 generator + `verify_candidates` #13 bar), `app/backend/api/routers/critical_review.py` (async job + candidate CRUD + egress-gated generate), `app/frontend/js/08x_methods_critical.jsx` + `styles.css` (the panel), `tests/test_critical_review.py` (16). Gates: `.claude/security-audits/2026-07-08_critical-review.md` (PASS), `.claude/qa-routes/route_67_critical_review.md` (215/215 API), help "Critically reading a paper" section, `INCREMENT-266-NOTES.md`, CLAUDE bump.
- **What:** a "Critical read" METHODS section — **Tier 1** (local, auto): the paper's method-check flags + claims the rest of the corpus *contests* (cross-corpus NLI contradiction detector), each grounded + confidence; **Tier 2** (opt-in, egress-gated): the LLM proposes critique *candidates* admitted only through the verbatim #13 bar, which the human accepts/rejects. Signal, never a verdict — no score, facts-vs-candidates distinct (amber), critique of the work never the authors.
- **Why:** finish backlog #12 (the Cliff-required "critical read"). Rebased the branch onto `main` first (re-chained the migration `0035_critical_review_candidates → 0037` off the merge migrations — the multi-head snarl inc 265 introduced).
- **Revert:** revert commits on branch `critical-review-design` (PR #3).
- **Help:** added "Critically reading a paper"; the last FULL corpus sync remains inc 259 (260–265 still pending a review).

## 2026-07-07 — Increment 265: reversible un-merge (#16) — the undo net for the inc-161 paper merge
- **Files:** `app/backend/metadata/paper_merge.py` (records a reversal snapshot as it merges → a `merge_operations` row + marks husks `merged_into`; `MergeResult.merge_operation_id`), `app/backend/metadata/paper_unmerge.py` (NEW — `unmerge` + `merge_origin`), `app/backend/api/routers/duplicates.py` (+`POST /merge/{id}/undo`, +`GET /papers/{id}/merge-origin`, +`merge_operation_id` on the merge response), `app/backend/persistence/schema.py` + `schema_merge.py` (NEW `merge_operations` table + `papers.merged_into`), `alembic/versions/0035_merge_operations.py` + `0036_papers_merged_into.py` (NEW), `app/backend/persistence/repository.py` + `paper_lifecycle_repo.py` (Trash list excludes merged-away; `purge_paper` guards both sides of an active merge), `app/frontend/js/25_detail.jsx` + `styles.css` (the "Merged from… — Un-merge" banner), `tests/test_library_merge.py` (NEW reversibility suite) + `tests/test_paper_merge.py` (updated). Deleted the redundant parallel `merge_repo.py` + `merge_allowlist.py`. Security audit `2026-07-07_library-merge-reversibility.md` (PASS); QA route 24 extended; help "Merging duplicates" section updated.
- **What:** the inc-161 non-destructive merge is now **fully reversible** (#16). Merge records a self-contained reversal snapshot (re-points, the union links it *added* via a before/after diff, nulled husk id columns, survivor metadata, primary-PDF role, My-Pubs refs); `unmerge` replays it exactly (all UPDATE/DELETE — no re-insertion, so no id/timestamp hazard). Merged-away copies become a distinct "merged-away" state (hidden from the live library **and** the plain Trash list) reachable only via **Un-merge** on the survivor's Details — because a naive Trash-restore of a husk would give an empty shell (its data moved to the survivor).
- **Why:** merge is the app's most destructive op in a tool with no git; #16 is its safety net. (Course-correction: #17's *merge* had already shipped in inc 161 — the genuine gap was reversibility.)
- **Revert:** restore from `.claude/backups/` OR revert commits on branch `library-merge`.
- **Help:** the "Merging duplicates" section was updated for the new un-merge behavior; the last FULL corpus sync remains inc 259 (marker unmoved — 260–264 still pending a review).

## 2026-07-06 — Increment 264: autonomy harness — the 600-line-cap gate (#20 ratchet 1) + the drift it caught
- **Files:** `tools/check_line_budget.py` (NEW — rule-#1 enforcer), `tools/git-hooks/pre-commit` (NEW — ruff + line-budget; installed via `git config core.hooksPath tools/git-hooks`), `.github/workflows/ci.yml` (+ a Line-budget step), `app/backend/api/routers/axes_models.py` (NEW, 125 — 14 axis models + caps peeled out), `app/backend/api/routers/axes.py` (609→**513**), `app/frontend/js/10d_papercard.jsx` (NEW, 100 — paper-card cluster), `app/frontend/js/10_pdf_layer.jsx` (604→**507**), `.claude/CLAUDE.md` (inc 263→264 + retired the hand-maintained watch list → the script), `INCREMENT-264-NOTES.md` (NEW). callosum-app.html rebuilt (byte-identical). No API/DB change, no migration.
- **What:** the first piece of the autonomous-operation safety layer — a fast, deterministic **600-line-cap gate** (`check_line_budget.py`) wired into a **git pre-commit hook** (+ ruff) and **CI**, so neither a human nor an unattended loop can ship over-cap or lint-red. On first run it caught two files that had drifted over the cap while the CLAUDE.md watch list stayed stale (`axes.py` 609, `10_pdf_layer.jsx` 604); both split behavior-preserving (inc-137 leaf pattern / inc-208 shared-IIFE hoist — the rebuilt bundle is byte-identical).
- **Why:** the user chose to "lean on autonomy." Hooks don't widen *what* can be built autonomously (the `⛔ NEEDS CLIFF` cut line does) — they make the loop *safe*. This is backlog #20 ratchet step 1. The gate immediately proved its value + retired the drift-prone hand-maintained watch list (run `python tools/check_line_budget.py --list` instead).
- **Verify:** line-budget clean (282 files ≤600); pre-commit hook green; `test_axes.py` 32 passed; frontend byte-identical; full `pytest --ignore=tests/test_mcp_server.py` → **1055 passed, 1 skipped** (unchanged); ruff clean.
- **Revert:** `git revert <sha>` + `git config --unset core.hooksPath` (additive: new tool + hook + CI step + two behavior-preserving splits; no migration).

## 2026-07-06 — Decision pass (backlog reconciliation; doc-only, no increment)
- **Files:** `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/docs/INCREMENT-BACKLOG-DONE.md`, `.claude/architectural-decisions-log.md`, `.claude/PRINCIPLES.md`.
- **What:** ruled on the cheap below-cut [decision] gates to shrink the "needs-Cliff" pile and define the keystone AI-assist gate. **#6** divergent-button migration → **DECLINED** (buttons stay documented exceptions per inc-86; closed). **#13** "how auditable is auditable enough?" → **RATIFIED** as a standard: every stronger AI-assist judgment/suggestion carries its retrieved source span(s) + a local-NLI stance label + a verbatim quote + a visible confidence, one low-friction click from the evidence, with an honest shortfall note if it can't — recorded durably in `architectural-decisions-log.md` + a `PRINCIPLES.md` THEORY cross-ref; un-gates #12 + Tracks B/C for planning. **#3** tag-source-as-always-on-label → **DECLINED** (aesthetic-only per inc-100; the #3 diff-toast + lock-this-tag remainders promoted to the autonomous queue). **statcheck (b)** paper-level "Check statistics" entry → **DECLINED** (rely on the inc-141 flagged-chip path per inc-122).
- **Why:** the user chose "widen the lane" — resolving decision gates promotes/closes below-cut items and defines the inspectability bar that gated the critical-review + highlight-suggest/evaluate tracks. Honors three prior deliberate rulings (inc-86/100/122) rather than reversing them.
- **Revert:** `git revert <sha>` (doc-only; no code).

<!-- HELP-DOCS-SYNCED 2026-07-06 inc 263 — help corpus gained "Get a paper through your library (OpenURL)" under *Acquiring an open-access copy*: the opt-in institutional link-resolver hand-off — set your library's OpenURL base in Settings → Library access, then "Get via my library" after an OA miss opens THAT resolver in your own browser (your SSO authenticates; callosum only builds + opens the link — it never fetches, scrapes, or stores credentials); credits NISO OpenURL (Van de Sompel & Beit-Arie 2001). Nothing above this line has an un-synced corpus change. -->
## 2026-07-06 — Increment 263: OpenURL institutional link-resolver hand-off (free-and-legal entitled-paper access)
- **Files:** `app/backend/acquisition/openurl.py` (NEW — pure OpenURL 1.0 / Z39.88 builder + `resolver_base_valid`; deterministic, no network), `app/backend/api/routers/acquisition.py` (+`GET /papers/{id}/library-link` — builds + returns the URL, **never fetches**), `app/backend/app_settings.py` (+`openurl_resolver_base`, a non-secret pref like `contact_email`), `app/backend/api/routers/settings.py` (GET/PUT the resolver base, validated → 422), `app/frontend/js/25_detail.jsx` ("Get via my library" after an OA miss → `window.open` the built OpenURL), `app/frontend/js/35_settings.jsx` (new "Library access" field + OpenURL credit-add block), `tests/test_openurl.py` (NEW, 11), `.claude/qa-routes/route_56_acquisition_wanted.md` (extended), `.claude/security-audits/2026-07-06_openurl-resolver.md` (PASS), `app/backend/help/help_content.md`, `INCREMENT-263-NOTES.md`, CLAUDE (262→263). callosum-app.html rebuilt. New `/papers/{id}/library-link` API surface; no migration.
- **What:** when the free-OA cascade misses, an **opt-in** "Get via my library" hand-off — callosum builds a standard **OpenURL** from the paper's metadata and opens the user's **own institution's official link resolver in their own browser**; their existing SSO authenticates, they download, and the existing attach / watched-folder path files it back. A link-builder + the ingest we already have.
- **Why:** the user's "don't leave callosum to get papers" goal, served **without** crossing the acquisition bright lines. The originally-proposed credentialed browser-connector (Playwright cookie-harvest → server-side stored session → auto-fetch → silent re-auth) IS the **deferred, Penn-counsel-gated** Tier-4 lane and violates veto-level bright lines (no server-side credential handling, no session harvesting, connector must be batch-incapable) — declined here. This hand-off crosses **none** of them: no Playwright, no credentials, no server-side fetch, no scraping; per-item, human-gated.
- **Gates:** PRINCIPLES / A-A (rule #9): no-circumvention honored (official resolver + user's own entitlement); **A8** — opt-in layer *atop* the free-OA-first chain, tool fully useful with no institution; honest terminal at the OA miss. SECURITY `2026-07-06_openurl-resolver.md` **PASS** (no server-side fetch → no SSRF; no credentials; only a public DOI in a URL the *user's own* browser opens; input validated, output urlencoded; default-off; egress gate untouched). QA route_56 extended; surface-map **207/207 API + 995/995 FE** clean. CREDIT-THE-LINEAGE: NISO OpenURL / SFX (Van de Sompel & Beit-Arie 2001) credited in-context + one-click library-add.
- **Verify:** `pytest tests/test_openurl.py` → 11 passed; full `pytest --ignore=tests/test_mcp_server.py` → **1055 passed, 1 skipped**; ruff clean; new `app/` files under cap; frontend built clean.
- **Revert:** `git revert <sha>` (additive: new module + endpoint + settings field + frontend control; no migration).

## 2026-07-04 — Increment 262: 600-line-cap cleanup — split `routers/methods.py` + `persistence/schema.py` (backlog #47)
- **Files:** `app/backend/api/routers/methods_retraction.py` (NEW, 186 — the retraction endpoint cluster peeled out of methods.py), `app/backend/api/routers/methods.py` (619→**450**; also dropped dead `import logging`/`_log`), `app/backend/api/app.py` (mounts `methods_retraction.router`), `app/backend/persistence/schema_summaries.py` (NEW, 107 — the summaries/citation_mappings/evidence_quotes/summary_sentences tables), `app/backend/persistence/schema.py` (628→**558**; re-exports the four tables), `app/backend/persistence/schema_base.py` (gained `enum_check`/`non_empty_check`/`CITATION_MAPPING_STATUSES`), `.claude/CLAUDE.md` (inc 261→262 + the rule-#1 watch line), `INCREMENT-262-NOTES.md` (NEW), `INCREMENT-BACKLOG.md`/`-DONE.md` (#47 + #46 relocated to DONE).
- **What:** behavior-preserving refactor bringing two files that had drifted over the rule-#1 hard cap back under 600 lines. `methods.py`: retraction endpoints → a sibling router (inc-226 `paper_enrich.py` pattern; shared state via `request.app.state`, mounted beside `methods.router`). `schema.py`: the verification-output table group → a new `schema_*.py` on the shared `schema_base` metadata (inc-137 `schema_findings.py` pattern; the CHECK helpers + `CITATION_MAPPING_STATUSES` moved to `schema_base` so both files share one definition without a circular import).
- **Why:** backlog #47 — the CLAUDE.md watch-list had gone stale and both files crossed the cap through inc 261; the next feature touching either MUST split first, so clear it now (rule #1). No new features, no API/DB/schema change, no migration.
- **Verify:** line counts all <600 (methods 450, schema 558, new files 186/107); `import schema` + `metadata.create_all` registers all 47 tables + FKs resolve; `ruff format`/`ruff check` clean; `pytest --ignore=tests/test_mcp_server.py` → **1044 passed, 1 skipped** (unchanged).
- **Revert:** `git revert <sha>` (additive: two new files re-exported/mounted, cluster moves, dead-code removal; no migration).

## 2026-07-04 — Increment 261: CRediTer (CRediT contribution-statement builder) + THEORY authoring-cluster reorg
- **Files:** `app/backend/methods/credit.py` (NEW, 144 — the pure `format_statement` formatter + the 14 NISO roles + `validate` + the AST-pinned `NO_INFERENCE`), `app/backend/api/routers/credit.py` (NEW, 88 — `POST /credit/statement` + `POST|GET /credit/pending`; a new router, NOT added to the over-cap `routers/methods.py`), `app/backend/api/app.py` (mounts `credit.router`), `app/frontend/js/38_credit.jsx` (NEW — the `CreditSection` THEORY-pane grid: authors × 14 role-chips ± degree, pull-authors, localStorage scratchpad, debounced POST, by-author/by-role toggle, Copy + Send-to-LibreOffice, credit block), `app/frontend/js/08_methods_findings.jsx` + `08e_methods_publishers.jsx` (paneId methods→theory), `app/frontend/js/35_settings.jsx` (copy: Theory → Where to submit), `app/frontend/styles.css` (`.credit-*` recipe + the `.credit-view-hint`), `adapters/libreoffice/callosum_cite.py` (`insert_statement` + `insertStatement` action + `CallosumInsertStatement` + `g_exportedScripts`) + `oxt/Addons.xcu` (menu item) + `README.md`, `tests/test_credit.py` (NEW, 12 — formatter/caps/AST-no-inference/endpoints/pending), `.claude/qa-routes/route_66_credit.md` (NEW) + `route_38_findings.md`/`route_60_publishers.md` (METHODS→THEORY prose), `.claude/security-audits/2026-07-04_credit-statement.md` (PASS), `app/backend/help/help_content.md`, `INCREMENT-261-NOTES.md`, `INCREMENT-BACKLOG.md` (#26 reconciled + new #47 cap-drift), CLAUDE (260→261). (callosum-app.html rebuilt.) **No migration; new `/credit/*` API surface.**
- **What:** **CRediTer** — a deterministic/local/no-egress/no-LLM **authoring aid** in the new THEORY authoring cluster: assign each author their NISO **CRediT** roles (± lead/equal/supporting) and callosum **formats** the contributions into a contributorship statement in **both** layouts (by-author / by-role, a toggle, one response). Output = **Copy** (universal, primary) **+ native LibreOffice injection** (Send to LibreOffice → `POST /credit/pending` → the add-on's **Insert CRediT statement** places it at the cursor as plain text). Also **moved "Where to submit" + "Review"** from the METHODS pane to THEORY (data-driven `order`), so THEORY reads understand → cite → where to submit → **credit** → review.
- **Why:** the user's request ("add tenzing… + move Review / Where-to-submit to Theory"). **Builder, not verifier** — it formats what the human *asserts*; it never infers/scores/judges who did what (an **AST-pinned no-inference** boundary in `methods/credit.py`, enforced by a test). Principle *facts ≠ candidates / the human is the filter*: no confidence, no composite score, no verdict. Credit-the-lineage honored — the panel credits **tenzing** (Holcombe et al. 2020) + the **CRediT/NISO taxonomy** (Brand et al. 2015) in-context with a one-click, idempotent library-add, under a **distinct** name.
- **Gates:** DESIGN — new `.credit-*` recipe (tokens + existing classes only); **deviation from the plan** logged in DESIGN Pass-2 (role *chips* per author, not the sketched author×role *matrix* — better in the ~260px sidebar). PRINCIPLES aligned (above). QA — new `route_66`; surface-map `check` clean (**206/206 API + 987/987 FE**, 0 uncovered). SECURITY — `2026-07-04_credit-statement.md` **PASS** (0 egress, caps/allowlists → 422, plain-text output). EXPERIENCE (rule #11, "deadline author") — flow completes end-to-end; **4 cheap fixes folded in** (Copy made primary + "Send to LibreOffice" relabel; a by-author layout hint; a persistent staged confirmation that clears on grid edit; the credit block reframed "About this tool:" so it doesn't read as manuscript citations); **3 backlogged** to #26 (role presets / an "and" before the last by-role name / accordion discoverability).
- **Verify:** `pytest --ignore=tests/test_mcp_server.py` → **1044 passed, 1 skipped** (+12 in `tests/test_credit.py`); `ruff format`/`ruff check` clean; new `app/` files under the 600 cap (`methods/credit.py` 144, `routers/credit.py` 88, `38_credit.jsx` ~215); frontend built clean via esbuild (all four new label strings present in the bundle). Pre-existing cap drift filed (not this increment's to fix): `routers/methods.py` 619, `persistence/schema.py` 628 → backlog #47. Manual script (port **8888**) in `INCREMENT-261-NOTES.md`.
- **Revert:** `git revert <sha>` (additive new router + new frontend chunk + two paneId flips + an adapter action; no migration).

## 2026-07-04 — Increment 260: Citation-equity no-DOI hints made actionable (+ stale-backlog reconciliation)
- **Files:** `app/frontend/js/08b_methods_citation_equity.jsx` (the two no-DOI hints — Run audit + Find overlooked work), `app/frontend/js/08c_methods_citation_context.jsx` (the How-it's-cited no-DOI hint), `.claude/qa-routes/route_51_methods_citation_equity.md` + `route_53_citation_context.md` (quoted hint strings updated to match), `.claude/docs/INCREMENT-BACKLOG.md` (removed the stale "Find overlooked work … 422s" item), two stray `.tmp` route artifacts deleted, `INCREMENT-260-NOTES.md`, CLAUDE (259→260). (callosum-app.html rebuilt.) **No migration; no new API surface; no help-corpus impact.**
- **What:** the three no-DOI empty-state hints in the THEORY → Cite tabs now **point the user to the fix** instead of dead-ending on the limitation — each keeps its honest service-specific *why* ("…so OpenAlex can't resolve its references" / "…can't relate work to it" / "…Semantic Scholar can't look up its citation graph") and appends *"Add one under Identifiers in the Detail pane to enable …"* (the app's own vocabulary for where the editable DOI lives, per `25_detail.jsx`).
- **Why:** investigating the backlog item (rule #7) found the **functional gating already shipped** — inc 257 gated both citation-concentration controls on `hasDoi` and inc 232 gated How-it's-cited; the 422-on-click gap the QA run (20260702, one day pre-fix) described no longer reproduces. The genuine remainder was an **experience gap (rule #11)**: a correct "no DOI" signal with no path to the action it implies. Making the hint actionable is the fix the plan preview confirmed; the backlog entry is reconciled (shipped inc 257 + actionable-hint polish inc 260).
- **Gates:** DESIGN not triggered (existing `.tag-suggest-empty` class reused, no CSS change); Principles aligned (an honest *limitation* disclosure made actionable — not a new claim/signal); QA surface-map `check` clean (203/203 API + 965/965 FE, 0 uncovered — no new surface, route assertions updated); EXPERIENCE — this change *is* the pass fix. DOI confirmed editable at the pointed-to location before writing the copy (`25_detail.jsx:445`, `paper_edits.py:88`).
- **Verify:** `pytest --ignore=tests/test_mcp_server.py` → **1032 passed, 1 skipped** (unchanged — frontend copy touches no Python); frontend built clean via esbuild, all three new strings present in the bundle; `08b` 270 / `08c` 149 lines (well under the 600 cap). Manual script (port **8888**) in `INCREMENT-260-NOTES.md`.
- **Revert:** `git revert <sha>` (copy-only change to three strings + doc updates; no migration, no logic change).

<!-- HELP-DOCS-SYNCED 2026-07-03 inc 259 — Extract help gained "Drafting cells with AI (you verify each one)": the assisted-extraction funnel proposes values for a row's empty structured cells as amber candidates, each with a verbatim quote + an exact/region/couldn't-verify anchor badge; accept / edit-then-accept / reject per cell; nothing enters the dataset until you accept; the Draft button is gated off when AI features are off — "the AI narrows the search, you stay the filter". Nothing else user-facing changed since the inc-258 marker. -->
## 2026-07-03 — Increment 259: Workbench SP2b — the assisted-extraction funnel (AI proposes, the human filters)
- **Files:** `alembic/versions/0034_extraction_proposals.py` (NEW — the `ma_proposals` candidate table + `ma_cells.origin`), `app/backend/persistence/workbench_repo.py` (proposal CRUD + `upsert_cell(origin=…)`; `proposals` ride the row view), `app/backend/workbench_assist.py` (NEW — `page_tagged_text` [50k cap], `primary_pdf_path`, `anchor_proposal` → exact/region/unanchored via `locate_quote`), `integrations/gemini/extraction_assistant.py` (NEW — `ExtractionAssistant` Protocol + `GeminiExtractionAssistant.propose` + defensive `parse_proposals`; rides the existing `EgressGatedExtractionAssistant`), `app/backend/api/routers/workbench.py` (`POST …/rows/{id}/propose` + `…/proposals/{id}/accept|reject`), `app/frontend/js/46_workbench_propose.jsx` (NEW, 60 — `WbDraftButton`/`WbAnchorBadge`/`WbCandidate`) + `45_workbench.jsx` (347 — draft/accept/reject/open wiring) + `styles.css` (`.wb-cand*`/`.wb-badge`/`.wb-draft`), `tests/test_workbench.py` + `tests/test_workbench_assist.py` (propose/accept/reject + candidate-safety + anchor-state + defensive-parse + egress-off-403), `.claude/security-audits/2026-07-03_workbench-assisted-extraction.md` (PASS), `.claude/qa-routes/route_65_workbench.md` (funnel block + 5 adversarial cases), help corpus, `INCREMENT-259-NOTES.md`, CLAUDE (258→259). (callosum-app.html rebuilt.) **Migration 0034.**
- **What:** an **egress-gated** assistant (**✨ Draft from PDF**) that *proposes* values for a row's empty **structured** cells as **amber candidates** — the LLM reads the paper's page-tagged text and returns `{value, quote, page}`; the app **anchors each locally** (`locate_quote` → **exact** [quote found + value literal in it → a union-rect bbox] / **region** [quote found, value not in it] / **couldn't verify** [quote absent]) and shows the verbatim quote + an honest badge. Accept / edit-then-accept / reject **per cell**; a candidate lives only in the isolated `ma_proposals` table and **nothing enters `ma_cells`/Convert/exports until accept** (`origin='assisted'` in provenance). *AI = funnel, human = filter.*
- **Why:** SP2b of future track #36 — narrow the manual extraction search without ceding the judgment. Every core invariant holds: egress off by default (invariant #3 — 403 with AI off, loopback = no egress); facts ≠ candidates (physical table isolation, PRINCIPLES); coordinate honesty (invariant #2 — the exact box is drawn only when the app itself located the quote+value, and an **edit drops it to region**); evidence always shown (invariant #4 — the quote stays visible even while editing). The model never asserts a location or a confidence — the anchor is derived locally.
- **Experience pass (rule #11, persona "deadline meta-analyst"):** verdict **serves-with-gaps**; the honesty foundation is sound. **5 cheap frontend fixes folded in** (count unchanged): quote visible while editing; **Esc** cancels an edit non-destructively; quote wraps instead of truncating at 320px; an honest note when an edit drops an exact anchor to region; the disabled-Draft tooltip names *Allow AI features*. **Backlogged to #36:** the "region" badge vocabulary for first-timers; the unanchored Open-at-anchor opening at the model's *claimed* page with no unverified-page note (a footgun); a text label so fact-vs-candidate isn't amber-only. See `INCREMENT-259-NOTES.md`.
- **Post-review fixes (SDD final whole-branch review → "ready to push, with fixes"):** 2 Important, both **strengthening** an invariant. **#1 — a human value is never contested:** `put_cell` now clears any live proposal for the field it writes (new `workbench_repo.delete_proposals_for_field`), so a stale candidate can't be accepted over a hand-entered value (closes the reachable clobber path **and** the resurfacing-stale-candidate footgun); test `test_manual_cell_write_clears_pending_candidate`. **#2 — unanchored open honesty (invariant #2):** `openProposalAnchor` passes `precision:null` (was `region`) for an unanchored candidate → Open-at-anchor no longer implies a located region (also resolves the experience-pass footgun). 3 Minors backlogged to #36. `45_workbench.jsx` rebuilt.
- **Verify:** `pytest --ignore=tests/test_mcp_server.py` → **1032 passed, 1 skipped** (+1 post-review); `ruff format`/`ruff check` clean; all touched `app/` files under the 600-line cap (`workbench.py` 319, `45_workbench.jsx` 333, `workbench_repo.py` 250, `46_workbench_propose.jsx` 57); frontend built clean via esbuild; QA surface-map `check` clean (203/203 API + 965/965 FE, 0 uncovered). Manual script in `INCREMENT-259-NOTES.md` (port **8888**).
- **Revert:** `git revert <sha>` (additive endpoints + a new candidate table + frontend controls; migration 0034 has no down-migration by design — the `ma_proposals` table + `ma_cells.origin` column can be left in place, they are unread once the routes are gone).

<!-- HELP-DOCS-SYNCED 2026-07-03 inc 258 — workbench Extract help updated for the dataset loop: "Convert all" + the "k of N converted" coverage readout (un-converted rows named, never fabricated), and the export list expanded to CSV / metafor (yi/vi table, blank yi/vi for un-converted, R rma() handoff) / RevMan (raw per-group data, downstream tool computes the effect) / Provenance; nothing between here and the inc-256 marker touched the corpus (inc 257 + the QA triage were no-corpus-impact) -->
## 2026-07-03 — Increment 258: Workbench SP2b — the dataset loop (Convert all) + metafor/RevMan exports
- **Files:** `app/backend/persistence/workbench_export.py` (NEW, 161 — pure `view→CSV` builders: `generic_csv` [moved verbatim from the router] + `metafor_csv` + `revman_csv` behind a `FORMATS` dict; number-aware `_csv_safe`), `app/backend/api/routers/workbench.py` (new `POST …/convert-all`; `export` dispatches `csv|metafor|revman` through `FORMATS`, keeps `audit`; dropped inline `csv`/`io`), `app/frontend/js/45_workbench.jsx` (Convert-all button + "k of N converted" readout + Export CSV/metafor/RevMan/provenance + a `convMsg` note), `app/frontend/styles.css` (`flex-wrap: wrap` on `.wb-head`), `tests/test_workbench.py` (+3: convert-all honest coverage / metafor yi-vi + negative-effect cleanliness / RevMan raw-by-design), `.claude/qa-routes/route_65_workbench.md` (extended for convert-all + the two exports), `.claude/security-audits/2026-07-03_workbench-convert-all.md` (PASS), `app/backend/help/help_content.md` (Extract section), `INCREMENT-258-NOTES.md`, CLAUDE (257→258). (callosum-app.html rebuilt.) **No migration.**
- **What:** turns the per-row extractions into an **accumulating dataset that feeds the SP1 converter across the whole included set**. **Convert all →** runs the audited per-study converter over every row at once (honest **"k of N converted"** readout; incomplete rows named, never fabricated), and the dataset exports **stat-package-native**: a **metafor** yi/vi table (one row per study + moderators; blank yi/vi for an un-converted row; the `rma(yi, vi, data=dat)` handoff in the tooltip/help, not the file) and a **RevMan** raw-per-group table per design (RevMan computes the effect itself). Also fixed a pre-existing bug where a **negative** effect size/mean was corrupted by the formula-injection guard (`'-0.59`) — `_csv_safe` is now number-aware.
- **Why:** the SP2 goal (future track #36) — extract → convert → hand a *ready* dataset to the meta-analyst's own tool. Deterministic, local, no egress, no values gate. The convert-never-synthesize boundary (rule #9) is preserved: batch = the same per-study convert N times; the readout is honest coverage (Principle #6), never a pooled estimate; no export carries a summary row. The misaligned "pooled effect so far" convenience readout was declined on purpose.
- **Experience pass (rule #11, persona "deadline meta-analyst", ~40 studies):** the metafor→`rma()` handoff held end-to-end and the pooling refusal is felt, not just coded. **3 cheap fixes folded in** (frontend-only, count unchanged): (1) Convert-all now **names** the un-converted rows in the note (was a count alone → hunting in a 40-row grid); (2) `convMsg` clears on a single-row Convert / any cell edit so the note can't contradict the live "k of N" readout; (3) tooltips on the CSV + provenance export buttons. Backlogged to #36: surface the converter's caveats/CI on the converted cell (Convert-all makes N of them silent — principle-relevant), field-level "why this row failed" + the comma-decimal trap, a 0-converted export guard. See `INCREMENT-258-NOTES.md`.
- **Verify:** `pytest --ignore=tests/test_mcp_server.py` → **1012 passed, 1 skipped** (+3); `ruff format`/`ruff check` clean; all touched files under the 600-line cap (router 276, export module 161, jsx 293); frontend built clean via esbuild; new controls confirmed in the bundle. Manual script in `INCREMENT-258-NOTES.md` (port **8888**).
- **Revert:** `git revert <sha>` (additive endpoint + a pure export module + frontend controls; no migration/destructive change).

## 2026-07-03 — Increment 257: Autonomous close-out sweep (QA/experience findings + a seed-fixture gap)
- **Files:** `tests/api_helpers.py` (both `_seed_library` papers now seed `item_type="article-journal"`), `app/frontend/js/06_methods_statcheck.jsx` (inline `p. N` / `p. —` page locator per row), `app/frontend/js/25b_tags.jsx` (an `error` state → inline `.axis-err` on a rejected add/color/remove), `app/frontend/js/08b_methods_citation_equity.jsx` (meta fetch lifted to `CitationEquitySection`; **both** Run-audit and Find-overlooked-work gated on `hasDoi`), `app/frontend/styles.css` (`.statcheck-page`/`.statcheck-page-none`; `flex-wrap` on `.lib-head`/`.lib-head-actions`); QA routes 20/23/33/51 extended; `INCREMENT-257-NOTES.md`; CLAUDE (256→257). (callosum-app.html rebuilt.) **No migration; no new API surface; no help-corpus impact** (polish to existing features, not new/renamed controls).
- **What:** five small, no-decision fixes that had queued above the backlog cut line. (1) seeded libraries now expose `item_type` so the Library **Type** filter renders in a seeded/QA instance; (2) statcheck's per-test **page** is surfaced **inline** (`p. N`, indigo = the page it opens at region precision) instead of tooltip-only, with a muted `p. —` when unattributable; (3) a rejected tag add/color/remove now shows an **honest inline error** instead of silently clearing; (4) a **no-DOI paper** in Citation concentration now hides **both** run controls behind an honest "needs a DOI" hint (previously "Find overlooked work" was clickable → a silent 422); (5) the library header action chips **wrap** at phone width instead of overflowing.
- **Why:** close real dead-ends / silent failures surfaced by QA + the experience pass — "silence is not a certificate" on the tag error path, decline-with-reason on a control that structurally can't succeed (no DOI → OpenAlex can't resolve references), legibility for the statcheck page, and reachable header controls on mobile. Each is low-risk and independently revertible.
- **Verify:** frontend built clean via esbuild; all touched chunks under the 600-line cap. QA surface-map `check` clean (199/199 API + 944/944 FE, 0 uncovered). **Full suite: 1009 passed, 1 skipped** (excl. optional `mcp`; +1 over the inc-256 baseline of 1008 = the intervening QA-triage boundary test, not an inc-257 addition) — four fixes are frontend-only, the fifth is a fixture change with no test asserting the seed's item-types were empty. `ruff format` clean. Manual verification script + experience pass (deadline citer / corpus builder / mobile reader) in `INCREMENT-257-NOTES.md`. Ran on port **8888**.
- **Revert:** `git revert <sha>` (independent low-risk fixes; no migration/destructive change).

## 2026-07-03 — QA triage (runs 20260702_200710 + 20260703_073208): fixture library-dir isolation + a search-query length cap
- **Files:** `tools/qa/_qa_serve.py` (the `qa_server()` env block now sets `CALLOSUM_LIBRARY_DIR`→an empty temp dir — sibling to the inc-254-era `CALLOSUM_SETTINGS_PATH`/`CALLOSUM_DISABLE_REMOTE_ACCESS` isolation); `app/backend/api/routers/papers.py` (the `GET /papers` `q` param gains `max_length=500`); `tests/test_papers.py` (+`test_oversized_search_query_rejected_at_boundary`); `.claude/docs/INCREMENT-BACKLOG.md` (write-lock item refined; 3 assorted UX findings filed). No migration; no help-corpus impact (boundary safety + harness isolation, not a user-facing feature).
- **What (root-cause triage of the two QA runs):** most of the run's "Critical" write-endpoint 500s (`route_15` axes, `route_30` `PATCH /papers`, `route_65` workbench cell) shared **one upstream cause** — a QA-harness fixture bug: `_qa_serve.py` never set `CALLOSUM_LIBRARY_DIR`, so `library_dir()` fell back to the real `library/` and the disposable instance's launch rescan imported the user's ~47 real PDFs into the throwaway DB (`route_23`: 3 seeded → "50 shown"); that heavy background import monopolized SQLite's single WAL write slot and starved the foreground UI writes into `database is locked` 500s. Pointing `CALLOSUM_LIBRARY_DIR` at an empty temp dir fixes it (verified: count stays **3→3** across a launch rescan). Separately, `route_22` was a **real app bug** — an unbounded `q` became a `%<q>%` LIKE pattern exceeding SQLite's `SQLITE_MAX_LIKE_PATTERN_LENGTH` (50000) → `OperationalError: LIKE or GLOB pattern too complex` → 500; capped at the boundary (rule #4) with `max_length=500` → clean 422 (verified through the real server).
- **Why:** honor the verification protocol — confirm each "Critical" is a real regression vs. a fixture/contention artifact before fixing. The write-lock family is the deferred pre-public concurrency item (backlog), *amplified* by the now-fixed fixture bug; the input cap is a genuine boundary hole. The remaining Medium/Low from routes 24/27/30/32 are held for re-triage against a clean-fixture re-run (they read as downstream of the fixture pollution).
- **Also:** removed 6 stray `app/backend/help/help_content.md.tmp.*` atomic-write leftovers (gitignored; rule #5).
- **Verify:** `test_oversized_search_query_rejected_at_boundary` RED→GREEN (422 for all scopes; normal query still 200); end-to-end script confirmed fixture isolation (3→3) + the 422 through a stood-up `qa_server()`; `ruff format`/`ruff check` clean; full suite green (see below). Re-run of the un-run/write-path routes launched to confirm the 500 cluster clears on the isolated fixture.
- **Revert:** `git revert <sha>` (tools + a boundary validator + a test; no app-logic or schema change).

<!-- HELP-DOCS-SYNCED 2026-07-03 inc 256 — AI-features help rewritten for the unified editable provider list: the four presets as editable rows, "+ Add provider" for a custom {name, base URL, API format, models, key}, the three wire formats (Anthropic messages / Chat completions / Responses with the DeepSeek=Chat-completions example), and the endpoint-based egress rule (loopback = local/no consent; any real internet address gated like Gemini) -->
## 2026-07-03 — Increment 256: Unified multi-provider BYOK — add custom LLM providers
- **Files:** `app/backend/providers_store.py` (NEW — the roster: 4 synthesized builtins + persisted `custom_providers`; validators + `/v1`-trim in `_norm_base`), `app/backend/api/routers/settings_providers.py` (NEW — `GET/POST /settings/providers` + `PUT/DELETE /settings/providers/{pid}`), `app/backend/llm/providers.py` (dispatch on `config.wire_format`; new `_complete_responses` for the OpenAI `/responses` shape; **`requires_egress` now dual-mode** — endpoint-based for a config, name-based for the legacy string arg), `integrations/gemini/generator.py` (`LLMConfig.wire_format`/`base_url`; `from_environment()` resolves the active roster record), `app/frontend/js/35b_providers.jsx` (NEW, 362 — the provider roster + Add-provider form) + `35_settings.jsx` (604→471, AI block hoisted out) + `styles.css` (`.provider-*` + `.provider-egress-warn`); `tests/test_providers_roster.py` (NEW) + `tests/test_providers.py` (responses parser + endpoint-egress); `.claude/security-audits/2026-07-03_custom-providers.md` (PASS); `.claude/docs/custom-providers-spec.md`; `route_35_settings.md` (extended); help corpus; CLAUDE; `INCREMENT-256-NOTES.md`. (callosum-app.html rebuilt.) **No migration** — `custom_providers` is additive; the active selection reuses the flat inc-149 `provider`/`model` fields.
- **What:** the fixed gemini/openai/anthropic/local set becomes **one editable list**. The four presets are pre-seeded, editable rows; **+ Add provider** adds a custom `{name, base URL, API format ∈ Anthropic-messages | Chat-completions | Responses, models[], key}`. A custom cloud provider is **egress-gated exactly like Gemini** (the decision moved to the endpoint — a non-loopback base needs `Allow AI features`; a loopback base is honestly no-egress), and its key is write-only + id-keyed (`provider_key::<uuid>`) outside the synced store.
- **Why:** Jeff's "Add model provider" request — use any OpenAI/Anthropic-compatible endpoint (DeepSeek, Together, Groq, OpenRouter, a local vLLM) without a code change, while preserving invariant #3 (egress off by default) for an arbitrary user URL and the write-only-secret discipline.
- **Experience pass (deadline-adjacent persona "Dana" wiring up DeepSeek):** 6 first-run traps found + **fixed in-increment** — Add-form defaults to **Chat completions** (was Anthropic-messages); host-only Base URL placeholder + a hint + `_norm_base` trims a trailing `/v1` (no double-`/v1`); an added provider is **auto-activated** with a toast; an amber **"AI features are off — Callosum won't contact X"** nudge on an active-but-gated cloud provider; the **"Sends to `<url>`" egress-posture line now shows on custom cloud providers too** (+ a loopback reassurance). See `INCREMENT-256-NOTES.md`.
- **Verify:** frontend built clean via esbuild; all touched chunks under the 600-line cap (35b_providers **362**, 35_settings **471**). Focused suite (`test_providers_roster` + `test_providers`) **27 passed**; **full suite 1008 passed, 1 skipped** (excluding the optional `mcp` suite). Security audit PASS. QA route 35 extended (endpoint-egress-gated + write-only assertions). Manual verification script in `INCREMENT-256-NOTES.md`. Ran on port **8888**.
- **Revert:** `git revert <sha>` (additive feature; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-03 inc 255 — "Extract workspace" help gained the select-in-PDF value capture (verbatim + editable value + an exact-coordinate anchor) and the exact-vs-region Open-at-anchor distinction -->
## 2026-07-03 — Increment 255: Workbench SP2a-2 — select-in-PDF value capture
- **Files:** `app/frontend/js/30f_pdf_gestures.jsx` (+`wbUnionRect`), `30_viewer.jsx` (armed-capture props + a capture branch in the stable `onPagesMouseUp` via an `armedRef` + an amber `.pdf-armed-note` banner), `30c_frame.jsx` (shared capture state above the grid + PDF tabs — `armCapture`/`captureAnchor`/`clearCapture`, threaded to `WorkbenchPane` + each `PdfViewer`), `45_workbench.jsx` (the 📎 anchor **hub** popover: ◎ Select-in-PDF + manual entry + Open-at-anchor; a consume-`useEffect` writes the verbatim value + page/quote + `bbox_json`), `styles.css` (`.wb-anchor.arming` / `.wb-anchor-select` / `.wb-anchor-or` / `.pdf-armed-note`); `.claude/qa-routes/route_65_workbench.md` (extended); help corpus; CLAUDE (254→255 + line-count watch); `INCREMENT-255-NOTES.md`. (callosum-app.html rebuilt.) **Frontend-only; no migration, no backend change** — the cell PUT already accepted `bbox_json` (SP2a-1 stored it; nothing wrote it until now).
- **What:** you can now fill a workbench cell by **selecting the reported number in the source PDF** — click a cell's 📎 → **◎ Select the value in the PDF**, highlight it, and the text drops into the cell **verbatim + editable** while the highlighted spot becomes an **exact-coordinate anchor**. **Open at anchor** then draws the exact passage rectangle; a hand-typed page-only anchor still opens at **region** (a note, no rect).
- **Why:** SP2a-1 made you hand-copy every number (transcription-error risk) and could only anchor at page granularity. Capture removes the copy step and earns an exact highlight — while keeping the human as the filter (nothing is parsed/inferred; the value stays editable) and honoring invariant #2 (precision derived from whether a real bbox exists, at open time).
- **Verify:** frontend built clean via esbuild; all touched chunks under the 600-line cap (30_viewer **563**, 45_workbench **245**, 30c_frame **83**, 30f_pdf_gestures **94**). **Full suite: 992 passed, 1 skipped** (frontend-only; the optional `test_mcp_server.py` is uncollectable without the `mcp` package, as at baseline). QA route 65 extended with the capture flow + the exact-vs-region coordinate-honesty assertion + two capture adversarials. Manual verification script in `INCREMENT-255-NOTES.md`; experience pass (deadline meta-analyst) recorded — no blocking gap. Ran on port **8888**.
- **Revert:** `git revert <sha>` (additive frontend feature; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-02 inc 254 — Remote-access help gained the in-app lockout-recovery path (paste the token, or the local-file-code reset that turns Remote access off); replaced the stale "remove the token from app-settings.json" advice -->
## 2026-07-02 — QA harness isolation: the disposable QA instance no longer inherits the user's shared settings or curated DB (backlog #46)
- **Files:** `tools/qa/_qa_serve.py` (the `qa_server()` env block gains `CALLOSUM_SETTINGS_PATH`→a temp file + `CALLOSUM_DISABLE_REMOTE_ACCESS=1`); `tools/qa/supervisor.py` (new `_codex_env()` — strips `CALLOSUM_DB_URL` + forces remote-access off in the `codex exec` child env; wired into `dispatch`). Doc: backlog #46 marked shipped. Tools-only (exempt from the 600-line cap); no `app/` change, no migration.
- **What:** a QA route stands the app up via `_qa_serve.qa_server()`, which already used a throwaway SQLite DB — but the disposable instance still read the user's **shared** `~/.callosum/app-settings.json`. With **Remote access** toggled ON there (the inc-254 lockout scenario), `AccessControlMiddleware` 401'd every QA request → empty library → `waitForSelector('.paper')` 30 s timeout → a whole run stalled (dead run `qa-inbox/20260702_171244`). Now the throwaway instance points at its own temp settings file and forces the remote-access gate off, so no shared toggle / BYOK key / token can leak in. Belt-and-suspenders in the supervisor: the `codex exec` env drops `CALLOSUM_DB_URL` so a stray *direct* `uvicorn` (off-contract) can't inherit the curated-library pointer we newly persisted at User scope today — it falls back to the harmless throwaway default, never the real library.
- **Why:** diagnosing "did codex finish or run out of credits?" — it did neither; the run died environmentally on this exact leak. Fixing it in the harness (not the app — the egress/access gates all worked as designed) de-risks every future QA run regardless of the user's live Remote-access setting.
- **Verify:** `python -m py_compile` both files; a one-shot `qa_server()` boot check → isolated instance healthy (`/health`=200, `/papers`=200), tore down cleanly. The full supervisor run launched right after (run `20260702_200710`) exercises it end-to-end (route_00 Tier-0 gate first).
- **Revert:** `git revert <sha>` (tools-only env-dict changes; no app/schema/API impact).

## 2026-07-02 — Increment 254: In-app recovery from a remote-access lockout (`POST /access/recover` + AccessLockOverlay)
- **Files:** `app/backend/api/access_recovery.py` (NEW — in-process one-time code + local-file write/verify) + `app/backend/api/routers/access.py` (NEW — gate-exempt, disable-only `POST /access/recover`) + `app/backend/api/access_control.py` (`_RECOVERY_PATHS`; recovery branch: no token, still rate-limited) + `app/backend/api/app.py` (register the router); `app/frontend/js/00_lib.jsx` (401 detection in every `api*` helper → `authRequired` + one-time `onAuthRequired` notifier + `startAccessRecovery`/`submitAccessRecovery`/`clearAccessToken`) + `app/frontend/js/01_recovery.jsx` (NEW — `AccessLockOverlay`) + `40_app.jsx` (wire it) + `03_library.jsx` (propagate `authRequired` into the error state) + `10_pdf_layer.jsx` (errbox: 401 → "Remote access is locked", no more "start the backend") + `35_settings.jsx` (fixed the stale hint) + `styles.css` (`.lockout-*`, reusing the `.axis-modal` shell); `tests/test_access_recovery.py` (NEW +11); `.claude/security-audits/2026-07-02_access-recovery.md` (PASS); `route_35_settings.md` (extended); help corpus; CLAUDE; `INCREMENT-254-NOTES.md`. (callosum-app.html rebuilt.) **No migration.**
- **What:** when **Remote access** (inc 168) is ON but the browser holds no valid token, EVERY call 401s — including `GET /settings` — so the user was stranded, and the on-screen error wrongly blamed a dead backend. Now any 401 raises ONE honest overlay with two testable recovery paths: **(1)** paste the access token → stored client-side → reload; **(2)** *turn Remote access off* → `POST /access/recover {}` writes a 128-bit single-use code to `~/.callosum/recovery-code.txt` (returns only the path, never the code), the user pastes it back → constant-time verify → `set_remote_access_enabled(False)`. Disable-only; never reveals the token/data.
- **Why:** discovered live — the maintainer's own instance 401'd after `remote_access_enabled` was left on with no browser token, a dead-end with no in-app way out. Recovery must prove **local-machine possession** (not just loopback — the middleware can't tell the local browser from a tunnel), so the escape is a code only someone at the machine can read, and it can only move the gate to its safe default (off). Beta-testable end to end.
- **Verify:** `test_access_recovery.py` +11 (module single-use/expiry/overwrite + endpoint start-returns-only-path/valid-disables/wrong-leaves-on/never-reveals-token/oversized-422/rate-limit-429/harmless-when-off) + existing `test_access_control.py` green; ruff+format clean; QA 195/195 API + 901/901 FE, 0 uncovered; audit PASS. Security: gate-exempt but rate-limited (`"recover"` key, kept out of `_EXEMPT_PATHS`), input capped + constant-time compared, fixed file path (no traversal), no new dependency, no egress. **Experience pass** (persona: non-technical locked-out beta tester) → found the code-file path had no "how to open it" guidance (the make-or-break gap) + jargon; fixed in-increment (Copy-path button + Notepad/Finder tip, named the actual "Allow citing from Google Docs" toggle, "Get my recovery code" button, dropped "Bearer" jargon, a green success confirmation before reload). **Full suite: 992 passed, 1 skipped** (excludes the optional `test_mcp_server.py` — `mcp` not installed here, pre-existing).
- **Revert:** `git revert <sha>` (additive endpoint + frontend overlay; no migration/destructive change).

## 2026-07-02 — Startup: auto-create the SQLite parent dir + collapse the DB-failure traceback flood (+ hermetic keychain test isolation)
- **Files:** `app/backend/api/startup.py` (new `_ensure_sqlite_parent_dir`, called from `_upgrade_database_to_head`; failure log collapsed to one line); `tests/conftest.py` (force `app_settings._keyring()`→None in the autouse fixture); `tests/test_startup_migration.py` (+2 tests, +1 assertion); `.claude/security-audits/2026-07-02_startup-db-dir-autocreate.md` (PASS).
- **What:** a no-config `uvicorn app.backend.api.app:app ...` launch (no `CALLOSUM_DB_URL`) fell back to `DEFAULT_DB_URL = sqlite:///.local/validation/validation.sqlite`; when that dir didn't exist SQLite raised `unable to open database file` and **every** DB request 500'd while `/` still served — printing a full traceback per hit. Now the startup migration first creates the SQLite URL's parent dir (so it boots a fresh empty DB), and a genuine DB failure logs **one actionable ERROR line** naming the DB + telling the user to set `CALLOSUM_DB_URL` (full trace demoted to DEBUG). No-op for in-memory/non-SQLite URLs.
- **What (test hermeticity):** the full-suite run surfaced 8 pre-existing failures in `test_settings`/`test_sync_endpoints`/`test_auth_oidc` on this dev machine — `app_settings._get_secret` reads the OS keychain (Windows Credential Vault, holding real callosum secrets) *before* the isolated settings file, so hermetic settings/sync/auth tests were reading the maintainer's real Gemini key / sync passphrase (a 409 "already set up", a leaked stored key). The autouse fixture now forces `_keyring()`→None so secrets fall back to the per-test temp file. **Not** caused by the startup change — this run simultaneously proved `startup.py` innocent (981 passed, 1 skipped).
- **Why:** the user kept launching in fresh shells without the env var and hit a console flood of tracebacks (not a code bug — a missing-DB-path ergonomics gap). Dev/ops ergonomics; no user-facing help-corpus impact.
- **Revert:** `git revert <sha>` (single-file behavior; no migration/schema/API change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-02 inc 252 — help corpus gained "Converting effect sizes" (the deterministic effect-size converter, meta-analysis workbench SP1) -->
## 2026-07-02 — Increment 252: Effect-size converter (meta-analysis workbench SP1)
- **Files:** `app/backend/methods/effectsize.py` (NEW pure converter — Conversion dataclass + SMD/SD-derivation/correlation/binary/cross-metric + `convert` dispatch + `NO_AGGREGATION`) + `app/backend/api/routers/methods.py` (+`POST /methods/effect-size`) + `app/frontend/js/08i_methods_effectsize.jsx` (NEW "Effect-size converter" panel, order 38) + `styles.css` (`.es-*`); `tests/test_effectsize.py` (+12); `.claude/security-audits/2026-07-02_effectsize-converter.md` (PASS); `route_64_methods_effectsize.md` (NEW); help corpus; THIRD-PARTY-NOTICES; CLAUDE; backlog; future-track doc; `INCREMENT-252-NOTES.md`. (callosum-app.html rebuilt.) **No migration.**
- **What:** a METHODS-panel calculator that converts one study's reported statistics → a common meta-analytic metric (Hedges' g, Fisher's z, log OR/RR, risk difference) + variance + a 95% CI, via standard cited formulas, with the conversion **path shown**, the **formula source cited**, and every **derivation/continuity/approximation choice recorded** + a **copy value + variance** button. The first buildable slice of the meta-analysis extraction workbench (#36 future-track).
- **Why:** the safe, deterministic, egress-free core of the workbench — the trusted sink the later LLM-drafted extraction pipeline hands its verified data into; genuinely useful standalone. Chose converter-first + the fullest converter (AskUserQuestion).
- **Verify:** pytest 971→(full-suite pending) +12 hermetic `test_effectsize.py`; ruff+format clean; QA 183/183 API + 828/828 FE, 0 uncovered; audit PASS; Principles+A-A aligned (the Bayes/statcheck/GRIM deterministic-recompute class). **The load-bearing boundary is structural + test-pinned:** converts one study at a time, NEVER pools/models/meta-regresses/does bias inference (`test_no_aggregation_code_path` — AST scan, no aggregation import/def); show-the-work (path + formula + choices + CI, no opaque number); cross-metric flagged as an approximation. Anchors hand+scipy-verified against Borenstein et al. 2009 formulas. Local/no-egress/no-LLM/no-migration/no-dependency. Headed-verified (`drive_inc252_effectsize.py` — SMD→Hedges' g 0.592442 + path + Borenstein source; Binary→log OR 0.916291; Cross d→r 0.2425 + APPROXIMATION caveat; no aggregation control; 0 console/page/genai). Experience pass (meta-analyst) → added the copy value+variance extract-loop button in-increment.
- **Revert:** `git revert <shas>` (methods+endpoint+panel; no migration/destructive change).

## 2026-07-02 — Increment 251: Persist transparency signals (backlog #44 increment 1b)
- **Files:** `app/backend/methods/transparency_findings.py` (NEW producer — present-only FACTs + per-disclosure status) + `app/backend/persistence/signals_repo.py` (+`store_transparency_status`/`count_transparency_review`/`TRANSPARENCY_SIGNAL`) + `app/backend/api/routers/transparency.py` (+`POST/GET /methods/transparency/run` + `GET /methods/transparency/summary` + async job) + `app/backend/api/app.py` (`transparency_jobs`) + `app/backend/persistence/repository.py` (SIGNAL_FILTERS `(type, source|None, status)` + 7 transparency review queues) + `app/frontend/js/{08h_methods_transparency,03_library,10_pdf_layer,40_app}.jsx` + `styles.css` (batch trigger + review-queue links + a `.transparency-chip`); `tests/test_transparency_findings.py` (+8); `.claude/security-audits/2026-07-02_transparency-persist.md` (PASS); `route_63` extended; help corpus; CLAUDE; backlog; `INCREMENT-251-NOTES.md`. (callosum-app.html rebuilt.) **No migration.**
- **What:** turns the inc-250 ephemeral panel into persistent, library-wide signal. A **Check all papers** batch persists each paper's *detected-present* disclosures as evidence-carrying **FACTs** (paper_findings, inc 130 — render as marks in the Review pane) + every disclosure's **check status** (open_science_signals, inc 97). Powers **7 review-queue library filters** ("data / code / COI / funding / registration / preregistration not detected — go look", + the *present* upon-request case) + a Library-header **🔎 N · open data not detected** chip (indigo work-queue color).
- **Why:** #44 increment 1b + the inc-250 experience-pass F4 (library-wide surfacing + a review queue). The consumer-side statcheck-persist / retraction-FACT pattern.
- **Verify:** pytest 963→(full-suite pending) +8 hermetic `test_transparency_findings.py`; ruff+format clean; QA 182/182 API + 814/814 FE, 0 uncovered; audit PASS; Principles + A-A aligned (statcheck-persist / retraction-FACT class). **The A-A no-accusation boundary is structural + test-pinned:** present-only FACTs (an absence is NEVER a fact — `test_bare_paper_writes_no_absence_facts`); review-queue-not-verdict wording ("not detected — go look", never "hides data"); no score/rank field; precondition-scoped filters (registration n/a excluded, upon-request is the present case). Local/no-egress/no-LLM/no-migration/no-dependency. Headed-verified (`drive_inc251_transparency_persist.py` — an open + a bare paper: batch → "2 checked · 1 with a disclosure" + 7 queues; the chip "🔎 1 · open data not detected" → narrows to the bare paper only [the open one excluded]; only the open paper has FACTs [the bare has none — the absence-is-never-a-fact pin]; 0 console/page/genai). Experience pass (open-science-vetter, inline) → delivers the inc-250 F1/F4 (library surfacing + review queue); the batch trigger stays panel-buried (the standing F1 chip finding, already filed to #23).
- **Revert:** `git revert <shas>` (producer+signals+router+repository-filter+frontend; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-02 inc 250 — help corpus gained "Auditing transparency signals" (#44, the Lakens track: ODDPub/rtransparent-derived open-science-disclosure detectors) -->
## 2026-07-02 — Increment 250: Transparency-signals auditor (backlog #44 increment 1, the Lakens track)
- **Files:** `app/backend/methods/transparency.py` (NEW pure auditor — 7 detectors, NO gate) + `app/backend/api/routers/transparency.py` (NEW `GET /papers/{id}/transparency`) + `app/backend/api/app.py` (import after tags + include after meta-analysis) + `app/frontend/js/08h_methods_transparency.jsx` (NEW "Transparency signals" panel, order 36); `tests/test_transparency.py` (+13); `.claude/security-audits/2026-07-02_transparency-signals.md` (PASS); `.claude/qa-routes/route_63_methods_transparency.md` (NEW); help corpus; THIRD-PARTY-NOTICES; CLAUDE; `INCREMENT-250-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a METHODS panel (the statcheck/LMM/meta sibling) that reads a paper's extracted text and detects whether it *discloses* 7 open-science artifacts (data availability, code/software availability, conflict-of-interest, funding, protocol/trial registration, preregistration, "available upon request" weak signal) — present/not-found/not-applicable, with evidence page-open at region precision, the in-context basis + explainer, and a factual status tally. Rule-based (ODDPub/rtransparent-derived), local, no AI. FLAG-not-ADJUDICATE: no transparency score, no rank, no verdict; **"not detected" ≠ "absent"**; never an accusation of the authors.
- **Why:** increment 1 of the Lakens track (#44) — help a reader see what a paper discloses (are the data/code shared, conflicts/funding declared, a trial registered?) before relying on it. The consumer-side auditor pattern (statcheck/LMM/meta), gated hard on the A-A no-accusation veto.
- **Verify:** pytest 963 (+13 hermetic `test_transparency.py`); ruff+format clean; QA 179/179 API + 808/808 FE, 0 uncovered; the no-accusation boundary structural + test-pinned (`test_no_accusatory_language`); audit PASS; Principles + A-A aligned (Example 3 / statcheck-LMM class; the no-accusation veto is load-bearing); local/no-egress/no-LLM/no-migration/no-dependency; NO gate (every paper gets the 7 checks; endpoint response is just `{checks}`). Headed-verified (`drive_inc250_transparency.py` — an open-footer non-trial paper: 7-row checklist [data/code/COI/funding ✓ detected, preregistration "not detected"+"check the paper", registration + upon-request n/a], tally "4 disclosed · 1 not detected · 2 not applicable", ODDPub basis, credit ＋add, evidence page-open; 0 console/page/genai). Experience pass (open-science-vetter, inline) → F1 report-card chip / F4 persist-as-findings-candidate / F2 credit-footer-on-not-applicable filed cross-method to #44 / the shared #23 chip item.
- **Revert:** `git revert <shas>` (methods+router+wiring+panel; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-02 inc 249 — help corpus gained "Auditing meta-analysis reporting" (#36, the consumer-side reporting auditor) -->
## 2026-07-02 — Increment 249: Meta-analysis reporting auditor (backlog #36, consumer-side)
- **Files:** `app/backend/methods/metaanalysis.py` (NEW pure auditor — `_META` gate + 7 checks) + `app/backend/api/routers/metaanalysis.py` (NEW `GET /papers/{id}/meta-analysis`) + `app/backend/api/app.py` (import + include after lmm) + `app/frontend/js/08g_methods_metaanalysis.jsx` (NEW "Meta-analysis reporting" panel, order 35) + `app/frontend/js/09_placeholders.jsx` (removed the meta-analysis coming-soon stub); `tests/test_metaanalysis.py` (+14); `.claude/security-audits/2026-07-02_metaanalysis-auditor.md` (PASS); `.claude/qa-routes/route_62_methods_metaanalysis.md` (NEW); help corpus; THIRD-PARTY-NOTICES; CLAUDE; backlog; `INCREMENT-249-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a METHODS panel (the statcheck/LMM sibling) that reads a published meta-analysis's extracted text and flags whether it *reports* 7 methodological choices (effect-size metric, model, heterogeneity I²/τ²/Q, publication bias, sensitivity/influence, study count k+participants, search & selection) — present/not-found/not-applicable, with evidence page-open at region precision, a grounded cited recommendation, an always-on explainer, and a factual status tally. FLAG-not-ADJUDICATE: never pools/models/re-computes/scores/accuses.
- **Why:** the consumer-side slice of #36 (the maintainer chose "reporting auditor now, extraction workbench next") — help a reader vet a meta-analysis's methodological reporting before relying on it, the sibling of the LMM/Bayesian/statcheck auditors.
- **Verify:** pytest 950 (+12 hermetic `test_metaanalysis.py`); ruff+format clean; QA 178/178 API + 802/802 FE, 0 uncovered; the identity boundary (never runs statistics) structural + test-pinned (`test_no_statistical_computation_import`); audit PASS; Principles aligned (Example 3 / the statcheck-LMM class); local/no-egress/no-LLM/no-migration/no-dependency. Headed-verified (`drive_inc249_metaanalysis.py` — a mini-meta: 7-row checklist [effect-size ✓, pub-bias not-found + k≥10 caveat, search n/a], tally, basis, credit ＋add, evidence page-open; 0 console/page/genai). Experience pass (deadline-citer) → F1 chip / F2 credit-footer-on-non-meta / F4 persist-as-candidate filed to #23 consolidated with the LMM entries.
- **Revert:** `git revert <shas>` (methods+router+wiring+panel+stub-removal; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-02 inc 248 — help corpus repointed the citation-concentration + how-it's-cited sections to the THEORY → Cite tabs -->
## 2026-07-02 — Increment 248: accordion panels polish (headers always visible, section padding, Cite tabs)
- **Files:** `app/frontend/styles.css` (`.pane-sidebar`/`.pane-detail` flex-column + overflow:hidden; `.pane-accordion`/`.acc-section`/`.acc-body` flex + `.acc-body` padding) + `app/frontend/js/05_panes.jsx` (register funcs own metadata + `tabLabel` + per-tab `hideInReadOnly`; PaneAccordion internal-scroll + tab filtering) + `37_cite.jsx` (tabLabel "Suggest") + `08b_methods_citation_equity.jsx` + `08c_methods_citation_context.jsx` (→ Cite tabs) + `09_placeholders.jsx` (removed the shipped Bayesian + Mixed-model stubs) + `25_detail.jsx` (inline padding vertical-only). callosum-app.html rebuilt. Docs: `route_51`/`route_53`/`route_42`, help corpus, DESIGN.md, `INCREMENT-248-NOTES.md`.
- **What:** (A) accordion side-panes no longer scroll as a whole — the open section's body scrolls internally so all collapsed headers stay visible; (C) `.acc-body` horizontal padding so section bodies aren't flush to the resize bar; (B) Citation concentration + How-it's-cited moved from METHODS to tabs of the THEORY "Cite" section `[Suggest | Citation concentration | How it's cited]` with per-tab read-only hiding; + removed two stale coming-soon stubs (Bayesian, Mixed-model — their real panels shipped) that surfaced as a duplicate/mis-ordered header.
- **Why:** maintainer's three next-up UX asks (headers-visible, padding, group the citation tools); the stub cleanup fixes a duplicate section header the maintainer would see.
- **Verify:** frontend-only — pytest 938 unchanged (`test_frontend_assembly` 5/5); ruff+format clean; QA 177/177 API + 796/796 FE, 0 uncovered; no migration/egress/dependency/endpoint; Principles non-triggering (layout + IA move, moved panels' honesty unchanged); no audit (no new fetch/path). Headed-verified (`drive_inc248_panels.py` — internal-scroll mechanism, 14px body padding, Cite 3-tab strip + switch, no duplicate Bayesian; 0 console/page/genai).
- **Revert:** `git revert <sha>` (all-frontend + docs; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-02 inc 247 — help corpus gained "Auditing mixed-model reporting" (#23, the LMM auditor) -->
## 2026-07-02 — Increment 247: LMM-reporting completeness auditor (backlog #23)
- **Files:** `app/backend/methods/lmm.py` (NEW pure auditor) + `app/backend/api/routers/lmm.py` (NEW `GET /papers/{id}/lmm`) + `app/backend/api/app.py` (import + include) + `app/frontend/js/08f_methods_lmm.jsx` (NEW "Mixed-model reporting" panel) + `app/frontend/styles.css` (`.lmm-*`, tokens); `tests/test_lmm.py` (+14); `.claude/security-audits/2026-07-02_lmm-auditor.md` (PASS); `.claude/qa-routes/route_61_methods_lmm.md` (NEW); help corpus; THIRD-PARTY-NOTICES; CLAUDE; backlog; `INCREMENT-247-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a METHODS auditor — the statcheck sibling for linear mixed models. It reads a mixed-model paper's extracted text and flags whether it *reports* 7 things (random-effects structure, df/inference method, convergence/singular fit, estimation REML/ML, ICC, marginal/conditional R², and — for longitudinal designs with dropout — a missing-data sensitivity analysis). Each check present / not-found / not-applicable, with a grounded cited recommendation + an always-on literacy explainer + a factual status tally. **It never runs a model, an imputation, or a sensitivity analysis, and never ingests raw data.** Local, deterministic, no AI, no egress.
- **Why:** the standing new-METHODS-auditor candidate (#23), built to its future-track doc's exact FLAG-not-ADJUDICATE shape; the maintainer chose all-7-checks + the literacy explainer.
- **Verify:** FLAG-not-ADJUDICATE structurally — no score/verdict/rank (the tally is a plain status count, not a grade); ICC + missing-data are precondition-scoped (n/a when not applicable — no flag on every LMM); "not found" = "not detected in the extracted text — check the paper", never "missing"; the never-runs-a-model identity boundary is pinned by a static import test; each check credits its source in-context + a ＋add-to-library. pytest 938 (+14); ruff+format clean; frontend rebuilt (`test_frontend_assembly` 5/5); QA 177/177 API + 796/796 FE, 0 uncovered; audit PASS; Principles aligned. Experience pass (deadline-citer persona) → a factual tally line + de-emphasized n/a rows fixed in-increment; discoverability chip + persist-as-candidate filed to backlog. Headed-verified (7-row checklist, present/not-found/n-a, region page-open, credit; 0 console/page/genai). **No migration, no new dependency, no egress, no LLM.**
- **Revert:** `git revert <sha>` (all-new pure module + endpoint + panel + one `include_router`; additive help/NOTICES; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-01 inc 246 — help corpus gained "Where to submit (choosing a journal)"; #40 SP1 complete -->
## 2026-07-01 — Increment 246: PUBLISHERS "where to submit" SP1b — the METHODS panel + weighting + first-use choice gate
- **Files:** `app/frontend/js/08e_methods_publishers.jsx` (NEW panel) + `app/frontend/js/35_settings.jsx` (a "Where to submit" section) + `app/frontend/styles.css` (`.pub-*`, tokens) + `app/backend/app_settings.py` (local publisher prefs) + `app/backend/api/routers/settings.py` (additive prefs + validation); `tests/test_settings.py` (+2); `.claude/security-audits/2026-07-01_publishers.md` (SP1b addendum, PASS); `.claude/qa-routes/route_60_publishers.md` (`fe:` + gate/legibility assertions); help corpus; CLAUDE; backlog; `INCREMENT-246-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the frontend of #40 — a METHODS "Where to submit" panel (paper-picker OR abstract+subject → the SP1a run → uniform per-journal profile cards, each fact linking to its source) behind a **first-use choice gate** (nothing pre-selected; the open-science weighting + result breadth forced **together** so the weighting isn't the lone choice) + an always-visible output weighting thumb (adjust + re-run). Prefs are local, validated, never transmitted; the panel reads them from `/settings` and passes weighting+top_k to the unchanged SP1a endpoint.
- **Why:** completes #40 SP1 (SP1a engine inc 245 + SP1b UI inc 246), built to the future-track choice-gate doc's exact shape.
- **Verify:** the vetoes are structural — no pre-selected default (Save disabled until both set), weighting-never-alone, prefs never transmitted (they reach only the local endpoint; SP1a's recording-transport test still holds), no composite `*score*` shown, no "predatory", every candidate (incl. closed) appears, elevate-don't-denigrate, output legibility. pytest 924 (+2); ruff+format clean; frontend rebuilt (`test_frontend_assembly` 5/5); QA 176/176 API + 790/790 FE, 0 uncovered; audit addendum PASS; Principles/A-A aligned. Headed-verified (gate no-pre-selection → save → run → 2 cards incl. closed + thumb; 0 external, 0 console/page). **No migration, no new dependency, no new endpoint** (additive `/settings` fields).
- **Revert:** `git revert <sha>` (a new frontend chunk + additive settings fields + CSS; no migration/destructive change).

## 2026-07-01 — Increment 245: PUBLISHERS "where to submit" journal-finder (backlog #40, SP1a: backend engine + endpoint)
- **Files:** `integrations/openalex/sources.py` (NEW `OpenAlexSourcesClient`) + `integrations/doaj/journals.py` (NEW `DoajJournalsClient`) + `app/backend/methods/publishers.py` (NEW pure engine) + `app/backend/api/routers/publishers.py` (NEW async endpoint) + `app/backend/api/app.py` (import/state/include + `create_app` injection); `tests/test_publishers.py` (+13, hermetic); `.claude/security-audits/2026-07-01_publishers.md` (PASS); `.claude/qa-routes/route_60_publishers.md` (NEW); CLAUDE; backlog; `INCREMENT-245-NOTES.md`. **No frontend build (backend-only).**
- **What:** the graduation of #40 — from an abstract, match candidate journals **locally** (SPECTER) and return a uniform factual profile per journal (fit · OA color · APC+waiver · license · DOAJ Seal · open impact), ranked by fit + optionally re-ordered by an open-science `weighting`. Two clients (OpenAlex `/sources`, DOAJ journals) + a pure profile engine + `POST/GET /methods/publishers/run`. SP1b = the panel + the visible weighting + the first-use choice gate.
- **Why:** the deliberately-controversial future-track, gated through Principles + A-A at graduation and built to its principled shape. Maintainer scope: full principled core · OpenAlex + DOAJ · both inputs.
- **Verify:** the vetoes are structural + test-pinned — **the abstract never leaves the machine** (topic-seeded pool + local embed; recording-transport test), **no composite score / no "predatory" label**, **every candidate appears** (closed journals too — gate the boost not the listing), elevate-don't-denigrate (`elevated_for` goods, never a deficit flag). SSRF closed (ids validated before any request; constant hosts; subject a bound param). Egress = public bibliographic metadata, cached + fail-closed, **NOT** the Gemini gate. pytest 922 (+13); ruff+format clean; QA 176/176 API + 771/771 FE, 0 uncovered; audit PASS; Principles/A-A aligned. **No migration, no new dependency** (SPECTER via the existing stack).
- **Revert:** `git revert <sha>` (all-new modules + additive `create_app` params + one `include_router`; no migration/destructive change).

## 2026-07-01 — Increment 244: Bayesian auditor SP4 — Tier-3 textual-coherence advisory prompts (FULLY CLOSES #24)
- **Files:** `app/backend/methods/bayes.py` (`_advisory_notes` + `AdvisoryNote` + `advisories` on `BayesCompleteness`) + `app/backend/api/routers/methods.py` (additive `advisories`) + `app/frontend/js/08d_methods_bayes.jsx` (`BayesAdvisories` block) + `styles.css` (`.bayes-advisory*`, neutral not amber); `tests/test_bayes.py` (+5); `route_59`; the audit addendum 3; CLAUDE; backlog; `INCREMENT-244-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** two conservatively-gated **Tier-3 advisory** prompts (never flags/verdicts) — credible-vs-confidence mislabel + BF-direction — clearly demarcated from the checklist, worded as "requires expert judgment" exploratory prompts (the future-track doc's Stage 3).
- **Why:** the last "build all three" thread to close out #24.
- **Verify:** honesty made structural — Bayesian-gated, suppressed when both interval types appear, BF-direction only on the specific co-occurrence, neutral (not amber) styling, prompt-not-verdict wording. pytest 909 (+5); `test_frontend_assembly` 5/5; ruff+format clean; QA 174/174 API + 771/771 FE, 0 uncovered; audit addendum PASS; Principles aligned. Headed-verified (2 prompts + "requires expert judgment" + neutral border; 0 console/page/genai). **No egress/LLM/migration/dependency. FULLY CLOSES future-track #24.**
- **Revert:** `git revert <sha>` (additive response field + a pure function + panel block; no migration/destructive change).

<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-07-01 inc 243 — "Checking Bayes factors" now covers correlation + the ANOVA caveat -->
## 2026-07-01 — Increment 243: Bayesian auditor SP3 — Pearson-correlation recompute (Ly 2016); ANOVA declined as a finding
- **Files:** `app/backend/methods/bayes.py` (`corr_bf10` + `_RSTAT` + `_scan_text` branches on t/r) + `app/backend/api/routers/methods.py` (additive `computed_correlation`) + `app/frontend/js/08d_methods_bayes.jsx` (correlation label + 2-paper credit); `tests/test_bayes.py` (+5); `route_59_methods_bayes.md`; the audit addendum 2; THIRD-PARTY-NOTICES (Ly 2016); help corpus; CLAUDE; backlog; `INCREMENT-243-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the "more designs" close-out — recompute the default **correlation** Bayes factor (Ly et al. 2016) for inline `r(df) = …, BF10 = …`; ANOVA/regression **declined as a finding** (not faithfully recomputable/verifiable from F+df → would produce false flags).
- **Why:** maintainer asked to close out #24; AskUserQuestion → "build all three" remaining threads.
- **Verify:** `corr_bf10` verified EXACTLY against pingouin `bayesfactor_pearson` (7 anchors incl. −r); no new dep (scipy). ANOVA candidate failed the J=2→two-sample-t reduction (0.63→0.52) → declined per rule #2 + the A-A veto. pytest 904 (+5); `test_frontend_assembly` 5/5; ruff+format clean; QA 174/174 API + 769/769 FE, 0 uncovered; audit addendum PASS; Principles aligned. Headed-verified (a correlation reproduces row + both credit papers; 0 console/page/genai). **No egress/LLM/migration/dependency.**
- **Revert:** `git revert <sha>` (additive response field + a pure function + panel copy; no migration/destructive change).

## 2026-07-01 — Increment 242: Bayesian auditor SP2 — a Tier-2 BARG/WAMBS/JASP reporting checklist (completes #24)
- **Files:** `app/backend/methods/bayes.py` (`audit_completeness` + the BARG/WAMBS/JASP detection) + `app/backend/api/routers/methods.py` (additive `completeness` block on `GET /papers/{id}/bayes`) + `app/frontend/js/08d_methods_bayes.jsx` (a Reporting checklist section) + `styles.css` (`.bayes-check-*`, tokens); `tests/test_bayes.py` (+5); `route_59_methods_bayes.md`; the audit addendum; help corpus; CLAUDE; backlog; `INCREMENT-242-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the completeness half of the Bayesian auditor — presence/absence of the prior, convergence diagnostics, and a sensitivity analysis (BARG/WAMBS/JASP), plus a coherence flag when a reported diagnostic breaches a convention. Runs only on a Bayesian paper; never a verdict.
- **Why:** completes the Bayesian auditor (#24). Maintainer fork: the BARG/WAMBS core (over the riskier textual-coherence path).
- **Verify:** honesty controls made structural (Bayesian-gated, convergence-n/a for closed-form BF, "not found" = not-detected-in-text never "missing", conventions-not-laws). pytest 899 (+5); `test_frontend_assembly` 5/5; ruff+format clean; QA 174/174 API + 769/769 FE, 0 uncovered; audit addendum PASS; Principles gate aligned. Headed-verified (checklist [prior ✓present / convergence n/a / sensitivity not-found] + credit; 0 console/page/genai). **No egress/LLM/migration/dependency.**
- **Revert:** `git revert <sha>` (additive response field + a panel section + a pure function; no migration/destructive change).

## 2026-07-01 — Increment 241: Bayesian auditor SP1 — recompute default JZS Bayes factors (statcheck sibling)
- **Files:** `app/backend/methods/bayes.py` (NEW — JZS BF recompute + inline extraction) + `app/backend/api/routers/methods.py` (`GET /papers/{id}/bayes`) + `app/frontend/js/08d_methods_bayes.jsx` (NEW METHODS panel); `tests/test_bayes.py` (NEW, +10); `.claude/qa-routes/route_59_methods_bayes.md`; `.claude/security-audits/2026-07-01_bayes-auditor.md`; THIRD-PARTY-NOTICES; help corpus; CLAUDE; backlog; `INCREMENT-241-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the Bayesian sibling of statcheck — recompute a paper's reported default (JZS) Bayes factors for inline t-test results (`t(df) = …, BF10 = …`) and flag where they don't reproduce under the default prior. Local, deterministic, no AI.
- **Why:** the maintainer picked a new METHODS auditor (whole A+B lists done); AskUserQuestion → Bayesian auditor + SP1=recompute-only.
- **Verify:** JZS math verified vs the pingouin anchor (26.744 vs 26.743). pytest 894 (+10); `test_frontend_assembly` 5/5; ruff+format clean; QA 174/174 API + 767/767 FE, 0 uncovered; audit PASS; Principles gate aligned (statcheck class; declined score/verdict). Headed-verified (a reproduces row + credit ＋add-to-library; 0 console/page/genai). **No egress/LLM/migration/dependency.**
- **Revert:** `git revert <sha>` (additive; a new endpoint + panel + a pure module; no migration/destructive change).

## 2026-07-01 — Increment 240: touch-native highlighting on mobile (the last B5 nicety)
- **Files:** `app/frontend/js/30f_pdf_gestures.jsx` (new `useTouchSelectionPicker` hook) + `30_viewer.jsx` (the hook call, mobile-gated); `styles.css` (`.app.mobile` finger-sized `.hl-swatch`/`.hl-note-add`); help corpus; DESIGN.md; CLAUDE; backlog; `INCREMENT-240-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** create highlights by touch — a long-press text selection on a phone now surfaces the same color-picker pill desktop shows (via a debounced `selectionchange`, since `mouseup` doesn't fire on touch), with finger-sized swatches; tap a color to highlight, or ＋ note.
- **Why:** the last B5 nicety (touch-native annotation). Maintainer forks: contextual pill + swatch row (reuse everything).
- **Verify:** frontend-only (no Python touched) → pytest 884 unchanged; `test_frontend_assembly` 5/5; ruff+format clean; QA 173/173 API + 761/761 FE, 0 uncovered. Headed-verified at 390×844 (DOM Selection → picker [5 swatches, +note, 28px] → tap → 1 annotation POST + highlight renders + picker closes; 0 errors). **No new endpoint/flow/migration/dependency.**
- **Revert:** `git revert <sha>` (frontend-only; no destructive change; desktop untouched — the hook is mobile-gated).

## 2026-07-01 — Increment 239: B5 SP3 — the mobile PDF reader (fit-width + pinch-zoom + citation back pill)
- **Files:** `app/frontend/js/30_viewer.jsx` (mobile fit-width default + Two-up hidden + touch-action + usePinchZoom call) + NEW `30f_pdf_gestures.jsx` (usePinchZoom + MinimapTrack, rule-#1 split) + `30c_frame.jsx` + `40_app.jsx` (mobile prop threading, region-switch on citation-open, `.pdf-back-pill`); `styles.css` (`.pdf-back-pill`, tokens); `route_32_viewer_annotations.md`; DESIGN.md; help corpus; CLAUDE; backlog; `INCREMENT-239-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** phone-native PDF reading — the page fits the screen by default, pinch-to-zoom works, and tapping a synthesis citation pulls the reader into view with a one-tap "← Synthesis" return.
- **Why:** the B5 SP2-deferred slice. Maintainer forks: back pill + core+pinch-zoom.
- **Verify:** frontend-only (no Python touched) → pytest 884 unchanged; `test_frontend_assembly` 5/5; ruff+format clean; QA 173/173 API + 760/760 FE, 0 uncovered. Rule-#1 split of 30_viewer (629→573). Headed-verified at 390×844 (fit-width, no Two-up, minimap tick, pinch 74%→148%, citation→back-pill→return; 0 errors). **No new endpoint/migration/dependency.**
- **Revert:** `git revert <sha>` (frontend-only; no destructive change; desktop untouched).

## 2026-07-01 — Increment 238: B5 SP2 — the read-only companion UI (hide write controls); B5 complete
- **Files:** `app/backend/api/routers/health.py` (`read_only` field) + `app/backend/app_settings.py` (`read_only_mode`); `adapters/mobile/cloudflared-config.yml` (widened read ingress); `app/frontend/js/40_app.jsx` (tri-state `readOnly` from `/health` + `healthLoaded`) + `03_library.jsx` (rescan gated) + `05_panes.jsx` (`hideInReadOnly` filter) + `06/07/08/08b/08c/09` (analysis sections flagged `hideInReadOnly`) + `30c_frame.jsx` (Discover/Feed hidden) + `10_pdf_layer.jsx` (header/bulk/markers) + `20_synthesis.jsx` (run/reverify/save/delete) + `15_axes.jsx`/`15b_axis_card.jsx` (axis writes) + `25_detail.jsx`/`24_detail_fields.jsx` (NEW — split; `DetailReadOnly` context; CiteRow gate) + `25b_tags.jsx` (tag writes) + `16_queue.jsx` (queue writes) + `02_mobilenav.jsx`; `styles.css` (`.read-only-badge`, `.detail-ro`); `tests/test_mobile_ingress.py` (+11); `.claude/security-audits/2026-07-01_mobile-reading.md` (SP2 addendum); `route_30_detail_pane.md`; DESIGN.md; help corpus; CLAUDE; backlog; `INCREMENT-238-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a read-only callosum instance (CALLOSUM_READ_ONLY=1) now advertises `read_only` on `/health`, and the app hides every write control + shows a "Read-only" badge, so the mobile companion reads clean with no dead buttons + no doomed writes on load.
- **Why:** backlog B5 SP2. Maintainer fork: comprehensive (all panels).
- **Verify:** +11 hermetic tests (broadened ingress forward/block lists + `/health.read_only`). pytest 884. QA 173/173 API + 758/758 FE, 0 uncovered. Audit addendum PASS. **No new endpoint, no migration, no new dependency.** Rule-#1 split of 25_detail (624→492). Headed-verified (read-only: badge + hidden write cluster/Discover + static Details + 0 request-403s on load; read-write: all controls return; 0 errors).
- **Revert:** `git revert <sha>` (a `/health` field + client control-hiding + config; default-false; no destructive change).

## 2026-07-01 — Increment 237: B5 SP1 — responsive mobile reading, read-only over the tunnel
- **Files:** `04_layout.jsx` (mobile flag + mobilePane), `02_mobilenav.jsx` (NEW — MobileNav), `40_app.jsx` (mobile branch + region-node extraction), `styles.css` (`.app.mobile`/`.mobile-nav`), `access_control.py` (CALLOSUM_READ_ONLY method gate) + `app_settings.py` (`read_only_mode()`), `adapters/mobile/cloudflared-config.yml` + `README.md` (NEW — read-only ingress + runbook), `tools/run_tunnel.py` (`--mobile`), `.gitignore`, `tests/test_mobile_ingress.py` (NEW +22), `.claude/security-audits/2026-07-01_mobile-reading.md`, `route_00_smoke_readonly.md`, help corpus, `.claude/docs/specs/2026-07-01-mobile-reading-sp1.md`, CLAUDE, backlog, `INCREMENT-237-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the app is now responsive (single-column + a bottom nav on a phone-width viewport), and there's a read-only deployment path over the cloudflared tunnel (a `CALLOSUM_READ_ONLY` method gate + a read-only ingress allowlist) so you can read your library on your phone.
- **Why:** backlog B5. Maintainer forks: responsive whole-app (not a separate `/m`) + full reader.
- **Verify:** +22 hermetic tests (ingress regex forwards reads / blocks writes; the method gate 403s writes incl. a path-matched POST; off-by-default lets writes through). pytest 872. QA 173/173 API + 758/758 FE, 0 uncovered. Audit PASS. **No new endpoint, no migration, no new dependency.** Headed-verified (`drive_inc237_mobile.py` — phone single-column + nav, desktop grid restored; 0 errors).
- **Revert:** `git revert <sha>` (responsive branch + a middleware gate + config; default-off; no destructive change).

## 2026-07-01 — Increment 236: library bundle SP3 — re-verify an imported synthesis against my library (B2 complete)
- **Files:** `app/backend/summarization/reverify.py` (NEW — `reverify_imported_summary`), `app/backend/api/routers/summaries.py` (`POST /summaries/{id}/reverify` + import), `app/backend/metadata/library_bundle.py` (`_import_syntheses` stores each citation's `source` identity + docstring), `app/frontend/js/20_synthesis.jsx` (Re-verify button + handler), `tests/test_reverify.py` (NEW +2), `.claude/security-audits/2026-07-01_library-bundle.md` (SP3 addendum 2), `.claude/qa-routes/route_54_library_bundle.md`, `app/backend/help/help_content.md`, `.claude/docs/specs/2026-07-01-library-bundle-reverify-sp3.md`, CLAUDE, backlog, `INCREMENT-236-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a "Re-verify against my library" button on an imported (relayed) synthesis re-runs the **local** verifier over the recipient's chunks + **converts it in place to native** — the statuses become the recipient's own; a claim whose source isn't present becomes a flagged sentence with no citation.
- **Why:** backlog B2 SP3 — the aligned outcome of the SP2 relay (verification becomes the recipient's substrate's job). Maintainer forks: convert-in-place; scope = the synthesis's source papers.
- **Verify:** +2 hermetic tests (convert-to-native via re-resolve-by-identity + 422/404; source-not-in-library → flagged-no-citation). pytest 850. QA 173/173 API + 755/755 FE, 0 uncovered. **No egress, no LLM, no new dependency, no migration.** Audit addendum 2 PASS. Headed-verified (`drive_inc236_reverify.py` — banner→Re-verify→banner-gone+native-citation; 0 off-machine).
- **Revert:** `git revert <sha>` (new module + one endpoint + a blob-field + a button; no destructive change).

## 2026-07-01 — Increment 235: library bundle SP2 — syntheses as relayed artifacts
- **Files:** `app/backend/metadata/library_bundle.py` (`_synthesis_entries` export + `_import_syntheses` import), `app/backend/api/routers/summaries.py` (read branch + `imported` flags + Optional citation ids), `app/backend/api/routers/library.py` (`BundleImportSummary.syntheses_imported`), `alembic/versions/0032_summary_imported_json.py` + `schema.py` (`summaries.imported_json`), `app/frontend/js/20_synthesis.jsx` (imported banner + region/null-source handling) + `28b_bundle.jsx` + `styles.css` (`.synth-imported`), `tests/test_library_bundle.py` (+6) + `tests/test_summaries.py`, `.claude/security-audits/2026-07-01_library-bundle.md` (SP2 addendum), `route_54_library_bundle.md`, help corpus, `.claude/docs/specs/2026-07-01-library-bundle-syntheses-sp2.md`, CLAUDE, backlog, `INCREMENT-235-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** syntheses now travel in a library bundle and import as **relayed artifacts** — the sender's assessment, region precision, stored as a display blob (never re-verified, never in the verification tables), clearly flagged.
- **Why:** backlog B2 SP2. A synthesis is a verification artifact (invariants #1/#4) → it must be relayed, not re-presented as the recipient's verified synthesis. Maintainer forks: relay+flag (re-verify deferred to SP3); syntheses in both whole-library + selection.
- **Verify:** +6 hermetic synthesis tests. pytest 848. QA 172/172 API + 753/753 FE, 0 uncovered. Migration 0032 additive/guarded. Audit addendum PASS. Headed-verified (`drive_inc235_syntheses.py` — banner + REGION coord + quote; 0 off-machine). No egress, no PDFs, no new dependency.
- **Revert:** `git revert <sha>` (additive migration 0032 + additive response fields; no destructive change).

## 2026-07-01 — Increment 234: portable library bundle (B2 SP1 — file-based library sharing, no PDFs)
- **Files:** `app/backend/metadata/library_bundle.py` (NEW — `build_bundle` + `import_bundle`), `app/backend/api/routers/library.py` (`POST /library/bundle/export`, `POST/GET /library/bundle/import`), `app/backend/api/app.py` (`library_bundle_import_jobs`), `app/frontend/js/28b_bundle.jsx` (NEW modal) + `00_lib.jsx` (`downloadBundle`) + `10b_libmenus.jsx` (Add-menu items) + `10_pdf_layer.jsx` (selection bulk `bundle`) + `03_library.jsx` + `40_app.jsx` (wiring), `tests/test_library_bundle.py` (NEW +8), `.claude/security-audits/2026-07-01_library-bundle.md`, `.claude/qa-routes/route_54_library_bundle.md`, `app/backend/help/help_content.md`, `.claude/docs/specs/2026-07-01-library-bundle-design.md`, CLAUDE, backlog, `INCREMENT-234-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** export a library (or a selection) to a versioned JSON bundle — metadata + tags + annotations + axis definitions, **NO PDFs** — and import/merge such a file into another library (additive + non-destructive, by identity).
- **Why:** backlog B2 (collaboration) — the file-based, copyright-safe realization of the accounts-SP4 sharing direction. Maintainer forks: syntheses deferred to SP2; axis defs in (whole-library); both whole-library + selection.
- **Verify:** `test_library_bundle.py` (round-trip/idempotent/non-destructive/selection-no-axes/curated-vs-keyword/attachment-dropped/parse-caps) — hermetic, two throwaway DBs. pytest 842. QA 172/172 API + 753/753 FE, 0 uncovered. **No egress (a local file), no PDFs (copyright veto), no new dependency, no migration.** Audit PASS. Headed-verified (`drive_inc234_bundle.py` — export→file→import→merged, NO pdf, 0 off-machine).
- **Revert:** `git revert <sha>` (new files + additive endpoints/wiring; no migration).

## 2026-07-01 — Increment 233: citation context SP2 — "how this paper cites its sources" (completes B4)
- **Files:** `integrations/semantic_scholar/adapter.py` (generalized into `_fetch_edge`; new `fetch_reference_contexts`; `CitingContext.claim`), `app/backend/methods/citation_context.py` (hypothesis = per-item `ctx.claim` or the constant focal_claim), `app/backend/api/routers/citation_context.py` (`direction` param; worker branches), `app/frontend/js/08c_methods_citation_context.jsx` (an Incoming/Outgoing toggle) + `styles.css` (`.citec-toggle`), `tests/test_citation_context.py` (+3), `.claude/security-audits/2026-07-01_citation-context.md` (SP2 addendum), `.claude/qa-routes/route_53_citation_context.md`, `app/backend/help/help_content.md`, CLAUDE, backlog, `INCREMENT-233-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the outgoing half of B4 — a toggle in the same panel: **How it's cited** (SP1, incoming) ⇄ **How it cites its sources** (SP2, outgoing). Outgoing fetches the focal paper's citing sentences per reference from Semantic Scholar's `/references` edge (S2 has already linked each in-text citation to its reference — no local parsing) and classifies each against the *cited* paper's own claim.
- **Why:** completes B4 (maintainer wanted both directions). The `/references` edge made SP2 a near-mirror of SP1 — no fiddly in-text-citation parsing needed.
- **Verify:** `test_citation_context.py` (references parse + per-item claim; endpoint `direction=references`) — hermetic. pytest 834. QA 169/169 API + 737/737 FE, 0 uncovered. **No new dependency, no migration; public-metadata egress (DOI→S2), NOT the Gemini gate**; classification local; same honesty (counts/evidence/no-score/no-accusation). Audit addendum PASS. **B4 complete (SP1 inc 232 + SP2 inc 233).**
- **Revert:** `git revert <sha>` (additive edge + param + toggle; no migration).

## 2026-07-01 — Increment 232: citation context "how this paper is cited" (B4 SP1, the scite analogue)
- **Files:** `integrations/semantic_scholar/{__init__,adapter}.py` (NEW — `SemanticScholarClient.fetch_citation_contexts`), `app/backend/methods/citation_context.py` (NEW — pure `classify_citation_contexts`), `app/backend/api/routers/citation_context.py` (NEW — `POST/GET /papers/citation-context/run`), `app/backend/api/app.py` (`citation_context_jobs` + injectable client + include before papers), `app/frontend/js/08c_methods_citation_context.jsx` (NEW panel) + `styles.css` (`.citec-*`), `tests/test_citation_context.py` (NEW +6), `.claude/security-audits/2026-07-01_citation-context.md`, `.claude/qa-routes/route_53_citation_context.md`, `THIRD-PARTY-NOTICES.md`, `app/backend/help/help_content.md`, `.claude/docs/specs/2026-07-01-citation-context-design.md`, CLAUDE, backlog, `INCREMENT-232-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a "How this paper is cited" METHODS panel — fetch a paper's citing sentences from Semantic Scholar (only the DOI leaves; public metadata), classify each stance **locally** (support/contrast/mention) with our NLI, and show the breakdown as **counts** (never a score) + every citing sentence with its stance pill + confidence + citing paper + an "influential" marker + honest coverage.
- **Why:** backlog B4 SP1 (a scite analogue) — knowing how the later literature responded to a paper matters before relying on it. Maintainer chose incoming-first + our local NLI stance. The honesty stance is load-bearing: a signal not a verdict, evidence always shown, no composite score, no accusation.
- **Verify:** `test_citation_context.py` (client parse/paginate/cap/DOI-validate/fail-closed-non-poisoning; classifier counts+evidence+no-guess+no-score; endpoint 202→poll→done, 404/422, empty) — hermetic (fake S2 fetcher + fake NLI). pytest 831. QA 169/169 API + 733/733 FE, 0 uncovered. **No new dependency, no migration; public-metadata egress (DOI→S2), NOT the Gemini gate**; classification local. Audit PASS. Credit: scite + Semantic Scholar (THIRD-PARTY-NOTICES + panel). SP2 (outgoing) deferred. Live S2 round-trip = maintainer's spot-check.
- **Revert:** `git revert <sha>` (new files + additive wiring; no migration).

## 2026-07-01 — Increment 231 (follow-up): find Tesseract even when it's installed but not on PATH
- **Files:** `app/backend/pdf_processing/ocr.py` (`tesseract_exe()` resolver), `tests/test_ocr.py` (+1), `.claude/security-audits/2026-07-01_ocr.md` (addendum), `app/backend/help/help_content.md`, CLAUDE.
- **What:** OCR now resolves the Tesseract binary via `CALLOSUM_TESSERACT_PATH` → PATH → common install locations (`C:\Program Files\Tesseract-OCR\…`, Homebrew/apt), so it works after a standard `winget`/UB-Mannheim install without a manual PATH edit.
- **Why:** the UB-Mannheim Windows installer doesn't add Tesseract to PATH, so `shutil.which` missed an installed binary (the maintainer had it installed but OCR reported "not installed"). Real Tesseract v5.4.0 round-trip verified live.
- **Verify:** `test_ocr.py` resolver test (override → PATH → common → None); real end-to-end round-trip (image-only page → searchable PDF → recovered text). pytest 825. No egress/dependency/migration; audit addendum PASS.
- **Revert:** `git revert <sha>`.

## 2026-07-01 — Increment 231: OCR scanned PDFs into a searchable copy (B3)
- **Files:** `app/backend/pdf_processing/ocr.py` (NEW — `make_searchable_pdf` + `TesseractUnavailable`, shells out to the tesseract binary), `app/backend/api/routers/ocr.py` (NEW — `POST/GET /papers/ocr/run` async job), `app/backend/api/app.py` (`ocr_jobs` + include before papers), `app/frontend/js/25_detail.jsx` (`OcrRow` — the "OCR this paper (scanned)" button), `tests/test_ocr.py` (NEW +5, hermetic), `.claude/security-audits/2026-07-01_ocr.md`, `.claude/qa-routes/route_52_ocr.md`, `app/backend/help/help_content.md`, CLAUDE, backlog, `INCREMENT-231-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a manual per-paper **"OCR this paper"** action (shown only for a PDF paper with no text layer, `chunk_count == 0`): render each page → local **Tesseract** → a **searchable PDF** (page image + embedded, correctly-positioned OCR text layer) → attach it as the new primary (original kept) → extract + embed through the **normal** pipeline. The scanned paper becomes searchable + embeddable + citable with **exact** highlights + selectable text.
- **Why:** backlog B3 — scanned/image-only PDFs imported with 0 chunks and were invisible to search/synthesis/citation. Maintainer chose **local Tesseract, manual, exact boxes**; exploration showed exact highlights require the OCR text *inside* the PDF (a searchable PDF), which cleanly reuses the whole extraction/quote-location pipeline with no changes to the honesty-critical code.
- **Verify:** `test_ocr.py` (engine builds a searchable PDF the normal extractor reads; endpoint 202→poll→done makes a scanned paper searchable + keeps the original + OCR copy primary; 404/422; graceful when Tesseract absent) — all hermetic via a fake page-runner (no binary). QA 167/167 API + 729/729 FE, 0 uncovered. **No new pip dependency** (Tesseract is a system binary via `shutil.which`+`subprocess`, the Node/citeproc pattern); no migration; fully local, **no egress**. Audit `2026-07-01_ocr.md` PASS. **The real Tesseract round-trip is the maintainer's manual step** (needs `winget install UB-Mannheim.TesseractOCR`).
- **Revert:** `git revert <sha>` (new files + additive wiring; no migration).
- **Files:** `app/frontend/js/08b_methods_citation_equity.jsx` (removed the `.cite-equity-deferred` note block; trimmed the intro clause + header comment), `app/frontend/styles.css` (removed the now-dead `.cite-equity-deferred` rule), `app/backend/help/help_content.md` (dropped the "It never categorizes the people you cite" paragraph → one trailing clause), `.claude/qa-routes/route_51_methods_citation_equity.md` (assert the absence is clean, no note), `.local/visual/drive_inc229_concentration.py`, CLAUDE, `INCREMENT-230-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** removed the prominent in-app + help note explaining what the tool deliberately doesn't do (categorize authors by gender/race/nationality). The panel now just measures concentration, cleanly, with no disclaimer about the dropped feature.
- **Why:** the maintainer: *"if we have dropped it now, we should just drop it."* Keeping a visible monument to the removed categorization is itself a way of keeping it alive — the same logic that removed the geography signal (inc 229). The **regression guard test stays** (invisible to users; keeps people-categorization from creeping back).
- **Verify:** headed (`drive_inc229_concentration.py` — 4 signals, **0 geography mentions + 0 gender/identity-disclaimer mentions**, ⚠ low-coverage flag intact; 0 console/page/genai). No Python changed → pytest 819 unaffected. QA 165/165 API + 727/727 FE, 0 uncovered. Frontend-only; no migration/egress/dependency.
- **Revert:** `git revert <sha>` (re-adds the note block + CSS + help paragraph).
- **Files:** `app/backend/methods/citation_equity.py` (removed `_geography` + `GLOBAL_NORTH`; docstring reframed; `audit_reference_list` now 4 signals; new frozen `Coverage{text, fraction, .low}` + `_coverage` returns it + `SignalView.coverage: Coverage` + `to_dict` emits `coverage_fraction`/`low_coverage`; `LOW_COVERAGE=0.5`), `integrations/openalex/adapter.py` (`_meta_from_work` no longer extracts `country_codes` — nationality deliberately not collected), `app/backend/api/routers/citation_equity.py` (docstring reframed; `SignalModel` += `coverage_fraction`/`low_coverage`), `app/frontend/js/08b_methods_citation_equity.jsx` (label "Citation equity"→"Citation concentration"; intro/howto/note reframed; ⚠ low-coverage badge + `.low-coverage` class), `app/frontend/styles.css` (`.cite-equity-lowcov`; tokens only), `tests/test_citation_equity.py` (−geography test; +low-coverage test on the institution signal; `test_no_people_categorization_in_core` + a strengthened static guard forbidding country/GLOBAL_NORTH/gender keying), `app/backend/help/help_content.md`, `.claude/docs/future-tracks/opus4.8_future-tracks_citationequitytool.md` (SUPERSEDED banner), `.claude/qa-routes/route_51_methods_citation_equity.md` (rewritten), `.local/visual/drive_inc229_concentration.py`, CLAUDE, backlog, `INCREMENT-229-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** removed the **geography ("Global South spread")** signal — the surviving instance of categorizing the people cited (it sorted each author's country-of-affiliation into a hardcoded North/South binary) — and all **gender** framing (reframed from "deferred" to *dropped, rejected on principle*; no gender code ever existed). Kept self-citation, Matthew (reliance on highly-cited), venue + **institutional** concentration — they measure deference to concentrated power/prestige (WHAT is cited), never WHO wrote it. Renamed the panel **"Citation concentration."** Folded in a **⚠ low coverage (N%)** badge when a signal resolves <50% of the references (the number stays shown). SP2 **Find overlooked work** untouched.
- **Why:** **maintainer values call (CC agreed independently):** you can't measure who is under-cited by sorting people into the categories the bias runs on — *making people visible by category uses the same machinery as making them invisible by it*. The SP1 design rejected gender inference, then shipped the same move on geography. Institutional concentration *stays* (the maintainer wants to surface Ivory-Tower over-emphasis — a power structure, not a person's identity).
- **Verify:** `test_citation_equity.py` (4 signals; no-people-categorization behavioral + static guards; institution low-coverage flag) + `test_overlooked_work.py` (unaffected) + headed (`drive_inc229_concentration.py` — 4 signals, **0 geography/Global-South mentions**, ⚠ low coverage (30%) with numbers shown, the never-categorize-people note; 0 console/page/genai). QA 165/165 API + 727/727 FE, 0 uncovered. No migration/dependency; egress posture unchanged + narrowed (country_codes no longer extracted). Principles aligned; A-A no-accusation veto honored structurally + guard-tested.
- **Revert:** `git revert <sha>` (no migration; re-adds `_geography`/`GLOBAL_NORTH`/`country_codes`).

<!-- HELP-DOCS-SYNCED 2026-06-30 inc 228 — the "Checking citation equity" help section now covers Find overlooked work -->
## 2026-06-30 — Increment 228: citation-equity SP2 — topical overlooked-work remediation (backlog #25)
- **Files:** `integrations/openalex/adapter.py` (`_meta_from_work` +related_works/concepts; `_meta_with_abstract`; `fetch_works_by_ids`; `fetch_topic_candidates` + private `_field_sample_body`), `app/backend/methods/overlooked_work.py` (NEW ranker), `app/backend/api/routers/citation_equity.py` (overlooked endpoint + worker + `_overlooked_model`), `app/backend/api/app.py` (`overlooked_jobs`), `app/frontend/js/08b_methods_citation_equity.jsx` (OverlookedWork + cards) + `styles.css` (`.cite-equity-cand*`), `tests/test_overlooked_work.py` (+10), `.claude/security-audits/2026-06-30_citation-equity.md` (inc-228 addendum), `.claude/qa-routes/route_51_methods_citation_equity.md`, `app/backend/help/help_content.md`, `.local/visual/drive_inc228_overlooked.py`, CLAUDE, `INCREMENT-228-NOTES.md`, backlog. (callosum-app.html rebuilt.)
- **What:** a "Find overlooked work" action in the Citation-equity panel — surface topically-relevant work the reference list omits, from OpenAlex `related_works` ∪ the topic sample, **minus what's already cited**, ranked by callosum's OWN local scientific-paper embedding cosine (SPECTER v1 via the existing stack — no new dependency), each with a labeled match + shared-topic "why" + a one-click metadata-only **＋ Add** (`/discovery/save`, no PDF). **Add-only, identity-agnostic, no quota** — no "drop" path, never identity-as-reason, ranked by match not citation count (the veto lines, structural).
- **Why:** backlog #25 SP2 — the distinctive remediation half of citation equity.
- **Verify:** `test_overlooked_work.py` (ranker order/threshold/no-identity + the endpoint via fake OpenAlex + fake embed model: excludes-already-cited, in-library-marked, empty state, 404/422) + headed (`drive_inc228_overlooked.py` — 3 candidates, in-lib marked, off-topic excluded, ＋ Add lands a paper; 0 console/page/genai). QA 165/165 API + 727/727 FE, 0 uncovered. Audit addendum PASS; public-metadata egress (NOT the Gemini gate); no migration/dependency. **Completes #25 (SP1 inc 227 + SP2 inc 228).**
- **Revert:** `git revert <sha>` (additive endpoint + ranker + UI; no migration).

<!-- HELP-DOCS-SYNCED 2026-06-30 inc 227 — added the "Checking citation equity" help section; corpus current -->
## 2026-06-30 — Increment 227: citation-equity audit (SP1, backlog #25)
- **Files:** `integrations/openalex/adapter.py` (`_meta_from_work` +venue/issn/institutions/country_codes/primary_topic; `fetch_field_sample`; `fetch_work_meta_for`), `app/backend/methods/citation_equity.py` (NEW analyzer), `app/backend/api/routers/citation_equity.py` (NEW async endpoint), `app/backend/api/app.py` (wiring), `app/frontend/js/08b_methods_citation_equity.jsx` (NEW METHODS panel) + `09_placeholders.jsx` (stub removed) + `styles.css` (`.cite-equity-*`), `tests/test_citation_equity.py` (+14), `.claude/security-audits/2026-06-30_citation-equity.md`, `.claude/qa-routes/route_51_methods_citation_equity.md`, `app/backend/help/help_content.md`, `.local/visual/drive_inc227_citation_equity.py`, CLAUDE, `INCREMENT-227-NOTES.md`, backlog. (callosum-app.html rebuilt.)
- **What:** a new "Citation equity" METHODS panel — an identity-agnostic, structural audit of a library paper's reference list (its OpenAlex `referenced_works`), shown against a sample of the paper's field: 5 descriptive signals (self-citation, Matthew concentration, venue, institutional, geographic/Global-South), each with an inspectable basis + honest coverage. Never a score/verdict/accusation; no author-identity inference (the gender module is deferred + absent). Async job over the audited OpenAlex client; ephemeral (no table/migration). The experience pass (conscientious-author persona) added: a neutral "context, not a target" bar caption, a "descriptive count, no baseline" self-citation anchor, a "mirror not a report card" how-to, the geography label led with the defensible phrasing, and an egress reassurance.
- **Why:** backlog #25 — measure the machinery that reproduces inequitable citation, structurally + honestly.
- **Verify:** `test_citation_equity.py` (analyzer per signal + no-identity-inference proven 2 ways + the async endpoint via a fake OpenAlex) + headed (`drive_inc227_citation_equity.py`, fake OpenAlex — 5 signals + field attribution + bases + deferred note + credit; 0 console/page/genai). QA surface 163/163 API + 723/723 FE, 0 uncovered. Audit PASS; public-metadata egress (NOT the Gemini gate); no migration/dependency. **SP2 next:** the topical overlooked-work remediation.
- **Revert:** `git revert <sha>` (additive endpoint + analyzer + panel; no migration).

## 2026-06-30 — Increment 226: per-identifier re-fetch 🔎 for PMID + arXiv
- **Files:** `app/backend/api/routers/paper_enrich.py` (NEW 113 — `reresolve_paper` + `fill_metadata` + `FillMetadataResponse` + `ReResolveRequest{source}`, moved out of papers.py), `app/backend/api/routers/papers.py` (598→528; the 3 blocks removed), `app/backend/api/app.py` (include paper_enrich before papers), `app/backend/metadata/enrichment.py` (`OPENALEX_SOURCE` + allowlist + `enrich_paper_metadata_from_identifier`; 450), `app/backend/metadata/__init__.py` (re-export), `app/frontend/js/25_detail.jsx` (DoiRow → generic IdentifierRow; PMID/arXiv rows get 🔎; 583), `tests/test_papers.py` (+4), `.claude/security-audits/2026-06-30_metadata-enrich.md` (inc-226 addendum), `.claude/qa-routes/route_30_detail_pane.md`, CLAUDE, `INCREMENT-226-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the DOI 🔎 (Crossref re-resolve) is generalized to PMID (→ PubMed via OpenAlex) + arXiv (→ the synthesized arXiv DOI via OpenAlex); ISBN/ISSN/Cite-key stay plain. Reuses the already-audited `OpenAlexClient.fetch_work_csl` + the inc-49 force-overwrite primitive; `source` is an allowlisted `Literal["crossref","pmid","arxiv"]` (default crossref → back-compat). The clicked identifier is preserved across the wholesale overwrite. A forced rule-#1 split (papers.py was at 600) extracted the enrichment-action endpoints to `paper_enrich.py`.
- **Why:** maintainer ask — "add search to the other identifiers like DOI has."
- **Verify:** unit/integration (`test_papers.py`: PMID overwrite via OpenAlex, arXiv synthesized DOI, miss-graceful, 422-when-absent) + headed (`drive_inc226_identifier_resolve.py`, fake OpenAlex — PMID 🔎 → title re-renders to the OpenAlex record, imported_source openalex, PMID preserved; 0 console/page/genai). pytest **795** (+4); ruff clean; QA surface unchanged (161/161 API + 719/719 FE); public-metadata egress (NOT the Gemini gate); no migration/dependency. Audit addendum PASS.
- **Revert:** `git revert <sha>` (additive endpoint param + a router split; no migration).

## 2026-06-30 — Increment 225: progress ETA ("~Ns left") on long async jobs (#4 close-out)
- **Files:** `app/backend/api/job_store.py` (`Job.started_at` + `eta_seconds()`), `app/backend/api/routers/library.py` (`JobProgressOut.eta_seconds` via `_progress_out`), `app/backend/api/routers/citation_counts.py` (`CitationRefreshProgress.eta_seconds`), `app/frontend/js/10_pdf_layer.jsx` (`_fmtEta` + ProgressBar), `app/frontend/js/10b_libmenus.jsx` (Citations/Enrich render eta), `tests/test_job_store.py` (+2), `.local/visual/drive_inc225_progress.py`, CLAUDE, `INCREMENT-225-NOTES.md`, `INCREMENT-BACKLOG.md`. (callosum-app.html rebuilt.)
- **What:** long async jobs now show a rough "~Ns left" ETA = elapsed/current × remaining, computed from a continuous `started_at` (preserved across progress ticks). Surfaced on scan/rescan/import/enrich + citation-counts payloads + rendered in ProgressBar + the libmenus. Cancel is deferred (needs the transaction-restructuring concurrency pass).
- **Why:** wrap up backlog #4's remaining ETA piece.
- **Verify:** unit (`test_job_store`) + a live-import API probe (eta in the payload, decreasing) + headed (`drive_inc225_progress.py` → `Embedding papers — 3 / 8 · ~2s left`, 0 console/page/genai). pytest **791** (+2); ruff clean; QA surface unchanged. Additive; no migration/egress/audit/Principles trigger.
- **Revert:** `git revert <sha>` (additive field + a method; no migration).

## 2026-06-30 — Increment 224: retraction auto-check on the remaining DOI-bearing routes (#31 close-out)
- **Files:** `app/backend/api/routers/acquisition.py` (OA-acquire hook), `app/backend/api/routers/papers.py` (reresolve + fill-metadata hooks; 598), `tests/test_retraction.py` (+3), `.claude/security-audits/2026-06-26_retraction.md` (addendum 2), `.claude/qa-routes/route_39_retraction.md`, CLAUDE, `INCREMENT-224-NOTES.md`, `INCREMENT-BACKLOG.md`.
- **What:** `auto_check_retractions` (inc 134) now also fires after the enrich on the OA-acquire job + the per-paper re-resolve / fill-metadata handlers — completing the on-import retraction lifecycle for the routed DOI-bearing paths. Reuses `app.state.retraction_checkers`; best-effort. The Zotero-import hook is moot (no Zotero route exists).
- **Why:** wrap up backlog #31's "on-import for the remaining paths" remainder.
- **Verify:** hermetic pytest (graceful Crossref fetcher + fake checker + empty enrich registry + fake OA resolver/download). pytest **789** (+3); ruff clean; QA surface unchanged. Audit addendum PASS; Principles non-triggering (reuses the established FACT producer; no new fetch/egress).
- **Revert:** `git revert <sha>` (3 hook insertions; no migration).

## 2026-06-30 — Increment 223: "By priority" sort gains a within-tier recency tiebreak (backlog close-out, finding #4)
- **Files:** `app/backend/persistence/repository.py` (`:107`, one-line ORDER-BY append), `tests/test_papers.py` (+`test_priority_sort_recency_tiebreak_within_tier`), CLAUDE, `INCREMENT-223-NOTES.md`, `INCREMENT-BACKLOG.md`.
- **What:** the `"priority"` sort now tiebreaks within each tier on `papers.id DESC` (recency), so the large **unset** tier isn't one undifferentiated oldest-imported-first block. `[_PRIORITY_RANK.asc(), papers.c.id.desc()]`.
- **Why:** experience-pass finding #4 (inc 220) — wrap up the reading-markers thread's last loose end.
- **Verify:** `GET /papers?sort=priority` → `[high-new, high-old, unset-new, unset-old]`. pytest **786** (+1); ruff clean; QA surface unchanged. Backend-only; no migration/egress/audit/Principles trigger.
- **Revert:** `git revert <sha>` (one-line sort change).

## 2026-06-30 — Increment 222: split 15_axes.jsx (axis-card subsystem → 15b_axis_card.jsx) — clears the last over-cap file
- **Files:** `app/frontend/js/15b_axis_card.jsx` (new, 224), `app/frontend/js/15_axes.jsx` (614→**395**), `.claude/qa-routes/route_15_axes.md` (`fe:` += `15b_axis_card.jsx`), CLAUDE, `INCREMENT-222-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** a behavior-preserving rule-#1 split — moved the **axis-card rendering subsystem** verbatim out of `15_axes.jsx`: `AxisItem` (the one-axis card, 166 lines) + its presentational helpers (`axisConfidenceLabel`/`AxisTierBadge`/`AxisPaperRow`/`AxisCutoffFlipper`/`_tierRank`) → `15b_axis_card.jsx`. `15_axes.jsx` keeps `MyPubsPrompt` + `AxesPanel` (state/loaders/handlers/sort-filter/modals) + `registerPaneTab`. Works via the cross-chunk function hoist in the shared esbuild IIFE (the inc-208 `10b_libmenus.jsx` precedent); cut by a deterministic line-range script with per-function boundary assertions.
- **Why:** clear the long-flagged `15_axes.jsx` 600-cap violation (614 since inc 211/212) — the last over-cap file; the tree is now fully under the cap.
- **Verify:** baseline-then-after on `drive_inc212_dragreorder.py` (curated path) + `drive_inc204_hide_uncertain.py` (keyword path) — both **GREEN before and after**, 0 console/page/genai. pytest **785** unchanged (`test_frontend_assembly` 5/5); ruff + format clean; QA **161/161 API + 719/719 FE, 0 uncovered**.
- **Revert:** `git revert <sha>` (frontend-only; restores the merged `15_axes.jsx`).

## 2026-06-30 — Increment 221: the 40_app.jsx split (useLibrary) + the read/priority filter facet
- **Files:** `app/frontend/js/03_library.jsx` (new — the `useLibrary` hook), `app/frontend/js/40_app.jsx` (599→**212**: calls useLibrary + breaks the focus↔library cycle with two refs), `app/frontend/js/10_pdf_layer.jsx` (PaperList gains `libraryReading`/`onReadingFilter` + the Read/Priority filter dropdowns), help corpus, `.claude/qa-routes/route_50_reading_markers.md`, `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-221-NOTES.md`. (callosum-app.html rebuilt.)
- **What:** the maintainer-chosen "proper split first" → **extracted the library-list subsystem** (filter/query/list-fetch state, pagination, bulk + trash + filter actions, saved searches, the statcheck/retraction chips + findings, the watched-folder rescan, the p-curve/merge modal state) from the App god-component into **`useLibrary`** (03_library.jsx). App keeps the shell + cross-cutting state (selection, tabs, modals, focus); the cross-cutting setters go into the hook via `opts`, and the **focus↔library circular dependency** (focus-enter clears the view filters / the filter actions cancel focus) is broken by App resolving `cancelFocus` + `setAxisRefresh` through refs (set after `useFocusMode`) + wiring focus's `onEnterClearFilters` to the hook's `clearViewFilters`. **Then** the deferred (inc-220, persona-blocking) **read/priority FILTER facet** landed: header **Read** (all/unread/read) + **Priority** (all/high/normal/low) dropdowns → `libraryReading` state in the hook → `read_status`/`priority` query params (already on `GET /papers` from inc 220).
- **Why:** pay down the long-flagged `40_app.jsx` 600-cap debt (it'd been "split before the next addition" for 10+ increments) AND ship the filter facet the inc-220 experience pass found persona-blocking ("you could mark/sort but not filter back to what's unread/hot").
- **Gates:** **frontend-only** (no Python/migration/endpoint/egress change — the backend read/priority + filter params shipped inc 220); **no audit/Principles trigger** (a refactor + a user-facet filter). pytest **785** unchanged (`test_frontend_assembly` confirms the build is in sync); QA surface **161/161 API + 719/719 FE, 0 uncovered**. **Behavior-preservation verified** by a baseline regression driver run GREEN on the pre-refactor code, then GREEN after (14/14: load/search/sort/type-filter/trash-toggle/saved-search save+apply+delete/bulk-select + the new read/priority facet); deterministic 3/3, 0 console/page/genai. **This completes Bella's reading-workflow thread** (reading queue inc 219 + read/priority markers inc 220 + the filter facet inc 221).
- **Revert:** `git revert` the inc-221 commit (frontend-only; no schema change).

## 2026-06-30 — Increment 220: read/unread + priority markers (+ a forced repository.py split)
<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-06-30 inc 220 — added "Read/unread & priority markers" section -->
- **Files:** `app/backend/persistence/schema.py` (+`papers.read_at` + `papers.priority`), `alembic/versions/0031_paper_read_priority.py` (new, guarded ADD COLUMN, guarded downgrade), `app/backend/persistence/repository.py` (+`PRIORITY_LEVELS` + `_PRIORITY_RANK` + "priority" sort + read_status/priority `list_papers` filters; **split: paper-lifecycle + summaries CRUD extracted, re-exported**), `app/backend/persistence/paper_lifecycle_repo.py` (new — trash/purge/tier + read/priority setters), `app/backend/persistence/summaries_repo.py` (new — list/get/delete summary), `app/backend/api/routers/papers.py` (+`POST /papers/{id}/read` + `POST /papers/{id}/priority` + read_status/priority query params + read_at/priority on the responses), `app/frontend/js/16b_readmark.jsx` (new — `ReadPriorityControl`), `app/frontend/js/10_pdf_layer.jsx` (render it in PaperCard + the "By priority" sort option), `app/frontend/styles.css` (`.paper-read`/`.paper-priority`/`.priority-pop`), `tests/test_papers.py` (+2), `.claude/qa-routes/route_50_reading_markers.md` (new), help corpus, `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-220-NOTES.md`.
- **What:** two per-paper, user-set reading markers on each library card — a **manual read/unread** toggle (`read_at`; opening a PDF does NOT auto-mark) + a **priority** picker (high/normal/low, the maintainer's "a few named levels") — plus a **"By priority"** sort and `read_status`/`priority` filters on `GET /papers`. Both are hand labels, NEVER an AI score (the inc-207 declined-ratings logic). The card control (`16b_readmark.jsx`) is optimistic. **Forced split:** `repository.py` was 662 (a pre-existing rule-#1 violation the watch note had drifted on); my additions took it over, so the paper-lifecycle cluster (trash/purge/tier + the new setters) → `paper_lifecycle_repo.py` and the summaries CRUD → `summaries_repo.py`, both re-exported (zero call-site change) → repository.py **565**.
- **Why:** Bella's beta ask (read/unread + priority markers), the other half of the inc-219 thread.
- **Gates:** **no security audit** (local columns + 2 local endpoints; no egress/fetch/dependency — the inc-207 color-tag precedent). **Principles non-triggering** (user labels, not claims/scores; the declined-ratings call applies — priority is a triage label, never a composite). QA surface **161/161 API + 715/715 FE, 0 uncovered** (`route_50`). pytest **+2** (`test_papers.py`); the split is behavior-preserving (summaries/merge/health green). Headed-verified deterministic (5/5, 0 console/page/genai) `.local/visual/drive_inc220_readmark.py` (the harness sets an empty `CALLOSUM_LIBRARY_DIR` so the on-load auto-rescan doesn't scan the real library into the seeded DB). **DEFERRED (backlogged):** the library-HEADER read/priority **filter facet** — it needs a `40_app.jsx` split (at the 600 cap), so it's a tight fast-follow; the markers + sort + the working backend filter params ship now.
- **Revert:** `git revert` the inc-220 commit; migration 0031 is additive (guarded; guarded downgrade drops the columns).

## 2026-06-30 — Increment 219: reading queue (the to-read "Queue" tab) + a SQLite concurrency fix
<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-06-30 inc 219 — added the "Reading queue (your to-read list)" section -->
- **Files:** `app/backend/persistence/schema.py` (+`reading_queue` table), `alembic/versions/0030_reading_queue.py` (new, guarded, no-op downgrade), `app/backend/persistence/reading_queue_repo.py` (new), `app/backend/api/routers/reading_queue.py` (new), `app/backend/api/app.py` (include router), `app/backend/persistence/database.py` (**WAL + busy_timeout pragmas**), `app/frontend/js/16_queue.jsx` (new), `app/frontend/js/05_panes.jsx` + `js/25_detail.jsx` + `js/40_app.jsx` + `styles.css` (the Details add button + paneCtx `queueRefresh`/`onQueueChanged` + `.queue-*` CSS), `tests/test_reading_queue.py` (new, 6), `.claude/qa-routes/route_49_reading_queue.md` (new), help corpus, `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-219-NOTES.md`.
- **What:** a **Reading queue** — the third tab of the left-pane AXES section ([Axes | Tags | Queue]): a personal, ordered to-read list (NOT an axis — its own `reading_queue` table, no scoring). Add by **dragging a library card onto the panel** (the inc-206 `application/x-callosum-paper` MIME) or the Details **+ Reading queue** button; **drag-to-reorder** via a queue-only MIME (the inc-212 pattern); **✓** (read → remove) / **×** (remove); click a row opens the paper. 4 endpoints (`GET`/`POST`/`DELETE /reading-queue` + `PUT /reading-queue/order`). Also: `make_engine` now sets `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`.
- **Why:** Bella's beta ask (a reading-queue). The WAL/busy_timeout fix is a real concurrency hardening the headed verification surfaced — under a burst of concurrent requests the default rollback-journal + busy_timeout=0 made a write racing the list-refresh GET fail with "database is locked"; WAL (readers don't block the writer) + busy_timeout (wait, don't error) is the standard local-SQLite-under-a-web-server pairing.
- **Gates:** **no security audit** (a local table + 4 local endpoints; no egress/fetch/dependency — the inc-208 saved-searches precedent). **Principles non-triggering** (a user-ordered list, no claim/score). QA surface **159/159 API + 706/706 FE, 0 uncovered** (`route_49`). pytest **+6** (`test_reading_queue.py`). Headed-verified deterministic (10/10) via `.local/visual/drive_inc219_queue.py` (drag-add / button-add / drag-reorder-persists / ✓ / ×; 0 console/page/genai). **Known residual (filed to backlog):** the app-wide **read-then-write upgrade-deadlock** — a SELECT-then-write endpoint can still rarely SQLITE_BUSY when a write collides with a concurrent fetch in the same instant (busy_timeout can't break a snapshot-upgrade); BEGIN IMMEDIATE is unsafe here (the scan/embed job holds one minutes-long write transaction), so it needs its own focused increment. A human essentially never hits it.
- **Revert:** `git revert` the inc-219 commit; migration 0030 is additive (guarded; no-op downgrade).

## 2026-06-30 — Increment 218: metadata enrichment SP2 — Europe PMC + PubMed sources
<!-- HELP-DOCS-SYNCED-PREVIOUS 2026-06-30 inc 218 — the gap-fill-enrichment section's source list is now present-tense (Crossref, OpenAlex, Europe PMC, PubMed) -->
- **Files:** `integrations/europepmc/adapter.py` (+`lookup_metadata` + `_csl_from_record`), `app/backend/metadata/enrich_sources.py` (+`EuropePmcEnrichSource` + `PubMedEnrichSource` + `_title_overlap`; register both → 4-source default), `app/backend/api/app.py` (+`enrich_registry` seam), `app/backend/api/routers/library.py` + `routers/papers.py` (use `app.state.enrich_registry` if set), `tests/test_metadata_multi_enrich.py` (+3, endpoint tests → stub registry), `.claude/security-audits/2026-06-30_metadata-enrich.md` (addendum), help corpus, CLAUDE, `INCREMENT-218-NOTES.md`.
- **What:** two more enrichment sources — **Europe PMC** (DOI/PMID → its cached `resultType=core` record, reusing the OA resolver's fetch) + **PubMed** (PMID → efetch abstract; else title-search → matched record + abstract, conservative title match) — each one `register()` + a mapper. Mainly add abstract coverage when Crossref/OpenAlex leave it blank. Default cascade is now `crossref → openalex → europepmc → pubmed`.
- **Why:** completes the maintainer's chosen v1 source set (Eileen's "fields consistently included"); purely additive to the SP1 cascade.
- **Gates:** **no new endpoint/host/dependency/migration** (reuses audited adapters/hosts). Audit **addendum PASS** (same posture — public-metadata egress not the Gemini gate; SSRF-safe constant hosts + bound params; PubMed title-match guard + regex-not-XML abstract parse; fail-closed; gap-fill non-destructive). **Principles non-triggering.** QA surface unchanged **155/155 API + 697/697 FE, 0 uncovered** (sources behind the existing endpoints). pytest **+3** (14 in `test_metadata_multi_enrich.py`: EPMC mapper, PubMed PMID/title-adopt/title-reject, the 4-source registry; endpoint tests repointed to a stub `enrich_registry` for hermeticity now the default cascade has live EPMC/PubMed clients). The live run over the real library is the maintainer's spot-check. **This completes the multi-pass enrichment feature (SP1 inc 217 + SP2 inc 218).**
- **Revert:** `git revert` the inc-218 commit (no schema change).

## 2026-06-30 — Increment 217: multi-pass, gap-filling metadata enrichment (SP1)
<!-- inc 217 help marker (superseded by inc 218 above) — added the "Filling in missing metadata (gap-fill enrichment)" section -->
- **Files:** `app/backend/metadata/enrich_sources.py` (NEW — `EnrichRef`/`EnrichmentSource`/`EnrichmentRegistry` + Crossref/OpenAlex sources + `build_default_enrich_registry`), `app/backend/metadata/enrichment.py` (+`enrich_paper_metadata_multi` + `gap_merge`/`_gap_fill_columns`/`MultiEnrichResult` + DOI-recovery helpers), `app/backend/metadata/__init__.py` (re-export), `integrations/openalex/adapter.py` (+`fetch_work_csl` + `_csl_from_work`/`_reconstruct_abstract`/`_OA_TYPE_TO_CSL`), `app/backend/api/routers/library.py` (+`POST/GET /library/enrich/refresh` + worker), `app/backend/api/routers/papers.py` (+`POST /papers/{id}/fill-metadata`), `app/backend/api/app.py` (`metadata_enrich_jobs` + `enrich_search_provider` seam), `app/frontend/js/10b_libmenus.jsx` (+`EnrichMetadataButton`) + `10_pdf_layer.jsx` + `40_app.jsx` (`onEnriched`; folded back under the 600 cap) + `25_detail.jsx` (+Fill-missing-fields) + `styles.css` (`.detail-fill`) + `callosum-app.html`; `tests/test_metadata_multi_enrich.py` (NEW), `.claude/qa-routes/route_48_metadata_enrich.md` (NEW), `.claude/security-audits/2026-06-30_metadata-enrich.md`, help corpus, CLAUDE, `INCREMENT-217-NOTES.md`.
- **What:** a multi-source, **gap-filling** enricher — recover a missing DOI (PDF scan → Crossref title-search, conservative match), then fill **only the empty fields** from a source cascade (Crossref-by-DOI → OpenAlex), **never overwriting a value the user typed** and **never downgrading** a hand-edited/merged/agent record's provenance. Shipped as a per-paper **Fill missing fields** (Details) + a library-wide **Enrich metadata ↻** async batch (progress + a recovered/filled/still-missing summary).
- **Why:** Eileen's beta feedback — metadata "fails to populate in full"; the old enrichment was Crossref-only + wholesale-overwrite. Gap-fill is the honest, non-destructive answer + the "run across the whole library" ask.
- **Gates:** **no migration, no new dependency** (reuses existing clients). Audit `2026-06-30_metadata-enrich.md` **PASS** (public-metadata egress not the Gemini gate; SSRF-safe constant hosts; gap-fill non-destructive; wrong-DOI + duplicate-DOI guards; fail-closed). **Principles non-triggering / strengthening** (bibliographic facts; gap-fill is *more* honest than overwrite). QA surface **155/155 API + 697/697 FE, 0 uncovered** (`route_48`). Rule-#1: `40_app.jsx` folded back to **598**; engine in new `enrich_sources.py` (122) + `enrichment.py` (380). Headed-verified (`.local/visual/drive_inc217_enrich.py`). **SP2 (inc 218): Europe PMC + PubMed sources** (each one `register()` + a mapper). The live Crossref/OpenAlex run over the real library is the maintainer's spot-check.
- **Revert:** `git revert` the inc-217 commit (no schema change).

## 2026-06-30 — Increment 216: gated MCP agent writes (B1 SP2)
<!-- inc 216 help marker (superseded by inc 217 above) — "Using Callosum from an AI agent (MCP)" covers the opt-in write tools -->
- **Files:** `app/backend/app_settings.py` (+`set_agent_writes_enabled`/`stored_agent_writes` + `CALLOSUM_DISABLE_AGENT_WRITES` kill switch), `app/backend/api/routers/settings.py` (+`agent_writes_enabled` on GET/PUT), `app/backend/persistence/schema_findings.py` (+`agent_writes` table) + `schema.py` (re-export) + `alembic/versions/0029_agent_writes.py` (guarded additive, no-op downgrade), `app/backend/persistence/agent_repo.py` (NEW — record/list/get/mark-reverted + delete_note), `app/backend/metadata/enrichment.py` (+`AI_AGENT_SOURCE`), `app/backend/api/routers/agent.py` (NEW — 7 `/agent/*` endpoints) + `app/backend/api/app.py` (include), `mcp_server/client.py` (+`agent_status`/`add_tag`/`add_to_axis`/`save_reference`/`annotate`) + `mcp_server/server.py` (register write tools only when enabled), `app/frontend/js/35_settings.jsx` (+`AgentSettings`) + `styles.css` (`.agent-activity*`) + `callosum-app.html` (rebuilt); `tests/test_settings.py` + `tests/test_agent_writes.py` (NEW) + `tests/test_mcp_server.py`; `.claude/qa-routes/route_47_agent_writes.md` (NEW), `.claude/security-audits/2026-06-30_mcp-agent-writes.md`, `mcp_server/README.md`, help corpus, CLAUDE, `INCREMENT-216-NOTES.md`.
- **What:** let an MCP agent **add a tag / add a paper to an axis / save a reference by DOI / add a note** — each gated behind an opt-in (`agent_writes_enabled`, **default OFF** → 403), stamped `imported_source="ai-agent"`, recorded in `agent_writes`, and **reversible** from Settings → AI agent (per-row + Revert-all). No destructive agent route exists (delete/merge/scan stay human-only); My-Publications axes are refused (422); `save_reference` resolves the DOI against Crossref and **refuses an unresolvable identifier** (no fabrication); revert is idempotent + dedup-safe.
- **Why:** B1 SP2 — the maintainer chose the **review+revert-after** model (writes apply immediately but are additive/reversible/audited; the host's per-call prompt is the in-the-moment gate) and **DOI-verified** save_reference. The A4 value ("the user owns every irreversible act") is honored structurally: nothing the agent does is irreversible.
- **Gates:** **migration 0029** (head via `alembic_head()`); audit `2026-06-30_mcp-agent-writes.md` **PASS** (default-off gate; additive+reversible by construction; ai-agent provenance; authorship boundary; bound-param SQL; DOI-verified, no SSRF; no library-text egress; no new app dependency). New QA route `route_47_agent_writes.md` → surface **152/152 API + 693/693 FE, 0 uncovered**. **Principles** non-triggering at code level (no new claim/signal); the **A4/A-A** pass ran in the spec. Headed-verified (`.local/visual/drive_inc216_agent_writes.py` — enable → agent tag write → activity row → Revert → tag removed + `reverted_at` set; 0 console/page/genai). The live MCP↔host write round-trip is the maintainer's manual check.
- **Revert:** `git revert` the inc-216 commit, then `alembic downgrade -1` (the `agent_writes` table drop is guarded).

## 2026-06-30 — Increment 215: PDF highlight minimap (the last close-out dreg)
- **Files:** `app/frontend/js/30_viewer.jsx` (a `MinimapTrack` component + the render hook) + `styles.css`
  (`.pdf-minimap` / `.pdf-minimap-tick`, tokens only) + `callosum-app.html` (rebuilt); `.claude/DESIGN.md`,
  `.claude/qa-routes/route_32_viewer_annotations.md`, CLAUDE, `INCREMENT-215-NOTES.md`.
- **What:** a thin gutter beside the page-scroller with one tick per highlight, positioned by **page fraction**
  (not pixel offset → never touches the inc-34/35 render core), tinted by the highlight's color; clicking a tick
  jumps to + flashes it. Shown only when the Notes panel is closed (the panel supersedes it).
- **Why:** the maintainer's "mop up the dregs" — the reading-pane minimap (the chosen option). No split was needed
  (`30_viewer.jsx` was 557, not the stale-noted 599/600 → 580 with the minimap).
- **Gates:** **frontend-only** — pytest **748** unchanged (`test_frontend_assembly` in sync); no backend/endpoint/
  migration/egress/dependency/audit; Principles non-triggering (coordinate-honest navigation overlay). QA surface
  **145/145 API + 687/687 FE, 0 uncovered**. Headed-verified (`.local/visual/drive_inc215_minimap.py` — 2 ticks,
  click→jump+flash, hidden while Notes open; 0 console/page/genai). **This empties the autonomous close-out band.**
- **Revert:** `git revert` the inc-215 commit (frontend-only; no schema/endpoint change).

## 2026-06-30 — Increment 214: close-out mop-up — per-file scan progress + first-class extra URLs (+ a forced split)
- **Files:** `app/backend/pdf_processing/library_scan.py` (on_progress → `(current,total,filename)`),
  `app/backend/api/routers/library.py` (the scan/rescan lambdas put the basename in the label),
  `app/backend/metadata/paper_edits.py` (+`extra_urls` field + `_apply_extra_urls` + reserved key),
  `app/backend/api/routers/papers.py` (610→510: extra_urls req/resp field + `_extra_urls_from_csl`; **the
  request-normalisation cluster extracted** → new `app/backend/api/routers/paper_edit_input.py`),
  `app/frontend/js/25_detail.jsx` (a "More URLs" `EditableText`) + `callosum-app.html` (rebuilt);
  `tests/test_library_scan.py`, `tests/test_paper_edits.py`, `tests/test_papers.py`; `INCREMENT-214-NOTES.md`.
- **What:** (#4) scan progress now shows "Reading <file> — X / N" (the basename threads through the existing
  `JobProgress.label`; no frontend change). (#5) a paper records additional URLs beyond the primary CSL `URL`
  (`csl_json["extra_urls"]`, a list; a "More URLs" editable field, one-per-line) — reserved against the generic
  "More" passthrough. The #5 field pushed `papers.py` over the 600-line cap → the request-normalisers were split
  out to `paper_edit_input.py` (rule #1; the inc-91/207 pattern; behavior-preserving).
- **Why:** the maintainer's "mop up the dregs" — clear the last small autonomous close-out items (#4 + #5).
- **Gates:** pytest **748 passed, 1 skipped** (+6); ruff clean; QA surface unchanged (145/145 API + 685/685 FE);
  no migration / endpoint / egress / dependency / audit trigger; Principles non-triggering. Headed-verified
  (`.local/visual/drive_inc214_extra_urls.py` — the More-URLs field persists `extra_urls`; 0 console/page/genai).
- **Revert:** `git revert` the inc-214 commit (re-inlines the normalisers; drops `extra_urls` + the progress filename).

## 2026-06-30 — Google Docs tunnel hostname renamed `callosum` → `callosum-tunnel`.clffwrkmn.net
- **Files:** `adapters/googledocs/{cloudflared-config.yml, cloudflared-config.local.yml [gitignored], Code.gs,
  sidebar.html, README.md, callosum-gdocs.gs [rebuilt via tools/build_gdocs_addon.py]}`, `tools/run_tunnel.py`,
  `.claude/CLAUDE.md` (directory-layout line).
- **What:** the Google Docs cite bridge now serves **`callosum-tunnel.clffwrkmn.net`** (was `callosum.clffwrkmn.net`)
  — a pure hostname rename across config + the add-on default URL + the runbook. The cloudflared **tunnel name**
  stays `callosum` (id `653c4da3…`); only the public hostname changed. Cite-only ingress + the bearer-token gate are
  unchanged (cloudflared `ingress validate` OK on the new host; `/papers`→forward, `/settings`→404).
- **Why:** free up `callosum.clffwrkmn.net` for Cliff's website (a hostname = one origin; the bridge moves to a
  clearly-named subdomain).
- **Not a security change:** the cite-only allowlist (path-based) + token are the controls, both intact; no audit
  trigger. No app code / migration / egress-posture change; pytest unchanged (`test_gdocs_bundle` in sync); node
  tests green.
- **Live steps (Cliff's, in Cloudflare):** `cloudflared tunnel route dns callosum callosum-tunnel.clffwrkmn.net`;
  delete/repoint the old `callosum` CNAME; re-set the add-on's base URL to the new host (or clear it → it now
  defaults there). Restart the tunnel (`python tools/run_tunnel.py`).
- **Revert:** `git revert` this commit + re-run `cloudflared tunnel route dns callosum callosum.clffwrkmn.net`.

<!-- HELP-DOCS-SYNCED 2026-06-30 inc 213 — privacy section: added "Using Callosum from an AI agent (MCP)" -->
## 2026-06-30 — Increment 213: read-first MCP server (backlog B1, SP1)
- **Files (new):** `mcp_server/{__init__,client,server,__main__}.py` + `mcp_server/requirements.txt` +
  `mcp_server/README.md`; `tests/test_mcp_server.py`; `.claude/security-audits/2026-06-30_mcp-server.md`;
  `.claude/docs/specs/2026-06-30-mcp-server-design.md`; `INCREMENT-213-NOTES.md`.
  **(modified):** `requirements-dev.txt` (+`mcp`), `app/backend/help/help_content.md`, CLAUDE,
  `.claude/docs/INCREMENT-BACKLOG.md`.
- **What:** a SEPARATE in-repo deployable (mirrors `sync_server/`) — a Model Context Protocol **stdio** server
  exposing five **read-only** tools (`search_library`/`get_paper`/`full_text_search`/`find_passages`/
  `format_citation`) to an agent host. Each tool makes one HTTP call to the running app via an injectable httpx
  client; read-only by construction (hardcoded read-endpoint allowlist; no write/scan method exists).
- **Why:** B1 SP1 — let agents use the library *through* callosum (provenance + grounding authority), read-first.
- **Gates:** **no app change** → no migration, no new app endpoint, QA surface unchanged (145/145 API + 685/685
  FE); audit `2026-06-30_mcp-server.md` PASS; new dep `mcp` fenced in `mcp_server/requirements.txt` (+ dev for CI).
  pytest +9 (`tests/test_mcp_server.py`, hermetic via httpx.MockTransport); ruff clean. Live MCP↔host handshake is
  the maintainer's manual check. SP2 (gated writes) = a separate spec + heavy A4/A-A pass.
- **Revert:** `git revert` the inc-213 commit + `rm -r mcp_server/` (the app never imports it; nothing else depends).

## 2026-06-30 — Increment 212: A7 SP2 — drag-to-reorder curated members
- **Files:** `app/frontend/js/15_axes.jsx` (↑/↓ → a ⠿ grip + HTML5 drag-source/drop-target rows; `reorderToIndex`
  replaces `reorderPaper`) + `styles.css` (`.axis-grip` + `.axis-member-drag.dragover`) + `callosum-app.html`
  (rebuilt); `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_15_axes.md`,
  CLAUDE, `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-212-NOTES.md`.
- **What:** curated-axis members reorder by **dragging the ⠿ grip** (was per-row ↑/↓). Member-drag uses a distinct
  MIME (`…-axismember`) so it never triggers the A6 card-level drop-to-add; reuses `PUT /axes/{id}/order`.
- **Why:** A7 SP2 — the drag-reorder the spec planned; completes the Curated Axis feature (and the A1–A10 list).
- **Gates:** **frontend-only** — pytest unchanged (733/1 skipped; `test_frontend_assembly` in sync); ruff clean;
  **no backend/endpoint/migration/audit/dependency**; QA surface **145/145 API + 685/685 FE, 0 uncovered**.
  Headed-verified (`.local/visual/drive_inc212_dragreorder.py` — drag Alpha onto Gamma → [Beta,Alpha,Gamma],
  persists across reload, no ↑/↓ remain; 0 console/page/genai). `15_axes.jsx` 562.
- **Revert:** `git revert` the inc-212 commit (frontend-only; no schema/endpoint change).

## 2026-06-30 — Increment 211: A7 SP1 — the Curated Axis primitive
- **Files:** `alembic/versions/0028_cluster_node_paper_position.py` (NEW) + `persistence/schema.py` (the column),
  `clustering/axis_assignments.py` (`CURATED_KIND`/`CREATABLE_KINDS`, `append_member_position`, `set_member_order`,
  `freeze_to_curated`, `revert_to_keyword`, curated short-circuit), `clustering/axis_scoring.py` (`create_axis(kind=)`),
  `persistence/repository.py` (ordered reads), `api/routers/axes.py` (`kind` on create/patch + `PUT /axes/{id}/order`
  + position-append + `ClusterPaperResponse.position`), `discovery/relevance.py` (exclude curated),
  `app/frontend/js/15_axes.jsx` + `styles.css` + `callosum-app.html` (rebuilt), `app/backend/help/help_content.md`,
  `.claude/DESIGN.md`, `.claude/qa-routes/route_15_axes.md`, `tests/test_curated_axis.py` (NEW), `tests/test_axes.py`,
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-211-NOTES.md`; spec `…/specs/2026-06-30-curated-axis-design.md`.
- **What:** a hand-populated, hand-ordered axis (`kind="curated"`) — hidden scoring UI, a 📌 cue, ↑/↓ ordering,
  drag-to-add, and the bidirectional **freeze** (❄) / warned **convert** (↩) switch. Membership stays in
  `cluster_node_papers` (a new `position` column) so synthesis/A6/merge keep working unchanged.
- **Why:** A7 — the bounded "manual container" path the axis model needs, without becoming a folder.
- **Gates:** pytest **733 passed, 1 skipped** (+9); ruff clean; migration head **0028**; QA surface **145/145 API**
  (+1) **+ 689/689 FE, 0 uncovered**; **no audit / no new dependency**. Headed-verified
  (`.local/visual/drive_inc211_curated.py` — freeze drops uncertain + 📌 + neutral badge + no scoring UI; ↓ reorder
  persists; create-by-name; convert restores; 0 console/page/genai). `15_axes.jsx` 551; `40_app.jsx` untouched (599).
- **Revert:** `git revert` the inc-211 commits + `alembic downgrade -1` (no-op; the column drops on a base downgrade).

<!-- HELP-DOCS-SYNCED 2026-06-29 inc 210 — browsing section: a "Citation counts" paragraph (Citations ↻ + Most cited) -->
## 2026-06-29 — Increment 210: A2 — library-wide per-paper citation counts
- **Files:** `alembic/versions/0027_paper_citation_counts.py` (NEW), `persistence/schema_findings.py` +
  `schema.py` (the table + re-export), `integrations/openalex/adapter.py` (`fetch_cited_by_count`),
  `persistence/repository.py` (list projection + `citations_desc` sort + `upsert_citation_count` +
  `list_live_papers_with_doi`), `api/routers/papers.py` (`PaperListItem` fields), `api/routers/citation_counts.py`
  (NEW — async batch) + `app.py` (register before papers), `app/frontend/js/10b_libmenus.jsx`
  (`CitationCountsButton`) + `10_pdf_layer.jsx` (chip + Most-cited option + control) + `40_app.jsx`
  (`onCitationsRefreshed`) + `callosum-app.html` (rebuilt), `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_23_citation_counts.md` (NEW), `.claude/security-audits/2026-06-29_citation-counts.md`
  (NEW), `tests/test_citation_counts.py` (NEW), `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-210-NOTES.md`.
- **What:** every library card can show its OpenAlex cited-by count (verbatim + "as of <date>") via a
  **"Citations ↻"** header refresh, plus an explicit opt-in **Most cited** sort. A displayed fact, attributed —
  never a composite/silent rank; no DOI/record → honest "—" (a real 0 shows "0 cited-by").
- **Why:** A2 — see how often the literature cites each paper, honestly, without a leaderboard.
- **Gates:** pytest **724 passed, 1 skipped** (+5); ruff clean; migration head **0027**; QA surface **144/144 API**
  (+2) **+ 679/679 FE, 0 uncovered**; **audit PASS**; **no new dependency** (reuses the OpenAlex adapter).
  Headed-verified (`.local/visual/drive_inc210_citations.py` — Citations ↻ → 2 chips + "Citations · <date>" →
  Most cited → "99 cited-by" first; unknown job → 404; 0 console/page/genai). `40_app.jsx` stays 599/600.
- **Revert:** `git revert` the inc-210 commit + `alembic downgrade -1` (no-op; the table is dropped by a base downgrade).

## 2026-06-29 — Increment 209: A3 — full-text PDF search (SQLite FTS5)
- **Files:** `alembic/versions/0026_chunks_fts.py` (NEW — external-content FTS5 + sync triggers + backfill),
  `persistence/fulltext_repo.py` (NEW — sanitize + MATCH query), `api/routers/fulltext.py` (NEW — GET /papers/fulltext)
  + `app.py` (register before papers), `app/frontend/js/10c_fulltext.jsx` (NEW — FulltextResults) + `10_pdf_layer.jsx`
  (scope option + swap the list when active) + `styles.css` (`.fulltext-*`/`.ft-mark`) + `callosum-app.html` (rebuilt),
  `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_22_fulltext.md` (NEW),
  `.claude/security-audits/2026-06-29_fulltext-search.md` (NEW), `tests/test_fulltext.py` (NEW),
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-209-NOTES.md`.
- **What:** verbatim search over the extracted PDF chunk text (FTS5 `MATCH`) — the exact-string complement to the
  semantic axes. A **"Full text (PDFs)"** search scope swaps the library list for per-occurrence snippet hits (matched
  terms bolded, page, **Open at page** → region-precision scroll). External-content FTS5 + a sync trigger trio (the
  AFTER DELETE trigger catches the inc-65 FK CASCADE purge). The query is sanitized (token-quoted → no FTS5 syntax
  error/injection) + bound + try/except (never 500). No claim/rank/score (bm25 = internal ordering).
- **Why:** A3 — find an exact phrase inside papers (axes/synthesis remain the meaning surface).
- **Gates:** pytest **719 passed, 1 skipped** (+4); ruff clean; migration head **0026**; QA surface **142/142 API**
  (+1) **+ 677/677 FE, 0 uncovered**; **audit `2026-06-29_fulltext-search.md` PASS**; **no new dependency** (FTS5 is
  core SQLite). Headed-verified (`.local/visual/drive_inc209_fulltext.py` — search → hit p.2 → Open at page; malformed
  `"` → 0 hits no error; 0 console/page/genai). `40_app.jsx` untouched (self-contained component); `10_pdf_layer.jsx` 555.
- **Revert:** `git revert` the inc-209 commit + `alembic downgrade -1` (drops chunks_fts + triggers).

## 2026-06-29 — Increment 208: A1 — saved searches + split the library-header menus → 10b_libmenus.jsx
- **Files:** `alembic/versions/0025_saved_searches.py` (+ `schema.py` saved_searches table), `persistence/saved_search_repo.py`
  (NEW), `api/routers/saved_searches.py` (NEW) + `app.py` (register), `app/frontend/js/10b_libmenus.jsx` (NEW — AddMenu +
  SavedSearchMenu extracted) + `10_pdf_layer.jsx` (split + SavedSearchMenu render) + `40_app.jsx` (gather/apply/save/delete)
  + `styles.css` (`.saved-search-*`) + `callosum-app.html` (rebuilt), `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_21_saved_searches.md` (NEW) + `route_00` (claim 10b), `tests/test_saved_searches.py` (NEW),
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-208-NOTES.md`.
- **What:** a **saved search** persists a named bundle of the existing library facets (q/search_field/item_type/axis/tag/
  needs_review/signal/sort) — recalled from a **Saved ▾** header menu (apply / save current / delete). A `saved_searches`
  table (params a JSON blob, validated by a typed `extra="forbid"` model → unknown key 422). **Distinct from an axis**
  (a semantic lens); it replays the GET /papers filters, computes no claim/score. **Rule-#1 split:** SavedSearchMenu
  pushed `10_pdf_layer.jsx` to 602/600 → both header dropdowns extracted → **10b_libmenus.jsx** (→ 547).
- **Why:** A1 — recall a working view in one click (the metadata-predicate complement to axes/tags).
- **Gates:** pytest **715 passed, 1 skipped** (+1); ruff clean; migration head **0025**; QA surface **141/141 API**
  (+3) **+ 675/675 FE, 0 uncovered**; **no audit** (local table + 3 local endpoints, no egress/fetch/dependency).
  Headed-verified 4/4 (`.local/visual/drive_inc208_saved_search.py` — save → apply restores → delete; 0 console/page/genai).
- **Revert:** `git revert` the inc-208 commit + `alembic downgrade -1` (drops `saved_searches`).

## 2026-06-29 — Increment 207: A5 — color tags (no ratings) + split TagsRow → 25b_tags.jsx
- **Files:** `alembic/versions/0024_tag_color.py` (+ `schema.py` color column), `persistence/tags_repo.py` (TAG_COLORS +
  `set_tag_color` + color in reads), `api/routers/tags.py` (GET /tags/colors + POST /tags/{id}/color + color in models),
  `api/routers/papers.py` (PaperTagRef.color), `app/frontend/js/25b_tags.jsx` (NEW — TagsRow extracted) + `25_detail.jsx`
  (split) + `10_pdf_layer.jsx` (sidebar dot) + `styles.css` (palette + recipes) + `callosum-app.html` (rebuilt),
  `.claude/DESIGN.md`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_20_tags.md`, `tests/test_tags.py` (+1),
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-207-NOTES.md`.
- **What:** tags carry an optional **color** (a fixed 8-key palette, stored as a key not hex; theme-aware via
  `color-mix`). A swatch popover off each chip's color dot (Details) sets/clears it (`POST /tags/{id}/color`, allowlisted
  → 422); colored chips override the inc-100 provenance styling; the sidebar Tags tab shows a color dot. **Ratings were
  declined** (Cliff): a star flattens a paper to one dimension; tags stay orthogonal/inspectable (#7). **Rule-#1 split:**
  the picker pushed `25_detail.jsx` to 609/600 → extracted **TagsRow → 25b_tags.jsx** (→ 522).
- **Why:** A5 organizational polish, charter-aligned (color = a user label, never an AI score).
- **Gates:** pytest **714 passed, 1 skipped** (+1); ruff clean; migration head **0024**; QA surface **138/138 API**
  (+2) **+ 667/667 FE, 0 uncovered**; **no audit** (color column + 2 local endpoints, no egress/fetch/dependency).
  Headed-verified (`.local/visual/drive_inc207_tag_color.py` — pick blue → chip recolors + persists; 0 console/page/genai).
- **Revert:** `git revert` the inc-207 commit + `alembic downgrade -1` (drops `tags.color`).

## 2026-06-29 — Increment 206: A6 — drag-and-drop a library paper onto an axis to add it
- **Files:** `app/frontend/js/10_pdf_layer.jsx` (PaperCard `draggable` + `onDragStart`), `app/frontend/js/15_axes.jsx`
  (AxisItem drop target + `dropPaper` handler), `app/frontend/styles.css` (`.axis.drag-over`) + `callosum-app.html`
  (rebuilt), `.claude/DESIGN.md` (drop-invite recipe), `app/backend/help/help_content.md`, `.claude/qa-routes/route_15_axes.md`,
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-206-NOTES.md`.
- **What:** drag a library card onto a (non-My-Pubs) axis card → a manual override via the existing
  `POST /axes/{id}/papers` (`status:"manual"`); the axis card shows a dashed-accent `.drag-over` invite; the badge
  count + open card refresh. The drag payload rides the native `dataTransfer` (custom MIME `application/x-callosum-paper`),
  so it works cross-pane with no React state plumbing. **My-Pubs is not a drop target** (authorship is resolved, ✓/✕).
- **Why:** A6 — a faster input for the existing manual-add path (no focus-mode round-trip).
- **Gates:** pytest **713** (unchanged — frontend-only; the endpoint is already tested, DnD is headed-verified); ruff
  clean; QA surface unchanged (136/136 API + 661/661 FE — handlers ride existing claimed elements); **no backend /
  migration / endpoint / egress / dependency**. Headed-verified (`.local/visual/drive_inc206_drag_axis.py` — drag a
  card onto an axis → badge 0→1; 0 console/page/genai).
- **Revert:** `git revert` the inc-206 commit (removes the drag affordance; the ＋ focus-mode add path is unchanged).

## 2026-06-29 — Increment 205: close A8 (covered) + remove the redundant THEORY → Discover placeholder
- **Files:** `app/frontend/js/09_placeholders.jsx` (drop the 3 Discover `registerPaneTab` blocks) + `callosum-app.html`
  (rebuilt), `tests/test_papers.py` (ruff-format the inc-204 A10 test — CI lint fix), `.claude/docs/INCREMENT-BACKLOG.md`
  (A8 closed-as-covered + A9/A10 marked done + the Discover item), CLAUDE, `INCREMENT-205-NOTES.md`.
- **What:** (1) **A8** — the synthesis scope label is **already covered**: the pre-run scope note ("N selected papers
  …", inc 145) + the inc-153 post-run coverage readout. A literal "uncertain excluded" claim would be **dishonest**
  (synthesis summarizes the *exact* selection regardless of certainty; A10 already enforces the boundary at selection
  time) → closed, not built. (2) **Removed the THEORY → Discover `<ComingSoon>` placeholder** (Cliff's queued request)
  — the real Discover/Search (inc 184) + Feed (inc 188) ship as center-pane library-frame tabs, so the stub was stale
  (inc-163 convention: drop a stub when its feature lands). (3) **Folded in:** ruff-format `tests/test_papers.py` (the
  inc-204 push went red on `ruff format --check` only — the suite was green; the A10 test's insert needed wrapping).
- **Why:** *shown = summarized* honesty (A8) + a clean THEORY accordion (no duplicative placeholder) + green CI.
- **Gates:** pytest **713 passed, 1 skipped** (unchanged); ruff check + format clean; QA surface unchanged (136/136 API
  + 661/661 FE — inert stubs, no route claimed them); **no migration / endpoint / egress / dependency**. Headed-verified
  (`.local/visual/drive_inc205_no_discover.py` — no "Discover" header, METHODS stubs survive; 0 console/page/genai).
- **Revert:** `git revert` the inc-205 commit (restores the Discover placeholder + the unwrapped test line).

## 2026-06-29 — Increment 204: carry "hide uncertain" through to the library-pane axis filter (backlog A10 close-out)
- **Files:** `app/backend/persistence/repository.py` (`axis_hide_uncertain` param + `DEFAULT_AXIS_CUTOFF`),
  `app/backend/api/routers/papers.py` (`GET /papers` query param), `app/frontend/js/15_axes.jsx` + `40_app.jsx` +
  `10_pdf_layer.jsx` (thread the boolean + banner note) + `callosum-app.html` (rebuilt), `tests/test_papers.py` (+1),
  `.claude/qa-routes/route_15_axes.md` (A10 step), `app/backend/help/help_content.md`, CLAUDE, `INCREMENT-204-NOTES.md`.
- **What:** the axis count-badge filter returned **every** axis member even when the card's 👁 hide-uncertain view was
  on, so *select-all → summarize* could include papers the card hid. The badge now carries the card's hide state →
  `GET /papers?axis_id=&axis_hide_uncertain=true` filters to the same assigned (≥ cutoff) + manual (NULL) set the card
  shows; the banner reads "… · assigned only". Cutoff = `axes.scoring_gain` (else 0.35), matching the card's tiering.
- **Why:** *shown == summarized* — the filtered Library must match what the card displays (a straight consistency bug).
- **Gates:** pytest **713 passed, 1 skipped** (+1); ruff clean; QA surface unchanged (136/136 API + 661/661 FE);
  Principles non-triggering (filter-consistency, the inc-66 class); **no migration / endpoint / egress / dependency**.
  Headed-verified (`.local/visual/drive_inc204_hide_uncertain.py`, 0 console/page/genai). Swept 4 stray
  `app/frontend/js/*.tmp.*` orphans.
- **Revert:** `git revert` the inc-204 commit (pure code/CSS; the badge filter reverts to all-members, inc-63 behavior).

## 2026-06-29 — Increment 203: activate the dormant `contradicted` verification status (backlog A9 close-out)
- **Files:** `app/backend/summarization/verification.py` (contradiction read + `_status` contradicted + config),
  `app/frontend/js/20_synthesis.jsx` + `styles.css` (distinct `contradicted` pill) + `callosum-app.html` (rebuilt),
  `.claude/DESIGN.md` (red-on-one-status-pill exception), `app/backend/help/help_content.md` (synthesis status),
  `.claude/qa-routes/route_55_synthesis_verification.md` (assertion), `tests/test_nli_support.py` (+3), CLAUDE,
  `INCREMENT-203-NOTES.md`.
- **What:** the verifier could flag *not-supported* but couldn't surface that a cited source **actively disagrees**.
  Now the NLI softmax's contradiction probability (already computed, previously discarded) yields a `contradicted`
  status when it dominates support — rendered as a distinct red "⚠ source disagrees" pill with its quote/page intact.
  **Signal, not verdict** — never "this claim is false."
- **Why:** the single most consequential citation error a verify-everything tool exists to catch — a completeness gap
  in the existing verification spine (the schema + NLI already supported it).
- **Gates:** pytest **712 passed, 1 skipped** (+3); ruff clean; QA surface unchanged (132/132 + 661/661); Principles
  gate aligned (signal-not-verdict, evidence shown); **no migration / endpoint / egress / dependency**. Swept 2 stray
  `tests/*.tmp.*` orphans.
- **Revert:** `git revert` the inc-203 commit (pure code/CSS; `contradicted` reverts to the amber "flagged" lump).

## 2026-06-29 — Increment 202: accounts SP3b — the reference sync-server + client transport + opt-in (the egress slice)
- **Files:** new `sync_server/` (`__init__`, `schema`, `auth`, `store`, `app`, `requirements.txt`, `README.md`),
  `app/backend/sync/transport.py` (new), `app/backend/api/routers/sync.py` (new) + wired in `app.py`
  (`include_router` + `create_app(sync_transport=…)`), `app/backend/app_settings.py` (sync config + sealed keyring +
  cursor), `tests/test_sync_server.py` (+9), `tests/test_sync_endpoints.py` (+8), `.claude/qa-routes/route_46_sync.md`
  (new), `.claude/security-audits/2026-06-29_sync-server.md` (PASS), `.claude/docs/specs/2026-06-29-sync-server-design.md`
  (the design), CLAUDE (layout/decision-log/footer), `INCREMENT-202-NOTES.md`.
- **What:** the first path where data leaves the machine — a self-hostable **sync-server** (`sync_server/`, FastAPI +
  Postgres-in-prod / SQLite-in-tests, an OIDC resource server storing **opaque AES-GCM blobs** per user), a client
  **`HttpSyncTransport`** (httpx), and the **opt-in** local `/sync/{status,settings,setup,run}` endpoints that drive
  `run_sync` over the transport. Default-off, E2E (the DEK never leaves), fully gated.
- **Why:** SP3b's server slice (the maintainer's chosen scope: server + transport + opt-in together) — the engine
  (incs 197–201) now has a real backend to sync against.
- **Gates:** pytest **709 passed, 1 skipped** (+17); ruff clean; QA surface **136/136 API + 661/661 FE, 0 uncovered**
  (new `route_46_sync.md`); audit PASS; **no migration; no new dependency in the local app** (server-only deps in
  `sync_server/requirements.txt`). The live deploy + live-Authentik token validation is the maintainer's manual step.
- **Revert:** `git revert` the inc-202 commit (removes `sync_server/` + the transport/router/settings additions; the
  inc-197–201 engine + the local sync tables are untouched).

## 2026-06-29 — Increment 201: accounts SP3b cont. — natural-key identity for tags (cross-device collision fix)
- **Files:** `app/backend/sync/changeset.py` (`SyncableCollection.natural_key`; `_natural_uid` helper;
  `ensure_identities` deterministic uid; tags `natural_key="name"`), `tests/test_sync_engine.py` (+2),
  `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` (addendum 3), CLAUDE (layout/decision-log/footer),
  `INCREMENT-201-NOTES.md`.
- **What:** a tag's `sync_uid` is now **deterministic from its (UNIQUE) name** instead of random — so two devices that
  independently created a same-named tag pick the same uid and **converge** on apply (UPDATE), instead of colliding on
  the `tags.name` UNIQUE constraint (an `IntegrityError` on first sync). The fix lives in `ensure_identities`;
  collect/apply/merge are untouched.
- **Why:** closes the one real correctness gap flagged in inc 200 (the addendum-2 known limitation) — robustness
  before any live sync.
- **Gates:** pytest **692 passed, 1 skipped** (+2); ruff clean; QA surface unchanged; audit addendum 3 PASS; **no
  migration / endpoint / egress / dependency / UI**.
- **Revert:** `git revert` the inc-201 commit (pure code; tags fall back to random uids — the pre-inc-201 behavior).

## 2026-06-29 — Increment 200: accounts SP3b cont. — the link-table model (paper_tags)
- **Files:** `app/backend/sync/changeset.py` (`SyncableCollection.pk` → `str|None`; `_outbound` helper; `SYNCABLE`
  += paper_tags `pk=None`; ensure_identities skips links), `app/backend/sync/engine.py` (`_apply_link`; dispatch;
  guard push-tombstone forget_identity), `tests/test_sync_engine.py` (+1 link test),
  `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` (addendum 2), CLAUDE (layout/decision-log/footer),
  `INCREMENT-200-NOTES.md`.
- **What:** sync the composite-PK link table **paper_tags** (tag assignments). A link has no own id → its identity is
  **derived from its endpoints** (record_id = the joined `paper_uid|tag_uid`, identical on every device); apply
  resolves the endpoints → local ids → INSERT-OR-IGNORE / DELETE. Also recorded `summaries` as **not synced**
  (derived) + manual `cluster_node_papers` as deferred.
- **Why:** completes the engine's user-authored relational coverage (papers · tags · axes · notes · annotations ·
  tag assignments) before the reference sync-server.
- **Gates:** pytest **690 passed, 1 skipped** (+1); ruff clean; QA surface unchanged; audit addendum 2 PASS; **no
  migration / endpoint / egress / UI**. Known limitation: `tags.name` UNIQUE → cross-device same-name-tag collision
  (a pre-existing inc-198 concern; natural-key reconciliation is a follow-on).
- **Revert:** `git revert` the inc-200 commit (pure code; `SYNCABLE` drops paper_tags; link path is additive).

## 2026-06-29 — Increment 199: accounts SP3b cont. — FK-translation layer + the child tables (notes, annotations)
- **Files:** `app/backend/sync/changeset.py` (+`SyncableCollection.fks`/`.drop`; `collect_local` FK-translates +
  drops; `SYNCABLE` += notes/annotations), `app/backend/sync/engine.py` (`_apply_record` FK-translates + skips
  unresolved; apply referenced-first), `tests/test_sync_engine.py` (+1 child-FK test),
  `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` (addendum), CLAUDE (layout/decision-log/footer),
  `INCREMENT-199-NOTES.md`.
- **What:** extend the sync engine to the FK-bearing child tables **notes + annotations** — a row's `paper_id` FK
  travels as the referenced paper's `sync_uid` and is translated back to each device's local id on apply (applied
  referenced-first); `annotations.attachment_id` (a per-device PDF pointer) is dropped from the synced payload.
- **Why:** SP3b cont. — sync the user's notes + highlights (the high-value relational data). The FK-translation layer
  is the generic mechanism the remaining FK tables will reuse.
- **Gates:** pytest **689 passed, 1 skipped** (+1); ruff clean; QA surface unchanged (132/132 API + 661/661 FE, no
  new route); audit addendum PASS; **no migration, no new dependency, no egress, no UI**.
- **Revert:** `git revert` the inc-199 commit (pure code; `SYNCABLE` reverts to papers/tags/axes; `sync_identity`
  rows for notes/annotations are harmless if left).

## 2026-06-29 — Increment 198: accounts SP3b — the client sync engine + `sync_uid` identity (top-level collections)
- **Files:** `app/backend/sync/engine.py` (new), `app/backend/sync/changeset.py` (revised → sync_uid keying),
  `app/backend/persistence/schema_sync.py` (+`sync_identity`) + re-export in `schema.py`,
  `alembic/versions/0023_sync_identity.py` (new), `tests/test_sync_engine.py` (new, +4),
  `tests/test_sync_crypto.py` (the changeset test updated → sync_uid), `.claude/security-audits/2026-06-29_sync-engine-sp3b.md`
  (new), CLAUDE (layout/decision-log/footer), `INCREMENT-198-NOTES.md`.
- **What:** the **client sync engine** (pull → decrypt → merge → apply → push) over an injectable `SyncTransport`
  (a fake in tests; **no live egress** — the reference server is the next slice), keyed on a global **`sync_uid`**
  (UUID, the new `sync_identity` map) so two devices with independent local ids converge. Scope = the top-level,
  FK-free collections (papers, tags, axes); apply is UPDATE-in-place/INSERT-and-bind/DELETE-and-forget by sync_uid,
  conflicts surfaced into `sync_conflicts` (A4), failing closed on a foreign/tampered blob.
- **Why:** SP3b — the maintainer chose "engine first, server next" + "top-level collections first". The cross-device
  identity problem (local int ids aren't global) needed the `sync_uid` layer; the engine proves convergence locally
  before any ciphertext leaves.
- **Gates:** pytest **688 passed, 1 skipped** (+4 engine tests; SP3a changeset test repointed to sync_uid); ruff
  clean; QA surface unchanged (132/132 API + 661/661 FE, no new route); audit PASS; migration 0023 (additive/guarded,
  head via `alembic_head()`); no new dependency (`uuid`/`json`/`cryptography` already present); no egress, no UI.
- **Revert:** `git revert` the inc-198 commit; the 0023 migration is additive (no down-migration; the table is
  local-only + unused without the engine). `sync_identity` is harmless if left.

## 2026-06-29 — Increment 197: accounts SP3a — E2E sync crypto + local change-tracking foundation (no egress)
- **Files:** `app/backend/sync/` (new: `__init__.py`, `crypto.py`, `changeset.py`), `app/backend/persistence/schema_sync.py`
  (new) + re-export in `schema.py`, `alembic/versions/0022_sync.py` (new), `tests/test_sync_crypto.py` (new, +14),
  `.claude/security-audits/2026-06-29_sync-crypto-sp3a.md` (new), `.claude/docs/specs/2026-06-29-accounts-sync-design.md`
  (new, the SP3 design), CLAUDE (layout/decision-log), `INCREMENT-197-NOTES.md`.
- **What:** the local, no-egress foundation for opt-in **E2E-encrypted multi-device sync**: `crypto.py` (random DEK →
  AES-256-GCM records; DEK sealed under a passphrase KEK + a recovery-code KEK via scrypt; fail-closed; no
  server-side reset), `changeset.py` (hash-diff change-tracking + per-record LWW that **surfaces conflicts**, not
  clobbers — A4), `sync_state`/`sync_conflicts` tables (local-only, migration 0022).
- **Why:** SP3 (the invariant-touching feature) — design-first, Principles/A-A gate run (E2E + opt-in honors A5;
  conflict-surfacing honors A4). SP3a is the security-critical core, proven locally before any data leaves (SP3b).
- **Gates:** pytest **684 passed, 1 skipped** (+14); ruff clean; QA surface unchanged (132/132 + 661/661, no new
  route); audit PASS; migration 0022 (additive/guarded); no new dependency (`cryptography` via `PyJWT[crypto]`).
- **Revert:** `git revert` the inc-197 commit; the 0022 migration is additive (no down-migration; tables are
  local-only + unused if reverted).

<!-- HELP-DOCS-SYNCED 2026-06-29 inc 196 -->
## 2026-06-29 — Increment 196: accounts SP2 — more login methods (email/password + Google), method-agnostic
- **Files:** `ops/accounts-authentik-setup.md` (SP2 connectors section), `app/backend/api/auth/oidc.py` +
  `router.py` (email claim; My-Pubs only on ORCID login), `app/backend/app_settings.py` + `routers/settings.py`
  (`account.email`), `app/frontend/js/35_settings.jsx` (+ `callosum-app.html`: "Sign in" + method-agnostic copy),
  `app/backend/help/help_content.md`, `tests/test_auth_oidc.py` (+1), `.claude/security-audits/2026-06-29_orcid-account.md`
  (addendum), `INCREMENT-196-NOTES.md`.
- **What:** add **email/password + Google** sign-in. The methods are **Authentik connectors** (runbook) — callosum is
  unchanged functionally; its refinement is a **method-agnostic "Sign in"** entry, capturing `email` for display, and
  populating My-Pubs **only on an ORCID login** (a Google/email login sets the account identity, leaves My-Pubs alone).
- **Why:** the maintainer asked to get SP2 underway (parking superuser capabilities). Approved single-entry design.
- **Gates:** pytest **670 passed, 1 skipped** (+1); ruff clean; QA surface unchanged (132/132 + 661/661, no new
  route); audit addendum PASS; no migration; headed driver re-verified.
- **Revert:** `git revert` the inc-196 commit; no migration.

## 2026-06-29 — Increment 195: superuser role (verified-ORCID flag) + Authentik standup runbook
- **Files:** `ops/accounts-authentik-setup.md` (new runbook), `app/backend/app_settings.py` (superuser allowlist +
  `is_superuser`), `app/backend/api/routers/settings.py` (`AccountStatus.is_superuser`), `app/frontend/js/35_settings.jsx`
  (+ `callosum-app.html`), `.env` (gitignored: `CALLOSUM_SUPERUSER_ORCIDS`), `tests/test_auth_oidc.py` (+3),
  `.claude/security-audits/2026-06-29_orcid-account.md` (addendum), README + design spec (runbook refs), backlog,
  `INCREMENT-195-NOTES.md`. Also corrected inc-194's "+12"→"+10" test-count references.
- **What:** (A) a maintainer runbook to stand up Authentik + wire ORCID so live sign-in works; (B) a **superuser**
  flag keyed off the **verified ORCID claim** (`CALLOSUM_SUPERUSER_ORCIDS` env allowlist → `account.is_superuser` +
  a "· superuser" indicator). Verified, not self-asserted; env-config, not hardcoded; capabilities deferred.
- **Why:** the maintainer asked to register their ORCID (`0000-0002-2206-0325`) as a superuser + needed a way to
  light up the live ORCID sign-in. Both approved ("both in sequence").
- **Gates:** pytest **669 passed, 1 skipped** (+3); ruff clean; QA surface unchanged (132/132 + 661/661, no new
  route); audit addendum PASS; no migration; headed driver re-verified (no regression).
- **Revert:** `git revert` the inc-195 commit; remove `CALLOSUM_SUPERUSER_ORCIDS` from `.env` (not committed).

## 2026-06-29 — Increment 194: accounts SP1 — optional "Sign in with ORCID" (OIDC, identity-only)
- **Files:** `app/backend/api/auth/` (new: `__init__.py`, `oidc.py`, `router.py`), `app/backend/app_settings.py`
  (OIDC config + flow/session storage), `app/backend/api/access_control.py` (exempt `/oauth/callback`),
  `app/backend/api/routers/settings.py` (`account` status block), `app/backend/api/app.py` (wire + `oidc_client`
  injectable), `app/frontend/js/35_settings.jsx` (Account section) → `callosum-app.html`, `requirements.txt`
  (`PyJWT[crypto]`), `tests/test_auth_oidc.py` (new, +10), `.claude/qa-routes/route_45_account.md` (new),
  `.claude/security-audits/2026-06-29_orcid-account.md`, help corpus + README + CLAUDE + the design spec/eval/notes.
- **What:** an opt-in, default-off, **identity-only** OIDC sign-in (authorization-code + PKCE, loopback redirect,
  JWKS id-token verify) to the callosum account platform (Authentik), which brokers ORCID; a successful sign-in's
  **verified ORCID + name populate My Publications**. Tokens are write-only (never in `GET /settings`); the callback
  is exempt from the inc-168 gate (a navigation); **no library data leaves the machine**.
- **Why:** backlog #15 — the maintainer wants a callosum account created several ways (ORCID/Google/email), with
  ORCID populating My Pubs. Local-first stays the default; the account is additive. SP1 = the de-risked first slice.
- **Gates:** pytest **666 passed, 1 skipped**; ruff clean; QA surface 132/132 API + 661/661 FE, 0 uncovered; audit
  PASS; Principles → A-A consent value. No migration. The live ORCID round-trip is the maintainer's manual check
  (platform standup, host-agnostic); the flow + pure helpers are pytest-covered + the unconfigured UI headed-verified.
- **Revert:** restore the files above from git (`git revert` the inc-194 commit); no migration to undo. The 204
  logout-route bug fix + the superuser ▲ NEXT-UP backlog entry (ORCID `0000-0002-2206-0325`) are part of this.

## 2026-06-29 — Increment 193: Google Docs setup automation — Quick Tunnel + one-file add-on bundle
- **Files:** `tools/run_tunnel.py` (--quick/--port), `tools/build_gdocs_addon.py` (new), `adapters/googledocs/callosum-gdocs.gs`
  (new generated bundle), `adapters/googledocs/README.md` (easiest-setup section), `tests/test_gdocs_bundle.py` (new, +2),
  `.claude/security-audits/2026-06-28_googledocs-tunnel.md` (addendum), `INCREMENT-193-NOTES.md`.
- **What:** cut the Google Docs install from "migrate a domain + paste 3 files" to "run a quick tunnel + paste 1 file."
  `run_tunnel.py --quick` = a zero-setup Cloudflare Quick Tunnel (throwaway URL, no account/domain/config);
  `build_gdocs_addon.py` bundles the 3 Apps Script sources (sidebar inlined) into one paste-able `callosum-gdocs.gs`.
- **Why:** the user flagged the setup as too much for an end user; user-approved scope = both.
- **Gates:** pytest 656 (+2 bundle sync/inline tests); ruff clean; QA surface unchanged (no API/FE surface — tools +
  adapter file); audit addendum PASS (the --quick mode drops cite-only ingress → token-only, opt-in + informed +
  non-default; named cite-only path remains; bundle is not a security change). node --check on the bundle. No app
  code/frontend/migration/dependency change. **The real quick-tunnel + in-Docs round-trip is the user's manual check.**
- **Also (this turn):** pointed the user's gitignored `cloudflared-config.local.yml` cite rule at `localhost:8888`
  (their port; was 8080).
- **Revert:** drop build_gdocs_addon.py + callosum-gdocs.gs + the test, revert the run_tunnel --quick block + README.

<!-- HELP-DOCS-SYNCED: 2026-06-29 (inc 192) — the "Following sources (Feed)" section now covers all four source types + the Auto-refresh-on-open toggle; covers inc 191/190/189/188 (Feed) + 186 (PubMed in Discover) + 184/185 + the inc 175–179 reading-pane catch-up. -->
## 2026-06-29 — Increment 192: Feed SP2c-3 (part 2) — auto-refresh cadence (#28 complete)
- **Files:** `app/frontend/js/30e_feed.jsx` (auto-refresh toggle + staleness-gated effect), `app/frontend/js/30c_frame.jsx`
  (pass `active`), `app/frontend/styles.css` (.feed-autorefresh), `callosum-app.html`, `app/backend/help/help_content.md`,
  `INCREMENT-192-NOTES.md`.
- **What:** an opt-in **"Auto-refresh on open"** toggle (default off, localStorage) — when the Feed tab is opened and a
  source is stale (newest poll >6h ago, or never), it fires the existing refresh; throttled ≤1/min, self-quiescing.
  Pull-first, no background daemon. **Closes #28 entirely.**
- **Why:** backlog #28 SP2c-3 (the last open item).
- **Gates:** frontend-only; pytest 654 unchanged; test_frontend_assembly 5/5; QA surface 132/132 API + 657/657 FE, 0
  uncovered; Principles non-triggering (UI convenience over the audited /feed/refresh; no audit gate). Headed-verified,
  no egress (drive_inc192_autorefresh.py: toggle off → 0 items; tick → stale sub auto-polls → 1 item; 0
  console/page/genai). No backend/migration/endpoint/dependency change.
- **Revert:** revert the autoRefresh state/effect/toggle in 30e_feed.jsx + the `active` prop + the CSS; rebuild.

## 2026-06-29 — Increment 191: Feed SP2c-3 (part 1) — medRxiv source + PubMed abstracts (efetch)
- **Files:** `app/backend/discovery/biorxiv_source.py` (server-configurable + medRxiv), `app/backend/discovery/pubmed_provider.py`
  (efetch abstracts), `app/backend/discovery/feed.py` (register medRxiv), `app/backend/help/help_content.md`,
  `tests/test_feed.py`, `.claude/security-audits/2026-06-28_feed.md` (addendum 3), `INCREMENT-191-NOTES.md`.
- **What:** two backend Feed enrichments — **medRxiv** (the preprint source is now server-configurable → kinds
  biorxiv_category + medrxiv_category; the data-driven picker shows both) + **PubMed abstracts** via NCBI efetch
  (targeted-regex parse, no XML parser → no XXE; injectable + fail-closed). No frontend change.
- **Why:** backlog #28 SP2c-3 (round out the Feed's sources + content).
- **Gates:** pytest 654 (+2); ruff clean; QA surface unchanged 132/132 API + 655/655 FE; audit addendum 3 PASS
  (medRxiv = audited host + fixed-literal server segment; efetch = audited host + digit-validated ids + regex parse,
  fail-closed). Live spot-checks (medRxiv epidemiology → 3; PubMed crispr → 3/4 abstracts). No migration/dependency/
  endpoint/frontend change.
- **Revert:** revert the biorxiv_source server param + the medRxiv register line + the efetch additions + the tests.

## 2026-06-29 — Increment 190: Feed SP2c-2 — the journal-by-ISSN source
- **Files:** `app/backend/discovery/journal_issn_source.py` (new), `app/backend/discovery/feed.py` (register),
  `app/backend/help/help_content.md`, `tests/test_feed.py`, `.claude/security-audits/2026-06-28_feed.md` (addendum 2),
  `INCREMENT-190-NOTES.md`.
- **What:** a third Feed source — follow a journal by its ISSN → its recent articles (Crossref
  `filter=issn:…&sort=published`); ISSN validated before the fetch. **No frontend/endpoint/surface change** (the
  data-driven Follow picker rendered the new option automatically — the registry promise, proven backend→UI).
- **Why:** backlog #28 SP2c-2; rounds out the Feed sources.
- **Gates:** pytest 652 (+1); ruff clean; QA surface unchanged 132/132 API + 655/655 FE; audit addendum 2 PASS
  (Crossref host already audited; ISSN validated + bound filter → no SSRF). Live spot-check (Nature 1476-4687 → 3) +
  headed-verified (real source + fake fetcher: "Journal (ISSN)" option, follow → Journal-tagged sub, Refresh polls;
  0 console/page/genai). No migration/dependency/endpoint/frontend change.
- **Revert:** delete `journal_issn_source.py` + the register line + the test; revert the help/audit edits.

## 2026-06-28 — Increment 189: Feed SP2c-1 — PubMed-keyword source + data-driven Follow picker
- **Files:** `app/backend/discovery/pubmed_provider.py` (+ PubMedKeywordFeedSource + record_to_feed_entry + sort param),
  `app/backend/discovery/feed.py` (FeedSource metadata + source_meta + register PubMed), `app/backend/discovery/biorxiv_source.py`
  (categories + metadata), `app/backend/api/routers/feed.py` (source_meta on GET), `app/frontend/js/30e_feed.jsx` +
  `styles.css` (data-driven source picker), `callosum-app.html`, `app/backend/help/help_content.md`,
  `tests/test_feed.py`, `.claude/security-audits/2026-06-28_feed.md` (addendum), `INCREMENT-189-NOTES.md`.
- **What:** the Feed is now multi-source — a saved **PubMed query** joins bioRxiv (esearch sorted by date); the Follow
  UI is a **data-driven** source picker (a `<select>` + per-kind placeholder/datalist from backend `source_meta`), so
  the next source needs no frontend edit.
- **Why:** backlog #28 SP2c — more Feed sources + the multi-kind UI the registry was built for.
- **Gates:** pytest 651 (+1); ruff clean; QA surface 132/132 API + 655/655 FE, 0 uncovered; audit addendum PASS
  (PubMed reuses the audited NCBI host; sort=date is a bound param; source_meta non-secret). Live spot-check (crispr
  off-target → 3 recent) + headed-verified (2 fake sources: select shows both, switch updates placeholder, Follow →
  PubMed-tagged sub, Refresh polls; 0 console/page/genai). No migration/dependency/endpoint.
- **Revert:** drop PubMedKeywordFeedSource + the register line + the source_meta/metadata + the frontend picker rework.

## 2026-06-28 — Increment 188: literature Feed SP2b — the Feed tab UI
- **Files:** `app/frontend/js/30e_feed.jsx` (new — FeedPane), `app/frontend/js/30c_frame.jsx` (Feed tab + pane),
  `app/frontend/styles.css` (.feed-* recipe), `callosum-app.html`, `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_44_feed.md` (fe: + UI flow), `INCREMENT-188-NOTES.md`.
- **What:** the Feed center tab — follow bioRxiv categories (chips), Refresh to poll, triage items (unread dot /
  read-dim / ★ star / Save / ✓ in library / Abstract; All/Unread/Starred filter; Mark all read). Pull-only, opt-in;
  the complete polled list is shown. Save reuses /discovery/save (metadata-only, no PDF) + refreshes the Library.
- **Why:** backlog #28 SP2's frontend half (backend was inc 187); completes #28 (Search + Feed).
- **Gates:** frontend-only; pytest 650 unchanged; test_frontend_assembly 5/5; QA route_44 fe-claimed → surface
  132/132 API + 653/653 FE, 0 uncovered; Principles non-triggering. Headed-verified, no egress
  (drive_inc188_feed.py: follow → refresh → 3 items → read/star → Save flips + lands in Library; 0 console/page/genai).
- **Revert:** delete `30e_feed.jsx`, revert the 30c/styles/help/route edits, rebuild `callosum-app.html`.

## 2026-06-28 — Increment 187: literature Feed SP2a — engine + store + endpoints + bioRxiv source
- **Files:** `app/backend/persistence/schema_feed.py` (new) + `alembic/versions/0021_feed.py` (new migration) +
  `schema.py` (re-export), `app/backend/persistence/feed_repo.py` (new), `app/backend/discovery/feed.py` (new),
  `app/backend/discovery/biorxiv_source.py` (new), `app/backend/api/routers/feed.py` (new), `app/backend/api/app.py`
  (wire feed registry + jobs + router), `tests/test_feed.py` (new, +7), `.claude/qa-routes/route_44_feed.md` (new),
  `.claude/security-audits/2026-06-28_feed.md`, `INCREMENT-187-NOTES.md`.
- **What:** the Feed backend — subscriptions (pull-only, opt-in; get-or-create), an async refresh that polls each
  followed source, a read/starred item store (re-poll idempotent + non-destructive), and the flagship
  **bioRxiv-by-category** source; 8 `/feed/*` endpoints. `in_library` computed at read time; save reuses
  `/discovery/save` (metadata-only, no PDF). The Feed tab UI is SP2b.
- **Why:** backlog #28 SP2 (user greenlit pull-only / no auto-subscribe).
- **Gates:** pytest 650 (+7); ruff clean; QA route_44 → surface 132/132 API + 631/631 FE, 0 uncovered; audit PASS
  (constant host + server-derived path + client-side category filter → no SSRF; bound-param; public-metadata, not the
  Gemini gate; additive guarded migration 0021; no new dependency). Values aligned (pull-only/opt-in/augment-never-filter).
  Live spot-check (neuroscience, 10-day window → 5 real preprints) confirms the mapping.
- **Revert:** drop the new discovery/feed + persistence/feed + routers/feed files + migration 0021, revert the app.py
  + schema.py re-export, delete the test + route + audit.

## 2026-06-28 — Increment 186: literature discovery SP1a — the PubMed source
- **Files:** `app/backend/discovery/pubmed_provider.py` (new), `app/backend/discovery/providers.py` (register PubMed),
  `tests/test_pubmed_provider.py` (new, +4), `tests/test_discovery.py` (registry test → crossref+pubmed),
  `app/backend/help/help_content.md`, `.claude/qa-routes/route_43_discovery.md`,
  `.claude/security-audits/2026-06-28_pubmed-provider.md`, `INCREMENT-186-NOTES.md`.
- **What:** a PubMed Search source (NCBI E-utilities, esearch → esummary; injectable fetcher) registered into the
  discovery registry — search now covers Crossref **+** PubMed with **no endpoint/UI change** (the registry promise);
  a Crossref+PubMed overlap (same DOI) merges to one row with both source pills.
- **Why:** backlog #28 SP1a (a second source; the registry was built for exactly this).
- **Gates:** pytest 643 (+4); ruff clean; QA surface unchanged (124/124 API + 631/631 FE — a provider, not a new
  surface); audit PASS (constant host + query-as-param → no SSRF; fail-closed; public-metadata, not the Gemini gate;
  no new dependency). Principles non-triggering. Live schema spot-check (crispr query → 3 real records) confirms the
  mapping. No migration/endpoint/frontend change.
- **Revert:** delete `pubmed_provider.py` + `test_pubmed_provider.py`, revert the providers.py register line + the
  registry test + help/route edits.

<!-- HELP-DOCS-SYNCED: 2026-06-28 (inc 185) — the "Finding new papers (Discover)" section now describes the axis-relevance highlight badge (hint, not a filter); covers inc 184 (Discover section) + the inc 175–179 reading-pane catch-up. -->
## 2026-06-28 — Increment 185: literature discovery SP1b — axis-relevance highlight
- **Files:** `app/backend/discovery/relevance.py` (new), `app/backend/api/routers/discovery.py` (+ `/discovery/relevance`
  + `_discovery_model`), `app/frontend/js/30d_discover.jsx` (relevance fetch + `.discover-relevance` badge),
  `app/frontend/styles.css` (.discover-relevance), `callosum-app.html`, `app/backend/help/help_content.md`,
  `tests/test_discovery_relevance.py` (new, +5), `.claude/qa-routes/route_43_discovery.md`,
  `.claude/security-audits/2026-06-28_discovery-relevance.md`, `INCREMENT-185-NOTES.md`.
- **What:** `POST /discovery/relevance` scores each search result's title+abstract against the user's axis embeddings
  (local, no egress, no DB write) → the Discover tab **highlights** likely matches in place ("likely: &lt;axis&gt; ·
  match 0.NN"). A hint, **never** a filter/reorder; below-cutoff = no badge (≠ irrelevant); my-publications excluded.
- **Why:** backlog #28 SP1b (the design-blessed fast-follow; user-chosen).
- **Gates:** pytest 639 (+5); ruff clean; QA surface 124/124 API + 631/631 FE, 0 uncovered; audit PASS + Principles
  gate run (signal feature — augment-never-filter, single-similarity, silence-≠-certificate). Headed-verified, no
  egress (drive_inc185_relevance.py: 3 rows shown, exactly 1 badge, 0 console/page/genai). No migration/dependency.
- **Revert:** delete `relevance.py` + `test_discovery_relevance.py`, revert the discovery-router/30d/styles/help/route
  edits, rebuild `callosum-app.html`.

<!-- HELP-DOCS-SYNCED: 2026-06-28 (inc 184) — added a "Finding new papers (Discover)" help section (the Search tab: keyword search of Crossref, keyboard triage, metadata-only save, complete-list-never-filtered); also brought "Highlights and notes" current for the reading-pane run (inc 175–179: Notes search/Noted filter, Copy/Export digest, ◂/▸ mark nav + [ / ] keys, remembered scroll). -->
## 2026-06-28 — Increment 184: literature discovery SP1 frontend — the Discover (Search) tab
- **Files:** `app/frontend/js/30d_discover.jsx` (new — DiscoverPane), `app/frontend/js/30c_frame.jsx` (Discover tab +
  pane), `app/frontend/js/40_app.jsx` (onDiscoverSaved → libRefresh), `app/frontend/styles.css` (.discover-* recipe),
  `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_43_discovery.md` (fe: + UI flow),
  `INCREMENT-184-NOTES.md`.
- **What:** the Discover center tab — a query box → `GET /discovery/search` → a dense keyboard-triage results list
  (j/k move, s save, Enter abstract; source pills; ✓ in library marker) → one-click metadata-only **Save** →
  `POST /discovery/save` (refreshes the Library). The complete deduped list is always shown (nothing filtered).
- **Why:** backlog #28 SP1's frontend half (the backend was inc 183).
- **Gates:** frontend-only; QA route_43 fe-claimed → surface 123/123 API + 631/631 FE, 0 uncovered; assembly 5/5;
  pytest 634 unchanged. Headed-verified, no egress (drive_inc184_discover.py: 3 rows, in-library marker, j-nav, Save →
  library; 0 console/page/genai). Principles non-triggering (augment-never-filter; metadata-only; human saves).
- **Revert:** delete `30d_discover.jsx`, revert the 30c/40_app/styles/help/route edits, rebuild `callosum-app.html`.

## 2026-06-28 — Increment 183: literature discovery SP1 (registry + Crossref search + save endpoints)
- **Files:** `app/backend/discovery/{__init__,providers,crossref_provider,search}.py` (new),
  `app/backend/api/routers/discovery.py` (new), `app/backend/api/app.py` (wire registry + router),
  `tests/test_discovery.py` (new, +15), `.claude/qa-routes/route_43_discovery.md` (new),
  `.claude/security-audits/2026-06-28_discovery-search.md`, `INCREMENT-183-NOTES.md`.
- **What:** the discovery backend — a SourceProvider registry + a normalized `Item` (cross-provider dedup,
  `in_library` marking), a Crossref search provider, and `GET /discovery/search` + `POST /discovery/save`
  (metadata-only, deduped, **no PDF fetch**). AI augments-never-filters (complete list); the Search tab UI is inc 184.
- **Why:** backlog #28 (Discover/Search), SP1 — engine-first (like inc-107→108) before the in-app tab.
- **Gates:** pytest +15 (test_discovery); ruff check + format clean; QA surface 123/123 API + 618/618 FE, 0 uncovered
  (route_43); audit PASS (constant Crossref host, query-as-param → no SSRF; bound-param persistence; public-metadata
  egress, not the Gemini gate; no new dependency; no migration). Principles non-triggering (no claim/judgment).
- **Revert:** remove `app/backend/discovery/`, `routers/discovery.py`, the 5 app.py wiring lines, the test + route +
  audit; or restore from a `.claude/backups/` snapshot.

## 2026-06-28 — Increment 182: extract LibraryFrame from 30_viewer (discovery SP0 prereq)
- **Files:** `app/frontend/js/30c_frame.jsx` (new — LibraryFrame), `app/frontend/js/30_viewer.jsx` (remove it),
  `.claude/qa-routes/route_00_smoke_readonly.md` (fe: repoint), `callosum-app.html`,
  `.claude/docs/specs/2026-06-28-discovery-search-design.md` (the design spec), `INCREMENT-182-NOTES.md`.
- **What:** behavior-preserving split — LibraryFrame (the center tab shell) → its own chunk; 30_viewer 599→557
  (clears the maxed cap) + gives the discovery Search tab a home. Wrote the discovery design spec.
- **Why:** prerequisite for the literature-discovery track (#28, approved with Cliff) + relieves the rule-#1 cap.
- **Gates:** frontend-only; QA surface 618/618 (route_00 claims the new chunk); assembly 5/5; pytest 619.
  Behavior-preserving (inc-176 driver re-run: PDF tab opens via LibraryFrame, 0 errors).
- **Revert:** inline LibraryFrame back into 30_viewer; revert the route fe:.

## 2026-06-28 — Increment 181: third-party software NOTICE pass (credit-the-lineage Lane B, backlog #8)
- **Files:** `THIRD-PARTY-NOTICES.md`, `INCREMENT-181-NOTES.md`.
- **What:** added a "Runtime & build dependencies" section crediting every shipped Python + JS dependency with its
  license (grouped by license; PyMuPDF=AGPL noted as reinforcing callosum's license; first-run models noted as
  author-distributed). The NOTICE previously listed only citeproc/CSL/methods.
- **Why:** AGPL compliance + credit-the-lineage Lane B (backlog #8).
- **Gates:** docs-only; no app/migration/egress/surface change; pytest 619. Completes #8 (Lane A = inc 180).
- **Revert:** remove the new section.

## 2026-06-28 — Increment 180: credit-the-lineage for statcheck + shared .method-credit recipe (backlog #8)
- **Files:** `app/frontend/js/06_methods_statcheck.jsx` (STATCHECK_CSL + StatcheckCredit), `app/frontend/js/07_methods_grim.jsx`
  + `app/frontend/js/29_pcurve.jsx` (className repoint), `app/frontend/styles.css` (consolidate), `callosum-app.html`,
  `INCREMENT-180-NOTES.md`.
- **What:** gave statcheck the in-context credit block (Nuijten et al. 2016) + one-click "＋ add to library" that
  GRIM/p-curve already had (credit-the-lineage). Consolidated the byte-identical `.grim-credit`/`.pcurve-credit`
  into one canonical `.method-credit` (DESIGN Pass-2), repointing all three methods.
- **Why:** honor the credit-the-lineage commitment for the one method that lacked it + kill a CSS duplicate.
- **Gates:** frontend-only, reuses the inc-93 import (no new endpoint/migration/egress); Principles-aligned
  (strengthens credit); QA surface 121/618; assembly 5/5; pytest 619. Headed-verified
  (`.local/visual/drive_inc180_credit.py`: statcheck add-to-library → the paper lands; GRIM credit still styles).
- **Revert:** drop StatcheckCredit + STATCHECK_CSL; revert the className/CSS consolidation.

## 2026-06-28 — Increment 179: mark-nav keyboard hotkeys (reading-pane)
- **Files:** `app/frontend/js/30_viewer.jsx` (keydown effect + button tooltip hints), `callosum-app.html`,
  `INCREMENT-179-NOTES.md`.
- **What:** `[` / `]` step to the prev/next highlight (gated to the visible viewer + not-while-typing) — the
  keyboard pairing for the inc-177 Mark buttons; tooltips show the keys.
- **Why:** complete the reading-pane mark-nav ("keep pushin").
- **Gates:** frontend-only; QA surface 121/616; assembly 5/5; pytest 619; headed-verified (`[`/`]` flash prev/next).
  **⚠ 30_viewer is now 599/600 — maxed; further viewer features need another split first.**
- **Revert:** drop the keydown effect + the tooltip key hints.

## 2026-06-28 — Increment 178: README front-door (backlog #11)
- **Files:** `README.md`, `INCREMENT-178-NOTES.md`.
- **What:** rewrote the stale ("Increment 73") README into a current contributor front door — brought the feature
  list current (word-processor adapters, BYOK, retraction/p-curve/GRIM, gap-finder, My Pubs, OA acquisition, merge,
  reading-pane, import) + added the missing onboarding essentials (the `npm install` + `build_frontend` step, venv +
  cross-platform commands, first-run model-download + auto-migrate notes, a Configuration & privacy table, a
  Security note, Known limitations, an AI-assistance note, credit/license pointers).
- **Why:** backlog #11 — the public repo's front door was ~100 increments stale + lacked the JS/build step.
- **Gates:** docs-only; no app/migration/egress/surface change; pytest 619. Shipped as a draft per #11's "your
  voice" boundary — **voice + a screenshot left to the maintainer** (a TODO placeholder marks the screenshot spot).
- **Revert:** `git checkout <prev> -- README.md`.

## 2026-06-28 — Increment 177: next/prev-mark navigation (reading-pane)
- **Files:** `app/frontend/js/30_viewer.jsx` (markCursorRef + stepMark + 2 toolbar buttons), `callosum-app.html`,
  `INCREMENT-177-NOTES.md`.
- **What:** **◂ Mark** / **Mark ▸** toolbar buttons cycle through the paper's highlights in page order (wrapping),
  flashing each via the existing `jumpToAnnotation`. Reuses `.pdf-annot-toggle` (no new CSS).
- **Why:** review marks in sequence without hunting the Notes panel ("follow your heart" reading-pane run).
- **Gates:** frontend-only; QA surface 121/616 (buttons covered by route_32); assembly 5/5; pytest 619.
  Headed-verified (`.local/visual/drive_inc177_marknav.py`: Mark ▸/◂ flash the next/prev highlight; 0 console/page/genai).
- **Revert:** drop stepMark/markCursorRef + the 2 buttons.

## 2026-06-28 — Increment 176: Notes-panel extraction + noted-only filter + note search (reading-pane)
- **Files:** `app/frontend/js/30b_notes.jsx` (new — `AnnotationsPanel`), `app/frontend/js/30_viewer.jsx` (use it),
  `app/frontend/styles.css` (filter-row CSS), `.claude/qa-routes/route_32_viewer_annotations.md` (fe: repoint),
  `callosum-app.html`, `INCREMENT-176-NOTES.md`.
- **What:** extracted the presentational Notes panel out of the viewer (30_viewer 595→573, clears the rule-#1
  watch; behavior-preserving — verified via the inc-144 driver), then added a **noted-only** checkbox + a **note &
  text search** box to it.
- **Why:** "follow your heart" — relieve the cap + ship the first reading-pane filters the close-reader wanted.
- **Gates:** frontend-only, no backend/migration/egress; QA surface 121/612 (route_32 repointed to claim the new
  chunk); assembly 5/5; pytest 619. Headed-verified (`.local/visual/drive_inc176_notesfilter.py`:
  search-by-text/by-note + noted-only each → 1 item; 0 console/page/genai).
- **Revert:** inline `AnnotationsPanel` back into 30_viewer + drop the filter/search + CSS; revert the route fe:.

## 2026-06-28 — Increment 175: remembered scroll position per paper (reading-pane follow-up)
- **Files:** `app/frontend/js/30_viewer.jsx` (save in onScroll + restore in the render block + 2 refs),
  `app/frontend/js/00_lib.jsx` (relocated `buildAnnotationDigest`), `callosum-app.html`, `INCREMENT-175-NOTES.md`.
- **What:** reopening a PDF resumes where you left off — `onScroll` persists `scrollTop` per paper (throttled) to
  localStorage; the render block restores it once per open (a citation `target` wins; not on zoom re-renders).
  Relocated the pure `buildAnnotationDigest` to 00_lib for the rule-#1 headroom (30_viewer 595→back to 595 with the
  feature; was over at 602 before compacting).
- **Why:** Close-reader quality-of-life; chosen over keyboard-zoom (which fights browser Ctrl+± zoom).
- **Gates:** frontend-only, no backend/migration/egress; QA surface unchanged (121/608); assembly 5/5; pytest 619.
  Headed-verified (`.local/visual/drive_inc175_scroll.py`): scroll→600, reload+reopen→restored 600, 0 console/page/genai.
- **Revert:** drop the save/restore + the 2 refs in 30_viewer; move `buildAnnotationDigest` back (optional).

## 2026-06-28 — Increment 174: confirm before re-resolve overwrites hand-edited metadata (backlog #3)
- **Files:** `app/frontend/js/25_detail.jsx` (DoiRow re-resolve guard), `callosum-app.html`, `INCREMENT-174-NOTES.md`.
- **What:** 🔎 re-resolve force-overwrites metadata from Crossref; for a hand-edited paper (`imported_source ==
  "user-edited"`) it now requires a `window.confirm` first, so edits aren't lost on a misclick. Non-edited papers
  are unaffected.
- **Why:** librarian-pass finding (backlog #3) — silent data loss on hand-edited papers.
- **Gates:** frontend-only, no backend/migration/egress; QA surface unchanged (121/608); assembly 5/5; pytest 619.
- **Revert:** drop the confirm in `DoiRow.resolve`.

## 2026-06-28 — Increment 173: import reports parse-time skipped records (backlog #4)
- **Files:** `app/backend/metadata/citation_import.py` (parsers → `(records, skipped)`), `app/backend/api/routers/library.py`
  (`ImportSummary.skipped`), `app/frontend/js/28_import.jsx` (show skipped; fix failed/skipped mislabel),
  `tests/test_citation_import.py`, `callosum-app.html`, `INCREMENT-173-NOTES.md`.
- **What:** the BibTeX/RIS/CSL-JSON import silently dropped entries with no title AND no DOI at parse; now the
  parsers count those drops (+ record-cap overflow) and the import summary reports "N skipped (no title or DOI)" —
  symmetric with inc-155's scan "which files couldn't be read." `failed` (per-record errors) + `skipped` (parse
  drops) are now distinct.
- **Why:** "silence is not a certificate" — an import that drops 3 of 50 entries should say so (backlog #4).
- **Gates:** backend-additive (one response field), no migration/egress/endpoint; QA surface unchanged (121/608);
  `test_citation_import` 9/9; pytest 619; ruff clean.
- **Revert:** restore the parsers' `list[dict]` returns + drop `ImportSummary.skipped` + the modal line.

## 2026-06-28 — Increment 172: download links carry the access token under Remote access (bug fix)
- **Files:** `app/frontend/js/00_lib.jsx` (new `downloadAsset`), `app/frontend/js/35_settings.jsx` (the two
  download links → buttons), `callosum-app.html` (rebuilt), `INCREMENT-172-NOTES.md`.
- **What:** while debugging a user "Couldn't install: Not Found" on the LibreOffice plugin (root cause: a **stale
  running uvicorn** predating the inc-162 routes → restart fixes it; current code serves them, confirmed via
  TestClient), fixed a related latent bug: the **Download .oxt** + **Download manifest** plain `<a download>` links
  bypassed the inc-168 auth shim → 401 under Remote access. They now fetch via the shim (`downloadAsset`) so they
  carry the token.
- **Why:** the user enabled Remote access for Google Docs; plain-anchor downloads silently broke under it.
- **Gates:** frontend-only, no backend/migration/egress; QA surface covered (121/121 API + 608/608 FE);
  `test_frontend_assembly` 5/5; pytest 619 unchanged. No audit/Principles trigger.
- **Revert:** restore the two `<a … download>` links + drop `downloadAsset`.

## 2026-06-28 — Increment 171: Google Docs SP3 — Suggest-from-the-selection + Flatten
<!-- HELP-DOCS-SYNCED: inc 171 — no corpus change needed; the Remote-access note's add-on pointer (inc 170) covers it. -->
- **Files:** `adapters/googledocs/Code.gs` (suggestFromSelection + flattenCitations + selection→cursor-end helpers),
  `adapters/googledocs/gdocs_core.js` (+ pickQueryText/buildSuggestRequest/formatSuggestRows — mirrors the Word core),
  `adapters/googledocs/gdocs_core.test.js` (13/13), `adapters/googledocs/sidebar.html` (Suggest + Flatten buttons),
  `adapters/googledocs/README.md` (§7), `INCREMENT-171-NOTES.md`. (No callosum app code.)
- **What:** Google Docs add-on parity (mirrors Word SP3). **Suggest** — select a sentence → `/citations/suggest`
  (inc 156) → ranked rows (stance + verbatim quote) → Insert (which now collapses a selection to its END so the cite
  lands after the sentence). **Flatten** — drop all citation + bibliography NamedRanges (text stays; Apps Script
  `remove()` keeps content) → plain text, one-way, two-click confirm.
- **Why:** complete the cite-while-you-write loop in Google Docs ("carry on with the plugin").
- **Gates:** no new audit (reuses `/citations/suggest` over the audited bridge); Principles non-triggering
  (signal-not-verdict display, author picks); QA surface unchanged (121/121 API + 604/604 FE); pytest 619 unchanged
  (no Python); node --test 13/13. **Deferred:** true document-order on Refresh (insertion-order v1).
- **Revert:** revert the SP3 additions in `Code.gs` / `gdocs_core.js` / `sidebar.html` (the SP2 add-on stands
  without them).

## 2026-06-28 — Increment 170: Google Docs SP2 — the Apps Script add-on (+ the SP1 bridge live-verified)
<!-- HELP-DOCS-SYNCED: inc 170 — Remote-access help note points to the Google Docs add-on (adapters/googledocs/). -->
- **Files:** `adapters/googledocs/Code.gs` (new — sidebar glue), `adapters/googledocs/gdocs_core.js` (new — pure
  mapping, node-tested + GAS-loaded), `adapters/googledocs/gdocs_core.test.js` (new — `node --test` 10/10),
  `adapters/googledocs/sidebar.html` (new), `adapters/googledocs/appsscript.json` (new),
  `adapters/googledocs/README.md` (§7 + status), `tools/run_tunnel.py` (SP1 refinement — prefer a gitignored local
  config), `.gitignore` (+ `cloudflared-config.local.yml`), `app/backend/help/help_content.md` (Remote-access note),
  `.claude/security-audits/2026-06-28_googledocs-addon.md`, `INCREMENT-170-NOTES.md`. (No callosum app code.)
- **What:** (1) **Completed + live-verified the SP1 bridge** — the user migrated `clffwrkmn.net` to Cloudflare
  (DKIM/SPF/MX verified by nslookup vs HostGator), then `cloudflared login`/`create`/`route dns`; I ran the tunnel +
  an isolated throwaway callosum on :8080 and confirmed through `https://callosum.clffwrkmn.net`: no-token→401,
  token→200, `/citations/styles`→200, `/settings` + `/`→404 (both boundaries hold live). `run_tunnel.py` now prefers
  a gitignored `cloudflared-config.local.yml` so the tunnel id never gets committed. (2) **Built the Google Docs
  add-on** — an Apps Script sidebar (search → insert → refresh+bibliography → style switch) reaching callosum over
  the bridge with the bearer token; citations as NamedRange + DocumentProperties (the Zotero pattern); the pure
  request/response mapping is in `gdocs_core.js` (node-tested + loaded by GAS as `CallosumCore` — no duplication).
- **Why:** make the local library citable from Google Docs (the third word-processor surface, after LibreOffice +
  Word) — the user's "keep pushing" through SP1 setup + SP2 build.
- **Gates:** audit `2026-06-28_googledocs-addon.md` PASS; Principles non-triggering (field-placer); QA surface
  unchanged (121/121 API + 604/604 FE — no new callosum endpoint); pytest 619 unchanged (adapter-only);
  `node --test` 10/10; ruff clean.
- **Revert:** delete the new `adapters/googledocs/{Code.gs,gdocs_core.js,gdocs_core.test.js,sidebar.html,appsscript.json}`;
  revert `tools/run_tunnel.py` + `.gitignore` + the help note. The cloudflared tunnel/CNAME live in the user's
  Cloudflare account (delete with `cloudflared tunnel delete callosum`). v1 limit: citations renumber in
  insertion-order (cut/paste-reorder not reflected on Refresh); Suggest + Flatten are SP3.

## 2026-06-28 — Increment 169: Google Docs SP1 — cloudflared bridge (cite-only) for callosum.clffwrkmn.net
- **Files:** `adapters/googledocs/cloudflared-config.yml` (new — the cite-only ingress), `adapters/googledocs/README.md`
  (new — the setup runbook), `tools/run_tunnel.py` (new — the runner), `.claude/security-audits/2026-06-28_googledocs-tunnel.md`,
  `INCREMENT-169-NOTES.md`. (No callosum app code — cloudflared is an external binary.)
- **What:** the bridge from Google's cloud → local callosum. Recon (via the user's granted SSH) confirmed
  clffwrkmn.net (HostGator shared hosting) prohibits `ssh -R` → can't relay; chose **Cloudflare subdomain
  delegation** (only `callosum.clffwrkmn.net` delegated via 2 NS records at HostGator) + a local **cloudflared**
  tunnel with a **cite-only ingress** (only `/papers`, `/papers/export`, `/citations/{render-document,suggest,styles}`
  → localhost:8080; else 404 — validated). Two boundaries: the inc-168 token + the cite-only ingress.
- **Why:** the user chose Google Docs + callosum.clffwrkmn.net + "only touch the callosum element"; cloudflared
  installed via the permitted winget.
- **Revert:** delete `adapters/googledocs/` + `tools/run_tunnel.py`. No app/schema change. The live tunnel needs the
  user's Cloudflare account (manual); the cite-only ingress + the install were verified, not the live tunnel.
- **Correction (post-build):** Cloudflare **free needs the ROOT domain** (subdomain-only zones are paid) — so the DNS
  side is a careful **whole-domain clffwrkmn.net → Cloudflare migration** (keep existing A/MX/SPF/DKIM "DNS only" →
  site+email unchanged; reversible), not subdomain delegation. `README.md` updated; current DNS enumerated (A→
  50.87.149.75, MX→mail, SPF, DKIM `default._domainkey`) to make the migration email-safe. cloudflared config unchanged.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 168) — privacy section gained a "Remote access (for the Google Docs add-on)" note (off by default; the access token; the recovery hatch). -->
## 2026-06-27 — Increment 168: Google Docs SP0 — remote-access security foundation (auth + rate-limiting)
- **Files:** `app/backend/api/access_control.py` (new — `AccessControlMiddleware` + `RateLimiter`), `app/backend/api/app.py`
  (wire after CORS), `app/backend/app_settings.py` (`remote_access_enabled` + `access_token`; `_get_secret`/`_set_secret`
  refactor), `app/backend/api/routers/settings.py` (status/update + `POST /settings/access-token`),
  `app/frontend/js/00_lib.jsx` (same-origin bearer fetch shim + token accessors), `app/frontend/js/35_settings.jsx`
  (`RemoteAccessSettings`) + `callosum-app.html`, `tests/test_access_control.py` (new, +8), `tests/test_health.py`
  (route-surface), `.claude/security-audits/2026-06-27_remote-access-auth.md`, `.claude/qa-routes/route_35_settings.md`,
  `app/backend/help/help_content.md`, `INCREMENT-168-NOTES.md`.
- **What:** an opt-in, **default-OFF** bearer-token gate + rate-limiting so callosum can be safely reached by the
  Google Docs add-on via a (later) cloudflared tunnel. cloudflared forwards to localhost → the app can't distinguish
  tunnel from local browser → the token is the only safe boundary, applied to every endpoint (except health/shell/
  preflight). Token stored like the BYOK key (write-only over the wire); the frontend sends it via a same-origin
  fetch shim. The Security-baseline prerequisite for exposure; SP1 (tunnel) + SP2 (add-on) follow.
- **Why:** the user approved Google Docs ("build what's needed, be safe") + chose cloudflared-on-local.
- **Revert:** remove `access_control.py` + unwire in `app.py`; revert the settings/app_settings/frontend additions;
  rebuild. No migration. **Default-off means reverting is low-risk; the feature is inert until a user enables it.**

## 2026-06-27 — Increment 167: split 40_app.jsx (clear the carried 600-line violation)
- **Files:** `app/frontend/js/39_focus.jsx` (new — `useFocusMode` hook), `app/frontend/js/00_lib.jsx`
  (+`downloadCitationExport`/`downloadBibliography`/`_downloadBlob`), `app/frontend/js/40_app.jsx`
  (630→551: focus state/callbacks → the hook; the two download bodies → 00_lib; thin wrappers), `callosum-app.html`,
  `INCREMENT-167-NOTES.md`.
- **What:** a behavior-preserving refactor — lift the axis focus-mode subsystem into a `useFocusMode` hook
  (`39_focus.jsx`) and the citation-download helpers into `00_lib.jsx`, dropping `40_app.jsx` from **630 to 551**
  (under the 600-line cap with margin). The inc-128 precedent (extract a hook into an earlier chunk).
- **Why:** clears the rule-#1 violation flagged as "the immediate next chore" across the last six increment footers
  (the App god-component had crept back over 600).
- **Revert:** `git checkout` `40_app.jsx`/`39_focus.jsx`/`00_lib.jsx` + rebuild. No backend/schema/surface change.
  Verified headed (`.local/visual/drive_inc167_app_split.py`: render + bulk-export download + focus-mode + axis
  filter, 0 console/page/genai). New rule-#1 watch: `30_viewer.jsx` at 595/600.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 166) — "Citing in Microsoft Word" help section now covers Suggest / one-click style switch / Flatten (SP3, full parity). -->
## 2026-06-27 — Increment 166: Word add-in SP3 — parity (Suggest + one-click style switch + Flatten)
- **Files:** `adapters/word/taskpane.js` (Suggest + style-onChange + Flatten + collapse-to-end insert),
  `adapters/word/taskpane_core.js` (SP3 pure helpers: `pickQueryText`/`buildSuggestRequest`/`formatSuggestRows`),
  `adapters/word/taskpane.{html,css}` (Suggest + Flatten buttons + suggestions list), `adapters/word/taskpane_core.test.js`
  (+3 tests → 11), `adapters/word/README.md`, `app/backend/help/help_content.md` (cite-in-word → SP3), `INCREMENT-166-NOTES.md`.
- **What:** complete Word parity — **Suggest from the sentence** (read selection/paragraph → `/citations/suggest` →
  ranked candidates with stance + quote → insert *after* the sentence), **one-click whole-doc style switch** (style
  dropdown re-renders + persists per-document), and **Flatten** (live → static, two-click confirm). Insert now
  collapses to the selection END (so Suggest doesn't overwrite the sentence).
- **Why:** the user's roadmap — finish the Word adapter (SP1+SP2+SP3).
- **Revert:** `git checkout` the `adapters/word/` files to the inc-165 state; no backend/schema touched.
  **Verification reality:** the user has no Word, so the Office.js glue is exercised by no one (best-effort-correct);
  the pure logic is `node --test` 11/11 and the called endpoints (`/citations/suggest`, render-document, export,
  styles) are all pytest-proven.

## 2026-06-27 — Increment 165: Word add-in SP2 — live cite-while-you-write (Content Controls + Refresh/renumber + bibliography)
- **Files:** `adapters/word/taskpane.js` (rewrite: live insert + Refresh loop), `adapters/word/taskpane_core.js`
  (SP2 pure helpers — tag encode/decode, render-document request/response mapping; SP1-only helpers removed),
  `adapters/word/taskpane.{html,css}` (Refresh button), `adapters/word/taskpane_core.test.js` (SP2 node tests),
  `adapters/word/README.md`, `app/backend/help/help_content.md` (cite-in-word → SP2), `INCREMENT-165-NOTES.md`.
- **What:** upgrade the SP1 static-text insert to the Zotero-style loop — each citation is a Word **Content Control**
  whose `.tag` carries the cluster's CSL-JSON (base64); **Insert** = `/papers/export` csl-json → wrap a CC → Refresh;
  **Refresh** scans citation CCs in document order → `POST /citations/render-document` → writes back position-aware
  in-text + a managed **References** CC. Style dropdown feeds Refresh. (Suggest / style-switch / flatten = SP3.)
- **Why:** the user's roadmap — the real cite-while-you-write feature (after SP1 de-risked the platform).
- **Revert:** `git checkout` the `adapters/word/` files to the inc-164 state; no backend/schema touched.
  **Verification reality:** the user has no Word, so the Office.js glue is exercised by no one (best-effort-correct);
  the pure logic is `node --test` 8/8 and the `/citations/render-document` contract is pytest-proven (inc 107).

## 2026-06-27 — Increment 164: Microsoft Word add-in (Office.js), SP1 — HTTPS spine + search-and-insert task pane
- **Files:** `adapters/word/{manifest.xml,taskpane.html,taskpane.js,taskpane_core.js,taskpane.css,icon.png,README.md,taskpane_core.test.js}`
  (new — the add-in, shipped client code), `app/backend/api/routers/word.py` (new — serve the task pane + manifest +
  install) + `app/backend/api/app.py` (register), `tools/run_https.py` (new — HTTPS run-mode helper),
  `app/frontend/js/35_settings.jsx` (`WordSettings` section) + `callosum-app.html`, `tests/test_word_addin.py` (new, +7),
  `.claude/security-audits/2026-06-27_word-addin.md`, `.claude/qa-routes/route_35_settings.md`,
  `app/backend/help/help_content.md` (cite-in-word), `INCREMENT-164-NOTES.md`.
- **What:** the first Word adapter — a desktop-Word task pane (served by callosum over HTTPS, **same-origin** with the
  API → **no egress, no CORS change**) that searches the library (`/papers?q=`) and inserts a formatted citation as
  static text via `/citations/render` + `Word.run`. SP1 of a 3-SP arc (SP2 = live fields + renumber; SP3 = suggest/
  style/flatten). Architecture A (user-chosen): zero-egress, desktop-only; one-time local-cert + sideload setup.
- **Why:** the user's roadmap — the second word-processor adapter after LibreOffice (inc 108/162); honors local-first.
- **Revert:** delete `adapters/word/`, `routers/word.py` (+ unregister in `app.py`), `tools/run_https.py`, the
  `WordSettings` block, `tests/test_word_addin.py`; rebuild. No migration/schema; restore from a backups snapshot.

## 2026-06-27 — Increment 163: "Coming soon" accordion placeholders (a visible roadmap)
- **Files:** `app/frontend/js/09_placeholders.jsx` (new), `app/frontend/styles.css` (`.coming-soon*`),
  `callosum-app.html`, `.claude/DESIGN.md` (§5 placeholder convention), `INCREMENT-163-NOTES.md`.
- **What:** Scaffold the planned THEORY/METHODS accordion sections + subsection tabs as honest, inert "Coming soon"
  stubs (a visible roadmap): THEORY → **Discover** (tabs Beyond library / Feed / Search, #30/#28); METHODS →
  **Mixed-model reporting** (#23), **Bayesian statistics** (#24), **Meta-analysis** (#37), **Citation equity** (#25);
  + a **"More checks"** tab appended to the shipped Statistics check (#27). Each names a real backlog item, is placed
  by the DESIGN §5 cognitive-task rubric, bakes in its signal-not-verdict framing, and shows no data.
- **Why:** the user wanted the roadmap visible in-GUI "to keep me psyched about all of the stuff we're gonna build."
- **Revert:** delete `09_placeholders.jsx` + the `.coming-soon*` CSS + rebuild. (Frontend-only; no backend/schema.)

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 162) — new "Citing in LibreOffice Writer" help section (install from Settings + the Callosum menu/toolbar; Add vs Suggest); the suggesting-citations "on the way" line corrected. -->
## 2026-06-27 — Increment 162: LibreOffice adapter v2 — discoverable, installable cite flow
- **Files:** `adapters/libreoffice/oxt/{description.xml,META-INF/manifest.xml,Addons.xcu}` (new — the extension),
  `adapters/libreoffice/callosum_addon.py` (new — the XJobExecutor dispatcher), `adapters/libreoffice/callosum_cite.py`
  (configurable server URL + Add-citation search + `_ACTIONS`/dispatch + `_DISPATCH_CTX`), `tools/build_libreoffice_oxt.py`
  (new), `app/backend/api/routers/libreoffice.py` (new — install/download endpoints) + `app.py` (register),
  `app/frontend/js/35_settings.jsx` (LibreOffice-plugin section) + `callosum-app.html`, `adapters/libreoffice/README.md`,
  `tests/test_libreoffice_oxt.py` + `tests/test_libreoffice_install.py` (new, +10), `.claude/qa-routes/route_35_settings.md`,
  `.claude/security-audits/2026-06-27_libreoffice-install.md`, help corpus, `.gitignore` (dist/), `INCREMENT-162-NOTES.md`.
- **What:** Package the LibreOffice citation macro as a one-click extension (`.oxt`) that adds a **Callosum** menu +
  toolbar to Writer (Add citation = search the library / Suggest from the sentence / Refresh / Style / Flatten /
  Server URL), installable from **Settings → LibreOffice plugin** (or a double-clickable `.oxt`). Replaces the
  buried "Organize Macros → Python" + insert-by-id flow with the Zotero/Mendeley-style toolbar + search-to-cite.
- **Why:** the routing was unusable for a real end user — "no end user is going to find this intuitive."
- **Revert:** revert the commit, or remove `adapters/libreoffice/{oxt,callosum_addon.py}` + `tools/build_libreoffice_oxt.py`
  + `routers/libreoffice.py` (+ its app.py registration) + the 35_settings section + the new tests. (No schema change.)

## 2026-06-27 — Increment 161: non-destructive merge of duplicate papers
- **Files:** `app/backend/metadata/paper_merge.py` (new engine), `app/backend/api/routers/duplicates.py`
  (+`POST /papers/merge`), `app/backend/metadata/enrichment.py` (+`MERGED_SOURCE`),
  `app/backend/persistence/profile_repo.py` (+`replace_paper_id`), `app/frontend/js/38_merge.jsx` (new),
  `19_duplicates.jsx` / `10_pdf_layer.jsx` / `40_app.jsx` + `styles.css` (`.merge-*`) + `callosum-app.html`,
  `tests/test_paper_merge.py` (+10), `.claude/qa-routes/route_24_duplicates.md`,
  `.claude/security-audits/2026-06-27_paper-merge.md`, help corpus, `INCREMENT-161-NOTES.md`.
- **What:** Merge two+ duplicate papers (a preprint + its published copy) into one **without deleting anything** —
  launched from the Duplicates modal or the library bulk bar (≥2 selected). The survivor absorbs **both PDFs** +
  every link/tag/highlight/axis-membership/external-id; the user picks the survivor + resolves differing fields +
  the primary PDF; a **"Merged from…"** note records each merged copy's identifiers (so the OSF link survives); the
  merged-away copies go to **Trash** (restorable husks). `POST /papers/merge` (422/409 on bad requests); local;
  no migration; no egress.
- **Why:** the user's real workflow — keep the preprint's PDF + ensure the OSF link survives — which the old
  delete-the-redundant-copy flow couldn't do without risking data loss.
- **Revert:** revert the commit, or remove `paper_merge.py` + the `/papers/merge` endpoint + `38_merge.jsx` + the
  four wiring edits. (No schema change to undo.)

## 2026-06-27 — Increment 160: the library folder is watched by default
- **Files:** `app/backend/acquisition/fetch.py` (`library_dir()` public), `app/backend/api/routers/library.py`
  (rescan always scans `library_dir()`; `GET /library/watched` pins it as the `is_default` entry; `DELETE 0`→422),
  `app/frontend/js/27_scan.jsx` + `styles.css` + `callosum-app.html`, `tests/conftest.py` (isolate
  `CALLOSUM_LIBRARY_DIR`), `tests/test_watched_folders.py` (+3), help corpus, `INCREMENT-160-NOTES.md`.
- **What:** The library folder (`library_dir()` = `CALLOSUM_LIBRARY_DIR` or the project `library/`) is now
  **watched by default** — the auto-rescan (launch/focus) always scans it even with no registered rows, and the
  Watched Folders modal shows it pinned as "default · always watched" (not removable). User-added folders work
  as before; one equal to the library folder folds into the pin.
- **Why:** the user dropped a (retracted) PDF into the library folder and it never appeared — root cause: the
  library folder was never a *registered* watched folder (harness-ingested as `pdf-scaffold`, never UI-scanned),
  and the rescan only scans registered folders. The user's design: the library folder should be watched by
  default + shown as such.
- **Notes:** no new endpoint (`is_default` additive); no migration/egress/dependency; conftest now isolates the
  library dir per-test (also stops OA tests writing the real `library/`). pytest 581; surface 110/110 + 577/577.
  Verified headed (`drive_inc160_library_watched.py`): pinned default row (no remove) + a drop → Re-scan all →
  "1 added"; 0 console/page/genai. **For the user:** restart uvicorn → the library folder auto-rescans →
  Whitehouse ingests + Crossref-enriches + retraction-checks.
- **Revert:** revert the rescan/GET changes in `routers/library.py` + the modal; from git.

## 2026-06-27 — Increment 159: formatted "Cite as…" in the Cite pane (#30 follow-on)
- **Files:** `app/frontend/js/37_cite.jsx` + `styles.css` + `callosum-app.html`, `INCREMENT-159-NOTES.md`.
- **What:** The in-app Cite pane gains a **style picker** + a per-card formatted **Cite** button that renders the
  paper (APA/MLA/IEEE/…) via the inc-106 citeproc engine and copies the reference; the BibTeX copy stays as a
  secondary action. Completes the deadline-writer persona's ask (a formatted citation, not just BibTeX).
- **Why:** #30 — a writer hand-citing in prose wants a formatted human citation, not a reference-manager BibTeX.
- **Notes:** frontend-only; reuses `/citations/render` + `/citations/styles` (local, no egress); no backend/
  endpoint/migration/gate. pytest 578 unchanged; surface 110/110 + 577/577, 0 uncovered. Verified headed
  (`drive_inc159_cite_format.py`): Cite click fires a render (200), 0 console/page/genai.
- **Revert:** drop `FormattedCiteButton` + the style picker from `37_cite.jsx`; from git.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 158) — Settings + Retraction Watch sections now point to Settings → Metadata access (contact email) instead of the env var. -->
## 2026-06-27 — Increment 158: contact email (polite-pool mailto) in Settings
- **Files:** `app/backend/app_settings.py` (`set_contact_email`/`stored_contact_email`/`resolved_mailto`),
  `app/backend/api/routers/settings.py` (contact_email status + update), `integrations/{crossref,retraction_watch,
  openalex}/adapter.py` + `openalex/author.py` (mailto via `resolved_mailto`), `app/frontend/js/35_settings.jsx`
  (Metadata access section) + `callosum-app.html`, `tests/test_settings.py` (+6), `route_35_settings.md` +
  `route_40_retraction_watch.md`, the BYOK audit (addendum), help corpus, `INCREMENT-158-NOTES.md`.
- **What:** One **Contact email** in Settings → Metadata access overlays `CALLOSUM_CROSSREF_MAILTO` /
  `CALLOSUM_OPENALEX_MAILTO` for Crossref, OpenAlex, and the **Retraction Watch download** — so the RW download
  no longer needs an env var (the user's report).
- **Why:** the RW download was env-only; everything else configurable lives in Settings (the BYOK pattern).
- **Notes:** not a secret (sent to public metadata APIs; `GET /settings` returns it); no new egress vector,
  endpoint, dependency, or migration; audit addendum PASS. pytest 578; surface 110/110 + 573/573, 0 uncovered.
  Verified headed (`drive_inc158_contact_email.py`, isolated settings path): save → persists, 0 console/page/genai.
- **Revert:** drop the contact_email setting + revert the 4 clients to `os.environ.get`; from git.

## 2026-06-27 — Increment 157: highlight-to-suggest, SP1b (LibreOffice "Suggest citations" macro)
- **Files:** `adapters/libreoffice/callosum_cite.py` (new `CallosumSuggestCitations` macro + `fetch_suggestions`/
  `build_suggest_rows`/`current_query_text`/`_suggest_listbox`/`suggest_and_insert`), `adapters/libreoffice/README.md`,
  `adapters/libreoffice/selftest_uno.py` (+ suggest→insert round-trip), `.local/lo_roundtrip/run_roundtrip.py`
  (seed+embed chunks; gitignored), `tests/test_libreoffice_adapter.py` (+4), the inc-108 audit (addendum),
  `INCREMENT-157-NOTES.md`.
- **What:** A LibreOffice writer selects (highlights) a sentence → the macro POSTs it to the inc-156
  `/citations/suggest` → a pick-list (stance + quote + match per row) → the chosen paper inserts as a live
  citation via the existing inc-108 flow. Client-side only; no server change.
- **Why:** #30 SP1b — surface the suggest+evaluate contract inside the word processor (the user's "from the
  LibreOffice document" intent); the inc-107→108 pattern (contract → adapter).
- **Notes:** addendum to the inc-108 adapter audit PASS (same local-only/no-egress posture; the new flow = doc
  text → 127.0.0.1); `SUGGEST_TIMEOUT=90s` (first call loads the embed+NLI models). **Verified: headless UNO
  round-trip SELFTEST OK** (suggest→insert through real LibreOffice; both seeded papers, `support` stance from the
  real NLI). The interactive dialog is the user's manual eyeball. pytest 572. No migration/surface/help change.
- **Revert:** drop the suggest macro + helpers from `callosum_cite.py` + revert the harness/README; from git.

## 2026-06-27 — Increment 156: highlight-to-suggest / evaluate (Track C, SP1a)
- **Files:** `app/backend/citations/suggest.py` (new), `app/backend/summarization/verification.py` (NLI stance),
  `app/backend/api/routers/citations.py` (`POST /citations/suggest`), `app/backend/api/app.py` (`stance_scorer`),
  `app/frontend/js/37_cite.jsx` (new) + `styles.css` + `callosum-app.html`, `tests/test_citations_suggest.py` (new)
  + `tests/test_health.py`, `.claude/qa-routes/route_42_cite.md` (new),
  `.claude/security-audits/2026-06-27_citation-suggest.md`, help corpus, `INCREMENT-156-NOTES.md`, the design spec.
- **What:** Given a draft sentence, **suggest** library papers to cite (retrieval in reverse) + **evaluate** each
  candidate's stance (supports/contrasts/mentions via local NLI). A new **Cite** pane (THEORY accordion) pastes a
  sentence → ranked cards (stance pill · match · verbatim quote · Open source region · Copy BibTeX). The
  `POST /citations/suggest` contract is what the LibreOffice macro (SP1b) will call. Fully local — **no egress**;
  no migration.
- **Why:** Track C (#30) — the highest-value novel capability; SP1a (engine + contract + in-app surface), then
  SP1b (the LibreOffice insert macro), per the inc-107→108 pattern.
- **Notes:** Principles gate run (candidates-not-verdicts, stance-with-quote, region-honest, no opaque score);
  audit PASS; experience pass (deadline-writer persona) → added the Copy-BibTeX extract + visible
  stance-unavailable + de-duped boilerplate in-increment. pytest 568; surface 110/110 + 569/569, 0 uncovered.
- **Revert:** drop the suggest engine/endpoint/pane + the stance scorer; from git.

## 2026-06-27 — Increment 155: scan done-summary surfaces which files couldn't be read (#4)
- **Files:** `app/backend/api/routers/library.py`, `app/frontend/js/27_scan.jsx` + `styles.css` + `callosum-app.html`,
  `tests/test_library_scan.py`, `INCREMENT-155-NOTES.md`.
- **What:** The folder-scan done-summary now lists **which files failed and why** (a `ScanError{path,error}` model +
  `ScanSummary.error_details`, populated from the scan's already-collected per-file errors; a collapsible in the
  scan modal). Scan side only — import parse-drops need a parser change (deferred, noted on #4).
- **Why:** the Migrator experience-pass (#4): "which entries were skipped/failed, and why."
- **Revert:** drop `error_details`/`ScanError` + the `.scan-errors` render; from git.

## 2026-06-27 — Increment 154: statcheck flagged-chip deep-link flashes the specific inconsistent test
- **Files:** `app/frontend/js/06_methods_statcheck.jsx` + `styles.css` + `callosum-app.html`, `INCREMENT-154-NOTES.md`.
- **What:** When a per-paper statcheck run finishes, the first inconsistent row scrolls into view + flashes
  (marked `.flagged-row`) — so the "⚠ flagged" chip path lands on the specific result that doesn't recompute.
  Frontend-only.
- **Why:** the statcheck experience-pass finding (d) — "flagged" → "the specific bad number."
- **Revert:** restore `06_methods_statcheck.jsx` + `styles.css` from git + rebuild.

## 2026-06-27 — Increment 153: synthesis coverage readout + top_k + answerability (#7)
- **Files:** `app/frontend/js/20_synthesis.jsx` + `styles.css` + `callosum-app.html`, `INCREMENT-153-NOTES.md`.
- **What:** After a papers-scope synthesis, a coverage line — "Drew from M of N selected papers · top K chunks
  (· K contributed no cited passage)" — computed from the result's citation `paper_id`s + a new `scopeMeta`; plus
  an answerability note when no claim clears verification. Frontend-only display.
- **Why:** the Skeptical-synthesizer pass (#7): show how much of the selection actually fed the summary.
- **Revert:** restore `20_synthesis.jsx` + `styles.css` from git + rebuild.

## 2026-06-27 — Backlog reconciliation (docs-only; no increment)
- **Files:** `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/docs/INCREMENT-BACKLOG-DONE.md`.
- **What:** Reconciled the open backlog against what actually shipped in inc 109–152 (it had drifted — many items
  listed open/partial were done). Relocated the fully-shipped items to DONE (full entries) + the breadcrumb list:
  #1 brand-assets (non-issue, 109), #2 page-view (110), #10 Gemini key (146), #39 BYOK arc (146–152); tightened the
  partial tracks to their true remainder (#5 Translators-done; #22; #27 GRIM/p-curve/facet-done; #29 gap-finder
  v2-done; #31 findings-done; #35 My-Pubs L1–3-done); retired the shipped "NEXT MAJOR UPGRADE" (121). Number gaps
  (#1/#2/#10/#39) kept for cross-ref stability.
- **Why:** so the OPEN list shows only genuine remaining work ("a good sense of what remains").
- **Verified read-only:** #1 is a non-bug (`inline_brand_assets.py` reads `.claude/media/` correctly); no app code touched.
- **Revert:** from git.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 152) — help corpus current as of OS-keychain key storage -->
## 2026-06-27 — Increment 152: OS-keychain key storage (optional keyring, file fallback)
- **Files:** `app/backend/app_settings.py`, `integrations/gemini/generator.py`, `app/backend/api/routers/settings.py`,
  `app/frontend/js/35_settings.jsx` + `callosum-app.html`, `requirements.txt`, `app/backend/help/help_content.md`,
  `tests/test_settings.py`, `.claude/security-audits/2026-06-27_keychain-storage.md`, `INCREMENT-152-NOTES.md`.
- **What:** BYOK provider keys can live in the **OS keychain** (`keyring`, optional) instead of the gitignored file.
  `get/set_provider_key` are keychain-aware (keychain → file fallback; migrate-on-save; fail-closed to file). `GET
  /settings` reports `key_storage` ("keychain"/"file"); the UI shows where keys live. No hard new dependency.
- **Why:** the deferred #39 hardening — encrypted-at-rest key storage when available, with a graceful fallback.
- **Revert:** restore the file-only `set/get_provider_key` + `_resolve_key`/`_stored_key`; from git.

## 2026-06-27 — Increment 151: validation-lock disclaimer + help-assistant toggle in Settings
- **Files:** `app/backend/api/routers/settings.py`, `app/backend/app_settings.py`, `integrations/gemini/generator.py`,
  `app/frontend/js/35_settings.jsx` + `styles.css` + `callosum-app.html`, `app/backend/help/help_content.md`,
  `tests/test_settings.py`, `INCREMENT-151-NOTES.md`.
- **What:** (A) A standing "verified locally — your model affects quality, not which citations pass" disclaimer in
  Settings → AI features (the validation-lock made visible). (B) The AI help assistant (already per-provider via the
  inc-149 seam) is now toggleable in Settings, not env-only — `help_assistant_enabled` stored + overlaid like egress.
- **Why:** set expectations for non-flagship/local models (quality vs correctness); finish moving AI config to the UI.
- **Revert:** drop the help-toggle field + the disclaimer note from the settings router + `35_settings.jsx`; from git.

## 2026-06-26 — Increment 150: multi-provider Settings UI (#39 part 2 — completes #39)
- **Files:** `app/backend/api/routers/settings.py`, `app/frontend/js/35_settings.jsx` + `callosum-app.html`,
  `app/backend/help/help_content.md`, `tests/test_settings.py`, `tests/test_providers.py`,
  `.claude/qa-routes/route_35_settings.md`, `.claude/security-audits/2026-06-26_multi-provider-llm.md` (addendum),
  `INCREMENT-150-NOTES.md`.
- **What:** A **Model provider** dropdown (Gemini / OpenAI / Anthropic / Local) in Settings → AI features. Cloud →
  key field + egress toggle; Local → a loopback `base_url` + "nothing leaves your machine" (no egress toggle).
  `PUT /settings` extended (provider allowlist, loopback-422, per-provider write-only keys); test-key is
  provider-aware. Completes #39.
- **Why:** Use OpenAI/Anthropic, or a local model for AI summaries with **zero egress**, all from the UI.
- **Revert:** restore `35_settings.jsx` + the settings router from git; rebuild.

## 2026-06-26 — Increment 149: multi-provider LLM engine (#39 part 1)
- **Files:** `app/backend/llm/providers.py` (new), `integrations/gemini/generator.py` (+ the 5 other
  `integrations/gemini/*.py` generators), `app/backend/llm/egress.py`, `app/backend/app_settings.py`,
  `app/backend/api/routers/{summaries,axes,my_publications}.py`, `tests/test_providers.py` (new),
  `.claude/security-audits/2026-06-26_multi-provider-llm.md`, `INCREMENT-149-NOTES.md`.
- **What:** One `complete(config, prompt)` seam routes all 6 generators to Gemini/OpenAI/Anthropic/local (httpx,
  no new dep). `GeminiConfig`→`LLMConfig` (+alias) gains `provider`/`base_url` + per-provider key resolution; the
  `EgressGated*` gate is provider-aware (`requires_egress`); a **loopback** local provider runs with **zero egress**.
- **Why:** BYOK beyond Gemini (#39) — and a local model means AI summaries that never leave the machine.
- **Revert:** revert the 6 generators to the genai call + drop providers.py + the gate `provider` field; from git.

## 2026-06-26 — Increment 148: synthesis pane "AI is off" nudge (frontend-only)
- **Files:** `app/frontend/js/{40_app,20_synthesis}.jsx` + `styles.css` + `callosum-app.html`,
  `app/backend/help/help_content.md`, `INCREMENT-148-NOTES.md`.
- **What:** When AI is off, the Synthesis pane shows an **"AI summaries are off — Enable in Settings →"** nudge
  (proactive + in place of the raw `DataEgressDisabledError`) instead of a dead-end. `paneCtx.onOpenSettings` +
  a `settingsNonce` (re-read egress on Settings close) wire it; the button opens the Settings modal.
- **Why:** A user who tries to summarize with egress off got a developer-y error with no path to fix it.
- **Revert:** restore the two frontend chunks + `styles.css` from git + rebuild.

## 2026-06-26 — Increment 147: "Test this key" — egress-gated key validation
- **Files:** `app/backend/api/routers/settings.py`, `app/frontend/js/35_settings.jsx` + `styles.css` +
  `callosum-app.html`, `app/backend/help/help_content.md`, `tests/test_settings.py`, `tests/test_health.py`,
  `.claude/qa-routes/route_35_settings.md`, `.claude/security-audits/2026-06-26_test-key.md`, `INCREMENT-147-NOTES.md`.
- **What:** A **Test key** button (Settings → AI features) validates a saved Gemini key via a tiny non-library
  ping. `POST /settings/test-key` → `{ok, detail}`; gated on egress ON (off ⟹ no outbound call); key never
  logged/returned (errors redacted).
- **Why:** A BYOK user wants to confirm a pasted key works before relying on it — without running a full summary.
- **Revert:** remove the endpoint + the Settings button; restore from git.

## 2026-06-26 — Increment 146: BYOK — Gemini API key + egress consent from the Settings UI
- **Files:** `app/backend/app_settings.py` (new), `app/backend/api/routers/settings.py` (new),
  `app/backend/api/app.py`, `integrations/gemini/generator.py`, `app/frontend/js/35_settings.jsx` + `styles.css` +
  `callosum-app.html`, `app/backend/help/help_content.md`, `tests/conftest.py`, `tests/test_settings.py`,
  `tests/test_health.py`, `.claude/qa-routes/route_35_settings.md`,
  `.claude/security-audits/2026-06-26_byok-api-key.md`, `INCREMENT-146-NOTES.md`.
- **What:** Bring-your-own-key — set the Gemini API key **and** toggle data egress from **Settings → AI features**,
  not just env vars. A local store (`~/.callosum/app-settings.json`, outside the repo + synced Dropbox) overlays the
  env defaults in `GeminiConfig.from_environment()` (so every AI feature picks it up with zero call-site changes).
  `GET /settings` returns status only (never the key value); `PUT /settings` sets/clears the key + toggles egress.
- **Why:** A GitHub user shouldn't have to edit a `.env` to use AI. The key never leaves the machine except to
  Google; egress stays default-OFF + explicit (invariant #3 unchanged); the key is write-only over the wire.
- **Revert:** delete the two new backend files + the router include + the `GeminiConfig` overlay + the frontend
  section; restore from git. (No migration.)


- **Files:** `app/frontend/js/10_pdf_layer.jsx` + `20_synthesis.jsx` + `40_app.jsx` + `styles.css` +
  `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_55_synthesis_verification.md`,
  `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-145-NOTES.md`. (Help corpus also brought current for inc 143/144.)
- **What:** Ran the **Skeptical synthesizer** persona pass on the select→summarize flow → the focus query (a
  query-ranked multi-paper synthesis, inc 111) **already worked but was invisible** (the focus lived in the
  Synthesis textarea, not the selection bar; the help even misframed it). Added a **"Focus on… (optional)"** input
  to the selection bar → threads to the multi-paper synthesis as `query` (query-ranked) + reflects into the
  textarea + the "focused on …" scope-note. Frontend + a help fix.
- **Why:** A skeptic would never discover the focused path and walk away thinking it only does generic summaries.
- **Revert:** restore the listed frontend files from git + rebuild.

## 2026-06-26 — Increment 144: export / copy a paper's highlights + notes (Close reader dogfood)
- **Files:** `app/frontend/js/30_viewer.jsx` + `styles.css` + `callosum-app.html`,
  `.claude/qa-routes/route_32_viewer_annotations.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-144-NOTES.md`.
- **What:** Ran the **Close reader** persona pass on the read→highlight→note→return flow → reading + marking +
  re-finding all work well, but the marks were trapped in the panel (no way to get them out). Added **Copy** +
  **Export .md** buttons in the Notes panel head → a Markdown digest of the paper's highlights + notes (built from
  the loaded annotations; `navigator.clipboard` + blob-download, the inc-70 pattern). Frontend-only.
- **Why:** A close reader's payoff is the marked-up artifact — "show me everything I marked, as a list I can carry
  elsewhere."
- **Revert:** restore `30_viewer.jsx` + `styles.css` from git + rebuild.

## 2026-06-26 — Increment 143: deleting an imported keyword tag is durable (Librarian pass + backlog #3)
- **Files:** `app/backend/persistence/schema.py` + `alembic/versions/0020_suppressed_paper_tags.py` (new),
  `app/backend/persistence/tags_repo.py`, `app/backend/metadata/enrichment.py`, `tests/test_tags.py`,
  `.claude/qa-routes/route_20_tags.md`, `INCREMENT-143-NOTES.md`.
- **What:** Ran the **Librarian** persona pass on the tag-curation flow → found deleting an imported keyword tag
  wasn't durable (🔎 re-resolve silently re-added it; tags don't duplicate + mine-vs-imported is clear — those
  work). Built a per-paper **suppressed-keyword** set (`suppressed_paper_tags`, migration 0020): removing an
  imported `keyword:*` tag records a suppression; `apply_crossref_subject_tags` skips suppressed names; re-adding a
  tag clears it. Backend-only.
- **Why:** A librarian must trust curation is non-destructive — a deliberate keyword removal shouldn't be undone by
  the next enrich.
- **Revert:** restore the listed files from git; `suppressed_paper_tags` is additive (migration 0020).

## 2026-06-26 — Increment 142: determinate import/scan progress (Migrator experience pass + backlog #4)
- **Files:** `app/backend/api/job_store.py`, `app/backend/embeddings/pipeline.py`,
  `app/backend/pdf_processing/library_scan.py`, `app/backend/api/routers/library.py`,
  `app/frontend/js/10_pdf_layer.jsx` (ProgressBar) + `27_scan.jsx` + `28_import.jsx` + `40_app.jsx` + `styles.css`
  + `callosum-app.html`, `tests/test_job_store.py` (new) + `test_embeddings.py`, `INCREMENT-142-NOTES.md`.
- **What:** Ran the **Migrator** persona pass on the import/scan onboarding flow → found the bar was an opaque
  indeterminate pulse ("looks identical at item 3 and item 380"). Built **determinate "X / N" progress**
  (`JobStore.mark_progress` + `on_progress` callbacks through `embed_papers`/`embed_chunks`/`scan_library_folder`
  → the modals render a real fill + "Embedding papers — X / N") + a **"Review unsorted →"** door in the scan
  done-summary → the inc-80 Unsorted view.
- **Why:** A few-hundred-item import felt like a black box; the migrator's #1 anxiety is "is it stuck / how far".
  Opt-in + additive (other jobs stay indeterminate).
- **Revert:** restore the listed files from git + rebuild.

## 2026-06-26 — Increment 141: statcheck flagged→detail path (the experience-pass fix)
- **Files:** `app/frontend/js/40_app.jsx` + `06_methods_statcheck.jsx` + `callosum-app.html`,
  `.claude/qa-routes/route_33_methods_statcheck.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-141-NOTES.md`.
- **What:** The inc-140 experience-pass dogfood found "this paper is flagged" never linked to "the specific result
  that doesn't recompute." Fix (frontend-only): the "⚠ N flagged" chip now opens the METHODS **Statistics check**
  section, re-targets the top *flagged* paper (a deferred-select ref, so it uses the filtered list not the stale
  one), and the per-paper check **auto-runs** when that section is open — so the inconsistent rows (reported vs
  recomputed *p* + page) show with no manual "Check statistics" click.
- **Why:** Close the experience gap the persona agent surfaced — the deadline citer's exact frustration.
- **Revert:** restore the two frontend files from git + rebuild.

## 2026-06-26 — Increment 140: the end-user experience pass (a 4th gate) + its first dogfood
- **Files:** `.claude/EXPERIENCE-PASS.md` (new), `.claude/CLAUDE.md` (rule #11 + reference row + footer),
  `.claude/docs/INCREMENT-BACKLOG.md` (the dogfood finding), `INCREMENT-140-NOTES.md`.
- **What:** Codifies a standing orientation — before any user-facing change is "done," make a pass *inhabiting the
  end user* (reception + intended-use, the latter bounded by the #9 + A-A vetoes) via **persona-grounded
  experience agents** (a subagent in-character as a concrete user with a goal-in-the-moment). The 4th gate beside
  DESIGN (looks) / PRINCIPLES (honest) / QA (works+covered): **EXPERIENCE (serves the user).** Dogfooded it on
  statcheck (the deadline-citer persona) → found the "this paper is flagged → the specific result that doesn't
  recompute" path is hidden; filed it **▲ BUILD FIRST** to the backlog.
- **Why:** A change can pass DESIGN/PRINCIPLES/QA and still strand a real person mid-task (the statcheck case the
  user kept raising). This gate catches that.
- **Revert:** delete `EXPERIENCE-PASS.md` + the rule #11 / reference-row / backlog additions. Docs-only.

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 139) — help corpus current as of the Tags-tab / accordion-tabs rewrite -->
## 2026-06-26 — Increment 139: accordion tabs-within-a-section (Tags → a tab of AXES; METHODS reordered)
- **Files:** `app/frontend/js/05_panes.jsx` + `15_axes.jsx` + `10_pdf_layer.jsx` + `06_methods_statcheck.jsx` +
  `07_methods_grim.jsx` + `styles.css` + `callosum-app.html`, `.claude/DESIGN.md`, `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_00_smoke_readonly.md` + `route_20_tags.md`, `INCREMENT-139-NOTES.md`.
- **What:** The pane registry gains **tabs-within-a-section** (`registerPaneTab`); **Tags** moves from its own
  THEORY section to the **second tab of AXES** (`[Axes | Tags]`); METHODS reordered so **Data consistency (GRIM)**
  precedes **Statistics check**. Tab strip reuses the `.tags-srcfilter` chip recipe; tabs mount-but-hide + persist.
- **Why:** Codify the IA rule (accordion sections = broad categories, tabs = like-with-like submenus, order by
  cognitive task) so the accordion stays shallow as more METHODS modules land (user request).
- **Revert:** restore the listed frontend files from git + rebuild.

## 2026-06-26 — Increment 138: auto-select the top library paper on load (Details populated)
- **Files:** `app/frontend/js/40_app.jsx`, `callosum-app.html`, `.claude/qa-routes/route_00_smoke_readonly.md`,
  `INCREMENT-138-NOTES.md`.
- **What:** On load the top library paper is auto-selected, so the METHODS → DETAILS section starts populated
  (its editable Details) instead of the "Select a paper …" hint. Fires only when nothing is selected and the
  (non-trash) list is ready; never overrides a user's selection. Frontend-only.
- **Why:** The right pane started empty until the user clicked a paper; auto-selecting the top one makes Details
  immediately useful on load (user request).
- **Revert:** remove the auto-select effect from `40_app.jsx` + rebuild.

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 137) — help corpus current as of the gap-finder v2 (direction/axis/cache) rewrite -->
## 2026-06-26 — Increment 137: gap-finder v2 (forward gap + axis-scoped + persistent cache)
- **Files:** `app/backend/clustering/gapfinder.py`, `integrations/openalex/adapter.py`,
  `app/backend/persistence/gap_repo.py` (new) + `schema_base.py` (new) + `schema_findings.py` (new) +
  `schema.py` (split) + `alembic/versions/0019_gap_candidates.py` (new), `app/backend/api/routers/gaps.py`,
  `app/frontend/js/36_gaps.jsx` + `10_pdf_layer.jsx` + `styles.css` + `callosum-app.html`, `tests/test_gapfinder.py`
  + `test_health.py`, `app/backend/help/help_content.md`, `.claude/security-audits/2026-06-26_gapfinder.md`
  (addendum), `.claude/qa-routes/route_41_gaps.md`, `INCREMENT-137-NOTES.md`.
- **What:** Extends the gap-finder with a **forward** direction (works that *cite* your papers), **axis-scoped**
  scanning, and a **persistent `gap_candidates` cache** (GET reads instantly + filters dismissed/in-library at
  read time; Refresh recomputes). New OpenAlex `fetch_work_id` + `fetch_citing_works`; new `GET /gaps` +
  `POST/GET /gaps/refresh` (replacing `/gaps/find*`). Frontend gains a direction toggle + axis dropdown + Refresh.
- **Why:** The user chose "persistent cache + axis-scoped + forward gap" — surface newer work building on the
  library, scope discovery to a topic, and open the modal instantly without re-scanning.
- **Also:** Split `schema.py` (611 → 558, over the 600-line cap from inc 130/132) — the findings/signals/retraction
  + gap tables moved to `schema_findings.py` on a shared `schema_base.metadata`, re-exported (zero blast radius).
- **Revert:** restore the listed files from git (this commit); `gap_candidates` is additive (migration 0019).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 136) — help corpus current as of the watched-folder focus-rescan line -->
## 2026-06-26 — Increment 136: watched folders rescan on window focus (live-ish pickup)
- **Files:** `app/frontend/js/40_app.jsx`, `app/backend/help/help_content.md`, `INCREMENT-136-NOTES.md`.
- **What:** Watched-folder rescans now also fire when the window regains focus (throttled 20s + in-flight guard),
  not just on launch — so a PDF dropped into a watched folder appears when you switch back to Callosum (its DOI is
  read from the file → enriched → retraction-checked, all already wired). Frontend-only.
- **Why:** A user dropped a PDF expecting it to appear; rescans only ran on launch, so nothing happened
  mid-session. A reasonable user expects a watched folder to feel live.
- **Revert:** restore `40_app.jsx` from git (this commit).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 135) — help corpus current as of the "Finding gaps" section -->
## 2026-06-26 — Increment 135: literature gap-finder (backward citation gap)
- **Files:** `integrations/openalex/adapter.py`, `app/backend/clustering/gapfinder.py` (new),
  `app/backend/api/routers/gaps.py` (new), `app/backend/persistence/profile_repo.py` + `schema.py` +
  `alembic/versions/0018_profile_dismissed_gaps.py` (new), `app/backend/clustering/my_publications.py`,
  `app/backend/api/app.py`, `app/frontend/js/36_gaps.jsx` (new) + `10_pdf_layer.jsx` + `40_app.jsx` + `styles.css`,
  `tests/test_gapfinder.py` (new) + `test_health.py`, `.claude/security-audits/2026-06-26_gapfinder.md` (new),
  `.claude/qa-routes/route_41_gaps.md` (new), `help_content.md`, `INCREMENT-135-NOTES.md`.
- **What:** Aggregate each library paper's OpenAlex `referenced_works` → surface works cited by ≥N of your papers
  that you don't have ("cited by N of your papers") as Add/Dismiss candidates. New OpenAlex fetches
  (`fetch_referenced_works` + `fetch_work_meta`); `clustering/gapfinder.compute_gaps`; an ephemeral async job
  (`POST/GET /gaps/find`); `POST /gaps/add` (metadata-only into the general library, reusing import_citing_work) +
  `POST /gaps/dismiss` (persisted in `profile.dismissed_gap_works`, migration 0018); a "Gaps" library-header
  button + modal. The count is the user's-library citing, never a quality rank; coverage stated.
- **Why:** A long-wanted discovery capability — find the important references your library leans on but is missing.
- **Revert:** restore the listed files from git (commits `…t1` adapter/compute, `…t2` migration+endpoints, `…t3`
  UI, + this docs commit); migration 0018 is additive (drop the `dismissed_gap_works` column to revert).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 134) — help corpus current as of the on-import/staleness lines -->
## 2026-06-26 — Increment 134: retraction lifecycle (on-import auto-check + RW staleness nudge)
- **Files:** `app/backend/methods/retraction.py` (`auto_check_retractions`), `app/backend/api/routers/library.py`
  (scan + import hooks), `app/frontend/js/08_methods_findings.jsx` + `styles.css`, `tests/test_retraction.py`,
  `.claude/security-audits/2026-06-26_retraction.md` (addendum), `help_content.md`, `INCREMENT-134-NOTES.md`.
- **What:** New papers are auto-checked for retraction on import (the scan + citation-import jobs, guarded
  best-effort over the new paper ids, reusing the inc-131 checkers) so a freshly imported retracted paper flags
  immediately; the Retraction Watch panel surfaces its snapshot age and nudges a refresh past 30 days.
- **Why:** Completes the producer's world-state lifecycle — automatic at import, with staleness visible — beyond
  the on-demand batch/per-paper.
- **Revert:** restore the listed files from git (commits `…t1` backend, `…t2` frontend, + this docs commit); no
  migration/endpoint to undo.

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 133) — help corpus current as of the review-queue lines -->
## 2026-06-26 — Increment 133: activate the candidate-review half (statcheck candidates + "N to review" facet)
- **Files:** `app/backend/api/routers/methods.py` (statcheck batch), `repository.py` (the `finding` filter),
  `routers/papers.py` (the `finding` param), `app/frontend/js/{40_app,10_pdf_layer}.jsx` + `styles.css`,
  `tests/test_findings_review.py` (new), `.claude/qa-routes/route_38_findings.md`, `help_content.md`, `INCREMENT-133-NOTES.md`.
- **What:** The statcheck batch now also emits a CANDIDATE finding per flagged paper (coexisting with the inc-97
  signal — candidate = the user's reviewable work-state, signal = the persistent fact), and a unified "📋 N to
  review" library chip + filter (`GET /papers?finding=needs-review` → `FINDING_FILTERS` bound subquery) surfaces
  every paper with an unreviewed candidate; reviewing one drops it from the queue live.
- **Why:** The inc-130 Confirmed/Accepted/Noted candidate-review machinery was built but unexercised (retraction
  writes facts); this gives it real content + a place to triage it library-wide.
- **Revert:** restore the listed files from git (commits `…t1` backend, `…t2` frontend, + this docs commit); no
  migration to undo (reuses `paper_findings` + a query param).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 132) — help corpus current as of the RW-database paragraph -->
## 2026-06-26 — Increment 132: Retraction Watch DB (SP2) — the bulk third retraction source
- **Files:** `app/backend/persistence/schema.py` + `retraction_repo.py` (new), `alembic/versions/0017_retraction_records.py`
  (new), `integrations/retraction_watch/{__init__,adapter}.py` (new), `app/backend/methods/retraction.py`,
  `app/backend/api/routers/methods.py`, `app.py`, `app/frontend/js/08_methods_findings.jsx` + `styles.css`,
  `tests/test_retraction_watch.py` (new) + `test_health.py`, `.claude/qa-routes/route_40_retraction_watch.md` (new),
  `.claude/security-audits/2026-06-26_retraction-watch.md` (new), `help_content.md`, `INCREMENT-132-NOTES.md`.
- **What:** Download the Crossref-hosted Retraction Watch DB (CC0 CSV) into a local `retraction_records` mirror
  (migration 0017) + a third checker (`RETRACTION_WATCH_CHECKER`, prepended to DEFAULT_CHECKERS — richest source,
  its reason/date/notice wins the merge) + `GET /methods/retraction/database` + async `POST`/`GET
  /methods/retraction/database/refresh` + a "Refresh database" UI with an as-of line. Reinstatements never flagged;
  replace-all keeps the mirror honest.
- **Why:** Completes the user's "all three sources" ask — the RW DB is the authoritative, richest retraction
  source; matching offline scales to the whole library from one download.
- **Revert:** restore the listed files from git (commits `…t1` storage+adapter, `…t2` checker+endpoints, `…t3` UI,
  + this docs/gates commit); migration 0017 is additive (drop `retraction_records` to revert the schema).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 131) — help corpus current as of the "Retraction checks" section -->
## 2026-06-26 — Increment 131: retraction producer (SP1: Crossref + OpenAlex) — the first findings producer
- **Files:** `app/backend/methods/retraction.py` (new), `integrations/crossref/adapter.py`,
  `integrations/openalex/adapter.py`, `app/backend/persistence/signals_repo.py`, `repository.py`,
  `app/backend/api/routers/methods.py`, `app.py`, `app/frontend/js/{08_methods_findings,10_pdf_layer,40_app}.jsx`,
  `styles.css`, `tests/test_retraction.py` (new) + `test_health.py`, `.claude/qa-routes/route_39_retraction.md` (new),
  `.claude/security-audits/2026-06-26_retraction.md` (new), `DESIGN.md`, `help_content.md`, `INCREMENT-131-NOTES.md`.
- **What:** Multi-source (Crossref + OpenAlex) per-DOI retraction detection → a FACT in `paper_findings`
  (Review-pane FactMark + notice link + ◆ card mark) + an honest per-paper check status in
  `open_science_signals` (silence ≠ clean) + a library "Retracted" chip/filter + a library-wide batch. `GET
  /papers/{id}/retraction`, `POST`/`GET /methods/retraction/run`, `GET /methods/retraction/summary`. No migration.
- **Why:** The first real findings producer; retractions are high-stakes to know before citing. A registry FACT
  relayed verbatim (no LLM), evidence-carried (sources + notice), no-accusation (the A-A veto), silence-honest.
- **Revert:** restore the listed files from git (commits `…t1` core, `…t2` endpoints, `…t3` UI, + this docs/gates
  commit); no migration to undo (reuses `paper_findings` + `open_science_signals`).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 130) — help corpus current as of the findings "Review" section -->
## 2026-06-26 — Increment 130: findings subsystem (FACT-vs-CANDIDATE backbone), foundation only
- **Files:** `app/backend/persistence/schema.py` + `findings_repo.py` (new), `alembic/versions/0016_paper_findings.py`
  (new), `app/backend/api/routers/findings.py` (new) + `app.py`, `app/frontend/js/08_methods_findings.jsx` (new) +
  `10_pdf_layer.jsx` + `40_app.jsx` + `styles.css`, `tests/test_findings.py` (new) + `test_health.py`,
  `.claude/qa-routes/route_38_findings.md` (new) + `route_00_smoke_readonly.md`, `.claude/DESIGN.md`,
  `app/backend/help/help_content.md`, `.claude/security-audits/2026-06-26_findings.md` (new), `INCREMENT-130-NOTES.md`.
- **What:** A persistent, typed, per-paper **findings** store (`paper_findings`, migration 0016) + a review surface.
  Producers call `upsert_findings` (idempotent by `content_key` — supersede + preserve unchanged reviews); the
  METHODS "Review" section renders **facts** as neutral marks and **candidates** as reviewable cards (Confirmed /
  Accepted[reason] / Noted); the library card shows a `◆ fact` mark + an `N to review` work-state badge from
  `GET /findings/overview`. Endpoints: `GET /papers/{id}/findings`, `GET /findings/overview`,
  `POST /findings/{id}/review`. **Contract + UI only — no producer wired yet** (retraction is next).
- **Why:** The FACT-vs-CANDIDATE backbone the data-detective features (statcheck/p-curve/GRIM/retraction) plug into;
  encodes the honesty distinction structurally (signal-not-verdict, no score, no accusation, human-is-the-filter).
- **Revert:** restore the listed files from git (commits `8aa278d` schema+repo, `1006513` endpoints, `7c3a87c` UI, +
  the docs/gates commit); migration 0016 is additive (drop `paper_findings` to fully revert the schema).

## 2026-06-25 — Increment 125: strengthen the front-matter classifier (live-validated)
- **Files:** `app/backend/summarization/chunk_filtering.py`, `tests/test_chunk_filtering.py`,
  `INCREMENT-125-NOTES.md`.
- **What:** A live real-Gemini synthesis (user-authorized token spend) showed inc-123's classifier still let
  paper titles, author/affiliation lines, journal running-headers, and funding lines into the verified claims.
  Strengthened `is_front_matter_chunk` to catch those (name-attached + digit-prefix author superscripts;
  funding/grant-id lines; Title-Case-without-terminal-punctuation titles/headers — safe for prose). Real leaked
  examples are now regression tests.
- **Why:** inc 123 (front-matter fix) was too conservative on real data; the verified claims (and the inc-124
  Overview built on them) must be body text. Confirmed live: clean claims + a real 3-sentence Overview with
  per-sentence claim traces.
- **Revert:** restore the inc-123 `is_front_matter_chunk` body (commit `e446b46`).

## 2026-06-25 — Increment 129: multi-item GRIMMER
- **Files:** `app/backend/methods/grim.py`, `app/frontend/js/07_methods_grim.jsx`, `callosum-app.html`,
  `app/backend/help/help_content.md`, `tests/test_grim.py`, `INCREMENT-129-NOTES.md`.
- **What:** Completes inc-127 GRIMMER — `grimmer_test` now supports `items > 1` (multi-item scales): the same
  analytic check with an `items²` factor on the variance term + the total over `N*items` responses + the same
  parity refinement. Validated against the scrutiny reference (2.74/0.96/63/items=2 → consistent). `supported` is
  now always true; removed the dead frontend "unsupported" branch (rule #5).
- **Why:** GRIMMER shipped single-item-only in inc 127; this finishes it. Errs toward leniency (safe,
  non-accusatory direction).
- **Revert:** restore the `items != 1 → supported=False` guard + the single-item SS formula in `grimmer_test`.

## 2026-06-25 — Increment 128: split 40_app.jsx (relieve the 600-line cap)
- **Files:** NEW `app/frontend/js/04_layout.jsx`; `app/frontend/js/40_app.jsx`, `callosum-app.html`,
  `INCREMENT-128-NOTES.md`.
- **What:** Behavior-preserving refactor — moved the layout helpers (`_loadLayout`/`_saveLayout`/`_clampW`/
  `_beginDrag`/`Divider` + the `LEFT_*`/`RIGHT_*` consts) and a new `useUiPrefs()` hook (theme + axis/scan prefs +
  panel layout + accordion-open + Reading mode) out of `40_app.jsx` into a new early-loading chunk. `40_app.jsx`
  **590 → 514**; `04_layout.jsx` 107.
- **Why:** `40_app.jsx` was at 590/600 (rule-#1 risk flagged since inc 126/127); cleared before the next feature
  lands there. No user-facing change, no API change, no new surface.
- **Revert:** restore the helper block + the inline pref/layout state in `40_app.jsx`; delete `04_layout.jsx`.

## 2026-06-25 — Increment 127: GRIM + GRIMMER data-consistency calculator
<!-- HELP-DOCS-SYNCED: app/backend/help/help_content.md current as of increment 127 (2026-06-25) — added a "Data consistency (GRIM / GRIMMER)" section. Entries ABOVE this line are newer than the last help sync. -->
- **Files:** NEW `app/backend/methods/grim.py`, `app/frontend/js/07_methods_grim.jsx`,
  `.claude/security-audits/2026-06-25_grim.md`, `.claude/qa-routes/route_37_methods_grim.md`,
  `INCREMENT-127-NOTES.md`; `app/backend/api/routers/methods.py`, `app/frontend/styles.css`, `callosum-app.html`,
  `app/backend/help/help_content.md`, `THIRD-PARTY-NOTICES.md`, `tests/{test_grim.py, test_health.py}`.
- **What:** The second GRIM/p-curve "data-detective" METHODS feature — an **assisted, per-value GRIM + GRIMMER
  calculator** (METHODS pane → "Data consistency (GRIM)"): enter a reported mean (+ SD), N, items → is it
  mathematically possible for integer data, with nearest-possible values + caveats + credit/add-to-library.
- **Why:** The user asked for GRIM (via the Lakens catalog). An assisted calculator (not an auto-scanner) is
  reliable + honest — extraction of mean+N+granularity from prose is unreliable. Inherently non-accusatory.
- **Gates:** Principles #9 aligned; audit `2026-06-25_grim.md` PASS; rule #10 route_37 + surface 91 API / 484 FE,
  0 uncovered; credit-the-lineage (THIRD-PARTY-NOTICES + in-context + add-to-library). No DB/migration/egress.
  GRIMMER is items=1 in v1 (multi-item deferred); GRIM supports items.
- **Revert:** `git revert` the inc-127 range, or drop `methods/grim.py` + the endpoint + the METHODS section.

## 2026-06-25 — Increment 126: p-curve (collection-level evidential-value check)
<!-- (prior help-sync marker for inc 126; superseded by the inc-127 marker above) added a "p-curve: evidential value" section. -->
- **Files:** NEW `app/backend/methods/pcurve.py`, `app/frontend/js/29_pcurve.jsx`,
  `.claude/security-audits/2026-06-25_pcurve.md`, `.claude/qa-routes/route_36_methods_pcurve.md`,
  `INCREMENT-126-NOTES.md`; `app/backend/api/{routers/methods.py, app.py}`, `app/frontend/js/{10_pdf_layer,40_app}.jsx`,
  `styles.css`, `callosum-app.html`, `app/backend/help/help_content.md`, `THIRD-PARTY-NOTICES.md`,
  `tests/{test_pcurve.py, test_health.py}`.
- **What:** The first GRIM/p-curve "data-detective" METHODS feature (p-curve first). Select papers → a **p-curve**
  bulk action → an async job (reusing the statcheck extractor) → a modal with the right-skew/binomial statistics +
  a hand-rolled SVG curve + the included tests + coverage + a credit block (add-to-library). Collection-level
  only; never per-paper; never "p-hacked"; the interpretation is the user's.
- **Why:** The user asked for GRIM/p-curve (via the Lakens automated-review catalog); p-curve reuses the proven
  statcheck p-value extraction (low risk). GRIM is the deliberate follow-up.
- **Gates:** Principles #9 aligned; audit `2026-06-25_pcurve.md` PASS; rule #10 route_36 + surface 90 API / 472 FE,
  0 uncovered; credit-the-lineage (THIRD-PARTY-NOTICES + in-context credit + library-add). No persistence/migration,
  no egress. **Note:** `40_app.jsx` now 590/600 — split overdue.
- **Revert:** `git revert` the inc-126 range, or drop `methods/pcurve.py` + the endpoint + the bulk action/modal.

## 2026-06-25 — Increment 124: synthesis evidence-traceable Overview (Part B)
<!-- (prior help-sync marker for inc 124; superseded by the inc-126 marker above) the synthesis-verification section gained an "Overview" paragraph. -->
- **Files:** NEW `app/backend/summarization/overview.py`, `integrations/gemini/overview.py`,
  `alembic/versions/0015_summary_overview.py`, `.claude/security-audits/2026-06-25_synthesis-overview.md`,
  `INCREMENT-124-NOTES.md`; `app/backend/{llm/egress.py, summarization/pipeline.py, persistence/schema.py,
  api/app.py, api/routers/summaries.py, help/help_content.md}`, `app/frontend/js/20_synthesis.jsx`, `styles.css`,
  `callosum-app.html`, `.claude/qa-routes/route_55_synthesis_verification.md`, `tests/{test_summary_overview.py,
  api_helpers.py}`.
- **What:** After a synthesis is generated + verified, a second LLM pass narrativizes ONLY the verified claims
  into a short **Overview** shown above them, where **each Overview sentence links back to the verified claim(s)
  it restates** (per-sentence trace; click → the claim flashes). Stored in a new `summaries.overview_json`
  column; egress-gated (`EgressGatedOverviewGenerator`); claim refs validated ⊆ the verified set + mapped to
  ordinals (citations inherited, never LLM-invented); 0 verified or egress-off → no overview.
- **Why:** Root cause #2 of "synthesis gives no real summary" — there was no synthesis-prose surface. Part B of
  the inc-123/124 design; framed "synthesized from the verified claims below" (traceable, not "unverified"), per
  the user's refinement.
- **Gates:** Principles #9 aligned; audit `2026-06-25_synthesis-overview.md` PASS; rule #10 route_55 extended;
  surface check 88 API / 462 FE, 0 uncovered. Migration head → 0015.
- **Revert:** `git revert` the inc-124 range, or drop the overview pass in `summarize_scope` + the
  `overview` response field + the `OverviewBlock` render.

## 2026-06-25 — Increment 123: synthesis no-query scope prefers content over front matter (Part A)
- **Files:** NEW `app/backend/summarization/chunk_filtering.py`; `app/backend/summarization/pipeline.py`,
  `tests/{test_chunk_filtering,test_summarize_selected}.py`, `INCREMENT-123-NOTES.md`.
- **What:** A conservative `is_front_matter_chunk` classifier + a two-phase `_select_no_query` so the no-query
  papers (and single-paper) synthesis scope feeds real body content, not title-page mastheads/DOIs/author lines.
- **Why:** Root cause #1 of "synthesis gives no real summary, just front matter" (validation summary #7) — the
  old `_round_robin_by_paper(rows)[:top_k]` fed the first chunk of each paper (its masthead). Part A of the
  inc-123/124 synthesis-overview design; Part B (the evidence-traceable Overview) is inc 124.
- **Revert:** restore the `_round_robin_by_paper(rows)[:top_k]` return in `_source_chunks_for_scope`.

## 2026-06-25 — Increment 122: statcheck relocated to a METHODS "Statistics check" section
<!-- HELP-DOCS-SYNCED: app/backend/help/help_content.md current as of increment 122 (2026-06-25) — the "Checking statistics (statcheck)" section's per-paper + library-wide passages were repointed from "Details pane" / "Settings → Statistics check" to "METHODS pane → Statistics check section". Entries ABOVE this line are newer than the last help sync. -->

- **Files:** NEW `app/frontend/js/06_methods_statcheck.jsx`; `app/frontend/js/{40_app,35_settings,25_detail}.jsx`,
  `callosum-app.html`, `.claude/DESIGN.md`, `.claude/qa-routes/{route_33_methods_statcheck,route_30_detail_pane,route_32_viewer_annotations}.md`,
  `app/backend/help/help_content.md`, `INCREMENT-122-NOTES.md`, `RECOVERY-LOG.md`, `.claude/CLAUDE.md`.
- **What:** Moved both statcheck surfaces — the library-wide batch (from `StatcheckSettings` in Settings) and the
  per-paper check (from `StatcheckRow` in the Details pane) — into a dedicated **METHODS accordion section**
  ("Statistics check", `06_methods_statcheck.jsx`, `order: 20`, after DETAILS). Added `onShowStatcheckFlagged` +
  `onStatcheckRan` to `paneCtx`; rewired the header **"⚠ N flagged" chip** refresh from "on Settings close" to
  "on mount + after a batch run". Removed statcheck from Settings and Details; kept the library chip + filter.
  Also swept stray `app/frontend/js/*.jsx.tmp.*` atomic-write orphans (rule #5).
- **Why:** The first real **METHODS** module on the inc-121 pane registry; co-locates the per-paper and
  library-wide statcheck; relieves the `25_detail.jsx` >600-line rule-#1 violation (625 → 579).
- **Honesty posture preserved verbatim** (Principles non-triggering): counts never a composite score; "a prompt
  to look, not a verdict"; non-accusatory; per-test rows open the page at region precision (no fake exact rect).
  Frontend-only — no backend/endpoint/migration/egress change. pytest 437. Surface check 0 uncovered (88/460).
- **Revert:** restore the `StatcheckSettings`/`StatcheckRow` blocks + the Settings-close-keyed chip effect (see
  commits `7bebfbc`/`44c6d76`/`5182419`), or `git revert` the inc-122 range.

## 2026-06-25 — Increment 121: THEORY/METHODS accordion side-panes on a module registry

- **Files:** NEW `app/frontend/js/05_panes.jsx`; `app/frontend/js/{40_app,10_pdf_layer,15_axes,20_synthesis,25_detail}.jsx`,
  `app/frontend/styles.css`, `callosum-app.html`, `.claude/DESIGN.md`, `.claude/qa-routes/route_00_smoke_readonly.md`,
  `app/backend/help/help_content.md`, `tests/qa surface-map (regen)`, `INCREMENT-121-NOTES.md`.
- **What:** Replaced the two fixed side-pane wrappers with **accordions** on an extensible **module registry**
  (`registerPaneSection({id,label,paneId,order,render})` + `<PaneAccordion>`). **Left** = THEORY accordion
  (Axes/Synthesis/Tags, one open at a time, AXES default); **right** = METHODS accordion (Details, with a
  select-a-paper hint). Sections self-register from their chunks; **mount-but-hide** keeps an in-progress synthesis
  alive across a switch; open section persists (`callosum.theoryOpen`/`methodsOpen`). Retired the inc-57 RightPane
  drag-split. **Soft labels** (section headers only; `paneId` is the internal THEORY/METHODS architecture).
  One intentional behavior change: **Tags always shows** (empty-state hint) instead of vanishing — discoverability.
- **Why:** the designated "next major upgrade" (the THEORY/METHODS future-track, UI-shell half) — place tools by
  the user's cognitive task; make the pane sections an additive registry for future METHODS modules.
- **Gate:** frontend-only; no backend/migration/egress; Principles gate non-triggering (behavior-preserving
  arrangement). DESIGN.md §5 added. Verified headed on `:8097` (switch/persist/synthesis-survives/details-on-select,
  0 console errors) + an additivity proof (a dummy chunk's section appeared with zero PaneAccordion edits).
- **Revert:** `git revert` the six inc-121 commits (`8b234d0`/`9022849`/`39508cb`/`0058ac0`/`ce35fb1` + this docs commit).
- **NB:** `25_detail.jsx` was already 625 (>600 pre-inc-121); the Details registration lives in `05_panes.jsx` to
  avoid worsening it — a split is queued (the statcheck→METHODS move will relieve it). **Next (user-queued):**
  (1) statcheck Settings→METHODS accordion section; (2) investigate synthesis showing no text summary.

## 2026-06-24 — Increment 120: QA mechanism — surface-coverage gate + Codex-exec supervisor

- **Files:** NEW `tools/qa/{build_surface_map.py, supervisor.py, _qa_serve.py, route_runner_prompt.md, __init__.py}`;
  `.claude/QA-POLICY.md`; `.claude/qa-routes/{_TEMPLATE.md + 15 route_NN_*.md}`; `.claude/CLAUDE.md` (rule #10 +
  kickoff #10 + layout/reference rows); `.gitignore`; `.github/workflows/ci.yml`; `INCREMENT-120-NOTES.md`.
- **What:** Installed the QA mechanism from `qa_routes.zip` (authored out-of-band): a **computed surface-coverage
  gate** (`build_surface_map.py` — static AST of the routers + JSX scan; `check` diffs vs. the `qa-routes/`
  `qa-coverage` blocks; API hard-gate, FE checklist), a **Codex-`exec` supervisor** that drives each route in a
  seeded throwaway browser and deposits severity-ranked reports to the watched `.claude/qa-inbox/`, and the
  **fixture/policy** that pins it to a disposable seeded DB + asserts the honesty invariants (egress gate,
  coordinate honesty, signal-not-verdict). New **rule #10** + kickoff #10 (triage the inbox). Had **Codex author
  the 13 missing routes** until the gate went green (**88/88 API + 460/460 FE covered**).
- **Why:** turn "no stone unturned" QA into a computed coverage guarantee + drop dev monitoring (Codex executes,
  a Claude session triages the inbox).
- **Verification:** `check` exits 0; `_qa_serve.py` serves a seeded throwaway DB (egress unset) + tears down;
  `supervisor --dry-run` emits a valid codex command; pytest 436 (additive, unchanged); ruff clean (incl. tools/qa).
- **Revert:** `git revert` `c95b791` + this commit; remove `tools/qa/` + `.claude/{QA-POLICY.md,qa-routes/}`.
- **Follow-on (same session):** ran the first **Tier-0** QA pass — clean (honesty invariants held: 0 egress with
  egress off, 0 page errors; no real app bugs). Fixed 3 Windows-portability bugs in the bundled supervisor
  (UTF-8 console, `shutil.which` for the codex shim, prompt-via-stdin — all caught before any credits spent; commit
  `5adc5e6`). Enriched `_seed_library` with a **real-PDF "Renderable Seed Paper"** (`tests/fixtures/seed.pdf`,
  truthful bboxes) + a tag so QA can exercise the viewer + coordinate-honesty + Tags panel, and calibrated
  `route_00` + the `_TEMPLATE` "Seed contract" (commit `ce934ed`; pytest 437; verified headed via `qa_server`).

## 2026-06-24 — Increment 119: My Publications overhaul, SP3 — citing articles & citation counts
- **Files:** `integrations/openalex/author.py`, `app/backend/clustering/my_publications.py`,
  `app/backend/api/routers/my_publications.py`, `app/frontend/js/{10_pdf_layer,31_mypubs_dashboard,33_mypubs_pubs,34_mypubs_citing [new]}.jsx`,
  `app/frontend/styles.css`, `app/backend/help/help_content.md`, `callosum-app.html`,
  `tests/{test_my_publications,test_health}.py`,
  `.claude/docs/specs/2026-06-24-mypubs-sp3-{citing-design,plan}.md`,
  `.claude/security-audits/2026-06-24_mypubs-citing.md`, `INCREMENT-119-NOTES.md`.
- **What:** Final My-Pubs sub-project (#14). Each own-pub card shows its **OpenAlex cited-by count** (verbatim +
  attributed); a **"Most cited"** sort; clicking the count opens a **citing-articles modal** (the papers OpenAlex
  records as citing it — discovery candidates, coverage stated) with per-row **Import** + a confirm-gated **Import
  all** (metadata-only, deduped, into the general library; the PDF stays the OA-acquire lane). Backend: capture the
  OpenAlex work id, `paper_citations` on the dashboard, `GET /my-publications/citing/{work_id}` (cached, capped 100,
  fail-closed) + `POST /my-publications/citing/import`; **Refresh now re-fetches works** so counts/ids stay fresh.
- **Why:** TDL #14 — surface who cites your work and let you pull those papers in.
- **Gate:** Principles gate run (spec §2 — aligned: verbatim+attributed count, candidates not verdicts, human-selected
  metadata-only import, OA-only PDFs); security audit PASS (new OpenAlex `cites:` fetch + 2 endpoints). No migration;
  public-metadata egress only (NOT the Gemini gate).
- **Revert:** `git revert` the six SP3 commits (`e695dd4`, `2cbbfc8`, `be41163`, `26c3ffa`, `d90dc2c`, + this docs commit).
- **NB:** **completes the My Publications overhaul (SP1 inc 117 + SP2 inc 118 + SP3 inc 119 = TDL #1 + #3–18).**

## 2026-06-24 — Increment 118: My Publications overhaul, SP2 — domain organization
<!-- (help sync marker moved to inc 119 above) -->

- **Files:** `app/backend/api/routers/{my_publications,axes}.py`, `app/backend/clustering/my_publications.py`,
  `app/backend/persistence/profile_repo.py`, `app/frontend/js/{15_axes,31_mypubs_dashboard,33_mypubs_pubs}.jsx`,
  `app/frontend/styles.css`, `app/backend/help/help_content.md`, `callosum-app.html`,
  `tests/{test_my_publications,test_axes,test_health}.py`,
  `.claude/docs/specs/2026-06-24-mypubs-sp2-{domains-design,plan}.md`,
  `.claude/security-audits/2026-06-24_mypubs-domain-rename.md`, `INCREMENT-118-NOTES.md`.
- **What:** Organize the My Publications corpus by research domain. A **Group by domain** toggle (dashboard list +
  sidebar axis card) regroups the publications under per-domain headers/subheadings with an **Other** group;
  **starred-first** sorting; **rename domains** inline (pre-suggesting the closest axis name) with names that
  **persist across Re-decompose** by paper-overlap; and **#18** — selecting a domain locks the Overview chart to
  Publications (filtered) and disables the Citations flip. Backend additive: `Domain.paper_ids`, `starred_ids`,
  per-paper `domain` on the my-pubs clusters response, and `POST /my-publications/domains/rename` (local profile-JSON
  edit). No migration, no egress.
- **Why:** TDL #9/#15/#16/#17/#18 — make the own-corpus navigable by research area, in both the dashboard and the
  pinned sidebar card.
- **Revert:** `git revert` the six SP2 commits (`8eb3e52`, `f028939`, `df0ef22`, `1078d42`, `922c063`, + this docs commit).
- **NB:** this docs commit also applies a `ruff format` pass the T1/T2 commits had missed (whitespace-only).

## 2026-06-24 — Increment 117: My Publications overhaul, SP1 — dashboard restructure & publication cards

- **Files:** `integrations/openalex/author.py`, `app/backend/clustering/my_publications.py`,
  `app/backend/api/routers/my_publications.py`, `app/frontend/js/{10_pdf_layer,30_viewer,31_mypubs_dashboard,
  32_mypubs_missing [new],33_mypubs_pubs [new],40_app}.jsx`, `app/frontend/styles.css`,
  `app/backend/help/help_content.md`, `callosum-app.html`, `tests/test_my_publications.py`,
  `.claude/docs/specs/2026-06-24-mypubs-sp1-{restructure-design,plan}.md`, `INCREMENT-117-NOTES.md`.
- **What:** First sub-project of the My Publications overhaul. Restructured the dashboard into author-priority order
  — **Overview** (collapsible 2×2 metrics + one **Publications⇄Citations** flip-chart, last 10 yrs `'NN`) →
  **Research summary** (⭐-only toggle hidden when 0 starred) → **Publications** (axis-scoped library cards via
  `/papers?axis_id`, search/sort + checkbox bulk bar [summarize/export/bibliography/delete] + copy + open, relocated
  Decompose button) → Research domains → **OpenAlex footer card** (as-of provenance, gap, 2-yr mean citedness +
  affiliation + profile link, Refresh, the missing-works **modal** trigger). Extracted a shared `PaperCard` from
  `PaperList`. Backend additive only: `openalex_extra` + `starred_count` on the dashboard response (parsed from the
  already-cached OpenAlex author object — no new endpoint, migration, or egress).
- **Why:** TDL line 1 + #1/#3/#4/#5/#6/#7/#8/#10/#11/#12/#13 — make the author's own corpus a first-class,
  browsable publications library; metrics & pubs first, OpenAlex provenance last.
- **Revert:** `git revert` the six SP1 commits (`870a96b`, `0fcd198`, `abea7a1`, `df3c10d`, `c189f83`, + this docs commit).
- **NB:** increments **109–116** (frontend/UX TDL items incl. the inc-110 PDF page-view) are journaled in
  `RECOVERY-LOG.md`, not folded into this log or the CLAUDE.md footer.

## 2026-06-21 — Increment 108: LibreOffice (UNO) citation adapter — word-processor track, first adapter

- **Files:** NEW `adapters/` tree — `adapters/libreoffice/{callosum_cite.py [the macro], README.md,
  selftest_uno.py [headless harness]}`; `tests/test_libreoffice_adapter.py` (+5); `THIRD-PARTY-NOTICES.md`
  (Zotero `CSL_CITATION` pattern credit); the audit; `INCREMENT-108-NOTES.md`.
- **What:** a drop-in LibreOffice Writer Python macro for cite-while-you-write — insert live citation fields
  (ReferenceMarks carrying CSL-JSON), refresh/restyle/renumber, build/maintain the bibliography, and flatten to
  static text — all riding the inc-107 `POST /citations/render-document`. The adapter places fields; the backend
  citeproc engine formats (so output matches the in-app "Cite as…").
- **Why:** the first piece of the word-processor track that's visible *inside a word processor*; proves the
  render→place→read-back→write-back loop + the field abstraction the Word/Docs adapters reuse.
- **Scope:** client-side, **no server change** (no new endpoint/migration/route/egress; local 127.0.0.1 only); no
  third-party dep (stdlib `urllib` in LO's bundled Python). Verified by the **headless UNO round-trip** (real
  LibreOffice: IEEE `[1]`/`[2]`, APA author-date, flatten preserves text — SELFTEST OK) + 5 pytest pure-logic
  tests. Four UNO traps found+fixed (Hidden-load crash; bib stale-anchor; ReferenceMark write-back deleting the
  mark; stale-collection-ref hang / flatten deleting text). pytest **424** (+5); `ruff` clean. Audit
  `.claude/security-audits/2026-06-21_libreoffice-adapter.md` PASS.
- **Revert:** delete the `adapters/` tree + `tests/test_libreoffice_adapter.py` + the `THIRD-PARTY-NOTICES.md`
  adapter section. (No app code touched.)

## 2026-06-21 — Increment 107: position-aware document-render layer — word-processor track, Phase 2

- **Files:** `app/backend/citations/citeproc_runner.js` (new `mode:"document"` branch), `render.py`
  (`_run_engine`→`_run`; new `render_document`), `app/backend/api/routers/citations.py` (new endpoint + models);
  `tests/{test_citations,test_health}.py`; the audit; `INCREMENT-107-NOTES.md`.
- **What:** `POST /citations/render-document` renders a word-processor document's **ordered citation clusters**
  position-aware via citeproc's `rebuildProcessorState` — numeric renumbering `[1][2][3]`, author-date
  disambiguation `2020a`/`2020b`, + the bibliography. The shared contract every word-processor adapter (LibreOffice
  → Word → Google Docs) will call; the adapter places fields, the engine formats. Self-contained (renders from the
  passed CSL-JSON; no library lookup).
- **Why:** the inc-106 engine renders each cite in isolation (right for a *selection*, wrong for a live document).
  This is the substrate before any LibreOffice client — fully pytest-testable, de-risks render correctness.
- **Scope:** backend-only; **no frontend change** (no rebuild); no new dependency, no egress, no migration; output
  sanitized (`_safe_html`); input capped (clusters/items/total). pytest **419** (+3); `ruff` clean. Audit
  `.claude/security-audits/2026-06-21_citation-render-document.md` PASS.
- **Revert:** drop the `mode:"document"` branch in the runner, `render_document` + the `_run` rename, the
  `/citations/render-document` endpoint + models, and the test + route-allowlist additions.

## 2026-06-21 — Increment 106: citation & bibliography engine (citeproc-js) — word-processor track, Phase 1


- **Files:** NEW `app/backend/citations/` (`render.py`, `citeproc_runner.js`, `csl/{styles,locales}` bundled CSL
  data) + `app/backend/api/routers/citations.py`; `app/backend/api/app.py` (router include); `package.json` +
  `package-lock.json` (citeproc); `25_detail.jsx` (Cite-as), `10_pdf_layer.jsx` + `40_app.jsx` (bulk
  bibliography), `styles.css`; `callosum-app.html`; `tests/{test_citations,test_health}.py`; `THIRD-PARTY-NOTICES.md`;
  the audit; help corpus.
- **What:** formatted citations + bibliographies (APA/MLA/Chicago/IEEE/Nature/Harvard) rendered from
  `papers.csl_json` by **citeproc-js** (Node sidecar) over bundled CSL styles. In-app: Details **"Cite as …"**
  (style dropdown + live sanitized preview + copy) + a bulk **"bibliography…"** `.html` download.
  `GET /citations/styles` + `POST /citations/render`.
- **Why:** the foundation of word-processor integration (the citation engine every adapter rides) — and it closes
  the "no formatted styles" gap inside the app (inc-70 export was machine-readable only).
- **Scope:** new dep `citeproc` (pinned; audit gate → PASS); **no egress** (bundled styles); citeproc HTML
  sanitized server-side before in-app render. pytest **416** (+5); `ruff` clean; opt-in e2e (0 console errors).
- **Revert:** drop the `citations` package + router (+ app.py include), the frontend Cite-as/bibliography wiring,
  `citeproc` from package.json, and the bundled `csl/` data; rebuild.

## 2026-06-21 — Increment 105: default axis cutoff in Settings + a tag source filter (2 chores)

- **Files:** `40_app.jsx` (axisCutoffDefault state + threading), `15_axes.jsx` (AxisItem cutoff fallback + AxesPanel
  key), `35_settings.jsx` (Default-axis-cutoff slider), `10_pdf_layer.jsx` (Sidebar/AxesPanel threading +
  TagsPanel All/Yours/Keywords filter), `styles.css` (`.settings-cutoff`, `.tags-srcfilter`); `callosum-app.html`;
  help corpus.
- **What:** (1) a **Default axis cutoff** slider in Settings → Axes (persisted; a new/unscored axis's re-score
  flipper starts there; per-axis gain still wins). (2) an **All / Yours / Keywords** segmented filter in the
  sidebar Tags panel (filters by the inc-100 tag `source`; shown only when both kinds exist).
- **Why:** the "2 chores" of a fresh patter (carrot = the literature gap-finder, next, plan-mode).
- **Scope:** both **frontend-only** over existing data — no Python, no migration, no egress, no new endpoint.
  pytest **411** unchanged; `ruff` clean; opt-in Playwright smoke (2) passed (0 console errors).
- **Revert:** restore the touched frontend files (drop `axisCutoffDefault` threading + the TagsPanel `src` filter
  + the two CSS blocks); rebuild.

## 2026-06-21 — Tweak: hover outline matches the icon color (gear/help + axis edit/add)

- **Files:** `app/frontend/styles.css` (`.icon-gear:hover`, `.icon-help:hover`, new `.axis-icon-btn:hover`);
  `callosum-app.html`.
- **What:** on hover, the **settings/help** buttons and the axis **edit/add** (and dashboard/eye) buttons now turn
  their **outline the same accent (icon) color** as the svg — `border-color: var(--line-2)` → `var(--accent)` for
  gear/help; a scoped `.axis-icon-btn:hover { border-color: var(--accent) }` for the axis icons. The axis
  **delete** (`.axis-icon-danger`) is unchanged (icon + outline amber — already ideal); the canonical `.btn-icon`
  recipe is untouched (only `.axis-icon-btn` is used in JSX, so the override is scoped).
- **Why:** user request — outline should match the icon color on mouseover (delete already did this).
- **Scope:** CSS-only (tokens; rule #8 — canonical recipe unchanged). pytest unaffected (411).
- **Revert:** restore the three hover rules' `border-color` to `var(--line-2)` / remove the `.axis-icon-btn:hover`.

## 2026-06-21 — Process: future-tracks inbox processed (8 specs filed + 1 principle captured)

- **What:** ran the inbox-processing pass on `.claude/docs/future-tracks-import/` (10 content files + README).
  Moved the **8 capability/build specs** (citation-bibliography engine, Bayesian auditor, LMM auditor,
  citation-equity, CRediT builder, meta-analysis extraction workbench, BYOK provider keys, credit-help backfill)
  → `.claude/docs/future-tracks/`; added them to `future-tracks/README.md` (index) + `INCREMENT-BACKLOG.md`
  (longer-horizon tracks + a near-term credit-backfill maintenance note). Captured the cross-cutting
  **credit-the-lineage principle** into the values layer at **`.claude/CREDIT-THE-LINEAGE.md`** (registered in
  CLAUDE.md's tree + reference-docs table). Left the **parked** `…_acquisitiondeferred.md` (counsel-gated) + the
  inbox `README.md` in place, untouched.
- **Why:** the user dropped 10 md files in the inbox; the documented Phase-8 protocol is audit → fold into the
  backlog/index → move to `future-tracks/` (parked items stay). The future-state characterization had *covered*
  all 9 genuine specs but hadn't *integrated* them — this closes that.
- **Scope:** docs/process only; no app/code/test change. **Open decision flagged:** whether credit-the-lineage
  should be elevated to a hard rule-#9 gate trigger (currently a values-layer commitment, not yet wired); and the
  principle could be folded into `APPROACH-AVOIDANCE.md` instead of a standalone file if preferred.
- **Revert:** move the 8 files back to the inbox + `CREDIT-THE-LINEAGE.md` back; undo the index/backlog/CLAUDE.md
  additions.

## 2026-06-21 — Increment 104: panel min-widths + Spotify pull-to-collapse + sidebar-button reposition

- **Files:** `app/frontend/js/40_app.jsx` (min/collapse constants + init clamps + both divider drag handlers),
  `app/frontend/styles.css` (`.icon-gear`/`.icon-help` positions); `callosum-app.html`.
- **What:** (1) left (AXES) panel min drag width **300px**, right (Synthesis/Details) **415px**; (2) dragging a
  resizer ~80px past its min **auto-collapses** that panel (no chevron); (3) repositioned the header buttons —
  help down 7px / left 4px then both nudged left 15px (`top:19;right:33`), settings to the same height 27px left of
  help (`top:19;right:60`, was top-left); (4) both buttons now show an **always-on outline** (`border: 1px solid currentColor` — the icon
  color at rest), hover look unchanged.
- **Why:** user request (wider, Spotify-like resizable panels + a button-layout tweak).
- **Scope:** frontend-only — no backend/migration/egress. pytest **411** unchanged; `ruff` clean; opt-in
  Playwright smoke (incl. reading-mode panel test) passed (0 console errors). Thresholds + button offsets are
  one-line tunables.
- **Revert:** restore the two `40_app.jsx` divider handlers + init lines (and drop the constants), and the two
  `.icon-*` CSS rules; rebuild.

## 2026-06-21 — Increment 103: per-card "copy BibTeX" clipboard button

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (`PaperCopyButton` + `ClipboardIcon`/`CheckIcon` + render before
  the checkbox), `app/frontend/styles.css` (`.paper-copy` + `.paper-title` padding-right); `callosum-app.html`;
  help corpus.
- **What:** each Library card now shows a small **clipboard SVG button** just left of its checkbox that copies the
  paper's **BibTeX** to the clipboard in one click (icon → ✓ ~1.5s).
- **Why:** inc-98's `.paper { user-select:none }` (which fixed the double-click word-select) removed the ability
  to select/copy card text — this restores a one-click citation copy.
- **Scope:** frontend-only; reuses the tested inc-70 `POST /papers/export {format:"bibtex"}` → `navigator.clipboard`
  (mirrors the Details `CiteRow`); `stopPropagation` so it never selects/opens the card; shown only in the normal
  library `selecting` view. **No backend/endpoint/migration/egress.** pytest **411** unchanged; `ruff` clean;
  opt-in Playwright smoke passed (0 console errors). Also synced the help corpus (per-card copy + Reading mode +
  a stale "chunk count" fix) → `HELP-DOCS-SYNCED` moved to 103.
- **Revert:** remove `PaperCopyButton`/the two icons + the card render line + the two CSS blocks; rebuild.

## 2026-06-21 — Chore: ruff format hygiene pass (pre-existing drift)

- **Files:** `app/backend/api/routers/papers.py`, `app/backend/metadata/citation_import.py`,
  `app/backend/methods/statcheck.py`, `app/backend/persistence/tags_repo.py`, `tests/test_papers.py`,
  `tests/test_citation_import.py`, `tests/test_statcheck.py`.
- **What:** ran `ruff format .` — 7 files had pre-existing formatting drift (compact multi-arg calls from
  incs 91–97 that ruff 0.9.6 expands to one-arg-per-line). Pure formatting, no logic change.
- **Why:** surfaced while adding the inc-102 CI `npm ci` step; CI runs `ruff format --check .`, so this would
  have failed it. CLAUDE.md convention is to run `ruff format .` before committing. (Likely undetected because
  CI billing isn't active yet — a known inc-74 follow-on.)
- **Scope:** formatting only; `ruff check` clean; the reformatted test files re-run green (61 passed). pytest 411.
- **Revert:** the change is mechanical formatting; re-running the prior ruff version would differ — leave as-is.

## 2026-06-21 — Increment 102: precompile the JSX with esbuild (drop in-browser Babel)

- **Files:** NEW `package.json` + `package-lock.json` + `.gitignore` (`node_modules/`); `app/backend/api/frontend.py`
  (`assemble_jsx` + `_transpile_jsx` esbuild + `build_frontend_document`); `app/frontend/index.html` (drop babel
  CDN, plain `<script>`); `app/backend/api/app.py` (live-fallback try/except); `tests/test_frontend_assembly.py`
  + `tests/e2e/test_smoke.py`; `.github/workflows/ci.yml` (setup-node + npm ci); `callosum-app.html`; the audit.
- **What:** the frontend JSX is now **precompiled to plain JS by esbuild at build time** and served as a normal
  `<script>`; the `babel-standalone` CDN + `<script type="text/babel">` runtime transform are gone.
- **Why:** the in-browser Babel transformer emitted two dev-console messages (a "precompile for production"
  warning + a `babel.min.js.map` 404) and cost a ~500KB download — user asked to clear them. (The third console
  line, `XrayWrapper … content-script.js`, is an external browser extension — not callosum.)
- **Scope:** new **build-time** dependency (esbuild 0.28.1, pinned; `npm install`/`npm ci`; audit gate → PASS);
  the **server stays Python-only** (serves the prebuilt file). No app-behavior change (esbuild IIFE preserves the
  shared scope). pytest **411** unchanged; `ruff` clean; **opt-in Playwright smoke passed with 0 console errors**;
  `node --check` on the output clean.
- **Revert:** restore `index.html` (re-add the babel `<script>` + `type="text/babel"`), `frontend.py`
  (concatenate-only `build_frontend_document`), `app.py`, the tests + CI; remove `package.json`/lockfile; rebuild.

## 2026-06-21 — Fix (post-inc-101): double-click no longer word-selects a library card's title

- **Files:** `app/frontend/styles.css` (`.paper` rule), `10_pdf_layer.jsx` (comment), `callosum-app.html`.
- **What:** added `-webkit-user-select: none; user-select: none;` to the `.paper` card so double-clicking a card
  opens the PDF (inc-98) **without** the browser also highlighting the title word under the cursor.
- **Why:** inc-98 made `onDoubleClick` always open but never suppressed the browser's default double-click
  word-selection, so the title flashed highlighted on every open — user-reported.
- **Scope:** frontend-only CSS; interaction property, not a token/color/recipe (no DESIGN.md concern). Trade-off
  (user-confirmed): card text is no longer drag-selectable — it stays copyable in the **Details** pane. Card
  buttons/checkbox unaffected (`user-select` governs text selection only). pytest unchanged **411**; `ruff` clean.
- **Revert:** remove the `user-select: none` line from `.paper` and rebuild.

## 2026-06-21 — Increment 101: Reading mode (one-click distraction-free reader)

- **Files:** `40_app.jsx` (readingMode state + toggle + Esc + `cols`/className), `30_viewer.jsx` (`LibraryFrame`
  `.frame-reading` toggle), `styles.css` (`.frame-reading` + `.app.reading .divider`); `callosum-app.html`.
- **What:** a **⛶ Read** toggle at the right of the center tab bar hides both side panels and their dividers to
  maximize the open PDF; **⤢ Exit** or **Esc** restores the prior layout. Transient (a reload returns to normal).
- **Why:** the carrot of the inc 100–101 patter — a focused reading view, built on the inc-42 collapsible panels.
- **Scope:** frontend-only — no backend/migration/egress/new token (tokens-only CSS, rule #8). pytest **411**
  unchanged; `ruff` clean. Visual QA delegated (no Playwright MCP this session). No help-corpus change (the labeled
  toggle + tooltip are self-evident).
- **Revert:** restore the three frontend files (drop `readingMode`/`toggleReading` + the `.frame-reading` button +
  the two CSS rules) and rebuild.

## 2026-06-21 — Increment 100: statcheck "flagged" header chip + tag-source aesthetic differentiation

- **Files:** `persistence/signals_repo.py` (+`count_statcheck_flagged`), `routers/methods.py` (+`GET
  /methods/statcheck/summary`); `persistence/tags_repo.py` + `routers/papers.py` + `routers/tags.py` (expose tag
  `source`/`import_source`); `00_lib.jsx` (`tagIsImported`/`tagSourceLabel`), `25_detail.jsx`, `10_pdf_layer.jsx`
  (chip + sidebar/Details tag styling), `40_app.jsx` (flagged count + wiring), `styles.css`; `callosum-app.html`;
  `tests/{test_tags,test_statcheck,test_health}.py`; help corpus (tags + statcheck sections).
- **What:** (1) a **⚠ N flagged** chip in the Library header (when the inc-97 batch run flagged any papers) that
  jumps to the flagged-papers filter — a more prominent door to a feature previously only in Settings. (2) Tags
  from different sources (imported Crossref/OpenAlex/Zotero keywords vs the ones you typed) are now distinguished
  by a **muted visual style + a source tooltip** instead of an on-screen label — declutters the Details pane.
- **Why:** user request — surface the library-wide statcheck result more visibly, and "use aesthetic means of
  differentiating tags from different sources to avoid cluttering up the details view."
- **Scope:** both are read-only projections of already-persisted facts (inc-97 signals; inc-73 `import_source`) —
  **no migration, no egress, no LLM, no new dependency.** The tag `source` field is additive (default null).
  pytest **411** (+1 `test_tag_source_exposed_on_responses`; statcheck-summary assertion folded into an existing
  test); `ruff` clean. Principles gate: chip = a more prominent path to a *filter* (no rank/verdict; no-accusation
  boundary holds); tag styling = provenance made visible (inspectability).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `count_statcheck_flagged` +
  the `/methods/statcheck/summary` route + the tag `source` plumbing + the two CSS blocks.

## 2026-06-21 — Increment 99: tests derive the Alembic head, not a hardcoded revision

- **Files:** `tests/api_helpers.py` (new `alembic_head()`), `tests/test_health.py`, `tests/test_startup_migration.py`.
- **What:** added `alembic_head()` (reads the head from the migration scripts) and repointed the two test files'
  head assertions to it, replacing hardcoded `"00NN_…"` revision constants.
- **Why:** a migration that bumps the head used to require editing those constants, and a missed edit only failed
  on the *full* suite (bit inc 91 + inc 98). Now a new migration needs zero test edits for the head.
- **Scope:** tests-only — no app code, no migration, no behavior change. pytest **410** unchanged; `ruff` clean.
- **Revert:** restore the three test files (re-hardcode the head constant).

## 2026-06-21 — Increment 98: double-click-to-open fix + watched library folders

- **Files:** `10_pdf_layer.jsx` (double-click always opens + the "Watched folders…" menu label); NEW
  `persistence/watched_repo.py` + `alembic/versions/0014_watched_folders.py` + `schema.py` (watched_folders table);
  `routers/library.py` (register-on-scan + watched endpoints + rescan worker + shared `_process_scan_result`);
  `27_scan.jsx` (Watched-folders modal), `40_app.jsx` (auto-rescan on launch + toggle), `35_settings.jsx`
  (toggle); `callosum-app.html`; `tests/{test_watched_folders,test_health,test_persistence_core}.py`; help corpus;
  backlog; the audit.
- **What:** (A) **bug** — double-clicking a paper's title selected the word instead of opening (inc-82 guard);
  double-click now always opens. (B) **feature** — Zotero/Mendeley-style **watched folders**: scanning a folder
  watches it, and watched folders are re-scanned automatically on launch (+ a manual "Re-scan all") so new PDFs
  appear without re-adding; manage them in "+ Add → Watched folders…".
- **Why:** the user reported the double-click regression and asked for real folder-watching.
- **Scope:** migration **0014** (additive/guarded); reuses the inc-87 scan (content-dedup → no dupes); only egress
  is Crossref (not the Gemini gate); **no live OS file-watcher** (on-launch + manual). pytest **410** (+2);
  `ruff` clean; audit PASS. Server-side folder read now persisted + auto-read → deployment-gate note extended.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `watched_repo.py` + the
  watched endpoints + the 0014 table + the auto-rescan effect (and restore the inc-82 double-click guard).

## 2026-06-21 — Increment 97: statcheck as a library-wide lens

- **Files:** NEW `app/backend/persistence/signals_repo.py`; `repository.py` (`signal` filter + `SIGNAL_FILTERS` +
  `list_live_paper_ids`), `routers/methods.py` (batch endpoints + worker), `routers/papers.py` (`signal` param),
  `api/app.py` (JobStore); frontend `35_settings.jsx` (`StatcheckSettings`), `40_app.jsx` (`librarySignalFilter`
  view + wiring), `10_pdf_layer.jsx` (banner); `callosum-app.html`; `tests/{test_statcheck,test_health}.py`; help
  corpus; backlog; the audit.
- **What:** a batch **Check all papers** (Settings) persists each paper's statcheck summary to
  `open_science_signals`, and a library **filter** shows only papers with reporting inconsistencies (reached via
  "Show flagged papers" + a banner). The inc-95 per-paper check is unchanged.
- **Why:** the patter's carrot — turn statcheck into whole-library triage.
- **Scope:** a **filter, never a rank/score or a "bad papers" list** (Principles gate run). No migration (the
  table existed since 0001), no egress, no LLM, no new dependency. pytest **408** (+3); `ruff` clean; audit PASS.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `signals_repo.py` + the batch
  endpoints + the `signal` filter + the Settings section + the `librarySignalFilter` view.

## 2026-06-21 — Increment 96: sidebar Tags browser + Details "More → + add field"

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (`TagsPanel` + Sidebar), `40_app.jsx` (`tagRefresh` + wiring),
  `20_synthesis.jsx` + `25_detail.jsx` (`onTagsChanged`; `AddFieldRow` + always-on More), `styles.css`;
  `callosum-app.html`; help corpus.
- **What:** (1) a sidebar **Tags** browser (every tag + count → click to filter the library; live-refreshed on
  per-paper tag edits); (2) a **"+ add field"** control in the Details **More** section (add an arbitrary CSL
  field by hand, via the inc-49 validated `csl` patch).
- **Why:** the patter's two chores — make the tag vocabulary browsable (it was per-paper only), and complete the
  inc-49 "More add-field" deferral (reference-manager parity).
- **Scope:** **frontend-only** (both reuse tested endpoints — `GET /tags`, the `csl` patch); no migration, no
  egress, no new endpoint. pytest **405** unchanged; `ruff` clean.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `TagsPanel` + the
  `tagRefresh`/`onTagsChanged` wiring + `AddFieldRow`.

## 2026-06-21 — Increment 95: statcheck — deterministic statistics-reporting signal

- **Files:** NEW `app/backend/methods/{__init__,statcheck}.py`, NEW `app/backend/api/routers/methods.py`;
  `api/app.py` (register), `requirements.txt` (scipy explicit); frontend `25_detail.jsx` (`StatcheckRow`) +
  `styles.css`; `callosum-app.html`; `tests/{test_statcheck,test_health}.py`; help corpus; backlog; the audit.
- **What:** a Details-pane **"Check statistics"** action that recomputes reported APA NHST p-values (t/F/r/χ²/z)
  from the paper's extracted text and flags reported-vs-computed disagreements (consistent / inconsistent /
  decision-error), with rounding + one-tailed tolerance, per-test rows + counts (no composite score), a
  non-accusatory caveat, and route-to-page. Deterministic, local, no LLM.
- **Why:** the patter's carrot; Track A's v1 — the project's verification ethos on the Methods side.
- **Scope:** `GET /papers/{id}/statcheck` (sync, read-only); `scipy` made explicit (already transitive); no
  migration, no egress, no persistence (deferred to the findings subsystem). pytest **405** (+10); `ruff` clean;
  audit PASS. Principles gate run (Example 3 / value A6; no-accusation veto honored).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `methods/statcheck.py` +
  `routers/methods.py` + the `StatcheckRow` + the scipy line.

## 2026-06-21 — Increment 94: library-header "+ Add ▾" menu + persistent/descending Sort

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (`AddMenu` + Sort options), `app/frontend/js/40_app.jsx` (persist
  `librarySort`), `app/frontend/styles.css` (`.add-menu*`), `app/backend/persistence/repository.py`
  (`title_desc`/`author_desc` sort keys), `callosum-app.html`, `tests/test_papers.py` (+2 sort assertions).
- **What:** (1) folded the header's Scan folder + Import into one **"+ Add ▾"** dropdown (6 header actions → 5);
  (2) the library **Sort** choice now persists across reloads (localStorage) and offers **Title/Author (Z–A)**.
- **Why:** the patter's two chores — declutter the header I flagged last round + remove the sort-resets papercut.
- **Scope:** frontend-only bar one backend allowlist line; no migration/egress/endpoint. pytest **395** unchanged;
  `ruff` clean. Help corpus unchanged (control relocation / sort options aren't described there).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `AddMenu` + the
  `title_desc`/`author_desc` keys + the localStorage persistence.

## 2026-06-21 — Increment 93: BibTeX / RIS / CSL-JSON import

- **Files:** NEW `app/backend/metadata/citation_import.py`, NEW `app/frontend/js/28_import.jsx`;
  `routers/library.py` (import endpoint + worker), `api/app.py` (JobStore), `10_pdf_layer.jsx` (Import button),
  `40_app.jsx` (wiring); `callosum-app.html`; `tests/{test_citation_import,test_health}.py`; help corpus; backlog;
  the security audit.
- **What:** import a BibTeX / RIS / CSL-JSON file → parse (hand-rolled, no new dep) → dedup → create metadata-only
  library papers → embed. The inverse of inc-70 export; reference-manager-first parity (also covers
  Mendeley/EndNote, which export these). An **Import** button in the library header opens a file-picker modal.
- **Why:** the patter's carrot; the only importer was Zotero.
- **Scope:** **entirely local — no egress** (the file is authoritative; no Crossref/Gemini), no multipart/upload
  surface (browser POSTs the file text as JSON), no new dependency, no migration. pytest **395** (+9); `ruff` clean;
  audit PASS. Completes the inc 91–93 patter.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `citation_import.py` +
  `28_import.jsx` + the `/library/import` endpoint + JobStore + the Import button.

## 2026-06-21 — Increment 92: un-dismiss for My-Publications missing works

- **Files:** `persistence/profile_repo.py` (`undismiss_work`), `clustering/my_publications.py`
  (`_dashboard_dismissed_works` + `build_dashboard`), `routers/my_publications.py` (`dismissed_works` field +
  `/works/undismiss` endpoint); frontend `31_mypubs_dashboard.jsx`; `callosum-app.html`;
  `tests/{test_my_publications,test_health}.py`; docs + backlog.
- **What:** completes inc-85's missing-works review queue with an **undo** for Dismiss — the dashboard now shows a
  "Previously dismissed (N)" section, and **Restore** sends a work back to the review queue (`POST
  /my-publications/works/undismiss`).
- **Why:** chore 2 of the patter; the inc-85 deferred follow-on (mirrors inc-67's un-dismiss-duplicates).
- **Scope:** pure `profile.dismissed_work_dois` JSON edit — no migration, no egress (dashboard stays cache-only).
  pytest **386** (+1); `ruff` clean.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `undismiss_work` +
  `dismissed_works` + the `/works/undismiss` endpoint + the dashboard section.

## 2026-06-21 — Increment 91: filter the library by type (+ prerequisite module splits)

- **Files:** NEW `app/backend/persistence/annotations_repo.py`, NEW `app/backend/api/routers/paper_files.py`;
  `repository.py`, `routers/papers.py`, `routers/annotations.py`, `api/app.py`; frontend `40_app.jsx`,
  `10_pdf_layer.jsx`, `styles.css`; `callosum-app.html`; `tests/{test_persistence_core,test_health,test_papers}.py`;
  docs + backlog.
- **What:** (1) **Rule-#1 splits** (behavior-preserving): native-annotations data-access moved out of
  `repository.py` (625→538) → `annotations_repo.py`; PDF file-serving moved out of `papers.py` (600→539) →
  `routers/paper_files.py`. (2) **Feature:** filter the library by CSL item type — a Type dropdown in the header,
  an `item_type` query param on `GET /papers` (bound `WHERE`), and a `GET /papers/item-types` facet endpoint
  (distinct live types + counts).
- **Why:** chore 1 of a "2 chores + 1 carrot" patter; adding the filter surfaced that two core files had drifted
  over the 600-line hard limit, so they were modularized first (rule #1).
- **Scope:** no migration, no egress; the PDF route kept its path so the only new route is `/papers/item-types`.
  pytest **385** (+1); `ruff` clean. Backlog reconciled (Unsorted→inc 80, re-score-wrap→inc 86, filter-by-type→inc 91).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot; the splits can be undone by moving the
  functions back and repointing imports, the feature by dropping the `item_type` param + `list_item_types` + the
  dropdown.

## 2026-06-21 — Increment 90: sidebar header redesign (horizontal logo + larger wordmark)

- **Files:** `app/frontend/styles.css` (`.brand`, `.brand h1`, `.icon-help`, `.icon-gear`), `callosum-app.html`
  (rebuilt).
- **What:** the sidebar brand header became a **horizontal lockup** — logo on the left, a **36px** "Callosum"
  wordmark to its right — with the `⚙` settings button in the **top-left** corner and the `?` help button in the
  **top-right**. Was a vertical stack (logo over a 19px wordmark). _(Two same-day tweaks after the user saw it:
  wordmark trimmed ~10% 40→36px; the buttons split back into the two corners — settings left, help right.)_
- **Why:** user request (a more prominent, conventional brand lockup that reclaims vertical space) — matched to
  the user's mockup + alignment guides.
- **Scope:** **CSS-only** (the JSX already supported it — buttons are absolute, `.brand` is a flex container);
  connection-status logo (inc 47) untouched; no new tokens/hexes (serif wordmark + `--ink`, existing `.icon-*`
  recipes). pytest **384** unchanged (frontend-only). Visual QA delegated to the user; font-size 36px is the
  flagged tunable.
- **Revert:** restore `styles.css` from a `.claude/backups/` snapshot, or revert the 4 rules (`.brand` →
  `flex-direction: column`, `.brand h1` → 19px, `.icon-gear` → `right: 14px`, `.icon-help` → `left: 14px`).

## 2026-06-21 — Increment 89: search across all fields + a search-scope dropdown

- **Files:** `app/backend/persistence/repository.py` (`_search_clause` + `search_field` on `list_papers`),
  `app/backend/api/routers/papers.py` (`search_field` query param); frontend `40_app.jsx` (`librarySearchField`
  state + fetch) + `10_pdf_layer.jsx` (scope dropdown + placeholder); `callosum-app.html`; help corpus;
  `tests/test_papers.py` (+1).
- **What:** the library search now covers **all** stored fields (every author, journal, year, DOI, abstract, the
  whole `csl_json` record) instead of only title + first author, and a **scope dropdown** (All / Title / Author /
  Journal) lets the user narrow it. Fixes the bug where searching a co-author's surname found only first-authored
  papers (6 instead of 40).
- **Why:** user request — non-first authors were unsearchable, and the Detail pane has since gained many fields
  the search never covered.
- **Scope:** no migration, no new endpoint (a query param), no egress; the `field` key is an allowlist (rule #3),
  the pattern is bound. pytest **384** (+1); `ruff` clean.
- **Revert:** restore `repository.py`/`papers.py`/the two JSX chunks from a `.claude/backups/` snapshot, or drop
  the `search_field` param + `_search_clause` (reverting to the old title/first-author `OR`).

## 2026-06-21 — Increment 88: search + sort on one row

- **Files:** `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/styles.css`, `callosum-app.html` (rebuilt).
- **What:** moved the **Sort** control inline to the right of the search box (into the `.searchbar` flex row;
  dropped the `.lib-sort-row` wrapper), reclaiming a vertical row in the library pane.
- **Why:** user request (tighter library header).
- **Scope:** frontend-only — no migration/endpoint/egress. pytest **383** unchanged.
- **Revert:** restore `10_pdf_layer.jsx` + `styles.css` from a `.claude/backups/` snapshot.

## 2026-06-21 — Increment 87: scan / refresh a library folder

- **Files:** `app/backend/pdf_processing/library_scan.py` (NEW), `app/backend/api/routers/library.py` (NEW),
  `app/backend/api/app.py` (router + JobStore); frontend `27_scan.jsx` (NEW) + `10_pdf_layer.jsx` +
  `40_app.jsx` + `styles.css`; `callosum-app.html`; help corpus; tests; the security audit.
- **What:** point Callosum at a folder of PDFs → ingest new ones (extract+chunk+embed, Crossref-enriched), skip
  unchanged (checksum dedup), flag removed (`availability="missing"`). Linked in-place (nothing copied). Async
  `POST/GET /library/scan` + a **Scan folder** button → modal in the library head.
- **Why:** the user's top-priority `callosum_TDL.txt` item — the Zotero-free way to keep a library current.
- **Scope:** no migration (reuses `attachments`); 2 new endpoints; only egress is the Crossref DOI lookup (NOT
  the Gemini gate); the folder is read server-side (gate before any hosted deploy — noted). pytest **383** (+3);
  `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `library_scan.py` + `routers/library.py` +
  the `27_scan.jsx` wiring + the JobStore.

## 2026-06-21 — Increment 86: axis re-score line-wrap fix + button-cleanup resolution

- **Files:** `app/frontend/styles.css`, `.claude/DESIGN.md`, `callosum-app.html` (rebuilt).
- **What:** (1) the axis re-score control row no longer wraps badly — `flex-wrap: nowrap` + a shrinkable Cutoff
  slider keep it on one line at any sidebar width. (2) DESIGN §3 #5 resolved — the remaining divergent buttons
  are intentional distinct variants (folding declined as value-shifting); the safe unification applied was
  tokenizing every `border-radius: 5px` → `var(--radius-sm)` (zero visual change; advances §3 #6).
- **Why:** two UI-polish chores (re-score wrap bug + the .btn-* worklist item).
- **Scope:** frontend-only — no migration/endpoint/egress. pytest **380** unchanged. Visual QA delegated.
- **Revert:** restore `styles.css` from a `.claude/backups/` snapshot.

## 2026-06-21 — Increment 85: My Publications — missing-works review + import

- **Files:** migration `0013_my_publication_dismissed_works.py` + `schema.py` (`profile.dismissed_work_dois`);
  `profile_repo.py` (`dismiss_work`); `clustering/my_publications.py` (`build_dashboard.missing_works`,
  `import_missing_work`, `_add_confirmed_member`); `routers/my_publications.py` (`POST /works/import` +
  `/works/dismiss` + `DashboardResponse.missing_works`); `31_mypubs_dashboard.jsx` + `styles.css`;
  `callosum-app.html`; help corpus; tests; the security audit.
- **What:** the dashboard's indexed-vs-library gap becomes a review queue — OpenAlex works not in your library,
  each with Import (metadata-only, guardrailed to your own indexed works → auto-joins My Pubs) or Dismiss
  (persisted).
- **Why:** the carrot from the user's My-Pubs follow-ups — the 79-indexed vs 40-in-library gap, made actionable.
- **Scope:** migration 0013; 2 new POST endpoints; import reuses the inc-74–76 lane (Crossref DOI lookup, NOT
  the Gemini gate; no PDF/file write). pytest **380** (+3); `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `import_missing_work`/`_dashboard_missing_works`
  + the 2 endpoints + the dashboard section + migration 0013.

## 2026-06-21 — Increment 84: star key publications + scope the AI summary to starred

- **Files:** migration `0012_my_publication_stars.py` + `schema.py` (`profile.starred_paper_ids`); `profile_repo.py`
  (`set_starred`); `routers/my_publications.py` (`POST /star` + `starred_only` on generate); `routers/axes.py`
  (`ClusterPaperResponse.starred`, my-pubs only); `clustering/my_publications.py` (`my_publication_documents(only_paper_ids=)`);
  `15_axes.jsx` (★ toggle) + `31_mypubs_dashboard.jsx` (⭐-only checkbox) + `styles.css`; `callosum-app.html`;
  help corpus; tests.
- **What:** ⭐ star key publications in the My Pubs sidebar card; a "⭐ only" toggle scopes the AI research
  summary to the starred set.
- **Why:** the chore from the user's My-Pubs follow-ups — focus the summary on flagship work.
- **Scope:** migration 0012; one new endpoint (`POST /star`, local) + a `starred_only` body on generate.
  pytest **377** (+2); `ruff` clean; no new egress (the summary path is the inc-81 gated seam).
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `set_starred` + the `/star` endpoint +
  `starred_only` + the `starred` cluster field + the frontend star UI + migration 0012.

## 2026-06-20 — Increment 83: My Publications Part 2 — domain decomposition (Layer 2)

- **Files:** migration `0011_my_publication_domains.py` + `schema.py` (`profile.research_domains`);
  `profile_repo.py`; `integrations/openalex/author.py` (`AuthorWork.cited_by_count` + `fetch_author_works(refresh=)`);
  `app/backend/clustering/my_publications.py` (`decompose_domains` + `_dashboard_domains`);
  `routers/my_publications.py` (2 endpoints + `DashboardResponse.domains`) + `app.py` (JobStore); frontend
  `31_mypubs_dashboard.jsx` + `styles.css`; `callosum-app.html` (rebuilt); help corpus; tests; the audit.
- **What:** a **Research domains** section on the My Pubs dashboard — cluster your confirmed own-papers into
  domains, show **impact-by-domain** (citation sums), and click a domain to re-filter the publications-by-year
  chart. LLM-free local clustering; the only egress is the OpenAlex works refresh (metadata, not the Gemini gate).
- **Why:** the chosen carrot — My Pubs Part 2 Layer 2 (the spec's differentiator).
- **Scope:** migration 0011; 2 new endpoints (1 read-only GET poll + 1 POST decompose job); stored as isolated
  `profile.research_domains` JSON (NOT child cluster_nodes — avoids double-counting the inc-78/79 card badge).
  pytest **375** (+5); `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `decompose_domains`/`_dashboard_domains` +
  the 2 endpoints + the `31_mypubs_dashboard.jsx` domains section + migration 0011.

## 2026-06-20 — Increment 82: library-card tidy + double-click/text-select fix

- **Files:** `app/frontend/js/10_pdf_layer.jsx`, `callosum-app.html` (rebuilt).
- **What:** (1) dropped the "N chunks" chip from library cards (processing-internal, not bibliographic);
  (2) a card's double-click opens the PDF only when it didn't select text (`getSelection().isCollapsed`), so
  double-clicking a title word selects it instead of opening.
- **Why:** two `callosum_TDL.txt` UX chores — cleaner cards + stop double-click-to-open hijacking text selection.
- **Scope:** frontend-only — no migration/endpoint/egress/CSS. pytest **370** unchanged.
- **Revert:** restore the chunks chip + the unconditional `onDoubleClick` in `10_pdf_layer.jsx`.

## 2026-06-20 — Increment 81: My Publications Part 2 — the impact dashboard (Layer 1)

- **Files:** migration `0010_my_publications_summary.py` + `schema.py` (`profile.research_summary`);
  `integrations/openalex/author.py` (enriched `ResolvedAuthor` + cache-only `cached_author`);
  `app/backend/clustering/my_publications.py` (`build_dashboard` + `my_publication_documents`);
  `integrations/gemini/research_summary.py` + `app/backend/llm/egress.py` (egress seam) + `app.py` wiring;
  `app/backend/api/routers/my_publications.py` (3 endpoints); `profile_repo.py`; frontend
  `31_mypubs_dashboard.jsx` + `40_app.jsx`/`30_viewer.jsx`/`15_axes.jsx`/`10_pdf_layer.jsx`/`styles.css`;
  `callosum-app.html` (rebuilt); help corpus; tests; the security audit.
- **What:** a 📊 impact **dashboard tab** for the My Publications axis — headline OpenAlex metrics, a
  publications-by-year SVG chart (+ citations-by-year), the indexed-vs-library gap, and an editable AI research
  summary. The dashboard read is **cache-only / egress-free** (gated on a prior Settings→Refresh); the AI
  summary is the only egress (library text → the `CALLOSUM_ALLOW_DATA_EGRESS` gate at the inc-58 seam; off → 503).
- **Why:** the chosen "carrot" — make the user's own corpus a first-class impact surface (My Pubs Part 2,
  Layer 1; Layers 2–4 deferred).
- **Scope:** migration 0010 (additive); 3 new endpoints (1 read-only GET + generate POST + persist PUT); a new
  egress path (the summary), gated. pytest **370** (+8); `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop the 3 endpoints + `build_dashboard` +
  `research_summary.py` + the `31_mypubs_dashboard.jsx` wiring + migration 0010.

## 2026-06-20 — Increment 80: the "Unsorted" library view (needs-review filter)

- **Files:** `app/backend/persistence/repository.py`, `app/backend/api/routers/papers.py`,
  `app/frontend/js/40_app.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `tests/test_papers.py`,
  `app/backend/help/help_content.md`, `callosum-app.html` (rebuilt).
- **What:** an **Unsorted** toggle in the Library header (+ a clearable banner) that filters to papers whose
  metadata still needs review — raw PDF scaffolds, Crossref-unresolved imports, and papers with no recorded
  source. Backend: a `needs_review` query param on `GET /papers` → `list_papers(needs_review=…)` filters
  `imported_source IN ("pdf-scaffold","crossref-unresolved") OR IS NULL` (local allowlist, bound-param). A view
  like Trash (clears axis/tag filters) but keeps checkbox-select on for bulk re-resolve/export/delete.
- **Why:** surface unresolved/under-catalogued papers instead of letting them disappear into the library
  ("silence is not a certificate"); the chosen "UNSORTED cluster" chore.
- **Scope:** read-only query param — no migration, no new endpoint, no egress. pytest **362** (+1); `ruff` clean.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `needs_review` from `list_papers` + the router
  and the `libraryNeedsReview` wiring from the two frontend chunks.

## 2026-06-20 — Increment 79: count badge subtracts hidden uncertain papers

- **Files:** `app/backend/clustering/axis_assignments.py`, `app/backend/api/routers/axes.py`,
  `app/frontend/js/15_axes.jsx`, `tests/test_axes.py`, `callosum-app.html` (rebuilt).
- **What:** when an axis is in the assigned/manual-only view (inc-51 👁 toggle / inc-77 Settings default), its
  count badge now shows the **visible** count (total − uncertain) instead of the full assignment count, with a
  tooltip noting how many uncertain are hidden. `axis_score_state(cutoff=…)` returns a new `uncertain_count`
  (scored `confidence < cutoff`); `AxisResponse.uncertain_count` exposes it; the frontend subtracts it per the
  per-axis view state.
- **Why:** the badge number should match what the list actually shows once uncertain papers are hidden (user
  nomination).
- **Scope:** additive read-only field on the existing `/axes` response — no migration, no new endpoint, no egress.
  pytest **361** (assertions added to two existing axis tests, count unchanged); `ruff` clean.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `uncertain_count` from `AxisResponse` +
  `axis_score_state` and revert the badge to `axis.assignment_count`.

> Also committed earlier this session as small **unnumbered UI chores**: a consistent indeterminate
> `ProgressBar` wired into the long async jobs (axis score / suggest / duplicates / synthesis / acquire-OA /
> wanted re-check / my-pubs refresh); moving the My Publications card below the filter/sort controls; bumping
> inter-axis-card spacing 2→5px; and the CI Node-24 action bumps (checkout@v5 / setup-python@v6).

## 2026-06-20 — CI fix: pin ruff + the web stack + apply ruff format (CI now green)

- **Result:** both CI jobs **green** — `lint-and-test` ✓ + `e2e-smoke` ✓ (browser smoke, 0 console errors).
- **Two unpinned-dep drifts**, both first exposed once the billing lock was cleared (CI had never run before):
  (1) **ruff** resolved to 0.15.18 vs local 0.9.6 → I001 import-ordering + format diffs; (2) **fastapi/starlette**
  resolved to 0.138/1.x vs local 0.115.8/0.45.3, and **starlette 1.0 restructured routing** → the route-surface
  introspection test (`test_api_exposes_only_read_only_get_routes`) saw only `/` (endpoints worked; 360 passed).
- **Fix:** pin `ruff==0.9.6` (`requirements-dev.txt`) + `ruff format .` (12 files, cosmetic); pin
  `fastapi==0.115.8` + `starlette==0.45.3` (`requirements.txt`). CI now installs the tested versions.
- **Non-blocking:** a Node-20 deprecation **warning** on `actions/checkout@v4` + `actions/setup-python@v5`
  (GitHub runs them on Node 24) — bump to checkout@v5/setup-python@v6 whenever; not a failure.
- **Follow-up:** a full lockfile (uv) / exact pins of the rest of the toolchain is the deferred *harness
  hardening* track; this pinned only the two tools that broke.
- **Revert:** restore from a `.claude/backups/` snapshot.

## 2026-06-20 — Increment 78: My Publications — the auto-axis of your own papers (Part 1)

- **What:** a pinned, OpenAlex-resolved, **LLM-free** axis of the researcher's own papers. Set a **profile**
  (name / published-name variants / ORCID) in Settings → **Refresh** resolves via OpenAlex (ORCID-first) →
  DOI/ORCID matches become **confirmed members**, name-only matches become **candidates** you ✓ confirm / ✕
  reject (**persisted** — a rejection never re-appears, a confirmation survives re-matching). An **import hook**
  adds new matching papers incrementally; the pinned 📄 card reuses `AxisItem` branched on the new `axes.kind`.
- **Why:** the satisfying personal feature — your own corpus as a first-class lens; the foundation for a future
  impact dashboard (Part 2, deferred).
- **Files:** migration **0009** (`axes.kind` + `profile` + `my_publication_decisions`) + `schema.py`;
  `integrations/openalex/author.py` (`OpenAlexAuthorClient`, fail-closed + cached); `persistence/profile_repo.py`;
  `clustering/my_publications.py` (resolver + cache-based import hook); `metadata/enrichment.py` (the guarded
  hook); `routers/my_publications.py` + `app.py` wiring + `AxisResponse.kind`; frontend `35_settings.jsx`
  (profile section), `15_axes.jsx` (pinned card + kind branch + ✓/× → `/decide`), `40_app.jsx`, `00_lib.jsx`
  (`apiPut`), `styles.css`; rebuilt `callosum-app.html`.
- **Principles / egress:** facts-vs-candidates + confirm-and-learn; **no model tokens**; OpenAlex author lookup
  is **metadata egress (public identifiers), NOT the Gemini gate**; strictly additive (the import hook is a
  guarded no-op when unused). Audit `.claude/security-audits/2026-06-20_my-publications.md` — **PASS**.
- **Verify:** `ruff` clean; `pytest` **361 passed, 1 skipped** (+14); migration head **0009**; route surface
  +`/my-publications/*`. Notes: `INCREMENT-78-NOTES.md`. Live OpenAlex resolution delegated to the user (needs
  their name/ORCID).
- **NEXT:** Part 2 — the impact dashboard tab (charts / citation graph / prospection), deferred.
- **Revert:** restore from a `.claude/backups/` snapshot; no down-migration (0009 is additive).

## 2026-06-20 — Increment 77: hide uncertain axis papers by default (Settings)

- **What:** the inc-51 per-axis 👁 hide-uncertain view can now be the **default** via a new **Settings → Axes**
  toggle; axis cards start in the assigned/manual-only view and surface uncertain papers on demand. Persisted to
  `localStorage["callosum.hideUncertainDefault"]` (mirrors the theme pattern).
- **Why:** a backlog quick-win — declutter the axes panel by default for users who treat uncertain papers as noise.
- **Files:** `35_settings.jsx` (the toggle row), `40_app.jsx` (state + persist; threaded to Sidebar + the
  SettingsModal), `10_pdf_layer.jsx` (Sidebar pass-through), `15_axes.jsx` (AxisItem initial `hideUncertain` reads
  the default; AxesPanel keys each card on it so a toggle remounts them live), `styles.css` (`.settings-sub`);
  rebuilt `callosum-app.html`.
- **Verify:** frontend-only; `pytest` **347** unchanged; **visual check delegated to the user** (no in-repo
  browser this session) — Settings → Axes → toggle on; expanded cards hide uncertain; persists across reload.
- **Revert:** restore from a `.claude/backups/` snapshot.

## 2026-06-20 — Backlog split: open vs closed

- **What:** split `INCREMENT-BACKLOG.md` so the open queue stays scannable — shipped/closed `[x]` items moved
  to a new **`INCREMENT-BACKLOG-DONE.md`** archive (what landed + which increment); `INCREMENT-BACKLOG.md` now
  holds **open `[ ]` items only** (+ the guiding-principle intro + a pointer to the archive). Also refreshed a
  few stale lines (Crossref-subject tags shipped inc 73; Track-D acquisition largely shipped inc 74–76).
- **Why:** a session no longer has to read past ~250 lines of finished work to see what remains (user's idea).
- **Files:** `INCREMENT-BACKLOG.md` (rewritten open-only), `INCREMENT-BACKLOG-DONE.md` (new), `docs/README.md`
  + `CLAUDE.md` reference table (both repointed).
- **Verify:** docs-only; no code/test change.
- **Revert:** restore from a `.claude/backups/` snapshot; the prior combined backlog is in Dropbox history.

## 2026-06-20 — Phase 8: future-tracks watched-inbox auto-rule (+ folded 2 pending specs)

- **What:** the release-readiness arc's final phase. A **session-kickoff watch rule** (CLAUDE.md Session kickoff
  #9) makes a fresh session check `.claude/docs/future-tracks-import/` on its own — anything beyond its README +
  the README's **Parked** list is unprocessed input to surface to the user and handle per the inbox README
  (genuine track → gate-frame → fold into the backlog + `future-tracks/` index → **move**; meta directive →
  action + remove; counsel-gated → leave **parked**, never published).
- **Why:** the inbox existed but relied on the user pointing the assistant at it; now a fresh session notices a
  non-empty inbox without being told.
- **Ran the rule once:** folded the two pending specs — **PUBLISHERS (where-to-submit METHODS tool)** + its
  **first-use choice gate** — into `INCREMENT-BACKLOG.md` + the `future-tracks/README.md` index, and **moved**
  them from the inbox to `future-tracks/`. Both are principles-aligned (facts-not-verdicts, no composite score,
  **no "predatory" label** [A-A no-accusation], local-only / never-transmitted, equity first-class) and carried
  explicit "capture into the backlog" dispositions. The counsel-gated **acquisitiondeferred** spec stays
  **parked** in the gitignored inbox (named in the README's Parked list — never folded or published).
- **Files:** `.claude/CLAUDE.md` (Session kickoff #9 + directory-layout note), `future-tracks-import/README.md`
  (rule-landed + Parked list; local-only), `docs/README.md`, `future-tracks/README.md` (+2 index rows),
  `INCREMENT-BACKLOG.md` (+1 entry); moved 2 specs; swept a stray `*.tmp.*` inbox orphan.
- **Verify:** docs-only — no code/test/schema change (pytest unaffected at 347). The inbox now sits at its README
  + the parked spec. **This closes the release-readiness arc (Phases 1–8).**
- **Revert:** restore from a `.claude/backups/` snapshot; move the 2 specs back to the inbox to un-fold.

## 2026-06-20 — Increment 76: literature acquisition — the wanted list + OA re-check + coverage (C)

- **What:** completes the acquisition arc's *track* loop — a persistent **wanted list** of papers you want an
  OA copy of (unified: auto-includes PDF-less library papers AND external papers you add by DOI), a manual
  async **Re-check OA** job that runs the resolver cascade over the list and **auto-acquires** any authorized
  copy, and a **coverage readout**. Opened from a **Wanted** button in the library head.
- **Why:** turns the per-paper acquire into a standing "fill my gaps" workflow + a way to watch for copies of
  papers you don't own yet (preprints get published, embargoes lift, repositories deposit).
- **How:** `wanted_items` table (migration **0008**; `paper_id` set = library, NULL = external w/ doi/pmid/title).
  The re-check service `acquisition/wanted.py::run_recheck` (kept out of the router → directly testable) resolves
  each open want through the **same `ResolverRegistry`** and on a hit downloads + imports — library wants fill
  the paper; external wants `create_paper` then `import_oa_pdf` (enriches from Crossref). OA-only is **free +
  structural** (registry-only → no non-OA/arbitrary-URL path, test-pinned); external wants need a doi/pmid
  (title-only → skipped `needs-id`, never a fuzzy mint); per-item errors never abort a run; a logged per-run cap.
- **Files:** `persistence/wanted_repo.py` + `schema.py`/migration 0008; `acquisition/wanted.py`;
  `routers/wanted.py` (`GET/POST/DELETE /wanted`, `POST /wanted/sync-library`, `GET /wanted/coverage`, async
  `POST /wanted/recheck` + poll) + `app.py` wiring (`wanted_jobs` + an `acquire_registry` test seam);
  `26_wanted.jsx` + a **Wanted** button in `10_pdf_layer.jsx` + `40_app.jsx`; rebuilt `callosum-app.html`.
- **Gates:** security audit `.claude/security-audits/2026-06-20_wanted-list.md` — **PASS** (OA-only structural,
  input validation, no fuzzy-mint, bulk-fetch politeness, bound-param, no new dep, no new egress).
- **Verify:** `ruff` clean; `pytest` **347 passed, 1 skipped** (+13); migration head `0008`; route surface
  extended with `/wanted*`. Notes: `INCREMENT-76-NOTES.md`. **Completes Acquisition A/B/C.**
- **Revert:** restore touched files from a `.claude/backups/` snapshot; no down-migration by design (the
  `wanted_items` table is additive + inert if unused).

## 2026-06-20 — Increment 75: literature acquisition — fan out the resolver cascade (B)

- **What:** the inc-74 OA lane gains a **7-source resolver cascade** (gold→green→preprint, first authorized
  copy wins) behind the unchanged `OaLocation` seam: OpenAlex (primary) → **DOAJ** → **Europe PMC** →
  **Crossref-OA** → **CORE** → **arXiv** → **bioRxiv/medRxiv** → **OSF/PsyArXiv**. Now a PDF-less paper has many
  authorized OA sources tried in turn, not just OpenAlex.
- **Why:** OpenAlex misses copies (new preprints, DOAJ gold, repository green, Europe PMC OA); the cascade
  fills the gaps while keeping OA judgment with the databases.
- **How (additive to a proven seam):** each source = the OpenAlex-adapter shape — an `integrations/<source>/`
  client (injectable `fetcher` Protocol, `external_api_cache` under a distinct provider, `lookup_oa →
  OaLocation|None`, fail-closed, https-only) + a thin `resolvers/<source>_resolver.py` + one `register(...)` in
  `build_default_registry`. The `resolve()` loop is untouched. OA-ness stays each database's assertion — a
  source with no honest https direct-PDF returns None (DOAJ needs a real PDF link; Europe PMC needs
  `isOpenAccess=Y`; Crossref-OA needs a registered license → CC=gold else bronze; never a guess).
- **Files:** `integrations/api_cache.py` (shared cache helper) + `integrations/{doaj,europepmc,core,arxiv,
  biorxiv,osf}/` + `integrations/crossref/oa.py`; `app/backend/acquisition/resolvers/{doaj,europepmc,crossref,
  core,arxiv,biorxiv,osf}_resolver.py` + the `build_default_registry` cascade; help corpus +
  "Acquiring an open-access copy" section.
- **Secrets:** **CORE** uses `CALLOSUM_CORE_API_KEY` (env only; Bearer header, never in a URL/cache/log;
  **absent → silent no-op**). The key value is in no file/code/doc/git. (Rotate it after testing — pasted in chat.)
- **No new dependency:** arXiv's Atom id is read with a targeted regex, **not** a stdlib XML parser (XXE/entity
  surface on untrusted input, rule #4). No new endpoint, no migration (head stays 0007), no frontend change.
- **Gates:** security audit `.claude/security-audits/2026-06-20_oa-acquisition-b.md` — **PASS** (per-source
  OA-assertion delegation, https/SSRF, CORE key handling, fail-closed, no new dep).
- **Verify:** `ruff` clean; `pytest` **334 passed, 1 skipped** (+31 hermetic per-source + cascade + structural).
  Notes: `INCREMENT-75-NOTES.md`.
- **NEXT:** Increment C (wanted-list + an OA-DB-only re-check job + a coverage readout).
- **Revert:** restore touched files from a `.claude/backups/` snapshot; no migration to undo.

## 2026-06-20 — Increment 74: literature acquisition — the legally-clear open-access lane (A)

- **What:** the keystone of the *track → acquire → read → interrogate → cite* ecosystem (**clean lane only** —
  the legally-ambiguous lane is deferred/counsel-gated, not built or scaffolded). A per-paper **"Acquire OA
  copy"** button on a PDF-less paper resolves it (DOI/PMID/title) → an **OpenAlex-asserted authorized
  open-access** PDF → downloads + validates → imports locally as a **`managed`** attachment named per the
  library convention (`Authors - Year - Venue.pdf`) + labeled OA color/version/source (bronze flagged unstable).
- **Why:** turns callosum from a reference manager into a full acquire→cite ecosystem, while keeping OA
  judgment with the databases (realizes the A8 access-equity value; honors the no-paywall-circumvention veto).
- **Bright lines enforced structurally** (not by convention): the `OaLocation` seam — required OA color (**no
  "closed" member**), the downloader takes an `OaLocation` not a URL → **no arbitrary/non-OA fetch is
  expressible**; OA-ness delegated to OpenAlex; fetched copies local-only. Same idea as the inc-58 egress gate.
- **Files:** `app/backend/acquisition/{registry,fetch}.py` + `resolvers/openalex_resolver.py`;
  `integrations/openalex/adapter.py`; `app/backend/pdf_processing/ingest.py` (extracted reusable
  `attach_pdf_to_paper`, behavior-preserving); migration **0007** + `schema.py` +
  `persistence/acquisition_repo.py` + `AttachmentResponse` OA fields; `app/backend/api/routers/acquisition.py`
  (async `POST /papers/{id}/acquire-oa` + `GET /papers/acquire-oa/{job_id}`, included before `papers.router`) +
  `app.py` wiring (`openalex_client` + `acquire_jobs`); `25_detail.jsx` button + OA chips + `styles.css` +
  rebuilt `callosum-app.html`. New env: `CALLOSUM_OPENALEX_MAILTO` (polite pool), `CALLOSUM_LIBRARY_DIR`
  (managed dir, default `library/`).
- **Gates:** Principles + values gate — clean pass. Security audit
  `.claude/security-audits/2026-06-20_oa-acquisition.md` — **PASS** (SSRF guard, 80 MiB size cap, PDF
  magic + PyMuPDF validation, structural OA-only, no new dependency, polite-pool/cache).
- **Verify:** `ruff` clean; `pytest` **303 passed, 1 skipped** (+24); e2e smoke green; migration head `0007`.
  Notes: `INCREMENT-74-NOTES.md`.
- **Help-docs:** ⚠️ the served help corpus does **not** yet cover acquisition — add an "Acquiring open-access
  copies" section (this entry sits above the `HELP-DOCS-SYNCED` marker → flagged for review).
- **NEXT:** Increment B (resolver cascade — DOAJ/CORE/arXiv·bioRxiv·PsyArXiv·PMC/Crossref) then C (wanted-list
  + OA-only re-check + coverage).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot; no down-migration by design — the
  0007 columns are additive nullable and inert if unused.

## 2026-06-20 — Phase 7: published to GitHub + follow-up (inbox 3rd batch, README badges)

- **PUBLISHED:** `https://github.com/cliffworkman/callosum` (public, AGPL-3.0), initial commit `58c4ce3`,
  307 files, **verified secret-free** (the `git init` secret-gate caught + fixed a `.gitignore` inline-comment
  bug that had leaked `callosum_TDL.txt` into staging; remote-tree re-check clean). Push needed two fixes: the
  `workflow` token scope (`gh auth refresh -s workflow`) and the git credential helper (`gh auth setup-git` →
  push as the active `cliffworkman` account instead of the cached personal account). **CI is configured but
  blocked by a GitHub account billing lock** ("account locked due to a billing issue") — not a code/config
  issue; resolve at github.com/settings/billing, then re-run.
- **Local prep:** `LICENSE` (verbatim AGPL-3.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/`
  (`workflows/ci.yml` = ruff + pytest + the opt-in e2e job; PR template; bug/feature issue templates;
  `CODEOWNERS` → `@cliffworkman`), `.gitignore` finalized (+ `callosum_TDL.txt`).
- **Inbox (3rd batch) processed:** filed two **process/dev-infra roadmaps** → `future-tracks/`
  (`harnesshardening.md` = post-git hardening — uv / pre-commit / CI-ratchet / `staged-harnesses/` registry /
  branch protection / repo furniture; `readmescopeaudit.md` = expand the README into a full contributor front
  door) + indexed them + captured both in a new backlog section *Dev-infra & repo hardening (post-git)*.
  Removed the re-synced already-actioned `approachavoidanceharness.md` dupe again. Inbox empty.
- **README badges:** added CI-status + AGPL-3.0 license badges.
- **Verify:** repo live + public; remote tree secret-clean; follow-up commit pushed.

## 2026-06-20 — Phase 6 (cont.): scrubbed key values out of the backup zips (user-requested)

- Removed the key-bearing entry `.claude/GEMINI_API.txt` from all **16** affected backup zips via a **validated
  atomic rewrite** (each temp zip `testzip`-checked before `os.replace`, with a lock retry; 0 corrupt). Re-scan of
  all **43** zips' contents = **0 key-pattern matches**. With the `.gitignore` rules + the `git check-ignore`
  proof, the backups now carry no secrets and cannot reach GitHub.
- **Key rotation** (the 4 keys still in Dropbox history) was added to `INCREMENT-BACKLOG.md` → *Security follow-up*
  as **non-blocking**, at the user's request.
- **Files:** the 16 `.claude/backups/callosum_claudecode_inc{43–48,64–73}.zip` (gitignored; never committed).
- **Verify:** content re-scan = 0 matches; all 43 zips pass `testzip`.

## 2026-06-20 — Phase 6 (cont.): backups secret exposure verified + .gitignore hardened (user-flagged)

- **User flagged** that `.claude/backups/` zips predate the keys→`.env` move and could carry secrets. Verified:
  scanning zip **contents** found the 4 key values in **16 backup zips** (inc43–48 ×1, inc64–73 ×4) — embedded in
  the **old `.claude/GEMINI_API.txt`** filename (which predated `GEMINI_API_KEYS.md`, so the earlier name-only
  check missed it). **The live tree is clean** (only `.env`).
- **GitHub path neutralized + PROVEN.** `.gitignore` already excluded `.claude/backups/`; hardened further with
  `*.zip`, `*GEMINI_API*` (catches the old filename if Dropbox resurrects it), and `*.key`. A throwaway
  `git init` + **`git check-ignore`** confirmed `.claude/backups/`, every `*.zip`, `.env`, and the key files are
  ignored; the throwaway `.git/` was removed (working tree is not a repo). → **the keys cannot reach GitHub.**
- **Residual (local/Dropbox only):** the keys persist in those 16 local zips + Dropbox version history →
  **key rotation RECOMMENDED** (revoke + reissue in Google AI Studio, update `.env`) as the only way to neutralize
  copies outside git. Recorded in the security audit.
- **Files:** `.gitignore` (`*.zip` / `*GEMINI_API*` / `*.key`); `.claude/security-audits/2026-06-20_pre-github-fullsweep.md`.
- **Verify:** `git check-ignore` PASS for all secret-bearing paths; live-tree sweep clean.

## 2026-06-20 — Phase 6 (cont.): 2nd inbox round + codex doc-refresh accepted

- **Codex doc-refresh reviewed + accepted.** The 7 refreshed `docs/*.md` (architecture, data-contracts,
  product-scope, ux-scope, risk-register, glossary, docs-README) verified accurate against the code — they even
  capture the *contrasted* (product term) vs `contradicted` (storage status) nuance and flag the PyMuPDF-AGPL
  redistribution risk; no overclaiming. (`build-log.md` left as a historical record.)
- **2nd inbox round** (the user dropped more material mid-session): **Research-impact analytics** track folded →
  `future-tracks/` + the index + a Longer-horizon backlog bullet (opt-in, local-first, **commons**; HSR-grade
  consent; Project A = zero-egress instrumentation seam + personal dashboard near-term, Project B = far-future
  gated). The re-synced `approachavoidanceharness.md` (already actioned in the 1st round) was removed again — its
  reappearance is **Dropbox restoring my earlier delete**; if it recurs, delete it from Dropbox so the delete
  propagates. Inbox empty again.
- **Files:** moved `…_researchimpactanalytics.md` → `future-tracks/`; `future-tracks/README.md`;
  `INCREMENT-BACKLOG.md`.
- **Verify:** docs-only; `pytest` unaffected (279 passed, 1 skipped).

## 2026-06-20 — Phase 6 (cont.): stdlib .env auto-loader; archived/refreshed stale planning docs

- **.env auto-loader (functional completion of the keys relocation).** `startup.load_local_env()` (+ pure,
  tested `_parse_dotenv`) populates the process env from a gitignored `.env` for any **unset** key (an exported
  shell var always wins — handy for swapping BYO test keys); called once in `app.py` before the default
  `create_app()`. **Skipped under pytest** (guarded on `"pytest" in sys.modules`) so the suite stays hermetic and
  never ingests a real `.env`. No new dependency (stdlib `KEY=VALUE` parser; `#` comments + quotes handled).
  Tested by `tests/test_env_loader.py` (+4). So `.env` now "just works": set `GOOGLE_API_KEY` there + run.
- **Archived stale planning docs.** `roadmap.md` (stale since ~inc 7) + `backlog-future-tracks.md` (superseded by
  `future-tracks/`) → `.claude/deprecated/`; the reference rows in CLAUDE.md + the INCREMENT-BACKLOG scope note
  were redirected. The 7 still-useful planning docs (architecture / data-contracts / product-scope / ux-scope /
  risk-register / glossary / docs-README) were **refreshed to current reality via `codex exec`, reviewed against
  the code** (same pattern as the Phase-3 README refresh).
- **Files:** `app/backend/api/startup.py` (+ loader), `app/backend/api/app.py` (call it),
  `tests/test_env_loader.py` (new); moved `roadmap.md` + `backlog-future-tracks.md` → `deprecated/`; refreshed
  the 7 `docs/*.md`; `CLAUDE.md` + `INCREMENT-BACKLOG.md` reference updates.
- **Verify:** `ruff` clean; `pytest` → **279 passed, 1 skipped** (+4 env-loader).

## 2026-06-20 — Phase 6: Gemini API keys relocated to .env (security gate)

- **What:** moved the **4** Gemini keys (newer `AQ.*` format) from `.claude/GEMINI_API_KEYS.md` → a **gitignored
  `.env`** (`GOOGLE_API_KEY` + 3 alternates for BYO-key testing); **deleted** the md; hardened `.gitignore` to
  exclude `.env` / `.env.*` / the md + `.ruff_cache/` / `.playwright-mcp/` / `*.tmp.*` / `library/` +
  `.claude/{backups,deprecated,plans}`.
- **How (no leak):** a masking Python script did the read→write — **no key value was ever read or printed** to
  the transcript (only counts + masked structure). Whole-tree secret sweep (`AQ.*` / `AIza*` patterns) = **clean**
  (only `.env`, which is gitignored; binary backup zips are skipped by grep + are gitignored).
- **Note:** the app reads `GOOGLE_API_KEY` from the **process env** and does **not** auto-load `.env` yet — so the
  run workflow is unchanged (set the env var before `uvicorn`). A tiny **stdlib `.env` loader** (no new dep,
  shell-override-preserving) is offered as the functional follow-up. Keys still live in local backup zips +
  Dropbox history (not git); optional key **rotation** is the user's call.
- **Files:** **new** `.env` (gitignored); `.gitignore`; **deleted** `.claude/GEMINI_API_KEYS.md`.
- **Why:** the security audit's hard pre-commit gate; enables the BYO-key model.

## 2026-06-20 — Release-readiness arc, Phase 6 (start): processed the future-tracks inbox + TDL; wired the values layer

Collaborative `.claude/` phase (user chose: process the inbox/TDL now + a full per-item inventory). Docs-only.

- **Values layer wired in.** Actioned the inbox's `…_approachavoidanceharness.md` directive (a meta task, not a
  track): **`APPROACH-AVOIDANCE.md`** (the value substrate beneath PRINCIPLES) is now the Principles gate's
  **deeper, *conditional* layer** — consulted only for novel / value-level / future-track changes (derive the
  check from the value; veto-level hard boundaries = no paywall circumvention / no reaching into other tools'
  stores / no accusation of individuals; the confirmed/extended/emergent/divergent drift typology). CLAUDE.md
  gate section + rule #9 + kickoff #8 + reference table + directory layout updated; explicitly **not** a second
  mandatory gate. The harness directive was removed from the inbox (actioned).
- **Equity & integrity signals track folded in.** Moved `…_equityintegritysignals.md` → `future-tracks/`; added
  it to the `future-tracks/` index + a "Longer-horizon" backlog bullet (HACKADEMIA-derived, **repointed to
  non-accusatory inspectable signals**; OpenAlex + findings-subsystem dependent; gated by the A-A no-accusation
  veto). Inbox now empty; added `future-tracks-import/README.md` documenting the inbox convention.
- **`callosum_TDL.txt` folded.** ~12 net-new near-term UX items captured into a new backlog section (watch
  library folders; UNSORTED/DOI-failed cluster; filter-by-type; card tidy-ups; viewer page-views; reading mode;
  **Gemini API key in Settings = BYO-key**; account/login + publishing name; hide-uncertain-by-default; progress
  bars; re-score wrap fix), deduped against shipped increments.
- **Files:** `.claude/CLAUDE.md`; `.claude/docs/INCREMENT-BACKLOG.md`; `.claude/docs/future-tracks/README.md` +
  the moved-in equity doc; **new** `.claude/docs/future-tracks-import/README.md`.
- **Still TODO this phase:** the full per-item `.claude/` inventory (user ruling on each) + the
  **Gemini-keys → `.env`** relocation (security gate before any commit).
- **Why:** the user pre-loaded the watched inbox + a TDL; integrate so the plan captures everything, and wire
  the values layer the harness doc requested. **Verify:** docs-only; `pytest` unaffected (275/1).

## 2026-06-20 — Release-readiness arc, Phase 5.5 (README coverage + planned→backlog reconciliation)

User-requested docs sweep (docs-only; no code touched).

- **Hygiene:** removed 3 atomic-write orphans (`app/backend/api/routers/*.tmp.26380.*`) + emptied the stray
  `.playwright-mcp/` MCP-scratch dir (dir handle was locked; files cleared). **Phase-7 `.gitignore` must add
  `.playwright-mcp/` + `*.tmp.*`.**
- **planned→backlog reconciliation:** swept every README for "planned / not-yet-implemented" items and checked
  each against `INCREMENT-BACKLOG.md` + `future-tracks/`. openalex/semantic-scholar/grobid were already
  **visible** (they cite future-tracks). Two were **invisible** → now captured:
  - **Mendeley** — its README correctly said *no track depends on it*, yet the backlog mis-framed it as "shared
    infra these unlock." It's **import coverage**, not track infra → new **"Import coverage — additional
    sources"** item (Theme 2: Mendeley via Zotero-bridge/exports + BibTeX/RIS/CSL-JSON import); backlog line
    328 corrected; mendeley README points at the item.
  - **Desktop-shell (Tauri) + OS keychain + desktop distribution** (desktop-shell + ops READMEs) — entirely
    absent from the plan → new **"Packaging & distribution (post-V1)"** item (Theme 4); both READMEs point at it.
- **README coverage:** added `tests/e2e/README.md` (the one genuine gap — the opt-in browser smoke +
  `CALLOSUM_RUN_E2E`). **Did NOT** blanket-add per-Python-package READMEs: the component READMEs (app/,
  app/backend/, integrations/, tests/) already map their subpackages, and per-package stubs would duplicate
  CLAUDE.md's directory layout and risk drift (rule #6). Offered deeper coverage if wanted.
- **Files:** `tests/e2e/README.md` (new); `.claude/docs/INCREMENT-BACKLOG.md`; `integrations/mendeley/README.md`,
  `app/desktop-shell/README.md`, `ops/README.md`.
- **Why:** docs better-scoped + the plan now captures all README-described planned functionality (user ask).
- **Verify:** no code touched (`pytest` unaffected at 275 passed, 1 skipped).

## 2026-06-20 — Release-readiness arc, Phase 5 (modularize · dedup · dead-code · lint/format · security audit)

Pre-GitHub code hardening (no API/schema/behavior change; increment counter stays 73).

- **Linting adopted — ruff.** Config in `pyproject.toml` (line-length 120, `select=E,F,W,I,B`, `ignore=E501`,
  bugbear `extend-immutable-calls` for FastAPI `Depends`/`Query`/… to kill B008 false positives). Applied
  **318 auto-fixes** (229 unused-import, import-sort, whitespace, etc.) + 7 manual (unused loop var, B023
  loop-capture, an `# noqa: E402` for the `sys.path` shim) + **`ruff format` repo-wide** (58 files). `ruff
  check` + `ruff format --check` now clean & idempotent. `requirements-dev.txt` carries pytest/httpx/ruff/
  pip-audit/playwright/pytest-playwright.
- **Modularize (600-line cap).** Only one app-source file was over: `axis_scoring.py` (617). Split the
  manual-assignment + read-state API → new **`app/backend/clustering/axis_assignments.py`** (167);
  `axis_scoring.py` → 463 (scoring engine only). Importers repointed (router, axis_operations, tests).
  **No app/integrations file now exceeds 600** (largest: repository 577, papers 576).
- **Dedup (lizard + difflib).** difflib flagged the 4 async-job subsystems as 0.87–0.92 similar — they each
  carried a near-identical `_XJob`/`_XJobStore` (differing only in result type). Consolidated into a generic
  **`app/backend/api/job_store.py`** (`Job`/`JobStore[R]`); `create_app` instantiates one per subsystem;
  routers type them `JobStore[XResponse]`. Removed ~130 lines of duplication. lizard complexity hotspots
  (clustering/dedup/merge fns) are inherent algorithmic complexity, left as-is (not duplication).
- **Dead code.** ruff F-series clean; removed one genuinely-unused back-compat alias
  (`canonicalize_quote_text_variants` in extraction.py). Hardcoded-secret grep: none.
- **Security audit:** `.claude/security-audits/2026-06-20_pre-github-fullsweep.md` — **PASS** for the local
  single-user model. Two tracked follow-ups: (1) secrets hygiene before first commit (`.env` relocation +
  `.gitignore` + working-tree secret scan — Phase 6/7 publication gates); (2) `pip-audit` found transitive
  CVEs in `transformers`/`urllib3` (LOW risk locally — trusted models + trusted endpoints; requirements use
  ranges so fresh installs patch) — upgrade + wire pip-audit into CI before any hosted deployment. (`yt-dlp`
  flagged but is NOT a callosum dependency — environment noise.)
- **Files:** `pyproject.toml` (ruff config); `requirements-dev.txt`; **new** `axis_assignments.py`,
  `job_store.py`; `axis_scoring.py`, `axis_operations.py`, `routers/{axes,summaries,duplicates}.py`,
  `app.py`, `extraction.py`, `tests/test_axes.py`, + ~60 files reformatted; security-audit doc.
- **Why:** ship a lint-clean, duplication-reduced, cap-compliant, audited codebase for the public repo.
- **Verify:** `ruff check` clean; `pytest` → **275 passed, 1 skipped**. **Revert:** restore from
  `.claude/backups/callosum_pre-phase5_20260620_1242.zip`.

## 2026-06-20 — Release-readiness arc, Phase 4 (test-harness audit + extension; usage-logging prod fix)

Pre-GitHub test hardening (docs/infra/test-only; increment counter stays 73).

- **New automated coverage (+19 tests, 256 → 275):**
  - `tests/test_egress_gate.py` (9) — direct unit tests of the inc-58 `EgressGated*` wrappers (the
    authoritative egress boundary): when egress is OFF each wrapper raises **and the inner provider is
    never invoked** (a spy inner records calls); ON delegates + passes metadata. Pins the security
    property the API-level tests could only imply, including the help assistant's independent toggle.
  - `tests/test_usage_logging.py` (5) — `llm/usage.py` was untested: logs the token counts, is silent on
    missing/None `usage_metadata`, never raises on malformed metadata, **and survives an Alembic
    migration** (regression for the fix below).
  - `tests/test_frontend_assembly.py` (5) — deterministic, offline frontend smoke: assembles without
    error, both `{{STYLES}}`/`{{SCRIPT}}` placeholders consumed, `#root` + babel script present, all 3
    CDN scripts carry SRI, **every** `app/frontend/js/*.jsx` chunk is included, and `callosum-app.html`
    is byte-in-sync with the live assembly (catches a forgotten `build_frontend.py`).
  - `tests/e2e/test_smoke.py` (1, **opt-in**) — committed Playwright browser smoke: launches the real
    `app:app` against a seeded temp DB, loads `/` in headless Chromium, asserts React mounts with **zero**
    console errors. Skipped unless `CALLOSUM_RUN_E2E=1` (keeps the default suite offline/deterministic);
    CI runs it after `playwright install chromium`. Verified green locally (23s).
- **Production fix surfaced by the new usage test:** `alembic/env.py` now calls
  `fileConfig(..., disable_existing_loggers=False)`. The default (`True`) disabled every app logger not
  named in `alembic.ini` on each migrate — so a real startup auto-migration left `callosum.llm.usage`
  disabled, **silently killing inc-61 token-usage logging until the next restart** (`_loud` only revived
  the `callosum` parent). `_loud` kept as defense-in-depth.
- **`requirements-dev.txt` created** (pytest, httpx, ruff, pip-audit, playwright, pytest-playwright) —
  also resolves a stale CLAUDE.md reference to a file that didn't exist.
- **Files:** `tests/test_egress_gate.py`, `tests/test_usage_logging.py`, `tests/test_frontend_assembly.py`,
  `tests/e2e/{__init__,test_smoke}.py` (new); `alembic/env.py` (logging fix); `requirements-dev.txt`
  (new); `tests/README.md` (codex Phase-3 draft + browser-smoke section); `.claude/CLAUDE.md` (test count,
  tree, migration-logging decision row).
- **Why:** close the survey-flagged gaps (egress-gate isolation, usage logging, no committed frontend
  test) before exposing the repo + CI; the audit also caught a live observability bug.
- **Verify:** `pytest` → **275 passed, 1 skipped** (e2e gated); `CALLOSUM_RUN_E2E=1 pytest tests/e2e` →
  1 passed. **Revert:** delete the new test files + `requirements-dev.txt`; restore `alembic/env.py` from
  Dropbox history.

## 2026-06-20 — Release-readiness arc, Phases 1–3 (principles gate · future-tracks fold-in · README/dir cleanup)

Pre-GitHub prep (docs/infra only; no app-code or schema change — increment counter stays 73).

- **Phase 1 — principles gate.** Added a **Principles alignment gate** section + **rule #9 (Principle
  fidelity)** + session-kickoff item #8 to `.claude/CLAUDE.md`, keyed to the new `.claude/PRINCIPLES.md`
  charter (10 commitments + THEORY contract + 4 worked examples). The gate is a *reflective pause* before
  adding/removing a literature-claim/signal feature: name the principle(s) + worked example, name the
  misalignment risk, and **propose the aligned alternative** (not just the objection). Added PRINCIPLES.md +
  future-tracks rows to the reference table.
- **Phase 2 — backlog reflects the full vision.** Moved the 7 root `opus4.8_future-tracks*.md` docs →
  **`.claude/docs/future-tracks/`** (+ a `README.md` index table); `INCREMENT-BACKLOG.md` now references each
  track (statcheck, Word/LibreOffice plugin, highlight-to-suggest/evaluate, acquisition, my-publications,
  theory/methods, plugins, gapfinder, Feed/Search) + shared deps
  (OpenAlex/Unpaywall/Semantic-Scholar/GROBID/mendeley); reconciled the stale
  `opus4.8_callosum_backlog-future-tracks.md` reference. Relocated increment notes 65–73 into
  `.claude/docs/increment-notes/`.
- **Phase 3 — GitHub strip-down + README refresh.** Archived vestigial planning-only `pipelines/` (+6
  subdirs) and `data/` (+library-store/sqlite/vector-store) → **`.claude/deprecated/`** (kept, not deleted —
  their real code lives in `app/backend/`). Removed 3 `.tmp.26380.*` crash orphans. Refreshed all **13 kept
  READMEs** (root front door + `app/**`, `integrations/**`, `tests/**`, `research/`, `ops/`) to current
  reality via `codex exec`, **each draft reviewed against the code** (root README rewritten from the stale
  "planning skeleton" to an accurate, principles-linked front door). Updated the CLAUDE.md root directory
  tree (dropped `pipelines/`; added `research/`, `ops/`).
- **Files:** `.claude/CLAUDE.md`; `.claude/docs/future-tracks/` (7 moved docs + new README);
  `.claude/docs/INCREMENT-BACKLOG.md`; `.claude/docs/increment-notes/` (65–73 moved); `.claude/deprecated/`
  (pipelines/, data/ moved); `README.md`, `app/README.md`, `app/frontend/README.md`,
  `app/desktop-shell/README.md`, `integrations/README.md` + the 4 planned stubs, `tests/README.md`,
  `tests/fixtures/README.md`, `research/README.md`, `ops/README.md`.
- **Why:** prepare an honest, principle-coherent, clutter-free tree for a public **AGPL-3.0** GitHub release
  without losing institutional memory (vestigial dirs are archived, never destroyed).
- **Revert:** restore moved dirs from `.claude/deprecated/`; READMEs/CLAUDE.md from Dropbox version history or
  `.claude/backups/`.

## 2026-06-20 — Import Crossref subjects as first-order keyword tags (increment 73)

- **Files:** `integrations/crossref/adapter.py` (capture `subject`); `app/backend/persistence/tags_repo.py`
  (`import_source` param + `add_tags_to_paper`); `app/backend/metadata/enrichment.py`
  (`apply_crossref_subject_tags` + hook); **new** `tools/backfill_keyword_tags.py`;
  `app/frontend/js/25_detail.jsx` (TagsRow re-sync bugfix) + rebuilt `callosum-app.html`;
  `app/backend/help/help_content.md`; `tests/{test_papers,test_tags,test_backfill_keyword_tags}.py`. Audit:
  `.claude/security-audits/2026-06-20_keyword-tags.md`. Notes: `INCREMENT-73-NOTES.md`.
- **What:** a paper's **Crossref subject categories** are imported as **first-order tags**
  (`import_source="keyword:crossref"`) — automatically on 🔎 re-resolve / batch enrich, and across the
  existing library via `python tools/backfill_keyword_tags.py` (full: cache-first, re-resolve the rest).
- **Why:** authors/indexers already did the concept work of naming a paper's dimensions — privilege it; the
  inc-72 c-TF-IDF suggester is the second-order gap-filler. (Zotero tags already imported via inc 71.)
- **How:** adapter keeps `subject` in `csl_json`; `apply_crossref_subject_tags` mirrors it to tags
  (additive, idempotent, **never clobbers metadata**). DOI-only to public Crossref (NOT the egress gate);
  no migration; no new endpoint. **Bugfix:** TagsRow now re-syncs on detail refetch so 🔎-added chips show.
- **Verify:** pytest **256** (+5: adapter dedupe, re-resolve→tags + provenance preserved, backfill
  cache/fetch/idempotent/metadata-safe); live E2E (`.local/keyword_tags_e2e/`) 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc73.zip` (or revert the adapter/enrichment/
  tags_repo edits + remove the tool, rebuild).
- **Help docs:** user-facing → tags section now covers Crossref keyword tags + the backfill (`HELP-DOCS-SYNCED`
  → inc 73).
- **NEXT (deferred):** the **provenance UI** (style/group tags by source — "author keywords" vs "your tags"
  vs system facts), OpenAlex/PubMed keyword sources, and the tags↔findings cross-cut. See `INCREMENT-BACKLOG.md`.

## 2026-06-20 — Auto-suggest tags via local c-TF-IDF (increment 72)

- **Files:** **new** `app/backend/clustering/tag_suggestion.py` + `app/backend/api/routers/tags.py`
  (`GET /papers/{id}/suggested-tags`); `app/frontend/js/25_detail.jsx` + `styles.css` (✨ Suggest + candidate
  chips) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (tags section);
  `tests/{test_tag_suggestion,test_health}.py`. Audit: `.claude/security-audits/2026-06-20_tag-suggest.md`.
  Notes: `INCREMENT-72-NOTES.md`.
- **What:** a **✨ Suggest** button on the Details Tags row proposes candidate tags via **local c-TF-IDF**
  (terms most distinctive of the paper vs the library); the user clicks to accept (added via the inc-71 path).
  The per-paper analogue of inc-52's axis suggestion.
- **Why:** speeds tagging by mining the paper's own text; complements manual tags + (future) imported keywords.
- **Backend:** `suggest_tags_for_paper` (tf·idf, reuses `axis_suggestion._paper_tokens`; excludes existing
  tags; trashed/missing → []); `GET /papers/{id}/suggested-tags`. **Purely local — no embeddings, no Gemini,
  no egress** (user's explicit choice). No migration.
- **Verify:** pytest **251** (+3: distinctive ranking, idf demotes common terms, exclude-existing, endpoint);
  route-surface +1; live E2E (`.local/tag_suggest_e2e/`) — Suggest → accept a candidate, 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc72.zip` (or remove `tag_suggestion.py` + the
  endpoint + the TagsRow Suggest UI, rebuild).
- **Help docs:** user-facing → tags section now covers ✨ Suggest + **moved the `HELP-DOCS-SYNCED` marker to
  inc 72**.
- **FOLLOW-UP (user, 2026-06-20):** **author/expert keywords as first-order tags** — privilege the authors'
  own concept work; the c-TF-IDF pass is the *second-order* gap-filler. Recorded in `INCREMENT-BACKLOG.md`
  with the **tag-provenance** model + the **tags ↔ findings/system-facts** cross-cut (e.g. a future RETRACTED
  tag from the retraction producer). See that file + the future-tracks "Tags hook" notes.

## 2026-06-20 — Tags: per-paper labels + filter the library by tag (increment 71)

- **Files:** **new** `app/backend/persistence/tags_repo.py` + `app/backend/api/routers/tags.py` +
  `app/backend/api/app.py` (include router); `app/backend/persistence/repository.py` (`list_papers` tag_id) +
  `app/backend/api/routers/papers.py` (detail `tags` field + `tag_id` param);
  `app/frontend/js/{25_detail,40_app,10_pdf_layer,20_synthesis}.jsx` + `styles.css` (Tags row + filter
  banner) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (tags section);
  `tests/{test_tags,test_health}.py`. Audit: `.claude/security-audits/2026-06-20_tags.md`. Notes:
  `INCREMENT-71-NOTES.md`.
- **What:** lightweight free-form **tags** on papers — view/add/remove on the Details pane, click a tag to
  **filter the library** to it. Surfaces the tags the Zotero importer already populates (previously invisible).
- **Why:** a reference-manager basic — manual labels complementing the heavyweight semantic axes; the
  `tags`/`paper_tags` tables existed but had no UI.
- **Backend:** new `tags_repo.py` (get/list/add[get-or-create+idempotent]/remove[+orphan prune]);
  `GET /tags`, `POST`/`DELETE /papers/{id}/tags*`; `tag_id` filter on `GET /papers` (IN subquery, mirrors
  inc-63). **No migration, local, bound-param.** Name trimmed/capped, rendered as plain text.
- **Frontend:** Details `TagsRow` (chips: name→filter, ×→remove; add input + `/tags` datalist); the inc-63
  axis-filter mirrored for tags (`libraryTagFilter`, mutually exclusive with the axis filter) + a "Filtered
  to tag …" banner.
- **Verify:** pytest **248** (+4); route-surface +3; live E2E (`.local/tags_e2e/`) — add→filter→clear→remove,
  0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc71.zip` (or remove `tags_repo.py`/
  `routers/tags.py` + the detail field + the four frontend edits, rebuild).
- **Help docs:** user-facing → added a "Tagging papers" section + **moved the `HELP-DOCS-SYNCED` marker to
  inc 71**.
- **NEXT (chosen):** inc 72 — **auto-suggest tags** per paper via **local c-TF-IDF** (no Gemini), reusing the
  inc-52 axis-suggestion machinery; candidates curated → added through this increment's tag path.

## 2026-06-20 — Citation export: BibTeX + RIS + CSL-JSON (increment 70)

- **Files:** **new** `app/backend/metadata/citation_export.py` (formatters) + `app/backend/persistence/repository.py`
  (`get_papers_for_export`) + `app/backend/api/routers/papers.py` (`POST /papers/export`);
  `app/frontend/js/{10_pdf_layer,40_app,25_detail}.jsx` + `styles.css` (bulk export picker + Details "Cite"
  row) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (new export section);
  `tests/{test_citation_export,test_papers,test_health}.py`. Audit:
  `.claude/security-audits/2026-06-20_citation-export.md`. Notes: `INCREMENT-70-NOTES.md`.
- **What:** export papers' citations in **BibTeX / RIS / CSL-JSON** from the stored `csl_json` — a **bulk
  file download** (select papers → export… → a `.bib`/`.ris`/`.json`) and a **per-paper clipboard copy**
  (Details → Cite row). The first way to get citations *out* of the library.
- **Why:** callosum is a reference manager you import into but couldn't export from — a core gap.
- **Backend:** `POST /papers/export {paper_ids, format:Literal}` → `render_citations`; live papers only
  (trashed never exported); 422 on bad format / no live ids. Read-only, **local (no egress)**, no migration;
  formatters escape their output; constant download filename. BibTeX deduped author+year key fallback.
- **Frontend:** `apiPost` forces `.json()`, so export uses a **raw fetch** → blob→`<a download>` (bulk) or
  →`navigator.clipboard` (per-paper copy, secure context on 127.0.0.1). Cite links reuse the inc-68
  canonical `.btn-link`.
- **Verify:** pytest **244** (+8: 7 formatter unit + 1 endpoint, route-surface +1); live E2E
  (`.local/citation_export_e2e/`) — bulk `.bib` download (both papers) + clipboard copy, 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc70.zip` (or remove the endpoint +
  `citation_export.py` + the three frontend edits, rebuild).
- **Help docs:** user-facing → added an "Exporting citations" section + **moved the `HELP-DOCS-SYNCED` marker
  to inc 70**.

## 2026-06-20 — Sort the library (increment 69)

- **Files:** `app/backend/persistence/repository.py` (`_paper_sort_order` + `list_papers(sort=…)`) +
  `app/backend/api/routers/papers.py` (`sort` query param); `app/frontend/js/{10_pdf_layer,40_app}.jsx` +
  `styles.css` (Sort dropdown) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (library
  section); `tests/test_papers.py`. Notes: `INCREMENT-69-NOTES.md`.
- **What:** a **Sort** dropdown orders the library by date added (oldest/recent), title (A–Z), publication
  year (newest/oldest), or first author (A–Z). NULL year/author sort last; `id` is the stable tiebreak.
- **Why:** the library only ever listed in import order — sorting is a reference-manager basic (the axes
  panel had it since inc 43; the library didn't).
- **Backend:** the sort key indexes an **allowlist** (rule #3 — never interpolated into SQL); unknown →
  default `added` (= prior `id ASC` behavior). No new route, no migration, no egress; composes with
  q/deleted/axis_id/pagination.
- **Verify:** pytest **236** (+1: every sort order + NULL-last + unknown→default); live E2E
  (`.local/library_sort_e2e/`) — list re-orders by title/year/recency, 0 console errors. No audit gate
  (read-only query param).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc69.zip` (or revert the `sort` param +
  the frontend dropdown, rebuild).
- **Help docs:** user-facing → documented the Sort control + **moved the `HELP-DOCS-SYNCED` marker to inc 69**.

## 2026-06-20 — Canonical .btn-* button classes (DESIGN.md §3 #5) (increment 68)

- **Files:** `app/frontend/styles.css` (canonical button layer + consolidation) + `.claude/DESIGN.md` (§2
  Buttons rewritten, §3 #5 → PARTIAL); rebuilt `callosum-app.html`. Notes: `INCREMENT-68-NOTES.md`.
- **What:** added canonical `.btn`/`.btn-primary`/`.btn-ghost`/`.btn-link`/`.btn-icon` + `.danger` classes
  and folded the cleanly-identical ad-hoc button blocks into them (primary: `.axis-btn` + `.synth-actions
  button`; ghost: `.pginate button`; link: `.axis-link`; icon: `.axis-icon-btn`). **CSS-only, zero visual
  change, no JSX touched.**
- **Why:** DESIGN.md §3 #5 standing worklist item — ~10 near-duplicate button blocks re-typing the same
  recipe. Establishes the single source of truth so new buttons conform instead of drifting.
- **How (safety):** consolidation by **selector grouping** (alias the existing class names into the canonical
  rules) only where every grouped property is byte-identical to the original — near-zero regression risk,
  no className churn (`.axis-link` has dozens of call sites). Size-divergent ghost/icon buttons left as-is
  (value-shifting → deferred to a per-button JSX-className migration).
- **Verify:** no Python changed → pytest unchanged at **235**; live E2E (`.local/btn_dry_e2e/`) asserts each
  canonical class's computed style equals the intended recipe + a real `.synth-actions button` keeps its
  sizing delta, 0 console errors. No audit gate (styling only).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc68.zip` (or revert the styles.css button
  section, rebuild).

## 2026-06-20 — Un-dismiss / manage dismissals for duplicate detection (increment 67)

- **Files:** **new** `app/backend/persistence/dedup_repo.py` (the dedup-dismiss data access, extracted from
  `repository.py`) + `app/backend/api/routers/duplicates.py` (GET dismissed + POST undismiss) +
  `app/backend/clustering/duplicate_detection.py` (import repoint); `app/frontend/js/19_duplicates.jsx` +
  `styles.css` ("Previously dismissed" section) + rebuilt `callosum-app.html`;
  `app/backend/help/help_content.md` (duplicates section); `tests/{test_papers,test_health}.py`. Audit:
  `.claude/security-audits/2026-06-20_undismiss-duplicates.md`. Notes: `INCREMENT-67-NOTES.md`.
- **What:** the Duplicates modal now has a **Previously dismissed (N)** section listing the pairs you marked
  "not a duplicate" (inc 64), each with an **un-dismiss** button that lets the scan flag them again. Adds the
  in-app undo inc-64 deferred.
- **Why:** a persistent dismiss with no way to see or reverse it was a trust gap.
- **Backend:** `GET /papers/duplicates/dismissed` (registered before `/{job_id}` so "dismissed" isn't a job
  id) + `POST /papers/duplicates/undismiss {paper_ids}` (non-destructive, idempotent, local, bound-param).
  No migration (reuses the inc-64 table).
- **Module split (rule #1):** the two new data-access fns pushed `repository.py` to **604** (>600), so the
  dedup-dismiss concern (4 fns) was **moved verbatim** to new `persistence/dedup_repo.py` (63);
  `repository.py` → **555**; two importers repointed. Behavior-preserving.
- **Verify:** pytest **235** (+1: list → undismiss → re-flag, idempotent, 422); route-surface +2; live E2E
  (`.local/undismiss_e2e/`) — dismiss → previously-dismissed → un-dismiss → re-flagged, 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc67.zip` (or revert the two endpoints +
  frontend section, fold `dedup_repo.py` back into `repository.py`, rebuild).
- **Help docs:** user-facing → added un-dismiss to the duplicates section + **moved the `HELP-DOCS-SYNCED`
  marker to inc 67**.

## 2026-06-20 — Exclude trashed papers from synthesis retrieval (increment 66)

- **Files:** `app/backend/summarization/pipeline.py` (`_source_chunks_for_scope` live-paper filter) +
  `app/backend/embeddings/retrieval.py` (`_candidate_embedding_ids` excludes trashed);
  `app/backend/help/help_content.md` (trash gotcha); `tests/{test_summaries,test_papers}.py`. Notes:
  `INCREMENT-66-NOTES.md`.
- **What:** a paper in **Trash** (soft-deleted, not yet purged) is no longer a retrieval candidate, so it
  can't be cited in a **new** synthesis. Closes the last soft-delete leak (inc-65 deferred item).
- **Why:** a trashed paper surfacing in a fresh synthesis is wrong; the user deleted it.
- **Where it actually was:** the synthesis pipeline doesn't use `search_similar` — `_source_chunks_for_scope`
  builds its own candidate SQL, and the **query** scope was `select(chunks)` with no paper filter (pulled
  every paper). Fixed there (covers query + hardens papers/cluster scopes); also hardened the general
  `_candidate_embedding_ids` primitive (defense-in-depth, used by the validation harness).
- **Verify:** pytest **234** (+2: query-scope `_source_chunks_for_scope` + `search_similar` both drop a paper
  after it's trashed, keep the live one). Backend-only — no migration/endpoint/egress/frontend; no audit
  gate; behavior-preserving when nothing is trashed (harness unaffected).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc66.zip` (or revert the two filter edits).
- **Help docs:** user-facing → updated the trash gotcha + **moved the `HELP-DOCS-SYNCED` marker to inc 66**.

## 2026-06-20 — Permanent delete: delete forever / empty Trash (increment 65)

- **Files:** `app/backend/embeddings/vector_store.py` (`VectorStore.delete`) +
  `app/backend/persistence/repository.py` (`purge_paper`/`purge_all_trashed`/`_purge_paper_embeddings`) +
  `app/backend/api/routers/papers.py` (`DELETE /papers/{id}/permanent`, `POST /papers/trash/empty`,
  `_vector_store`); `app/frontend/js/{10_pdf_layer,40_app}.jsx` + `styles.css` (Delete forever / Empty Trash,
  danger-styled, confirm) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (trash section);
  `tests/{test_papers,test_health}.py`. Audit: `.claude/security-audits/2026-06-20_permanent-delete.md`.
  Notes: `INCREMENT-65-NOTES.md`.
- **What:** a **trashed** paper can now be **permanently deleted** — per-paper **Delete forever** or
  **Empty Trash** — removing the paper, its dependent rows, AND its embeddings + sqlite-vec vectors. Finishes
  inc-54's soft-delete (Trash had no way to be emptied).
- **Why:** completes the library-delete feature; a real reference manager must be able to free space / truly
  remove a record.
- **Orphan-safety:** `embeddings.target_id` has no FK and the store had no delete, so a naive paper delete
  left embeddings + vectors behind → an orphaned paper-embedding crashes `retrieval._resolve_hit`. Purge now
  deletes the paper's embeddings + vectors **before** the paper row (CASCADE handles the rest), in one
  transaction → no orphan, no crash (unit-proven via a post-purge `search_similar`).
- **Safety:** **only reachable from Trash** (`purge_paper` returns False for a live paper → 404), so a live
  paper can never be purged in one step; the UI double-confirms. Local-only, no egress; bound-param SQL.
  **No migration** (pure DML; head stays 0006).
- **Verify:** pytest **232** (+4); live E2E (`.local/permanent_delete_e2e/`) — delete-forever + empty-trash,
  live paper survives, 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc65.zip` (or revert the vector_store/repo/
  router/frontend edits + rebuild; no schema to undo).
- **Help docs:** user-facing → updated the trash-and-restore section + **moved the `HELP-DOCS-SYNCED` marker
  to inc 65**.

## 2026-06-20 — Persistent "not a duplicate" dismiss (increment 64)

- **Files:** `app/backend/persistence/schema.py` (+`dismissed_duplicate_pairs`) +
  `alembic/versions/0006_dismissed_duplicate_pairs.py` (head 0005→0006) +
  `app/backend/persistence/repository.py` (`get_dismissed_duplicate_pairs`/`dismiss_duplicate_pairs`) +
  `app/backend/clustering/duplicate_detection.py` (drop dismissed pairs before union-find);
  **new** `app/backend/api/routers/duplicates.py` (the dedup concern extracted from `papers.py`) +
  `app/backend/api/app.py` (include it before `papers.router`); `app/frontend/js/19_duplicates.jsx`
  (dismiss → persist) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (duplicates section);
  `tests/{test_papers,test_health,test_startup_migration}.py`. Audit:
  `.claude/security-audits/2026-06-20_dedup-dismiss.md`. Notes: `INCREMENT-64-NOTES.md`.
- **What:** marking a duplicate group **"not a duplicate"** is now **persistent** — the scan stores the
  group's pairs in `dismissed_duplicate_pairs` and drops them on every future scan, so a legitimate
  preprint+published pair stops re-flagging. Finishes inc-56's deferred "persistent dedup-dismiss."
- **Why:** session-only dismiss meant the same false positives reappeared every scan.
- **Backend:** `POST /papers/duplicates/dismiss {paper_ids}` (≥2 existing live papers → else 422) stores all
  canonical `(low<high)` pairs; bound-param `INSERT OR IGNORE` (rule #3); local-only (no egress);
  non-destructive (records a preference, never deletes). The drop happens in `find_duplicate_groups` before
  the union-find, so a dismissed pair never links its papers into a group.
- **Module split (rule #1):** extending dedup pushed `routers/papers.py` to **636** (>600), so the duplicates
  concern (models + `_DedupJobStore` + the 3 endpoints + `_run_dedup_job`) was **moved verbatim** to the new
  `routers/duplicates.py` (157); `papers.py` → **497**. Behavior-preserving (full suite green); `app.py`
  includes `duplicates.router` before `papers.router` so `/papers/duplicates*` still wins over
  `/papers/{paper_id}`.
- **Verify:** pytest **228** (+1: dismiss → re-scan flags 0; idempotent; <2 ids → 422); migration-head +
  route-surface asserts bumped to `0006` / +`/papers/duplicates/dismiss`; live E2E
  (`.local/dedup_dismiss_e2e/`) — dismiss → reopen modal → "No likely duplicates found.", 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc64.zip` (or drop migration 0006 + the
  `dismissed_duplicate_pairs` table, revert the duplicate_detection filter, and fold `duplicates.py` back
  into `papers.py`).
- **Help docs:** user-facing → corrected the duplicates section (dismiss is persistent, not session-only) +
  **moved the `HELP-DOCS-SYNCED` marker to inc 64**.

## 2026-06-20 — Filter the library by axis (+ select-all) (increment 63)

- **Files:** `app/backend/persistence/repository.py` (`list_papers` `axis_id` filter) +
  `app/backend/api/routers/papers.py` (`axis_id` query param); `app/frontend/js/{40_app,10_pdf_layer,15_axes}.jsx`
  + `styles.css` (clickable count badge → filter; "Filtered to axis …" banner; "select all");
  `app/backend/help/help_content.md` (axis-review section); `tests/test_papers.py`; rebuilt
  `callosum-app.html`. Notes: `INCREMENT-63-NOTES.md`.
- **What:** click an axis's **count badge** → the Library narrows to that axis's papers (with a clearable
  "Filtered to axis …" banner). Server-side filter (pagination/search compose). Pairs with inc-62: filter →
  **select all → summarize** = a verified synthesis of a whole topic cluster.
- **Why:** completes the axes-as-a-navigation-lens vision (backlog "open proposal: filter the library by
  axis").
- **Backend:** bound-param `IN` subquery over `cluster_node_papers`→`cluster_nodes` (rule #3); no new
  endpoint/egress/ingestion/migration; trashed papers stay excluded.
- **Verify:** pytest **227** (+1); live E2E (`.local/library_axis_filter_e2e/`) — filter narrows 2→1 +
  banner + select-all→summarize verified + clear restores, 0 console errors. Read-only feature → security
  note in the increment notes (no separate audit doc).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc63.zip` (or revert the `axis_id` filter +
  the three frontend files, rebuild).
- **Help docs:** user-facing → updated the axis-review section + **moved the `HELP-DOCS-SYNCED` marker to inc
  63**.

## 2026-06-20 — Summarize selected papers: multi-paper verified synthesis from the library (increment 62)

- **Files:** `app/backend/summarization/pipeline.py` (`_round_robin_by_paper` coverage fix);
  `app/frontend/js/{10_pdf_layer,40_app,20_synthesis}.jsx` + `styles.css` (bulk-bar **summarize** button →
  papers-scope synthesis + scope-note badge); `app/backend/help/help_content.md` (synthesis section);
  `tests/test_summarize_selected.py`; rebuilt `callosum-app.html`. Audit:
  `.claude/security-audits/2026-06-20_summarize-selected.md`. Notes: `INCREMENT-62-NOTES.md`.
- **What:** checkbox-select papers in the Library → click **summarize** → a **verified, citation-grounded
  synthesis of just that subset** runs in the always-on Synthesis pane (with an "N selected papers" note).
  Reuses the existing `/summarize` papers scope + local verification + the inc-61 cache.
- **Why:** the verified-synthesis crown jewel, applied to a user-chosen subset — backlog item "Multi-paper
  summary from a library selection" (the selection→summarize half; the critical-review supplement stays
  deferred behind the Auditability standard).
- **Backend fix:** a multi-paper, no-query summary previously took the first `top_k` chunks by id (filling
  from the lowest-id paper, ignoring the rest); now **round-robin across the selected papers** so the
  summary covers them all. Single-paper / query scopes unchanged.
- **Verify:** pytest **226** (+3); live E2E (`.local/summarize_selected_e2e/`) — select 2 → summarize →
  verified result + scope note, 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc62.zip` (or revert the four frontend files
  + the `_round_robin_by_paper` block, rebuild).
- **Help docs:** user-facing → updated the synthesis section + **moved the `HELP-DOCS-SYNCED` marker to inc
  62** (the convention working).

## 2026-06-20 — Backlog curation: record future objectives (docs only, no code)

- **Files:** `.claude/docs/INCREMENT-BACKLOG.md` (new "Multi-paper summary from a library selection"
  item [Partial] under Theme 3 + a cross-cutting "Auditability standard" gating note + fixed a stale
  future-tracks path pointer); `.claude/docs/backlog-future-tracks.md` (augmented Track C with the captured
  verification-funnel / low-friction / flow-state design intent; Track B cross-ref; an Auditability-standard
  note in the intro).
- **What:** recorded three stated future objectives as tracked commitments — (2) word-processor plugin
  [Not started → already designed as Track B + C], (3) in-flow accuracy/meaning check [Not started → Track C
  "Evaluate"], (4) multi-paper summary from a library selection [Partial] — each WITH its design intent +
  the cross-cutting auditability gate. Item 1 (automatic axis nomination) confirmed **[Done]** (inc 52) and
  not re-added.
- **Why:** make future objectives tracked commitments rather than undocumented intentions (user request);
  deduped against the existing Tracks B/C (augmented in place, not duplicated).
- **Revert:** restore the three docs from `.claude/backups/callosum_claudecode_inc61.zip` (or remove the new
  blocks). No code/app/API change; no increment bump.
- **Noted (not fixed):** `README.md` is still stale ("planning skeleton"); `CLAUDE.md`'s reference-table row
  for the future-tracks doc points at a stale path (the canonical doc is `.claude/docs/backlog-future-tracks.md`).

## 2026-06-20 — Reduce LLM token spend: content-addressed summary cache + usage logging (increment 61)

- **Files:** new `app/backend/llm/{cache.py, usage.py}`; `alembic/versions/0005_llm_generation_cache.py` +
  `schema.py` (`llm_cache` table); `summarization/generators.py` + `integrations/gemini/generator.py` +
  `llm/egress.py` (thread `conn` through `generate`; `SUMMARY_PROMPT_VERSION` + `cache_signature`);
  `routers/summaries.py` (wrap with `CachedSummaryGenerator`); `summarization/pipeline.py` (pass `conn`);
  usage logging in the 4 gemini modules; `tests/test_llm_cache.py` + head bumps. Audit:
  `.claude/security-audits/2026-06-20_llm-cache.md`. Notes: `INCREMENT-61-NOTES.md`.
- **What:** a **persistent content-addressed cache** on the token-expensive **summary generation** step (a
  cache hit costs zero tokens) — keyed by a content hash of model + prompt-version + the chunk set +
  scope, so any input change misses automatically (no explicit invalidation). Plus lightweight **token-usage
  logging** at all 4 LLM call sites.
- **Why:** cut LLM token spend (the summary path is the top offender) without degrading the
  citation-verification guarantees. The cache wraps generation ONLY — local verification re-runs on every
  result; the egress gate stays byte-for-byte unchanged (cache layered inside it).
- **Verify:** pytest **223** (+6); audit PASS. Other levers (cache extension, output caps, top_k, provider
  prefix caching, Batch API) are **proposed with a measurement plan and deferred for review** (see notes).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc61.zip` (or remove `app/backend/llm/{cache,
  usage}.py` + migration 0005 + the `conn`/`cache_signature` plumbing + the factory wrap).
- **Help docs:** backend-only, **no user-facing change** → the `HELP-DOCS-SYNCED` marker is NOT moved (this
  entry sits above it as a since-sync change that does not warrant a help update — the convention working).

## 2026-06-20 — AI help assistant, separate gate (increment 60)

- **Files:** new `app/backend/help/assistant.py`, `integrations/gemini/help_assistant.py`;
  `app/backend/llm/egress.py` (+`HelpAssistantDisabledError` + `EgressGatedHelpAssistant`);
  `integrations/gemini/generator.py` (`GeminiConfig.help_assistant_enabled`); `routers/help.py` (`POST
  /help/ask` + factory), `app.py` (param/state); `app/frontend/js/18_help.jsx` + `styles.css` (chat);
  `app/backend/help/help_content.md` (+`ai-help-assistant` section); `tests/test_help.py`,
  `tests/test_health.py`, `tests/conftest.py`. Audit: `.claude/security-audits/2026-06-20_help-assistant.md`.
  Notes: `INCREMENT-60-NOTES.md`.
- **What:** an AI help assistant in the help modal — ask a question, get an answer + reference chips that
  scroll to and highlight the matching help section (reusing inc-59's `flashHelpSection`). Multi-turn, NO
  RAG (whole corpus stuffed), defensive parse (failure → answer, no refs, never 500); the router drops
  hallucinated section ids.
- **Why:** condition the synthesis "probe → route to source" workflow over the app's own help; close the
  help loop started in inc 59.
- **Separate gate (the key constraint):** keyed on a NEW **`CALLOSUM_HELP_ASSISTANT_ENABLED`** (off by
  default), **independent** of `CALLOSUM_ALLOW_DATA_EGRESS` — the bot sends only the question + the public
  help docs, never library text, so it works with the library gate off. Enforced at the inc-58 seam.
- **Verify:** pytest **217** (+7: answer+refs, gate-independence, hole-closed 503, unknown-id drop, 422,
  parse degradation, provider self-check); live E2E (`.local/help_assistant_e2e/`, **library egress off**)
  — ask → answer + chips → chip scroll+flash, 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc60.zip` (or remove the new files + the
  `18_help.jsx` chat + the egress wrapper + the `/help/ask` handler + the config field, rebuild).

## 2026-06-20 — Help corpus + navigable help modal (increment 59)

- **Files:** new `app/backend/help/{help_content.md, corpus.py, __init__.py}`,
  `app/backend/api/routers/help.py` (`GET /help/corpus`), `app/backend/api/app.py` (wire router);
  `app/frontend/js/18_help.jsx` (rewrite) + `styles.css`; `tests/test_help.py`, `tests/test_health.py`
  (route surface); rebuilt `callosum-app.html`. Audit: `.claude/security-audits/2026-06-19_help-corpus.md`.
  Notes: `INCREMENT-59-NOTES.md`.
- **What:** the in-app help is now extensive end-user documentation served as a structured **corpus**
  (22 sections, stable anchor ids) and rendered in a **navigable two-column modal** (TOC + sections +
  scroll-to-flash). Replaces the old single hard-coded tips block.
- **Why:** a real help surface (groundwork for the inc-60 AI help assistant, whose references deep-link to
  these stable section ids); first pass generated by **Codex** to save Claude-Code tokens, then reviewed
  against the real code and shipped.
- **Also:** introduced the `HELP-DOCS-SYNCED` changelog-marker convention (above) + a CLAUDE.md
  start-of-session check, so future sessions can tell from the changelog whether the corpus needs updating.
- **Verify:** pytest **210** (+7); live E2E (`.local/help_e2e/`) — 22 sections render, TOC scroll+flash,
  0 console errors; audit PASS. Backend-only egress posture (the corpus endpoint is ungated, app-owned).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc59.zip` (or remove `app/backend/help/`
  + `routers/help.py` + the `18_help.jsx` rewrite, restore the static HelpModal, rebuild).

## 2026-06-19 — Provider-agnostic egress gate at the DI seam (increment 58)

- **Files:** new `app/backend/llm/egress.py` (+`__init__.py`); `integrations/gemini/generator.py`
  (re-export `DataEgressDisabledError`); `app/backend/api/routers/summaries.py` + `routers/axes.py`
  (wrap at `_summary_generator` / `_axis_term_suggester` / `_axis_cluster_labeler`);
  `tests/conftest.py` (autouse egress-consent default); `tests/test_summaries.py` + `tests/test_axes.py`
  (+4 tests). Audit: `.claude/security-audits/2026-06-19_egress-gate-seam.md`. Notes:
  `INCREMENT-58-NOTES.md`.
- **What:** moved data-egress enforcement from per-provider self-checks to a **provider-neutral gate at
  the DI seam**, applied in all three Gemini provider factories so an **injected** provider can no longer
  bypass the egress check. `DataEgressDisabledError`'s canonical home is now the neutral module
  (re-exported from Gemini). Provider self-checks kept as defense-in-depth.
- **Why:** closed the hole where `create_app(summary_generator=…)`/suggester/labeler instances were
  returned unchecked — invariant #3 is now enforced at the boundary, not by convention.
- **Verify:** pytest **203** (+4: hole-closed + behavior-preserved for the generator/suggester/labeler);
  re-export identity smoke test; route-surface invariant green; audit PASS. Behavior-preserving for the
  real Gemini path (egress-on → identical; egress-off → same `DataEgressDisabledError` → same 503).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc58.zip` (or remove `app/backend/llm/`,
  restore the local `DataEgressDisabledError` in `generator.py`, and revert the three factories +
  conftest fixture).
- **Housekeeping:** removed 25 stray `*.tmp.26380.*` atomic-write orphans left across the tree by an
  earlier crashed process.

## 2026-06-19 — Always-on Synthesis + contextual Details split (increment 57)

- **Files:** `app/frontend/js/20_synthesis.jsx` (`RightPane` tabs → vertical split); `app/frontend/js/40_app.jsx`
  (`_beginDrag` passes clientX **and** clientY); `app/frontend/styles.css` (`.pane-split`/`.rp-synth`/
  `.rp-detail`/`.divider-h`; removed dead `.pane-tabs`); rebuilt `callosum-app.html`. Notes:
  `INCREMENT-57-NOTES.md`.
- **What:** the right pane is no longer tabbed — **Synthesis stays on top always**, and selecting a paper
  shows its (editable) **Details in a lower section** with a draggable divider between them (height
  persisted to localStorage). No tab-switching; Details auto-appear when a paper is selected.
- **Why:** backlog F — elevate the inc-49 editable Details into the daily flow + keep the crown-jewel
  synthesis always visible (a coherent research workspace).
- **Verify:** pytest 199 (unchanged, frontend-only); live E2E (`.local/synthesis_split_e2e/`) — no-paper→
  Synthesis only, paper→both, drag resizes + persists across reload, 0 console errors. No audit gate.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc57.zip` (or revert RightPane + the CSS +
  the 1-line _beginDrag change, rebuild).

## 2026-06-19 — Duplicate detection (layered, flag-only) + review modal (increment 56)

- **Files:** `app/backend/clustering/duplicate_detection.py` (new — layered pairs + union-find);
  `api/routers/papers.py` (`_DedupJobStore`, `POST`/`GET /papers/duplicates`, models, `_run_dedup_job`,
  `_embedding_model`); `api/app.py` (`dedup_jobs` store); frontend `19_duplicates.jsx` (new modal) +
  `10_pdf_layer.jsx` ("Duplicates" button) + `40_app.jsx` (mount); `styles.css`; rebuilt
  `callosum-app.html`. Tests: `test_duplicate_detection.py` (+7), `test_papers.py` (+2), `test_health.py`
  (route surface). Docs: `INCREMENT-56-NOTES.md`, `.claude/security-audits/2026-06-19_duplicate-detection.md`.
- **What:** a **"Duplicates"** scan surfaces likely-duplicate paper groups with a confidence + reason,
  layered (shared PMID/arXiv → title+author+year → embedding ≥0.92, union-find). Flag-only: the user
  reviews each group and deletes the redundant copy (soft-delete → Trash) or inspects it; **merge deferred**.
- **Why:** backlog E — retroactively catch dups (preprint↔published, unresolved re-imports) that import-time
  identity dedup missed. Now well-set-up by G (clean identifiers) + inc-54 (trash as the resolution).
- **Verify:** pytest 199 (+9); live E2E (`.local/duplicates_e2e/`) — scan→group→delete→resolve, 0 console
  errors. Audit PASS (read-only, local, flag-only).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc56.zip` (or delete the new module +
  chunk, revert the endpoints/wiring, rebuild). No migration.

## 2026-06-19 — Fix: strip JATS from the editable abstract + suggest-axes terms (increment 55)

- **Files:** `app/backend/metadata/abstract_display.py` (new `abstract_plain_text`); `api/routers/papers.py`
  (`PaperDetailResponse.abstract_text`); `clustering/axis_suggestion.py` (`_paper_tokens` strips JATS);
  `app/frontend/js/25_detail.jsx` (abstract textarea → `abstract_text`); rebuilt `callosum-app.html`.
  Tests: `test_abstract_display.py` (+6), `test_papers.py` (+assertions), `test_axes.py` (+1). Notes:
  `INCREMENT-55-NOTES.md`.
- **What:** raw Crossref JATS XML was leaking — as `<jats:p>` tags in the editable abstract textarea
  (inc-49) and as the term "jats" in suggested axes (the c-TF-IDF tokenizer). A shared plain-text strip
  (`abstract_plain_text`) now feeds both (the textarea via a new `abstract_text` field; the tokenizer
  directly).
- **Why:** two user-reported leaks with one root cause (the abstract is stored raw JATS, inc-33).
- **Verify:** pytest 190 (+7); live E2E (`.local/jats_fix_e2e/`) — abstract textarea is tag-free, 0 console
  errors. Deferred: cleaning the abstract in the embedding text (`paper_embedding_text`) — needs a
  re-embed.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc55.zip` (or revert the 4 files, rebuild).

## 2026-06-19 — Library delete (soft) + multi-select + Trash / Restore (increment 54)

- **Files:** `alembic/versions/0004_paper_soft_delete.py` (new); `app/backend/persistence/schema.py`
  (`papers.deleted_at`); `repository.py` (`soft_delete_paper`/`restore_paper`, `list_papers` only_deleted,
  cluster-node filter); `clustering/axis_suggestion.py` (exclude trashed); `api/routers/papers.py`
  (`?deleted` listing + `DELETE /papers/{id}` + `POST /papers/{id}/restore`); frontend `40_app.jsx`
  (multi-select + trashView + handlers) + `10_pdf_layer.jsx` (checkboxes + bulk bar + Trash toggle +
  Restore) + `styles.css`; rebuilt `callosum-app.html`. Tests: `test_papers.py` (+4), `test_health.py`
  (route surface), `test_health.py`/`test_startup_migration.py` (head→0004). Docs:
  `INCREMENT-54-NOTES.md`, `.claude/security-audits/2026-06-19_library-delete.md`.
- **What:** the first way to delete a paper — checkbox multi-select + a bulk-delete bar (mirrors the
  inc-43 axis pattern) → **soft-delete** (a `deleted_at` stamp; hidden from library/axes/clustering but
  kept), with a **Trash ⇄ Library** toggle + per-row **Restore**.
- **Why:** the biggest CRUD gap. Soft because hard-delete orphans embeddings/vectors (no FK +
  no vector-store delete) and crashes retrieval — and soft is reversible, which the user wanted.
- **Verify:** pytest 183 (+4); live E2E (`.local/library_delete_e2e/`) — select→delete→trash→restore,
  0 console errors. Audit PASS. Permanent-delete/empty-trash deferred (needs vector cleanup).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc54.zip` (the additive `deleted_at`
  migration can stay; or revert the endpoints + frontend, rebuild).

## 2026-06-19 — Polish pass: SRI · radius scale · in-app HELP · favicon dark-swap (increment 53)

- **Files:** `app/frontend/index.html` (SRI integrity+crossorigin on React/ReactDOM/Babel; favicon split
  into 2 media-query links); `app/frontend/styles.css` (`--radius-sm/-lg/-pill` tokens + migrate
  pills/modal); `app/frontend/js/18_help.jsx` (new HelpModal) + `10_pdf_layer.jsx` (? button) +
  `40_app.jsx` (helpOpen + mount); `tools/inline_brand_assets.py` (two favicon targets); rebuilt
  `callosum-app.html`. Notes: `INCREMENT-53-NOTES.md`.
- **What:** four deferred quick wins — (1) Subresource Integrity hashes on the CDN scripts; (2) a radius
  scale (`--radius-sm/-lg/-pill`) with the clean pill/modal values migrated; (3) an in-app **? Help**
  viewer surfacing the axes/tiers tips from HELP.md; (4) the favicon swaps to the OS color scheme via
  `media="(prefers-color-scheme:…)"` links (no JS).
- **Why:** hardening (SRI) + DESIGN.md hygiene (radius tokens) + discoverability (help) + a dark-mode finish.
- **Verify:** pytest 179 (unchanged, frontend-only); live E2E (`.local/polish_e2e/`) — app renders under
  SRI (hashes correct), both favicon links present, help modal opens, 0 console errors. No audit gate.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc53.zip` (or revert the index.html SRI +
  favicon, the styles.css radius tokens, delete 18_help.jsx + its wiring, rebuild).

## 2026-06-19 — Suggest optimal axes (unsupervised discovery + coverage-with-diversity) (increment 52)

- **Files:** `app/backend/clustering/axis_suggestion.py` (new — cluster + novelty filter + MMR-lite +
  local c-TF-IDF labels + `apply_labels`); `integrations/gemini/axis_cluster_labeler.py` (new,
  egress-gated) + `__init__.py`; `app/backend/api/routers/axes.py` (`_AxisSuggestJobStore`, `POST
  /axes/suggest`, `GET /axes/suggest/{job_id}`, accessor, models); `app/backend/api/app.py` (inject
  labeler + suggest job store); `app/frontend/js/17_axes_suggest.jsx` (new) + `15_axes.jsx` (✨ button +
  modal) + `styles.css`; rebuilt `callosum-app.html`. Tests: `tests/test_axes.py` (+5),
  `tests/test_health.py` (route surface). Docs: `INCREMENT-52-NOTES.md`,
  `.claude/security-audits/2026-06-19_suggest-axes.md`.
- **What:** a ✨ Suggest button mines the library's embeddings → proposes a diverse set of candidate axes
  that don't duplicate each other or existing axes → the user curates (rename + toggle term chips) and
  creates the ones they like. Labels are local-from-your-papers (always) with optional egress-gated
  Gemini polish (degrades to local; never 503).
- **Why:** the AI-clustering finally surfaces *as discovery* — a new user no longer faces a blank axes
  panel; coverage-with-diversity ensures suggestions blanket the literature.
- **Verify:** pytest 179 (+5); live E2E (`.local/suggest_axes_e2e/`, fake model, no network) — ✨ → cards
  → create → axis appears, 0 console errors. Audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc52.zip` (or delete the two new modules
  + the new frontend chunk, revert the axes.py/app.py/15_axes.jsx wiring, rebuild). No migration.

## 2026-06-19 — B′: eyeball toggle to hide/show UNCERTAIN papers (increment 51)

- **Files:** `app/frontend/js/15_axes.jsx` (`AxisItem` `hideUncertain` state + 👁 toggle in the
  re-score row + filtered list + "show" restore hint); `app/frontend/styles.css` (`.axis-eye`,
  `.axis-eye-hint`); rebuilt `callosum-app.html`. Notes: `INCREMENT-51-NOTES.md`.
- **What:** an eye toggle (shown only when an axis has uncertain papers) collapses the list to an
  assigned/manual-only view; a "N uncertain hidden — show" hint restores them.
- **Why:** a focused, assigned-only view of an axis once the user has triaged the uncertain tier
  (pairs with inc-45's cutoff + inc-50's ✓-confirm). Pure display filter — no backend.
- **Verify:** pytest 174 (unchanged); live E2E (`.local/eye_e2e/`) — hide/show works, 0 console errors.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc51.zip` (or revert the 15_axes.jsx +
  styles.css changes, rebuild).

## 2026-06-19 — Axes manual-assignment cleanup (B) + library focus-mode add (C) (increment 50)

- **Files:** `app/backend/clustering/axis_scoring.py` (`add_manual_assignment` upsert-to-NULL;
  `restore_manual_assignments` force-NULL even when present); `app/frontend/js/15_axes.jsx`
  (AxisTierBadge drops the assigned tag; AxisPaperRow ✓-confirm; ＋ enters focus; AddPaperPicker
  removed; `axisRefresh`); `10_pdf_layer.jsx` (Sidebar forwards focus props; PaperList focus card +
  per-row add buttons); `40_app.jsx` (focus state + handlers); `styles.css` (`.axis-confirm`,
  `.focus-card`, `.paper-axis-add`); rebuilt `callosum-app.html`. Tests: `tests/test_axes.py` (+2).
  Docs: `INCREMENT-50-NOTES.md`, `.claude/security-audits/2026-06-19_axes-manual-assignment.md`.
- **What:** (B) the redundant ASSIGNED tag is gone (assigned = no tag; amber = uncertain; dashed =
  manual) and a **✓** on uncertain rows promotes them to a manual override; (C) the axis **＋** opens a
  **library focus-mode** (reminder card + per-row +add/−remove buttons) to add the papers the scorer
  missed, **staged and committed on Save**. The inc-38 in-card AddPaperPicker is retired.
- **Why:** the axes panel is the AI-clustering surface; its manual-override UX was cramped + the tags
  obscured titles. Confirms/manual-adds must survive re-scores → `confidence IS NULL` is now the single,
  durable encoding of a human override (fixes a latent revert-on-re-score bug too).
- **Verify:** pytest 174 (+2); live E2E (`.local/axes_manual_e2e/`, fake model) — no ASSIGNED tag,
  ✓→manual, focus card + Save commits, 0 console errors. Audit PASS (no new endpoint/surface).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc50.zip` (or revert the two
  axis_scoring.py functions + the four frontend files, rebuild). No migration to undo.

## 2026-06-19 — Editable Details pane (Mendeley-style) + DOI correction / re-resolve (increment 49)

- **Files:** `app/backend/metadata/paper_edits.py` (new — `build_paper_update`, the safe partial
  csl_json merge + column projection); `app/backend/metadata/enrichment.py` (`USER_EDITED_SOURCE` +
  `force` flag); `app/backend/api/routers/papers.py` (`PaperUpdateRequest`, `PATCH /papers/{id}`,
  `POST /papers/{id}/re-resolve`, `_crossref` accessor); `app/backend/api/app.py`
  (`crossref_client` injectable); `app/frontend/js/25_detail.jsx` (new — inline-editable pane),
  `20_synthesis.jsx` (DetailContent removed → forwards `onOpenPaper`), `40_app.jsx`
  (`onOpenPaper=openPdf`), `styles.css` (`.detail-edit*` recipe; dead `.detail-title`/`.author-list`/
  `.abstract` removed); rebuilt `callosum-app.html`. Tests: `tests/test_paper_edits.py` (new),
  `tests/test_papers.py` (+9), `tests/test_health.py` (route surface). Docs: `INCREMENT-49-NOTES.md`,
  `.claude/security-audits/2026-06-19_paper-edit-doi.md`, `.claude/DESIGN.md` (§2 inline-editable variant).
- **What:** The Detail pane is now a Mendeley-style **always-editable** bibliographic editor (inline
  fields, "Add …" placeholders, auto-save on blur, Literature Type dropdown, collapsible Identifiers,
  a "More" section that auto-surfaces extra DOI-populated fields, a Files list, honest provenance). A
  wrong/missing **DOI can be corrected and re-fetched from Crossref** (🔎). No schema migration —
  `csl_json` is already the canonical record; scalar columns are projections kept in sync.
- **Why:** "reference manager first" — metadata quality is upstream of everything (clustering, dedup,
  citations, synthesis); fixing a DOI and re-resolving is table-stakes for a Zotero/Mendeley replacement.
- **Verify:** pytest 172 (+22); live E2E (`.local/detail_edit_e2e/`, fake Crossref) — inline edit
  auto-saves (prov→user-edited), re-resolve fills metadata (prov→crossref), 0 console errors. Audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc49.zip` (or delete `paper_edits.py` +
  `25_detail.jsx`, revert the PATCH/re-resolve routes + `crossref_client`, restore DetailContent in
  `20_synthesis.jsx`, rebuild). No migration to undo (`scoring_gain` head 0003 unchanged).

## 2026-06-19 — Sidebar density (axis filter + green "+") + cutoff acts on displayed precision (increment 48)

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (drop "local reference workbench" subtitle);
  `app/frontend/js/15_axes.jsx` (filter state + `Filter axes…` input, "+ new"→green "+", one no-wrap
  controls row, `visibleAxes` filter, no-match hint); `app/frontend/styles.css` (`.axis-controls`/
  `.axis-filter`, green `.axis-new`, removed dead `.axis-head-actions` + `.brand .sub`);
  `app/backend/clustering/axis_scoring.py` (`_confidence_from_cosine_distance` rounds to 2dp);
  `tests/test_axes.py` (+1) → rebuilt `callosum-app.html`. Notes: `INCREMENT-48-NOTES.md`.
- **What:** (1) Rest of B″ density — removed the subtitle, added an axis **filter** (matches title or
  terms), turned "+ new" into a green **"+"**, all controls on one no-wrap row → more axes visible.
  (2) **Cutoff rounding:** confidences now stored/compared at the 2 decimals the UI shows, so a paper
  displayed as "0.35" can't be tagged UNCERTAIN because its raw score was 0.349 (user-caught).
- **Why:** density (power-user sees more axes) + honesty (displayed number == the number that decides the
  tier).
- **Verify:** pytest 150 (+1 rounding unit test); live E2E (`.local/density_e2e/`) — subtitle gone, filter
  narrows/restores, controls one row (no wrap), 0 console errors. Frontend density is rebuild-only; the
  rounding affects new scores (re-score to apply).
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc47.zip` + rebuild.

## 2026-06-19 — Connection status shown by the logo (increment 47)

- **Files:** `app/frontend/styles.css` (4 `--logo-*` bg-image tokens + `.brand-logo` div rules
  theme×.connected; removed dead `.brand-logo-light/dark` + `.conn`/`.led*`); `app/frontend/js/10_pdf_layer.jsx`
  (two `<img>` → one status `<div>`; removed `ConnStatus` + usage); `tools/inline_brand_assets.py` (logo
  targets → 4 CSS tokens); recompressed `app/media/logo_on.png` + `logo_dm_on.png` (423KB→~57KB) → rebuilt
  `callosum-app.html`. Notes: `INCREMENT-47-NOTES.md`.
- **What:** The brand logo now indicates connection — a green dot in the brain's cell-body when connected
  (the user's `logo_on`/`logo_dm_on` assets) — replacing the `● connected · local-verifier-v1` text line.
  Driven as a 4-state CSS background-image (theme × `.connected`); base64 lives in CSS (not the Babel
  script, avoiding the 500KB deopt).
- **Why:** declutter the header (B″ density step) while keeping the signal, using the user's assets.
- **Verify:** pytest 149 (frontend-only); live E2E (`.local/conn_logo_e2e/`) — `.connected` class, `.conn`
  text gone, bg-image swaps on connection + theme, 0 console errors (no Babel note); dark screenshot shows
  the green dot. No backend/migration/egress.
- **Revert:** restore `styles.css`/`10_pdf_layer.jsx`/`inline_brand_assets.py` + `logo_on.png`/`logo_dm_on.png`
  from `.claude/backups/callosum_claudecode_inc46.zip`, + rebuild.

## 2026-06-19 — DESIGN.md token consolidation + dark mode + Settings modal (increment 46)

- **Files:** `app/frontend/styles.css` (new chrome tokens + `:root[data-theme="dark"]` override + hex→token
  replacements + `--on-fill` + settings/logo-toggle CSS); `app/frontend/index.html` (no-flash theme
  bootstrap in `<head>`); `app/frontend/js/10_pdf_layer.jsx` (two themed brand logos + gear button); new
  `app/frontend/js/35_settings.jsx` (`SettingsModal`); `app/frontend/js/40_app.jsx` (theme + settings
  state); `tools/inline_brand_assets.py` (light+dark logo targets); recompressed `app/media/logo_dm.png`
  (427KB→57KB, lossless) → rebuilt `callosum-app.html`. Docs: `.claude/DESIGN.md` (tokens + §1b Dark theme
  + §3 status), `.claude/CLAUDE.md`, audit `.claude/security-audits/2026-06-19_dark-mode-settings.md`,
  `INCREMENT-46-NOTES.md`.
- **What:** Finished DESIGN.md's color-token consolidation (scattered hex → tokens; split destructive color
  reconciled to `--danger`) and added a **warm-dark theme** via `data-theme` + CSS-variable overrides,
  toggled in a new sparse **Settings modal** (gear icon in the sidebar). No-flash bootstrap; theme-matched
  logo swap; the **rendered PDF page stays light** in both themes; `--on-fill` keeps text legible on the
  now-light semantic fills.
- **Why:** "wrap up DESIGN.md" + add dark mode — the token consolidation IS the dark-mode groundwork; the
  Settings modal establishes the prefs surface (backlog H).
- **Verify:** pytest 149 (frontend-only, unchanged); live E2E (`.local/dark_mode_e2e/`) — toggle dark→
  `data-theme=dark` + `--bg`=#1a1815 + logo swap, persists across reload (no flash), back to light, 0
  console errors; audit PASS. HTML 989KB→495KB after the dark-logo recompress.
- **Revert:** restore the listed frontend files + `inline_brand_assets.py` + `logo_dm.png` from
  `.claude/backups/callosum_claudecode_inc45.zip`, delete `35_settings.jsx`, + rebuild.

## 2026-06-19 — Design dictionary (`DESIGN.md`) + badge-encodes-scoring-status

- **Files:** new `.claude/DESIGN.md`; `.claude/CLAUDE.md` (rule #8 "read DESIGN.md before any CSS change" +
  reference-table + 2 decision-log rows); `.claude/docs/INCREMENT-BACKLOG.md`; `app/frontend/js/15_axes.jsx`
  (badge status class, removed the `.axis-state` text line) + `styles.css` (badge color modifiers; dropped
  the dead `.axis-state`/`.axis-flag-*` rules) → rebuilt `callosum-app.html`.
- **What:** (1) Created **`DESIGN.md`** — a two-pass design dictionary (Pass 1 = the CSS as-is: tokens +
  element recipes; Pass 2 = inconsistencies + canonical rules + a consolidation worklist, e.g. the split
  destructive colors `--flag` vs `#b3261e`, three indigos, repeated hover/border hexes, ~10 near-duplicate
  buttons). CLAUDE.md now **requires reading it before any CSS/inline-style edit** (rule #8). (2) The axis
  **count badge now encodes scoring status by color** — green `--verified` (scored & fresh), amber `--flag`
  (`.is-stale`, edited → re-score), muted `--line-2` (not scored) — and the textual `.axis-state` status
  line was **removed** (status lives in the badge color + tooltip; reclaims sidebar density).
- **Why:** set the design tether *before* the upcoming UI wave (sidebar density, settings + dark mode,
  synthesis redesign) to prevent design-by-committee drift; the badge change is a first dictionary-driven
  consistency decision (status-by-color, not by text).
- **Verify:** live check (`.local/badge_status_e2e/`) — `.axis-state` gone, badge neutral→green on score,
  0 console errors; build clean (`15_axes.jsx` 376). No backend change (pytest unaffected, 149).
- **Revert:** delete `DESIGN.md`, revert the CLAUDE.md rule/rows + the `15_axes.jsx`/`styles.css` badge
  edits, + rebuild.

## 2026-06-19 — Adjustable assignment cutoff ("gain") + axis-card redesign (increment 45)

- **Files:** `schema.py` (`axes.scoring_gain`); `alembic/versions/0003_axis_scoring_gain.py`;
  `app/backend/clustering/axis_scoring.py` (absolute-cutoff badge + shared never-empty helper);
  `app/backend/api/routers/axes.py` (`DEFAULT_AXIS_CUTOFF`, score `gain` param + clamp + persist, read
  re-tiers by axis cutoff, `AxisResponse.scoring_gain`); `tests/test_axes.py`, `tests/test_health.py`,
  `tests/test_startup_migration.py`; `app/frontend/js/15_axes.jsx` (card icon buttons + red count badge +
  Re-score/cutoff-flipper row, tip removed) + `styles.css` → rebuilt `callosum-app.html`. New
  `.claude/HELP.md`. Audit: `.claude/security-audits/2026-06-19_axis-gain.md`. Notes: `INCREMENT-45-NOTES.md`.
- **What:** Replaced inc-39's relative natural-break badge (which assigned only the top 2–6 papers — the
  largest gap sits near the top of smooth declines) with an **absolute cutoff** (default 0.35), now a
  **per-axis, persisted, user-adjustable** value (a "Cutoff" flipper on the Re-score row). Redesigned the
  axis card: ✎/＋/🗑 icon buttons (＋ auto-expands + opens the picker; ✎ doesn't expand) + a circular red
  count badge; Re-score is the lone in-list control. Moved the relative-tiers tip to `.claude/HELP.md`.
- **Why:** the dynamic cut was systematically too exclusive (user evidence across 3 axes); 0.35 captures
  the relevant ~half, and the user wanted it tunable as the library grows.
- **Verify:** pytest 149 (+1 cutoff-persistence; recalibrated fake model; head→0003); live E2E
  (`.local/axis_gain_e2e/`) — card icons + badge, ✎ no-expand, ＋ expands, flipper persists `scoring_gain`
  across reload, tip gone, 0 console errors; audit PASS. Additive migration 0003 (auto-applies on startup);
  existing axes re-tier at 0.35 on read — no re-score needed.
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc44.zip`, drop the
  `scoring_gain` column (or `alembic downgrade`), + rebuild.

## 2026-06-19 — Fix (interim): axis edit modal lost its term pills on reopen when the description was blank

- **Files:** `app/frontend/js/16_axes_merge.jsx` (`_axisBase`/`_axisRelatedTerms` parser) → rebuilt
  `callosum-app.html`; also removed stray `app/frontend/js/*.jsx.tmp.*` files (interrupted-write leftovers).
- **What:** Editing an axis to clear the description prose, then saving, composed the description as just
  `"Related: …"` (no leading blank line, since the empty prose is dropped before `join("\n\n")`). The
  parser split only on the literal `"\n\nRelated:"`, so on reopen it failed to recover the terms — the
  pills vanished and the whole `"Related: …"` string showed up in the description box. Fixed the parser to
  split on any `Related:` marker (with/without leading newlines, multiple blocks) + case-insensitively
  dedupe; it now round-trips empty-prose axes and also cleans up the double-`Related:` descriptions old
  merges left.
- **Why:** user hit it on resting-state after clearing the description and adding many terms; the string
  *looked* editable so they deleted it (a UX trap any user would fall into).
- **Verify:** live E2E (`.local/axis_terms_roundtrip_e2e/`) — empty-prose axis with 3 terms survives
  save→reopen as 3 pills, description box empty, 0 console errors. Frontend-only (hard-reload). pytest 148
  (unchanged).
- **Note:** this is the **interim** fix. The real fix (next increment) promotes the terms to a first-class
  field separate from the description prose, so the `"Related:"`-in-description convention — and this whole
  class of parsing bug — goes away. (Per the user: "the pills should effectively replace 'Related:'
  tracking via string in the description.")
- **Revert:** restore `16_axes_merge.jsx` from `.claude/backups/callosum_claudecode_inc44.zip` + rebuild.

## 2026-06-19 — Fix: axis perpetually "re-score" after merge + restore the 600-line cap

- **Files:** `app/backend/clustering/axis_scoring.py` (`axis_score_state` membership check; trimmed
  `_axis_text`/`_embed_axis` comments back under 600); `tests/test_axes.py` (+1 regression test).
- **What:** An axis could show "description changed — re-score" forever even right after re-scoring.
  Root cause: `_embed_axis` adds one embedding row per distinct scored text version and never prunes, and
  `axis_score_state` judged freshness from the **newest row by id**. A merge/edit cycle that revisits a
  prior text version leaves a stale row with a *higher* id than the row matching the current text →
  perpetually stale. Fix: an axis is fresh if **any** stored embedding matches the current text
  (`score_axis` always embeds the current text, so a match means the live assignments reflect it).
  Self-heals existing DBs on the next `/axes` read — no re-score needed. Also fixes a 600-line-cap
  violation: the inc-44 `_axis_text` comment had pushed `axis_scoring.py` to 603 → trimmed to 598.
- **Why:** user hit it on `anomalous-is-bad` after merging two related axes (`resting-state` was unaffected
  because its newest row happened to match); confirmed by replaying `axis_score_state` on the live DB
  (now `stale=False`). The newest-by-id heuristic was simply wrong given accumulating embedding rows.
- **Verify:** pytest 148 (+1: freshness survives text revisiting a prior scored version); read-only replay
  on `.local/validation-summarize/validation.sqlite` → anomalous-is-bad/resting-state/major-depression all
  `stale=False`. Backend-only (restart uvicorn; no rebuild). Known minor follow-up: embedding rows still
  accumulate per axis (harmless — axis vectors aren't read for scoring; a future prune could tidy them).
- **Revert:** restore `axis_scoring.py` + `tests/test_axes.py` from `.claude/backups/callosum_claudecode_inc44.zip`.

## 2026-06-19 — Axis edit modal + title/term decoupling + click-to-open (increment 44, backlog A + A′)

- **Files:** `app/backend/clustering/axis_scoring.py` (`_axis_text` embeds description-only w/ label
  fallback); new `app/frontend/js/14_axes_edit.jsx` (`AxisEditModal`); `app/frontend/js/15_axes.jsx`
  (quick-name create, removed inline create/edit forms + old terms modal + `.axis-desc` preview, A′
  openPaper); `app/frontend/js/40_app.jsx` + `10_pdf_layer.jsx` (thread `onOpenPaper`); `styles.css`;
  `tests/test_axes.py` (+2 tests) → rebuilt `callosum-app.html`. Audit:
  `.claude/security-audits/2026-06-19_axis-edit-modal.md`. Notes: `INCREMENT-44-NOTES.md`.
- **What:** One **Edit Axis modal** for create/edit/term-search. The **title is now a cosmetic display
  name**; the search vocabulary is a curated terms list (stored in the description's `Related:` block,
  primary term first, embedded — the label is no longer the query). Suggested terms are **deselected by
  default** (selected sort to top). Clicking an axis-listed article **opens its PDF** (A′).
- **Why:** name a lens naturally without the name polluting the embedding; consolidate scattered forms;
  keep the human in the loop on AI terms; make the axes panel a clickable library overview.
- **Verify:** pytest 147 (+2: scoring keys on description not label; label-only fallback); live E2E
  (`.local/axis_edit_e2e/`) — deselect-by-default, no `.axis-desc`, click-to-open PDF, 0 console errors;
  audit PASS. No migration, no new egress/endpoint (existing axes show stale → re-score once).
- **Revert:** delete `14_axes_edit.jsx`, restore `axis_scoring.py`/`15_axes.jsx`/`40_app.jsx`/
  `10_pdf_layer.jsx`/`styles.css`/`tests/test_axes.py` from `.claude/backups/callosum_claudecode_inc43.zip`
  + rebuild.

## 2026-06-19 — Axis management: sort + multi-select + bulk delete + curated merge (increment 43)

- **Files:** new `app/backend/clustering/axis_operations.py` (`merge_axes`); `app/backend/api/routers/axes.py`
  (`POST /axes/merge` + `MergeAxesRequest` + `created_at` on `AxisResponse`); `tests/test_axes.py`,
  `tests/test_health.py`; `app/frontend/js/15_axes.jsx` (sort select + checkbox multi-select + bulk bar) +
  new `app/frontend/js/16_axes_merge.jsx` (`MergeAxesModal` comparison view) + `styles.css` → rebuilt
  `callosum-app.html`. Audit: `.claude/security-audits/2026-06-19_axis-merge.md`. Notes: `INCREMENT-43-NOTES.md`.
- **What:** The Axes panel is now sortable (name / paper count / newest), supports checkbox multi-select with a
  bulk-action bar (delete N, or merge ≥2), and a **merge** that consolidates axes into one surviving axis via a
  comparison/curation view — you pick which axis's identity survives and curate the merged label + description.
  Each folded axis's label is carried into the survivor's `Related:` terms by default, so a re-score keeps the
  papers each source axis used to surface discoverable; manual assignments are unioned; the survivor auto-re-scores.
- **Why:** as axes accumulate (esp. after the inc-41 synonym suggester), the user needs to order, bulk-act on, and
  consolidate near-duplicate lenses without losing the vocabulary that made each one find its papers.
- **Verify:** pytest 145 (merge + validation tests; route-surface invariant adds `/axes/merge`); live E2E
  (`.local/axes_manage_e2e/`) — sort, multi-select, comparison-view merge (folded label → `Related:`), bulk delete,
  0 console errors; security audit PASS. No migration, no egress.
- **Revert:** delete `axis_operations.py` + `16_axes_merge.jsx`, restore `axes.py`/`15_axes.jsx`/`styles.css`/tests
  from `.claude/backups/callosum_claudecode_inc42.zip` + rebuild.

## 2026-06-19 — Resizable + collapsible side panels (increment 42)

- **Files:** `app/frontend/js/40_app.jsx` (Divider component + drag/collapse + persisted layout state),
  `app/frontend/styles.css` (divider/collapsed styles; removed the narrow-screen media query) → rebuilt
  `callosum-app.html`. Notes: `INCREMENT-42-NOTES.md`.
- **What:** The left (Axes) and right (Synthesis) panels are now drag-resizable and collapsible via a
  divider with a grip + chevron toggle; the center PDF/library area expands as a side collapses. Widths +
  open/closed state persist to localStorage. Frontend-only; no backend/migration/egress (no audit).
- **Why:** let users focus on the PDF viewer and tune the layout.
- **Verify:** pytest 143 (Python untouched); live E2E — collapse/expand both panels, drag-resize, center
  widens, 0 console errors.
- **Revert:** restore the two frontend files from `.claude/backups/callosum_claudecode_inc41.zip` + rebuild.

## 2026-06-19 — Gemini axis synonym suggester (increment 41)

- **Files:** new `integrations/gemini/axis_terms.py` + `__init__` export; `app/backend/api/app.py`
  (`axis_term_suggester` wiring); `app/backend/api/routers/axes.py` (`POST /axes/suggest-terms` + accessor
  + models); `tests/test_axes.py`, `tests/test_health.py`; `app/frontend/js/15_axes.jsx` + `styles.css`
  (suggest-terms modal) → rebuilt `callosum-app.html`. Audit:
  `.claude/security-audits/2026-06-19_axis-term-suggester.md`. Notes: `INCREMENT-41-NOTES.md`.
- **What:** Optional AI assist to broaden niche axes: Gemini proposes related terms, the user curates
  them in a **modal**, and the chosen terms fold into the axis description (re-score to apply). New
  `POST /axes/suggest-terms` (sync, stateless) is **egress-gated** (off → 503 guidance; other failure →
  502, never 500); untrusted model output is deduped/capped/echo-stripped. Human-in-the-loop + transparent
  (terms are visible/editable text in the description). No migration.
- **Why:** raise recall on niche axes (e.g. surface more than the literal phrasing matches) while keeping
  the human in control and the default local-first path intact.
- **Verify:** pytest **143** (140 + 3 new: terms returned, empty-label 422, egress-off→503 hermetic,
  `_parse_terms` cleaning); live E2E (curate → apply → description folded, 0 console errors). Audit: PASS.
- **Usage:** set `CALLOSUM_ALLOW_DATA_EGRESS=1` + `GOOGLE_API_KEY`, restart, then "suggest terms" on an axis.
- **Revert:** restore the listed files (and delete `integrations/gemini/axis_terms.py`) from
  `.claude/backups/callosum_claudecode_inc40.zip`.

## 2026-06-19 — Axis punctuation normalization (increment 40)

- **Files:** `app/backend/embeddings/models.py` (`strip_punctuation`), `app/backend/clustering/axis_scoring.py`
  (apply to `_embed_axis` + `axis_score_state`), `tests/test_axes.py`. Notes: `INCREMENT-40-NOTES.md`.
- **What:** Axes differing only in punctuation/spacing scored differently ("anomalous-is-bad" vs
  "anomalous is bad"; "resting-state" vs "resting state") because `normalize_text` keeps punctuation, so
  MiniLM tokenizes them differently. Now the axis text is run through a new `strip_punctuation` util
  (punctuation/underscores → spaces, unicode-aware) before embedding + text-versioning, so equivalent
  phrasings produce an identical axis embedding → identical results. Axis-side only — no paper re-embed,
  no migration, no frontend change.
- **Why:** equivalent axis phrasings should give the same results.
- **Verify:** pytest **140** (138 + 2 new: a `strip_punctuation` unit test + an integration test where
  two punctuation-variant axes score identically under a punctuation-sensitive fake model).
- **User action:** re-score existing punctuated axes once (they'll show stale).
- **Revert:** restore the two source files from `.claude/backups/callosum_claudecode_inc39.zip`.

## 2026-06-18 — Axis scoring calibration: natural-break relative tiering (increment 39)

- **Files:** `app/backend/clustering/axis_scoring.py` (+`natural_break` mode + 2 helpers),
  `app/backend/api/routers/axes.py` (`SUPERVISED_AXIS_CONFIG`; relative read tier),
  `app/frontend/js/15_axes.jsx` + `styles.css` (relative caption) → rebuilt `callosum-app.html`,
  `tests/test_axes.py`. Notes: `INCREMENT-39-NOTES.md`.
- **What:** Inc-38's absolute thresholds (assigned ≥0.7 / uncertain ≥0.5) assigned **nothing** on real
  data — `all-MiniLM-L6-v2` axis-vs-paper-metadata cosine maxes ~0.37 (median 0.02), though the ranking
  is correct. Switched to **natural-break relative tiering**: assigned = the cluster above the largest
  gap in the axis's ranking (above a 0.2 MiniLM-calibrated noise floor), uncertain = the rest of the
  eligible, never-empty fallback shows the closest few. Tiers are **recomputed on read** from the
  stored confidences (no migration; read == score). Raw similarity still shown honestly.
- **Why:** make supervised axes actually surface relevant papers (validated: the anomalous-is-bad axis
  now assigns its facial-difference papers, excludes off-topic ones).
- **Verify:** pytest **138** (136 + 2 new); real-data read-only check + live E2E (tiers populate, 0
  console errors). Users must **re-score** axes scored under the old logic.
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc38.zip`.

## 2026-06-17 — Axes increment 1: create / browse / score / correct user-defined axes (increment 38)

- **Files:** `app/backend/clustering/axis_scoring.py` (new reuse helpers), `app/backend/api/routers/axes.py`
  (6 new mutations + 1 GET + async score job + extended reads), `app/backend/api/app.py`
  (`axis_score_jobs` wiring), `tests/test_health.py` (route surface), `tests/test_axes.py` (hermetic
  suite), `app/frontend/js/15_axes.jsx` (new AxesPanel) + `10_pdf_layer.jsx`/`40_app.jsx`/`styles.css`,
  rebuilt `callosum-app.html`. Notes: `INCREMENT-38-NOTES.md`; audit:
  `.claude/security-audits/2026-06-17_axes-supervised.md`.
- **What:** Exposed the existing `axis_scoring.py` engine as write endpoints + UI. Create an axis from
  a label + description; score it (async job, `assignment_mode="absolute"` → assigned ≥0.7 / uncertain
  ≥0.5 / below-threshold not stored); browse assigned papers by honest tier + confidence; manually
  add/remove papers (human override, `confidence IS NULL` = manual vs scored float); edit (→ stale until
  re-scored, via the axis embedding's text-version) and delete (CASCADE, axis-tree only). Re-score
  preserves manual adds. **No migration, no egress** (scoring is fully local).
- **Why:** the Axes sidebar panel was read-only/inert; this makes user-defined axes usable end-to-end
  (increment 1 of a staged feature; unsupervised clustering / synthesis-scope / multi-pole deferred).
- **Verify:** pytest **136 passed** (129 + 7 new, route-surface updated); hermetic fake-model tiers,
  stale, re-score-preserves-manual, manual add/remove, narrow cascade, graceful model-unavailable.
  Live browser E2E: create → score → tiers (1 assigned / 1 uncertain, far excluded) → manual-add,
  **0 console errors**. Security audit: PASS.
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc37.zip` (pre-inc-38).

## 2026-06-17 — Restore `callosum-app.html` as a generated build artifact (inc 37 follow-up)

- **Files:** new `tools/build_frontend.py`; `app/backend/api/app.py` (serve precedence); regenerated
  `callosum-app.html`.
- **What:** Kept the modular `app/frontend/` source, but `tools/build_frontend.py` now rebuilds the
  single-file `callosum-app.html` from it (verified **byte-identical** to the pre-split original,
  CRLF and all). The `/` route serves that file by default (restoring the prior behavior file-based
  UI testing relies on), with live assembly as the fallback when it's absent.
- **Why:** preserve the user's existing frontend-testing workflow, which expects that particular file.
- **Verify:** `python tools/build_frontend.py` → 375312 bytes, identical to the original; `GET /`
  serves it (200, text/html, app markers present); pytest **129**.
- **Revert:** delete `callosum-app.html` + `tools/build_frontend.py` and restore the default-assembly
  `/` route.

## 2026-06-17 — Modularize the monolith files (increment 37)

- **Files:** new `app/backend/api/{dependencies,startup,frontend}.py` + `app/backend/api/routers/*.py`;
  new `app/backend/pdf_processing/quote_matching.py`; new `tools/validation/{reports,report_renderer}.py`;
  new `app/frontend/{index.html,styles.css,js/*.jsx}`; new `tests/{conftest,api_helpers,test_papers,
  test_annotations,test_axes,test_summaries,test_health}.py`. Slimmed `app/backend/api/app.py`,
  `extraction.py`, `tools/validation_harness.py`. Deleted `callosum-app.html` + `tests/test_api.py`.
  Updated importers + `tools/inline_brand_assets.py`. Notes: `INCREMENT-37-NOTES.md`; audit:
  `.claude/security-audits/2026-06-17_frontend-assembly.md`.
- **What:** Behavior-preserving split of the oversized files at their natural joints into
  descriptively-named modules so directed code reviews touch one concern at a time. `app.py`
  1108→113 (factory + per-resource routers; only logic change: `/summarize*` read the job store via
  `request.app.state`). `extraction.py` 662→555 (+`quote_matching.py`). `test_api.py` →
  conftest + per-resource files. `validation_harness.py` 1298→898 (report dataclasses + markdown
  renderer extracted; probes stay — exempt tool). `callosum-app.html` 2023 → modular `app/frontend/`
  **assembled at serve time** into one document at `/` (no build step, no new file-serving surface;
  JSX concatenated into one `<script>` so the shared scope is identical).
- **Why:** `app.py`/`extraction.py` were over the 600-line hard limit (overdue standing-split tasks);
  the rest were unwieldy for review. Now **no file under `app/`/`integrations/` exceeds 600** (largest
  `extraction.py` 555).
- **Verify:** `pytest` **129 passed** after every phase; route-surface invariant green (no endpoint
  drift); inc-36 E2E re-run against the **assembled** frontend — reload-drift **0.0px**, **0 console
  errors** (faithful in-browser reassembly). Security audit: PASS.
- **Revert:** restore the affected files from `.claude/backups/callosum_claudecode_inc36.zip`
  (pre-increment-37 snapshot).

## 2026-06-17 — Synthesis → annotation bridge: save a citation as a highlight (increment 36 / suite C)

- **Files:** `app/backend/api/app.py`, `callosum-app.html`, `tests/test_api.py`,
  `INCREMENT-36-NOTES.md`, `.claude/security-audits/2026-06-17_synthesis-source.md`.
- **What:** A verified, exact-coordinate synthesis citation can now be **saved as a durable
  annotation** (`source="synthesis"`). Backend: `POST /papers/{id}/annotations` accepts an optional
  `source`, allowlist-validated (`NATIVE_ANNOTATION_SOURCES`, forged → 422), defaulting to `"user"`;
  the handler stopped hardcoding `"user"`. No new route, no migration. Frontend: a "Save as
  highlight" control on each `CitationCard`, **enabled only for exact+verified** citations and
  otherwise **disabled with a tooltip** (honesty contract); `App.saveCitationHighlight` POSTs the
  citation's bboxes/quote as a synthesis annotation and bumps an `annoRefresh` nonce so an open
  `PdfViewer` refetches **without a reload** (no-flicker effect). Synthesis highlights render with a
  distinct **dashed `.pdf-synthesis-outline`** marker (user choice: outline only; fill palette
  unchanged), drawn outside the multiply group so it stays crisp.
- **Why:** unite the ephemeral citation-overlay system with durable user highlights, so a machine-
  found passage becomes a first-class, annotatable highlight — without ever presenting a
  region/null/flagged citation as a precise highlight.
- **Verify:** pytest **129 passed** (126 + 3 new source accept/default/forged tests). Headless E2E
  (`.local/inc36_e2e/`, real uvicorn + real PDF, Chromium): gating proof (1 enabled / 1 disabled+
  tooltip), save persists `source="synthesis"`, **live refresh** (`.pdf-synthesis-outline` 0→1 with
  the tab open), **reload-drift 0.0px**, 0 console errors. Security audit: PASS.
- **Revert:** restore `app/backend/api/app.py` + `callosum-app.html` + `tests/test_api.py` from the
  pre-increment snapshot `.claude/backups/callosum_claudecode_inc33-35.zip`.

## 2026-06-17 — Fix multi-line highlight opacity doubling (increment 35)

- **Files:** `callosum-app.html`, `INCREMENT-35-NOTES.md`.
- **What:** A multi-line highlight's overlapping per-line rects double-filled the interior (darker
  band); the pre-existing per-fill `mix-blend-mode: multiply` didn't help (multiply compounds at
  overlap). Fix: wrap each annotation's rects in an isolated per-annotation group
  (`.pdf-user-highlight-group{position:absolute;inset:0;isolation:isolate;mix-blend-mode:multiply;opacity:0.7}`)
  with **opaque** per-line fills that union with no doubling; the group composites once → uniform on
  every row, darkening toward the text. Removed the per-fill multiply + inset border (would seam the
  union). No geometry change.
- **Why:** even, legible highlighting (worsens with the longer passages increment C will create).
- **Verify (headless):** 60-rect highlight — gap-row luminance top/mid/bottom 250.7/253.1/251.9 →
  **spread 2.4 (~1%)**, uniform; screenshot confirms no interior band; reload-drift **0.0px**; zoom
  unchanged. Citation overlay (low-alpha/bordered, transient) left as-is; text layer untouched.
  pytest **126 passed**.
- **Revert:** restore `callosum-app.html` from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-17 — Fix PDF text-layer/canvas misalignment (scale + DPR sync) (increment 34)

- **Files:** `callosum-app.html`, `INCREMENT-34-NOTES.md`.
- **What:** The invisible text layer drifted from the rendered PDF text (worse toward the page
  bottom) and desynced under zoom/HiDPI. Root causes: `Math.floor` truncation of the canvas/text
  containers vs un-floored span coords; responsive `width:100%`/`max-width:100%` shrinking the canvas
  but not the fixed-px text layer; no `devicePixelRatio`. Fix: every layer now derives from one
  `getViewport({scale})` with **exact un-floored CSS dims**; canvas backing store at device
  resolution (`round(css*dpr)` + a `[dpr,0,0,dpr,0,0]` render transform) with the exact CSS box;
  text layer + wrapper + overlays sized identically; removed the responsive shrink (too-wide pages
  scroll, `overflow:auto`); a `matchMedia` DPR listener re-renders on browser zoom/HiDPI change.
- **Why:** selection/highlighting requires the text layer to sit exactly over the visible text.
- **Verify (headless):** bottom-of-page drift **−7.97px → −0.20px** (wide@115%; regression across the
  full page −0.83px); narrow pane went from desynced to −0.20px; HiDPI dpr=2 backing now 2× with the
  exact CSS box (bottom offset −0.10). **Highlight reload-drift = 0.0px at 50/75/115/195% and dpr=2.**
  pytest 126 passed (frontend-only).
- **Revert:** restore `callosum-app.html` from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-17 — Loud startup auto-migration + honest /health migration check

- **Files:** `app/backend/api/app.py`, `tests/test_api.py`, `tests/test_startup_migration.py` (new).
- **What:** (1) The startup auto-migrate now **announces itself** — INFO "startup migration check:
  db=… current=… head=…", a WARNING "database auto-migrated … X -> Y" when it actually migrates, an
  INFO "already at head …" when not, and an ERROR (non-fatal) on failure. A minimal stdout logging
  setup + a `_loud()` helper keep these visible even though Alembic's `env.py` runs
  `fileConfig(disable_existing_loggers=True)` on every migrate (which had been silencing our logger
  mid-startup — the post-upgrade line would otherwise never appear). (2) `/health` is now **honest**:
  `db_migrated` means *at head* (compares the DB's current Alembic revision to head), not merely
  "some version stamped"; added `db_revision` + `db_head_revision` so a behind-DB is diagnosable from
  /health alone.
- **Why:** a silent schema mutation on the user's DB must be surfaced, and the health check that was
  supposed to warn of a behind-DB was lying (this is what hid the earlier silent-500).
- **Verify:** pytest 126 passed (behind-DB reports not-at-head; at-head reports up-to-date; startup
  emits the from→to WARNING + at-head INFO; a forced migration failure logs ERROR but is non-fatal and
  the app still serves /health). Sample real log lines captured (from→to + at-head). No schema change;
  env.py untouched; non-fatal-on-failure preserved.
- **Revert:** restore the two app/test files from the pre-change zip snapshot in `.claude/backups/`.

## 2026-06-17 — Clean JATS abstract rendering (increment 33)

- **Files:** `app/backend/metadata/abstract_display.py` (new), `app/backend/api/app.py`,
  `callosum-app.html`, `tests/test_abstract_display.py` (new), `tests/test_api.py`,
  `INCREMENT-33-NOTES.md`, `.claude/security-audits/2026-06-17_jats-abstract-display.md`.
- **What:** Crossref abstracts (stored raw as JATS XML) now render as clean structured text in the
  Detail pane instead of literal `<jats:…>` tags. New pure transform `clean_abstract_for_display`
  emits a small allowlist of attribute-free HTML (`p/em/strong/sub/sup`); `PaperDetailResponse`
  gains a derived `abstract_display` (raw `abstract` unchanged); the frontend renders it via the
  app's only `dangerouslySetInnerHTML` (allowlisted backend output).
- **Why:** readable abstracts (italics, bold, sub/sup for formulae/p-values) without mutating the
  faithful stored value (store raw, render structured).
- **Verify:** pytest 122 passed (real HBM + Alves fixtures, plain-text, malformed, entities/sub-sup,
  allowlist/security, purity, stored-unchanged API test); headless Firefox renders clean, no console
  errors. No schema/migration change.
- **Revert:** restore the listed files from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-17 — Fix: highlight create 500'd on stale (un-migrated) DBs + robustness

- **Files:** `app/backend/api/app.py`, `callosum-app.html`; plus migrated all
  `.local/**/validation.sqlite` to head.
- **Root cause:** the running DB predated increments 30/31 and lacked the `annotations`
  columns (`color`, …); every create-annotation INSERT returned **500**, and the frontend
  **swallowed the error silently** → "highlighting does nothing." Found via the user's
  uvicorn traceback (`table annotations has no column named color`).
- **What:** (B) **auto-migrate on startup** — `create_app`'s lifespan now runs
  `alembic upgrade head` (absolute `script_location`, defensive) against the configured DB,
  so the app self-heals any DB it opens. (C) **surface API errors** — `apiPost/apiPatch/apiDelete`
  `console.warn` on failure, and the annotation actions show a transient `.pdf-toast`
  ("Couldn't save highlight — …") instead of failing silently. (A) ran `alembic upgrade head`
  on all 10 existing `.local` validation DBs (`color` now present).
- **Why:** the code/migration were correct; the DB just hadn't run `0002`. Auto-migrate +
  visible errors prevent this class of silent failure recurring.
- **Verify:** end-to-end — a stale DB copy auto-migrated on startup (`color` false→true) and
  an HTTP create returned 201; Firefox highlight renders; a forced 500 shows the toast +
  console.warn. `pytest` 113 passed (lifespan auto-migrate doesn't affect the non-`with`
  TestClient tests). No schema/migration change (single head stays `0002`).
- **Revert:** restore the two files from the pre-change zip snapshot in `.claude/backups/`.

## 2026-06-17 — Highlight visibility + note-on-create affordance (annotation UX)

- **Files:** `callosum-app.html`.
- **What:** (1) Made user highlights clearly visible — overlay fill 0.38 → **0.55** alpha and a
  crisper inset edge (the old marker was so faint over the page that, since clicking a swatch also
  clears the blue text-selection, it read as "nothing happened"). (2) Added a **"✎ note" button to
  the create picker** (`createHighlightWithNote`) that makes the highlight and immediately opens the
  note editor — notes are no longer only reachable by clicking an existing highlight.
- **Why:** User reported highlighting "doesn't highlight" (it did — it persisted to the DB — but was
  too subtle) and that the create menu had no way to add a note.
- **Verify:** headless **Firefox** — highlight renders at 0.55 alpha (screenshot confirmed),
  "✎ note" → POST 201 → editor opens → note saves (PATCH) → note-dot shows; no console errors.
  No Python changed (suite unaffected).
- **Revert:** restore `callosum-app.html` from the pre-change zip snapshot in `.claude/backups/`.

## 2026-06-16 — Brand logo + favicon (increment 32)

- **Files:** `callosum-app.html` (+ user-added `app/media/logo.png`, `app/media/favicon.png`),
  `INCREMENT-32-NOTES.md`.
- **What:** Brand lockup in the sidebar header — the brain logo (62px) stacked **above** the
  "Callosum" wordmark, centered, with the subtitle/status centered under it; favicon wired. Both
  PNGs inlined as base64 `data:` URIs (favicon `<link rel="icon">` + a `.brand-logo` `<img>`);
  replaced the old accent `.dot` (rule removed); `.brand` is a centered column and the sidebar
  header is centered.
- **Why:** Branding. Inline data URIs (matching the existing `data:,` favicon placeholder) avoid a
  new file-serving route/surface and keep the single-file, offline frontend self-contained.
- **Verify:** headless Chromium PASS (logo decodes 348px → 62px, stacked centered above the
  wordmark, favicon is a PNG data URI, no console errors); `pytest` still 113 passed (no Python touched).
- **Revert:** restore `callosum-app.html` from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-16 — Annotation notes + management panel (increment 31 / suite B)

- **Files:** `app/backend/api/app.py`, `app/backend/persistence/repository.py`,
  `callosum-app.html`, `tests/test_api.py`, `tests/test_persistence_core.py`,
  `INCREMENT-31-NOTES.md`, `.claude/security-audits/2026-06-16_annotation-notes.md`.
- **What:** Comments/notes on highlights + a per-paper annotation panel. `note` accepted on
  create; new `PATCH /annotations/{id}` (note and/or color; note capped at 4000) — the
  project's first update endpoint; `update_annotation` repo helper. Frontend: clicking a
  highlight opens a note+color editor (replaces delete-only), a note dot marks commented
  highlights, and a collapsible in-viewer panel lists/edits/deletes/jumps-to annotations.
- **Why:** Suite increment B; activates the `note` column scaffolded in A. No migration (the
  column already exists). Synthesis-sourcing + re-anchoring remain later increments.
- **Verify:** `pytest` (113 passed); headless E2E PASS — note persists across reload with the
  highlight still at **0.0 px** drift; two PATCH round-trips; delete-from-panel clears UI + DB.
- **Revert:** restore the listed files from the pre-increment zip snapshot in `.claude/backups/`
  (no schema/migration change to undo).

## 2026-06-16 — Annotation highlights (increment 30 / annotation suite A)

- **Files:** `app/backend/persistence/schema.py`, `alembic/versions/0002_annotation_highlights.py`,
  `app/backend/persistence/repository.py`, `app/backend/api/app.py`, `callosum-app.html`,
  `tests/test_api.py`, `tests/test_persistence_core.py`, `INCREMENT-30-NOTES.md`,
  `.claude/security-audits/2026-06-16_annotations.md`.
- **What:** First user-authored persistent data + first mutating endpoints. PDF.js text
  layer added so text is selectable; selecting text offers a color and creates a durable
  highlight (POST), highlights load + render on open and stay zoom-aligned (reusing the
  increment-29 coordinate model), and can be deleted. Backend: extended the existing
  `annotations` table with native columns (color/bboxes_json/anchor_text/prefix/suffix/
  source/note/updated_at), repository CRUD, and `POST/GET /papers/{id}/annotations` +
  `DELETE /annotations/{id}`.
- **Why:** Foundation of the staged annotation suite (comments, synthesis-linking,
  re-anchoring come later). `note`/`source` columns scaffold those without building them.
- **Verify:** `pytest` (107 passed); headless Playwright E2E PASS (highlight lands on
  text 98.6%, persists at 0px after reload, 0% zoom drift, delete clears UI + DB).
- **Revert:** restore the listed files from the pre-increment zip snapshot in
  `.claude/backups/`; on any already-migrated DB, the 0002 columns are additive/nullable
  and can be left in place (downgrade available via `alembic downgrade 0001_persistence_core`).
