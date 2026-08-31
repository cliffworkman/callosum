# Mendeley / EndNote External-Gate Completion Playbook

**Date:** 2026-08-30
**Audience:** Callosum maintainer and any outside reviewer/test-machine owner
**Purpose:** close the remaining non-code gates without weakening credential, privacy, licensing, or fixture
provenance requirements.

This document is a maintainer checklist, not authorization to ship either importer. Complete each gate, preserve
the requested evidence, and tell Codex only that the evidence is available. Never paste a secret, refresh token,
signing credential, private library, or personal filesystem path into chat, an issue, or a committed file.

## Current state

| Gate | Current state | What it blocks |
|---|---|---|
| Mendeley registered client identity | `MENDELEY_SECRET` exists locally; client ID and approved redirect design do not | Live OAuth, token refresh, real folders/documents/PDF import |
| Mendeley desktop OAuth shape | Official auth-code flow requires a confidential secret; no documented PKCE path | Safe production desktop activation |
| MariaDB distribution legal review | Engineering analysis complete; qualified legal approval absent | Bundling/catalog/updater integration |
| EndNote macOS runtime | No reproducible signed/notarized arm64/x86_64 runtime or live Mac receipt | macOS legacy-library import |
| Attached-PDF EndNote fixture | Existing X1/X7 fixtures contain no real attachment bytes | Attachment mapping, MIME, deduplication, ingestion tests |
| Current-format EndNote fixture | No verified current EndNote-created compressed library | Modern-format detection/parser qualification |
| Final Linux package matrix | Runtime-only ABI matrix complete; component cannot legally enter the `.deb` yet | Release-level Ubuntu/Debian support claim |

Relevant repository evidence:

- `2026-08-29_codex-mendeley-endnote-import-handoff.md`
- `research/2026-08-29_mendeley_endnote_native_import.md`
- `research/2026-08-30_endnote_managed_bootstrap_engine.md`
- `research/2026-08-30_endnote_mariadb_distribution_review.md`
- `research/2026-08-30_endnote_linux_abi_matrix.md`
- `../security-audits/2026-08-30_endnote-compressed-library-import.md`

## Recommended order

1. Send the Mendeley OAuth capability questions and the MariaDB legal-review request; both may have external
   turnaround time.
2. Create privacy-safe EndNote fixtures while those reviews are pending.
3. Arrange macOS arm64 and x86_64 access.
4. Give Codex the non-secret Mendeley identity/redirect decision and fixture locations.
5. Only after written legal approval, authorize optional-runtime packaging and the final `.deb` install matrix.

## Gate 1 — Mendeley application and desktop-safe OAuth

### 1A. Ask Mendeley/Elsevier to confirm the supported native-app shape

Use the developer portal/support channel and ask these questions verbatim or equivalently:

> Callosum is an installed, open-source desktop application. Does the Mendeley API support Authorization Code
> with PKCE for a public native client, without a distributable client secret? If so, which authorization/token
> parameters are required?
>
> Are literal loopback redirect URIs such as `http://127.0.0.1:<ephemeral-port>/...` supported, including a
> dynamically selected port? Are `localhost` and `127.0.0.1` treated differently?
>
> Can one application register multiple redirect URIs for development and production?
>
> If public-client PKCE or dynamic loopback redirects are not supported, is a server-side confidential-client
> broker the approved pattern for installed desktop software?
>
> Please confirm current refresh-token rotation/expiry behavior and the least scope that can read a user's own
> documents, personal folders, folder memberships, and file metadata/downloads.

Save the response outside the public repository. A sanitized summary may later be committed, but it must name the
support date and exact capability statements rather than paraphrasing them optimistically.

Why this matters: the documented Authorization Code flow authenticates `/oauth/token` with the application ID and
secret. Embedding that secret in Callosum would make it public. The documented Implicit flow avoids the secret but
provides a one-hour token and no refresh path, so it is not the approved production fallback.

Official references:

- Application registration: <https://dev.mendeley.com/reference/topics/application_registration.html>
- Authorization overview: <https://dev.mendeley.com/reference/topics/authorization_overview.html>
- Authorization Code flow: <https://dev.mendeley.com/reference/topics/authorization_auth_code.html>
- Implicit flow: <https://dev.mendeley.com/reference/topics/authorization_implicit.html>

### 1B. Register or update the development application

1. Sign in at <https://dev.mendeley.com/myapps.html>.
2. Use a clear name such as `Callosum Development`; keep production and disposable development clients separate.
3. Describe it as an open-source scholarly desktop application importing the consenting user's personal library.
4. Do **not** guess the final redirect. The portal allows it to be edited. Register the exact URI only after Gate
   1A establishes the supported public-client or broker design.
