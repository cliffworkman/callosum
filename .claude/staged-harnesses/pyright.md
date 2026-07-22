# Staged harness: Pyright (strict type checking)

**Checks:** static type errors across `app/` + `integrations/`, in *warn → baseline → ratchet* mode (report
everything first, freeze the current error count as a baseline, then only fail CI on *new* errors — never a
big-bang "fix 2,000 errors" cliff).

**Why deferred:** the codebase has no type-clean baseline today and is only loosely annotated. Turning Pyright
on as a hard gate now would either block every PR on pre-existing untyped code or require a large, disruptive
annotation pass that isn't the point of this ratchet (subtraction is the default tie-breaker — CLAUDE.md #20).

**Activation trigger:** a type-clean baseline exists across the core app (someone runs Pyright in `basic` mode,
fixes or `# type: ignore`s what's flagged, and commits that as the frozen baseline) — or, more concretely,
**before the first outside contributor's first typed module**, so a new contributor's code is held to a
standard the existing code doesn't yet meet consistently.

**Not mypy.** The project uses Pyright per the harness-hardening plan's nomenclature correction — do not
reach for the deprecated SQLAlchemy mypy plugin if this activates; Pyright understands SQLAlchemy 2.0's typed
ORM constructs natively.

## Draft config (moves to `pyrightconfig.json` at the repo root on activation)

```json
{
  "include": ["app", "integrations"],
  "exclude": ["**/__pycache__", "app/frontend"],
  "typeCheckingMode": "basic",
  "pythonVersion": "3.11",
  "reportMissingImports": true,
  "reportMissingTypeStubs": false,
  "useLibraryCodeForTypes": true
}
```

## Activation steps
1. `pip install pyright` (or add to the `dev` dependency group in `pyproject.toml`).
2. Move this draft to `pyrightconfig.json` at the repo root; run `pyright` and record the current error count
   as the accepted baseline (e.g., a `# pyright: baseline` note here, or a baseline file if Pyright's own
   baseline feature is used).
3. Add a pre-commit hook (`local`, `language: system`, `entry: pyright`) and a CI step; gate on *new* errors
   only until the baseline is worked down, then tighten `typeCheckingMode` to `"strict"`.
4. Update this registry's status to `active` and remove this file (or mark it superseded).
