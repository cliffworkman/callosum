"""Which retrieval profile an Ask actually uses (inc 618): the one policy every Ask route resolves through.

Order, re-evaluated against stored rows at the start of every operation:

1. An explicit user choice wins. A user-chosen MiniLM stays MiniLM. A user-forced Arctic S that has become
   incomplete fails closed (the inc-608 contract): it is never silently swapped.
2. Otherwise, when automatic selection is on, Arctic S is used if its pinned checkpoint is verified (inc 615) and its
   index covers every currently eligible passage at the current chunk version (``profile_coverage``). A completed
   index-run row or a finished download proves neither.
3. Otherwise the MiniLM baseline. Its contract is lazy: the ranking step embeds any candidate passage that lacks a
   current MiniLM vector before searching, so the searched set is always the whole candidate pool.

No index is ever queried for a subset of the pool: the ranking step separately refuses any non-lazy profile with a
missing candidate vector (``query_ranking`` / ``faceted_pipeline``), so an operation that resolved Arctic S and then
saw the library change fails closed rather than searching the indexed part.

Preference storage (``library_settings``): ``retrieval_embedding_profile`` holds the profile key and
``retrieval_embedding_profile_source`` holds ``user`` or ``modernization``. A key with no source predates inc 618;
the only writer before it was the user's own Settings selection, so it is treated as a user choice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import Connection, delete, select, text

from app.backend.embeddings.profiles import (
    ACTIVE_RETRIEVAL_PROFILE_SETTING,
    ARCTIC_S_PROFILE_KEY,
    BASELINE_PROFILE_KEY,
    PROFILES,
    EmbeddingProfile,
    IncompleteEmbeddingIndexError,
    get_profile,
    profile_coverage,
    require_complete_index,
)
from app.backend.model_provisioning import checkpoint_pending
from app.backend.persistence.schema import library_settings

PREFERENCE_SOURCE_SETTING = "retrieval_embedding_profile_source"
SOURCE_USER = "user"
SOURCE_MODERNIZATION = "modernization"
AUTOMATIC = "automatic"

# Why an automatic resolution is on MiniLM rather than Arctic S.
MODEL_UNAVAILABLE = "model_unavailable"  # the pinned checkpoint is not verified
INDEXING = "indexing"  # Arctic S has never been complete for this library yet
CATCHING_UP = "catching_up"  # Arctic S was activated; new or changed passages are being indexed
PAUSED = "paused"
CANCELLED = "cancelled"
FAILED = "failed"


@dataclass(frozen=True)
class Preference:
    key: str | None  # None = no stored selection (automatic)
    source: str | None  # user | modernization | None
    legacy: bool = False  # a selection written before inc 618 recorded its source

    @property
    def explicit(self) -> bool:
        return self.source == SOURCE_USER


@dataclass(frozen=True)
class Resolution:
    profile: EmbeddingProfile
    preference: str  # automatic | user
    preference_source: str | None
    intended: str | None  # Arctic S when automatic selection aims for it
    fallback_reason: str | None
    verified_complete: bool  # True only when a non-lazy profile's complete coverage was checked for this operation
    coverage: dict = field(default_factory=dict)

    def provenance(self, model: object, baseline_version: str | None) -> dict[str, object]:
        """The ``retrieval_embedding`` record: the encoder that actually ranked (read from the model itself, the
        inc-609 convention), plus why it was chosen."""
        record: dict[str, object] = {
            "profile": self.profile.key,
            "model_name": getattr(model, "name", None),
            "model_version": getattr(model, "version", None),
            "normalization": getattr(model, "normalization", None),
            "verification_embedding": baseline_version,
            "preference": self.preference,
            "preference_source": self.preference_source,
            "intended_profile": self.intended,
            "fallback_reason": self.fallback_reason,
            "index_verified_complete": self.verified_complete,
            "index_contract": "complete_index_required"
            if not self.profile.lazy_indexing
            else "baseline_embeds_missing",
        }
        if self.verified_complete:
            record["indexed_chunks"] = self.coverage.get("indexed_chunks")
        return record


def _get(conn: Connection, key: str) -> str | None:
    return conn.execute(select(library_settings.c.value).where(library_settings.c.key == key)).scalar_one_or_none()


def _put(conn: Connection, key: str, value: str) -> None:
    if _get(conn, key) is None:
        conn.execute(library_settings.insert().values(key=key, value=value))
    else:
        conn.execute(library_settings.update().where(library_settings.c.key == key).values(value=value))


def read_preference(conn: Connection) -> Preference:
    key = _get(conn, ACTIVE_RETRIEVAL_PROFILE_SETTING)
    source = _get(conn, PREFERENCE_SOURCE_SETTING)
    if key is None or key not in PROFILES:
        return Preference(None, None)  # unset, or a key from a newer build: nothing to honor
    if source not in (SOURCE_USER, SOURCE_MODERNIZATION):
        return Preference(key, SOURCE_USER, legacy=True)
    return Preference(key, source)


def _take_write_lock(conn: Connection) -> None:
    """Start the transaction with a write so the reads that follow see the latest commit and nothing can commit in
    between: a no-op UPDATE takes SQLite's writer lock without changing a row. Callers run inside ``run_write``,
    which retries the whole unit on a lock collision."""
    conn.execute(text("UPDATE library_settings SET value = value WHERE 0"))


def set_user_preference(conn: Connection, key: str | None) -> Preference:
    """The user's explicit choice, or ``None`` to return to automatic selection. Atomic against activation."""
    _take_write_lock(conn)
    if key is None:
        conn.execute(
            delete(library_settings).where(
                library_settings.c.key.in_((ACTIVE_RETRIEVAL_PROFILE_SETTING, PREFERENCE_SOURCE_SETTING))
            )
        )
        return Preference(None, None)
    profile = get_profile(key)
    _put(conn, ACTIVE_RETRIEVAL_PROFILE_SETTING, profile.key)
    _put(conn, PREFERENCE_SOURCE_SETTING, SOURCE_USER)
    return Preference(profile.key, SOURCE_USER)


