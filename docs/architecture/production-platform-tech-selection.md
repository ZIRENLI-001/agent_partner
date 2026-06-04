# 履约外呼多轮对话评测平台技术选型与目录重构设计

## 1. 目标定位

本项目下一阶段采用“比赛可演示 + 准生产可演进”的折中方案。系统需要完整覆盖比赛要求中的用户模拟器、自动评测报告、评测过程可解释、评测结果可量化，同时为后续部署到开发机和生产化扩展保留清晰边界。

当前项目已经具备可运行的 FastAPI MVP、评测引擎模块、文件落盘的历史 run 和静态 HTML 前端。下一阶段不应推倒重写评测内核，而应把工程结构拆清楚：

- 保留 Python 评测内核，升级 API、存储、模型接入和任务执行边界。
- 将单文件 HTML 前端重构为 React 工程，支撑多页面、多状态、多报告组件。
- 先用轻量数据库和本地 artifact 存储满足开发机部署，后续平滑切换到 PostgreSQL、对象存储和异步 worker。

## 2. 比赛要求对齐

| 比赛要求 | 平台落点 |
| --- | --- |
| 构建用户模拟器 | 场景生成器、用户画像、用户模拟 Provider、多轮对话 Runner |
| 充分有效测试任务指令效果 | 场景覆盖矩阵、异常分支、FAQ 追问、忙碌/拒绝/越界等履约外呼场景 |
| 自动产出评测报告 | 报告服务生成 Markdown 与结构化 JSON，前端渲染可视化报告 |
| 评测过程可解释 | 每个评分项绑定原始指令依据、对话轮次、命中证据、扣分原因 |
| 评测结果可量化 | 总分、维度分、场景分、失败率、高风险项数量、覆盖率 |
| 可靠性 | 规则评测 + LLM Judge + 可复现运行配置 + 历史 run |
| 创新性 | 将复杂任务指令编译为 TaskSpec、Rubric 和可执行测试场景 |
| 商业价值 | 服务履约数字人外呼质检、模型上线前回归、Prompt 版本对比 |

平台不是通用聊天机器人评测系统，也不是模型训练系统。它的核心业务对象是“履约外呼任务指令”，核心评测目标是“复杂指令下的多轮对话遵循能力”。

## 3. 推荐技术选型

### 3.1 前端

| 能力 | 选型 | 说明 |
| --- | --- | --- |
| 应用框架 | React + TypeScript + Vite | 替代单文件 HTML，支持长期维护和快速开发 |
| 路由 | React Router | 首页、评测可视化、历史评测、报告详情独立路由 |
| 服务端状态 | TanStack Query | 管理 run 创建、轮询、历史记录、报告详情 |
| UI 组件 | Ant Design + 自定义美团主题 | 表单、步骤条、表格、折叠面板、上传、抽屉能力成熟 |
| 图表 | ECharts | 展示总分、维度分、场景覆盖、失败分布和趋势 |
| 样式 | CSS Modules 或普通 CSS 分层 | 控制样式边界，避免全局样式膨胀 |

前端需要承载两类评测模式：

- 端到端自动评测：用户输入模型、任务指令、样例数据后一键生成完整结果。
- 评测可视化：用户按阶段生成和查看 TaskSpec、Rubric、Scenario、Trace、Report。

### 3.2 后端

| 能力 | 选型 | 说明 |
| --- | --- | --- |
| API 服务 | FastAPI | 当前已有基础，适合结构化 JSON 和模型调用接口 |
| 数据建模 | Pydantic | 保留当前 domain 模型，并区分 API schema 与内部 domain |
| 数据库 | SQLite 起步，PostgreSQL 生产 | 开发机部署简单，后续可迁移到生产数据库 |
| ORM 和迁移 | SQLAlchemy 2.x + Alembic | 支持 Project、Run、Version、Artifact 元数据管理 |
| 异步任务 | Redis + RQ | 比 Celery 更轻，适合开发机和比赛阶段；后续可替换为 Celery |
| 模型接入 | OpenAI-compatible Provider 抽象 | 支持 OpenAI、Qwen、DeepSeek、内部模型网关、美团 LongCat 类模型 |
| 配置管理 | Pydantic Settings | 管理 DB、Redis、模型网关、artifact 路径 |
| 日志 | structlog 或标准 logging JSON 化 | 便于后续定位 run、trace、provider 请求 |

