# Meituan Wizard Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the evaluation platform frontend as a Meituan-style, one-screen-at-a-time wizard that guides users through model input, data import, instruction parsing, rubric generation, scenario generation, trace review, and final visual report.

**Architecture:** Keep the existing FastAPI backend and evaluation engine, but add small stage endpoints so the UI can show real intermediate artifacts instead of fake progress. Replace the current single-page block layout with a fresh wizard shell in `eval_agent/web/index.html`, using Meituan yellow as a brand accent and an operations-tool layout optimized for competition demo and future production extension.

**Tech Stack:** FastAPI, Pydantic, plain HTML/CSS/JavaScript, pytest, FastAPI TestClient.

---

## File Structure

- Modify: `eval_agent/app.py`
  - Add stage endpoints for parse, rubric, and scenario generation.
  - Extend run request to carry model configuration, input data, and selected scenario IDs.
  - Keep existing `/api/runs` response shape compatible while adding `model_config_summary`.

- Modify: `eval_agent/engine.py`
  - Add optional `selected_scenario_ids` support so the one-click run can execute user-selected scenarios.
  - Persist selected scenario IDs and model config summary into run artifacts.

- Replace: `eval_agent/web/index.html`
  - Rebuild from scratch as a 7-step wizard.
  - Do not preserve the current block/tabs UI.
  - Use a CSS Meituan-style wordmark placeholder: yellow brand tile plus `美团履约评测`.
  - If an official logo file is later provided, replace only the `.brand-mark` element.

- Modify: `tests/test_app.py`
  - Replace old page text assertions with wizard interaction anchors.
  - Add tests for stage endpoints and model config summary.
  - Add selected scenario filtering test.

- Modify: `docs/verification.md`
  - Record the final verification command and the local smoke test URL after implementation.

---

## Design Constraints

- The first screen must be the actual product workflow, not a landing page.
- The UI must be a wizard: one active step per screen, with Previous/Next/Run actions.
- The required steps are:
  1. 用户输入评测模型
  2. 导入待评测数据和场景
  3. 指令解析
  4. Rubric
  5. 测试场景
  6. 轨迹展示，结果展示
  7. 最终可视化结果报告
- The top shell must show brand, run status, and current step.
- The left rail must show the 7-step progress with `locked`, `ready`, `running`, and `done` states.
- Use Meituan yellow `#FFD100` only as accent, not as full-page background.
- Do not use blue as the primary action color.
- Keep text dense and operational. Avoid oversized marketing hero sections.
- Cards are allowed for repeated scenario/result items; do not nest cards inside cards.
- Use stable dimensions for step rail, action bar, metric tiles, and trace/result panes.

---

### Task 1: Update App Tests For Wizard Contract

**Files:**
- Modify: `tests/test_app.py`

- [ ] **Step 1: Replace the old HTML assertion test with wizard assertions**

Replace `test_index_serves_workbench_html` with:

```python
def test_index_serves_meituan_wizard_html():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "美团履约评测" in response.text
    assert "评测模型" in response.text
    assert "导入数据与场景" in response.text
    assert "指令解析" in response.text
    assert "Rubric 生成" in response.text
    assert "测试场景" in response.text
    assert "轨迹与结果" in response.text
    assert "可视化报告" in response.text
    assert "data-step=\"model\"" in response.text
    assert "data-step=\"data\"" in response.text
    assert "data-step=\"parse\"" in response.text
    assert "data-step=\"rubric\"" in response.text
    assert "data-step=\"scenarios\"" in response.text
    assert "data-step=\"run\"" in response.text
    assert "data-step=\"report\"" in response.text
    assert "模型 API Base" in response.text
    assert "加载美团履约样例" in response.text
    assert "下一步" in response.text
```

- [ ] **Step 2: Add tests for stage endpoints**

Append:

