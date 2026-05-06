---
phase: 03-bc-deep-fixes
reviewed: 2026-05-04T14:35:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - deploy/web/backend/main.py
  - deploy/web/backend/chat_ui.py
  - src/mitoflow/ai/auth.py
  - src/mitoflow/cli.py
  - src/mitoflow/ai/sessions.py
findings:
  critical: 4
  warning: 6
  info: 3
  total: 13
status: issues_found
---

# Phase 03: MitoFlow AI Web Platform 安全代码审查报告

**审查时间:** 2026-05-04
**审查深度:** deep（跨文件分析 + 调用链追踪）
**审查文件数:** 5
**状态:** 发现严重安全问题

## 摘要

本次审查覆盖 MitoFlow AI multi-agent platform 的后端核心代码（FastAPI）、前端 UI（chat_ui.py）、认证模块（auth.py）、CLI 入口（cli.py）和会话存储（sessions.py）。发现了 **4 个严重（Critical）**、**6 个警告（Warning）** 和 **3 个信息（Info）** 级别的安全问题。

**核心风险：**
1. **JWT 密钥在每次导入时重新生成**，导致所有 token 在进程重启后失效，且多进程/多实例部署时 token 无法互认
2. **CORS 配置过于宽松**（`allow_origins=["*"]` + `allow_credentials=True`），存在 CSRF 和凭证泄露风险
3. **多处路径遍历漏洞**：`session_id` 和 `path` 参数未经净化直接拼接到文件路径
4. **文件上传缺乏类型校验**：仅检查后缀，不检查文件内容（Magic Number），可上传伪装文件
5. **API Key 以明文存储**在 SQLite 中，且通过 HTTP 明文传输到后端
6. **SQL 注入风险**：用户输入直接拼接到 SQL 查询中（虽然使用了参数化查询，但 `email.strip().lower()` 未做长度限制）
7. **前端 XSS 风险**：`md()` 函数渲染 Markdown 时未对链接做安全过滤

---

## 严重问题（Critical）

### CR-01: JWT 密钥每次导入重新生成，导致 Token 失效和多实例不兼容

**文件:** `src/mitoflow/ai/auth.py:19`
**问题:**
```python
_SECRET = os.getenv("MITOFLOW_SECRET", hashlib.sha256(os.urandom(32)).hexdigest())
```
当未设置 `MITOFLOW_SECRET` 环境变量时，`_SECRET` 在模块导入时通过 `os.urandom(32)` 随机生成。这意味着：
1. **每次 Python 进程重启后，所有已颁发的 token 全部失效**（因为密钥变了，HMAC 验证失败）
2. **多 worker/多实例部署时 token 无法互认**（每个进程有自己的密钥）
3. **密钥从未持久化**，用户登录后一旦服务器重启就需要重新登录

**修复:**
```python
import secrets

_SECRET = os.getenv("MITOFLOW_SECRET")
if not _SECRET:
    # 尝试从持久化文件读取，否则生成并保存
    secret_file = _DB_DIR / ".jwt_secret"
    if secret_file.exists():
        _SECRET = secret_file.read_text().strip()
    else:
        _SECRET = secrets.token_hex(32)
        secret_file.write_text(_SECRET)
        secret_file.chmod(0o600)  # 仅所有者可读
```

---

### CR-02: CORS 配置允许任意来源且携带凭证，存在 CSRF 和凭证泄露风险

**文件:** `deploy/web/backend/main.py:25-31`
**问题:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
`allow_origins=["*"]` 与 `allow_credentials=True` 的组合是 **OWASP 明确禁止**的配置。恶意网站可以通过跨域请求携带用户的登录凭证（cookie/token）访问 API。

**修复:**
```python
import os

allowed_origins = os.getenv("MITOFLOW_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

### CR-03: 文件下载路径遍历漏洞（results/download）

**文件:** `deploy/web/backend/main.py:508-518`
**问题:**
```python
@app.get("/api/ai/sessions/{session_id}/results/download")
async def download_result_file(session_id: str, path: str = Query(...)):
    target = (_P("./.mitoflow_ai_sessions") / session_id / "artifacts" / path).resolve()
    allowed = (_P("./.mitoflow_ai_sessions") / session_id / "artifacts").resolve()
    if str(allowed) not in str(target):
        raise HTTPException(status_code=403, detail="Access denied")
```
路径遍历检查使用 `str(allowed) not in str(target)` 存在绕过风险：
- Linux 下 `path="../../../etc/passwd"` 可能被阻止，但 `path=".."` 或符号链接可绕过
- 如果 `allowed` 路径包含在目标路径中作为子串（如 `allowed="/app/data"`，`target="/app/data_backup/file"`），会误判为合法
- **未对 `session_id` 做校验**：`session_id` 可以是任意字符串（如 `../data`），直接拼接到路径中

**修复:**
```python
import re
from pathlib import Path

# 校验 session_id 格式
if not re.match(r'^[a-f0-9-]{36}$', session_id):
    raise HTTPException(status_code=400, detail="Invalid session ID")

allowed = (Path("./.mitoflow_ai_sessions") / session_id / "artifacts").resolve()
target = (allowed / path).resolve()

try:
    target.relative_to(allowed)
except ValueError:
    raise HTTPException(status_code=403, detail="Access denied")

if not target.exists() or not target.is_file():
    raise HTTPException(status_code=404, detail="File not found")
```

---

### CR-04: 工作区文件操作存在路径遍历（upload/download/delete）

**文件:** `deploy/web/backend/main.py:566-584, 605-614, 617-627`
**问题:**
```python
session_dir = WORKSPACE_ROOT / session_id
# session_id 未经校验，可以是 "../../../tmp"
```
在 `upload_files`、`download_file`、`delete_file` 三个端点中，`session_id` 参数直接拼接到 `WORKSPACE_ROOT` 路径中。虽然 `download_file` 和 `delete_file` 使用了 `resolve()` 和字符串包含检查，但 `upload_files` 完全没有路径遍历防护。

**修复:**
```python
import re

def _validate_session_id(session_id: str) -> None:
    if not session_id or not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

@app.post("/api/files/upload")
async def upload_files(files: list[UploadFile] = File(...), session_id: str = Form("default")):
    _validate_session_id(session_id)
    session_dir = WORKSPACE_ROOT / session_id
    # 确保 session_dir 在 WORKSPACE_ROOT 下
    try:
        session_dir.resolve().relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid workspace path")
    session_dir.mkdir(parents=True, exist_ok=True)
    ...
```

---

## 警告（Warning）

### WR-01: API Key 明文存储和传输

**文件:** `src/mitoflow/ai/auth.py:167-175`, `deploy/web/backend/main.py:301-311`
**问题:**
1. `users` 表的 `api_key` 字段以 **明文** 存储用户 API Key
2. 前端通过 HTTP POST 将 API Key 明文传输到 `/api/auth/api-key` 端点
3. 如果数据库泄露，所有用户的第三方 API Key 直接暴露

**修复:**
```python
# 存储时加密（使用 Fernet 或至少 AES）
from cryptography.fernet import Fernet

# 初始化时从环境变量加载加密密钥
_ENCRYPTION_KEY = os.getenv("MITOFLOW_ENCRYPTION_KEY")
if _ENCRYPTION_KEY:
    _fernet = Fernet(_ENCRYPTION_KEY.encode())

def _encrypt_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    return _fernet.encrypt(api_key.encode()).decode()

def _decrypt_api_key(encrypted: str) -> str:
    if not encrypted:
        return ""
    return _fernet.decrypt(encrypted.encode()).decode()
```

---

### WR-02: 文件上传仅检查后缀，不验证文件内容（Magic Number）

**文件:** `deploy/web/backend/main.py:566-584`
**问题:**
```python
ext = Path(f.filename).suffix.lower()
if ext not in ALLOWED_EXTENSIONS_UPLOAD and not any(f.filename.endswith(x) for x in ['.tar.gz','.tar.bz2','.fq.gz','.fastq.gz']):
    errors.append(f"{f.filename}: unsupported type")
    continue
```
攻击者可以构造一个 `.fasta` 后缀的文件，实际内容是恶意脚本或二进制文件。系统会将其保存到服务器并可能在后续处理中执行。

**修复:**
```python
import magic

def validate_file_content(content: bytes, expected_ext: str) -> bool:
    """使用 python-magic 验证文件类型"""
    mime = magic.from_buffer(content, mime=True)
    allowed_mimes = {
        '.fasta': ['text/plain', 'application/fasta'],
        '.fa': ['text/plain', 'application/fasta'],
        '.gb': ['text/plain'],
        '.zip': ['application/zip'],
        '.png': ['image/png'],
    }
    return mime in allowed_mimes.get(expected_ext, [])
