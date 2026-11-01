"""Which NLI model verifies a synthesis (inc 619): the one policy every synthesis route resolves through.

Order, decided once per operation, before retrieval or generation starts (the operation boundary):

1. An explicit user choice wins. A chosen MiniLM2 stays MiniLM2. A chosen DeBERTa that is not verified on disk,
   cannot be loaded, or does not fit in memory is refused with a stated reason; it is never swapped for MiniLM2.
2. Otherwise DeBERTa, when the release gates permit automatic use (``DEBERTA_RELEASE_GATES``, inc 615), its pinned
   checkpoint is verified by the provisioner, the memory precheck passes, and it loads and passes its label /
   architecture / tokenizer contract.
3. Otherwise MiniLM2, the compatibility verifier, with ``fallback_reason`` recorded.

The verifier chosen at the boundary is used for every claim of the operation. If it fails after scoring starts
(including running out of memory), the operation fails and saves nothing (inc 609); no claim is ever scored by a
different model. The next operation resolves again.

Thresholds are unchanged and shared (support 0.55, contradiction 0.55, calibrated on MiniLM2); this module never
reads or changes them, it only records them.

Preference storage (``library_settings``): ``verification_nli_profile`` holds the key and
``verification_nli_profile_source`` holds ``user``. A key without a source predates inc 619; the only writer before it
was the Settings selection, so it is kept as the user's choice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Connection, delete, select, text

from app.backend.embeddings.resources import ResourcePolicy, ResourceSnapshot
from app.backend.persistence.schema import library_settings
from app.backend.summarization.nli_profiles import (
    ACTIVE_NLI_PROFILE_SETTING,
    BASELINE_NLI_PROFILE_KEY,
    DEBERTA_NLI_PROFILE_KEY,
    NLI_PROFILES,
    NliProfile,
    get_nli_profile,
)

PREFERENCE_SOURCE_SETTING = "verification_nli_profile_source"
SOURCE_USER = "user"
AUTOMATIC = "automatic"
PREFERRED_PROFILE_KEY = DEBERTA_NLI_PROFILE_KEY  # the product's intended verifier for 0.6.0

# Stable fallback reasons (why a synthesis was verified with MiniLM2 rather than DeBERTa).
NOT_QUALIFIED = "not_qualified"  # the release gates do not yet permit automatic use
NOT_PROVISIONED = "not_provisioned"  # the checkpoint is absent or still downloading
NOT_VERIFIED = "not_verified"  # present but unverified, invalid, unreadable, or failed to load / its contract
INSUFFICIENT_MEMORY = "insufficient_memory"
MEMORY_UNMEASURED = "memory_unmeasured"  # free memory could not be measured: treated as insufficient
USER_CHOICE = "user_choice"  # the user selected MiniLM2

_NOT_PROVISIONED_STATES = {"absent", "downloading", "waiting_for_network", "interrupted", "insufficient_resources"}

# G2 (dev runtime, 16 GB Windows, torch 2.6): the process held 540 MB after imports and the embedding model, peaked at
# 2,016 MB with DeBERTa loaded and scoring (1,601 MB after load). Loading and running it therefore needs about
# 1,476 MB beyond what is already resident; once loaded, inference added about 415 MB. Rounded up. Both exceed the
# G2 condition (~1.1 GB over MiniLM2) when DeBERTa is not yet loaded. Not measured on 8 GB machines, macOS, Linux, or
# the packaged runtime.
DEBERTA_LOAD_AND_RUN_MB = 1500
DEBERTA_RESIDENT_RUN_MB = 512


class VerifierUnavailableError(RuntimeError):
    """An explicitly chosen verifier cannot run safely. The message is user-facing and names the way back."""


@dataclass(frozen=True)
class NliPreference:
    key: str | None  # None = automatic
    legacy: bool = False

    @property
    def explicit(self) -> bool:
        return self.key is not None


@dataclass(frozen=True)
class MemoryCheck:
    ok: bool
    need_mb: int
    free_mb: int | None
    reserve_mb: int | None
    indexing_reserve_mb: int
    resident: bool
    source: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "need_mb": self.need_mb,
            "free_mb": self.free_mb,
            "reserve_mb": self.reserve_mb,
            "indexing_reserve_mb": self.indexing_reserve_mb,
            "deberta_resident": self.resident,
            "source": self.source,
        }


def memory_check(probe: Callable[[], ResourceSnapshot], *, resident: bool, indexing_reserve_mb: int = 0) -> MemoryCheck:
    """Free memory (the lower of available physical memory and, on Windows, available commit; it already excludes
    this process and any running index worker) must cover DeBERTa's need, the policy's reserve, and the remaining
    allowance for a running index worker. An unmeasurable snapshot fails the check."""
    need = (DEBERTA_RESIDENT_RUN_MB if resident else DEBERTA_LOAD_AND_RUN_MB) + max(0, indexing_reserve_mb)
    try:
        snapshot = probe()
    except Exception:  # noqa: BLE001 -- an unreadable measurement is never treated as "enough"
        return MemoryCheck(False, need, None, None, indexing_reserve_mb, resident, None)
    policy = ResourcePolicy.for_machine(snapshot)
    free = snapshot.available_physical_mb
    if snapshot.available_commit_mb is not None:
        free = min(free, snapshot.available_commit_mb)
    return MemoryCheck(
        policy.can_start(snapshot, need), need, free, policy.reserve_mb, indexing_reserve_mb, resident, snapshot.source
    )


def read_nli_preference(conn: Connection) -> NliPreference:
    def get(key: str) -> str | None:
        return conn.execute(select(library_settings.c.value).where(library_settings.c.key == key)).scalar_one_or_none()

    key, source = get(ACTIVE_NLI_PROFILE_SETTING), get(PREFERENCE_SOURCE_SETTING)
    if key is None or key not in NLI_PROFILES:
        return NliPreference(None)  # unset, or a key from a newer build: nothing to honor
    return NliPreference(key, legacy=source != SOURCE_USER)


def set_nli_user_preference(conn: Connection, key: str | None) -> NliPreference:
    """The user's explicit choice, or ``None`` to return to automatic selection."""
    conn.execute(text("UPDATE library_settings SET value = value WHERE 0"))  # take the writer lock first
    keys = (ACTIVE_NLI_PROFILE_SETTING, PREFERENCE_SOURCE_SETTING)
    conn.execute(delete(library_settings).where(library_settings.c.key.in_(keys)))
    if key is None:
        return NliPreference(None)
    profile = get_nli_profile(key)
    conn.execute(
        library_settings.insert(),
        [
            {"key": ACTIVE_NLI_PROFILE_SETTING, "value": profile.key},
            {"key": PREFERENCE_SOURCE_SETTING, "value": SOURCE_USER},
        ],
    )
    return NliPreference(profile.key)


