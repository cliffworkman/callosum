You are running a single callosum QA route, non-interactively, to completion, with no human in the loop.

## Your assignment

Read and execute the QA route file at:

    {ROUTE_FILE}

That file is the complete contract: it tells you how to stand up a clean seeded instance of callosum,
which end-user surfaces to exercise, the standing honesty-invariant assertions, the adversarial checklist,
and the exact reporting format. Follow it precisely. Also read `.claude/QA-POLICY.md` once for the severity
rubric and the invariant definitions if anything in the route file is unclear.

## Non-negotiables

- **Fixture contract:** run ONLY against a freshly migrated + seeded throwaway SQLite DB on a free
  `127.0.0.1` port (see the route file's Environment section / `tools/qa/_qa_serve.py` if present). NEVER
  point `CALLOSUM_DB_URL` at the user's real library or any path under their Dropbox. Tear the server down
  when finished.
- **Egress:** leave `CALLOSUM_ALLOW_DATA_EGRESS` UNSET unless the route file is an explicit Tier-2 egress
  route. Capture every outbound request; a request to a Gemini/generativelanguage/genai host while egress is
  unset is a **Critical** finding to report (do not suppress it, do not "fix" it — report it).
- **Console budget:** collect every console `error` and `pageerror`; zero is the target.
- You MAY mutate the seeded library freely (it is disposable). Do not touch anything outside the repo
  working directory and its temp DB.

## You MUST finish by depositing your report

Write your consolidated, severity-ordered bug report (lead with Critical/High, collapse the rest) to EXACTLY:

    .claude/qa-inbox/{RUN_ID}/{ROUTE_STEM}.md

and save all screenshots under:

    .claude/qa-inbox/{RUN_ID}/screenshots/

Create those directories if they do not exist. The supervisor detects completion by the presence of that
markdown file — if you do not write it, the route is treated as failed. After writing it, stop.
