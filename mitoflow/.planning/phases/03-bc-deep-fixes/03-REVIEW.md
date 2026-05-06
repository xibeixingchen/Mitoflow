---
phase: 03-bc-deep-fixes
reviewed: 2026-05-04T00:00:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - src/mitoflow/ai/runtime.py
  - src/mitoflow/ai/runtime_deep.py
  - src/mitoflow/ai/service.py
  - src/mitoflow/ai/service_deep.py
  - src/mitoflow/ai/models.py
findings:
  critical: 3
  warning: 6
  info: 4
  total: 13
status: issues_found
---

# Phase 03: MitoFlow AI 核心运行时代码深度审查报告

**Reviewed:** 2026-05-04
**Depth:** deep
**Files Reviewed:** 5
**Status:** issues_found

## Summary

本次深度审查覆盖了 MitoFlow AI multi-agent platform 的 5 个核心文件（runtime.py、runtime_deep.py、service.py、service_deep.py、models.py），并交叉分析了其依赖模块（sessions.py、tools.py、providers.py）。

**总体评估：** 代码架构清晰，但存在 **3 个 Critical 级别问题**，主要集中在：
1. **并发安全问题**：`LocalSessionStore` 的 JSONL 文件操作无任何并发控制，多线程/多进程环境下会导致数据损坏
2. **资源泄漏风险**：`OpenAIChatAdapter` 和 `AnthropicAdapter` 未正确管理 HTTP 客户端生命周期
3. **会话管理安全漏洞**：`session_id` 未经验证直接用于路径拼接，存在路径遍历风险

此外发现 6 个 Warning 和 4 个 Info 级别问题，详见下文。

---

## Critical Issues

### CR-01: LocalSessionStore 完全无并发控制，JSONL 文件操作存在竞态条件

**File:** `src/mitoflow/ai/sessions.py:66-69`, `src/mitoflow/ai/sessions.py:71-79`
**涉及文件:** `src/mitoflow/ai/runtime.py`, `src/mitoflow/ai/runtime_deep.py`
**Issue:**
`LocalSessionStore._append_model()` 和 `_load_models()` 方法在读写 JSONL 文件时没有任何锁机制。当多个线程（Web API 并发请求）或多个进程同时访问同一个 session 时：
- `append_message` 会导致 JSONL 文件内容交错损坏（两个线程同时写入，行数据被截断或混合）
- `load_messages` 可能在另一个线程写入时读取到不完整的 JSON 行，导致 `json.loads()` 抛出异常
- `create_session` 使用 `exist_ok=False` 但 `mkdir` 本身也不是原子操作，在并发下可能抛出 `FileExistsError`

**影响：** 在 Web 入口（EntryPoint.WEB）下，并发用户访问会导致会话数据损坏，AI 对话历史丢失或解析失败。

**Fix:**
```python
import fcntl
import threading

class LocalSessionStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_lock(self, session_id: str) -> threading.Lock:
        with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.Lock()
            return self._locks[session_id]

    def _append_model(self, path: Path, value: BaseModel) -> None:
        # 需要按 session_id 加锁
        session_id = path.parent.name
        with self._get_lock(session_id):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.write(json.dumps(value.model_dump(mode="json"), ensure_ascii=True) + "\n")
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
```

---

### CR-02: session_id 未经验证直接用于路径拼接，存在路径遍历攻击

**File:** `src/mitoflow/ai/sessions.py:57-58`
**涉及文件:** `src/mitoflow/ai/runtime.py:37`, `src/mitoflow/ai/runtime_deep.py:65`
**Issue:**
`LocalSessionStore._session_dir()` 直接将 `session_id` 拼接到 `self.root` 下：
```python
def _session_dir(self, session_id: str) -> Path:
    return self.root / session_id
```

如果攻击者传入 `session_id="../../etc/passwd"` 或 `session_id="../../../tmp/malicious"`，则：
- `artifact_dir()` 会在系统任意位置创建目录
- `append_message()` 会在系统任意位置写入文件
- `load_messages()` 会读取系统任意文件

虽然 `runtime.py:37` 和 `runtime_deep.py:65` 有 `session_exists()` 检查，但 `session_exists()` 本身也会解析这个恶意路径，且 `create_session()` 返回的 UUID 是安全的，**Web 层如果直接暴露 session_id 参数给外部用户**，攻击者可以构造恶意 session_id。

