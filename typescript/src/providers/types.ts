/** Normalized message/content shapes. Mirrors specs/schemas/provider-message.schema.json. */

export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_call"; id: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; toolCallId: string; output: unknown; isError?: boolean };

export interface ProviderMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: ContentBlock[];
  name?: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  cachedInputTokens?: number;
}

export interface ChatCompletionRequest {
  system?: string;
  messages: ProviderMessage[];
  tools?: ToolDefinition[];
  maxTokens?: number;
}

export interface ChatCompletionResult {
  message: ProviderMessage;
  usage: TokenUsage;
  stopReason: "end_turn" | "tool_use" | "max_tokens";
}

/** One adapter per vendor SDK. No routing library in between - this is the whole abstraction. */
export interface ChatModel {
  readonly provider: string;
  readonly model: string;
  complete(request: ChatCompletionRequest): Promise<ChatCompletionResult>;
}
