# EXPERIENCE-PASS.md — the callosum end-user experience pass

This is the gate **CLAUDE.md rule #11** points to. Like its siblings, it is read before a class of change:

| Gate | Doc | The question it asks |
|---|---|---|
| #8 | `DESIGN.md` | Does it **look** right (consistent recipes/tokens)? |
| #9 | `PRINCIPLES.md` | Is it **honest** (evidence-carried, signal-not-verdict, no opaque score)? |
| #10 | `QA-POLICY.md` | Does the surface **work** + is it **covered** by a route? |
| **#11** | **this file** | Does it **serve the user** — can a real person, mid-task, actually *use* it? |

The four are complementary. A change can pass #8/#9/#10 — it looks right, it's honest, the button clicks, a
route covers it — and still **fail the user**: a correct signal with no obvious path to the action it implies, a
feature buried where no one finds it, a number with no way to reach the evidence behind it. That gap is what this
pass exists to catch.

---

## 1. The pass

Before any **user-facing** change is "done" — a new feature, a revised flow, a moved control, a new
signal/output — make one deliberate pass **inhabiting the end user of the thing you touched**. Two questions:

1. **Reception — how will the user *receive* this?** Is it discoverable and legible? Is the next step obvious? A
   correct output with no obvious path onward strands the user. *(The motivating case: statcheck reported "N
   papers flagged," but — especially when it lived in Settings — it wasn't obvious how to get from that count to
   the **specific inconsistencies** so you could weigh the evidence.)*

2. **Intended use — how will the user *want* to use this?** Trace the natural workflow around the thing: what
   does the user reach for next? Does the built feature support it, or dead-end? This question takes vigilance —
   and it is **bounded by our codified commitments**: a user may want something the ethics forbid (an
   accusation/leaderboard, paywall circumvention, an opaque "quality score"). Those desires are **declined** per
   `PRINCIPLES.md` + `APPROACH-AVOIDANCE.md`'s veto boundaries — *not* served. But for any feature we *have*
   chosen to ship, we owe it this pass: pretend to be the user and ask whether the interaction leaves anything to
   be desired.

