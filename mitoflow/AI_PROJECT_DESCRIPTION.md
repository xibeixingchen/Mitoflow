# MitoFlow AI — Multi-Agent Platform for Plant Organelle Genomics

## Architecture

```
Browser (HTML5 Chat UI)
       │
       ▼
FastAPI Backend (:8002)
  ├── /api/auth/*     — Register, Login (JWT), API key management
  ├── /api/ai/*       — Chat, Sessions (persisted), Results
  ├── /api/files/*    — Workspace upload, download, delete
  └── /               — Single-page HTML5 chat application
       │
       ▼
MitoFlow AI Engine (src/mitoflow/ai/)
  ├── AgentRuntime       — Manager-agent loop (max 12 turns)
  ├── DeepAgentRuntime   — LangGraph/DeepAgents sub-agent delegation
  ├── Providers          — OpenAI + Anthropic protocol adapters
  ├── Tool Registry      — 22 registered tools (4 safety levels)
  └── Service Layer      — AIService (CLI + API + Web entry points)
       │
       ├── Knowledge Layer ───────────────┐
       │   ├── gene_info_lookup           │
       │   ├── search_genes               │
       │   └── splicing/editing info      │
       │                                  │
       ├── MCP Literature ────────────────┤
       │   ├── 21 structured references   │  Tool
       │   ├── DOI/PMID indexed           │  Registry
       │   └── crossref API fallback      │
       │                                  │
       ├── LLM Wiki ──────────────────────┤
       │   ├── 9 knowledge pages          │
       │   └── wiki_search/wiki_get_page  │
       │                                  │
       ├── Skills ────────────────────────┤
       │   ├── 6 ClawBio-style SKILL.md   │
       │   └── assembly/annotation/qc/... │
       │                                  │
       ├── Web Tools ─────────────────────┤
       │   ├── web_search_literature      │
       │   ├── web_lookup_github          │
       │   └── web_fetch_page             │
       │                                  │
       └── MitoFlow Core ─────────────────┘
           ├── list_mitoflow_modules
           ├── list_workspace_files
           ├── summarize_result_directory
           ├── run_annotation
           └── delegate_task (sub-agent)
```

## Key Design Decisions

### 1. Provider-Neutral Architecture
- Internal models (`AIMessage`, `ToolCall`, `ProviderRequest`) decoupled from LLM APIs
- `OpenAIChatAdapter` → GPT, DeepSeek, GLM, Kimi, Qwen, Baichuan, OpenRouter, Ollama
- `AnthropicAdapter` → Claude, Kimi Code, DeepSeek Code (custom `base_url` support)
- 13 pre-configured provider presets with auto-detected base URLs

### 2. Safety-First Tool Registry
| Level | Description | Example |
|-------|-------------|---------|
| `read_only` | No side effects | gene lookup, wiki search |
| `writes_output` | Creates files | report generation |
| `launches_job` | Runs analysis | annotation pipeline |
| `external_network` | Makes HTTP calls | web search |

### 3. Session Persistence
- Sessions stored as JSONL files (`.mitoflow_ai_sessions/{id}/messages.jsonl`)
- Session metadata in `_sessions.json` (name, pinned, first_message)
- Survives server restart via filesystem scan on startup
- Per-user session isolation via JWT tokens

### 4. Workspace & Results
- Uploaded files → `mitoflow_workspace/{session_id}/` (per-session)
- Analysis outputs → `.mitoflow_ai_sessions/{session_id}/artifacts/`
- Results directory browser with tree view and inline file preview
- Pipeline trace showing step-by-step tool execution chain

### 5. Authentication
- Email + username + password registration (PBKDF2-SHA256 hashing)
- JWT tokens (HMAC-SHA256, 30-day expiry)
- Per-provider API keys stored in browser localStorage
- Optional server-side API key persistence

## LLM Providers

| Provider | Protocol | Base URL | Models |
|----------|----------|----------|--------|
| DeepSeek | OpenAI | `api.deepseek.com/v1` | deepseek-chat, deepseek-reasoner |
| DeepSeek Code | Anthropic | `api.deepseek.com/anthropic` | deepseek-v4-pro, deepseek-v4-flash |
| GLM (Zhipu) | OpenAI | `open.bigmodel.cn/api/paas/v4` | glm-4-plus, glm-4-flash |
| Kimi (Moonshot) | OpenAI | `api.moonshot.cn/v1` | moonshot-v1-8k, moonshot-v1-32k |
| Kimi Code | Anthropic | `api.kimi.com/coding/` | K2.6 |
| Qwen (Tongyi) | OpenAI | `dashscope.aliyuncs.com/compatible-mode/v1` | qwen-plus, qwen-max |
| Baichuan | OpenAI | `api.baichuan-ai.com/v1` | Baichuan4 |
| OpenAI | OpenAI | `api.openai.com/v1` | gpt-4o, gpt-4o-mini |
| Claude | Anthropic | (native) | claude-sonnet-4, claude-haiku-4 |
| OpenRouter | OpenAI | `openrouter.ai/api/v1` | 200+ models |
| Ollama | OpenAI | `localhost:11434/v1` | llama3, qwen2.5 |

## API Endpoints

