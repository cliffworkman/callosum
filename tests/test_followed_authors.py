"""Followed authors — the follow/unfollow primitive (backlog #29, inc 454; consolidated into Discover -> Feed
2026-08-27, dropping the standalone tab's gap-candidate view -- see test_feed.py for the Suggest-modal Author
tab's `suggest_authors_to_follow` coverage)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.followed_author_repo import add_followed_author
from app.backend.persistence.profile_repo import dismiss_gap, dismissed_gaps


class _FakeAuthorClient:
    """Mirrors OpenAlexAuthorClient's shape; records every call for zero-egress assertions."""

    def __init__(self, resolved=None):
        self.calls: list[tuple[str, tuple]] = []
        self.resolved = resolved or {}  # keyed by (orcid, name)

    def resolve_author(self, conn, *, orcid=None, name=None):
        self.calls.append(("resolve_author", (orcid, name)))
        return self.resolved.get((orcid, name))


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


def test_ordinary_reads_never_egress(temp_db_url):
    author_client = _FakeAuthorClient()
    app = create_app(db_url=temp_db_url, openalex_author_client=author_client)
    client = TestClient(app)
    client.get("/followed-authors")
    client.get("/followed-authors")
    assert author_client.calls == []  # plain GETs never touch the author client


def test_dismiss_gap_is_the_shared_gaps_dismissal_list(temp_db_url):
    """The dismissal list this tab used to feed (Add/Dismiss) is gone, but `dismiss_gap`/`dismissed_gaps`
    themselves are still gap-finder's own shared primitive -- exercised directly here now that this file no
    longer drives them through a followed-authors endpoint."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert dismissed_gaps(conn) == set()
        dismiss_gap(conn, "10.9/direct")
        assert dismissed_gaps(conn) == {"10.9/direct"}
    engine.dispose()


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
    invalid_orcid = client.post("/followed-authors", json={"orcid": "0000-0002-3521-7708"})
    assert invalid_orcid.status_code == 422


def test_unfollow_is_idempotent(temp_db_url):
    app = create_app(db_url=temp_db_url, openalex_author_client=_FakeAuthorClient())
    client = TestClient(app)
    client.post("/followed-authors", json={"author_id": "A1", "display_name": "A"})
    assert client.delete("/followed-authors/A1").status_code == 204
    assert client.delete("/followed-authors/A1").status_code == 204  # already gone -- still 204, not 404
    assert client.get("/followed-authors").json() == []


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