```python
def test_stage_parse_returns_task_spec_and_input_summary():
    client = TestClient(web_app.app)

    response = client.post(
        "/api/stages/parse",
        json={
            "instruction": RAW_TASK,
            "input_data": '{"rider_id":"r_001","contract_status":"active"}',
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "parse"
    assert data["task_spec"]["required_steps"]
    assert data["input_data_summary"]["format"] == "json"
    assert data["input_data_summary"]["field_count"] == 2


def test_stage_rubric_returns_quantitative_items():
    client = TestClient(web_app.app)

    response = client.post("/api/stages/rubric", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "rubric"
    assert data["rubric_spec"]["items"]
    assert all("weight" in item for item in data["rubric_spec"]["items"])
    assert all("criterion" in item for item in data["rubric_spec"]["items"])


def test_stage_scenarios_returns_meituan_scenario_set():
    client = TestClient(web_app.app)

    response = client.post("/api/stages/scenarios", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "scenarios"
    assert len(data["scenario_set"]["scenarios"]) >= 5
    assert all("coverage_targets" in item for item in data["scenario_set"]["scenarios"])
```

- [ ] **Step 3: Add tests for model config and selected scenario run**

Append:

```python
def test_create_run_accepts_model_config_summary(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "model_config": {
                "provider": "openai_compatible",
                "model_name": "demo-model",
                "api_base": "https://example.com/v1",
                "api_key": "sk-secret",
                "judge_mode": "hybrid",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model_config_summary"]["provider"] == "openai_compatible"
    assert data["model_config_summary"]["model_name"] == "demo-model"
    assert data["model_config_summary"]["api_key_configured"] is True
    assert "sk-secret" not in data["model_config_summary"].values()


def test_create_run_can_filter_selected_scenarios(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={"instruction": RAW_TASK, "selected_scenario_ids": ["normal_acceptance"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trace_count"] == 1
    assert data["result_count"] == 1
    assert data["traces"][0]["scenario_id"] == "normal_acceptance"
```

- [ ] **Step 4: Run tests and verify they fail before implementation**

Run:

```bash
python3 -m pytest tests/test_app.py -v
```

Expected: failures for missing `/api/stages/*`, missing `model_config_summary`, missing scenario filtering, and old `index.html` content.

---

### Task 2: Add Stage API And Run Configuration

**Files:**
- Modify: `eval_agent/app.py`
- Modify: `eval_agent/engine.py`

- [ ] **Step 1: Add imports and request models in `eval_agent/app.py`**

Add imports:

```python
from typing import Any

from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.scenario_generator import generate_scenarios
from backend.evaluation_engine.engine import run_full_evaluation, summarize_input_data
```

Replace `RunRequest` with:

```python
class ModelConfig(BaseModel):
    provider: str = "mock"
    model_name: str = ""
    api_base: str = ""
    api_key: str = ""
    judge_mode: str = "hybrid"


class StageRequest(BaseModel):
    instruction: str
    input_data: str = ""
    minimum_scenarios: int = 5


class RunRequest(StageRequest):
    model_config: ModelConfig = ModelConfig()
    selected_scenario_ids: list[str] = []
```

- [ ] **Step 2: Add stage endpoints in `eval_agent/app.py`**

Add below `sample_tasks()`:

```python
@app.post("/api/stages/parse")
def parse_stage(request: StageRequest) -> dict[str, object]:
    task_spec = parse_instruction(request.instruction)
    return {
        "stage": "parse",
        "task_spec": task_spec.model_dump(mode="json"),
        "input_data_summary": summarize_input_data(request.input_data),
    }


@app.post("/api/stages/rubric")
def rubric_stage(request: StageRequest) -> dict[str, object]:
    task_spec = parse_instruction(request.instruction)
    rubric_spec = build_rubric(task_spec)
    return {
        "stage": "rubric",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
    }


@app.post("/api/stages/scenarios")
def scenarios_stage(request: StageRequest) -> dict[str, object]:
    task_spec = parse_instruction(request.instruction)
    rubric_spec = build_rubric(task_spec)
    scenario_set = generate_scenarios(
        task_spec=task_spec,
        rubric=rubric_spec,
        minimum=request.minimum_scenarios,
    )
    return {
        "stage": "scenarios",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
        "scenario_set": scenario_set.model_dump(mode="json"),
    }
```

- [ ] **Step 3: Add model config summary helper in `eval_agent/app.py`**

Add:

```python
def _model_config_summary(model_config: ModelConfig) -> dict[str, object]:
    return {
        "provider": model_config.provider,
        "model_name": model_config.model_name,
        "api_base": model_config.api_base,
        "judge_mode": model_config.judge_mode,
        "api_key_configured": bool(model_config.api_key),
    }
```

- [ ] **Step 4: Pass new fields through `create_run()`**

Change the `run_full_evaluation(...)` call:

```python
result = run_full_evaluation(
    raw_instruction=request.instruction,
    run_root=RUN_ROOT,
    assistant_provider=FakeAssistantProvider(),
    user_provider=FakeUserProvider(),
    minimum_scenarios=request.minimum_scenarios,
    input_data=request.input_data,
    selected_scenario_ids=request.selected_scenario_ids,
    model_config_summary=_model_config_summary(request.model_config),
)
```

Add to the response:

```python
"model_config_summary": _model_config_summary(request.model_config),
```

- [ ] **Step 5: Extend `run_full_evaluation()` signature in `eval_agent/engine.py`**

Change the function signature:

```python
def run_full_evaluation(
    raw_instruction: str,
    run_root: Path = Path("runs"),
    assistant_provider: AssistantProvider | None = None,
    user_provider: UserProvider | None = None,
    minimum_scenarios: int = 5,
    input_data: str = "",
    selected_scenario_ids: list[str] | None = None,
    model_config_summary: dict[str, object] | None = None,
) -> FullRunResult:
```

- [ ] **Step 6: Filter scenarios before running traces in `eval_agent/engine.py`**

After `scenario_set = generate_scenarios(...)`, add:

```python
    selected_ids = set(selected_scenario_ids or [])
    if selected_ids:
        scenario_set.scenarios = [
            scenario
            for scenario in scenario_set.scenarios
            if scenario.scenario_id in selected_ids
        ]
```

- [ ] **Step 7: Persist run configuration extensions in `eval_agent/engine.py`**

In the `run_config.json` payload, add:

```python
        "selected_scenario_ids": selected_scenario_ids or [],
        "model_config_summary": model_config_summary or {},
```

- [ ] **Step 8: Run app tests**

Run:

```bash
python3 -m pytest tests/test_app.py -v
```

Expected: stage endpoint and model config tests pass; HTML wizard test still fails until the frontend is replaced.

---

### Task 3: Replace Frontend With Meituan Wizard Shell

**Files:**
- Replace: `eval_agent/web/index.html`

- [ ] **Step 1: Replace document metadata and app shell**

Use this page structure:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>美团履约评测工作台</title>
    <style>
      :root {
        --mt-yellow: #ffd100;
        --mt-yellow-dark: #e6b800;
        --ink: #111111;
        --ink-muted: #5f6368;
        --line: #e6e8eb;
        --surface: #ffffff;
        --surface-soft: #f7f8fa;
        --success: #188038;
        --danger: #d93025;
        --warning: #b06000;
        --focus: rgba(255, 209, 0, 0.34);
      }
    </style>
  </head>
  <body>
    <div class="app-shell">
      <header class="topbar">
        <div class="brand">
          <div class="brand-mark" aria-hidden="true">美</div>
          <div>
            <div class="brand-title">美团履约评测</div>
            <div class="brand-subtitle">复杂指令下的多轮对话自动评估</div>
          </div>
        </div>
        <div class="run-status">
          <span id="run-status-dot" class="status-dot idle"></span>
          <span id="run-status-text">等待配置</span>
        </div>
      </header>

      <main class="workspace">
        <aside class="step-rail" aria-label="评测流程">
          <button class="step-item active" type="button" data-step="model">1. 评测模型</button>
          <button class="step-item locked" type="button" data-step="data">2. 导入数据与场景</button>
          <button class="step-item locked" type="button" data-step="parse">3. 指令解析</button>
          <button class="step-item locked" type="button" data-step="rubric">4. Rubric 生成</button>
          <button class="step-item locked" type="button" data-step="scenarios">5. 测试场景</button>
          <button class="step-item locked" type="button" data-step="run">6. 轨迹与结果</button>
          <button class="step-item locked" type="button" data-step="report">7. 可视化报告</button>
        </aside>

        <section class="stage" id="stage-root" aria-live="polite"></section>
      </main>

      <footer class="actionbar">
        <button id="prev-button" class="secondary-button" type="button">上一步</button>
        <div id="action-hint" class="action-hint">先配置被测模型，再进入数据导入。</div>
        <button id="next-button" class="primary-button" type="button">下一步</button>
      </footer>
    </div>
    <script>
      const steps = ["model", "data", "parse", "rubric", "scenarios", "run", "report"];
    </script>
  </body>
