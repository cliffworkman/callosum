# EndNote MariaDB runtime distribution review (increment 545)

**Date:** 2026-08-30
**Status:** **ENGINEERING REVIEW COMPLETE — LEGAL SIGN-OFF REQUIRED BEFORE DISTRIBUTION**
**Scope:** prospective optional MariaDB runtime for the legacy EndNote `.enlx` import seam. No runtime is shipped,
downloaded, or activated by this increment.

This is an engineering assessment, not legal advice. It identifies a technically defensible separate-component
design and the exact materials a release would need. Because MariaDB Server is GPL-2.0-only while Callosum is
AGPL-3.0-or-later, a qualified human reviewer must approve the aggregate/independent-program conclusion before a
MariaDB binary enters a Callosum installer, updater, download catalog, or release asset.

## License facts

| Component | License fact | Evidence |
|---|---|---|
| Callosum | AGPL-3.0-or-later | `pyproject.toml`, `README.md`, repository `LICENSE` |
| MariaDB Server 10.11.19 | GPL-2.0-only, explicitly without an “any later version” clause | upstream `README.md`, `COPYING`, and official MariaDB licensing FAQ |
| MariaDB third-party material | multiple licenses retained in upstream `THIRDPARTY` | signed binary/source archives |

GPL-2.0-only and AGPL-3.0-or-later are not compatible licenses for code combined into one program. The design
therefore must not copy MariaDB code into Callosum, link against server libraries, load server code into the
Callosum process, or claim the server is relicensed under AGPL.

GNU's GPL FAQ describes command-line arguments and pipes as mechanisms normally used between separate programs,
while warning that both communication mechanics and semantics matter. MariaDB's own FAQ likewise describes an
independent optional server as an aggregate case, but includes its own non-lawyer disclaimer. Callosum's proposed
boundary has favorable separate-program facts:

- a distinct executable and process/address space;
- direct argv plus fixed SQL on stdin, with bounded files as output;
- no MariaDB client library, linking, RPC protocol binding, plugin, shared module, or copied server code;
- Callosum remains functional without the runtime; only optional legacy EndNote import is unavailable; and
- MariaDB keeps its own identity, license, notices, source, update stream, install root, and removal lifecycle.

The feature-specific dependency still creates a legal judgment question. These technical facts support an
aggregate conclusion; they do not substitute for approval.

## Exact upstream artifacts

The official MariaDB downloads REST API was queried on 2026-08-30. Both archives were downloaded into a private
Juno temp root, checked against API SHA-256 values, and verified with the official MariaDB signing key. GPG reported
good signatures made 2026-08-20 by fingerprint
`177F 4010 FE56 CA33 3630 0305 F165 6F24 C74C D1D8`. The temporary keyring was not trusted beyond matching the
fingerprint published by the MariaDB signing-key documentation.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `mariadb-10.11.19-linux-systemd-x86_64.tar.gz` | 357,390,930 | `7efb257927f31f4422f496246b32590d0b7617f3d9dd900e575de761b302d919` |
| `mariadb-10.11.19.tar.gz` | 114,812,324 | `b8e543ee69d380fb1cfd563226f49e0fe96e4d67e7b7a9045ee514a168ed2066` |

The binary and source roots contain byte-identical top-level GPLv2 `COPYING` files and byte-identical
`THIRDPARTY` inventories:

| Notice | SHA-256 |
|---|---|
| `COPYING` | `240a15a1d0f34d3abca462cdb7e5fb89470967563f16b0e71169e51c1e74cf2b` |
| `THIRDPARTY` | `e1099b3b42df5cb2e43118a77be01efc3ad2f46ab7a5579b286c1883e6e0d9e1` |
| binary `README.md` | `b66971296a4cfcf45047afc95131b327034a9aa0d775241ace282a380afa4ae7` |

The official binary tarball does not include an exact build-receipt file. A future Callosum release must retain the
upstream source archive and signature and add its own deterministic pruning/transformation receipt rather than
claiming reproducibility from the version string alone.

## Official-binary live proof

A temporary 31-file distribution candidate retained only `bin/mariadbd`, English messages, character sets,
`COPYING`, `THIRDPARTY`, and `README.md`. The 28 execution files produced runtime manifest
`8f570d9216edfa103fd49c6af6c00235f4eb10a3d2d9530441615b5111615f3c`; including the three notice files produced
distribution manifest `021597bce084057de3c6daf9aac246ff5acf5d0684f4746bc19fcf9da7ac9bec`.

The upstream launcher is unstripped: 310,372,864 of the candidate's 310,742,522 bytes. It ran directly on Juno,
resolved 14 OS-owned dynamic libraries, read the public X7 fixture as 59 rows/54 columns in 259 ms, preserved the
fixture SHA-256, and left no process.

## Deterministic strip experiment

Two independent copies of the signed upstream launcher were transformed with GNU binutils 2.40:

