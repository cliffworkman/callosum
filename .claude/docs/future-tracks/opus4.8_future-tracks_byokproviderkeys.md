# Future track — Bring-your-own-key multi-provider (settings modal)

**Disposition for CC:** Capture into the backlog + `.claude/docs/future-tracks/`. Build-ready and **load-bearing
for the shared/open release** — Callosum can't ship its own key once others run it. Runs through the Principles
gate (should clear) + the **security audit gate** (key storage = secret storage; new per-provider egress). It
surfaces the existing Protocol-based provider seam to the user.

## What it is
A settings-modal feature that lets the user supply their own API key and choose the LLM provider for Callosum's
**generation** functions (synthesis, help assistant) — the functions currently routed through Gemini. The user's
content goes to the user's chosen provider under the user's own account, or to a local model with no egress at all.

## Scope
- **Generation only** (synthesis, help assistant). **Not embeddings** — those stay local (sentence-transformers +
  sqlite-vec); no code path routes them through a provider.

## Providers
- **First-class adapters:** Gemini, OpenAI, Anthropic.
- **One OpenAI-compatible adapter** with a **custom base-URL field** — covers the long tail (Mistral, DeepSeek,
  Groq, OpenRouter, …) *and* the local runners (Ollama, LM Studio, llama.cpp server) in a single code path, since
  they all speak the OpenAI format. This delivers "any popular LLM" without N integrations.
- **Local models are first-class via the compatible adapter** — the zero-egress, zero-cost path, and the
  structural cure for "a closed cloud model under a local-first tool." Surface it as a genuine option.

## The validation lock (the lock mechanism, gated on conformance not vendor)
- Each provider key field carries a **lock**. An **unvalidated** provider's field is locked; to use it the user
  clicks unlock → **acknowledges a disclaimer** → the field unlocks. The field **cannot unlock until the disclaimer
  is acknowledged**.
- **The lock gates on validation, not vendor identity.** "Validated" = **passed Callosum's provider conformance
  eval**, NOT "is Gemini." This avoids re-enshrining Gemini as the blessed provider (the whole point was to reduce
  that dependency) and keeps the line principled and extensible — any provider, including a local model, that
  passes graduates to unlocked.
- **Ships now without waiting on the eval.** Until the eval exists, the honest framing is "**developed against
  Gemini; this provider is unvalidated**" — do not claim "tested" before testing exists. When the eval lands,
  "validated" upgrades from "developed-against" to "passed the check," and **all three first-class providers are
  validated and unlocked equally** (run the eval against each), so no single vendor is the privileged default.

## The disclaimer (precise — quality, not correctness)
The warning is about **usefulness, not honesty**, because the verification layer holds regardless of provider.
Content, roughly:

> Callosum was developed against Gemini. This provider hasn't been validated, so synthesis quality and format
> reliability may be worse, and it may produce more flagged or failed verifications — or, in the worst case,
> output Callosum can't use. Callosum still checks every claim against its source, so an unvalidated provider can
> make synthesis **less useful, not less honest**. Quality is never guaranteed for any provider, and especially
> not for unvalidated ones.

- **Tone:** a heads-up / quality caveat, **not** a safety or danger warning. Nothing here is unsafe; it's
  unvalidated.

## Two distinct failure modes (both handled — verification covers only one)
- **Lower verification hit-rate:** the provider produces more unverifiable claims. The verification layer
  **catches** this — the user sees flags. Integrity holds.
- **Malformed / unparseable output:** the provider returns structure Callosum can't parse. Verification does
  **not** cover this — it's a break, not a flag. So the provider layer must **degrade gracefully**: validate the
  provider's output shape, fail closed with a clear error ("this provider returned output Callosum couldn't use"),
  never crash, never silently proceed. The conformance eval must test for **parseable structured output**, not
  just answer quality.

## Key storage (security-audit gate)
- API keys are **secrets**: store in the **OS keychain** where available, else **encrypted at rest** — never
  plaintext config, never logged, never written to a backup, never transmitted to Callosum HQ. (Same
  secrets-hygiene that bit the backup zips earlier.)
- Per-provider **egress consent**: each cloud provider is an egress destination behind the existing consent gate;
  the local option is zero-egress and needs no egress consent.

## First-run / default
With BYOK-no-key, the generation features are **inactive until a provider is configured** — state this plainly so
first-run doesn't feel broken. Guide the user to either supply a cloud key or point at a local model. (Open:
whether to ship a recommended default or present the choice neutrally — lean toward presenting the validated set
with the local zero-cost path clearly available.)

## Architecture fit
Surfaces the existing Protocol-based provider DI seam; the adapter set is swappable behind it. The verification
layer is provider-independent and is what makes BYOK safe — **no provider can make Callosum lie, only less
useful.**

## Gates
- **Principles gate:** provider-agnosticism, honest disclaimers, and verification-protects-integrity all align;
  expect a clean pass.
- **Security audit gate:** fires — key/secret storage, new per-provider egress destinations, malformed-output
  handling. Document storage (keychain/encrypted; no plaintext/logs/backups/telemetry), per-provider egress
  consent, and output validation. End **PASS** or **RISK ACCEPTED BY USER**.

## Tests / acceptance criteria
- A user can add a key and select any first-class provider; synthesis routes through the chosen provider.
- The OpenAI-compatible adapter works against a custom base URL (covers long-tail + local).
- An **unvalidated** provider's field is **locked**, and unlocks **only** after the disclaimer is acknowledged.
- "Validated/unlocked" is driven by the **conformance result**, not a hardcoded vendor name.
- **Keys are never stored in plaintext, logged, backed up, or transmitted** (each asserted).
- **Malformed provider output fails closed with a clear error** — no crash, no silent bad result.
- **Embeddings remain local** — no code path routes them through a provider.
- The disclaimer states quality-not-correctness and reads as a heads-up, not a danger warning.

## OUTPUT
A settings-modal BYOK system for the generation functions: first-class Gemini/OpenAI/Anthropic adapters plus an
OpenAI-compatible/custom-base-URL adapter covering the long tail and local models; per-field validation locks
gated on a conformance eval (not vendor identity), with honest "developed-against/unvalidated" language until the
eval lands and all three first-class providers validated equally thereafter; a precise quality-not-correctness
disclaimer; graceful handling of both the lower-hit-rate and malformed-output failure modes; secure
keychain/encrypted key storage with per-provider egress consent; embeddings left local; and the verification layer
intact as the guarantee that no provider can compromise Callosum's integrity.
