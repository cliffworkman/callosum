from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import fitz
import pytest
from pydantic import ValidationError

from app.backend.demo_ask_overview import DemoAskOverviewState, verified_claims_sha256
from app.backend.demo_coverage import DemoCoverageCatalogue
from app.backend.demo_extended_state import DemoExtendedState, DemoFeedState
from app.backend.demo_snapshot import DemoSnapshot, assert_public_snapshot_bytes
from app.backend.demo_synthesis_state import DemoSynthesisState
from tools.demo.build_demo import build_demo
from tools.demo.export_demo_snapshot import export_snapshot
from tools.demo.generate_demo_library_state import generate_state
from tools.demo.generate_demo_synthesis_state import generate_synthesis_state
from tools.demo.generate_demo_wip_state import generate_wip_state


class _DeterministicDemoEmbedding:
    name = "fixture-embedding"
    version = "1"

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _text in texts]


def _demo_source_db(tmp_path: Path) -> Path:
    db = tmp_path / "dedicated-public-demo.sqlite"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE papers (
          id INTEGER PRIMARY KEY, abstract TEXT, item_type TEXT, language TEXT, publication_date TEXT,
          first_author_family_name TEXT, citation_key TEXT, csl_json TEXT, processing_tier TEXT
        );
        CREATE TABLE attachments (
          id INTEGER PRIMARY KEY, paper_id INTEGER, storage_mode TEXT, availability TEXT,
          original_path TEXT, resolved_path TEXT, checksum TEXT, file_size INTEGER,
          content_type TEXT, import_source TEXT, attachment_type TEXT, role TEXT,
          oa_color TEXT, oa_version TEXT, oa_source TEXT, oa_landing_page_url TEXT,
          oa_license TEXT, oa_bronze_unstable INTEGER, created_at TEXT
        );
        CREATE TABLE chunks (
          id INTEGER PRIMARY KEY, paper_id INTEGER, attachment_id INTEGER, text TEXT, section TEXT,
          grobid_section_id INTEGER, page_start INTEGER, page_end INTEGER, char_start INTEGER, char_end INTEGER,
          bbox_json TEXT, bbox_coordinate_system TEXT, extraction_tool TEXT, extraction_version TEXT,
          chunking_strategy TEXT, chunk_version TEXT, source_attachment_checksum TEXT, created_at TEXT
        );
        CREATE TABLE summaries (
          id INTEGER PRIMARY KEY, scope_type TEXT, scope_ref_json TEXT, status TEXT, created_at TEXT
        );
        CREATE TABLE summary_sentences (id INTEGER PRIMARY KEY, summary_id INTEGER, ordinal INTEGER, text TEXT);
        CREATE TABLE citation_mappings (id INTEGER PRIMARY KEY, summary_sentence_id INTEGER, status TEXT);
        CREATE TABLE evidence_quotes (
          id INTEGER PRIMARY KEY, citation_mapping_id INTEGER, chunk_id INTEGER, quote_text TEXT,
          page_start INTEGER, page_end INTEGER, bbox_json TEXT, retrieval_confidence REAL,
          quote_confidence REAL, support_confidence REAL
        );
        """
    )
    for paper_id in (42, 67, 88, 90):
        pdf = tmp_path / f"source-{paper_id}.pdf"
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), f"Public evidence fixture for paper {paper_id}.")
        document.save(pdf)
        document.close()
        checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
        con.execute(
            "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                paper_id,
                f"Public abstract {paper_id}",
                "article-journal",
                "en",
                "2024-01-01",
                "Workman",
                f"demo{paper_id}",
                json.dumps({"id": f"source-{paper_id}", "type": "article-journal"}),
                "full-text",
            ),
        )
        con.execute(
            """INSERT INTO attachments (
                 id, paper_id, storage_mode, availability, resolved_path, checksum, file_size,
                 content_type, import_source, attachment_type, role, oa_license, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                paper_id,
                paper_id,
                "managed_copy",
                "available",
                str(pdf),
                checksum,
                pdf.stat().st_size,
                "application/pdf",
                "demo-fixture",
                "pdf",
                "primary",
                "CC0-1.0",
                "2026-08-10 00:00:00",
            ),
        )
        chunk_text = (
            "We fitted a linear mixed-effects model with random intercepts and report model assumptions, "
            "software versions, data availability, materials availability, preregistration, conflicts of interest, "
            "funding, and ethics approval. F(1, 20) = 4.00, p = .06."
        )
        con.execute(
            """INSERT INTO chunks (
                 id, paper_id, attachment_id, text, section, page_start, page_end, char_start, char_end,
                 bbox_json, bbox_coordinate_system, extraction_tool, extraction_version, chunking_strategy,
                 chunk_version, source_attachment_checksum, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                paper_id * 10,
                paper_id,
                paper_id,
                chunk_text,
                "results",
                1,
                1,
                0,
                len(chunk_text),
                None,
                "pdf_points_top_left",
                "demo-fixture",
                "1",
                "paragraph",
                "1",
                checksum,
                "2026-08-10 00:00:00",
            ),
        )
    con.execute(
        "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            89,
            "Public abstract 89",
            "article-journal",
            "en",
            "2026-06-12",
            "Bilici",
            "demo89",
            json.dumps({"id": "source-89", "type": "article-journal"}),
            "metadata-only",
        ),
    )
    con.execute(
        "INSERT INTO summaries VALUES (1, 'query', ?, 'flagged', '2026-08-10 12:00:00')",
        (json.dumps({"query": "What is the anomalous-is-bad bias?"}),),
    )
    for ordinal, (paper_id, status) in enumerate(((42, "verified"), (67, "weak"))):
        sentence_id = ordinal + 1
        con.execute(
            "INSERT INTO summary_sentences VALUES (?, 1, ?, ?)", (sentence_id, ordinal, f"Claim {sentence_id}.")
        )
        con.execute("INSERT INTO citation_mappings VALUES (?, ?, ?)", (sentence_id, sentence_id, status))
        precision = "exact" if status == "verified" else "region"
        con.execute(
            "INSERT INTO evidence_quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sentence_id,
                sentence_id,
                paper_id * 10,
                f"Evidence quote {sentence_id}.",
                sentence_id,
                sentence_id,
                json.dumps(
                    [{"page": sentence_id, "x0": 1, "y0": 2, "x1": 3, "y1": 4, "coordinate_precision": precision}]
                ),
                1.0,
                1.0,
                0.9,
            ),
        )
    con.commit()
    con.close()
    return db


def test_snapshot_generation_is_deterministic_and_uses_live_contracts(tmp_path: Path):
    source = _demo_source_db(tmp_path)
    first = tmp_path / "first" / "snapshot.json"
    second = tmp_path / "second" / "snapshot.json"
    claims = json.dumps([{"ordinal": 0, "text": "Claim 1."}], ensure_ascii=False, separators=(",", ":"))
    ask_overview = tmp_path / "ask-overview.json"
    ask_overview.write_text(
        json.dumps(
            {
                "summary_id": 1,
                "overview": [{"text": "A generated overview of the verified claim.", "claim_ordinals": [0]}],
                "verified_claim_count": 1,
                "verified_claims_sha256": hashlib.sha256(claims.encode("utf-8")).hexdigest(),
                "provider_id": "fixture",
                "model_id": "fixture",
                "prompt_version": "overview-v1",
            }
        ),
        encoding="utf-8",
    )
    export_snapshot(source, first, tmp_path / "first" / "documents", ask_overview_path=ask_overview)
    export_snapshot(source, second, tmp_path / "second" / "documents", ask_overview_path=ask_overview)
    assert first.read_bytes() == second.read_bytes()
    snapshot = DemoSnapshot.model_validate_json(first.read_bytes())
    assert snapshot.api.papers[0].list_item.title.startswith("What is good is beautiful")
    assert len(snapshot.api.papers) == 5
    assert snapshot.api.papers[2].list_item.title.startswith("Only human after all?")
    assert snapshot.api.papers[0].detail.authors == [
        "Dexian He",
        "Clifford I. Workman",
        "Xianyou He",
        "Anjan Chatterjee",
    ]
    assert snapshot.api.papers[1].detail.authors == [
        "Clifford I. Workman",
        "Stacey Humphries",
        "Franziska Hartung",
        "Geoffrey K. Aguirre",
        "Joseph W. Kable",
        "Anjan Chatterjee",
    ]
    assert snapshot.api.papers[2].detail.csl_json["issued"] == {"date-parts": [[2023, 12, 12]]}
    assert snapshot.api.papers[0].detail.csl_json["page"] == "633-641"
    assert snapshot.api.papers[1].detail.csl_json["volume"] == "1494"
    assert snapshot.api.summaries["1"].sentences[1].flagged is True
    assert snapshot.manifest.initial_workspace == "library"
    assert snapshot.api.papers[0].methods.statcheck.checked == 1
    assert len(snapshot.api.papers[1].methods.transparency.checks) == 7
    assert snapshot.api.status.jobs[0].status == "done"
    assert snapshot.api.status.jobs[0].nav["summary_id"] == 1
    assert [item.priority for item in snapshot.api.reading_queue] == ["high", "normal", None, None, None]
    assert {paper.id for paper in snapshot.api.axis_clusters["9001"][0].papers} == {42, 67, 88, 89, 90}
    assert {paper.id for paper in snapshot.api.axis_clusters["9002"][0].papers} == {42, 67, 89, 90}
    assert all(paper.detail.tags for paper in snapshot.api.papers)
    assert all(snapshot.api.suggested_tags[str(paper.list_item.id)].suggestions for paper in snapshot.api.papers)
    assert snapshot.api.my_publications_dashboard.status == "ok"
    assert "resolved_path" not in first.read_text(encoding="utf-8")
    assert set(snapshot.manifest.workspace_capabilities) >= {
        "profile",
        "library",
        "discover.feed",
        "work.statements",
        "settings",
    }
    assert len(snapshot.api.wip.manuscripts) == 2
    assert set(snapshot.api.synthesis.critical_reads) == {"42", "67", "88", "89", "90"}
    assert len(snapshot.api.synthesis.registration_comparison_details["1"].rows) == 12
    registration_detail = snapshot.api.synthesis.registration_comparison_details["1"]
    assert registration_detail.llm_triage_status["status"] == "success"
    assert all(row.llm_triage for row in registration_detail.rows)
    assert snapshot.api.extended.discover.search.items
    assert len(snapshot.api.extended.discover.citation_gaps.candidates) == 25
    assert len(snapshot.api.extended.discover.emerging_topics.topics) == 5
    assert len(snapshot.api.extended.discover.citing_authors.authors) == 12
    # All 4 confirmed My-Pubs papers have a DOI now (was 1/2 before the corpus grew, hence the old fallback note).
    assert snapshot.api.extended.discover.citation_gaps.coverage.checked == 4
    assert snapshot.api.extended.discover.citation_gaps.coverage.with_doi == 4
    assert snapshot.api.extended.discover.emerging_topics.coverage.recent_work_count > 0
    assert snapshot.api.extended.discover.citing_authors.coverage.citing_work_count > 0
    assert snapshot.api.extended.feed.included is True
    assert snapshot.api.extended.feed.approved_digest == (
        "9b829270831d63f4a5705bcf9a58c426aa3b256f9b837cd7223f825f6ce56824"
    )
    assert len(snapshot.api.extended.feed.subscriptions) == 9
    assert len(snapshot.api.extended.feed.items) == 1240
    assert snapshot.api.extended.discover.journals.profiles
    assert snapshot.api.extended.discover.funding_runs
    funding_report = next(iter(snapshot.api.extended.discover.funding_reports.values()))
    assert funding_report.llm_triage_status["status"] == "success"
    assert funding_report.llm_triage_status["annotated_count"] == 45
    assert all(
        item.get("llm_evaluation") for item in [*funding_report.open_opportunities, *funding_report.funding_prospects]
    )
    assert snapshot.api.extended.work.cite.suggestions
    assert snapshot.manifest.initial_paper_id == 67
    cite_ids = {item.paper_id for item in snapshot.api.extended.work.cite.suggestions}
    assert set(map(int, snapshot.api.extended.work.citation_renderings)) == cite_ids
    assert set(map(int, snapshot.api.extended.work.citation_bibtex)) == cite_ids
    assert all(
        "reference_text" in next(iter(value["items"]))
        for value in snapshot.api.extended.work.citation_renderings.values()
    )
    assert snapshot.api.extended.work.workbench_projects
    assert set(map(int, snapshot.api.extended.work.workbench_exports)) == {
        item.id for item in snapshot.api.extended.work.workbench_projects
    }
    assert all(
        set(exports) == {"csv", "metafor", "revman", "audit"}
        for exports in snapshot.api.extended.work.workbench_exports.values()
    )
    assert all(snapshot.api.extended.library.grim_checks.values())
    assert snapshot.api.synthesis.registration_license_audits[0].license_name == "No explicit reuse license recorded"
    assert snapshot.api.synthesis.registration_license_audits[0].bundled_full_registration is False
    for state in snapshot.api.wip.by_id.values():
        assert {reference.paper_id for reference in state.references} == {42, 67, 88, 89, 90}
        assert {run.tool_id for run in state.checks.runs} == {
            "statcheck",
            "transparency",
            "lmm",
            "bayes",
            "meta-analysis",
        }
        assert state.snapshots and state.tasks and state.sections


def test_demo_library_state_generation_is_deterministic(tmp_path: Path):
    source = _demo_source_db(tmp_path)
    first = tmp_path / "library-state-first.json"
    second = tmp_path / "library-state-second.json"
    generate_state(source, first, model=_DeterministicDemoEmbedding())
    generate_state(source, second, model=_DeterministicDemoEmbedding())
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["generated_with"]["suggested_tags"] == "Callosum local c-TF-IDF"
    assert [item["id"] for item in payload["reading_queue"]] == [67, 88, 42, 89, 90]


def test_demo_wip_state_regenerates_from_real_sandbox_deterministically(tmp_path: Path):
    output = tmp_path / "wip-state.json"
    generate_wip_state(output)
    # The generator always writes LF; a checked-out working copy may carry CRLF on a platform where
    # core.autocrlf normalizes text files on checkout (the git-stored blob itself is LF -- confirmed via
    # `git show HEAD:demo/wip-state-v1.json`). Comparing content, not raw checkout-dependent bytes.
    committed = Path("demo/wip-state-v1.json").read_bytes().replace(b"\r\n", b"\n")
    assert output.read_bytes() == committed


def test_demo_synthesis_state_regenerates_deterministically(tmp_path: Path):
    source = Path(".local/nli-01-anomalous/good-beautiful-export-v2.sqlite")
    if not source.is_file():
        pytest.skip("dedicated curated source database is not available")
    first = tmp_path / "synthesis-first.json"
    second = tmp_path / "synthesis-second.json"
    generate_synthesis_state(source, Path("demo/snapshot-v1.json"), first)
    generate_synthesis_state(source, Path("demo/snapshot-v1.json"), second)
    assert first.read_bytes() == second.read_bytes()
    generated = json.loads(first.read_text(encoding="utf-8"))
    curated = json.loads(Path("demo/synthesis-state-v1.json").read_text(encoding="utf-8"))
    for runs in curated["registration_comparison_runs"].values():
        for run in runs:
            run["model_versions"].pop("llm_triage", None)
    for detail in curated["registration_comparison_details"].values():
        detail["model_versions"].pop("llm_triage", None)
        detail["llm_triage_status"] = {
            "status": "not_searched",
            "annotated_count": 0,
            "focused_count": 0,
            "warning": "AI triage has not been requested for this comparison.",
        }
        for row in detail["rows"]:
            row["llm_triage"] = None
    assert DemoSynthesisState.model_validate(curated).model_dump(mode="json", exclude_none=True) == (
        DemoSynthesisState.model_validate(generated).model_dump(mode="json", exclude_none=True)
    )


def test_saved_meta_preregistration_uses_exact_reviewed_triage_snapshot():
    fixture = json.loads(
        Path("tools/demo/fixtures/good-beautiful-registration-triage-run2.json").read_text(encoding="utf-8")
    )
    synthesis = DemoSynthesisState.model_validate_json(Path("demo/synthesis-state-v1.json").read_bytes())
    detail = next(iter(synthesis.registration_comparison_details.values()))
    assert fixture["source"]["comparison_run_id"] == 2
    assert fixture["triage_status"]["provider_id"] == "gemini"
    assert fixture["triage_status"]["model_id"] == "gemini-2.5-flash-lite"
    assert len(fixture["annotations"]) == len(detail.rows) == 12
    assert [row.llm_triage for row in detail.rows] == [item["llm_triage"] for item in fixture["annotations"]]
    assert (
        detail.rows[7].llm_triage["rationale"]
        == "The registration outlines the use of linear mixed effect models with attractiveness, friendliness, "
        "and confidence as dependent variables, and vignette type as a fixed factor, including random intercepts "
        "for items and subjects. The publication reports using a linear mixed model with attractiveness as the "
        "dependent variable and vignette type as a fixed factor, with random intercepts for face stimulus and "
        "subject."
    )
    assert detail.llm_triage_status["warning"] == fixture["public_basis_warning"]
    assert any(not item["basis_matches_demo"] for item in fixture["annotations"])


def test_snapshot_rejects_unknown_fields_for_live_nested_shapes():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["papers"][0]["detail"]["parallel_demo_title"] = "must fail closed"
    payload = json.dumps(raw).encode()
    with pytest.raises(ValueError, match="unrecognized fields"):
        assert_public_snapshot_bytes(payload)


def test_saved_demo_synthesis_includes_traceable_generated_overview():
    snapshot = DemoSnapshot.model_validate_json(Path("demo/snapshot-v1.json").read_bytes())
    summary = snapshot.api.summaries[str(snapshot.manifest.initial_summary_id)]
    state = DemoAskOverviewState.model_validate_json(Path("demo/ask-overview-v1.json").read_bytes())
    assert summary.overview == state.overview
    assert state.verified_claims_sha256 == verified_claims_sha256(summary)
    # Only 1 of 5 saved sentences is fully verified (see the mixed-status test below) -- the Overview can only
    # ever narrate that one claim, never the flagged ones, so its length is bounded by the verified count, not
    # a fixed "several claims" assumption.
    assert 1 <= len(summary.overview) <= 6
    verified_ordinals = {sentence.ordinal for sentence in summary.sentences or [] if not sentence.flagged}
    assert all(set(item.claim_ordinals) <= verified_ordinals for item in summary.overview)


def test_saved_demo_synthesis_is_the_verified_and_flagged_three_paper_sandbox_run():
    # Deliberately a mixed-status summary (backlog: demo/Ask flagged-state gap, 2026-08-30): an all-"verified"
    # demo is less representative of the app's real verified/flagged behavior than an honest mix -- see
    # tools/demo/promote_verified_demo_synthesis.py's own docstring for the promotion-gate rationale.
    snapshot = DemoSnapshot.model_validate_json(Path("demo/snapshot-v1.json").read_bytes())
    summary = snapshot.api.summaries[str(snapshot.manifest.initial_summary_id)]
    assert summary.summary_status == "flagged"
    assert len(summary.sentences or []) == 5
    flagged = [sentence.flagged for sentence in summary.sentences or []]
    assert flagged.count(False) == 1  # exactly one fully-verified claim
    assert flagged.count(True) == 4  # exactly four flagged (weak-retrieval) claims
    assert {citation.paper_id for sentence in summary.sentences or [] for citation in sentence.citations} == {
        42,
        67,
        88,
    }
    citations = [citation for sentence in summary.sentences or [] for citation in sentence.citations]
    statuses = [citation.status for citation in citations]
    assert statuses.count("verified") == 1
    assert statuses.count("weak") == 4
    # Every quote/support is genuinely strong even on the "weak" citations -- their status comes from
    # retrieval_confidence alone falling just under threshold, not a fabricated or low-quality match.
    assert all(citation.quote_confidence == pytest.approx(1.0) for citation in citations)
    assert all(citation.support_confidence == pytest.approx(1.0) for citation in citations)


def test_saved_my_publications_dashboard_has_real_citation_chart_data():
    # 4 confirmed My Publications papers (42, 67, 89, 90 -- Workman-authored; 88 is Rasset et al., not a
    # My-Pub) since the 2026-08-30 corpus growth closed cap-domains (MIN_DOMAIN_PAPERS=4). Citation counts
    # are live OpenAlex reads and drift between captures; only the corpus-shape assertions stay exact.
    snapshot = DemoSnapshot.model_validate_json(Path("demo/snapshot-v1.json").read_bytes())
    dashboard = snapshot.api.my_publications_dashboard
    assert dashboard.status == "ok"
    assert dashboard.in_library == 4
    assert dashboard.indexed_works == 4
    assert dashboard.gap == 0
    assert dashboard.missing_works == []
    assert dashboard.metrics.works_count == 4
    assert dashboard.metrics.cited_by_count == sum(item.cited_by_count for item in dashboard.paper_citations.values())
    assert {item.year for item in dashboard.counts_by_year} == {2021, 2022, 2024, 2026}
    assert all(item.works_count == 1 for item in dashboard.counts_by_year)
    assert dashboard.research_summary and "facial appearance" in dashboard.research_summary
    # Real /my-publications/domains decomposition (never a fabricated placeholder): 2 domains over the 4
    # confirmed papers, keyed by the real job's own content-derived ids (not a "demo-presentation:" fixture).
    assert len(dashboard.domains) == 2
    assert all(domain.key.startswith("domain:") for domain in dashboard.domains)
    assert {paper_id for domain in dashboard.domains for paper_id in domain.paper_ids} == {42, 67, 89, 90}
    assert dashboard.openalex_extra and dashboard.openalex_extra.openalex_author_id
    assert set(snapshot.api.my_publications_citing) == {
        item.openalex_work_id for item in dashboard.paper_citations.values()
    }
    # Paper 89 (Bilici et al. 2026) is brand new with 0 real citations yet -- an honest zero, not missing data.
    assert sum(len(result.works) for result in snapshot.api.my_publications_citing.values()) > 0
    assert {paper.list_item.id: paper.list_item.processing_tier for paper in snapshot.api.papers} == {
        42: "fully-chunked",
        67: "fully-chunked",
        88: "fully-chunked",
        89: "metadata-only",
        90: "fully-chunked",
    }
    assert {paper.detail.id: paper.detail.processing_tier for paper in snapshot.api.papers} == {
        42: "fully-chunked",
        67: "fully-chunked",
        88: "fully-chunked",
        89: "metadata-only",
        90: "fully-chunked",
    }
    assert all(topic.increase > 0 for topic in snapshot.api.extended.discover.emerging_topics.topics)
    assert all(
        author.citing_work_count >= 2 and author.cited_publication_count >= 2
        for author in snapshot.api.extended.discover.citing_authors.authors
    )


def test_saved_meta_reference_covers_every_outcome_for_all_curated_papers():
    # Papers 42 and 89 have a real, pre-existing external-data gap (neither Semantic Scholar nor OpenAlex has
    # ever resolved a reference list for either DOI -- confirmed independently, not a capture bug; see
    # tools/demo/capture_demo_meta_reference.py's own all-empty-fails/some-empty-tolerated posture) -- both
    # checked_count=0 and citation-context total_citations=0 for those two specifically, never for every paper.
    snapshot = DemoSnapshot.model_validate_json(Path("demo/snapshot-v1.json").read_bytes())
    work = snapshot.api.extended.work
    assert {pid: work.reference_integrity[str(pid)].checked_count > 0 for pid in (42, 67, 88, 89, 90)} == {
        42: False,
        67: True,
        88: True,
        89: True,
        90: True,
    }
    assert all(len(work.citation_equity[str(pid)].signals) == 4 for pid in (42, 67, 88, 89, 90))
    assert all(work.overlooked_work[str(pid)].shown > 0 for pid in (42, 67, 88, 89, 90))
    assert all(
        work.citation_context_incoming[str(pid)].total_citations
        + work.citation_context_outgoing[str(pid)].total_citations
        > 0
        for pid in (67, 88, 90)
    )


def test_snapshot_rejects_unknown_fields_in_saved_method_results():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["papers"][0]["methods"]["statcheck"]["parallel_demo_score"] = 1
    with pytest.raises(ValueError, match="unrecognized fields"):
        assert_public_snapshot_bytes(json.dumps(raw).encode())


def test_snapshot_rejects_unknown_fields_in_saved_wip_state():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["wip"]["manuscripts"][0]["private_demo_note"] = "must fail closed"
    with pytest.raises(ValidationError, match="private_demo_note"):
        DemoSnapshot.model_validate(raw)


def test_snapshot_rejects_unknown_fields_in_saved_synthesis_state():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["synthesis"]["critical_reads"]["42"]["parallel_demo_score"] = 100
    with pytest.raises(ValueError, match="unrecognized fields"):
        assert_public_snapshot_bytes(json.dumps(raw).encode())


def test_snapshot_rejects_unknown_fields_in_extended_state():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["extended"]["work"]["parallel_demo_ui"] = True
    with pytest.raises(ValidationError, match="parallel_demo_ui"):
        DemoSnapshot.model_validate(raw)


def test_public_scanner_rejects_unknown_fields_in_nested_extended_live_models():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["extended"]["discover"]["journals"]["parallel_demo_rank"] = 1
    with pytest.raises(ValidationError, match="parallel_demo_rank"):
        assert_public_snapshot_bytes(json.dumps(raw).encode())


def test_feed_snapshot_requires_exact_human_approval_digest():
    with pytest.raises(ValidationError, match="approved review digest"):
        DemoFeedState(included=True, subscriptions=[], items=[])
    with pytest.raises(ValidationError, match="unapproved Feed records"):
        DemoFeedState(
            subscriptions=[{"id": 1, "kind": "journal", "value": "Public journal", "label": "Public journal"}]
        )


def test_saved_discover_fixture_preserves_reviewed_feed_and_followed_authors():
    extended = DemoExtendedState.model_validate_json(Path("demo/extended-state-v1.json").read_bytes())
    feed = extended.feed
    assert feed.included is True
    assert len(feed.subscriptions) == 9
    assert len(feed.items) == 1240  # the static provider applies the live endpoint's 200-item default at read time
    assert any(item.is_read for item in feed.items)
    assert any(item.in_library for item in feed.items)
    assert len(extended.discover.followed_authors) == 1  # the tab's gap-candidate view was retired 2026-08-27;
    # the follow list itself (now surfaced via Feed's own pills, not a separate tab) is unaffected


def test_demo_runtime_has_bounded_feed_local_state_locks_and_static_funding_export():
    runtime = Path("demo/demo-runtime.js").read_text(encoding="utf-8")
    assert 'parts.search.get("limit") || 200' in runtime
    assert 'path === "/demo/feed-state/reset"' in runtime
    assert "Feed refresh is unavailable online because it polls external journal" in runtime
    assert "/export\\.csv$/" in runtime
    assert '"text/csv; charset=utf-8"' in runtime
    assert 'path === "/citations/render"' in runtime
    assert 'path === "/papers/export"' in runtime
    assert "workbenchExportMatch" in runtime


def test_demo_runtime_resolves_system_reads_and_explains_every_unavailable_surface():
    runtime = Path("demo/demo-runtime.js").read_text(encoding="utf-8")
    for path in (
        'path === "/settings/providers"',
        'path === "/sync/status"',
        'path === "/sync/conflicts"',
        'path === "/agent/writes"',
        'path === "/usage/summary"',
        'path === "/feedback/capability"',
    ):
        assert path in runtime
    assert "This read-only surface is not included in the current demo snapshot" in runtime
    assert "blocked(missingReadMessage, path)" in runtime
    for boundary in (
        "Settings changes",
        "Sync is unavailable",
        "LibreOffice installation",
        "Word add-in",
        "Feedback submission",
    ):
        assert boundary in runtime


def test_coverage_catalogue_agrees_with_central_capabilities():
    snapshot = DemoSnapshot.model_validate_json(Path("demo/snapshot-v1.json").read_bytes())
    coverage = DemoCoverageCatalogue.model_validate_json(Path("demo/coverage-v1.json").read_bytes())
    by_id = {item.id: item for item in coverage.items}
    assert coverage.snapshot_schema_version == snapshot.manifest.snapshot_schema_version
    for surface, capability in snapshot.manifest.workspace_capabilities.items():
        assert by_id[surface].status == capability.mode


@pytest.mark.parametrize(
    "payload, message",
    [
        (b'{"original_path":"C:/Users/private/library.pdf"}', "forbidden field"),
        (b'{"value":"/home/person/library.pdf"}', "local filesystem path"),
        (b'{"value":"sk-public-demo-should-never-contain-this"}', "credential-like"),
    ],
)
def test_public_scanner_rejects_paths_credentials_and_forbidden_fields(payload: bytes, message: str):
    with pytest.raises(ValueError, match=message):
        assert_public_snapshot_bytes(payload)


def test_snapshot_schema_version_mismatch_fails_clearly():
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    for incompatible_version in (1, 999):
        raw["manifest"]["snapshot_schema_version"] = incompatible_version
        with pytest.raises(ValidationError, match="unsupported demo snapshot schema"):
            DemoSnapshot.model_validate(raw)


def test_snapshot_rejects_asset_and_base_path_traversal(tmp_path: Path):
    raw = json.loads(Path("demo/snapshot-v1.json").read_text(encoding="utf-8"))
    raw["api"]["papers"][0]["document"]["asset_path"] = "../private.pdf"
    with pytest.raises(ValidationError, match="asset_path"):
        DemoSnapshot.model_validate(raw)
    with pytest.raises(ValueError, match="traversal"):
        build_demo(Path("demo/snapshot-v1.json"), tmp_path / "demo", "/safe/%2e%2e/private/")


def test_static_build_is_self_contained_and_base_path_safe(tmp_path: Path):
    output = tmp_path / "callosum-demo"
    build_demo(Path("demo/snapshot-v1.json"), output, "/research/callosum/")
    index = (output / "index.html").read_text(encoding="utf-8")
    assert '<base href="/research/callosum/">' in index
    assert "demo-config.js" in index
    assert "demo-runtime.js" in index
    assert "cdnjs.cloudflare.com" not in index
    assert "localhost:" not in index and "127.0.0.1:" not in index
    assert (output / "synthesis" / "index.html").is_file()
    assert (output / "404.html").is_file()
    assert (output / "assets" / "react.production.min.js").is_file()
    assert (output / "assets" / "pdf.min.mjs").is_file()
    assert (output / "demo-config.js").is_file()
    assert (output / "coverage-v1.json").is_file()
    assert (output / "experience-coverage-v1.json").is_file()
    assert "No explicit reuse license recorded" in (output / "demo-about.html").read_text(encoding="utf-8")
    assert (output / "documents" / "he-2021-good-beautiful-preprint.pdf").is_file()
    assert (output / "documents" / "rasset-2023-only-human.pdf").is_file()
    assert "frame-ancestors 'none'" in (output / "_headers").read_text(encoding="utf-8")
