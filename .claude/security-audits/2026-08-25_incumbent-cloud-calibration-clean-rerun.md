# Security audit — clean funded Gemini calibration rerun

Date: 2026-08-25/26

## Scope

Executed the already-frozen developer-only `benchmark-calibration-v1` study against Gemini only. Production
routing, provider defaults, prompts, parsers, credentials, and user-facing behavior remain unchanged.

## Findings

- **Egress:** 96 fresh requests containing only frozen synthetic qualification claims were sent to
  `gemini-2.5-flash-lite`. No OpenAI or Anthropic client was called. The challenge holdout remained structurally
  inaccessible.
- **Credentials:** the dedicated funded Gemini key was mapped into an approved temporary slot file under ignored
  `.local` storage. The file was removed immediately after provider execution. No key appears in argv, tracked
  receipts, logs, packet metadata, or documentation.
- **Excluded evidence:** prior pilot/partial response files were never read by the clean runner and remain excluded.
- **Raw output:** fresh synthetic raw responses, the human packet, and the decode key remain gitignored. Only
  aggregate metrics and hashes are tracked.
- **Blinding:** packet and decode key are separate. A case-insensitive scan found no provider, model, cloud/local,
  or historical candidate label in the final reviewer packet.
- **Cost:** the frozen preflight limited a complete run to 108 attempts and USD 2.00. Execution used 96 attempts,
  zero retries, and USD 0.0069285 at paid list prices.
- **Secrets/paths:** tracked-result scans found no configured secret value or private absolute path.

Security Audit: PASS
