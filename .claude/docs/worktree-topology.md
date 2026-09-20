# Worktree topology (current state)

This file records the **current** checkout topology, not history — update it in place when the
topology changes again rather than appending. For the historical narrative of *why* the primary
checkout was ever off `main`, see `.claude/changes.md` (2026-09-17 entry) and the Ask-CLI research
branch's own `.claude/SCRATCH.md` (only present in its dedicated worktree, see below).

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

## Ask-CLI experiment (0.6/0.7 evidence-hygiene research track)

`.claude/worktrees/ask-cli-staged-synthesis` — branch `experiment/ask-cli-staged-synthesis`. This
is where the active Ask-CLI/evidence-hygiene research (H1a/H1b/H1c and successors) lives day to
day, including its own detailed operational log at `.claude/SCRATCH.md` **inside that worktree**
(not present in the primary checkout — it was never part of `main`'s tracked tree). Read that file
for the research track's own state; don't duplicate its content here.

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
use `.claude/changes.md`.
