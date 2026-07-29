"""Assemble a feedback report into a local bundle + a prefilled ``mailto:`` draft (inc 265).

A submitted report becomes a folder under ``~/.callosum/feedback/`` holding a plain-Markdown
``report.md`` and, if one was attached, ``screenshot.png``. Nothing is sent from here: the caller gets
back the bundle paths, the full report text, and a ``mailto:`` URL that opens the user's own mail client
with the report already in the body. The user attaches the screenshot and presses send — so the report
leaves the machine only by an explicit human action, in a client the user can read it in first.

Boundary rules (rule #4). The report is a file we write from request data, so:
- the folder name is built **server-side** from a UTC timestamp + a sanitized slug of the title, never
  from a client-supplied path, and the resolved path is asserted to sit inside the feedback root;
- the screenshot is base64 decoded strictly, size-capped, and accepted only if its **magic bytes** are
  PNG or JPEG — the extension we write is ours, never the client's;
- every text field is length-capped by the router's pydantic model, and again here on render.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from app.backend import app_settings

FEEDBACK_KINDS = {"bug": "Bug report", "feature": "Feature request"}

TITLE_MAX_LEN = 200
BODY_MAX_LEN = 20_000
STEPS_MAX_LEN = 8_000
REPLY_TO_MAX_LEN = 254
SCREENSHOT_MAX_BYTES = 5 * 1024 * 1024  # decoded; the frontend downscales before encoding
SCREENSHOT_B64_MAX_LEN = 4 * (SCREENSHOT_MAX_BYTES // 3) + 64  # the encoded cap the router declares
# A mailto: URL is a browser/OS argument, not a document — long ones are silently truncated (or rejected)
# by some mail clients. Keep the body short and point at the full report on disk.
MAILTO_BODY_MAX_LEN = 1_500

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_DATA_URL_RE = re.compile(r"^data:image/(png|jpe?g);base64,", re.IGNORECASE)
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class FeedbackBundle:
    directory: Path
    report_path: Path
    screenshot_path: Path | None
    report_markdown: str


def feedback_root() -> Path:
    """``<settings dir>/feedback`` — beside the settings file, so ``CALLOSUM_SETTINGS_PATH`` keeps the
    suite hermetic and production writes stay outside the repo and the synced project folder."""
    return app_settings.settings_path().parent / "feedback"


def slugify(title: str) -> str:
    slug = _SLUG_STRIP_RE.sub("-", (title or "").strip().lower()).strip("-")
    return slug[:48] or "report"


def decode_screenshot(raw: str | None) -> bytes | None:
    """Decode a data-URL/base64 screenshot. Returns ``None`` when absent; raises ``ValueError`` when the
    payload is malformed, oversized, or not actually a PNG/JPEG."""
    if not raw or not raw.strip():
        return None
    payload = _DATA_URL_RE.sub("", raw.strip())
    if payload.startswith("data:"):  # some other data URL — an image is the only thing we accept
        raise ValueError("The screenshot must be a PNG or JPEG image.")
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The screenshot could not be decoded.") from exc
    if len(data) > SCREENSHOT_MAX_BYTES:
        raise ValueError(f"The screenshot is larger than {SCREENSHOT_MAX_BYTES // (1024 * 1024)} MB.")
    if not (data.startswith(_PNG_MAGIC) or data.startswith(_JPEG_MAGIC)):
        raise ValueError("The screenshot must be a PNG or JPEG image.")
    return data


def render_report(
    *,
    kind: str,
    title: str,
    body: str,
    steps: str | None,
    reply_to: str | None,
    diagnostics: dict[str, str] | None,
    client_diagnostics: dict[str, str] | None,
    has_screenshot: bool,
    submitted_at: datetime | None = None,
) -> str:
    """Render the report as plain Markdown — the same text the user reads, the file we write, and the
    body of the email draft. One rendering, so there is no version of the report the user didn't see."""
    label = FEEDBACK_KINDS.get(kind, FEEDBACK_KINDS["bug"])
    stamp = (submitted_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# [{label}] {title.strip()[:TITLE_MAX_LEN]}",
        "",
        f"- **Type:** {label}",
        f"- **Submitted:** {stamp}",
    ]
    if reply_to:
        lines.append(f"- **Reply to:** {reply_to.strip()[:REPLY_TO_MAX_LEN]}")
    lines.append(f"- **Screenshot attached:** {'yes (screenshot.png)' if has_screenshot else 'no'}")
    lines += [
        "",
        "## What happened" if kind == "bug" else "## What you'd like",
        "",
        body.strip()[:BODY_MAX_LEN] or "_(not described)_",
    ]
    if steps and steps.strip():
        lines += ["", "## Steps to reproduce", "", steps.strip()[:STEPS_MAX_LEN]]
    if diagnostics or client_diagnostics:
        lines += ["", "## Diagnostics", "", "| key | value |", "| --- | --- |"]
        for key, value in (diagnostics or {}).items():
            lines.append(f"| {key} | {_cell(value)} |")
        for key, value in (client_diagnostics or {}).items():
            lines.append(f"| client.{key} | {_cell(value)} |")
    lines += [
        "",
        "---",
        "",
        "_Generated by callosum's in-app reporter. It was assembled on this machine and sent only when "
        "the sender pressed send — callosum itself transmits nothing._",
        "",
    ]
    return "\n".join(lines)


