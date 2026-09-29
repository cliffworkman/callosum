# Worktree topology (current state)

This file records the **current** checkout topology, not history — update it in place when the
topology changes again rather than appending. For the historical narrative of *why* the primary
checkout was ever off `main`, see `.claude/changes.md` (2026-09-17 entry) and the Ask-CLI research
branch's own `.claude/SCRATCH.md` (only present in its dedicated worktree, see below).

**This copy of the file was written inside the integrated Ask worktree** (see below) as part of
Phase 2 of the 0.6.0 Ask consolidation (2026-09-29) — this branch's own history predates
`main`'s most recent topology update (`4bce1a77`), so this version adds the Ask-lineage detail
that update didn't yet carry, without altering `main`'s copy (out of this phase's scope; land the
reconciliation the ordinary way when this worktree's work is merged).

## Primary checkout

`C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum` — this repo root — is the **canonical current
`main` checkout**. It is what Cliff runs day-to-day, and what the Tauri desktop-shell build
pipeline packages from. Ordinary product development happens here under normal increment rules
(see the root `.claude/CLAUDE.md`).

Completed product work should not remain stranded only in a long-lived development worktree —
land it on `main` in the ordinary course of a session, the same as any other increment.

## Frozen 0.6 baseline

`.claude/worktrees/060` — durable branch `freeze/060`, pinned exactly to commit
`5ddb321f5a9374d8258234562da4b0781c965d1a` (inc 581, the pre-registered Ask query-planner/H1a
baseline). This is a historical time-capsule for **deferred human adjudication of the 0.6
evidence-hygiene research track**, not an active development branch. Do not advance it.

**0.6 adjudication is pending** (Cliff is finishing a manuscript first, as of 2026-09-17). Until
it's adjudicated: R_0_6 stays unfrozen, and 0.7 semantic work stays blocked on its existing
dependency on an accepted 0.6. This is a research-methodology state, not a topology fact — don't
infer it's resolved just because this file or the primary checkout looks normal again.

## Ask-CLI experiment lineage (0.6/0.7 evidence-hygiene research track)

The Ask-CLI/evidence-hygiene research is **one linear lineage**, not parallel branches — confirmed
via `git merge-base --is-ancestor` during Phase 1 of the 0.6.0 Ask consolidation (2026-09-29):

```
main --> experiment/ask-cli-staged-synthesis --> experiment/ask-e2e
      --> experiment/ask-e2e-overview --> experiment/ask-contract-directed
      --> experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z   <-- ACTIVE INTEGRATION LANE
```

- **`.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z`** (branch of the same
  name) is the **current active lane** for hierarchical q_aib E2E work — the reconciled,
  integration-tested build combining the 11-child frozen hierarchy, the recovery-only
  deterministic +/-3 neighborhood, and the NLI citation-boundary repair, per its own
  `INTEGRATION_MANIFEST.json` (repo root of this worktree). Branched from
  `experiment/ask-contract-directed` at `13540524`. Read that manifest, not this paragraph, for
  exact validation status of each piece.
- **`.claude/worktrees/ask-cli-staged-synthesis`** (branch `experiment/ask-cli-staged-synthesis`)
  — an early ancestor. Its own detailed operational log lives at `.claude/SCRATCH.md`
  **inside that worktree** (not present in the primary checkout). Historical relative to the
  active lane above; not where new Ask work should land.
- **`.claude/worktrees/ask-e2e`** (branch `experiment/ask-e2e`) — the flat two-round E2E
  orchestrator's own development worktree. **Has a dirty (uncommitted) working tree** — an
  independent, non-git snapshot of it was taken 2026-09-29 (see the Phase 2 handback for its
  location) before any Phase-2 work touched anything. Every piece of its own dirty work that was
  still wanted has already been folded into the active lane above (see
  `INTEGRATION_MANIFEST.json`'s `section_4_reconciliation`); this worktree itself remains
  untouched and historical.
- **`.claude/worktrees/ask-e2e-overview`** (branch `experiment/ask-e2e-overview`) — added the S
  (Overview) stage. Historical relative to the active lane above, which descends from it.
- **`.claude/worktrees/ask-contract-directed`** (branch `experiment/ask-contract-directed`) — the
  standalone, richer `contract_directed/` pipeline (child-scoped evidence, deterministic
  neighborhoods, recovery planning) that the active lane's own recovery-only integration (Section
  5) reuses `neighborhood.build_neighborhood()` FROM, without modifying. This worktree's own
  `contract_directed/` pipeline stays independent and untouched; the active lane above is branched
  from its tip but is not itself `contract_directed`.

## Other isolated worktrees

- `.claude/worktrees/browser-capture-research` (branch `browser-capture-research`) — a substantial,
  mostly-complete browser-capture/import-queue feature (issue #61) with real committed work cleanly
  ahead of `main`, plus **uncommitted, in-progress changes** referencing a separate open issue (#98).
  Deliberately left isolated and untouched as of 2026-09-17 pending its own explicit review/merge
  decision — not part of ordinary `main` development until that happens.
- Assorted temp-directory worktrees under `%TEMP%` hold other point-in-time research/audit
  checkpoints (H1c adversarial audits, corpus census, replication studies, etc.). These are
  ephemeral and outside this file's scope; `git worktree list` is authoritative for what currently
  exists.

## Maintaining this file

Update it in place whenever the topology changes (a worktree is added/removed/relocated, or a
branch's role changes) — this is a snapshot of *now*, not a log. For the *why* behind a change,
use `.claude/changes.md`. **This copy and `main`'s copy will need reconciling** the next time this
worktree's work lands on `main` — don't assume they already agree.
