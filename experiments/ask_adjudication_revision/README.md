# Ask adjudication revision: synthetic preparation

This is the non-production implementation of the approved two-study/two-freeze
methods infrastructure. The capability audit is **Phase -1** in the methods
(the capability machinery requested as "Phase 1"). No actual study has been
frozen or executed by this package delivery.

**Scope:** generated synthetic packets, capability manifest templates, a
non-echo capture sink, deterministic adapters/parsers, individual rater
provenance, private interstudy amendment records, synthetic freeze/gate/queue
rehearsals, and immutable audit artifacts. No archive loader, sealed-key reader,
live provider dispatcher, browser automation, production imports, or genuine
human-label ingestion is implemented. Existing `ask_070` files are unchanged.

## Use

Run from the repository root with the existing environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv/Scripts/python.exe -m pytest experiments/ask_adjudication_revision/tests -q -p no:cacheprovider
.venv/Scripts/python.exe -m experiments.ask_adjudication_revision prepare-capability
.venv/Scripts/python.exe -m experiments.ask_adjudication_revision demo-synthetic
```

`prepare-capability` creates a new task-owned directory immediately under the
system temporary directory, outside Dropbox. It prints the directory location
and a mechanical receipt. It creates three synthetic packets plus nine
**UNTESTED** capability templates. It does not open or submit to any model.

For new mechanical audits use the amended literal-copy fixture:

```powershell
.venv/Scripts/python.exe -m experiments.ask_adjudication_revision prepare-capability --fixture literal-copy-v2
```

This creates one fixed combined envelope: eight fabricated records, including
one long record, 38,958 input bytes and 1,624 expected response bytes. Each record
supplies its receipt line literally. The surface copies text instead of counting
padding. The original counting-v1 default remains reproducible for archival
compatibility. V2 rejects incompatible size/format CLI overrides rather than
ignoring them. Capture recognizes and checks both versioned packet identities.

The default compact/intended/largest envelopes are illustrative synthetic
sizes, **not measurements of the real experiment**. Customize using:

```powershell
.venv/Scripts/python.exe -m experiments.ask_adjudication_revision prepare-capability --intended-count 8 --intended-padding 2048 --largest-padding 16000 --response-width 160 --format txt
```

Formats are `txt`, `json`, `csv`, and `markdown`. Generated packet files always
use a `.txt` extension for compatibility; the manifest records their actual
serialization. TXT and Markdown use labeled JSON-escaped records inside an
ordinary UTF-8 text document, so literal tabs, delimiters and multiline values
round-trip without loss. A surface need not support JSON attachments or return
JSON. No candidate object is split to fit a byte envelope.

`demo-synthetic` fabricates both rater responses and human labels with explicit
SYNTHETIC provenance. Its queue, freezes, outcomes, accounts, and model names
are demonstration data. They are never genuine selections, adjudication, or
qualification evidence. The demo preserves its fake raw responses, private
design, frozen manifests, human presentation examples, and review provenance.

## Capture seam and capability records

`capture-capability --run <owned-run-directory> --surface <roster-id>
--packet-id <generated-id>` accepts **redirected binary stdin only**. An
interactive terminal is rejected. This is a sink for a future qualified hidden
adapter, not a request to copy model results through a visible editor or shell.
It has no arbitrary input-file option and reads only generated packet metadata
from a verified task-owned store. Output is limited to capture success, byte
count, and SHA256. Exceptions use a fixed error response without raw content,
traceback, file contents, or semantic labels.

Captures are independent by surface, packet, and attempt. Raw bytes are stored
exclusively and never overwritten. A second attempt requires a failed first
capability response and an existing mechanical amendment; a third is refused.
The first response remains preserved. A passing response cannot be retried.

`record-mechanical-amendment --run <owned-run-directory> --id <opaque-id>`
accepts a JSON object via redirected stdin with exactly:

```json
{
  "what": "Synthetic transport change",
  "why": "Mechanical reason",
  "when_utc": "ISO-8601 timestamp",
  "semantic_results_visible": false,
  "cliff_blinded": true,
  "consequences": "Interpretation consequences",
  "artifact_hashes": ["Affected artifact SHA256"]
}
```

Use the returned SHA256 as `--amendment-sha256` on the second capture. Amendments
and their contents stay private. `verify-store --run <owned-run-directory>`
checks the receipt chain, artifact hashes, duplicate records, orphan artifacts,
and an interrupted write lock. An indeterminate store is not automatically
repaired, overwritten, or retried.

`capability.assess_capability(record, packets)` is the pure manifest-assessment
API. Actual capability receipts must identify the actual model/account/surface,
tested envelopes, formats, complete synthetic profile responses, and separate
evidence for all hidden-capture checks. The function evaluates supplied evidence;
it does not itself prove UI concealment or verify an operator's assertions.
Templates remain UNTESTED until evidence is supplied. Synthetic evidence returns
QUALIFIED_SYNTHETIC, never QUALIFIED. A mechanical or visibility failure returns
TECHNICALLY_UNAVAILABLE, never a semantic failure.

The original infrastructure delivery contacted no consumer surfaces. The later
authorized synthetic surface audit is recorded in
[SYNTHETIC_SURFACE_AUDIT_2026-09-11.md](SYNTHETIC_SURFACE_AUDIT_2026-09-11.md).
The amended test results are in
[SYNTHETIC_COPY_AUDIT_V2_2026-09-11.md](SYNTHETIC_COPY_AUDIT_V2_2026-09-11.md).
The user-authorized all-surface bounded replication is in
[SYNTHETIC_RETRY_ALL_2026-09-11.md](SYNTHETIC_RETRY_ALL_2026-09-11.md).
The qualification and remaining blinding blockers are recorded in
[PHASE_MINUS_1_QUALIFICATION_REVIEW.md](PHASE_MINUS_1_QUALIFICATION_REVIEW.md).
The later user-approved operational standard and final dispositions are in
[PHASE_MINUS_1_CLOSURE.md](PHASE_MINUS_1_CLOSURE.md); it supersedes that review's
global blinding blocker while preserving all historical evidence. A live
hidden browser/export/clipboard adapter and its actual UI qualification remain
future work. Direct Python in-memory APIs can rehearse capability assessment;
there is no CLI that admits real raters to a semantic study.

## Two-freeze interfaces

- `SyntheticCase` generates its own fabricated content. The packet renderer does
  not accept caller-supplied scientific objects or experimental input files.
- `assign_roles` admits only synthetic-qualified evidence in this delivery. It
  assigns the eight model-independent roles after qualification, requiring at
  least three raters and at most three roles per rater. All qualified members of
  the proposed roster are used. Actual evidence cannot enable a real freeze.
- `SyntheticStudy.freeze_a` snapshots the corpus identities, roles/prompts,
  scientific task, missingness, access, adaptation, and interpretation rules.
  There is no human ordering algorithm in Freeze A.
- `record_screen` preserves individual label/reason/provenance records or an
  explicit technical disposition. A malformed batch supplies no favorable
  partial rows. Normalization supports JSON and delimited text without model
  repair. Raw responses belong in the separate immutable store.
- `close_frontier` requires coverage of every planned rater/candidate cell,
  including explicit failed dispositions. Private content becomes accessible
  through `private_frontier` only after closure.
- `amend_interstudy` records private content-informed findings, design changes,
  justification, access identities, blinding, timestamp, and referenced hashes.
  It supplies no semantic verdict.
- `freeze_b` snapshots explicit synthetic eligibility rationale, selections,
  seed, challenge/expansion allocations, attention ceiling, reread/stop rules,
  and visibility. Caller mutation cannot alter either freeze.
- `human_packet` uses an allowlist and omits frontier information, earlier
  labels, configuration identity, selection rationale, and challenge labels.
- `Review` accepts only SYNTHETIC provenance. `review` enforces release order,
  distinct sessions for rereads, and a two-review limit. Real labels are blocked.
- `diagnostic_form` opens the optional eleven dimensions only after a detected
  concern. `record_diagnostics` preserves only the dimensions actually supplied;
  diagnostics never manufacture a semantic verdict.
- `outcome` computes provisional gate state from synthetic human evidence. It
  neither judges fidelity nor nominates R_0_6. A later confirmed shared miss can
  require extra scrutiny of a survivor previously meeting its local gates.

The bundled `synthetic_design` is a fixture, **not the real Study-2 design**.
It demonstrates three discovery cases, nine challenge cases, and a four-case
conditional expansion per configuration. Random fixture allocations reproduce
from a seed; fixture source classes are not real scientific class selections.
The actual human design must be constructed after the actual frontier study.

This first simulation intentionally supports one executable gate policy: material
concerns pause expansion, a second conflicting review leaves insufficient
evidence, and corruption/source-ineligibility needs an amendment rather than
automatic replacement. It does not invent a flexible policy language. Broader
approved interstudy choices can be implemented and synthetically tested before
the eventual Freeze B. No human design is being prematurely frozen here.

## Safety and interpretation limits

The offline guard denies network connection/DNS, subprocess launches, model and
production imports, named prohibited archive paths, and production writes in
task-owned guarded execution. Entry points have no real-input loader or live
submission path. These are process-local safeguards, not an OS sandbox or a
security guarantee against a malicious local administrator, arbitrary imports
outside the guard, or renamed external files.

Store permissions use the platform's inherited private temp-directory ACL plus
`chmod(0700)` where meaningful. This does **not** claim Windows ACL isolation
from Cliff or other processes running as his account. Actual blinded collection
still requires qualified hidden automation and operational access controls.
Hash-linked receipts detect accidental corruption; they are not tamper-proof
custody. No encryption or production credentials are introduced.

Tests use invented paths to prove archive access is blocked before file opening.
They do not inspect or hash actual candidate observations, sealed mappings, or
adjudication packets. Existing experimental and production artifacts are not
opened by this package's commands.

See [METHODS.md](METHODS.md) for the governing method and remaining execution gates.