</html>
```

- [ ] **Step 2: Add layout CSS**

Add CSS rules for:

```css
body {
  margin: 0;
  color: var(--ink);
  background: var(--surface-soft);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: 72px 1fr 72px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: var(--mt-yellow);
  color: var(--ink);
  font-weight: 800;
  font-size: 22px;
}

.workspace {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  min-height: 0;
}

.step-rail {
  padding: 20px 16px;
  background: var(--surface);
  border-right: 1px solid var(--line);
}

.step-item {
  width: 100%;
  height: 44px;
  margin-bottom: 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-muted);
  text-align: left;
  padding: 0 12px;
  cursor: pointer;
}

.step-item.active {
  background: #fff7cc;
  border-color: var(--mt-yellow);
  color: var(--ink);
  font-weight: 700;
}

.step-item.done::after {
  content: "完成";
  float: right;
  color: var(--success);
  font-size: 12px;
}

.step-item.locked {
  cursor: not-allowed;
  opacity: 0.48;
}

.stage {
  min-width: 0;
  padding: 28px;
  overflow: auto;
}

.actionbar {
  display: grid;
  grid-template-columns: 120px 1fr 160px;
  align-items: center;
  gap: 16px;
  padding: 0 28px;
  background: var(--surface);
  border-top: 1px solid var(--line);
}
```

- [ ] **Step 3: Add reusable UI CSS**

Add `.stage-panel`, `.form-grid`, `.field`, `.input`, `.textarea`, `.metric-grid`, `.metric`, `.list`, `.list-item`, `.split-pane`, `.trace-pane`, `.result-pane`, `.evidence-chain`, `.primary-button`, `.secondary-button`, `.danger-chip`, `.success-chip`, `.coverage-chip`, and responsive rules:

```css
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .step-rail {
    display: flex;
    overflow-x: auto;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .step-item {
    min-width: 160px;
  }

  .actionbar {
    grid-template-columns: 96px 1fr 120px;
    padding: 0 16px;
  }
}
```

- [ ] **Step 4: Run the HTML test**

Run:

```bash
python3 -m pytest tests/test_app.py::test_index_serves_meituan_wizard_html -v
```

Expected: PASS.

---

### Task 4: Implement Wizard State And Step Rendering

**Files:**
- Modify: `eval_agent/web/index.html`

- [ ] **Step 1: Add frontend state object**

Add in `<script>`:

```javascript
const state = {
  activeStep: "model",
  completed: new Set(),
  modelConfig: {
    provider: "openai_compatible",
    model_name: "",
    api_base: "",
    api_key: "",
    judge_mode: "hybrid",
  },
  instruction: "",
  inputData: "",
  sampleTasks: [],
  selectedScenarioIds: new Set(),
  parseResult: null,
  rubricResult: null,
  scenarioResult: null,
  runResult: null,
};
```

- [ ] **Step 2: Implement navigation helpers**

Add:

```javascript
function stepIndex(step) {
  return steps.indexOf(step);
}

function canOpenStep(step) {
  return step === "model" || state.completed.has(steps[stepIndex(step) - 1]) || state.completed.has(step);
}

function setActiveStep(step) {
  if (!canOpenStep(step)) return;
  state.activeStep = step;
  renderShell();
  renderStep();
}

