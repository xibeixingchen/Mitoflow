# MitoFlow AI Multi-Agent Platform Design

## Objective

Build an AI-driven, multi-agent platform on top of MitoFlow that supports CLI, API, and Web chat entry points while sharing one core runtime. The first implementation phase focuses on the platform kernel: provider adapters, agent orchestration, tool registration, session state, and minimal safe tools. Full chloroplast, mitochondrial assembly, comparative genomics, and pan-organelle workflows are planned as later tool packages.

## Context

MitoFlow is currently a Python 3.10+ plant mitochondrial genome annotation and analysis package with a Typer CLI, a synchronous annotation pipeline, and an early FastAPI/Streamlit web prototype. Its architecture already exposes reusable modules such as `annotate`, `qc`, `viz`, `mtpt`, `rna_edit`, `codon`, `kaks`, `synteny`, `phylo`, `cms`, `repeat`, and `multiconf`.

The target system is inspired by PhenoAssistant, which uses a manager agent to route natural language requests to specialized tools and supporting agents. For organelle genomics, the same pattern should let a user ask for analysis in natural language while the system chooses MitoFlow tools, validates inputs, launches jobs, explains outputs, and captures reusable workflows.

CGAS is the main chloroplast workflow reference. It organizes chloroplast analysis into preparation, comparative genomics, and phylogeny phases, including FASTQ quality control, GetOrganelle assembly, PGA annotation, gene normalization, NCBI conversion, gene content, genome structure, codon usage, amino acid composition, SNP, intron, SSR, nucleotide diversity, and IQ-TREE-based phylogeny. Those capabilities are out of the first platform-kernel phase but must fit the tool interface.

## First-Phase Scope

The first phase builds a reusable AI platform kernel and three thin entry points:

- `mitoflow ai-chat` CLI entry.
- FastAPI endpoint family under `/api/ai/*`.
- Streamlit AI chat page that calls the FastAPI service.

The first phase includes:

- OpenAI-compatible provider adapter.
- Native Anthropic Claude Messages provider adapter.
- A shared `AgentRuntime` used by CLI, API, and Web.
- A tool registry with structured schemas and explicit safety metadata.
- A manager-agent loop that can plan, call tools, observe tool results, and summarize final answers.
- Local session storage and run-event logging.
- Minimal tools that are safe to expose early:
  - list available MitoFlow modules;
  - inspect uploaded or existing result directories;
  - summarize pipeline outputs;
  - launch existing `annotate`, `qc`, and `viz` wrappers through the task abstraction, with file-path validation.

The first phase does not implement the full public-service stack. Authentication, quota enforcement, Redis/Celery workers, PostgreSQL, S3/MinIO, and container sandboxing are represented by interfaces and local implementations only.

## Out of First-Phase Scope

- Full chloroplast CGAS-like implementation.
- Mitochondrial assembly from reads.
- Pan-mitochondrial or pan-chloroplast genomics.
- Full public multi-tenant deployment hardening.
- General arbitrary code execution by agents.
- Fine-tuning, model training, or GPU-based vision workflows.

These become later tool packages once the kernel is stable.

## Architecture

```text
CLI / FastAPI / Streamlit
        |
        v
AI Session Service
        |
        v
AgentRuntime
  - Manager loop
  - Message normalization
  - Tool-call normalization
  - Event logging
  - Final summarization
        |
        +------------------------+
        |                        |
        v                        v
Provider Adapters          Tool Registry
  - OpenAI                 - Tool schemas
  - Anthropic              - Safety policy
  - future local LLM       - Executors
        |                        |
        v                        v
External LLM APIs          MitoFlow / Organelle tools
```

The critical boundary is between provider-specific model protocols and provider-neutral agent operations. The runtime should work with normalized concepts: messages, tool definitions, tool calls, tool results, usage, stop reasons, and streaming deltas.

## Core Modules

### `mitoflow.ai.providers`

Defines provider-neutral request and response models plus provider adapters.

Responsibilities:

- Convert internal messages and tools to OpenAI request shape.
- Convert internal messages and tools to Anthropic Messages request shape.
- Parse provider responses into normalized assistant messages and tool calls.
- Support non-streaming first, then streaming in a later task.
- Keep provider configuration out of code through environment variables and optional config files.

Expected provider config:

- `MITOFLOW_AI_PROVIDER=openai|anthropic`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` optional
- `OPENAI_MODEL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

### `mitoflow.ai.tools`

