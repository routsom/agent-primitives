## What and why

<!-- The motivation, not just a restatement of the diff. Link an issue if one exists. -->

## Scope

- [ ] `specs/` (schemas, prompts, or agent role definitions)
- [ ] `typescript/`
- [ ] `python/`
- [ ] `docs/`
- [ ] `.claude/` or `.github/`

If this changes behavior defined in `specs/`, both `typescript/` and `python/` must be updated
in this PR - `python3 scripts/check_parity.py` checks for this.

## Checklist

- [ ] `typescript/`: `npm run typecheck && npm run lint && npm test` pass
- [ ] `python/`: `uv run ruff check . && uv run pytest` pass
- [ ] `specs/` changes: `python3 scripts/check_parity.py` passes from the repo root
- [ ] `docs/` builds if touched: `npm run build`
- [ ] No new dependency on an orchestration framework (see `CONTRIBUTING.md`)
- [ ] Ran the relevant example (`/run-task` or `npm run example:*` / `uv run python -m examples.*`) against the mock provider to confirm end-to-end behavior, not just unit tests

## Test plan

<!-- How you verified this beyond the automated checks above. -->
