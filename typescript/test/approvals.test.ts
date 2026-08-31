import { describe, expect, it } from "vitest";
import { Harness, ToolApprovalGate, type ApprovalDecision, type ApprovalRequest } from "../src/harness/index.js";
import type { Tool } from "../src/tools/types.js";

const noRuntime = {
  async spawnSubagents(): Promise<never> {
    throw new Error("n/a");
  },
  async writeArtifact() {
    return {};
  },
  async readArtifact() {
    return {};
  },
  async savePlan() {},
};

const role = { role: "subagent", allowedTools: ["send_email"], canSpawn: [], maxDelegationDepth: 0, budget: { maxToolCalls: 100 } };

let sent = 0;
const sendEmail: Tool = {
  name: "send_email",
  description: "sends an email (consequential)",
  inputSchema: { type: "object" },
  async execute() {
    sent += 1;
    return { sent: true };
  },
};

const call = (key: string) => ({ idempotencyKey: key, toolName: "send_email", input: { to: "x@y.z" }, delegationDepth: 0 });

describe("human-in-the-loop approval gate", () => {
  it("blocks a gated tool when the decision is denied - the tool never runs", async () => {
    sent = 0;
    const gate = new ToolApprovalGate(["send_email"], async () => "denied");
    const harness = new Harness([sendEmail], { approvals: gate });
    const outcome = await harness.execute(role, call("a"), noRuntime);
    expect(outcome.status).toBe("rejected");
    if (outcome.status !== "ok") expect(outcome.error.type).toBe("auth");
    expect(sent).toBe(0);
  });

  it("runs a gated tool once approved, passing the request to the resolver", async () => {
    sent = 0;
    const seen: ApprovalRequest[] = [];
    const resolver = async (req: ApprovalRequest): Promise<ApprovalDecision> => {
      seen.push(req);
      return "approved";
    };
    const harness = new Harness([sendEmail], { approvals: new ToolApprovalGate(["send_email"], resolver) });
    const outcome = await harness.execute(role, call("b"), noRuntime);
    expect(outcome.status).toBe("ok");
    expect(sent).toBe(1);
    expect(seen[0]?.toolName).toBe("send_email");
    expect(seen[0]?.input).toEqual({ to: "x@y.z" });
  });

  it("does not gate tools outside the gated set (default is auto-approve)", async () => {
    sent = 0;
    const harness = new Harness([sendEmail], { approvals: new ToolApprovalGate(["some_other_tool"], async () => "denied") });
    const outcome = await harness.execute(role, call("c"), noRuntime);
    expect(outcome.status).toBe("ok");
    expect(sent).toBe(1);
  });
});
