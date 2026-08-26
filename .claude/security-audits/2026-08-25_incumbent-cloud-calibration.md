# Security audit — incumbent cloud calibration benchmark

Date: 2026-08-25

## Scope

Developer-only benchmark tooling sends only the frozen synthetic synthesis-Overview fixtures to Callosum's current
Gemini model. Production routing, provider defaults, prompts, parsers, credentials, and user-facing behavior remain
unchanged.

## Threat review

- **Egress:** only frozen privacy-safe synthetic claims may be submitted; the challenge holdout is structurally
  unavailable to the runner.
- **Secrets:** credentials are read from the existing ignored `.env` research source, held in memory, omitted from
  argv, errors, raw receipts, aggregate receipts, blinded packets, and logs. Rotation is bounded to the three
  explicitly authorized Gemini slots.
- **Cost/resource bounds:** a frozen request/retry cap and a conservative token-price preflight must remain below
  `CALLOSUM_BENCHMARK_MAX_USD` (default USD 2.00) before generation begins.
- **Untrusted output:** provider text is retained only in gitignored research storage and parsed/scored through the
  existing production Overview parser and frozen mechanical scorer. Public receipts contain aggregates and hashes.
- **Blinding:** reviewer packet and decode material are separate; model/provider/execution identity is absent from
  the packet.
- **Paths:** committed schemas and aggregate receipts cannot contain absolute user, temporary, or secret paths.
- **Supply chain:** no dependency is added; the pinned `google-genai` client and existing provider runtime are reused.

## Negative-path checks

Focused tests cover the cost ceiling, missing usage, secret redaction, holdout refusal, packet/decode separation,
protocol-ineligible comparator isolation, deterministic freezes, and cloud-hardware non-fabrication. The live run
also exercised quota rotation and fail-stop behavior. An initial retry-scope defect was preserved as an invalidated
pilot and corrected through an explicit, hashed amendment before the clean rerun.

## Result

The amended run exhausted every authorized provider quota and stopped before Track B. No secret, raw output,
private path, or decode key was committed. Existing production provider behavior was untouched.

Security Audit: PASS
