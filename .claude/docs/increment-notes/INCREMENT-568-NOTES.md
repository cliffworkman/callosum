# Increment 568 Notes — an unpolished axis label must say so

## The report

Cliff: descriptive axis titles had reverted to keyword labels ("Brain Patients", "Training Infection"),
and the regression **persisted across a restart**. Inc 557 had just fixed a labeling bug, so the natural
reading was that the fix had failed or the local model had regressed.

Neither was true.

## Root cause — verified, not inferred

1. `~/.callosum/app-settings.json` → `provider = "managed_local"` (read live).
2. `resolve_llm_config` routes `managed_local` → `resolve_managed_local_provider` → `load_preview_target()`
   (`dependencies.py:39-42`).
3. `_preview_descriptor_path()` requires `CALLOSUM_APP_DATA_DIR`; unset → `ManagedLocalTargetError
   ("app_data_missing")` (`managed_local.py:311-313`).
4. **Only `backend.rs:202` ever sets that variable** — the Tauri shell. No `tools/` script does, so
   `run_dev.py` and a bare `uvicorn` never do (confirmed by repo-wide grep).
5. `axes.py:443-447` caught it → `labeler = None`.
6. `apply_labels` early-returned unchanged → the c-TF-IDF labels.

The report came from the **dev PowerShell instance**, which structurally cannot reach Local AI. The
packaged desktop app was fine the whole time — which is exactly why syntheses kept working there and
confused the picture.

## The model was never the problem — proven, not assumed

Before changing anything, a live probe drove the running desktop app's endpoint (`127.0.0.1:54915`) from a
plain Python process outside Tauri, using the real `_prompt()`:

