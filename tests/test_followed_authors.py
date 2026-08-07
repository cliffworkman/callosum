"""Followed authors — a lightweight gap-finder source (backlog #29, inc 454)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.clustering.followed_authors import (
    FOLLOWED_AUTHOR_MAX_CANDIDATES,
    FollowedAuthorCandidate,
    compute_followed_author_candidates,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.followed_author_repo import (
    add_followed_author,
    list_followed_authors,
    read_followed_author_candidates,
    remove_followed_author,
    replace_followed_author_candidates,
)
from app.backend.persistence.profile_repo import dismiss_gap, dismissed_gaps
from app.backend.persistence.repository import create_paper
from integrations.openalex.author import AuthorWork, ResolvedAuthor


def _paper(conn, doi) -> int:
    return create_paper(conn, title=doi, csl_json={"title": doi, "DOI": doi}, doi=doi)


def _work(doi, title="T", year=2020, cited_by=0, work_id=None):
    return AuthorWork(doi=doi, title=title, year=year, cited_by_count=cited_by, openalex_work_id=work_id)


class _FakeAuthorClient:
    """Mirrors OpenAlexAuthorClient's shape; records every call for zero-egress assertions."""

    def __init__(self, resolved=None, works_by_author=None):
        self.calls: list[tuple[str, tuple]] = []
        self.resolved = resolved or {}  # keyed by (orcid, name)
        self.works_by_author = works_by_author or {}

    def with_cache_engine(self, _engine):
        return self

    def resolve_author(self, conn, *, orcid=None, name=None):
        self.calls.append(("resolve_author", (orcid, name)))
        return self.resolved.get((orcid, name))

    def fetch_author_works(self, conn, author_id, *, refresh=False):
        self.calls.append(("fetch_author_works", (author_id, refresh)))
        return self.works_by_author.get(author_id, [])


# ---- compute_followed_author_candidates (inc 454, the design-doc test spec) -----------------------------------


def test_compute_candidates_surfaces_absent_work_with_provenance(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, "10.1/already-have")
        client = _FakeAuthorClient(
            works_by_author={
                "A1": [
                    _work("10.9/new-work", "New Work", 2024, work_id="W1"),
                    _work("10.1/already-have", "Already Have", 2020, work_id="W2"),
                ]
            }
        )
        candidates, coverage = compute_followed_author_candidates(
            conn, author_client=client, author_id="A1", author_display_name="A. Researcher", dismissed=set()
        )
    engine.dispose()
    assert [c.doi for c in candidates] == ["10.9/new-work"]  # already-in-library work never appears
    assert candidates[0].author_id == "A1" and candidates[0].author_display_name == "A. Researcher"
    assert candidates[0].title == "New Work" and coverage["works_checked"] == 2
    assert "not filtered or ranked" in coverage["note"].lower()  # the disclosed v1 axis-relevance limitation


