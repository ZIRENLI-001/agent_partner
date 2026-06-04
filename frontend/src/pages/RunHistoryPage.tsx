import { Alert, Button, Collapse, Input, Progress, Segmented, Select, Table, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import {
  getRunComparison,
  getRunHistory,
  type ComparisonScenarioRow,
  type FailureReasonSummary,
  type OptimizationInsight,
  type RunSummary
} from "../api/runs";

type ComparisonMode = "scenario" | "model";

export function RunHistoryPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedModelName, setSelectedModelName] = useState<string>();
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>();
  const [comparisonMode, setComparisonMode] = useState<ComparisonMode>("scenario");
  const { data, isLoading, error } = useQuery({
    queryKey: ["run-history"],
    queryFn: getRunHistory
  });
  const {
    data: comparisonData,
    isLoading: isComparisonLoading,
    error: comparisonError
  } = useQuery({
    queryKey: ["run-comparison"],
    queryFn: getRunComparison
  });

  const runs = data?.runs || [];
  const comparisonRows = comparisonData?.scenario_rows || [];
  const scenarioOptions = comparisonData?.filters.scenario_ids || [];
  const modelOptions = comparisonData?.filters.model_names || [];
  const activeScenarioId = selectedScenarioId;
  const activeModelName = selectedModelName;

  const filteredRuns = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    const scenarioRunIds = new Set(
      comparisonRows
        .filter((row) => !selectedScenarioId || row.scenario_id === selectedScenarioId)
        .map((row) => row.run_id)
    );
    return runs.filter((run) => {
      const matchesKeyword =
        !query ||
        [run.run_id, run.task_name, run.model_name]
          .join(" ")
          .toLowerCase()
          .includes(query);
      const matchesComparison =
        comparisonMode === "scenario"
          ? !selectedScenarioId || scenarioRunIds.has(run.run_id)
          : !selectedModelName || run.model_name === selectedModelName;
      return matchesKeyword && matchesComparison;
    });
  }, [comparisonMode, comparisonRows, keyword, runs, selectedModelName, selectedScenarioId]);

  const visibleComparisonRows = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    return comparisonRows
      .filter((row) => {
        const matchesKeyword =
          !query ||
          [row.run_id, row.task_name, row.model_name, row.scenario_id]
            .join(" ")
            .toLowerCase()
            .includes(query);
        if (comparisonMode === "scenario") {
          if (!activeScenarioId) return false;
          return matchesKeyword && (!activeScenarioId || row.scenario_id === activeScenarioId);
        }
        if (!activeModelName) return false;
        return matchesKeyword && (!activeModelName || row.model_name === activeModelName);
      })
      .sort((left, right) => Number(right.pass_rate || 0) - Number(left.pass_rate || 0));
  }, [activeModelName, activeScenarioId, comparisonMode, comparisonRows, keyword]);

  const visibleFailureReasons = useMemo(
    () => filterFailureReasons(comparisonData?.failure_reasons || [], visibleComparisonRows),
    [comparisonData?.failure_reasons, visibleComparisonRows]
  );
  const visibleOptimizationInsights = useMemo(
    () => filterOptimizationInsights(comparisonData?.optimization_insights || [], visibleComparisonRows),
    [comparisonData?.optimization_insights, visibleComparisonRows]
  );

  const averagePassRate = filteredRuns.length
    ? Math.round(
        filteredRuns.reduce((sum, run) => sum + Number(run.pass_rate || 0), 0) /
          filteredRuns.length
      )
    : 0;

  return (
    <section className="viewport-page history-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">历史评测</h1>
          <p className="page-subtitle">按 run 查看模型、场景数量、通过率和报告详情。</p>
        </div>
      </header>

      <div className="history-toolbar">
        <Input.Search
          allowClear
          placeholder="搜索任务或 Run"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
        />
      </div>

      <div className="metric-row">
        <div className="metric-card">
          <span>评测次数</span>
          <strong>{filteredRuns.length}</strong>
        </div>
        <div className="metric-card">
          <span>平均通过率</span>
          <strong>{averagePassRate}%</strong>
        </div>
        <div className="metric-card">
          <span>场景数</span>
          <strong>{filteredRuns.reduce((sum, run) => sum + Number(run.scenario_count || 0), 0)}</strong>
        </div>
      </div>

      {error ? <Alert type="error" message={(error as Error).message} /> : null}
      {comparisonError ? <Alert type="error" message={(comparisonError as Error).message} /> : null}
      <Collapse
        className="history-collapse"
        defaultActiveKey={["comparison-panel", "history-records-panel"]}
        items={[
          {
            key: "comparison-panel",
            label: "对比分析",
            children: (
              <section className="history-comparison-panel">
                <div className="history-comparison-toolbar">
                  <Segmented
                    value={comparisonMode}
                    onChange={(value) => setComparisonMode(value as ComparisonMode)}
                    options={[
                      { label: "同一场景不同模型", value: "scenario" },
                      { label: "同一模型不同场景", value: "model" }
                    ]}
                  />
                  {comparisonMode === "scenario" ? (
                    <Select
                      className="comparison-focus-select"
                      allowClear
                      showSearch
                      placeholder="选择要横向比较的场景"
                      value={selectedScenarioId}
                      onChange={(value) => setSelectedScenarioId(value)}
                      options={scenarioOptions.map((scenarioId) => ({ label: scenarioId, value: scenarioId }))}
                    />
                  ) : (
                    <Select
                      className="comparison-focus-select"
                      allowClear
                      showSearch
                      placeholder="选择要横向比较的模型"
                      value={selectedModelName}
                      onChange={(value) => setSelectedModelName(value)}
                      options={modelOptions.map((modelName) => ({ label: modelName, value: modelName }))}
                    />
                  )}
                </div>

                <div className="comparison-grid">
                  <div className="comparison-table-shell">
                    <div className="comparison-section-head">
                      <h2>对比记录</h2>
                      <span>{comparisonMode === "scenario" ? activeScenarioId || "请选择场景" : activeModelName || "请选择模型"}</span>
                    </div>
                    <Table<ComparisonScenarioRow>
                      rowKey={(row) => `${row.run_id}-${row.scenario_id}-${row.model_name}`}
                      loading={isComparisonLoading}
                      dataSource={visibleComparisonRows}
                      pagination={historyPagination(5)}
                      columns={[
                        {
                          title: "Run",
                          dataIndex: "run_id",
                          render: (runId: string) => <Link to={`/runs/${runId}`}>{runId}</Link>
                        },
                        { title: "模型", dataIndex: "model_name" },
                        { title: "场景", dataIndex: "scenario_id" },
                        {
                          title: "得分",
                          render: (_, row) => `${formatScore(row.score)} / ${formatScore(row.possible_score)}`
                        },
                        {
                          title: "通过率",
                          dataIndex: "pass_rate",
                          sorter: (left, right) => Number(left.pass_rate || 0) - Number(right.pass_rate || 0),
                          render: (value: number, row) => (
                            <div className="table-progress">
                              <Progress percent={Number(value || 0)} size="small" />
                              {row.score_anomaly ? <Tag color="red">分数异常 {row.raw_pass_rate}%</Tag> : null}
                            </div>
                          )
                        },
                        {
                          title: "关键失败",
                          dataIndex: "critical_failure_count",
                          render: (value: number) => <Tag color={value ? "red" : "green"}>{value}</Tag>
                        },
                        {
                          title: "保存时间",
                          dataIndex: "updated_at",
                          render: (value: number) => formatSavedTime(value)
                        }
                      ]}
                    />
                  </div>

                  <aside className="failure-reason-panel">
                    <Collapse
                      className="comparison-side-collapse"
                      defaultActiveKey={["failure-reasons-panel", "optimization-insights-panel"]}
                      items={[
                        {
                          key: "failure-reasons-panel",
                          label: (
                            <div className="comparison-collapse-label">
                              <span>失败原因汇总</span>
                              <Tag color="orange">{visibleFailureReasons.length} 类</Tag>
                            </div>
                          ),
                          children: visibleFailureReasons.length ? (
                            <div className="comparison-scroll-region failure-reason-list">
                              {visibleFailureReasons.map((reason) => (
                                <article key={reason.key}>
                                  <div>
                                    <strong>{reason.label}</strong>
                                    <Tag color="orange">历史出现 {reason.count} 次</Tag>
                                  </div>
                                  <p>
                                    涉及 {reason.model_names.length} 个模型、{reason.scenario_ids.length} 个场景
                                  </p>
                                  {reason.examples[0] ? (
                                    <Link to={`/runs/${reason.examples[0].run_id}`}>
                                      示例：{reason.examples[0].model_name} / {reason.examples[0].scenario_id}
                                    </Link>
                                  ) : null}
                                </article>
                              ))}
                            </div>
                          ) : (
                            <p className="empty-hint">当前筛选结果暂无失败证据</p>
                          )
                        },
                        {
                          key: "optimization-insights-panel",
                          label: (
                            <div className="comparison-collapse-label">
                              <span>优化建议摘要</span>
                              <Tag color="blue">{visibleOptimizationInsights.length} 条</Tag>
                            </div>
                          ),
                          children: visibleOptimizationInsights.length ? (
                            <div className="comparison-scroll-region comparison-optimization-list">
                              {visibleOptimizationInsights.map((insight) => (
                                <article
                                  className="comparison-optimization-card"
                                  key={`${insight.category}-${insight.business_context}-${insight.title}`}
                                >
                                  <div className="comparison-optimization-head">
                                    <Tag color={insight.priority === "high" ? "red" : "blue"}>
                                      {insight.category_label}
                                    </Tag>
                                    <span>
                                      {insight.scenario_ids.length} 场景 / {insight.model_names?.length || 0} 模型
                                    </span>
                                  </div>
                                  <strong>{insight.decision}</strong>
                                  <div className="comparison-insight-lines">
                                    <p>
                                      <b>问题判断</b>
                                      {insight.issue_summary || insight.recommended_action}
                                    </p>
                                    <p>
                                      <b>证据指向</b>
                                      {insight.evidence_summary || insight.business_context}
                                    </p>
                                    <p>
                                      <b>下一步动作</b>
                                      {insight.next_action || insight.recommended_action}
                                    </p>
                                  </div>
                                  {insight.examples[0]?.run_id ? (
                                    <Link to={`/runs/${insight.examples[0].run_id}`}>
                                      查看示例：{insight.examples[0].model_name || "未知模型"} /{" "}
                                      {insight.examples[0].scenario_id}
                                    </Link>
                                  ) : null}
                                </article>
                              ))}
                            </div>
                          ) : (
                            <p className="empty-hint">当前筛选结果暂无链路优化建议</p>
                          )
                        }
                      ]}
                    />
                  </aside>
                </div>
              </section>
            )
          },
          {
            key: "history-records-panel",
            label: "历史评测记录",
            children: (
              <div className="history-table-shell">
                <Table<RunSummary>
                  rowKey="run_id"
                  loading={isLoading}
                  dataSource={filteredRuns}
                  pagination={historyPagination(6)}
                  columns={[
                    {
                      title: "Run",
                      dataIndex: "run_id",
                      render: (runId: string) => <Link to={`/runs/${runId}`}>{runId}</Link>
                    },
                    { title: "任务", dataIndex: "task_name" },
                    { title: "模型", dataIndex: "model_name" },
                    { title: "场景数", dataIndex: "scenario_count" },
                    {
                      title: "保存时间",
                      dataIndex: "updated_at",
                      render: (value: number) => formatSavedTime(value)
                    },
                    {
                      title: "通过率",
                      dataIndex: "pass_rate",
                      render: (value: number) => (
                        <div className="table-progress">
                          <Progress percent={Number(value || 0)} size="small" />
                        </div>
                      )
                    },
                    {
                      title: "操作",
                      dataIndex: "run_id",
                      render: (runId: string) => (
                        <Link to={`/runs/${runId}`}>
                          <Button className="mt-action-button" size="small">查看报告</Button>
                        </Link>
                      )
                    }
                  ]}
                />
              </div>
            )
          }
        ]}
      />
    </section>
  );
}

