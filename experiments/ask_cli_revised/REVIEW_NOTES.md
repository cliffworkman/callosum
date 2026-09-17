# Ask CLI staged-synthesis review - pass 2

This revision keeps the experiment isolated from production and leaves production verifier thresholds unchanged.
It is a response to the first frozen run plus manual small-Qwen prompting tests. The goal is not to make Qwen
"smarter" through longer prompts. The goal is to make every local-model call do one small reading/judgment job.

## Main defects found

1. **Stage 1 mixed language understanding with bookkeeping.** One call had to decompose the question, preserve
   relationships, generate IDs, map requests into a closed 13-kind ontology, and serialize nested JSON. The run
   showed both a shape failure and semantic incompleteness. The closed taxonomy also makes otherwise reasonable
   outputs disappear on spelling/category errors.

2. **Stage 5 asked four partly redundant judgments at once.** The validator also coerced malformed values through
   Python `bool()`, so strings such as `"false"` could become `True`. The first run showed systematic over-growth.

3. **Stage 6 was a mega-task.** Qwen had to find evidence, copy an exact quote, identify its chunk, formulate a
   semantic tuple, map obligation IDs, and serialize everything. This produced paraphrased "quotes", malformed
   obligation IDs, non-scientific propositions, and three 10-minute provider timeouts.

4. **Intermediate calls inherited a 4096-token output ceiling.** Tiny classification jobs could therefore consume
   pathological local runtime. The revised wrappers set task-specific local output caps.

5. **Known structural/bibliographic neighbors could become evidence anchors.** That is how correspondence metadata
   and a keyword line reached verification. They may remain interpretive context, but known structural or
   bibliographic chunks are no longer candidate scientific evidence anchors.

6. **Axis-only paper nomination was cap-order dependent.** Axis-only papers never received a ranking score, so all
   were tied at zero and arbitrary cluster membership order determined which survived the 25-paper cap.

7. **Gap recovery skipped the agreed first step.** It immediately re-nominated papers instead of searching the
   already-established candidate set first.

8. **The trace omitted the exact prompt and per-call timing, and Qwen state was only flushed at run end.** The
   revised trace records prompt, provider/parse/validation states separately, output cap, elapsed time, and appends
   each Qwen call/decision immediately.

9. **Gemini was the default terminal path.** The revised CLI defaults to Qwen and resolves Gemini only when the user
   explicitly requests `--terminal gemini` or `--terminal both`.

10. **`08_evidence_packets.jsonl` did not contain evidence packets.** It duplicated context-growth IDs. The revised
    artifact stores the actual local packet chunks and metadata, while `07_context_growth.jsonl` stores the growth
    decisions.

## Revised model-mediated pipeline

```text
question
  -> Qwen: list complete natural-language subquestions
  -> Qwen: for each subquestion, list explicitly requested information
  -> deterministic: assign IDs and assemble answer contract
  -> paper discovery / axes
  -> within-paper retrieval
  -> Qwen: accept / before / after / both / discard
  -> deterministic: expose exact sentence-ish source spans from evidence-eligible chunks
  -> Qwen: select useful span IDs only
  -> deterministic: recover exact source text from selected IDs
  -> Qwen: form ONE atomic claim from ONE exact span + context
  -> Qwen: map that claim to natural-language obligations
  -> unchanged verifier
  -> deterministic coverage
  -> one recovery pass: existing candidate papers first, then one new nomination pass
  -> sealed verified ledger
  -> Qwen terminal synthesis by default; Gemini terminal remains explicit opt-in only
```

## Important representation changes

- Natural-language obligations are canonical. `kind` is optional metadata rather than a load-bearing closed ontology.
- Qwen never generates `subquestion_id`, `field_id`, source-span IDs, or exact quote text.
- Retrieval anchor and evidence anchor remain distinct.
- Exact quote fidelity is now deterministic: Qwen selects an ID whose text Callosum already owns.
- Context can include structural material, but known `bibliographic`/`structural` chunks and obvious structural
  chunk types cannot become scientific evidence anchors.

## Runtime changes

Intermediate output caps are now intentionally small:

- decomposition: 512 tokens
- requested-information extraction: 256
- context action: 48
- evidence selection: 96
- claim formation: 192
- obligation mapping: 96
- recovery phrase: 64

This should prevent the Stage-6 4096-token behavior that dominated the first run's ~42-minute runtime.

## Deliberately not changed

- verifier thresholds
- NLI implementation
- paper/vector embedding model
- retrieval top-k/caps
- graph rescue remains disabled while reference coverage is inadequate
- benchmark question
- production Ask code

## Remaining hypotheses, not solved by this patch

1. The 1.5B model may still be too weak even after task decomposition. The manual 3B result makes a 3B controlled
   local-model comparison worth considering only after one revised 1.5B run.
2. Auto-axis nomination is still coarse. This revision fixes arbitrary axis-only ordering but does not claim the
   current axis-label similarity is the final paper-neighborhood mechanism.
3. Sentence-ish exact spans are a simple experimental navigation unit, not a production evidence reconstruction
   system. H1b/H1c remain separate research.
4. Terminal Qwen can still invent unsupported connective/background material. Proposition IDs are now required in
   the terminal prompt for inspectability, but this is not yet a hard terminal verification layer.
5. The known amygdala verifier boundary case remains untouched. A 0.698 retrieval score against a 0.70 threshold
   is a verifier-research specimen, not permission to lower the threshold.

## Recommended next run

Run the revised pipeline once with `--terminal qwen` only. Do not spend Gemini credits and do not tune after seeing
intermediate output. Compare the same known targets stage-by-stage. The most informative questions are:

- Did Stage 1 preserve all explicit AIB subquestions and relationships?
- Did the evidence selector choose the already-observed amygdala/IAT/DG/empathy/just-world/Hadza spans?
- Did exact-span selection eliminate `quote_not_verbatim` entirely?
- Did the known front-matter/keyword rows disappear before verification?
- Did Stage-6 time fall from minutes per packet to seconds/tens of seconds?
- Did coverage now create real gaps and did recovery act on them?
- Is the richer sealed ledger sufficient to keep terminal Qwen useful without leaning as heavily on model priors?
