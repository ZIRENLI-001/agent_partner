# 多轮对话评测平台开发前设计

## 1. 定位

本平台面向“复杂指令下的多轮对话评测系统”比赛题目，目标是为后续平台开发提供稳定规格。

平台不是通用 LLM 评测平台，也不是模型训练系统；生产落地时它服务于外呼模型评测与质检，不直接执行真实外呼。它聚焦一个核心闭环：

```text
已有任务指令
  -> 指令解析
  -> 用户模拟场景生成
  -> 多轮对话评测
  -> 可解释量化报告
```

第一版采用“可扩展评测引擎 + 轻量 Web 向导式 Demo”的形态。底层模块按平台化方式设计，比赛阶段 Web 只承载核心评测闭环，但核心数据模型和执行引擎必须支持后续生产落地：多任务、多场景、多模型、批量运行、历史记录、回归评测和人工校准。

## 2. Web Demo 流程

Web Demo 采用多步骤向导式流程，便于比赛展示。

```text
Step 1 任务输入
  -> Step 2 指令解析
  -> Step 3 场景生成
  -> Step 4 对话评测
  -> Step 5 评测报告
```

### Step 1：任务输入

用户可以：

- 粘贴任务指令文本。
- 选择当前 Excel 样例中的飞毛腿任务。

页面目标是明确系统输入来自“已有任务指令”，对齐比赛要求。

### Step 2：指令解析

展示 `TaskSpec` 和 `RubricSpec` 的核心内容：

- 任务目标。
- 角色和目标用户。
- 开场白。
- 流程步骤。
- FAQ。
- 约束条件。
- 异常分支。
- 评分项。

页面目标是让评委看到系统如何把复杂指令拆成可执行评测规格。

### Step 3：场景生成

展示 5 到 10 个用户模拟场景。每个场景展示：

- 用户画像。
- 初始意图。
- 覆盖分支。
- 测试重点。

页面目标是证明用户模拟器不是随意聊天，而是围绕任务指令分支做覆盖测试。

### Step 4：对话评测

支持选择单个场景运行，也支持批量运行全部场景。

页面展示：

- 用户模拟器与待测模型的多轮对话。
- 当前轮次。
- 结束原因。
- 触发的分支。

页面目标是证明评测过程是多轮交互，而不是静态单轮打分。

### Step 5：评测报告

展示：

- 总分和维度分。
- 场景覆盖矩阵。
- 场景级通过/失败结果。
- 高风险项。
- 扣分证据链。
- 改进建议。
- Markdown 导出按钮。

页面目标是对应比赛要求中的“评测过程可解释，评测结果可量化”。

## 3. 后端模块

Web 层只负责触发和展示，核心逻辑放在评测引擎中。

| 模块 | 输入 | 输出 | 职责 |
| --- | --- | --- | --- |
| `InstructionParser` | 原始任务指令 | `TaskSpec` | 抽取角色、目标、流程、FAQ、约束、异常分支 |
| `RubricBuilder` | `TaskSpec` | `RubricSpec` | 生成评分项、权重、规则/语义判定方式 |
| `ScenarioGenerator` | `TaskSpec + RubricSpec` | `ScenarioSet` | 生成用户画像和测试分支 |
| `UserSimulator` | `Scenario + DialogueHistory` | 用户下一轮输入 | 动态模拟用户 |
| `DialogueRunner` | `Scenario + TargetModel` | `DialogueTrace` | 控制多轮对话和终止条件 |
| `RuleEvaluator` | `Trace + Rubric` | `RuleEvalResult` | 判断字数、禁词、必需信息、挂断等硬约束 |
| `JudgeEvaluator` | `Trace + Rubric + Scenario` | `JudgeEvalResult` | 判断任务完成、流程遵循、异常处理等语义项 |
| `ReportWriter` | 全部评测结果 | `Report` | 输出分数、证据链、建议 |

模块之间只通过 JSON 对象通信，避免把评测逻辑写死在 Web 页面中。

为保证生产可扩展性，后端模块需要遵守以下原则：

- 模块无状态优先：核心函数输入完整 JSON，输出完整 JSON。
- 运行状态外置：评测进度、trace、结果统一写入运行存储。
- 模型调用抽象：待测模型、用户模拟模型、Judge 模型通过统一 provider 接口接入。
- 评测规格版本化：`TaskSpec`、`RubricSpec`、`ScenarioSet` 都需要带版本号，便于回归评测。
- 场景库可复用：场景不是一次性生成物，后续可以沉淀为 `ScenarioSuite`。

## 4. 数据流

核心数据流：

```text
RawInstruction
  -> TaskSpec
  -> RubricSpec
  -> ScenarioSet
  -> DialogueTrace[]
  -> EvaluationResult[]
  -> Report
```

