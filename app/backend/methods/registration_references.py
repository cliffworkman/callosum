"""Local extraction and normalization of registration references.

A disclosure signal says registration-related language was detected.  A reference is narrower: an
identifier or link a reader can inspect.  This module only extracts evidence; it never resolves a
provider, attaches a candidate, or judges whether the registration belongs to the paper.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from app.backend.pdf_processing.pdf_links import PdfLinkAnnotation

_OSF_DOI = re.compile(r"\b10\.17605/OSF\.IO/([A-Z0-9]+)\b", re.IGNORECASE)
_OSF_URL = re.compile(
    r"https?://(?:www\.)?osf\.io/(?:(?:registries/)([a-z0-9]{4,12})|"
    r"(?!registries(?:/|$))([a-z0-9]{4,12}))(?:/[^\s<>\]\[\)\(]*)?",
    re.I,
)
_ASPREDICTED_URL = re.compile(r"https?://(?:www\.)?aspredicted\.org/[^\s<>\]\[\)\(]+", re.I)
_ASPREDICTED_ID = re.compile(r"\bAsPredicted\b.{0,50}?(?:#|ID\s*[:#]?\s*)([A-Z0-9_-]{3,40})\b", re.I)
_NCT = re.compile(r"\bNCT\d{6,12}\b", re.I)
_PROSPERO = re.compile(r"\bCRD\d{6,20}\b", re.I)
_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_URL = re.compile(r"https?://[^\s<>\]\[]+", re.I)
_REG_CONTEXT = re.compile(
    r"pre[-\s]?regist|registered\s+(?:at|on|with|in|under)|registration|registry|trial\s+registration|"
    r"study\s+protocol|analysis\s+plan|AsPredicted|ClinicalTrials\.gov|PROSPERO",
    re.I,
)
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""


@dataclass(frozen=True)
class RegistrationReference:
    provider: str
    external_id: str
    canonical_url: str | None
    visible_text: str | None
    evidence_snippet: str | None
    page: int | None
    attachment_id: int | None
    extraction_method: str
    evidence_class: str
    explicitly_printed: bool

    def to_dict(self) -> dict:
        return asdict(self)


def extract_registration_references(
    chunks: Iterable[object], *, hyperlinks: Iterable[PdfLinkAnnotation] = ()
) -> list[RegistrationReference]:
    found: list[RegistrationReference] = []
    for chunk in chunks:
        text = str(getattr(chunk, "text", "") or _mapping_value(chunk, "text") or "")
        if not text:
            continue
        page = _int_or_none(getattr(chunk, "page_start", None) or _mapping_value(chunk, "page_start"))
        attachment_id = _int_or_none(getattr(chunk, "attachment_id", None) or _mapping_value(chunk, "attachment_id"))
        found.extend(
            _references_in_text(
                text,
                page=page,
                attachment_id=attachment_id,
                extraction_method="printed-text",
                explicitly_printed=True,
            )
        )
    for link in hyperlinks:
        context = link.nearby_text or link.visible_text or ""
        refs = _references_in_text(
            link.uri,
            page=link.page_number,
            attachment_id=None,
            extraction_method="pdf-hyperlink",
            explicitly_printed=False,
            context=context,
            visible_text=link.visible_text,
            evidence_class="exact-link-target" if link.association == "overlapping-text" else "unpaired-link-target",
        )
        found.extend(refs)
    return _deduplicate(found)


def normalize_manual_reference(value: str) -> RegistrationReference:
    """Normalize one user-supplied URL, DOI, or registry identifier; never performs egress."""
    clean = value.strip()
    if not clean:
        raise ValueError("Enter a registration URL, DOI, or identifier.")
    refs = _references_in_text(
        clean,
        page=None,
        attachment_id=None,
        extraction_method="manual",
        explicitly_printed=False,
        context="User supplied this registration reference.",
        evidence_class="user-supplied",
        allow_context_free_generic=True,
    )
    if not refs:
        raise ValueError("This does not look like a supported registration URL, DOI, or identifier.")
    return refs[0]


def _references_in_text(
    text: str,
    *,
    page: int | None,
    attachment_id: int | None,
    extraction_method: str,
    explicitly_printed: bool,
    context: str | None = None,
    visible_text: str | None = None,
    evidence_class: str = "explicit-identifier",
    allow_context_free_generic: bool = False,
) -> list[RegistrationReference]:
    refs: list[RegistrationReference] = []
    evidence_text = context or text

    for match in _OSF_DOI.finditer(text):
        guid = match.group(1).lower()
        refs.append(
            _ref(
                "osf",
                guid,
                f"https://osf.io/{guid}/",
                match,
                evidence_text,
                page,
                attachment_id,
                extraction_method,
                evidence_class,
                explicitly_printed,
                visible_text,
            )
        )
    for match in _OSF_URL.finditer(text):
        guid = (match.group(1) or match.group(2)).lower()
        refs.append(
            _ref(
                "osf",
                guid,
                f"https://osf.io/{guid}/",
                match,
                evidence_text,
                page,
                attachment_id,
                extraction_method,
                evidence_class,
                explicitly_printed,
                visible_text,
            )
        )
    for match in _ASPREDICTED_URL.finditer(text):
        url = _clean_url(match.group(0))
        external_id = _aspredicted_external_id(url)
        refs.append(
            _ref(
                "aspredicted",
                external_id,
                url,
                match,
                evidence_text,
                page,
                attachment_id,
                extraction_method,
                evidence_class,
                explicitly_printed,
                visible_text,
            )
        )
    for match in _ASPREDICTED_ID.finditer(text):
        refs.append(
            _ref(
                "aspredicted",
                match.group(1),
                None,
                match,
                evidence_text,
                page,
                attachment_id,
                extraction_method,
                evidence_class,
                explicitly_printed,
                visible_text,
            )
        )
    for match in _NCT.finditer(text):
        identifier = match.group(0).upper()
        refs.append(
            _ref(
                "clinicaltrials.gov",
                identifier,
                f"https://clinicaltrials.gov/study/{identifier}",
                match,
                evidence_text,
                page,
                attachment_id,
                extraction_method,
                evidence_class,
                explicitly_printed,
                visible_text,
            )
        )
    for match in _PROSPERO.finditer(text):
        identifier = match.group(0).upper()
        refs.append(
            _ref(
                "prospero",
                identifier,
                None,
                match,
                evidence_text,
                page,
                attachment_id,
                extraction_method,
                evidence_class,
                explicitly_printed,
                visible_text,
            )
        )

    context_allows_generic = allow_context_free_generic or bool(_REG_CONTEXT.search(evidence_text))
    if context_allows_generic:
        occupied = {(r.provider, r.external_id) for r in refs}
        for match in _DOI.finditer(text):
            doi = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            if _OSF_DOI.fullmatch(doi):
                continue
            candidate = ("doi", doi.lower())
            if candidate not in occupied:
                refs.append(
                    _ref(
                        "doi",
                        doi.lower(),
                        f"https://doi.org/{doi}",
                        match,
                        evidence_text,
                        page,
                        attachment_id,
                        extraction_method,
                        "contextual-identifier" if evidence_class == "explicit-identifier" else evidence_class,
                        explicitly_printed,
                        visible_text,
                    )
                )
        for match in _URL.finditer(text):
            url = _clean_url(match.group(0))
            if any(item.canonical_url == url for item in refs):
                continue
            host = (urlsplit(url).hostname or "").casefold()
            if host in {"osf.io", "www.osf.io", "aspredicted.org", "www.aspredicted.org"}:
                continue
            refs.append(
                _ref(
                    "url",
                    url,
                    url,
                    match,
                    evidence_text,
                    page,
                    attachment_id,
                    extraction_method,
                    "contextual-link" if evidence_class == "explicit-identifier" else evidence_class,
                    explicitly_printed,
                    visible_text,
                )
            )
    return refs


def _ref(
    provider,
    external_id,
    canonical_url,
    match,
    evidence_text,
    page,
    attachment_id,
    extraction_method,
    evidence_class,
    explicitly_printed,
    visible_text,
) -> RegistrationReference:
    return RegistrationReference(
        provider=provider,
        external_id=external_id,
        canonical_url=canonical_url,
        visible_text=visible_text or match.group(0),
        evidence_snippet=_snippet(evidence_text, match.start(), match.end()),
        page=page,
        attachment_id=attachment_id,
        extraction_method=extraction_method,
        evidence_class=evidence_class,
        explicitly_printed=explicitly_printed,
    )


def _snippet(text: str, start: int, end: int, pad: int = 100) -> str:
    if start >= len(text):
        return re.sub(r"\s+", " ", text).strip()[:300]
    return re.sub(r"\s+", " ", text[max(0, start - pad) : min(len(text), end + pad)]).strip()[:300]


def _clean_url(value: str) -> str:
    value = value.rstrip(_TRAILING_PUNCTUATION)
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _aspredicted_external_id(url: str) -> str:
    parts = urlsplit(url)
    query = dict(item.split("=", 1) for item in parts.query.split("&") if "=" in item)
    if query.get("x"):
        return query["x"]
    tail = parts.path.rstrip("/").rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0] or url


def _deduplicate(refs: list[RegistrationReference]) -> list[RegistrationReference]:
    seen: set[tuple[str, str, int | None]] = set()
    result: list[RegistrationReference] = []
    for ref in refs:
        key = (ref.provider, ref.external_id.casefold(), ref.attachment_id)
        if key not in seen:
            seen.add(key)
            result.append(ref)
    return result


def _mapping_value(value: object, key: str) -> object | None:
    try:
        return value[key]  # type: ignore[index]
    except (KeyError, TypeError):
        return None


def _int_or_none(value: object | None) -> int | None:
    return int(value) if value is not None else None
