# 前端（Frontend）· 智能体动态记忆管理

M4 演示前端：在浏览器中查看结构化 Memory、回溯原始证据，并展示「检索候选 → 关系判定 → 有效性解析 → 回答」的完整链路。

技术栈：Vite + React 18 + TypeScript + Ant Design 5。

---

## 1. 启动方式

### 方式 A：前后端分开（开发选择）

```powershell
# 终端 1：后端
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2：前端
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173/`。Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`，不需要额外配置 CORS。

### 方式 B：构建后由 FastAPI 单进程托管

```powershell
cd frontend
npm run build

cd ../backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/`。`backend/app/main.py` 会检测 `frontend/dist` 并挂载静态文件；API 仍在 `/api/*`。

---

## 2. 准备演示数据

前端暂未实现导入数据功能，数据需要先由后端导入并构建。演示可以使用两段开发对话：

```powershell
cd backend
python scripts/make_demo_subset.py
python scripts/import_data.py --file data/demo_locomo.json --version demo-2conv --dev conv-26,conv-30
python scripts/build_memories.py --conversation conv-26
python scripts/build_memories.py --conversation conv-30

# 可选：合成 CONFLICT 受控用例（明确标记为合成，不进入真实评测）
python scripts/import_data.py --file tests/fixtures/synthetic_conflict.json --version synthetic
python scripts/build_memories.py --conversation synthetic-conflict-01
```

默认 `LLM_PROVIDER=mock`，无需 API Key 即可跑通全链路。接入 DeepSeek 时在 `backend/.env` 配置 `LLM_PROVIDER=openai`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

---

## 3. 页面与交互

### 记忆浏览

- 按对话查看结构化 Memory，表格展示内容、实体、属性、会话时间、来源轮次和记录状态。
- 支持关键词搜索、实体筛选、记录状态筛选和分页。
- 点击任意行打开右侧抽屉：完整字段、时间表达、来源证据（说话人、轮次、会话原文）。
- 「导出 JSON」调用 `POST /api/export`，下载当前对话的结构化记忆。

### 问答与解析

- 顶部可切换对话；示例问题按对话提供，点击即可填入。
- 「高级选项」里可设置 `as_of` 时间截止和 `top_k`；`as_of` 留空表示使用对话历史末端。
- 结果区自上而下展示：
  - 最终回答、回答状态（已生成 / 证据不足 / 存在未决冲突）、引用证据和实际截止时间；
  - 候选数、有效数、历史数、冲突/不确定数；
  - 关系时间线：旧 → 新，四种关系标签（RETAIN / UPDATE / SUPERSEDE / CONFLICT）和判定理由；
  - 候选记忆表：相关度、逐条有效性、理由、来源；点击行查看证据；
  - 技术细节：运行配置和原始 QueryResult JSON。

### 推荐的演示顺序

1. conv-26「Caroline 的领养进度」→ 展示 UPDATE 链；
2. conv-26「职业变化 · 含替代」（`top_k=20`）→ 展示 SUPERSEDE 与多条 UPDATE；
3. conv-30「Gina 的工作变化（含替代）」（`as_of=2023-05-01`、`top_k=20`）→ 展示课程里的失业 → 开店 SUPERSEDE；
4. conv-26「历史视角 · 2023-08」→ 展示 `as_of` 时间截止；
5. 切到 `synthetic-conflict-01`（页面标记“合成 / 合成用例”）→「同一会话中的矛盾」→ 展示 CONFLICT、`unresolved_conflict` 和双方证据保留。

---

## 4. 目录结构

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts          # fetch 封装、错误结构解析、导出下载
│   │   └── types.ts           # 与后端 Pydantic 契约对应
│   ├── components/
│   │   ├── AppHeader.tsx
│   │   ├── ConversationBar.tsx
│   │   ├── MemoryBrowser.tsx  # 表格 + 筛选 + 分页
│   │   ├── MemoryDrawer.tsx   # 字段与证据抽屉
│   │   ├── MemoryDrawerContext.tsx
│   │   ├── QueryWorkbench.tsx # 问答页与结果概览
│   │   ├── RelationTimeline.tsx
│   │   └── CandidateTable.tsx
│   ├── App.tsx                # 对话选择与两个 Tab
│   ├── constants.ts           # 标签、颜色、示例问题
│   ├── hooks.ts
│   ├── main.tsx
│   ├── styles.css
│   └── utils.ts
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## 5. 设计约定

- **界面**：标题「智能体动态记忆管理」；技术名（Memory、UPDATE、effective 等）保留英文，便于和 SRS/后端契约对应。
- **表格 + 抽屉**：记忆浏览以数据密度优先，详情不跳页；问答结果中候选表同样点击行打开抽屉。
- **关系时间线 + 关系卡片**：不引入图数据库，符合 SRS「关系可用列表或时间线表达」。
- **错误与空状态**：后端不可达、对话未构建、筛选无结果、查询失败均有明确提示；错误信息包含后端 `code` 与 `request_id`。
- **不读取 gold**：前端只调用后端 API，不接触 `qa`、`event_summary`、`observation` 等评测标注。

---

## 6. 已知限制

- 当前后端默认使用 `mock` provider；回答文本是规则生成的证据摘录，关系判定也以规则为主。接入 DeepSeek 后回答和关系会更自然。
- 不含登录、多用户、移动端适配；演示按单用户桌面浏览器设计。
