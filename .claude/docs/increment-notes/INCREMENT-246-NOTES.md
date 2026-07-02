# Increment 246 — PUBLISHERS "where to submit" SP1b (the METHODS panel + weighting + first-use choice gate)

## Implemented

The frontend half of backlog #40 (SP1a = the backend engine + endpoint, inc 245). A METHODS **"Where to submit"**
panel that runs the SP1a endpoint and shows a uniform per-journal profile, under an open-science **weighting** the
user sets behind a **first-use choice gate**. Maintainer scope (from SP1a): full principled core · both inputs.

**No change to the SP1a endpoint** — the panel reads the two prefs from `GET /settings`, maps breadth → `top_k`
client-side, and passes `weighting` + `top_k` to the existing `/methods/publishers/run`.

Files:
- `app/backend/app_settings.py` (MODIFIED) — local, non-secret publisher prefs (file-stored, **never transmitted
  externally**): `set/stored_publisher_weighting` (float|None), `set/stored_publisher_breadth` (str|None), and
  `publisher_defaults_set()` = both non-None (the gate). Both start None (no pre-selection).
- `app/backend/api/routers/settings.py` (MODIFIED) — additive `publisher_weighting`/`publisher_breadth`/
  `publisher_defaults_set` on `SettingsStatus`; `set_publisher_weighting`/`publisher_weighting` (0..1 → 422 else) +
  `set_publisher_breadth`/`publisher_breadth` (`{focused, broad}` allowlist → 422 else) on `SettingsUpdate`;
  `PUBLISHER_BREADTHS` constant.
- `app/frontend/js/08e_methods_publishers.jsx` (NEW) — `registerPaneSection` (order 34, `hideInReadOnly`):
  - `PublishersGate` — the first-use step: two segmented controls (`PubSegmented`, reusing `.tags-srcfilter`) with
    **no option pre-selected**; **Save disabled until BOTH are chosen** (the weighting is never the lone forced
    choice); a local-only privacy note; Save persists both via `PUT /settings` then re-fetches.
  - `PublishersPanel` — reads `GET /settings`; if `!publisher_defaults_set` renders the gate, else the input
    (Selected paper / Paste abstract) + Find journals → the SP1a run/poll (the 08b pattern) → results.
  - `PubProfileCard` — fit / OA color / cost (APC + waiver) / license / open impact (+ Matthew caveat) / legitimacy
    chips / `elevated_for`; each links to its source (homepage, OpenAlex, DOAJ). No `*score*` shown.
  - The **output weighting thumb** (output legibility, non-negotiable): always shows the weighting's state inline +
    a segmented control that adjusts + re-runs.
- `app/frontend/js/35_settings.jsx` (MODIFIED) — a **Where to submit** section exposing the two prefs (editable
  anytime), reusing `PubSegmented`/`PUB_WEIGHTS`/`PUB_BREADTHS` hoisted from 08e.
- `app/frontend/styles.css` (MODIFIED) — `.pub-*` recipes (tokens only): OA-color badges are **neutral chips**
  (green = verified is a different semantic), `elevated_for` uses `--accent-soft`, `legitimacy_absent` is muted
  `--ink-3` (absence is neutral fact, never the amber flag). Segmented controls reuse `.tags-srcfilter`.

## Key technical detail

**The first-use choice gate, structural (the future-track doc's veto lines):** the panel yields **no output** until
the user actively sets **both** the weighting **and** the result breadth — nothing pre-selected (`publisher_defaults_set`
is false until both are non-None), so the open-science weighting is **one forced choice among peers**, never the lone
spotlighted field (the de-singularization). The gate fires **once**; thereafter the panel runs inline and the prefs
stay editable in Settings → Where to submit and via the output thumb. The prefs are **local + never transmitted** —
they reach only the local `/methods/publishers/run` endpoint as ordering params; SP1a's recording-transport test
already proves the weighting is in no outbound OpenAlex/DOAJ request.

## Manual verification script

1. `HF_HUB_OFFLINE=1 PYTHONPATH=. python .local/visual/drive_inc246_publishers.py` → "OK - gate (no pre-selection)
   -> save -> run -> thumb + 2 cards (incl. closed); 0 external, 0 console/page errors".
2. `python tools/qa/build_surface_map.py check` → API 176/176, FE 790/790, 0 uncovered.
3. Live spot-check (the maintainer's, needs network): open METHODS → Where to submit → paste an abstract + a real
   subject → Find journals → confirm the profiles resolve against live OpenAlex `/sources` + DOAJ.

## Pytest

922 → **924 passed, 1 skipped** (+2 `tests/test_settings.py`: the gate round-trip [both required] + validation
[weighting 0..1, breadth allowlist, rejected PUT writes nothing]). The panel is frontend-only (headed-verified).
`ruff check` + `ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5).

## Gates

- **Security audit** — addendum to `.claude/security-audits/2026-07-01_publishers.md` — **PASS** (prefs are local +
  never transmitted externally [the weighting never reaches a fetch]; validated at the boundary; no new external
  fetch / endpoint / migration / dependency; the choice gate withholds output, not access).
- **Principles + A-A (rule #9)** — the future-track choice-gate doc is the gate output; the vetoes (no pre-selection,
  weighting-not-alone, never-transmitted, PUBLISHERS-scoped, output legibility) are honored structurally.
- **QA (rule #10)** — `route_60_publishers.md` gained the `fe:` panel claim + the gate/legibility/output-thumb
  assertions; surface 176/176 API + 790/790 FE, 0 uncovered.

## This completes backlog #40 SP1 (SP1a engine inc 245 + SP1b panel inc 246).

Deferred within #40 (no data source yet): green-route / TOP-factor / regional-index legitimacy signals; user
exclusion/filtering; thumb auditability; a real field self-citation baseline.