每次评测运行生成一个 `run_id`，相关文件落地到：

```text
runs/{run_id}/
  run_config.json
  task_spec.json
  rubric_spec.json
  scenarios.json
  traces.jsonl
  evaluation_results.json
  report.md
```

这样可以保证：

- 评测过程可复现。
- 报告证据可追溯。
- 后续支持历史记录、批量评测和回归测试。

生产落地时，文件存储可以平滑替换为数据库和对象存储：

- `Run`、`TaskSpec`、`ScenarioSuite`、`EvaluationResult` 存入关系型数据库。
- `DialogueTrace`、`Report`、原始输入文件存入对象存储或文档存储。
- Web 页面通过 `run_id` 查询运行状态和结果。

### 4.1 生产数据层抽象

平台后续生产化至少需要以下核心实体：

| 实体 | 说明 |
| --- | --- |
| `Project` | 一组评测任务集合，例如某业务线或某版本模型评测 |
| `TaskInstruction` | 原始任务指令和元信息 |
| `TaskSpecVersion` | 某次指令解析结果，支持版本化 |
| `RubricVersion` | 某次评分标准，支持版本化和人工修订 |
| `ScenarioSuite` | 针对某任务的一组测试场景 |
| `Run` | 一次评测运行，绑定模型、任务、场景和配置 |
| `DialogueTrace` | 运行产生的多轮对话轨迹 |
| `EvaluationResult` | 评测分数、证据和高风险项 |
| `Report` | 面向用户查看或导出的报告 |

比赛 MVP 可以用文件模拟这些实体，但代码结构需要保留这些边界。

## 5. 核心数据对象

### TaskSpec

表示任务指令的结构化结果。

关键字段：

- `task_id`
- `task_name`
- `role`
- `target_user`
- `task_goal`
- `opening_line`
- `required_steps`
- `constraints`
- `faq`
- `edge_cases`
- `forbidden_actions`

### RubricSpec

表示可评测项。

关键字段：

- `rubric_id`
- `items`
- `dimension`
- `criterion`
- `source`
- `check_type`
- `weight`
- `critical`

每个评分项必须有 `source`，用于追溯原始任务指令。

### Scenario

表示一条用户模拟场景。

关键字段：

- `scenario_id`
- `task_id`
- `user_profile`
- `coverage_targets`
- `initial_user_intent`
- `expected_test_focus`

### DialogueTrace

表示一条完整多轮对话轨迹。

关键字段：

- `trace_id`
- `task_id`
- `scenario_id`
- `turns`
- `termination_reason`

### EvaluationResult

表示评测结果。

关键字段：

- `trace_id`
- `total_score`
- `dimension_scores`
- `evidence`
- `critical_failures`

每条 evidence 必须包含：

- `rubric_item_id`
- `verdict`
- `source`
- `turn_ids`
- `reason`

### Project

生产平台用于组织多任务、多模型和多轮评测。

关键字段：

- `project_id`
- `name`
- `description`
- `created_at`
- `default_model_config`
- `default_judge_config`

MVP 可以不提供项目管理页面，但后端数据模型应允许未来引入。

### ScenarioSuite

表示一组可复用测试场景，不是单次运行的临时数据。

关键字段：

- `suite_id`
- `task_id`
- `rubric_version`
- `scenario_ids`
- `coverage_summary`
- `created_by`
- `source`

`source` 可标记为 `generated`、`manual`、`from_desensitized_data`。

### Run

表示一次评测执行。

关键字段：

- `run_id`
- `project_id`
- `task_id`
- `scenario_suite_id`
- `target_model_config`
- `judge_model_config`
- `status`
- `started_at`
- `finished_at`
- `error_summary`

## 6. MVP 范围

比赛 MVP 必须同时满足两类目标：

- 比赛演示目标：完整展示任务输入、用户模拟、多轮评测和报告生成。
- 准生产目标：一次运行必须覆盖一个任务下的多场景评测，结果可复查、可量化、可导出、可复现。

### 必做

1. 任务输入
   - 支持粘贴任务指令。
   - 支持读取当前 Excel 样例中的飞毛腿任务。

2. 指令解析
   - 生成 `TaskSpec`。
   - 生成 `RubricSpec`。
   - Web 页面展示任务目标、流程、约束、FAQ、异常分支。

3. 场景生成
   - 至少生成 5 个用户模拟场景。
   - 覆盖正常配合、不想配送、询问奖励、询问退出方式、不方便通话、超出职责范围问题。
   - 每个场景必须带 `coverage_targets`，报告中展示场景覆盖矩阵。

4. 多轮对话
   - 默认运行一个任务下的完整 `ScenarioSet`，而不是只运行单个场景。
   - 支持选择单个场景运行，用于调试和 Demo 控制等待时间。
   - 保存完整 `DialogueTrace`。
   - 单个场景失败时记录错误，不阻断整个 run 的其余场景。
   - 每次运行必须生成 `run_id` 和 `run_config.json`。

