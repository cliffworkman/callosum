# Increment 472 — TUI terminal client: reviewed and merged (round 3, item #1a)

*(Numbered 472, not 471 — a concurrent, orthogonal session was already using 471 locally, uncommitted, for the
public website/showcase refresh at the time this landed; renumbered to avoid collision.)*

## Implemented

While surveying the backlog for round 3 (memory `callosum-next5-backlog-roadmap-round3`), a real finding
surfaced: two shipped external-client features — the MCP server (backlog "B1", incs 213/216) and a TUI terminal
client (`tui/`) — were entirely absent from `CLAUDE.md`'s feature narrative and `INCREMENT-BACKLOG.md`, and the
TUI turned out not to be merged at all. It was **GitHub PR #1**, **DRAFT**, opened 2026-07-06 by an actual
external contributor — **Jeffrey Vadala** (`jeffrey.vadala@pennmedicine.upenn.edu`) — callosum's first real
outside code contribution, sitting unreviewed for over a month.

Cliff asked for a careful review specifically against `PRINCIPLES.md`, given this is the precedent-setting
first review of outside code, then confirmed merging it once reviewed clean.

### The review

Checked out `origin/feat/tui` into an isolated worktree (never touching `main`) and read every file
(`registry.py`, `client.py`, `__main__.py`, `menus.py`, `render.py`, tests, README). Full writeup:
`.claude/security-audits/2026-08-10_tui-external-contribution-review.md`. Highlights:

- **Principles-aligned by construction.** The TUI computes no judgment of its own — `render.py` is a dumb
  table/detail/JSON formatter over whatever fields the backend's own already-principled endpoints return. No
  scoring, no new fact/candidate distinction, zero direct external calls (only the user's own callosum
  instance). Jobs it submits land in the same `JobStore` the web UI's Status popover already polls.
- **The `--agent` gate is structurally enforced, not just documented** — `registry.validate()` (run in CI)
  proves no destructive action is ever agent-reachable and every agent-mode write routes through `/agent/*`,
  mirroring `agent.py`'s own "structurally inexpressible" guarantee.
- **Verified, not trusted, against current reality.** Independently re-ran the test suite (14/14 pass) rather
  than citing the PR description, and — since the branch was ~212 increments behind `main` — extracted all 143
  unique `(method, path)` pairs the registry declares and diffed them against current `main`'s live OpenAPI
  schema. **Zero were missing or renamed.** Also cross-checked the TUI's client-side `/agent/*` field allowlist
  (`{tag, paper_id, identifier, text}`) against the actual current Pydantic body schemas — an exact match.
- **One honest, non-blocking limitation named, not hidden:** a terminal can't render the web UI's visual
  honesty affordances (bbox highlighting, the verified/contrasted/flagged treatment) — but nothing is
  misrepresented, since the same underlying fields print as plain text. Inherent to any non-visual client
  (implicitly true of the already-blessed read-only MCP server too), not a defect.

### The merge

Two small, real lint/format issues surfaced when checked against this project's own `ruff` config (an unused
import, a missing `from exc` exception chain, and 6 files needing reformatting) — expected for code written
without this project's tooling, fixed in a separate follow-up commit (preserving Jeffrey's original commit
exactly as authored, rather than rewriting it). Rebased cleanly onto current `main` (purely additive — 8 new
files, zero existing files touched, so no conflicts were possible), pushed, confirmed CI green (lint-and-test +
e2e-smoke + all four CodeQL language scans), marked the draft ready for review, and merged via `gh pr merge
--rebase --admin` (the repo's branch-protection ruleset required a review approval that hadn't been submitted;
admin privileges were used under Cliff's own explicit "merge it now" authorization, not to bypass any
substantive check — every CI/quality gate had already passed).

## Key technical detail

The endpoint-drift check is the most load-bearing part of this review: a branch 212 increments stale could
plausibly target endpoints that no longer exist or have changed shape, silently breaking on first real use.
Verifying this **programmatically** (via the live `FastAPI.openapi()` schema, not by reading code) rather than
assuming "the tests pass so it must be fine" is what actually proves the merge is safe today, not just safe
as of when it was written — the hermetic `MockTransport` tests only prove internal logic is self-consistent,
they can't catch drift against the real, current API shape.

## Manual verification script

1. `python -m tui --self-test` → `OK`.
2. `python -m tui` (no server running) → honest `CallosumUnavailable` naming the uvicorn start command.
3. With the app running: `python -m tui papers list --format json` → real library data.
4. `python -m tui --agent papers delete 1` → refused, names the human path (`--agent` can't reach destructive
   tiers).
5. `python -m tui --agent tags add 1 --tag test` (with agent writes enabled in Settings) → tagged via
   `/agent/papers/{id}/tags`, audited, revertible via `python -m tui status agent-revert <id>`.

## Verification

- `pytest tests/test_tui.py -q` → **14 passed** (re-run on the real, merged `main`, not just the review
  worktree).
- `python -m ruff check` / `ruff format --check` on the touched files → clean (after the follow-up fix commit).
- `python tools/check_line_budget.py` → clean (`tui/` is outside `app/`/`integrations/`, exempt like
  `mcp_server/`/`tools/`, but every file is comfortably under 600 lines regardless).
- CI on the PR itself: `lint-and-test`, `e2e-smoke`, and all four CodeQL language scans (actions/js-ts/python/
  rust) — all green before merge.
- Full pytest collection on `main` post-merge: **2098 tests** (2084 + 14 new).

## Housekeeping

- `.claude/CLAUDE.md`: new Stack bullet documenting both the MCP server (backlog-only until now) and the TUI,
  with their real increment numbers (213/216/472); counter bumped to 472; pytest count updated to 2098.
- `.claude/security-audits/2026-08-10_tui-external-contribution-review.md` (new).
- `.claude/staged-harnesses/REGISTRY.md`'s `tach.md` entry names its own activation trigger — *"an outside
  contributor begins pushing code"* — as now fired by this exact PR; activated immediately after in inc 473.
- Memory `callosum-next5-backlog-roadmap-round3`: item 1 (MCP/TUI reconciliation) continues in inc 473
  (the `tach` harness activation).
