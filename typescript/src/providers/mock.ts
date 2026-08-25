import type { ChatCompletionRequest, ChatCompletionResult, ChatModel, ContentBlock } from "./types.js";

/**
 * Deterministic, network-free provider. Used as the default so `npm install && npm run
 * example:research` works with zero API keys, and so CI never depends on a live model.
 *
 * Behavior is a small state machine keyed on (a) which role's prompt is in `system` and
 * (b) how many assistant turns have already happened in *this* agent's own message history
 * (each agent gets an isolated context, so counting prior assistant turns is an accurate,
 * pure-function way to track progress without external mutable state).
 */
export class MockChatModel implements ChatModel {
  readonly provider = "mock";
  readonly model = "mock-deterministic-1";

  async complete(request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    const turn = request.messages.filter((m) => m.role === "assistant").length;
    const system = request.system ?? "";
    const firstUserText = textOf(request.messages.find((m) => m.role === "user"));

    if (system.includes("You are the lead agent")) {
      return leadTurn(turn, firstUserText, request);
    }
    if (system.includes("You are a subagent")) {
      return subagentTurn(turn, firstUserText, request);
    }
    if (system.includes("You are the citation and synthesis agent")) {
      return citationTurn(firstUserText);
    }
    if (system.includes("You are evaluating the output")) {
      return judgeTurn();
    }
    // Plain single-agent usage: no orchestration prompt, just answer directly.
    return {
      message: {
        role: "assistant",
        content: [{ type: "text", text: `[mock] Direct answer to: ${firstUserText}` }],
      },
      usage: { inputTokens: estimateTokens(request), outputTokens: 40 },
      stopReason: "end_turn",
    };
  }
}

function leadTurn(turn: number, topic: string, request: ChatCompletionRequest): ChatCompletionResult {
  const canSpawn = request.tools?.some((t) => t.name === "spawn_subagents") ?? false;

  if (turn === 0 && canSpawn) {
    const tasks = [
      {
        taskId: "sub-1",
        role: "subagent",
        objective: `Investigate angle A of: ${topic}`,
        outputFormat: "bullet list of findings with source references",
        allowedTools: ["search_web", "write_artifact"],
        boundaries: "Cover angle A only; do not duplicate angle B's territory.",
        budget: { maxToolCalls: 15, maxDelegationDepth: 0 },
      },
      {
        taskId: "sub-2",
        role: "subagent",
        objective: `Investigate angle B of: ${topic}`,
        outputFormat: "bullet list of findings with source references",
        allowedTools: ["search_web", "write_artifact"],
        boundaries: "Cover angle B only; do not duplicate angle A's territory.",
        budget: { maxToolCalls: 15, maxDelegationDepth: 0 },
      },
    ];
    return toolCallResult("call-spawn-0", "spawn_subagents", { tasks }, request);
  }

  // Turn 1: subagent findings are in the latest tool_result - synthesize a final answer.
  const lastToolResult = findLastToolResult(request.messages);
  const findingsText = lastToolResult ? JSON.stringify(lastToolResult.output) : "(no findings)";
  return {
    message: {
      role: "assistant",
      content: [{ type: "text", text: `[mock] Based on subagent findings, here is the synthesized answer for "${topic}": ${findingsText}` }],
    },
    usage: { inputTokens: estimateTokens(request), outputTokens: 80 },
    stopReason: "end_turn",
  };
}

function subagentTurn(turn: number, _topic: string, request: ChatCompletionRequest): ChatCompletionResult {
  if (turn === 0) {
    return toolCallResult("call-search-0", "search_web", { query: taskObjective(request) }, request);
  }
  if (turn === 1) {
    const lastToolResult = findLastToolResult(request.messages);
    return toolCallResult(
      "call-artifact-0",
      "write_artifact",
      {
        kind: "raw-findings",
        summary: `Findings for: ${taskObjective(request)}`,
        content: lastToolResult?.output ?? {},
      },
      request,
    );
  }
  const lastToolResult = findLastToolResult(request.messages);
  return {
    message: {
      role: "assistant",
      content: [
        {
          type: "text",
          text: `[mock] Distilled findings for "${taskObjective(request)}": mock result available at ${JSON.stringify(lastToolResult?.output ?? {})}`,
        },
      ],
    },
    usage: { inputTokens: estimateTokens(request), outputTokens: 60 },
    stopReason: "end_turn",
  };
}

function citationTurn(inputText: string): ChatCompletionResult {
  return {
    message: {
      role: "assistant",
      content: [{ type: "text", text: `[mock] Cited synthesis: ${inputText}` }],
    },
    usage: { inputTokens: inputText.length, outputTokens: 60 },
    stopReason: "end_turn",
  };
}

function judgeTurn(): ChatCompletionResult {
  const scores = { accuracy: 4, completeness: 4, source_quality: 3, process: 4, disclosure: 5 };
  return {
    message: {
      role: "assistant",
      content: [
        {
          type: "text",
          text: JSON.stringify({
            scores,
            justifications: Object.fromEntries(Object.keys(scores).map((k) => [k, "mock justification"])),
            flag_for_human_review: false,
          }),
        },
      ],
    },
    usage: { inputTokens: 100, outputTokens: 60 },
    stopReason: "end_turn",
  };
}

function toolCallResult(id: string, name: string, input: Record<string, unknown>, request: ChatCompletionRequest): ChatCompletionResult {
  const content: ContentBlock[] = [{ type: "tool_call", id, name, input }];
  return {
    message: { role: "assistant", content },
    usage: { inputTokens: estimateTokens(request), outputTokens: 30 },
    stopReason: "tool_use",
  };
}

function findLastToolResult(messages: ChatCompletionRequest["messages"]) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (!message) continue;
    const result = message.content.find((b) => b.type === "tool_result");
    if (result && result.type === "tool_result") return result;
  }
  return undefined;
}

function taskObjective(request: ChatCompletionRequest): string {
  const system = request.system ?? "";
  const match = /Objective: (.+)/.exec(system);
  return match?.[1] ?? textOf(request.messages.find((m) => m.role === "user"));
}

function textOf(message: ChatCompletionRequest["messages"][number] | undefined): string {
  if (!message) return "";
  return message.content
    .filter((b): b is Extract<ContentBlock, { type: "text" }> => b.type === "text")
    .map((b) => b.text)
    .join(" ");
}

function estimateTokens(request: ChatCompletionRequest): number {
  return Math.ceil(JSON.stringify(request.messages).length / 4);
}
