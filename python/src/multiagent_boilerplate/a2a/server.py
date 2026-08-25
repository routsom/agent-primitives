"""Minimal A2A server: publishes an agent card and accepts delegated tasks over HTTP+JSON.
Every inbound task is validated and run through the same harness as a local subagent spawn -
no shortcut for remote callers (specs/protocols/a2a.md, notes section 7).

Built on the standard library (http.server) rather than a web framework, mirroring the
TypeScript server's use of node:http - consistent with this boilerplate's "no framework"
stance."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..agents.subagent import run_subagent
from ..agents.types import AgentTask
from ..harness import Harness, validate_agent_task
from ..providers.types import ChatModel
from ..tools.types import ToolRuntime
from ..tracing.tracer import Tracer
from .agent_card import build_agent_card


@dataclass
class A2AServerOptions:
    port: int
    base_url: str
    model: ChatModel
    harness: Harness
    runtime: ToolRuntime
    tracer: Tracer
    max_delegation_depth: int


def start_a2a_server(opts: A2AServerOptions) -> ThreadingHTTPServer:
    card = build_agent_card("subagent", opts.base_url)
    handler_cls = _make_handler(opts, card)
    server = ThreadingHTTPServer(("0.0.0.0", opts.port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _make_handler(opts: A2AServerOptions, card: dict) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # quiet by default
            pass

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path == "/.well-known/agent.json":
                self._respond(200, card)
            else:
                self._respond(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            if self.path != "/tasks":
                self._respond(404, {"error": "not found"})
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
                result = asyncio.run(
                    run_subagent(
                        task=task,
                        model=opts.model,
                        harness=opts.harness,
                        runtime=opts.runtime,
                        tracer=opts.tracer,
                        delegation_depth=depth,
                    )
                )
                self._respond(200, dataclasses.asdict(result))
            except Exception as error:  # noqa: BLE001 - returned to the caller as an error response
                self._respond(400, {"error": str(error)})

        def _respond(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler
