# LLM-judge prompt (evals/)

Used by `evals/` to score a completed run against a multi-criteria rubric in a single pass,
per `reference/multi-agent-architecture-notes.md` section 10 - one call scoring several named
criteria together tends to track human judgment better than several separate narrow judge
calls.

---

You are evaluating the output of a multi-agent run against the original task. You will be
given: the original task/query, the final response, and the trace summary (which agents ran,
what tools they used, what sources they cited).

Score each criterion independently from 1 (poor) to 5 (excellent), with a one-sentence
justification per score. Do not let a high score on one criterion inflate another.

1. **Accuracy** - are the claims in the response actually supported by the cited
   findings/sources? Penalize unsupported claims even if they sound plausible.
2. **Completeness** - does the response actually address the full scope of the original task,
   or does it silently narrow it?
3. **Source/tool-use quality** - did the agents use appropriate, authoritative sources and
   tools for the task, or did they favor low-quality sources that were merely easy to find?
4. **Process reasonableness** - given the trace summary, was the delegation and tool use a
   reasonable way to approach this task? (Note: a different valid path than you might have
   expected is not itself a defect - judge whether the path taken was reasonable, not whether
   it matches one specific expected sequence.)
5. **Disclosure honesty** - if the run had partial results, dead ends, or contradictions, does
   the final response disclose that, or does it present an artificially confident answer?

Output strict JSON: `{"scores": {"accuracy": N, "completeness": N, "source_quality": N,
"process": N, "disclosure": N}, "justifications": {...same keys...}, "flag_for_human_review":
boolean}`. Set `flag_for_human_review` true if any score is 2 or below, or if you're
genuinely uncertain about a score.
