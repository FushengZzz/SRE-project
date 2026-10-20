# Milestone 1: Team Workflow

> 项目：智能体动态记忆管理-Agent Dynamic Memory Management
> 团队名：SRE小组　｜　Team ID：第六组　｜　提交日期：2026-10-10

---

## 1. Team Name

- **团队名**：SRE小组
- **项目名**：智能体动态记忆管理-Agent Dynamic Memory Management
- **简介**：基于 LoCoMo 长程多会话对话数据，构建一个支持结构化记忆构建、查询驱动的动态状态解析-RETAIN / UPDATE / SUPERSEDE / CONFLICT、有效记忆检索与可视化的 Web 应用。

---

## 2. Team Roles

团队共 5 人，角色与职责如下：

| 角色 | 成员 | 主要职责 |
|---|---|---|
| 组长 / 项目经理 | `王嘉淦 3240102143` | 统筹整体进度、主持周会、跟踪 weekly action items、负责对外提交与命名规范 |
| 需求 / 数据 + 算法 | `李胡诚 3240103356` | 需求分析与 SRS 撰写、LoCoMo 数据选段与预处理、记忆抽取规则设计 |
| 后端开发 | `叶泽晨 3240102973` | 记忆检索、状态关系判定（RETAIN/UPDATE/SUPERSEDE/CONFLICT）逻辑、Web API |
| 前端开发 | `马旻瑄 3240104241` | Web 端可视化：结构化记忆、原始证据、状态解析过程展示 |
| 测试 / DevOps + 评测 | `陈镇灏 3240102466` | 测试用例、CI、评测脚本：QA F1 / Recall@K / 状态判定准确率、对照实验与文档 |

> 会议记录人采用**轮值制**。

---

## 3. Project Management

### 3.1 沟通策略

- **每周例会**：每周 `周五` 晚 `20:00`，线上`微信群聊进行分工、协调工作内容`。
- **即时通讯**：`通过微信群聊同步工作进程`，日常问题及时同步，重大决策记录到会议纪要。
- **文档共享**：GitHub `docs/process/` 文件夹，记录会议纪要。

### 3.2 会议机制

- **安排人**：组长负责提前一天发布会议议程。
- **记录人**：成员轮值，会后 24 小时内将会议纪要提交到 GitHub `docs/process/meeting-minutes/`。
  - 会议时间 / 参与人 / 缺席人
  - 上周 action items 完成情况
  - 本周讨论要点与决策
  - 本周 action items

### 3.3 版本控制-基于GitHub，提交pr开发协作

- **仓库**：GitHub 仓库 https://github.com/w13126755377-ops/SRE-project ，已邀请全部 5 名成员。
- **权限**：文档与代码仅授权成员可更新。
- **提交方式**：成员直接提交到 `main`；重大变更需组内确认后提交pull request。
- **版本标签**：每个里程碑交付物定稿打 tag，如 `v1.0-m1`。
- **跟踪起点**：自第一个交付物初稿起开始跟踪提交记录。

### 3.4 过程文件夹（docs/process/）

```
docs/process/
├── meeting-minutes/      # 会议纪要
├── plans/                # 周计划与 action items 跟踪
├── worklog/              # 仓库工作记录（Git 提交日志）
└── versions/             # 版本记录（版本 tag 与 changelog）
```

### 3.5 推荐工具

- 版本控制：Git / GitHub
- 文档：Markdown
- 项目管理：Notion

---

## 4. Plan

总体时间线-根据课程时间安排各个milestone大致时间：

| 里程碑 | 占比 | 截止 | 迭代安排 | 关键行动项 |
|---|---|---|---|---|
| **M1** Team Workflow | 15% | 10/10 | 第 1 轮：初稿 第 2 轮：内部评审修订 | 定团队名/角色、建仓库、写 workflow 文档、整理 process 文件 |
| **M2** Project Proposal Presentation | 5% | 10/10 | 第 1 轮：大纲 → 第 2 轮：内容+评审 | Vision & Scope、Feature Roadmap、PPT 转 PDF |
| **M3** Software Requirements Specification | 15% | 10/24 | v0.1 初稿 → 评审 → v1.0 定稿 | 需求规格、用例、数据选段 |
| **M4** Mid-term presentation| 35% | 10/24 | 设计,编码,测试,修 bug,复测,开发大部分功能 | 记忆构建、检索、状态判定、Web、评测脚本 |
| **M5** Final Presentation & Final Report | 30% | 11/9 | 报告 v1 → 评审 → 终稿 | 完整评测、对照分析、报告、终版 PPT |

### 4.1 分阶段计划

**阶段一（10/8 – 10/10）：M1 + M2**
- 10/8：kickoff 会议，定团队名、角色分工、建 GitHub 仓库与 process 文件夹
- 10/9：M1 文档初稿 + M2 大纲；内部评审
- 10/10：修订定稿，导出 PDF，按时提交

**阶段二（10/11 – 10/24）：M3 + M4**
- 10/11–10/15：需求分析、SRS v0.1；确定 4 段 dev + 2 段 test 数据；设计记忆字段与 JSON 结构
- 10/16–10/20：编码-根据文档进行记忆构建、检索、状态判定、Web，第一轮测试
- 10/20：SRS 评审，修改为 v1.0
- 10/21–10/23：第二轮编码与测试，修 bug；整理测试结果与 M4 汇报
- 10/23：功能冻结，准备提交

**阶段三（10/25 – 11/9）：M5**
- 10/25–10/31：完整评测与对照实验，补充完毕所有要求功能；补充 Bonus 功能
- 11/1–11/5：Final Report v1 初稿 → 内部评审 → v1.0 定稿
- 11/6–11/8：终版 PPT、演练、导出 PDF
- 11/9：最终提交

### 4.2 迭代与 Buffer 说明

- 每阶段截止前预留 **1–2 天 buffer**，用于应对突发情况与评审返工。
- 所有文档在 GitHub 上从初稿开始提交，保证版本可追溯。

---

*本文档即 M1 交付文档初稿，随项目推进持续更新。*
