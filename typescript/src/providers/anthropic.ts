import Anthropic from "@anthropic-ai/sdk";
import type {
  ChatCompletionRequest,
  ChatCompletionResult,
  ChatModel,
  ContentBlock,
  ProviderMessage,
} from "./types.js";

/** Thin adapter over the official Anthropic SDK. No routing library, no framework. */
export class AnthropicChatModel implements ChatModel {
  readonly provider = "anthropic";
  private readonly client: Anthropic;

  constructor(
    apiKey: string,
    readonly model: string = "claude-sonnet-5",
  ) {
    this.client = new Anthropic({ apiKey });
  }

  async complete(request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    const response = await this.client.messages.create({
      model: this.model,
      max_tokens: request.maxTokens ?? 4096,
      system: request.system
        ? [{ type: "text", text: request.system, cache_control: { type: "ephemeral" } }]
        : undefined,
      messages: request.messages.map(toAnthropicMessage),
      tools: request.tools?.map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: t.inputSchema as Anthropic.Tool.InputSchema,
      })),
    });

    return {
      message: fromAnthropicMessage(response),
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
        cachedInputTokens: response.usage.cache_read_input_tokens ?? undefined,
      },
      stopReason: response.stop_reason === "tool_use" ? "tool_use" : response.stop_reason === "max_tokens" ? "max_tokens" : "end_turn",
    };
  }
}

function toAnthropicMessage(message: ProviderMessage): Anthropic.MessageParam {
  return {
    role: message.role === "assistant" ? "assistant" : "user",
    content: message.content.map((block): Anthropic.ContentBlockParam => {
      if (block.type === "text") return { type: "text", text: block.text };
      if (block.type === "tool_call") {
        return { type: "tool_use", id: block.id, name: block.name, input: block.input };
      }
      return {
        type: "tool_result",
        tool_use_id: block.toolCallId,
        content: typeof block.output === "string" ? block.output : JSON.stringify(block.output),
        is_error: block.isError,
      };
    }),
  };
}

function fromAnthropicMessage(response: Anthropic.Message): ProviderMessage {
  const content: ContentBlock[] = [];
  for (const block of response.content) {
    if (block.type === "text") {
      content.push({ type: "text", text: block.text });
    } else if (block.type === "tool_use") {
      content.push({ type: "tool_call", id: block.id, name: block.name, input: block.input as Record<string, unknown> });
    }
    // Other block types (thinking, server tool use, etc.) are not part of this boilerplate's
    // normalized ContentBlock union - extend it deliberately if you need to surface them.
  }
  return { role: "assistant", content };
}
