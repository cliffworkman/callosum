"""Render a stored JATS abstract fragment as clean, safe display HTML.

Crossref abstracts are stored verbatim in ``papers.abstract`` as JATS XML fragments
(``<jats:p>``, ``<jats:title>``, ``<jats:italic>``, ``<jats:bold>``, ``<jats:sub>``,
``<jats:sup>``). This module produces a *display-only* copy for the UI; the stored value
is never touched (store raw, render structured — the same faithful-source ethos as quote
canonicalization).

Safety: output is built from a strict allowlist of attribute-free tags
(``<p> <em> <strong> <sub> <sup>``); every run of text is HTML-escaped and unknown tags
are dropped (their text is kept). The result therefore contains only markup this module
emitted — a malformed or hostile abstract cannot inject tags or attributes.

Parsing uses the stdlib ``html.parser.HTMLParser`` (no dependency), which is lenient:
unclosed/malformed tags degrade instead of raising, and entities are decoded.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser

# Source tag name (namespace prefix stripped, lower-cased) -> output allowlist tag.
_INLINE_TAGS = {
    "italic": "em",
    "i": "em",
    "em": "em",
    "bold": "strong",
    "b": "strong",
    "strong": "strong",
    "sub": "sub",
    "sup": "sup",
}
_PARAGRAPH_TAGS = {"p"}
_TITLE_TAGS = {"title"}


def _local_name(tag: str) -> str:
    """Drop any namespace prefix (``jats:p`` -> ``p``) and lower-case."""
    return tag.split(":", 1)[-1].lower()


class _AbstractCleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._paragraphs: list[str] = []
        self._buf: list[str] = []  # inline HTML of the current paragraph
        self._open: list[str] = []  # stack of open inline output tags
        self._has_para = False  # has any explicit <p> been opened?
        self._in_title = False
        self._title_parts: list[str] = []

    # -- paragraph lifecycle ------------------------------------------------
    def _flush_paragraph(self) -> None:
        for tag in reversed(self._open):  # close any inline tags left open
            self._buf.append(f"</{tag}>")
        self._open.clear()
        content = "".join(self._buf).strip()
        self._buf.clear()
        if content:
            self._paragraphs.append(f"<p>{content}</p>")

    # -- HTMLParser hooks ---------------------------------------------------
    def handle_starttag(self, tag: str, attrs: object) -> None:
        name = _local_name(tag)
        if name in _PARAGRAPH_TAGS:
            self._flush_paragraph()
            self._has_para = True
        elif name in _TITLE_TAGS:
            self._in_title = True
            self._title_parts = []
        elif name in _INLINE_TAGS:
            out = _INLINE_TAGS[name]
            self._open.append(out)
            self._buf.append(f"<{out}>")
        # any other tag: dropped (text content still flows via handle_data)

    def handle_endtag(self, tag: str) -> None:
        name = _local_name(tag)
        if name in _PARAGRAPH_TAGS:
            self._flush_paragraph()
        elif name in _TITLE_TAGS:
            self._in_title = False
            title = "".join(self._title_parts).strip()
            self._title_parts = []
            # Drop a redundant leading "Abstract" heading; keep any real title.
            if title and title.lower() != "abstract":
                self._paragraphs.append(f"<p><strong>{html.escape(title, quote=False)}</strong></p>")
        elif name in _INLINE_TAGS:
            out = _INLINE_TAGS[name]
            if out in self._open:
                # close down to (and including) the matching tag
                while self._open:
                    top = self._open.pop()
                    self._buf.append(f"</{top}>")
                    if top == out:
                        break

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        else:
            self._buf.append(html.escape(data, quote=False))

    def result(self) -> str:
        self._flush_paragraph()
        return "".join(self._paragraphs)


class _AbstractTextExtractor(HTMLParser):
    """Like _AbstractCleaner but emits PLAIN TEXT — all tags dropped (their text kept), entities
    decoded, paragraphs joined with blank lines. Used where markup must not appear: the editable
    abstract textarea + the suggest-axes term tokenizer (so JATS tag names never leak as 'terms')."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._paragraphs: list[str] = []
        self._buf: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []

    def _flush(self) -> None:
        content = " ".join("".join(self._buf).split())
        self._buf.clear()
        if content:
            self._paragraphs.append(content)

    def handle_starttag(self, tag: str, attrs: object) -> None:
        name = _local_name(tag)
        if name in _PARAGRAPH_TAGS:
            self._flush()
        elif name in _TITLE_TAGS:
            self._in_title = True
            self._title_parts = []

    def handle_endtag(self, tag: str) -> None:
        name = _local_name(tag)
        if name in _PARAGRAPH_TAGS:
            self._flush()
        elif name in _TITLE_TAGS:
            self._in_title = False
            title = " ".join("".join(self._title_parts).split())
            self._title_parts = []
            if title and title.lower() != "abstract":  # drop a redundant leading "Abstract" heading
                self._paragraphs.append(title)

    def handle_data(self, data: str) -> None:
        (self._title_parts if self._in_title else self._buf).append(data)

    def result(self) -> str:
        self._flush()
        return "\n\n".join(self._paragraphs)


def abstract_plain_text(raw: str | None) -> str | None:
    """Return the abstract as tag-free plain text (or ``None``). Pure: the stored value is untouched.

    Drops JATS/HTML markup (keeping the text), decodes entities, and joins paragraphs with blank lines —
    so neither the editable textarea nor the term tokenizer ever sees ``<jats:…>`` tag names. Lenient:
    malformed input degrades to the stripped raw rather than raising.
    """
    if not raw or not raw.strip():
        return None
    text = raw
    if "<jats:" not in text and "&lt;jats:" in text.lower():
        text = html.unescape(text)  # entity-encoded fragment → make the tags real so they're dropped
    extractor = _AbstractTextExtractor()
    try:
        extractor.feed(text)
        extractor.close()
    except Exception:
        return raw.strip()
    return extractor.result() or raw.strip()


def clean_abstract_for_display(raw: str | None) -> str | None:
    """Return display-safe allowlisted HTML for a stored abstract, or ``None``.

    Pure: the input string is never mutated and the stored column is untouched. Plain text
    (no tags) is returned wrapped in a single ``<p>``; JATS markup is mapped to the
    allowlist; malformed input degrades without raising.
    """
    if not raw or not raw.strip():
        return None
    text = raw
    # Handle a fully entity-encoded fragment (e.g. "&lt;jats:p&gt;...") by decoding once.
    if "<jats:" not in text and "&lt;jats:" in text.lower():
        text = html.unescape(text)
    cleaner = _AbstractCleaner()
    try:
        cleaner.feed(text)
        cleaner.close()
    except Exception:
        # HTMLParser is lenient, but never let display formatting crash a response:
        # fall back to escaped plain text in a single paragraph.
        return f"<p>{html.escape(raw, quote=False)}</p>"
    out = cleaner.result()
    return out or f"<p>{html.escape(raw, quote=False)}</p>"
