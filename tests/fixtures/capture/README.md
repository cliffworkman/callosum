# Ioannidis DOI review regression fixture

`ioannidis-pmed.0020124.pdf` is the exact original PDF captured during Cliff's real
Intel-Mac acceptance at `c7a7c10b16e01e587c5b69e0d3212987bae106ad` (2026-09-24).
Retrieved read-only over `ssh callosum-imac` from the existing QA fixture; no re-download
or PDF rewrite. SHA-256:
`ffc1005680cb620eec4c913437dfabbf311b535cfe16cbaeb2faec1f92afc362` (255629 bytes).

John P. A. Ioannidis (2005), *Why Most Published Research Findings Are False*,
PLoS Medicine 2(8): e124. https://doi.org/10.1371/journal.pmed.0020124
Publisher PDF: https://journals.plos.org/plosmedicine/article/file?id=10.1371/journal.pmed.0020124&type=printable
Copyright 2005 John P. A. Ioannidis. Page 1 specifies the Creative Commons Attribution
License and permits reuse with original-author/source credit. PDF bytes are unmodified.

`ioannidis-acceptance.json` preserves the original automatic evidence and Cliff's
subsequent **manual** DOI-confirmation provenance. Do not rewrite this record to claim
automatic resolution or a candidate confirmation. New extraction outcomes are tested
separately. Tests use injected deterministic resolver records, never the live provider.
