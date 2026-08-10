# Security + Principles-alignment review — TUI terminal client (external contribution, PR #1, DRAFT)

**Date:** 2026-08-10
**Status:** complete — PASS, with follow-ups before merge (not blocking findings)

## Scope and provenance

`tui/` (`registry.py`, `client.py`, `__main__.py`, `menus.py`, `render.py`, `README.md`) +
`tests/test_tui.py` — a terminal client covering the running callosum app's API surface: a numbered-menu REPL
for humans and a one-shot CLI (`python -m tui <group> <action>`) for scripts/agents, both generated from one
declarative registry so they can't drift from each other.

**This is not merged code.** It is **GitHub PR #1** (`feat/tui` → `main`), **DRAFT**, opened 2026-07-06 by
**Jeffrey Vadala** (`jeffrey.vadala@pennmedicine.upenn.edu`) — **callosum's first real external code
contribution**, not written in a Claude Code session. It sat unreviewed for over a month before this pass.
Reviewed by checking out `origin/feat/tui` into an isolated worktree (`.claude/worktrees/feat-tui-review/`,
not merged into `main`) and reading every file, running the real test suite, and cross-checking the registry's
143 declared endpoints against current `main`'s actual API surface. Requested explicitly by Cliff, with
particular attention to `.claude/PRINCIPLES.md` alignment, given this is the precedent-setting first review of
outside code.

## Principles alignment (rule #9) — the part Cliff specifically asked about

**The TUI is a pure, faithful client — it computes no new judgment of its own.** `render.py` is a dumb
formatter (table/detail/JSON); it never collapses fields into a score, never adds interpretation, never
decides what's "good" or "bad." Every value it prints is a field the backend's own already-principled endpoint
returned. Nothing in `tui/` calls an LLM, calls any external service besides the user's own callosum instance,
or introduces a new candidate/fact distinction. On the specific commitments:

- **#2 signal, not verdict / #7 no opaque scores:** trivially upheld — there is no scoring logic anywhere in
  this code. `render.py`'s table/detail rendering is the only transformation applied, and it's structural
  (column width, truncation), not semantic.
- **#3 facts vs. candidates:** the TUI passes through whatever distinction the API response already encodes
  (e.g. a finding's FACT/CANDIDATE field renders as a plain table cell) — it neither collapses nor relabels it.
- **Core invariant #3 (local-first, egress-off by default):** the TUI makes **zero direct external calls**.
  Its only network target is the user's own callosum instance (`--base-url` / `$CALLOSUM_BASE_URL`, default
  loopback `127.0.0.1:8080`). Any egress that results from a TUI-driven action (e.g. `summaries create`) is
  mediated entirely by the *existing*, already-gated `/summarize` endpoint server-side — the TUI adds no new
  egress path, the same posture the read-only MCP server audit (`2026-06-30_mcp-server.md`) already established
  for this exact client shape.
- **Core invariant #5 (visible work is globally findable):** a job the TUI submits (e.g. `gaps refresh`) hits
  the *same* `JobStore` the web UI's Status popover already polls — there is no separate, TUI-only notion of
  background work. If the web UI happens to be open at the same time, a TUI-triggered job is visible there too.
  No new invisible-work surface is introduced.
- **APPROACH-AVOIDANCE veto boundaries:** no paywall circumvention (acquisition actions call the existing
  `/papers/{id}/acquire-oa` unchanged), no reaching into another tool's protected store, no accusation logic of
  any kind — the TUI has no forensic/integrity computation of its own to misuse.

**One genuine, worth-naming limitation, not a violation.** A terminal cannot render the web UI's visual honesty
affordances — invariant #2's exact/region/null bbox highlighting has no meaning as text, and invariant #1's
verified/contrasted/flagged sentence-level treatment collapses to a plain field in a table row rather than the
web UI's designed visual distinction. This does **not** hide or misrepresent anything — the underlying
`coordinate_precision` / verification-status fields are the same ones sent to the browser, printed verbatim,
never simplified into a friendlier-but-false claim. It is an inherent property of any non-visual client (the
same is implicitly true of the already-blessed read-only MCP server), not something introduced here. Worth a
line in the TUI's own README so a human REPL user knows a `detail` view is not the same honesty surface as the
web UI's PDF overlay — a cheap, non-blocking addition, not a design change.

## Threat review

- **The `--agent` gate is structurally enforced, not just documented.** `registry.validate()` — run in CI via
  `test_registry_is_valid` — asserts (a) no `DESTRUCTIVE` action is ever `agent_allowed()`, and (b) every
  non-read action reachable in agent mode has an effective path under `/agent/*`. This is exactly the same
  "structurally inexpressible" guarantee `agent.py`'s own docstring claims for the backend itself (inc 216) —
  the TUI's registry cannot express a wider agent surface than the backend already permits, by construction,
  proven by `test_the_four_audited_agent_writes_are_reachable_in_agent_mode` and
  `test_no_destructive_action_in_agent_mode`.
