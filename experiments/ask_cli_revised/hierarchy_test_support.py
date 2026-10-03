"""Shared test support for the hierarchy adapter tests. Not a test module.

Every mutation test works on a temporary COPY of the four preserved closure artifacts: the originals under `.local/` are
only ever read, never opened for writing.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

ARTIFACTS_PRESENT = all(Path(p).is_file() for p in hc.DEFAULT_PATHS.values())
needs_artifacts = unittest.skipUnless(
    ARTIFACTS_PRESENT, "the preserved q_aib closure artifacts (.local/) are not present"
)


class ArtifactCopy:
    """A temp copy of the four closure artifacts that a test may mutate."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.paths = {}
        for name, src in hc.DEFAULT_PATHS.items():
            dst = self.dir / Path(src).name
            shutil.copyfile(src, dst)
            self.paths[name] = dst

    def close(self):
        self._tmp.cleanup()

    def read(self, name):
        return json.loads(self.paths[name].read_text(encoding="utf-8"))

    def edit(self, name, fn):
        data = self.read(name)
        fn(data)
        self.paths[name].write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    def edit_node(self, child_id, fn):
        def apply(data):
            fn(next(n for n in data["nodes"] if n["child_id"] == child_id))

        self.edit("assembled", apply)

    def load(self, **kwargs):
        kwargs.setdefault("pins", None)
        return hc.load_contract(BENCHMARK_QUESTION, **self.paths, **kwargs)


def rejection(test, fn, *needles):
    """Call ``fn``, require ``HierarchyRejected``, and require every needle to appear in some problem (case-insensitive)."""
    with test.assertRaises(hc.HierarchyRejected) as ctx:
        fn()
    joined = " | ".join(ctx.exception.problems).lower()
    for needle in needles:
        test.assertIn(needle.lower(), joined, f"no problem mentions {needle!r}: {ctx.exception.problems}")
    return ctx.exception


# ---- E2E harness over a hierarchical contract (faked retrieval and clients; no model, no network, no database) ---------
import re  # noqa: E402
from unittest.mock import patch  # noqa: E402

from experiments.ask_cli_revised import e2e  # noqa: E402
from experiments.ask_cli_revised.test_e2e_run import Harness, ScriptedClient, rec  # noqa: E402,F401

CHILD_IDS = ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]


class HierHarness(Harness):
    """The existing orchestration harness, driven by a hierarchical contract instead of a flat one."""

    def __init__(self, profile, contract, **kwargs):
        super().__init__(profile, **kwargs)
        self.contract = contract

    def run(
        self,
        smoke_limits=None,
        seed_pass=None,
        entail=None,
        *,
        sufficiency_contract=None,
        sufficiency_parent_of=None,
        sufficiency_recovery_gate_enabled=False,
        sufficiency_model_assist_enabled=False,
        parent_synthesis_enabled=False,
    ):
        # entail=None matches execute()'s own default -- every existing caller that never passed it
        # (no S role bound in its profile) is unaffected; a caller binding an Overview-enabled profile
        # (e.g. CHILD_OVERVIEW_PROFILES["T5C"]) now has a way to supply one, the same as OverviewHarness
        # already does for the flat case. sufficiency_contract/sufficiency_parent_of/
        # sufficiency_recovery_gate_enabled (Phase 20a) default exactly like execute()'s own
        # parameters -- every existing caller that never passes them observes byte-identical
        # behavior; this is the seam test_hierarchy_e2e.py's sufficiency-integration tests use to
        # exercise execute()'s already-built sufficiency block without going through run_topology().
        bound = e2e.bind(
            self.profile,
            rt=self.rt,
            clients=self.clients,
            trace=self.trace,
            managed_chat=lambda config: self.clients["shared"],
        )
        with (
            patch.object(e2e, "_initial_pass", self._initial_pass),
            patch.object(e2e, "_recover_round", self._recover_round),
        ):
            return e2e.execute(
                rt=self.rt,
                profile=self.profile,
                contract=self.contract,
                trace=self.trace,
                guard=self.guard,
                bound=bound,
                smoke_limits=smoke_limits,
                seed_pass=seed_pass,
                entail=entail,
                sufficiency_contract=sufficiency_contract,
                sufficiency_parent_of=sufficiency_parent_of,
                sufficiency_recovery_gate_enabled=sufficiency_recovery_gate_enabled,
                sufficiency_model_assist_enabled=sufficiency_model_assist_enabled,
                parent_synthesis_enabled=parent_synthesis_enabled,
            )


def claim_in(prompt: str) -> str:
    """The candidate claim inside an R prompt (frozen Task-A template)."""
    return prompt.split("Candidate claim:\n", 1)[1].split("\n\nRequested items:", 1)[0]


def r_by_claim(mapping: dict):
    """A scripted R: claim text -> the child ids it directly answers (anything else answers nothing)."""
    return lambda prompt, schema: {
        "rationale": "scripted",
        "responsive_obligation_ids": mapping.get(claim_in(prompt), []),
    }


def c_supports_children(support: dict):
    """A scripted model C over child ids: ``{child_id: proposition_id}``; every other child is unresolved."""

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


def request_block(prompt: str) -> str:
    """The item lines a supervisory prompt shows (the part derived from the request), without the ``- cN:`` id prefixes."""
    text = prompt.split("Requested items:\n", 1)[1].split("\n\n", 1)[0]
    return "\n".join(re.sub(r"^- c\d+: ", "", line) for line in text.splitlines())