```

---

### WR-03: 前端 Markdown 渲染存在 XSS 漏洞

**文件:** `deploy/web/backend/chat_ui.py:465-468`
**问题:**
```javascript
function md(t){
  ...
  o=o.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
  ...
}
```
`md()` 函数将 Markdown 链接转换为 HTML `<a>` 标签时，未对 `href` 属性做过滤。如果 AI 返回的内容包含恶意链接：
```markdown
[click me](javascript:alert(document.cookie))
```
会被渲染为：
```html
<a href="javascript:alert(document.cookie)" target="_blank">click me</a>
```

**修复:**
```javascript
function md(t){
  ...
  o=o.replace(/\[([^\]]+)\]\(([^)]+)\)/g,function(match, text, url){
    // 只允许 http/https 链接
    if(!/^https?:\/\//i.test(url)){
      return '<a href="#" onclick="return false;">' + esc(text) + '</a>';
    }
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(text) + '</a>';
  });
  ...
}
```

---

### WR-04: 用户输入直接用于 SQL 查询，未做长度限制和特殊字符过滤

**文件:** `src/mitoflow/ai/auth.py:92-115`
**问题:**
```python
def register_user(email: str, username: str, password: str) -> Dict[str, Any]:
    db.execute(
        "INSERT INTO users (email, username, password_hash, created_at, last_login) VALUES (?, ?, ?, ?, ?)",
        (email.strip().lower(), username.strip(), ph, now, now),
    )
```
虽然使用了参数化查询防止 SQL 注入，但：
1. `email` 和 `username` 未做长度限制（可能导致 DoS 或存储溢出）
2. 未过滤控制字符（如换行符、NULL 字节）
3. `email.strip().lower()` 不是标准的 email 校验，可能接受 `"@."` 这样的无效输入

**修复:**
```python
import re
from email_validator import validate_email, EmailNotValidError

def register_user(email: str, username: str, password: str) -> Dict[str, Any]:
    # 长度限制
    if len(email) > 254 or len(username) > 64 or len(password) > 128:
        return {"error": "Input too long"}
    
    # 标准 email 校验
    try:
        valid = validate_email(email.strip(), check_deliverability=False)
        email = valid.email
    except EmailNotValidError:
        return {"error": "Invalid email address"}
    
    # Username 格式校验
    if not re.match(r'^[a-zA-Z0-9_-]{3,64}$', username.strip()):
        return {"error": "Username must be 3-64 alphanumeric characters"}
    
    ...
```

---

### WR-05: 任务删除端点未验证任务所有权

**文件:** `deploy/web/backend/main.py:233-250`
**问题:**
```python
@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    # 任何人知道 task_id 就可以删除任务
    del tasks[task_id]
```
`task_id` 是 UUID 格式，虽然难以猜测，但端点未验证调用者是否是任务的创建者。如果 task_id 泄露，任何人都可以删除他人任务。

**修复:**
```python
@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, authorization: str = Header(None)):
    # 验证用户身份
    user = _get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查任务所有权（需要在创建时记录 user_id）
    if tasks[task_id].get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your task")
    
    ...
```

---

### WR-06: `run_annotation_task` 中的异常处理导致任务状态不一致

**文件:** `deploy/web/backend/main.py:77-126`
**问题:**
```python
def run_annotation_task(task_id: str, input_path: Path, output_dir: Path, params: dict):
    try:
        ...
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = f"Error: {str(e)}"
        raise  # 重新抛出异常，但状态已更新
```
在 `except` 块中更新了 `tasks[task_id]` 的状态后又 `raise` 重新抛出异常。由于 FastAPI 的 `BackgroundTasks` 不会捕获后台任务的异常，这会导致：
1. 异常被静默吞掉（或记录到 stderr），但任务状态显示为 failed
2. 如果 `tasks[task_id]` 在异常处理期间被其他请求修改，可能出现竞态条件

**修复:**
```python
def run_annotation_task(task_id: str, input_path: Path, output_dir: Path, params: dict):
    try:
        ...
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}"
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = error_msg
        tasks[task_id]["error_traceback"] = traceback.format_exc()
        # 不要 re-raise，让后台任务正常结束
        # 如果需要日志，使用 logging
        logger.exception("Annotation task failed: %s", task_id)
