# Staged harness: bandit (Python security static analysis)

**Checks:** common Python security anti-patterns (`subprocess` with `shell=True`, weak hashes, hardcoded
secrets, unsafe deserialization, etc.) via static analysis across `app/` + `integrations/`.

**Why deferred:** callosum's actual threat model today is a **local, single-user, 127.0.0.1-bound** app —
resource exhaustion and untrusted-content handling (rule #4), not the network-facing attack classes bandit is
built for. The project's existing discipline (parameterized SQL only, egress gate, PDF/API boundary
validation, the per-feature `.claude/security-audits/` gate) already covers the threat model that actually
applies today; bandit's marginal catch rate here is low relative to noise until the app faces a broader
attack surface.

**Activation trigger:** **before any public/hosted deployment**, or **when adding a new network-facing or
file-write surface** (the same triggers CLAUDE.md's own audit gate already names for those changes) — at
that point the threat model widens enough that a static security scanner's continuous signal starts pulling
its weight alongside the per-feature manual audits.

## Draft config (moves to a `[tool.bandit]` section in `pyproject.toml` on activation)

```toml
[tool.bandit]
exclude_dirs = ["tests", "tools", ".venv"]
# B101 (assert used) is noisy in a codebase that leans on asserts for internal invariants, not user input
# validation; revisit if bandit becomes the primary gate rather than a supplement to the manual audit process.
skips = ["B101"]
```

```yaml
# Draft CI step (add to ci.yml's lint-and-test job on activation)
- name: Bandit (Python security static analysis)
  run: uv run bandit -c pyproject.toml -r app integrations
```

## Activation steps
1. Add `bandit` to the `dev` dependency group.
2. Move the `[tool.bandit]` draft into `pyproject.toml`; run once and triage findings (fix or `# nosec` with a
   reason, matching the project's "no silent skip" discipline).
3. Add the CI step above; consider a pre-commit hook too if it stays fast enough.
4. Update this registry's status to `active` and remove this file (or mark it superseded).
