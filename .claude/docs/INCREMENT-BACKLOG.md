# Increment backlog — OPEN (restructured 2026-08-09, at inc 466)

> **What this file is.** The running list of what's genuinely left to build. Full shipped detail lives in
> `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md` (the per-increment diary) and `INCREMENT-BACKLOG-DONE.md`
> (the closure index); this file's job is to say **what's still open**, not to re-narrate what already shipped.
>
> **Closure discipline (2026-08-09).** When an item here closes: **delete its entry from this file** — don't
> leave a growing "✅ CLOSED [paragraph]" bullet in place. Instead **append one compressed `- [x]` line to
> `INCREMENT-BACKLOG-DONE.md`**, keyed by the item's own stable `#N` where it has one, pointing at the relevant
> `INCREMENT-NN-NOTES.md` for full narrative. This file had drifted from that discipline (a duplicate in-file
> "Shipped — breadcrumbs only" section, plus several individually-growing closed entries) — the 2026-08-09 pass
> reconciled all of it into `INCREMENT-BACKLOG-DONE.md` and trimmed this file back to open items only. See
> CLAUDE.md's Increment workflow section for the enforced rule going forward.
>
> **Numbering is stable across edits.** Item numbers are cross-referenced from `CLAUDE.md`, session handoffs, and
> increment notes ("backlog #20", "backlog #5"), so a number is never reassigned. Gaps in the numbering are
> shipped/closed items now living in `INCREMENT-BACKLOG-DONE.md` — `grep "#12" INCREMENT-BACKLOG-DONE.md` finds
> them.
>
> **Guiding principle (Cliff's):** *reference manager first.* The verified-synthesis crown jewel only matters if
> Callosum is a credible day-one replacement for Mendeley/Zotero — so table-stakes reference-manager UX stays
> high priority; differentiators come after.
>
> **Scope note:** the bigger **longer-horizon tracks** have detailed build-prompt docs under **`future-tracks/`**
> (its `README.md` is the index) — that's the canonical design source; the entries below are the queue summary.

---

## 1. Near-term (small, self-contained, no design decision needed)

- **#80 Automate the release *bump*, not the Tauri build — the build is already automated.** Raised by
  Cliff (2026-09-04) as "a GitHub action to automate our Tauri builds." **Checked before scoping, and the
  framing turned out to be stale:** `desktop-shell-{windows,macos,linux}.yml` already build *and* verify
  the real installer on every push (launch it, screenshot the running window, assert backend health), and
  `desktop-shell-release.yml` already fires on a `v*` tag, calls all three as reusable workflows, signs the
  updater artifacts, and publishes one GitHub Release with all three installers only if all three succeed.
  There is no missing build automation. What is genuinely manual is everything *around* it:
  - **The version bump is five hand-edited files** — `tauri.conf.json`, `package.json`, `Cargo.toml`, plus
    `package-lock.json` (two self-references, and the *only* two: a naive replace-all would rewrite
    dependency versions) and `Cargo.lock` (the `callosum-shell` stanza alone). Done by hand for 0.5.6 this
    session. The tag-time preflight catches a *mismatch*, but nothing prevents the error or does the work.
    Wanted: `python tools/bump_version.py 0.5.6` that edits exactly those five, refuses on any unexpected
    occurrence count, validates the JSON, and prints the diff. Cheap, and removes the whole error class.
  - **`desktop-shell-release.yml` has no `workflow_dispatch`** (the three platform workflows all do). If
    the `publish` job fails after three successful builds — a transient GitHub API error, a missing
    secret — the only recovery is deleting and re-pushing the tag. A dispatch trigger taking a tag name
    would make that a button.
  - **Optional, and NOT an obvious win: migrating to the official `tauri-apps/tauri-action`.** The current
    workflows are hand-rolled `npx tauri build`, and they carry a lot of hard-won project-specific logic
    that the generic action does not have: the blocking `objdump` glibc-floor guards (backlog #71/#76), the
    macOS re-sign-after-resources step (without which Gatekeeper reports the app as *damaged*, inc 395),
    App-Translocation-aware verification (inc 571), and the immutable-Python-runtime provisioning check
    (inc 570). Migrating risks silently dropping those. Treat as a research task with an explicit
    "what would we lose" inventory first, not a default modernization.
  - Not urgent: releases work today, and 0.5.6 shipped on this machinery.

- **#79 A query-scope synthesis materializes the entire library to pick 8 chunks.** Surfaced by inc 573's
  crash fix (backlog #78-adjacent, reported by Vasiliki Meletaki with a 716,670-chunk library). The crash
  is fixed and the path is ~19x faster, but it is still O(library) where it should be O(top_k). Measured on
  a real 23,782-chunk library and extrapolated (30.1x) to hers:

  | phase | 23,782 chunks | ~716,670 chunks |
  |---|---|---|
  | load all candidate rows (all columns, incl. `text`) | 10.5s | **~315s** |
  | `exclude_repeated_boilerplate_chunks` | 4.1s | ~123s |
  | classify current embeddings | 2.4s | ~72s |
  | **total** | **16.9s** | **~8.5 min** |

  `_source_chunks_for_scope` (`app/backend/summarization/pipeline.py`) builds the candidate pool by
  selecting **every** article chunk of every live paper, then ranks it. For the `papers`/`cluster_node`
  scopes that pool is genuinely bounded by the selection; for the **query** scope it is the whole library.
  - **The aligned shape already exists:** `SQLiteVecVectorStore.search` does a real KNN and its
    `_search_candidates` already uses a **temp table**, not an `IN (...)`. A query scope could search
    globally and fetch rows only for the hits, making cost proportional to `top_k`.
  - **Two real obstacles, not incidental:** (1) the live-paper + `ARTICLE_DOCUMENT_ROLES` filters currently
    run *before* ranking, so a global KNN must over-fetch and filter after, and can under-deliver `top_k`;
    (2) `exclude_repeated_boilerplate_chunks` is per-paper over the candidate pool — running it only on the
    hits changes which chunks survive. Both are behaviour changes at the margin, so this needs its own
    increment with before/after retrieval comparisons on a real library, not a drive-by.
  - **UX consequence, from inc 573's experience pass (rule #11):** `summarize_scope` reports this stage as
    `on_stage("preparing_sources", …, None, False)` — total unknown, indeterminate. That is correct under
    invariant #5 (never invent a percentage), but it means a large-library user watches an indeterminate
    "Preparing sources" for ~5 minutes before anything else happens, which reads as a hang. Even without
    the architectural fix, this stage *is* countable (the candidate pool size is known once loaded), so it
    could report honest determinate progress. Whoever takes #79 should fix the signal too, not only the
    speed — a correct slow operation that looks broken is still a bad outcome.
  - Non-blocking: the feature works today at every library size, just slowly at the top end.

- **#82 Reference lists are the largest thing synthesis retrieval can find, and it finds them.** Measured
  during inc 575's live verification against the 219-paper testing library, not inferred. `references` is
  the **single biggest section in the corpus — 5,635 of 23,875 chunks (24%)** — and a bibliography entry
  is keyword-dense across many topics, so a multi-construct question finds it irresistible. A real
  four-construct query retrieved **4 of 8 chunks from `section='references'`**, i.e. half the evidence
  budget went to citation lists like *"Moll, J., de Oliveira-Souza, R., … J Cogn Neurosci 21(7):1396"*.
  - **A reference-list entry can never be the verbatim evidence for a scientific claim** — it is a
    pointer to a finding, not a finding. So excluding it from the synthesis candidate pool is
    principled, not merely a quality heuristic.
  - **Measured effect, same question, same library, same model.** With references excluded via the
    existing `sections` filter, claims went from vacuous (*"Depression has been studied using fMRI to
    investigate the neural correlates of rumination"*) to substantive (*"individuals with TBI showed
    increased neural activity in the insula, anterior cingulate…"*), and distinct chunks cited went 1 → 2.
    **Honest limit: verified citations stayed 0/4 in both runs** — better grounding, not yet correct
    attribution, because the 1.5B local model still stretched one paper across four constructs. This
    improves the evidence offered, not the model's reasoning over it.
  - Cheap: `_source_chunks_for_scope` already filters by `chunks.section`, `SUMMARY_SECTION_KEYS` already
    lists `references`, and the UI already exposes a section picker — so the change is defaulting the
    query scope to exclude references, not building anything.
  - Care needed: `chunks.section` is the pre-existing *heuristic* labeller (every chunk in this sample had
    `grobid_section_id = NULL`), and 4,282 chunks are labelled `None`, so exclusion is partial and can
    mislabel. Prefer GROBID's mapped sections where they exist (inc 479), and keep it a default the user
    can turn off rather than a hard filter.

- **#83 `run_dev.py` leaves orphaned children on teardown — including one it has just made
  unidentifiable.** Found during inc 575's live verification, which leaked **three** processes across two
  sessions: `llama-server` twice and `run_https.py` once (still holding its TLS port). `run_dev` prints
  "stopping the rest" and clears the Local AI descriptor, but children it did not spawn *directly* —
  `llama-server` is a grandchild via `run_local_ai.py` — survive. The `llama-server` case is the worst
  of the three: a ~1.5 GB CPU-bound process left running *after* deleting the descriptor that names it,
  so nothing can identify it afterwards. All three had to be found by inspecting command lines
  (`--api-key-file` against the dev app-data path; the TLS port) and killed by PID, taking care not to
  hit the packaged app's own Local AI or a developer's separate server.
  - Directly contradicts the "no orphan" post-condition inc 569's own security audit asserts, and the
    hazard `test_a_stale_descriptor_is_removed_before_a_new_run` exists to prevent.
  - Fix: `run_local_ai.py` should terminate its child on any exit path (process group, as
    `managed_local_ai/process.rs` already does under `#[cfg(unix)]`), and/or `run_dev` should stop the
    grandchild before clearing the descriptor rather than after.
  - Related, same session: `run_dev` printed `serving on http://127.0.0.1:8888` and *then* exited on
    `[Errno 10048] address already in use`. Because another server already held the port, `/health`
    answered 200 the whole time — so the tooling looked healthy while serving someone else's instance.
    A port preflight (or not announcing until bound) would remove a genuinely misleading failure.

- **#73 Both Linux lanes pin `runs-on: ubuntu-22.04`, a runner label GitHub is retiring.** Introduced
  deliberately in inc 570: the shell and the Python-runtime artifact must both be built at the supported
  glibc floor (2.35) so the `.deb` runs on Debian 12 (2.36) and Ubuntu 22.04+ — see backlog #71's closure
  and `INCREMENT-570-NOTES.md`. It works today (both lanes build and publish), so this is durability, not
  breakage. **When the label goes away, do not "fix" it by moving back to `ubuntu-latest`** — that is
  exactly the regression that shipped a `.deb` which could not start at all. The durable form is a pinned
  container (`container: ubuntu:22.04`) on `ubuntu-latest`, which also makes the glibc floor explicit
  rather than implied by a runner image; expect friction with `actions/*` inside a container (git for
  checkout, Node for the JS actions). The blocking `objdump` glibc guard in `desktop-shell-linux.yml`
  will catch a wrong base immediately either way.

- **#77 llama.cpp/ggml and Qwen are absent from `THIRD-PARTY-NOTICES.md`.** Found during inc 572's
  security audit; **pre-existing since inc 547**, not introduced by it, and applies equally to all three
  platforms. Per-install provenance already exists — `write_receipt` records `runtime_source`/
  `runtime_license` (`ggml-org/llama.cpp release b10516`, MIT) and `model_source`/`model_license`
  (`Qwen/Qwen2.5-1.5B-Instruct-GGUF`, Apache-2.0) into `install.json` platform-generically — so this is
  the repo-level notices file only, not a missing disclosure in the product. Cheap: two entries.
  `.claude/CREDIT-THE-LINEAGE.md` is the governing value (credit a prior tool by citation, never by
  appropriating its name).

- **#78 Make the desktop startup loader branded, stateful, and genuinely informative.** Raised from a real
  Windows 0.5.3 → 0.5.5 upgrade on 2026-09-04: the 0.5.5 shell and WebView were healthy, but no Python/backend
  child existed yet because startup was walking and hashing the old bundled Python environment before deciding
  whether it could be migrated. The candidate runtime is about **1.315 GB across 41,338 entries**; if migration
  rejects it, the fallback archive is another **382,932,668-byte download**. During the tree walk the persistent
  runtime directory remains empty, write progress is zero, and the current migration event carries no files,
  bytes, elapsed time, or ETA, so this legitimate work looks exactly like a hung application. This is a loader UX
  requirement, not merely a special case for Python-runtime migration.
  - **Visual hierarchy:** the top half of the window should use Callosum's actual product identity — the real
    logo beside **“Callosum” with a capital C**, matching the in-app presentation rather than a generic/lowercase
    loading window. The bottom half must answer, in ordinary language, **“What is going on, and how much longer
    until I can use Callosum?”**
  - **Truthful stages:** distinguish at least checking the managed runtime; inspecting an existing runtime;
    reusing/copying it; downloading a required runtime; verifying integrity; extracting/installing;
    smoke-testing; starting Local AI when applicable; starting the Python backend; waiting for backend health;
    and ready. Do not collapse all pre-backend work into “Loading” or “Starting.” Explain that the one-time
    runtime step may be longer after an upgrade and that later launches will be faster.
  - **Progress and time:** for every measurable stage emit current/total bytes or entries, percentage, transfer/
    processing rate, elapsed time, and a conservative ETA. For stages that cannot yet be estimated, show an
    explicit indeterminate state plus elapsed time and explain what completion signal is being awaited; never
    invent a countdown. Preserve progress when the window subscribes late — startup state needs a queryable/
    replayable snapshot so an early `backend-status` event cannot be lost before `splash.js` registers its
    listener.
  - **Stalls and failures:** define stage-specific stall detection without treating slow disks/networks as
    failures. On a real failure, keep the window open with a stable error code, concise remediation, Retry, and
    one-click copyable sanitized diagnostics; do not require screenshots or expose credentials/private paths.
  - **Underlying migration follow-up:** measure why the legacy tree-digest pass is slow on real Windows installs
    (small-file enumeration, antivirus/Defender, cache state, and the later full copy are plausible factors).
    Preserve exact-manifest verification and immutable-runtime safety, but add an authenticated cheap-rejection
    check or a safer/faster migration route if evidence supports one. UX progress is required even if the
    operation is optimized.
  - **Coverage:** test stage transitions, byte/entry formatting, ETA behavior, late-listener recovery, unknown
    totals, retry/failure diagnostics, accessibility/live-region semantics, capitalization/logo regression, and
    a real old-bundled-runtime → persistent-runtime upgrade on Windows, macOS, and Linux. The acceptance test is
    that at every point a nontechnical user can tell that Callosum is working, what it is doing, whether their
    action is required, and approximately when the application will be usable.

- **#28 remaining slice:** more Feed sources are a one-line `register()` each as they come up; a true background
  polling daemon is **deliberately not built** (pull-first design choice, not a gap).
- **#64 Dependabot GHSA-wrw7-89jp-8q8g (`glib`, moderate) on the desktop-shell Linux build.** Flagged by GitHub
  on the inc-543 push (2026-08-30). `app/desktop-shell/src-tauri/Cargo.lock` pins `glib 0.18.5`, inside the
  vulnerable range `>=0.15.0, <0.20.0` (unsound `VariantStrIter` iterator impl, fixed in `0.20.0`). Confirmed
  transitive-only — pulled in by `tauri = "2"`'s Linux-only gtk-rs/webkit2gtk stack (`atk`/`gdk`/`gtk`/
  `webkit2gtk`/…, `app/desktop-shell/src-tauri/Cargo.toml` pins none of these directly) — and not reachable from
  any callosum code path (`VariantStrIter` is internal GTK variant/dbus-type iteration). Fixing it means a
  coordinated bump of the whole gtk-rs sibling-crate family via a newer `tauri`/`wry` release, not a standalone
  `cargo update -p glib`. Low urgency: Linux-desktop-build only, moderate severity, no known reachable path.
- **#65 `cap-pdf-search` on `www/showcase.html` claims "PDF text search" but no in-reader find/search UI exists
  anywhere in the app.** Found auditing demo coverage (2026-08-30): `app/frontend/js/30_viewer.jsx` loads only
  pdf.js's render/text-layer API, never `FindController` — this is a showcase claim for a feature that was
  never built, not a missing demo snapshot of an existing one. **Cliff's call:** build the real feature (pdf.js
  `FindController`-based in-reader find/search) once the current website arc finishes, then recapture
  `www/shots/app_current.png` and fold in the already-queued `.app-map` hotspot redesign (see the plan doc at
  `.claude/backups/plans/2026-08-30_website-demo-improvements.md`) in the same pass rather than recapturing
  twice.
- **#68 Tie GitHub release tags to the in-app "what's new" notification banner.** The banner mechanism
  (`app/frontend/js/30c_frame.jsx`'s `LocalAiWhatsNewHint`, a versioned dismissible-once localStorage key —
  `LOCAL_AI_WHATSNEW_KEY = "callosum.local-ai-whatsnew.v1"`) is a real, useful pattern, but each instance is a
  bespoke one-off added ad-hoc per feature with no systematic tie to a release — Cliff's own observation is that
  a prior instance (a "New layout" banner for the Synthesize/Work menu reorg) went stale/unused after
  implementation rather than being kept current release-over-release. **Proposal:** a CI gate on the existing
  `vX.Y.Z` release-tag push (CLAUDE.md's documented "Cutting a public desktop-shell release" flow —
  `git tag -a vX.Y.Z` + `git push origin vX.Y.Z`, which fires `desktop-shell-release.yml`) that fails unless an
  explicit, reasoned acknowledgment exists that the in-app banner reflects that release's real user-facing
  changes — reusing the exact `--refresh`/`--decline` + registry pattern `tools/qa/changelog_drift.py` already
  established for the demo/showcase drift gates (inc TBD, see increment notes) rather than inventing a new
  mechanism. Needs a design decision on where the "current release's banner content" registry lives (likely a
  small new JSON alongside the release tag, or a field in an existing settings/version file) — flagged here
  rather than built, since it's a genuinely new registry, not just a new glob on the existing one.
- **#69 A changelog-driven drift gate for `README.md` and `www/how-it-works.html`, mirroring the demo/showcase
  gate.** Cliff's own observation: `README.md` often goes stale relative to real functionality; `how-it-works.html`
  is unlikely to drift much on its own (most of the core pipeline it explains is already stable) but **is** worth
  a content update now given Local AI (inc 547) — see the increment that fixes this alongside the demo sweep
  for whether that content update landed in the same pass or needs a follow-up. **Proposal:** extend
  `tools/qa/changelog_drift.py` (built for the demo/showcase gates, inc TBD) with a third `_source_files()` glob
  scoped to whatever backend/frontend surface each doc actually describes, reusing the same `--refresh`/
  `--decline`/registry/CI-gate shape rather than a new mechanism per doc.
- **#70 The all-6-stage demo currency audit (2026-08-31/09-01, the same session that shipped #66/#67 and the
  changelog-drift gate) found real remaining gaps in Write and Synthesize beyond what was cheap to fix inline.**
  Fixed in the same session: the crosswalk "Open Registration/Publication Evidence" buttons silently served the
  wrong PDF for 10 of 12 Meta-Preregistration rows (`demo-runtime.js`'s pdf route now validates `attachment_id`
  against the paper's real attachments and blocks honestly on mismatch); the two page-less crosswalk rows'
  permanent "loading stored registration…" dead end (`08i_registration_comparison.jsx`'s `openSource`); the
  Citation Styles panel auto-firing a live preview POST in demo mode and rendering a raw error box
  (`35d_citation_styles.jsx` now gates it behind `isDemoMode()`); and `cap-fulltext` was reclassified
  `saved-inspectable` → `missing-snapshot` in `demo/experience-coverage-v1.json` (no matched route for
  `/papers/fulltext` exists at all — Library-wide full-text search 404s in the demo). **Still open, needs a new
  capture job or product decision:**
  - `cap-fulltext` (Read): needs an actual capture (one representative saved query over the 4 bundled PDFs) +
    matching `demo-runtime.js` route, or it stays honestly `missing-snapshot`.
  - `cap-cite-stance` (Write): all 3 saved Cite suggestions are `"support"` — no "contrast" or "mention" example
    exists despite the panel narrating all three; needs a recaptured canned claim/result set.
  - `cap-csl` breadth (Write): only one hardcoded style (`"apa"`) is ever servable; demonstrating real
    install/switch between ≥2 styles needs a new capture job, not just better error copy (already added).
  - `cap-bibliography` breadth (Write): saved renderings cover only 3 of 5 papers/one style (inherent to "only
    what the one canned Cite example touched") — extending needs a deliberate `export_demo_snapshot.py` scope
    decision.
  - `cap-contrasts` (Synthesize): zero citations have `status:"contradicted"` in the saved synthesis, so the
    "⚠ source disagrees" UI state is never demonstrated — needs a real sandbox run producing one, then promotion
    via the already-capable `tools/demo/promote_verified_demo_synthesis.py`.
  - `cap-extraction-candidates` (Synthesize): `capture_demo_extended_state.py` PUTs every workbench cell value
    directly and never calls the real `/propose` endpoint, so the accept/reject candidate UI never renders —
    fix is mechanical (call `/propose` before filling ≥1 row's cells) but needs the capture script touched.
  - `cap-extraction-anchors` (Synthesize): every workbench cell has `bbox_json: null` and a synthetic placeholder
    quote — needs a real exact-precision anchor captured via the actual select-in-PDF flow.
  - `cap-staleness` + `cap-registration-correction` (Synthesize): zero stale-comparison and zero rejected/
    incorrect-match registration-link examples exist; a deliberately-incorrect link seeded alongside the
    confirmed one would naturally produce both together.
  - `cap-registration-review` (Synthesize): all 12 crosswalk rows are `review_state:"unreviewed"` by deliberate
    privacy design (`snapshot_saved_registration_triage.py` strips real review notes) — needs a product decision
    on seeding 1-2 clearly-synthetic reviewed/dismissed rows.
  - `cap-raw-registration` (Synthesize): "Inspect Stored Registration" is unconditionally disabled — not a bug,
    a genuine OSF licensing constraint (no bundled full registration text to show); needs a product decision to
    either reword the showcase claim or build an excerpts-only substitute view.
  See the increment notes for this session's audit for the full per-capability evidence trail.
---

## 2. Needs a design decision from Cliff (not destructive/security — just your call)

- **#81 An answer's length should be proportionate to the question: split-and-stitch synthesis.**
  Raised by Cliff (2026-09-04), in his words: *"I'd rather get back 16 statements than 8 when I ask a
  question sufficiently complex to require 16 statements for the response to feel complete."* Prompted
  by Vasiliki's real question — *"What neural findings have been reported for fascination, comfort,
  hominess, or preference in built environments? Separate findings by construct and cite the supporting
  text."* Inc 575 stopped that crashing, but only by making the ask fit the allowance. **The real limit
  is untouched:** every synthesis is one call producing `minItems: 4, maxItems: 7` claims with 1–3
  citations — **21 quotes total, however complex the question**. Four constructs split that budget, so
  each gets 1–2 claims.
  - **Why this cannot be fixed by raising the cap again — the arithmetic decides the design.** Claim
    count and evidence richness compete for the *same* context window, and on the managed local model
    that window is 12,288 tokens:

    | claims | output tokens | + input (~3,257) | vs 12,288 |
    |---|---|---|---|
    | 7 (today) | 3,778 | 7,035 | fits |
    | 12 | 6,464 | 9,721 | fits |
    | 16 | 8,613 | 11,870 | **418 tokens of margin** |
    | 20 | 10,761 | 14,018 | **exceeds the context** |

    So 16 claims is *just barely* reachable in one call — and only by starving the evidence side, since
    every output token spent on a longer answer is one not available for retrieved chunks. Splitting
    across calls is the only way to grow the answer **and** the evidence together, because each call
    gets a fresh window. That is the argument for this item, and it is why "raise `maxItems` again" is
    not a substitute.
  - **Splitting is the mechanism; one coherent answer is the goal.** Cliff wants 16 statements, not four
    separate mini-reports — so stitching back into a single ordered answer is part of the requirement,
    not an optional presentation choice.
  - **Let the user name the parts where they already have.** Deciding how to decompose a question is the
    model making a structural claim about the literature — judgment, not narration, and the wrong side
    of PRINCIPLES #4 (deterministic substrate as source of truth) and #5 (the human is the filter).
    Vasiliki's question already listed its four constructs. Prefer a user-visible facet list (parsed and
    then *editable*, or entered explicitly); if the model ever proposes the split, show it before it is
    used, never silently.
  - **Per-facet retrieval is the other half of "some claims require more evidence."** One `top_k`
    (default 8, max 50) currently serves the whole question, so a four-construct question retrieves for
    all four at once and the rarest construct loses. A per-part retrieval budget fixes that at the
    evidence layer rather than by letting the model write longer.
  - **The honesty constraint on stitching:** claims may be *ordered* into one answer and must keep their
    own evidence and verification (each part is an ordinary `summarize_scope` run, so invariant #1,
    coordinate honesty, and caching all work unchanged). Do **not** generate a connecting or summarizing
    sentence across parts — no retrieved chunk supports a claim about the relationship *between* parts,
    so it would be exactly the unbacked narration the charter forbids. If two parts' claims disagree,
    that must remain visible rather than be smoothed away.
  - Cost/latency: N parts means N provider calls and N verification passes — minutes at Local AI speeds.
    Needs real progress reporting (invariant #5) and likely an explicit opt-in rather than becoming the
    default for every question.


- **#75 Debian/Ubuntu users have no update path at all — they must notice a release and re-download the
  `.deb` by hand.** Raised by Cliff (2026-09-03). Windows and macOS get Tauri's in-app updater (silent
  background download, prompt to restart); Linux gets only "Open release page" (`updater.rs:1-8`),
  because Tauri's updater plugin requires AppImage and inc 395 dropped AppImage. #71 made the cost
  concrete: anyone who installed the Linux build before inc 570 has one that never opened, and nothing
  in the app will ever tell them a fixed build exists.
  - **The reason AppImage was dropped no longer holds — this is the new information that reopens the
    question.** `INCREMENT-395-NOTES.md:74-85` records four `linuxdeploy` failures, and its conclusion
    was "a bundler fundamentally fighting a full embedded ML stack it wasn't designed around." Two of
    the four *were* that stack: torch's rpath'd internal C++ test binaries, and scipy/scikit-learn's
    uniquely-hashed vendored `libgfortran`/`libquadmath` (called out at the time as a genuine upstream
    wheel-packaging quirk, not fixable by pruning). **Inc 570 removed the embedded ML stack from the
    bundle entirely** — the `.deb` went 540.4 MB → 9.4 MB — so an AppImage would now wrap only the Rust
    shell plus `callosum-src`. The remaining blocker, `linuxdeploy` itself needing FUSE, already has a
    known fix in that same note (`libfuse2` + `APPIMAGE_EXTRACT_AND_RUN=1`).
  - **Options, for Cliff's call:**
    - **AppImage alongside the `.deb`.** Directly enables the *existing* Tauri updater, so Linux gets
      the same UX as Windows/macOS with no new mechanism, and the signing/`latest.json` infrastructure
      is already in place. Needs `darwin`-style platform entries added to `latest.json` and AppImage's
      own FUSE-at-runtime caveat on the user's machine considered.
    - **A signed APT repository** (GitHub Pages, or the existing clffwrkmn.net host). The canonical
      Debian answer and the one experienced users expect — `apt upgrade` just works, no in-app updater
      needed. Costs: repo GPG key management, a `sources.list.d` entry at install time, and hosting.
    - **Flatpak/Snap.** Own update channels and wide reach, but sandboxing needs checking against
      Callosum's real filesystem access (watched folders, `library_dir`, the user-chosen Zotero path),
      which is not incidental for a reference manager.
  - Whatever is chosen, the honest interim is to say plainly in Linux release notes that updating means
    re-downloading — see #71's closure note.

---

## 3. Gated — destructive / security / outward-facing sign-off, or an explicit maintainer decision

- **#52 Activate the hosted feedback relay and private Slack destination.** [non-code] [infra] [outward-facing]
  The in-app workflow and deployable relay shipped in inc 439; publication remains intentionally disabled until
  Cliff has a focused operations window. Create/select the private Slack channel and Slack app, enable an incoming
  webhook for that fixed destination, store `CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL` only in the hosted secret manager,
  deploy one HTTPS relay process behind a trusted reverse proxy, and configure clients with only the public
  `CALLOSUM_FEEDBACK_RELAY_URL`. Before enabling broadly: suppress bodies and authorization headers in proxy/APM
  capture for `/feedback/reports`; keep the relay's one-process limiter or add a shared ingress limiter before
  scaling; verify `/health` exposes only the configured boolean; submit a synthetic previewed report from Callosum;
  exercise missing-webhook, timeout, rate-limit, and disable paths; and confirm the message lands only in the
  intended private channel. Record the relay host/owner, monitoring and rotation procedure, then rotate by replacing
  the hosted secret, testing, and revoking the old webhook. Never put the webhook in a client `.env`, frontend/Tauri
  config, installer, log, issue, or feedback report. Full runbook: `feedback_relay/README.md`.
- **#42 Rotate the Gemini API keys** (and the CORE key pasted in chat during inc 75). [non-code — your manual
  action] `.gitignore` keeps all key material out of GitHub (verified via `git check-ignore`), so this is **not
  blocking** — but rotation is the only way to neutralize copies that exist in Dropbox version history / chat
  history outside git. Deferred by you.
- **#15 Sync — remaining threads.** [gated, non-code] Setup/enable/run UI, conflict review, server hardening,
  and the full SP4 sharing arc (identity → share → receive → revoke/block, staged like the original sync
  feature) all shipped — see `INCREMENT-BACKLOG-DONE.md`. **Still open, not code:** the live deploy of
  `sync_server/` on Postgres + wiring the Authentik audience [your infra]; a per-user storage quota + a real
  migration tool.
- **#49 Auto-updater — Cliff's own remaining rollout steps.** [non-code] The updater itself is live (inc 409) —
  see `INCREMENT-BACKLOG-DONE.md`. **Still open, not code:** (1) set the two `TAURI_SIGNING_PRIVATE_KEY`/
  `_PASSWORD` GitHub secrets yourself (`gh secret set`, from your own machine — the public key is already
  embedded in `tauri.conf.json`); (2) run the recommended throwaway `v0.3.0-rc1`→`rc2` rehearsal cycle (a real
  signed release, a scratch library — never your real 209-paper one) to prove the full check→download→ready→
  install→relaunch loop end to end before trusting it with real testers.

---

## 4. Longer-horizon future tracks — remaining slices only

*(Full design docs live in `future-tracks/`; most of these tracks are mostly-to-fully shipped — only the
genuinely-open remainder is listed here. Each still needs its own design + your graduation call, and must pass
the Principles + A-A gates before build.)*

- **#24 Bayesian auditor — ANOVA/regression BF.** Not a build queue item: **declined as a documented finding**
  (a candidate failed the J=2 → two-sample-t reduction check; no in-env anchor exists). **Rechecked 2026-08-10,
  confirmed still blocked, finding sharpened, not just re-asserted:** pingouin (this project's own dev-only
  verification anchor for the t-test/correlation BFs) still has no ANOVA/regression function — confirmed by
  reading its current `bayesian.py` source directly, not assumed stale. No validated Python port of Rouder et
  al. (2012) exists anywhere findable; the one real implementation of that method (a MATLAB toolbox built
  explicitly from the 2012 paper) requires the *full raw dataset + a model formula*, not summary statistics —
  meaning this isn't just "unverified," it's **structurally unreconstructable** from what a paper reports
  inline (F, df, N), unlike the t-test/correlation cases that already shipped. Revisit only if a trusted
  anchor (R BayesFactor / a validated Rouder-2012 quadrature) turns up **and** a way exists to extract
  sufficient design/cell-size info from papers — a second, separate gap this recheck surfaced.
- **#33/#34 Citation & bibliography engine + plugins — the LibreOffice adapter's next phase.** The full P0/P1/P2
  build-out (incs 106-464) is shipped (`INCREMENT-BACKLOG-DONE.md`). **Word and Google Docs parity also
  already shipped their own SP1-3 arcs (incs 164-166, 169-171) — corrected 2026-08-18, see `.claude/CLAUDE.md`'s
  "Cross-editor adapters" paragraph; this entry previously and incorrectly said this work "hadn't started."**
  **Still genuinely open:**
  - Traveling-library portability (named a P1 future track, never scheduled).
  - **#43** a true Google Workspace Marketplace one-click install (its own project — GCP project, OAuth
    verification, a public privacy policy, Google app review; likely overkill for a local-first single-user
    tool — build only if it becomes worth the ongoing maintenance cost).
  - **Word/Docs P1 parity, in progress (scoping resumed 2026-08-18).** Both adapters store an `items` array
    per citation cluster but only ever populate one (grouped citations/locators not yet wired up — the exact
    LibreOffice-roadmap-doc gap, now confirmed present on both cross-editor adapters too); neither has
    section-scoped bibliographies yet. Google Docs Refresh renumbers in insertion order, not true document
    order (Word's own Refresh already scans true document order, confirmed — this is Docs-specific).
  - **Word-on-the-web shipped inc 482 (SP4)** — the same task pane now runs through the existing cloudflared
    relay Google Docs already uses (a real `AccessControlMiddleware` exemption-list bug was found and fixed
    in the same increment; see `INCREMENT-482-NOTES.md` + `security-audits/2026-08-18_word-online-relay.md`).
    **Both desktop AND Word-on-the-web live-verified 2026-08-28 (inc 508)** — search-insert, Suggest,
    Refresh/bibliography, and Flatten all confirmed working in real Word (desktop) and real Word on the web
    (via the tunnel) for the first time; found + fixed three real bugs along the way (a `tools/run_https.py`
    `sys.path` bug, a wrong Trust-Center sideload instruction in the README, and a `taskpane.js` styles-dropdown
    race where `loadStyles()` ran before the tunneled user had saved their access token and never retried — see
    `INCREMENT-508-NOTES.md`).
  - **Word/Docs parity toward LibreOffice — phased roadmap (scoped 2026-08-28).** LibreOffice's adapter shipped
    every P0/P1/P2 item in `.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md`
    (the shared, generically-written "word processor plugins" roadmap doc — the right reference for Word's own
    build-out too, not LibreOffice-specific). Word/Docs only has the thin SP1-4 slice (search-insert, suggest,
    refresh/renumber, style switch, flatten, web relay). Sequencing for the remaining gap, confirmed against
    real Office.js API capabilities (WordApi 1.3-1.5: `Range.parentContentControlOrNullObject`,
    `Range.insertBookmark`/`.hyperlink`, `Word.Footnote`/`Endnote`, `Word.Field.code`) — **Office.js has no
    UNO-`enterUndoContext`/`leaveUndoContext` equivalent**, so any "verified one-step Undo/Redo" LibreOffice
    promises can only be approximated (build-before-mutate + explicit manual revert-on-failure), never
    guaranteed as one native Ctrl+Z entry — flag this honestly wherever it matters, don't silently promise
    LibreOffice-level safety:
    - **P0 items 1-5 (grouped citations, locators/prefix/suffix, edit/delete) shipped inc 509** — a real
      composer mirroring `adapters/libreoffice/composer.py`'s assembly model; the shared backend
      (`render_document`/`citeproc_runner.js`) needed zero changes, it already supported this. See
      `INCREMENT-509-NOTES.md`.
    - **P0 remainder — Document diagnostics shipped inc 512.** A read-only "Document diagnostics…" command
      (malformed/unresolvable citations, orphaned or retraction-flagged cited works, bibliography health),
      walking `context.document.contentControls` instead of UNO ReferenceMarks; "unsupported schema version"/
      "duplicate mark identity" have no Word equivalent (disclosed, not silently dropped). Fixed a real bug
      found while scoping it: Word's composer trusted the stored `csl_json.id` instead of stamping a reliable
      `"callosum-<paperId>"` id the way LibreOffice's `_build_records` already does — see
      `INCREMENT-512-NOTES.md`. **Inc 513 fixed a second real bug found live**: orphan detection wasn't
      trash-aware (sourced from `check-selected`'s `not_found`, whose internal lookup has no `deleted_at`
      filter) — now uses a trash-aware per-id `/papers/export` existence check instead — see
      `INCREMENT-513-NOTES.md`. **P0 fully closed, inc 515**: the bibliography-bounds safety review confirmed
      Word's Content-Control-bounded bibliography is structurally safe already (no code change needed — Word
      gets the safety property LibreOffice needed incs 374-384 to earn, for free from its data model); Flatten
      now shows a pre-confirm citation/bibliography count, an honest "Callosum can't save a copy for you"
      reminder (Office.js has no `saveAs`, confirmed), an opt-in style-setting cleanup, and a post-operation
      integrity re-scan — see `INCREMENT-515-NOTES.md`.
    - **P1 — "Citations in this document" panel shipped inc 516.** Every unique cited work, occurrence count,
      orphan/retraction badges (reusing the shared `checkPaperExistence()` helper factored out of Document
      diagnostics in the same increment), click-to-navigate, client-side search. Scoped narrower than the
      roadmap's wishlist: "metadata conflicts" and "most recent citation" skipped (disclosed, not silently
      dropped — see `INCREMENT-516-NOTES.md`). **Accessibility pass shipped inc 517** — icon-button
       `aria-label`s, Enter-to-add-top-result in search, Escape-to-cancel an in-progress assembly; tab order/
       keyboard reachability were already correct (confirmed by direct read, plain HTML with no `tabindex`
       overrides) — see `INCREMENT-517-NOTES.md`.
      **Inc 519 closes the storage prerequisite the 2026-08-18 design decision approved but inc 509 did not
      carry through:** new Word citations keep CSL-JSON in a versioned document Custom XML Part and put only its
      opaque ID in the Content Control tag. Legacy base64 tags migrate on Refresh/Edit; duplicate references are
      de-aliased; delete/Flatten clean their parts; missing/malformed parts fail closed. This prevents grouped
      citations from making `.tag` grow with full scholarly metadata before native note placement deepens the
      format. Pure logic is Node-tested; the Office.js lifecycle is explicitly not yet live-verified. See
      `INCREMENT-519-NOTES.md`.
      **Inc 520 ships native note-style placement:** the style catalog's existing `citation_format=note` reveals
      a per-document Footnotes/Endnotes preference; Insert creates a native Word note or adds to an existing
      matching note; Refresh scans all native note bodies and passes Word's real one-based position as
      `noteIndex` (ordinary notes leave gaps; multiple clusters in one note share an index). Mixed inline/note,
      footnote/endnote, or preference/existing-type placement fails closed and diagnostics explains it. The same
      all-story scan now covers panel navigation, Delete, and Flatten. Pure rules are tested; Office.js note
      lifecycle is explicitly not yet live-verified. See `INCREMENT-520-NOTES.md`.
      **Inc 521 starts bibliography item #11 with safe document-local categories:** each resolvable cited work in
      the existing document panel can receive one bounded label; the managed bibliography groups named categories
      alphabetically, preserves citeproc order within them, and leaves unassigned/mixed entries under **Other
      references**. Storage is bounded and fail-closed on missing entry identity; failed refresh restores the
      prior setting. Pure logic is tested; Office.js settings/UI/layout are not yet live-verified. **Inc 522 adds
      bounded batch assignment:** explicit checkboxes, Select visible/Clear, mixed-selection safety, one atomic map
      update, and one Refresh/rollback for the whole selection. Pure logic is tested; live Word interaction remains
      deferred. **Inc 523 adds explicit category precedence:** active named groups can move up/down in a staged
      editor, reset removes the setting, current unranked groups fall back alphabetically, Other remains last, and
      Save performs one Refresh with exact-property rollback. Pure logic is tested; live Word interaction remains
      deferred. **Inc 524 adds heading-scoped bibliography blocks:** strict hidden-heading/generated-block Content
      Control pairs share a random bounded identity; semantic membership is the nearest heading subtree; the full
      citeproc result is projected without changing prompts/rendering; multiple/full blocks coexist; Refresh,
      diagnostics, removal, categories, and Flatten understand the pair. It requires WordApi 1.6 and deliberately
      refuses note styles until native note anchors can be mapped to headings without guessing. Pure logic is
      tested; live Word interaction remains deferred. See `INCREMENT-521-NOTES.md` through
      `INCREMENT-524-NOTES.md`. **Inc 525 adds opt-in bibliography title/DOI links:** the backend's existing
      validated per-entry spans now survive category/order and section projection, with Unicode code-point
      conversion and exact paragraph-local single-match checks before WordApi 1.3 applies any hyperlink. One
      bounded document setting governs full and section blocks; disable restores the same plain generated text
      without touching ordinary manuscript links. Unsafe, malformed, misaligned, overlapping, or ambiguous
      metadata remains plain. No backend/citeproc/text change. Pure logic is tested; live Word interaction remains
      deferred. See `INCREMENT-525-NOTES.md`.
      **HANDED OFF TO CODEX 2026-08-28** (Cliff's Claude usage maxed out ~48h) — see
      `.claude/docs/2026-08-28_codex-word-parity-handoff.md` for the exact remaining scope, verification
      requirements, and known traps. A dedicated style-browser UI is
      low-value — Word's style dropdown already reflects anything
      installed via Settings' shared catalog.
    - **P2/leapfrog (started inc 526):** **evidence-aware Suggest-Citation details closed inc 526** — the full
      matched passage, complete support/mention/contrast signal, plain-language retrieval reason, shared-threshold
      weak-evidence warning, editable auto page locator, and region-precision **Open in PDF** now sit behind each
      Word suggestion's **Details…** action. An inserted suggestion adds one bounded evidence snippet/page/chunk
      record to the existing Custom XML payload; Edit preserves it and the document panel exposes **View
      evidence…**. The response, models, prompt, ranking, user-choice boundary, and fully local/no-egress posture
      are unchanged. Pure/static logic is tested; live Word interaction remains deferred. See
      `INCREMENT-526-NOTES.md`. **Open-science statement insertion closed inc 527:** Word now mirrors the seven
      existing author-asserted disclosure kinds and canned starting phrases, reads/stages/clears through unchanged
      `/statements/pending`, and inserts the exact bounded author-reviewed draft as ordinary text at the cursor.
      No Content Control, AI/provider call, inferred fact, backend contract, or document mutation occurs during
      staging. Pure/static logic is tested; live Word interaction remains deferred. See `INCREMENT-527-NOTES.md`.
      **Citation coverage closed inc 528:** Word now performs the same local structural scan for 3+ consecutive
      substantive paragraphs without a Callosum citation anchor, counting inline and native-note anchors at the
      main-text paragraph while excluding headings, short transitions, tables, and managed bibliography blocks.
      This is explicitly a neutral review prompt, not a support/citation verdict. The originally grouped
      "integrity-preflight" half required no new control: **Document diagnostics…** already performs the fresh,
      trash-aware existence + `POST /methods/retraction/check-selected` retraction check (incs 512-513), so inc
      528 did not duplicate it. See `INCREMENT-528-NOTES.md`. **Zotero field conversion closed inc 530:** after
      verifying Zotero's current first-party Word integration source and WordApi 1.5 field contracts, Word now
      scans exact `ADDIN ZOTERO_ITEM CSL_CITATION {json}` fields, previews and snapshot-checks a bounded conversion,
      resolves embedded records through the unchanged local inc-464 endpoint, preserves grouped per-item overrides,
      and replaces only verified inline fields through the existing Custom-XML/Refresh lifecycle. Note-style,
      Bookmark-mode, malformed, oversized, and ambiguous material remains untouched; bibliography replacement is
      conditional. Office.js mutation remains awaiting the consolidated live Word check. Mendeley
      Cite / EndNote CWY field conversion stay declined for Word for the identical reason already documented
      for LibreOffice (no complete vendor payload contract) — see
      `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`.
  - AppSource / broader public distribution readiness (design with it in mind; do not build the actual
    submission/review process until there's a real reason to).
  - **LibreOffice/Word/Docs support in the packaged desktop (Tauri) app — completed 2026-08-29 (a
    separate Claude-driven track, NOT part of the Codex Word/Docs-parity handoff above — different files, no
    overlap: `app/desktop-shell/*`, `app/backend/api/routers/libreoffice.py`, Settings UI, confirmed via `git
    diff` against Codex's own commits before starting).** Full plan:
    `.claude/backups/plans/2026-08-29_tauri-word-libreoffice-googledocs-support.md`. **Phase 1 shipped inc 531**:
    the packaged app now prefers its last-successful port across ordinary restarts (`backend.rs`'s
    `read_preferred_port`/`pick_port`, falling back to a fresh random pick on conflict — same access-control
    boundary as before, CORS/`AccessControlMiddleware`, not port obscurity); Settings shows the live server
    address with a Copy button; and a one-click "Point LibreOffice at This Instance" button
    (`POST /integrations/libreoffice/set-server-url`, loopback-only, rejects a Remote-Access-tunnel Host) writes
    the adapter's own `~/.callosum/libreoffice.json` sidecar directly — closing the LibreOffice-in-the-packaged-
    app gap completely. **Phase 2 shipped inc 532:** an explicit packaged-Settings action creates a localhost-
    only end-entity certificate, restricts its private key, installs/verifies per-user OS trust, and enables a
    Tauri-supervised fixed `127.0.0.1:8443` HTTPS Uvicorn companion against the same DB/library/version as the
    main app. Trust mutations are loopback + Settings-header gated; the companion gets Remote access disabled
    only in its own environment; disable removes trust/material; browser/source workflows retain the separate
    dev-certificate launcher. Windows uses PowerShell `Import-Certificate` (not `certutil`); macOS targets the
    login keychain but awaits live hardware QA. See `INCREMENT-532-NOTES.md` and
    `.claude/security-audits/2026-08-29_tauri-word-https.md`. **Phase 3 shipped inc 533:** packaged Settings can
    explicitly start/stop a Tauri-owned Cloudflare Quick Tunnel and copy its temporary URL. The connector targets
    a separate Uvicorn child whose bearer gate fails closed whenever Remote access is off, so cloudflared's
    loopback forwarding can never inherit the ordinary local-trust path. Tauri isolates cloudflared from any
    existing user config, waits for strict URL issuance, owns both process trees, and removes both on stop/exit.
    Quick Tunnel's bearer-only/no-ingress-allowlist tradeoff remains visible; source and named-tunnel workflows
    remain available. See `INCREMENT-533-NOTES.md` and
    `.claude/security-audits/2026-08-29_tauri-quick-tunnel.md`.
- **#35 My Publications — Layer 4.** Deterministic Layer 4 is complete (`INCREMENT-BACKLOG-DONE.md`). **Still
  open:** optional LLM narration over the already-grounded data remains deferred — no need to build it unless
  narration becomes useful.
- **#36 Meta-analysis — the assisted-extraction funnel's next escalations.** The consumer-side reporting
  auditor, effect-size converter, extraction workspace, batch drafting, and retrieval narrowing are all shipped
  (`INCREMENT-BACKLOG-DONE.md`). **Far future, its own workspace:** screening/PRISMA, double-coding/IRR
  (human-only — the track's no-independent-coder veto holds), RoB instruments, figure extraction (point at
  WebPlotDigitizer, don't build it).
- **#37 Equity & integrity signals — remaining, narrowed 2026-08-17.** The overlooked-work lens, positive
  self-correction, the real field self-citation baseline (= #25), and analytic-flexibility surfacing are shipped
  (`INCREMENT-BACKLOG-DONE.md`). Of the two forensic candidates it also named, stylometric inconsistency is
  declined (§6). **Still open, blocked on external data, not a design question:** an evidence-grade
  replication badge and a null-engagement badge — neither Crossref's relation vocabulary nor PubMed's publication
  types encode either fact today; an LLM-inferred version would only ever be candidate-class, which can't back
  the deterministic badge the design promised. Revisit only if a real metadata source appears (same disposition
  as #24).
- **#38 Research-impact analytics.** [future track — gated] Opt-in, local-first, commons-structured measurement
  of whether Callosum changes how people research. **Project A (local usage analytics) shipped** —
  `INCREMENT-BACKLOG-DONE.md`. **Project B (cross-user impact signal) remains far-future, gated** — needs N>1
  users, an accounts/hosting decision, and the design doc's own research-grade consent flow (Stage 3 on-device
  aggregation + Stage 4 opt-in contribution, neither built). Must still pass Principles + the A-A values layer
  (default-deny, compute-locally/transmit-summaries-only, public field registry, commons reciprocity) at that
  graduation.
- **#40 Publishers tool — deferred signals.** SP1a/SP1b + SciELO/TOP Factor/AJOL/NLM MEDLINE/thumb auditability
  all shipped (`INCREMENT-BACKLOG-DONE.md`). **Still open:** self-archiving/green-route (needs a
  Jisc-registered API key only the maintainer can obtain); Redalyc (TLS hostname mismatch + maintainer-only
  registration, live re-checked)/Latindex (confirmed closed); COPE (Cloudflare-bot-blocked)/OASPA (no structured
  members endpoint) membership; user exclusion/filtering (deliberately deferred — the design doc flags it as
  ethically fraught, "the disfavored extreme — it reintroduces the 'these are bad' valence").
- **#41 User-authored modules (plugins) — a real design doc now exists (scoping pass 2026-08-19).**
  The admin-gated `plugins_enabled` foundation toggle shipped (inc 483, `INCREMENT-483-NOTES.md`) —
  deliberately inert, controls nothing yet. See
  `.claude/docs/specs/2026-08-19-admin-gated-plugins-design.md` for the full scoping: a curated
  plugin "store" (not an open marketplace), a panel-modules-vs-source-providers decomposition
  (**source providers are explicitly sequenced AFTER panel modules**, not started), and a concrete
  direction for the principle-enforcement crux (constrain a module to typed fact/candidate output,
  let callosum's own already-trusted components do the rendering). **Still fully open, not
  started:** the plugin data model, a loader, sandboxing (browser-side for panel modules; the
  egress-centric trust problem is unresolved for source providers), and the review/store pipeline.
  The stale future-track file (`future-tracks/opus4.8_future-tracks_plugins.md`) now points at the
  design doc as the live reference; the two real existing internal registries
  (`registerPaneTab`/`build_default_feed_registry`) carry marker comments naming them as candidate
  extension points, deferred pending the design doc's open questions.
- **#57 Whole-library migration (Zotero/Mendeley/EndNote).** A user's *entire* existing
  reference-manager library moving into callosum, distinct from the #33/#34 "Traveling-library
  portability" line above (that one is about a single document's own in-document citations, not a
  whole library).
  - **Phase 1 shipped, inc 484:** the already-built native Zotero importer
    (`app/backend/importers/zotero.py`) — `POST /library/zotero/import`, a Library "+ Add" entry,
    and an onboarding-wizard option.
  - **Phase 2 partial, inc 486:** EndNote's documented RefMan (RIS) transfer path is covered by the
    existing generic importer; current Clarivate RIS aliases are parser-tested and Help gives the
    shortest export/import route. **Still open:** verify end to end against a real EndNote-created
    export—the checked-in contract fixture is explicitly only a synthetic stand-in.
  - **Phase 3 feasibility spike complete, inc 487:** Zotero's documented **Mendeley Reference
    Manager (online import)** is the practical fuller-library bridge; Callosum guides the user to
    run it once, then uses the shipped native Zotero importer. Online-sync/auth, personal-library,
    custom-field, and Mendeley Cite document boundaries are explicit; no protected-store reader.
  - **Phase 4 shipped, inc 485:** Zotero PDF highlight/underline positions are bounded, validated,
    and mapped into callosum's own PDF-space bbox/page coordinates for their owning attachment;
    ambiguous/unsupported geometry retains raw provenance and is not drawn. Inc 489 hardening pins an already-
    exact row to its proven attachment across a later Zotero relink and covers sibling PDFs/rotated pages.
  - **Phase 5 research gate complete, inc 488; implementation remains open/gated:** first-party sources confirm
    Mendeley Cite content controls and EndNote `ADDIN EN.CITE` Word fields/Traveling Library, but do not publish
    either complete, versioned payload contract. No converter was built from conflicting third-party reverse
    engineering. Reopen only with a vendor schema/supported API or an explicitly approved, multi-version fixture
    corpus plus fail-closed preservation safeguards. **Re-verified 2026-08-29 (fresh research, not re-guessed):
    still correctly gated** — no vendor schema, no open-source reference implementation, and no reverse-
    engineering write-up exists for Mendeley Cite's Word content-control payload; a well-resourced competitor
    (Paperpile) independently confirms the same gap as of Feb 2025. **This is NOT the same thing as Phase 2/3
    below being good enough** — see Phase 6.
  - **Phase 6 (started 2026-08-29): real Mendeley + EndNote whole-library import (metadata + PDFs + folders),
    handed to Codex.** Phase 2 (EndNote RIS) and Phase 3 (Mendeley-via-Zotero) turned out to have real gaps a
    live user hit: RIS import is metadata-only (no PDFs, no folders — confirmed by reading
    `app/backend/metadata/citation_import.py` directly), and the Zotero bridge requires installing an entire
    separate application just to leave Mendeley. Research doc:
    `.claude/docs/research/2026-08-29_mendeley_endnote_native_import.md`. Handoff:
    `.claude/docs/2026-08-29_codex-mendeley-endnote-import-handoff.md`. Summary: Mendeley gets a real OAuth2
    importer against the official `dev.mendeley.com` REST API (no Zotero needed — **blocked on the maintainer
    registering an OAuth app there first**); EndNote gets a `.enlx` Compressed Library importer (metadata + PDFs
    + groups in one file). **Increment 535 resolved the reader-strategy question empirically:** no maintained
    pure-language row reader was found, while a disposable MariaDB 10.11 engine successfully upgraded and read
    EndNote's public X7 MyISAM `refs` table from a copy. **Increment 541 resolved the managed-engine design:**
    Windows and Debian live tests proved that one-shot `mariadbd --bootstrap` can rebuild/read a private copy,
    write bounded `--secure-file-priv` output, and exit under `--skip-networking`, eliminating a persistent
    service/listener/account. A pruned experimental Windows runtime was 29 files/20.24 MB. The next approved seam
    was completed in **increment 542**: a developer-only executor now performs bounded archive preflight,
    digest-verified copy-only extraction, deterministic allowlisted runtime identity, fixed SQL/direct argv,
    bounded output/timeout cleanup, and path-free aggregate receipts. A fresh official-Windows live run returned
    the public fixture's 59 rows/54 columns and left no process. **Increment 544 closes the launcher-only Linux
    identity gap:** a deterministic 28-file launcher/message/charset bundle extracted from the pinned official
    image ran directly on Debian 12 outside Docker, reproduced the same schema receipt, resolved all 18 OS-owned
    dependencies, and remained identity-stable after relocation. It is not imported by production. Shipping
    **Increment 545 completes the engineering license/provenance review:** MariaDB is GPL-2.0-only and remains a
    separate optional process; official Linux binary/source hashes and signatures plus a deterministic 31.8 MB
    stripped candidate are proven. Distribution is still blocked on qualified legal approval of the aggregate
    boundary and implementation of the specified source/notices/signatures/transformation kit. **Increment 546
    closes the runtime-specific Linux ABI/package-policy gate:** the exact candidate passed seven Ubuntu/Debian
    releases as root and uid 1000; support is conservatively limited to Ubuntu 22.04/24.04/26.04 and Debian 12/13
    inside Callosum's amd64 `.deb`, with five declared OS libraries and no vendored system copies. Shipping remains
    gated on an actual packaged-app install matrix after legal approval, macOS build/sign/notarization, a real
    attached-PDF fixture, and a separate modern SQLite-era fixture; Docker is not an end-user prerequisite.
    Fixtures remain gitignored at `.claude/backups/endnote-fixtures/`. **Increment 537 added the safe, dormant
    Mendeley transport scaffold:**
    version-pinned/bounded documents, folders, memberships, files, signed-download redirect, and OAuth exchange
    primitives with hermetic tests. It also found the official authorization-code flow still requires a
    confidential secret, documents no PKCE, and pins one redirect URI—a real packaged-desktop blocker beyond
    merely obtaining credentials. No callback/token persistence/UI is published until registration capabilities
    and safe secret/redirect ownership are proven live. **Increment 538 added the dormant snapshot import core:**
    complete synthetic v1 document/folder/membership snapshots validate before writes, map through the existing
    CSL paper contract, deduplicate via canonical identity plus stable `mendeley-document` provenance, and
    atomically populate the existing imported-collection hierarchy. Identity disagreement, orphan/cyclic folders,
    and unknown memberships fail closed. No route, token use, live request, PDF handling, or UI exists; the newly
    supplied gitignored secret does not by itself solve client-ID/redirect/desktop-confidentiality. **The shared
    imported-folder/group → axis seam shipped in
    increment 536:**
    Zotero now preserves `parentCollectionID`, previews top-level folders in its existing import dialog, and only
    on explicit action snapshots descendant-inclusive membership into idempotent ordinary axes. Curated is the
    default; the unchecked keyword option keeps exact folder papers as manual anchors and reuses local scoring.
    The generic provenance/API seam already accepts future `mendeley` and `endnote` collection rows. See
    §6 below — this does **not** contradict the "folders/collections declined" entry; that decision was about
    manual folder-creation inside callosum, not imported structure from another tool.

---

## 5. Open proposals (undecided, not gated on anything — just not prioritized)

*(none currently — the scratch/ephemeral axis proposal was resolved 2026-08-09; see §6.)*

---

## 6. Declined / will-not-build (recorded so it's not re-proposed)

- **Folders/collections hierarchy** — superseded by axes (a coherent set → axis; an arbitrary flat set → tag;
  "read this week" → the needs-review filter; the Curated Axis is the manual-container path). **Scope note
  (2026-08-29):** this was a decision about *manual* folder-creation inside callosum's own UI — it does not
  apply to *imported* folder/collection structure arriving from another tool (Zotero/EndNote/Mendeley), which
  is a different question with its own scoped feature under #57 Phase 6 (map imported structure onto axes).
- **Arbitrary manual nesting** — declined; when nesting lands it's recursive *semantic* sub-axes (the My-Pubs
  subheading prototype), not folder-style nesting.
- **PDF translation** — out of scope.
- **Cloud multi-agent "write my review"**, website-bibliography publishing, mind-mapping/Alfred/Todoist
  integrations, embedded closed models, casual data-from-charts extraction — all declined.
- **The `.btn-*` divergent-button migration** — declined 2026-07-06 (maintainer decision pass): the divergent
  ghost/icon buttons stay documented exceptions per inc-86; new CSS already follows the canonical `.btn-*` rules.
- **A unidimensional star/paper rating** — declined 2026-07-06: reduces a paper to one number, erasing the
  multi-dimensionality tags capture. Color tags only (#A5/#207), never a rating field.
- **A tag's source as an always-on label/icon** — declined 2026-07-06: kept aesthetic-only (muted styling +
  tooltip + the All/Yours/Keywords filter already convey provenance).
- **A scratch / ephemeral axis** — declined 2026-08-09 (confirmed with Cliff, first item of the post-P2 backlog
  sequence): the doc that proposed it already flagged doubt ("may already be covered"), and checking against the
  current codebase confirmed it — axis deletion is already 1 click + 1 confirm (`15_axes.jsx`'s `remove()`,
  `window.confirm`), and full-text search (A3, FTS5, `fulltext_repo.py`) already covers "quick lookup without
  committing to an axis." The one thing genuinely uncovered — auto-expiry, so a throwaway axis vanishes without
  the user remembering to delete it — was declined on its own terms: silently discarding user data has no
  precedent anywhere else in this codebase (papers go to Trash, never straight deletion, for exactly this
  reason), so auto-expiry would cut against an established value rather than fill a real gap.
- **Duplicate-publication / salami-slicing detection** (backlog #54's cross-paper branch) — declined 2026-08-09
  after research, not guessed: the research-integrity literature is explicit that there is **no algorithmic
  detection method** for redundant/overlapping publication across separate papers — it requires expert peer
  judgment about whether findings should have been one paper, not something a deterministic check can answer.
  Any automated attempt would mean guessing at an author's intent with no reliable evidence chain — the
  APPROACH-AVOIDANCE no-accusation boundary, not a data-consistency question. The narrower, genuinely
  buildable half of #54 — `scrutiny`'s actual within-paper repeated-value counting functions, which the
  design doc's "duplication analysis" mention actually pointed at — shipped as inc 469's honestly-framed
  repeated-values checker instead; see `INCREMENT-BACKLOG-DONE.md`.
- **Stylometric inconsistency** (backlog #37's forensic candidate #5,
  `future-tracks/opus4.8_future-tracks_equityintegritysignals.md`) — declined 2026-08-10, confirmed with Cliff.
  The source doc itself flagged this as an open question for the user ("the noisiest and most
  accusation-adjacent item in the entire residual — it points at *people*, not statistics... there is a real
  case that recording it at all risks a later blunt implementation"); even the doc's own hard-gated "neutral
  span-pointing signal, never an authorship claim" version keeps the accusation-adjacent shape front and
  center. Same disposition as the declined salami-slicing branch of #54 — the A-A no-accusation veto, not a
  data-consistency question.
