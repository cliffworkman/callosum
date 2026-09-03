from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.backend.summarization.verification import VerificationConfig

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "www"


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []
        self.tabs: list[dict[str, str | None]] = []
        self.panels: list[dict[str, str | None]] = []
        self.favicon: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        if tag == "button" and values.get("role") == "tab":
            self.tabs.append(values)
        if values.get("role") == "tabpanel":
            self.panels.append(values)
        if tag == "link" and values.get("rel") == "icon":
            self.favicon = values.get("href")


def _parse(path: Path) -> _PageParser:
    parser = _PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def test_how_it_works_pipeline_is_complete_and_accessible() -> None:
    page = _parse(WWW / "how-it-works.html")
    assert len(page.ids) == len(set(page.ids))
    assert len(page.tabs) == len(page.panels) == 8
    panels = {panel["id"]: panel for panel in page.panels}
    assert all("hidden" not in panel for panel in page.panels)
    for tab in page.tabs:
        assert tab.get("type") == "button"
        assert tab.get("aria-controls") in panels
        assert panels[str(tab["aria-controls"])].get("aria-labelledby") == tab.get("id")


def test_how_it_works_uses_current_verification_contract() -> None:
    html = (WWW / "how-it-works.html").read_text(encoding="utf-8")
    config = VerificationConfig()
    assert f"Retrieval ≥ {config.retrieval_threshold:.2f}" in html
    assert f"quote = {config.quote_threshold:.2f}" in html
    assert f"support ≥ {config.support_threshold:.2f}" in html
    assert f"Contradiction ≥ {config.contradiction_threshold:.2f}" in html
    assert "cross-encoder/nli-MiniLM2-L6-H768" in html
    assert "__CALLOSUM_FAVICON__" not in html


def test_website_navigation_reaches_the_page_and_reuses_the_favicon() -> None:
    how = _parse(WWW / "how-it-works.html")
    home = _parse(WWW / "index.html")
    header = (WWW / "site-header.js").read_text(encoding="utf-8")
    index = (WWW / "index.html").read_text(encoding="utf-8")
    assert 'page === "how" ? "#pipeline" : "how-it-works.html"' in header
    assert 'href="how-it-works.html">Explore the evidence pipeline' in index
    assert how.favicon == home.favicon


@pytest.mark.parametrize(
    ("href", "target"),
    [
        ("index.html", WWW / "index.html"),
        ("showcase.html#tour", WWW / "showcase.html"),
        ("demo/", ROOT / "dist-demo"),
    ],
)
def test_primary_local_destinations_exist(href: str, target: Path) -> None:
    assert href in _parse(WWW / "how-it-works.html").links
    assert target.exists()


def test_showcase_hotspots_paint_no_marker_at_narrow_widths() -> None:
    """Regression: the Showcase image map rendered a purple dot inside every hotspot below 560px.

    `@media(max-width:560px)` carried `.hotspot::after{...background:var(--accent)}`, so all 53 hotspots
    painted an accent-coloured circle over the screenshot they annotate. Portrait phones (360/390/412 CSS px)
    are under that breakpoint while the same devices in landscape (800/844/915) are over it -- which is the
    whole reason rotating the device appeared to "fix" it. Nothing in the CSS was orientation-aware.

    Hotspot geometry was never at fault and is deliberately not asserted here: it is percentage-based against
    the image box and was already correct at every width. What this pins is that hotspots stay visually
    transparent AT REST, with feedback reserved for :hover / :focus-visible.
    """
    css = (WWW / "showcase.html").read_text(encoding="utf-8")
    narrow = [block for block in css.split("@media") if block.lstrip().startswith("(max-width:560px)")]
    assert narrow, "the narrow-width breakpoint should still exist"
    rules = narrow[0]
    assert ".hotspot::after" not in rules, "a hotspot marker dot must not be reintroduced at narrow widths"
    assert ".hotspot::before" not in rules
    # The narrow breakpoint must not restyle .hotspot at all -- geometry/appearance are width-independent.
    assert ".hotspot{" not in rules

    # Intentional feedback states must survive, unconditioned by width.
    assert ".hotspot:hover,.hotspot:focus-visible{background:" in css
    assert ".hotspot:focus-visible{outline:" in css
    # The labelled fallback row remains the touch/no-hover discoverability affordance.
    assert 'class="map-fallback"' in css
