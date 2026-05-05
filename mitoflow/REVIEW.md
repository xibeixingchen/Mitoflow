# MitoFlow 全栈代码审查报告

**审查日期**: 2026-05-05
**审查范围**: `deploy/web/backend/*.py`, `src/mitoflow/ai/*.py`, `deploy/web/frontend/src/**/*.vue`
**审查维度**: 安全漏洞、代码质量、性能、前端美观、可访问性

---

## 一、后端安全问题（🔴 P0 — 需立即修复）

### 1.1 路径遍历漏洞

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `main.py` | 709-715 | `download_result_file` 使用 `str(allowed) not in str(target)` 判断路径安全 | 可被 `/artifacts/../../etc/passwd` 绕过 |
| `main.py` | 805-811 | `download_file` 同样使用字符串包含判断 | 同上 |
| `main.py` | 814-824 | `delete_file` 同样使用字符串包含判断 | 同上，且可导致任意文件删除 |

**修复方案**: 统一使用 `pathlib.Path.relative_to()` 严格校验：
```python
try:
    target.relative_to(base)
except ValueError:
    raise HTTPException(403, "Access denied")
```

### 1.2 CORS 配置过于宽松

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `main.py` | 31 | `allow_origins=["*"]` 且 `allow_credentials=True` | 生产环境任意网站可跨域携带凭证访问 |

**修复方案**: 改为从环境变量读取白名单，默认只允许同源。

### 1.3 Token Secret 非持久化

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `auth.py` | 20 | `_SECRET = os.getenv(...) or hashlib.sha256(os.urandom(32)).hexdigest()` | 每次服务重启生成新 secret，所有用户 token 失效；无法水平扩展 |

**修复方案**: 强制从环境变量或文件读取固定 secret，启动时检查并警告。

### 1.4 密码哈希强度不足

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `auth.py` | 74 | PBKDF2-SHA256 迭代次数仅 100,000 | 远低于 OWASP 2023 建议（600,000） |

**修复方案**: 提升至 600,000 次；兼容旧密码（存储格式含迭代次数字段，或自动重哈希）。

### 1.5 SQL 注入风险

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `sessions_sqlite.py` | 228-249 | `search_messages` 直接拼接 `f"%{query}%"` 到 SQL | LIKE 注入 |

**修复方案**: 使用参数化查询 `LIKE ?` 传入参数。

### 1.6 文件上传无大小限制

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `main.py` | 763-781 | `upload_files` 未限制单文件大小 | 恶意上传超大文件导致磁盘耗尽 |

**修复方案**: 增加 `MAX_UPLOAD_SIZE`（如 500MB）并在写入前校验。

### 1.7 裸异常捕获掩盖错误

| 文件 | 行号 | 问题描述 | 风险 |
|------|------|----------|------|
| `main.py` | 665-676 | `get_session_messages` 裸 `except Exception: return {"messages": []}` | 数据库损坏/权限问题被静默掩盖 |
| `web_tools.py` | 82-88 | `_http_get` 裸 `except Exception: return None` | 网络故障不可观测 |

**修复方案**: 区分已知错误和未知错误，后者记录 `logger.warning` 或 `logger.error`。

---

## 二、后端代码质量问题（🟡 P1）

| 文件 | 行号 | 问题 | 建议 |
|------|------|------|------|
| `main.py` | 508-524 | `@app.on_event("startup")` 已被 FastAPI 弃用 | 迁移到 `lifespan` 上下文管理器 |
| `main.py` | 75 | `tasks = {}` 纯内存存储 | 使用 SQLite/Redis 持久化，支持重启恢复 |
| `main.py` | 556-557 | 模块级内联 `import json as _json` | 移至文件顶部标准导入 |
| `main.py` | 561-581 | `_load_sessions()` 在模块导入时执行 | 延迟到 lifespan 或首次请求时执行 |
| `main.py` | — | 单文件 858 行，职责过重 | 拆分为 `auth.py`, `ai.py`, `files.py` |
| `runtime_deep.py` | 184-189 | 直接访问 `registry._definitions` 私有属性 | 暴露公开 API `get_definition(name)` |
| `service.py` | 34-35 | 回退 API key 时可能把 OpenAI key 传给 Anthropic | 隔离各 provider 的 key 查找逻辑 |
| `skills_tools.py` | 160 | `Path(input_path)` 在 `input_path` 为 None 时崩溃 | 前置空值校验 |
| `mitoflow_tools.py` | 192-194 | `rglob` 后仅 `break` 取第一个匹配 | 明确处理多匹配场景或报错 |
| `chat_ui.py` | — | 遗留 HTML fallback 700+ 行 | 确认 Vue SPA 已完全替换后删除 |

