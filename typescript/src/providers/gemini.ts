import { GoogleGenAI } from "@google/genai";
import type {
  ChatCompletionRequest,
  ChatCompletionResult,
  ChatModel,
  ContentBlock,
  ProviderMessage,
} from "./types.js";

/** Thin adapter over the official Google GenAI SDK. */
export class GeminiChatModel implements ChatModel {
  readonly provider = "google";
  private readonly client: GoogleGenAI;

  constructor(
    apiKey: string,
    readonly model: string = "gemini-3-pro",
  ) {
    this.client = new GoogleGenAI({ apiKey });
  }

  async complete(request: ChatCompletionRequest): Promise<ChatCompletionResult> {
    const response = await this.client.models.generateContent({
      model: this.model,
      contents: request.messages.map(toGeminiContent),
      config: {
        systemInstruction: request.system,
        maxOutputTokens: request.maxTokens ?? 4096,
        tools: request.tools?.length
          ? [
              {
                functionDeclarations: request.tools.map((t) => ({
                  name: t.name,
                  description: t.description,
                  parameters: t.inputSchema,
                })),
              },
            ]
          : undefined,
      },
    });

    const content: ContentBlock[] = [];
    let callIndex = 0;
    for (const part of response.candidates?.[0]?.content?.parts ?? []) {
      if (part.text) content.push({ type: "text", text: part.text });
      if (part.functionCall) {
        content.push({
          type: "tool_call",
          id: `${part.functionCall.name}-${callIndex++}`,
          name: part.functionCall.name ?? "unknown",
          input: (part.functionCall.args ?? {}) as Record<string, unknown>,
        });
      }
    }

    const hasToolCall = content.some((b) => b.type === "tool_call");
    return {
      message: { role: "assistant", content },
      usage: {
        inputTokens: response.usageMetadata?.promptTokenCount ?? 0,
        outputTokens: response.usageMetadata?.candidatesTokenCount ?? 0,
      },
      stopReason: hasToolCall ? "tool_use" : "end_turn",
    };
  }
}

function toGeminiContent(message: ProviderMessage) {
  return {
    role: message.role === "assistant" ? "model" : "user",
    parts: message.content.map((block) => {
      if (block.type === "text") return { text: block.text };
      if (block.type === "tool_call") return { functionCall: { name: block.name, args: block.input } };
      return {
        functionResponse: {
          name: block.toolCallId,
          response: typeof block.output === "object" && block.output !== null ? (block.output as Record<string, unknown>) : { value: block.output },
        },
      };
    }),
  };
}