模型接入不绑定单一模型平台。比赛阶段可以优先支持 OpenRouter，便于快速选择不同厂商模型；生产阶段可以接入自研模型网关。二者都应尽量收敛到 OpenAI-compatible Chat Completions 协议。

推荐模型配置字段：

```text
provider_type       openrouter | openai_compatible | internal_gateway | mock
api_base            例如 https://openrouter.ai/api/v1 或内部模型网关地址
api_key             用户填写或后端密钥托管
model_name          例如 openai/gpt-4o、anthropic/claude-3.5-sonnet、internal-fulfillment-v1
temperature
max_tokens
timeout_seconds
```

平台每次评测 run 应保存三类模型配置：

```text
target_model_config       被测对话模型
user_simulator_config     用户模拟器模型
judge_model_config        自动评测 Judge 模型
```

这样可以在比赛中展示“动态切换被测模型”的能力，也能在生产中分别优化用户模拟器和 Judge 的稳定性。

### 3.3 存储

数据库只保存可查询、可过滤、可关联的元数据；大对象继续以 artifact 形式保存。

| 数据 | MVP 存储 | 后续生产存储 |
| --- | --- | --- |
| Project、User、Run 元数据 | SQLite | PostgreSQL |
| TaskSpec、Rubric、ScenarioSuite 版本索引 | SQLite | PostgreSQL |
| DialogueTrace、EvaluationResult、Report | 本地 artifacts | 对象存储或文档存储 |
| 上传样例数据 | 本地 artifacts | 对象存储 |
| 模型调用日志 | 本地 JSONL | 日志平台或数据库分表 |

## 4. 推荐目录结构

```text
agent_partner/
  backend/
    eval_agent/
      api/
        main.py
        routes/
          context.py
          runs.py
          stages.py
          projects.py
          auth.py
      core/
        config.py
        errors.py
        logging.py
      engine/
        instruction_parser.py
        rubric_builder.py
        scenario_generator.py
        user_simulator.py
        dialogue_runner.py
        rule_evaluator.py
        judge_evaluator.py
        report_writer.py
      models/
        domain.py
        db.py
        schemas.py
      providers/
        base.py
        mock.py
        openai_compatible.py
      services/
        evaluation_service.py
        run_service.py
        stage_service.py
        report_service.py
        artifact_service.py
      storage/
        repositories.py
        artifact_store.py
      workers/
        tasks.py
      tests/

  frontend/
    src/
      app/
        router.tsx
        queryClient.ts
      api/
        client.ts
        context.ts
        runs.ts
        stages.ts
      components/
        layout/
        navigation/
        ui/
      features/
        evaluation/
          components/
          hooks/
          types.ts
        report/
          components/
          charts/
          types.ts
        history/
          components/
      pages/
        HomePage.tsx
        EvaluationWizardPage.tsx
        RunHistoryPage.tsx
        RunDetailPage.tsx
      styles/
        globals.css
        theme.ts

  artifacts/
    runs/
      run_xxx/
        raw_input.json
        task_spec.json
        rubric_spec.json
        scenarios.json
        traces.jsonl
        evaluation_results.json
        report.md

  docs/
    architecture/
    product/
    deployment/

  docker-compose.yml
  README.md
```

## 5. 后端模块边界

### API 层

API 层只负责 HTTP 协议、参数校验和错误返回，不直接写评测逻辑。

核心接口建议：

```text
GET  /api/context
GET  /api/projects
POST /api/runs
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/artifacts/{artifact_name}
POST /api/stages/parse
POST /api/stages/rubric
POST /api/stages/scenarios
POST /api/stages/run
```

`POST /api/runs` 后续应演进为异步接口：创建 run 后立即返回 `run_id`，worker 后台执行，前端通过详情接口轮询状态。

### Service 层

Service 层编排业务流程：

- `RunService`：创建 run、查询 run、更新状态。
- `StageService`：按阶段生成 TaskSpec、Rubric、Scenario。
- `EvaluationService`：调用评测引擎完成端到端评测。
- `ReportService`：生成结构化报告和 Markdown 报告。
- `ArtifactService`：读写 trace、report、上传数据等 artifact。

