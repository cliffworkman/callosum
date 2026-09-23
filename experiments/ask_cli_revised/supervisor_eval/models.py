"""Candidate registry and the ONE uniform run envelope. Data only.

Nothing here is tuned per model. The envelope is the one ask_070's neutral-preflight spec fixes
(prompt <= 8192, generation <= 4096, total 12288); temperature 0 / seed 42 match the Qwen control so the
comparison is like-for-like. `think_level` records each model family's own *default* reasoning level, not a
tuned value: a model that reasons natively is run with its native reasoning on, and its reasoning text is
stored privately but never scored.
"""

ENVELOPE = {"num_ctx": 12288, "num_predict": 4096, "temperature": 0, "seed": 42, "num_thread": 6, "num_batch": 512}
KEEP_ALIVE = "30m"
BATTERY_CALL_WALL_TIMEOUT_S = 1200.0  # uniform per-call watchdog for the semantic battery
STAGE0_CALL_WALL_TIMEOUT_S = 600.0  # ask_070's neutral-preflight inference watchdog

# `size_gb` is the ollama.com library download size, used only to check store headroom before a pull.
CANDIDATES = [
    {"key": "qwen3.5-9b", "tag": "qwen3.5:9b", "think_level": None, "size_gb": 6.6},
    {"key": "gemma3-12b", "tag": "gemma3:12b", "think_level": None, "size_gb": 8.1},
    {"key": "phi4-14b", "tag": "phi4:14b", "think_level": None, "size_gb": 9.1},
    {"key": "gpt-oss-20b", "tag": "gpt-oss:20b", "think_level": "medium", "size_gb": 14.0},  # takes a level, not a bool
]

BLOCKED = "BLOCKED_PENDING_RUNTIME_CHANGE"


def by_key(key):
    return next(c for c in CANDIDATES if c["key"] == key)


def think_setting(candidate, capabilities):
    """The `think` request value for a candidate: native default reasoning ON where the runtime says it has it."""
    if "thinking" not in (capabilities or []):
        return None
    return candidate["think_level"] or True
