# Multi-agent AI systems — architecture & production best practices

Companion to `support-agent-architecture-notes.md`. That file's tool contracts, harness validation, idempotency, prompt caching, memory hygiene, logging shape, and production controls all still apply here — **per agent**. This file covers what's genuinely different or additional once you have more than one agent, grounded partly in Anthropic's own published engineering lessons from building their multi-agent Research system.

---

## 1. When to use multi-agent at all — read this before anything else

A multi-agent system is multiple agents (LLMs autonomously using tools in a loop) working together, coordinating rather than one agent doing everything. This is not the default architecture — it's an escalation you earn with evidence, not a starting point.

- **Good fit**: open-ended, breadth-first tasks that decompose into independent parallel threads (e.g. research across many independent sources), tasks whose required information exceeds a single context window, tasks interfacing with numerous complex tools.
- **Bad fit**: tasks needing heavy shared context or tight dependencies between steps (most coding tasks fall here), tasks needing real-time coordination between agents, anything a single well-prompted agent with good tools can already do.
- **The honest industry pattern**: teams regularly spend months building elaborate multi-agent architectures only to discover that better prompting and better tools on a *single* agent gets equivalent results for less cost and complexity. Try that first. Multi-agent is justified by measured evidence of a ceiling single-agent can't clear, not by an assumption that more agents means more capable.
- **The cost reality check that should anchor this decision**: a single agent typically burns roughly 4x the tokens of a plain chat turn; a multi-agent system burns roughly 15x. Token usage alone explains the large majority of performance variance between systems — multi-agent mostly works because it buys more tokens spent in parallel, not because of some qualitatively different intelligence. This only pays off when the task's value clearly justifies that multiplier.

---

## 2. Topology patterns

- **Orchestrator-worker (lead agent + parallel subagents)** — a lead agent plans, decomposes, and spawns subagents that work independently and report back distilled findings. This is the pattern to default to; it's what production multi-agent research systems use, and it maps cleanly onto the single-agent harness architecture already built (the lead agent *is* an orchestrator; each subagent gets its own orchestrator+harness instance).
- **Sequential pipeline** — a fixed handoff chain (agent A's output becomes agent B's input). Simple to reason about, but brittle if a task doesn't actually decompose linearly, and doesn't parallelize.
- **Parallel fan-out/fan-in without a lead** — multiple agents attack the same problem independently for redundancy/verification, then results get merged or voted on. Useful for high-stakes single answers where you want independent corroboration, expensive for everything else.
- **Peer-to-peer / debate** — agents critique or challenge each other's outputs. Genuinely useful for adversarial review of a specific artifact, but coordination-heavy and rarely worth it as a general-purpose pattern.

Default to orchestrator-worker unless you have a specific reason (verification, a fixed known pipeline) to use something else.

---

## 3. Task decomposition & delegation — teach the orchestrator to delegate explicitly

This is the single highest-leverage prompt engineering problem in a multi-agent system. Vague delegation causes real, measured failures: subagents given short instructions like "research the semiconductor shortage" misinterpreted scope and duplicated each other's work — in one documented case, one subagent explored an old, unrelated crisis while two others independently investigated the same current topic, with no actual division of labor.

Each subagent needs, explicitly, in its task description:
- A clear **objective**
- A specified **output format**
- **Guidance on which tools/sources** to use
- **Clear task boundaries** distinguishing it from siblings' work

**Scale agent count and effort to task complexity, explicitly** — don't leave this to the model's judgment alone. Embed scaling rules directly in the orchestrator's prompt: simple fact-finding gets one agent with a handful of tool calls; direct comparisons get a few subagents with a moderate call budget each; genuinely complex research gets many subagents with clearly divided responsibilities. Without explicit rules, agents both over-invest in simple queries and under-resource complex ones.

---

## 4. Inter-agent communication & context isolation

- **Each subagent gets its own clean context window.** This is what makes parallel exploration possible without one agent's tangents polluting another's reasoning — same principle as context composition in the single-agent design, just instantiated per agent instead of per turn.
- **Findings get distilled before returning to the lead, never dumped raw.** Same structured-handoff principle as tool contracts in the single-agent notes — a subagent's return value is a designed artifact, not a transcript.
- **Route large outputs (reports, code, generated data) to external storage; pass lightweight references back to the coordinator**, rather than copying big blobs through conversation history repeatedly. This avoids both token bloat and a "game of telephone" degradation where the lead agent's summary of a subagent's summary loses fidelity with each hop.
- **Synchronous vs. asynchronous execution** — most production systems, including Anthropic's own, run the lead agent synchronously waiting for its subagents to finish before proceeding. It's simpler to reason about and debug, at the cost of the whole system blocking on the slowest subagent. Asynchronous execution unlocks more parallelism (agents working concurrently, spawning new subagents as needed) but adds real complexity in result ordering, state consistency, and error propagation across agents. Start synchronous. Only move to async once you have concrete evidence the blocking is the actual bottleneck.

