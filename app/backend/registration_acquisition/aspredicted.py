from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import parse_qs, urljoin, urlsplit

import fitz
import httpx

from app.backend.registration_acquisition.domain import AcquiredRegistration, RegistrationAcquisitionError

MAX_ASPREDICTED_HTML_BYTES = 2 * 1024 * 1024
MAX_ASPREDICTED_PDF_BYTES = 80 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_QUESTIONS = {
    1: "Have any data been collected for this study already?",
    2: "What's the main question being asked or hypothesis being tested in this study?",
    3: "Describe the key dependent variable(s) specifying how they will be measured.",
    4: "How many and which conditions will participants be assigned to?",
    5: "Specify exactly which analyses you will conduct to examine the main question/hypothesis.",
    6: "Describe exactly how outliers will be defined and handled, and your precise rule(s) for excluding observations.",
    7: "How many observations will be collected or what will determine sample size?",
    8: "Anything else you would like to pre-register?",
}


class AsPredictedFetcher(Protocol):
    def __call__(self, url: str, *, max_bytes: int, accepted_types: set[str]) -> tuple[bytes, str, str]: ...


class AsPredictedRegistrationAcquirer:
    id = "aspredicted"

    def __init__(self, fetch: AsPredictedFetcher | None = None) -> None:
        self._fetch = fetch or fetch_aspredicted

    def acquire(self, link: dict) -> AcquiredRegistration:
        external_id = str(link["external_id"])
        if not _ID.fullmatch(external_id):
            raise RegistrationAcquisitionError("The confirmed AsPredicted identifier is not valid.")
        verification_url = str(link.get("canonical_url") or f"https://aspredicted.org/blind.php?x={external_id}")
        _validate_aspredicted_url(verification_url)
        if urlsplit(verification_url).path.casefold().endswith(".pdf"):
            pdf_url = verification_url
        else:
            body, resolved_url, _ = self._fetch(
                verification_url,
                max_bytes=MAX_ASPREDICTED_HTML_BYTES,
                accepted_types={"text/html"},
            )
            parser = _PdfLinkParser(resolved_url)
            parser.feed(body.decode("utf-8", errors="replace"))
            parser.close()
            if not parser.pdf_urls:
                raise RegistrationAcquisitionError(
                    "AsPredicted did not expose a public timestamped PDF for this verification identifier."
                )
            pdf_url = parser.pdf_urls[0]
        pdf_bytes, resolved_pdf_url, _ = self._fetch(
            pdf_url,
            max_bytes=MAX_ASPREDICTED_PDF_BYTES,
            accepted_types={"application/pdf", "application/octet-stream"},
        )
        if not pdf_bytes.startswith(b"%PDF-"):
            raise RegistrationAcquisitionError("AsPredicted returned non-PDF content for the registration artifact.")
        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
            if document.page_count < 1:
                raise ValueError("no pages")
            text = "\n".join(page.get_text("text") for page in document)
            page_count = document.page_count
            document.close()
        except Exception as exc:
            raise RegistrationAcquisitionError(f"The AsPredicted PDF could not be opened: {exc}") from exc
        questions = _parse_questions(text)
        structured = {
            "format": "callosum-registration-v1",
            "provider": "aspredicted",
            "external_id": external_id,
            "canonical_url": resolved_pdf_url,
            "verification_url": verification_url,
            "title": _parse_title(text),
            "registered_at": _parse_registered_at(text),
            "registration_status": "public",
            "schema": {
                "id": None,
                "name": "AsPredicted",
                "version": _match(text, r"Version of AsPredicted Questions:\s*([^\n]+)"),
            },
            "questions": questions,
        }
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        return AcquiredRegistration(
            provider="aspredicted",
            external_id=external_id,
            canonical_url=resolved_pdf_url,
            content_hash=digest,
            registered_at=structured["registered_at"],
            registration_status="public",
            schema_name="AsPredicted",
            schema_version=structured["schema"]["version"],
            structured=structured,
            rendered_text=text,
            source_metadata={
                "verification_url": verification_url,
                "resolved_pdf_url": resolved_pdf_url,
                "page_count": page_count,
                "content_type": "application/pdf",
            },
            file_bytes=pdf_bytes,
            file_suffix=".pdf",
            content_type="application/pdf",
        )


