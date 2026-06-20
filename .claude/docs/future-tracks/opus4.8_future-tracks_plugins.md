Goal: RECORD the notion of user-authored THEORY/METHODS plugin modules as a DEFERRED future
feature and mark the intended extension point — WITHOUT implementing any plugin system. Capture
the idea, its motivation, and the open questions so it is neither lost nor accidentally built
wrong. Implementation is blocked pending a dedicated design conversation.

EXPLICIT DEFERRAL: Do NOT implement a plugin system, a plugin API/contract, a loader, sandboxing,
or any user-facing "add a module" UI. Do NOT design the module contract. Those await a dedicated
design pass. This is a record-and-mark task only.

WHAT TO DO:
1. DESIGN.md — add a "Deferred: user-authored modules" section recording:
   - THE IDEA: let users author and add their own THEORY/METHODS panel modules (and, by extension,
     source providers), so the shipped tools are a starting point, not a ceiling.
   - THE MOTIVATION: the anti-foisting principle — defaults and prioritization should be the user's;
     an extensible tool avoids imposing one curator's (or the AI's) view of what matters.
   - THE OPEN QUESTIONS THAT BLOCK IT (the point of the record):
     a. Code execution / sandboxing — a user/third-party module runs in-process and renders in the
        panes; security model unresolved.
     b. Principle enforcement — can the module contract ENFORCE DESIGN.md (require fact/candidate
        declarations, forbid scores and freelance verdicts) or only enforce output shape and trust
        the rest? Unresolved, and the crux: a system that can't guarantee its modules behave may not
        be shippable, which could mean the honest version is your-own-modules-only, never
        third-party.
     c. Trusted vs untrusted — your own future modules (additive, already served by the internal
        registry) vs third-party modules (need sandbox + principle gate) are different problems and
        must be separated.
   - STATUS: DEFERRED until a dedicated design conversation resolves the above.
2. Mark the seam: at the existing panel module registry (and the SourceProvider registry once it
   exists), add a brief comment noting it is the intended future extension point for user-authored
   modules, that user-facing plugins are DEFERRED pending the DESIGN.md open questions, and that no
   plugin-loading is to be added without that design pass.

CONSTRAINTS:
- No plugin functionality, no contract design, no UI.
- Do NOT pre-commit a plugin API shape — committing a contract before the design conversation risks
  locking in the wrong one; that is itself a deferred decision.
- The internal module registries remain internal; nothing user-facing changes.

OUTPUT: the DESIGN.md "Deferred: user-authored modules" section (idea + motivation + open questions +
status) and the registry marker comments; confirmation no plugin system, contract, or UI was built.