**Fix:**
```python
import re

_SESSION_ID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID_PATTERN.match(session_id):
        raise ValueError(f"Invalid session_id format: {session_id}")

def _session_dir(self, session_id: str) -> Path:
    _validate_session_id(session_id)
    return self.root / session_id
```

---

### CR-03: OpenAI/Anthropic HTTP 客户端未显式关闭，存在连接泄漏

**File:** `src/mitoflow/ai/providers.py:40-61`, `src/mitoflow/ai/providers.py:136-151`
**Issue:**
`OpenAIChatAdapter` 和 `AnthropicAdapter` 在 `__init__` 中创建 `OpenAI()` 和 `anthropic.Anthropic()` 客户端，但：
- 没有实现 `__enter__`/`__exit__` 或 `close()` 方法
- 没有在任何地方调用 `client.close()`
- `AIService` 在 `service.py:58-108` 中持有 provider 实例但从不释放

OpenAI Python SDK 的 `OpenAI` 类内部使用 `httpx.Client`，默认会保持连接池。在长期运行的服务（如 Web 服务）中，如果不关闭客户端，会导致：
- 文件描述符泄漏（每个客户端持有一个连接池）
- 内存泄漏（连接池中的连接对象累积）
- 在进程退出时可能产生 `ResourceWarning: unclosed transport`

**Fix:**
```python
class OpenAIChatAdapter:
    def __init__(...):
        # ... existing code ...
        self._client_owned = client is None

    def close(self) -> None:
        if self._client_owned and hasattr(self.client, 'close'):
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 在 AIService 中同样需要
class AIService:
    def close(self) -> None:
        if hasattr(self.provider, 'close'):
            self.provider.close()
```

---

## Warnings

### WR-01: AgentRuntime.run_turn 在 max_turns 达到后未记录 max_turns 事件

**File:** `src/mitoflow/ai/runtime.py:107-116`
**Issue:**
当循环达到 `max_turns` 上限时，代码直接返回 `RuntimeResult`，但没有向 `events` 列表和 session store 中追加一个 `max_turns_reached` 类型的事件。这导致：
- 调用方无法区分是正常结束还是因达到上限而截断
- 事件日志不完整，调试困难

**Fix:**
```python
final_text = "Stopped after reaching maximum tool turns without a final answer."
self.store.append_message(session_id, AIMessage(role="assistant", content=final_text))
event = RuntimeEvent(
    type="max_turns_reached",
    message=final_text,
    data={"max_turns": self.max_turns},
)
self.store.append_event(session_id, event)
events.append(event)
```

---

### WR-02: DeepAgentRuntime._plan_if_needed 的 plan 结果完全未使用

**File:** `src/mitoflow/ai/runtime_deep.py:138-168`
**Issue:**
`_plan_if_needed` 方法：
1. 构建 `plan_messages` 并调用 provider
2. 合并了 usage
3. **始终返回 `None`**

第 168 行 `return None` 是硬编码的，plan 的响应内容（`response.message.content`）被完全丢弃。这意味着：
- 调用 provider 进行规划是**纯粹的资源浪费**（消耗 token 但结果不用）
- 第 94 行 `data={"turn_index": turn_index, "plan": plan}` 中的 `plan` 永远是 `None`
- 方法文档说 "Returns list of plan steps if planning was done"，实际永远返回 `None`

**Fix:**
要么完全移除规划逻辑（避免浪费 token），要么实际使用规划结果：
```python
# 方案 A：移除无意义的规划调用（推荐）
def _plan_if_needed(...):
    return None  # 直接返回，不调用 provider

# 方案 B：实际使用规划结果
def _plan_if_needed(...):
    # ... existing logic ...
    self._merge_usage(usage, response.usage)
    plan_text = response.message.content
    # 解析 plan_text 为步骤列表并返回
    return plan_text.split('\n') if plan_text else None
```

---

### WR-03: ToolRegistry.execute 对 executor 返回值类型处理过于宽松

**File:** `src/mitoflow/ai/tools.py:84-107`
**Issue:**
`execute()` 方法捕获所有异常后返回 `ToolResult(ok=False, ...)`，这是正确的。但当 executor 返回 `dict` 时：
```python
content = str(raw.get("content", raw))
data = raw.get("data", raw)
if not isinstance(data, dict):
    data = {"value": data}
```

