"""Structured-table extraction fixtures for table-aware Methods checks."""

from __future__ import annotations

import zipfile

from app.backend.document_tables import extract_document_tables


def test_jats_table_preserves_headers_rows_caption_and_section(tmp_path):
    path = tmp_path / "article.jats"
    path.write_text(
        """
        <article><body><sec><title>Results</title><table-wrap>
          <label>Table 1</label><caption><p>Primary outcomes</p></caption>
          <table><thead><tr><th>Outcome</th><th>Test (df)</th><th>Statistic</th><th>p</th></tr></thead>
          <tbody><tr><td>Memory</td><td>t(28)</td><td>2.10</td><td>.04</td></tr></tbody></table>
        </table-wrap></sec></body></article>
        """,
        encoding="utf-8",
    )
    extraction = extract_document_tables(path)
    assert extraction.tables_scanned == 1
    assert len(extraction.rows) == 1
    row = extraction.rows[0]
    assert row.headers == ("Outcome", "Test (df)", "Statistic", "p")
    assert row.cells == ("Memory", "t(28)", "2.10", ".04")
    assert row.caption == "Table 1"
    assert row.section == "Results"


def test_html_table_preserves_explicit_header_and_heading_scope(tmp_path):
    path = tmp_path / "article.html"
    path.write_text(
        """
        <h2>Results</h2><table><caption>Primary outcomes</caption>
          <tr><th>Outcome</th><th>t</th><th>df</th><th>p</th></tr>
          <tr><td>Memory</td><td>2.10</td><td>28</td><td>.04</td></tr>
        </table>
        """,
        encoding="utf-8",
    )
    row = extract_document_tables(path).rows[0]
    assert row.headers == ("Outcome", "t", "df", "p")
    assert row.cells == ("Memory", "2.10", "28", ".04")
    assert row.caption == "Primary outcomes"
    assert row.section == "Results"


def test_docx_table_uses_first_row_as_bounded_headers(tmp_path):
    path = tmp_path / "article.docx"
    document_xml = """
      <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>
        <w:tr>
          <w:tc><w:p><w:r><w:t>Outcome</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>Test (df)</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>Statistic</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>p</w:t></w:r></w:p></w:tc>
        </w:tr>
        <w:tr>
          <w:tc><w:p><w:r><w:t>Memory</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>t(28)</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>2.10</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>.04</w:t></w:r></w:p></w:tc>
        </w:tr>
      </w:tbl></w:body></w:document>
    """
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("word/document.xml", document_xml)
    row = extract_document_tables(path).rows[0]
    assert row.headers == ("Outcome", "Test (df)", "Statistic", "p")
    assert row.cells == ("Memory", "t(28)", "2.10", ".04")
