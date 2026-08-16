"""Centralized capability labels for the immutable public demo."""

from app.backend.demo_snapshot import DemoWorkspaceCapability

WORKSPACE_CAPABILITIES = {
    "profile": DemoWorkspaceCapability(
        mode="saved",
        note="Inspect two demo-corpus publications plus saved citation gaps, emerging topics, and citing authors.",
    ),
    "library": DemoWorkspaceCapability(
        mode="saved", note="Browse and search the curated public library and inspect its licensed documents."
    ),
    "library.wip": DemoWorkspaceCapability(
        mode="saved", note="Inspect two synthetic manuscripts, genuine saved checks, tasks, sources, and checkpoints."
    ),
    "synthesis.ask": DemoWorkspaceCapability(
        mode="saved", note="Inspect the completed synthesis, sentence-level evidence, coverage, and verification."
    ),
    "synthesis.critique": DemoWorkspaceCapability(
        mode="saved", note="Inspect saved deterministic critical-reading results for every curated paper."
    ),
    "synthesis.meta-preregistration": DemoWorkspaceCapability(
        mode="saved",
        note="Inspect the saved OSF crosswalk and its evidence-bounded, reversible AI display triage.",
    ),
    "discover.feed": DemoWorkspaceCapability(
        mode="saved",
        note="Inspect nine saved source subscriptions and their cached public results; refresh is unavailable.",
    ),
    "discover.search": DemoWorkspaceCapability(
        mode="saved", note="Inspect a saved public-provider scholarly search; new searches are unavailable."
    ),
    "discover.journals": DemoWorkspaceCapability(
        mode="saved", note="Inspect a saved journal decision-support run; new matching runs require the local app."
    ),
    "discover.funding": DemoWorkspaceCapability(
        mode="saved",
        note="Inspect saved funding results, source coverage, and bounded AI fit labels; refresh is unavailable.",
    ),
    "discover.followed-authors": DemoWorkspaceCapability(
        mode="saved", note="Inspect a saved followed-author profile and cached public works; changes are unavailable."
    ),
    "work.cite": DemoWorkspaceCapability(
        mode="saved", note="Inspect saved evidence-aware citation suggestions produced from the demo library."
    ),
    "work.meta-reference": DemoWorkspaceCapability(
        mode="saved", note="Inspect saved reference-integrity, concentration, equity, and citation-context results."
    ),
    "work.credit": DemoWorkspaceCapability(
        mode="saved", note="Inspect and locally explore a saved CRediT grid and formatted statement."
    ),
    "work.statements": DemoWorkspaceCapability(
        mode="saved", note="Inspect saved open-science and disclosure drafts; edits remain browser-local."
    ),
    "work.meta-analyze": DemoWorkspaceCapability(
        mode="saved", note="Inspect a saved provenance-anchored extraction project and converted effects."
    ),
    "help": DemoWorkspaceCapability(
        mode="saved", note="Browse Callosum's bundled help corpus; AI help answers are unavailable."
    ),
    "settings": DemoWorkspaceCapability(
        mode="visible-disabled",
        note="Inspect provider, egress, sync, account, editor, terminal, agent, onboarding, and theme boundaries; changes require the installed local app.",
    ),
}
