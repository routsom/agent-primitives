import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Server } from "node:http";
import { startA2AServer } from "../src/a2a/server.js";
import { delegateToRemoteAgent, fetchAgentCard } from "../src/a2a/client.js";
import { Harness, SlidingWindowRateLimiter } from "../src/harness/index.js";
import { MockChatModel } from "../src/providers/mock.js";
import { buildToolRegistry } from "../src/tools/registry.js";
import { Tracer } from "../src/tracing/tracer.js";

const dummyRuntime = {
  async spawnSubagents(): Promise<never> {
    throw new Error("n/a");
  },
  async writeArtifact(input: { kind: string; summary: string; createdBy: string }) {
    return { artifactId: "x", kind: input.kind, sizeBytes: 1, createdBy: input.createdBy, createdAt: "now", summary: input.summary, uri: "file://x" };
  },
  async readArtifact() {
    return {};
  },
  async savePlan() {},
};

const task = {
  taskId: "t1",
  role: "subagent",
  objective: "test",
  outputFormat: "bullets",
  allowedTools: ["search_web", "write_artifact"],
  boundaries: "none",
  budget: { maxToolCalls: 5 },
};

describe("sliding-window rate limiter", () => {
  it("allows up to the cap within the window, then rejects", () => {
    const limiter = new SlidingWindowRateLimiter(2, 1000);
    expect(limiter.tryAcquire("k", 0)).toBe(true);
    expect(limiter.tryAcquire("k", 100)).toBe(true);
    expect(limiter.tryAcquire("k", 200)).toBe(false);
    // A different caller has its own window.
    expect(limiter.tryAcquire("other", 200)).toBe(true);
    // Once the window slides past the earlier hits, capacity frees up.
    expect(limiter.tryAcquire("k", 1200)).toBe(true);
  });
});

describe("A2A server auth + rate limiting (real HTTP)", () => {
  let server: Server;
  const port = 8894;
  const baseUrl = `http://localhost:${port}`;

  beforeEach(async () => {
    server = startA2AServer({
      port,
      baseUrl,
      model: new MockChatModel(),
      harness: new Harness(buildToolRegistry()),
      runtime: dummyRuntime,
      tracer: new Tracer(() => {}),
      maxDelegationDepth: 2,
      authToken: "secret-token",
      rateLimit: { maxRequests: 100, windowMs: 60_000 },
    });
    await new Promise((r) => setTimeout(r, 150));
  });

  afterEach(() => {
    server.close();
  });

  it("serves the agent card without auth", async () => {
    const card = await fetchAgentCard(baseUrl);
    expect(card.role).toBe("subagent");
  });

  it("rejects a task with no token (401)", async () => {
    await expect(delegateToRemoteAgent(baseUrl, task, 0)).rejects.toThrow("401");
  });

  it("rejects a task with a wrong token (401)", async () => {
    await expect(delegateToRemoteAgent(baseUrl, task, 0, "wrong")).rejects.toThrow("401");
  });

  it("accepts a task with the correct token", async () => {
    const result = await delegateToRemoteAgent(baseUrl, task, 0, "secret-token");
    expect(result.status).toBe("ok");
  });
});
