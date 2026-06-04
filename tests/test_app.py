import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.evaluation_engine import app as web_app


RAW_TASK = """# Role
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
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。
"""


def test_index_serves_meituan_wizard_html():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "美团履约评测" in response.text
    assert "评测模型" in response.text
    assert "导入数据与场景" in response.text
    assert "指令解析" in response.text
    assert "Rubric 生成" in response.text
    assert "测试场景" in response.text
    assert "轨迹与结果" in response.text
    assert "可视化报告" in response.text
    assert "data-step=\"model\"" in response.text
    assert "data-step=\"data\"" in response.text
    assert "data-step=\"parse\"" in response.text
    assert "data-step=\"rubric\"" in response.text
    assert "data-step=\"scenarios\"" in response.text
    assert "data-step=\"run\"" in response.text
    assert "data-step=\"report\"" in response.text
    assert "模型 API Base" in response.text
    assert "加载美团履约样例" in response.text
    assert "生成" in response.text
    assert "下一步" in response.text
    assert "进入下一步" not in response.text


def test_backend_api_entrypoint_reuses_current_fastapi_app():
    from backend.eval_agent.api.main import app as backend_app

    client = TestClient(backend_app)
    response = client.get("/")

    assert response.status_code == 200
    assert "美团履约评测" in response.text


def test_engine_app_exposes_calibration_dataset_api():
    client = TestClient(web_app.app)

    summary = client.get("/api/calibration/summary")
    samples = client.get("/api/calibration/samples")

    assert summary.status_code == 200
    assert samples.status_code == 200
    assert summary.json()["sample_count"] >= 10
    assert "L5" in summary.json()["difficulty_counts"]
    assert samples.json()["summary"]["evidence_coverage_rate"] == 1.0
    assert samples.json()["samples"][0]["expected_labels"]


def test_engine_app_exposes_reusable_run_payload_helpers():
    assert callable(web_app._run_response_payload)
    assert callable(web_app._run_history_payload)
    assert callable(web_app._run_detail_payload)


def test_index_exposes_production_editability_controls():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "generatedSteps" in response.text
    assert "人工校准入口" in response.text
    assert "重新生成解析结果" in response.text
    assert "重新生成 Rubric" in response.text
    assert "重新生成测试场景" in response.text
    assert "重新运行评测" in response.text
    assert "对话轨迹和评分证据不可直接编辑" in response.text


def test_index_exposes_home_mode_selection():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "global-nav" in response.text
    assert "aria-label=\"全局导航\"" in response.text
    assert "data-global-view=\"home\"" in response.text
    assert "data-global-view=\"wizard\"" in response.text
    assert "data-global-view=\"history\"" in response.text
    assert "首页" in response.text
    assert "可视化评测" in response.text
    assert "复杂指令可视化评测流程" in response.text
    assert "评测链路" in response.text
    assert "历史评测" in response.text
    assert "端到端快速评测" in response.text
    assert "分阶段评测" in response.text
    assert "评测历史" in response.text
    assert "评测记录按项目隔离保存" in response.text
    assert "compact-home" in response.text
    assert "home-capability-grid" in response.text
    assert "指令解析" in response.text
    assert "用户模拟" in response.text
    assert "证据报告" in response.text


def test_index_uses_light_navigation_and_collapsible_results():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "background: #151515" not in response.text
    assert "background: #191919" not in response.text
    assert "global-nav light-nav" in response.text
    assert "scenario-accordion" in response.text
    assert "result-summary-row" in response.text
    assert "<details class=\"scenario-accordion\"" in response.text


def test_index_hides_internal_isolation_ids_from_visible_ui():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "当前用户：demo_user" not in response.text
    assert "workspace_demo / project_meituan_fulfillment" not in response.text
    assert "当前隔离上下文" not in response.text
    assert "Workspace：" not in response.text
    assert "Project：" not in response.text
    assert "评测记录按项目隔离保存" in response.text


