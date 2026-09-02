"""app/backend/llm/prompt_budget.py — the shared provider-aware prompt-size budgeting utility."""

from __future__ import annotations

from app.backend.llm.prompt_budget import (
    is_managed_local,
    per_item_char_budget,
    select_total_chars,
    truncate_items,
    truncate_text,
)


def test_is_managed_local():
    assert is_managed_local("managed_local")
    assert not is_managed_local("gemini")
    assert not is_managed_local("local")
    assert not is_managed_local(None)


def test_per_item_char_budget_divides_evenly_with_a_floor():
    assert per_item_char_budget(4, total_chars=8000) == 2000
    assert per_item_char_budget(0, total_chars=8000) == 8000  # no items -> the whole budget
    assert per_item_char_budget(1000, total_chars=8000) == 200  # never below min_chars
    assert per_item_char_budget(1000, total_chars=8000, min_chars=50) == 50


def test_truncate_items_only_truncates_for_managed_local_never_drops():
    items = ["a" * 1000, "b" * 1000, "c" * 1000]
    cloud = truncate_items(items, provider="gemini", total_chars=300)
    assert cloud == items  # cloud/manual providers are never truncated here

    managed = truncate_items(items, provider="managed_local", total_chars=300, min_chars=50)
    assert len(managed) == 3  # never drops an item
    assert all(len(x) == 100 for x in managed)  # 300 // 3 items
    assert managed[0] == items[0][:100]  # a genuine prefix, not a rewrite


def test_truncate_items_empty_list_is_a_noop():
    assert truncate_items([], provider="managed_local", total_chars=300) == []


def test_truncate_text_only_truncates_for_managed_local():
    text = "x" * 5000
    assert truncate_text(text, provider="gemini", total_chars=1000) == text
    assert truncate_text(text, provider="managed_local", total_chars=1000) == text[:1000]


def test_select_total_chars_picks_by_provider():
    assert select_total_chars("gemini", cloud_default=60000, managed_local_budget=8000) == 60000
    assert select_total_chars("managed_local", cloud_default=60000, managed_local_budget=8000) == 8000
    assert select_total_chars(None, cloud_default=60000, managed_local_budget=8000) == 60000
