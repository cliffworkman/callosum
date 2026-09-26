# Standing experiment gate (Cliff, 2026-09-25)

**No experiment runs without a plain-English brief and Cliff's explicit confirmation of that specific experiment.**
This applies to the q_lld / q_builtenv transfer tests and every later E2E comparison. It does not restrict engine
implementation, unit tests, or development checks on the q_aib development target.

## The brief (before any technical protocol)

1. **What actually runs.** Which software and which models, and exactly what differs between conditions.
2. **What it can and cannot establish.** Plain claims, plain limits.
3. **What outputs will be examined, and what decision they inform.**
4. **Expected time and model-credit cost, and the stop condition.**

## Confirmation

- Wait for Cliff's explicit statement that he understands and authorizes **that specific experiment**.
- **No approval by silence. No approval by a previous general authorization.** A new experiment needs a new confirmation.
- Record the confirmation in an authorization file (JSON: `experiment_id`, `question_sha256s`, `authorized_by`,
  `authorized_at`, `brief_confirmed: true`).

## Mechanical guard

`decompose/gate.py` refuses to run the protected questions (q_lld, q_builtenv) through the decomposition CLI unless
`--experiment-authorization FILE` names the question's sha256 and carries `brief_confirmed: true`. It is a speed
bump against running an experiment by accident, not a security boundary; the rule itself is the human gate above.
