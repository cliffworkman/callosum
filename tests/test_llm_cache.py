from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from app.backend.llm.cache import (
    CachedSummaryGenerator,
    GenerationCacheIdentity,
    canonical_hash,
    repair_summary_cache,
    summary_generation_input_hash,
    synthesis_generation_cache_signature,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks, llm_cache
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, SourceChunk
from integrations.gemini.generator import GeminiSummaryGenerator, LLMConfig
from tests.api_helpers import _seed_summarization_library, _summarization_app

# A generation cache hit must cost zero LLM calls AND return an identical (re-verified) result. This
# generator counts its calls and lets a test set a distinct cache_signature, so we can prove hit/miss.


class CountingSummaryGenerator:
    def __init__(self, sentences, *, name="counting-summary-generator", signature=None):
        self.sentences = sentences
        self.name = name
        self._signature = signature
        self.calls = 0

    @property
    def cache_signature(self) -> str:
        return self._signature if self._signature is not None else self.name

    def generate(self, *, source_chunks, scope_ref, conn=None):
        self.calls += 1
        return list(self.sentences)


def _facial(seeded, *, quote="Facial anomalies influence social judgments."):
    return [
        CandidateSummarySentence(
            text="Facial anomalies influence social judgments.",
            citations=[CandidateCitation(chunk_id=seeded["facial_chunk_id"], quote=quote)],
        )
    ]


def _summarize(client, *, query="facial social judgment", top_k=2):
    started = client.post("/summarize", json={"scope_type": "query", "query": query, "top_k": top_k})
    assert started.status_code == 202
    return client.get(f"/summarize/{started.json()['job_id']}").json()


def _shape(result):
    """The meaningful output (text + verification outcome), ignoring per-row ids that differ each run."""
    return [
        (
            s["text"],
            s["flagged"],
            [
                (c["quote"], c["chunk_id"], c["status"], c["quote_confidence"], c["coordinate_precision"])
                for c in s["citations"]
            ],
        )
        for s in result["sentences"]
    ]


def _gen_shape(result):
    """Only the cached GENERATION output (sentence text + cited quotes), not the re-run verification verdict.
    The cache guarantees identical candidates; verification re-runs against the current environment."""
    return [(s["text"], [(c["quote"], c["chunk_id"]) for c in s["citations"]]) for s in result["sentences"]]


def _config_signature(config: LLMConfig, *, prompt_version: str = "summary-v5") -> str:
    return synthesis_generation_cache_signature(
        generator_name="gemini-summary-generator",
        prompt_version=prompt_version,
        config=config,
    )


def _source_chunk(**overrides) -> SourceChunk:
    values = {
        "chunk_id": 11,
        "paper_id": 7,
        "attachment_id": 3,
        "text": "Evidence text.",
        "page_start": 4,
        "page_end": 5,
        "chunk_version": "chunk-v1",
    }
    values.update(overrides)
    return SourceChunk(**values)


def test_cache_hit_returns_identical_and_generates_once(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    first = _summarize(client)
    second = _summarize(client)

    assert first["status"] == "done" and second["status"] == "done"
    assert gen.calls == 1  # the second call was a cache hit (zero tokens)
    assert first["summary_status"] == second["summary_status"]
    assert _shape(first) == _shape(second)  # identical result


def test_identical_provider_configuration_remains_cache_eligible(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    config = LLMConfig(
        provider="custom-a",
        wire_format="chat_completions",
        model="shared-model",
        base_url="https://provider.example/api/",
        api_key="sk-same-account",
    )
    signature = _config_signature(config)
    first = CountingSummaryGenerator(_facial(seeded), signature=signature)
    _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=first)), seeded["facial_paper_id"])
    second = CountingSummaryGenerator(_facial(seeded), signature=_config_signature(config))
    _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=second)), seeded["facial_paper_id"])

    assert first.calls == 1
    assert second.calls == 0


def test_provider_change_with_same_model_endpoint_and_wire_forces_cache_miss(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    common = {
        "wire_format": "chat_completions",
        "model": "shared-model",
        "base_url": "https://provider.example/api",
        "api_key": "sk-same-account",
    }
    first = CountingSummaryGenerator(_facial(seeded), signature=_config_signature(LLMConfig(provider="a", **common)))
    _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=first)), seeded["facial_paper_id"])
    second = CountingSummaryGenerator(_facial(seeded), signature=_config_signature(LLMConfig(provider="b", **common)))
    _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=second)), seeded["facial_paper_id"])

    assert first.calls == 1
    assert second.calls == 1


