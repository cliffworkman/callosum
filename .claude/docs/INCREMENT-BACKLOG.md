# Increment backlog — MOVED TO GITHUB ISSUES (2026-09-10)

> **The live open backlog is now GitHub issues:**
> <https://github.com/cliffworkman/callosum/issues>
>
> This file is a **pointer stub**, not the queue. It exists so the ~1,800 historical
> `backlog #N` references scattered across the increment notes, CLAUDE.md, and memory stay
> resolvable after the migration. Do **not** add new open items here — open a GitHub issue.

## Where the open queue lives now

The 733-line open backlog was migrated to GitHub issues on 2026-09-10. Filter the tracker by the
category labels:

- **`near-term`** — small, self-contained, no design decision needed.
- **`needs-decision`** — awaiting a design decision from the maintainer.
- **`future-track`** — longer-horizon; each has a design doc under `.claude/docs/future-tracks/`.
- **`blocked`** — waiting on an external dependency or data source.

Existing feature issues (#21–#32, opened directly on GitHub before the migration) were labeled the
same way.

## Closure discipline going forward

- **New work → open a GitHub issue** (with a category label). Never re-open this file as a queue.
- **When an item closes → close its issue**, referencing the increment in the close comment or
  commit (e.g. `Closes #56`). The per-increment narrative still lives in
  `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md`, which stays the source of truth for *what
  happened*.
- **`INCREMENT-BACKLOG-DONE.md`** is now a **frozen historical archive** of everything that shipped
  *before* the migration — `grep "#N" INCREMENT-BACKLOG-DONE.md` still resolves a closed legacy tag.
  New closures are not appended to it.

## Gated maintainer/infra items (NOT public issues)

Legacy `#42` (key rotation), `#49` (updater signing-secret + rehearsal), `#52` (feedback-relay +
Slack), and `#15` (sync live-deploy + quota/migration) are the maintainer's own ops actions and
some name secrets, so they were kept **out of the public tracker**. They live in the gitignored
`.claude/MAINTAINER-TODO.md`.

## Legacy `#N` → GitHub issue map (open items migrated 2026-09-10)

Historical references say "backlog #57"; GitHub auto-numbered the migrated issues, so the numbers
do **not** line up (e.g. legacy `#57` is GitHub issue #56). Resolve them here:

| Legacy `#N` | GitHub issue | What |
|---|---|---|
| `#24` | [#48](https://github.com/cliffworkman/callosum/issues/48) | Bayesian ANOVA/regression BF (parked) |
| `#28` | [#40](https://github.com/cliffworkman/callosum/issues/40) | Feed: remaining slice (register()-per-source) |
| `#33/#34` | [#49](https://github.com/cliffworkman/callosum/issues/49) | Word/Docs parity remainder (legacy #33/#34) |
| `#35` | [#50](https://github.com/cliffworkman/callosum/issues/50) | My Publications Layer 4 narration |
| `#36` | [#51](https://github.com/cliffworkman/callosum/issues/51) | Meta-analysis far-future escalations |
| `#37` | [#52](https://github.com/cliffworkman/callosum/issues/52) | Equity/integrity: replication + null-engagement badges |
| `#38` | [#53](https://github.com/cliffworkman/callosum/issues/53) | Research-impact analytics Project B |
| `#40` | [#54](https://github.com/cliffworkman/callosum/issues/54) | Publishers tool deferred signals |
| `#41` | [#55](https://github.com/cliffworkman/callosum/issues/55) | User-authored modules (plugins) |
| `#57` | [#56](https://github.com/cliffworkman/callosum/issues/56) | Whole-library migration remainder |
| `#64` | [#41](https://github.com/cliffworkman/callosum/issues/41) | Dependabot glib GHSA on desktop-shell Linux build |
| `#65` | [#42](https://github.com/cliffworkman/callosum/issues/42) | Real in-reader PDF find/search |
| `#68` | [#43](https://github.com/cliffworkman/callosum/issues/43) | Release tag -> in-app what's-new banner |
| `#69` | [#44](https://github.com/cliffworkman/callosum/issues/44) | Changelog drift gate for README / how-it-works |
| `#70` | [#45](https://github.com/cliffworkman/callosum/issues/45) | Remaining demo-currency gaps (Write / Synthesize) |
| `#73` | [#37](https://github.com/cliffworkman/callosum/issues/37) | Linux CI lanes pin ubuntu-22.04 (label being retired) |
| `#75` | [#47](https://github.com/cliffworkman/callosum/issues/47) | Debian/Ubuntu update path |
| `#77` | [#38](https://github.com/cliffworkman/callosum/issues/38) | llama.cpp/Qwen in THIRD-PARTY-NOTICES.md |
| `#78` | [#39](https://github.com/cliffworkman/callosum/issues/39) | Branded, stateful desktop startup loader |
| `#79` | [#34](https://github.com/cliffworkman/callosum/issues/34) | Query-scope synthesis materializes the entire library |
| `#80` | [#33](https://github.com/cliffworkman/callosum/issues/33) | Automate the release version bump (not the Tauri build) |
| `#81` | [#46](https://github.com/cliffworkman/callosum/issues/46) | Split-and-stitch synthesis |
| `#82` | [#35](https://github.com/cliffworkman/callosum/issues/35) | Exclude reference-list chunks from synthesis retrieval |
| `#83` | [#36](https://github.com/cliffworkman/callosum/issues/36) | run_dev.py leaves orphaned children on teardown |

*(Closed legacy numbers not in this table shipped before the migration — see
`INCREMENT-BACKLOG-DONE.md`.)*

---

## Declined / will-not-build (recorded so it's not re-proposed)

Preserved verbatim from the pre-migration backlog. These are decisions, not open work, so they were
not minted as issues.

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
