from __future__ import annotations

from app.backend.metadata.abstract_display import abstract_plain_text, clean_abstract_for_display

# Real Crossref JATS fragments (user-supplied), used verbatim.
HBM = (
    "<jats:title>Abstract</jats:title><jats:p>Resting‐state functional connectivity "
    "alterations have been demonstrated in Alzheimer's disease (AD) and mild cognitive "
    "impairment (MCI) before the observation of AD neuropathology, but mechanisms driving "
    "these changes are not well understood. The current study investigated the relationship "
    "between serotonin transporter availability (SERT) and brain network functional "
    "connectivity in MCI. These results suggest that a serotonergic mechanism may underlie "
    "changes in brain functional connectivity in MCI. <jats:italic>Hum Brain Mapp "
    "38:3391–3401, 2017</jats:italic>. © <jats:bold>2017 Wiley Periodicals, "
    "Inc.</jats:bold></jats:p>"
)
ALVES = (
    "<jats:p>When judging whether someone is trustworthy, people rely on the perceptual "
    "typicality of a person’s face. We tested whether a more general "
    "typical-is-trustworthy heuristic exists based on the descriptive typicality of a person. "
    "This implies a human tendency to trust typical individuals more and, conversely, a "
    "disadvantage for atypical individuals such as minorities.</jats:p>"
)


def test_hbm_fragment_renders_structured_without_jats_tags() -> None:
    out = clean_abstract_for_display(HBM)
    assert "jats" not in out  # no namespace prefix leaks (covers "<jats:" and "jats:")
    assert out.count("<p>") == 1  # the redundant "Abstract" title is dropped → one paragraph
    assert "<strong>Abstract</strong>" not in out
    assert out.startswith("<p>Resting")
    assert "<em>Hum Brain Mapp" in out and "</em>" in out
    assert "<strong>2017 Wiley Periodicals, Inc.</strong>" in out
    assert "©" in out  # © preserved
    assert "serotonin" in out


def test_alves_fragment_single_paragraph_passthrough() -> None:
    out = clean_abstract_for_display(ALVES)
    assert out.count("<p>") == 1
    assert "jats" not in out
    assert out.startswith("<p>When judging whether someone is trustworthy")
    assert out.endswith("minorities.</p>")
    assert "person’s" in out  # smart apostrophe preserved


def test_plain_text_is_wrapped_unchanged() -> None:
    assert clean_abstract_for_display("Just a plain abstract.") == "<p>Just a plain abstract.</p>"


def test_none_and_blank_return_none() -> None:
    assert clean_abstract_for_display(None) is None
    assert clean_abstract_for_display("") is None
    assert clean_abstract_for_display("   ") is None


def test_malformed_unclosed_tags_degrade_without_crashing() -> None:
    out = clean_abstract_for_display("<jats:p>open <jats:italic>oops")
    assert "jats" not in out
    assert "<em>oops</em>" in out  # the unclosed inline tag is closed for us
    assert out.startswith("<p>") and out.endswith("</p>")


def test_entities_and_sub_sup_preserved() -> None:
    out = clean_abstract_for_display(
        "<jats:p>p &lt; 0.05, CO<jats:sub>2</jats:sub>, x<jats:sup>2</jats:sup> &amp; H&amp;E</jats:p>"
    )
    assert "p &lt; 0.05" in out  # literal < kept as an entity, not a tag
    assert "<sub>2</sub>" in out
    assert "<sup>2</sup>" in out
    assert "&amp; H&amp;E" in out


def test_disallowed_tags_and_attributes_are_stripped() -> None:
    out = clean_abstract_for_display(
        "<jats:p>ok <script>alert(1)</script> "
        '<jats:italic onclick="x()">t</jats:italic> '
        '<a href="http://evil">l</a></jats:p>'
    )
    assert "<script" not in out
    assert "onclick" not in out
    assert "href" not in out
    assert "<a" not in out
    assert "<em>t</em>" in out  # allowlisted tag kept, its attribute dropped


def test_transform_is_pure_does_not_mutate_input() -> None:
    raw = HBM
    snapshot = str(raw)
    clean_abstract_for_display(raw)
    assert raw == snapshot


# ── abstract_plain_text (inc 55): tag-free strip for the editable textarea + term tokenizer ──


def test_plain_text_strips_jats_to_readable_text() -> None:
    out = abstract_plain_text(HBM)
    assert "jats" not in out.lower()  # the bug: no tag names survive
    assert "<" not in out and ">" not in out
    assert out.startswith("Resting")  # leading "Abstract" title dropped
    assert "Hum Brain Mapp" in out and "serotonin" in out


def test_plain_text_handles_entity_encoded_jats() -> None:
    out = abstract_plain_text("&lt;jats:p&gt;Encoded body.&lt;/jats:p&gt;")
    assert out == "Encoded body." and "jats" not in out.lower()


def test_plain_text_passes_plain_text_through() -> None:
    assert abstract_plain_text("Just a plain abstract.") == "Just a plain abstract."


def test_plain_text_joins_paragraphs_with_blank_line() -> None:
    assert abstract_plain_text("<jats:p>One.</jats:p><jats:p>Two.</jats:p>") == "One.\n\nTwo."


def test_plain_text_none_and_blank_return_none() -> None:
    assert abstract_plain_text(None) is None and abstract_plain_text("   ") is None


def test_plain_text_is_pure() -> None:
    raw = HBM
    snapshot = str(raw)
    abstract_plain_text(raw)
    assert raw == snapshot
