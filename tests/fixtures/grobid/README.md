# GROBID TEI-XML fixtures

`sample_fulltext.tei.xml` is a **real, unedited** TEI-XML response from a real GROBID 0.8.1 instance
(`docker run -p 8070:8070 grobid/grobid:0.8.1`, `POST /api/processFulltextDocument` with
`teiCoordinates=div,head,p`) run against a real PDF. It is not hand-written or synthesized -- see
`.claude/CLAUDE.md`'s GROBID-integration notes and `tests/test_grobid_tei_parse.py` for why that matters
(a synthetic fixture risks a parser that only matches a guess of GROBID's format, not the real one).

## Source PDF and license

- **Title:** Short communication: Lifetime musical activity and resting-state functional connectivity in
  cognitive networks
- **Authors:** Liebscher M, Dell'Orco A, Doll-Lee J, Buerger K, Dechent P, Ewers M, et al.
- **Journal:** PLOS ONE 19(5): e0299939, May 2, 2024
- **DOI:** [10.1371/journal.pone.0299939](https://doi.org/10.1371/journal.pone.0299939)
- **License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) -- PLOS ONE publishes all articles
  under this license. Per the article page: "This is an open access article distributed under the terms of
  the Creative Commons Attribution License, which permits unrestricted use, distribution, and reproduction in
  any medium, provided the original author and source are credited."

Only the derived TEI-XML structure (section headings, paragraph text, and page-coordinate metadata GROBID
extracted) is checked in here -- not the source PDF itself. Regenerate by downloading the PDF from
`https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0299939&type=printable` and POSTing it
to a local GROBID instance via `integrations/grobid/client.py`'s `parse_fulltext()`.
