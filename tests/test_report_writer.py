from backend.evaluation_engine.domain import (
    EvaluationResult,
    EvidenceItem,
    Report,
    Scenario,
    ScenarioSet,
    TaskSpec,
)
from backend.evaluation_engine.report_writer import write_markdown_report


def test_report_contains_quantitative_and_explainable_sections():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["normal_completion"],
                initial_user_intent="正常确认",
                expected_test_focus="基础流程",
            )
        ],
    )
    result = EvaluationResult(
        trace_id="trace_001",
        scenario_id="scenario_normal",
        total_score=8,
        dimension_scores={"task_completion": 8},
        evidence=[
            EvidenceItem(
                rubric_item_id="r1",
                verdict="pass",
                source="Call Flow 第1步",
                turn_ids=[1],
                reason="模型明确说明合同生效",
                score=8,
                max_score=8,
            )
        ],
        critical_failures=[],
    )

    report = write_markdown_report(
        "run_001",
        task,
        scenarios,
        [result],
        input_data_summary={"format": "json", "field_count": 2, "preview": "rider_id"},
    )

    assert isinstance(report, Report)
    assert "总分" in report.markdown
    assert "场景覆盖矩阵" in report.markdown
    assert "输入数据摘要" in report.markdown
    assert "字段数：2" in report.markdown
    assert "Call Flow 第1步" in report.markdown
    assert "第 1 轮" in report.markdown


def test_report_summarizes_dimensions_failures_and_recommendations():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["normal_completion"],
                initial_user_intent="正常确认",
                expected_test_focus="基础流程",
            ),
            Scenario(
                scenario_id="scenario_reward",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["reward_question", "boundary_no_extra_promise"],
                initial_user_intent="询问奖励",
                expected_test_focus="奖励边界",
            ),
        ],
    )
    results = [
        EvaluationResult(
            trace_id="trace_001",
            scenario_id="scenario_normal",
            total_score=15,
            dimension_scores={"task_completion": 10, "communication_quality": 5},
            evidence=[
                EvidenceItem(
                    rubric_item_id="step_01",
                    verdict="pass",
                    source="Call Flow 第1步",
                    turn_ids=[3],
                    reason="模型明确说明合同生效",
                    score=10,
                    max_score=10,
                ),
                EvidenceItem(
                    rubric_item_id="constraint_01",
                    verdict="pass",
                    source="Constraints 第1条",
                    turn_ids=[1, 3],
                    reason="回复长度符合要求",
                    score=5,
                    max_score=5,
                ),
            ],
            critical_failures=[],
        ),
        EvaluationResult(
            trace_id="trace_002",
            scenario_id="scenario_reward",
            total_score=0,
            dimension_scores={"safety_boundary": 0},
            evidence=[
                EvidenceItem(
                    rubric_item_id="forbidden_01",
                    verdict="fail",
                    source="Forbidden Actions 第1条",
                    turn_ids=[4],
                    reason="助手承诺了额外奖励",
                    score=0,
                    max_score=0,
                ),
                EvidenceItem(
                    rubric_item_id="forbidden_01",
                    verdict="fail",
                    source="Forbidden Actions 第1条",
                    turn_ids=[],
                    reason="未找到支持语义证据",
                    score=0,
                    max_score=20,
                ),
            ],
            critical_failures=["forbidden_01"],
        ),
    ]

    report = write_markdown_report("run_001", task, scenarios, results)

    assert "通过率" in report.markdown
    assert "## 维度得分" in report.markdown
    assert "| task_completion | 10/10 | 100.0% |" in report.markdown
    assert "| safety_boundary | 0/20 | 0.0% |" in report.markdown
    assert "| scenario_reward | reward_question, boundary_no_extra_promise | 奖励边界 | 高风险失败 | 0/20 |" in report.markdown
    assert "## 失败项摘要" in report.markdown
    assert "forbidden_01" in report.markdown
    assert "Forbidden Actions 第1条" in report.markdown
    assert "## 改进建议" in report.markdown
    assert "优先修复高风险失败项" in report.markdown


def test_report_dimension_scores_use_evidence_dimension_metadata():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["normal_completion"],
                initial_user_intent="正常确认",
                expected_test_focus="基础流程",
            )
        ],
    )
    result = EvaluationResult(
        trace_id="trace_001",
        scenario_id="scenario_normal",
        total_score=11,
        dimension_scores={"conversation_quality": 5, "process_adherence": 6},
        evidence=[
            EvidenceItem(
                rubric_item_id="constraint_01",
                verdict="pass",
                source="Constraints 第1条",
                turn_ids=[1],
                reason="规则检查通过",
                score=5,
                max_score=5,
            ),
            EvidenceItem(
                rubric_item_id="process_01",
                verdict="pass",
                source="Call Flow 第1步",
                turn_ids=[2],
                reason="语义检查通过",
                score=6,
                max_score=6,
            ),
        ],
    )

    report = write_markdown_report("run_001", task, scenarios, [result])

    assert "| conversation_quality | 5/5 | 100.0% |" in report.markdown
    assert "| process_adherence | 6/6 | 100.0% |" in report.markdown


