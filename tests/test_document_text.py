"""DocumentTextProvider adapters for transparency / registration-alignment infrastructure."""

from __future__ import annotations

import zipfile

from app.backend.document_text import extract_text_document
from app.backend.pdf_processing.ingest import attach_text_document_to_paper
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_attachments_for_paper, get_chunks_for_paper


def test_jats_xml_provider_extracts_sections(tmp_path):
    path = tmp_path / "article.xml"
    path.write_text(
        """<article>
          <front><article-meta><abstract><p>Data are available at OSF.</p></abstract></article-meta></front>
          <body><sec><title>Methods</title><p>This randomized trial was registered at ClinicalTrials.gov.</p></sec></body>
        </article>""",
        encoding="utf-8",
    )
    extraction = extract_text_document(path)
    assert extraction.provider_id == "jats-xml-text"
    assert [s.section for s in extraction.segments] == ["Abstract", "Methods"]
    assert "registered at ClinicalTrials.gov" in extraction.segments[1].text


def test_html_provider_extracts_heading_scoped_blocks(tmp_path):
    path = tmp_path / "article.html"
    path.write_text(
        "<html><body><h2>Open materials</h2><p>Code is available at GitHub.</p><p>Funding: NIH.</p></body></html>",
        encoding="utf-8",
    )
    extraction = extract_text_document(path)
    assert extraction.provider_id == "html-text"
    assert [(s.section, s.text) for s in extraction.segments] == [
        ("Open materials", "Code is available at GitHub."),
        ("Open materials", "Funding: NIH."),
    ]


def test_docx_provider_extracts_paragraphs(tmp_path):
    path = tmp_path / "article.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
      <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
          <w:p><w:r><w:t>Conflict of interest:</w:t></w:r><w:r><w:t> none declared.</w:t></w:r></w:p>
          <w:p><w:r><w:t>Data available upon request.</w:t></w:r></w:p>
        </w:body>
      </w:document>"""
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("word/document.xml", document_xml)
    extraction = extract_text_document(path)
    assert extraction.provider_id == "docx-text"
    assert [s.text for s in extraction.segments] == [
        "Conflict of interest: none declared.",
        "Data available upon request.",
    ]


def test_attach_text_document_feeds_normal_chunks(temp_db_url, tmp_path):
    path = tmp_path / "article.xml"
    path.write_text(
        "<article><body><sec><title>Availability</title><p>Data are openly available at https://osf.io/abcd1.</p></sec></body></article>",
        encoding="utf-8",
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="XML paper", csl_json={"title": "XML paper"})
        result = attach_text_document_to_paper(conn, paper_id, path, storage_mode="linked")
        chunks = get_chunks_for_paper(conn, paper_id)
        attachments = get_attachments_for_paper(conn, paper_id)
        assert result["extraction_tool"] == "jats-xml-text"
        assert attachments[0]["attachment_type"] == "jats-xml"
        assert chunks[0]["text"] == "Data are openly available at https://osf.io/abcd1."
        assert chunks[0]["section"] == "Availability"
        assert chunks[0]["bbox_coordinate_system"] == "document-text-offsets"
        assert chunks[0]["chunk_version"].startswith("document-text-block-v1:jats-xml-text-1:")
    engine.dispose()
