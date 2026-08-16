"""Strict curation contract for the saved public-demo synthesis Overview."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.backend.api.routers.summaries import OverviewItemResponse, SummarizeJobResponse


def verified_claims_sha256(summary: SummarizeJobResponse) -> str:
    """Fingerprint the exact ordered verified claims narrated by an Overview."""
    claims = [
        {"ordinal": sentence.ordinal, "text": sentence.text}
        for sentence in summary.sentences or []
        if not sentence.flagged
    ]
    payload = json.dumps(claims, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class DemoAskOverviewState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_id: int
    overview: list[OverviewItemResponse] = Field(min_length=1)
    verified_claim_count: int = Field(gt=0)
    verified_claims_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_id: str
    model_id: str
    prompt_version: str

    @model_validator(mode="after")
    def validate_trace(self) -> "DemoAskOverviewState":
        if any(not item.claim_ordinals for item in self.overview):
            raise ValueError("every saved Overview sentence must trace to a verified claim")
        return self
