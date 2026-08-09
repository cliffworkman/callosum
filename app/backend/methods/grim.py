"""GRIM + GRIMMER + DEBIT — granularity/consistency checks for reported summary statistics (inc 127, inc 467).

GRIM (Brown & Heathers, 2017): a mean of N integer observations (each the average of `items` integer items) must
equal K/(N*items) for an integer K; rounded to the reported decimals, only some means are achievable. GRIMMER
(Anaya 2016; Allard 2018 analytic): additionally the reported SD must correspond to an integer sum of squares
consistent with that mean and N, with the parity refinement Sum(x^2) == Sum(x) (mod 2) for integer x.

DEBIT (Heathers & Brown, 2019): the binary-data analog — for a variable that can only take values 0/1, the
sample SD is fully determined by the mean and N (Bessel-corrected): SD = sqrt(K(n-K) / (n(n-1))) for the
integer count K implied by the mean. Reuses grim_test for the mean's own GRIM-consistency (binary data is the
items=1 case) before checking whether the reported SD matches what that mean and N imply.

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


@dataclass(frozen=True)
class DebitResult:
    consistent: bool
    reported_mean: str
    reported_sd: str
    n: int
    mean_consistent: bool  # GRIM-consistency of the mean alone, for binary (items=1) data
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
    # Multi-item (items>1): each person's score is the mean of `items` integer items, so over all N*items item
    # responses the total T is an integer and the variance of the N person-scores is
    # (Sum(c_i^2) - T^2/N) / (items^2 * (N-1)), where c_i is person i's integer item-sum. So the achievable integer
    # Sum(c_i^2) = SD^2 * (N-1) * items^2 + T^2/N, with the same parity refinement Sum(c_i^2) == Sum(c_i) = T (mod 2).
    # items=1 is the special case (items^2 = 1). Validated against the scrutiny reference cases.
    _check(n, items)
    d_sd = _decimals(sd)
    d_m = _decimals(mean)
    m, s = float(mean), float(sd)
    totals = _consistent_totals(m, n * items, d_m)  # the integer total over all N*items item responses
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
        ss_lo = s_lo * s_lo * (n - 1) * items * items + (total * total) / n
        ss_hi = s_hi * s_hi * (n - 1) * items * items + (total * total) / n
        lo_i, hi_i = math.ceil(ss_lo - 1e-9), math.floor(ss_hi + 1e-9)
        # an integer sum-of-squares in the SD interval with the right parity (Sum(c^2) == Sum(c) (mod 2))
        if any((ss % 2) == (total % 2) for ss in range(lo_i, hi_i + 1)):
            consistent = True
            break
    note = (
        "Consistent — an integer sum of squares matches this mean, SD, and N."
        if consistent
        else (
            "GRIMMER-inconsistent — no integer dataset of this N gives this mean AND SD. A prompt to look, not a "
            "verdict; assumes integer-scale data."
        )
    )
    return GrimmerResult(consistent, sd, d_sd, supported=True, note=note)


def debit_test(mean: str, sd: str, n: int) -> DebitResult:
    # For binary (0/1) data with n observations and mean M = K/n (K the count of 1s), the sample SD is fully
    # determined: Sum((x_i - M)^2) = K*(1-M)^2 + (n-K)*M^2 = K*(n-K)/n, so the Bessel-corrected sample SD is
    # sqrt(K*(n-K) / (n*(n-1))). Candidate K values come from grim_test's own rounding-tolerant reconstruction
    # (the reported mean may round from more than one exact K/n), matching GRIMMER's own tolerance treatment for
    # the reported SD (±half a unit in its last decimal place).
    if n < 2:
        raise ValueError("n must be at least 2 for a sample SD to be defined")
    _check(n, 1)
    grim = grim_test(mean, n, items=1)
    if not grim.consistent:
        return DebitResult(
            False,
            mean,
            sd,
            n,
            mean_consistent=False,
            note="The mean is GRIM-inconsistent for binary (0/1) data, so the SD cannot be consistent either.",
        )
    d_sd = _decimals(sd)
    totals = _consistent_totals(float(mean), n, _decimals(mean))
    half = 0.5 * 10 ** (-d_sd)
    s = float(sd)
    s_lo, s_hi = max(0.0, s - half), s + half
    consistent = any(s_lo <= math.sqrt((k * (n - k)) / (n * (n - 1))) <= s_hi for k in totals)
    note = (
        "Consistent — the reported SD matches the SD implied by this mean and N for binary (0/1) data."
        if consistent
        else (
            "DEBIT-inconsistent — for binary (0/1) data the SD is fully determined by the mean and N; the "
            "reported SD doesn't match. A prompt to look, not a verdict; assumes truly binary (0/1) data."
        )
    )
    return DebitResult(consistent, mean, sd, n, mean_consistent=True, note=note)
