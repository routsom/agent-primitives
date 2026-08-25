# Multi-agent system diagrams

Companion to `multi-agent-architecture-notes.md`, mirroring the single-agent diagram set. Modeled on the orchestrator-worker topology (lead agent + parallel subagents), the pattern recommended as the default in the notes.

---

## 1. High-level design

```mermaid
flowchart TB
    subgraph Client["Client layer"]
        User([User])
    end

    subgraph LeadLayer["Lead agent"]
        LeadAgent[Lead agent: plans, decomposes, decides sufficiency]
        PlanMemory[(Plan / progress memory)]
    end

    subgraph HarnessLayer["Shared harness"]
        Harness[Harness: auth, validation, scoping, idempotency, delegation-depth cap]
        JobStore[(Durable job store)]
    end

    subgraph WorkerLayer["Subagent pool, parallel"]
        SubA[Subagent A]
        SubB[Subagent B]
        SubC[Subagent C]
    end

    subgraph ToolLayer["Tools, scoped per agent role"]
        SearchTools[Search / retrieval tools]
        ActionTools[Action tools, lead-only]
    end

    subgraph ArtifactLayer["Artifact store"]
        Artifacts[(External artifact store<br/>large outputs, lightweight refs returned)]
    end

    subgraph SynthLayer["Synthesis"]
        CitationAgent[Citation / synthesis agent]
    end

    subgraph ObsLayer["Observability"]
        Traces[(Trace store, turn to agent to call)]
        EvalPipeline[LLM-judge + human review]
        Metrics[Metrics and anomaly detection]
    end

    subgraph DeployLayer["Production controls"]
        Rainbow[Rainbow deployment]
        KillSwitch[Kill switch: swarm-level and per-agent-type]
    end

    User --> LeadAgent
    LeadAgent --> PlanMemory
    LeadAgent --> Harness
    Harness --> SubA
    Harness --> SubB
    Harness --> SubC
    SubA --> SearchTools
    SubB --> SearchTools
    SubC --> SearchTools
    LeadAgent --> ActionTools
    Harness --> JobStore
    SubA --> Artifacts
    SubB --> Artifacts
    SubC --> Artifacts
    Artifacts --> LeadAgent
    LeadAgent --> CitationAgent
    CitationAgent --> User
    LeadAgent --> Traces
    SubA --> Traces
    SubB --> Traces
    SubC --> Traces
    Traces --> EvalPipeline --> Metrics
    DeployLayer -.-> LeadLayer
    DeployLayer -.-> WorkerLayer
```

**Reading it**: the harness is shared infrastructure, not duplicated per agent — every agent's tool calls pass through the same auth/validation/idempotency/delegation-depth checks, which is what prevents an agent-to-agent shortcut around security (notes section 7). Subagents write large outputs to the artifact store and hand the lead agent a lightweight reference, not the raw content — this is the "avoid the game of telephone" pattern from the notes. Deployment controls apply across both the lead and worker layers because a version change can land mid-execution on either.

---

## 2. Sequence diagram — how the lead and subagents actively integrate

```mermaid
sequenceDiagram
    actor User
    participant Lead as Lead agent
    participant Memory as Plan memory
    participant Harness
    participant SubA as Subagent A
    participant SubB as Subagent B
    participant Artifacts as Artifact store
    participant Citation as Citation agent
    participant Trace as Trace / eval

    User->>Lead: Submit query
    Lead->>Lead: Assess complexity, decide subagent count and effort
    Lead->>Memory: Save plan (survives context truncation)
    Lead->>Harness: Spawn subagents with explicit objective, output format, boundaries

    par Subagent A works
        Harness->>SubA: Task A, scoped tools
        SubA->>SubA: Search, evaluate, refine query
        SubA->>Artifacts: Store raw findings
        Artifacts-->>SubA: Reference
        SubA-->>Harness: Distilled findings + reference
    and Subagent B works
        Harness->>SubB: Task B, scoped tools
        SubB->>SubB: Search, evaluate, refine query
        SubB->>Artifacts: Store raw findings
        Artifacts-->>SubB: Reference
        SubB-->>Harness: Distilled findings + reference
    end

    Harness-->>Lead: Aggregated distilled findings
    Lead->>Lead: Sufficient, or need more research?

    alt Needs more research
        Lead->>Harness: Spawn additional or refined subagents
        Harness-->>Lead: Additional findings
    else Sufficient
        Lead->>Citation: Findings + source references
        Citation->>Citation: Attribute claims to sources
        Citation-->>Lead: Cited report
    end

    Lead->>Trace: Log spans per agent: tokens, cost, delegation depth
    Lead-->>User: Final response with citations
    Trace->>Trace: Check flags, attribute any failure to originating agent
    Trace-->>Trace: If flagged, queue judge or human review
```

