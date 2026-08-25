"""Reference production entrypoint: starts the A2A server exposing the subagent role, backed
by a real Orchestrator (harness, artifact store, plan memory) rather than the dummy runtime
used in tests. This is what deploy/Dockerfile.python runs by default - swap it for your own
entrypoint as needed.

Run with: uv run python -m multiagent_boilerplate.server
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from .a2a.server import A2AServerOptions, start_a2a_server
from .config import load_config
from .harness import Harness
from .orchestrator.orchestrator import Orchestrator, OrchestratorOptions
from .providers import resolve_provider
from .tools.registry import build_tool_registry
from .tracing.tracer import Tracer


def main() -> None:
    config = load_config()
    model = resolve_provider(config.default_provider)
    harness = Harness(build_tool_registry())
    tracer = Tracer()
    port = int(os.environ.get("PORT", "8787"))
    base_url = os.environ.get("BASE_URL", f"http://localhost:{port}")

    orchestrator = Orchestrator(
        OrchestratorOptions(
            model=model,
            harness=harness,
            tracer=tracer,
            caps=config.caps,
            artifact_store_dir=config.artifact_store_dir,
            plan_memory_dir=str(Path(config.artifact_store_dir) / "plans"),
            run_id=str(uuid.uuid4()),
        )
    )

    start_a2a_server(
        A2AServerOptions(
            port=port,
            base_url=base_url,
            model=model,
            harness=harness,
            runtime=orchestrator,
            tracer=tracer,
            max_delegation_depth=config.caps.max_delegation_depth,
        )
    )

    print(f'[server] provider "{model.provider}" ({model.model}), A2A subagent server listening on {base_url}')

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
