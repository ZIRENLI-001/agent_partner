import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Collapse, Pagination, Progress, Select, Spin, Tag } from "antd";
import { useMemo, useState } from "react";
import { getCalibrationSamples, type CalibrationSample } from "../api/calibration";

const samplePageSize = 9;
const coveragePageSize = 5;

export function CalibrationDatasetPage() {
  const [difficultyFilter, setDifficultyFilter] = useState<string>();
  const [domainFilter, setDomainFilter] = useState<string>();
  const [riskFilter, setRiskFilter] = useState<string>();
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useQuery({
    queryKey: ["calibration-samples"],
    queryFn: getCalibrationSamples
  });

  const summary = data?.summary;
  const samples = data?.samples || [];
  const difficultyOptions = useMemo(
    () => uniqueOptions(samples.map((sample) => sample.difficulty)),
    [samples]
  );
  const domainOptions = useMemo(
    () => uniqueOptions(samples.map((sample) => sample.domain)),
    [samples]
  );
  const riskOptions = useMemo(
    () => uniqueOptions(samples.flatMap((sample) => sample.risk_tags)),
    [samples]
  );
  const filteredSamples = useMemo(
    () =>
      samples.filter((sample) => {
        if (difficultyFilter && sample.difficulty !== difficultyFilter) return false;
        if (domainFilter && sample.domain !== domainFilter) return false;
        if (riskFilter && !sample.risk_tags.includes(riskFilter)) return false;
        return true;
      }),
    [difficultyFilter, domainFilter, riskFilter, samples]
  );
  const visibleSamples = filteredSamples.slice((page - 1) * samplePageSize, page * samplePageSize);

  return (
    <section className="viewport-page calibration-page">
      <header className="page-header">
        <div>
          <span className="section-kicker">Evaluation Sample Library</span>
          <h1 className="page-title">评测样本库</h1>
          <p className="page-subtitle">
            覆盖美团履约外呼的难度分层、风险标签、预期评分与证据轮次，用于验证评测系统可靠性。
          </p>
        </div>
      </header>

      {error ? <Alert type="error" message={(error as Error).message} /> : null}
      {isLoading ? <Spin /> : null}

      {summary ? (
        <>
          <Collapse
            className="calibration-standard-collapse"
            items={[
              {
                key: "difficulty-standard",
                label: "难度分层标准",
                children: (
                  <section className="difficulty-standard">
                    <div>
                      <p>
                        难度分层综合考虑任务流程复杂度、用户阻力、风险边界、对话轮次、证据定位难度。
                      </p>
                    </div>
                    <div className="difficulty-level-grid">
                      {difficultyLevels.map((level) => (
                        <article key={level.code}>
                          <strong>{level.label}</strong>
                          <span>{level.description}</span>
                        </article>
                      ))}
                    </div>
                    <div className="turn-note">
                      <strong>轮次影响说明</strong>
                      <span>
                        轮次会影响难度，但不会单独决定难度；少轮高风险越权场景可能高于多轮普通 FAQ 场景。
                      </span>
                    </div>
                  </section>
                )
              }
            ]}
          />

          <div className="calibration-body">
            <section className="surface calibration-coverage">
              <h2>覆盖概览</h2>
              <CoverageBlock title="难度覆盖" values={summary.difficulty_counts} />
              <CoverageBlock title="风险标签" values={summary.risk_tag_counts} />
              <CoverageTags title="覆盖目标" values={summary.coverage_targets} />
            </section>

            <section className="surface calibration-samples">
              <div className="sample-section-head">
                <h2>样本详情（{filteredSamples.length} / {samples.length} 条）</h2>
                <span>筛选标签</span>
              </div>
              <div className="sample-filter-row">
                <Select
                  allowClear
                  placeholder="难度"
                  options={difficultyOptions}
                  value={difficultyFilter}
                  onChange={(value) => {
                    setDifficultyFilter(value);
                    setPage(1);
                  }}
                />
                <Select
                  allowClear
                  placeholder="业务域"
                  options={domainOptions}
                  value={domainFilter}
                  onChange={(value) => {
                    setDomainFilter(value);
                    setPage(1);
                  }}
                />
                <Select
                  allowClear
                  showSearch
                  placeholder="风险标签"
                  options={riskOptions}
                  value={riskFilter}
                  onChange={(value) => {
                    setRiskFilter(value);
                    setPage(1);
                  }}
                />
              </div>
              <Collapse
                className="calibration-sample-collapse"
                items={visibleSamples.map((sample) => ({
                  key: sample.sample_id,
                  label: <SampleHeader sample={sample} />,
                  children: <SampleDetail sample={sample} />
                }))}
              />
              <Pagination
                className="sample-pagination"
                current={page}
                pageSize={samplePageSize}
                total={filteredSamples.length}
                showSizeChanger={false}
                onChange={setPage}
              />
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}

function uniqueOptions(values: string[]) {
  return Array.from(new Set(values))
    .sort()
    .map((value) => ({ label: value, value }));
}

const difficultyLevels = [
  {
    code: "L1",
    label: "L1 基础顺行",
    description: "用户配合度高，主要验证身份确认、合同生效通知与配送确认。"
  },
  {
    code: "L2",
    label: "L2 FAQ 问答",
    description: "用户提出指令内问题，重点验证知识点准确性。"
  },
  {
    code: "L3",
    label: "L3 履约阻力",
    description: "用户忙碌、拒绝或质疑安排，需要模型挽留并保持任务目标。"
  },
  {
    code: "L4",
    label: "L4 边界风险",
    description: "涉及奖励、安全、政策解释等敏感边界，避免越权承诺。"
  },
  {
    code: "L5",
    label: "L5 复杂对抗",
    description: "包含情绪化打断、反复追问、代操作或免罚要求等高风险场景。"
  }
];

function CoverageBlock(props: { title: string; values: Record<string, number> }) {
  const [page, setPage] = useState(1);
  const entries = Object.entries(props.values);
  const visibleEntries = entries.slice(
    (page - 1) * coveragePageSize,
    page * coveragePageSize
  );
  const max = Math.max(...Object.values(props.values), 1);
  return (
    <div className="coverage-section">
      <h3>{props.title}</h3>
      <div className="coverage-list">
        {visibleEntries.map(([name, count]) => (
          <div className="coverage-row" key={name}>
            <span>{name}</span>
            <Progress percent={Math.round((count / max) * 100)} showInfo={false} />
            <strong>{count}</strong>
          </div>
        ))}
      </div>
      {entries.length > coveragePageSize ? (
        <Pagination
          className="coverage-pagination"
          current={page}
          pageSize={coveragePageSize}
          total={entries.length}
          showSizeChanger={false}
          size="small"
          onChange={setPage}
        />
      ) : null}
    </div>
  );
}

function CoverageTags(props: { title: string; values: string[] }) {
  const [showAllTargets, setShowAllTargets] = useState(false);
  const hasOverflowTargets = props.values.length > coveragePageSize;
  const visibleValues = props.values.slice(0, coveragePageSize);
  const displayedValues = showAllTargets ? props.values : visibleValues;
  return (
    <div className="coverage-section">
      <div className="coverage-target-heading">
        <h3>{props.title}</h3>
        {hasOverflowTargets ? (
          <Button
            className="mt-action-button"
            size="small"
            onClick={() => setShowAllTargets((value) => !value)}
          >
            {showAllTargets ? "收起" : `展开全部 ${props.values.length} 项`}
          </Button>
        ) : null}
      </div>
      <div
        className={
          showAllTargets
            ? "tag-row coverage-target-list coverage-target-list-expanded"
            : "tag-row coverage-target-list"
        }
      >
        {displayedValues.map((target) => (
          <em key={target}>{target}</em>
        ))}
      </div>
      {hasOverflowTargets ? (
        <div className="coverage-target-actions">
          <span>
            {showAllTargets
              ? `已展开 ${props.values.length} 项`
              : `显示 ${visibleValues.length} / ${props.values.length} 项`}
          </span>
        </div>
      ) : null}
    </div>
  );
}

function SampleHeader({ sample }: { sample: CalibrationSample }) {
  return (
    <div className="calibration-sample-header">
      <strong>{sample.sample_id}</strong>
      <Tag>{sample.difficulty}</Tag>
      <Tag color="gold">{sample.scenario_type}</Tag>
      <span>
        预期分 {sample.expected_score_band.min}-{sample.expected_score_band.max}
      </span>
    </div>
  );
}

function SampleDetail({ sample }: { sample: CalibrationSample }) {
  return (
    <div className="calibration-detail-scroll">
      <div className="calibration-detail">
        <section>
          <h3>多轮对话</h3>
          <div className="dialogue-bubbles">
            {sample.dialogue.map((turn) => (
              <p className={turn.speaker === "assistant" ? "assistant" : "user"} key={turn.turn_id}>
                <strong>
                  #{turn.turn_id} {turn.speaker}
                </strong>
                {turn.content}
              </p>
            ))}
          </div>
        </section>

        <section>
          <h3>预期标签</h3>
          <div className="label-list">
            {sample.expected_labels.map((label) => (
              <article key={`${sample.sample_id}-${label.rubric_item_id}`}>
                <div>
                  <strong>{label.rubric_item_id}</strong>
                  <Tag color={label.expected_verdict === "fail" ? "red" : "green"}>
                    {label.expected_verdict}
                  </Tag>
                  <Tag>{label.severity}</Tag>
                </div>
                <p>{label.expected_reason}</p>
                <span>证据轮次：{label.evidence_turn_ids.join(", ")}</span>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