5. 自动评测
   - 至少实现 3 类规则评测：字数限制、必需信息、禁止承诺/越界回答。
   - 至少实现 1 类 Judge 语义评测：任务完成度、流程遵循或异常处理。
   - 规则评测和 Judge 评测结果统一汇总为 `EvaluationResult[]`。
   - 高风险项必须单独标记，不只体现在总分中。

6. 报告
   - 总分和维度分。
   - 场景覆盖矩阵。
   - 全部场景的通过/失败/部分通过状态。
   - 扣分证据链。
   - 高风险项标记。
   - Markdown 导出。
   - 报告必须能从 `run_id` 对应的运行文件复现。

### 准生产硬要求

即使比赛阶段只接入样例任务，MVP 也必须具备以下准生产条件：

- 一站式自动评估：用户点击一次运行后，系统自动完成场景执行、评测和报告生成，中间不要求人工逐场景触发。
- 多场景覆盖：一次 run 至少覆盖 5 个场景，报告按场景聚合。
- 可解释性：每个 fail 或 partial 的评分项必须包含 `source`、`turn_ids`、`reason`。
- 可量化：报告必须包含总分、维度分、场景级结果和高风险项数量。
- 可追溯：保存 `TaskSpec`、`RubricSpec`、`ScenarioSet`、`DialogueTrace[]`、`EvaluationResult[]`、`Report`。
- 可复现：相同 `TaskSpec`、`RubricSpec`、`ScenarioSet` 和模型配置可以重新运行。
- 可扩展：核心接口支持 `ScenarioSet` 和 `EvaluationResult[]`，不允许写死单场景。

### 第一版暂不做，但必须预留边界

第一版不做以下生产功能的完整页面和完整治理流程：

- 登录和权限。
- 多项目管理。
- 多模型排行榜。
- 生产外呼接入。
- 自动训练或微调模型。
- 复杂 BI 看板。
- 多租户。
- 大规模数据管理。

但底层设计不得阻断这些能力。具体要求：

- 数据对象保留 `project_id`、`run_id`、版本号等扩展字段。
- 评测执行接口支持传入多个 scenario。
- 模型调用通过 provider 抽象，不写死某一个模型。
- 报告生成基于 `EvaluationResult[]`，不假设只有一个场景。
- 运行结果按 `run_id` 持久化，便于后续查询历史。

## 7. 生产扩展路线

以下能力作为生产落地路线，比赛 MVP 不需要完整实现，但架构需要兼容。

### 7.1 多任务与批量评测

生产中不会只评测一个任务。平台需要支持：

- 一个项目下管理多条任务指令。
- 为每条任务生成或维护独立 `ScenarioSuite`。
- 批量运行多个任务。
- 输出任务级报告和项目级汇总报告。

项目级汇总指标包括：

- 平均总分。
- 各维度平均分。
- 高风险项数量。
- 常见失败模式 Top N。
- 场景覆盖率。

### 7.2 场景库沉淀

用户模拟场景需要从“一次性生成”演进为“可维护场景库”。

场景来源：

- 指令自动生成。
- 人工补充。
- 脱敏历史数据抽取。
- 失败 case 回流。

场景应支持：

- 标签管理，例如 `FAQ`、`拒绝`、`忙碌`、`越界`。
- 难度分级，例如 L1 正常、L2 干扰、L3 高风险。
- 启用/禁用。
- 版本化。

### 7.3 模型接入扩展

生产中需要评估不同模型或不同 prompt 版本。

平台需要抽象统一接口：

```text
ModelProvider.generate(messages, config) -> ModelResponse
```

适配对象包括：

- 待测对话模型。
- 用户模拟模型。
- Judge 模型。

provider 层需要记录：

- 模型名称。
- prompt 版本。
- temperature 等参数。
- 请求耗时。
- 错误信息。

### 7.4 异步运行与任务队列

生产评测可能包含几十个任务、上百个场景，不能依赖同步请求。

后续需要支持：

- 创建 run 后立即返回 `run_id`。
- 后台 worker 执行场景对话和评测。
- Web 轮询或订阅 run 状态。
- 单场景失败不影响整个 run。
- 支持取消运行。

MVP 可以同步执行单场景，但接口设计应接近异步模型。

### 7.5 人工校准与审核

生产可靠性需要人工闭环。

后续平台应支持：

- 人工查看 Judge 结果。
- 修改评分项 verdict。
- 标记 Judge 错误。
- 形成校准样本。
- 用校准样本优化 Judge prompt 和 Rubric。

### 7.6 历史报告与回归评测

生产中平台应支持模型版本升级后的回归评测：

