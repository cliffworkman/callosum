"""GitHub #76 + the suggestion-parity invariant (backend/data-contract coverage).

Invariant: **every canonical followable feed source kind is represented in Suggested Sources, or explicitly
exempt with a reason.** This file also confirms the category-vs-keyword mode the modal DERIVES from
`source_meta` (a fixed suggestion list ⇒ category-style) and that following any suggestable kind creates the
same canonical source as the ordinary Follow flow.

Scope note: this is a data/contract test. The top-level/subtab SWITCHING behavior is a real Playwright test in
`tests/e2e/test_smoke.py` — this file does **not** claim to test tab switching.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.discovery.feed import build_default_feed_registry

# The Suggested-Sources surface mapping, mirrored from 30g_feed_suggest.jsx's presentation grouping. Every
# canonical followable kind must appear here or in EXEMPT; a new kind added without a surface fails the parity
# test below (the invariant guard). This is a test assertion keyed to the registry — not a runtime taxonomy.
SUGGESTION_SURFACE = {
    "journal": "Journal tab",
    "biorxiv_category": "Rxiv Categories → bioRxiv",
    "medrxiv_category": "Rxiv Categories → medRxiv",
    "arxiv_category": "Rxiv Categories → arXiv",
    "psyarxiv": "Rxiv Categories → PsyArXiv",
    "pubmed_query": "Keyword Search → PubMed",
    "europepmc_keyword": "Keyword Search → Europe PMC",
    "followed_author": "Author tab",
}
EXEMPT: dict[str, str] = {}  # documented reasons a followable kind cannot be suggested; none today.

# followed_author is followable via the /followed-authors resolve flow (user_addable=false), so it is absent
# from the user-addable source_meta listing but IS a canonical followable kind that must be represented.
_RESOLVE_ONLY_KINDS = {"followed_author"}


def _followable_kinds() -> set[str]:
    return set(build_default_feed_registry().kinds) | _RESOLVE_ONLY_KINDS


def test_every_followable_kind_is_represented_in_suggestions_or_exempt():
    covered = set(SUGGESTION_SURFACE) | set(EXEMPT)
    missing = _followable_kinds() - covered
    assert not missing, (
        f"followable kinds with no Suggested-Sources surface: {sorted(missing)} — add a subtab/tab in "
        "30g_feed_suggest.jsx + SUGGESTION_SURFACE here, or record an explicit EXEMPT reason."
    )
    stale = set(SUGGESTION_SURFACE) - _followable_kinds()
    assert not stale, f"SUGGESTION_SURFACE names kinds that are not followable: {sorted(stale)}"


def test_source_meta_encodes_the_category_vs_keyword_mode_the_modal_derives():
    meta = {m["kind"]: m for m in build_default_feed_registry().source_meta}
    for kind in ("biorxiv_category", "medrxiv_category", "arxiv_category"):
        assert meta[kind]["suggestions"], f"{kind} must ship a fixed category list (category-style subtab)"
    for kind in ("psyarxiv", "pubmed_query", "europepmc_keyword"):
        assert meta[kind]["suggestions"] == [], f"{kind} must be keyword-style (no fixed list → keyword subtab)"


def test_following_each_suggestable_kind_creates_the_canonical_source(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    cases = {
        "biorxiv_category": "neuroscience",
        "medrxiv_category": "psychiatry",
        "arxiv_category": "cs.AI",
        "psyarxiv": "working memory",
        "pubmed_query": "hippocampus memory",
        "europepmc_keyword": "synaptic plasticity",
    }
    for kind, value in cases.items():
        r = client.post("/feed/subscriptions", json={"kind": kind, "value": value, "label": value})
        assert r.status_code == 200, (kind, r.text)
        row = r.json()
        assert row["kind"] == kind and row["value"] == value  # exact canonical kind/value == ordinary Follow
    stored = {(s["kind"], s["value"]) for s in client.get("/feed/subscriptions").json()["subscriptions"]}
    for kind, value in cases.items():
        assert (kind, value) in stored
