---
title: Evals
description: LLM-as-judge with a multi-criteria rubric, a small seed set, and why that beats waiting for a comprehensive suite.
---

Traditional evals assume a fixed correct path: given input X, follow path Y, produce output Z.
Multi-agent systems break this assumption - different agents can take entirely different valid
routes to the same correct outcome. Evaluation has to judge whether the outcome is right and the
process was reasonable, not whether a prescribed sequence of steps was followed exactly
(`reference/multi-agent-architecture-notes.md` section 10).

## Running it

```bash
npm run eval                                              # typescript/
uv run python -m multiagent_boilerplate.evals.run_eval    # python/
```

Both run the same seed task set (`specs/prompts/judge.md` + each runtime's `seed_tasks`/
`seedTasks.json`) through the full orchestrator-worker flow, then score the result with the
judge role.

## The rubric

One LLM call scoring several named criteria at once, per `specs/prompts/judge.md` - this tends
to be more consistent with human judgment than several separate narrow judge calls:

1. **Accuracy** - are claims actually supported by cited findings?
2. **Completeness** - does the response address the full scope, or silently narrow it?
3. **Source/tool-use quality** - authoritative sources, or merely easy-to-find ones?
4. **Process reasonableness** - was the delegation and tool use a reasonable approach, given a
   different valid path than expected isn't itself a defect?
5. **Disclosure honesty** - are partial results, dead ends, or contradictions disclosed, or
   smoothed into an artificially confident answer?

Each run also gets a `flag_for_human_review` boolean - true if any score is 2 or below, or the
judge is genuinely uncertain.

## Start small, start early

This ships with three seed tasks. That's deliberate: per the notes, early-stage changes tend to
have large, easy-to-detect effects, and a few dozen realistic queries is enough to see that.
Don't wait for a comprehensive eval set before starting - a small set you actually run beats a
large one you keep delaying. Add tasks to `seed_tasks.json` / `seedTasks.json` as you find real
gaps.

## Human review still matters

Automated LLM-judge scoring has shown systematic biases in practice - e.g. consistently favoring
heavily-optimized-but-lower-quality sources over authoritative ones - that only surfaced under
manual review after passing automated checks cleanly. Keep spot-checking flagged runs by hand;
don't fully automate this away.

## Iterating on the rubric itself

Use the [`eval-judge` Claude Code subagent](/claude-code/) to test a candidate rubric change
against a specific task/response/trace before editing `specs/prompts/judge.md` for real.
