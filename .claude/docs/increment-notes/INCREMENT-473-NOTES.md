# Increment 473 — activate the tach module-boundary harness (round 3, item #1b)

## Implemented

The second half of round 3's item #1 (memory `callosum-next5-backlog-roadmap-round3`), following inc 472's
TUI review/merge. `.claude/staged-harnesses/tach.md`'s own drafted activation trigger — *"an outside
contributor begins pushing code"* — named the actual scenario months in advance ("Jeff") and had now genuinely
fired via Jeffrey Vadala's merged `tui/` PR #1.

- **Dependency:** `tach>=0.35` added to `pyproject.toml`'s dev group + `requirements-dev.txt` (kept in sync by
  hand, per this project's own convention); `uv.lock` regenerated.
- **Config:** `tach.toml` at the repo root, fencing exactly what the draft named plus the two new client
  surfaces: `app.backend.persistence` can never import `app.backend.api` (the read-first architecture — the
  repository layer doesn't reach up into routers); `sync_server`, `mcp_server`, and `tui` can never import
  `app.backend` at all (each is a pure HTTP client over the running app — proven, not assumed, by `tach sync`
  finding zero real internal imports for any of the three against the actual current codebase).
- **Wired in:** a `tach` hook in `.pre-commit-config.yaml` (mirrors the existing bandit/ruff/line-budget
  hooks); a `Tach module-boundary check` step in `.github/workflows/ci.yml`'s `lint-and-test` job, right after
  the line-budget step (the closest existing architectural-discipline check).

## Key technical detail

**`depends_on` lists are auto-populated by `tach sync` from real usage, not hand-written** — the draft's own
guessed values (`app.backend.api` depending on a specific enumerated list of sibling packages) turned out to
be exactly the kind of thing that goes stale; `sync` derives the truth from the actual current import graph
every time, and a human only needs to review the diff after running it.

**A real, non-obvious debugging finding, worth recording for the next person who touches this config**: tach
only enforces a boundary between **two modules that are both explicitly declared**. A module declared with
`depends_on = []` does *not* implicitly forbid importing from arbitrary undeclared ("root") code — it only
restricts imports into *other declared modules*. This was proven the hard way: an initial config declaring
only `app.backend.persistence` (empty `depends_on`) silently passed `tach check` even with a deliberately
injected `from app.backend.api.routers.agent import router` violation, because `app.backend.api` wasn't itself
a declared module. `tach report <path>` (which shows real detected import edges regardless of enforcement)
was the tool that separated "tach isn't seeing this" from "tach sees it but isn't enforcing it" — the latter
turned out to be the real cause. The fix was declaring both sides of every fence explicitly: `app.backend`
(the catch-all for everything not covered by a more specific entry), `app.backend.api`, and
`app.backend.persistence` all as their own modules, letting `tach sync` fill in the real cross-references.

**Every fence in the shipped config was verified with a real, temporary negative-test violation** (an actual
bad import added to a real file, confirmed to fail `tach check`, then reverted) — not just a clean pass on the
unmodified codebase, which — per the finding above — would not have been sufficient proof on its own.

## Manual verification script

1. `python -m tach check` → `[OK] All modules validated!` on a clean tree.
2. Temporarily add `from app.backend.api.routers.agent import router` (and use the name) to any file in
   `app/backend/persistence/` → `tach check` fails, naming the exact file/line and the forbidden module pair.
   Revert.
3. Temporarily add a real `app.backend.*` import (and use the name) to `tui/registry.py` or `mcp_server/*.py`
   → same failure shape. Revert.
4. `uv run pre-commit run tach --all-files` → passes on a clean tree.

## Verification

- `python -m tach check` / `uv run python -m tach check` (matching CI's exact invocation) → clean.
- `uv sync --locked` → clean (confirms `uv.lock` genuinely matches `pyproject.toml`, not just locally installed).
- `uv run pre-commit run tach --all-files` → passes.
- `pytest tests/test_tui.py -q` → still 14 passed (tach's own pytest-plugin auto-registers once installed and
  reports change-impact info; purely informational, doesn't affect outcomes or exit codes).
- `python -m ruff check` / `ruff format --check` / `python tools/check_line_budget.py` on every file I touched
  → clean. (A `pre-commit run --all-files` dry run surfaced unrelated whitespace/EOF-fixer side effects on
  ~14 pre-existing files elsewhere in the tree, and a ruff finding in a Codex-authored scratch file
  [`.claude/showcase_header_check.py`, from a concurrent orthogonal session] — none of that is part of this
  increment; explicitly reverted the incidental files before committing, leaving Codex's own in-progress work
  (`www/showcase.html`, uncommitted at the time) completely untouched.)

## Housekeeping

- `.claude/staged-harnesses/REGISTRY.md`: `tach.md` marked **active**; also flagged (not activated) that
  `pyright.md`'s own trigger clause ("the first outside contributor's first typed module") fired by this same
  event — a separate, larger decision left for Cliff.
- `.claude/staged-harnesses/tach.md`: marked superseded, pointing at the live `tach.toml`; original design
  rationale kept for history.
- Memory `callosum-next5-backlog-roadmap-round3`: item 1 (MCP/TUI docs + TUI review/merge + tach activation) now
  fully complete. Item 2 (#24 Bayesian ANOVA/regression BF recheck) is next.