---

## 5. Shared state & memory across agents

Extends the single-agent state management section — now with multiple concurrent writers.

- **Persist the plan to external memory before spawning subagents**, not after — if the lead agent's context gets truncated mid-process (a real risk on long-running multi-agent tasks), the plan must survive that, or the whole run silently loses its own strategy.
- **Summarize completed phases and store essentials externally** as work progresses, rather than carrying the full history forward. When context limits approach, spawn a fresh subagent with a clean context and an explicit, deliberate handoff of only what's needed — not the full accumulated history.
- **End-state evaluation, not turn-by-turn, for agents that mutate shared state.** Agents can take different valid paths to the same correct outcome — one might search three sources, another ten, and both be right. Validate discrete checkpoints and final state rather than trying to enforce one prescribed sequence of steps.
- **Define write ownership per resource explicitly** — which agent (or the harness) has authority to act on a given record — to prevent two agents from taking conflicting actions on the same piece of state. This is cross-agent idempotency: the same discipline as the single-agent idempotency-key pattern, now needing to account for more than one actor.

---

## 6. Tools & harness for multi-agent

The harness principles don't change — validate, scope, authenticate, enforce idempotency — but scoping now happens **per agent role**, not just per turn. A search-only subagent should never hold refund-issuing tools even if the lead agent does; least privilege applies at the agent level.

**Tool descriptions matter more here than in single-agent systems.** With many tools — especially externally-defined ones of inconsistent quality — a bad or ambiguous description sends an agent down a completely wrong path before it's done anything wrong itself. Treat tool descriptions as a first-class engineering artifact worth testing and iterating on, not incidental documentation. One effective, low-cost pattern: have a model attempt to use a tool repeatedly, diagnose where the description misled it, and rewrite the description — this kind of self-improving tool documentation has produced large reductions in downstream task-completion time for the agents that use the improved description afterward. Worth running as a recurring maintenance loop, not a one-time pass.

---

## 7. Trust boundaries between agents — this is the security section unique to multi-agent

Extend "treat tool outputs as untrusted" (from the single-agent notes) to: **treat other agents' outputs as untrusted too**, especially any agent that has processed external or web content. Prompt injection can propagate agent-to-agent, not just tool-to-agent — a compromised or manipulated instruction picked up by a research subagent can ride along in its "findings" straight into the lead agent's next decision.

- An agent receiving a delegated instruction from another agent should pass through the **same harness validation** it would if the instruction came directly from a user — never create an agent-to-agent shortcut around auth or confirmation checks. "Another agent said so" is not an authorization boundary.
- Least privilege applies at the agent-role level: define what each agent type is allowed to do, independent of what any other agent in the system can do.

---

## 8. Cost & latency — the central engineering constraint, not an afterthought

The ~4x (single agent) and ~15x (multi-agent) token multipliers over a plain chat turn from section 1 aren't a footnote — they're the primary economic constraint on this architecture, and they should shape the design directly:

- **Hard caps on subagent count and per-subagent tool-call budget**, embedded as explicit rules rather than left to model judgment alone — this is the swarm-level version of the single-agent iteration/budget cap from the orchestrator design.
- **Cap delegation depth explicitly.** If agent A can spawn B, decide deliberately whether B may spawn further agents, and bound it — unbounded recursive delegation is exactly the kind of runaway cost (and potential infinite loop) this architecture is prone to without a hard ceiling.
- **Parallelize tool calls aggressively where tasks are genuinely independent** — both across subagents (spin several up at once rather than serially) and within a subagent (multiple tool calls in flight at once). This is one of the largest available latency levers, with documented reductions in total task time of up to 90% for complex queries when applied at both levels.

---

## 9. Failure modes unique to multi-agent

- **Runaway spawning** — dozens of subagents launched for a query that needed one. Fixed by explicit scaling rules (section 3) plus hard caps (section 8), not prompting alone.
- **Unproductive search loops** — agents that keep searching for information that doesn't exist rather than recognizing a dead end. Needs explicit stopping criteria in the prompt and harness-enforced iteration caps.
- **Agents distracting each other with excessive updates** — needs a minimal, defined communication protocol (section 4) rather than open-ended chatter between agents.
- **Cascading errors** — because minor issues compound into large behavioral shifts, one early wrong turn can send the entire system down a completely different trajectory than intended. Treat this as a systemic architectural risk, not an isolated bug to patch reactively.
- **Partial completion** — some subagents succeed, others fail or time out. The orchestrator needs an explicit policy for this (proceed with partial results and flag the gap, vs. block and retry the failed ones) rather than silently treating a partial result set as complete.