```

---

## 信息（Info）

### IN-01: 密码最小长度 6 位过短，建议至少 8 位并增加复杂度要求

**文件:** `src/mitoflow/ai/auth.py:94-95`
**问题:**
```python
if len(password) < 6:
    return {"error": "Password must be at least 6 characters"}
```
6 位密码在现代计算能力下极易被暴力破解。

**修复:**
```python
import re

if len(password) < 8:
    return {"error": "Password must be at least 8 characters"}
if not re.search(r'[A-Z]', password):
    return {"error": "Password must contain at least one uppercase letter"}
if not re.search(r'[a-z]', password):
    return {"error": "Password must contain at least one lowercase letter"}
if not re.search(r'\d', password):
    return {"error": "Password must contain at least one digit"}
```

---

### IN-02: Token 过期时间 30 天过长，且未实现 Token 刷新机制

**文件:** `src/mitoflow/ai/auth.py:72`
**问题:**
```python
payload = json.dumps({"uid": user_id, "iat": int(time.time()), "exp": int(time.time()) + 86400 * 30})
```
30 天的 token 有效期过长，如果 token 泄露，攻击者有充足时间利用。建议缩短到 1-7 天，并实现 refresh token 机制。

**修复:**
```python
# Access token: 1 小时
# Refresh token: 7 天

def _make_token(user_id: int, token_type: str = "access") -> str:
    if token_type == "access":
        exp = int(time.time()) + 3600  # 1 hour
    else:
        exp = int(time.time()) + 86400 * 7  # 7 days
    payload = json.dumps({"uid": user_id, "type": token_type, "iat": int(time.time()), "exp": exp})
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + sig
```

---

### IN-03: `LocalSessionStore` 未对 `session_id` 做格式校验

**文件:** `src/mitoflow/ai/sessions.py:20-28`
**问题:**
```python
def create_session(self) -> str:
    session_id = str(uuid.uuid4())
    self._session_dir(session_id).mkdir(parents=True, exist_ok=False)
    ...
```
虽然 `create_session` 使用 `uuid.uuid4()` 生成安全的 session_id，但 `session_exists`、`append_message` 等公共方法接受任意字符串作为 `session_id`，可能被用于路径遍历攻击。

**修复:**
```python
import re
import uuid

class LocalSessionStore:
    def _validate_session_id(self, session_id: str) -> None:
        if not re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$', session_id):
            raise ValueError(f"Invalid session ID format: {session_id}")
    
    def session_exists(self, session_id: str) -> bool:
        self._validate_session_id(session_id)
        return self._session_dir(session_id).exists()
    
    def append_message(self, session_id: str, message: AIMessage) -> None:
        self._validate_session_id(session_id)
        ...
```

---

## 跨文件分析补充

### 调用链追踪：AI Chat 请求处理流程

```
main.py:521 /api/ai/chat
  -> _get_ai_service() [main.py:344]
    -> build_provider() [service.py:24]
      -> 用户可传入 api_key, base_url [main.py:327-328]
  -> svc.send_message() [service.py:88]
    -> AgentRuntime.run_turn() [runtime.py]
      -> ToolRegistry.execute() [tools.py:65]
        -> 工具执行器（如 run_annotation）
```

**风险点：**
1. `api_key` 和 `base_url` 从用户请求直接传入 `build_provider()`，未做校验。如果 `base_url` 指向内网地址（如 `http://localhost:22` 或 `http://169.254.169.254/`），可能导致 **SSRF（服务器端请求伪造）** 攻击。
2. `run_annotation` 工具接收 `input` 参数后直接作为文件路径使用，虽然 `ensure_under_root` 做了限制，但 `list_workspace_files` 和 `run_visualization` 中存在硬编码路径，未统一使用 `workspace_root`。

### 状态一致性风险

`_ai_sessions` 和 `_session_meta` 是全局内存字典（`main.py:318, 374`），在多 worker 部署（如 gunicorn）时，每个 worker 进程有自己的内存空间，导致：
1. 用户在一个 worker 创建的 session，在另一个 worker 可能不可见
2. `_save_sessions()` 和 `_load_sessions()` 虽然持久化到文件，但存在竞态条件（无文件锁）

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