@dataclass(frozen=True)
class VerifierDecision:
    profile: NliProfile
    preference: str  # automatic | user
    legacy_preference: bool
    fallback_reason: str | None
    memory: MemoryCheck | None

    def provenance(self, *, support_threshold: float, contradiction_threshold: float, similarity_threshold: float):
        """The ``verification_nli`` record (extends the inc-608/609 record; older rows simply lack the new keys)."""
        return {
            "verification_nli": {
                "profile": self.profile.key,
                "model_name": self.profile.model_name,
                "revision": self.profile.revision,
                "thresholds_calibrated_on": NLI_PROFILES[BASELINE_NLI_PROFILE_KEY].model_name,
                "embedding_fallback": False,
                "preference": self.preference,
                "preferred_profile": PREFERRED_PROFILE_KEY,
                "fallback_reason": self.fallback_reason,
                "support_threshold": support_threshold,
                "contradiction_threshold": contradiction_threshold,
                "similarity_threshold": similarity_threshold,
                "memory_check": self.memory.as_dict() if self.memory is not None else None,
            }
        }


def _state_reason(state: str | None) -> str | None:
    if state == "verified":
        return None
    return NOT_PROVISIONED if state in _NOT_PROVISIONED_STATES else NOT_VERIFIED


UNAVAILABLE_MESSAGES = {
    NOT_VERIFIED: "The {label} model files are not verified on this computer, so Callosum will not load them.",
    NOT_PROVISIONED: "The {label} model has not been downloaded and verified yet.",
    INSUFFICIENT_MEMORY: "There is not enough free memory to run {label} safely right now.",
    MEMORY_UNMEASURED: "Free memory could not be measured, so {label} was not started.",
}
WAY_BACK = " Nothing was saved. Choose Automatic or MiniLM2 in Settings → Verification model, or try again later."