问题：
1. 如果 `raw` 是 `dict` 但没有 `"content"` 键，`raw.get("content", raw)` 会返回整个 dict，然后 `str(dict)` 产生不友好的用户消息
2. 如果 `raw` 不是 `dict`（比如 `list`、`str`），`raw.get(...)` 会抛出 `AttributeError`，但这个异常**不在 try/except 块内**，会导致整个 `execute()` 抛出未捕获异常

**Fix:**
```python
try:
    raw = self._executors[call.name](call.arguments, context)
except Exception as exc:
    return ToolResult(...)

if isinstance(raw, ToolResult):
    return raw

if isinstance(raw, dict):
    content = str(raw.get("content", ""))
    data = raw.get("data", raw) if raw.get("data") is not None else raw
    if not isinstance(data, dict):
        data = {"value": data}
else:
    content = str(raw)
    data = {"value": raw}

return ToolResult(...)
```

---

### WR-04: service_deep.py 中 ChatAnthropic/ChatOpenAI 参数传递可能泄露 API key 到日志

**File:** `src/mitoflow/ai/service_deep.py:46-62`
**Issue:**
```python
kwargs: Dict[str, Any] = {"model": model}
if resolved_key:
    kwargs["api_key"] = resolved_key
```

LangChain 的 `ChatOpenAI` 和 `ChatAnthropic` 在 `repr()` 或某些调试输出中可能会打印参数。虽然这不是直接的代码漏洞，但如果上层代码（如 FastAPI 的异常处理器、日志框架）打印了 LLM 对象或 kwargs，API key 会泄露到日志中。

更安全的做法是让 LangChain 从环境变量自行读取，而不是显式传递：

**Fix:**
```python
# 不要显式传递 api_key，让 LangChain 从环境变量读取
# 如果必须传递，确保 resolved_key 不会进入任何日志
kwargs: Dict[str, Any] = {"model": model}
# 移除显式的 api_key 传递，依赖环境变量
# LangChain 会自动读取 OPENAI_API_KEY / ANTHROPIC_API_KEY
```

---

### WR-05: runtime_deep.py 的 _run_sub_agent 与父会话共享 store 导致消息历史污染

**File:** `src/mitoflow/ai/runtime_deep.py:180-226`
**Issue:**
```python
sub_store = self.store  # Share store for message history
```

子代理与父会话**共享同一个 `LocalSessionStore` 实例**，但子代理使用不同的 session_id（`f"{parent_session}/sub"`）。这导致：
1. 子代理的消息被写入到父 session 目录下的子目录中（`session_id/sub`），但 `session_id/sub` 不是一个有效的 UUID，如果后续有代码假设 session_id 是 UUID 格式会出错
2. 子代理的调用结果通过 `ToolResult` 返回给父代理，但子代理的详细消息历史没有被清理，长期运行会累积大量子代理消息
3. 子代理的 `ToolContext` 使用 `session_id="{parent}/sub"`，如果工具内部使用 session_id 做文件路径，可能创建深层嵌套目录

**Fix:**
```python
# 使用隔离的子会话存储
sub_session_id = f"{parent_session}_sub_{uuid.uuid4().hex[:8]}"
sub_context = ToolContext(
    session_id=sub_session_id,
    workspace_root=context.workspace_root,
    output_root=context.output_root / "sub_agents" / sub_session_id,
    entry_point=context.entry_point,
)
```

---

### WR-06: providers.py 中 OpenAIChatAdapter.parse_response 的 tool_calls 参数解析容错不足

**File:** `src/mitoflow/ai/providers.py:111-116`
**Issue:**
```python
arguments_raw = call.function.arguments or "{}"
try:
    arguments = json.loads(arguments_raw)
except json.JSONDecodeError:
    arguments = {"_raw": arguments_raw}
```

当 LLM 返回的 arguments 不是合法 JSON 时，代码将其包装为 `{"_raw": ...}`。但 `call.function.arguments` 可能是 `None`（某些 API 实现），此时 `or "{}"` 能处理。更严重的问题是：
- 如果 `call.function` 本身为 `None`，`call.function.arguments` 会抛出 `AttributeError`
- 这个异常不在任何 try/except 块内，会导致整个请求失败

