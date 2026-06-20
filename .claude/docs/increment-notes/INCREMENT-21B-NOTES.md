# Increment 21a Notes

## Fixed

- Replaced OS-dependent attachment filename derivation with separator-agnostic parsing.
- `C:\papers\facial.pdf`, `/home/u/library/facial.pdf`, `C:/papers/facial.pdf`, and `facial.pdf` now all render as bare filenames.
- Hardened `tests/test_api.py` so the paper-detail response asserts Windows-style, POSIX-style, drive-with-forward-slash, and bare filename cases.

## Note

- Stored attachment paths carry host-specific separators, so future path-display code must be separator-agnostic too.

## Raw Pytest Output

```text
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 34.88s
```