def test_generation_configuration_dimensions_define_cache_identity(monkeypatch) -> None:
    base = LLMConfig(
        provider="custom-a",
        wire_format="chat_completions",
        model="shared-model",
        base_url="https://provider.example/api",
        api_key="sk-account-a",
    )
    signature = _config_signature(base)

    assert GeminiSummaryGenerator(config=base).cache_signature == signature
    assert _config_signature(replace(base, base_url="https://other.example/api")) != signature
    assert _config_signature(replace(base, wire_format="responses")) != signature
    assert _config_signature(replace(base, model="other-model")) != signature
    assert _config_signature(base, prompt_version="summary-v6") != signature
    assert _config_signature(replace(base, api_key="sk-account-b")) != signature

    # Trailing slash and an explicitly spelled builtin default resolve to the same actual request endpoint.
    assert _config_signature(replace(base, base_url="https://provider.example/api/")) == signature
    openai_default = LLMConfig(
        provider="openai",
        wire_format="chat_completions",
        model="shared-model",
        api_key="sk-account-a",
    )
    assert _config_signature(openai_default) == _config_signature(
        replace(openai_default, base_url="https://api.openai.com/")
    )

    # Gemini SDK mode is endpoint/environment-sensitive even though it carries no base_url in LLMConfig.
    gemini = LLMConfig(provider="gemini", wire_format="gemini", model="shared-model", api_key="gemini-key")
    before = _config_signature(gemini)
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    assert _config_signature(gemini) != before


def test_generation_parameter_change_alters_cache_identity() -> None:
    config = LLMConfig(
        provider="anthropic",
        wire_format="messages",
        model="shared-model",
        base_url="https://api.anthropic.com",
        api_key="sk-ant",
    )
    identity = GenerationCacheIdentity.from_config(
        generator_name="gemini-summary-generator",
        prompt_version="summary-v4",
        config=config,
    )
    changed = replace(identity, generation_parameters=((*identity.generation_parameters, ("temperature", 1))))

    assert identity.signature != changed.signature


def test_managed_local_cache_identity_survives_a_restart(monkeypatch) -> None:
    """The managed target's endpoint/credential are re-randomized every Tauri launch (security material, not
    scientific identity) -- without a stable fingerprint, a semantically-identical Local AI request would never
    hit cache across a restart. Two configs differing only in the per-launch-ephemeral base_url/api_key, but
    sharing the same stable_identity_fingerprint, must produce the SAME cache signature."""
    from types import SimpleNamespace

    def _managed_config(*, base_url: str, api_key: str, fingerprint: str) -> SimpleNamespace:
        return SimpleNamespace(
            provider="managed_local",
            wire_format="chat_completions",
            model="callosum-managed-local",
            base_url=base_url,
            api_key=api_key,
            stable_identity_fingerprint=fingerprint,
            resolved_api_key=lambda: api_key,
        )

    launch_one = _managed_config(
        base_url="http://127.0.0.1:51234", api_key="launch-1-token", fingerprint="stable-model-abc"
    )
    launch_two = _managed_config(
        base_url="http://127.0.0.1:60111", api_key="launch-2-token", fingerprint="stable-model-abc"
    )
    assert _config_signature(launch_one) == _config_signature(launch_two)

    # A genuinely different model/runtime (a different fingerprint) must still miss.
    different_model = _managed_config(
        base_url="http://127.0.0.1:51234", api_key="launch-1-token", fingerprint="stable-model-xyz"
    )
    assert _config_signature(launch_one) != _config_signature(different_model)


def test_manual_local_provider_without_a_fingerprint_still_keys_on_transport(monkeypatch) -> None:
    """A manually-configured "local"/custom loopback provider (no stable_identity_fingerprint attribute at
    all -- only the managed target ever sets one) must keep the existing endpoint/credential-based identity
    unchanged, matching every other non-managed provider."""
    base = LLMConfig(
        provider="local", wire_format="chat_completions", model="llama3", base_url="http://127.0.0.1:11434"
    )
    assert _config_signature(replace(base, base_url="http://127.0.0.1:22222")) != _config_signature(base)


