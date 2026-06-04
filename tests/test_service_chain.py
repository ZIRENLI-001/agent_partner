from fastapi.testclient import TestClient

from backend.eval_agent.api.main import create_app


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
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的飞毛腿报名中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。
"""


def test_backend_frontend_service_chain_supports_full_smoke_run(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    app = create_app()
    client = TestClient(app)

    home = client.get("/")
    evaluation_page = client.get("/evaluation")
    context = client.get("/api/context")
    parse = client.post(
        "/api/stages/parse",
        json={"instruction": RAW_TASK, "input_data": "{\"city\":\"北京\"}"},
    )
    created = client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "input_data": "{\"city\":\"北京\"}",
            "model_config": {"model_name": "chain-test-model"},
            "minimum_scenarios": 5,
        },
    )
    run_id = created.json()["run_id"]
    history = client.get("/api/runs/history")
    detail = client.get(f"/api/runs/{run_id}")

    assert home.status_code == 200
    assert evaluation_page.status_code == 200
    assert context.json()["project"]["name"] == "美团履约外呼评测"
    assert parse.json()["input_data_summary"]["format"] == "json"
    assert created.status_code == 200
    assert created.json()["trace_count"] == 5
    assert created.json()["result_count"] == 5
    assert "总分" in created.json()["report"]
    assert history.json()["runs"][0]["run_id"] == run_id
    assert detail.json()["model_config_summary"]["model_name"] == "chain-test-model"


def test_service_exposes_run_comparison_payload(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    app = create_app()
    client = TestClient(app)

    client.post(
        "/api/runs",
        json={
            "instruction": RAW_TASK,
            "model_config": {"model_name": "chain-comparison-model"},
        },
    )
    response = client.get("/api/runs/comparison")

    assert response.status_code == 200
    data = response.json()
    assert data["scenario_rows"]
    assert data["filters"]["model_names"] == ["chain-comparison-model"]