def activate_arctic(conn: Connection, *, model_verified: bool) -> str:
    """Record Arctic S as the modernization-managed preference, in one write transaction that rechecks everything.

    Returns ``activated``, ``already_active``, ``user_preference``, ``model_unavailable`` or ``incomplete``. Never
    overwrites a user choice, never activates a partial or stale index, and is idempotent across checks and
    processes. Resolution still rechecks coverage per operation; this record only says activation happened.
    """
    _take_write_lock(conn)
    current = read_preference(conn)
    if current.explicit:
        return "user_preference"
    if not model_verified:
        return MODEL_UNAVAILABLE
    if not profile_coverage(conn, PROFILES[ARCTIC_S_PROFILE_KEY])["complete"]:
        return "incomplete"
    if current == Preference(ARCTIC_S_PROFILE_KEY, SOURCE_MODERNIZATION):
        return "already_active"
    _put(conn, ACTIVE_RETRIEVAL_PROFILE_SETTING, ARCTIC_S_PROFILE_KEY)
    _put(conn, PREFERENCE_SOURCE_SETTING, SOURCE_MODERNIZATION)
    return "activated"


def _fallback_reason(preference: Preference, *, model_verified: bool, paused: bool, run: dict | None) -> str:
    if not model_verified:
        return MODEL_UNAVAILABLE
    state = run["state"] if run else None
    if paused or state in ("paused", "pausing"):
        return PAUSED
    if state == "cancelled":
        return CANCELLED
    if state == "failed":
        return FAILED
    # Running, waiting, or about to be (re)scheduled by the coordinator's next check: activation decides which.
    activated = preference == Preference(ARCTIC_S_PROFILE_KEY, SOURCE_MODERNIZATION)
    return CATCHING_UP if activated else INDEXING


def resolve(
    conn: Connection,
    *,
    automatic: bool,
    model_status: Callable[[], dict],
    paused: bool = False,
    run: dict | None = None,
) -> Resolution:
    """The effective retrieval profile for one operation. Raises ``IncompleteEmbeddingIndexError`` only for a
    user-forced non-lazy profile whose index is incomplete."""
    preference = read_preference(conn)
    baseline = PROFILES[BASELINE_PROFILE_KEY]
    if preference.explicit:
        profile = get_profile(preference.key)  # type: ignore[arg-type]
        if profile.lazy_indexing:
            return Resolution(profile, SOURCE_USER, SOURCE_USER, None, None, False)
        coverage = require_complete_index(conn, profile)  # the inc-608 fail-closed contract, unchanged
        if checkpoint_pending(profile.model_name):  # never load unverified managed weights (no Hub fetch from Ask)
            raise IncompleteEmbeddingIndexError(CHECKPOINT_PENDING_MESSAGE.format(label=profile.label))
        return Resolution(profile, SOURCE_USER, SOURCE_USER, None, None, True, coverage)
    if not automatic:
        return Resolution(baseline, AUTOMATIC, None, None, None, False)
    arctic = PROFILES[ARCTIC_S_PROFILE_KEY]
    try:
        model_verified = model_status().get("state") == "verified"
    except Exception:  # noqa: BLE001 -- an unreadable provisioning state means "not verified", never a crash
        model_verified = False
    if model_verified:
        coverage = profile_coverage(conn, arctic)
        if coverage["complete"]:
            return Resolution(arctic, AUTOMATIC, preference.source, arctic.key, None, True, coverage)
    reason = _fallback_reason(preference, model_verified=model_verified, paused=paused, run=run)
    return Resolution(baseline, AUTOMATIC, preference.source, arctic.key, reason, False)


CHECKPOINT_PENDING_MESSAGE = (
    "The {label} model files are not verified on this computer, so Callosum will not load them. They are downloaded "
    "and checked again automatically. Until then, switch to MiniLM or to automatic selection."
)

FALLBACK_MESSAGES = {
    MODEL_UNAVAILABLE: "Using MiniLM until the Arctic S model has finished downloading and been verified.",
    INDEXING: "Using MiniLM while the Arctic S index is being built.",
    CATCHING_UP: "Using MiniLM while newly added or changed passages are indexed for Arctic S.",
    PAUSED: "Using MiniLM: Arctic S indexing is paused.",
    CANCELLED: "Using MiniLM: Arctic S indexing was cancelled.",
    FAILED: "Using MiniLM: Arctic S indexing stopped after repeated failures.",
}


def explanation(resolution: Resolution) -> str:
    """One plain sentence for the user. Never implies that a partial Arctic S index was searched."""
    if resolution.preference == SOURCE_USER:
        return f"Using {resolution.profile.label} because you selected it."
    if resolution.fallback_reason:
        return FALLBACK_MESSAGES[resolution.fallback_reason]
    if resolution.profile.key == ARCTIC_S_PROFILE_KEY:
        return "Using Arctic S: its index covers every passage in this library."
    return f"Using {resolution.profile.label}."
