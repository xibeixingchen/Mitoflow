# Phase 05: UI/UX 打磨 — Logo、登录、语言、模型、用户资料、工具页面

## 目标
修复 Vue SPA 上线后的关键体验问题，补全用户系统、模型选择、工具页面功能。

## 需求拆解

### A. Logo 与布局（1 文件）
- AppToolbar 最左上角添加 MitoFlow logo（当前只有汉堡菜单 ☰）

### B. 登录与数据修复（2 文件）
- **Bug**: 旧版 HTML UI 和 Vue SPA 使用不同的 localStorage key，导致已登录状态、聊天记录、API key 全部丢失
- **Bug**: 登录响应解析需确认 `backend/auth.py` 返回 `id(int)` 但前端 `User.id` 是 `string`
- **Fix**: 迁移旧 localStorage key（如有）到新的 `mitoflow_token` / `mitoflow_user`

### C. 语言切换 Bug（1 文件）
- **Bug**: `useLocale` composable 中 `useI18n()` 在事件处理器（非 setup 上下文）中调用返回 null，导致 `setLocale` 失败
- **Fix**: 在 composable 顶层（setup 上下文内）捕获 `locale` ref，再供函数使用

### D. 模型提供商重构（2 文件 + 联网搜索）
- **合并**: Kimi Code → Kimi（单一提供商，增加 plan 选项如 auto/8k/32k/128k）
- **自定义模型**: SettingsView 模型下拉框支持自定义输入（`<input>` + `<datalist>` 或 editable select）
- **最新模型**: 联网搜索各平台最新模型列表，更新 `constants/presets.ts`

### E. 用户资料扩展（3 文件：后端 + 前端）
- **后端**: `auth.py` users 表增加 `institution TEXT, role TEXT, degree TEXT`
- **后端**: 新增 `/api/auth/profile` (GET/POST) 和 `/api/auth/change-password`
- **前端**: SettingsView 增加用户信息面板（单位、工作角色、学历、修改密码）
- **前端**: AuthCard 注册表单增加单位、角色、学历字段
- **前端**: 密码输入框增加显示/隐藏切换

### F. 工具页面功能（3 文件）
- **ModuleGrid**: 每个卡片改为三个操作按钮：AI / 手动 / 结果
- **AI 按钮**: 路由到 `/chat`，自动将模块 prompt 填入输入框并发送
- **手动按钮**: 路由到新页面 `/tools/:id/manual`，包含参数表单 + 运行按钮 + 输出区域
- **结果按钮**: 路由到 `/results`

## 执行顺序

| 顺序 | 任务 | 预估 | 依赖 |
|------|------|------|------|
| 1 | C. 修复语言切换 bug | 5 min | 无 |
| 2 | A. Logo 放左上角 | 10 min | 无 |
| 3 | B. 登录数据修复 | 15 min | 无 |
| 4 | D. 联网搜最新模型 + 重构 presets | 20 min | 无 |
| 5 | D. 模型自定义输入 + Kimi 合并 | 15 min | 4 |
| 6 | E. 后端用户表扩展 + API | 20 min | 无 |
| 7 | E. 前端用户资料面板 | 25 min | 6 |
| 8 | F. 工具页面三按钮 + 路由 | 20 min | 无 |
| 9 | F. 手动模块页面 | 25 min | 8 |
| 10 | 构建验证 + 联调 | 15 min | 全部 |

## 修改文件清单

### 前端（~10 文件）
- `src/composables/useLocale.ts` — 修复 setup 上下文
- `src/components/layout/AppToolbar.vue` — 加 logo
- `src/stores/auth.ts` — 登录响应解析 + 旧数据迁移
- `src/constants/presets.ts` — 更新模型列表
- `src/views/SettingsView.vue` — 自定义模型输入 + 用户资料
- `src/components/auth/AuthCard.vue` — 注册字段扩展 + 密码显隐
- `src/components/modules/ModuleGrid.vue` — 三按钮卡片
- `src/views/ToolsView.vue` — 布局调整
- `src/views/ModuleManualView.vue` — 新页面（手动模式）
- `src/router/index.ts` — 新增 `/tools/:id/manual` 路由

### 后端（1 文件）
- `src/mitoflow/ai/auth.py` — 用户表扩展 + 新 API
- `deploy/web/backend/main.py` — 新增 `/api/auth/profile`, `/api/auth/change-password`

## 验证标准
1. 语言切换中英文双向正常，刷新保持
2. Logo 显示在左上角，点击可回首页
3. 旧版用户登录正常，数据不丢失
4. 模型下拉支持自定义输入，Kimi 只有一个提供商选项
5. 用户可修改资料、修改密码
6. 工具卡片三个按钮，AI 跳转 chat 并自动输入，手动跳转参数页
