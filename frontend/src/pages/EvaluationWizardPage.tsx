import { Alert, AutoComplete, Button, Checkbox, Collapse, Input, Select, Table, Tag } from "antd";
import { Play } from "lucide-react";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMockEvaluationRows, uploadEvaluationRows } from "../api/imports";
import { type CalibrationSample } from "../api/calibration";
import {
  getRunDetail,
  getRunStatus,
  submitRun,
  type RunResponse,
  type RunStatusResponse
} from "../api/runs";
import { EvaluationProgress, type EvaluationProgressStage } from "../components/evaluation/EvaluationProgress";
import { SampleLibraryPicker } from "../components/evaluation/SampleLibraryPicker";
import { RunCharts } from "../components/evaluation/RunCharts";
import { ScenarioTraceSwitcher } from "../components/evaluation/ScenarioTraceSwitcher";
import {
  buildRubric,
  generateScenarios,
  parseInstruction,
  type ParseStageResponse,
  type RubricStageResponse,
  type ScenariosStageResponse
} from "../api/stages";
import { type CsvEvaluationRow } from "../utils/csvImport";

const { TextArea } = Input;

const OPENROUTER_API_BASE = "https://openrouter.ai/api/v1";
const openrouterBackendKeyHint = "使用后端默认 OpenRouter API Key";
const MAX_RUN_POLL_ATTEMPTS = 900;

const openRouterModelOptions = [
  { value: "openai/gpt-4.1-mini", label: "openai/gpt-4.1-mini" },
  { value: "anthropic/claude-sonnet-4.6", label: "anthropic/claude-sonnet-4.6" },
  { value: "google/gemini-2.5-flash", label: "google/gemini-2.5-flash" },
  { value: "qwen/qwen3-max", label: "Qwen3 Max · qwen/qwen3-max" },
  { value: "qwen/qwen3-max-thinking", label: "Qwen3 Max Thinking · qwen/qwen3-max-thinking" },
  { value: "qwen/qwen3-235b-a22b", label: "Qwen3 235B A22B · qwen/qwen3-235b-a22b" },
  { value: "deepseek/deepseek-chat", label: "DeepSeek Chat · deepseek/deepseek-chat" },
  { value: "deepseek/deepseek-r1", label: "DeepSeek R1 · deepseek/deepseek-r1" },
  { value: "deepseek/deepseek-chat-v3.1", label: "DeepSeek V3.1 · deepseek/deepseek-chat-v3.1" },
  { value: "openai/gpt-4o-mini", label: "openai/gpt-4o-mini" },
  { value: "google/gemini-2.0-flash-001", label: "google/gemini-2.0-flash-001" }
];

const defaultOpenRouterModel = openRouterModelOptions[0].value;

type StepKey = "model" | "data" | "parse" | "rubric" | "scenarios" | "run" | "report";

const stepItems: { key: StepKey; title: string }[] = [
  { key: "model", title: "模型配置" },
  { key: "data", title: "样本导入" },
  { key: "parse", title: "指令解析" },
  { key: "rubric", title: "Rubric 生成" },
  { key: "scenarios", title: "对话模拟" },
  { key: "run", title: "执行评测" },
  { key: "report", title: "报告分析" }
];

const regeneratableSteps: StepKey[] = ["parse", "rubric", "scenarios", "run"];

const stageDescriptions: Record<StepKey, string> = {
  model: "配置被测模型和 API 连接方式",
  data: "导入指令、变量和样本数据",
  parse: "抽取任务目标、流程与约束",
  rubric: "生成可判定的评分标准",
  scenarios: "模拟不同用户反应与风险分支",
  run: "执行对话轨迹和自动判分",
  report: "检查最终量化指标和失败证据"
};

const sampleInstruction = `# Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。
3. 尽量挽留不想配送的骑手。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的飞毛腿报名中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。`;