function completeStep(step) {
  state.completed.add(step);
  const next = steps[stepIndex(step) + 1];
  if (next) setActiveStep(next);
  else renderShell();
}
```

- [ ] **Step 3: Implement model step**

Render fields:

```javascript
function renderModelStep() {
  stageRoot.innerHTML = `
    <div class="stage-panel">
      <div class="stage-heading">
        <p class="eyebrow">Step 1</p>
        <h1>输入评测模型</h1>
        <p>配置被测对话模型与评测方式。MVP 默认使用本地 Mock Provider，生产环境可替换为 OpenAI Compatible API。</p>
      </div>
      <div class="form-grid">
        <label class="field">模型供应商
          <select id="provider" class="input">
            <option value="openai_compatible">OpenAI Compatible</option>
            <option value="mock">Mock Demo</option>
          </select>
        </label>
        <label class="field">模型名称
          <input id="model-name" class="input" placeholder="例如 gpt-4.1 / internal-dialogue-model" />
        </label>
        <label class="field">模型 API Base
          <input id="api-base" class="input" placeholder="https://example.com/v1" />
        </label>
        <label class="field">API Key
          <input id="api-key" class="input" type="password" placeholder="仅前端脱敏展示，后端不回显明文" />
        </label>
        <label class="field">评测模式
          <select id="judge-mode" class="input">
            <option value="hybrid">规则 + LLM Judge 混合</option>
            <option value="rule">仅规则</option>
            <option value="judge">仅 LLM Judge</option>
          </select>
        </label>
      </div>
    </div>
  `;
}
```

- [ ] **Step 4: Implement data/import step**

Render:

```javascript
function renderDataStep() {
  stageRoot.innerHTML = `
    <div class="stage-panel">
      <div class="stage-heading">
        <p class="eyebrow">Step 2</p>
        <h1>导入待评测数据和场景</h1>
        <p>输入任务指令、业务数据和美团履约样例。后续所有评分证据都会回指这里的原始输入。</p>
      </div>
      <div class="split-pane">
        <section>
          <div class="section-title">任务指令</div>
          <textarea id="instruction-input" class="textarea tall" placeholder="粘贴外呼任务指令"></textarea>
          <button id="load-sample-button" class="secondary-button inline" type="button">加载美团履约样例</button>
        </section>
        <section>
          <div class="section-title">待评测数据</div>
          <textarea id="input-data" class="textarea tall" placeholder='{"rider_id":"r_001","contract_status":"active"}'></textarea>
        </section>
      </div>
    </div>
  `;
}
```

- [ ] **Step 5: Implement parse/rubric/scenario/run/report renderers**

Each renderer must show real data from API responses:

```javascript
function renderParseStep() {
  const spec = state.parseResult?.task_spec;
  stageRoot.innerHTML = spec ? renderTaskSpec(spec) : renderEmptyStage("指令解析", "点击下一步后解析任务目标、流程、约束、FAQ 和异常分支。");
}

function renderRubricStep() {
  const rubric = state.rubricResult?.rubric_spec;
  stageRoot.innerHTML = rubric ? renderRubric(rubric) : renderEmptyStage("Rubric 生成", "点击下一步后生成评分项、权重、判定方式和证据来源。");
}

function renderScenariosStep() {
  const scenarios = state.scenarioResult?.scenario_set?.scenarios || [];
  stageRoot.innerHTML = scenarios.length ? renderScenarios(scenarios) : renderEmptyStage("测试场景", "点击下一步后生成覆盖拒绝、忙碌、追问、退出、超范围等分支的用户模拟场景。");
}

function renderRunStep() {
  stageRoot.innerHTML = state.runResult ? renderRunResult(state.runResult) : renderEmptyStage("轨迹与结果", "点击运行后展示每个场景的多轮对话轨迹、得分和失败证据。");
}

function renderReportStep() {
  stageRoot.innerHTML = state.runResult ? renderReport(state.runResult) : renderEmptyStage("可视化报告", "完成运行后生成量化总览、维度得分、覆盖矩阵和证据链报告。");
}
```

- [ ] **Step 6: Run full app tests**

Run:

```bash
python3 -m pytest tests/test_app.py -v
```

Expected: PASS for endpoint tests and static HTML tests.

---

### Task 5: Wire Stage Actions To Real APIs

**Files:**
- Modify: `eval_agent/web/index.html`

- [ ] **Step 1: Add API helper**

Add:

```javascript
async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `请求失败：${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 2: Add sample task loading**

Add:

```javascript
async function loadSampleTasks() {
  const response = await fetch("/api/sample-tasks");
  if (!response.ok) throw new Error("无法加载 Excel 样例");
  const data = await response.json();
  state.sampleTasks = data.tasks || [];
  if (state.sampleTasks[0]) {
    state.instruction = state.sampleTasks[0].instruction;
    document.getElementById("instruction-input").value = state.instruction;
  }
}
```

- [ ] **Step 3: Add stage execution functions**

Add:

```javascript
async function executeParseStage() {
  state.parseResult = await postJson("/api/stages/parse", {
    instruction: state.instruction,
    input_data: state.inputData,
  });
}

