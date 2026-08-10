# Increment 471 — public website and showcase refresh

## Goal

Bring `www/index.html` and `www/showcase.html` forward from their last substantive content commit on July 21,
2026. Git history established that cutoff; everything above the corresponding point in `.claude/changes.md`
was reviewed rather than treating the current README as a generic rewrite prompt. Increment 472 landed
concurrently during the refresh, so the final source-build copy also names its terminal client and the existing
read-only MCP server, and the published test count follows the resulting 2,098-test baseline.

## Editorial decisions

- Kept verified, sentence-level synthesis as the hero and product thesis. The intervening work broadens the
  workflow around that core; it does not replace it.
- Changed the product category from “reference manager” to “research workspace,” and the lifecycle from six
  stages to seven: Find, Acquire, Read, Evaluate, Synthesize, Draft, Cite.
- Replaced obsolete Theory/Methods-pane taxonomy with workflows researchers can recognize: library and reading,
  synthesis and registrations, methods and review, discovery and context, writing and citing, and system-wide
  status/usage.
- Rewrote privacy literally. PDFs, notes, indexes, checks, and citation rendering remain local. Public metadata
  lookups send identifiers/queries; configured AI sends displayed task context; encrypted sync is opt-in; and
  feedback leaves only after an exact preview. These are separate explicit doors, not “the one door.”
- Restored all three vetoes: no paywall circumvention, no protected-store access, and no accusation of people.
- Kept pre-1.0 posture prominent: single-user-focused, unsigned installers, moving interface, not a hardened
  multi-tenant hosted service.

## Showcase architecture

The old showcase embedded all 50 screenshots as base64 despite also keeping them in `www/shots`, producing a
6.4 MB HTML file and making routine updates difficult. The replacement is about 23 KB and references curated
external PNGs. Twelve current captures were taken read-only from the live app and combined with still-accurate
detail crops from the existing set. No screenshot containing private account information was published.

The new tour contains six chapters and 22 figures. Captions state limits where they matter: AI proposes
meta-analysis cells, registration acquisition is explicit, repeated-values is a neutral heuristic, z-curve has a
hard small-N warning, and contribution statements format only what the user asserts.

## Verification

- Local HTML reference audit: all relative links and image sources resolve; every image has an `alt` attribute.
- Chromium, desktop 1440×1000 and mobile 390×844: both pages load; all images decode; no horizontal overflow;
  no console errors or page errors.
- Full-page screenshots reviewed at both widths. The landing page keeps a legible evidence-first hierarchy; the
  showcase remains navigable and preserves figure order on a narrow screen.
- Persona pass: a skeptical first-time visitor can identify the core claim, current scope, privacy boundary, and
  pre-1.0 status; a researcher moving from evidence to manuscript can follow source → synthesis/registration →
  methods → WIP checkpoint → citation without a taxonomy jump.
- `git diff --check` clean.

Application tests are unchanged by this static increment; the repository baseline advanced concurrently to 2,098
with increment 472's TUI contribution. The served in-app help corpus does not need a sync: this increment changes
no application behavior or user-facing app workflow.
