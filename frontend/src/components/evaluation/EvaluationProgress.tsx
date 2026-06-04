import { Progress, Tag } from "antd";

export type EvaluationProgressStatus = "pending" | "running" | "completed" | "failed" | "queued";

export interface EvaluationProgressStage {
  key: string;
  name: string;
  description?: string;
  status: EvaluationProgressStatus | string;
}

interface EvaluationProgressProps {
  title: string;
  description?: string;
  stages: EvaluationProgressStage[];
  onStageClick?: (index: number, stage: EvaluationProgressStage) => void;
  isStageDisabled?: (index: number, stage: EvaluationProgressStage) => boolean;
}

export function EvaluationProgress({
  title,
  description,
  stages,
  onStageClick,
  isStageDisabled
}: EvaluationProgressProps) {
  const progressPercent = calculateProgressPercent(stages);
  const activeStage = stages.find((stage) => stage.status === "running")
    || stages.find((stage) => stage.status === "queued")
    || stages.find((stage) => stage.status === "failed")
    || [...stages].reverse().find((stage) => stage.status === "completed");
  const isInteractive = Boolean(onStageClick);

  return (
    <section className="evaluation-progress">
      <div className="evaluation-progress-header">
        <div>
          <h3>{title}</h3>
          <p>{description || `当前阶段：${activeStage?.name || "未开始"}`}</p>
        </div>
        <strong>{progressPercent}%</strong>
      </div>
      <Progress percent={progressPercent} showInfo={false} status={progressStatus(stages)} />
      <div className="progress-stage-grid">
        {stages.map((stage, index) => {
          const disabled = isStageDisabled?.(index, stage) || false;
          const className = [
            "progress-stage-card",
            String(stage.status),
            isInteractive ? "clickable" : "",
            disabled ? "disabled" : ""
          ].filter(Boolean).join(" ");
          return (
            <button
              className={className}
              disabled={!isInteractive || disabled}
              key={stage.key}
              onClick={() => onStageClick?.(index, stage)}
              type="button"
            >
              <span>
                <strong>{stage.name}</strong>
                {stage.description ? <small className="progress-stage-copy">{stage.description}</small> : null}
              </span>
              <Tag color={stageTagColor(stage.status)}>{stageStatusLabel(stage.status)}</Tag>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function calculateProgressPercent(stages: EvaluationProgressStage[]) {
  if (!stages.length) return 0;
  const completed = stages.filter((stage) => stage.status === "completed").length;
  const runningWeight = stages.some((stage) => stage.status === "running") ? 0.5 : 0;
  return Math.min(100, Math.round(((completed + runningWeight) / stages.length) * 100));
}

function progressStatus(stages: EvaluationProgressStage[]) {
  if (stages.some((stage) => stage.status === "failed")) return "exception";
  if (stages.every((stage) => stage.status === "completed")) return "success";
  return "active";
}

function stageStatusLabel(status: EvaluationProgressStage["status"]) {
  if (status === "completed") return "已完成";
  if (status === "running") return "生成中";
  if (status === "failed") return "失败";
  if (status === "queued") return "排队中";
  return "等待中";
}

function stageTagColor(status: EvaluationProgressStage["status"]) {
  if (status === "completed") return "green";
  if (status === "running") return "gold";
  if (status === "failed") return "red";
  if (status === "queued") return "blue";
  return "default";
}