Defines the registry, tool schema model, tool execution context, and initial MitoFlow tool wrappers.

Each tool must declare:

- stable name;
- description;
- JSON-schema-compatible input schema;
- output schema or structured result model;
- safety level: read-only, writes-output, launches-job, external-network, destructive;
- allowed entry points: CLI, API, Web;
- executor function.

Arbitrary shell execution is not allowed. Tools wrap specific Python functions or specific task types.

### `mitoflow.ai.runtime`

Runs the manager-agent loop.

Responsibilities:

- Receive a user message, session id, provider config, and available tools.
- Add a domain system prompt describing MitoFlow and organelle-genomics constraints.
- Ask the provider for a response.
- Execute validated tool calls.
- Feed tool observations back to the model.
- Stop after final answer, max turns, or tool safety failure.
- Return a structured transcript with events, tool calls, final text, and usage.

The manager loop is intentionally simple in phase one. Separate specialist agents can be represented as tools or prompt profiles first, then split into true sub-agents later.

### `mitoflow.ai.sessions`

Stores conversation state and run events.

Phase one uses local JSONL files:

```text
ai_sessions/
  <session_id>/
    messages.jsonl
    events.jsonl
    artifacts/
```

Later implementations can replace this with PostgreSQL plus object storage without changing the runtime API.

### `mitoflow.ai.service`

Provides application-facing APIs used by CLI and FastAPI.

Primary operations:

- `create_session()`
- `send_message(session_id, message, attachments, provider)`
- `list_tools()`
- `get_session(session_id)`
- `list_events(session_id)`

## Agent Roles

Phase one uses one manager loop with role-specific prompts, not a heavy multi-agent framework. This keeps the protocol and safety boundary controlled.

Initial roles:

- **Manager**: interprets user intent, chooses tools, asks clarification if required, summarizes results.
- **Tool Executor**: deterministic Python layer that validates arguments and runs registered tools.
- **Result Summarizer**: prompt profile used at final response time to convert raw outputs into concise scientific explanations.

Later roles:

- **Assembly Agent**: chooses and runs organelle assembly workflows.
- **Annotation Agent**: runs MitoFlow or chloroplast annotation workflows.
- **Comparative Genomics Agent**: handles gene content, structure, SNP, SSR, pi, codon usage, synteny, orthogroups.
- **Phylogeny Agent**: builds matrices and tree jobs.
- **Reviewer/Critic Agent**: checks tool selection, parameter choices, and output consistency.
- **Workflow Reproducer**: extracts completed steps into reusable pipeline definitions.

## Tool Packages Roadmap

### Phase 1 Tool Package: `mitoflow_core`

- List modules and capabilities.
- Validate file paths and input types.
- Summarize an existing MitoFlow output directory.
- Run existing `AnnotationPipeline` through a controlled task wrapper.
- Run QC on FASTA.
- Generate genome visualization from GenBank when dependencies are available.

### Phase 2 Tool Package: `server_jobs`

- Replace local task execution with queue-backed execution.
- Add job cancellation and progress events.
- Add per-user work directories.
- Add quota and retention hooks.

### Phase 3 Tool Package: `chloroplast`

Inspired by CGAS:

- FASTQ QC and trimming wrapper.
- GetOrganelle chloroplast assembly wrapper.
- Plastome annotation wrapper.
- Gene-name normalization.
- NCBI submission conversion.
- Comparative modules for gene content, structure, codon usage, amino acid composition, SNP, introns, SSR, nucleotide diversity, and phylogeny.

### Phase 4 Tool Package: `mitochondrial_assembly`

- GetOrganelle mitochondrial assembly.
- Alternative assemblers where appropriate, exposed through explicit wrappers.
- Read mapping and coverage validation.
- Circularity and multi-configuration checks.
- Assembly-to-annotation handoff into MitoFlow.

### Phase 5 Tool Package: `pan_organelle`

- Orthogroup inference across mitochondrial and chloroplast genomes.
- Core/accessory gene matrix.
- Presence/absence visualization.
- Gene family gain/loss summaries.
- Cross-species structure and synteny comparison.
- Organelle pangenome graph export where feasible.

## Entry Points

### CLI

Add a Typer command:

```bash
mitoflow ai-chat --provider openai --model gpt-5.2
mitoflow ai-chat --provider anthropic --model claude-opus-4-1-20250805
```

The CLI should support:

- interactive REPL;
- one-shot prompt mode;
- attaching paths with `--file`;
- outputting a transcript JSONL for reproducibility.

### FastAPI

Add endpoints:

```text
GET  /api/ai/health
GET  /api/ai/tools
POST /api/ai/sessions
GET  /api/ai/sessions/{session_id}
POST /api/ai/sessions/{session_id}/messages
GET  /api/ai/sessions/{session_id}/events
```

The first API version uses local session storage. It should not expose provider API keys to clients; keys stay server-side.

### Streamlit

Add an AI Chat tab/page that:

- creates a session;
- uploads or references files;
- sends chat messages to FastAPI;
- renders assistant text, tool calls, and artifacts;
- links to existing task-result downloads when tool calls launch jobs.

## Safety Model

Safety is part of the kernel, not an afterthought.

Rules:

- No arbitrary shell execution from model output.
- All tools validate paths under configured workspace roots.
- Tool calls fail closed if required files do not exist or unsafe paths are requested.
- Public Web mode only exposes a curated allowlist of tools.
- Write tools must write under a session/job output directory.
- Destructive tools are unsupported in phase one.
- Provider prompts must state that biological conclusions are generated from pipeline outputs and require expert review.

## Multi-User and Public-Service Plan

Phase one uses local implementations:

- local sessions in JSONL;
- local artifact directories;
- in-process or background-task execution for small jobs;
- simple server-side provider configuration.

Production replacements:

- PostgreSQL for users, sessions, jobs, audit logs.
- Redis/Celery or equivalent queue for long-running workflows.
- S3/MinIO for uploads and results.
- Auth provider for public access.
- Per-user quotas, rate limiting, and result retention.
- Containerized job sandbox for bioinformatics tools.

## Testing Strategy

Unit tests:

- provider request conversion for OpenAI and Anthropic;
- response normalization for final text and tool calls;
- tool schema registration and duplicate-name detection;
- path validation and safety levels;
- session JSONL persistence.

Integration tests:

- fake provider returns tool call, runtime executes tool, final answer includes tool result;
- CLI one-shot chat with fake provider;
- FastAPI session/message endpoints with fake provider;
- Streamlit is smoke-tested manually or through API-level coverage first.

Regression tests:

- existing MitoFlow tests must continue to pass.
- no existing CLI command behavior changes except adding `ai-chat`.

## Milestone Plan

### Milestone 1: Kernel Skeleton

Create provider-neutral message models, tool registry, local session store, fake provider, and runtime loop. Validate with unit tests and a fake tool.

### Milestone 2: Provider Adapters

Implement OpenAI and Anthropic adapters. Test request/response conversion with mocked clients, not live API calls.

### Milestone 3: MitoFlow Tool Wrappers

Register safe core tools for listing modules, summarizing outputs, running annotation/QC/visualization wrappers, and returning structured artifacts.

### Milestone 4: CLI Entry

Add `mitoflow ai-chat` with one-shot and interactive modes. Use the same runtime and registry as other entry points.

### Milestone 5: FastAPI Entry

Add `/api/ai/*` endpoints and local session persistence. Keep provider keys server-side.

### Milestone 6: Streamlit Entry

Add AI Chat UI that consumes the FastAPI endpoints and renders tool events and artifacts.

### Milestone 7: Public-Service Hardening Plan

Document and stub production replacements for auth, queues, database, object storage, quotas, and sandboxed job execution.

## Success Criteria

- One runtime powers CLI, FastAPI, and Streamlit.
- OpenAI and Anthropic adapters share the same internal tool-call model.
- Tool execution is allowlisted and path-safe.
- A fake-provider integration test covers the full loop: user message -> model tool call -> tool result -> final answer.
- Existing MitoFlow CLI and tests are not regressed.
- The design can accept later chloroplast, mitochondrial assembly, and pan-organelle packages without changing the entry points.

## Sources

- PhenoAssistant paper: https://www.nature.com/articles/s41467-026-71090-y
- PhenoAssistant code: https://github.com/vios-s/PhenoAssistant/
- OpenAI Chat Completions and Responses documentation: https://platform.openai.com/docs/api-reference/chat/create-chat-completion
- Anthropic OpenAI SDK compatibility and Messages documentation: https://docs.anthropic.com/en/api/openai-sdk
- CGAS repository: https://github.com/abdullah30/Chloroplast-Genome-Analysis-Suite-CGAS
- CGAS DOI: https://doi.org/10.1002/imo2.70093
