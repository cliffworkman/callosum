"""Shared fixtures for the overview tests. Not a test module.

Every passage here is INVENTED. Each reproduces the *structure* of a failure found in the real q_aib run (a claim that adds a
direction its passage lacks, "toward" rewritten as "in", a hedged intervention idea, a null result, a passage cut off mid-
sentence, a description of what a study set out to do, a statement about what other studies did not examine) so the tests pin
the behavior without copying any library text into the repository.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from experiments.ask_cli_revised import e2e, stages
from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.test_e2e_run import Harness, ScriptedClient, add, c_supports, p_all  # noqa: F401

QUESTION = (
    "How does aversion to visible scarring show up in behavior? Which interventions reduce it? "
    "Is there cross-cultural evidence?"
)
CONTRACT = build_request_contract(QUESTION)
SUBQUESTIONS = request_subquestions(CONTRACT)
S1, S2, S3 = "s1-o1", "s2-o1", "s3-o1"  # behavior / interventions / cross-cultural

# (paper, chunk, span, text)
GIVING = (
    11,
    101,
    "e1",
    "The insular response to pictured scarring correlated with lower generosity toward the people pictured and with a stronger belief in a just world.",
)
PATTERN = (11, 102, "e1", "The authors described a behavioral pattern of avoidance linked to visible scarring.")
HEDGE = (12, 201, "e1", "Training in perspective taking might reduce avoidance of people with visible scarring.")
NULL = (
    11,
    103,
    "e1",
    "Participants reported explicit dislike of people with scarring, but implicit dislike was small and not significant.",
)
FRAGMENT = (13, 301, "e1", "results suggest that the aversion is culturally shared, providing evidence against a")
STUDY = (14, 401, "e1", "This study examined relations between dislike and gaze duration toward pictured people.")
ABSENT = (13, 302, "e1", "These earlier studies did not examine the aversion across cultures.")
OTHER_PAPER = (15, 501, "e1", "Explicit dislike of people with scarring was also reported in a second sample.")
SHARED = (16, 601, "e1", "Results suggest that the aversion is culturally shared across the three samples.")
SHAPED = (17, 701, "e1", "Results suggest that the aversion is culturally shaped across the three samples.")


def record(claim: str, passage: tuple, attached=(), *, sid: str = "s1") -> dict:
    paper, chunk, span, text = passage
    return {
        "subquestion_id": sid,
        "proposition_text": claim,
        "quote": text,
        "paper_id": paper,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": span,
        "obligation_ids": list(attached),
        "mapping_state": "mapped",
        "verification": {"status": "verified", "page_start": 3},
        "provenance": {"origin": "initial"},
    }


def sealed_ledger(specs: list[tuple]) -> dict:
    """A real sealed ledger (through ``stages.seal``) from ``(claim, passage, attached_field_ids)`` specs."""
    records = [record(claim, passage, attached) for claim, passage, attached in specs]
    packets = [
        {
            "paper_id": r["paper_id"],
            "candidate_spans": [
                {"chunk_id": r["evidence_anchor_chunk_id"], "span_id": r["evidence_span_id"], "text": r["quote"]}
            ],
        }
        for r in records
    ]
    coverage = stages.det_coverage(SUBQUESTIONS, records, authority={"kind": "det", "role": "R"})
    return stages.seal(CONTRACT, SUBQUESTIONS, records, packets, coverage)


def uid(sealed: dict, passage: tuple) -> str:
    units, _ = oe.build_units(sealed)
    return next(u["unit_id"] for u in units if u["passage"] == passage[3])


def stmt(text: str, unit_ids, bears_on=()) -> dict:
    return {"text": text, "unit_ids": list(unit_ids), "bears_on": list(bears_on)}


# ---- scripted model + scorer -------------------------------------------------------------------------------------------
class OverviewClient(ScriptedClient):
    """The existing scripted client, plus an S handler routed by the overview schema (which the base class would call P)."""

    def __init__(self, *, s=None, thinking: str = "", **kwargs):
        super().__init__(**kwargs)
        self.s, self.thinking = s, thinking

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive=None, wall_timeout=None):
        if "overview" not in schema["properties"]:
            return super().chat(
                model,
                prompt,
                schema=schema,
                options=options,
                think=think,
                keep_alive=keep_alive,
                wall_timeout=wall_timeout,
            )
        self.calls.append(
            {"kind": "S", "model": model, "prompt": prompt, "think": think, "options": dict(options), "schema": schema}
        )
        answer = self.s(prompt, schema) if callable(self.s) else self.s
        base = {
            "status": "ok",
            "error": None,
            "thinking": self.thinking,
            "timings": {"prompt_eval_count": 1500, "eval_count": 2500},
            "wall_seconds": 1.0,
        }
        if answer is None:
            return {**base, "content": "", "done_reason": "length"}
        return {**base, "content": answer if isinstance(answer, str) else json.dumps(answer), "done_reason": "stop"}


def make_supervisor(client, options: dict | None = None) -> stages.Supervisor:
    return stages.Supervisor(
        role="S",
        binding=topo.OVERVIEW_PROFILES["T5O"].S,
        client=client,
        base_options=options or topo.OVERVIEW_S_OPTIONS,
    )


class Entail:
    """A fake local NLI scorer that counts its calls (the real one takes ``(passage, sentence)`` pairs)."""

    def __init__(self, score=(0.9, 0.05)):
        self.score, self.calls = score, []

    def __call__(self, pairs):
        self.calls.append(list(pairs))
        return [self.score] * len(pairs)


def entail_raises(pairs):
    raise RuntimeError("nli runtime unavailable")


def build(sealed: dict, client, entail=None, options=None):
    """``(record, reasoning)`` from the real ``build_overview`` with a scripted S client."""
    return ov.build_overview(
        sealed, "sealed-hash", supervisor=make_supervisor(client, options), entail=entail or Entail()
    )


class OverviewHarness(Harness):
    """The existing orchestration harness with S bound; ``entail`` is what ``run_topology`` wires from the runtime."""

    def run(self, entail=None, **kwargs):
        bound = e2e.bind(
            self.profile,
            rt=self.rt,
            clients=self.clients,
            trace=self.trace,
            managed_chat=lambda config: self.clients["shared"],
        )
        from unittest.mock import patch

        with (
            patch.object(e2e, "_initial_pass", self._initial_pass),
            patch.object(e2e, "_recover_round", self._recover_round),
        ):
            return e2e.execute(
                rt=self.rt,
                profile=self.profile,
                contract=CONTRACT,
                trace=self.trace,
                guard=self.guard,
                bound=bound,
                entail=entail,
                **kwargs,
            )


def c_maps(support: dict):
    """A scripted model C over this contract's items: ``{field_id: proposition_id}``; every other item stays unresolved."""

    def answer(prompt, schema):
        ids = schema["properties"]["coverage"]["required"]
        return {
            "rationale": "scripted",
            "coverage": {
                ob: {
                    "status": "responsive_support" if support.get(ob) else "unresolved",
                    "supporting_proposition_ids": [support[ob]] if support.get(ob) else [],
                }
                for ob in ids
            },
        }

    return answer


def p_preserve(prompt, schema):
    ids = schema["properties"]["plan"]["required"]
    return {"rationale": "scripted", "plan": {ob: f"{ob}:PRESERVE_UNRESOLVED" for ob in ids}}


def harness_records() -> list[dict]:
    return [record("c-give", GIVING), record("c-pattern", PATTERN), record("c-hedge", HEDGE), record("c-null", NULL)]


_ = SimpleNamespace, add  # re-exported for tests
