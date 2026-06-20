"""Provider-neutral help-assistant interface.

The help assistant answers a user's natural-language question about **using** callosum, drawing ONLY on
the public help corpus (never library text). It returns a concise answer plus structured references to the
help sections it used, so the UI can deep-link + highlight them — mirroring the synthesis tool's
"probe → matches → route to source", over the app's own help content.

Provider-portable: the concrete Gemini implementation lives in ``integrations/gemini/help_assistant.py``;
the API resolves it through the same injected-override-with-default seam as the summary generator, gated by
the help assistant's **own** consent toggle (``CALLOSUM_HELP_ASSISTANT_ENABLED``) — independent of the
library data-egress gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class HelpTurn:
    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class HelpReference:
    section_id: str
    reason: str = ""


@dataclass(frozen=True)
class HelpAnswer:
    answer: str
    references: list[HelpReference] = field(default_factory=list)


class HelpAssistant(Protocol):
    def answer(self, *, message: str, history: list[HelpTurn]) -> HelpAnswer:
        """Answer a help question from the public help corpus. May raise HelpAssistantDisabledError."""
