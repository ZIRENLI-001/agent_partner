import { Alert } from "antd";
import { useEffect, useMemo, useRef } from "react";
import type { EChartsType } from "echarts/core";
import type { RunResponse } from "../../api/runs";

interface RunChartsProps {
  result: RunResponse;
  compact?: boolean;
}

interface ChartPanelProps {
  title: string;
  description: string;
  option: Record<string, unknown>;
  empty?: boolean;
}

const stageLabels: Record<string, string> = {
  instruction_parsing: "指令解析",
  rubric_generation: "Rubric",
  scenario_generation: "对话模拟",
  scenario_execution: "轨迹执行",
  report_generation: "报告生成"
};

const chartAxisLabel = {
  fontSize: 10,
  interval: 0,
  overflow: "truncate",
  width: 72
};

const chartValueLabel = {
  show: true,
  position: "top",
  fontSize: 10,
  distance: 4,
  hideOverlap: true
};

export function RunCharts({ result, compact = false }: RunChartsProps) {
  const charts = useMemo(
    () => [
      {
        key: "dimension",
        title: "维度得分",
        description: "对比各能力维度的通过率与得分。",
        option: dimensionOption(result),
        empty: !result.dimension_summary.length
      },
      {
        key: "scenario",
        title: "场景得分",
        description: "定位拖低总分的具体测试场景。",
        option: scenarioOption(result),
        empty: !result.scenario_summary.length
      },
      {
        key: "failure",
        title: "失败分布",
        description: "按评测维度聚合失败与需复核项。",
        option: failureOption(result),
        empty: !result.failure_summary.length
      },
      {
        key: "timing",
        title: "阶段耗时",
        description: "展示自动评测链路各阶段耗时。",
        option: timingOption(result),
        empty: !Object.keys(result.stage_timings_ms || {}).length
      }
    ],
    [result]
  );
  const visibleCharts = compact ? charts.slice(0, 2) : charts;

  return (
    <div className={compact ? "run-chart-grid compact" : "run-chart-grid"}>
      {visibleCharts.map((chart) => (
        <ChartPanel
          key={chart.key}
          title={chart.title}
          description={chart.description}
          option={chart.option}
          empty={chart.empty}
        />
      ))}
    </div>
  );
}

function ChartPanel({ title, description, option, empty }: ChartPanelProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || empty) return;
    let disposed = false;
    let chart: EChartsType | undefined;
    const resize = () => chart?.resize();

    void loadECharts().then((echarts) => {
      if (disposed || !chartRef.current) return;
      chart = echarts.init(chartRef.current);
      chart.setOption(option);
      window.addEventListener("resize", resize);
    });

    return () => {
      disposed = true;
      window.removeEventListener("resize", resize);
      chart?.dispose();
    };
  }, [empty, option]);

  return (
    <section className="run-chart-card">
      <div className="run-chart-head">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      {empty ? (
        <Alert type="info" showIcon message="暂无可视化数据" />
      ) : (
        <div className="run-chart-canvas" ref={chartRef} />
      )}
    </section>
  );
}

async function loadECharts() {
  const { echarts } = await import("./loadECharts");
  return echarts;
}

function dimensionOption(result: RunResponse) {
  const dimensions = result.dimension_summary.map((item) => item.dimension);
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 38, right: 18, top: 24, bottom: 64, containLabel: true },
    xAxis: { type: "category", data: dimensions, axisLabel: { ...chartAxisLabel, rotate: 30 } },
    yAxis: { type: "value", max: 100, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: "通过率",
        type: "bar",
        data: result.dimension_summary.map((item) => Number(item.pass_rate || 0)),
        itemStyle: { color: "#ffd100", borderRadius: [5, 5, 0, 0] },
        label: { ...chartValueLabel, formatter: "{c}%" }
      }
    ]
  };
}

