"""Candidate-cascade acquisition (backlog #59): a 403/404 on one candidate must not terminate acquisition
when other legitimate candidates remain. Hermetic — a fake registry of fake resolvers + a fake download."""

from __future__ import annotations

from pathlib import Path

from app.backend.acquisition.acquire import (
    ACQUIRED,
    CANDIDATES_EXHAUSTED,
    NO_CANDIDATE,
    acquire_first_working,
)
from app.backend.acquisition.fetch import OaFetchError
from app.backend.acquisition.registry import OaLocation, PaperRef


def _loc(url: str, *, source: str = "openalex", color: str = "gold", version: str = "vor") -> OaLocation:
    return OaLocation(pdf_url=url, oa_color=color, version=version, source=source)


class _FakeResolver:
    def __init__(self, location: OaLocation | None):
        self._location = location
        self.calls = 0

    def resolve(self, conn, ref):
        self.calls += 1
        return self._location


class _FakeRegistry:
    def __init__(self, *resolvers: _FakeResolver):
        self._resolvers = resolvers

    def resolvers(self):
        return self._resolvers


class _NullEngine:
    """`acquire_first_working` only uses `engine.begin()` as a context manager around each resolve; the fake
    resolvers ignore the connection, so a no-op context manager is all that's needed (no real DB)."""

    def begin(self):
        class _Ctx:
            def __enter__(self):
                return None

            def __exit__(self, *a):
                return False

        return _Ctx()


class _RecordingDownload:
    """Fails for URLs in ``fail`` (with the given OaFetchError), succeeds otherwise — recording every attempt
    and every temp file it 'creates' so a test can prove no stray artifacts survive."""

    def __init__(self, fail: dict[str, OaFetchError] | None = None, tmp_root: Path | None = None):
        self.fail = fail or {}
        self.tmp_root = tmp_root
        self.attempts: list[str] = []
        self.created: list[Path] = []

    def __call__(self, location: OaLocation) -> Path:
        self.attempts.append(location.pdf_url)
        if location.pdf_url in self.fail:
            raise self.fail[location.pdf_url]
        # Simulate download_oa_pdf's contract: a temp file exists ONLY on success.
        p = (self.tmp_root or Path(".")) / f"ok-{len(self.created)}.pdf"
        if self.tmp_root is not None:
            p.write_bytes(b"%PDF-1.4 fake")
        self.created.append(p)
        return p


_REF = PaperRef(doi="10.1/x")


def test_403_on_first_candidate_falls_through_to_a_working_one():
    good = _loc("https://oa.example/good.pdf", source="arxiv")
    reg = _FakeRegistry(
        _FakeResolver(_loc("https://oa.example/bad.pdf", source="openalex")),
        _FakeResolver(good),
    )
    dl = _RecordingDownload(
        fail={"https://oa.example/bad.pdf": OaFetchError("HTTP 403", reason_code="http_error", http_status=403)}
    )

    outcome = acquire_first_working(_NullEngine(), reg, _REF, download=dl)

    assert outcome.reason_code == ACQUIRED and outcome.location is good
    assert outcome.candidates_tried == 2 and len(outcome.failures) == 1
    assert outcome.failures[0].source == "openalex" and outcome.failures[0].http_status == 403
    assert dl.attempts == ["https://oa.example/bad.pdf", "https://oa.example/good.pdf"]


def test_all_candidates_403_404_is_a_structured_exhausted_result():
    reg = _FakeRegistry(
        _FakeResolver(_loc("https://oa.example/a.pdf", source="openalex")),
        _FakeResolver(_loc("https://oa.example/b.pdf", source="crossref")),
    )
    dl = _RecordingDownload(
        fail={
            "https://oa.example/a.pdf": OaFetchError("HTTP 403", reason_code="http_error", http_status=403),
            "https://oa.example/b.pdf": OaFetchError("HTTP 404", reason_code="http_error", http_status=404),
        }
    )

    outcome = acquire_first_working(_NullEngine(), reg, _REF, download=dl)

    assert outcome.reason_code == CANDIDATES_EXHAUSTED  # NOT no_candidate, NOT an opaque error
    assert outcome.candidates_tried == 2 and outcome.location is None and outcome.temp_path is None
    assert [f.http_status for f in outcome.failures] == [403, 404]
    detail = outcome.human_detail()
    assert "404" in detail and "crossref" in detail  # the last failure is surfaced, structured


def test_no_candidate_at_all_is_distinct_from_exhausted():
    reg = _FakeRegistry(_FakeResolver(None), _FakeResolver(None))
    outcome = acquire_first_working(_NullEngine(), reg, _REF, download=_RecordingDownload())
    assert outcome.reason_code == NO_CANDIDATE and outcome.candidates_tried == 0


def test_duplicate_candidate_url_is_fetched_only_once():
    dup = "https://oa.example/same.pdf"
    reg = _FakeRegistry(
        _FakeResolver(_loc(dup, source="openalex")),
        _FakeResolver(_loc(dup, source="crossref")),  # same URL a prior resolver already tried
        _FakeResolver(_loc("https://oa.example/other.pdf", source="arxiv")),
    )
    dl = _RecordingDownload(fail={dup: OaFetchError("HTTP 403", reason_code="http_error", http_status=403)})

    outcome = acquire_first_working(_NullEngine(), reg, _REF, download=dl)

    assert dl.attempts == [dup, "https://oa.example/other.pdf"]  # the known-bad URL is never re-fetched
    assert outcome.reason_code == ACQUIRED and outcome.candidates_tried == 2


def test_resolver_priority_is_preserved_first_hit_tried_first():
    first = _loc("https://oa.example/first.pdf", source="openalex")
    reg = _FakeRegistry(_FakeResolver(first), _FakeResolver(_loc("https://oa.example/second.pdf", source="arxiv")))
    dl = _RecordingDownload()  # first candidate downloads fine

    outcome = acquire_first_working(_NullEngine(), reg, _REF, download=dl)

    assert outcome.location is first and outcome.candidates_tried == 1
    assert dl.attempts == [
        "https://oa.example/first.pdf"
    ]  # later resolvers never consulted (lazy, priority-preserving)


def test_unexpected_exception_is_not_swallowed_into_exhaustion():
    reg = _FakeRegistry(_FakeResolver(_loc("https://oa.example/x.pdf")))

    def _boom(location):
        raise RuntimeError("unexpected bug")

    try:
        acquire_first_working(_NullEngine(), reg, _REF, download=_boom)
    except RuntimeError as exc:
        assert str(exc) == "unexpected bug"  # propagates — never reclassified as candidates_exhausted
    else:
        raise AssertionError("a non-OaFetchError must propagate, not be swallowed")


def test_failed_attempts_leave_no_temp_artifacts_only_the_success_survives(tmp_path):
    good = _loc("https://oa.example/good.pdf", source="arxiv")
    reg = _FakeRegistry(_FakeResolver(_loc("https://oa.example/bad.pdf", source="openalex")), _FakeResolver(good))
    dl = _RecordingDownload(
        fail={"https://oa.example/bad.pdf": OaFetchError("HTTP 403", reason_code="http_error", http_status=403)},
        tmp_root=tmp_path,
    )

    outcome = acquire_first_working(_NullEngine(), reg, _REF, download=dl)

    # The failed candidate produced NO temp file (download raised before writing); exactly one file exists.
    survivors = list(tmp_path.glob("*.pdf"))
    assert len(survivors) == 1 and survivors[0] == outcome.temp_path
