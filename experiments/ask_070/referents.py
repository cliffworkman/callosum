"""Question-owned literal spans; no scientific answers or automatically accepted semantics."""

import re

from .hashing import digest, text_hash

# Literal human-request phrases. Categorization is a DRAFT, never an accepted semantic referent.
DRAFT_PHRASES = {
    "eval_5ht2a": {
        "constructs": ["serotonin 5-HT2A receptor", "human brain function and pharmacology"],
        "operations": ["Identify", "distinguish", "describe", "preserve"],
        "relationships": [
            "receptor-related findings from broader serotonergic findings",
            "direction and type of reported relationships",
        ],
        "populations": ["human"],
        "output_fields": ["specific brain regions or systems implicated"],
        "qualifications": ["null", "mixed", "uncertain"],
        "open_elements": ["What does my library suggest"],
    },
    "eval_expert_lay_faces": {
        "constructs": ["visual attention to faces"],
        "operations": ["differ", "Identify"],
        "relationships": ["between experts and laypeople", "which group differences are supported"],
        "populations": ["experts", "laypeople"],
        "output_fields": ["populations compared", "facial regions or features receiving attention", "measures used"],
        "qualifications": ["null", "mixed", "uncertain"],
        "open_elements": ["the studies in my library"],
    },
    "eval_aesthetics_truthiness": {
        "constructs": ["images or their aesthetic qualities", "perceived truth or belief"],
        "operations": ["Identify"],
        "relationships": [
            "influence perceived truth or belief",
            "direction of reported effects",
            "moderation or boundary conditions",
        ],
        "populations": [],
        "output_fields": ["constructs and measures used"],
        "qualifications": ["null", "mixed", "uncertain"],
        "open_elements": ["whether images or their aesthetic qualities influence"],
    },
}


def inventory(question):
    text = question["text"]
    spans = []
    # Partition all bytes conceptually; offsets are Python Unicode code points and UTF-8 bytes.
    for index, match in enumerate(re.finditer(r"[^?!.]+[?!.]*|[?!.]+", text), start=1):
        start, end = match.span()
        spans.append(
            {
                "id": f"literal-{index}",
                "start": start,
                "end": end,
                "utf8_start": len(text[:start].encode()),
                "utf8_end": len(text[:end].encode()),
                "text": text[start:end],
                "status": "EXACT_QUESTION_SPAN",
            }
        )
    assert "".join(s["text"] for s in spans) == text
    annotations = []
    for category, phrases in DRAFT_PHRASES.get(question["id"], {}).items():
        for phrase in phrases:
            start = text.index(phrase)
            annotations.append(
                {
                    "category": category,
                    "literal_text": phrase,
                    "start": start,
                    "end": start + len(phrase),
                    "status": "HUMAN_REFERENT_REVIEW_REQUIRED",
                    "origin": "CODEX_DRAFT_FROM_EXPLICIT_QUESTION_WORDS_NOT_GROUND_TRUTH",
                }
            )
    record = {
        "question_id": question["id"],
        "original_question": text,
        "question_sha256": text_hash(text),
        "offset_convention": "zero-based half-open Unicode code points plus UTF-8 byte offsets",
        "literal_spans": spans,
        "interpretive_annotations": annotations,
        "review_status": "HUMAN_REFERENT_REVIEW_REQUIRED",
        "review_checklist": [
            "load-bearing constructs",
            "requested operations",
            "relationships",
            "explicit populations",
            "requested output fields",
            "qualification requirements",
            "open/unresolved request elements",
        ],
        "ground_truth_accepted": False,
        "scientific_answer_targets": "NOT_AUTHORED",
        "provenance": "deterministic partition of human-approved question; review tasks are not labels",
    }
    return record | {"inventory_sha256": digest(record)}


def validate_review(inventory, review):
    content = {k: v for k, v in inventory.items() if k != "inventory_sha256"}
    return (
        digest(content) == inventory["inventory_sha256"]
        and review.get("inventory_sha256") == inventory["inventory_sha256"]
        and review.get("decision") == "APPROVED"
        and review.get("origin") == "HUMAN"
        and bool(review.get("reviewer"))
        and not review.get("unresolved")
    )
