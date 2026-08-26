"""Minimal A2A server: publishes an agent card and accepts delegated tasks over HTTP+JSON.
Every inbound task is authenticated, rate-limited, validated, and run through the same harness
as a local subagent spawn - no shortcut for remote callers (specs/protocols/a2a.md, notes
section 7). Auth and rate limiting happen *before* the model runs, so abusive traffic is
rejected at near-zero cost (notes section 19).

Built on the standard library (http.server) rather than a web framework, mirroring the
TypeScript server's use of node:http - consistent with this boilerplate's "no framework"
stance."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import re
import threading
import warnings
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..agents.subagent import run_subagent
from ..agents.types import AgentTask
from ..harness import Harness, RunBudget, SlidingWindowRateLimiter, validate_agent_task
from ..providers.types import ChatModel
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer
from .agent_card import build_agent_card

_BEARER = re.compile(r"^Bearer (.+)$")


@dataclass
class A2AServerOptions:
    port: int
    base_url: str
    model: ChatModel
    harness: Harness
    runtime: ToolRuntime
    tracer: Tracer
    max_delegation_depth: int
    # Bearer token required on inbound tasks. When None, auth is disabled (dev only) with a warning.
    auth_token: str | None = None
    # Sliding-window rate limit per caller (max_requests, window_ms). Defaults to 60 / 60s.
    rate_limit: tuple[int, int] = (60, 60_000)
    # Per-request session token ceiling. 0 = unlimited. Each inbound task gets its own budget.
    max_run_tokens: int = 0
    _rate_limiter: SlidingWindowRateLimiter | None = field(default=None, init=False, repr=False)


def start_a2a_server(opts: A2AServerOptions) -> ThreadingHTTPServer:
    card = build_agent_card("subagent", opts.base_url)
    opts._rate_limiter = SlidingWindowRateLimiter(opts.rate_limit[0], opts.rate_limit[1])
    if opts.auth_token is None:
        warnings.warn(
            "[a2a] A2A server started with no auth_token - inbound tasks are unauthenticated. "
            "Set A2A_AUTH_TOKEN in production.",
            stacklevel=2,
        )
    handler_cls = _make_handler(opts, card)
    server = ThreadingHTTPServer(("0.0.0.0", opts.port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _make_handler(opts: A2AServerOptions, card: dict) -> type[BaseHTTPRequestHandler]:
    rate_limiter = opts._rate_limiter
    assert rate_limiter is not None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # quiet by default
            pass

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            # The agent card is public discovery metadata - no auth required.
            if self.path == "/.well-known/agent.json":
                self._respond(200, card)
            else:
                self._respond(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            if self.path != "/tasks":
                self._respond(404, {"error": "not found"})
                return

            # 1. Authenticate before anything else touches the request body.
            presented = self._bearer_token()
            if opts.auth_token is not None and presented != opts.auth_token:
                self._respond(401, {"error": "unauthorized"})
                return

            # 2. Rate-limit per caller identity (token when authenticated, else remote address).
            caller_key = presented or (self.client_address[0] if self.client_address else "anonymous")
            if not rate_limiter.try_acquire(caller_key):
                self._respond(429, {"error": "rate limit exceeded"})
                return

            try:
                length = int(self.headers.get("content-length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError) as error:
                self._respond(400, {"error": str(error)})
                return

            inbound_depth = body.get("delegationDepth", 0)
            depth = (inbound_depth if isinstance(inbound_depth, int) else 0) + 1
            if depth > opts.max_delegation_depth:
                self._respond(
                    429, {"error": f"delegation depth {depth} exceeds this server's cap {opts.max_delegation_depth}"}
                )
                return

            try:
                validate_agent_task(body)
                task = AgentTask.from_schema_dict(body)
                # Fresh per-request budget: a long-lived server must not accumulate spend.
                run_budget = RunBudget(opts.max_run_tokens)
                result = asyncio.run(
                    run_subagent(
                        task=task,
                        model=opts.model,
                        harness=opts.harness,
                        runtime=opts.runtime,
                        tracer=opts.tracer,
                        delegation_depth=depth,
                        run_budget=run_budget,
                    )
                )
                self._respond(200, dataclasses.asdict(result))
            except Exception as error:  # noqa: BLE001 - returned to the caller as an error response
                self._respond(400, {"error": str(error)})

        def _bearer_token(self) -> str | None:
            header = self.headers.get("authorization", "")
            match = _BEARER.match(header)
            return match.group(1) if match else None

        def _respond(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler
