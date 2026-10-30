"""Verification NLI profiles: which local cross-encoder scores citation support/contradiction for synthesis.

The baseline (MiniLM2) is unchanged and is the rollback. An alternative profile is a pinned checkpoint plus the
exact contract it must satisfy -- label order, architecture and tokenizer -- verified on the loaded model before any
score is used, because a silently mis-ordered softmax would turn entailment into contradiction. The verification
thresholds (support >= 0.55, contradiction >= 0.55) are NOT re-tuned per profile: they are probabilities of the same
labels, but they were calibrated on MiniLM2, so a non-baseline profile is labelled uncalibrated wherever it appears.

Scope: synthesis citation verification only. Stance features (Suggest-citation, Critical Read, citation context)
keep MiniLM2 and their own thresholds; switching this profile never changes them.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, func, select

from app.backend.model_runtime import PINNED_MODEL_REVISIONS
from app.backend.persistence.schema import library_settings
from app.backend.summarization.stance import DEFAULT_NLI_MODEL


@dataclass(frozen=True)
class NliProfile:
    key: str
    label: str
    model_name: str
    revision: str
    id2label: dict[int, str]  # the exact label order this profile's scores are read with
    model_type: str
    tokenizer_class_prefix: str
    enforce_contract: bool  # the baseline keeps its legacy load path byte-for-byte
    qualification: str


BASELINE_NLI_PROFILE_KEY = "minilm2"
DEBERTA_NLI_PROFILE_KEY = "deberta-v3-base"
_DEBERTA_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

NLI_PROFILES: dict[str, NliProfile] = {
    BASELINE_NLI_PROFILE_KEY: NliProfile(
        key=BASELINE_NLI_PROFILE_KEY,
        label="MiniLM2 NLI (baseline)",
        model_name=DEFAULT_NLI_MODEL,
        revision=PINNED_MODEL_REVISIONS.get(DEFAULT_NLI_MODEL) or "",
        id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
        model_type="bert",
        tokenizer_class_prefix="Bert",
        enforce_contract=False,
        qualification="Production default; the verification thresholds were calibrated on this model.",
    ),
    DEBERTA_NLI_PROFILE_KEY: NliProfile(
        key=DEBERTA_NLI_PROFILE_KEY,
        label="DeBERTa-v3 base NLI",
        model_name=_DEBERTA_MODEL,
        revision=PINNED_MODEL_REVISIONS[_DEBERTA_MODEL],
        id2label={0: "entailment", 1: "neutral", 2: "contradiction"},
        model_type="deberta-v2",
        tokenizer_class_prefix="DebertaV2",
        enforce_contract=True,
        qualification="Experimental and uncalibrated: uses the MiniLM2-calibrated thresholds unchanged.",
    ),
}

ACTIVE_NLI_PROFILE_SETTING = "verification_nli_profile"


class UnknownNliProfileError(ValueError):
    pass


class NliProfileConfigurationError(RuntimeError):
    """The loaded checkpoint does not match the contract its profile scores are read with."""


def get_nli_profile(key: str) -> NliProfile:
    try:
        return NLI_PROFILES[key]
    except KeyError:
        raise UnknownNliProfileError(f"Unknown NLI profile: {key}") from None


def active_nli_profile(conn: Connection) -> NliProfile:
    """The library's verification NLI profile; the baseline when unset or unknown (never a guess)."""
    value = conn.execute(
        select(library_settings.c.value).where(library_settings.c.key == ACTIVE_NLI_PROFILE_SETTING)
    ).scalar_one_or_none()
    return NLI_PROFILES.get(value or BASELINE_NLI_PROFILE_KEY, NLI_PROFILES[BASELINE_NLI_PROFILE_KEY])


def set_active_nli_profile(conn: Connection, key: str) -> NliProfile:
    profile = get_nli_profile(key)
    values = {"value": profile.key, "updated_at": func.current_timestamp()}
    where = library_settings.c.key == ACTIVE_NLI_PROFILE_SETTING
    if conn.execute(select(library_settings.c.key).where(where)).first() is None:
        conn.execute(library_settings.insert().values(key=ACTIVE_NLI_PROFILE_SETTING, **values))
    else:
        conn.execute(library_settings.update().where(where).values(**values))
    return profile


def verify_nli_checkpoint(model: object, profile: NliProfile) -> None:
    """Refuse a checkpoint whose label order, architecture or tokenizer differs from the profile's contract."""
    if not profile.enforce_contract:
        return
    inner = getattr(model, "model", None)
    config = getattr(inner, "config", None)
    raw = getattr(config, "id2label", None)
    if not isinstance(raw, dict):
        raise NliProfileConfigurationError(f"{profile.model_name}: checkpoint has no label map")
    labels = {int(k): str(v).lower() for k, v in raw.items()}
    if labels != profile.id2label:
        raise NliProfileConfigurationError(
            f"{profile.model_name}: label order {labels} does not match the expected {profile.id2label}"
        )
    if getattr(config, "model_type", None) != profile.model_type:
        raise NliProfileConfigurationError(
            f"{profile.model_name}: architecture {getattr(config, 'model_type', None)!r}, expected {profile.model_type!r}"
        )
    tokenizer = type(getattr(model, "tokenizer", None)).__name__
    if not tokenizer.startswith(profile.tokenizer_class_prefix):
        raise NliProfileConfigurationError(
            f"{profile.model_name}: tokenizer {tokenizer}, expected {profile.tokenizer_class_prefix}*"
        )


def verification_nli_provenance(profile: NliProfile) -> dict[str, object]:
    """Recorded on every synthesis, baseline included, so a missing record means "unknown" rather than "MiniLM2".
    ``embedding_fallback: False`` marks runs made under the no-fallback contract: NLI failure fails the job, so a
    saved record can never hold cosine scores under an NLI label (rows written before it carry no such marker)."""
    return {
        "verification_nli": {
            "profile": profile.key,
            "model_name": profile.model_name,
            "revision": profile.revision,
            "thresholds_calibrated_on": NLI_PROFILES[BASELINE_NLI_PROFILE_KEY].model_name,
            "embedding_fallback": False,
        }
    }
