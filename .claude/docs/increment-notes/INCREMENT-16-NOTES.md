# Increment 16 Notes

## Implemented

- Hardened quote-location canonicalization in `app/backend/pdf_processing/extraction.py`.
- Kept the increment-15 token/line geometry decision for document-side hyphenation.
- Added hard-keep guards before dropping a line-break hyphen:
  - keep if a digit is adjacent to either side of the break;
  - keep if the left fragment is a documented hyphen-retaining prefix;
  - keep if the left fragment already contains an internal hyphen, preserving compound fragments such as `beauty-is-`.
- Kept verifier precheck consistency through `canonical_text_contains`.

## Prefix Guard Set

The prefix allow-list is:

`anti`, `co`, `ex`, `inter`, `intra`, `multi`, `non`, `post`, `pre`, `pseudo`, `quasi`, `re`, `self`, `semi`, `sub`, `super`, `un`.

Rationale: these prefixes commonly form meaningful hyphenated scientific or scholarly terms. The guard is conservative: it preserves the hyphen rather than making the matcher more permissive.

## Unicode Pipeline

- Base normalization is now Unicode NFC, not NFKC.
- Explicit ligature folds remain:
  - `ﬀ -> ff`
  - `ﬁ -> fi`
  - `ﬂ -> fl`
  - `ﬃ -> ffi`
  - `ﬄ -> ffl`
  - `ﬅ -> st`
  - `ﬆ -> st`
  - `ſ -> s`
- Soft hyphen `U+00AD` is removed unless it is acting as a guarded line-break hyphen, where it canonicalizes to `-`.
- Dash/hyphen equivalents `U+2010`, `U+2011`, `U+2012`, `U+2013`, `U+2014`, and `U+2212` canonicalize to ASCII `-`.
- Whitespace collapse is unchanged.
- NFKC-only rewrites such as `½ -> 1⁄2` and `² -> 2` are deliberately not performed.

## Document-As-Dictionary Tiebreaker

- Deferred.
- The current guards address the observed high-risk failures without adding a second document-level pass or changing match permissiveness.
- A future tiebreaker can still use same-document token usage, without an external lexicon, if real runs show ambiguous unresolved cases.

## Coordinates

- The document canonicalizer still walks `_WordToken` records.
- Canonical characters map back to original token indices, and rectangles are derived from those original tokens.
- Digit/prefix/compound hyphen guards do not change stored chunk text.

## Guardrails

- No fuzzy matching, edit distance, or synonym matching was added.
- Altered and fabricated quotes still fail to locate.
- Same-line/internal compounds still preserve hyphens.
- Digit-adjacent breaks such as `α2- / integrin` and `5- / HT` preserve hyphens.
- Plain soft breaks such as `beau- / tiful` still match `beautiful`.

## Raw Pytest Output

```text
pytest -q
.............................................................            [100%]
61 passed in 34.91s
```