### Engine 层

Engine 层保留当前核心评测能力，输入输出为纯 domain 对象，不依赖数据库和 FastAPI。

```text
RawInstruction
  -> TaskSpec
  -> RubricSpec
  -> ScenarioSet
  -> DialogueTrace[]
  -> EvaluationResult[]
  -> Report
```

该层应保持可单元测试、可复用、可离线运行。

### Provider 层

Provider 层统一模型调用接口：

```text
ModelProvider.generate(messages, config) -> ModelResponse
```

至少拆分三类调用：

- 待评测模型 Provider。
- 用户模拟模型 Provider。
- Judge 模型 Provider。

Provider 需要记录模型名称、参数、耗时、错误信息和响应摘要，服务可解释性和复现。

#### OpenRouter 接入

OpenRouter 作为 `openrouter` 类型的 OpenAI-compatible Provider 使用。默认配置：

```text
api_base = https://openrouter.ai/api/v1
endpoint = /chat/completions
```

前端允许用户选择或填写 OpenRouter 模型名，例如：

```text
openai/gpt-4o
anthropic/claude-3.5-sonnet
google/gemini-pro
deepseek/deepseek-chat
```

后端不直接依赖某个具体模型，只将 `model_name` 透传给 Provider。这样平台能对同一任务、同一 ScenarioSuite 运行多个模型版本，形成横向对比。

#### 自研模型 API 接入

自研模型优先要求暴露 OpenAI-compatible 接口：

```text
POST {api_base}/chat/completions
```

请求体保持统一：

```json
{
  "model": "internal-fulfillment-v1",
  "messages": [
    {"role": "system", "content": "系统提示词"},
    {"role": "user", "content": "用户输入"}
  ],
  "temperature": 0.2,
  "max_tokens": 512
}
```

如果自研模型网关不是 OpenAI-compatible，则新增独立 adapter，例如 `InternalGatewayProvider`，在 adapter 内完成字段映射、鉴权头转换、响应解析和错误归一化。业务层和评测引擎仍只调用统一 `ModelProvider` 接口。

#### 密钥与安全边界

比赛 MVP 可以允许用户在前端输入 API Key，但后端不得把完整密钥写入 run artifact。落盘时只保存：

```text
api_key_configured = true
api_key_last4 = ****
```

生产阶段应改为后端密钥托管或项目级密钥引用，例如：

```text
credential_ref = project_secret_openrouter
```

这样既能支持比赛演示中的灵活模型选择，也避免后续生产部署时泄露模型网关凭证。

## 6. 数据模型边界

下一阶段建议引入以下数据库实体：

| 实体 | 用途 |
| --- | --- |
| User | 登录用户，MVP 可使用 demo user |
| Project | 评测项目，例如某业务线、某模型版本评测 |
| TaskInstruction | 原始任务指令和输入数据引用 |
| TaskSpecVersion | 指令解析结果版本 |
| RubricVersion | 评分标准版本 |
| ScenarioSuite | 测试场景集合 |
| Run | 一次评测运行 |
| RunArtifact | run 关联的文件 artifact 索引 |
| HumanReviewNote | 人工校准备注，不直接改分 |

比赛 MVP 可以只实现 `Project`、`Run`、`RunArtifact` 的轻量版本，但代码结构要允许后续补齐版本化实体。

## 7. 前端页面边界

### 首页

首页只承担入口和概览，不堆完整评测结果。主要内容：

- 平台定位：履约外呼复杂指令评测。
- 三个入口：端到端自动评测、评测可视化、历史评测。
- 最近 run 简要状态。
- 评测能力概览：指令解析、用户模拟、证据报告。

### 评测可视化

页面采用向导式流程：

```text
模型配置
  -> 导入任务指令和评测数据
  -> 指令解析
  -> Rubric 生成
  -> 测试场景生成
  -> 轨迹与评分结果
  -> 可视化报告
```

每一步点击“生成”后生成当前步骤结果，再点击“下一步”进入后续步骤。上游变更时，下游结果应失效。

### 历史评测

历史页用于准生产能力展示：

