import { Alert, Button, Card, Collapse, Descriptions, Progress, Spin, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  getRunDetail,
  type EnrichedFailureEvidence,
  type RunDetailResponse
} from "../api/runs";
import { RunCharts } from "../components/evaluation/RunCharts";
import { ScenarioTraceSwitcher } from "../components/evaluation/ScenarioTraceSwitcher";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const [showMarkdown, setShowMarkdown] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["run-detail", runId],
    queryFn: () => getRunDetail(runId),
    enabled: Boolean(runId)
  });

  if (isLoading) {
    return <Spin />;
  }

  if (error) {
    return <Alert type="error" message={(error as Error).message} />;
  }

  if (!data) {
    return <Alert type="warning" message="未找到评测报告" />;
  }

  return (
    <section className="viewport-page report-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">评测报告</h1>
          <p className="page-subtitle">
            {runId} · 保存时间：{formatSavedTime(data.updated_at)}
          </p>
        </div>
      </header>

      <div className="report-hero surface">
        <div>
          <span className="section-kicker">总览</span>
          <h2>{data.score_summary.normalized_score ?? data.score_summary.pass_rate}/100</h2>
          {data.score_summary.score_reliable === false ? (
            <Tag color="orange">分数需复核</Tag>
          ) : null}
          <p className="muted">评测过程可解释，结果可量化，证据可追溯。</p>
        </div>
        <Progress
          type="circle"
          percent={Number((data.score_summary.normalized_score ?? data.score_summary.pass_rate) || 0)}
          size={132}
        />
      </div>

      {data.score_summary.score_reliable === false ? (
        <Alert
          className="mb-16"
          type="warning"
          showIcon
          message="当前百分制分数暂不可单独采信"
          description={
            data.score_summary.score_reliability_reason ||
            "链路质量门禁未通过，请先查看链路健康度、漏评项和证据覆盖。"
          }
        />
      ) : null}

      <div className="metric-row">
        <div className="metric-card">
          <span>场景数</span>
          <strong>{data.score_summary.scenario_count}</strong>
        </div>
        <div className="metric-card">
          <span>失败项</span>
          <strong>{data.score_summary.failure_count || 0}</strong>
        </div>
        <div className="metric-card">
          <span>高风险项</span>
          <strong>{data.score_summary.critical_failure_count || 0}</strong>
        </div>
      </div>

      <div className="metric-row">
        <div className="metric-card">
          <span>链路状态</span>
          <strong>{data.quality_summary?.overall_status || "unknown"}</strong>
        </div>
        <div className="metric-card">
          <span>证据命中</span>
          <strong>{data.quality_summary?.evidence_traceability?.traceable_evidence_rate ?? 0}%</strong>
        </div>
        <div className="metric-card">
          <span>Judge 漏项</span>
          <strong>{data.quality_summary?.judge_integrity?.missing_item_count ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>场景多样性</span>
          <strong>{data.quality_summary?.scenario_coverage?.diversity_score ?? 0}</strong>
        </div>
      </div>

      <Card title="可视化对比" className="mb-16">
        <RunCharts result={data} />
      </Card>

      <Card title="链路优化决策" className="mb-16">
        <OptimizationInsightsPanel data={data} />
      </Card>

      <div className="report-insight-grid mb-16">
        <Card title="对话轨迹" className="report-trace-card">
          <ScenarioTraceSwitcher result={data} />
        </Card>

        <Card title="失败证据链" className="report-failure-card">
          <FailureEvidenceCollapse data={data} />
        </Card>
      </div>

      <Card
        title="Markdown 原文"
        extra={
          <Button
            className="mt-action-button"
            size="small"
            onClick={() => setShowMarkdown((current) => !current)}
          >
            {showMarkdown ? "收起 Markdown 原文" : "展开 Markdown 原文"}
          </Button>
        }
      >
        {showMarkdown ? <pre>{data.report}</pre> : null}
      </Card>
    </section>
  );
}