---

## 三、前端安全问题（🔴 P0）

| 文件 | 行号 | 问题 | 风险 | 修复 |
|------|------|------|------|------|
| `ChatPanel.vue` | 35 | `v-html="renderMarkdown(msg.content)"` | XSS：LLM 返回恶意标签直接执行 | 使用 `DOMPurify` 净化 |
| `ChatPanel.vue` | 126-133 | `renderMarkdown` 手写解析，顺序易出错 | 代码块内 HTML 实体双重处理 | 改用 `marked` + `sanitize` |
| `SettingsView.vue` | 66-76 | API Key 明文存入 `localStorage` | 浏览器扩展/XSS 可窃取 | 改为 `sessionStorage` 并提示风险 |

---

## 四、前端美化建议（🟢 P2）

### 4.1 视觉层次

| 位置 | 现状 | 建议 |
|------|------|------|
| `ChatPanel.vue` 欢迎页 | 纯文字 | 添加渐变动画背景、浮动 SVG 插图、打字机标题 |
| `ChatPanel.vue` 消息气泡 | 扁平无阴影 | 细微阴影 `0 1px 3px rgba(0,0,0,0.08)`，用户消息渐变背景 |
| `ChatPanel.vue` 代码块 | 灰底无高亮 | 集成 `highlight.js` / `shiki` |
| `AppNav.vue` | emoji 无文字 | hover tooltip；active 项左侧光条 |
| `ChatInput.vue` | 静态按钮 | 发送按钮 hover `scale(1.05)` + 涟漪 |

### 4.2 交互体验

| 位置 | 现状 | 建议 |
|------|------|------|
| `MainLayout.vue` | drawer 切换生硬 | `cubic-bezier(0.4, 0, 0.2, 1)` 过渡 |
| `ChatPanel.vue` | 无 typing indicator | 三圆点跳动动画 |
| `ChatPanel.vue` | 无时间戳 | 消息角添加相对时间 |
| 全局 | 无骨架屏 | loading 时 shimmer 骨架 |
| 全局 | 无 Toast | 右上角通知系统 |
| `theme.css` | 仅 3 主题 | 增加 `nature`、`lab` 主题 |
| `index.html` | 无 PWA | 添加 `manifest.json`, `theme-color` |

### 4.3 移动端适配

| 位置 | 问题 | 建议 |
|------|------|------|
| `AppToolbar.vue` | 高度 44px 过小 | 移动端 52px |
| `AppNav.vue` | 左侧固定 58px | 移动端底部 tab bar |
| `MainLayout.vue` | 无响应式断点 | `@media (max-width: 768px)` 全屏化 |

### 4.4 可访问性（A11y）

| 问题 | 建议 |
|------|------|
| emoji 图标被屏幕阅读器朗读 | 添加 `aria-hidden="true"` + `aria-label` |
| 按钮无 `focus-visible` 样式 | 添加 `outline: 2px solid var(--accent)` |
| 无 `prefers-reduced-motion` | 添加媒体查询禁用动画 |
| 无 `skip-to-content` | 添加键盘跳转链接 |

---

## 五、性能问题（🟡 P1）

| 位置 | 问题 | 建议 |
|------|------|------|
| `main.py:686-702` | `rglob("*")` 遍历结果目录 | 限制递归深度或用数据库索引 |
| `ChatPanel.vue:126-133` | `renderMarkdown` 每次重新计算 | `computed` 缓存 |
| `chat_ui.py` | fallback HTML 内嵌所有资源 | 确认可删除后清理 |

---

## 六、修复优先级

```
P0 (立即)
├── 路径遍历漏洞 (main.py download/delete)
├── XSS 漏洞 (ChatPanel.vue v-html)
├── Token secret 持久化 (auth.py)
├── SQL 注入 (sessions_sqlite.py search_messages)
└── 文件上传大小限制 (main.py upload_files)

P1 (本周)
├── CORS 配置化
├── PBKDF2 迭代升级
├── FastAPI lifespan 迁移
├── 裸异常捕获修复
├── 添加 highlight.js + DOMPurify
└── 后端模块拆分

P2 (持续)
├── 骨架屏 + Toast + 动画
├── 移动端响应式
├── 可访问性改进
└── 删除 chat_ui.py 遗留代码
```

---

*报告生成完毕，下一步通过 GSD 流程逐个修复。*
