"""MitoFlow AI — Plant Mitochondrial Genomics Platform.
Inspired by ScienceClaw's professional chat UI design.
"""

from __future__ import annotations
import os, json, time, requests, streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8002")

# ── Provider presets with icons ───────────────────────────────────────
PRESETS = [
    {"key": "deepseek",      "name": "DeepSeek",           "icon": "🦈", "proto": "openai",    "base": "https://api.deepseek.com/v1",                       "models": ["deepseek-chat","deepseek-reasoner"],                                "desc": "高性价比推理"},
    {"key": "deepseek_code", "name": "DeepSeek Code (Claude协议)","icon":"💻","proto":"anthropic","base":"https://api.deepseek.com/anthropic",          "models": ["deepseek-v4-pro","deepseek-v4-flash"],                             "desc": "DeepSeek Anthropic 兼容"},
    {"key": "zhipu",         "name": "GLM (智谱)",           "icon": "🧠", "proto": "openai",    "base": "https://open.bigmodel.cn/api/paas/v4",               "models": ["glm-4-plus","glm-4-flash"],                                         "desc": "国产中文理解"},
    {"key": "moonshot",      "name": "Kimi (月之暗面)",        "icon": "🌙", "proto": "openai",    "base": "https://api.moonshot.cn/v1",                         "models": ["moonshot-v1-8k","moonshot-v1-32k"],                                "desc": "长上下文"},
    {"key": "kimicode",      "name": "Kimi Code",            "icon": "🔧", "proto": "anthropic", "base": "https://api.kimi.com/coding/",                       "models": ["K2.6"],                                                            "desc": "Coding 专用 Anthropic 协议"},
    {"key": "qwen",          "name": "Qwen (通义千问)",        "icon": "☁️", "proto": "openai",    "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",  "models": ["qwen-plus","qwen-max"],                                            "desc": "阿里多语言"},
    {"key": "baichuan",      "name": "Baichuan (百川)",       "icon": "🌊", "proto": "openai",    "base": "https://api.baichuan-ai.com/v1",                     "models": ["Baichuan4","Baichuan3-Turbo"],                                     "desc": "中文推理"},
    {"key": "openai",        "name": "OpenAI",               "icon": "⚡", "proto": "openai",    "base": "https://api.openai.com/v1",                          "models": ["gpt-4o","gpt-4o-mini"],                                            "desc": "综合能力强"},
    {"key": "claude",        "name": "Claude (Anthropic)",   "icon": "🔮", "proto": "anthropic", "base": "",                                                  "models": ["claude-sonnet-4-20250514","claude-haiku-4-5-20251001"],            "desc": "最强推理"},
    {"key": "openrouter",    "name": "OpenRouter",           "icon": "🌐", "proto": "openai",    "base": "https://openrouter.ai/api/v1",                       "models": ["deepseek/deepseek-chat","anthropic/claude-sonnet-4"],              "desc": "200+ 模型网关"},
    {"key": "ollama",        "name": "Ollama (本地)",          "icon": "🏠", "proto": "openai",    "base": "http://localhost:11434/v1",                           "models": ["llama3","qwen2.5"],                                                "desc": "本地离线"},
    {"key": "custom",        "name": "Custom / vLLM",        "icon": "⚙️", "proto": "openai",    "base": "",                                                  "models": [""],                                                                "desc": "任意兼容端点"},
]

