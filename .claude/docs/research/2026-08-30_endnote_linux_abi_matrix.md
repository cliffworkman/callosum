# EndNote MariaDB Linux ABI and package matrix (increment 546)

**Date:** 2026-08-30
**Status:** **ENDNOTE-RUNTIME LINUX ABI GATE CLOSED FOR THE TESTED AMD64 `.deb` ENVELOPE**
**Scope:** the exact developer-only MariaDB 10.11.19 bootstrap candidate used in increments 545–546. No runtime,
dependency, installer change, downloader, import route, or user-visible capability ships in this increment.

## Decision

The optional legacy-EndNote runtime may target the same glibc/amd64 `.deb` envelope as Callosum, with an initial
component support matrix limited to the exact tested releases:

- Ubuntu 22.04, 24.04, and 26.04 LTS; and
- Debian 12 and 13.

Ubuntu 20.04 and Debian 11 also passed and establish backward ABI evidence, but are not support promises. Ubuntu
20.04 left standard security maintenance in May 2025, and Debian 11 LTS ends on 2026-08-31. The component must not
expand Callosum's overall desktop support envelope: a future release still needs an actual packaged-app install/run
receipt on every release Callosum claims to support.

The runtime package must declare, not vendor, these direct OS dependencies:

```text
libc6
libcrypt1
libgcc-s1
libstdc++6
libsystemd0
```

The distribution must let APT resolve their transitive libraries. Copying glibc, systemd, libcrypt, libstdc++, or
their transitive system libraries into the optional bundle is outside the approved boundary and would reopen both
ABI and license analysis.

## Frozen runtime and fixture

| Item | Identity |
|---|---|
| Upstream archive | `mariadb-10.11.19-linux-systemd-x86_64.tar.gz` |
| Upstream archive SHA-256 | `7efb257927f31f4422f496246b32590d0b7617f3d9dd900e575de761b302d919` |
| Runtime version | `10.11.19-MariaDB for linux-systemd on x86_64` |
| Stripped launcher SHA-256 | `a7373757a2b2b3093e85af7382cc1633b169b895d9fffe7099e209d4e600414e` |
| 28-file runtime manifest | `5868954e88dba0eab030e33e6f4ad025857c5d336807af0667cd9cab41043ea5` |
| Runtime bytes | 31,730,615 |
| Public X7 fixture SHA-256 | `ad53d894baf15045a7504107e576c9591ff01fca76176a9d32e4c50a3043ab98` |

The official archive hash was rechecked before extraction. The launcher was transformed with the already-received
GNU binutils 2.40 `strip --strip-unneeded` procedure and reproduced the increment-545 digest.

## ABI facts

ELF inspection found a maximum direct symbol requirement of `GLIBC_2.17` and `GLIBCXX_3.4.19`. Direct `DT_NEEDED`
entries are the glibc loader/core libraries plus `libcrypt.so.1`, `libstdc++.so.6`, `libgcc_s.so.1`, and
`libsystemd.so.0`. The tested base releases resolved the complete graph through the five packages above.

`dpkg-shlibdeps` on Debian 12 emitted:

```text
libc6 (>= 2.34), libcrypt1 (>= 1:4.1.0), libgcc-s1 (>= 3.0),
libstdc++6 (>= 4.8), libsystemd0
```

The `libc6 >= 2.34` result is host-package metadata affected by glibc's libdl/libpthread merge, not the launcher's
empirical execution floor: the same bytes ran on glibc 2.31. A future `.deb` should derive dependency versions on
its pinned packaging baseline and then install-test the resulting package; it must not hand-lower generated bounds
merely because this research matrix found older execution compatibility.

## Live matrix

Every row used an official clean container base, the same read-only candidate and fixture, a fresh private working
root, two CPU cores, a 1 GiB memory limit, `--network none`, and MariaDB `--skip-networking`. The direct matrix ran
once as container root and once as uid/gid 1000. Both passes produced the same 59-row/54-column schema receipt,
preserved the source digest, and left no process.

| Base | Base digest | glibc | Root | Unprivileged | Unprivileged elapsed |
|---|---|---:|---|---|---:|
| Ubuntu 20.04 | `8feb4d8ca5354def3d8fce243717141ce31e2c428701f6682bd2fafe15388214` | 2.31 | pass | pass | 159 ms |
| Ubuntu 22.04 | `2edbbc5dc405e9612ba3584ce95480277e3eb374407b5505fe26f17df77c7dbc` | 2.35 | pass | pass | 187 ms |
| Ubuntu 24.04 | `33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517` | 2.39 | pass | pass | 157 ms |
| Ubuntu 26.04 | `2260313b31c8c011cd2eebe728008efac1b3982be73eb71348ea2648d2c0e09b` | 2.43 | pass | pass | 157 ms |
| Debian 11 slim | `e5b6442dd2e9684cf5e87d8338b5968f3b348636fc0be6d7850a381e3731a2bd` | 2.31 | pass | pass | 168 ms |
| Debian 12 slim | `88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171` | 2.36 | pass | pass | 157 ms |
| Debian 13 slim | `d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132` | 2.41 | pass | pass | 173 ms |

The Ubuntu 26.04 rows used the existing `legacy_bootstrap.py` end to end. The other container rows used the same
fixed bootstrap argv/SQL against a pre-extracted private copy so Ubuntu 20.04/Debian 11's system Python could not
confound the runtime ABI question. Callosum ships its own Python 3.11 runtime; system Python is not a product
dependency. A separate direct-host Juno/Python 3.11 run reproduced the canonical manifest and returned 59/54 in
259 ms.

The read-only container sandbox required an explicit private `--tmpdir=/work/tmp`; the developer harness already
executes inside an owned writable temporary root, so no production code change was needed. Fully isolated
containers emitted a 67-byte MAC-address warning because no network interface was available. It contained no
fixture content and did not affect bootstrap. There was no TCP exposure: the container had no network and the
runtime also received `--skip-networking`.

## Package policy

1. Build and publish only an `amd64` glibc candidate for the current Linux desktop scope.
2. Keep the five direct OS libraries as `.deb` dependencies; do not copy them into the runtime root.
3. Keep the MariaDB bundle separately identified/licensed and optional as specified by increment 545.
4. On every candidate update, rerun at least the oldest and newest supported Ubuntu/Debian releases, as an
   unprivileged user, with the exact signed/derived runtime manifest and public fixture.
5. Fail installation/activation when required libraries are absent; do not fall back to an unverified host
   `mariadbd` or download packages silently.
6. Before public release, install and run the actual Callosum `.deb` plus optional component on every claimed OS.

## Boundaries and remaining gates

This closes the EndNote runtime's Linux ABI/package-policy research gate. It does not approve MariaDB distribution,
which remains blocked on the increment-545 legal review, and it does not prove RPM/musl/ARM support. The remaining
EndNote gates are reproducible macOS builds/signing/notarization, a real attached-PDF fixture, a modern SQLite-era
fixture, production mapping/import/UI work, and the legal/source/signature release kit.

All downloaded archives, fixture copies, derived binaries, receipts, temporary scripts, and research container
images were removed from Juno after confirming no `mariadbd` process remained.

## Authoritative lifecycle sources

- Ubuntu release cycle: <https://ubuntu.com/about/release-cycle>
- Debian releases and lifecycle: <https://www.debian.org/releases/index.en.html>
- Debian 11 lifecycle: <https://www.debian.org/releases/bullseye/>
- Debian 12 lifecycle: <https://www.debian.org/releases/bookworm/>