function scenarioOption(result: RunResponse) {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 42, right: 18, top: 24, bottom: 64, containLabel: true },
    xAxis: {
      type: "category",
      data: result.scenario_summary.map((item) => item.scenario_id),
      axisLabel: { ...chartAxisLabel, rotate: 30 }
    },
    yAxis: { type: "value", max: 100, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: "场景通过率",
        type: "bar",
        data: result.scenario_summary.map((item) => Number(item.pass_rate || 0)),
        itemStyle: { color: "#111111", borderRadius: [5, 5, 0, 0] },
        label: { ...chartValueLabel, formatter: "{c}%" }
      }
    ]
  };
}

function failureOption(result: RunResponse) {
  const counts = new Map<string, number>();
  const dimensionByItem = rubricDimensionByItem(result);
  for (const failure of result.failure_summary) {
    const dimension = dimensionByItem.get(failure.rubric_item_id) || "其他";
    counts.set(dimension, (counts.get(dimension) || 0) + 1);
  }
  const data = Array.from(counts.entries()).map(([name, value]) => ({ name, value }));
  return {
    tooltip: { trigger: "item" },
    series: [
      {
        name: "失败项",
        type: "pie",
        radius: ["42%", "70%"],
        center: ["50%", "52%"],
        data,
        itemStyle: { borderColor: "#ffffff", borderWidth: 2 },
        color: ["#ffd100", "#111111", "#f59e0b", "#ef4444", "#9ca3af"],
        label: {
          formatter: "{b}: {c}",
          fontSize: 10,
          width: 78,
          overflow: "truncate"
        },
        labelLine: { length: 8, length2: 6 },
        avoidLabelOverlap: true
      }
    ]
  };
}

function rubricDimensionByItem(result: RunResponse) {
  const mapping = new Map<string, string>();
  const rubric = result.rubric_spec;
  const items =
    rubric && typeof rubric === "object" && Array.isArray((rubric as { items?: unknown }).items)
      ? ((rubric as { items: Array<Record<string, unknown>> }).items)
      : [];
  for (const item of items) {
    const itemId = typeof item.item_id === "string" ? item.item_id : "";
    const dimension = typeof item.dimension === "string" ? item.dimension : "";
    if (itemId && dimension) mapping.set(itemId, dimension);
  }
  return mapping;
}

function timingOption(result: RunResponse) {
  const entries = Object.entries(result.stage_timings_ms || {});
  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const item = Array.isArray(params) ? params[0] : params;
        const payload = item as { name?: string; value?: number | string; dataIndex?: number };
        const stageKey = entries[payload.dataIndex ?? 0]?.[0] || "";
        return [
          payload.name || stageLabels[stageKey] || stageKey,
          `耗时：${formatDuration(Number(payload.value || 0))}`,
          formatStageDiagnostic(result, stageKey)
        ].filter(Boolean).join("<br/>");
      }
    },
    grid: { left: 48, right: 18, top: 24, bottom: 64, containLabel: true },
    xAxis: {
      type: "category",
      data: entries.map(([key]) => stageLabels[key] || key),
      axisLabel: { ...chartAxisLabel, rotate: 25 }
    },
    yAxis: { type: "value", name: "ms", axisLabel: { fontSize: 10 }, nameTextStyle: { fontSize: 10 } },
    series: [
      {
        name: "耗时",
        type: "bar",
        data: entries.map(([, value]) => Number(value)),
        itemStyle: { color: "#f59e0b", borderRadius: [5, 5, 0, 0] },
        label: {
          ...chartValueLabel,
          formatter: ({ value }: { value: number | string }) => formatDuration(Number(value))
        }
      }
    ]
  };
}

function formatStageDiagnostic(result: RunResponse, stageKey: string) {
  const diagnostic = result.stage_diagnostics?.[stageKey];
  if (!diagnostic) return "";
  const source = String(diagnostic.output_source || "");
  const attempted = diagnostic.model_attempted === true ? "已尝试模型" : "本地生成";
  const fallback = diagnostic.fallback_used === true ? "已回退" : "未回退";
  const reason = diagnostic.fallback_reason ? `；${String(diagnostic.fallback_reason)}` : "";
  return `来源：${source || attempted}；${fallback}${reason}`;
}

function formatDuration(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0ms";
  if (value < 1000) return `${Math.max(1, Math.round(value))}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}