- 按项目、模型、时间、状态筛选。
- 分页展示 run。
- 点击进入 run 详情。
- 后续支持同一任务下不同模型版本对比。

### 报告详情

报告页必须避免长文本平铺，采用折叠和图表组合：

- 总览：总分、通过率、场景数、高风险项。
- 维度分：任务完成、流程遵循、知识准确、异常处理、安全边界。
- 场景覆盖矩阵。
- 失败项列表。
- 证据链折叠详情。
- Markdown 报告导出。

## 8. 部署方案

开发机部署推荐 Docker Compose：

```text
frontend    Vite build 后由 Nginx 或 FastAPI 静态服务托管
api         FastAPI + Uvicorn
worker      RQ worker，比赛阶段可不开启
redis       任务队列
db          SQLite 文件或 PostgreSQL
artifacts   本地挂载目录
```

比赛阶段可以先采用单进程部署：

```text
FastAPI
  -> serves frontend build
  -> sync evaluation
  -> SQLite metadata
  -> local artifacts
```

准生产阶段再开启：

```text
FastAPI API
  -> Redis Queue
  -> Worker
  -> PostgreSQL
  -> Object Store
```

## 9. 分阶段实施建议

### Phase 1：结构重构，不改变核心能力

- 建立 `backend/` 和 `frontend/` 工程。
- 迁移现有 FastAPI 和评测模块到新目录。
- 保留当前 API 行为，确保测试通过。
- 前端 React 复刻当前核心页面能力。

### Phase 2：数据层和历史 run 生产化

- 引入 SQLite、SQLAlchemy、Alembic。
- 建立 `Run`、`Project`、`RunArtifact` 表。
- `runs/` 改为 `artifacts/runs/`。
- 历史页从数据库查询，详情从 artifact 读取。

### Phase 3：模型 Provider 接入

- 实现 mock provider 和 OpenAI-compatible provider。
- 支持目标模型、用户模拟模型、Judge 模型分别配置。
- 记录 provider 调用耗时、错误和响应摘要。

### Phase 4：异步任务和运行状态

- 引入 Redis + RQ。
- `POST /api/runs` 创建 run 后返回 `run_id`。
- Worker 执行评测并更新状态。
- 前端轮询 run 状态并展示阶段进度。

### Phase 5：报告增强和评委展示

- ECharts 可视化报告。
- 证据链折叠详情。
- 场景覆盖矩阵。
- 一键导出 Markdown 或 PDF。

## 10. 当前项目迁移策略

不建议一次性大改所有文件。推荐迁移顺序：

1. 先新增目录结构和文档，不影响当前服务。
2. 把 `eval_agent/domain.py` 迁移为 `backend/eval_agent/models/domain.py`。
3. 把评测核心模块迁移到 `backend/eval_agent/engine/`。
4. 把 `app.py` 拆为 `api/main.py` 和 routes。
5. 用兼容层保持旧测试可运行。
6. 新建 React 前端，逐步替代 `eval_agent/web/index.html`。
7. 确认新前端功能完整后，再移除旧静态页。

这样可以降低重构风险，保证比赛 MVP 在迁移期间始终可运行。

## 11. 风险与约束

| 风险 | 应对 |
| --- | --- |
| 前端重构周期过长 | 第一版只复刻首页、评测可视化、历史和报告四个页面 |
| 数据库引入后影响现有测试 | 先保留文件存储兼容层，再逐步替换 |
| 异步任务增加部署复杂度 | Phase 1 到 Phase 3 仍支持同步评测 |
| 模型调用不稳定 | 保留 mock provider，真实 provider 失败时给出可解释错误 |
| 报告可解释性不足 | 评分 evidence 字段设为强约束，缺失则测试失败 |

## 12. 推荐结论

下一阶段采用以下路线：

```text
React + TypeScript + Vite 前端
FastAPI + Pydantic 后端
SQLite 起步，PostgreSQL 预留
本地 artifacts 起步，对象存储预留
同步评测起步，Redis + RQ 异步预留
OpenAI-compatible Provider 抽象
Docker Compose 开发机部署
```

该方案能够满足比赛演示的一站式自动评估、可解释报告、可量化结果，也能支撑后续生产落地中的多用户、多项目、多模型、多场景和历史回归评测。