export function EvaluationWizardPage() {
  const [activeStep, setActiveStep] = useState<StepKey>("model");
  const [provider, setProvider] = useState("openrouter");
  const [modelName, setModelName] = useState(defaultOpenRouterModel);
  const [apiBase, setApiBase] = useState(OPENROUTER_API_BASE);
  const [apiKey, setApiKey] = useState("");
  const [instruction, setInstruction] = useState(sampleInstruction);
  const [inputData, setInputData] = useState('{"city":"北京","scene":"履约外呼"}');
  const [caseName, setCaseName] = useState("默认样本");
  const [csvRows, setCsvRows] = useState<CsvEvaluationRow[]>([]);
  const [importPreview, setImportPreview] = useState("");
  const [minimumScenarios, setMinimumScenarios] = useState(5);
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [parseResult, setParseResult] = useState<ParseStageResponse>();
  const [rubricResult, setRubricResult] = useState<RubricStageResponse>();
  const [scenarioResult, setScenarioResult] = useState<ScenariosStageResponse>();
  const [runResult, setRunResult] = useState<RunResponse>();
  const [runStatus, setRunStatus] = useState<RunStatusResponse>();
  const [stageAdjustments, setStageAdjustments] = useState<Record<StepKey, string>>({
    model: "",
    data: "",
    parse: "",
    rubric: "",
    scenarios: "",
    run: "",
    report: ""
  });
  const [saved, setSaved] = useState(false);
  const [generatedSteps, setGeneratedSteps] = useState<Set<StepKey>>(new Set());
  const [dirtySteps, setDirtySteps] = useState<Set<StepKey>>(new Set(["model"]));
  const [maxVisitedIndex, setMaxVisitedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeIndex = stepItems.findIndex((item) => item.key === activeStep);
  const isGenerated = isStepGenerated(activeStep);
  const canRegenerateActiveStep = regeneratableSteps.includes(activeStep);
  const primaryActionLabel = getPrimaryActionLabel();
  const primaryActionFeedbackLabel = loading ? getLoadingActionLabel() : primaryActionLabel;
  const scenarios = scenarioResult?.scenario_set.scenarios || [];
  const wizardProgressStages = stepItems.map((item, index) => ({
    key: item.key,
    name: item.title,
    description: stageDescriptions[item.key],
    status: wizardStepProgressStatus(item.key, index)
  }));
  const selectedScenarios = selectedScenarioIds;

  const stagePayload = useMemo(
    () => ({
      instruction,
      input_data: stageAdjustments[activeStep].trim()
        ? `${inputData}\n\n# ${stepItems[activeIndex].title}自定义修改\n${stageAdjustments[activeStep].trim()}`
        : inputData,
      minimum_scenarios: minimumScenarios
    }),
    [activeIndex, activeStep, instruction, inputData, minimumScenarios, stageAdjustments]
  );

  useEffect(() => {
    void loadMockRows(setCsvRows, applyImportedRow);
  }, []);

  function applyImportedRow(row: CsvEvaluationRow, previewText = formatImportedRow(row)) {
    setCaseName(row.caseName);
    if (row.instruction) setInstruction(row.instruction);
    if (row.inputData) setInputData(row.inputData);
    setImportPreview(previewText);
    resetGeneratedFrom("data");
  }

  function applyCalibrationSample(sample: CalibrationSample) {
    const row = calibrationSampleToCsvRow(sample);
    setCsvRows((previous) => upsertEvaluationRow(previous, row));
    applyImportedRow(row, formatImportedRow(row));
  }

  function resetGeneratedFrom(step: StepKey) {
    const stepIndex = stepItems.findIndex((item) => item.key === step);
    const affectedSteps = stepItems.slice(stepIndex).map((item) => item.key);
    setGeneratedSteps((previous) => {
      const next = new Set(previous);
      affectedSteps.forEach((item) => next.delete(item));
      return next;
    });
    setDirtySteps((previous) => new Set(previous).add(step));
    clearStageResultsFrom(step);
  }

  function markStepGenerated(step: StepKey) {
    setGeneratedSteps((previous) => new Set(previous).add(step));
    setDirtySteps((previous) => {
      const next = new Set(previous);
      next.delete(step);
      return next;
    });
  }

  function markStepDirty(step: StepKey) {
    resetGeneratedFrom(step);
  }

  function markStepResultEdited(step: StepKey) {
    const stepIndex = stepItems.findIndex((item) => item.key === step);
    const downstreamSteps = stepItems.slice(stepIndex + 1).map((item) => item.key);
    setGeneratedSteps((previous) => {
      const next = new Set(previous);
      next.add(step);
      downstreamSteps.forEach((item) => next.delete(item));
      return next;
    });
    setDirtySteps((previous) => {
      const next = new Set(previous);
      next.delete(step);
      downstreamSteps.forEach((item) => next.add(item));
      return next;
    });
    clearStageResultsAfter(step);
  }

  function clearStageResultsFrom(step: StepKey) {
    const stepIndex = stepItems.findIndex((item) => item.key === step);
    if (stepIndex <= stepItems.findIndex((item) => item.key === "parse")) setParseResult(undefined);
    if (stepIndex <= stepItems.findIndex((item) => item.key === "rubric")) setRubricResult(undefined);
    if (stepIndex <= stepItems.findIndex((item) => item.key === "scenarios")) {
      setScenarioResult(undefined);
      setSelectedScenarioIds([]);
    }
    if (stepIndex <= stepItems.findIndex((item) => item.key === "run")) {
      setRunResult(undefined);
      setRunStatus(undefined);
      setSaved(false);
    }
  }

  function clearStageResultsAfter(step: StepKey) {
    const nextStep = stepItems[stepItems.findIndex((item) => item.key === step) + 1];
    if (nextStep) clearStageResultsFrom(nextStep.key);
  }

  function updateStageAdjustment(step: StepKey, value: string) {
    setStageAdjustments((previous) => ({ ...previous, [step]: value }));
    resetGeneratedFrom(step);
  }

  function isStepGenerated(step: StepKey) {
    if (step === "report") return generatedSteps.has("report");
    return generatedSteps.has(step) && !dirtySteps.has(step);
  }

  function isStepProgressCompleted(step: StepKey, index: number) {
    return stepItems.slice(0, index + 1).every((item) => isStepGenerated(item.key)) && isStepGenerated(step);
  }

  function getPrimaryActionLabel() {
    if (dirtySteps.has(activeStep) && generatedSteps.has(activeStep)) return "调整后重新生成";
    if (isGenerated && activeIndex < stepItems.length - 1) return "进入下一步";
    if (activeStep === "report" && isGenerated) return "完成评测";
    return "生成当前步骤";
  }

  function getLoadingActionLabel() {
    if (activeStep === "run") return "正在执行评测";
    return "正在生成当前步骤";
  }

  function getStepDescription(step: StepKey, index: number) {
    if (step === activeStep) return "当前步骤";
    if (dirtySteps.has(step) && generatedSteps.has(step)) return "已调整，需重新生成";
    if (isStepGenerated(step)) return "已生成";
    if (index <= maxVisitedIndex) return "未开始";
    return "未到达";
  }

  function wizardStepProgressStatus(step: StepKey, index: number): EvaluationProgressStage["status"] {
    if (loading && step === activeStep) return "running";
    if (dirtySteps.has(step) && generatedSteps.has(step)) return "running";
    if (isStepProgressCompleted(step, index)) return "completed";
    if (index <= maxVisitedIndex) return "pending";
    return "pending";
  }

  function goToStep(index: number) {
    if (index <= maxVisitedIndex) setActiveStep(stepItems[index].key);
  }

  function advanceToNextStep() {
    const next = stepItems[activeIndex + 1];
    if (!next) return;
    setActiveStep(next.key);
    setMaxVisitedIndex((value) => Math.max(value, activeIndex + 1));
  }

  async function handlePrimaryAction() {
    if (isGenerated && activeIndex < stepItems.length - 1) {
      advanceToNextStep();
      return;
    }
    await generateCurrentStep();
  }

  async function regenerateActiveStep() {
    if (!canRegenerateActiveStep) return;
    resetGeneratedFrom(activeStep);
    await generateCurrentStep();
  }

  function handleQualityRemediation(stage: string) {
    const target = stepItems.find((item) => item.key === stage)?.key;
    if (!target) return;
    const targetIndex = stepItems.findIndex((item) => item.key === target);
    setActiveStep(target);
    setMaxVisitedIndex((value) => Math.max(value, targetIndex));
    if (regeneratableSteps.includes(target)) {
      resetGeneratedFrom(target);
    }
  }

  async function generateCurrentStep() {
    setError("");
    setLoading(true);
    try {
      if (activeStep === "model") {
        markStepGenerated("model");
        return;
      }
      if (activeStep === "data") {
        markStepGenerated("data");
        return;
      }
      if (activeStep === "parse") {
        setParseResult(await parseInstruction(stagePayload));
        markStepGenerated("parse");
        return;
      }
      if (activeStep === "rubric") {
        setRubricResult(await buildRubric(stagePayload));
        markStepGenerated("rubric");
        return;
      }
      if (activeStep === "scenarios") {
        const result = await generateScenarios(stagePayload);
        setScenarioResult(result);
        setSelectedScenarioIds(result.scenario_set.scenarios.map((item) => item.scenario_id));
        markStepGenerated("scenarios");
        return;
      }
      if (activeStep === "run") {
        if (!parseResult || !rubricResult || !scenarioResult) {
          throw new Error("Please generate parse, rubric, and scenarios before running.");
        }
        const selectedScenarioSet = new Set(selectedScenarios);
        const confirmedScenarioSet = {
          ...scenarioResult.scenario_set,
          scenarios: scenarioResult.scenario_set.scenarios.filter((scenario) =>
            selectedScenarioSet.has(scenario.scenario_id)
          )
        };
        if (!confirmedScenarioSet.scenarios.length) {
          throw new Error("No selected scenarios are available for evaluation.");
        }
        setRunStatus(undefined);
        const submitted = await submitRun({
          instruction,
          input_data: stagePayload.input_data,
          minimum_scenarios: minimumScenarios,
          selected_scenario_ids: confirmedScenarioSet.scenarios.map((scenario) => scenario.scenario_id),
          task_spec: parseResult.task_spec,
          rubric_spec: rubricResult.rubric_spec,
          scenario_set: confirmedScenarioSet,
          model_config: {
            provider,
            model_name: modelName,
            api_base: apiBase,
            api_key: apiKey
          }
        });
        const finalStatus = await pollRunStatus(submitted.run_id, setRunStatus);
        if (finalStatus.status === "failed") {
          throw new Error(finalStatus.error || "评测任务执行失败");
        }
        setRunResult(await getRunDetail(submitted.run_id));
        setSaved(false);
        markStepGenerated("run");
        return;
      }
      if (activeStep === "report" && runResult) {
        markStepGenerated("report");
        return;
      }
      if (activeStep === "report" && !runResult) {
        setError("请先在执行评测阶段生成评测运行。");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="viewport-page evaluation-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">分阶段评测</h1>
          <p className="page-subtitle">
            逐阶段生成、检查和调整评测链路，再进入下一阶段运行与报告分析。
          </p>
        </div>
        <div className="button-row">
          <Button
            className="evaluation-primary-action"
            loading={loading}
            disabled={loading}
            type="primary"
            icon={<Play size={16} />}
            onClick={handlePrimaryAction}
          >
            {primaryActionFeedbackLabel}
          </Button>
        </div>
      </header>

      {error ? <Alert className="mb-16" type="error" message={error} /> : null}
      {runStatus && activeStep === "run" && !runResult ? (
        <Alert
          className="mb-16"
          type="info"
          showIcon
          message={`后台任务生成中：${currentStageLabel(runStatus)}`}
        />
      ) : null}

      <div className="evaluation-grid">
        <aside className="surface">
          <EvaluationProgress
            title="阶段评测进度"
            description={`${stepItems[activeIndex].title} · ${getStepDescription(activeStep, activeIndex)}`}
            stages={wizardProgressStages}
            onStageClick={goToStep}
            isStageDisabled={(index) => index > maxVisitedIndex}
          />
        </aside>
        <main className="surface evaluation-stage">
          <div className="stage-action-bar">
            <div>
              <span className="eyebrow">当前阶段</span>
              <strong>{stepItems[activeIndex].title}</strong>
            </div>
            {canRegenerateActiveStep ? (
              <Button
                className="mt-action-button"
                disabled={loading}
                loading={loading}
                onClick={regenerateActiveStep}
              >
                重新生成当前步骤
              </Button>
            ) : null}
          </div>
          {activeStep === "model" ? (
            <ModelForm
              provider={provider}
              setProvider={setProvider}
              modelName={modelName}
              setModelName={setModelName}
              apiBase={apiBase}
              setApiBase={setApiBase}
              apiKey={apiKey}
              setApiKey={setApiKey}
              onChange={() => resetGeneratedFrom("model")}
            />
          ) : null}
          {activeStep === "data" ? (
            <DataForm
              instruction={instruction}
              inputData={inputData}
              caseName={caseName}
              csvRows={csvRows}
              importPreview={importPreview}
              minimumScenarios={minimumScenarios}
              setInstruction={(value) => {
                setInstruction(value);
                resetGeneratedFrom("data");
              }}
              setInputData={(value) => {
                setInputData(value);
                resetGeneratedFrom("data");
              }}
              setCaseName={setCaseName}
              setCsvRows={setCsvRows}
              setImportPreview={setImportPreview}
              setMinimumScenarios={setMinimumScenarios}
              applyImportedRow={applyImportedRow}
              applyCalibrationSample={applyCalibrationSample}
              fileInputRef={fileInputRef}
            />
          ) : null}
          {activeStep === "parse" ? (
            <>
              <StageAdjustment value={stageAdjustments.parse} onChange={(value) => updateStageAdjustment("parse", value)} />
              <ParseResult
                result={parseResult}
                onResultChange={(value) => {
                  setParseResult(value);
                  markStepResultEdited("parse");
                }}
              />
            </>
          ) : null}
          {activeStep === "rubric" ? (
            <>
              <StageAdjustment value={stageAdjustments.rubric} onChange={(value) => updateStageAdjustment("rubric", value)} />
              <RubricResult
                result={rubricResult}
                onResultChange={(value) => {
                  setRubricResult(value);
                  markStepResultEdited("rubric");
                }}
              />
            </>
          ) : null}
          {activeStep === "scenarios" ? (
            <>
              <StageAdjustment value={stageAdjustments.scenarios} onChange={(value) => updateStageAdjustment("scenarios", value)} />
              <ScenarioResult
                result={scenarioResult}
                selectedScenarioIds={selectedScenarioIds}
                setSelectedScenarioIds={setSelectedScenarioIds}
                onResultChange={(value) => {
                  setScenarioResult(value);
                  setSelectedScenarioIds(value.scenario_set.scenarios.map((item) => item.scenario_id));
                  markStepResultEdited("scenarios");
                }}
              />
            </>
          ) : null}
          {activeStep === "run" ? (
            <>
              <StageAdjustment value={stageAdjustments.run} onChange={(value) => updateStageAdjustment("run", value)} />
              <RunResult
                result={runResult}
                saved={saved}
                onSave={() => setSaved(true)}
                onRemediate={handleQualityRemediation}
              />
            </>
          ) : null}
          {activeStep === "report" ? (
            <>
              <StageAdjustment value={stageAdjustments.report} onChange={(value) => updateStageAdjustment("report", value)} />
              <ReportResult result={runResult} onRemediate={handleQualityRemediation} />
            </>
          ) : null}
        </main>
      </div>
    </section>
  );
}

async function pollRunStatus(
  runId: string,
  onStatus: (status: RunStatusResponse) => void
) {
  let latest = await getRunStatus(runId);
  onStatus(latest);
  for (let attempt = 0; attempt < MAX_RUN_POLL_ATTEMPTS; attempt += 1) {
    if (latest.status === "completed" || latest.status === "failed") {
      return latest;
    }
    await delay(1000);
    latest = await getRunStatus(runId);
    onStatus(latest);
  }
  throw new Error("后台任务仍在运行，已超过 15 分钟。请稍后在历史评测中查看结果。");
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function currentStageLabel(status: RunStatusResponse) {
  const active = status.stages.find((stage) => stage.key === status.current_stage);
  return active?.name || status.current_stage || status.status;
}

function ModelForm(props: {
  provider: string;
  setProvider: (value: string) => void;
  modelName: string;
  setModelName: (value: string) => void;
  apiBase: string;
  setApiBase: (value: string) => void;
  apiKey: string;
  setApiKey: (value: string) => void;
  onChange: () => void;
}) {
  return (
    <div>
      <h2>模型配置</h2>
      <h3>被测模型</h3>
      <div className="form-grid">
        <label>
          Provider
          <Select
            value={props.provider}
            options={[
              { value: "openrouter", label: "OpenRouter" },
              { value: "mock", label: "Mock" },
              { value: "openai_compatible", label: "OpenAI Compatible" },
              { value: "internal_gateway", label: "自研模型网关" }
            ]}
            onChange={(value) => {
              props.setProvider(value);
              if (value === "openrouter" && !props.apiBase) {
                props.setApiBase(OPENROUTER_API_BASE);
              }
              if (value === "openrouter") {
                props.setApiKey("");
              }
              if (value === "openrouter" && (!props.modelName || props.modelName === "smoke-test-model")) {
                props.setModelName(defaultOpenRouterModel);
              }
              props.onChange();
            }}
          />
        </label>
        {props.provider === "openrouter" ? (
          <label>
            OpenRouter 模型 ID
            <AutoComplete
              value={props.modelName}
              options={openRouterModelOptions}
              filterOption={false}
              onChange={(value) => {
                props.setModelName(value);
                props.onChange();
              }}
              placeholder="例如 openai/gpt-4.1-mini，也可手动输入 OpenRouter 模型 ID"
            />
          </label>
        ) : (
          <label>
            模型名称
            <Input
              value={props.modelName}
              onChange={(event) => {
                props.setModelName(event.target.value);
                props.onChange();
              }}
              placeholder="openai/gpt-4o 或 internal-fulfillment-v1"
            />
          </label>
        )}
        <label>
          API Base
          <Input
            value={props.apiBase}
            onChange={(event) => {
              props.setApiBase(event.target.value);
              props.onChange();
            }}
            placeholder="https://openrouter.ai/api/v1"
          />
        </label>
        <label>
          API Key
          <Input.Password
            value={props.provider === "openrouter" ? "" : props.apiKey}
            disabled={props.provider === "openrouter"}
            onChange={(event) => {
              props.setApiKey(event.target.value);
              props.onChange();
            }}
            placeholder={props.provider === "openrouter" ? openrouterBackendKeyHint : "仅用于本次请求，不在报告中明文展示"}
          />
          {props.provider === "openrouter" ? <span className="field-help">{openrouterBackendKeyHint}</span> : null}
        </label>
      </div>
    </div>
  );
}

function DataForm(props: {
  instruction: string;
  inputData: string;
  caseName: string;
  csvRows: CsvEvaluationRow[];
  importPreview: string;
  minimumScenarios: number;
  setInstruction: (value: string) => void;
  setInputData: (value: string) => void;
  setCaseName: (value: string) => void;
  setCsvRows: (value: CsvEvaluationRow[]) => void;
  setImportPreview: (value: string) => void;
  setMinimumScenarios: (value: number) => void;
  applyImportedRow: (row: CsvEvaluationRow, previewText?: string) => void;
  applyCalibrationSample: (sample: CalibrationSample) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
}) {
  function applyCsvRow(row: CsvEvaluationRow, previewText = formatImportedRow(row)) {
    props.applyImportedRow(row, previewText);
  }

  return (
    <div>
      <h2>样本导入</h2>
      <p className="muted">评测对象是一条条骑手/用户样本，系统会围绕当前样本生成多种对话场景。</p>
      <div className="form-grid single">
        <div className="form-field instruction-field">
          <span className="field-label">任务指令</span>
          <div className="inline-tools">
            <Button className="mt-action-button" size="small" onClick={() => props.fileInputRef.current?.click()}>
              导入数据
            </Button>
            <input
              ref={props.fileInputRef}
              className="file-input-hidden"
              type="file"
              accept=".csv,.tsv,.txt,.json,.jsonl,.xlsx,.xls,text/csv,application/json"
              onChange={(event) => importCsvFile(event, props.setCsvRows, applyCsvRow)}
            />
            <SampleLibraryPicker buttonLabel="选择评测样本库" onSelect={props.applyCalibrationSample} />
            <span className="field-help">
              支持 CSV / TSV / TXT / JSON / JSONL / Excel：case_name / instruction / input_data。
            </span>
          </div>
          <TextArea rows={12} value={props.instruction} onChange={(event) => props.setInstruction(event.target.value)} />
        </div>
        {props.csvRows.length ? (
          <label>
            样本名称
            <Select
              value={props.caseName}
              options={props.csvRows.map((row) => ({ value: row.caseName, label: row.caseName }))}
              onChange={(value) => {
                const row = props.csvRows.find((item) => item.caseName === value);
                if (row) applyCsvRow(row);
              }}
            />
          </label>
        ) : null}
        <ImportedRowsEditor
          value={props.importPreview}
          importedCount={props.csvRows.length}
          onChange={(value) => {
            props.setImportPreview(value);
            const row = parseImportedPreview(value);
            if (row) applyCsvRow(row, value);
          }}
        />
        <label>
          单条待评测数据
          <span className="field-help">当前样本 JSON，可替换为骑手状态、城市、报名/履约上下文等字段。</span>
          <TextArea rows={5} value={props.inputData} onChange={(event) => props.setInputData(event.target.value)} />
        </label>
        <label>
          模拟对话数量
          <span className="field-help">
            生成多少种不同用户反应和对话分支；数量越多覆盖越充分，但生成耗时也会增加。
          </span>
          <Input
            type="number"
            min={1}
            max={20}
            value={props.minimumScenarios}
            onChange={(event) => props.setMinimumScenarios(Number(event.target.value))}
          />
        </label>
      </div>
    </div>
  );
}

async function importCsvFile(
  event: ChangeEvent<HTMLInputElement>,
  setRows: (rows: CsvEvaluationRow[]) => void,
  applyRow: (row: CsvEvaluationRow) => void
) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const response = await uploadEvaluationRows(file);
    setRows(response.rows);
    if (response.rows[0]) applyRow(response.rows[0]);
  } catch (error) {
    window.alert(error instanceof Error ? error.message : String(error));
  }
  event.target.value = "";
}

async function loadMockRows(
  setRows: (rows: CsvEvaluationRow[]) => void,
  applyRow: (row: CsvEvaluationRow) => void
) {
  try {
    const response = await fetchMockEvaluationRows();
    setRows(response.rows);
    if (response.rows[0]) applyRow(response.rows[0]);
  } catch (error) {
    console.warn("加载官方 mock 样本失败", error);
  }
}

function ImportedRowsEditor(props: { value: string; importedCount: number; onChange: (value: string) => void }) {
  return (
    <label className="import-preview-editor">
      导入内容预览
      <span className="field-help">
        {props.importedCount
          ? `已导入 ${props.importedCount} 条样本。可复制，也可直接编辑 JSON 后同步到下方评测字段。`
          : "导入后将在这里显示首条样本内容，也可直接粘贴 JSON 编辑。"}
      </span>
      <TextArea
        rows={5}
        value={props.value}
        placeholder='导入后将在这里显示，例如：{"caseName":"样本1","instruction":"...","inputData":"..."}'
        onChange={(event) => props.onChange(event.target.value)}
      />
    </label>
  );
}

function formatImportedRow(row: CsvEvaluationRow) {
  return JSON.stringify(row, null, 2);
}

function parseImportedPreview(value: string): CsvEvaluationRow | null {
  try {
    const parsed = JSON.parse(value) as Partial<CsvEvaluationRow>;
    if (!parsed || typeof parsed !== "object") return null;
    return {
      caseName: parsed.caseName || "导入样本",
      instruction: parsed.instruction || "",
      inputData: parsed.inputData || ""
    };
  } catch {
    return null;
  }
}

function calibrationSampleToCsvRow(sample: CalibrationSample): CsvEvaluationRow {
  return {
    caseName: sample.sample_id,
    instruction: sample.task_instruction,
    inputData: JSON.stringify(sample.input_variables, null, 2)
  };
}

function upsertEvaluationRow(rows: CsvEvaluationRow[], row: CsvEvaluationRow) {
  const existingIndex = rows.findIndex((item) => item.caseName === row.caseName);
  if (existingIndex < 0) {
    return [row, ...rows];
  }
  return rows.map((item, index) => (index === existingIndex ? row : item));
}

function StageAdjustment(props: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="stage-adjustment">
      <label>
        当前步骤自定义修改
        <TextArea
          rows={3}
          value={props.value}
          onChange={(event) => props.onChange(event.target.value)}
          placeholder="例如：增加骑手追问合同退出规则的场景；Rubric 加强话术长度约束；对话演示优先看拒绝配送分支。"
        />
      </label>
      <p className="muted">环节调整说明会随当前步骤请求提交。修改说明后点击“生成 / 调整后重新生成”，当前环节会基于调整重新产出结果。</p>
    </div>
  );
}

function ParseResult({
  result,
  onResultChange
}: {
  result?: ParseStageResponse;
  onResultChange: (value: ParseStageResponse) => void;
}) {
  if (!result) return <EmptyStage title="指令解析" />;
  const task = result.task_spec;
  return (
    <div className="result-section">
      <h2>指令解析结果</h2>
      <p className="muted">结构化摘要</p>
      <div className="summary-grid">
        <Metric label="任务名称" value={String(task.task_name || "-")} />
        <Metric label="目标用户" value={String(task.target_user || "-")} />
        <Metric label="流程步骤" value={Array.isArray(task.required_steps) ? task.required_steps.length : 0} />
      </div>
      <EditableJsonResult title="TaskSpec JSON" payload={result} onChange={onResultChange} />
    </div>
  );
}

function RubricResult({
  result,
  onResultChange
}: {
  result?: RubricStageResponse;
  onResultChange: (value: RubricStageResponse) => void;
}) {
  const items = Array.isArray(result?.rubric_spec.items)
    ? (result?.rubric_spec.items as Record<string, unknown>[])
    : [];
  return (
    <div className="result-section">
      <h2>Rubric 生成</h2>
      <p className="muted">评分项数量：{items.length}</p>
      <Table
        className="rubric-table"
        size="small"
        rowKey={(record) => String(record.item_id)}
        dataSource={items}
        pagination={false}
        columns={[
          { title: "评分项", dataIndex: "item_id" },
          { title: "维度", dataIndex: "dimension" },
          { title: "权重", dataIndex: "weight" },
          {
            title: "依据",
            dataIndex: "source",
            render: (value) => <Tag>{String(value)}</Tag>
          }
        ]}
      />
      {result ? <EditableJsonResult title="Rubric JSON" payload={result} onChange={onResultChange} /> : null}
    </div>
  );
}

function ScenarioResult(props: {
  result?: ScenariosStageResponse;
  selectedScenarioIds: string[];
  setSelectedScenarioIds: (value: string[]) => void;
  onResultChange: (value: ScenariosStageResponse) => void;
}) {
  const result = props.result;
  const scenarios = result?.scenario_set.scenarios || [];
  if (!result || !scenarios.length) return <EmptyStage title="对话模拟" />;
  return (
    <div>
      <h2>场景覆盖</h2>
      <Checkbox.Group
        className="scenario-list"
        value={props.selectedScenarioIds}
        onChange={(value) => props.setSelectedScenarioIds(value.map(String))}
      >
        {scenarios.map((scenario) => (
          <label className="scenario-card" key={scenario.scenario_id}>
            <Checkbox value={scenario.scenario_id} />
            <strong>{scenario.scenario_id}</strong>
            <span>{scenario.expected_test_focus}</span>
            <div>
              {scenario.coverage_targets.map((target) => (
                <Tag key={target}>{target}</Tag>
              ))}
            </div>
          </label>
        ))}
      </Checkbox.Group>
      <EditableJsonResult title="场景 JSON" payload={result} onChange={props.onResultChange} />
    </div>
  );
}

function RunResult({
  result,
  saved,
  onSave,
  onRemediate
}: {
  result?: RunResponse;
  saved: boolean;
  onSave: () => void;
  onRemediate: (stage: string) => void;
}) {
  if (!result) return <EmptyStage title="执行评测" />;
  return (
    <div className="result-section trace-preview">
      <div className="sample-section-head">
        <h2>对话轨迹</h2>
        <span>{result.run_id}</span>
      </div>
      <div className="metric-row">
        <Metric label="Trace" value={result.trace_count} />
        <Metric label="Result" value={result.result_count} />
        <Metric label="百分制得分" value={`${result.score_summary.normalized_score ?? result.score_summary.pass_rate}/100`} />
      </div>
      <ScoreReliabilityAlert result={result} onRemediate={onRemediate} />
      <div className="button-row">
        <Button className="mt-action-button" onClick={onSave}>保存到历史评测</Button>
        <Link to={`/runs/${result.run_id}`}>
          <Button className="mt-action-button">查看完整报告</Button>
        </Link>
        <Link to="/history">
          <Button>返回历史评测</Button>
        </Link>
        {saved ? <Tag color="green">已保存到历史评测</Tag> : null}
      </div>
      <ScenarioTraceSwitcher result={result} compact />
    </div>
  );
}

function ReportResult({
  result,
  onRemediate
}: {
  result?: RunResponse;
  onRemediate: (stage: string) => void;
}) {
  if (!result) return <EmptyStage title="报告分析" />;
  return (
    <div className="result-section">
      <div className="sample-section-head">
        <h2>评分证据</h2>
        <div className="button-row">
          <Link to={`/runs/${result.run_id}`}>
            <Button className="mt-action-button" size="small">查看完整报告</Button>
          </Link>
          <Link to="/history">
            <Button size="small">返回历史评测</Button>
          </Link>
        </div>
      </div>
      <div className="metric-row">
        <Metric label="百分制得分" value={`${result.score_summary.normalized_score ?? result.score_summary.pass_rate}/100`} />
        <Metric label="总分" value={`${result.score_summary.total_score}/${result.score_summary.possible_score}`} />
        <Metric label="失败项" value={result.score_summary.failure_count || 0} />
        <Metric label="高风险项" value={result.score_summary.critical_failure_count || 0} />
      </div>
      <ScoreReliabilityAlert result={result} onRemediate={onRemediate} />
      <QualitySummaryPanel result={result} />
      <RunCharts result={result} compact />
      <Collapse
        items={[
          {
            key: "dialogue",
            label: "对话场景切换",
            children: <ScenarioTraceSwitcher result={result} compact />
          }
        ]}
      />
      <Collapse
        items={[
          {
            key: "dimensions",
            label: "维度分",
            children: (
              <div className="evidence-list">
                {result.dimension_summary.map((item) => (
                  <p key={item.dimension}>
                    <strong>{item.dimension}</strong>：{item.score}/{item.possible_score}（{item.pass_rate}%）
                  </p>
                ))}
              </div>
            )
          },
          {
            key: "failures",
            label: "失败证据",
            children: (
              <div className="evidence-list">
                {result.failure_summary.slice(0, 12).map((item) => (
                  <p key={`${item.scenario_id}-${item.rubric_item_id}`}>
                    <strong>{item.scenario_id}</strong> · {item.rubric_item_id}：{item.reason}
                  </p>
                ))}
              </div>
            )
          },
          {
            key: "markdown",
            label: "Markdown 报告",
            children: <pre>{result.report}</pre>
          }
        ]}
      />
    </div>
  );
}

function EmptyStage({ title }: { title: string }) {
  return (
    <div>
      <h2>{title}</h2>
      <p className="muted">点击“生成当前步骤”后展示当前步骤结果。</p>
    </div>
  );
}

function EditableJsonResult<T>({ title, payload, onChange }: { title: string; payload: T; onChange: (value: T) => void }) {
  const [draft, setDraft] = useState(() => JSON.stringify(payload, null, 2));
  const [error, setError] = useState("");

  useEffect(() => {
    setDraft(JSON.stringify(payload, null, 2));
    setError("");
  }, [payload]);

  function updateDraft(value: string) {
    setDraft(value);
    try {
      onChange(JSON.parse(value) as T);
      setError("");
    } catch {
      setError("JSON 暂未解析成功，修正格式后会自动同步。");
    }
  }

  return (
    <div className="json-result editable-json-result">
      <h3>{title}</h3>
      <TextArea
        rows={10}
        value={draft}
        onChange={(event) => updateDraft(event.target.value)}
      />
      <p className={error ? "field-error" : "muted"}>
        {error || "可直接修改当前步骤产物；保存为有效 JSON 后，后续步骤会标记为需要重新生成。"}
      </p>
    </div>
  );
}

function ScoreReliabilityAlert({
  result,
  onRemediate
}: {
  result: RunResponse;
  onRemediate?: (stage: string) => void;
}) {
  if (result.score_summary.score_reliable !== false) return null;
  const actions = result.quality_summary?.remediation_actions || [];
  return (
    <Alert
      className="mb-16"
      type="warning"
      showIcon
      message="当前百分制分数暂不可单独采信"
      description={
        <div className="quality-remediation">
          <p>
            {result.score_summary.score_reliability_reason ||
              "链路质量门禁未通过，请先查看链路健康度、漏评项和证据覆盖。"}
          </p>
          {actions.length ? (
            <>
              <strong>质量门禁建议</strong>
              <div className="button-row">
                {actions.slice(0, 3).map((action) => (
                  <Button
                    key={`${action.stage}-${action.action}`}
                    size="small"
                    onClick={() => onRemediate?.(action.stage)}
                  >
                    {action.action}
                  </Button>
                ))}
              </div>
              <ul>
                {actions.slice(0, 3).map((action) => (
                  <li key={`${action.stage}-${action.reason}`}>{action.reason}</li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      }
    />
  );
}

function QualitySummaryPanel({ result }: { result: RunResponse }) {
  const quality_summary = result.quality_summary;
  const autoRepair = quality_summary?.auto_repair;
  return (
    <section className="report-section">
      <h2>链路健康度</h2>
      {autoRepair?.attempted ? (
        <Alert
          className="mb-16"
          type={autoRepair.after_status === "pass" ? "success" : "info"}
          showIcon
          message="后端自动修复"
          description={`已自动重试 ${autoRepair.attempt_count ?? 0} 次：${autoRepair.before_status || "unknown"} -> ${autoRepair.after_status || "unknown"}`}
        />
      ) : null}
      <div className="metric-row">
        <Metric label="链路状态" value={quality_summary?.overall_status || "unknown"} />
        <Metric
          label="证据命中"
          value={`${quality_summary?.evidence_traceability?.traceable_evidence_rate ?? 0}%`}
        />
        <Metric
          label="Judge 漏项"
          value={quality_summary?.judge_integrity?.missing_item_count ?? 0}
        />
        <Metric
          label="场景多样性"
          value={quality_summary?.scenario_coverage?.diversity_score ?? 0}
        />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