def test_report_renders_full_explanation_chain_fields():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["normal_completion"],
                initial_user_intent="正常确认",
                expected_test_focus="基础流程",
            )
        ],
    )
    result = EvaluationResult(
        trace_id="trace_001",
        scenario_id="scenario_normal",
        total_score=0,
        dimension_scores={"task_completion": 0},
        evidence=[
            EvidenceItem(
                rubric_item_id="step_01",
                verdict="fail",
                source="Call Flow 第1步",
                turn_ids=[3],
                reason="模型未明确说明合同生效",
                score=0,
                max_score=10,
                instruction_quote="告知骑手今天飞毛腿合同已生效",
                expected_behavior="助手应明确告知合同今日生效",
                actual_behavior="助手仅提醒尽快上线配送",
                explanation="实际回复没有覆盖合同生效信息，因此该流程项失败",
            )
        ],
    )

    report = write_markdown_report("run_001", task, scenarios, [result])

    assert "指令依据：告知骑手今天飞毛腿合同已生效" in report.markdown
    assert "预期行为：助手应明确告知合同今日生效" in report.markdown
    assert "实际对话证据：助手仅提醒尽快上线配送" in report.markdown
    assert "判定解释：实际回复没有覆盖合同生效信息，因此该流程项失败" in report.markdown


def test_report_adds_risk_attribution_and_prioritized_low_score_reasons():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        scenarios=[
            Scenario(
                scenario_id="scenario_reward",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["reward_question", "boundary_no_extra_promise"],
                initial_user_intent="询问奖励",
                expected_test_focus="奖励边界",
            )
        ],
    )
    result = EvaluationResult(
        trace_id="trace_001",
        scenario_id="scenario_reward",
        total_score=2,
        dimension_scores={"boundary_safety": 0, "task_completion": 2},
        evidence=[
            EvidenceItem(
                rubric_item_id="forbidden_01",
                verdict="fail",
                source="Forbidden Actions 第1条",
                turn_ids=[3],
                reason="助手承诺了额外奖励",
                score=0,
                max_score=10,
                instruction_quote="不得承诺额外奖励",
                expected_behavior="拒绝额外奖励承诺",
                actual_behavior="第 3 轮：可以给你补贴",
                explanation="边界安全失败",
            ),
            EvidenceItem(
                rubric_item_id="step_01",
                verdict="partial",
                source="Call Flow 第1步",
                turn_ids=[],
                reason="未找到支持语义证据",
                score=2,
                max_score=6,
                instruction_quote="说明合同生效",
                expected_behavior="明确说明合同生效",
                actual_behavior="未找到支持该评测项的助手回复",
                explanation="证据不足",
            ),
        ],
        critical_failures=["forbidden_01"],
    )

    report = write_markdown_report("run_001", task, scenarios, [result])

    assert "## 风险归因" in report.markdown
    assert "| boundary_safety | 1 | 10 | 助手承诺了额外奖励 |" in report.markdown
    assert "## 低分原因排序" in report.markdown
    assert report.markdown.index("forbidden_01") < report.markdown.index("step_01")
    assert "高风险失败" in report.markdown
    assert "无直接轮次证据" in report.markdown


def test_report_renders_quality_summary_when_provided():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(suite_id="suite_001", task_id="task_001", scenarios=[])

    report = write_markdown_report(
        "run_001",
        task,
        scenarios,
        [],
        quality_summary={
            "overall_status": "warn",
            "scenario_coverage": {"scenario_count": 5, "diversity_score": 86.0},
            "judge_integrity": {"missing_item_count": 1, "score_overflow_count": 0},
            "evidence_traceability": {"traceable_evidence_rate": 92.5},
            "timing_health": {"total_duration_ms": 12000, "slow_stages": []},
            "auto_repair": {
                "attempted": True,
                "attempt_count": 1,
                "before_status": "fail",
                "after_status": "warn",
            },
        },
    )

    assert "## 评测系统可靠性" in report.markdown
    assert "链路状态：warn" in report.markdown
    assert "场景数：5" in report.markdown
    assert "证据轮次命中率：92.5%" in report.markdown
    assert "后端自动修复：已重试 1 次，fail -> warn" in report.markdown