- 固定 `TaskSpecVersion`、`RubricVersion`、`ScenarioSuite`。
- 对新模型或新 prompt 重跑同一批场景。
- 对比新旧分数和失败项变化。

这项能力可以作为比赛后的重点扩展。

### 7.7 生产目标架构

```text
Web Console
  -> API Server
  -> Evaluation Engine
  -> Job Queue / Worker
  -> Model Providers
  -> Storage
       - relational metadata
       - trace/report object store
```

比赛阶段可以合并为单进程服务，但模块边界应向该架构演进。

## 8. 创新点

### 8.1 任务指令自动编译为评测规格

系统从每条任务指令中自动生成任务目标、流程步骤、FAQ、约束、异常分支和评分 Rubric，不使用一套固定指标套所有任务。

### 8.2 用户模拟器按任务分支动态测试

用户模拟器围绕任务指令中的关键分支生成用户行为，覆盖正常配合、拒绝、FAQ 追问、打断、忙碌和越界问题。

### 8.3 证据链式评测报告

每个扣分项都能追溯到：

```text
原始指令依据 -> 对话轮次证据 -> 评分结论和扣分原因
```

这比单纯给出总分更适合比赛要求中的可解释性。

## 9. 可信度设计

### 9.1 用户模拟可信

用户模拟器的场景来源包括：

- 任务指令中的显式分支。
- FAQ 中的用户追问。
- 约束条件中的异常情形。
- 履约外呼常见业务先验。

模拟器约束：

- 不泄露评分标准。
- 不主动帮助模型完成任务。
- 不生成明显脱离任务指令的极端问题。
- 输出后可由审计逻辑检查角色一致性和场景覆盖。

### 9.2 Judge 可信

硬约束优先走规则评测，不依赖 Judge。

Judge 只负责语义项，例如：

- 是否完成任务目标。
- 是否按照流程推进。
- 是否合理处理用户拒绝、追问和越界问题。

Judge 每个结论必须引用：

- 原始指令依据。
- 对话轮次。
- 判断理由。

小规模人工标注样本用于校准 Judge prompt 和 Rubric。

### 9.3 结果可复现

每次评测保存：

- `TaskSpec`
- `RubricSpec`
- `ScenarioSet`
- `DialogueTrace`
- `EvaluationResult`
- `Report`

报告中的分数和证据都能回查到本次运行文件。

## 10. 验收标准

比赛 MVP 验收标准：

- 能读取至少一条复杂任务指令。
- 能生成结构化 `TaskSpec` 和 `RubricSpec`。
- 能生成不少于 5 个用户模拟场景。
- 能一键运行完整 `ScenarioSet` 的多轮对话评测。
- 能保存每个场景的 `DialogueTrace`。
- 能执行至少 3 类规则评测。
- 能执行至少 1 类 Judge 语义评测。
- 能生成总分、维度分、场景结果、高风险项数量。
- 每个 fail 或 partial 扣分项包含原始指令依据、对话轮次证据和扣分原因。
- Web Demo 能完整展示输入、解析、场景、对话和报告五步。
- Web Demo 支持一站式运行：从已解析任务开始，一次点击完成多场景评测和报告生成。

生产可扩展性验收标准：

- 评测接口不限制单场景，支持 `ScenarioSet` 输入。
- 运行结果以 `run_id` 组织，支持多条 trace。
- 报告聚合逻辑基于多场景结果，不写死单场景。
- 模型调用通过 provider 接口，不直接绑定具体厂商或模型。
- `TaskSpec`、`RubricSpec`、`ScenarioSuite` 带版本字段或预留版本字段。
- 文件存储结构能映射到未来数据库实体。
- 单场景运行失败不导致整个 run 丢失结果。
- 报告可以从运行存储重新生成。

## 11. 开发顺序

推荐按以下顺序开发：

1. 数据对象和运行目录。
2. 指令解析与 Rubric 生成。
3. 场景生成。
4. 用户模拟器。
5. 对话执行器。
6. 规则评测。
7. Judge 评测。
8. Markdown 报告。
9. 多场景 run 聚合。
10. Web 向导页面。
11. Excel 样例接入和 Demo 打磨。

开发时需要坚持一个约束：即使比赛只演示一个任务，也不要把实现写成只能处理一个任务或一个场景。

## 12. 设计结论

本设计采用可扩展评测引擎作为底座，用轻量 Web 向导承载比赛演示。它避免把比赛项目做成过大的通用平台，同时从数据对象、运行记录、模型 provider、场景库和批量 run 维度预留生产落地能力。

核心交付应始终围绕比赛要求：用户模拟器充分测试模型，自动报告可解释且可量化。

其中“评估过程可解释、评估结果可量化、一站式自动评估”不是后续扩展项，而是比赛 MVP 的硬性验收门槛。
