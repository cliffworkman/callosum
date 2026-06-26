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
        note = (
            "GRIM-inconsistent — no integer dataset of this N gives this mean at this precision. Usually a typo "
            "or a misreported N; assumes integer-scale data — a prompt to look, not a verdict."
        )
    return GrimResult(consistent, mean, n, items, d, 1.0 / denom, nearest, no_power, note)


def grimmer_test(mean: str, sd: str, n: int, items: int = 1) -> GrimmerResult:
    _check(n, items)
    d_sd = _decimals(sd)
    if items != 1:
        return GrimmerResult(
            False,
            sd,
            d_sd,
            supported=False,
            note="Multi-item GRIMMER isn't supported yet — GRIM still checks the mean above.",
        )
    d_m = _decimals(mean)
    m, s = float(mean), float(sd)
    totals = _consistent_totals(m, n, d_m)
    if not totals:
        return GrimmerResult(
            False,
            sd,
            d_sd,
            supported=True,
            note="The mean is GRIM-inconsistent, so the SD cannot be consistent either.",
        )
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
    note = (
        "Consistent — an integer sum of squares matches this mean, SD, and N."
        if consistent
        else (
            "GRIMMER-inconsistent — no integer dataset of this N gives this mean AND SD. A prompt to look, not a "
            "verdict; assumes integer-scale, single-item data."
        )
    )
    return GrimmerResult(consistent, sd, d_sd, supported=True, note=note)