function formatSavedTime(value?: number) {
  if (!value) return "-";
  return new Date(value * 1000).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function OptimizationInsightsPanel({ data }: { data: RunDetailResponse }) {
  const insights = data.optimization_insights || [];
  if (!insights.length) {
    return <p className="muted">暂无需要优先处理的链路优化建议。</p>;
  }
  return (
    <div className="optimization-grid">
      {insights.slice(0, 8).map((insight) => (
        <article className="optimization-card" key={`${insight.category}-${insight.title}`}>
          <div className="optimization-card-head">
            <Tag color={priorityColor(insight.priority)}>{priorityText(insight.priority)}</Tag>
            <Tag>{insight.category_label}</Tag>
            <strong>{insight.decision}</strong>
          </div>
          <p className="optimization-action">{insight.recommended_action}</p>
          <dl className="optimization-meta">
            <dt>业务上下文</dt>
            <dd>{insight.business_context || "未匹配到样本上下文"}</dd>
            <dt>影响范围</dt>
            <dd>
              {insight.scenario_ids.length} 个场景 ·{" "}
              {insight.rubric_item_ids.join("、") || "未提供 Rubric 项"}
            </dd>
            <dt>样本参考</dt>
            <dd>
              {insight.sample_references.length
                ? insight.sample_references
                    .map((sample) => `${sample.domain}/${sample.scenario_type}/${sample.difficulty}`)
                    .join("；")
                : "暂无样本匹配"}
            </dd>
          </dl>
          {insight.examples[0] ? (
            <div className="optimization-example">
              <strong>证据摘要</strong>
              <span>{insight.examples[0].reason}</span>
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function FailureEvidenceCollapse({ data }: { data: RunDetailResponse }) {
  const failures = collectFailureEvidence(data).slice(0, 20);
  if (!failures.length) return <p className="muted">暂无失败证据。</p>;
  return (
    <Collapse
      items={failures.map((item) => ({
        key: `${item.scenario_id}-${item.rubric_item_id}`,
        label: (
          <span>
            {item.scenario_id} · {item.rubric_item_id}
            <Tag color={item.severity === "critical" ? "red" : "orange"}>
              {item.score}/{item.max_score}
            </Tag>
          </span>
        ),
        children: (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="评判标准">
              {item.expected_behavior || item.instruction_quote || item.source}
            </Descriptions.Item>
            <Descriptions.Item label="失败原因">{item.reason}</Descriptions.Item>
            <Descriptions.Item label="实际表现">
              {item.actual_behavior || item.explanation || "暂无实际表现摘要"}
            </Descriptions.Item>
            <Descriptions.Item label="Rubric 来源">{item.source}</Descriptions.Item>
            <Descriptions.Item label="对话轮次">
              {item.turn_ids.length ? item.turn_ids.join(", ") : "无直接轮次证据"}
            </Descriptions.Item>
          </Descriptions>
        )
      }))}
    />
  );
}

function priorityColor(priority: string) {
  if (priority === "high") return "red";
  if (priority === "low") return "default";
  return "orange";
}

function priorityText(priority: string) {
  if (priority === "high") return "高优先级";
  if (priority === "low") return "低优先级";
  return "中优先级";
}

function collectFailureEvidence(data: RunDetailResponse): EnrichedFailureEvidence[] {
  const severityByKey = new Map(
    (data.failure_summary || []).map((item) => [
      `${item.scenario_id}-${item.rubric_item_id}`,
      item.severity
    ])
  );
  return (data.results || []).flatMap((evaluation) =>
    (evaluation.evidence || [])
      .filter((item) => item.verdict !== "pass")
      .map((item) => ({
        ...item,
        scenario_id: evaluation.scenario_id,
        severity: severityByKey.get(`${evaluation.scenario_id}-${item.rubric_item_id}`)
      }))
  );
}