**Fix:**
```python
for call in getattr(message, "tool_calls", None) or []:
    func = getattr(call, "function", None)
    if func is None:
        continue
    arguments_raw = getattr(func, "arguments", None) or "{}"
    try:
        arguments = json.loads(arguments_raw)
    except json.JSONDecodeError:
        arguments = {"_raw": arguments_raw}
    calls.append(ToolCall(
        id=getattr(call, "id", ""),
        name=getattr(func, "name", ""),
        arguments=arguments,
    ))
```

---

## Info

### IN-01: _merge_usage 方法未处理非 int 的 usage 值（如 float 或字符串）

**File:** `src/mitoflow/ai/runtime.py:124-127`, `src/mitoflow/ai/runtime_deep.py:236-239`
**Issue:**
```python
def _merge_usage(self, target: Dict[str, int], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, int):
            target[key] = target.get(key, 0) + value
```

如果 provider 返回的 usage 中包含 `float` 类型的值（如某些 API 返回的 `prompt_tokens_details` 中的嵌套对象），这些值会被静默跳过。不会导致错误，但 usage 统计会不准确。

**Fix:**
```python
def _merge_usage(self, target: Dict[str, int], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, (int, float)):
            target[key] = target.get(key, 0) + int(value)
```

---

### IN-02: models.py 中 AIMessage 的 tool_calls 字段在 role="tool" 时无意义但未约束

**File:** `src/mitoflow/ai/models.py:37-44`
**Issue:**
`AIMessage` 模型允许任何 role 携带 `tool_calls`，但 `tool_calls` 只在 `role="assistant"` 时有意义。Pydantic 模型没有使用 `model_validator` 来约束这一点。

**Fix:**
```python
from pydantic import model_validator

class AIMessage(BaseModel):
    # ... existing fields ...

    @model_validator(mode='after')
    def validate_tool_calls(self):
        if self.tool_calls is not None and self.role != "assistant":
            raise ValueError("tool_calls can only be set for assistant messages")
        return self
```

---

### IN-03: runtime.py 和 runtime_deep.py 中的 _messages_with_system 存在重复 system message 风险

**File:** `src/mitoflow/ai/runtime.py:118-122`, `src/mitoflow/ai/runtime_deep.py:230-234`
**Issue:**
```python
def _messages_with_system(self, session_id: str) -> List[AIMessage]:
    messages = self.store.load_messages(session_id)
    if messages and messages[0].role == "system":
        return messages
    return [AIMessage(role="system", content=_DEFAULT_PROMPT)] + messages
```

如果 store 中的消息列表为空列表 `[]`，条件 `messages and messages[0].role == "system"` 为 False，会在每次调用时添加一个新的 system message。但如果消息列表的第一个是 user message（某些边界情况），也会在前面插入 system message，导致消息顺序变为 `[system, user, assistant, system, user...]` 的异常模式。

实际上由于 `run_turn` 总是先 append user message，messages 不会为空。但如果从外部直接操作 store（如手动插入消息），可能产生重复 system message。

**Fix:**
```python
def _messages_with_system(self, session_id: str) -> List[AIMessage]:
    messages = self.store.load_messages(session_id)
    if not messages:
        return [AIMessage(role="system", content=_DEFAULT_PROMPT)]
    if messages[0].role == "system":
        return messages
    # 如果第一个不是 system，检查是否已有 system 消息
    has_system = any(m.role == "system" for m in messages)
    if has_system:
        # 将 system message 移到开头
        system_msgs = [m for m in messages if m.role == "system"]
        other_msgs = [m for m in messages if m.role != "system"]
        return system_msgs + other_msgs
    return [AIMessage(role="system", content=_DEFAULT_PROMPT)] + messages
```

---

### IN-04: service_deep.py 中动态创建的 SchemaModel 缺少 __module__ 和 __qualname__，可能影响序列化

**File:** `src/mitoflow/ai/service_deep.py:101-106`
**Issue:**
```python
SchemaModel = type(
    f"{tool_name}_schema",
    (BaseModel,),
    {"__annotations__": annotations, **namespace},
)
```

使用 `type()` 动态创建的 Pydantic 模型缺少 `__module__` 属性。LangChain 的 `StructuredTool` 在某些序列化场景（如缓存、checkpoint）中可能需要模型的完整路径信息。虽然当前不影响功能，但可能在 LangGraph 的 checkpoint 序列化时产生警告。

**Fix:**
```python
SchemaModel = type(
    f"{tool_name}_schema",
    (BaseModel,),
    {"__annotations__": annotations, "__module__": "mitoflow.ai.service_deep", **namespace},
)
```

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
