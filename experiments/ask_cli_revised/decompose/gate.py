"""Mechanical speed bump for the standing experiment gate (see EXPERIMENT_GATE.md).

It stops the protected requests (q_lld, q_builtenv) from being decomposed by accident. It is not a security
boundary; the rule itself is the human gate: a brief, then Cliff's explicit confirmation of that specific experiment.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROTECTED_KEYS = ("lld", "builtenv")


class GateRefused(RuntimeError):
    pass


def protected_hashes() -> dict[str, str]:
    from experiments.ask_cli_revised.e2e_contracts import E2E_QUESTIONS

    return {hashlib.sha256(E2E_QUESTIONS[k].encode("utf-8")).hexdigest(): k for k in PROTECTED_KEYS}


def check(question: str, authorization_path: str | None = None) -> None:
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    key = protected_hashes().get(digest)
    if key is None:
        return
    if not authorization_path:
        raise GateRefused(
            f"q_{key} is protected by the experiment gate; no authorization file was given (see EXPERIMENT_GATE.md)"
        )
    try:
        auth = json.loads(Path(authorization_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateRefused(f"authorization file unreadable: {exc}") from exc
    if not (
        isinstance(auth, dict)
        and auth.get("brief_confirmed") is True
        and auth.get("experiment_id")
        and auth.get("authorized_by")
        and digest in (auth.get("question_sha256s") or [])
    ):
        raise GateRefused(
            f"authorization file does not name q_{key} ({digest[:12]}) with brief_confirmed=true, an experiment_id and authorized_by"
        )