```text
strip --strip-unneeded bin/mariadbd
```

Both outputs were byte-identical:

- launcher bytes: 31,468,440 (down from 310,372,864);
- launcher SHA-256: `a7373757a2b2b3093e85af7382cc1633b169b895d9fffe7099e209d4e600414e`;
- 28-file runtime manifest: `5868954e88dba0eab030e33e6f4ad025857c5d336807af0667cd9cab41043ea5`;
- 31-file distribution manifest: `241049c9a9e0e9391de772c486244f4ca34c38c601cd22050834fdab22818b6a`;
- total distribution bytes: 31,838,098; and
- live result: 59 rows/54 columns in 259 ms, no orphan.

This proves a small deterministic candidate is technically plausible. It does not authorize distribution. A
stripped output is no longer byte-identical to the upstream signed binary, so Callosum would have to sign the
derived asset, publish the exact input hash/toolchain/command/output receipt, and mirror corresponding source.

## Required release layout

If legal review approves the separate-component conclusion, MariaDB must remain an optional component with a
separate root and identity. A release must contain or co-publish:

1. the exact runtime allowlist and canonical relative-path/size/SHA-256 manifest;
2. upstream `COPYING`, `THIRDPARTY`, and `README.md`, unmodified;
3. upstream binary filename/hash/signature and verified signing fingerprint;
4. the exact official source tarball, its hash/signature, and a source download beside the binary asset—not only
   a mutable upstream URL;
5. every Callosum transformation/pruning script, command, tool/version, input hash, and output hash;
6. a Callosum signature/checksum for the derived component;
7. an installer/About notice that names MariaDB Server, GPL-2.0-only, and the source/notice location without
   suggesting MariaDB endorses Callosum;
8. no EULA or technical restriction that removes GPL rights;
9. a retained source-access policy at least as durable as the binary release, with a conservative three-year
   retention floor after the last distribution; and
10. a complete license/source inventory for any non-System-Library dependency later copied into the bundle.

Callosum's own AGPL source and notices remain separate. `THIRD-PARTY-NOTICES.md` should gain a MariaDB section only
when a runtime actually ships; adding it now would falsely imply that MariaDB is already distributed.

## Forbidden shortcuts

- Do not label MariaDB as AGPL-compatible or relicense it under Callosum's license.
- Do not link/load MariaDB Server code into the Callosum executable or Python process.
- Do not omit `THIRDPARTY` when pruning the upstream distribution.
- Do not point only to “latest” source or rely only on an upstream server remaining available.
- Do not treat an upstream signature as covering a stripped/pruned Callosum-derived asset.
- Do not bundle Linux system libraries without adding their exact licenses and corresponding-source analysis.
- Do not put the component into installers, updaters, or a managed download catalog before legal sign-off.

## Linux ABI/package follow-up

Increment 546 closes the runtime-specific Linux ABI/package-policy research gate; see
`.claude/docs/research/2026-08-30_endnote_linux_abi_matrix.md`. The exact stripped candidate passed Ubuntu
20.04/22.04/24.04/26.04 and Debian 11/12/13 as root and uid 1000. The initial support policy is narrower:
Ubuntu 22.04/24.04/26.04 and Debian 12/13, amd64 only, within Callosum's existing `.deb` envelope. The component
must declare `libc6`, `libcrypt1`, `libgcc-s1`, `libstdc++6`, and `libsystemd0` instead of copying those libraries.
This evidence does not change the legal blocker or authorize installer integration.

## Decision

**Conditional engineering decision:** keep MariaDB as a separately executed, optional component and prepare a
self-contained source/notice/transformation release kit. The signed official Linux tarball is the cleanest upstream
provenance; a deterministic strip step makes its size practical, but creates a Callosum-derived artifact that needs
its own signature and receipt.

**Blocking decision:** no distribution is approved yet. Obtain qualified legal review of the aggregate boundary,
especially the fact that the component is required for one optional Callosum feature. If that review rejects the
boundary, fall back to a user-managed/upstream-fetched runtime or a separately distributed import utility whose
license relationship is reviewed independently.

## Authoritative sources

- MariaDB licensing FAQ:
  <https://mariadb.com/docs/general-resources/community/community/faq/licensing-questions/licensing-faq>
- MariaDB Server repository/license statement:
  <https://github.com/MariaDB/server>
- MariaDB 10.11.19 release API:
  <https://downloads.mariadb.org/rest-api/mariadb/10.11.19/>
- MariaDB downloads REST API contract:
  <https://mariadb.org/downloads-rest-api/>
- MariaDB signing-key documentation:
  <https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/installing-mariadb/binary-packages/gpg>
- GNU GPL FAQ (aggregation, separate programs, corresponding source):
  <https://www.gnu.org/licenses/gpl-faq.en.html>
- GNU license compatibility guidance:
  <https://www.gnu.org/licenses/license-compatibility.html>
