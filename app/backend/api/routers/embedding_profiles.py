"""Retrieval embedding profiles (coverage, index builds, selection) and the verification NLI profile selection.

Local only: building an index runs the profile's pinned local model over this library's own chunks; nothing leaves
the machine (a first use may fetch the pinned weights from the Hugging Face Hub, a model request, not library text).
Only Ask's evidence retrieval follows the selected profile; citation verification stays on the MiniLM baseline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.backend.api.routers.embedding_index import IndexRunOut, active_index_job_id, index_run_out
from app.backend.embeddings.profiles import (
    BASELINE_PROFILE_KEY,
    PROFILES,
    EmbeddingProfile,
    IncompleteEmbeddingIndexError,
    UnknownEmbeddingProfileError,
    get_profile,
    profile_coverage,
)
from app.backend.embeddings.retrieval_resolution import AUTOMATIC, explanation, read_preference, set_user_preference
from app.backend.persistence.sqlite_retry import run_write
from app.backend.summarization.nli_profiles import (
    BASELINE_NLI_PROFILE_KEY,
    NLI_PROFILES,
    UnknownNliProfileError,
    active_nli_profile,
    get_nli_profile,
    set_active_nli_profile,
    verify_nli_checkpoint,
)

router = APIRouter(tags=["embedding-profiles"])


class ProfileCoverage(BaseModel):
    eligible_chunks: int
    indexed_chunks: int
    missing_chunks: int
    complete: bool
    live_papers: int
    papers_with_eligible_chunks: int
    papers_without_passage_text: int


class ProfileOut(BaseModel):
    key: str
    label: str
    model_name: str
    revision: str
    model_version: str
    normalization: str
    query_prefix: str
    document_prefix: str
    pooling: str | None
    qualification: str
    is_baseline: bool
    coverage: ProfileCoverage
    index_run: IndexRunOut | None = None  # inc 610: durable build lifecycle, None if never built


class ProfilesResponse(BaseModel):
    active: str  # inc 618: the profile Ask would use right now (the effective one), not merely the stored choice
    preference: str  # "automatic", or the key the user explicitly selected
    preference_source: str | None = None  # user | modernization | None
    legacy_preference: bool = False  # a selection saved before inc 618 recorded who made it; kept as the user's
    fallback_reason: str | None = None
    explanation: str
    ask_blocked: str | None = None  # a user-forced profile whose index is incomplete: Ask fails closed with this
    verification_model: str  # what citation verification uses regardless of the retrieval profile
    profiles: list[ProfileOut]
    index_job_id: str | None = None


class SelectProfileRequest(BaseModel):
    key: str = Field(min_length=1, max_length=40)


def _profile_out(profile: EmbeddingProfile, coverage: dict, run: IndexRunOut | None = None) -> ProfileOut:
    return ProfileOut(
        key=profile.key,
        label=profile.label,
        model_name=profile.model_name,
        revision=profile.revision,
        model_version=profile.model_version,
        normalization=profile.normalization,
        query_prefix=profile.query_prefix,
        document_prefix=profile.document_prefix,
        pooling=profile.pooling,
        qualification=profile.qualification,
        is_baseline=profile.key == BASELINE_PROFILE_KEY,
        coverage=ProfileCoverage(**coverage),
        index_run=run,
    )


def profiles_state(request: Request) -> ProfilesResponse:
    from app.backend.api.routers.modernization import resolve_retrieval

    with request.app.state.engine.connect() as conn:
        preference = read_preference(conn)
        blocked = None
        try:
            resolution = resolve_retrieval(request.app, conn)
            active, reason, said = resolution.profile.key, resolution.fallback_reason, explanation(resolution)
        except IncompleteEmbeddingIndexError as exc:
            active, reason, said, blocked = preference.key or BASELINE_PROFILE_KEY, None, str(exc), str(exc)
        profiles = []
        for p in PROFILES.values():
            coverage = profile_coverage(conn, p)
            profiles.append(_profile_out(p, coverage, index_run_out(conn, p, coverage)))
    return ProfilesResponse(
        active=active,
        preference=preference.key if preference.explicit else AUTOMATIC,
        preference_source=preference.source,
        legacy_preference=preference.legacy,
        fallback_reason=reason,
        explanation=said,
        ask_blocked=blocked,
        verification_model=PROFILES[BASELINE_PROFILE_KEY].label,
        profiles=profiles,
        index_job_id=active_index_job_id(request.app),
    )


def _known(key: str) -> EmbeddingProfile:
    try:
        return get_profile(key)
    except UnknownEmbeddingProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/embedding-profiles", response_model=ProfilesResponse)
def list_profiles(request: Request) -> ProfilesResponse:
    return profiles_state(request)


@router.put("/embedding-profiles/active", response_model=ProfilesResponse)
def select_profile(payload: SelectProfileRequest, request: Request) -> ProfilesResponse:
    """An explicit user choice (it then wins over automatic selection), or ``automatic`` to clear it."""
    engine = request.app.state.engine
    if payload.key == AUTOMATIC:
        run_write(engine, lambda conn: set_user_preference(conn, None))
        return profiles_state(request)
    profile = _known(payload.key)
    with engine.connect() as conn:
        coverage = profile_coverage(conn, profile)
    if not profile.lazy_indexing and not coverage["complete"]:
        raise HTTPException(
            status_code=409,
            detail=f"The {profile.label} index covers {coverage['indexed_chunks']} of {coverage['eligible_chunks']} "
            "passages. Build it before selecting this profile.",
        )
    run_write(engine, lambda conn: set_user_preference(conn, profile.key))
    return profiles_state(request)


# ---- verification NLI profile (synthesis citation verification only) ------------------------------------------


class NliProfileOut(BaseModel):
    key: str
    label: str
    model_name: str
    revision: str
    qualification: str
    is_baseline: bool


class NliProfilesResponse(BaseModel):
    active: str
    thresholds_calibrated_on: str
    profiles: list[NliProfileOut]


def _nli_state(request: Request) -> NliProfilesResponse:
    with request.app.state.engine.connect() as conn:
        active = active_nli_profile(conn)
    return NliProfilesResponse(
        active=active.key,
        thresholds_calibrated_on=NLI_PROFILES[BASELINE_NLI_PROFILE_KEY].label,
        profiles=[
            NliProfileOut(
                key=p.key,
                label=p.label,
                model_name=p.model_name,
                revision=p.revision,
                qualification=p.qualification,
                is_baseline=p.key == BASELINE_NLI_PROFILE_KEY,
            )
            for p in NLI_PROFILES.values()
        ],
    )


@router.get("/verification-nli-profiles", response_model=NliProfilesResponse)
def list_nli_profiles(request: Request) -> NliProfilesResponse:
    return _nli_state(request)


@router.put("/verification-nli-profiles/active", response_model=NliProfilesResponse)
def select_nli_profile(payload: SelectProfileRequest, request: Request) -> NliProfilesResponse:
    """Selecting a non-baseline profile loads its pinned checkpoint and verifies its contract first, so a mismatched
    checkpoint is refused here rather than mid-synthesis."""
    try:
        profile = get_nli_profile(payload.key)
    except UnknownNliProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    app = request.app
    if profile.enforce_contract and getattr(app.state, "support_scorer", None) is None:
        try:
            runtime = app.state.model_runtime_registry.get_nli_runtime(
                model_name=profile.model_name, revision=profile.revision
            )
            runtime.run(lambda model: verify_nli_checkpoint(model, profile))
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"{profile.label} could not be verified: {exc}") from None
    run_write(app.state.engine, lambda conn: set_active_nli_profile(conn, profile.key))
    return _nli_state(request)
