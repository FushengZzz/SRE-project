# 智能体动态记忆管理（Agent Dynamic Memory Management）

> **SRE小组** · Team ID：第六组 · Software Requirements Engineering 课程项目

基于 **LoCoMo** 长程多会话对话数据，开发一个支持**结构化记忆构建、查询驱动的动态状态解析、有效记忆检索与可视化**的 Web 应用。

---

## 项目要解决什么问题

长程、多轮对话中，用户的状态、计划和偏好会持续变化。普通向量检索虽然能召回与问题相关的历史信息，但会**同时召回「当前状态」和「已被后续信息更新掉的旧状态」**，从而导致错误回答或错误决策。

本项目的目标：不仅「召回相关历史」，还能判断哪些记忆已经过时、被替代或相互冲突，从而给出**基于当前有效记忆**的正确回答。

> 例子：`Gina 1月失业于 DoorDash` → `Gina 3月开了网店`。直接检索可能把过时职业状态当作当前事实；本系统应识别出 `SUPERSEDE`（替代）关系，以最新状态作答。

---

## 核心功能

### 必做
| 功能 | 说明 |
|---|---|
| 结构化记忆构建 | 从 LoCoMo 对话提取人物/事件/时间/状态，构建结构化 Memory（Memory ID · Content · Entity/Event · Timestamp · Source Session/Turn · State） |
| 统一 JSON 导出 | 所有 Memory 导出为统一 JSON 格式 |
| Web 记忆可视化 | 查看结构化记忆及其原始证据（会话/轮次） |
| 记忆检索 | 给定问题，从长期历史中检索相关 Memory |
| 状态关系判定 | 判断 RETAIN（保留）/ UPDATE（更新）/ SUPERSEDE（替代）/ CONFLICT（冲突） |
| 有效记忆解析 + 回答 | 确定当前有效 Memory，据此生成答案 |
| Web 状态解析展示 | 展示相关历史 Memory 及其关系与解析过程 |

### Bonus（可选）
- 更复杂的冲突消解与多版本保留
- Graph Memory / 多跳关系建模
- Memory 合并与压缩
- 自适应检索 / 复杂时间推理

---

## 数据来源

- **LoCoMo**（[github.com/snap-research/locomo](https://github.com/snap-research/locomo)）
- 从官方 10 段长对话中选 **6 段**：4 段 dev（开发调试）+ 2 段 test（最终评测），其余 4 段作扩展评测。
- 每段平均约 **588.2 轮、27.2 个会话、约 1.66 万 Token**，含 QA / 证据轮次 / 事件摘要标注。

---

## 评测指标

- 问题回答 **F1**
- 证据记忆检索 **Recall@K**
- 动态状态更新判断**准确率**

对照方法（Baseline）：**Full Text**（全文）、**Vector RAG**（检索相关记忆但不做状态关系判断）。

---

## 里程碑

| 里程碑 | 内容 | 占比 | 截止 |
|---|---|---|---|
| M1 | Team Workflow | 15% | 2026-10-10 |
| M2 | Project Proposal Presentation | 5% | 2026-10-10 |
| M3 | Software Requirements Specification | 15% | 2026-10-24 |
| M4 | Mid-term（设计/编码/测试） | 35% | 2026-10-24 |
| M5 | Final Presentation & Final Report | 30% | 2026-11-09 |

---

## 仓库结构

```
SRE-project/
├── README.md                          # 项目入口
└── docs/                              # 项目文档与课程材料
    ├── README.md                      # 文档索引
    ├── Project-Specification.pdf       # 课程项目说明
    ├── PROJECT-MILESTONE1-*.md / .pdf   # M1 工作流
    ├── PROJECT-MILESTONE2-*            # M2 愿景、范围与展示
    ├── PROJECT-MILESTONE3-第六组-SRE小组.md # M3 SRS
    └── process/                       # 会议、计划、工作和版本记录
```

文档入口见 [docs/README.md](docs/README.md)，需求规格见 [M3 SRS](docs/PROJECT-MILESTONE3-第六组-SRE小组.md)。

---

## 团队成员

| 角色 | 成员 |
|---|---|
| 组长 / 项目经理 | 王嘉淦（3240102143） |
| 需求 / 数据 + 算法 | 李胡诚（3240103356） |
| 后端开发 | 叶泽晨（3240102973） |
| 前端开发 | 马旻瑄（3240104241） |
| 测试 / DevOps + 评测 | 陈镇灏（3240102466） |

---

## 参考

1. Maharana A, et al. *Evaluating Very Long-Term Conversational Memory of LLM Agents.* ACL 2024.
2. DimMem — Dimensional Structuring for Efficient Long-Term Agent Memory.
3. MRAgent — Memory is Reconstructed, Not Retrieved.
