"""Help endpoints.

- ``GET /help/corpus`` serves the in-app help content: **app-owned, public, static** — no DB, no request
  input, **no egress** (the docs must render even when the AI assistant is off or the machine is offline).
- ``POST /help/ask`` is the AI help assistant: it answers a question from the public help corpus and
  returns references to the sections it used. It is gated by its **own** consent toggle
  (``CALLOSUM_HELP_ASSISTANT_ENABLED``), **independent** of the library data-egress gate — it never sends
  library text. Resolved through the inc-58 seam-gate pattern (the gate covers an injected assistant AND
  the default), mirroring ``_summary_generator``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field

from app.backend.api.dependencies import resolve_llm_config
from app.backend.help.assistant import HelpAssistant, HelpTurn
from app.backend.help.corpus import load_help_corpus
from app.backend.llm.egress import EgressGatedHelpAssistant, HelpAssistantDisabledError
from app.backend.llm.managed_local import ManagedLocalTargetError
from integrations.gemini import GeminiHelpAssistant

router = APIRouter()

MAX_MESSAGE_LEN = 4000
MAX_HISTORY_TURNS = 20


class HelpSectionResponse(BaseModel):
    id: str
    title: str
    html: str


class HelpCorpusResponse(BaseModel):
    sections: list[HelpSectionResponse]


class HelpTurnModel(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN)


class HelpAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN)
    history: list[HelpTurnModel] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)


class HelpReferenceModel(BaseModel):
    section_id: str
    reason: str = ""


class HelpAskResponse(BaseModel):
    answer: str
    references: list[HelpReferenceModel]


@router.get("/help/corpus", response_model=HelpCorpusResponse)
def help_corpus() -> HelpCorpusResponse:
    return HelpCorpusResponse(
        sections=[HelpSectionResponse(id=s.id, title=s.title, html=s.html) for s in load_help_corpus()],
    )


@router.post("/help/ask", response_model=HelpAskResponse)
def help_ask(payload: HelpAskRequest, request: Request) -> HelpAskResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message must not be empty")
    history = [HelpTurn(role=turn.role, content=turn.content) for turn in payload.history]
    try:
        result = _help_assistant(request.app).answer(message=message, history=history)
    except HelpAssistantDisabledError:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI help assistant is off. Enable it in Settings → AI features. "
            "(The help docs work without it.)",
        ) from None
    except ManagedLocalTargetError as exc:
        raise HTTPException(
            status_code=422, detail=f"Local AI is not ready ({exc.code}). Check Settings → AI features."
        ) from None
    except Exception as exc:  # any Gemini/network/parse failure → surface, never 500
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"Help assistant failed: {type(exc).__name__}: {exc}",
        ) from None
    # Drop any section_id the model invented — only real corpus anchors can be deep-linked by the UI.
    valid_ids = {s.id for s in load_help_corpus()}
    references = [
        HelpReferenceModel(section_id=ref.section_id, reason=ref.reason)
        for ref in result.references
        if ref.section_id in valid_ids
    ]
    return HelpAskResponse(answer=result.answer, references=references)


def _help_assistant(app: FastAPI) -> HelpAssistant:
    config = resolve_llm_config(app)
    inner = app.state.help_assistant
    if inner is None:
        inner = GeminiHelpAssistant(config=config)
    # Authoritative gate at the seam — covers the injected assistant AND the default. Keyed on the help
    # assistant's OWN toggle, independent of the library data-egress gate.
    return EgressGatedHelpAssistant(
        inner=inner,
        help_assistant_enabled=config.help_assistant_enabled,
    )
