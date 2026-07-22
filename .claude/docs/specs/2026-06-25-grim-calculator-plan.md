# GRIM + GRIMMER calculator (inc 127) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An assisted GRIM/GRIMMER data-consistency calculator — the user enters a reported mean (+ SD), N, and
items; the tool reports whether they are mathematically possible for integer data.

**Architecture:** A pure backend module (`methods/grim.py`, stdlib only) + a sync stateless `POST /methods/grim`
endpoint + a self-registering METHODS-pane section (`07_methods_grim.jsx`) with a small form. No DB, no migration,
no egress, no LLM, **no `40_app.jsx` wiring** (self-registered section).

**Tech Stack:** Python (stdlib `decimal`/`math`), FastAPI, React JSX (esbuild), pytest.

## Global Constraints
- Per `2026-06-25-grim-calculator-design.md`. **Assisted per-value calculator** (no auto-extraction) → inherently
  non-accusatory. GRIM supports `items`; **GRIMMER v1 is items=1 only** (multi-item GRIMMER deferred).
- Local/no-egress/no-LLM/no-DB/no-migration. New endpoint → audit gate; new surface → QA route (rule #10).
- **Principles (#9) aligned:** signal-not-verdict; nearest-possible values + granularity = inspectable; integer-
  scale + no-power caveats; no score; the A-A no-accusation veto held (never scans/ranks/labels). Declined: an
  auto-scanner that flags means with guessed Ns.
- **Credit-the-lineage:** GRIM = Brown & Heathers (2017), *SPPS* 8(4):363–369 (DOI 10.1177/1948550616673876);
  GRIMMER = Anaya (2016, PeerJ Preprints) / Allard (2018, analytic). In-context + one-click add-to-library +
  THIRD-PARTY-NOTICES.
- Read `.claude/DESIGN.md` before CSS (tokens only). Rebuild `callosum-app.html` after frontend edits. This is
  **increment 127**. Commit per task; push at session end on the user's OK.

---

### Task 1: `methods/grim.py` (GRIM + GRIMMER) + tests

**Files:** Create `app/backend/methods/grim.py`, `tests/test_grim.py`.

**Interfaces — Produces:** `grim_test(mean: str, n: int, items: int = 1) -> GrimResult`;
`grimmer_test(mean: str, sd: str, n: int, items: int = 1) -> GrimmerResult`; the two frozen dataclasses.

- [ ] **Step 1: Write the failing tests** (`tests/test_grim.py`):

```python
from __future__ import annotations

import pytest

from app.backend.methods.grim import GrimResult, GrimmerResult, grim_test, grimmer_test


def test_grim_impossible_mean():
    r = grim_test("3.48", 20)  # dividing an integer by 20 to 2dp can only end in .x0/.x5
    assert isinstance(r, GrimResult) and r.consistent is False
    assert r.nearest == ["3.45", "3.50"]


def test_grim_consistent_mean():
    assert grim_test("3.45", 20).consistent is True
    assert grim_test("5.18", 28).consistent is True  # 145/28 = 5.17857 -> 5.18


def test_grim_inconsistent_5_19_n28():
    assert grim_test("5.19", 28).consistent is False  # neither 145/28 nor 146/28 rounds to 5.19


def test_grim_decimals_matter():
    assert grim_test("3.5", 20).consistent is True  # 1 decimal: 70/20 = 3.5


def test_grim_items_multi():
    # items=2 -> denominator 2N; more means become achievable.
    assert grim_test("3.48", 20, items=2).consistent is True  # 139/40 = 3.475 -> 3.48


def test_grim_no_power_large_n():
    r = grim_test("3.48", 500)  # denom 500 >= 10^2 -> every 2dp mean achievable
    assert r.no_power is True and r.consistent is True


def test_grim_bad_inputs():
    with pytest.raises(ValueError):
        grim_test("3.45", 0)


def test_grimmer_consistent():
    assert grimmer_test("5.23", "2.55", 31).consistent is True  # scrutiny reference


def test_grimmer_inconsistent_parity():
    # scrutiny reference: same mean/SD, N=35 -> the only integer SS in the interval has the wrong parity.
    assert grimmer_test("5.23", "2.55", 35).consistent is False


def test_grimmer_requires_grim_consistent_mean():
    r = grimmer_test("5.19", "2.55", 28)  # mean already GRIM-fails
    assert r.consistent is False


def test_grimmer_multi_item_unsupported_v1():
    r = grimmer_test("2.74", "0.96", 63, items=2)
    assert r.supported is False  # GRIM still works for items>1; GRIMMER multi-item is deferred
```

- [ ] **Step 2: Run it to verify it fails** — `python -m pytest tests/test_grim.py -q` → ImportError.

- [ ] **Step 3: Implement `app/backend/methods/grim.py`:**

```python
"""GRIM + GRIMMER — granularity-consistency checks for reported integer-data summary statistics (inc 127).

GRIM (Brown & Heathers, 2017): a mean of N integer observations (each the average of `items` integer items) must
equal K/(N*items) for an integer K; rounded to the reported decimals, only some means are achievable. GRIMMER
(Anaya 2016; Allard 2018 analytic): additionally the reported SD must correspond to an integer sum of squares
consistent with that mean and N, with the parity refinement Sum(x^2) == Sum(x) (mod 2) for integer x.

Assisted, per-value, deterministic, local, no-LLM: the user enters one reported value to check (we do NOT scan the
paper or guess N) — inherently non-accusatory; a signal to look, never a verdict. GRIMMER here covers the
single-item case (items=1); GRIM supports multi-item scales.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MAX_N = 1_000_000  # bound the inputs (rule #4)
MAX_ITEMS = 1_000


@dataclass(frozen=True)
class GrimResult:
    consistent: bool
    reported_mean: str
    n: int
    items: int
    decimals: int
    granularity: float
    nearest: list[str]  # the achievable means bracketing the reported one (to `decimals`)
    no_power: bool  # N*items too large for GRIM to be informative at this precision
    note: str


@dataclass(frozen=True)
class GrimmerResult:
    consistent: bool
    reported_sd: str
    decimals: int
    supported: bool  # False when items != 1 (multi-item GRIMMER deferred)
    note: str


def _decimals(s: str) -> int:
    s = s.strip()
    return len(s.split(".", 1)[1]) if "." in s else 0


def _round_str(value: float, d: int) -> str:
    # everyday round-half-up to d decimals, as a string (avoids float-equality + banker's-rounding pitfalls).
    return str(Decimal(repr(value)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _check(n: int, items: int) -> None:
    if n <= 0 or items <= 0 or n > MAX_N or items > MAX_ITEMS:
        raise ValueError("n and items must be positive and within sane bounds")


def _consistent_totals(m: float, denom: int, d: int) -> list[int]:
    exact = m * denom
    cands = {math.floor(exact), math.ceil(exact), round(exact)}
    target = _round_str(m, d)
    return sorted(k for k in cands if k >= 0 and _round_str(k / denom, d) == target)


def grim_test(mean: str, n: int, items: int = 1) -> GrimResult:
    _check(n, items)
    d = _decimals(mean)
    m = float(mean)
    denom = n * items
    no_power = denom >= 10**d
    consistent = bool(_consistent_totals(m, denom, d))
    lo = math.floor(m * denom)
    hi = lo + 1
    nearest = sorted({_round_str(lo / denom, d), _round_str(hi / denom, d)})
    if consistent:
        note = "Consistent — this mean is achievable for integer data with this N." + (
            " (But N is large for this precision, so GRIM has little power here.)" if no_power else ""
        )
    else:
        note = "GRIM-inconsistent — no integer dataset of this N gives this mean at this precision. Usually a "
        note += "typo or a misreported N; assumes integer-scale data — a prompt to look, not a verdict."
    return GrimResult(consistent, mean, n, items, d, 1.0 / denom, nearest, no_power, note)


def grimmer_test(mean: str, sd: str, n: int, items: int = 1) -> GrimmerResult:
    _check(n, items)
    d_sd = _decimals(sd)
    if items != 1:
        return GrimmerResult(False, sd, d_sd, supported=False,
                             note="Multi-item GRIMMER isn't supported yet — GRIM still checks the mean above.")
    d_m = _decimals(mean)
    m, s = float(mean), float(sd)
    totals = _consistent_totals(m, n, d_m)
    if not totals:
        return GrimmerResult(False, sd, d_sd, supported=True,
                             note="The mean is GRIM-inconsistent, so the SD cannot be consistent either.")
    half = 0.5 * 10 ** (-d_sd)
    s_lo, s_hi = max(0.0, s - half), s + half
    consistent = False
    for total in totals:
        ss_lo = s_lo * s_lo * (n - 1) + (total * total) / n
        ss_hi = s_hi * s_hi * (n - 1) + (total * total) / n
        lo_i, hi_i = math.ceil(ss_lo - 1e-9), math.floor(ss_hi + 1e-9)
        # an integer sum-of-squares in the SD interval with the right parity (Sum(x^2) == Sum(x) (mod 2))
        if any((ss % 2) == (total % 2) for ss in range(lo_i, hi_i + 1)):
            consistent = True
            break
    note = ("Consistent — an integer sum of squares matches this mean, SD, and N."
            if consistent else
            "GRIMMER-inconsistent — no integer dataset of this N gives this mean AND SD. A prompt to look, not a "
            "verdict; assumes integer-scale, single-item data.")
    return GrimmerResult(consistent, sd, d_sd, supported=True, note=note)
```

- [ ] **Step 4: Run** — `python -m pytest tests/test_grim.py -q` → PASS (all 11). If a GRIMMER reference case
  fails, debug the SS bounds/parity against Allard (2018); if single-item GRIMMER still can't match the scrutiny
  values, STOP and report — ship GRIM-only and file GRIMMER to `INCREMENT-BACKLOG.md` rather than ship a GRIMMER
  that disagrees with the reference.

- [ ] **Step 5: Commit** — `git add app/backend/methods/grim.py tests/test_grim.py && git commit -m "feat(methods): GRIM + GRIMMER consistency math (inc 127 t1)"`.

---

### Task 2: `POST /methods/grim` endpoint

**Files:** Modify `app/backend/api/routers/methods.py` (~243 → ~290), `tests/test_grim.py` (endpoint test),
`tests/test_health.py` (route-surface).

**Interfaces — Consumes:** `grim_test`/`grimmer_test` (Task 1). **Produces:** `POST /methods/grim`
`{mean, sd?, n, items=1}` → `{grim: {...}, grimmer: {...} | null}`.

- [ ] **Step 1: Write the failing endpoint test** (append to `tests/test_grim.py`):

```python
from fastapi.testclient import TestClient

from app.backend.api import create_app


def test_grim_endpoint(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/methods/grim", json={"mean": "3.48", "n": 20})
    assert r.status_code == 200
    body = r.json()
    assert body["grim"]["consistent"] is False and body["grimmer"] is None
    r2 = client.post("/methods/grim", json={"mean": "5.23", "sd": "2.55", "n": 31})
    assert r2.json()["grimmer"]["consistent"] is True
    assert client.post("/methods/grim", json={"mean": "3.45", "n": 0}).status_code == 422
```

- [ ] **Step 2: Run** → 404 (route missing).

- [ ] **Step 3: Implement** in `app/backend/api/routers/methods.py` — add `from app.backend.methods.grim import
  grim_test, grimmer_test` and:

```python
class GrimRequest(BaseModel):
    mean: str
    sd: str | None = None
    n: int
    items: int = 1


class GrimResultModel(BaseModel):
    consistent: bool
    reported_mean: str
    n: int
    items: int
    decimals: int
    granularity: float
    nearest: list[str]
    no_power: bool
    note: str


class GrimmerResultModel(BaseModel):
    consistent: bool
    reported_sd: str
    decimals: int
    supported: bool
    note: str


class GrimComputeResponse(BaseModel):
    grim: GrimResultModel
    grimmer: GrimmerResultModel | None = None


@router.post("/methods/grim", response_model=GrimComputeResponse)
def grim_compute(payload: GrimRequest) -> GrimComputeResponse:
    try:
        grim = grim_test(payload.mean, payload.n, payload.items)
        grimmer = grimmer_test(payload.mean, payload.sd, payload.n, payload.items) if payload.sd else None
    except (ValueError, ArithmeticError):
        raise HTTPException(status_code=422, detail="Invalid GRIM inputs: mean/SD must be numbers; n and items must be positive.") from None
    return GrimComputeResponse(
        grim=GrimResultModel(**vars(grim)),
        grimmer=GrimmerResultModel(**vars(grimmer)) if grimmer else None,
    )
```

  (`vars(dataclass_instance)` works for these frozen dataclasses.)

- [ ] **Step 4: Route-surface** — in `tests/test_health.py`, add `("/methods/grim", frozenset({"POST"}))` to
  `allowed_mutation_routes`.

- [ ] **Step 5: Run** — `python -m pytest tests/test_grim.py tests/test_health.py -q` → PASS; confirm
  `wc -l app/backend/api/routers/methods.py` < 600.

- [ ] **Step 6: Commit** — `git add app/backend/api/routers/methods.py tests/test_grim.py tests/test_health.py && git commit -m "feat(methods): POST /methods/grim endpoint (inc 127 t2)"`.

---

### Task 3: frontend METHODS section `07_methods_grim.jsx`

**Files:** Create `app/frontend/js/07_methods_grim.jsx`; modify `app/frontend/styles.css`; rebuild
`callosum-app.html`.

**Interfaces — Consumes:** `POST /methods/grim`; the inc-121 `registerPaneSection`; globals `useState`,
`apiPost`, `ProgressBar`.

- [ ] **Step 1: Read `.claude/DESIGN.md`** (rule #8) — reuse `.detail-*` / `.settings-*` recipes + the
  `.cite-status verified|flagged` pills + tokens; no raw hex.

- [ ] **Step 2: Create `07_methods_grim.jsx`** — register a METHODS section + the form/result + credit:

```jsx
// inc 127: GRIM + GRIMMER — an assisted, per-value data-consistency calculator (Brown & Heathers 2017; Anaya
// 2016 / Allard 2018). The user enters a reported mean (+ SD), N, and items; it reports whether they're possible
// for integer data. User-driven → inherently non-accusatory: a prompt to look, never a verdict. No paper scan.

const GRIM_CSL = {
  type: "article-journal", title: "The GRIM test: A simple technique detects numerous anomalies in the reporting of results in psychology",
  author: [{ family: "Brown", given: "Nicholas J. L." }, { family: "Heathers", given: "James A. J." }],
  "container-title": "Social Psychological and Personality Science", volume: "8", issue: "4", page: "363-369",
  issued: { "date-parts": [[2017]] }, DOI: "10.1177/1948550616673876",
};

function GrimSection() {
  const [f, setF] = useState({ mean: "", sd: "", n: "", items: "1" });
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const [added, setAdded] = useState("idle");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const run = async () => {
    const n = parseInt(f.n, 10), items = parseInt(f.items || "1", 10);
    if (!f.mean.trim() || !Number.isFinite(n)) return;
    setState({ status: "running" });
    const body = { mean: f.mean.trim(), n, items: Number.isFinite(items) ? items : 1 };
    if (f.sd.trim()) body.sd = f.sd.trim();
    const r = await apiPost("/methods/grim", body);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify([GRIM_CSL]), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };
  const d = state.data;
  return (
    <div className="grim-section">
      <div className="settings-sub">Check whether a reported mean (and SD) of <b>integer-scale</b> data — counts or Likert-type items — is mathematically possible for the sample size. Enter a value you're reading; local, no AI.</div>
      <div className="grim-form">
        <label>Mean <input className="grim-in" value={f.mean} onChange={set("mean")} placeholder="3.45" spellCheck={false} /></label>
        <label>SD <input className="grim-in" value={f.sd} onChange={set("sd")} placeholder="(optional)" spellCheck={false} /></label>
        <label>N <input className="grim-in" value={f.n} onChange={set("n")} placeholder="50" spellCheck={false} /></label>
        <label>items <input className="grim-in" value={f.items} onChange={set("items")} title="scale items averaged per score; 1 for a single integer measure" /></label>
        <button className="btn btn-primary" disabled={state.status === "running" || !f.mean.trim() || !f.n.trim()} onClick={run}>Check</button>
      </div>
      {state.status === "running" && <ProgressBar />}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d &&
        <div className="grim-result">
          <div className="grim-line">
            <span className="grim-k">GRIM</span>
            <span className={"cite-status " + (d.grim.consistent ? "verified" : "flagged")}>{d.grim.consistent ? "consistent" : "impossible"}</span>
            {!d.grim.consistent && <span className="grim-near">nearest possible: {d.grim.nearest.join(" / ")}</span>}
          </div>
          {d.grim.no_power && <div className="grim-caveat">N is large for this precision — GRIM has little power here (most means are achievable).</div>}
          {d.grimmer && d.grimmer.supported &&
            <div className="grim-line">
              <span className="grim-k">GRIMMER</span>
              <span className={"cite-status " + (d.grimmer.consistent ? "verified" : "flagged")}>{d.grimmer.consistent ? "consistent" : "impossible"}</span>
            </div>}
          {d.grimmer && !d.grimmer.supported && <div className="grim-caveat">{d.grimmer.note}</div>}
          <div className="grim-caveat">{d.grim.note} GRIM/GRIMMER assume integer-scale data — they don't apply to continuous measures. An inconsistency is a prompt to look, not a verdict or an accusation.</div>
        </div>}
      <div className="grim-credit">
        <b>Method:</b> GRIM — Brown &amp; Heathers (2017); GRIMMER — Anaya (2016) / Allard (2018).{" "}
        <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
          {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add to library"}
        </button>
        <div className="grim-credit-sub">Re-implemented in Python; cf. the <i>scrutiny</i> package (Lukas Jung). Surfaced via D. Lakens' automated-review catalog.</div>
      </div>
    </div>
  );
}

registerPaneSection({ id: "grim", label: "Data consistency (GRIM)", paneId: "methods", order: 30, render: () => <GrimSection /> });
```

- [ ] **Step 3: Add CSS** (`styles.css`, after the pcurve block, tokens only):

```css
  /* inc 127: GRIM calculator (METHODS). */
  .grim-section { font-size: 12px; }
  .grim-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px; margin: 8px 0; }
  .grim-form label { display: flex; flex-direction: column; font-size: 10px; color: var(--ink-3); gap: 2px; }
  .grim-in { width: 64px; font-family: var(--mono); font-size: 12px; padding: 3px 5px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel); color: var(--ink); }
  .grim-result { margin: 8px 0; }
  .grim-line { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .grim-k { font-family: var(--mono); font-size: 11px; color: var(--ink-3); width: 64px; }
  .grim-near { font-family: var(--mono); font-size: 11px; color: var(--ink-2); }
  .grim-caveat { font-size: 11px; color: var(--ink-3); line-height: 1.45; margin: 6px 0; }
  .grim-credit { font-size: 11.5px; color: var(--ink-2); border-top: 1px solid var(--line); padding-top: 8px; margin-top: 8px; }
  .grim-credit-sub { font-size: 10.5px; color: var(--ink-3); margin-top: 3px; }
```

- [ ] **Step 4: Rebuild + assembly test** — `python tools/build_frontend.py && python -m pytest tests/test_frontend_assembly.py -q` → PASS.

- [ ] **Step 5: Headed Playwright** — `.local/visual/drive_inc127_grim.py` (start a server on a free port against
  a copy of the validation DB; open the METHODS pane → "Data consistency (GRIM)"; enter mean 3.48 / N 20 → GRIM
  "impossible" + nearest 3.45/3.50; enter mean 5.23 / SD 2.55 / N 31 → GRIM consistent + GRIMMER consistent;
  add-to-library → "✓ added"; assert 0 console/page errors, 0 genai requests).

- [ ] **Step 6: Commit** — `git add app/frontend/js/07_methods_grim.jsx app/frontend/styles.css callosum-app.html && git commit -m "feat(methods): GRIM calculator METHODS section (inc 127 t3)"`.

---

### Task 4: gates + docs + verify + push

**Files:** Create `.claude/security-audits/2026-06-25_grim.md`, `.claude/qa-routes/route_37_methods_grim.md`,
`.claude/docs/increment-notes/INCREMENT-127-NOTES.md`; modify `app/backend/help/help_content.md`,
`THIRD-PARTY-NOTICES.md`, `.claude/changes.md`, `RECOVERY-LOG.md`, `.claude/CLAUDE.md`.

- [ ] **Step 1: Security audit** `2026-06-25_grim.md` — input validation (n/items bounds + parse → 422), no DB,
  no egress, no external fetch, no SQL, bounded enumeration (the SS loop is bounded by the SD interval); credit-add
  rides the audited inc-93 import. Negative paths: n=0 → 422; non-numeric mean → 422. **PASS**.
- [ ] **Step 2: QA route** `route_37_methods_grim.md` (`api: /methods/grim`; `fe: 07_methods_grim.jsx`) — assert
  the calculator flow, the integer-scale + no-power caveats, the nearest-possible inspectability, no
  accusation/score, 422 on bad input, and that it makes **no genai request** (local). Then
  `python tools/qa/build_surface_map.py extract && check` → 0 uncovered.
- [ ] **Step 3: Help corpus** — a "Data consistency (GRIM/GRIMMER)" section (what it checks, the integer-scale
  assumption, items, no-power-at-large-N, non-accusatory framing, the credit); move the `HELP-DOCS-SYNCED` marker
  to inc 127.
- [ ] **Step 4: THIRD-PARTY-NOTICES** — under the methods-lineage section add GRIM (Brown & Heathers 2017) +
  GRIMMER (Anaya 2016 / Allard 2018); note re-implementation + the `scrutiny` reference (credited, not reused).
- [ ] **Step 5: Docs** — `INCREMENT-127-NOTES.md` (Implemented / Key detail: the parity refinement makes
  GRIMMER correct; items=1 for GRIMMER; matches the scrutiny reference cases / Manual verification / Pytest) +
  `changes.md` entry + `RECOVERY-LOG.md` line + `.claude/CLAUDE.md` footer & "Increment 127" bump.
- [ ] **Step 6: Verify** — `ruff check . && ruff format --check . && python -m pytest -q` (expect ~470 passed;
  record the count) — apply `ruff format` if it flags new files. Surface check 0 uncovered.
- [ ] **Step 7: Commit + push** — commit the gates/docs; `git push origin main`; confirm CI green.

---

## Self-Review
**Spec coverage:** §2 GRIM+GRIMMER math → Task 1; §3 endpoint → Task 2; §4 frontend section → Task 3;
§5 gates (Principles/audit/QA/credit/help) → Tasks 1–4; §6 verification (hermetic + headed) → Tasks 1–4. GRIMMER
items=1 restriction honored (Task 1 `test_grimmer_multi_item_unsupported_v1`). ✔
**Placeholder scan:** full code for `grim.py`, the endpoint, and the section; tests with concrete expected values;
the only deferred value is the final pytest count + the headed-driver body (described concretely). The GRIMMER
fallback (Task 1 Step 4) is a risk-managed decision with a hard criterion (match scrutiny or ship GRIM-only), not
a placeholder. ✔
**Type/name consistency:** `grim_test`/`grimmer_test` + `GrimResult`/`GrimmerResult` defined Task 1, consumed
Task 2 (`vars(...)` → the matching Pydantic models) + Task 3 (`d.grim.*`, `d.grimmer.*`). `nearest` is a list of
strings throughout. The METHODS section needs no `40_app.jsx` change (self-registered). ✔