function formatSavedTime(value?: number) {
  if (!value) return "-";
  return new Date(value * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function historyPagination(pageSize: number) {
  return {
    className: "history-pagination",
    pageSize,
    showSizeChanger: false,
    showLessItems: false,
    size: "small" as const
  };
}

function filterFailureReasons(
  reasons: FailureReasonSummary[],
  rows: ComparisonScenarioRow[]
) {
  const runIds = new Set(rows.map((row) => row.run_id));
  const modelNames = new Set(rows.map((row) => row.model_name));
  const scenarioIds = new Set(rows.map((row) => row.scenario_id));

  return reasons.filter((reason) => {
    const matchesRun = reason.run_ids.some((runId) => runIds.has(runId));
    const matchesModel = reason.model_names.some((modelName) => modelNames.has(modelName));
    const matchesScenario = reason.scenario_ids.some((scenarioId) => scenarioIds.has(scenarioId));
    return matchesRun && matchesModel && matchesScenario;
  });
}

function filterOptimizationInsights(
  insights: OptimizationInsight[],
  rows: ComparisonScenarioRow[]
) {
  if (!rows.length) return [];
  const visibleRunIds = new Set(rows.map((row) => row.run_id));
  const visibleModelNames = new Set(rows.map((row) => row.model_name));
  return insights.filter((insight) => {
    const matchesRun =
      !insight.run_ids?.length || insight.run_ids.some((runId) => visibleRunIds.has(runId));
    const matchesModel =
      !insight.model_names?.length ||
      insight.model_names.some((modelName) => visibleModelNames.has(modelName));
    return matchesRun && matchesModel;
  });
}

function formatScore(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
