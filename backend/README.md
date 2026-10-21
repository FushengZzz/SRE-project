# 后端（Backend）· 智能体动态记忆管理

M4 最小链路：LoCoMo 导入 → 结构化记忆构建（LLM / mock）→ 持久化与 JSON 导出 →
问题驱动检索 → 动态关系判定 → 有效性解析 → 回答生成与证据引用。

技术选型：Python 3.11+ / FastAPI + uvicorn / Pydantic v2 / SQLite / TF-IDF（M4 版）/
OpenAI 兼容 LLM（内置 mock provider，无 Key 可全链路运行）。

---

## 1. 环境与安装

```powershell
cd backend
pip install -r requirements.txt
```

Python 3.11+（开发环境为 3.13）。无需 GPU 与外部数据库。

## 2. 配置

```powershell
copy .env.example .env
```

关键项：

| 配置 | 说明 |
|---|---|
| `LLM_PROVIDER` | `mock`（默认，无需 Key，确定性规则实现）/ `openai`（OpenAI 兼容 API） |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 仅 `openai` 模式需要；兼容 GLM / DeepSeek / Qwen / ollama 等 |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | 有限超时与重试（NFR-03） |
| `RELATION_MODE` | `rules`（M4 默认）/ `llm`（LLM 判定，失败自动回退 rules） |
| `DEV_CONVERSATIONS` / `TEST_CONVERSATIONS` | 6 段对话划分名单（官方确认前的占位配置，SRS 3.1） |

API Key 仅由服务端从 `.env` 读取，不写入仓库 / 日志 / 响应（NFR-05）。
`LLM_PROVIDER=openai` 但未配置 Key 时启动即报错提示，不宣称完整运行（NFR-01）。

## 3. 数据导入与构建（UC-01）

命令行（在 `backend/` 下）：

```powershell
python scripts/import_data.py --file ../data/raw/locomo10.json
python scripts/build_memories.py --conversation conv-26   # 或 --all
```

或经 API（见下表）。重复导入同一对话会被跳过，不产生重复记录（FR-01）；
构建重试不重复写入已完成记忆（FR-03）。

## 4. 启动 Web 服务

```powershell
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

交互式文档：`http://127.0.0.1:8000/docs`

## 5. API 一览（SRS 7.1 → REST）

| 操作 | 方法与路径 | 说明 |
|---|---|---|
| 健康检查 | `GET /api/health` | 服务与 provider 状态 |
| 对话列表 | `GET /api/conversations` | split / 会话数 / 记忆数 |
| 导入 | `POST /api/import` | body: `{file_path, dataset_version?, dev_conversations?, test_conversations?}` |
| 构建（任务） | `POST /api/build` | body: `{conversation_id, force?}` → 后台任务 |
| 任务状态 | `GET /api/build/{task_id}` | 阶段 / 进度 / 成功失败数 / 错误摘要（FR-03） |
| 记忆列表 | `GET /api/memories?conversation_id=…&entity=…&keyword=…&page=1&page_size=20` | 筛选分页（FR-05） |
| 记忆详情 | `GET /api/memories/{memory_id}` | SRS 3.2 Memory 契约 |
| 证据回溯 | `GET /api/memories/{memory_id}/evidence` | 全部来源轮次原文（FR-06） |
| 原始轮次 | `GET /api/turns/{conversation_id}/{turn_id}` | 单轮次定位（turn_id 如 `D19:1`） |
| 导出 | `POST /api/export` | body: `{conversation_id?}`；JSON 附件下载（FR-04） |
| 问答 | `POST /api/query` | body: `{conversation_id, question, as_of?, top_k?}` → QueryResult（UC-03） |
| 查询结果 | `GET /api/query/{query_id}` | 历史查询结果回查 |
| 批量评测 | `POST /api/eval/run` | **501 占位**，Phase 2 提供（FR-13） |

错误结构统一为 `{error: {code, message, request_id}}`；`validation_error` / `not_found` /
`model_unavailable` / `timeout` 可区分（SRS 7.1）。

## 6. 端到端演示流程（UC-02 / UC-03）

1. `POST /api/import` 导入 `data/raw/locomo10.json`（或用 CLI）；
2. `POST /api/build` 构建（mock 或真实 LLM）；
3. `GET /api/conversations` → 选择对话（UC-02：浏览）；
4. `GET /api/memories?conversation_id=conv-26&keyword=adoption` 筛选；
5. `GET /api/memories/{id}/evidence` 查看原始轮次证据；
6. `POST /api/query`：

```json
{"conversation_id": "conv-30", "question": "Where does Gina work now?", "top_k": 5}
```

返回候选及分数、关系（RETAIN/UPDATE/SUPERSEDE/CONFLICT，旧→新方向）、逐条有效性
（effective/historical/conflict/uncertain/irrelevant + 理由）、有效/冲突集合、答案与引用、
实际截止时间与运行配置；证据不足 → `insufficient_evidence`，存在未决冲突 →
`unresolved_conflict`（FR-11）。

## 7. M4 范围与设计要点

- **时间语义（BR-08/09/10）**：默认截止 = 对话"可用历史末端"（最后一个**有轮次**会话
  的时间，LoCoMo 中仅有日期无轮次的未来会话不计入）；显式 `as_of` 过滤晚于截止的来源；
  事件时间无法解析时保留原文与 null，不补齐、不以记录时间伪装。
- **数据隔离（SRS 3.1）**：gold（qa 答案/证据、observation、event_summary）只入
  `gold_qa` 表供评测，抽取 / 检索 / 推理代码路径不读取；observation 等标注不导入。
- **幂等构建（FR-03）**：memory_id 由内容 + 来源哈希决定（内容寻址）+
  会话级完成标记，重试零重复写入。
- **检索质量、LLM 提示词调优、批量评测** 属 Phase 2（M5 前），本里程碑聚焦链路正确性。
- 测试：`backend/tests`（pytest 覆盖 AT-01/02/05/07/08 级用例 + mock 全链路冒烟）。

```powershell
cd backend
python -m pytest tests -q
```