def decide(
    preference: NliPreference,
    *,
    gates_armed: bool,
    model_state: Callable[[], str | None],
    checkpoint_required: bool,
    memory: Callable[[], MemoryCheck],
) -> VerifierDecision:
    """Choose before anything loads. ``checkpoint_required`` is True when the provisioner manages the checkpoint
    (packaged app); a user-chosen DeBERTa in a source checkout may load an already-cached copy (offline only)."""
    baseline, preferred = NLI_PROFILES[BASELINE_NLI_PROFILE_KEY], NLI_PROFILES[PREFERRED_PROFILE_KEY]
    if preference.explicit:
        profile = get_nli_profile(preference.key)  # type: ignore[arg-type]
        if profile.key == BASELINE_NLI_PROFILE_KEY:
            return VerifierDecision(profile, SOURCE_USER, preference.legacy, USER_CHOICE, None)
        if checkpoint_required and (reason := _state_reason(_safe(model_state))) is not None:
            raise VerifierUnavailableError(UNAVAILABLE_MESSAGES[reason].format(label=profile.label) + WAY_BACK)
        check = memory()
        if not check.ok:
            reason = INSUFFICIENT_MEMORY if check.free_mb is not None else MEMORY_UNMEASURED
            raise VerifierUnavailableError(UNAVAILABLE_MESSAGES[reason].format(label=profile.label) + WAY_BACK)
        return VerifierDecision(profile, SOURCE_USER, preference.legacy, None, check)
    if not gates_armed:
        return VerifierDecision(baseline, AUTOMATIC, False, NOT_QUALIFIED, None)
    if (reason := _state_reason(_safe(model_state))) is not None:
        return VerifierDecision(baseline, AUTOMATIC, False, reason, None)
    check = memory()
    if not check.ok:
        reason = INSUFFICIENT_MEMORY if check.free_mb is not None else MEMORY_UNMEASURED
        return VerifierDecision(baseline, AUTOMATIC, False, reason, check)
    return VerifierDecision(preferred, AUTOMATIC, False, None, check)


def _safe(model_state: Callable[[], str | None]) -> str | None:
    try:
        return model_state()
    except Exception:  # noqa: BLE001 -- an unreadable provisioning state is "not verified", never a crash
        return None


def load_failed(decision: VerifierDecision, exc: BaseException) -> VerifierDecision:
    """DeBERTa was chosen but would not load or failed its contract, before any claim was scored. Automatic selection
    records ``not_verified`` and uses MiniLM2; an explicit choice is refused."""
    if decision.preference == SOURCE_USER:
        message = UNAVAILABLE_MESSAGES[NOT_VERIFIED].format(label=decision.profile.label)
        raise VerifierUnavailableError(message + WAY_BACK) from exc
    return VerifierDecision(NLI_PROFILES[BASELINE_NLI_PROFILE_KEY], AUTOMATIC, False, NOT_VERIFIED, decision.memory)


AUTOMATIC_EXPLANATIONS = {
    NOT_QUALIFIED: "Using MiniLM2: automatic DeBERTa verification is not enabled in this release yet.",
    NOT_PROVISIONED: "Using MiniLM2 until the DeBERTa model has been downloaded and verified.",
    NOT_VERIFIED: "Using MiniLM2: the DeBERTa model files could not be verified or loaded.",
    INSUFFICIENT_MEMORY: "Using MiniLM2: not enough free memory to run DeBERTa safely right now.",
    MEMORY_UNMEASURED: "Using MiniLM2: free memory could not be measured.",
}


def explanation(decision: VerifierDecision) -> str:
    """One plain sentence about which verifier the next synthesis uses and why."""
    if decision.preference == SOURCE_USER:
        return f"Using {decision.profile.label} because you selected it."
    return AUTOMATIC_EXPLANATIONS.get(decision.fallback_reason or "", f"Using {decision.profile.label}.")