def fetch_aspredicted(url: str, *, max_bytes: int, accepted_types: set[str]) -> tuple[bytes, str, str]:
    current = url
    with httpx.Client(timeout=30.0, follow_redirects=False, headers={"User-Agent": "Callosum/0.1"}) as client:
        for _ in range(6):
            _validate_aspredicted_url(current)
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        target = response.headers.get("location")
                        if not target:
                            raise RegistrationAcquisitionError("AsPredicted returned a redirect without a target.")
                        current = urljoin(current, target)
                        continue
                    if response.status_code != 200:
                        raise RegistrationAcquisitionError(f"AsPredicted returned HTTP {response.status_code}.")
                    content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
                    if content_type not in accepted_types:
                        raise RegistrationAcquisitionError(
                            f"AsPredicted returned unexpected content type {content_type or 'unknown'}."
                        )
                    body = bytearray()
                    for block in response.iter_bytes():
                        body.extend(block)
                        if len(body) > max_bytes:
                            raise RegistrationAcquisitionError("AsPredicted response exceeded the download limit.")
                    return bytes(body), current, content_type
            except httpx.HTTPError as exc:
                raise RegistrationAcquisitionError(f"AsPredicted request failed: {type(exc).__name__}") from exc
    raise RegistrationAcquisitionError("AsPredicted returned too many redirects.")


def _validate_aspredicted_url(url: str) -> None:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise RegistrationAcquisitionError("AsPredicted URL contains an invalid port.") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"aspredicted.org", "www.aspredicted.org"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise RegistrationAcquisitionError("AsPredicted URL is outside the supported public provider origin.")
    if parsed.path.casefold() == "/blind.php":
        values = parse_qs(parsed.query).get("x") or []
        if len(values) != 1 or not _ID.fullmatch(values[0]):
            raise RegistrationAcquisitionError("AsPredicted verification URL has an invalid identifier.")
    elif not parsed.path.casefold().endswith(".pdf"):
        raise RegistrationAcquisitionError("AsPredicted URL is not a supported verification or PDF path.")


class _PdfLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.pdf_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a":
            return
        href = next((value for key, value in attrs if key.casefold() == "href"), None)
        if not href:
            return
        candidate = urljoin(self.base_url, href)
        if urlsplit(candidate).path.casefold().endswith(".pdf"):
            try:
                _validate_aspredicted_url(candidate)
            except RegistrationAcquisitionError:
                return
            if candidate not in self.pdf_urls:
                self.pdf_urls.append(candidate)


def _parse_questions(text: str) -> list[dict]:
    starts = list(re.finditer(r"(?m)^\s*([1-8])\)\s*", text))
    questions = []
    for index, match in enumerate(starts):
        number = int(match.group(1))
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        section = text[match.end() : end].strip()
        label = _QUESTIONS[number]
        if section.casefold().startswith(label.casefold()):
            section = section[len(label) :].strip()
        questions.append(
            {
                "response_key": f"aspredicted-{number}",
                "question_block_id": None,
                "question_group_id": None,
                "label": label,
                "section": "AsPredicted questions",
                "answer": section,
                "answer_order": len(questions),
                "input_type": "pdf-text",
                "required": True,
            }
        )
    return questions


def _parse_title(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if "aspredicted" in line.casefold() and index + 1 < len(lines):
            candidate = lines[index + 1].strip(" '#")
            if candidate and not candidate.casefold().startswith(("created:", "public:", "author")):
                return candidate
    return None


def _parse_registered_at(text: str) -> str | None:
    return _match(text, r"(?:Pre-registered on|Created:)\s*([^\n]+)")


def _match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.I)
    return match.group(1).strip() if match else None
