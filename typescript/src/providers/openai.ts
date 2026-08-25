import OpenAI from "openai";
import type {
  ChatCompletionRequest,
  ChatCompletionResult,
  ChatModel,
  ContentBlock,
  ProviderMessage,
} from "./types.js";

/** Thin adapter over the official OpenAI SDK, normalized to the same ChatModel contract. */
export class OpenAIChatModel implements ChatModel {
  readonly provider = "openai";
  private readonly client: OpenAI;

  constructor(
    apiKey: string,
    readonly model: string = "gpt-5",
  ) {
    this.client = new OpenAI({ apiKey });
  }

  async complete(request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [];
    if (request.system) messages.push({ role: "system", content: request.system });
    for (const m of request.messages) messages.push(...toOpenAIMessages(m));

    const response = await this.client.chat.completions.create({
      model: this.model,
      max_tokens: request.maxTokens ?? 4096,
      messages,
      tools: request.tools?.map((t) => ({
        type: "function",
        function: { name: t.name, description: t.description, parameters: t.inputSchema },
      })),
    });

    const choice = response.choices[0];
    if (!choice) throw new Error("OpenAI response contained no choices");

    return {
      message: fromOpenAIMessage(choice.message),
      usage: {
        inputTokens: response.usage?.prompt_tokens ?? 0,
        outputTokens: response.usage?.completion_tokens ?? 0,
      },
      stopReason: choice.finish_reason === "tool_calls" ? "tool_use" : choice.finish_reason === "length" ? "max_tokens" : "end_turn",
    };
  }
}

function toOpenAIMessages(message: ProviderMessage): OpenAI.Chat.ChatCompletionMessageParam[] {
  const text = message.content.filter((b) => b.type === "text").map((b) => (b as { text: string }).text).join("\n");
  const toolCalls = message.content.filter((b) => b.type === "tool_call") as Extract<ContentBlock, { type: "tool_call" }>[];
  const toolResults = message.content.filter((b) => b.type === "tool_result") as Extract<ContentBlock, { type: "tool_result" }>[];

  const out: OpenAI.Chat.ChatCompletionMessageParam[] = [];
  if (message.role === "assistant") {
    out.push({
      role: "assistant",
      content: text || null,
      tool_calls: toolCalls.length
        ? toolCalls.map((tc) => ({
            id: tc.id,
            type: "function",
            function: { name: tc.name, arguments: JSON.stringify(tc.input) },
          }))
        : undefined,
    });
  } else if (toolResults.length) {
    for (const tr of toolResults) {
      out.push({
        role: "tool",
        tool_call_id: tr.toolCallId,
        content: typeof tr.output === "string" ? tr.output : JSON.stringify(tr.output),
      });
    }
  } else {
    out.push({ role: "user", content: text });
  }
  return out;
}

function fromOpenAIMessage(message: OpenAI.Chat.ChatCompletionMessage): ProviderMessage {
  const content: ContentBlock[] = [];
  if (message.content) content.push({ type: "text", text: message.content });
  for (const tc of message.tool_calls ?? []) {
    if (tc.type !== "function") continue;
    content.push({
      type: "tool_call",
      id: tc.id,
      name: tc.function.name,
      input: JSON.parse(tc.function.arguments || "{}"),
    });
  }
  return { role: "assistant", content };
}