def test_index_paginates_history_runs():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "historyPageSize: 5" in response.text
    assert "history-page-controls" in response.text
    assert "history-prev-page" in response.text
    assert "history-next-page" in response.text
    assert "history-page-indicator" in response.text
    assert "history-panel" in response.text
    assert "historyPageSize: 5" in response.text
    assert "返回首页" not in response.text


def test_index_supports_collapsible_sidebar_and_full_height_home():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "sidebarCollapsed" in response.text
    assert "nav-toggle" in response.text
    assert "收起侧栏" in response.text
    assert "展开侧栏" in response.text
    assert "‹" in response.text
    assert "›" in response.text
    assert "sidebar-collapsed" in response.text
    assert "min-height: calc(100vh - 112px)" in response.text


def test_home_action_buttons_use_hover_yellow_not_default_yellow():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "home-action-button" in response.text
    assert ".home-action-button:hover" in response.text
    assert "background: var(--mt-yellow)" in response.text
    assert "开始快速评测</button>" in response.text


def test_home_balances_large_hero_with_compact_action_cards():
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "font-size: 30px" in response.text
    assert "home-card-tags" in response.text
    assert "min-height: 118px" in response.text
    assert "grid-template-rows: auto" in response.text
    assert "home-icon" in response.text
    assert "icon-sprite" in response.text
    assert "use href=\"#icon-zap\"" in response.text
    assert "min-height: 360px" in response.text
    assert "M6 6h4v4H6V6Z" in response.text


def test_context_endpoint_returns_demo_isolation_context():
    client = TestClient(web_app.app)

    response = client.get("/api/context")

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["user_id"] == "demo_user"
    assert data["workspace"]["workspace_id"] == "workspace_demo"
    assert data["project"]["project_id"] == "project_meituan_fulfillment"


