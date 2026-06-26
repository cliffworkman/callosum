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
    assert isinstance(r, GrimmerResult) and r.consistent is False


def test_grimmer_multi_item_unsupported_v1():
    r = grimmer_test("2.74", "0.96", 63, items=2)
    assert r.supported is False  # GRIM still works for items>1; GRIMMER multi-item is deferred
