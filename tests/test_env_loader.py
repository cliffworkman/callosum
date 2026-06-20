"""Tests for the stdlib .env loader (startup.load_local_env / _parse_dotenv).

The loader lets secrets (e.g. GOOGLE_API_KEY) live in a gitignored .env instead of being exported by
hand. Contract: fill only UNSET keys (shell wins), skip a missing file, and no-op under pytest so the
suite never picks up a developer's real keys.
"""

from __future__ import annotations

from app.backend.api.startup import _parse_dotenv, load_local_env


def test_parse_dotenv_handles_comments_quotes_and_equals():
    parsed = _parse_dotenv(
        "# a comment\n"
        "\n"
        "A=1\n"
        'B = "two"\n'
        "C='three'\n"
        "D=a=b=c\n"  # only the first '=' splits
        "novalue\n"  # no '=' → ignored
        "=novalue\n"  # empty key → ignored
    )
    assert parsed == {"A": "1", "B": "two", "C": "three", "D": "a=b=c"}


def test_load_local_env_fills_unset_only(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=fromfile\nBAR=baz\n", encoding="utf-8")
    environ = {"FOO": "fromshell"}
    load_local_env(env_file, environ=environ, skip_under_pytest=False)
    assert environ["FOO"] == "fromshell"  # an already-set (shell) value is never overridden
    assert environ["BAR"] == "baz"  # an unset key is filled from .env


def test_load_local_env_missing_file_is_noop(tmp_path):
    environ: dict[str, str] = {}
    load_local_env(tmp_path / "absent.env", environ=environ, skip_under_pytest=False)
    assert environ == {}


def test_load_local_env_skips_under_pytest(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SHOULD_NOT_LOAD=1\n", encoding="utf-8")
    environ: dict[str, str] = {}
    load_local_env(env_file, environ=environ)  # skip_under_pytest defaults True; pytest is imported
    assert environ == {}  # guarded → no-op, so the suite never ingests a real .env