**Reading it**: the `par` block is the parallel fan-out that makes multi-agent worth its token cost — both subagents work simultaneously, not in sequence. Notice the lead agent explicitly decides "sufficient, or need more research" as its own step, rather than subagents deciding autonomously when the whole task is done — that judgment stays centralized. The plan gets saved to memory before any subagent spawns, so a context truncation mid-run doesn't lose the strategy.

---

## 3. Flow chart — end-to-end decomposition and coordination logic

```mermaid
flowchart TD
    Start([User query]) --> Assess[Lead agent assesses complexity]
    Assess --> ScaleCheck{Complexity tier}
    ScaleCheck -->|Simple| OneAgent[1 subagent, small tool-call budget]
    ScaleCheck -->|Moderate| FewAgents[2-4 subagents, moderate budget each]
    ScaleCheck -->|Complex| ManyAgents[Many subagents, divided responsibilities]

    OneAgent --> DepthCheck{Delegation depth cap reached?}
    FewAgents --> DepthCheck
    ManyAgents --> DepthCheck
    DepthCheck -->|Yes| Reject[Reject further spawning, proceed with current agents]
    DepthCheck -->|No| SpawnPar[Spawn subagents in parallel via harness]

    Reject --> SpawnPar
    SpawnPar --> SubLoop[Each subagent: search, evaluate, refine]
    SubLoop --> SubResult{Subagent outcome}
    SubResult -->|Success| Distill[Distill findings, store artifact, return reference]
    SubResult -->|Tool failure, transient| SubRetry{Retries left?}
    SubRetry -->|Yes| SubLoop
    SubRetry -->|No| PartialFlag[Flag as partial, return what exists]
    SubResult -->|No results found| StopCriterion[Stop, report empty rather than loop]

    Distill --> Aggregate[Lead aggregates distilled findings]
    PartialFlag --> Aggregate
    StopCriterion --> Aggregate

    Aggregate --> SufficiencyCheck{Lead: sufficient coverage?}
    SufficiencyCheck -->|No, and budget remains| Assess
    SufficiencyCheck -->|No, budget exhausted| PartialResponse[Proceed with partial coverage, disclose gap]
    SufficiencyCheck -->|Yes| Synthesize[Citation / synthesis agent]

    Synthesize --> LogTrace[Log trace: per-agent spans, cost, delegation depth]
    PartialResponse --> LogTrace
    LogTrace --> FlagCheck{needs_review or structural flag?}
    FlagCheck -->|Yes| TriggerEval[Trigger judge or human review, async]
    FlagCheck -->|No| Respond
    TriggerEval --> Respond([Response served to user])
```

**Reading it**: the delegation-depth cap and the per-subagent retry cap are two distinct circuit breakers, same principle as the single-agent flowchart's two separate breakers — one bounds runaway *spawning*, the other bounds runaway *retrying*. The "no results found" branch is deliberately separate from a tool failure: it's a stopping criterion, not an error, and treating it as an error would push the system toward the unproductive-search-loop failure mode documented in the notes.

---

*Companion to `multi-agent-architecture-notes.md` and, at one level further back, `support-agent-architecture-notes.md` / `support-agent-system-diagrams.md`.*