async function executeRubricStage() {
  state.rubricResult = await postJson("/api/stages/rubric", {
    instruction: state.instruction,
    input_data: state.inputData,
  });
}

async function executeScenariosStage() {
  state.scenarioResult = await postJson("/api/stages/scenarios", {
    instruction: state.instruction,
    input_data: state.inputData,
    minimum_scenarios: 5,
  });
  state.selectedScenarioIds = new Set(
    state.scenarioResult.scenario_set.scenarios.map((scenario) => scenario.scenario_id)
  );
}

async function executeRunStage() {
  state.runResult = await postJson("/api/runs", {
    instruction: state.instruction,
    input_data: state.inputData,
    minimum_scenarios: 5,
    model_config: state.modelConfig,
    selected_scenario_ids: Array.from(state.selectedScenarioIds),
  });
}
```

- [ ] **Step 4: Add primary button behavior**

Implement:

```javascript
async function handleNext() {
  try {
    setRunning(true);
    if (state.activeStep === "model") {
      readModelForm();
      completeStep("model");
      return;
    }
    if (state.activeStep === "data") {
      readDataForm();
      completeStep("data");
      return;
    }
    if (state.activeStep === "parse") {
      await executeParseStage();
      completeStep("parse");
      return;
    }
    if (state.activeStep === "rubric") {
      await executeRubricStage();
      completeStep("rubric");
      return;
    }
    if (state.activeStep === "scenarios") {
      await executeScenariosStage();
      completeStep("scenarios");
      return;
    }
    if (state.activeStep === "run") {
      await executeRunStage();
      completeStep("run");
      return;
    }
    if (state.activeStep === "report") {
      renderReportStep();
    }
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    setRunning(false);
  }
}
```

- [ ] **Step 5: Add validation before advancing**

Validation behavior:

```javascript
function validateCurrentStep() {
  if (state.activeStep === "data" && !state.instruction.trim()) {
    throw new Error("请先输入任务指令，或加载美团履约样例。");
  }
  if (state.activeStep === "scenarios" && state.selectedScenarioIds.size === 0) {
    throw new Error("请至少选择一个测试场景。");
  }
}
```

Call `validateCurrentStep()` at the beginning of `handleNext()`.

- [ ] **Step 6: Manual smoke test**

Start server:

```bash
python3 -m uvicorn backend.evaluation_engine.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Expected:
- Step 1 can accept model config.
- Step 2 can load the Feimaotui sample.
- Step 3 shows parsed required steps and constraints.
- Step 4 shows rubric items with weights.
- Step 5 shows at least 5 scenarios and selectable checkboxes.
- Step 6 runs selected scenarios and shows traces plus failure evidence.
- Step 7 shows visual summary and Markdown report.

---

### Task 6: Build Explainable Visual Report UI

**Files:**
- Modify: `eval_agent/web/index.html`

- [ ] **Step 1: Render quantitative summary**

`renderReport(result)` must include:

```javascript
function renderReport(result) {
  const score = result.score_summary;
  return `
    <div class="stage-panel">
      <div class="stage-heading">
        <p class="eyebrow">Step 7</p>
        <h1>最终可视化结果报告</h1>
        <p>报告由任务指令、Rubric、场景、对话轨迹和评测证据自动汇总生成。</p>
      </div>
      <div class="metric-grid">
        <div class="metric"><span>总分</span><strong>${score.total_score}/${score.possible_score}</strong></div>
        <div class="metric"><span>通过率</span><strong>${score.pass_rate}%</strong></div>
        <div class="metric"><span>场景数</span><strong>${score.scenario_count}</strong></div>
        <div class="metric"><span>严重失败</span><strong>${score.critical_failure_count}</strong></div>
      </div>
      ${renderDimensionBars(result.dimension_summary)}
      ${renderScenarioMatrix(result.scenario_summary)}
      ${renderFailureSummary(result.failure_summary)}
      ${renderEvidenceChains(result.results)}
      <details class="markdown-report">
        <summary>查看 Markdown 报告</summary>
        <pre>${escapeHtml(result.report)}</pre>
      </details>
    </div>
  `;
}
```

