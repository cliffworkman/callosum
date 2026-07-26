# Security audit — positive self-correction signal

**Date:** 2026-07-26
**Status:** complete — PASS

## Scope

Bounded deterministic metadata signal for explicit correction records. The implementation reuses the existing
Crossref DOI lookup/cache and findings/system-fact pipeline; it does not inspect authors, infer relationships
from prose, call an LLM, or create a composite score. Replication was reviewed and deliberately left out because
the available structured sources do not expose an evidence-grade controlled relation.

## Threat review

- **Input validation:** no new input surface. The producer consumes the paper's existing normalized DOI and the
  existing Crossref parser's controlled `update-to` records. A positive projection additionally requires
  `status == correction` and a non-empty merged `notice_url`.
- **Output encoding / injection:** React renders registry metadata as text. The evidence link is a URL already
  produced by the existing Crossref relationship parser (normally `https://doi.org/<notice DOI>`), opens only
  after a user click, and uses `target="_blank"` with `rel="noopener noreferrer"`.
- **SSRF / external calls:** no new fetch path, endpoint, host, or server-side URL dereference. The existing
  allowlisted Crossref/Retraction Watch job remains the sole producer.
- **Secret handling:** no credentials, tokens, environment values, or private identifiers were added.
- **Data egress:** the existing job sends only a public DOI for public registry lookup. No PDF text, manuscript
  content, library notes, tags, or user-authored material leaves the application.
- **Resource caps:** no extra provider call or fan-out was added. The existing one-check-per-live-DOI batch and
  cache behavior are unchanged.
- **File-path safety:** no file path is accepted, resolved, displayed, or written by this feature.
- **Supply chain:** no dependency, executable, database migration, or deployment surface was added. The existing
  paper-list response gains one additive boolean derived from the read-only system tag.

## Negative-path checks

- A correction with a notice DOI receives the read-only positive system tag and an exact evidence link.
- A correction without an openable record remains a generic fact and receives no positive tag/badge.
- Concern, retraction, and checked-clean outcomes do not receive the positive tag; later concern/clean results
  remove a stale correction tag.
- Missing DOI remains unchecked, and existing checker-failure behavior remains non-destructive.
- Existing system-tag authorization tests continue to reject user creation/mutation of reserved tags.
- Focused backend tests cover endpoint counts, finding payloads, paper-detail tags, precedence, and stale removal.
- Headed browser checks at 375×812 and 1440×900 found no horizontal overflow. The correction tag filtered to the
  single corrected paper, the evidence link had the exact expected href and safe rel attributes, and the tested
  application run emitted zero console errors or warnings. A final two-paper fixture confirmed that identical
  `correction` statuses do not suffice: only the record with openable evidence received the list boolean, badge,
  and Details evidence row.

## Result

No exploitable issue or new sensitive boundary was found.

**Security Audit: PASS**
