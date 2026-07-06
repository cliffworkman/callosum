# callosum TUI

A terminal client covering the full feature surface of the running callosum app — numbered
menus for humans, one-shot subcommands for agents. Stdlib + httpx only (no curses, no rich),
matching the rest of the repo.

Needs the app running:

```bash
cd ~/callosum && .venv/bin/uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

## Interactive (humans)

```bash
python -m tui
```

Numbered main menu → numbered submenu → prompts. `0` back, `q` quit. Destructive actions
(trash, permanent delete, merge, axis delete…) always confirm with y/N.

## One-shot (agents and scripts)

```bash
python -m tui papers list --q "aesthetic" --format json
python -m tui fulltext search --q "default mode network" --format json
python -m tui wanted list
python -m tui gaps refresh --no-wait          # submit only; poll with: gaps … {job_id}
python -m tui methods statcheck 42
python -m tui papers pdf 42 --out paper.pdf
python -m tui papers delete 42 --yes          # destructive ops require --yes
```

Every menu item is a subcommand (`python -m tui <group> --help` lists them; both are generated
from `tui/registry.py`, the single source of truth). Job endpoints (202 + `{job_id}`) poll to
completion by default; `--no-wait` returns the submit response. Escape hatches for anything the
registry doesn't model as a named flag: `--extra-query k=v` (repeatable) and `--body '<json>'`.

Connection: `--base-url` / `$CALLOSUM_BASE_URL` (default `http://127.0.0.1:8080`),
`--token` / `$CALLOSUM_TOKEN` when remote access is enabled.

## Agent mode

```bash
python -m tui --agent tags add 42 --tag "predictive-processing" --format json
```

`--agent` (or `CALLOSUM_TUI_AGENT=1`) restricts the surface to reads plus the **gated, audited,
revertible `/agent/*` writes** (tag a paper, add a paper to an axis, save a reference by DOI,
add a note). Writes that remap (`tags add`, `tags axis-add-paper`, `papers annotate`,
`papers save-reference`, and DOI-only `discovery save` / `gaps add`) go to `/agent/*`
automatically; every other write — and all destructive actions — is refused with the human
path named. The gate itself lives in callosum (Settings → AI agent); when it's off, agent
writes exit 3 with that hint. Audit trail: `python -m tui status agent-writes`, revert with
`status agent-revert <write_id>`.

## Self-test / tests

```bash
python -m tui --self-test            # offline, no server
python -m pytest tests/test_tui.py   # hermetic (httpx.MockTransport)
```