It is a **reflective pause, not a block** (like the Principles gate). Its output is a **finding**: if the
experience leaves something to be desired, **fix it in the same increment when cheap, else file a UX follow-up to
`INCREMENT-BACKLOG.md`** — and say which. The pass is *not* satisfied by "the surface works + is covered" (that's
QA, #10) or "it looks consistent" (DESIGN, #8); it asks the harder question of whether the thing **serves the
user's actual task**.

---

## 2. The mechanism — persona-grounded experience agents

Abstract "inhabit the user" is too weak to be honest with. **Ground it:** dispatch a subagent *in character* as a
**concrete persona pursuing a specific goal in the moment**, to use the feature end-to-end and report friction,
dead-ends, and what's-left-to-be-desired — **experience, not implementation critique**. Grounding the agent in a
persona + a task is what turns a vague "is the UX good?" into a checkable "can *this* person, doing *this*, get
where they're going?"

- **Prefer to drive the built feature** (headed, against a freshly seeded instance — the QA fixture pattern,
  `tools/qa/_qa_serve.py`) exactly as the user would. **Fall back** to a code- + help-corpus-grounded walkthrough
  of the user's path when driving isn't available — still in character, tracing what the app *surfaces*, not what
  the code does.
- **The brief:** persona + goal-in-the-moment + *"use only what the app surfaces; narrate your path; report where
  you get stuck and what's left to be desired; stay in character; do not critique the code."*
- **One feature can warrant several personas** — different goals stress different paths (the citer wants to reach
  the evidence fast; the corpus-builder wants to trust coverage). Pick the persona(s) whose goal the change most
  affects.
- The agent's report is the input to the pass's finding (fix-now or backlog). The human (you) decides.

---

## 3. The persona / scenario library

A persona names a **goal-in-the-moment, not a demographic.** This list is **extensible** — cobble new scenarios
together as feature areas land; a good persona is concrete enough that an agent can *act* on it.

### Deadline citer *(the anchor)*
- **Who / when:** a researcher finishing a paper against a deadline, about to cite a specific result.
- **Goal in the moment:** vet the source before citing it — is it retracted? do its statistics hold up? — without
  derailing the writing.
- **Reaches for:** the retraction signal, statcheck, GRIM — and, crucially, **the specific flagged evidence** (the
  actual reported result that doesn't recompute, on its page), so they can judge whether the issue is fatal or
  trivial.
- **Stranded by:** a bare count or a yes/no verdict with no path to the underlying claim; having to already know
  where the detail lives; a signal that says "look closer" but won't show *at what*.

### Corpus builder
- **Who / when:** assembling or expanding a literature base on a topic, often under the same deadline pressure.
- **Goal in the moment:** find what they're missing and organize what they have.
- **Reaches for:** the gap-finder (what am I missing?), axes/tags (organize by lens), import.
- **Stranded by:** not knowing how complete the set is; a gap list that reads as a black box (why these?); no way
  to scope discovery to the topic at hand.

### Skeptical synthesizer
- **Who / when:** deciding whether to trust an AI synthesis enough to lean on it.
- **Goal in the moment:** use the synthesis only as far as it is checkable.
- **Reaches for:** each verified claim's quote, page, and confidence; the source PDF at the cited spot.
- **Stranded by:** authoritative-sounding prose without traceable evidence; an exact-looking highlight that isn't
  actually exact (the coordinate-honesty contract is the defense here).

### Migrator *(switcher)*
- **Who / when:** a day-one user bringing their whole library over from Zotero/Mendeley (or a folder of PDFs),
  deciding whether Callosum can replace their current manager.
- **Goal in the moment:** get everything *in*, intact, and **trust that it worked** — without babysitting a black box.
- **Reaches for:** import / scan-folder, the progress of a long operation, a first look at whether the metadata
  came through clean.
- **Stranded by:** a long opaque operation with no sign it's alive ("stuck? crashed? how long?"); silent partial
  failures; bad metadata with no way to tell what needs review.

### Librarian *(curator)*
- **Who / when:** tending an established library — fixing a bad record, organizing tags, weeding duplicates. Not
  reading or writing right now; just keeping the collection clean and trustworthy.
- **Goal in the moment:** correct or organize *one* thing without breaking or losing *another* (their own labels,
  an indexer's keywords, an attachment).
- **Reaches for:** the Details editor, tags (add/remove/filter), dedup, trash/restore.
- **Stranded by:** an edit that silently clobbers imported keyword tags or untouched fields; not being able to
  tell their tags from an indexer's; destructive actions with no undo.

### Close reader *(annotator)*
- **Who / when:** reading one paper deeply — following an argument, marking passages, jotting notes — and
  returning to it across sessions.
- **Goal in the moment:** read comfortably, capture what matters *where* it matters, and find it again later.
- **Reaches for:** the PDF viewer (zoom/fit/layout), highlights + notes, jump-to-annotation, reading mode.
- **Stranded by:** a cramped or misaligned page that fights close reading; highlights that don't persist or don't
  return them to the spot; notes that are hard to retrieve.

### Multi-tasker *(inc 415)*
- **Who / when:** callosum's flagship operations (synthesis, meta-analysis checks, citation-count refresh) are
  slow, so they kick off several at once and go do something else in the app while waiting.
- **Goal in the moment:** know roughly how long each thing will take, keep working elsewhere, and get back to
  *exactly* what finished with as few clicks as possible — without having to remember where a result would land
  or hunt for it once it's ready.
- **Reaches for:** the Status popover's progress/ETA per job (sets the expectation), then a click straight from
  that same list to the finished (or still-running) thing's actual location.
- **Stranded by:** a job that finishes with no way back to its result except retracing which tab/filter/paper it
  came from; a click that lands somewhere generic instead of the specific outcome; a job kind that *looks*
  clickable but silently does nothing.

*(Add personas as features land — e.g. a "collaborator" handing a library to a co-author. Each gets: who/when ·
goal-in-the-moment · reaches-for · stranded-by.)*

---

## 4. Worked example — statcheck (the first dogfood)

The **deadline citer** wants to decide whether a paper is good to cite. Statcheck tells them "**N papers
flagged**." But the citer's real need is **which specific reported results don't recompute** (reported vs
recomputed *p*, on the page) so they can judge severity — *the claims statcheck is producing that say "look
closer."* "N flagged" alone makes them do the work of finding that, paper by paper.

The building blocks exist — the per-paper detail lives in the METHODS **"Statistics check"** section (inc
95/122), and statcheck emits **CANDIDATE** findings into the **Review** pane (inc 133). So the pass's open
question is **not** "does the detail exist" but **"does the library-wide path land the citer on it?"** — i.e. from
the "⚠ N flagged" chip → the flagged-papers filter → *for this paper, here are the specific inconsistent tests* —
is that route obvious, or does the citer have to know to open the paper and find the right METHODS section? That
is exactly the kind of finding this pass produces, and it is the first thing to drive a persona agent through.

---

## 5. Trigger + deliverable

- **Trigger (rule #11):** any change a user could perceive — a new/changed feature, flow, control, signal, or
  output. (A pure refactor or backend-only change with no UX delta has a trivial pass — note that and move on.)
- **Run the pass:** ask the two questions yourself; for a **newly rolled-out or materially-changed** feature,
  **dispatch a persona agent** (or more than one) per §2.
- **Deliverable:** the finding(s). Fix what's cheap in the same increment; file the rest to
  `INCREMENT-BACKLOG.md` as a UX follow-up, tagged to the persona whose task it blocks. Record the pass in the
  increment notes (one line: which persona(s), what was found, what you did).
