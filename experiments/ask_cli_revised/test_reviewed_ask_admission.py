"""Phase 34 B2 pilot: the experimental admission policy is opt-in, scoped, and changes only two thresholds.

The decision tests run the shared verifier's own ``_status`` / ``verify_many`` unmodified. The downstream test
runs the public reviewed route offline (the ``test_reviewed_fresh`` harness shape) to pin one property the pilot
relies on: scientific mapping, witnessing, Layer C and rendering read the sealed physical quote, so a claim
sentence that overstates its quote cannot put its own wording into the selected answer.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.backend.summarization.generators import CandidateCitation, SourceChunk
from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig
from experiments.ask_cli_revised import e2e, reviewed_ask, reviewed_ask_inputs
from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import runtime as runtime_mod
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import test_e2e_run as harness
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.reviewed_ask_admission import B2_PILOT_VERIFICATION_CONFIG as B2

DEFAULT = VerificationConfig()
REPO = Path(__file__).resolve().parents[2]


def test_b2_changes_only_the_similarity_and_support_thresholds():
    assert (B2.retrieval_threshold, B2.support_threshold) == (0.0, 0.90)
    assert B2.quote_threshold == DEFAULT.quote_threshold == 1.0
    assert B2.contradiction_threshold == DEFAULT.contradiction_threshold == 0.55
    assert (DEFAULT.retrieval_threshold, DEFAULT.support_threshold) == (0.7, 0.55)


def _status(config, *, retrieval, quote, support, contradiction):
    verifier = LocalCitationVerifier(
        model=MagicMock(), vector_store=MagicMock(), config=config, support_scorer=object()
    )
    return verifier._status(
        retrieval_confidence=retrieval,
        quote_confidence=quote,
        support_confidence=support,
        contradiction_confidence=contradiction,
    )


@pytest.mark.parametrize(
    "scores,default_status,b2_status",
    [
        # Live Q1 5591: exact quote, high NLI, similarity under 0.70 -- the gate-only loss B2 targets.
        ({"retrieval": 0.657, "quote": 1.0, "support": 0.994, "contradiction": 0.001}, "weak", "verified"),
        # Support under 0.90 is no longer admitted, however similar the chunk.
        ({"retrieval": 0.95, "quote": 1.0, "support": 0.89, "contradiction": 0.01}, "verified", "weak"),
        ({"retrieval": 0.10, "quote": 1.0, "support": 0.54, "contradiction": 0.01}, "unverified", "weak"),
        # The quote requirement is untouched.
        ({"retrieval": 0.95, "quote": 0.0, "support": 0.99, "contradiction": 0.0}, "weak", "weak"),
        # The contradiction veto is untouched and still checked first.
        ({"retrieval": 0.95, "quote": 1.0, "support": 0.30, "contradiction": 0.60}, "contradicted", "contradicted"),
        ({"retrieval": 0.20, "quote": 1.0, "support": 0.05, "contradiction": 0.93}, "contradicted", "contradicted"),
    ],
)
def test_status_under_default_and_b2(scores, default_status, b2_status):
    assert _status(DEFAULT, **scores) == default_status
    assert _status(B2, **scores) == b2_status


def _verify(config, *, quote, chunk_text, support=(0.97, 0.01)):
    """The real ``verify_many``; only the DB-touching internals are stubbed. Similarity is forced low."""
    model = SimpleNamespace(encode_texts=lambda texts: [[0.0] * 8 for _ in texts], name="fake-model", version="1")
    searches = []

    def search(conn, *, vector, top_k, candidate_embedding_ids):
        searches.append(top_k)
        return [SimpleNamespace(embedding_id=1, distance=1.2)]

    scorer = SimpleNamespace(support_and_contradiction_many=lambda pairs: [support for _ in pairs])
    verifier = LocalCitationVerifier(
        model=model, vector_store=SimpleNamespace(search=search), config=config, support_scorer=scorer
    )
    verifier._embedding_lookup = lambda conn, *, candidate_chunk_ids: {1: candidate_chunk_ids[0]}
    chunk = SourceChunk(
        chunk_id=5, paper_id=1, attachment_id=1, text=chunk_text, page_start=1, page_end=1, chunk_version="v", bbox_json=None
    )  # fmt: skip
    with patch(
        "app.backend.summarization.verification.locate_quote_for_attachment", return_value=SimpleNamespace(found=False)
    ):
        result = verifier.verify_many(
            None, items=[("A claim.", CandidateCitation(chunk_id=5, quote=quote))], source_chunks=[chunk]
        )[0]
    return result, searches


def test_real_verifier_admits_low_similarity_high_support_only_under_b2():
    kwargs = {"quote": "the sample held four cases", "chunk_text": "Here the sample held four cases in total."}
    default_result, _ = _verify(DEFAULT, **kwargs)
    b2_result, searches = _verify(B2, **kwargs)
    assert default_result.retrieval_confidence == b2_result.retrieval_confidence < 0.7
    assert (default_result.status, b2_result.status) == ("weak", "verified")
    # The gate is disabled logically; the similarity is still computed and recorded.
    assert searches == [1]


def test_real_verifier_still_rejects_a_quote_absent_from_its_chunk_and_a_contradiction_under_b2():
    absent, _ = _verify(B2, quote="text that is not in the chunk", chunk_text="Here the sample held four cases.")
    assert absent.quote_confidence == 0.0 and absent.status != "verified"
    vetoed, _ = _verify(B2, quote="four cases", chunk_text="Here the sample held four cases.", support=(0.2, 0.9))
    assert vetoed.status == "contradicted"


def _build(**kwargs):
    with (
        patch.object(runtime_mod, "make_engine", return_value=MagicMock()),
        patch.object(runtime_mod, "ModelRuntimeRegistry", return_value=MagicMock()),
        patch.object(runtime_mod, "ProviderClientRuntime", return_value=MagicMock()),
        patch.object(runtime_mod, "SQLiteVecVectorStore", return_value=MagicMock()),
        patch.object(runtime_mod, "default_support_scorer", return_value=object()),
    ):
        return runtime_mod.build_runtime("copy.sqlite", want_qwen=False, **kwargs)


def test_runtime_keeps_shared_defaults_unless_the_policy_is_passed_explicitly():
    assert _build().verifier.config == DEFAULT
    assert _build(verification_config=B2).verifier.config == B2


def test_no_other_runtime_surface_selects_the_pilot_policy():
    surfaces = [
        "experiments/ask_cli_revised/e2e.py",
        "experiments/ask_cli_revised/reviewed_ask.py",
        "experiments/ask_cli_revised/__main__.py",
        "experiments/ask_cli_revised/propositions.py",
        "experiments/ask_cli_revised/stages.py",
        "experiments/ask_cli/runtime.py",
        "app/backend/summarization/verification.py",
        "app/backend/summarization/pipeline.py",
        "app/backend/summarization/faceted_pipeline.py",
        "app/backend/summarization/reverify.py",
        "app/backend/api/app.py",
    ]
    for relative in surfaces:
        source = (REPO / relative).read_text(encoding="utf-8")
        assert "reviewed_ask_admission" not in source and "B2_PILOT" not in source, relative
        assert "verification_config=" not in source, relative


QUOTE = "We found that the Amber Scale measures just-world beliefs and was positively associated with the amygdala response."
FABRICATED = "Stronger just-world beliefs on the Amber Scale cause an increased amygdala response."
FAITHFUL = "Amber Scale just-world beliefs were positively associated with the amygdala response."


def _reviewed_run(monkeypatch, question, claim):
    request = build_request_contract(question)
    cid = request_subquestions(request)[0]["obligations"][0]["field_id"]
    specs = {
        "outcome": se.new_role_spec("outcome", "reported direction", "direction_or_sign_pattern"),
        "measure": se.new_role_spec("measure", "named measure", "named_instrument_lexicon"),
    }
    req = se.new_requirement(
        "result-obligation", "relational", specs, se.new_role_completion(required_roles=list(specs)), "exists"
    )
    science = {cid: se.frozen_view(se.new_contract(cid, [req]))}
    reporting = rc.single_question(request, science, requested_construct_terms=["just-world beliefs"])
    review = {
        "schema": "reviewed-ask-inputs-v1",
        "status": "reviewed",
        "reviewed_by": "OFFLINE SYNTHETIC SAFETY CONTROL; not a production approval",
        "reviewed_at": "2026-10-12",
        "inputs": reviewed_ask_inputs.input_refs(request, science, reporting, {}),
    }
    bound_inputs = reviewed_ask_inputs.bind_reviewed_inputs(request, science, reporting, {}, review)
    row = harness.rec("s1", claim, chunk=11)
    row["quote"] = QUOTE
    client = harness.ScriptedClient(r=harness.r_maps(cid))
    h = harness.Harness(topo.WAVE1["T0"], initial=[row], recovery=[], clients={"shared": client})
    bound = e2e.bind(h.profile, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda config: client)
    try:
        with monkeypatch.context() as m:
            m.setattr(e2e, "_initial_pass", h._initial_pass)
            m.setattr(e2e, "_recover_round", h._recover_round)
            return reviewed_ask.run_reviewed_request(
                bound_inputs, rt=h.rt, profile=h.profile, trace=h.trace, guard=h.guard, bound=bound
            )
    finally:
        h.close()


@pytest.mark.parametrize(
    "question",
    [
        "What was found about the relationship between just-world beliefs and the amygdala response?",
        "Do stronger just-world beliefs cause an increased amygdala response?",
    ],
)
def test_an_admitted_causal_overstatement_cannot_put_its_wording_into_the_selected_answer(monkeypatch, question):
    """Synthetic analogue of bakeoff control E009: a correlational quote paired with a causal claim sentence."""
    fabricated = _reviewed_run(monkeypatch, question, FABRICATED)
    faithful = _reviewed_run(monkeypatch, question, FAITHFUL)
    answer = fabricated["selected_answer"]
    assert answer == faithful["selected_answer"]
    assert QUOTE in answer and FABRICATED not in answer
    assert "cause" not in answer.replace(question, "")
    output = fabricated["layerc_v2"]
    # The quote's own association is witnessed; that is the source's statement, not the fabricated one.
    assert all(u["relation_witnessed"] and u["witness_ids"] for u in output["relation_units"].values())
    assert all(receipt["citation"] for receipt in output["claim_evidence"].values())