def test_prompt_relevant_source_and_scope_fields_define_input_hash() -> None:
    chunk = _source_chunk()
    kwargs = {"cache_signature": "sig", "source_chunks": [chunk], "scope_ref": {"query": "question"}}
    reference = summary_generation_input_hash(**kwargs)

    for changed in (
        replace(chunk, chunk_id=12),
        replace(chunk, chunk_version="chunk-v2"),
        replace(chunk, paper_id=8),
        replace(chunk, page_start=6),
        replace(chunk, page_end=6),
        replace(chunk, text="Changed evidence."),
    ):
        assert summary_generation_input_hash(**{**kwargs, "source_chunks": [changed]}) != reference
    assert summary_generation_input_hash(**{**kwargs, "scope_ref": {"query": "other"}}) != reference
    assert summary_generation_input_hash(**{**kwargs, "source_chunks": [chunk, replace(chunk, chunk_id=12)]}) != (
        summary_generation_input_hash(**{**kwargs, "source_chunks": [replace(chunk, chunk_id=12), chunk]})
    )


def test_legacy_under_specified_cache_row_is_not_reused(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    source_chunks = [_source_chunk()]
    scope_ref = {"query": "question"}
    generator = CountingSummaryGenerator([], signature="legacy-generator")
    legacy_key = canonical_hash(
        {
            "sig": generator.cache_signature,
            "chunks": [[11, "chunk-v1", "Evidence text."]],
            "scope": scope_ref,
        }
    )
    with engine.begin() as conn:
        conn.execute(
            insert(llm_cache).values(
                namespace="summary",
                input_hash=legacy_key,
                signature=generator.cache_signature,
                output_json={"sentences": [{"text": "legacy", "citations": []}]},
            )
        )
        result = CachedSummaryGenerator(generator).generate(
            source_chunks=source_chunks,
            scope_ref=scope_ref,
            conn=conn,
        )
        rows = conn.execute(select(func.count()).select_from(llm_cache)).scalar_one()
    engine.dispose()

    assert result == []
    assert generator.calls == 1
    assert rows == 2


def test_cache_identity_and_metadata_never_contain_raw_secrets(temp_db_url: str) -> None:
    secret = "sk-RECOGNIZABLE-RAW-SECRET"
    config = LLMConfig(
        provider="custom-a",
        wire_format="chat_completions",
        model="shared-model",
        base_url="https://user:password@provider.example/api",
        api_key=secret,
    )
    signature = _config_signature(config)
    generator = CountingSummaryGenerator([], signature=f"custom/{secret}/https://user:password@provider.example/api")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        CachedSummaryGenerator(generator).generate(
            source_chunks=[_source_chunk()],
            scope_ref={"query": "question"},
            conn=conn,
        )
        row = conn.execute(select(llm_cache.c.input_hash, llm_cache.c.signature)).one()
    engine.dispose()

    persisted = "|".join(str(value) for value in row)
    assert secret not in signature and secret not in persisted
    assert "password" not in signature and "password" not in persisted


def test_changed_chunk_version_forces_miss(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    _summarize(client)
    assert gen.calls == 1
    engine = make_engine(temp_db_url)  # bump the cited chunk's version → key changes
    with engine.begin() as conn:
        conn.execute(update(chunks).where(chunks.c.id == seeded["facial_chunk_id"]).values(chunk_version="bumped-v2"))
    engine.dispose()

    _summarize(client)
    assert gen.calls == 2  # a changed keyed input forces a miss


def test_verification_runs_on_cache_hit(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded, quote="This quote is not present in the source chunk."))
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    first = _summarize(client)
    second = _summarize(client)

    assert gen.calls == 1  # cache hit on the second run
    assert first["summary_status"] == "flagged"
    assert second["summary_status"] == "flagged"  # verification re-ran on the cached candidates
    assert second["sentences"][0]["flagged"] is True
    assert second["sentences"][0]["citations"][0]["quote_confidence"] == 0.0


def _summarize_papers(client, paper_id):
    # A papers scope selects chunks in pure DB order (no vector ranking), so the chunk set — and thus the
    # cache key — is identical across fresh app instances (unlike a query scope, whose ranking depends on
    # the per-app in-memory vector store).
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [paper_id]})
    assert started.status_code == 202
    return client.get(f"/summarize/{started.json()['job_id']}").json()


