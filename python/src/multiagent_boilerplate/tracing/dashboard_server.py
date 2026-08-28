"""Live profiler over Server-Sent Events - the realtime sibling of the static dashboard. Serves
the same shared template (so the two can't drift) and streams each span to the browser as it
completes, which animates the gauges/charts in real time. Built on http.server, no framework -
the same owned-code approach as the A2A server. Mirrors typescript/src/tracing/dashboardServer.ts.
"""

from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .dashboard import render_dashboard
from .tracer import Tracer, TraceSpan


@dataclass
class _State:
    tracer: Tracer
    meta: dict
    clients: set[queue.Queue] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def broadcast(self, event: str, data: str) -> None:
        msg = f"event: {event}\ndata: {data}\n\n"
        with self.lock:
            for q in list(self.clients):
                q.put(msg)


@dataclass
class DashboardServer:
    url: str
    _state: _State
    _server: ThreadingHTTPServer
    _unsubscribe: object

    def done(self) -> None:
        """Tell connected browsers the run finished (stops the LIVE pulse); page stays viewable."""
        self._state.broadcast("done", "{}")

    def close(self) -> None:
        self._unsubscribe()  # type: ignore[operator]
        with self._state.lock:
            for q in list(self._state.clients):
                q.put(None)
        self._server.shutdown()


def start_dashboard_server(tracer: Tracer, meta: dict | None = None, port: int = 8790) -> DashboardServer:
    state = _State(tracer=tracer, meta={**(meta or {}), "live": True})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            pass

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path in ("/", "/index.html"):
                body = render_dashboard(state.tracer.all_spans(), state.meta).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/events":
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.send_header("connection", "keep-alive")
                self.end_headers()
                self._write(f"event: meta\ndata: {json.dumps(state.meta)}\n\n")
                for span in state.tracer.all_spans():
                    self._write(f"event: span\ndata: {json.dumps(span.to_schema_dict())}\n\n")
                q: queue.Queue = queue.Queue()
                with state.lock:
                    state.clients.add(q)
                try:
                    while True:
                        msg = q.get()
                        if msg is None or not self._write(msg):
                            break
                finally:
                    with state.lock:
                        state.clients.discard(q)
                return
            self.send_response(404)
            self.end_headers()

        def _write(self, text: str) -> bool:
            try:
                self.wfile.write(text.encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, ValueError):
                return False

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def on_span(span: TraceSpan) -> None:
        state.broadcast("span", json.dumps(span.to_schema_dict()))

    unsub = tracer.add_listener(on_span)
    return DashboardServer(url=f"http://localhost:{port}", _state=state, _server=server, _unsubscribe=unsub)