| Request shape | Result |
|---|---|
| top-level `json_schema` (what the code sends) | bare JSON, correct, 11.3 s |
| no constraint | correct answer wrapped in a ``` fence, 7.2 s |
| OpenAI-style `response_format` | bare JSON, correct, 6.4 s |

All three returned `{"label": "Brain Disorders", "terms": [...]}` and `_parse_label` extracted every one.
So: llama.cpp b10516 **does** honor the top-level `json_schema` (the constrained runs dropped the code
fence), inc 557's grammar works, and the parser works. This probe is what turned a plausible-sounding
"the small model regressed" story into a ruled-out hypothesis.

## The actual defect: silence

Axis-suggest was the **only** path in the backend that turned `ManagedLocalTargetError` into a `done` job.
Every other consumer — summaries, help, overview, critique, workbench, my-publications,
analytic-flexibility — raises a visible 422 "Local AI is not ready". And `apply_labels` swallowed *every*
per-cluster failure (egress-off, missing key, 401/429/5xx, timeouts, and successful-but-unparseable
responses) with **no logging in either file** and **no response field** separating a polished label from a
keyword one. The two were byte-identical on the wire.

That is PRINCIPLES #6 ("silence is not a certificate") and invariant #4. The fallback behaviour itself was
right — keyword labels are a usable result, better than failing the job. Only the silence was wrong.

## Implemented

- **`app/backend/llm/managed_local.py`** — `unavailable_reason(code)`: one honest sentence per failure
  class, always naming the code. One mapping, so every surface says the same thing.
- **`app/backend/api/routers/settings.py`** — `generation_provider_detail` on `SettingsStatus`.
  `generation_provider_available` was *already* correct here; line 130's `except Exception` was throwing the
  reason away. Now populated for managed-local codes and for the cloud cases (no key / egress off / no
  endpoint). Additive — the five existing consumers (`08n`, `08x`, `08y`, `20_synthesis`, `45_workbench`)
  get it for free.
- **`app/backend/clustering/axis_suggestion.py`** — `apply_labels` returns `LabelPolish`
  (polished / fell_back / first reason) instead of a bare list, and logs. Still never raises. `SuggestedAxis`
  gains `label_source`. The subtle case is handled explicitly: a **successful** response with a blank label
  never entered the old `except`, but is still a fallback and is now counted as one.
- **`app/backend/api/routers/axes.py`** — captures `exc.code` instead of discarding it, logs a warning, and
  threads the reason into `label_notice` via `_label_notice`.
- **`app/backend/api/routers/axes_models.py`** — `label_source` per suggestion, `label_notice` per job. Both
  defaulted, so existing clients are unaffected.
- **`integrations/gemini/generator.py` / `axis_cluster_labeler.py`** — closed a residual hole in inc 557's own
  recovery: `first_embedded_json` took the **first** decodable dict, so a schema echo or a bare `{}` emitted
  before the real answer defeated the recovery. It now takes an optional `accept` predicate; the labeler
  passes `_has_label`. Latent here (the current model answers cleanly) but real.
- **`17_axes_suggest.jsx` / `styles.css`** — renders the notice as `.axis-label-notice`, amber `--flag` per
  DESIGN.md (an unresolved *status*, never `--danger`); same recipe as the adjacent `.axis-err`, minus the
  click affordance. The suggestions still render.

## Key technical detail

`CALLOSUM_APP_DATA_DIR` is **process-local and Tauri-set**. That single fact explains why the bug was
invisible to every test (which sets it via `monkeypatch`), invisible in the packaged app (where it is set),
and 100% reproducible in the dev server (where it never is). It is not intermittent and not a race.

## Dev unblock (documented, deliberately not wired)

With the desktop app open, before starting the dev server:

```powershell
$env:CALLOSUM_APP_DATA_DIR = "$env:APPDATA\com.callosum.desktop"
```

The dev backend then reads the same descriptor and drives the same llama-server — this is exactly what the
probe above did. Cliff's call was to document rather than wire it into `run_dev.py`. The broader
requirement — Local AI must be genuinely usable from the dev browser build, because a Tauri rebuild is an
hours-long loop — is filed as **backlog #72** with three candidate designs.

## Manual verification script

1. Dev server **without** `CALLOSUM_APP_DATA_DIR`, provider = Local AI → Axes → **Suggest axes**. Expect
   keyword labels **plus** an amber notice naming `app_data_missing` and pointing at the desktop app.
2. `GET /settings` → `generation_provider_available:false` with a matching `generation_provider_detail`.
3. Set the env var (desktop app open), restart the dev server, re-run → descriptive labels,
   `label_source:"ai"`, `label_notice:null`, no notice rendered.

## Gates

- **#9 Principles:** restores #6 / invariant #4 rather than adding a claim. No new judgment about the
  literature. The misaligned easy path was to keep degrading silently because the fallback "works".
- **#10 QA:** `route_15_axes.md` (A11) and `route_35_settings.md` extended; `build_surface_map.py check` →
  437/437 API covered, 0 uncovered (the 8 FE items are pre-existing, in untouched files).
- **#8 DESIGN:** amber `--flag`, existing recipe reused, no new token.
- **#12 LATENCY:** no change to call shape, batching, or client reuse. Noted for the record: the axis-label
  contract inherits `max_output_tokens = 2048` (`with_managed_output_contract` caps only the *Overview*
  contract at 256) — 6–11 s per cluster × 6 clusters. Out of scope; worth revisiting if suggest feels slow.
- No security audit triggered — no new endpoint, fetch, ingestion path, auth logic, or dependency.

## Pytest

`tests/test_axes.py` + `tests/test_settings.py` + `tests/test_frontend_assembly.py` — **167 passed**.
Eight new tests, each written to fail on the old code:

- the reported bug reproduced at its real cause (notice names `app_data_missing`);
- a positive control (`label_source:"ai"`, `label_notice:null`) so a permanently-broken labeler cannot pass;
- a per-cluster raising labeler; a blank-label response (the non-exception fallback path);
- decoy-object parsing — verified discriminating by running the old and new paths side by side: the old one
  returns `{"type": "object", ...}`, the new one finds the real answer;
- three `/settings` cases (unreachable Local AI, cloud with no key, and the available/no-detail control).
