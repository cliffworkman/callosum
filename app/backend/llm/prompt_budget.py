"""Shared provider-aware prompt-size budgeting.

The managed Local AI preview runs a fixed 12,288-token context (2,048 reserved for output — see
``managed_local.py``'s ``_PREVIEW_CONTEXT_TOKENS``/``max_output_tokens``), leaving roughly 10,240
tokens (conservatively ~30-40k characters) for input. Cloud providers have an effectively unbounded
context by comparison. Several prompt-builders across the codebase size their input only for cloud
providers, which can silently overflow the managed target's window with no local guard.

This module generalizes the truncate-never-drop pattern first shipped for Synthesize/Ask
(``integrations/gemini/generator.py``) and Critical Review (``integrations/gemini/critical_review.py``):
when the active provider is ``managed_local``, truncate each item's text down to an even share of a
conservative total-character budget rather than dropping any item outright — a truncated prefix
remains a genuine substring of the original text, so downstream verbatim-quote verification/anchoring
(invariant #1/#2) is unaffected. Cloud and manually-configured providers are never truncated here.

Each call site still picks its own ``total_chars`` (see the sites listed in
``.claude/docs/research/2026-09-01_llm-provider-integration-audit.md``'s prompt-overflow table) —
sized conservatively below the ~10,240-token ceiling, since the surrounding prompt also carries
instructions/scaffolding beyond the raw item content.
"""

from __future__ import annotations

from collections.abc import Sequence

MANAGED_LOCAL_PROVIDER = "managed_local"


def is_managed_local(provider: str | None) -> bool:
    return provider == MANAGED_LOCAL_PROVIDER


def per_item_char_budget(item_count: int, *, total_chars: int, min_chars: int = 200) -> int:
    """Divide ``total_chars`` evenly across ``item_count`` items, never below ``min_chars`` per item."""
    if item_count <= 0:
        return total_chars
    return max(min_chars, total_chars // item_count)


def truncate_items(items: Sequence[str], *, provider: str | None, total_chars: int, min_chars: int = 200) -> list[str]:
    """Truncate each item (never drop one) to fit ``total_chars`` total when ``provider`` is managed_local.

    Returns ``items`` unchanged (as a list) for every other provider, or when ``items`` is empty."""
    if not is_managed_local(provider) or not items:
        return list(items)
    limit = per_item_char_budget(len(items), total_chars=total_chars, min_chars=min_chars)
    return [item[:limit] for item in items]


def truncate_text(text: str, *, provider: str | None, total_chars: int) -> str:
    """Truncate a single blob of text to ``total_chars`` when ``provider`` is managed_local, else unchanged."""
    if not is_managed_local(provider):
        return text
    return text[:total_chars]


def select_total_chars(provider: str | None, *, cloud_default: int, managed_local_budget: int) -> int:
    """Pick the total-character budget a call site should bound its prompt content to: its existing
    cloud-sized default for cloud/manual providers, or a conservative managed_local-specific budget
    when the active provider is managed_local. Fits call sites that already track cumulative size
    against one constant (e.g. an existing ``MAX_TOTAL_INPUT_CHARS``) and only need that constant to
    shrink for the managed target."""
    return managed_local_budget if is_managed_local(provider) else cloud_default
