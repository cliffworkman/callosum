## Directory layout

```
callosum/
├── .claude/                       ← dev-only working space; NOT part of the app
│   ├── CLAUDE.md                  (this file)
│   ├── PRINCIPLES.md              (the project charter — the Principles alignment gate, rule #9)
│   ├── APPROACH-AVOIDANCE.md      (the value substrate beneath PRINCIPLES — the gate's deeper conditional layer)
│   ├── CREDIT-THE-LINEAGE.md      (values-layer cross-cutting principle — credit + library-add the scholarly work a tool stands on; inbox-captured 2026-06-21)
│   ├── DESIGN.md                  (the design dictionary — rule #8)
│   ├── QA-POLICY.md               (the QA contract — rule #10 / the surface-coverage gate)
│   ├── qa-routes/                 (QA route scripts the Codex-exec supervisor traverses; route_NN_*.md, NN
│   │                              encodes complexity order; _TEMPLATE.md is the contract shape — inc 120)
│   ├── qa-inbox/                  (gitignored, local-only: <run-id>/ deposits — md reports + screenshots +
│   │                              run-summary.md; _processed/ = triaged runs; the watched dropzone — inc 120)
│   ├── docs/                      (planning suite: product-scope, data-contracts, architecture, risk-register,
│   │   ├── increment-notes/       glossary, INCREMENT-BACKLOG, README; increment-notes/ = the per-increment diary;
│   │   ├── future-tracks/         future-tracks/ = longer-horizon docs; future-tracks-import/ = the watched inbox
│   │   ├── future-tracks-import/  (session-kickoff watch rule, Phase 8; gitignored — local-only dropzone);
│   │   └── research/              research/ = deep-research planning + feedback baselines + ref-manager surveys.
│   │                              NB roadmap.md + backlog-future-tracks.md were archived → deprecated/)
│   ├── deprecated/                (vestigial scaffolding archived here, not deleted)
│   ├── backups/                   (timestamped zip snapshots: callosum_HHMMpm.zip;
│   │   └── plans/                 plus plan-file backups — this is the recovery net)
│   ├── security-audits/           (per-feature threat-review write-ups — see audit gate)
│   ├── changes.md                 (running human-readable change log)
│   └── media/                     (brand-asset PNG sources — logo/favicon variants; re-inlined by tools/inline_brand_assets.py)
├── app/
│   ├── backend/                   ← all backend implementation
│   │   ├── api/                   (app.py [thin create_app factory + lifespan + CORS + frontend route],
│   │   │                          access_control.py [remote-access bearer-token gate + rate limiter, opt-in, inc 168;
│   │                          + CALLOSUM_READ_ONLY method gate (403 on writes) for B5 mobile reading, inc 237],
│   │   │                          auth/ [OIDC "Sign in with ORCID" client + router — optional account, SP1, inc 194],
│   │   │                          startup.py [logging + Alembic auto-migrate], dependencies.py,
│   │   │                          job_store.py [generic async-job store: Job/JobStore[R]],
│   │   │                          frontend.py [serve-time assembler], routers/{health,papers,paper_files [PDF
│   │   │                          file-serving, inc 91],methods [statcheck inc 95; GRIM inc 127; p-curve inc 126; Bayesian inc 241; POST /methods/effect-size inc 252],citation_equity [citation-concentration: structural reference-list audit, inc 227; geography signal removed inc 229],citation_context [scite-analogue "how this paper is cited" — Semantic Scholar contexts + local NLI stance, inc 232],citations [formatted-citation
│   │   │                          engine, inc 106],duplicates,acquisition,wanted,my_publications,library,
│   │   │                          annotations,tags,axes,summaries,findings [FACT/CANDIDATE store, inc 130],
   │                          gaps [literature gap-finder, inc 135],discovery [Search providers, inc 183],settings [BYOK: Gemini key + egress
   │                          consent + PUBLISHERS "where to submit" prefs, inc 146/246],libreoffice [LO plugin install/download, inc 162],word [Word add-in
   │                          task pane + manifest serving, inc 164],sync [opt-in E2E sync: setup/settings/status/run,
   │                          inc 202],agent [gated MCP write endpoints: tag/axis/reference/note + audit + revert, inc 216],
   │                          reading_queue [the to-read "Queue" tab — reading_queue table, inc 219],
   │                          ocr [scanned PDF → searchable copy via local Tesseract, inc 231],
   │                          publishers [PUBLISHERS "where to submit" journal-finder, #40 SP1a, inc 245],
   │                          lmm [LMM-reporting completeness auditor, #23, inc 247],
   │                          metaanalysis [meta-analysis reporting auditor, #36 consumer-side, inc 249],
   │                          transparency [transparency-signals auditor: open-science-disclosure detectors + the library batch/summary/review-queue persistence, #44, inc 250/251],
   │                          help,wip_critical_review [local exact-snapshot WIP Critique job, inc 445]}.py [models + handlers])
│   │   ├── persistence/           (schema.py [SQLAlchemy Core core tables] + schema_base.py [shared metadata] +
│   │   │                          schema_findings.py [findings/signals/retraction/gap tables] + schema_feed.py
│   │   │                          [feed_subscriptions/feed_items, inc 187] + schema_sync.py [sync_state/sync_conflicts/
│   │   │                          sync_identity, local-only, SP3a/3b inc 197/198] [all re-exported from schema], gap_repo.py
│   │   │                          [gap_candidates cache, inc 137], feed_repo.py [Feed data access, inc 187],
│   │   │                          database.py, repository.py,
│   │   │                          dedup_repo.py [dismissed-duplicate-pairs data access, inc 67],
│   │   │                          tags_repo.py [tag data access, inc 71], acquisition_repo.py [OA attachment labels, inc 74],
│   │   │                          wanted_repo.py [wanted-list data access, inc 76], profile_repo.py [My Publications profile + decisions, inc 78],
│   │   │                          annotations_repo.py [native-annotation data access, inc 91],
│   │   │                          signals_repo.py [open_science_signals: statcheck + retraction + per-disclosure transparency status, inc 97/131/251],
│   │   │                          watched_repo.py [watched_folders, inc 98],
   │   │                          findings_repo.py [paper_findings: FACT/CANDIDATE contract, inc 130],
   │   │                          retraction_repo.py [retraction_records: local Retraction Watch mirror, inc 132],
   │   │                          agent_repo.py [agent_writes: gated MCP-write audit log + revert, inc 216],
   │   │                          reading_queue_repo.py [reading_queue: the ordered to-read list, inc 219],
   │   │                          paper_lifecycle_repo.py [trash/purge/tier + read/priority setters, split inc 220],
   │   │                          summaries_repo.py [synthesis CRUD, split inc 220] [both re-exported from repository];
   │   │                          wip_critical_review_repo.py [generic exact-snapshot WIP critical-read receipt,
   │   │                          inc 445]; database.py sets PRAGMA journal_mode=WAL + busy_timeout=5000, inc 219)
│   │   ├── pdf_processing/        (extraction.py [PyMuPDF text + canonicalize], quote_matching.py
│   │   │                          [locate_quote → bbox rects], ingest.py, library_scan.py [folder scan, inc 87],
│   │   │                          ocr.py [scanned PDF → searchable PDF via local Tesseract binary, inc 231],
│   │   │                          location.py, cli.py)
│   │   ├── embeddings/            (models.py, pipeline.py, vector_store.py [sqlite-vec], retrieval.py)
│   │   ├── clustering/            (abstract_clustering.py, axis_scoring.py [scoring engine],
│   │                          axis_assignments.py [manual-override + state API], axis_suggestion.py,
│   │                          axis_operations.py, duplicate_detection.py, tag_suggestion.py [inc 72],
│   │                          my_publications.py [own-papers resolver + import hook, inc 78],
   │                          gapfinder.py [backward citation gap-finder, inc 135])
│   │   ├── methods/               (statcheck.py [NHST p-value recomputation, inc 95], pcurve.py [inc 126], grim.py
   │   │                          [GRIM/GRIMMER, inc 127], retraction.py [multi-source retraction → FACT, inc 131],
   │   │                          citation_equity.py [citation-concentration: structural reference-list audit, inc 227;
   │   │                          geography signal + nationality dropped inc 229 — never categorizes the people cited],
   │   │                          overlooked_work.py [topical overlooked-work ranker — local SPECTER cosine, inc 228],
   │   │                          citation_context.py [local-NLI stance classifier for "how this paper is cited", inc 232],
   │   │                          bayes.py [Bayesian auditor: recompute default JZS t-test Bayes factors, inc 241; + a Tier-2 BARG/WAMBS/JASP completeness checklist, inc 242; + Ly-2016 Pearson-correlation BFs, inc 243; + Tier-3 textual-coherence advisory prompts, inc 244],
   │   │                          publishers.py [PUBLISHERS "where to submit": uniform journal profiles + local SPECTER fit + open-science weighting, #40 SP1a, inc 245],
   │   │                          lmm.py [LMM-reporting completeness auditor: reads reported text, flags 7 reporting checks, never runs a model, #23, inc 247],
   │   │                          metaanalysis.py [meta-analysis reporting auditor: reads a published meta-analysis's reported text, flags 7 reporting checks, never pools/models/re-computes, #36, inc 249],
   │   │                          transparency.py [transparency-signals auditor: ODDPub/rtransparent-derived, detects 7 open-science disclosures in reported text, never scores/accuses, #44, inc 250] +
   │   │                          transparency_findings.py [persist present disclosures as findings-FACTs + per-disclosure status → 7 library review queues + chip, #44 inc 1b, inc 251] +
   │   │                          effectsize.py [deterministic effect-size converter: one study's stats → Hedges' g/Fisher's z/log OR/RR + variance + CI, cited formulas, NEVER pools/models, meta-analysis workbench SP1, inc 252],
   │   │                          critical_review.py [paper + transient-query WIP contested-claim backbone, inc 266/445])
│   │   ├── discovery/             (providers.py [SourceProvider registry + normalized Item + cross-provider dedup],
   │   │                          crossref_provider.py [Crossref /works keyword search], pubmed_provider.py [NCBI
   │   │                          E-utilities esearch→esummary: PubMed Search provider (SP1a inc 186) + PubMedKeywordFeedSource
   │   │                          (SP2c inc 189)], search.py [run_search + metadata-only save], relevance.py [axis-relevance
   │   │                          highlight — local, SP1b inc 185]; #28 Search, inc 183; feed.py [Feed engine: FeedSource
   │   │                          registry + source_meta + refresh + read view] + biorxiv_source.py [bioRxiv +
   │   │                          medRxiv, server-configurable] + journal_issn_source.py [Feed sources; + PubMed-keyword
   │   │                          (esearch sort=date) + efetch abstracts in pubmed_provider]; #28 Feed SP2a/2c, inc 187/189-191)
│   │   ├── citations/             (render.py [citeproc-js sidecar wrapper: render_papers (per-item, inc 106) +
│   │   │                          render_document (position-aware, inc 107) + style manifest + HTML sanitizer],
│   │   │                          suggest.py [highlight-to-suggest/evaluate engine: retrieval-in-reverse + NLI stance, inc 156],
│   │   │                          citeproc_runner.js [Node sidecar; per-item + mode:"document"], csl/{styles,locales} [bundled CSL data, CC-BY-SA])
│   │   ├── summarization/         (pipeline.py, generators.py, verification.py, reverify.py [B2 SP3: re-verify an imported synthesis locally → convert in place to native, inc 236])
│   │   ├── llm/                   (egress.py [provider-neutral DataEgressDisabledError + seam-gate wrappers, inc 58];
│   │   │                          cache.py [content-addressed summary-generation cache, inc 61]; usage.py [token logging])
│   │   ├── help/                  (help_content.md [served corpus, inc 59], corpus.py [loader + allowlisted
│   │   │                          md→html], assistant.py [HelpAssistant Protocol + dataclasses, inc 60])
│   │   ├── importers/             (zotero.py)
│   │   ├── sync/                  (crypto.py [E2E: passphrase/recovery → scrypt → AES-GCM record encryption] +
│   │   │                          changeset.py [sync_uid-keyed hash-diff change-tracking + LWW conflict-surfacing
│   │   │                          merge + the sync_identity map helpers + FK-translation: collect/apply translate a
│   │   │                          row's FK local-id ↔ the referenced row's sync_uid; a LINK table (pk=None, paper_tags)
│   │   │                          keys on its endpoint uids; a natural_key collection (tags=name) gets a deterministic
│   │   │                          name-derived uid → cross-device convergence; SYNCABLE = papers/tags/axes/notes/
│   │   │                          annotations/paper_tags] + engine.py [pull→decrypt→merge→apply (referenced-first;
│   │   │                          link path)→push over a SyncTransport Protocol] + transport.py [HttpSyncTransport:
│   │   │                          the Protocol over httpx → the reference server, fail-closed; SP3b inc 202]; accounts
│   │   │                          SP3a/3b, local; egress only via the opt-in /sync/* + sync_server/; summaries=not-synced)
│   │   ├── metadata/              (doi.py, enrichment.py [+enrich_paper_metadata_multi: multi-pass gap-fill, inc 217],
│   │   │                          enrich_sources.py [pluggable enrichment-source registry: Crossref/OpenAlex/EuropePMC/PubMed, inc 217-218],
│   │   │                          abstract_display.py, paper_edits.py,
│   │   │                          paper_merge.py [non-destructive duplicate merge, inc 161],
│   │   │                          citation_export.py [→BibTeX/RIS/CSL-JSON, inc 70],
│   │   │                          citation_import.py [←parse BibTeX/RIS/CSL-JSON, inc 93],
│   │   │                          library_bundle.py [portable library bundle: export/import metadata+tags+annotations+axis-defs+syntheses, NO PDFs; B2 SP1 inc 234 + SP2 relayed-syntheses inc 235 + SP3 re-verify inc 236])
│   │   └── acquisition/           (registry.py [OaLocation OA-only seam + cascade], fetch.py [download/validate/
│   │                              name/import], wanted.py [wanted-list re-check service, inc 76], resolvers/{openalex,
│   │                              doaj,europepmc,crossref,core,arxiv,biorxiv,osf}_resolver.py; the OA acquisition
│   │                              clean lane, inc 74 + cascade inc 75 + wanted list inc 76)
│   ├── frontend/                  ← the UI SOURCE: index.html shell + styles.css + js/*.jsx chunks
│   │                              (assembled by app/backend/api/frontend.py; build → callosum-app.html)
│   └── desktop-shell/             (placeholder — Tauri, post-V1)
├── adapters/                      ← word-processor adapters (CLIENT code, ships into the word processor; NOT the
│   └── libreoffice/               app, NOT a server integration). inc 108: callosum_cite.py [UNO macro: Insert/
│                                  Refresh/SetStyle/Flatten + inc-157 Suggest + inc-162 AddCitation (search) /
│                                  SetServerUrl + an _ACTIONS/dispatch registry + configurable base URL]. inc 162 (v2):
│                                  oxt/ [description.xml, META-INF/manifest.xml, Addons.xcu = the Callosum menu/toolbar]
│                                  + callosum_addon.py [XJobExecutor dispatcher] → a one-click `.oxt` (built by
│                                  tools/build_libreoffice_oxt.py; installable from Settings, inc 162). README.md,
│                                  selftest_uno.py [headless round-trip: unopkg-installs the .oxt + verifies the
│   └── word/                       dispatcher]. inc 164/165/166 (Word add-in, Office.js, SP1/SP2/SP3): manifest.xml +
│                                  taskpane.{html,js,css} + taskpane_core.js [pure logic, node --test] + icon.png +
│                                  README.md — a desktop-Word task pane served by callosum over HTTPS (Architecture A:
│                                  same-origin, zero egress). Full parity: live citations (Content Controls carrying
│                                  CSL-JSON) + Refresh/renumber + bibliography (/citations/render-document) + Suggest
│                                  (/citations/suggest) + one-click style-switch + Flatten.
│   └── googledocs/                inc 169 (SP1 — the bridge): cloudflared-config.yml [CITE-ONLY ingress for
│                                  callosum-tunnel.clffwrkmn.net → localhost; the hostname renamed from
│                                  callosum.clffwrkmn.net (2026-06-30) to free callosum.clffwrkmn.net for a website —
│                                  tunnel NAME stays `callosum`; validated + LIVE-verified] (+ a gitignored
│                                  cloudflared-config.local.yml filled copy) + tools/run_tunnel.py. inc 170 (SP2 — the
│                                  Apps Script add-on): Code.gs [sidebar glue] + gdocs_core.js [pure mapping, node --test,
│                                  also loaded by GAS as CallosumCore] + gdocs_core.test.js + sidebar.html + appsscript.json
│                                  — citations as NamedRange + DocumentProperties (Zotero pattern); reuses the cite
│                                  contracts; manual-test-only. inc 171 (SP3): Suggest-from-the-selection
│                                  (/citations/suggest) + Flatten (live→static). inc 193: callosum-gdocs.gs [the 3 sources
│                                  bundled to one paste, built by tools/build_gdocs_addon.py] + a --quick Quick-Tunnel path.
│                                  README.md = the setup runbook (leads with the easy path).
│   └── mobile/                     B5 (inc 237 SP1 + inc 238 SP2): read-only mobile reading over the tunnel —
│                                  cloudflared-config.yml [READ-ONLY ingress allowlist: forward the GET read paths
│                                  (papers/summaries/axes/tags/reading-queue/annotations/help), else 404] + README.md
│                                  [runbook: a 2nd callosum with CALLOSUM_READ_ONLY=1 + Remote access on]. tools/run_tunnel.py
│                                  --mobile runs it. The responsive + read-only-companion UI lives in app/frontend
│                                  (02_mobilenav.jsx + the 04_layout mobile flag + a `readOnly` flag from /health.read_only
│                                  threaded through the panels; inc 239 SP3 = the mobile reader — fit-width default +
│                                  pinch-to-zoom [30f_pdf_gestures.jsx] + a citation "← Synthesis" back pill; inc 240 =
│                                  touch-native highlighting — a mobile selectionchange trigger surfaces the picker).
│                                  The read-only *guarantee* = the CALLOSUM_READ_ONLY method gate.
├── integrations/                  (external adapters: zotero, crossref, gemini, openalex [+sources.py = journals for
│                                  the where-to-submit tool, #40 inc 245], doaj [+journals.py = journal facts APC/waiver/
│                                  Seal/license, #40 inc 245], europepmc, core, arxiv, biorxiv, osf,
│                                  retraction_watch [RW DB download, inc 132],
│                                  semantic_scholar [citation contexts → "how this paper is cited", inc 232] [impl];
│                                  api_cache.py [shared cache helper]; grobid, mendeley [planned])
├── sync_server/                   ← the reference E2E **sync-server** (accounts SP3b, inc 202): a SEPARATE deployable
│                                  (its own requirements.txt; the local app never imports it), FastAPI + SQLAlchemy
│                                  Core (Postgres in prod / SQLite in tests). schema.py [sync_records + sync_cursor,
│                                  per-user], auth.py [TokenVerifier Protocol + JwksVerifier — an OIDC resource server],
│                                  store.py [push LWW-by-version + per-user seq / pull since-delta], app.py
│                                  [GET/POST /sync/records + /health], README.md. Stores only OPAQUE AES-GCM blobs.
├── mcp_server/                    ← the read-first **MCP server** (backlog B1 SP1, inc 213): a SEPARATE stdio
│                                  deployable (its own requirements.txt — `mcp` SDK + httpx; the app never imports it,
│                                  it never imports the app — talks HTTP). client.py [CallosumClient: 5 read methods +
│                                  4 opt-in write methods, injectable httpx, fail-closed], server.py [create_server(client)
│                                  →FastMCP; 5 read tools + 4 write tools registered only when agent_writes_enabled],
│                                  __main__.py [`python -m mcp_server`], README.md. Reads = hardcoded allowlist; writes
│                                  (SP2, inc 216) hit only the gated/audited/reversible `/agent/*` endpoints — no
│                                  delete/scan/merge method anywhere.
├── research/                      (planning + research docs; Track-D acquisition rate-limit records)
├── ops/                           (deployment notes — planning state; gets real content pre-deploy)
├── tools/                         (validation_harness.py + validation/ [reports.py, report_renderer.py],
│                                  enrich_metadata.py, inline_brand_assets.py, build_frontend.py,
│                                  build_libreoffice_oxt.py [the LO extension build, inc 162],
│                                  run_https.py [serve over HTTPS on :8443 for the Word add-in, inc 164],
│                                  run_tunnel.py [cloudflared tunnel for the Google Docs add-on: named cite-only (inc 169)
│                                  or --quick zero-setup Quick Tunnel (inc 193)], build_gdocs_addon.py [bundle the 3 Apps
│                                  Script sources → one paste-able callosum-gdocs.gs, inc 193]; qa/ [inc 120:
│                                  build_surface_map.py = surface-coverage gate, supervisor.py = Codex-exec
│                                  dispatcher, _qa_serve.py = seeded throwaway server, route_runner_prompt.md])
├── tests/                         (pytest suite — per-resource files + conftest.py + api_helpers.py; 303 passing;
│                                  tests/e2e/ = opt-in Playwright browser smoke, CALLOSUM_RUN_E2E=1)
├── alembic/                       (env.py + versions/0001_persistence_core … 0032_summary_imported_json)
├── alembic.ini, pyproject.toml, requirements.txt, requirements-dev.txt
├── package.json, package-lock.json  ← JS deps: esbuild (frontend build, inc 102) + citeproc (citation engine, inc 106); node_modules/ gitignored
├── THIRD-PARTY-NOTICES.md           ← credit-the-lineage: citeproc-js (AGPL) + bundled CSL styles (CC-BY-SA), inc 106
├── callosum-app.html              ← GENERATED from app/frontend/ by tools/build_frontend.py; served at /
├── library/                       (77 scholarly PDFs; "Author et al. - YEAR - Journal.pdf"; gitignored)
└── .local/                        (generated validation DBs + debug images; gitignored)
```

`.gitignore` excludes `.local/`, `.pytest_cache/`, `__pycache__/`, `*.py[cod]`, `*.sqlite`,
`*.db`, `*.pdf`. **callosum IS a git repo** (remote `origin` → `github.com/cliffworkman/callosum`,
public, AGPL-3.0; CI in `.github/workflows/ci.yml`). Recovery is git history + the off-machine
GitHub backup, plus zip snapshots + Dropbox version history (see Backup & snapshot protocol).
