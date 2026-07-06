"""OpenURL 1.0 (Z39.88-2004) link builder — the institutional link-resolver hand-off (inc 263).

Deterministic, local, **NO network**. callosum turns a paper's bibliographic metadata into an OpenURL query and
hands it to the user's institution's **own official** link resolver (opened in the *user's* browser). callosum
never fetches the resolver, never handles credentials, never scrapes — it is a *link-builder*. This is the
free-and-legal hand-off for the case where the OA cascade misses; the credentialed "browser connector" stays the
**deferred, Penn-counsel-gated** lane (see `.claude/docs/future-tracks-import/…_acquisitiondeferred.md`) and is
NOT reachable from here.

OpenURL / SFX lineage (credit-the-lineage): Van de Sompel & Beit-Arie (2001), "Open Linking in the Scholarly
Information Environment Using the OpenURL Framework," *D-Lib* 7(3), doi:10.1045/march2001-vandesompel; the format
is NISO Z39.88-2004.
"""

from __future__ import annotations

from urllib.parse import urlencode, urlsplit

RESOLVER_BASE_MAX_LEN = 500

# CSL `type` → OpenURL KEV metadata-format + genre. Journal article is the default (covers most papers).
_FMT_JOURNAL = "info:ofi/fmt:kev:mtx:journal"
_FMT_BOOK = "info:ofi/fmt:kev:mtx:book"
_FMT_DISSERTATION = "info:ofi/fmt:kev:mtx:dissertation"
_PAGE_SEPARATORS = ("-", "–", "—")  # hyphen / en-dash / em-dash


def resolver_base_valid(url: str | None) -> bool:
    """True iff ``url`` is a plausible resolver base: an http/https URL with a host, within the length cap. The
    user configures this once (their library's published link-resolver base); callosum only ever *opens* it in
    the user's browser, so this is a shape check, not a trust decision."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url or len(url) > RESOLVER_BASE_MAX_LEN:
        return False
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _first_author_names(csl: dict) -> tuple[str | None, str | None]:
    authors = csl.get("author")
    if isinstance(authors, list) and authors and isinstance(authors[0], dict):
        a = authors[0]
        return (a.get("family") or None), (a.get("given") or None)
    return None, None


def _issued_year(csl: dict) -> str | None:
    issued = csl.get("issued")
    if isinstance(issued, dict):
        parts = issued.get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return None


def _pages(csl: dict) -> tuple[str | None, str | None]:
    page = csl.get("page")
    if isinstance(page, str) and page.strip():
        page = page.strip()
        for sep in _PAGE_SEPARATORS:
            if sep in page:
                start, _, end = page.partition(sep)
                return (start.strip() or None), (end.strip() or None)
        return page, None
    return None, None


def _fmt_and_genre(csl_type: str | None) -> tuple[str, str]:
    t = (csl_type or "").lower()
    if t in ("book", "monograph"):
        return _FMT_BOOK, "book"
    if t in ("chapter", "book-chapter"):
        return _FMT_BOOK, "bookitem"
    if t in ("thesis", "dissertation"):
        return _FMT_DISSERTATION, "dissertation"
    return _FMT_JOURNAL, "article"


def _first_str(value) -> str | None:
    """A single string from a CSL field that may be a scalar or a list (ISSN/ISBN are often lists)."""
    if isinstance(value, list):
        value = value[0] if value else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def build_openurl(resolver_base: str, csl_json: dict | None, *, doi: str | None = None) -> str | None:
    """Build an institution link-resolver URL (OpenURL 1.0 KEV) for a paper, or ``None`` if there is not enough
    metadata (no DOI and no title) to resolve — an honest "can't build", never a guessed link. Deterministic; no
    network. The returned URL is for the *user's browser* to open; callosum never fetches it."""
    csl = csl_json if isinstance(csl_json, dict) else {}
    doi = (doi or csl.get("DOI") or csl.get("doi") or "").strip() or None
    title = _first_str(csl.get("title"))
    if not doi and not title:
        return None
    if not resolver_base_valid(resolver_base):
        return None

    fmt, genre = _fmt_and_genre(csl.get("type"))
    params: list[tuple[str, str]] = [
        ("url_ver", "Z39.88-2004"),
        ("ctx_ver", "Z39.88-2004"),
        ("rft_val_fmt", fmt),
        ("rfr_id", "info:sid/callosum"),  # polite referrer id — identifies the request's origin to the resolver
        ("rft.genre", genre),
    ]
    if doi:
        params.append(("rft_id", f"info:doi/{doi}"))
    if title:
        params.append(("rft.atitle", title))
    container = _first_str(csl.get("container-title"))
    if container:
        params.append(("rft.jtitle" if genre == "article" else "rft.btitle", container))
    issn = _first_str(csl.get("ISSN"))
    if issn:
        params.append(("rft.issn", issn))
    isbn = _first_str(csl.get("ISBN"))
    if isbn:
        params.append(("rft.isbn", isbn))
    for key, field in (("rft.volume", "volume"), ("rft.issue", "issue")):
        val = csl.get(field)
        if val not in (None, ""):
            params.append((key, str(val)))
    spage, epage = _pages(csl)
    if spage:
        params.append(("rft.spage", spage))
    if epage:
        params.append(("rft.epage", epage))
    year = _issued_year(csl)
    if year:
        params.append(("rft.date", year))
    aulast, aufirst = _first_author_names(csl)
    if aulast:
        params.append(("rft.aulast", aulast))
    if aufirst:
        params.append(("rft.aufirst", aufirst))

    sep = "&" if urlsplit(resolver_base).query else "?"
    return f"{resolver_base}{sep}{urlencode(params)}"