def test_compute_candidates_excludes_dismissed_no_doi_and_caps_ordering(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works = [
            _work("10.9/dismissed-doi", "Dismissed", 2022, work_id="WD"),
            _work(None, "No DOI", 2023, work_id="WN"),  # unpersistable -> skipped
            _work("10.9/older", "Older", 2019, work_id="WO"),
            _work("10.9/newer", "Newer", 2025, work_id="WNew"),
        ]
        client = _FakeAuthorClient(works_by_author={"A1": works})
        candidates, _ = compute_followed_author_candidates(
            conn,
            author_client=client,
            author_id="A1",
            author_display_name="A",
            dismissed={"10.9/dismissed-doi"},
            max_candidates=1,
        )
    engine.dispose()
    assert [c.doi for c in candidates] == ["10.9/newer"]  # newest-first, capped to 1, dismissed+no-DOI dropped


def test_compute_candidates_dismissed_by_openalex_id_also_excluded(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = _FakeAuthorClient(works_by_author={"A1": [_work("10.9/x", "X", 2021, work_id="WX")]})
        candidates, _ = compute_followed_author_candidates(
            conn, author_client=client, author_id="A1", author_display_name="A", dismissed={"WX"}
        )
    engine.dispose()
    assert candidates == []


def test_compute_candidates_respects_max_candidates_default(temp_db_url):
    assert FOLLOWED_AUTHOR_MAX_CANDIDATES == 50  # pinned -- a change here should be deliberate, not accidental


# ---- followed_author_repo ---------------------------------------------------------------------------------


def test_repo_add_is_idempotent_and_remove_cascades(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        add_followed_author(conn, author_id="A1", display_name="First Name", orcid=None, matched_by="name")
        add_followed_author(conn, author_id="A1", display_name="Updated Name", orcid="0000-1", matched_by="orcid")
        rows = list_followed_authors(conn)
        replace_followed_author_candidates(
            conn,
            "A1",
            [
                FollowedAuthorCandidate(
                    author_id="A1",
                    author_display_name="Updated Name",
                    openalex_work_id="W1",
                    doi="10.9/w1",
                    title="T",
                    year=2020,
                    cited_by_count=0,
                )
            ],
            computed_at="2026-08-01T00:00:00Z",
        )
        cached_before = read_followed_author_candidates(conn)
        removed = remove_followed_author(conn, "A1")
        cached_after = read_followed_author_candidates(conn)
        removed_again = remove_followed_author(conn, "A1")  # idempotent no-op
    engine.dispose()
    assert len(rows) == 1 and rows[0]["display_name"] == "Updated Name" and rows[0]["matched_by"] == "orcid"
    assert len(cached_before) == 1
    assert removed is True and cached_after == []  # cascade purge
    assert removed_again is False


def test_repo_read_defensively_filters_stale_candidates_after_a_failed_cascade(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        add_followed_author(conn, author_id="A1", display_name="A", orcid=None, matched_by="name")
        candidate = FollowedAuthorCandidate(
            author_id="A1",
            author_display_name="A",
            openalex_work_id="W1",
            doi="10.9/w1",
            title="T",
            year=2020,
            cited_by_count=0,
        )
        replace_followed_author_candidates(conn, "A1", [candidate], computed_at="2026-08-01T00:00:00Z")
        # simulate an unfollow whose cascade delete of followed_authors succeeded but somehow left the
        # candidate row behind (defense against exactly that partial-failure shape)
        from sqlalchemy import delete

        from app.backend.persistence.schema import followed_authors

        conn.execute(delete(followed_authors).where(followed_authors.c.author_id == "A1"))
        rows = read_followed_author_candidates(conn)
    engine.dispose()
    assert rows == []  # the stale candidate never resurfaces once the author is gone


# ---- endpoints ----------------------------------------------------------------------------------------------


def _resolved(author_id="A1", name="A. Researcher", orcid=None, matched_by="name"):
    return ResolvedAuthor(author_id=author_id, display_name=name, orcid=orcid, works_count=10, matched_by=matched_by)


def _drive_refresh(client, author_id=None):
    body = {"author_id": author_id} if author_id else {}
    jid = client.post("/followed-authors/refresh", json=body).json()["job_id"]
    data = {}
    for _ in range(30):
        data = client.get(f"/followed-authors/refresh/{jid}").json()
        if data["status"] in ("done", "error"):
            return data
    return data


def test_endpoint_full_lifecycle_follow_refresh_dismiss_add(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, "10.1/in-lib")
    engine.dispose()
    author_client = _FakeAuthorClient(
        resolved={(None, "A. Researcher"): _resolved()},
        works_by_author={
            "A1": [
                _work("10.9/absent", "Absent Work", 2024, cited_by=3, work_id="WA"),
                _work("10.1/in-lib", "In Library", 2020, work_id="WL"),
            ]
        },
    )
    app = create_app(db_url=temp_db_url, openalex_author_client=author_client)
    client = TestClient(app)

    f1 = client.post("/followed-authors", json={"name": "A. Researcher"})
    assert f1.status_code == 200 and f1.json()["status"] == "followed"
    f2 = client.post("/followed-authors", json={"name": "A. Researcher"})
    assert f2.json()["status"] == "already-following"

    empty = client.get("/followed-authors/candidates").json()["candidates"]
    assert empty == []  # never refreshed yet

    done = _drive_refresh(client)
    assert done["status"] == "done" and done["result"]["authors_refreshed"] == 1
    assert done["result"]["works_checked"] == 2

    cands = client.get("/followed-authors/candidates").json()["candidates"]
    assert [c["doi"] for c in cands] == ["10.9/absent"]  # in-library work excluded
    assert cands[0]["author_display_name"] == "A. Researcher"

    dismiss = client.post("/followed-authors/dismiss", json={"doi": "10.9/absent", "openalex_work_id": "WA"})
    assert dismiss.status_code == 204
    assert client.get("/followed-authors/candidates").json()["candidates"] == []


def test_direct_follow_from_citing_authors_panel_makes_zero_resolve_calls(temp_db_url):
    author_client = _FakeAuthorClient()
    app = create_app(db_url=temp_db_url, openalex_author_client=author_client)
    client = TestClient(app)
    r = client.post("/followed-authors", json={"author_id": "A9", "display_name": "Quick Follow"})
    assert r.status_code == 200 and r.json()["status"] == "followed"
    assert r.json()["author"]["matched_by"] == "direct"
    assert author_client.calls == []  # zero OpenAlex resolution -- the panel already resolved this author


def test_follow_no_match_returns_clean_200(temp_db_url):
    author_client = _FakeAuthorClient(resolved={})  # nothing matches
    app = create_app(db_url=temp_db_url, openalex_author_client=author_client)
    client = TestClient(app)
    r = client.post("/followed-authors", json={"name": "Nobody Findable"})
    assert r.status_code == 200 and r.json()["status"] == "no-match" and r.json()["author"] is None


def test_ordinary_reads_never_egress_only_refresh_does(temp_db_url):
    author_client = _FakeAuthorClient(
        resolved={(None, "A. Researcher"): _resolved()},
        works_by_author={"A1": [_work("10.9/x", "X", 2024, work_id="WX")]},
    )
    app = create_app(db_url=temp_db_url, openalex_author_client=author_client)
    client = TestClient(app)
    client.post("/followed-authors", json={"name": "A. Researcher"})
    author_client.calls.clear()  # clear the resolve_author call from following

    client.get("/followed-authors")
    client.get("/followed-authors/candidates")
    client.get("/followed-authors")
    assert author_client.calls == []  # plain GETs never touch the author client

    _drive_refresh(client)
    assert any(name == "fetch_author_works" for name, _ in author_client.calls)  # only refresh calls out


def test_dismiss_is_shared_with_gaps_dismissal_list(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert dismissed_gaps(conn) == set()
    engine.dispose()
    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    client = TestClient(app)
    r = client.post("/followed-authors/dismiss", json={"doi": "10.9/shared", "openalex_work_id": "WS"})
    assert r.status_code == 204
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        keys = dismissed_gaps(conn)
        # dismiss_gap itself is exercised directly too, proving the exact same repo function is reused
        dismiss_gap(conn, "10.9/direct")
        keys2 = dismissed_gaps(conn)
    engine.dispose()
    assert keys == {"10.9/shared", "WS"}
    assert keys2 == {"10.9/shared", "WS", "10.9/direct"}


def test_malformed_author_id_and_oversized_name_are_rejected(temp_db_url):
    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    client = TestClient(app)
    bad_follow = client.post("/followed-authors", json={"author_id": "not-an-id", "display_name": "X"})
    assert bad_follow.status_code == 422
    bad_unfollow = client.delete("/followed-authors/not-an-id")
    assert bad_unfollow.status_code == 422
    oversized = client.post("/followed-authors", json={"author_id": "A1", "display_name": "x" * 301})
    assert oversized.status_code == 422
    missing_display_name = client.post("/followed-authors", json={"author_id": "A1"})
    assert missing_display_name.status_code == 422


def test_unfollow_is_idempotent_and_add_imports_a_candidate(temp_db_url):
    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    client = TestClient(app)
    client.post("/followed-authors", json={"author_id": "A1", "display_name": "A"})
    assert client.delete("/followed-authors/A1").status_code == 204
    assert client.delete("/followed-authors/A1").status_code == 204  # already gone -- still 204, not 404
    assert client.get("/followed-authors").json() == []

    add = client.post("/followed-authors/add", json={"doi": "10.9/added", "title": "Added Work"})
    assert add.status_code == 200 and add.json()["status"] == "imported"


# ---- Feed sync (inc 455) -----------------------------------------------------------------------------------


def test_follow_creates_a_matching_feed_subscription_and_unfollow_removes_it(temp_db_url):
    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    client = TestClient(app)
    client.post("/followed-authors", json={"author_id": "A1", "display_name": "A. Researcher"})

    subs = client.get("/feed/subscriptions").json()["subscriptions"]
    sub = next(s for s in subs if s["kind"] == "followed_author")
    assert sub["value"] == "A1" and sub["label"] == "A. Researcher"

    client.delete("/followed-authors/A1")
    subs_after = client.get("/feed/subscriptions").json()["subscriptions"]
    assert not any(s["kind"] == "followed_author" for s in subs_after)


def test_refollowing_does_not_duplicate_the_feed_subscription(temp_db_url):
    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    client = TestClient(app)
    client.post("/followed-authors", json={"author_id": "A1", "display_name": "A"})
    client.post("/followed-authors", json={"author_id": "A1", "display_name": "A"})  # already-following
    subs = client.get("/feed/subscriptions").json()["subscriptions"]
    assert len([s for s in subs if s["kind"] == "followed_author"]) == 1


def test_backfill_creates_feed_subscriptions_for_pre_existing_followed_authors(temp_db_url):
    """A follow written directly to the repo (simulating one that predates inc 455, before the sync existed)
    gets a matching feed_subscriptions row from the app's own startup self-heal -- proven via the real ASGI
    lifespan, which only fires inside a `with TestClient(app) as client:` block."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        add_followed_author(conn, author_id="A1", display_name="Pre-existing", orcid=None, matched_by="name")
    engine.dispose()

    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    with TestClient(app) as client:
        subs = client.get("/feed/subscriptions").json()["subscriptions"]
    assert any(s["kind"] == "followed_author" and s["value"] == "A1" for s in subs)
