"""Lightweight LLM token-usage logging (inc 61).

Reads ``response.usage_metadata`` (when the provider returns it) and logs prompt/candidate/total token
counts per call site, so real token spend can be measured and the deferred cost levers (output caps,
top_k, provider caching) sized. Read-only — no behavior change, no persistence, and no failure surface
(a missing or odd ``usage_metadata`` is silently skipped).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("callosum.llm.usage")


def log_usage(site: str, model: str, response: Any) -> None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return
    logger.info(
        "llm-usage site=%s model=%s prompt=%s candidates=%s total=%s",
        site,
        model,
        getattr(meta, "prompt_token_count", None),
        getattr(meta, "candidates_token_count", None),
        getattr(meta, "total_token_count", None),
    )
