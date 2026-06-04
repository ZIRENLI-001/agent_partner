import { Alert, Empty, Select, Tag } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { EvaluationResult, RunResponse } from "../../api/runs";

interface ScenarioTraceSwitcherProps {
  result: RunResponse;
  compact?: boolean;
}

export function ScenarioTraceSwitcher({ result, compact = false }: ScenarioTraceSwitcherProps) {
  const scenarioOptions = useMemo(() => scenarioTraceOptions(result), [result]);
  const [selectedScenarioId, setSelectedScenarioId] = useState(
    scenarioOptions[0]?.scenario_id || ""
  );

  useEffect(() => {
    if (!scenarioOptions.length) {
      setSelectedScenarioId("");
      return;
    }
    if (!scenarioOptions.some((item) => item.scenario_id === selectedScenarioId)) {
      setSelectedScenarioId(scenarioOptions[0].scenario_id);
    }
  }, [scenarioOptions, selectedScenarioId]);

  if (!scenarioOptions.length) {
    return <Empty description="暂无对话轨迹" />;
  }

  const selectedScenario = scenarioOptions.find(
    (item) => item.scenario_id === selectedScenarioId
  ) || scenarioOptions[0];
  const trace = result.traces.find(
    (item) => item.scenario_id === selectedScenario.scenario_id
  );
  const evaluation = result.results.find(
    (item) => item.scenario_id === selectedScenario.scenario_id
  );
  const failures = collectScenarioFailures(evaluation);

  return (
    <div className={compact ? "scenario-trace-switcher compact" : "scenario-trace-switcher"}>
      <div className="scenario-switcher-header">
        <div className="scenario-switcher-score">
          <span>场景得分</span>
          <strong>
            {selectedScenario.score}/{selectedScenario.possible_score}
          </strong>
        </div>
        <label className="scenario-switcher-control">
          <span>场景切换</span>
          <Select
            value={selectedScenario.scenario_id}
            options={scenarioOptions.map((item) => ({
              value: item.scenario_id,
              label: item.scenario_id
            }))}
            onChange={setSelectedScenarioId}
          />
        </label>
      </div>

      <div className="scenario-switcher-meta">
        <Tag color={selectedScenario.critical_failures.length ? "red" : "green"}>
          {selectedScenario.critical_failures.length ? "高风险失败" : "已评测"}
        </Tag>
        {selectedScenario.coverage_targets.map((target) => (
          <Tag key={target}>{target}</Tag>
        ))}
        {selectedScenario.expected_test_focus ? (
          <span>{selectedScenario.expected_test_focus}</span>
        ) : null}
      </div>

      {!trace ? (
        <Alert type="warning" showIcon message="当前场景没有可用对话轨迹" />
      ) : (
        <div className="dialogue-bubbles" aria-label="对话轨迹">
          {trace.turns.map((turn) => (
            <p
              className={turn.speaker === "assistant" ? "assistant" : "user"}
              key={turn.turn_id}
            >
              <strong>{turn.speaker === "assistant" ? "数字人" : "用户"}</strong>
              {turn.content}
            </p>
          ))}
        </div>
      )}

      {!compact && failures.length ? (
        <div className="scenario-failure-strip">
          <strong>当前场景失败项</strong>
          {failures.map((item) => (
            <Tag color={item.critical ? "red" : "orange"} key={item.rubric_item_id}>
              {item.rubric_item_id} · {item.score}/{item.max_score}
            </Tag>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function scenarioTraceOptions(result: RunResponse) {
  const summaryByScenario = new Map(
    (result.scenario_summary || []).map((item) => [item.scenario_id, item])
  );
  const scenarioIds = new Set<string>();
  for (const item of result.scenario_summary || []) scenarioIds.add(item.scenario_id);
  for (const trace of result.traces || []) scenarioIds.add(trace.scenario_id);
  for (const evaluation of result.results || []) scenarioIds.add(evaluation.scenario_id);

  return Array.from(scenarioIds).map((scenarioId) => {
    const summary = summaryByScenario.get(scenarioId);
    const evaluation = result.results.find((item) => item.scenario_id === scenarioId);
    const evaluationScore = evaluation?.total_score;
    const evaluationPossibleScore = evaluation?.evidence.reduce(
      (total, item) => total + item.max_score,
      0
    );
    return {
      scenario_id: scenarioId,
      coverage_targets: summary?.coverage_targets || [],
      expected_test_focus: summary?.expected_test_focus || "",
      score: evaluationScore ?? summary?.score ?? 0,
      possible_score: evaluationPossibleScore ?? summary?.possible_score ?? 0,
      critical_failures: summary?.critical_failures || evaluation?.critical_failures || []
    };
  });
}

function collectScenarioFailures(evaluation?: EvaluationResult) {
  if (!evaluation) return [];
  return evaluation.evidence
    .filter((item) => item.verdict !== "pass")
    .map((item) => ({
      ...item,
      critical: evaluation.critical_failures.includes(item.rubric_item_id)
    }));
}