- **The real security boundary is server-side, and I independently verified it hasn't drifted.** Cross-checked
  the TUI's client-side field allowlist (`{"tag", "paper_id", "identifier", "text"}` in
  `__main__.py::run_action`) against current `main`'s actual `/agent/*` Pydantic body schemas via the live
  OpenAPI spec: `TagBody→{tag}`, `AxisBody→{paper_id}`, `RefBody→{identifier}`, `NoteBody→{text}` — an exact
  match, even though this branch is ~212 increments behind `main`. Even if the TUI's client-side filter had a
  bug, the server's own strict body models are the actual gate.
- **Endpoint drift, checked precisely, not assumed.** Extracted all 143 unique `(method, path)` pairs the
  registry declares and diffed them against current `main`'s live OpenAPI schema (408 routes). **Zero are
  missing or renamed.** Every endpoint this branch targets still exists, unchanged, on `main` today — the
  6-week-old branch is stale in *coverage* (nothing here knows about z-curve, DEBIT, repeated-values, the WIP
  workspace, diagnostics, etc. — everything shipped since), but nothing it targets is *broken*.
- **Secrets:** `CALLOSUM_TOKEN` / `CALLOSUM_BASE_URL` come from env vars or CLI flags only, matching the
  existing BYOK/remote-access token convention (rule #2) — never hardcoded, never logged.
- **No SQL, no filesystem access beyond `--out FILE`** (writing a response the *user* explicitly asked to save,
  to a path the *user* typed — not derived from any API response field).
- **Escape hatches (`--body JSON`, `--extra-query k=v`) are neutralized in agent mode**, not just discouraged —
  the same field-allowlist strip applies regardless of what a caller tries to smuggle through `--body`, proven
  by `test_agent_body_is_stripped_to_the_gated_fields`. In human (non-agent) mode they're unrestricted by
  design, but a human operator already has full read-write access to their own local instance via the web UI —
  no new privilege is created.
- **Honest failure handling**, mirroring the MCP client's own precedent: unreachable app, 401, and
  agent-writes-disabled (403 containing "agent") each raise a distinct, actionable error naming the fix, never
  a fabricated result (`test_client_down_message_names_the_fix`, `test_client_surfaces_api_detail`).
- **Supply-chain:** stdlib + httpx only — httpx is already a root project dependency (`CLAUDE.md`'s own stack
  list). **No new third-party dependency.**

## Negative-path checks (re-run independently, not trusted from the PR description)

- `python -m pytest tests/test_tui.py -q` in the isolated worktree → **14 passed** (not just cited from the PR
  body — actually re-run).
- `python -m tui --self-test` → **OK** (offline, MockTransport; independently re-run).
- Registry cross-check against live `main` OpenAPI schema → 143/143 declared endpoints exist; `/agent/*` body
  schemas match the client's field allowlist exactly (both checks done programmatically, not by inspection).

## Findings — none blocking; two worth doing before/at merge

1. **(Low, cosmetic)** A generic `CALLOSUM_READ_ONLY`-mode 403 (a mutating call under `CALLOSUM_READ_ONLY=1`)
   isn't specifically named the way the 401/agent-403 cases are in `client.py::_ok()` — it still surfaces
   honestly via the generic `CallosumUnavailable(f"callosum returned {r.status_code}: {detail}")` fallback, just
   with a less specific hint. Not a security gap (the server still correctly refuses the write); a small UX
   polish if picked up.
2. **(Expected, not a defect)** The registry is frozen at roughly inc 258's feature set — a real, honest
   staleness gap (WIP workspace, all four Data-consistency checks, superuser/diagnostics, statements, evidence
   insertion, Zotero conversion, usage analytics, followed-authors, and more are entirely absent). Since
   `registry.py` is a flat declarative tuple with a `validate()` self-check, extending it is additive and
   low-risk — a natural follow-up increment once/if this PR is merged, not a precondition for merging what's
   here now (everything present still works correctly against current `main`).

## Result

No exploitable issue, no Principles violation, and no drift-induced breakage were found. The contribution
mirrors this project's own established security posture for exactly this client shape (the already-audited
read-only MCP server) and extends it correctly to gated writes, with its own structural (`registry.validate()`)
and test-suite proof that the agent surface can never widen beyond `/agent/*`. The one genuine limitation
(no visual honesty affordances in a terminal) is inherent to the client type, not a defect, and doesn't
misrepresent anything — the same fields are shown, just as text.

**Security Audit: PASS.** Still a **DRAFT PR** pending Cliff's own merge decision — this review clears the
Principles/security gate; it does not itself merge or mark the PR ready.