5. Generate/rotate the secret in the portal if needed. Store it only in the gitignored local `.env` or approved
   credential store. Never commit it or place it in argv, logs, screenshots, receipts, or chat.
6. Record the numerical client ID and exact redirect URI. These are not passwords, but keep configuration in
   `.env` until the production ownership model is approved.

Once the redirect design is approved, the expected local configuration names are:

```dotenv
MENDELEY_CLIENT_ID=<numeric application id>
MENDELEY_SECRET=<secret; already present locally>
MENDELEY_REDIRECT_URI=<exact registered URI>
```

Do not add these names to production code merely to make the values appear configured. Codex must first wire the
approved flow, write-only credential storage, callback state validation, and token lifecycle.

### 1C. What to tell Codex

Send only:

- “Mendeley client ID is present in `.env`” — do not paste its value unless specifically needed;
- the exact registered redirect URI, which is non-secret;
- whether Mendeley approved PKCE/dynamic loopback, multiple redirects, or a confidential broker;
- the date/source of that answer; and
- whether the app may be used for a live test account.

Codex's live acceptance must then prove state/CSRF matching, one-time code exchange, refresh-token replacement,
bounded pagination, folder membership, signed PDF redirect/download, credential redaction, revocation/failure, and
no partial import. A secret in `.env` alone is not completion.

## Gate 2 — MariaDB GPL distribution review

This is legal review, not a request for a general open-source-license opinion. Give qualified counsel the exact
feature design and ask for a written release decision.

### 2A. Review packet

Provide:

- Callosum license: AGPL-3.0-or-later;
- MariaDB Server 10.11.19 license: GPL-2.0-only;
- `research/2026-08-30_endnote_mariadb_distribution_review.md`;
- `research/2026-08-30_endnote_managed_bootstrap_engine.md`;
- `research/2026-08-30_endnote_linux_abi_matrix.md`;
- the proposed separate optional-component/process boundary;
- the fixed stdin/file-output protocol and absence of linked MariaDB client/server code;
- the proposed exact source, COPYING, THIRDPARTY, signature, transformation, and derived-signature kit; and
- the fact that Callosum works without the component, while legacy EndNote import does not.

### 2B. Questions requiring explicit answers

1. May Callosum distribute this separately executed optional GPL-2.0-only component beside the
   AGPL-3.0-or-later application as an aggregate?
2. Does inclusion in the same installer violate or materially weaken that conclusion compared with a separate,
   user-initiated component download?
3. Is the proposed corresponding-source delivery sufficient, including for a deterministically stripped binary?
4. Which notices must appear in the installer, component directory, About screen, and download page?
5. Is the conservative three-year source-retention floor sufficient for the chosen distribution mechanism?
6. Are there MariaDB trademark/endorsement wording constraints?
7. May Callosum sign the derived stripped asset while preserving the upstream signature over the original input?
8. Does counsel require a separate component EULA/disclaimer, and if so, does it preserve all GPL rights?

### 2C. Acceptable outcome evidence

Keep the full legal opinion privately. Commit only a sanitized decision receipt containing reviewer role/firm,
date, scope reviewed, approved distribution shape, mandatory conditions, and yes/no status. Do not publish
privileged analysis without counsel's approval.

Until that receipt says **approved**, MariaDB must not enter Callosum's installer, updater, managed catalog, release
assets, or user-facing settings. A conditional or ambiguous answer remains blocked.

## Gate 3 — privacy-safe EndNote fixtures

Use synthetic/public data only. Do not contribute a personal scholarly library, licensed paper, private note,
username, absolute path, or identifying metadata.

### 3A. Current EndNote compressed library with real attachment bytes

On the newest EndNote version available:

1. Create a brand-new library named generically, such as `Callosum Import Fixture`.
2. Add at least five synthetic references spanning journal article, book/chapter, conference item, report, and a
   record without DOI. Use clearly fictional metadata or public-domain test metadata.
3. Create a group set with two nested groups and overlapping membership; leave one reference ungrouped.
4. Create small original test PDFs containing obvious text such as `CALLOSUM ATTACHMENT A`, `B`, and `C`. These
   should be authored for the fixture, not downloaded scholarly articles.
5. Attach at least one PDF to three different records. Attach the same PDF bytes to two records to exercise
   deduplication. Optionally add one deliberately broken attachment link in a separate negative fixture.
6. Use EndNote's broken-attachment check and ensure the positive fixture has none.
7. Choose **File → Compress Library (.enlx)**, include **all references** and **file attachments**, and save the
   resulting `.enlx`.
