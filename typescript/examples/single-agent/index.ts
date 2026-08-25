import { resolveProvider } from "../../src/providers/index.js";
import { loadConfig } from "../../src/config/index.js";

/**
 * The baseline this boilerplate deliberately keeps around: one well-prompted agent, no
 * orchestrator, no subagents. Multi-agent (examples/research-task) is an escalation you earn
 * with evidence a single agent can't clear - not the default. Compare the two before reaching
 * for the orchestrator-worker path on a real task.
 */
async function main() {
  const config = loadConfig();
  const model = resolveProvider(config.defaultProvider);

  console.log(`[single-agent] using provider "${model.provider}" (${model.model})`);

  const result = await model.complete({
    system: "You are a helpful, direct assistant. Answer in a few sentences.",
    messages: [
      {
        role: "user",
        content: [{ type: "text", text: "What are the main tradeoffs between orchestrator-worker and sequential-pipeline multi-agent topologies?" }],
      },
    ],
  });

  const text = result.message.content
    .filter((b) => b.type === "text")
    .map((b) => (b as { text: string }).text)
    .join("\n");

  console.log("\n[single-agent result]");
  console.log(text);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
