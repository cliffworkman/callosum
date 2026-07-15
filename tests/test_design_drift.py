from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / ".claude" / "DESIGN.md"
STYLES = ROOT / "app" / "frontend" / "styles.css"
FRONTEND_JS = ROOT / "app" / "frontend" / "js"

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
COMMENT_RE = re.compile(r"/\*.*?\*/")


def _strip_inline_comment(line: str) -> str:
    return COMMENT_RE.sub("", line)


def test_design_dictionary_exists_and_names_the_enforced_rules() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    for required in (
        "Use a token; never re-type a raw hex",
        "New buttons use",
        "Semantics of color are fixed",
        "Type roles are fixed",
        "Coming soon",
    ):
        assert required in text


def test_chrome_css_does_not_introduce_raw_hex_colors_outside_documented_exceptions() -> None:
    css = STYLES.read_text(encoding="utf-8").splitlines()
    allowed_selectors = (
        ":root",
        ".skel .bar",
        ".errbox code",
        ".textLayer",
        ".pdf-page",
        ".pdf-user-highlight",
        ".pdf-toast",
        ".pdf-region-note",
        ".page-caret",
        ".copy-toast",
    )
    violations: list[str] = []
    in_block_comment = False
    current_selector = ""

    for line_no, raw_line in enumerate(css, 1):
        if "/*" in raw_line:
            in_block_comment = True
        line = _strip_inline_comment(raw_line).strip()
        if in_block_comment and "*/" not in raw_line:
            continue
        if "*/" in raw_line:
            in_block_comment = False
            continue
        if "{" in line:
            current_selector = line.split("{", 1)[0].strip()
        if "}" in line:
            current_selector = ""
        if not HEX_RE.search(line):
            continue
        if (
            line.startswith("--")
            or line.startswith("*")
            or any(selector in line for selector in allowed_selectors)
            or any(selector in current_selector for selector in allowed_selectors)
        ):
            continue
        violations.append(f"{line_no}: {raw_line.strip()}")

    assert violations == []


def test_inline_styles_do_not_add_raw_hex_chrome_colors() -> None:
    violations: list[str] = []
    for path in sorted(FRONTEND_JS.glob("*.jsx")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"style=\{\{[^}]*#[0-9a-fA-F]{3,8}\b[^}]*\}\}", text):
            violations.append(f"{path.relative_to(ROOT)}: {match.group(0)}")

    assert violations == []


def test_funding_discovery_type_accents_use_design_tokens() -> None:
    css = STYLES.read_text(encoding="utf-8")
    assert ".funding-card.scheme { border-left: 4px solid var(--accent); }" in css
    assert ".funding-card.prospect { border-left: 4px solid var(--verified); }" in css
    assert "#7c3aed" not in css
    assert "#24845a" not in css
