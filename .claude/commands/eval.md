---
description: Run the eval seed set for a runtime and report scores against the multi-criteria rubric
argument-hint: [typescript|python]
allowed-tools: Bash(npm run eval), Bash(uv run python -m multiagent_boilerplate.evals.run_eval)
---

Run this boilerplate's eval suite (specs/prompts/judge.md rubric, notes section 10) and report
back.

Arguments: `$ARGUMENTS` - the runtime to eval (`typescript` or `python`, default `typescript`).

Steps:

1. Run the matching command:
   - TypeScript: `npm run eval` in `typescript/`
   - Python: `uv run python -m multiagent_boilerplate.evals.run_eval` in `python/`
2. Report, per seed task: the five rubric scores and whether it was flagged for human review.
3. If anything was flagged, look at that task's justifications and give your own read on
   whether the flag looks legitimate or like a judge miscalibration - don't just relay the
   score.
4. Note this is a small starting seed set (specs/prompts/judge.md notes section 10) - if the
   user is trying to validate a real behavior change, suggest whether the seed set needs a
   task added for the case they care about.
