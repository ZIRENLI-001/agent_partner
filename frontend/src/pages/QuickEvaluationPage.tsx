import { Alert, AutoComplete, Button, Collapse, Input, Select, Tag } from "antd";
import { Play } from "lucide-react";
import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMockEvaluationRows, uploadEvaluationRows } from "../api/imports";
import {
  getRunDetail,
  getRunStatus,
  submitRun,
  type EnrichedFailureEvidence,
  type RunResponse,
  type RunStatusResponse
} from "../api/runs";
import { EvaluationProgress, type EvaluationProgressStage } from "../components/evaluation/EvaluationProgress";
import { SampleLibraryPicker } from "../components/evaluation/SampleLibraryPicker";
import { RunCharts } from "../components/evaluation/RunCharts";
import { ScenarioTraceSwitcher } from "../components/evaluation/ScenarioTraceSwitcher";
import { type CalibrationSample } from "../api/calibration";
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
  { value: "openai/gpt-4o-mini", label: "openai/gpt-4o-mini" }
];

export function QuickEvaluationPage() {
  const [provider, setProvider] = useState("openrouter");
  const [modelName, setModelName] = useState(openRouterModelOptions[0].value);
  const [apiBase, setApiBase] = useState(OPENROUTER_API_BASE);
  const [apiKey, setApiKey] = useState("");
  const [instruction, setInstruction] = useState("");
  const [inputData, setInputData] = useState("");
  const [caseName, setCaseName] = useState("");
  const [csvRows, setCsvRows] = useState<CsvEvaluationRow[]>([]);
  const [importPreview, setImportPreview] = useState("");
  const [minimumScenarios, setMinimumScenarios] = useState(1);
  const [runResult, setRunResult] = useState<RunResponse>();
  const [runStatus, setRunStatus] = useState<RunStatusResponse>();
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void loadMockRows(setCsvRows, applyCsvRow);
  }, []);

  async function runEndToEndEvaluation() {
    setError("");
    setRunResult(undefined);
    setRunStatus(undefined);
    setSaved(false);
    setLoading(true);
    try {
      const submitted = await submitRun({
        instruction,
        input_data: inputData,
        minimum_scenarios: minimumScenarios,
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
      const result = await getRunDetail(submitted.run_id);
      setRunResult(result);
      window.setTimeout(() => {
        document.getElementById("quick-result-output")?.scrollIntoView({ block: "nearest" });
      }, 0);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="viewport-page quick-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">端到端评测</h1>
          <p className="page-subtitle">一次提交后自动完成全链路，适合快速验收数字人模型的外呼效果。</p>
        </div>
        <Button
          className="quick-primary-action"
          loading={loading}
          type="primary"
          icon={<Play size={16} />}
          onClick={runEndToEndEvaluation}
        >
          生成端到端评测报告
        </Button>
      </header>

      {error ? <Alert className="mb-16" type="error" message={error} /> : null}
      {runResult ? (
        <Alert
          className="mb-16"
          type="success"
          showIcon
          message="端到端评测报告已生成"
          description={
            <span>
              Run ID：{runResult.run_id}，
              <Link to={`/runs/${runResult.run_id}`}>查看完整报告</Link>
            </span>
          }
        />
      ) : null}
      {loading && runStatus ? (
        <Alert
          className="mb-16"
          type="info"
          showIcon
          message="端到端评测正在后台生成"
          description={`当前阶段：${currentStageLabel(runStatus)}。页面无需保持请求阻塞，完成后会自动加载报告。`}
        />
      ) : null}

      <div className="quick-grid">
        <main className="surface quick-form">
          <h2>输入配置</h2>
          <div className="form-grid">
            <label>
              Provider
              <Select
                value={provider}
                options={[
                  { value: "openrouter", label: "OpenRouter" },
                  { value: "mock", label: "Mock" },
                  { value: "openai_compatible", label: "OpenAI Compatible" },
                  { value: "internal_gateway", label: "自研模型网关" }
                ]}
                onChange={(value) => {
                  setProvider(value);
                  if (value === "openrouter" && !apiBase) setApiBase(OPENROUTER_API_BASE);
                  if (value === "openrouter") setApiKey("");
                  if (value === "openrouter" && modelName === "smoke-test-model") {
                    setModelName(openRouterModelOptions[0].value);
                  }
                }}
              />
            </label>
            <label>
              模型 ID
              {provider === "openrouter" ? (
                <AutoComplete
                  value={modelName}
                  options={openRouterModelOptions}
                  filterOption={false}
                  onChange={setModelName}
                  placeholder="选择或输入 OpenRouter 模型 ID"
                />
              ) : (
                <Input value={modelName} onChange={(event) => setModelName(event.target.value)} />
              )}
            </label>
            <label>
              API Base
              <Input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder={OPENROUTER_API_BASE} />
            </label>
            <label>
              API Key
              <Input.Password
                value={provider === "openrouter" ? "" : apiKey}
                disabled={provider === "openrouter"}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={provider === "openrouter" ? openrouterBackendKeyHint : "仅用于本次请求"}
              />
              {provider === "openrouter" ? <span className="field-help">{openrouterBackendKeyHint}</span> : null}
            </label>
          </div>
          <div className="form-grid single mt-12">
            <div className="form-field instruction-field">
              <span className="field-label">任务指令</span>
              <div className="inline-tools">
                <Button className="mt-action-button" size="small" onClick={() => fileInputRef.current?.click()}>
                  导入数据
                </Button>
                <input
                  ref={fileInputRef}
                  className="file-input-hidden"
                  type="file"
                  accept=".csv,.tsv,.txt,.json,.jsonl,.xlsx,.xls,text/csv,application/json"
                  onChange={(event) => importCsvFile(event, setCsvRows, applyCsvRow)}
                />
                <SampleLibraryPicker buttonLabel="选择评测样本库" onSelect={applyCalibrationSample} />
                <span className="field-help">
                  支持 CSV / TSV / TXT / JSON / JSONL / Excel：case_name / instruction / input_data。
                </span>
              </div>
              <TextArea
                rows={8}
                value={instruction}
                placeholder="导入数据后自动填入任务指令，也可以在这里粘贴待评测任务指令。"
                onChange={(event) => setInstruction(event.target.value)}
              />
            </div>
            {csvRows.length ? (
              <label>
                样本名称
                <Select
                  value={caseName}
                  options={csvRows.map((row) => ({ value: row.caseName, label: row.caseName }))}
                  onChange={(value) => {
                    const row = csvRows.find((item) => item.caseName === value);
                    if (row) applyCsvRow(row);
                  }}
                />
              </label>
            ) : null}
            <ImportedRowsEditor
              value={importPreview}
              importedCount={csvRows.length}
              onChange={(value) => {
                setImportPreview(value);
                const row = parseImportedPreview(value);
                if (row) applyCsvRow(row, value);
              }}
            />
            <label>
              单条待评测数据
              <span className="field-help">当前样本 JSON。生产中可以由文件或数据集逐条生成评测 run。</span>
              <TextArea
                rows={4}
                value={inputData}
                placeholder='导入数据后自动填入当前样本数据，也可以手动输入 JSON，例如 {"rider_name":"..."}。'
                onChange={(event) => setInputData(event.target.value)}
              />
            </label>
            <label>
              模拟对话数量
              <span className="field-help">
                生成多少种不同用户反应和对话分支；快速模式建议 1-2 个，更多数量适合在分阶段评测中生成。
              </span>
              <Input
                type="number"
                min={1}
                max={5}
                value={minimumScenarios}
                onChange={(event) => setMinimumScenarios(Number(event.target.value))}
              />
            </label>
          </div>
        </main>

        <aside className="surface quick-result" id="quick-result-output">
          <h2>端到端结果</h2>
          {runStatus ? (
            <EvaluationProgress
              title="评测任务进度"
              description={`当前阶段：${currentStageLabel(runStatus)}`}
              stages={runStatusToProgressStages(runStatus)}
            />
          ) : null}
          {!runResult ? (
            <p className="muted">
              {loading
                ? `后台任务生成中：${runStatus ? currentStageLabel(runStatus) : "排队中"}。`
                : "提交后将自动生成指令解析、Rubric、测试场景、对话轨迹和量化报告。"}
            </p>
          ) : (
            <>
              <div className="quick-result-header">
                <div>
                  <strong>报告已生成</strong>
                  <span>{runResult.run_id}</span>
                </div>
                <div className="button-row">
                  <Button className="mt-action-button" size="small" onClick={() => setSaved(true)}>
                    保存到历史评测
                  </Button>
                  <Link to={`/runs/${runResult.run_id}`}>
                    <Button className="mt-action-button" size="small">查看完整报告</Button>
                  </Link>
                </div>
              </div>
              {saved ? <Alert className="mb-16" type="success" message="已保存到历史评测" /> : null}
              <div className="metric-row">
                <Metric label="百分制得分" value={`${runResult.score_summary.normalized_score ?? runResult.score_summary.pass_rate}/100`} />
                <Metric label="场景数" value={runResult.score_summary.scenario_count} />
                <Metric label="失败项" value={runResult.score_summary.failure_count || 0} />
              </div>
              <ScoreReliabilityAlert result={runResult} />
              <RunCharts result={runResult} compact />
              <Collapse
                items={[
                  {
                    key: "dialogue",
                    label: "对话演示",
                    children: <ScenarioTraceSwitcher result={runResult} compact />
                  },
                  {
                    key: "evidence",
                    label: "失败证据",
                    children: <FailureEvidencePanel result={runResult} limit={8} />
                  },
                  {
                    key: "report",
                    label: "Markdown 报告",
                    children: <pre>{runResult.report}</pre>
                  }
                ]}
              />
            </>
          )}
        </aside>
      </div>
    </section>
  );

  function applyCsvRow(row: CsvEvaluationRow, previewText = formatImportedRow(row)) {
    setCaseName(row.caseName);
    if (row.instruction) setInstruction(row.instruction);
    if (row.inputData) setInputData(row.inputData);
    setImportPreview(previewText);
  }

  function applyCalibrationSample(sample: CalibrationSample) {
    const row = calibrationSampleToCsvRow(sample);
    setCsvRows((previous) => upsertEvaluationRow(previous, row));
    applyCsvRow(row, formatImportedRow(row));
  }
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

function runStatusToProgressStages(status: RunStatusResponse): EvaluationProgressStage[] {
  return status.stages
    .filter((stage) => stage.key !== "queued")
    .map((stage) => ({
      key: stage.key,
      name: stage.name,
      status: stage.status
    }));
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

function FailureEvidencePanel({ result, limit }: { result: RunResponse; limit: number }) {
  const failures = collectFailureEvidence(result).slice(0, limit);
  if (!failures.length) return <p className="muted">暂无失败证据。</p>;
  return (
    <div className="failure-card-list">
      {failures.map((item) => (
        <article className="failure-card" key={`${item.scenario_id}-${item.rubric_item_id}`}>
          <div className="failure-card-head">
            <Tag color={item.severity === "critical" ? "red" : "orange"}>{item.scenario_id}</Tag>
            <strong>{item.rubric_item_id}</strong>
            <span>{item.score}/{item.max_score} 分</span>
          </div>
          <dl>
            <dt>评判标准</dt>
            <dd>{item.expected_behavior || item.instruction_quote || item.source}</dd>
            <dt>失败原因</dt>
            <dd>{item.reason}</dd>
            <dt>实际表现</dt>
            <dd>{item.actual_behavior || item.explanation || "暂无实际表现摘要"}</dd>
            <dt>证据轮次</dt>
            <dd>{item.turn_ids.length ? item.turn_ids.join(", ") : "无直接轮次证据"}</dd>
          </dl>
        </article>
      ))}
    </div>
  );
}

function collectFailureEvidence(result: RunResponse): EnrichedFailureEvidence[] {
  const severityByKey = new Map(
    (result.failure_summary || []).map((item) => [
      `${item.scenario_id}-${item.rubric_item_id}`,
      item.severity
    ])
  );
  return (result.results || []).flatMap((evaluation) =>
    (evaluation.evidence || [])
      .filter((item) => item.verdict !== "pass")
      .map((item) => ({
        ...item,
        scenario_id: evaluation.scenario_id,
        severity: severityByKey.get(`${evaluation.scenario_id}-${item.rubric_item_id}`)
      }))
  );
}

function ScoreReliabilityAlert({ result }: { result: RunResponse }) {
  if (result.score_summary.score_reliable !== false) return null;
  return (
    <Alert
      className="mb-16"
      type="warning"
      showIcon
      message="当前百分制分数暂不可单独采信"
      description={
        result.score_summary.score_reliability_reason ||
        "链路质量门禁未通过，请先查看链路健康度、漏评项和证据覆盖。"
      }
    />
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
