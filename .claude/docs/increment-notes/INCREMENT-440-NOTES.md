# Increment 440 — deterministic funding partial-provider coverage

## Outcome

The sole open near-term code item, backlog #51, is closed. Funding Discovery's selected-paper partial-provider test
now proves that a failed Grants.gov provider remains visible while deterministic evidence from another provider still
produces a funding prospect. The test no longer contacts or depends on OpenAlex or Crossref.

The operational activation work for inc 439's feedback relay is also preserved as backlog #52. It records the private
Slack destination, hosted secret, relay deployment, ingress/logging, rate-limit, failure-path, synthetic-report,
monitoring, rotation, and disable checks without placing a credential in the repository or distributed client.

## Root cause and correction

`test_selected_paper_mode_and_provider_partial_failure_visibility` replaced only
`funding_grants_gov_client`. Because the application intentionally constructs real OpenAlex and Crossref providers
when their test seams are unset, the test made two external searches and relied on those mutable results to satisfy
`funding_prospects`. That explains both the one-off CI failure and the roughly 25-second isolated run; the production
provider aggregation was not racing.

The test now injects:

- one matching `FixtureAwardHistoryProvider` record as its known successful evidence source;
- an explicit empty-success `OpenAlexFundingProvider` fetcher;
- an explicit empty-success `CrossrefFundingProvider` fetcher; and
- the existing explicit failed Grants.gov fetcher.

It additionally asserts the local provider's successful status, so “partial failure” cannot pass with only a failed
provider and an accidentally populated result.

## Verification

- Before the correction, the isolated test passed in **25.09 s** while making default-provider requests.
- `uv run pytest tests/test_funding_discovery.py::test_selected_paper_mode_and_provider_partial_failure_visibility -q --durations=1`
  — **1 passed in 10.01 s** including application/pytest startup; the test call itself no longer appears among the
  reported slow duration.
- `uv run pytest tests/test_funding_discovery.py -q --durations=10` — **28 passed in 37.01 s**.
- Five separate-process reruns of the focused test — **5/5 passed** (**8.29–8.97 s** each including startup).
- Post-format `uv run pytest tests/test_funding_discovery.py -q` — **28 passed in 38.73 s**.
- `uv run ruff format --check tests/test_funding_discovery.py` — **passed**.
- `uv run ruff check tests/test_funding_discovery.py` — **passed**.
- `git diff --check` — **passed**.

## Product, privacy, and security

No production code, endpoint, UI, schema, stored data, authorization, dependency, egress behavior, or user-visible
workflow changed. The correction removes unintended test-suite egress. Backlog #52 names only environment-variable
keys and operational steps; it contains no Slack workspace, channel, webhook, host, account, or other secret value.

## Rollback

Remove the three deterministic provider seams and fixture award from the focused test, restore backlog #51 to open,
and remove backlog #52 only if the feedback relay is intentionally abandoned. No application or data rollback is
required.
