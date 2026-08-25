# Contributing

Thanks for considering a contribution. This project stays useful by staying small and
opinionated — read this before opening a PR.

## Ground rules

- **No orchestration frameworks.** PRs adding LangChain/LangGraph/CrewAI/AutoGen or similar
  as a runtime dependency will be declined regardless of the feature — see
  [`DESIGN.md`](DESIGN.md#why-no-orchestration-framework).
- **`specs/` is the source of truth.** Behavioral changes (prompts, schemas, agent roles)
  start in `specs/`, then land in both `typescript/` and `python/` in the same PR. A PR that
  changes one runtime's behavior without the other will fail `scripts/check_parity.py`.
- **New LLM provider = a thin adapter over its official SDK**, matching the existing
  `ChatModel` interface in `providers/`. Not a routing library.
- Keep `examples/single-agent` working — it's the deliberate baseline the multi-agent path is
  compared against.

## Workflow

1. Fork, branch from `main`.
2. Match the layer order in `CLAUDE.md` — place new code in the narrowest layer that needs
   it.
3. Run the full check before opening a PR:
   - TypeScript: `npm run typecheck && npm run lint && npm test` in `typescript/`
   - Python: `uv run ruff check . && uv run pytest` in `python/`
   - Cross-runtime (if you touched `specs/`): `python3 scripts/check_parity.py` from the repo root
   - Docs (if touched): `npm run build` in `docs/`
4. Open a PR describing *why*, not just *what* — link the relevant section of
   `reference/multi-agent-architecture-notes.md` if the change is architectural.

## Reporting bugs / requesting features

Use the issue templates under `.github/ISSUE_TEMPLATE/`. For security issues, see
[`SECURITY.md`](SECURITY.md) instead of opening a public issue.
