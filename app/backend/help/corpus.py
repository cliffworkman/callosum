"""Load the shipped help content (``help_content.md``) into structured, safely-rendered sections.

The corpus is authored as markdown where each section begins with an explicit-id marker
``<!-- section: <id> -->`` followed by a ``## Title`` heading and a markdown body. We parse it into
sections, each carrying a **stable id** (independent of the heading text), a title, a SAFE
allowlisted-HTML body (for the in-app modal, rendered with ``dangerouslySetInnerHTML``), and a plain-text
body (for the help-assistant prompt — consumed in a later increment).

The HTML is escaped + tag-allowlisted (same safety posture as
``app/backend/metadata/abstract_display.py::clean_abstract_for_display``) because it is served to the
frontend. The markdown renderer supports a small subset on purpose, so **no new dependency** is needed:
paragraphs, ``- ``/``* `` bullet lists, ``### `` sub-headings, ``**bold**``, ``*italic*``, ``` `code` ```,
and ``[text](url)`` links restricted to http(s)/in-page-``#`` schemes. Anything else renders as escaped
text. (If the corpus ever outgrows simple markdown, swap in a real renderer — the parse boundary is here.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path

CONTENT_PATH = Path(__file__).with_name("help_content.md")

_SECTION_MARKER = re.compile(r"^<!--\s*section:\s*([a-z0-9][a-z0-9-]*)\s*-->\s*$", re.MULTILINE)
_HEADING = re.compile(r"^##\s+(.*\S)\s*$")
_SUBHEADING = re.compile(r"^###\s+(.*\S)\s*$")
_BULLET = re.compile(r"^[-*]\s+(.*\S)\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)")
_CODE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class HelpSection:
    id: str
    title: str
    html: str
    text: str


@lru_cache(maxsize=1)
def load_help_corpus() -> tuple[HelpSection, ...]:
    """Parse the shipped help_content.md into sections (cached; the file is static at runtime)."""
    return tuple(parse_help_sections(CONTENT_PATH.read_text(encoding="utf-8")))


def help_corpus_prompt() -> str:
    """The whole corpus stuffed for the help assistant (``[id] Title`` + plain text). Consumed in inc 60."""
    return "\n\n".join(f"[{s.id}] {s.title}\n{s.text}" for s in load_help_corpus())


def parse_help_sections(raw: str) -> list[HelpSection]:
    """Split the marker-delimited markdown into sections (pure; used directly by tests)."""
    markers = list(_SECTION_MARKER.finditer(raw))
    sections: list[HelpSection] = []
    seen: set[str] = set()
    for index, marker in enumerate(markers):
        section_id = marker.group(1)
        if section_id in seen:
            raise ValueError(f"duplicate help section id: {section_id}")
        seen.add(section_id)
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(raw)
        title, body = _split_title(raw[start:end].strip("\n"))
        sections.append(HelpSection(id=section_id, title=title, html=render_html(body), text=render_text(body)))
    return sections


def _split_title(block: str) -> tuple[str, str]:
    lines = block.splitlines()
    title = "Untitled"
    body_start = 0
    for index, line in enumerate(lines):
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(1).strip()
            body_start = index + 1
            break
    return title, "\n".join(lines[body_start:]).strip("\n")


def render_html(body: str) -> str:
    """Render the small markdown subset to escaped, allowlisted HTML."""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    def flush_list() -> None:
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ul>")
            items.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_para()
            flush_list()
            continue
        subheading = _SUBHEADING.match(stripped)
        bullet = _BULLET.match(stripped)
        if subheading:
            flush_para()
            flush_list()
            out.append(f"<h3>{_inline(subheading.group(1))}</h3>")
        elif bullet:
            flush_para()
            items.append(bullet.group(1))
        else:
            flush_list()
            para.append(stripped)
    flush_para()
    flush_list()
    return "".join(out)


def render_text(body: str) -> str:
    """Strip the markdown to readable plain text (for the help-assistant prompt)."""
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        subheading = _SUBHEADING.match(stripped)
        if subheading:
            stripped = subheading.group(1)
        else:
            bullet = _BULLET.match(stripped)
            if bullet:
                stripped = "- " + bullet.group(1)
        stripped = _LINK.sub(r"\1", stripped)
        stripped = _BOLD.sub(r"\1", stripped)
        stripped = _ITALIC.sub(r"\1", stripped)
        stripped = _CODE.sub(r"\1", stripped)
        lines.append(stripped)
    return "\n".join(lines)


def _inline(text: str) -> str:
    """Escape text, then apply the inline markdown subset to the escaped string (markers survive escaping)."""
    out = escape(text, quote=True)
    out = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    out = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    out = _ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", out)
    out = _LINK.sub(_render_link, out)
    return out


def _render_link(match: re.Match) -> str:
    label, url = match.group(1), match.group(2).strip()
    # `url` is already HTML-escaped (the whole run was escaped); the scheme prefix has no escaped chars,
    # so this check is safe. Drop any other scheme (javascript:, data:, …) — keep the visible label.
    if not url.startswith(("http://", "https://", "#")):
        return label
    external = ' target="_blank" rel="noopener noreferrer"' if url.startswith("http") else ""
    return f'<a href="{url}"{external}>{label}</a>'