def test_create_run_returns_quantitative_report(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post("/api/runs", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"].startswith("run_")
    assert data["trace_count"] >= 5
    assert data["result_count"] == data["trace_count"]
    assert "总分" in data["report"]
    assert (tmp_path / data["run_id"] / "report.md").exists()


def test_create_run_returns_quality_summary_and_persists_artifact(
    tmp_path: Path, monkeypatch
):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={
            "instruction": "# Role\n你是站长。\n# Task\n通知合同生效。\n# Opening Line\n你好",
            "minimum_scenarios": 2,
            "model_config": {"provider": "mock", "model_name": "mock"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_summary"]["overall_status"] in {"pass", "warn", "fail"}
    assert "scenario_coverage" in payload["quality_summary"]
    assert "evidence_traceability" in payload["quality_summary"]
    assert "评测系统可靠性" in payload["report"]
    assert (tmp_path / payload["run_id"] / "quality_summary.json").exists()


def test_create_run_persists_context_metadata(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "workspace_id": "workspace_a",
            "project_id": "project_b",
            "created_by": "user_c",
        },
    )

    assert response.status_code == 200
    data = response.json()
    config = json.loads((tmp_path / data["run_id"] / "run_config.json").read_text())
    assert config["workspace_id"] == "workspace_a"
    assert config["project_id"] == "project_b"
    assert config["created_by"] == "user_c"
    assert data["run_context"]["workspace_id"] == "workspace_a"


def test_run_history_and_detail_endpoints_return_persisted_runs(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    created = client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "model_config": {"model_name": "history-model"},
            "workspace_id": "workspace_hist",
            "project_id": "project_hist",
            "created_by": "history_user",
        },
    ).json()

    history_response = client.get("/api/runs/history")

    assert history_response.status_code == 200
    history = history_response.json()
    assert history["runs"]
    assert history["runs"][0]["run_id"] == created["run_id"]
    assert history["runs"][0]["workspace_id"] == "workspace_hist"
    assert history["runs"][0]["project_id"] == "project_hist"
    assert history["runs"][0]["created_by"] == "history_user"
    assert history["runs"][0]["model_name"] == "history-model"

    detail_response = client.get(f"/api/runs/{created['run_id']}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["run_id"] == created["run_id"]
    assert detail["task_spec"]["required_steps"]
    assert detail["report"]
    assert detail["quality_summary"]["overall_status"] in {"pass", "warn", "fail"}
    assert "remediation_actions" in detail["quality_summary"]

    quality_path = tmp_path / created["run_id"] / "quality_summary.json"
    stale_quality = json.loads(quality_path.read_text())
    stale_quality.pop("remediation_actions", None)
    quality_path.write_text(json.dumps(stale_quality), encoding="utf-8")

    stale_detail_response = client.get(f"/api/runs/{created['run_id']}")
    assert stale_detail_response.status_code == 200
    stale_detail = stale_detail_response.json()
    assert "remediation_actions" in stale_detail["quality_summary"]


def test_optimization_insights_are_sample_library_driven():
    scenario_set = {
        "scenarios": [
            {
                "scenario_id": "course_latency_case",
                "scenario_type": "course_latency_price_faq",
                "coverage_targets": ["latency_difference", "price_boundary"],
                "risk_tags": ["low_latency_live", "price_explanation"],
                "expected_test_focus": "回答标准直播和低延迟直播差异",
            }
        ]
    }
    results = [
        {
            "scenario_id": "course_latency_case",
            "critical_failures": ["latency_difference"],
            "dimension_scores": {},
            "evidence": [
                {
                    "rubric_item_id": "latency_difference",
                    "verdict": "fail",
                    "score": 0,
                    "max_score": 3,
                    "source": "TaskSpec",
                    "reason": "未说明标准直播和低延迟直播延迟差异",
                    "turn_ids": [3],
                    "expected_behavior": "说明延迟、适用课型和价格差异",
                    "actual_behavior": "只询问客户课程类型，没有回答差异",
                }
            ],
        }
    ]

    insights = web_app._optimization_insights_from_dicts(
        scenario_set=scenario_set,
        results=results,
        quality_summary={},
        stage_diagnostics={},
    )

    assert insights
    insight = insights[0]
    assert insight["category"] == "prompt"
    assert "course_latency_price_faq" in insight["business_context"]
    assert "latency_difference" in insight["business_context"]
    assert "回答标准直播和低延迟直播的延迟" in insight["sample_task_instruction"]
    assert any(ref["domain"] == "course_publishing" for ref in insight["sample_references"])
    assert "低延迟直播" in insight["recommended_action"]
    assert "缺失" in insight["issue_summary"]
    assert "latency_difference" in insight["issue_summary"]
    assert "course_publishing" in insight["evidence_summary"]
    assert "把" in insight["next_action"]
    assert "低延迟直播" in insight["next_action"]


def test_run_comparison_endpoint_returns_scenario_rows_and_filters(
    tmp_path: Path, monkeypatch
):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    first = client.post(
        "/api/runs",
        json={"instruction": RAW_TASK, "model_config": {"model_name": "model-a"}},
    ).json()
    second = client.post(
        "/api/runs",
        json={"instruction": RAW_TASK, "model_config": {"model_name": "model-b"}},
    ).json()

    response = client.get("/api/runs/comparison")

    assert response.status_code == 200
    data = response.json()
    assert {first["run_id"], second["run_id"]} <= {
        item["run_id"] for item in data["runs"]
    }
    assert data["scenario_rows"]
    assert {"model-a", "model-b"} <= set(data["filters"]["model_names"])
    assert data["filters"]["scenario_ids"]
    assert all("raw_pass_rate" in item for item in data["scenario_rows"])
    assert all("score_anomaly" in item for item in data["scenario_rows"])
    assert all(item["pass_rate"] <= 100 for item in data["scenario_rows"])


def test_run_comparison_endpoint_returns_sample_driven_optimization_summary(
    tmp_path: Path, monkeypatch
):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)
    run_dir = tmp_path / "run_course_compare"
    run_dir.mkdir()
    (run_dir / "run_config.json").write_text(
        json.dumps(
            {
                "model_config_summary": {"model_name": "compare-model"},
                "workspace_id": "workspace_demo",
                "project_id": "project_meituan_fulfillment",
                "created_by": "demo_user",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "task_spec.json").write_text(
        json.dumps(
            {
                "task_name": "回答标准直播和低延迟直播差异",
                "task_goal": "回答标准直播和低延迟直播的延迟、适用课型和价格差异。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "scenarios.json").write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "task_001_latency_faq",
                        "user_profile": {"role": "机构负责人"},
                        "initial_user_intent": "客户询问标准直播和低延迟直播差异",
                        "focus_points": [
                            "course_latency_price_faq",
                            "latency_difference",
                        ],
                        "expected_risks": ["low_latency_live"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "evaluation_results.json").write_text(
        json.dumps(
            [
                {
                    "scenario_id": "task_001_latency_faq",
                    "total_score": 0,
                    "critical_failures": ["latency_difference"],
                    "evidence": [
                        {
                            "rubric_item_id": "latency_difference",
                            "verdict": "fail",
                            "score": 0,
                            "max_score": 3,
                            "reason": "未说明标准直播和低延迟直播延迟差异",
                            "expected_behavior": "说明延迟、适用课型和价格差异",
                            "actual_behavior": "只询问课程类型，没有回答差异",
                            "turn_ids": [3],
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    response = client.get("/api/runs/comparison")

    assert response.status_code == 200
    insights = response.json()["optimization_insights"]
    assert insights
    first = insights[0]
    assert first["category_label"] in {"提示词优化", "算法链路优化"}
    assert "course_publishing" in first["business_context"]
    assert "latency_difference" in first["business_context"]
    assert "低延迟直播" in first["recommended_action"]
    assert first["examples"][0]["run_id"] == "run_course_compare"


def test_comparison_scenario_row_marks_score_anomaly():
    row = web_app._comparison_scenario_row(
        run_id="run_demo",
        task_name="Demo",
        task_goal="Demo goal",
        model_name="model-a",
        updated_at=100,
        result={
            "scenario_id": "scenario_001",
            "total_score": 12,
            "critical_failures": ["missing_confirmation"],
            "evidence": [{"max_score": 10}],
        },
    )

    assert row["raw_pass_rate"] == 120.0
    assert row["pass_rate"] == 100.0
    assert row["score_anomaly"] is True


def test_create_run_returns_stage_artifacts_for_explainable_workflow(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post("/api/runs", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["task_spec"]["required_steps"]
    assert data["rubric_spec"]["items"]
    assert len(data["scenario_set"]["scenarios"]) >= 5
    assert len(data["traces"]) == len(data["scenario_set"]["scenarios"])
    assert len(data["results"]) == len(data["traces"])
    assert data["stages"][0]["name"] == "指令解析"
    assert data["stages"][-1]["name"] == "报告生成"
    assert all(stage["status"] == "completed" for stage in data["stages"])


def test_create_run_returns_visual_report_summaries(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post("/api/runs", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["score_summary"]["total_score"] >= 0
    assert data["score_summary"]["possible_score"] > 0
    assert "pass_rate" in data["score_summary"]
    assert data["dimension_summary"]
    assert all("dimension" in item for item in data["dimension_summary"])
    assert all("score" in item for item in data["dimension_summary"])
    assert data["scenario_summary"]
    assert all("scenario_id" in item for item in data["scenario_summary"])
    assert all("score" in item for item in data["scenario_summary"])
    assert all("pass_rate" in item for item in data["scenario_summary"])
    assert "failure_summary" in data
    assert isinstance(data["failure_summary"], list)


def test_scenario_summary_returns_truthful_pass_rate():
    scenarios = {
        "scenarios": [
            {
                "scenario_id": "scenario_001",
                "coverage_targets": ["normal"],
                "expected_test_focus": "基础流程",
            }
        ]
    }
    results = [
        {
            "scenario_id": "scenario_001",
            "total_score": 7,
            "evidence": [
                {"max_score": 4},
                {"max_score": 6},
            ],
            "critical_failures": [],
        }
    ]

    summary = web_app._scenario_summary_from_dicts(scenarios, results)

    assert summary[0]["score"] == 7
    assert summary[0]["possible_score"] == 10
    assert summary[0]["pass_rate"] == 70.0


def test_dimension_summary_uses_rubric_dimensions_for_truthful_pass_rates():
    result = {
        "trace_id": "trace_001",
        "scenario_id": "scenario_001",
        "total_score": 8,
        "dimension_scores": {
            "conversation_quality": 5,
            "constraint_following": 3,
        },
        "evidence": [
            {
                "rubric_item_id": "constraint_length",
                "verdict": "pass",
                "source": "Constraints 第1条",
                "turn_ids": [1],
                "reason": "长度符合要求",
                "score": 5,
                "max_score": 5,
                "instruction_quote": "每次回复控制在约 30 个字以内",
            },
            {
                "rubric_item_id": "constraint_boundary",
                "verdict": "pass",
                "source": "Constraints 第2条",
                "turn_ids": [2],
                "reason": "未超出职责范围",
                "score": 3,
                "max_score": 3,
                "instruction_quote": "超出职责范围的问题确认后再回电",
            },
        ],
        "critical_failures": [],
    }
    rubric = {
        "items": [
            {"item_id": "constraint_length", "dimension": "conversation_quality"},
            {"item_id": "constraint_boundary", "dimension": "constraint_following"},
        ]
    }

    summary = web_app._dimension_summary_from_dicts([result], rubric)

    assert summary == [
        {
            "dimension": "constraint_following",
            "score": 3,
            "possible_score": 3,
            "pass_rate": 100.0,
        },
        {
            "dimension": "conversation_quality",
            "score": 5,
            "possible_score": 5,
            "pass_rate": 100.0,
        },
    ]


def test_create_run_accepts_input_data_and_persists_it(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "input_data": '{"rider_id":"r_001","contract_status":"active"}',
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["input_data_summary"]["format"] == "json"
    assert data["input_data_summary"]["field_count"] == 2
    assert (tmp_path / data["run_id"] / "input_data.json").exists()
    assert "输入数据摘要" in data["report"]


def test_sample_tasks_endpoint_returns_excel_examples():
    client = TestClient(web_app.app)

    response = client.get("/api/sample-tasks")

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"]
    assert data["tasks"][0]["id"] == "1"
    assert "飞毛腿" in data["tasks"][0]["instruction"]


def test_stage_parse_returns_task_spec_and_input_summary():
    client = TestClient(web_app.app)

    response = client.post(
        "/api/stages/parse",
        json={
            "instruction": RAW_TASK,
            "input_data": '{"rider_id":"r_001","contract_status":"active"}',
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "parse"
    assert data["task_spec"]["required_steps"]
    assert data["input_data_summary"]["format"] == "json"
    assert data["input_data_summary"]["field_count"] == 2


def test_stage_rubric_returns_quantitative_items():
    client = TestClient(web_app.app)

    response = client.post("/api/stages/rubric", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "rubric"
    assert data["rubric_spec"]["items"]
    assert all("weight" in item for item in data["rubric_spec"]["items"])
    assert all("criterion" in item for item in data["rubric_spec"]["items"])


def test_stage_scenarios_returns_meituan_scenario_set():
    client = TestClient(web_app.app)

    response = client.post("/api/stages/scenarios", json={"instruction": RAW_TASK})

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "scenarios"
    assert len(data["scenario_set"]["scenarios"]) >= 5
    assert all("coverage_targets" in item for item in data["scenario_set"]["scenarios"])


def test_create_run_accepts_model_config_summary(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "model_config": {
                "provider": "openai_compatible",
                "model_name": "demo-model",
                "api_base": "https://example.com/v1",
                "api_key": "sk-secret",
                "judge_mode": "hybrid",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model_config_summary"]["provider"] == "openai_compatible"
    assert data["model_config_summary"]["model_name"] == "demo-model"
    assert data["model_config_summary"]["api_key_configured"] is True
    assert "sk-secret" not in json.dumps(data["model_config_summary"], ensure_ascii=False)


def test_create_run_can_filter_selected_scenarios(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    response = client.post(
        "/api/runs",
        json={"instruction": RAW_TASK, "selected_scenario_ids": ["task_001_normal_completion"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trace_count"] == 1
    assert data["result_count"] == 1
    assert data["traces"][0]["scenario_id"] == "task_001_normal_completion"
