from __future__ import annotations

from typing import Optional

from backend.evaluation_engine.domain import EvaluationResult, EvidenceItem, Report, ScenarioSet, TaskSpec
from backend.evaluation_engine.scoring import SCORING_SCALE, normalized_percent


def write_markdown_report(
    run_id: str,
    task_spec: TaskSpec,
    scenario_set: ScenarioSet,
    results: list[EvaluationResult],
    input_data_summary: Optional[dict[str, object]] = None,
    quality_summary: Optional[dict[str, object]] = None,
) -> Report:
    total_score = sum(result.total_score for result in results)
    possible_score = _possible_score(results)
    average_score = 0.0
    if results:
        average_score = round(total_score / len(results), 2)
    pass_rate = normalized_percent(total_score, possible_score)

    scenario_possible_scores = _scenario_possible_scores(results)
    dimension_scores = _dimension_scores(results)
    failed_items = _failed_items(results)

    lines = [
        "# 评测报告 %s" % run_id,
        "",
        "## 任务概览",
        "- 任务：%s" % task_spec.task_name,
        "- 角色：%s" % task_spec.role,
        "- 目标用户：%s" % task_spec.target_user,
        "- 任务目标：%s" % task_spec.task_goal,
        "- 开场白：%s" % task_spec.opening_line,
        "",
        "## 输入数据摘要",
        "- 数据格式：%s" % _input_value(input_data_summary, "format", "empty"),
        "- 字段数：%s" % _input_value(input_data_summary, "field_count", 0),
        "- 行数：%s" % _input_value(input_data_summary, "line_count", 0),
        "- 字符数：%s" % _input_value(input_data_summary, "char_count", 0),
        "- 预览：%s" % _input_value(input_data_summary, "preview", "未提供评测数据"),
        "",
        "## 量化结果",
        "- 总分：%s/%s" % (total_score, possible_score),
        "- 百分制标准化分：%s/%d" % (pass_rate, SCORING_SCALE),
        "- 通过率：%s%%" % pass_rate,
        "- 平均分：%s" % average_score,
        "- 场景数：%d" % len(scenario_set.scenarios),
        "- 已评测场景数：%d" % len(results),
        "- 高风险失败数：%d" % sum(len(result.critical_failures) for result in results),
        "- 失败评测项数：%d" % len(failed_items),
        "",
        "## 维度得分",
        "| 维度 | 得分 | 通过率 |",
        "| --- | --- | --- |",
    ]

    if dimension_scores:
        for dimension in sorted(dimension_scores):
            score, max_score = dimension_scores[dimension]
            rate = normalized_percent(score, max_score)
            lines.append("| %s | %d/%d | %s%% |" % (dimension, score, max_score, rate))
    else:
        lines.append("| 暂无 | 0/0 | 0.0% |")

    lines.extend(
        [
            "",
            "## 场景覆盖矩阵",
            "| 场景 | 覆盖目标 | 测试重点 | 结果 | 得分 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    result_by_scenario = {result.scenario_id: result for result in results}
    for scenario in scenario_set.scenarios:
        result = result_by_scenario.get(scenario.scenario_id)
        if result is None:
            status = "未运行"
            score = "-"
        else:
            status = "高风险失败" if result.critical_failures else "已评测"
            score = "%d/%d" % (
                result.total_score,
                scenario_possible_scores.get(result.scenario_id, 0),
            )
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (
                scenario.scenario_id,
                ", ".join(scenario.coverage_targets),
                scenario.expected_test_focus,
                status,
                score,
            )
        )

    lines.extend(["", "## 失败项摘要"])
    if failed_items:
        lines.extend(
            [
                "| 场景 | 评测项 | 结论 | 得分 | 指令依据 | 证据轮次 | 原因 |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for scenario_id, item in failed_items:
            lines.append(
                "| %s | %s | %s | %d/%d | %s | %s | %s |"
                % (
                    scenario_id,
                    item.rubric_item_id,
                    item.verdict,
                    item.score,
                    item.max_score,
                    item.source,
                    _turn_refs(item.turn_ids),
                    item.reason,
                )
            )
    else:
        lines.append("未发现失败项。")

    lines.extend(["", "## 风险归因"])
    lines.extend(_risk_attribution_lines(results, failed_items))

    lines.extend(["", "## 低分原因排序"])
    lines.extend(_prioritized_low_score_lines(results, failed_items))

    if quality_summary:
        lines.extend(["", "## 评测系统可靠性"])
        lines.extend(_quality_summary_lines(quality_summary))

    lines.extend(["", "## 改进建议"])
    lines.extend(_recommendations(results, failed_items))

    lines.extend(["", "## 证据链"])
    if not results:
        lines.append("暂无评测结果。")

    for result in results:
        lines.append("### 场景 %s" % result.scenario_id)
        lines.append(
            "- 总分：%d/%d"
            % (result.total_score, scenario_possible_scores.get(result.scenario_id, 0))
        )
        if result.critical_failures:
            lines.append("- 高风险失败：%s" % ", ".join(result.critical_failures))
        for item in result.evidence:
            turn_refs = _turn_refs(item.turn_ids)
            lines.extend(
                [
                    "- 评测项：%s" % item.rubric_item_id,
                    "  - 结论：%s" % item.verdict,
                    "  - 得分：%d/%d" % (item.score, item.max_score),
                    "  - Rubric 来源：%s" % item.source,
                    "  - 指令依据：%s" % _evidence_value(item.instruction_quote, item.source),
                    "  - 预期行为：%s" % _evidence_value(item.expected_behavior, item.reason),
                    "  - 实际对话证据：%s"
                    % _evidence_value(item.actual_behavior, turn_refs),
                    "  - 对话证据：%s" % turn_refs,
                    "  - 判定解释：%s" % _evidence_value(item.explanation, item.reason),
                    "  - 原因：%s" % item.reason,
                ]
            )

    markdown = "\n".join(lines) + "\n"
    return Report(run_id=run_id, task_id=task_spec.task_id, markdown=markdown)


def _possible_score(results: list[EvaluationResult]) -> int:
    return sum(item.max_score for result in results for item in result.evidence)


def _input_value(
    input_data_summary: Optional[dict[str, object]],
    key: str,
    default: object,
) -> object:
    if not input_data_summary:
        return default
    return input_data_summary.get(key, default)


def _evidence_value(value: str, fallback: str) -> str:
    return value if value else fallback


def _scenario_possible_scores(results: list[EvaluationResult]) -> dict[str, int]:
    return {
        result.scenario_id: sum(item.max_score for item in result.evidence)
        for result in results
    }


def _dimension_scores(results: list[EvaluationResult]) -> dict[str, tuple[int, int]]:
    dimensions = {}
    for result in results:
        for dimension, score in result.dimension_scores.items():
            current_score, current_max = dimensions.get(dimension, (0, 0))
            dimensions[dimension] = (current_score + score, current_max)
        for item in result.evidence:
            dimension = _dimension_for_evidence(item, result.dimension_scores)
            score, max_score = dimensions.get(dimension, (0, 0))
            dimensions[dimension] = (score, max_score + item.max_score)
    return dimensions


def _dimension_for_evidence(
    evidence: EvidenceItem,
    dimension_scores: dict[str, int] | None = None,
) -> str:
    return _dimension_for_item(
        evidence.rubric_item_id,
        dimension_scores,
        " ".join(
            [
                evidence.instruction_quote,
                evidence.source,
                evidence.reason,
                evidence.expected_behavior,
            ]
        ),
    )


def _dimension_for_item(
    rubric_item_id: str,
    dimension_scores: dict[str, int] | None = None,
    evidence_text: str = "",
) -> str:
    dimension_scores = dimension_scores or {}
    if rubric_item_id.startswith("step_"):
        return "task_completion"
    if rubric_item_id.startswith("process_"):
        return "process_adherence"
    if rubric_item_id.startswith("constraint_"):
        if "conversation_quality" in dimension_scores and "constraint_following" not in dimension_scores:
            return "conversation_quality"
        if "constraint_following" in dimension_scores and "conversation_quality" not in dimension_scores:
            return "constraint_following"
        if (
            "conversation_quality" in dimension_scores
            and ("30" in evidence_text or "字" in evidence_text or "长度" in evidence_text)
        ):
            return "conversation_quality"
        if (
            "constraint_following" in dimension_scores
            and ("超出职责范围" in evidence_text or "约束" in evidence_text)
        ):
            return "constraint_following"
        return "communication_quality"
    if rubric_item_id.startswith("faq_"):
        return "knowledge_accuracy"
    if rubric_item_id.startswith("edge_"):
        return "edge_case_handling"
    if rubric_item_id.startswith("forbidden_"):
        if "boundary_safety" in dimension_scores:
            return "boundary_safety"
        return "safety_boundary"
    return "other"


def _failed_items(results: list[EvaluationResult]) -> list[tuple[str, EvidenceItem]]:
    failed = []
    for result in results:
        for item in result.evidence:
            if item.verdict in ("fail", "partial", "needs_review"):
                failed.append((result.scenario_id, item))
    return failed


def _recommendations(
    results: list[EvaluationResult],
    failed_items: list[tuple[str, EvidenceItem]],
) -> list[str]:
    if not results:
        return ["- 暂无运行结果，需先完成评测。"]

    recommendations = []
    critical_failures = [
        item_id
        for result in results
        for item_id in result.critical_failures
    ]
    if critical_failures:
        recommendations.append(
            "- 优先修复高风险失败项：%s。"
            % ", ".join(_unique(critical_failures))
        )

    dimension_scores_by_scenario = {
        result.scenario_id: result.dimension_scores for result in results
    }
    failed_dimensions = _unique(
        _dimension_for_evidence(item, dimension_scores_by_scenario.get(scenario_id, {}))
        for scenario_id, item in failed_items
        if item.max_score > 0
    )
    if failed_dimensions:
        recommendations.append(
            "- 针对低分维度补充模型提示词或训练样例：%s。"
            % ", ".join(failed_dimensions)
        )

    no_evidence_count = sum(1 for _, item in failed_items if not item.turn_ids)
    if no_evidence_count:
        recommendations.append(
            "- 对无直接轮次证据的失败项，复查模型是否遗漏了对应流程或 FAQ。"
        )

    if not recommendations:
        recommendations.append("- 当前样例未发现失败项，可扩大场景集继续回归验证。")
    return recommendations


def _risk_attribution_lines(
    results: list[EvaluationResult],
    failed_items: list[tuple[str, EvidenceItem]],
) -> list[str]:
    if not failed_items:
        return ["未发现失败风险。"]

    dimension_scores_by_scenario = {
        result.scenario_id: result.dimension_scores for result in results
    }
    attribution: dict[str, dict[str, object]] = {}
    for scenario_id, item in failed_items:
        dimension = _dimension_for_evidence(
            item,
            dimension_scores_by_scenario.get(scenario_id, {}),
        )
        current = attribution.setdefault(
            dimension,
            {"count": 0, "lost_score": 0, "reasons": []},
        )
        current["count"] = int(current["count"]) + 1
        current["lost_score"] = int(current["lost_score"]) + max(
            0,
            item.max_score - item.score,
        )
        reasons = current["reasons"]
        if isinstance(reasons, list) and item.reason not in reasons:
            reasons.append(item.reason)

    lines = [
        "| 风险维度 | 失败项数 | 损失分 | 代表原因 |",
        "| --- | --- | --- | --- |",
    ]
    for dimension, data in sorted(
        attribution.items(),
        key=lambda pair: (-int(pair[1]["lost_score"]), pair[0]),
    ):
        reasons = data["reasons"] if isinstance(data["reasons"], list) else []
        lines.append(
            "| %s | %d | %d | %s |"
            % (
                dimension,
                int(data["count"]),
                int(data["lost_score"]),
                reasons[0] if reasons else "未提供原因",
            )
        )
    return lines


def _prioritized_low_score_lines(
    results: list[EvaluationResult],
    failed_items: list[tuple[str, EvidenceItem]],
) -> list[str]:
    if not failed_items:
        return ["未发现低分项。"]

    critical_by_scenario = {
        result.scenario_id: set(result.critical_failures) for result in results
    }
    ranked = sorted(
        failed_items,
        key=lambda pair: (
            0 if pair[1].rubric_item_id in critical_by_scenario.get(pair[0], set()) else 1,
            -(pair[1].max_score - pair[1].score),
            0 if not pair[1].turn_ids else 1,
            pair[0],
            pair[1].rubric_item_id,
        ),
    )
    lines = []
    for index, (scenario_id, item) in enumerate(ranked, start=1):
        labels = []
        if item.rubric_item_id in critical_by_scenario.get(scenario_id, set()):
            labels.append("高风险失败")
        if not item.turn_ids:
            labels.append("无直接轮次证据")
        if item.verdict == "needs_review":
            labels.append("需要人工复核")
        label_text = "；".join(labels) if labels else "普通失败"
        lines.append(
            "%d. [%s] %s / %s：损失 %d 分，%s。原因：%s"
            % (
                index,
                label_text,
                scenario_id,
                item.rubric_item_id,
                max(0, item.max_score - item.score),
                _turn_refs(item.turn_ids),
                item.reason,
            )
        )
    return lines


def _quality_summary_lines(summary: dict[str, object]) -> list[str]:
    scenario = _summary_section(summary, "scenario_coverage")
    judge = _summary_section(summary, "judge_integrity")
    evidence = _summary_section(summary, "evidence_traceability")
    timing = _summary_section(summary, "timing_health")
    lines = [
        "- 链路状态：%s" % summary.get("overall_status", "unknown"),
        "- 场景数：%s，场景多样性：%s"
        % (scenario.get("scenario_count", 0), scenario.get("diversity_score", 0)),
        "- Judge 漏项：%s，分数溢出：%s"
        % (judge.get("missing_item_count", 0), judge.get("score_overflow_count", 0)),
        "- 证据轮次命中率：%s%%" % evidence.get("traceable_evidence_rate", 0.0),
        "- 总耗时：%sms，慢阶段数：%s"
        % (timing.get("total_duration_ms", 0), len(timing.get("slow_stages", []))),
    ]
    auto_repair = _summary_section(summary, "auto_repair")
    if auto_repair.get("attempted"):
        lines.append(
            "- 后端自动修复：已重试 %s 次，%s -> %s"
            % (
                auto_repair.get("attempt_count", 0),
                auto_repair.get("before_status", "unknown"),
                auto_repair.get("after_status", "unknown"),
            )
        )
    return lines


def append_quality_summary_section(markdown: str, summary: dict[str, object]) -> str:
    if not summary or "## 评测系统可靠性" in markdown:
        return markdown
    section = "\n".join(["", "## 评测系统可靠性"] + _quality_summary_lines(summary))
    return markdown.rstrip() + "\n" + section + "\n"


def _summary_section(summary: dict[str, object], key: str) -> dict[str, object]:
    value = summary.get(key, {})
    return value if isinstance(value, dict) else {}


def _unique(values) -> list[str]:
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _turn_refs(turn_ids: list[int]) -> str:
    if not turn_ids:
        return "无直接轮次证据"
    return "、".join("第 %d 轮" % turn_id for turn_id in turn_ids)
