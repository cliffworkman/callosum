"""The single source of truth for the callosum TUI: every feature as a declarative Action.

Menus (tui/menus.py), one-shot subcommands (tui/__main__.py), and the agent-mode gate are all
generated from ACTIONS, so the three surfaces cannot drift. Each Action maps one menu item /
subcommand to one HTTP endpoint of the running callosum app.

Write tiers:
- "read"        — no mutation (GETs, plus POSTs that only compute/render/search).
- "write"       — additive or reversible mutation. In agent mode these are allowed ONLY when
                  `agent_path` remaps them to a gated, audited `/agent/*` endpoint (or the path
                  already lives under `/agent/`); everything else is refused.
- "destructive" — delete/merge/trash. Human-only, always confirmed (y/N in the REPL, --yes in
                  one-shot). Never available in agent mode — this mirrors callosum's own
                  structural guarantee that no destructive `/agent/*` route exists.

Job endpoints (202 + poll) declare `job=` with the poll-path template; the client turns
submit+poll into one call unless --no-wait is passed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

READ, WRITE, DESTRUCTIVE = "read", "write", "destructive"

# Path params are auto-derived from {placeholders}; everything here is ints except these.
_STR_PATH_PARAMS = {"job_id", "work_id"}


@dataclass(frozen=True)
class Param:
    """One query or body parameter an action accepts (path params are auto-derived)."""

    name: str
    kind: str  # "query" | "body"
    type: str = "str"  # str | int | float | bool | json (json = parsed JSON fragment)
    required: bool = False
    help: str = ""


@dataclass(frozen=True)
class Action:
    group: str  # subcommand area / menu group key, e.g. "papers"
    name: str  # subcommand name / menu item key, e.g. "list"
    title: str  # human menu label
    method: str
    path: str  # template with {param} placeholders
    tier: str = READ
    params: tuple[Param, ...] = ()
    job: str | None = None  # poll-path template containing {job_id}
    agent_path: str | None = None  # gated /agent/* equivalent used in agent mode
    help: str = ""

    @property
    def path_params(self) -> tuple[str, ...]:
        return tuple(re.findall(r"{(\w+)}", self.path))

    def agent_allowed(self) -> bool:
        """Available when the TUI runs in --agent mode?"""
        if self.tier == READ:
            return True
        if self.path.startswith("/agent/") or self.agent_path is not None:
            return True
        return False

    def effective_path(self, agent: bool) -> str:
        return self.agent_path if (agent and self.agent_path) else self.path


def _q(name: str, type: str = "str", required: bool = False, help: str = "") -> Param:
    return Param(name, "query", type, required, help)


def _b(name: str, type: str = "str", required: bool = False, help: str = "") -> Param:
    return Param(name, "body", type, required, help)


@dataclass(frozen=True)
class Group:
    key: str
    title: str
    blurb: str = ""


GROUPS: tuple[Group, ...] = (
    Group("papers", "Library & papers", "list/search/detail, read state, priority, export, metadata"),
    Group("fulltext", "Full-text search", "passage search across ingested PDFs"),
    Group("discovery", "Discovery & feed", "external literature search, followed sources"),
    Group("wanted", "Wanted list", "papers to acquire; coverage; OA recheck"),
    Group("queue", "Reading queue", "the to-read stack"),
    Group("tags", "Tags & axes", "tags, colors, axes, cluster membership"),
    Group("gaps", "Gaps & findings", "literature gap-finder; FACT-vs-CANDIDATE findings"),
    Group("methods", "Methods audits", "statcheck, GRIM, p-curve, retraction, transparency, equity, LMM"),
    Group("citations", "Citations", "styles, render, suggest, per-paper export"),
    Group("summaries", "Summaries", "structured paper summaries"),
    Group("mypubs", "My publications", "your ORCID-backed publication dashboard"),
    Group("library", "Library ops", "scan, watched folders, import/export, OCR, duplicates"),
    Group("status", "Status & settings", "health, settings, sync, agent-write audit"),
)


ACTIONS: tuple[Action, ...] = (
    # ---- papers -----------------------------------------------------------------
    Action("papers", "list", "List / search papers", "GET", "/papers",
           params=(_q("q", help="search text"), _q("limit", "int"), _q("offset", "int"),
                   _q("tag", help="filter by tag name"), _q("status"), _q("item_type"),
                   _q("sort"), _q("order"))),
    Action("papers", "item-types", "Item-type counts", "GET", "/papers/item-types"),
    Action("papers", "get", "Paper detail", "GET", "/papers/{paper_id}"),
    Action("papers", "chunks", "Paper text chunks", "GET", "/papers/{paper_id}/chunks",
           params=(_q("limit", "int"), _q("offset", "int"))),
    Action("papers", "annotations", "List annotations", "GET", "/papers/{paper_id}/annotations"),
    Action("papers", "annotate", "Add annotation (agent: audited note)", "POST",
           "/papers/{paper_id}/annotations", tier=WRITE,
           agent_path="/agent/papers/{paper_id}/notes",
           params=(_b("text", required=True, help="note text"),)),
    Action("papers", "edit", "Edit metadata (title/authors/year/…)", "PATCH", "/papers/{paper_id}",
           tier=WRITE, help="human-only; pass fields via --body JSON"),
    Action("papers", "read", "Mark read / unread", "POST", "/papers/{paper_id}/read", tier=WRITE,
           params=(_b("read", "bool", required=True),)),
    Action("papers", "priority", "Set priority", "POST", "/papers/{paper_id}/priority", tier=WRITE,
           params=(_b("priority", help="high|normal|low, empty to clear"),)),
    Action("papers", "export", "Export citations (bibtex/ris/csl-json)", "POST", "/papers/export",
           params=(_b("paper_ids", "json", required=True, help='e.g. [1,2,3]'),
                   _b("format", required=True, help="bibtex|ris|csl-json"))),
    Action("papers", "pdf", "Download PDF", "GET", "/papers/{paper_id}/pdf",
           help="binary; use --out FILE"),
    Action("papers", "re-resolve", "Re-resolve metadata (Crossref)", "POST",
           "/papers/{paper_id}/re-resolve", tier=WRITE),
    Action("papers", "fill-metadata", "Fill missing metadata", "POST",
           "/papers/{paper_id}/fill-metadata", tier=WRITE),
    Action("papers", "delete", "Move to trash", "DELETE", "/papers/{paper_id}", tier=DESTRUCTIVE),
    Action("papers", "restore", "Restore from trash", "POST", "/papers/{paper_id}/restore", tier=WRITE),
    Action("papers", "delete-permanent", "Delete permanently", "DELETE",
           "/papers/{paper_id}/permanent", tier=DESTRUCTIVE),
    Action("papers", "empty-trash", "Empty trash", "POST", "/papers/trash/empty", tier=DESTRUCTIVE),
    Action("papers", "acquire-oa", "Acquire open-access PDF", "POST", "/papers/{paper_id}/acquire-oa",
           tier=WRITE, job="/papers/acquire-oa/{job_id}"),
    Action("papers", "citation-context", "Citation-context run", "POST", "/papers/citation-context/run",
           job="/papers/citation-context/run/{job_id}"),
    Action("papers", "citation-counts", "Refresh citation counts", "POST",
           "/papers/citation-counts/refresh", job="/papers/citation-counts/refresh/{job_id}"),
    Action("papers", "save-reference", "Save a reference by DOI (audited)", "POST",
           "/agent/references", tier=WRITE,
           params=(_b("identifier", required=True, help="DOI"),),
           help="creates a metadata-only record via Crossref; audited + revertible"),
    # ---- fulltext ---------------------------------------------------------------
    Action("fulltext", "search", "Search full text", "GET", "/papers/fulltext",
           params=(_q("q", required=True), _q("limit", "int"))),
    # ---- discovery & feed -------------------------------------------------------
    Action("discovery", "search", "Search external literature", "GET", "/discovery/search",
           params=(_q("q", required=True), _q("provider"), _q("limit", "int"))),
    Action("discovery", "relevance", "Score relevance vs library", "POST", "/discovery/relevance",
           help="--body {items:[{dedup_key,title,abstract}]}"),
    Action("discovery", "save", "Save a discovered paper", "POST", "/discovery/save", tier=WRITE,
           agent_path="/agent/references",
           params=(_b("title"), _b("doi"), _b("abstract"), _b("authors", "json"),
                   _b("journal"), _b("year", "int"), _b("url"),
                   _b("identifier", help="agent mode: DOI (only field sent)")),
           help="agent mode saves by DOI via /agent/references instead"),
    Action("discovery", "feed", "Show feed", "GET", "/feed",
           params=(_q("state"), _q("limit", "int"))),
    Action("discovery", "subscriptions", "List feed subscriptions", "GET", "/feed/subscriptions"),
    Action("discovery", "subscribe", "Add feed subscription", "POST", "/feed/subscriptions",
           tier=WRITE, help="--body per feed kind (journal/author/query)"),
    Action("discovery", "unsubscribe", "Remove subscription", "DELETE", "/feed/subscriptions/{sub_id}",
           tier=WRITE),
    Action("discovery", "feed-refresh", "Refresh feed now", "POST", "/feed/refresh",
           job="/feed/refresh/{job_id}"),
    Action("discovery", "feed-state", "Set feed item state", "POST", "/feed/items/{item_id}/state",
           tier=WRITE, params=(_b("state", required=True, help="e.g. read|saved|dismissed"),)),
    Action("discovery", "feed-mark-read", "Mark all read", "POST", "/feed/mark-read", tier=WRITE),
    # ---- wanted -----------------------------------------------------------------
    Action("wanted", "list", "List wanted papers", "GET", "/wanted"),
    Action("wanted", "coverage", "Coverage report", "GET", "/wanted/coverage"),
    Action("wanted", "add", "Add to wanted list", "POST", "/wanted", tier=WRITE,
           params=(_b("doi"), _b("pmid"), _b("title"), _b("note"), _b("paper_id", "int")),
           help="/wanted is deliberately human-gated; agents: use papers save-reference"),
    Action("wanted", "remove", "Remove wanted item", "DELETE", "/wanted/{item_id}", tier=WRITE),
    Action("wanted", "sync-library", "Sync against library", "POST", "/wanted/sync-library", tier=WRITE),
    Action("wanted", "recheck", "Recheck OA availability", "POST", "/wanted/recheck",
           job="/wanted/recheck/{job_id}"),
    # ---- reading queue ----------------------------------------------------------
    Action("queue", "list", "Show reading queue", "GET", "/reading-queue"),
    Action("queue", "add", "Add paper to queue", "POST", "/reading-queue", tier=WRITE,
           params=(_b("paper_id", "int", required=True),)),
    Action("queue", "reorder", "Reorder queue", "PUT", "/reading-queue/order", tier=WRITE,
           params=(_b("paper_ids", "json", required=True, help="[id,id,…] full order"),)),
    Action("queue", "remove", "Remove from queue", "DELETE", "/reading-queue/{paper_id}", tier=WRITE),
    # ---- tags & axes ------------------------------------------------------------
    Action("tags", "list", "List tags", "GET", "/tags"),
    Action("tags", "colors", "Available tag colors", "GET", "/tags/colors"),
    Action("tags", "color", "Set tag color", "POST", "/tags/{tag_id}/color", tier=WRITE,
           params=(_b("color", required=True),)),
    Action("tags", "suggested", "Suggested tags for paper", "GET", "/papers/{paper_id}/suggested-tags"),
    Action("tags", "add", "Tag a paper (agent: audited)", "POST", "/papers/{paper_id}/tags",
           tier=WRITE, agent_path="/agent/papers/{paper_id}/tags",
           params=(_b("tag", required=True, help="tag name"),)),
    Action("tags", "remove", "Untag a paper", "DELETE", "/papers/{paper_id}/tags/{tag_id}", tier=WRITE),
    Action("tags", "axes", "List axes", "GET", "/axes"),
    Action("tags", "axis-create", "Create axis", "POST", "/axes", tier=WRITE,
           params=(_b("name", required=True), _b("description"))),
    Action("tags", "axis-edit", "Edit axis", "PATCH", "/axes/{axis_id}", tier=WRITE),
    Action("tags", "axis-delete", "Delete axis", "DELETE", "/axes/{axis_id}", tier=DESTRUCTIVE),
    Action("tags", "axis-merge", "Merge axes", "POST", "/axes/merge", tier=DESTRUCTIVE,
           help="--body {source_id, target_id}"),
    Action("tags", "axis-clusters", "Axis clusters", "GET", "/axes/{axis_id}/clusters"),
    Action("tags", "axis-add-paper", "Add paper to axis (agent: audited)", "POST",
           "/axes/{axis_id}/papers", tier=WRITE, agent_path="/agent/axes/{axis_id}/papers",
           params=(_b("paper_id", "int", required=True),)),
    Action("tags", "axis-remove-paper", "Remove paper from axis", "DELETE",
           "/axes/{axis_id}/papers/{paper_id}", tier=WRITE),
    Action("tags", "axis-order", "Reorder axes", "PUT", "/axes/{axis_id}/order", tier=WRITE),
    Action("tags", "axis-score", "Score papers along axis", "POST", "/axes/{axis_id}/score",
           tier=WRITE, job="/axes/score/{job_id}"),
    Action("tags", "axis-suggest", "Suggest new axes", "POST", "/axes/suggest",
           job="/axes/suggest/{job_id}"),
    Action("tags", "axis-suggest-terms", "Suggest axis terms", "POST", "/axes/suggest-terms"),
    Action("tags", "saved-searches", "List saved searches", "GET", "/saved-searches"),
    Action("tags", "saved-search-add", "Save a search", "POST", "/saved-searches", tier=WRITE,
           params=(_b("name", required=True), _b("query", required=True))),
    Action("tags", "saved-search-remove", "Delete saved search", "DELETE",
           "/saved-searches/{search_id}", tier=WRITE),
    # ---- gaps & findings --------------------------------------------------------
    Action("gaps", "list", "List citation gaps", "GET", "/gaps",
           params=(_q("direction", help="backward|forward"), _q("axis_id", "int"))),
    Action("gaps", "refresh", "Recompute gaps", "POST", "/gaps/refresh",
           job="/gaps/refresh/{job_id}",
           params=(_b("direction", help="backward|forward"), _b("axis_id", "int"))),
    Action("gaps", "add", "Import a gap into library", "POST", "/gaps/add", tier=WRITE,
           agent_path="/agent/references",
           params=(_b("doi", required=True), _b("openalex_work_id"), _b("title"),
                   _b("identifier", help="agent mode: DOI (only field sent)")),
           help="agent mode imports by DOI via /agent/references"),
    Action("gaps", "dismiss", "Dismiss a gap", "POST", "/gaps/dismiss", tier=WRITE,
           params=(_b("doi"), _b("openalex_work_id"))),
    Action("gaps", "findings", "Findings for a paper", "GET", "/papers/{paper_id}/findings"),
    Action("gaps", "findings-overview", "Findings overview", "GET", "/findings/overview"),
    Action("gaps", "finding-review", "Review a finding (FACT/CANDIDATE)", "POST",
           "/findings/{finding_id}/review", tier=WRITE,
           params=(_b("verdict", required=True), _b("note"))),
    # ---- methods audits ----------------------------------------------------------
    Action("methods", "statcheck", "Statcheck a paper", "GET", "/papers/{paper_id}/statcheck"),
    Action("methods", "statcheck-run", "Statcheck the whole library", "POST", "/methods/statcheck/run",
           job="/methods/statcheck/run/{job_id}"),
    Action("methods", "statcheck-summary", "Statcheck library summary", "GET",
           "/methods/statcheck/summary"),
    Action("methods", "bayes", "Bayes-factor re-analysis", "GET", "/papers/{paper_id}/bayes"),
    Action("methods", "grim", "GRIM test", "POST", "/methods/grim",
           help="--body {mean, n, decimals}"),
    Action("methods", "effect-size", "Effect-size converter", "POST", "/methods/effect-size",
           help="--body per converter input"),
    Action("methods", "pcurve", "P-curve analysis", "POST", "/methods/pcurve/run",
           job="/methods/pcurve/run/{job_id}"),
    Action("methods", "retraction", "Retraction status of a paper", "GET",
           "/papers/{paper_id}/retraction"),
    Action("methods", "retraction-run", "Check library for retractions", "POST",
           "/methods/retraction/run", job="/methods/retraction/run/{job_id}"),
    Action("methods", "retraction-summary", "Retraction library summary", "GET",
           "/methods/retraction/summary"),
    Action("methods", "retraction-db", "Retraction database status", "GET",
           "/methods/retraction/database"),
    Action("methods", "retraction-db-refresh", "Refresh retraction database", "POST",
           "/methods/retraction/database/refresh", tier=WRITE,
           job="/methods/retraction/database/refresh/{job_id}"),
    Action("methods", "transparency", "Transparency signals of a paper", "GET",
           "/papers/{paper_id}/transparency"),
    Action("methods", "transparency-run", "Audit library transparency", "POST",
           "/methods/transparency/run", job="/methods/transparency/run/{job_id}"),
    Action("methods", "transparency-summary", "Transparency library summary", "GET",
           "/methods/transparency/summary"),
    Action("methods", "citation-equity", "Citation-equity audit", "POST",
           "/methods/citation-equity/run", job="/methods/citation-equity/run/{job_id}"),
    Action("methods", "citation-equity-overlooked", "Overlooked-work suggestions", "POST",
           "/methods/citation-equity/overlooked", job="/methods/citation-equity/overlooked/{job_id}"),
    Action("methods", "lmm", "LMM-reporting audit", "GET", "/papers/{paper_id}/lmm"),
    Action("methods", "meta-analysis", "Meta-analysis extraction", "GET",
           "/papers/{paper_id}/meta-analysis"),
    Action("methods", "publishers", "Where to submit (journal finder)", "POST",
           "/methods/publishers/run", job="/methods/publishers/run/{job_id}"),
    # ---- citations ---------------------------------------------------------------
    Action("citations", "styles", "List citation styles", "GET", "/citations/styles"),
    Action("citations", "render", "Render formatted citations", "POST", "/citations/render",
           params=(_b("paper_ids", "json", required=True), _b("style"), _b("locale"))),
    Action("citations", "render-document", "Render citations + bibliography", "POST",
           "/citations/render-document", help="--body {citations:[…], style, locale}"),
    Action("citations", "suggest", "Suggest citations for text", "POST", "/citations/suggest",
           params=(_b("text", required=True), _b("top_k", "int"), _b("evaluate", "bool"))),
    # ---- summaries ---------------------------------------------------------------
    Action("summaries", "list", "List summaries", "GET", "/summaries"),
    Action("summaries", "get", "Show a summary", "GET", "/summaries/{summary_id}"),
    Action("summaries", "create", "Summarize a paper", "POST", "/summarize",
           job="/summarize/{job_id}", tier=WRITE,
           params=(_b("paper_id", "int", required=True),)),
    Action("summaries", "reverify", "Re-verify a summary", "POST",
           "/summaries/{summary_id}/reverify", tier=WRITE),
    Action("summaries", "delete", "Delete a summary", "DELETE", "/summaries/{summary_id}",
           tier=DESTRUCTIVE),
    # ---- my publications ----------------------------------------------------------
    Action("mypubs", "profile", "Show profile", "GET", "/my-publications/profile"),
    Action("mypubs", "profile-set", "Set profile (ORCID…)", "PUT", "/my-publications/profile",
           tier=WRITE),
    Action("mypubs", "dashboard", "Publications dashboard", "GET", "/my-publications/dashboard"),
    Action("mypubs", "refresh", "Refresh from ORCID/OpenAlex", "POST", "/my-publications/refresh",
           tier=WRITE, job="/my-publications/refresh/{job_id}"),
    Action("mypubs", "decide", "Accept/reject a candidate work", "POST", "/my-publications/decide",
           tier=WRITE),
    Action("mypubs", "domains", "Compute research domains", "POST", "/my-publications/domains",
           tier=WRITE, job="/my-publications/domains/{job_id}"),
    Action("mypubs", "domain-rename", "Rename a domain", "POST", "/my-publications/domains/rename",
           tier=WRITE),
    Action("mypubs", "work-import", "Import a work", "POST", "/my-publications/works/import",
           tier=WRITE),
    Action("mypubs", "work-dismiss", "Dismiss a work", "POST", "/my-publications/works/dismiss",
           tier=WRITE),
    Action("mypubs", "work-undismiss", "Un-dismiss a work", "POST",
           "/my-publications/works/undismiss", tier=WRITE),
    Action("mypubs", "summary-generate", "Generate research summary", "POST",
           "/my-publications/summary/generate", tier=WRITE),
    Action("mypubs", "summary-set", "Edit research summary", "PUT", "/my-publications/summary",
           tier=WRITE),
    Action("mypubs", "star", "Star/unstar a work", "POST", "/my-publications/star", tier=WRITE),
    Action("mypubs", "citing", "Who cites this work", "GET", "/my-publications/citing/{work_id}"),
    Action("mypubs", "citing-import", "Import a citing work", "POST",
           "/my-publications/citing/import", tier=WRITE),
    Action("mypubs", "reset", "Delete my-publications data", "DELETE", "/my-publications",
           tier=DESTRUCTIVE),
    # ---- library ops ---------------------------------------------------------------
    Action("library", "scan", "Scan a folder for PDFs", "POST", "/library/scan", tier=WRITE,
           job="/library/scan/{job_id}", params=(_b("path", required=True),)),
    Action("library", "watched", "List watched folders", "GET", "/library/watched"),
    Action("library", "unwatch", "Remove watched folder", "DELETE", "/library/watched/{folder_id}",
           tier=WRITE),
    Action("library", "rescan", "Rescan watched folders", "POST", "/library/watched/rescan",
           tier=WRITE, job="/library/watched/rescan/{job_id}"),
    Action("library", "enrich", "Refresh metadata enrichment", "POST", "/library/enrich/refresh",
           tier=WRITE, job="/library/enrich/refresh/{job_id}"),
    Action("library", "import", "Import (Zotero/BibTeX…)", "POST", "/library/import", tier=WRITE,
           job="/library/import/{job_id}"),
    Action("library", "bundle-export", "Export library bundle", "POST", "/library/bundle/export"),
    Action("library", "bundle-import", "Import library bundle", "POST", "/library/bundle/import",
           tier=WRITE, job="/library/bundle/import/{job_id}"),
    Action("library", "ocr", "OCR scanned PDFs", "POST", "/papers/ocr/run", tier=WRITE,
           job="/papers/ocr/run/{job_id}"),
    Action("library", "duplicates", "Find duplicates", "POST", "/papers/duplicates",
           job="/papers/duplicates/{job_id}"),
    Action("library", "duplicates-dismissed", "Dismissed duplicate pairs", "GET",
           "/papers/duplicates/dismissed"),
    Action("library", "duplicates-dismiss", "Dismiss a duplicate pair", "POST",
           "/papers/duplicates/dismiss", tier=WRITE),
    Action("library", "duplicates-undismiss", "Un-dismiss a pair", "POST",
           "/papers/duplicates/undismiss", tier=WRITE),
    Action("library", "merge", "Merge two papers", "POST", "/papers/merge", tier=DESTRUCTIVE,
           help="--body {primary_id, duplicate_id}"),
    # ---- status & settings ----------------------------------------------------------
    Action("status", "health", "Health check", "GET", "/health"),
    Action("status", "settings", "Show settings", "GET", "/settings"),
    Action("status", "settings-set", "Change settings", "PUT", "/settings", tier=WRITE),
    Action("status", "access-token", "Mint remote-access token", "POST", "/settings/access-token",
           tier=WRITE),
    Action("status", "test-key", "Test a BYOK API key", "POST", "/settings/test-key"),
    Action("status", "sync", "Sync status", "GET", "/sync/status"),
    Action("status", "sync-settings", "Change sync settings", "PUT", "/sync/settings", tier=WRITE),
    Action("status", "sync-setup", "Set up E2E sync", "POST", "/sync/setup", tier=WRITE),
    Action("status", "sync-run", "Run sync now", "POST", "/sync/run", tier=WRITE),
    Action("status", "agent-status", "Agent-writes gate status", "GET", "/agent/status"),
    Action("status", "agent-writes", "Audit log of agent writes", "GET", "/agent/writes"),
    Action("status", "agent-revert", "Revert an agent write", "POST",
           "/agent/writes/{write_id}/revert", tier=WRITE),
    Action("status", "help-corpus", "Help corpus", "GET", "/help/corpus"),
    Action("status", "help-ask", "Ask the in-app help", "POST", "/help/ask",
           params=(_b("question", required=True),)),
)


def groups() -> tuple[Group, ...]:
    return GROUPS


def actions_for(group_key: str, agent: bool = False) -> list[Action]:
    acts = [a for a in ACTIONS if a.group == group_key]
    if agent:
        acts = [a for a in acts if a.agent_allowed()]
    return acts


def find(group_key: str, name: str) -> Action | None:
    for a in ACTIONS:
        if a.group == group_key and a.name == name:
            return a
    return None


def validate() -> list[str]:
    """Registry invariants; returns a list of problems (empty = healthy)."""
    problems: list[str] = []
    keys = set()
    group_keys = {g.key for g in GROUPS}
    for a in ACTIONS:
        if (a.group, a.name) in keys:
            problems.append(f"duplicate action {a.group} {a.name}")
        keys.add((a.group, a.name))
        if a.group not in group_keys:
            problems.append(f"{a.group} {a.name}: unknown group")
        if a.tier not in (READ, WRITE, DESTRUCTIVE):
            problems.append(f"{a.group} {a.name}: bad tier {a.tier}")
        if a.tier == DESTRUCTIVE and a.agent_allowed():
            problems.append(f"{a.group} {a.name}: destructive action reachable in agent mode")
        if a.agent_path and not a.agent_path.startswith("/agent/"):
            problems.append(f"{a.group} {a.name}: agent_path must live under /agent/")
        if a.tier != READ and a.agent_allowed():
            eff = a.effective_path(agent=True)
            if not eff.startswith("/agent/"):
                problems.append(f"{a.group} {a.name}: agent-mode write outside /agent/ ({eff})")
        if a.job and "{job_id}" not in a.job:
            problems.append(f"{a.group} {a.name}: job path lacks {{job_id}}")
        for p in a.params:
            if p.kind not in ("query", "body"):
                problems.append(f"{a.group} {a.name}: param {p.name} bad kind {p.kind}")
    return problems
