# Security Policy

## Supported versions

Callosum is pre-1.0 and single-maintainer. There is one supported line: the latest commit on `main`. There are
no LTS branches or backported fixes.

## Threat model (read this first)

Callosum is designed to run **locally, for one user, on `127.0.0.1`** — it ships with no authentication by
default, and the local-app threat model is resource exhaustion and untrusted-content handling (a malicious
PDF, a hostile API response), not multi-tenant isolation. See the "Security note" in [`README.md`](README.md)
and `.claude/CLAUDE.md`'s "Security baseline & audit gate" for the full picture, including what's still owed
before any general/hosted deployment (this is explicitly not there yet — the project's own docs say so).

Every non-trivial new endpoint, external integration, file-ingestion path, or auth change goes through an
internal security-review discipline before it ships (`.claude/security-audits/` — one dated file per feature,
each ending in an explicit PASS or a recorded, accepted risk). That's project-internal process, not a public
guarantee, but it's why the project can say plainly what has and hasn't been reviewed.

The optional in-app **Feedback** action is an explicit egress surface to a separately hosted relay. The desktop never
contains the private Slack webhook and cannot choose a destination. The relay strictly validates and size-limits
reports, neutralizes Slack mentions/markup, and rate-limits verified accounts or anonymous source IPs. Because a
distributed desktop secret would not authenticate clients, anonymous spam remains a documented residual risk; see
[`feedback_relay/README.md`](feedback_relay/README.md). Do not put credentials, unpublished material, or sensitive
vulnerability details into an ordinary feedback report.

The public online demo is deliberately **not** a hosted instance of that local service. It is a static build of
the shared frontend over a curated immutable snapshot: no FastAPI process, database, credentials, AI calls,
telemetry, or live endpoints are deployed. Its data provider rejects mutations in memory and a browser guard plus
Content Security Policy restrict requests to static files beneath the deployment path. Snapshot export is
whitelist-based and rejects unknown fields, local paths, credential markers, and unverified document assets. Treat
saved axes, tags, tag suggestions, queue/profile state, method results, Status receipts, synthetic manuscripts,
manuscript checkpoints, tasks, references, WIP findings, discovery results, journal/funding reports, followed-author
records, extraction rows, annotations, and statement drafts as public data too. A current-Feed candidate is never
public merely because it was sanitized: it must be reviewed and approved by its exact SHA-256, and the schema
rejects any unapproved Feed records.
Treat every byte under `demo/` as public; never point either the library-state generator or snapshot exporter at an
ordinary user database. The detailed trust and
licensing boundary is in [`demo/README.md`](demo/README.md).

Public registry access is not treated as a reuse license. The Rasset OSF registration reports “No license,” so the
demo contains verified metadata, short bounded comparison excerpts, and the canonical URL—not the complete
registration or its files. That decision is explicit in the strict snapshot license audit.

## Reporting a vulnerability

<!-- TODO(maintainer): add a preferred private contact (email, or enable GitHub's private vulnerability
reporting under this repo's Security tab) once you have one you're comfortable publishing here. -->

- **If it's not sensitive** (e.g. a hardening suggestion, not an exploitable issue), please just open a
  [GitHub issue](https://github.com/cliffworkman/callosum/issues).
- **If it's sensitive** (something exploitable, or that could affect a real user's data), please do not open
  a public issue. Until a dedicated private channel is set up here, use GitHub's private vulnerability
  reporting if it's enabled on this repo, or reach the maintainer through a channel you already have.

This is a pre-1.0, single-maintainer project — please have reasonable patience with response time, and thank
you for reporting responsibly rather than disclosing publicly first.

## Scope

In scope: the Callosum application itself (`app/`, `integrations/`, `adapters/`, `tools/`). Out of scope:
third-party services Callosum talks to (Crossref, OpenAlex, Semantic Scholar, Gemini, etc.) — report those to
their own maintainers.
