"""inc 306 — `keywords_from_work`: curated OpenAlex topics (else concepts) → keyword-tag display names."""

from __future__ import annotations

from integrations.openalex.work_keywords import keywords_from_work


def test_topics_preferred_score_filtered_and_ordered():
    work = {
        "topics": [
            {"display_name": "Facial Recognition", "score": 0.98},
            {"display_name": "Emotion Perception", "score": 0.71},
            {"display_name": "Low Signal Topic", "score": 0.10},  # below default min_score 0.3 → dropped
        ]
    }
    assert keywords_from_work(work) == ["Facial Recognition", "Emotion Perception"]


def test_topic_without_score_is_kept():
    # curated topics may omit a numeric score; a missing/non-numeric score is not a reason to drop it.
    work = {"topics": [{"display_name": "Curated Topic"}]}
    assert keywords_from_work(work) == ["Curated Topic"]


def test_falls_back_to_concepts_dropping_level_zero_and_low_score():
    work = {
        "concepts": [
            {"display_name": "Psychology", "level": 0, "score": 0.9},  # broadest discipline → dropped
            {"display_name": "Facial expression", "level": 2, "score": 0.6},
            {"display_name": "Faint Concept", "level": 3, "score": 0.1},  # below min_score → dropped
        ]
    }
    assert keywords_from_work(work) == ["Facial expression"]


def test_topics_win_over_concepts_when_both_present():
    work = {
        "topics": [{"display_name": "The Topic", "score": 0.9}],
        "concepts": [{"display_name": "A Concept", "level": 2, "score": 0.9}],
    }
    assert keywords_from_work(work) == ["The Topic"]


def test_dedupes_case_insensitively_and_caps():
    work = {
        "topics": [{"display_name": f"T{i}", "score": 0.9} for i in range(8)] + [{"display_name": "t0", "score": 0.9}]
    }
    assert keywords_from_work(work, max_terms=5) == ["T0", "T1", "T2", "T3", "T4"]


def test_empty_or_malformed_work_returns_empty():
    assert keywords_from_work(None) == []
    assert keywords_from_work({}) == []
    assert keywords_from_work({"topics": "not-a-list"}) == []
    assert keywords_from_work({"topics": [{"score": 0.9}]}) == []  # no display_name
    assert keywords_from_work({"topics": ["string-not-dict"]}) == []