st.set_page_config(page_title="MitoFlow AI", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

# ── CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, .stDeployButton { display: none; }
.chat-container { max-width: 880px; margin: 0 auto; }

/* Welcome */
.welcome-title { font-size: 2rem; font-weight: 700; text-align: center; margin: 1.5rem 0 0.3rem; }
.welcome-sub { text-align: center; color: #888; margin-bottom: 1rem; font-size: 0.9rem; }
.skill-chips { display: flex; gap: 0.4rem; flex-wrap: wrap; justify-content: center; margin: 0.8rem 0 1.5rem; }

/* Tool cards */
.tool-card { background: #f5f7fa; border-radius: 8px; padding: 0.5rem 1rem; margin: 0.3rem 0; font-size: 0.82rem; border-left: 3px solid #4A90D9; }

/* Sidebar */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #f8fafb 0%, #f0f4f8 100%); }
.sidebar-header { font-size: 1.15rem; font-weight: 700; margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.4rem; }
.sidebar-sub { font-size: 0.78rem; color: #999; margin-bottom: 0.8rem; }

/* Model card */
.model-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; }
.model-card .name { font-weight: 600; font-size: 0.9rem; }
.model-card .desc { font-size: 0.75rem; color: #888; }

/* Chat messages */
[data-testid="stChatMessage"] { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Session State ────────────────────────────────────────────────────
for k, v in {"session_id": None, "messages": [], "lang": "en"}.items():
    if k not in st.session_state: st.session_state[k] = v

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-header">🧬 MitoFlow AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Plant Mitochondrial Genomics Platform</div>', unsafe_allow_html=True)

    lang = st.toggle("中文", value=st.session_state.lang == "zh")
    st.session_state.lang = "zh" if lang else "en"
    L = st.session_state.lang

    T = {
        "en": {
            "provider": "Provider", "model": "Model", "api_key": "API Key",
            "api_key_help": "Leave empty to use environment variable", "base_url": "Endpoint",
            "new_chat": "New Chat", "placeholder": "Ask any question about plant mitochondrial genomics...",
            "thinking": "Analyzing...",
            "error_api": "Cannot connect to backend API.",
            "welcome_title": "Plant Mitochondrial Genomics AI",
            "welcome_sub": "Multi-agent platform — gene annotation, QC, comparative genomics, ERC, CMS, phylogenetics, and more.",
            "suggestions": [
                "What does cox1 encode?",
                "How does RNA editing work?",
                "What is cytoplasmic male sterility?",
                "List organelle assembly tools",
                "Which genes are trans-spliced?",
                "Explain ERC coevolution analysis",
            ],
            "api_ready": "Backend Connected", "api_down": "Backend Offline",
            "session": "Session", "tool_calls": "Tool Calls",
            "upload_fasta": "Upload FASTA", "sample_name": "Sample Name",
            "threads": "Threads", "start_btn": "Start Annotation",
            "task_id": "Task", "annotation": "Run Annotation",
            "mitoflow_modules": "MitoFlow Modules",
        },
        "zh": {
            "provider": "模型提供商", "model": "模型选择", "api_key": "API 密钥",
            "api_key_help": "留空使用环境变量", "base_url": "接口地址",
            "new_chat": "新对话", "placeholder": "询问植物线粒体基因组学的问题...",
            "thinking": "思考分析中...",
            "error_api": "无法连接后端服务",
            "welcome_title": "植物线粒体基因组学 AI 平台",
            "welcome_sub": "多智能体平台 — 基因注释、质控、比较基因组、ERC 协进化、CMS 检测、系统发育。",
            "suggestions": [
                "cox1 基因编码什么？",
                "RNA 编辑如何影响基因注释？",
                "什么是细胞质雄性不育（CMS）？",
                "列出细胞器基因组组装工具",
                "哪些基因需要反式剪接？",
                "解释 ERC 协进化分析流程",
            ],
            "api_ready": "后端已连接", "api_down": "后端离线",
            "session": "会话", "tool_calls": "工具调用",
            "upload_fasta": "上传 FASTA 文件", "sample_name": "样本名称",
            "threads": "线程数", "start_btn": "开始注释",
            "task_id": "任务", "annotation": "运行注释",
            "mitoflow_modules": "MitoFlow 模块",
        },
    }[L]

    st.divider()

    # ── Provider selection (ScienceClaw ModelSettings style) ──
    st.caption(f"🔌 {T['provider']}")
    preset_idx = st.selectbox(
        T["provider"], range(len(PRESETS)),
        format_func=lambda i: f"{PRESETS[i]['icon']} {PRESETS[i]['name']}",
        label_visibility="collapsed",
    )
    preset = PRESETS[preset_idx]
    st.caption(f"_{preset['desc']}_")

    model = st.selectbox(T["model"], preset["models"] if preset["models"][0] else [""],
                         label_visibility="collapsed")

    with st.expander("🔑 API Settings"):
        api_key = st.text_input(T["api_key"], type="password", placeholder=T["api_key_help"])
        base_url = st.text_input(T["base_url"], value=preset["base"],
                                 disabled=(preset["key"] not in ("custom",)))

    st.divider()

    # ── Actions ──
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"✨ {T['new_chat']}", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()
    with c2:
        if st.session_state.session_id:
            st.success(f"`{st.session_state.session_id[:8]}...`")

    st.divider()

    # ── API Status ──
    try:
        resp = requests.get(f"{API_URL}/api/health", timeout=3)
        st.success(f"🟢 {T['api_ready']}") if resp.status_code == 200 else st.error(f"🔴 {T['api_down']}")
    except Exception:
        st.error(f"🔴 {T['api_down']}")

    # ── Annotation & Modules ──
    st.divider()
    with st.expander(f"🔧 {T['annotation']}"):
        uploaded_file = st.file_uploader(T["upload_fasta"], type=["fasta", "fa", "fas", "fna"])
        sample_name = st.text_input(T["sample_name"], "MyMito")
        threads = st.slider(T["threads"], 1, 8, 4)
        if uploaded_file and st.button(f"🚀 {T['start_btn']}", use_container_width=True):
            with st.spinner("Uploading..."):
                files = {"file": uploaded_file}
                data = {"name": sample_name, "threads": threads,
                        "skip_trna": False, "skip_rrna": False, "skip_qc": False}
                r = requests.post(f"{API_URL}/api/annotate", files=files, data=data, timeout=30)
                if r.status_code == 200:
                    st.success(f"{T['task_id']}: `{r.json()['task_id'][:8]}...`")

# ── Main Chat ────────────────────────────────────────────────────────
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown(f'<div class="welcome-title">🧬 {T["welcome_title"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="welcome-sub">{T["welcome_sub"]}</div>', unsafe_allow_html=True)
    # Suggestion chips (ScienceClaw SuggestedQuestions style)
    st.markdown('<div class="skill-chips">', unsafe_allow_html=True)
    cols = st.columns(len(T["suggestions"]))
    for i, s in enumerate(T["suggestions"]):
        with cols[i]:
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": s})
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools"):
            with st.expander(T["tool_calls"]):
                for tr in msg["tools"]:
                    st.markdown(f'<div class="tool-card"><strong>{tr["name"]}</strong><br>{tr["content"][:300]}</div>',
                                unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input(T["placeholder"]):
    if not st.session_state.session_id:
        try:
            r = requests.post(f"{API_URL}/api/ai/sessions", timeout=10)
            if r.status_code == 200:
                st.session_state.session_id = r.json()["session_id"]
        except Exception:
            st.error(T["error_api"]); st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(T["thinking"]):
            try:
                payload = {"session_id": st.session_state.session_id, "message": prompt,
                           "provider": preset["proto"], "model": model}
                if api_key: payload["api_key"] = api_key
                if base_url: payload["base_url"] = base_url

                r = requests.post(f"{API_URL}/api/ai/chat", json=payload, timeout=180)
                if r.status_code == 200:
                    result = r.json()
                    st.markdown(result["final_text"])
                    tools = []
                    if result.get("tool_results"):
                        with st.expander(T["tool_calls"]):
                            for tr in result["tool_results"]:
                                st.markdown(f'<div class="tool-card"><strong>{tr["name"]}</strong><br>{tr["content"][:300]}</div>',
                                            unsafe_allow_html=True)
                                tools.append({"name": tr["name"], "content": tr["content"]})
                    st.session_state.messages.append({
                        "role": "assistant", "content": result["final_text"], "tools": tools})
                else:
                    st.error(f"Error {r.status_code}: {r.text[:200]}")
            except Exception as e:
                st.error(str(e))

st.markdown('</div>', unsafe_allow_html=True)