---

## 10. Evaluations for multi-agent — genuinely harder, needs a different method

Traditional evals assume a fixed correct path: given input X, follow path Y, produce output Z. Multi-agent systems break this assumption — different agents can take entirely different valid routes to the same correct outcome. Evaluation has to judge whether the outcome is right and the process was reasonable, not whether a prescribed sequence of steps was followed exactly.

- **Start evaluating immediately, with a small sample.** Early-stage changes tend to have large, easy-to-detect effects — a prompt tweak might move success rates dramatically. A few dozen realistic queries is enough to see that. Don't wait for a large eval set before starting; starting small and early beats a comprehensive eval you keep delaying.
- **LLM-as-judge with an explicit multi-criteria rubric works well for open-ended output** — a single LLM call scoring against several named criteria at once (accuracy, completeness, source/tool-use quality, and so on) in one pass tends to be more consistent with human judgment than running several separate narrow judge calls.
- **Human evaluation still catches what automation misses** — systematic biases (e.g. consistently favoring lower-quality but heavily-optimized sources over authoritative ones) have shown up in human review after passing automated checks cleanly. Keep manual spot-checking in the loop; don't fully automate it away.
- **For agents that mutate shared or persistent state, evaluate end-state and defined checkpoints**, not turn-by-turn process — directly extends section 5 and the single-agent state management section.

---

## 11. Observability — distributed tracing across agent boundaries

Extends the single-agent trace-tree design (support-agent notes, section 22) with a new middle layer: a trace now spans multiple agents, each with its own child spans for its model and tool calls — turn → agent → model/tool call, not just turn → model/tool call.

- **Track agent decision patterns and interaction structure** — which agent spawned which, delegation depth, handoff shape — as a monitoring layer distinct from reading individual conversation content. This gives you system-level visibility (and can be designed to preserve privacy, by monitoring structure rather than content) while still surfacing where coordination is breaking down.
- **Full production tracing is not optional here.** Multi-agent systems are non-deterministic between runs even with identical prompts, which makes "the agent didn't find something obvious" reports very hard to root-cause without a full trace — was it a bad search query, a poor tool choice, a tool failure, or bad delegation from the lead? Tracing is how you attribute a bad outcome to the specific agent and decision that caused it, which is a fundamentally harder problem here than in a single-agent system.

---

## 12. Production controls & deployment for multi-agent

- **Rainbow deployments, not instant cutover.** Multi-agent systems are long-running, stateful webs of prompts, tools, and execution logic running almost continuously — a version change can land while agents are mid-execution. Gradually shift traffic from the old version to the new one while both run simultaneously, rather than switching all at once. This is the canary rollout pattern from the single-agent production controls section, now a necessity rather than an optimization, because of statefulness.
- **Durable execution and resumability.** Agents must be able to resume from where they were when an error occurred, not restart from scratch — restarts are expensive, frustrating, and risk duplicate side effects if any step wasn't idempotent. This extends the durable-job pattern from the cancel-mid-action discussion in the single-agent notes to the entire multi-agent execution, not just a single tool call.
- **Combine model adaptability with deterministic safeguards** — letting an agent itself adapt when a tool fails (informing it and letting it reroute) works well, but pair that adaptability with deterministic retry logic and regular checkpoints underneath. Same defense-in-depth principle as the single-agent orchestrator section, applied at the scale of a whole multi-step run.
- **Kill switch needs two levels**, not one: pause the entire swarm, or pause just one agent type (e.g. the web-search subagent) without taking down the whole system. A single global switch is too blunt once multiple independently-versioned agent types exist.

---

## 13. What carries over unchanged from the single-agent notes

No need to re-derive these — apply them per agent:

- **Tool contracts** (structured input/output envelope, idempotency keys)
- **Harness validation** (auth, scope, confirmation gates) — no shortcuts for agent-to-agent calls (section 7)
- **Prompt caching and context layering** — applied to each agent's own context window independently
- **Memory hygiene** (soft facts vs. hard facts, PII filtering, per-user isolation) — unchanged in principle; now potentially read/written by multiple agents, so the write-ownership point from section 5 matters more
- **Logging/trace structure** — same shape, nested one level deeper (section 11)
- **"Treat prompts as code"** — now applies to every agent's prompt independently, with one added wrinkle: a change to the lead agent's delegation prompt can unpredictably change how subagents behave downstream. This emergent-behavior risk is specific to multi-agent systems and worth testing for explicitly, not assumed away because each individual prompt change looks small.