8. Restore that `.enlx` into a separate empty directory and verify that EndNote opens it, the group hierarchy is
   present, and each positive attachment opens.

EndNote officially documents that `.enlx` can contain the `.enl`, companion `.Data` directory, and file
attachments: <https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/02library/saving_a_cmprssdcpy_ofa_lib.htm>.

### 3B. Record provenance

Create a sidecar text receipt outside the archive containing only:

- EndNote product/version/build;
- OS/version;
- creation date;
- whether all/selected references and attachments were included;
- expected reference/group/group-set/attachment counts;
- expected duplicate-attachment relationship;
- `.enlx` filename, byte size, and SHA-256; and
- SHA-256 values of the original synthetic PDFs.

Do not include a machine username or absolute path.

### 3C. Store and hand off safely

Place the archive and receipt under a new gitignored directory such as:

```text
.claude/backups/endnote-fixtures/current-with-attachments/
```

Confirm with `git check-ignore -v <path>` before copying. Tell Codex the relative path and expected counts; do not
commit the `.enlx` or PDFs. Codex must inspect the archive format before calling it SQLite or assuming it matches
community documentation.

If a legacy EndNote X7-capable machine is available, repeat the same synthetic attachment exercise there. A
current-format attachment fixture proves the general attachment boundary but does not automatically prove the
legacy MyISAM `pdf_index` mapping.

## Gate 4 — macOS runtime access and signing

Arrange access to both:

- Apple Silicon (arm64), macOS 12 or newer; and
- Intel x86_64, macOS 12 or newer, whether physical or a legitimate hosted Mac.

Do not provide Apple signing/notarization credentials to Codex. The maintainer should execute signing commands
locally through the existing keychain/notary profile after Codex prepares an auditable unsigned candidate.

Each architecture must use the same MariaDB 10.11.19 source identity and produce:

1. compiler/Xcode/SDK identity and complete build recipe;
2. launcher plus allowlisted message/charset runtime manifest;
3. binary and bundle SHA-256 values;
4. dependency inspection proving no Homebrew/MacPorts or developer-machine path is required;
5. unprivileged public-X7 bootstrap receipt: 59 rows/54 columns, network disabled, source unchanged;
6. timeout/crash/forced-cleanup tests with no orphan;
7. relocation test from a second installation root;
8. code-sign verification, Gatekeeper assessment, and notarization/stapling receipt; and
9. operational logs proving no bibliographic content, fixture path, token, or signing credential leaked.

Do not claim universal-binary equivalence unless both slices are independently identified and exercised.

## Gate 5 — final Linux packaged-app matrix

This gate opens only after Gate 2 authorizes the exact distribution shape.

Build the actual Callosum `.deb` with the optional component and declared dependencies:

```text
libc6, libcrypt1, libgcc-s1, libstdc++6, libsystemd0
```

Install and run on clean amd64 instances of Ubuntu 22.04, 24.04, 26.04 and Debian 12, 13. For each target record:

- base-image/VM identity and update state;
- package/control-file dependency list;
- clean install and uninstall;
- app launch and backend health;
- optional component absent/degraded behavior;
- component installation/verification;
- one public-X7 import attempt;
- no TCP/Unix listener, no orphan, and clean app shutdown;
- source/notice availability; and
- removal without deleting user libraries or unrelated files.

Do not silently fetch missing APT packages or an arbitrary host `mariadbd`. Package resolution and failures must
be visible and deterministic.

## Completion handoff template

Copy this block into a future request and fill only non-secret facts:

```text
Mendeley support response date/source:
Mendeley approved OAuth shape:
MENDELEY_CLIENT_ID present in .env: yes/no
MENDELEY_SECRET present in .env: yes/no
Exact registered redirect URI:

MariaDB legal review status: approved / rejected / conditional / pending
Approved distribution shape and mandatory conditions:
Sanitized decision-receipt path:

Current EndNote fixture relative path:
Current EndNote version/build and OS:
Fixture SHA-256:
Expected references/groups/attachments:
Legacy attached-PDF fixture available: yes/no

macOS arm64 access available: yes/no
macOS x86_64 access available: yes/no
Signing/notarization operator available: yes/no

Authorization granted for actual optional-component packaging: yes/no
```

## Stop conditions

Stop and ask before proceeding if:

- Mendeley requires embedding a shared secret in the distributed desktop app;
- the registered redirect cannot match a strict, owned callback;
- legal review is conditional or rejects the aggregate boundary;
- a fixture contains private/copyrighted material or cannot be restored by EndNote;
- a macOS binary depends on an unowned package-manager path;
- signing credentials would have to enter source, argv, logs, or chat; or
- any package/runtime test alters the source `.enlx` or leaves a process/listener behind.
