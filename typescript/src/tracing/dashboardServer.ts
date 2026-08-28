import { createServer, type ServerResponse } from "node:http";
import { renderDashboard, type DashboardMeta, type EvalRecord } from "./dashboard.js";
import type { Tracer } from "./tracer.js";

export interface DashboardServerOptions {
  /** Optional: when provided, the server streams this tracer's spans live. Omit for an eval-only dashboard. */
  tracer?: Tracer;
  meta?: DashboardMeta;
  port?: number;
}

export interface DashboardServer {
  url: string;
  /** Push an LLM-judge verdict to connected browsers (appears in the Evals section in real time). */
  pushEval(record: EvalRecord): void;
  /** Tell connected browsers the run finished (stops the LIVE pulse); the page stays viewable. */
  done(): void;
  /** Close the server and all live connections. */
  close(): void;
}

/**
 * Live profiler over Server-Sent Events - the realtime sibling of the static dashboard. Serves
 * the same shared template (so the two can't drift) and streams each span to the browser as it
 * completes, which animates the gauges/charts in real time. Built on node:http, no framework -
 * the same owned-code approach as the A2A server. Not started by default; opt in per run.
 */
export function startDashboardServer(opts: DashboardServerOptions): DashboardServer {
  const port = opts.port ?? 8790;
  const meta = { ...opts.meta, live: true };
  const clients = new Set<ServerResponse>();
  const evals: EvalRecord[] = [];
  const spans = () => opts.tracer?.allSpans() ?? [];

  const server = createServer((req, res) => {
    if (req.method === "GET" && (req.url === "/" || req.url === "/index.html")) {
      res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      res.end(renderDashboard(spans(), meta, evals));
      return;
    }
    if (req.method === "GET" && req.url === "/events") {
      res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
      res.write(`event: meta\ndata: ${JSON.stringify(meta)}\n\n`);
      for (const span of spans()) res.write(`event: span\ndata: ${JSON.stringify(span)}\n\n`);
      for (const record of evals) res.write(`event: eval\ndata: ${JSON.stringify(record)}\n\n`);
      clients.add(res);
      req.on("close", () => clients.delete(res));
      return;
    }
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "not found" }));
  });

  const unsubscribe = opts.tracer?.addListener((span) => {
    const line = `event: span\ndata: ${JSON.stringify(span)}\n\n`;
    for (const res of clients) res.write(line);
  });

  server.listen(port);
  const url = `http://localhost:${port}`;

  return {
    url,
    pushEval(record: EvalRecord) {
      evals.push(record);
      const line = `event: eval\ndata: ${JSON.stringify(record)}\n\n`;
      for (const res of clients) res.write(line);
    },
    done() {
      for (const res of clients) res.write("event: done\ndata: {}\n\n");
    },
    close() {
      unsubscribe?.();
      for (const res of clients) res.end();
      server.close();
    },
  };
}