def test_cache_persists_across_app_instances(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen1 = CountingSummaryGenerator(_facial(seeded))
    first = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen1)), seeded["facial_paper_id"])
    assert gen1.calls == 1

    gen2 = CountingSummaryGenerator(_facial(seeded))  # a fresh app on the SAME db (≈ restart)
    second = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen2)), seeded["facial_paper_id"])

    assert gen2.calls == 0  # served from the persisted SQLite cache (no regeneration)
    assert _gen_shape(first) == _gen_shape(second)  # identical cached generation output


def test_malformed_cached_chunk_id_regenerates_instead_of_crashing(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen1 = CountingSummaryGenerator(_facial(seeded))
    first = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen1)), seeded["facial_paper_id"])
    assert first["status"] == "done"
    assert gen1.calls == 1
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            update(llm_cache)
            .where(llm_cache.c.namespace == "summary")
            .values(
                output_json={
                    "sentences": [
                        {
                            "text": "Facial anomalies influence social judgments.",
                            "citations": [
                                {"chunk_id": "chunk_1", "quote": "Facial anomalies influence social judgments."}
                            ],
                        }
                    ]
                }
            )
        )
    engine.dispose()
    gen2 = CountingSummaryGenerator(_facial(seeded))
    second = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen2)), seeded["facial_paper_id"])

    assert second["status"] == "done"
    assert gen2.calls == 1
    assert second["sentences"][0]["citations"][0]["chunk_id"] == seeded["facial_chunk_id"]


def test_repair_summary_cache_removes_only_malformed_summary_rows(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen)), seeded["facial_paper_id"])
    malformed = {
        "sentences": [
            {
                "text": "Facial anomalies influence social judgments.",
                "citations": [{"chunk_id": "chunk_1", "quote": "Facial anomalies influence social judgments."}],
            }
        ]
    }
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            insert(llm_cache),
            [
                {
                    "namespace": "summary",
                    "input_hash": "bad-summary",
                    "signature": "test",
                    "output_json": malformed,
                },
                {
                    "namespace": "other",
                    "input_hash": "bad-other",
                    "signature": "test",
                    "output_json": malformed,
                },
            ],
        )
        result = repair_summary_cache(conn)
        summary_rows = conn.execute(
            select(func.count()).select_from(llm_cache).where(llm_cache.c.namespace == "summary")
        ).scalar_one()
        other_rows = conn.execute(
            select(func.count()).select_from(llm_cache).where(llm_cache.c.namespace == "other")
        ).scalar_one()
    engine.dispose()

    assert result == {"scanned": 2, "removed": 1}
    assert summary_rows == 1
    assert other_rows == 1


def test_settings_repair_summary_cache_endpoint_commits(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            insert(llm_cache).values(
                namespace="summary",
                input_hash="bad-summary",
                signature="test",
                output_json={"sentences": [{"text": "x", "citations": [{"chunk_id": "chunk_1", "quote": "x"}]}]},
            )
        )
    client = TestClient(_summarization_app(temp_db_url))

    response = client.post("/settings/repair-summary-cache", json={})

    assert response.status_code == 200
    assert response.json() == {"scanned": 1, "removed": 1}
    with engine.connect() as conn:
        remaining = conn.execute(select(func.count()).select_from(llm_cache)).scalar_one()
    engine.dispose()
    assert remaining == 0


def test_signature_change_forces_miss(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen_a = CountingSummaryGenerator(_facial(seeded), signature="model-A/summary-v1")
    _summarize(TestClient(_summarization_app(temp_db_url, generator=gen_a)))
    assert gen_a.calls == 1

    gen_b = CountingSummaryGenerator(_facial(seeded), signature="model-B/summary-v2")
    _summarize(TestClient(_summarization_app(temp_db_url, generator=gen_b)))
    assert gen_b.calls == 1  # different model/prompt-version → miss


def test_cache_row_written(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    _summarize(TestClient(_summarization_app(temp_db_url, generator=gen)))

    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(llm_cache).where(llm_cache.c.namespace == "summary")
        ).scalar_one()
    engine.dispose()
    assert count == 1