### Authentication
```
POST /api/auth/register  {"email","username","password"} → user
POST /api/auth/login     {"email","password"} → {token, user}
POST /api/auth/me        Bearer token → user info
POST /api/auth/api-key   {"api_key"} → ok
```

### AI Chat
```
POST /api/ai/sessions                    → {session_id}
GET  /api/ai/sessions                    → [{id, name, pinned, ...}]
GET  /api/ai/sessions/{id}/messages      → {messages, events}
GET  /api/ai/sessions/{id}/results       → {results: [{path, files}]}
GET  /api/ai/sessions/{id}/results/download?path= → file
PATCH /api/ai/sessions/{id}              → update name/pinned
DELETE /api/ai/sessions/{id}             → delete session
POST /api/ai/chat    {"session_id","message","provider","model","api_key","base_url"}
GET  /api/ai/tools                       → tool list
```

### Files
```
POST   /api/files/upload    multipart files + session_id
GET    /api/files/list      ?session_id=
GET    /api/files/download/{name} ?session_id=
DELETE /api/files/{name}   ?session_id=
```

## UI Layout

```
┌──────┬───────────┬──────────────────────┬──────────────┐
│ Nav  │ Session   │    Main Content       │   Results    │
│ Rail │ Drawer    │  (Chat/Tools/...)     │   Panel      │
│ 58px │ 260px⇔    │                      │   300px⇔     │
│      │           │                      │              │
│ 💬   │ ⋯ Session│  Chat messages       │ 📁 Files     │
│ 🔧   │ 📌 Pinned│  + input area        │ 👁 Preview   │
│ 📋   │ ⋯        │                      │ 🔗 Pipeline  │
│ 📤   │           │  or Tools/Skills     │              │
│ 📊   │           │  or Upload/Results   │              │
│ 👤   │           │  or Settings         │              │
│ ⚙️   │           │                      │              │
└──────┴───────────┴──────────────────────┴──────────────┘
```

Panels are resizable with min/max constraints.

## File Structure

```
src/mitoflow/ai/
├── __init__.py          # Package exports
├── models.py            # AIMessage, ToolCall, ToolDefinition, etc.
├── tools.py             # ToolRegistry, ToolContext, path safety
├── sessions.py          # LocalSessionStore (JSONL)
├── providers.py         # FakeProvider, OpenAIChatAdapter, AnthropicAdapter
├── runtime.py           # AgentRuntime (manager-agent loop)
├── runtime_deep.py      # DeepAgentRuntime (LangGraph sub-agents)
├── service.py           # AIService, build_provider, build_default_registry
├── service_deep.py      # DeepAgents create_deep_agent integration
├── prompts.py           # System prompts
├── domain_prompts.py    # Domain knowledge + workspace-aware rules
├── mitoflow_tools.py    # MitoFlow tool wrappers + workspace listing
├── knowledge.py         # Gene knowledge base
├── knowledge_tools.py   # Gene query tools (6)
├── skills_tools.py      # Skills registry tools (3)
├── web_tools.py         # Web search + GitHub lookup (3)
├── auth.py              # SQLite user DB + JWT
├── provider_presets.py  # 13 pre-configured LLM providers
├── notebook_export.py   # BioClaw-style .ipynb export
├── mcp/                 # Model Context Protocol
│   ├── references.json  # 21 structured references
│   ├── references_schema.py
│   ├── knowledge_base.py
│   ├── mcp_server.py
│   └── mcp_tools.py
├── wiki/                # LLM Wiki
│   ├── wiki_index.py
│   ├── wiki_tools.py
│   └── pages/           # 9 markdown knowledge pages
└── skills/              # ClawBio-style SKILL.md
    ├── loader.py
    ├── assembly/SKILL.md
    ├── annotation/SKILL.md
    ├── qc/SKILL.md
    ├── erc/SKILL.md
    ├── cms/SKILL.md
    └── comparative/SKILL.md

deploy/web/backend/
├── main.py              # FastAPI app (all endpoints)
└── chat_ui.py           # HTML5 chat interface (~680 lines)

tests/
├── test_ai_models.py    (4 tests)
├── test_ai_tools.py     (8 tests)
├── test_ai_sessions.py  (5 tests)
├── test_ai_providers.py (4 tests)
├── test_ai_runtime.py   (3 tests)
├── test_ai_service.py   (3 tests)
├── test_ai_cli.py       (2 tests)
├── test_ai_knowledge.py (7 tests)
├── test_ai_mcp.py       (9 tests)
├── test_ai_skills.py    (8 tests)
└── test_ai_wiki.py      (10 tests)
```

## Verification

```bash
# Run all AI tests
pytest tests/test_ai_*.py -v           # 63 tests

# Start server
conda run -n mitoflow-ai python3 -m uvicorn deploy.web.backend.main:app --host 0.0.0.0 --port 8002

# Access
http://10.2.145.42:8002/
```

## References

- DeepAgents (LangChain): LangGraph state machine + sub-agent delegation
- ClawBio: SKILL.md spec-first design pattern
- BioClaw: Session isolation + notebook export
- STELLA: Manager/Dev/Critic agent pattern
- ScienceClaw: Vue 3 chat UI design patterns
