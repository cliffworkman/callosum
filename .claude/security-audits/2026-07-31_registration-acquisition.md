# Security and privacy audit — registration acquisition

**Date:** 2026-07-31
**Increment:** 428
**Status:** PASS

## Surface

An explicit action downloads one user-confirmed public OSF registration or AsPredicted PDF and stores a deterministic,
hashed local version. A local registration attachment uses the same versioning seam without egress.

## Threat review

- **Unexpected egress:** only `POST /papers/{paper_id}/registration-links/{link_id}/acquire` invokes a provider.
  Candidate confirmation, panel load, version listing/detail, manual PDF import, and local chunking make no request.
- **SSRF:** OSF requests use fixed `https://api.osf.io/v2` and schema URLs validated back to that origin.
  AsPredicted URLs must be HTTPS on `aspredicted.org` or `www.aspredicted.org`; path forms are provider-specific.
  No generic URL provider or internal-network fetch exists.
- **Redirects:** automatic redirect following is disabled. Redirect targets are resolved then revalidated against the
  provider origin. A legacy AsPredicted landing page may yield only a revalidated same-origin PDF target.
- **Bounds/timeouts:** JSON is capped at 5 MiB, legacy HTML at 2 MiB, artifacts at 80 MiB, and requests have bounded
  timeouts. Oversize, timeout, status, or malformed-response failures are classified and visible.
- **Content validation:** OSF structured payloads must be valid expected JSON. AsPredicted artifacts require a PDF
  content type, `%PDF-` magic, and successful PyMuPDF open before import. HTML is never stored as a PDF.
- **Storage:** SHA-256 identifies content. Managed filenames are hash-derived and extension-controlled; provider
  titles never become paths. Temporary files live under the system temp directory, outside application bundles.
- **Integrity/versioning:** an existing hash is reused. Changed bytes create a new attachment/version. Writes are
  transactional; a failed import removes its newly moved managed file and cannot replace the prior link/version.
- **Credentials/privacy:** providers receive no registry credentials, Callosum keys, browser cookies, paper text,
  notes, chunks, annotations, or model prompt. Public registration content is downloaded only after user confirmation.
- **Provider isolation:** unsupported providers and provider failures become job errors without altering confirmed
  link metadata or existing versions. No authenticated content or browser cookie import is attempted.
- **Dependencies:** existing `httpx` and PyMuPDF are reused; no dependency or executable was added.

## Negative-path evidence

- Unconfirmed and withdrawn links return 409 before provider invocation.
- Embargoed/unavailable statuses are blocked by API and UI.
- Cross-origin AsPredicted legacy links are rejected.
- Invalid content type/PDF bytes fail closed.
- Provider exception leaves links, attachments, and version rows unchanged.
- Same-hash re-acquisition creates no duplicate attachment/version; changed hash preserves the prior basis.
- Version GETs and local registration imports invoke no provider; hermetic tests require fixture transports.

## Result

**PASS.** Acquisition is deliberate, provider-bounded, credential-free, size/type checked, hash-versioned, and
failure-safe. Any later external-model commitment extraction/comparison needs the separate existing AI egress gate.