def write_bundle(
    *,
    kind: str,
    title: str,
    report_markdown: str,
    screenshot: bytes | None,
    now: datetime | None = None,
) -> FeedbackBundle:
    """Write ``report.md`` (+ ``screenshot.png``) into a fresh timestamped folder under the feedback root."""
    root = feedback_root().resolve()
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    prefix = "bug" if kind == "bug" else "feature"
    base = f"{stamp}_{prefix}_{slugify(title)}"
    directory = root / base
    suffix = 2
    while directory.exists():  # two reports in the same second
        directory = root / f"{base}-{suffix}"
        suffix += 1
    directory = _contained(root, directory)
    directory.mkdir(parents=True, exist_ok=False)

    report_path = _contained(root, directory / "report.md")
    report_path.write_text(report_markdown, encoding="utf-8")

    screenshot_path: Path | None = None
    if screenshot is not None:
        # OUR extension, from OUR magic-byte check — never a client-supplied filename.
        name = "screenshot.png" if screenshot.startswith(_PNG_MAGIC) else "screenshot.jpg"
        screenshot_path = _contained(root, directory / name)
        screenshot_path.write_bytes(screenshot)

    return FeedbackBundle(
        directory=directory,
        report_path=report_path,
        screenshot_path=screenshot_path,
        report_markdown=report_markdown,
    )


def build_mailto_url(
    *,
    destination: str,
    kind: str,
    title: str,
    report_markdown: str,
    directory: Path,
    has_screenshot: bool,
) -> str | None:
    """The prefilled draft. ``None`` when no destination is set — the bundle is still written, so an
    unset address costs the user their notes only if we silently dropped them, and we don't."""
    if not destination.strip():
        return None
    label = FEEDBACK_KINDS.get(kind, FEEDBACK_KINDS["bug"])
    subject = f"[callosum] [{label}] {title.strip()[:TITLE_MAX_LEN]}"
    body = report_markdown
    if len(body) > MAILTO_BODY_MAX_LEN:
        body = body[:MAILTO_BODY_MAX_LEN].rstrip() + "\n\n… (truncated — the full report is in the folder below)"
    tail = ["", "", f"Full report: {directory / 'report.md'}"]
    if has_screenshot:
        tail.append(f"Please attach the screenshot from: {directory}")
    full_body = body + "\n".join(tail)
    return f"mailto:{quote(destination.strip())}?subject={quote(subject)}&body={quote(full_body)}"


def _cell(value: str) -> str:
    """Keep a diagnostic value inside its table cell (a stray pipe would forge a column)."""
    return str(value).replace("|", "\\|")


def _contained(root: Path, path: Path) -> Path:
    """Defense in depth: every write target must resolve inside the feedback root."""
    resolved = (path if path.is_absolute() else root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("Refusing to write outside the feedback folder.")
    return resolved