- [ ] **Step 2: Render trace and evidence side by side**

`renderRunResult(result)` must include:

```javascript
function renderRunResult(result) {
  const firstTrace = result.traces[0];
  const firstResult = result.results[0];
  return `
    <div class="stage-panel">
      <div class="stage-heading">
        <p class="eyebrow">Step 6</p>
        <h1>轨迹展示与结果展示</h1>
        <p>每条扣分结论都回指具体对话轮次，便于评委复核。</p>
      </div>
      <div class="split-pane trace-result">
        <section class="trace-pane">${renderTrace(firstTrace)}</section>
        <section class="result-pane">${renderResultEvidence(firstResult)}</section>
      </div>
    </div>
  `;
}
```

- [ ] **Step 3: Evidence chain must include four fields**

Every evidence item displayed must include:

```text
指令依据
预期行为
实际对话证据
判定解释
```

Use values from:

```javascript
item.instruction_quote
item.expected_behavior
item.actual_behavior
item.explanation
```

- [ ] **Step 4: Run all tests**

Run:

```bash
python3 -m pytest -v
```

Expected: all tests pass.

---

### Task 7: Verification And Documentation

**Files:**
- Modify: `docs/verification.md`

- [ ] **Step 1: Record test evidence**

Append:

```markdown
## 2026-05-21 Meituan Wizard Frontend

- Command: `python3 -m pytest -v`
- Expected: all tests passed.
- Scope verified:
  - 7-step Meituan-style wizard HTML served at `/`.
  - Stage endpoints return parse, rubric, and scenario artifacts.
  - Run endpoint accepts model configuration and selected scenario IDs.
  - Visual report contains quantitative summary and explainable evidence chains.
```

- [ ] **Step 2: Record local smoke test**

Append:

```markdown
### Local Smoke Test

- Server command: `python3 -m uvicorn backend.evaluation_engine.app:app --host 127.0.0.1 --port 8000`
- URL: `http://127.0.0.1:8000`
- Manual path:
  1. Configure model.
  2. Load Meituan Feimaotui sample.
  3. Parse instruction.
  4. Generate Rubric.
  5. Select scenarios.
  6. Run evaluation.
  7. Review final visual report.
```

- [ ] **Step 3: Final verification before completion**

Run:

```bash
python3 -m pytest -v
```

Expected: all tests pass.

Run server smoke test:

```bash
python3 -m uvicorn backend.evaluation_engine.app:app --host 127.0.0.1 --port 8000
```

Expected: browser can complete all 7 wizard steps.

---

## Self-Review

- Spec coverage:
  - User input model: Task 3 and Task 4.
  - Import evaluation data and scenario: Task 4 and Task 5.
  - Instruction parsing: Task 2 and Task 5.
  - Rubric generation: Task 2 and Task 5.
  - Test scenario generation and selection: Task 2, Task 4, Task 5.
  - Trace/result display: Task 6.
  - Final visual report: Task 6.
  - Explainable evidence chain: Task 6.
  - Quantitative results: Task 6.
  - Production extension baseline: model config, selected scenarios, stage endpoints, persisted run artifacts.

- Placeholder scan:
  - No task uses TBD, TODO, or undefined implementation steps.
  - Official Meituan logo is intentionally not embedded because no asset is present; the plan uses a replaceable CSS wordmark.

- Type consistency:
  - `StageRequest`, `RunRequest`, and `ModelConfig` are defined in Task 2 before use.
  - Frontend payload field names match backend request models.
  - `selected_scenario_ids` is consistently named in tests, API, engine, and frontend.

